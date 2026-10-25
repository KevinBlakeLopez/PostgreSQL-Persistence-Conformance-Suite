"""SQLITE-01: SQLite ends a transaction itself. What does sqlite3 do next?

A BEFORE UPDATE trigger rejects a negative balance with RAISE(ABORT, ...) or
RAISE(ROLLBACK, ...). Inside one transaction the writer debits account 1 and
records ledger row A, then tries to debit account 2 below zero (the fault),
catches the error, optionally records ledger row B, and completes the
transaction. A next unit of work then runs on the same connection, writes N,
and rolls back.

Four sqlite3 transaction-control configurations:

    explicit     connect(autocommit=True); SQL BEGIN and SQL COMMIT
    legacy       connect() defaults: autocommit=LEGACY_TRANSACTION_CONTROL,
                 isolation_level=""; the driver begins before DML;
                 Connection.commit()
    legacy-none  connect(isolation_level=None); SQL BEGIN;
                 Connection.commit()  (the setting SQLAlchemy's BEGIN recipe
                 and Django's sqlite3 backend use)
    pep249       connect(autocommit=False); Connection.commit()

    .venv/bin/python -I repro/sqlite01_raw.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402


MODES = ("explicit", "legacy", "legacy-none", "pep249")
FAULTS = {
    # Same trigger body in every variant except the RAISE action; "none" keeps
    # the ROLLBACK trigger installed and debits an amount that does not fire it.
    "none": ("ROLLBACK", 50),
    "abort": ("ABORT", 500),
    "rollback": ("ROLLBACK", 500),
}
FOLLOW_UPS = ("write-b", "no-write")

# pep249 only: what an application could do, after the failed completion, to
# get the connection back into a transaction before the next unit of work.
RECOVERIES = {
    "rollback-call": lambda conn: conn.rollback(),
    "autocommit-reassign": lambda conn: setattr(conn, "autocommit", False),
    "autocommit-toggle": lambda conn: (setattr(conn, "autocommit", True), setattr(conn, "autocommit", False)),
    "sql-begin": lambda conn: conn.execute("BEGIN").rowcount,
}

TRIGGER = (
    "CREATE TRIGGER reject_invalid_balance BEFORE UPDATE ON accounts "
    "WHEN NEW.balance < 0 BEGIN SELECT RAISE({action}, 'negative balance'); END"
)


def queries(token: str) -> dict[str, str]:
    return {
        "balances": "SELECT id, balance FROM accounts ORDER BY id",
        "ledger": f"SELECT step FROM ledger WHERE token = '{token}' ORDER BY id",
    }


def setup(path: Path, action: str) -> None:
    connection = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)")
        connection.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY, token TEXT NOT NULL, step TEXT NOT NULL)")
        connection.execute(TRIGGER.format(action=action))
        connection.execute("INSERT INTO accounts(id, balance) VALUES (1, 100), (2, 100)")
    finally:
        connection.close()


def connect(path: Path, mode: str) -> sqlite3.Connection:
    if mode == "explicit":
        return sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    if mode == "legacy":
        connection = sqlite3.connect(str(path), timeout=0.0)
        assert connection.autocommit == sqlite3.LEGACY_TRANSACTION_CONTROL
        assert connection.isolation_level == ""
        return connection
    if mode == "legacy-none":
        return sqlite3.connect(str(path), timeout=0.0, isolation_level=None)
    if mode == "pep249":
        return sqlite3.connect(str(path), timeout=0.0, autocommit=False)
    raise ValueError(mode)


class Writer:
    def __init__(self, path: Path, mode: str, token: str):
        self.path = path
        self.mode = mode
        self.token = token
        self.conn = connect(path, mode)
        self.config = {
            "mode": mode,
            "autocommit": self.conn.autocommit,
            "isolation_level": self.conn.isolation_level,
            "in_transaction_at_connect": self.conn.in_transaction,
        }
        self.trace = common.Trace(self.conn)
        self.steps: list[dict[str, Any]] = []

    def step(self, label: str, fn: Callable[[], Any], **extra: Any) -> dict[str, Any]:
        start = len(self.trace.events)
        before = common.in_transaction(self.conn)
        entry = common.call(label, fn, **extra)
        entry["in_transaction_before"] = before
        entry["in_transaction_after"] = common.in_transaction(self.conn)
        entry["sql_started"] = self.trace.statements()[start:]
        self.steps.append(entry)
        return entry

    def sql(self, label: str, statement: str, params: tuple = ()) -> dict[str, Any]:
        return self.step(label, lambda: self.conn.execute(statement, params).rowcount, sql=statement)

    def begin(self, label: str) -> dict[str, Any] | None:
        if self.mode in ("explicit", "legacy-none"):
            return self.sql(label, "BEGIN")
        return None  # legacy: the driver begins before DML; pep249: already open

    def complete(self, label: str) -> dict[str, Any]:
        if self.mode == "explicit":
            return self.sql(label, "COMMIT")
        return self.step(label, self.conn.commit, method="Connection.commit()")

    def abandon(self, label: str) -> dict[str, Any]:
        if self.mode == "explicit":
            return self.sql(label, "ROLLBACK")
        return self.step(label, self.conn.rollback, method="Connection.rollback()")

    def own_view(self) -> dict[str, Any]:
        balances = [list(row) for row in self.conn.execute("SELECT id, balance FROM accounts ORDER BY id")]
        ledger = [row[0] for row in self.conn.execute(
            "SELECT step FROM ledger WHERE token = ? ORDER BY id", (self.token,))]
        return {"balances": balances, "ledger": ledger}


def scenario(mode: str, fault: str, follow_up: str, recovery: str | None = None) -> Callable[[Path, str], dict[str, Any]]:
    action, amount = FAULTS[fault]

    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        setup(path, action)
        q = queries(token)
        writer = Writer(path, mode, token)
        observers: dict[str, Any] = {}
        checkpoints: dict[str, Any] = {}
        try:
            writer.begin("begin")
            writer.sql("write-a-debit", "UPDATE accounts SET balance = balance - 30 WHERE id = 1")
            writer.sql("write-a-ledger", "INSERT INTO ledger(token, step) VALUES (?, 'A')", (token,))
            checkpoints["before-fault"] = {"in_transaction": writer.conn.in_transaction, "own_view": writer.own_view()}

            fault_step = writer.sql("fault", f"UPDATE accounts SET balance = balance - {amount} WHERE id = 2")
            checkpoints["after-fault"] = {"in_transaction": writer.conn.in_transaction, "own_view": writer.own_view()}
            observers["after-fault"] = common.observe(path, q)

            write_b = None
            if follow_up == "write-b":
                write_b = writer.sql("write-b", "INSERT INTO ledger(token, step) VALUES (?, 'B')", (token,))
                checkpoints["after-write-b"] = {"in_transaction": writer.conn.in_transaction}
                observers["after-write-b"] = common.observe(path, q)

            complete = writer.complete("complete")
            checkpoints["after-complete"] = {"in_transaction": writer.conn.in_transaction}
            observers["after-complete"] = common.observe(path, q)

            recovered = None
            if recovery is not None:
                recovered = writer.step("recovery", lambda: RECOVERIES[recovery](writer.conn), method=recovery)
                checkpoints["after-recovery"] = {"in_transaction": writer.conn.in_transaction}

            # The next unit of work on the same connection: write N, then roll back.
            writer.begin("next-begin")
            next_write = writer.sql("next-write", "INSERT INTO ledger(token, step) VALUES (?, 'N')", (token,))
            next_rollback = writer.abandon("next-rollback")
            checkpoints["after-next-unit"] = {"in_transaction": writer.conn.in_transaction}
            observers["after-next-unit"] = common.observe(path, q)
        finally:
            writer.conn.close()
        observers["final"] = common.observe(path, q)

        def status(entry: dict[str, Any] | None) -> Any:
            if entry is None:
                return "not-run"
            if entry["status"] == "ok":
                return "ok"
            driver = (entry["error"] or {}).get("driver") or {}
            return {"error": driver.get("sqlite_errorname") or entry["error"]["type"], "message": driver.get("message")}

        observed = {
            "configuration": writer.config,
            "fault": status(fault_step),
            "fault_error_code": ((fault_step.get("error") or {}).get("driver") or {}).get("sqlite_errorcode"),
            "in_transaction": {label: value["in_transaction"] for label, value in checkpoints.items()},
            "writer_view": {
                "before-fault": checkpoints["before-fault"]["own_view"],
                "after-fault": checkpoints["after-fault"]["own_view"],
            },
            "write_b": None if write_b is None else {
                "status": status(write_b),
                "sql_started": write_b["sql_started"],
                "observer_saw_b_before_complete": ["B"] in (observers["after-write-b"].get("ledger") or []),
            },
            "complete": status(complete),
            "complete_sql_started": complete["sql_started"],
            "recovery": None if recovered is None else {
                "method": recovery,
                "status": status(recovered),
                "sql_started": recovered["sql_started"],
            },
            "persisted_after_complete": {k: observers["after-complete"][k] for k in ("balances", "ledger")},
            "next_unit": {
                "write": status(next_write),
                "rollback": status(next_rollback),
                "rollback_sql_started": next_rollback["sql_started"],
            },
            "persisted_final": {k: observers["final"][k] for k in ("balances", "ledger")},
        }
        return {
            "observed": observed,
            "trace": writer.trace.statements(),
            "steps": writer.steps,
            "checkpoints": checkpoints,
            "observers": observers,
            "trace_events": writer.trace.events,
        }

    return run


def main() -> None:
    variants = [
        (f"{mode}.{fault}.{follow_up}", scenario(mode, fault, follow_up))
        for mode in MODES
        for fault in FAULTS
        for follow_up in FOLLOW_UPS
    ]
    variants += [
        (f"pep249.rollback.no-write.recover-{name}", scenario("pep249", "rollback", "no-write", name))
        for name in RECOVERIES
    ]
    common.run_experiment("sqlite01-raw", variants)


if __name__ == "__main__":
    main()
