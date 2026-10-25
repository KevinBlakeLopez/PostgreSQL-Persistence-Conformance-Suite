"""SQLITE-02: SQLAlchemy Core transaction objects after SQLite ends the transaction.

The SQLITE-01 schema and trigger. In unit 1 the application debits account 1
and records ledger row A, then tries to debit account 2 below zero. In the
"write-b" and "no-write" follow-ups it catches the database error, optionally
records ledger row B, and lets the transaction complete; in "escape" the error
leaves the unit. If unit 1's completion returns normally, the application
records a confirmation in an independent sink (layer D: what an application
does with a reported commit).

Three later units then run on the same pool of one connection, through the
same API: N1 commits, N2 rolls back, N3 commits.

Engine configurations, all from SQLAlchemy 2.1's SQLite transaction docs
(dialects/sqlite/base.py, "Transactions with SQLite and the sqlite3 driver"):

    default           create_engine("sqlite:///file"): legacy sqlite3 control
    autocommit-false  connect_args={"autocommit": False}
    begin-recipe      "connect" sets isolation_level=None; "begin" emits BEGIN

APIs:

    explicit          with engine.connect() as conn: tx = conn.begin(); ...; tx.commit()
    commit-as-you-go  with engine.connect() as conn: conn.execute(...); conn.commit()
    engine-begin      with engine.begin() as conn: ...   (commits on a clean exit)

    .venv/bin/python -I repro/sqlite02_core.py
"""

from __future__ import annotations

import gc
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
import sqlite01_raw  # noqa: E402

import sqlalchemy  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402


CONFIGS = ("default", "autocommit-false", "begin-recipe")
APIS = ("explicit", "commit-as-you-go", "engine-begin")
FAULTS = sqlite01_raw.FAULTS
FOLLOW_UPS = ("write-b", "no-write", "escape")
LATER_UNITS = (("N1", "commit"), ("N2", "rollback"), ("N3", "commit"))


class AppError(Exception):
    """The application's own reason to roll a unit back."""


def require_versions() -> None:
    common.require_python()
    if sqlalchemy.__version__ != "2.1.6":
        raise SystemExit(f"SQLAlchemy 2.1.6 is required, this is {sqlalchemy.__version__}")


class PoolLog(logging.Handler):
    """Routes what SQLAlchemy's pools log to the scenario whose pool logged it.

    Each Engine names its pool after the scenario token (pool_logging_name), so
    a record is attributed by logger name. A record from a pool whose scenario
    has finished, for example a connection finalized later by the garbage
    collector, goes to `stray` instead of being credited to whatever runs now.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.active: dict[str, list[dict[str, Any]]] = {}
        self.stray: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        exc = record.exc_info[1] if record.exc_info else None
        entry = {
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "exception": common.error_dict(exc),
        }
        for name, records in self.active.items():
            if record.name.endswith("." + name):
                records.append(entry)
                return
        self.stray.append(entry)


POOL_LOG = PoolLog()
logging.getLogger("sqlalchemy.pool").addHandler(POOL_LOG)
POOL_TIMEOUT = 2.0  # seconds a checkout waits on the exhausted pool of one (SQLAlchemy's default is 30)


class Engine:
    """An engine on one file, a pool of one, and layer-A/B recording hooks."""

    def __init__(self, path: Path, config: str, token: str):
        self.token = token
        kwargs: dict[str, Any] = {
            "pool_size": 1,
            "max_overflow": 0,
            "pool_timeout": POOL_TIMEOUT,
            "pool_logging_name": token,
        }
        if config == "autocommit-false":
            kwargs["connect_args"] = {"autocommit": False}
        self.engine = create_engine(f"sqlite:///{path}", **kwargs)
        self.pool_log: list[dict[str, Any]] = []
        POOL_LOG.active[token] = self.pool_log
        self.trace: list[dict[str, Any]] = []
        self.events: list[str] = []
        self.dbapi: list[sqlite3.Connection] = []
        self.dbapi_config: list[dict[str, Any]] = []

        @event.listens_for(self.engine, "connect")
        def on_connect(dbapi_connection, record):
            serial = len(self.dbapi)
            self.dbapi.append(dbapi_connection)
            if config == "begin-recipe":
                dbapi_connection.isolation_level = None  # the recipe's connect hook
            self.dbapi_config.append({
                "autocommit": dbapi_connection.autocommit,
                "isolation_level": dbapi_connection.isolation_level,
                "in_transaction_at_connect": dbapi_connection.in_transaction,
            })

            def on_trace(sql: str, conn=dbapi_connection, serial=serial) -> None:
                self.trace.append({"dbapi": serial, "sql": sql, "in_transaction_before": common.in_transaction(conn)})

            dbapi_connection.set_trace_callback(on_trace)
            self.events.append(f"pool.connect dbapi={serial}")

        if config == "begin-recipe":
            @event.listens_for(self.engine, "begin")
            def do_begin(conn):
                conn.exec_driver_sql("BEGIN")  # the recipe's begin hook

        for name in ("begin", "commit", "rollback"):
            event.listen(self.engine, name, self._core_event(name))
        for name in ("checkout", "checkin", "reset", "invalidate"):
            event.listen(self.engine, name, self._pool_event(name))

    def _core_event(self, name: str) -> Callable[..., None]:
        def handler(conn, *args) -> None:
            self.events.append(f"core.{name}")
        return handler

    def _pool_event(self, name: str) -> Callable[..., None]:
        def handler(dbapi_connection, *args) -> None:
            extra = ""
            if name == "reset" and len(args) >= 2:
                extra = f" transaction_was_reset={args[1].transaction_was_reset}"
            self.events.append(f"pool.{name} dbapi={self.serial_of(dbapi_connection)}{extra}")
        return handler

    def serial_of(self, dbapi_connection) -> int | None:
        return next((i for i, c in enumerate(self.dbapi) if c is dbapi_connection), None)

    def serial(self, conn) -> int | None:
        return self.serial_of(conn.connection.driver_connection)

    def finish(self) -> dict[str, Any]:
        """Measure connections still checked out, collect garbage, then dispose.

        A connection that was never returned to the pool is counted before the
        collection; the collection lets SQLAlchemy finalize it inside this
        scenario, so its log records are attributed here.
        """
        before = self.engine.pool.checkedout()
        events_before = len(self.events)
        gc.collect()
        after = self.engine.pool.checkedout()
        self.engine.dispose()
        POOL_LOG.active.pop(self.token, None)
        return {
            "checked_out_before_gc": before,
            "checked_out_after_gc": after,
            "pool_events_during_gc": self.events[events_before:],
        }


def sa_state(conn) -> dict[str, Any]:
    """Layer B through public attributes; layer A through the DBAPI connection."""
    tx = conn.get_transaction()
    state: dict[str, Any] = {
        "sa_in_transaction": conn.in_transaction(),
        "sa_tx_is_active": None if tx is None else tx.is_active,
        "sa_invalidated": conn.invalidated,
    }
    try:
        state["sqlite_in_transaction"] = conn.connection.driver_connection.in_transaction
    except Exception as exc:  # recorded, e.g. a closed or invalidated connection
        state["sqlite_in_transaction"] = {"error": common.error_dict(exc)}
    return state


def status(entry: dict[str, Any] | None) -> Any:
    if entry is None:
        return "not-run"
    if "error" not in entry:
        return "ok"
    error = entry.get("error") or {}
    driver = error.get("driver") or {}
    return {
        "status": entry["status"],
        "type": error.get("type"),
        "sqlite_errorname": driver.get("sqlite_errorname"),
        "message": driver.get("message") or error.get("message"),
    }


def scenario(config: str, api: str, fault: str, follow_up: str) -> Callable[[Path, str], dict[str, Any]]:
    action, amount = FAULTS[fault]

    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        sink = common.Sink(work / "sink.sqlite")
        sqlite01_raw.setup(path, action)
        q = sqlite01_raw.queries(token)
        eng = Engine(path, config, token)
        steps: list[dict[str, Any]] = []
        checkpoints: dict[str, Any] = {}
        observers: dict[str, Any] = {}

        def step(label: str, fn: Callable[[], Any], conn) -> dict[str, Any]:
            start = len(eng.trace)
            entry = common.call(label, fn)
            entry["sql_started"] = [event["sql"] for event in eng.trace[start:]]
            entry["state_after"] = sa_state(conn)
            steps.append(entry)
            return entry

        def insert(conn, label: str) -> Callable[[], Any]:
            return lambda: conn.execute(
                text("INSERT INTO ledger(token, step) VALUES (:t, :s)"), {"t": token, "s": label}).rowcount

        def unit_one_body(conn) -> None:
            step("write-a-debit", lambda: conn.execute(
                text("UPDATE accounts SET balance = balance - 30 WHERE id = 1")).rowcount, conn)
            step("write-a-ledger", insert(conn, "A"), conn)
            checkpoints["before-fault"] = sa_state(conn)
            fault_sql = text(f"UPDATE accounts SET balance = balance - {amount} WHERE id = 2")
            if follow_up == "escape":
                start = len(eng.trace)
                steps.append({"step": "fault (not caught)", "sql_started_from": start})
                conn.execute(fault_sql)  # an error leaves the unit
                checkpoints["after-fault"] = sa_state(conn)
                return
            entry: dict[str, Any] = {"step": "fault", "status": "ok"}
            start = len(eng.trace)
            try:
                conn.execute(fault_sql)
            except DBAPIError as exc:  # the application catches the database error
                entry = {"step": "fault", "status": "caught", "error": common.error_dict(exc)}
            entry["sql_started"] = [event["sql"] for event in eng.trace[start:]]
            entry["state_after"] = sa_state(conn)
            steps.append(entry)
            checkpoints["after-fault"] = sa_state(conn)
            observers["after-fault"] = common.observe(path, q)
            if follow_up == "write-b":
                step("write-b", insert(conn, "B"), conn)
                checkpoints["after-write-b"] = sa_state(conn)
                observers["after-write-b"] = common.observe(path, q)

        def run_unit(label: str, body: Callable[[Any], None], ending: str) -> dict[str, Any]:
            """One unit of work through `api`; `ending` is commit or rollback."""
            record: dict[str, Any] = {"unit": label, "ending": ending}
            start = len(eng.trace)

            def explicit() -> None:
                with eng.engine.connect() as conn:
                    record["dbapi_serial"] = eng.serial(conn)
                    record["state_at_checkout"] = sa_state(conn)
                    tx = conn.begin()
                    body(conn)
                    record["end_from"] = len(eng.trace)
                    tx.commit() if ending == "commit" else tx.rollback()

            def commit_as_you_go() -> None:
                with eng.engine.connect() as conn:
                    record["dbapi_serial"] = eng.serial(conn)
                    record["state_at_checkout"] = sa_state(conn)
                    body(conn)  # the first execute() autobegins
                    record["end_from"] = len(eng.trace)
                    conn.commit() if ending == "commit" else conn.rollback()

            def engine_begin() -> None:
                with eng.engine.begin() as conn:
                    record["dbapi_serial"] = eng.serial(conn)
                    record["state_at_checkout"] = sa_state(conn)
                    body(conn)
                    record["end_from"] = len(eng.trace)
                    if ending == "rollback":
                        raise AppError("the application rolls this unit back")

            outcome = common.call(label, {"explicit": explicit, "commit-as-you-go": commit_as_you_go,
                                          "engine-begin": engine_begin}[api])
            record["outcome"] = status(outcome)
            if outcome.get("error") and outcome["error"]["type"].endswith("AppError"):
                record["outcome"] = "rolled back by AppError"
            record["sql_started"] = [event["sql"] for event in eng.trace[start:]]
            record["end_sql_started"] = [event["sql"] for event in eng.trace[record.get("end_from", len(eng.trace)):]]
            record["error"] = outcome.get("error")
            record["warnings"] = outcome.get("warnings")
            return record

        try:
            unit1 = run_unit("unit-1", unit_one_body, "commit")
            observers["after-unit-1"] = common.observe(path, q)
            if unit1["error"] is None:
                sink.record(token, "application-confirmed-transfer", "unit 1 completion returned normally")
            events_unit1 = list(eng.events)
            later = []
            for label, ending in LATER_UNITS:
                later.append(run_unit(label, lambda conn, label=label: step(
                    f"{label}-write", insert(conn, label), conn), ending))
                observers[f"after-{label}"] = common.observe(path, q)
        finally:
            finished = eng.finish()
        observers["final"] = common.observe(path, q)

        fault_entry = next((s for s in steps if s["step"].startswith("fault")), None)
        write_b = next((s for s in steps if s["step"] == "write-b"), None)
        observed = {
            "configuration": {"config": config, "api": api, "dbapi_at_connect": eng.dbapi_config},
            "fault": status(fault_entry) if fault_entry and "sql_started_from" not in fault_entry else (
                "not caught: see unit 1 outcome" if fault_entry else "not-run"),
            "state_before_fault": checkpoints.get("before-fault"),
            "state_after_fault": checkpoints.get("after-fault"),
            "write_b": None if write_b is None else {
                "status": status(write_b),
                "sql_started": write_b["sql_started"],
                "state_after": write_b.get("state_after"),
                "observer_saw_b_before_completion": ["B"] in (observers["after-write-b"].get("ledger") or []),
            },
            "unit_1": {
                "outcome": unit1["outcome"],
                "end_sql_started": unit1["end_sql_started"],
                "persisted": {k: observers["after-unit-1"][k] for k in ("balances", "ledger")},
                "sink": sink.read(token),
            },
            "pool_events_through_unit_1": events_unit1,
            "later_units": [
                {
                    "unit": unit["unit"],
                    "ending": unit["ending"],
                    "same_dbapi_as_unit_1": unit.get("dbapi_serial") == unit1.get("dbapi_serial"),
                    "sqlite_in_transaction_at_checkout": (unit.get("state_at_checkout") or {}).get("sqlite_in_transaction"),
                    "outcome": unit["outcome"],
                    "end_sql_started": unit["end_sql_started"],
                    "ledger_after": observers[f"after-{unit['unit']}"]["ledger"],
                }
                for unit in later
            ],
            "persisted_final": {k: observers["final"][k] for k in ("balances", "ledger")},
            "pool_at_end": finished,
            "pool_log": [
                {"level": r["level"], "message": r["message"],
                 "exception": (r["exception"] or {}).get("message")}
                for r in eng.pool_log if r["level"] in ("WARNING", "ERROR", "CRITICAL")
            ],
        }
        return {
            "observed": observed,
            "trace": [f"dbapi{event['dbapi']}: {event['sql']}" for event in eng.trace],
            "trace_events": eng.trace,
            "events": eng.events,
            "steps": steps,
            "units": [unit1, *later],
            "checkpoints": checkpoints,
            "observers": observers,
            "pool_log_all": eng.pool_log,
        }

    return run


def main() -> None:
    require_versions()
    variants = [
        (f"{config}.{api}.{fault}.{follow_up}", scenario(config, api, fault, follow_up))
        for config in CONFIGS
        for api in APIS
        for fault in FAULTS
        for follow_up in FOLLOW_UPS
    ]
    run_dir = common.run_experiment("sqlite02-core", variants)
    write_stray_pool_log(run_dir)


def write_stray_pool_log(run_dir: Path) -> None:
    """Pool log records no running scenario owned (see PoolLog). Kept, not discarded."""
    gc.collect()
    common.write_json(run_dir / "stray-pool-log.json", POOL_LOG.stray)


if __name__ == "__main__":
    main()
