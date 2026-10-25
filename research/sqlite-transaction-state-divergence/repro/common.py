"""Shared recording helpers for the SQLite transaction-state divergence study.

Four evidence layers are kept apart (see ../methodology.md):

- A, SQLite's own state: Connection.in_transaction on the connection under
  test (the negation of sqlite3_get_autocommit()), and the SQL SQLite actually
  started, from Connection.set_trace_callback.
- B, framework state: recorded by each experiment through public APIs.
  Private attributes are recorded only under keys that say "private".
- C, persisted state: rows read by a separate sqlite3 connection, opened with
  autocommit=True and PRAGMA query_only=ON. It sees committed rows only.
- D, external effects: callbacks write to a separate sink database through a
  connection of their own (Sink below).

Recorded output must not carry local paths: every string is passed through
scrub() before it is written.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import sqlite3
import sys
import traceback
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


STUDY = Path(__file__).resolve().parents[1]
WORKTREE = STUDY.parents[1]
# Smoke runs set STUDY_OUTPUT to a scratch directory; recorded runs use output/.
OUTPUT = Path(os.environ.get("STUDY_OUTPUT", STUDY / "output"))
REPETITIONS = 3
MIN_PYTHON = (3, 12)


def require_python() -> None:
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required for sqlite3 "
            f"Connection.autocommit and sqlite_errorcode; this is {sys.version}"
        )


# ---------------------------------------------------------------- scrubbing

def _scrub_pairs() -> list[tuple[str, str]]:
    pairs = [
        (str(STUDY), "$STUDY"),
        (str(WORKTREE), "$WORKTREE"),
        (str(Path.home()), "$HOME"),
    ]
    for name in ("TMPDIR",):
        value = os.environ.get(name)
        if value:
            pairs.append((value.rstrip("/"), "$TMPDIR"))
    # Longest first, so the study directory wins over the worktree and $HOME.
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


SCRUB = _scrub_pairs()


def scrub(text: str) -> str:
    for needle, replacement in SCRUB:
        text = text.replace(needle, replacement)
    return text


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, Path):
        return scrub(str(value))
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return scrub(repr(value))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ------------------------------------------------------------------- errors

def error_dict(exc: BaseException | None) -> dict[str, Any] | None:
    """An exception, plus the sqlite3 error underneath any framework wrapper."""
    if exc is None:
        return None
    record: dict[str, Any] = {
        "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
        "message": str(exc).splitlines()[0] if str(exc) else "",
    }
    chain = []
    seen = set()
    link: BaseException | None = exc
    while link is not None and id(link) not in seen and len(chain) < 6:
        seen.add(id(link))
        chain.append(f"{type(link).__qualname__}: {str(link).splitlines()[0] if str(link) else ''}")
        link = link.__cause__ or link.__context__
    record["chain"] = chain  # the exception, then its __cause__ or __context__, and so on
    driver = _driver_error(exc)
    if driver is not None:
        code = getattr(driver, "sqlite_errorcode", None)
        record["driver"] = {
            "type": f"{type(driver).__module__}.{type(driver).__qualname__}",
            "message": str(driver),
            "sqlite_errorcode": code,
            "sqlite_errorname": getattr(driver, "sqlite_errorname", None),
            "primary_code": code & 0xFF if isinstance(code, int) else None,
        }
    return record


def _driver_error(exc: BaseException) -> BaseException | None:
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, sqlite3.Error):
            return current
        orig = getattr(current, "orig", None)  # SQLAlchemy DBAPIError
        if isinstance(orig, sqlite3.Error):
            return orig
        current = current.__cause__ or current.__context__
    return None


def call(label: str, fn: Callable[[], Any], **extra: Any) -> dict[str, Any]:
    """Run one step and record its return value or exception, and any warnings it emitted."""
    entry: dict[str, Any] = {"step": label, **extra}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            value = fn()
        except Exception as exc:  # recorded, never swallowed silently
            entry["status"] = "error"
            entry["error"] = error_dict(exc)
            entry["traceback_tail"] = [scrub(line.rstrip()) for line in traceback.format_exception(exc)[-3:]]
            entry["warnings"] = [f"{w.category.__name__}: {w.message}" for w in caught]
            return entry
    entry["warnings"] = [f"{w.category.__name__}: {w.message}" for w in caught]
    entry["status"] = "ok"
    entry["returned"] = value if isinstance(value, (int, float, str, bool, type(None), list, dict)) else repr(value)
    return entry


# ---------------------------------------------------------------- layer A

class Trace:
    """SQL that SQLite started on one connection, with in_transaction at that moment.

    CPython's trace callback runs when a statement starts. A trigger
    subprogram restarting the same statement can appear as a repeated line.
    """

    def __init__(self, connection: sqlite3.Connection, name: str = "writer"):
        self.connection = connection
        self.name = name
        self.events: list[dict[str, Any]] = []
        connection.set_trace_callback(self._on_trace)

    def _on_trace(self, sql: str) -> None:
        try:
            state = self.connection.in_transaction
        except sqlite3.Error as exc:  # closed connection
            state = {"error": str(exc)}
        self.events.append({"sql": sql, "in_transaction_before": state})

    def statements(self) -> list[str]:
        return [event["sql"] for event in self.events]


def in_transaction(connection: Any) -> Any:
    try:
        return connection.in_transaction
    except sqlite3.Error as exc:
        return {"error": error_dict(exc)}


# ---------------------------------------------------------------- layer C

def observe(path: Path, queries: dict[str, str]) -> dict[str, Any]:
    """Read the database file from a connection that did not run the experiment."""
    connection = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        report: dict[str, Any] = {"observer_in_transaction": connection.in_transaction}
        for name, statement in queries.items():
            try:
                report[name] = [list(row) for row in connection.execute(statement).fetchall()]
            except sqlite3.Error as exc:
                report[name] = {"error": error_dict(exc)}
        return report
    finally:
        connection.close()


# ---------------------------------------------------------------- layer D

class Sink:
    """An independent sink for callbacks: its own file, its own connection per write."""

    def __init__(self, path: Path):
        self.path = path
        connection = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS effect ("
                " seq INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL,"
                " event TEXT NOT NULL, detail TEXT)"
            )
        finally:
            connection.close()

    def record(self, token: str, event: str, detail: str = "") -> None:
        connection = sqlite3.connect(str(self.path), timeout=0.0, autocommit=True)
        try:
            connection.execute(
                "INSERT INTO effect(token, event, detail) VALUES (?, ?, ?)", (token, event, detail)
            )
        finally:
            connection.close()

    def read(self, token: str) -> list[list[Any]]:
        connection = sqlite3.connect(str(self.path), timeout=0.0, autocommit=True)
        try:
            return [
                list(row)
                for row in connection.execute(
                    "SELECT event, detail FROM effect WHERE token = ? ORDER BY seq", (token,)
                )
            ]
        finally:
            connection.close()


# ------------------------------------------------------------- environment

def environment() -> dict[str, Any]:
    probe = sqlite3.connect(":memory:")
    try:
        compile_options = [row[0] for row in probe.execute("PRAGMA compile_options")]
        source_id = probe.execute("SELECT sqlite_source_id()").fetchone()[0]
    finally:
        probe.close()
    default = sqlite3.connect(":memory:")
    try:
        default_control = {
            "autocommit": default.autocommit,
            "isolation_level": default.isolation_level,
            "in_transaction": default.in_transaction,
        }
    finally:
        default.close()
    packages: dict[str, Any] = {}
    for name in ("sqlalchemy", "django", "aiosqlite", "greenlet"):
        try:
            module = __import__(name)
            packages[name] = getattr(module, "__version__", None) or getattr(module, "get_version", lambda: None)()
        except ImportError:
            packages[name] = None
    return {
        "python": {
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "sqlite": {
            "library_version": sqlite3.sqlite_version,
            "source_id": source_id,
            "compile_options": compile_options,
            "threadsafety": sqlite3.threadsafety,
            "LEGACY_TRANSACTION_CONTROL": sqlite3.LEGACY_TRANSACTION_CONTROL,
            "default_connect": default_control,
        },
        "packages": packages,
        "os": {"platform": platform.platform(), "machine": platform.machine()},
    }


# ------------------------------------------------------------------ runner

def new_token() -> str:
    """A unique identifier written into every row a repetition creates."""
    return uuid.uuid4().hex


def mask(value: Any, tokens: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: mask(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [mask(item, tokens) for item in value]
    if isinstance(value, str):
        for token in tokens:
            value = value.replace(token, "<token>")
        return value
    return value


def run_experiment(
    experiment: str,
    variants: list[tuple[str, Callable[[Path, str], dict[str, Any]]]],
    *,
    repetitions: int = REPETITIONS,
    fingerprint_keys: tuple[str, ...] = ("observed", "trace"),
) -> Path:
    """Run every variant `repetitions` times on fresh files and record agreement.

    Each variant function receives a fresh work directory and a unique token,
    and returns a dict that includes an "observed" section. The fingerprint is
    the masked JSON of fingerprint_keys; repetitions agree when it is equal.
    """
    require_python()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"{stamp}-{secrets.token_hex(3)}"
    run_dir = OUTPUT / experiment / run_id
    write_json(run_dir / "environment.json", environment())
    summary: dict[str, Any] = {"experiment": experiment, "run_id": run_id, "repetitions": repetitions, "variants": {}}
    all_agree = True
    for name, fn in variants:
        prints = []
        for rep in range(1, repetitions + 1):
            work = run_dir / "db" / f"{name}.rep{rep}"
            work.mkdir(parents=True, exist_ok=True)
            token = new_token()
            try:
                record = fn(work, token)
            except Exception as exc:  # an experiment bug, recorded as such
                record = {"experiment_error": error_dict(exc), "traceback": traceback.format_exc(), "observed": None}
            record = {"variant": name, "repetition": rep, "token": token, **record}
            write_json(run_dir / "cases" / f"{name}.rep{rep}.json", record)
            masked = mask(jsonable({key: record.get(key) for key in fingerprint_keys}), [token])
            prints.append(json.dumps(masked, sort_keys=True))
        agree = len(set(prints)) == 1
        all_agree &= agree
        first = json.loads(prints[0])
        summary["variants"][name] = {"agreement": agree, "observed": first.get("observed")}
    summary["agreement"] = all_agree
    write_json(run_dir / "summary.json", summary)
    print(f"{experiment}: {run_id}: {len(variants)} variants x {repetitions}, agreement={all_agree}")
    return run_dir
