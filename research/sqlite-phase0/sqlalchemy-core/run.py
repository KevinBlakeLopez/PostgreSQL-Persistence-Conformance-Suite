"""Score SQLAlchemy Core Connection.begin() on SQLite against the control's outcomes.

This is not a PPCS adapter. It does not speak the PostgreSQL protocol and it
does not import adapters/sqlalchemy-core. The engine is create_engine("sqlite:///...")
with SQLAlchemy's own transaction handling: legacy isolation_level, and
Connection.begin() / Connection.begin_nested().

A second sqlite3 connection is the observer. Expectations match the sqlite3
control: what a second connection can see after the Core API returns.

    /path/to/sqlalchemy-2.1.5/bin/python research/sqlite-phase0/sqlalchemy-core/run.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, InvalidRequestError, OperationalError


ROOT = Path(__file__).resolve().parents[1]
REPETITIONS = 3
SCHEMA = "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name"


class AppError(Exception):
    pass


def require_versions() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit(f"Python 3.12+ is required, this is {sys.version}")
    if sqlalchemy.__version__ != "2.1.5":
        raise SystemExit(f"SQLAlchemy 2.1.5 is required, this is {sqlalchemy.__version__}")


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


def observe(path: Path, queries: dict[str, str]) -> dict:
    connection = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        report = {}
        for name, statement in queries.items():
            try:
                report[name] = {"status": "ok", "rows": [list(row) for row in connection.execute(statement)]}
            except sqlite3.Error as exc:
                report[name] = {
                    "status": "error",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
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
    return [row[0] for row in found]


def dbapi_error(exc: Exception) -> dict:
    orig = getattr(exc, "orig", exc)
    return {
        "type": type(exc).__name__,
        "orig_type": type(orig).__name__,
        "message": str(orig),
        "sqlite_errorcode": getattr(orig, "sqlite_errorcode", None),
        "sqlite_errorname": getattr(orig, "sqlite_errorname", None),
    }


class Case:
    def __init__(self, path: Path):
        self.path = path
        self.engine = create_engine(f"sqlite:///{path}")
        self.trace: list[str] = []
        self.conn = self.engine.connect()
        self.raw = self.conn.connection.driver_connection
        self.raw.set_trace_callback(self.trace.append)
        self.mode = {
            "autocommit": self.raw.autocommit,
            "isolation_level": self.raw.isolation_level,
        }

    def close(self) -> None:
        self.conn.close()
        self.engine.dispose()

    def driver_in_transaction(self) -> bool:
        return bool(self.raw.in_transaction)


def finished(case_id: str, checks: Checks, case: Case, observers: dict, steps: dict) -> dict:
    return {
        "id": case_id,
        "passed": checks.passed,
        "driver": case.mode,
        "sqlalchemy": sqlalchemy.__version__,
        "checks": checks.items,
        "trace": case.trace,
        "observers": observers,
        "steps": steps,
    }


def ctl_commit(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.commit()
        with case.conn.begin():
            case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("driver autocommit", case.mode["autocommit"], sqlite3.LEGACY_TRANSACTION_CONTROL)
        checks.eq("driver isolation_level", case.mode["isolation_level"], "")
        checks.eq("in_transaction after begin()", case.driver_in_transaction(), False)
        checks.eq("observer", rows(after.get("item")), [[1, "marker"]])
        checks.eq("trace ends with COMMIT", case.trace[-1], "COMMIT")
        return finished("SQLITE-CTL.commit", checks, case, {"after": after}, {})
    finally:
        case.close()


def ctl_rollback(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.commit()
        try:
            with case.conn.begin():
                case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
                raise AppError("application error")
        except AppError:
            pass
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("in_transaction after rollback", case.driver_in_transaction(), False)
        checks.eq("core in_transaction", case.conn.in_transaction(), False)
        checks.eq("observer", rows(after.get("item")), [])
        checks.eq("trace ends with ROLLBACK", case.trace[-1], "ROLLBACK")
        return finished("SQLITE-CTL.rollback", checks, case, {"after": after}, {})
    finally:
        case.close()


def caught_unique_then_commit(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'taken')")
        case.conn.commit()
        fault = None
        with case.conn.begin():
            case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (2, 'marker')")
            try:
                case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (3, 'taken')")
            except IntegrityError as exc:
                fault = dbapi_error(exc)
            still_open = case.driver_in_transaction()
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("fault type", (fault or {}).get("orig_type"), "IntegrityError")
        checks.eq("fault name", (fault or {}).get("sqlite_errorname"), "SQLITE_CONSTRAINT_UNIQUE")
        checks.eq("fault code", (fault or {}).get("sqlite_errorcode"), 2067)
        checks.eq("in_transaction after catch", still_open, True)
        checks.eq("in_transaction after begin() returns", case.driver_in_transaction(), False)
        checks.eq("observer", rows(after.get("item")), [[1, "taken"], [2, "marker"]])
        return finished("SQLITE-TX-01.caught-unique-then-commit", checks, case, {"after": after}, {"fault": fault})
    finally:
        case.close()


def missing_savepoint_then_commit(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.commit()
        fault = None
        with case.conn.begin():
            case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'kept')")
            try:
                case.conn.exec_driver_sql("ROLLBACK TO SAVEPOINT does_not_exist")
            except OperationalError as exc:
                fault = dbapi_error(exc)
            still_open = case.driver_in_transaction()
            follow = case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (2, 'after')")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("fault name", (fault or {}).get("sqlite_errorname"), "SQLITE_ERROR")
        checks.eq("fault code", (fault or {}).get("sqlite_errorcode"), 1)
        checks.eq("fault message", (fault or {}).get("message"), "no such savepoint: does_not_exist")
        checks.eq("in_transaction after error", still_open, True)
        checks.eq("follow-up rowcount", follow.rowcount, 1)
        checks.eq("observer", rows(after.get("item")), [[1, "kept"], [2, "after"]])
        return finished("SQLITE-TX-02.missing-savepoint-then-commit", checks, case, {"after": after}, {"fault": fault})
    finally:
        case.close()


def release_then_outer_rollback(path: Path) -> dict:
    """Core translation of the control: begin(), begin_nested(), then the outer block raises.

    begin_nested() emits SAVEPOINT. On this driver that statement is not preceded
    by BEGIN, so SQLite treats RELEASE of that savepoint as the end of the
    transaction. The expectation stays the control's: the outer rollback leaves
    no table.
    """
    case = Case(path)
    checks = Checks()
    try:
        try:
            with case.conn.begin():
                with case.conn.begin_nested():
                    case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
                    case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'released')")
                after_release = case.driver_in_transaction()
                raise AppError("outer")
        except AppError:
            pass
        after = observe(path, {"schema": SCHEMA, "item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("in_transaction after nested exit", after_release, True)
        checks.eq("in_transaction after outer exit", case.driver_in_transaction(), False)
        checks.eq("core in_transaction", case.conn.in_transaction(), False)
        checks.eq("observer schema", schema_names(after), [])
        checks.eq("observer item", after.get("item", {}).get("status"), "error")
        return finished("SQLITE-TX-04.release-then-outer-rollback", checks, case, {"after": after}, {})
    finally:
        case.close()


def reuse_while_open(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.commit()
        second = None
        trans = case.conn.begin()
        case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
        try:
            case.conn.begin()
        except InvalidRequestError as exc:
            second = {"type": type(exc).__name__, "message": str(exc).split("\n", 1)[0]}
        still_open = case.driver_in_transaction()
        case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (2, 'next')")
        trans.commit()
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("second begin type", (second or {}).get("type"), "InvalidRequestError")
        checks.eq("in_transaction while held", still_open, True)
        checks.eq("in_transaction after commit", case.driver_in_transaction(), False)
        checks.eq("observer", rows(after.get("item")), [[1, "doomed"], [2, "next"]])
        return finished("SQLITE-TX-03.reuse-while-open", checks, case, {"after": after}, {"second_begin": second})
    finally:
        case.close()


def reuse_after_rollback(path: Path) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        case.conn.exec_driver_sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        case.conn.commit()
        try:
            with case.conn.begin():
                case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
                raise AppError("application error")
        except AppError:
            pass
        between = case.driver_in_transaction()
        with case.conn.begin():
            case.conn.exec_driver_sql("INSERT INTO item(id, name) VALUES (2, 'next')")
        after = observe(path, {"item": "SELECT id, name FROM item ORDER BY id"})
        checks.eq("in_transaction between units", between, False)
        checks.eq("in_transaction after second unit", case.driver_in_transaction(), False)
        checks.eq("observer", rows(after.get("item")), [[2, "next"]])
        return finished("SQLITE-TX-03.reuse-after-rollback", checks, case, {"after": after}, {})
    finally:
        case.close()


def _migration(path: Path, end: str, case_id: str) -> dict:
    case = Case(path)
    checks = Checks()
    try:
        fault = None
        try:
            with case.conn.begin():
                case.conn.exec_driver_sql("CREATE TABLE schema_migrations (id TEXT PRIMARY KEY)")
                case.conn.exec_driver_sql("CREATE TABLE account (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
                case.conn.exec_driver_sql("INSERT INTO schema_migrations(id) VALUES ('001_account')")
                case.conn.exec_driver_sql("INSERT INTO account(id, email) VALUES (1, 'a@example.com')")
                try:
                    case.conn.exec_driver_sql("INSERT INTO account(id, email) VALUES (2, 'a@example.com')")
                except IntegrityError as exc:
                    fault = dbapi_error(exc)
                still_open = case.driver_in_transaction()
                if end == "ROLLBACK":
                    raise AppError("rollback the migration")
        except AppError:
            if end != "ROLLBACK":
                raise
        after = observe(path, {
            "schema": SCHEMA,
            "accounts": "SELECT id, email FROM account ORDER BY id",
            "migrations": "SELECT id FROM schema_migrations ORDER BY id",
        })
        checks.eq("fault name", (fault or {}).get("sqlite_errorname"), "SQLITE_CONSTRAINT_UNIQUE")
        checks.eq("fault code", (fault or {}).get("sqlite_errorcode"), 2067)
        checks.eq("in_transaction after fault", still_open, True)
        checks.eq("in_transaction after end", case.driver_in_transaction(), False)
        if end == "ROLLBACK":
            checks.eq("observer schema", schema_names(after), [])
            checks.eq("accounts query", after.get("accounts", {}).get("status"), "error")
        else:
            checks.eq("observer schema", schema_names(after), ["account", "schema_migrations"])
            checks.eq("accounts", rows(after.get("accounts")), [[1, "a@example.com"]])
            checks.eq("migrations", rows(after.get("migrations")), [["001_account"]])
        return finished(case_id, checks, case, {"after": after}, {"fault": fault})
    finally:
        case.close()


def ddl_rollback(path: Path) -> dict:
    return _migration(path, "ROLLBACK", "SQLITE-DDL.statement-error-rollback")


def ddl_commit(path: Path) -> dict:
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
    payload = {"id": record["id"], "passed": record["passed"], "checks": record["checks"], "trace": record["trace"]}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    require_versions()
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = ROOT / "sqlalchemy-core" / "evidence" / run_id
    case_dir = run_dir / "cases"
    db_dir = run_dir / "db"
    db_dir.mkdir(parents=True)
    failed = False
    summary_cases = []
    for function in CASES:
        records = []
        for repetition in range(1, REPETITIONS + 1):
            case_id = function.__doc__.split(":", 1)[0].strip() if function.__doc__ and function.__doc__.startswith("SQLITE-") else function.__name__
            # Prefer the id the function records. Placeholder until it returns.
            db_path = db_dir / f"{function.__name__}.rep{repetition}.sqlite"
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
            write_json(case_dir / f"{record['id']}.rep{repetition}.json", record)
            records.append(record)
            print(f"{record['id']}.rep{repetition} {'PASS' if record['passed'] else 'FAIL'}", flush=True)
        agreed = len({fingerprint(record) for record in records}) == 1
        passed = all(record["passed"] for record in records) and agreed
        if not passed:
            failed = True
            for record in records:
                for item in record["checks"]:
                    if not item["ok"]:
                        print(f"  {record['id']}: {item['name']}: observed {item['observed']!r}, expected {item['expected']!r}", flush=True)
                        break
        if not agreed:
            print(f"NONDETERMINISTIC {records[0]['id']}", flush=True)
        summary_cases.append({"id": records[0]["id"], "passed": passed, "repetitions_agreed": agreed})
    summary = {
        "run_id": run_id,
        "python": sys.version,
        "sqlite": sqlite3.sqlite_version,
        "sqlalchemy": sqlalchemy.__version__,
        "repetitions": REPETITIONS,
        "passed": not failed,
        "cases": summary_cases,
    }
    write_json(run_dir / "summary.json", summary)
    print(f"evidence {run_dir}", flush=True)
    print("PASS" if not failed else "FAIL", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
