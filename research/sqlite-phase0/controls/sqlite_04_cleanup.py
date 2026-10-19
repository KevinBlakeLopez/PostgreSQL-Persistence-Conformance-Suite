"""SQLITE-04: closing a connection with pending work, and what reuse would require.

No pool is implemented. The reuse variants borrow the same open connection for
a second unit of work and record whether that unit joins the first transaction.
"""

from __future__ import annotations

from pathlib import Path

import harness


QUERIES = {"item": harness.ITEM_ROWS, "schema": harness.SCHEMA}


def variants() -> list[tuple[str, object]]:
    return [
        ("explicit-begin-close", lambda path: close_pending(path, mode="explicit", savepoint=False, autocommit_insert=False)),
        ("explicit-begin-savepoint-close", lambda path: close_pending(path, mode="explicit", savepoint=True, autocommit_insert=False)),
        ("legacy-implicit-dml-close", lambda path: close_pending(path, mode="legacy", savepoint=False, autocommit_insert=False)),
        ("pep249-implicit-dml-close", lambda path: close_pending(path, mode="pep249", savepoint=False, autocommit_insert=False)),
        ("explicit-autocommit-insert-close", lambda path: close_pending(path, mode="explicit", savepoint=False, autocommit_insert=True)),
        ("legacy-none-explicit-begin-close", lambda path: close_pending(path, mode="legacy-none", savepoint=False, autocommit_insert=False)),
        ("context-manager-does-not-begin", context_manager_does_not_begin),
        ("context-manager-commits-explicit-begin", context_manager_commits_explicit_begin),
        ("context-manager-rolls-back-on-exception", context_manager_rolls_back_on_exception),
        ("legacy-context-manager-commits-implicit", legacy_context_manager_commits_implicit),
        ("reuse-while-transaction-open", reuse_while_transaction_open),
        ("reuse-after-explicit-rollback", reuse_after_explicit_rollback),
        ("reuse-after-constraint-without-rollback", reuse_after_constraint_without_rollback),
        ("implicit-begin-matrix", implicit_begin_matrix),
    ]


def _committed_schema(path: Path) -> None:
    """Create the table through autocommit so later rollback probes do not also undo setup."""
    session = harness.Session(path, mode="explicit", timeout=0.0, name="setup")
    harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    created = session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    if created["status"] != "ok" or session.in_transaction() is True:
        raise RuntimeError(f"schema setup did not leave autocommit: {created}")
    session.close()


def close_pending(path: Path, *, mode: str, savepoint: bool, autocommit_insert: bool) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode=mode, timeout=0.0, name="writer")
    steps = []
    if autocommit_insert:
        steps.append(session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')"))
    else:
        if mode == "explicit" or mode == "legacy-none":
            steps.append(session.sql("BEGIN"))
        steps.append(session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')"))
        if savepoint:
            steps.append(session.sql("SAVEPOINT sp1"))
            steps.append(session.sql("INSERT INTO item(id, name) VALUES (2, 'inside-savepoint')"))
    before_close = session.state("before-close")
    same_before = session.sql("SELECT id, name FROM item ORDER BY id")
    observer_before = harness.observe(path, QUERIES)
    closed = session.close()
    observer_after = harness.observe(path, QUERIES)
    observed = {
        "mode": mode,
        "savepoint": savepoint,
        "autocommit_insert": autocommit_insert,
        "in_transaction_before_close": before_close["in_transaction"],
        "autocommit_before_close": before_close["autocommit"],
        "isolation_level": before_close["isolation_level"],
        "writer_before_close": harness.names_from(harness.rows(same_before)),
        "observer_before_close": harness.names_from(harness.observer_rows(observer_before, "item")),
        "close_status": closed["status"],
        "close_returned": closed.get("returned"),
        "in_transaction_after_close_status": closed.get("in_transaction_after_status"),
        "in_transaction_after_close_error_type": (closed.get("in_transaction_after_error") or {}).get("type"),
        "observer_after_close": harness.names_from(harness.observer_rows(observer_after, "item")),
        "implicit_begin_count": harness.implicit_begin_count(session),
        "sidecars": harness.sidecars(path),
    }
    return _package(observed, session, {"steps": steps, "closed": closed}, {"before": observer_before, "after": observer_after}, {"before_close": before_close})


def context_manager_does_not_begin(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    with session.conn:
        inside = session.state("inside-empty-with")
    after = session.state("after-with")
    observer = harness.observe(path, QUERIES)
    closed = session.close()
    observed = {
        "in_transaction_inside_empty_with": inside["in_transaction"],
        "in_transaction_after_with": after["in_transaction"],
        "trace_sql": [event["sql"] for event in session.trace],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
        "close_status": closed["status"],
    }
    return _package(observed, session, {}, {"after": observer}, {"inside": inside, "after": after})


def context_manager_commits_explicit_begin(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    with session.conn:
        begin = session.sql("BEGIN")
        inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
        inside = session.state("inside-with")
    after = session.state("after-with")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "begin_status": begin["status"],
        "insert_status": inserted["status"],
        "in_transaction_inside": inside["in_transaction"],
        "in_transaction_after": after["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
        "implicit_begin_count": harness.implicit_begin_count(session),
    }
    return _package(observed, session, {"begin": begin, "inserted": inserted}, {"after": observer}, {"inside": inside, "after": after})


def context_manager_rolls_back_on_exception(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    caught = None
    try:
        with session.conn:
            session.sql("BEGIN")
            session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
            raise RuntimeError("application error inside with")
    except RuntimeError as exc:
        caught = {"type": type(exc).__name__, "message": str(exc)}
    after = session.state("after-with")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "caught": caught,
        "in_transaction_after": after["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, {}, {"after": observer}, {"after": after})


def legacy_context_manager_commits_implicit(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="legacy", timeout=0.0, name="writer")
    with session.conn:
        inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
        inside = session.state("inside-with")
    after = session.state("after-with")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "insert_status": inserted["status"],
        "in_transaction_inside": inside["in_transaction"],
        "in_transaction_after": after["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
        "implicit_begin_count": harness.implicit_begin_count(session),
        "trace_sql": [event["sql"] for event in session.trace],
    }
    return _package(observed, session, {"inserted": inserted}, {"after": observer}, {"inside": inside, "after": after})


def reuse_while_transaction_open(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="pooled")
    first_begin = session.sql("BEGIN")
    doomed = session.sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
    after_unit1 = session.state("after-unit1")
    second_begin = session.sql("BEGIN")
    after_second_begin = session.state("after-second-begin")
    nxt = session.sql("INSERT INTO item(id, name) VALUES (2, 'next')")
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "first_begin_status": first_begin["status"],
        "doomed_status": doomed["status"],
        "in_transaction_after_unit1": after_unit1["in_transaction"],
        "second_begin_status": second_begin["status"],
        "second_begin_error_name": (second_begin.get("error") or {}).get("sqlite_errorname"),
        "second_begin_message": (second_begin.get("error") or {}).get("message"),
        "in_transaction_after_second_begin": after_second_begin["in_transaction"],
        "next_status": nxt["status"],
        "commit_status": commit["status"],
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, {
        "first_begin": first_begin,
        "doomed": doomed,
        "second_begin": second_begin,
        "next": nxt,
        "commit": commit,
    }, {"after": observer}, {"after_unit1": after_unit1, "after_second_begin": after_second_begin, "after_commit": after_commit})


def reuse_after_explicit_rollback(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="pooled")
    session.sql("BEGIN")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'doomed')")
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    second = session.sql("BEGIN")
    nxt = session.sql("INSERT INTO item(id, name) VALUES (2, 'next')")
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "rollback_status": rolled["status"],
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "second_begin_status": second["status"],
        "next_status": nxt["status"],
        "commit_status": commit["status"],
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, {}, {"after": observer}, {"after_rollback": after_rollback, "after_commit": after_commit})


def reuse_after_constraint_without_rollback(path: Path) -> dict:
    _committed_schema(path)
    session = harness.Session(path, mode="explicit", timeout=0.0, name="pooled")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'taken')")
    session.sql("BEGIN")
    doomed = session.sql("INSERT INTO item(id, name) VALUES (2, 'doomed')")
    fault = session.sql("INSERT INTO item(id, name) VALUES (3, 'taken')")
    after_fault = session.state("after-fault")
    second_begin = session.sql("BEGIN")
    after_second_begin = session.state("after-second-begin")
    nxt = session.sql("INSERT INTO item(id, name) VALUES (4, 'next')")
    same = session.sql("SELECT id, name FROM item ORDER BY id")
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer = harness.observe(path, QUERIES)
    session.close()
    observed = {
        "doomed_status": doomed["status"],
        "fault_status": fault["status"],
        "fault_error_name": (fault.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_fault": after_fault["in_transaction"],
        "second_begin_status": second_begin["status"],
        "second_begin_message": (second_begin.get("error") or {}).get("message"),
        "in_transaction_after_second_begin": after_second_begin["in_transaction"],
        "next_status": nxt["status"],
        "writer_before_commit": harness.names_from(harness.rows(same)),
        "commit_status": commit["status"],
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, {"fault": fault, "second_begin": second_begin, "commit": commit}, {"after": observer}, {
        "after_fault": after_fault,
        "after_second_begin": after_second_begin,
        "after_commit": after_commit,
    })


def implicit_begin_matrix(path: Path) -> dict:
    """Which statements cause the driver to issue BEGIN, one fresh connection per statement.

    INSERT and SELECT run against a table that was committed by a separate
    autocommit connection. The probed connection's trace therefore contains
    only the statement under test and any BEGIN the driver adds.
    """
    statements = [
        "CREATE TABLE seen(id INTEGER)",
        "INSERT INTO item(id, name) VALUES (1, 'marker')",
        "SELECT id, name FROM item ORDER BY id",
        "PRAGMA user_version=3",
    ]
    matrix = []
    for mode in ("explicit", "legacy", "pep249"):
        for statement in statements:
            probe_path = path.with_name(path.stem + f"-{mode}-{_slug(statement)}.sqlite")
            if probe_path.exists():
                probe_path.unlink()
            _committed_schema(probe_path)
            session = harness.Session(probe_path, mode=mode, timeout=0.0, name=mode)
            opened_in_transaction = session.in_transaction()
            # autocommit=False opens inside a transaction. Roll that back first so the
            # probed statement is what starts the next one, if anything does.
            if opened_in_transaction is True:
                session.sql("ROLLBACK")
            probed = session.sql(statement)
            state = session.state("after-statement")
            record = {
                "mode": mode,
                "statement": statement,
                "opened_in_transaction": opened_in_transaction,
                "status": probed["status"],
                "error_name": (probed.get("error") or {}).get("sqlite_errorname"),
                "in_transaction_before_close": state["in_transaction"],
                "implicit_begin_count": harness.implicit_begin_count(session),
                "trace_sql": [event["sql"] for event in session.trace],
            }
            session.close()
            observer = harness.observe(probe_path, {
                "schema": harness.SCHEMA,
                "item": harness.ITEM_ROWS,
                "user_version": "PRAGMA user_version",
            })
            record["observer_schema_names"] = [
                row[1] for row in (harness.observer_rows(observer, "schema") or []) if len(row) > 1
            ]
            record["observer_item"] = harness.names_from(harness.observer_rows(observer, "item"))
            record["observer_user_version"] = harness.observer_rows(observer, "user_version")
            matrix.append(record)
    observed = {"matrix": matrix}
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": {},
        "steps": {},
        "observers": {},
        "session": None,
    }


def _slug(statement: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in statement)[:40].strip("-")


def _package(observed, session, steps, observers, checkpoints) -> dict:
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": checkpoints,
        "steps": steps,
        "observers": observers,
        "session": None if session is None else session.dump(),
    }
