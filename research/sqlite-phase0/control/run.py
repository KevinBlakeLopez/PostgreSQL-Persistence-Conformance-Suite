"""SQLite Phase 1 control. Standard-library sqlite3 only.

This program is not a PPCS adapter. It does not read specifications/, and the
PostgreSQL runner does not discover it. Each case uses autocommit=True and
explicit BEGIN, COMMIT, and ROLLBACK. A second connection is the observer.

Run, from the worktree root:

    /opt/homebrew/bin/python3.13 research/sqlite-phase0/control/run.py

Exit 0 when every case passes and the three repetitions agree. Exit 1 otherwise.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPETITIONS = 3
SCHEMA = "SELECT type, name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name"


def require_python() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit(
            f"The SQLite control needs Python 3.12+ (this is {sys.version}). "
            "Run it with /opt/homebrew/bin/python3.13."
        )


def error_info(exc: BaseException) -> dict:
    code = getattr(exc, "sqlite_errorcode", None)
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "sqlite_errorcode": code,
        "sqlite_errorname": getattr(exc, "sqlite_errorname", None),
    }


class Conn:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
        self.trace: list[str] = []
        self.conn.set_trace_callback(self.trace.append)

    def sql(self, statement: str, params: tuple = ()) -> dict:
        entry = {
            "sql": statement,
            "params": list(params),
            "in_transaction_before": self.conn.in_transaction,
        }
        try:
            cursor = self.conn.execute(statement, params)
        except sqlite3.Error as exc:
            entry["status"] = "error"
            entry["error"] = error_info(exc)
            entry["in_transaction_after"] = self.conn.in_transaction
            return entry
        entry["status"] = "ok"
        entry["rowcount"] = cursor.rowcount
        if cursor.description is not None:
            entry["rows"] = [list(row) for row in cursor.fetchall()]
        entry["in_transaction_after"] = self.conn.in_transaction
        return entry

    def close(self) -> None:
        self.conn.close()


def observe(path: Path, queries: dict[str, str]) -> dict:
    connection = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        report = {"in_transaction": connection.in_transaction}
        for name, statement in queries.items():
            try:
                rows = [list(row) for row in connection.execute(statement)]
                report[name] = {"status": "ok", "rows": rows}
            except sqlite3.Error as exc:
                report[name] = {"status": "error", "error": error_info(exc)}
        return report
    finally:
        connection.close()


def rows(section: dict | None) -> list | None:
    if not isinstance(section, dict) or section.get("status") != "ok":
        return None
    return section.get("rows")


def schema_names(report: dict) -> list | None:
    found = rows(report.get("schema"))
    if found is None:
        return None
    return [row[1] for row in found if len(row) > 1]


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def eq(self, name: str, observed, expected) -> None:
        self.items.append({
            "name": name,
            "observed": observed,
            "expected": expected,
            "ok": observed == expected,
        })

    @property
    def passed(self) -> bool:
        return bool(self.items) and all(item["ok"] for item in self.items)


def configure(conn: Conn) -> None:
    # Assignment forms of journal_mode and busy_timeout return the new value.
    # PRAGMA foreign_keys=ON does not, so the flag is read back separately.
    conn.sql("PRAGMA journal_mode=DELETE")
    conn.sql("PRAGMA foreign_keys=ON")
    conn.sql("PRAGMA busy_timeout=0")
    journal = conn.sql("PRAGMA journal_mode")
    foreign_keys = conn.sql("PRAGMA foreign_keys")
    busy = conn.sql("PRAGMA busy_timeout")
    if journal.get("rows") != [["delete"]] or foreign_keys.get("rows") != [[1]] or busy.get("rows") != [[0]]:
        raise RuntimeError(f"baseline pragmas were not applied: {journal}, {foreign_keys}, {busy}")
    if conn.conn.in_transaction:
        raise RuntimeError("configuration left a transaction open")


def result(case_id: str, checks: Checks, writer: Conn, observers: dict, steps: dict) -> dict:
    return {
        "id": case_id,
        "passed": checks.passed,
        "checks": checks.items,
        "trace": writer.trace,
        "observers": observers,
        "steps": steps,
    }


def ctl_commit(path: Path) -> dict:
    """SQLITE-CTL.commit: a SQL COMMIT is visible to a second connection."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        checks.eq("autocommit", writer.conn.autocommit, True)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        begin = writer.sql("BEGIN")
        inserted = writer.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
        pending = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        commit = writer.sql("COMMIT")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("begin", begin["status"], "ok")
        checks.eq("insert", inserted["status"], "ok")
        checks.eq("in_transaction before commit", inserted["in_transaction_after"], True)
        checks.eq("pending hidden", rows(pending.get("item")), [])
        checks.eq("commit status", commit["status"], "ok")
        checks.eq("in_transaction after commit", writer.conn.in_transaction, False)
        checks.eq("observer after commit", rows(after.get("item")), [[1, "marker"]])
        return result("SQLITE-CTL.commit", checks, writer, {"pending": pending, "after": after}, {
            "begin": begin, "insert": inserted, "commit": commit,
        })
    finally:
        writer.close()


def ctl_rollback(path: Path) -> dict:
    """SQLITE-CTL.rollback: a SQL ROLLBACK leaves the marker invisible."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        writer.sql("BEGIN")
        writer.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
        pending = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        rolled = writer.sql("ROLLBACK")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("pending hidden", rows(pending.get("item")), [])
        checks.eq("rollback status", rolled["status"], "ok")
        checks.eq("in_transaction after rollback", writer.conn.in_transaction, False)
        checks.eq("observer after rollback", rows(after.get("item")), [])
        return result("SQLITE-CTL.rollback", checks, writer, {"pending": pending, "after": after}, {"rollback": rolled})
    finally:
        writer.close()


def caught_unique_then_commit(path: Path) -> dict:
    """SQLITE-TX-01.caught-unique-then-commit: the violation does not end the transaction."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        writer.sql("INSERT INTO item(id, name) VALUES (1, 'taken')")
        writer.sql("BEGIN")
        marker = writer.sql("INSERT INTO item(id, name) VALUES (2, 'marker')")
        fault = writer.sql("INSERT INTO item(id, name) VALUES (3, 'taken')")
        after_fault = writer.conn.in_transaction
        writer_rows = writer.sql("SELECT id, name FROM item ORDER BY id")
        pending = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        commit = writer.sql("COMMIT")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("marker insert", marker["status"], "ok")
        checks.eq("fault type", (fault.get("error") or {}).get("type"), "IntegrityError")
        checks.eq("fault code", (fault.get("error") or {}).get("sqlite_errorcode"), 2067)
        checks.eq("fault name", (fault.get("error") or {}).get("sqlite_errorname"), "SQLITE_CONSTRAINT_UNIQUE")
        checks.eq("in_transaction after fault", after_fault, True)
        checks.eq("writer still has marker", writer_rows.get("rows"), [[1, "taken"], [2, "marker"]])
        checks.eq("observer before commit", rows(pending.get("item")), [[1, "taken"]])
        checks.eq("commit status", commit["status"], "ok")
        checks.eq("in_transaction after commit", writer.conn.in_transaction, False)
        checks.eq("observer after commit", rows(after.get("item")), [[1, "taken"], [2, "marker"]])
        return result("SQLITE-TX-01.caught-unique-then-commit", checks, writer, {
            "pending": pending, "after": after,
        }, {"fault": fault, "commit": commit})
    finally:
        writer.close()


def missing_savepoint_then_commit(path: Path) -> dict:
    """SQLITE-TX-02.missing-savepoint-then-commit: the error leaves the transaction usable."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        writer.sql("BEGIN")
        kept = writer.sql("INSERT INTO item(id, name) VALUES (1, 'kept')")
        missing = writer.sql("ROLLBACK TO SAVEPOINT does_not_exist")
        after_error = writer.conn.in_transaction
        follow = writer.sql("INSERT INTO item(id, name) VALUES (2, 'after')")
        pending = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        commit = writer.sql("COMMIT")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("kept insert", kept["status"], "ok")
        checks.eq("missing type", (missing.get("error") or {}).get("type"), "OperationalError")
        checks.eq("missing code", (missing.get("error") or {}).get("sqlite_errorcode"), 1)
        checks.eq("missing name", (missing.get("error") or {}).get("sqlite_errorname"), "SQLITE_ERROR")
        checks.eq("missing message", (missing.get("error") or {}).get("message"), "no such savepoint: does_not_exist")
        checks.eq("in_transaction after error", after_error, True)
        checks.eq("follow-up insert", follow["status"], "ok")
        checks.eq("observer before commit", rows(pending.get("item")), [])
        checks.eq("commit status", commit["status"], "ok")
        checks.eq("in_transaction after commit", writer.conn.in_transaction, False)
        checks.eq("observer after commit", rows(after.get("item")), [[1, "kept"], [2, "after"]])
        return result("SQLITE-TX-02.missing-savepoint-then-commit", checks, writer, {
            "pending": pending, "after": after,
        }, {"missing": missing, "commit": commit})
    finally:
        writer.close()


def release_then_outer_rollback(path: Path) -> dict:
    """SQLITE-TX-04.release-then-outer-rollback: RELEASE does not publish the savepoint's table or row."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("BEGIN")
        writer.sql("SAVEPOINT sp1")
        created = writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        inserted = writer.sql("INSERT INTO item(id, name) VALUES (1, 'released')")
        released = writer.sql("RELEASE SAVEPOINT sp1")
        after_release = writer.conn.in_transaction
        writer_schema = writer.sql(SCHEMA)
        writer_rows = writer.sql("SELECT id, name FROM item ORDER BY id")
        pending = observe(path, {"schema": SCHEMA, "item": "SELECT id, name FROM item ORDER BY id"})
        rolled = writer.sql("ROLLBACK")
        after = observe(path, {"schema": SCHEMA, "item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("create", created["status"], "ok")
        checks.eq("insert", inserted["status"], "ok")
        checks.eq("release", released["status"], "ok")
        checks.eq("in_transaction after release", after_release, True)
        checks.eq("writer schema after release", [row[1] for row in writer_schema.get("rows", [])], ["item"])
        checks.eq("writer row after release", writer_rows.get("rows"), [[1, "released"]])
        checks.eq("observer schema after release", schema_names(pending), [])
        checks.eq("observer item after release", pending.get("item", {}).get("status"), "error")
        checks.eq("rollback", rolled["status"], "ok")
        checks.eq("in_transaction after rollback", writer.conn.in_transaction, False)
        checks.eq("observer schema after rollback", schema_names(after), [])
        checks.eq("observer item after rollback", after.get("item", {}).get("status"), "error")
        return result("SQLITE-TX-04.release-then-outer-rollback", checks, writer, {
            "after_release": pending, "after_rollback": after,
        }, {"release": released, "rollback": rolled})
    finally:
        writer.close()


def reuse_while_open(path: Path) -> dict:
    """SQLITE-TX-03.reuse-while-open: a second unit on the same open transaction commits both."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        writer.sql("BEGIN")
        doomed = writer.sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
        after_unit1 = writer.conn.in_transaction
        second_begin = writer.sql("BEGIN")
        nxt = writer.sql("INSERT INTO item(id, name) VALUES (2, 'next')")
        commit = writer.sql("COMMIT")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("doomed insert", doomed["status"], "ok")
        checks.eq("in_transaction after unit 1", after_unit1, True)
        checks.eq("second begin status", second_begin["status"], "error")
        checks.eq("second begin message", (second_begin.get("error") or {}).get("message"), "cannot start a transaction within a transaction")
        checks.eq("in_transaction after second begin", second_begin["in_transaction_after"], True)
        checks.eq("next insert", nxt["status"], "ok")
        checks.eq("commit", commit["status"], "ok")
        checks.eq("in_transaction after commit", writer.conn.in_transaction, False)
        checks.eq("observer", rows(after.get("item")), [[1, "doomed"], [2, "next"]])
        return result("SQLITE-TX-03.reuse-while-open", checks, writer, {"after": after}, {
            "second_begin": second_begin, "commit": commit,
        })
    finally:
        writer.close()


def reuse_after_rollback(path: Path) -> dict:
    """SQLITE-TX-03.reuse-after-rollback: SQL ROLLBACK lets the next unit commit alone."""
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        writer.sql("BEGIN")
        writer.sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
        rolled = writer.sql("ROLLBACK")
        second = writer.sql("BEGIN")
        nxt = writer.sql("INSERT INTO item(id, name) VALUES (2, 'next')")
        commit = writer.sql("COMMIT")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("rollback", rolled["status"], "ok")
        checks.eq("in_transaction after rollback", second["in_transaction_before"], False)
        checks.eq("second begin", second["status"], "ok")
        checks.eq("next insert", nxt["status"], "ok")
        checks.eq("commit", commit["status"], "ok")
        checks.eq("in_transaction after commit", writer.conn.in_transaction, False)
        checks.eq("observer", rows(after.get("item")), [[2, "next"]])
        return result("SQLITE-TX-03.reuse-after-rollback", checks, writer, {"after": after}, {
            "rollback": rolled, "commit": commit,
        })
    finally:
        writer.close()


def _migration(path: Path, end: str, case_id: str) -> dict:
    writer = Conn(path)
    checks = Checks()
    try:
        configure(writer)
        writer.sql("BEGIN")
        steps = [
            writer.sql("CREATE TABLE schema_migrations (id TEXT PRIMARY KEY)"),
            writer.sql("CREATE TABLE account (id INTEGER PRIMARY KEY, email TEXT UNIQUE)"),
            writer.sql("INSERT INTO schema_migrations(id) VALUES ('001_account')"),
            writer.sql("INSERT INTO account(id, email) VALUES (1, 'a@example.com')"),
        ]
        fault = writer.sql("INSERT INTO account(id, email) VALUES (2, 'a@example.com')")
        after_fault = writer.conn.in_transaction
        pending = observe(path, {
            "schema": SCHEMA,
            "accounts": "SELECT id, email FROM account ORDER BY id",
            "migrations": "SELECT id FROM schema_migrations ORDER BY id",
        })
        ending = writer.sql(end)
        after = observe(path, {
            "schema": SCHEMA,
            "accounts": "SELECT id, email FROM account ORDER BY id",
            "migrations": "SELECT id FROM schema_migrations ORDER BY id",
        })
        checks.eq("setup statements", [step["status"] for step in steps], ["ok", "ok", "ok", "ok"])
        checks.eq("fault type", (fault.get("error") or {}).get("type"), "IntegrityError")
        checks.eq("fault code", (fault.get("error") or {}).get("sqlite_errorcode"), 2067)
        checks.eq("in_transaction after fault", after_fault, True)
        checks.eq("observer schema while pending", schema_names(pending), [])
        checks.eq("end status", ending["status"], "ok")
        checks.eq("in_transaction after end", writer.conn.in_transaction, False)
        if end == "ROLLBACK":
            checks.eq("observer schema", schema_names(after), [])
            checks.eq("accounts query", after.get("accounts", {}).get("status"), "error")
            checks.eq("migrations query", after.get("migrations", {}).get("status"), "error")
        else:
            checks.eq("observer schema", schema_names(after), ["account", "schema_migrations"])
            checks.eq("accounts", rows(after.get("accounts")), [[1, "a@example.com"]])
            checks.eq("migrations", rows(after.get("migrations")), [["001_account"]])
        return result(case_id, checks, writer, {"pending": pending, "after": after}, {"fault": fault, "end": ending})
    finally:
        writer.close()


def ddl_rollback(path: Path) -> dict:
    """SQLITE-DDL.statement-error-rollback: ROLLBACK removes the DDL and the rows."""
    return _migration(path, "ROLLBACK", "SQLITE-DDL.statement-error-rollback")


def ddl_commit(path: Path) -> dict:
    """SQLITE-DDL.statement-error-commit: COMMIT after the caught error keeps the partial migration."""
    return _migration(path, "COMMIT", "SQLITE-DDL.statement-error-commit")


CASES = [
    ctl_commit,
    ctl_rollback,
    caught_unique_then_commit,
    missing_savepoint_then_commit,
    release_then_outer_rollback,
    reuse_while_open,
    reuse_after_rollback,
    ddl_rollback,
    ddl_commit,
]


def fingerprint(record: dict) -> str:
    payload = {
        "id": record["id"],
        "passed": record["passed"],
        "checks": record["checks"],
        "trace": record["trace"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    require_python()
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = ROOT / "control" / "evidence" / run_id
    case_dir = run_dir / "cases"
    db_dir = run_dir / "db"
    db_dir.mkdir(parents=True)
    summary_cases = []
    failed = False
    for function in CASES:
        prints = []
        records = []
        for repetition in range(1, REPETITIONS + 1):
            case_id = function.__doc__.split(":", 1)[0].strip()
            db_path = db_dir / f"{case_id}.rep{repetition}.sqlite"
            try:
                record = function(db_path)
            except Exception as exc:
                record = {
                    "id": case_id,
                    "passed": False,
                    "checks": [{
                        "name": "case raised",
                        "observed": {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
                        "expected": "completed",
                        "ok": False,
                    }],
                    "trace": [],
                    "observers": {},
                    "steps": {},
                }
            record["repetition"] = repetition
            record["database"] = str(db_path)
            write_json(case_dir / f"{record['id']}.rep{repetition}.json", record)
            records.append(record)
            prints.append(record["passed"])
            print(f"{record['id']}.rep{repetition} {'PASS' if record['passed'] else 'FAIL'}", flush=True)
        agreed = len({fingerprint(record) for record in records}) == 1
        passed = all(prints) and agreed
        if not passed:
            failed = True
            for record in records:
                if record["passed"]:
                    continue
                for item in record["checks"]:
                    if not item["ok"]:
                        print(f"  {record['id']}: {item['name']}: observed {item['observed']!r}, expected {item['expected']!r}", flush=True)
        if not agreed:
            print(f"NONDETERMINISTIC {records[0]['id']}", flush=True)
        summary_cases.append({
            "id": records[0]["id"],
            "passed": passed,
            "repetitions_agreed": agreed,
        })
    summary = {
        "run_id": run_id,
        "python": sys.version,
        "sqlite": sqlite3.sqlite_version,
        "repetitions": REPETITIONS,
        "passed": not failed,
        "cases": summary_cases,
    }
    write_json(run_dir / "summary.json", summary)
    print(f"evidence {run_dir}", flush=True)
    print(f"{'PASS' if not failed else 'FAIL'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
