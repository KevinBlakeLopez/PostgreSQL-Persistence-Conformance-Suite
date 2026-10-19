"""SQLITE-03: savepoint release, rollback-to, and a missing savepoint.

RELEASE is not a durable commit. ROLLBACK of the outer transaction is what
the second connection is asked to confirm. A missing savepoint is attempted
with the outer transaction still open, because SQLite is not assumed to abort
the transaction the way PostgreSQL aborts it on 3B001.
"""

from __future__ import annotations

from pathlib import Path

import harness


QUERIES = {"item": harness.ITEM_ROWS, "schema": harness.SCHEMA}


def variants() -> list[tuple[str, object]]:
    return [
        ("release-then-outer-rollback", release_then_outer_rollback),
        ("rollback-to-then-commit", rollback_to_then_commit),
        ("rollback-to-missing", rollback_to_missing),
        ("rollback-to-already-released", rollback_to_already_released),
    ]


def _prepare(path: Path) -> harness.Session:
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    return session


def release_then_outer_rollback(path: Path) -> dict:
    session = _prepare(path)
    begin = session.sql("BEGIN")
    savepoint = session.sql("SAVEPOINT sp1")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'released')")
    after_insert = session.state("after-insert")
    same_after_insert = session.sql("SELECT id, name FROM item ORDER BY id")
    released = session.sql("RELEASE SAVEPOINT sp1")
    after_release = session.state("after-release")
    same_after_release = session.sql("SELECT id, name FROM item ORDER BY id")
    observer_after_release = harness.observe(path, QUERIES)
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    observer_after_rollback = harness.observe(path, QUERIES)
    closed = session.close()
    observed = {
        "in_transaction_after_insert": after_insert["in_transaction"],
        "release_status": released["status"],
        "in_transaction_after_release": after_release["in_transaction"],
        "writer_after_release": harness.names_from(harness.rows(same_after_release)),
        "observer_after_release": harness.names_from(harness.observer_rows(observer_after_release, "item")),
        "rollback_status": rolled["status"],
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "observer_after_rollback": harness.names_from(harness.observer_rows(observer_after_rollback, "item")),
        "implicit_begin_count": harness.implicit_begin_count(session),
    }
    return _package(observed, session, {
        "begin": begin,
        "savepoint": savepoint,
        "inserted": inserted,
        "same_after_insert": same_after_insert,
        "released": released,
        "rolled": rolled,
        "closed": closed,
    }, {
        "after_release": observer_after_release,
        "after_rollback": observer_after_rollback,
    }, {
        "after_insert": after_insert,
        "after_release": after_release,
        "after_rollback": after_rollback,
    })


def rollback_to_then_commit(path: Path) -> dict:
    session = _prepare(path)
    begin = session.sql("BEGIN")
    outer = session.sql("INSERT INTO item(id, name) VALUES (1, 'outer')")
    savepoint = session.sql("SAVEPOINT sp1")
    inner = session.sql("INSERT INTO item(id, name) VALUES (2, 'inner')")
    after_inner = session.state("after-inner")
    rolled = session.sql("ROLLBACK TO SAVEPOINT sp1")
    after_rollback_to = session.state("after-rollback-to")
    same_after = session.sql("SELECT id, name FROM item ORDER BY id")
    # ROLLBACK TO leaves the savepoint in place. Releasing it records that fact.
    released = session.sql("RELEASE SAVEPOINT sp1")
    continued = session.sql("INSERT INTO item(id, name) VALUES (3, 'after')")
    after_continue = session.state("after-continue")
    observer_before_commit = harness.observe(path, QUERIES)
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer_after_commit = harness.observe(path, QUERIES)
    closed = session.close()
    observed = {
        "in_transaction_after_inner": after_inner["in_transaction"],
        "rollback_to_status": rolled["status"],
        "rollback_to_error_name": (rolled.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_rollback_to": after_rollback_to["in_transaction"],
        "writer_after_rollback_to": harness.names_from(harness.rows(same_after)),
        "release_after_rollback_to_status": released["status"],
        "release_after_rollback_to_error_name": (released.get("error") or {}).get("sqlite_errorname"),
        "continue_status": continued["status"],
        "in_transaction_after_continue": after_continue["in_transaction"],
        "observer_before_commit": harness.names_from(harness.observer_rows(observer_before_commit, "item")),
        "commit_status": commit["status"],
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer_after_commit": harness.names_from(harness.observer_rows(observer_after_commit, "item")),
    }
    return _package(observed, session, {
        "begin": begin,
        "outer": outer,
        "savepoint": savepoint,
        "inner": inner,
        "rolled": rolled,
        "released": released,
        "continued": continued,
        "commit": commit,
        "closed": closed,
    }, {
        "before_commit": observer_before_commit,
        "after_commit": observer_after_commit,
    }, {
        "after_inner": after_inner,
        "after_rollback_to": after_rollback_to,
        "after_continue": after_continue,
        "after_commit": after_commit,
    })


def rollback_to_missing(path: Path) -> dict:
    return _missing(path, release_first=False)


def rollback_to_already_released(path: Path) -> dict:
    return _missing(path, release_first=True)


def _missing(path: Path, *, release_first: bool) -> dict:
    session = _prepare(path)
    begin = session.sql("BEGIN")
    kept = session.sql("INSERT INTO item(id, name) VALUES (1, 'kept')")
    savepoint = None
    nested = None
    released = None
    if release_first:
        savepoint = session.sql("SAVEPOINT sp1")
        nested = session.sql("INSERT INTO item(id, name) VALUES (2, 'nested')")
        released = session.sql("RELEASE SAVEPOINT sp1")
    before = session.state("before-missing-rollback")
    same_before = session.sql("SELECT id, name FROM item ORDER BY id")
    missing = session.sql("ROLLBACK TO SAVEPOINT sp1" if release_first else "ROLLBACK TO SAVEPOINT does_not_exist")
    after = session.state("after-missing-rollback")
    same_after = session.sql("SELECT id, name FROM item ORDER BY id")
    followup = session.sql("INSERT INTO item(id, name) VALUES (3, 'after')")
    after_followup = session.state("after-followup")
    observer_before_commit = harness.observe(path, QUERIES)
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer_after_commit = harness.observe(path, QUERIES)
    closed = session.close()
    observed = {
        "release_first": release_first,
        "release_status": None if released is None else released["status"],
        "in_transaction_before": before["in_transaction"],
        "writer_before": harness.names_from(harness.rows(same_before)),
        "missing_status": missing["status"],
        "missing_error_type": (missing.get("error") or {}).get("type"),
        "missing_error_name": (missing.get("error") or {}).get("sqlite_errorname"),
        "missing_error_code": (missing.get("error") or {}).get("sqlite_errorcode"),
        "missing_message": (missing.get("error") or {}).get("message"),
        "in_transaction_after_error": after["in_transaction"],
        "writer_after_error": harness.names_from(harness.rows(same_after)),
        "followup_status": followup["status"],
        "followup_error_name": (followup.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_followup": after_followup["in_transaction"],
        "observer_before_commit": harness.names_from(harness.observer_rows(observer_before_commit, "item")),
        "commit_status": commit["status"],
        "commit_error_name": (commit.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer_after_commit": harness.names_from(harness.observer_rows(observer_after_commit, "item")),
    }
    return _package(observed, session, {
        "begin": begin,
        "kept": kept,
        "savepoint": savepoint,
        "nested": nested,
        "released": released,
        "missing": missing,
        "followup": followup,
        "commit": commit,
        "closed": closed,
    }, {
        "before_commit": observer_before_commit,
        "after_commit": observer_after_commit,
    }, {
        "before": before,
        "after": after,
        "after_followup": after_followup,
        "after_commit": after_commit,
    })


def _package(observed, session, steps, observers, checkpoints) -> dict:
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": checkpoints,
        "steps": steps,
        "observers": observers,
        "session": session.dump(),
    }
