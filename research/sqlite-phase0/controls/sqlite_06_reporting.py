"""SQLITE-06: what sqlite3 itself exposes after commit, rollback, and failure.

A lost network reply has no counterpart in this embedded library. The
subprocess variants terminate a child process. They record only outcomes that
were actually produced. A trace-callback kill during COMMIT is an attempt to
interrupt the commit before execute() returns; if COMMIT returns, the attempt
is recorded as not reproduced.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import harness
import sqlite_02_commit_busy as busy


QUERIES = {"item": harness.ITEM_ROWS}


def variants() -> list[tuple[str, object]]:
    return [
        ("sql-commit-success", sql_commit_success),
        ("sql-rollback-success", sql_rollback_success),
        ("method-commit-after-explicit-begin", method_commit_after_explicit_begin),
        ("method-rollback-after-explicit-begin", method_rollback_after_explicit_begin),
        ("method-commit-with-no-transaction", method_commit_with_no_transaction),
        ("method-commit-isolation-level-none", method_commit_isolation_level_none),
        ("failed-commit-busy", failed_commit_busy),
        ("failed-rollback-to-savepoint", failed_rollback_to_savepoint),
        ("constraint-violation", constraint_violation),
        ("close-with-pending-changes", close_with_pending_changes),
        ("executescript-during-pending-transaction", executescript_during_pending_transaction),
        ("subprocess-killed-before-commit", subprocess_killed_before_commit),
        ("subprocess-killed-after-commit-returned", subprocess_killed_after_commit_returned),
        ("subprocess-killed-in-commit-trace", subprocess_killed_in_commit_trace),
    ]


def _prepare(path: Path) -> harness.Session:
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    return session


def sql_commit_success(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-commit")
    commit = session.sql("COMMIT")
    after = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = _outcome("sql-commit", inserted, commit, before, after, observer)
    return _package(observed, session, observer)


def sql_rollback_success(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-rollback")
    rolled = session.sql("ROLLBACK")
    after = session.state("after-rollback")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = _outcome("sql-rollback", inserted, rolled, before, after, observer)
    return _package(observed, session, observer)


def method_commit_after_explicit_begin(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-method")
    method = session.commit_method()
    after = session.state("after-method")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = _outcome("connection-commit", inserted, method, before, after, observer)
    observed["trace_sql"] = [event["sql"] for event in session.trace]
    return _package(observed, session, observer)


def method_rollback_after_explicit_begin(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-method")
    method = session.rollback_method()
    after = session.state("after-method")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = _outcome("connection-rollback", inserted, method, before, after, observer)
    observed["trace_sql"] = [event["sql"] for event in session.trace]
    return _package(observed, session, observer)


def method_commit_isolation_level_none(path: Path) -> dict:
    """isolation_level=None keeps autocommit at LEGACY. commit() is not the autocommit=True no-op."""
    session = harness.Session(path, mode="legacy-none", timeout=0.0, name="writer")
    session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    session.sql("BEGIN")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-method")
    method = session.commit_method()
    after = session.state("after-method")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = _outcome("connection-commit-isolation-level-none", inserted, method, before, after, observer)
    observed["trace_sql"] = [event["sql"] for event in session.trace]
    observed["connect_warnings"] = session.connect_warnings
    return _package(observed, session, observer)


def method_commit_with_no_transaction(path: Path) -> dict:
    session = _prepare(path)
    before = session.state("before-method")
    method = session.commit_method()
    after = session.state("after-method")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "kind": "connection-commit-without-transaction",
        "before_in_transaction": before["in_transaction"],
        "method_status": method["status"],
        "method_returned": method.get("returned", None),
        "method_error_type": (method.get("error") or {}).get("type"),
        "method_message": (method.get("error") or {}).get("message"),
        "after_in_transaction": after["in_transaction"],
        "trace_sql": [event["sql"] for event in session.trace],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, observer)


def failed_commit_busy(path: Path) -> dict:
    result = busy.commit_contention(path, journal_mode="DELETE", with_reader=True)
    observed = {
        "kind": "failed-commit-busy",
        "first_commit_status": result["observed"]["first_commit_status"],
        "first_commit_error_type": result["observed"]["first_commit_error_type"],
        "first_commit_error_name": result["observed"]["first_commit_error_name"],
        "first_commit_error_code": result["observed"]["first_commit_error_code"],
        "in_transaction_before": result["observed"]["in_transaction_before_commit"],
        "in_transaction_after_failed_commit": result["observed"]["in_transaction_after_first_commit"],
        "retry_commit_status": result["observed"]["retry_commit_status"],
        "in_transaction_after_retry": result["observed"]["in_transaction_after_retry"],
        "observer_during": result["observed"]["observer_during"],
        "observer_after_retry": result["observed"]["observer_after_retry"],
        "writer_still_sees_marker": result["observed"]["writer_sees_marker_after_first_commit"],
    }
    result["observed_reporting"] = observed
    result["fingerprint"] = harness.fingerprint(observed)
    return result


def failed_rollback_to_savepoint(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'kept')")
    before = session.state("before")
    missing = session.sql("ROLLBACK TO SAVEPOINT does_not_exist")
    after = session.state("after-error")
    follow = session.sql("INSERT INTO item(id, name) VALUES (2, 'after')")
    commit = session.sql("COMMIT")
    end = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "kind": "failed-rollback-to",
        "before_in_transaction": before["in_transaction"],
        "error_status": missing["status"],
        "error_type": (missing.get("error") or {}).get("type"),
        "error_name": (missing.get("error") or {}).get("sqlite_errorname"),
        "error_code": (missing.get("error") or {}).get("sqlite_errorcode"),
        "error_message": (missing.get("error") or {}).get("message"),
        "after_in_transaction": after["in_transaction"],
        "followup_status": follow["status"],
        "commit_status": commit["status"],
        "commit_rowcount": commit.get("rowcount"),
        "commit_description": commit.get("description"),
        "end_in_transaction": end["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, observer)


def constraint_violation(path: Path) -> dict:
    session = _prepare(path)
    session.sql("INSERT INTO item(id, name) VALUES (1, 'taken')")
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (2, 'marker')")
    before = session.state("before")
    fault = session.sql("INSERT INTO item(id, name) VALUES (3, 'taken')")
    after = session.state("after-error")
    follow = session.sql("SELECT id, name FROM item ORDER BY id")
    commit = session.sql("COMMIT")
    end = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "kind": "constraint",
        "before_in_transaction": before["in_transaction"],
        "error_status": fault["status"],
        "error_type": (fault.get("error") or {}).get("type"),
        "error_name": (fault.get("error") or {}).get("sqlite_errorname"),
        "error_code": (fault.get("error") or {}).get("sqlite_errorcode"),
        "error_message": (fault.get("error") or {}).get("message"),
        "after_in_transaction": after["in_transaction"],
        "writer_rows": harness.names_from(harness.rows(follow)),
        "commit_status": commit["status"],
        "commit_rowcount": commit.get("rowcount"),
        "commit_description": commit.get("description"),
        "end_in_transaction": end["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, observer)


def close_with_pending_changes(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    before = session.state("before-close")
    closed = session.close()
    follow_error = None
    try:
        session.conn.execute("SELECT 1")
    except Exception as exc:
        follow_error = harness.error_dict(exc)
    observer = harness.observe(path, QUERIES)
    observed = {
        "kind": "close-pending",
        "before_in_transaction": before["in_transaction"],
        "close_status": closed["status"],
        "close_returned": closed.get("returned"),
        "in_transaction_after_close_status": closed.get("in_transaction_after_status"),
        "in_transaction_after_close_error": closed.get("in_transaction_after_error"),
        "statement_after_close": follow_error,
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, observer)


def executescript_during_pending_transaction(path: Path) -> dict:
    session = _prepare(path)
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'pending')")
    before = session.state("before-script")
    entry = {
        "method": "Connection.executescript()",
        "sql": "INSERT INTO item(id, name) VALUES (2, 'scripted');",
        "in_transaction_before": session.in_transaction(),
    }
    try:
        returned = session.conn.executescript(entry["sql"])
        entry["status"] = "ok"
        entry["returned_type"] = type(returned).__name__
    except Exception as exc:
        entry["status"] = "error"
        entry["error"] = harness.error_dict(exc)
    entry["in_transaction_after"] = session.in_transaction()
    after = session.state("after-script")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "kind": "executescript",
        "before_in_transaction": before["in_transaction"],
        "script_status": entry["status"],
        "script_error_type": (entry.get("error") or {}).get("type"),
        "script_message": (entry.get("error") or {}).get("message"),
        "after_in_transaction": after["in_transaction"],
        "trace_sql": [event["sql"] for event in session.trace],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, observer, extra_steps={"executescript": entry})


def subprocess_killed_before_commit(path: Path) -> dict:
    return _child(path, "kill-before-commit")


def subprocess_killed_after_commit_returned(path: Path) -> dict:
    return _child(path, "kill-after-commit-returned")


def subprocess_killed_in_commit_trace(path: Path) -> dict:
    return _child(path, "kill-in-commit-trace")


def _child(path: Path, kind: str) -> dict:
    harness.require_python()
    if path.exists():
        path.unlink()
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--child", kind, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
    observer = harness.observe(path, QUERIES) if path.exists() else {"item": {"status": "missing-database"}}
    observed = {
        "kind": kind,
        "child_returncode": proc.returncode,
        "child_stdout": stdout,
        "child_stderr": stderr,
        "commit_returned_in_child_output": "commit-returned" in stdout,
        "killed_marker_in_child_output": any(token in stdout for token in ("ready-to-kill", "trace-commit")),
        "observer": harness.names_from(harness.observer_rows(observer, "item")) if isinstance(observer.get("item"), dict) else None,
        "observer_status": (observer.get("item") or {}).get("status") if isinstance(observer.get("item"), dict) else "missing-database",
        "sidecars": harness.sidecars(path),
        "synchronous": (observer.get("pragmas") or {}).get("synchronous") if isinstance(observer, dict) else None,
    }
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint({
            "kind": kind,
            "returncode": proc.returncode,
            "commit_returned": observed["commit_returned_in_child_output"],
            "observer": observed["observer"],
            "stdout": stdout,
        }),
        "checkpoints": {},
        "steps": {},
        "observers": {"after_child": observer},
        "session": None,
    }


def child_main(kind: str, path: Path) -> None:
    """Run inside the child process. SIGKILL is used so the process cannot run atexit cleanup."""
    session = _prepare(path)
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    if kind == "kill-before-commit":
        print("ready-to-kill", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
        print("commit-returned", flush=True)
        return
    if kind == "kill-after-commit-returned":
        session.sql("COMMIT")
        print("commit-returned", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
        return
    if kind == "kill-in-commit-trace":
        def on_trace(sql: str) -> None:
            if sql.strip().upper() == "COMMIT":
                print("trace-commit", flush=True)
                os.kill(os.getpid(), signal.SIGKILL)

        session.conn.set_trace_callback(on_trace)
        session.sql("COMMIT")
        print("commit-returned", flush=True)
        return
    raise SystemExit(f"unknown child kind {kind}")


def _outcome(kind, inserted, terminal, before, after, observer) -> dict:
    return {
        "kind": kind,
        "insert_status": inserted["status"],
        "terminal_status": terminal["status"],
        "terminal_returned": terminal.get("returned", None),
        "terminal_rowcount": terminal.get("rowcount"),
        "terminal_description": terminal.get("description"),
        "terminal_lastrowid": terminal.get("lastrowid"),
        "terminal_error_type": (terminal.get("error") or {}).get("type"),
        "terminal_error_name": (terminal.get("error") or {}).get("sqlite_errorname"),
        "terminal_error_code": (terminal.get("error") or {}).get("sqlite_errorcode"),
        "terminal_message": (terminal.get("error") or {}).get("message"),
        "before_in_transaction": before["in_transaction"],
        "after_in_transaction": after["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
        "command_tag": None,
        "sqlstate": None,
    }


def _package(observed, session, observer, extra_steps=None) -> dict:
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": {},
        "steps": extra_steps or {},
        "observers": {"after": observer},
        "session": session.dump(),
    }


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--child":
        child_main(sys.argv[2], Path(sys.argv[3]))
    else:
        raise SystemExit("run this module through run_all.py")
