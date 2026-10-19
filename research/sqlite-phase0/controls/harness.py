"""Shared recording helpers for the SQLite Phase 0 baseline.

The baseline uses Python's standard-library sqlite3. Outcomes are recorded
from three places that must stay distinct:

- the SQL the application asked for, and what sqlite3 returned or raised
- Connection.in_transaction on that same connection
- rows and schema read by a second connection

Python 3.12+ transaction control, which this harness selects explicitly:

- explicit: autocommit=True. The driver does not issue BEGIN. The experiment
  issues BEGIN, COMMIT, and ROLLBACK itself.
- legacy: autocommit=LEGACY_TRANSACTION_CONTROL and isolation_level="".
  The driver may issue BEGIN before a DML statement.
- pep249: autocommit=False. The driver opens a transaction before DML.

Driver-issued statements show up in the trace callback even when the
experiment did not call them.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any


MIN_PYTHON = (3, 12)

PRAGMA_NAMES = (
    "journal_mode",
    "synchronous",
    "foreign_keys",
    "busy_timeout",
    "locking_mode",
    "read_uncommitted",
    "query_only",
    "auto_vacuum",
    "wal_autocheckpoint",
    "temp_store",
    "defer_foreign_keys",
    "fullfsync",
    "checkpoint_fullfsync",
    "legacy_alter_table",
    "trusted_schema",
    "user_version",
)


def require_python() -> None:
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"SQLite Phase 0 requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ "
            f"for autocommit and sqlite_errorcode. This interpreter is {sys.version}. "
            "Invoke it as /opt/homebrew/bin/python3.13."
        )


def error_dict(exc: BaseException) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": type(exc).__name__,
        "module": type(exc).__module__,
        "message": str(exc),
        "is_integrity_error": isinstance(exc, sqlite3.IntegrityError),
        "is_operational_error": isinstance(exc, sqlite3.OperationalError),
        "is_programming_error": isinstance(exc, sqlite3.ProgrammingError),
        "is_database_error": isinstance(exc, sqlite3.DatabaseError),
    }
    code = getattr(exc, "sqlite_errorcode", None)
    name = getattr(exc, "sqlite_errorname", None)
    record["sqlite_errorcode"] = code
    record["sqlite_errorname"] = name
    if isinstance(code, int):
        record["primary_code"] = code & 0xFF
        record["extended"] = code != (code & 0xFF)
    return record


def jsonable(value: Any) -> Any:
    if isinstance(value, sqlite3.Row):
        return [jsonable(value[key]) for key in value.keys()]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fingerprint(payload: Any) -> str:
    return json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":"))


class Session:
    """One sqlite3 connection plus the SQL and transaction checkpoints around it."""

    def __init__(self, path: Path, *, mode: str = "explicit", timeout: float = 0.0, name: str = "conn"):
        self.path = Path(path)
        self.mode = mode
        self.name = name
        self.trace: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.conn, self.connect_warnings = connect(self.path, mode=mode, timeout=timeout)
        self.conn.set_trace_callback(self._on_trace)

    def _on_trace(self, sql: str) -> None:
        self.trace.append({"sql": sql, "in_transaction": self.in_transaction()})

    def in_transaction(self) -> Any:
        try:
            return self.conn.in_transaction
        except sqlite3.Error as exc:
            return {"error": error_dict(exc)}

    def state(self, label: str) -> dict[str, Any]:
        return {
            "label": label,
            "connection": self.name,
            "in_transaction": self.in_transaction(),
            "autocommit": _attr(self.conn, "autocommit"),
            "isolation_level": _attr(self.conn, "isolation_level"),
            "total_changes": self._total_changes(),
        }

    def _total_changes(self) -> Any:
        try:
            return self.conn.total_changes
        except sqlite3.Error as exc:
            return {"error": error_dict(exc)}

    def sql(self, statement: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "connection": self.name,
            "sql": statement,
            "params": list(params),
            "in_transaction_before": self.in_transaction(),
        }
        try:
            cursor = self.conn.execute(statement, params)
        except sqlite3.Error as exc:
            entry["status"] = "error"
            entry["error"] = error_dict(exc)
            entry["in_transaction_after"] = self.in_transaction()
            self.calls.append(entry)
            return entry
        entry["status"] = "ok"
        entry["rowcount"] = cursor.rowcount
        entry["lastrowid"] = cursor.lastrowid
        entry["description"] = [column[0] for column in cursor.description] if cursor.description else None
        if cursor.description is not None:
            entry["rows"] = [list(row) for row in cursor.fetchall()]
        entry["in_transaction_after"] = self.in_transaction()
        self.calls.append(entry)
        return entry

    def commit_method(self) -> dict[str, Any]:
        return self._txn_method("commit")

    def rollback_method(self) -> dict[str, Any]:
        return self._txn_method("rollback")

    def _txn_method(self, name: str) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "connection": self.name,
            "method": f"Connection.{name}()",
            "in_transaction_before": self.in_transaction(),
        }
        try:
            returned = getattr(self.conn, name)()
        except sqlite3.Error as exc:
            entry["status"] = "error"
            entry["error"] = error_dict(exc)
            entry["in_transaction_after"] = self.in_transaction()
            self.calls.append(entry)
            return entry
        entry["status"] = "ok"
        entry["returned"] = returned
        entry["in_transaction_after"] = self.in_transaction()
        self.calls.append(entry)
        return entry

    def close(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "connection": self.name,
            "method": "Connection.close()",
            "in_transaction_before": self.in_transaction(),
        }
        try:
            returned = self.conn.close()
        except sqlite3.Error as exc:
            entry["status"] = "error"
            entry["error"] = error_dict(exc)
            self.calls.append(entry)
            return entry
        entry["status"] = "ok"
        entry["returned"] = returned
        try:
            entry["in_transaction_after"] = self.conn.in_transaction
            entry["in_transaction_after_status"] = "ok"
        except sqlite3.Error as exc:
            entry["in_transaction_after_status"] = "error"
            entry["in_transaction_after_error"] = error_dict(exc)
        self.calls.append(entry)
        return entry

    def dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "autocommit": _attr(self.conn, "autocommit"),
            "isolation_level": _attr(self.conn, "isolation_level"),
            "connect_warnings": self.connect_warnings,
            "calls": self.calls,
            "trace": self.trace,
        }


def _attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except sqlite3.Error as exc:
        return {"error": error_dict(exc)}


def connect(path: Path, *, mode: str, timeout: float) -> tuple[sqlite3.Connection, list[str]]:
    """Open a file-backed connection in one of the three transaction-control modes.

    sqlite3.Connection has no instance dictionary, so warnings are returned
    beside the connection instead of being stored on it.
    """
    target = str(path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        connection = _connect_mode(target, mode=mode, timeout=timeout)
    return connection, [str(item.message) for item in caught]


def _connect_mode(target: str, *, mode: str, timeout: float) -> sqlite3.Connection:
    if mode == "explicit":
        # autocommit=True: sqlite3 never issues BEGIN. isolation_level is not the control.
        return sqlite3.connect(target, timeout=timeout, autocommit=True)
    if mode == "legacy":
        # Module default: LEGACY_TRANSACTION_CONTROL and isolation_level="".
        connection = sqlite3.connect(target, timeout=timeout)
        if connection.autocommit != sqlite3.LEGACY_TRANSACTION_CONTROL:
            connection.autocommit = sqlite3.LEGACY_TRANSACTION_CONTROL
        connection.isolation_level = ""
        return connection
    if mode == "pep249":
        return sqlite3.connect(target, timeout=timeout, autocommit=False)
    if mode == "legacy-none":
        # Pre-3.12 spelling of autocommit. Kept only as a comparison, not the baseline.
        return sqlite3.connect(target, timeout=timeout, isolation_level=None)
    raise ValueError(f"unknown transaction-control mode {mode}")


def apply_baseline_pragmas(session: Session, *, journal_mode: str = "DELETE") -> list[dict[str, Any]]:
    """State the configuration the experiment depends on, instead of inheriting defaults silently."""
    statements = [
        f"PRAGMA journal_mode={journal_mode}",
        "PRAGMA foreign_keys=ON",
        "PRAGMA busy_timeout=0",
    ]
    return [session.sql(statement) for statement in statements]


def read_pragmas(connection: sqlite3.Connection) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name in PRAGMA_NAMES:
        try:
            rows = [list(row) for row in connection.execute(f"PRAGMA {name}")]
            found[name] = rows
        except sqlite3.Error as exc:
            found[name] = {"error": error_dict(exc)}
    return found


def observe(path: Path, queries: dict[str, str], *, timeout: float = 0.0) -> dict[str, Any]:
    """Read a database from a connection that did not perform the experiment."""
    connection = sqlite3.connect(str(path), timeout=timeout, autocommit=True)
    try:
        report: dict[str, Any] = {
            "autocommit": connection.autocommit,
            "in_transaction": connection.in_transaction,
            "pragmas": {},
        }
        try:
            connection.execute("PRAGMA query_only=ON")
            report["query_only"] = "on"
        except sqlite3.Error as exc:
            report["query_only"] = {"error": error_dict(exc)}
        for name in ("journal_mode", "synchronous", "foreign_keys", "busy_timeout", "user_version"):
            try:
                report["pragmas"][name] = [list(row) for row in connection.execute(f"PRAGMA {name}")]
            except sqlite3.Error as exc:
                report["pragmas"][name] = {"error": error_dict(exc)}
        for name, statement in queries.items():
            try:
                cursor = connection.execute(statement)
                report[name] = {
                    "status": "ok",
                    "rows": [list(row) for row in cursor.fetchall()],
                }
            except sqlite3.Error as exc:
                report[name] = {"status": "error", "error": error_dict(exc)}
        report["in_transaction_after"] = connection.in_transaction
        return report
    finally:
        connection.close()


ITEM_ROWS = "SELECT id, name FROM item ORDER BY id"
SCHEMA = (
    "SELECT type, name, sql FROM sqlite_schema "
    "WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
)


def rows(entry: dict[str, Any] | None, key: str = "rows") -> list[list[Any]]:
    if not entry or entry.get("status") != "ok":
        return []
    value = entry.get(key)
    return value if isinstance(value, list) else []


def observer_rows(report: dict[str, Any], key: str) -> list[list[Any]] | None:
    section = report.get(key)
    if not isinstance(section, dict) or section.get("status") != "ok":
        return None
    return section.get("rows")


def names_from(pairs: list[list[Any]] | None) -> list[Any] | None:
    if pairs is None:
        return None
    return [row[1] if len(row) > 1 else row[0] for row in pairs]


def implicit_begin_count(session: Session) -> int:
    issued = 0
    for call in session.calls:
        sql = str(call.get("sql", "")).strip().upper()
        if sql == "BEGIN" or sql.startswith("BEGIN "):
            issued += 1
    traced = 0
    for event in session.trace:
        sql = str(event.get("sql", "")).strip().upper()
        if sql == "BEGIN" or sql.startswith("BEGIN "):
            traced += 1
    return traced - issued


def sidecars(path: Path) -> list[str]:
    """Lock and journal files, named by role so repetition numbers do not look like disagreement."""
    found = []
    if path.exists():
        found.append("database")
    for suffix, label in (("-journal", "journal"), ("-wal", "wal"), ("-shm", "shm")):
        if Path(str(path) + suffix).exists():
            found.append(label)
    return found


def environment_report(sample_db: Path) -> dict[str, Any]:
    """Versions and the configuration a fresh file-backed database actually opens with."""
    require_python()
    sample_db.parent.mkdir(parents=True, exist_ok=True)
    if sample_db.exists():
        sample_db.unlink()
    connection = sqlite3.connect(str(sample_db), timeout=0.0, autocommit=True)
    try:
        compile_options = [row[0] for row in connection.execute("PRAGMA compile_options")]
        source_id = list(connection.execute("SELECT sqlite_source_id()").fetchone())
        version_row = list(connection.execute("SELECT sqlite_version()").fetchone())
        default_pragmas = read_pragmas(connection)
        lock_status: Any
        try:
            lock_status = [list(row) for row in connection.execute("PRAGMA lock_status")]
        except sqlite3.Error as exc:
            lock_status = {"error": error_dict(exc)}
        module_version: Any
        try:
            module_version = sqlite3.version
        except AttributeError as exc:
            module_version = {"absent": str(exc)}
        probe_error: Any = None
        try:
            connection.execute("CREATE TABLE probe_unique(code TEXT UNIQUE)")
            connection.execute("INSERT INTO probe_unique(code) VALUES ('taken')")
            connection.execute("INSERT INTO probe_unique(code) VALUES ('taken')")
        except sqlite3.Error as exc:
            probe_error = error_dict(exc)
    finally:
        connection.close()

    return {
        "python": {
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "sqlite": {
            "library_version": sqlite3.sqlite_version,
            "library_version_info": list(sqlite3.sqlite_version_info),
            "sqlite_version_sql": version_row,
            "sqlite_source_id": source_id,
            "module_version": module_version,
            "module_version_meaning": "sqlite3.version is the DB-API module version, not the SQLite library version.",
            "apilevel": sqlite3.apilevel,
            "paramstyle": sqlite3.paramstyle,
            "threadsafety": sqlite3.threadsafety,
            "compile_options": compile_options,
            "lock_status_pragma": lock_status,
        },
        "transaction_control": {
            "LEGACY_TRANSACTION_CONTROL": sqlite3.LEGACY_TRANSACTION_CONTROL,
            "default_autocommit_on_bare_connect": _default_autocommit(sample_db),
            "modes": {
                "explicit": "connect(..., autocommit=True); experiments issue SQL BEGIN/COMMIT/ROLLBACK",
                "legacy": "autocommit=LEGACY_TRANSACTION_CONTROL and isolation_level=''",
                "pep249": "connect(..., autocommit=False)",
                "legacy-none": "connect(..., isolation_level=None), comparison only",
            },
        },
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "uname": list(os.uname()),
        },
        "fresh_file_pragmas": default_pragmas,
        "constraint_error_probe": probe_error,
        "sample_database": str(sample_db),
    }


def _default_autocommit(sample_db: Path) -> dict[str, Any]:
    other = sample_db.with_name(sample_db.stem + "-default-connect.sqlite")
    if other.exists():
        other.unlink()
    connection = sqlite3.connect(str(other))
    try:
        return {
            "autocommit": connection.autocommit,
            "isolation_level": connection.isolation_level,
            "in_transaction": connection.in_transaction,
            "timeout_attribute": getattr(connection, "timeout", "absent"),
            "busy_timeout": [list(row) for row in connection.execute("PRAGMA busy_timeout")],
        }
    finally:
        connection.close()


def experiment_error(exc: BaseException) -> dict[str, Any]:
    return {
        "status": "experiment-error",
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        },
        "observed": {"status": "experiment-error"},
    }
