"""SQLITE-01: unique-constraint conflict resolution inside an explicit transaction.

Each variant uses its own file. The seed row is committed before BEGIN, with
autocommit=True, so the conflict is against durable data. A second connection
reads before the conflicting statement, after it, and after the later COMMIT
or ROLLBACK.
"""

from __future__ import annotations

from pathlib import Path

import harness


QUERIES = {"item": harness.ITEM_ROWS, "schema": harness.SCHEMA}

SINGLE = {
    "default": "INSERT INTO item(id, name) VALUES (3, 'taken')",
    "abort": "INSERT OR ABORT INTO item(id, name) VALUES (3, 'taken')",
    "fail": "INSERT OR FAIL INTO item(id, name) VALUES (3, 'taken')",
    "ignore": "INSERT OR IGNORE INTO item(id, name) VALUES (3, 'taken')",
    "rollback": "INSERT OR ROLLBACK INTO item(id, name) VALUES (3, 'taken')",
    "replace": "INSERT OR REPLACE INTO item(id, name) VALUES (6, 'taken')",
}

MULTI = {
    "abort": (
        "INSERT OR ABORT INTO item(id, name) "
        "SELECT 4, 'from-statement' UNION ALL SELECT 5, 'taken'"
    ),
    "fail": (
        "INSERT OR FAIL INTO item(id, name) "
        "SELECT 4, 'from-statement' UNION ALL SELECT 5, 'taken'"
    ),
    "ignore": (
        "INSERT OR IGNORE INTO item(id, name) "
        "SELECT 4, 'from-statement' UNION ALL SELECT 5, 'taken'"
    ),
    "rollback": (
        "INSERT OR ROLLBACK INTO item(id, name) "
        "SELECT 4, 'from-statement' UNION ALL SELECT 5, 'taken'"
    ),
}


def variants() -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    for name in SINGLE:
        found.append((f"single-{name}", _make("single", name, SINGLE[name])))
    for name in MULTI:
        found.append((f"multi-{name}", _make("multi", name, MULTI[name])))
    return found


def _make(shape: str, resolution: str, statement: str):
    def run(path: Path) -> dict:
        return conflict(path, shape=shape, resolution=resolution, statement=statement)

    return run


def conflict(path: Path, *, shape: str, resolution: str, statement: str) -> dict:
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    setup = harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    setup.append(session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"))
    setup.append(session.sql("INSERT INTO item(id, name) VALUES (1, 'taken')"))
    after_setup = session.state("after-setup")
    observer_after_setup = harness.observe(path, QUERIES)

    begin = session.sql("BEGIN")
    marker = session.sql("INSERT INTO item(id, name) VALUES (2, 'marker')")
    before_fault = session.state("before-fault")
    same_before = session.sql("SELECT id, name FROM item ORDER BY id")
    observer_before = harness.observe(path, QUERIES)

    fault = session.sql(statement)
    after_fault = session.state("after-fault")
    same_after = session.sql("SELECT id, name FROM item ORDER BY id")
    changes = session.sql("SELECT changes()")
    observer_after_fault = harness.observe(path, QUERIES)

    followup = session.sql("INSERT INTO item(id, name) VALUES (8, 'after')")
    after_followup = session.state("after-followup")
    same_after_followup = session.sql("SELECT id, name FROM item ORDER BY id")
    observer_after_followup = harness.observe(path, QUERIES)

    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer_after_commit = harness.observe(path, QUERIES)
    closed = session.close()

    same_after_names = harness.names_from(harness.rows(same_after))
    observed = {
        "shape": shape,
        "resolution": resolution,
        "setup_in_transaction": after_setup["in_transaction"],
        "seed_visible_before_begin": harness.names_from(
            harness.observer_rows(observer_after_setup, "item")
        ),
        "in_transaction_before_fault": before_fault["in_transaction"],
        "fault_status": fault["status"],
        "fault_error_type": (fault.get("error") or {}).get("type"),
        "fault_error_name": (fault.get("error") or {}).get("sqlite_errorname"),
        "fault_error_code": (fault.get("error") or {}).get("sqlite_errorcode"),
        "fault_rowcount": fault.get("rowcount"),
        "in_transaction_after_fault": after_fault["in_transaction"],
        "same_connection_after_fault": same_after_names,
        "from_statement_visible_after_fault": (
            None if same_after_names is None else "from-statement" in same_after_names
        ),
        "marker_visible_on_writer_after_fault": (
            None if same_after_names is None else "marker" in same_after_names
        ),
        "changes_after_fault": harness.rows(changes),
        "observer_after_fault": harness.names_from(harness.observer_rows(observer_after_fault, "item")),
        "followup_status": followup["status"],
        "followup_error_name": (followup.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_followup": after_followup["in_transaction"],
        "observer_after_followup": harness.names_from(
            harness.observer_rows(observer_after_followup, "item")
        ),
        "commit_status": commit["status"],
        "commit_error_type": (commit.get("error") or {}).get("type"),
        "commit_error_name": (commit.get("error") or {}).get("sqlite_errorname"),
        "commit_rowcount": commit.get("rowcount"),
        "commit_description": commit.get("description"),
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer_after_commit": harness.names_from(harness.observer_rows(observer_after_commit, "item")),
        "implicit_begin_count": harness.implicit_begin_count(session),
        "close_status": closed["status"],
    }
    return {
        "status": "recorded",
        "statement": statement,
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": {
            "after_setup": after_setup,
            "before_fault": before_fault,
            "after_fault": after_fault,
            "after_followup": after_followup,
            "after_commit": after_commit,
        },
        "writer_reads": {
            "before_fault": same_before,
            "after_fault": same_after,
            "after_followup": same_after_followup,
        },
        "steps": {
            "setup": setup,
            "begin": begin,
            "marker": marker,
            "fault": fault,
            "changes": changes,
            "followup": followup,
            "commit": commit,
            "close": closed,
        },
        "observers": {
            "after_setup": observer_after_setup,
            "before_fault": observer_before,
            "after_fault": observer_after_fault,
            "after_followup": observer_after_followup,
            "after_commit": observer_after_commit,
        },
        "session": session.dump(),
    }
