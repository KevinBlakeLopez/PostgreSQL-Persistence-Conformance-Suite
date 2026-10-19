"""SQLITE-05: transactional DDL under explicit BEGIN, and the driver's implicit path.

The explicit cases use autocommit=True and SQL BEGIN/ROLLBACK. A separate
variant issues the same DDL with no BEGIN so the driver's autocommit behavior
is visible. PRAGMA user_version, journal_mode, and foreign_keys are included
because not every PRAGMA is reversible.
"""

from __future__ import annotations

from pathlib import Path

import harness


SCHEMA = {"schema": harness.SCHEMA}
ACCOUNT = {
    "schema": harness.SCHEMA,
    "migrations": "SELECT id FROM schema_migrations ORDER BY id",
    "accounts": "SELECT id, email FROM account ORDER BY id",
}


def variants() -> list[tuple[str, object]]:
    return [
        ("create-table-rollback", create_table_rollback),
        ("alter-table-rollback", alter_table_rollback),
        ("ddl-inside-savepoint", ddl_inside_savepoint),
        ("release-then-outer-rollback", release_then_outer_rollback),
        ("migration-statement-fails-then-rollback", migration_fails_then_rollback),
        ("migration-statement-fails-then-commit", migration_fails_then_commit),
        ("ddl-without-begin-explicit", ddl_without_begin),
        ("ddl-without-begin-legacy", lambda path: ddl_without_begin(path, mode="legacy")),
        ("ddl-without-begin-pep249", lambda path: ddl_without_begin(path, mode="pep249")),
        ("pragma-user-version-rollback", pragma_user_version_rollback),
        ("pragma-journal-mode-inside-transaction", pragma_journal_mode_inside_transaction),
        ("pragma-foreign-keys-inside-transaction", pragma_foreign_keys_inside_transaction),
    ]


def _session(path: Path) -> harness.Session:
    session = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    return session


def create_table_rollback(path: Path) -> dict:
    session = _session(path)
    begin = session.sql("BEGIN")
    created = session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    after_ddl = session.state("after-ddl")
    same_schema = session.sql(harness.SCHEMA)
    same_rows = session.sql("SELECT id, name FROM item ORDER BY id")
    observer_pending = harness.observe(path, {**SCHEMA, "item": harness.ITEM_ROWS})
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    observer_after = harness.observe(path, {**SCHEMA, "item": harness.ITEM_ROWS})
    session.close()
    observed = {
        "in_transaction_after_ddl": after_ddl["in_transaction"],
        "writer_schema": _schema_names(same_schema),
        "writer_rows": harness.names_from(harness.rows(same_rows)),
        "observer_pending_schema": _observer_schema_names(observer_pending),
        "observer_pending_item_status": (observer_pending.get("item") or {}).get("status"),
        "rollback_status": rolled["status"],
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "observer_after_schema": _observer_schema_names(observer_after),
        "create_status": created["status"],
        "insert_status": inserted["status"],
        "begin_status": begin["status"],
        "implicit_begin_count": harness.implicit_begin_count(session),
    }
    return _package(observed, session, observer_pending, observer_after, after_ddl, after_rollback)


def alter_table_rollback(path: Path) -> dict:
    session = _session(path)
    session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    begin = session.sql("BEGIN")
    added = session.sql("ALTER TABLE item ADD COLUMN extra TEXT")
    dropped = session.sql("ALTER TABLE item DROP COLUMN extra")
    # The DROP above would undo the ADD inside the transaction if both succeed.
    # Re-add, then roll the transaction back, so the durable table has no extra column.
    readded = session.sql("ALTER TABLE item ADD COLUMN extra TEXT")
    filled = session.sql("UPDATE item SET extra = 'pending' WHERE id = 1")
    after_ddl = session.state("after-ddl")
    writer_schema = session.sql(harness.SCHEMA)
    observer_pending = harness.observe(path, SCHEMA)
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    observer_after = harness.observe(path, {**SCHEMA, "item": "SELECT id, name FROM item ORDER BY id"})
    session.close()
    observed = {
        "begin_status": begin["status"],
        "add_status": added["status"],
        "drop_status": dropped["status"],
        "readd_status": readded["status"],
        "update_status": filled["status"],
        "add_error": (added.get("error") or {}).get("message"),
        "drop_error": (dropped.get("error") or {}).get("message"),
        "in_transaction_after_ddl": after_ddl["in_transaction"],
        "writer_schema_sql": [row[2] for row in harness.rows(writer_schema)],
        "observer_pending_schema_sql": [
            row[2] for row in (harness.observer_rows(observer_pending, "schema") or [])
        ],
        "rollback_status": rolled["status"],
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "observer_after_schema_sql": [
            row[2] for row in (harness.observer_rows(observer_after, "schema") or [])
        ],
        "observer_after_item": harness.observer_rows(observer_after, "item"),
    }
    return _package(observed, session, observer_pending, observer_after, after_ddl, after_rollback)


def ddl_inside_savepoint(path: Path) -> dict:
    session = _session(path)
    begin = session.sql("BEGIN")
    outer = session.sql("CREATE TABLE kept (id INTEGER PRIMARY KEY)")
    savepoint = session.sql("SAVEPOINT sp1")
    inner = session.sql("CREATE TABLE discarded (id INTEGER PRIMARY KEY)")
    inserted = session.sql("INSERT INTO discarded(id) VALUES (1)")
    after_inner = session.state("after-inner")
    writer_before = session.sql(harness.SCHEMA)
    rolled = session.sql("ROLLBACK TO SAVEPOINT sp1")
    after_rollback_to = session.state("after-rollback-to")
    writer_after = session.sql(harness.SCHEMA)
    released = session.sql("RELEASE SAVEPOINT sp1")
    commit = session.sql("COMMIT")
    after_commit = session.state("after-commit")
    observer = harness.observe(path, SCHEMA)
    session.close()
    observed = {
        "begin_status": begin["status"],
        "outer_status": outer["status"],
        "savepoint_status": savepoint["status"],
        "inner_status": inner["status"],
        "insert_status": inserted["status"],
        "in_transaction_after_inner": after_inner["in_transaction"],
        "writer_schema_before_rollback_to": _schema_names(writer_before),
        "rollback_to_status": rolled["status"],
        "in_transaction_after_rollback_to": after_rollback_to["in_transaction"],
        "writer_schema_after_rollback_to": _schema_names(writer_after),
        "release_status": released["status"],
        "commit_status": commit["status"],
        "in_transaction_after_commit": after_commit["in_transaction"],
        "observer_schema": _observer_schema_names(observer),
    }
    return _package(observed, session, None, observer, after_inner, after_commit)


def release_then_outer_rollback(path: Path) -> dict:
    session = _session(path)
    session.sql("BEGIN")
    session.sql("SAVEPOINT sp1")
    created = session.sql("CREATE TABLE released_ddl (id INTEGER PRIMARY KEY)")
    released = session.sql("RELEASE SAVEPOINT sp1")
    after_release = session.state("after-release")
    writer_schema = session.sql(harness.SCHEMA)
    observer_pending = harness.observe(path, SCHEMA)
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    observer_after = harness.observe(path, SCHEMA)
    session.close()
    observed = {
        "create_status": created["status"],
        "release_status": released["status"],
        "in_transaction_after_release": after_release["in_transaction"],
        "writer_schema_after_release": _schema_names(writer_schema),
        "observer_after_release": _observer_schema_names(observer_pending),
        "rollback_status": rolled["status"],
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "observer_after_rollback": _observer_schema_names(observer_after),
    }
    return _package(observed, session, observer_pending, observer_after, after_release, after_rollback)


def migration_fails_then_rollback(path: Path) -> dict:
    return _migration(path, end="ROLLBACK")


def migration_fails_then_commit(path: Path) -> dict:
    return _migration(path, end="COMMIT")


def _migration(path: Path, *, end: str) -> dict:
    session = _session(path)
    begin = session.sql("BEGIN")
    steps = [
        begin,
        session.sql("CREATE TABLE schema_migrations (id TEXT PRIMARY KEY)"),
        session.sql("CREATE TABLE account (id INTEGER PRIMARY KEY, email TEXT UNIQUE)"),
        session.sql("INSERT INTO schema_migrations(id) VALUES ('001_account')"),
        session.sql("INSERT INTO account(id, email) VALUES (1, 'a@example.com')"),
    ]
    fault = session.sql("INSERT INTO account(id, email) VALUES (2, 'a@example.com')")
    after_fault = session.state("after-fault")
    writer_schema = session.sql(harness.SCHEMA)
    writer_accounts = session.sql("SELECT id, email FROM account ORDER BY id")
    writer_migrations = session.sql("SELECT id FROM schema_migrations ORDER BY id")
    observer_pending = harness.observe(path, ACCOUNT)
    ending = session.sql(end)
    after_end = session.state("after-end")
    observer_after = harness.observe(path, ACCOUNT)
    session.close()
    observed = {
        "end": end,
        "step_statuses": [step["status"] for step in steps],
        "fault_status": fault["status"],
        "fault_error_type": (fault.get("error") or {}).get("type"),
        "fault_error_name": (fault.get("error") or {}).get("sqlite_errorname"),
        "fault_error_code": (fault.get("error") or {}).get("sqlite_errorcode"),
        "in_transaction_after_fault": after_fault["in_transaction"],
        "writer_schema_after_fault": _schema_names(writer_schema),
        "writer_accounts_after_fault": harness.rows(writer_accounts),
        "writer_migrations_after_fault": harness.rows(writer_migrations),
        "observer_pending_schema": _observer_schema_names(observer_pending),
        "end_status": ending["status"],
        "end_error_name": (ending.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_end": after_end["in_transaction"],
        "observer_after_schema": _observer_schema_names(observer_after),
        "observer_after_accounts": harness.observer_rows(observer_after, "accounts"),
        "observer_after_migrations": harness.observer_rows(observer_after, "migrations"),
        "implicit_begin_count": harness.implicit_begin_count(session),
    }
    return _package(observed, session, observer_pending, observer_after, after_fault, after_end)


def ddl_without_begin(path: Path, mode: str = "explicit") -> dict:
    session = harness.Session(path, mode=mode, timeout=0.0, name="writer")
    if mode == "explicit":
        harness.apply_baseline_pragmas(session, journal_mode="DELETE")
    created = session.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT)")
    after_create = session.state("after-create")
    inserted = session.sql("INSERT INTO item(id, name) VALUES (1, 'marker')")
    after_insert = session.state("after-insert")
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    observer = harness.observe(path, {**SCHEMA, "item": harness.ITEM_ROWS})
    session.close()
    observed = {
        "mode": mode,
        "create_status": created["status"],
        "in_transaction_after_create": after_create["in_transaction"],
        "insert_status": inserted["status"],
        "in_transaction_after_insert": after_insert["in_transaction"],
        "rollback_status": rolled["status"],
        "rollback_message": (rolled.get("error") or {}).get("message"),
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "implicit_begin_count": harness.implicit_begin_count(session),
        "trace_sql": [event["sql"] for event in session.trace],
        "observer_schema": _observer_schema_names(observer),
        "observer_item": harness.names_from(harness.observer_rows(observer, "item")),
    }
    return _package(observed, session, None, observer, after_create, after_rollback)


def pragma_user_version_rollback(path: Path) -> dict:
    session = _session(path)
    before = session.sql("PRAGMA user_version")
    begin = session.sql("BEGIN")
    set_version = session.sql("PRAGMA user_version=7")
    inside = session.sql("PRAGMA user_version")
    after_set = session.state("after-set")
    observer_pending = harness.observe(path, {"user_version": "PRAGMA user_version"})
    rolled = session.sql("ROLLBACK")
    after = session.sql("PRAGMA user_version")
    after_rollback = session.state("after-rollback")
    observer_after = harness.observe(path, {"user_version": "PRAGMA user_version"})
    session.close()
    observed = {
        "before": harness.rows(before),
        "begin_status": begin["status"],
        "set_status": set_version["status"],
        "set_rows": set_version.get("rows"),
        "inside": harness.rows(inside),
        "in_transaction_after_set": after_set["in_transaction"],
        "observer_pending": harness.observer_rows(observer_pending, "user_version"),
        "rollback_status": rolled["status"],
        "after": harness.rows(after),
        "observer_after": harness.observer_rows(observer_after, "user_version"),
    }
    return _package(observed, session, observer_pending, observer_after, after_set, after_rollback)


def pragma_journal_mode_inside_transaction(path: Path) -> dict:
    session = _session(path)
    begin = session.sql("BEGIN")
    change = session.sql("PRAGMA journal_mode=WAL")
    after = session.state("after-pragma")
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    writer_after = session.sql("PRAGMA journal_mode")
    session.close()
    observer = harness.observe(path, {"journal_mode": "PRAGMA journal_mode"})
    observed = {
        "begin_status": begin["status"],
        "change_status": change["status"],
        "change_rows": change.get("rows"),
        "change_error": (change.get("error") or {}).get("message"),
        "in_transaction_after_pragma": after["in_transaction"],
        "rollback_status": rolled["status"],
        "rollback_error": (rolled.get("error") or {}).get("message"),
        "in_transaction_after_rollback": after_rollback["in_transaction"],
        "writer_journal_mode": harness.rows(writer_after),
        "observer_journal_mode": harness.observer_rows(observer, "journal_mode"),
    }
    return _package(observed, session, None, observer, after, after_rollback)


def pragma_foreign_keys_inside_transaction(path: Path) -> dict:
    session = _session(path)
    begin = session.sql("BEGIN")
    change = session.sql("PRAGMA foreign_keys=OFF")
    inside = session.sql("PRAGMA foreign_keys")
    after = session.state("after-pragma")
    rolled = session.sql("ROLLBACK")
    after_rollback = session.state("after-rollback")
    writer_after = session.sql("PRAGMA foreign_keys")
    session.close()
    observer = harness.observe(path, {"foreign_keys": "PRAGMA foreign_keys"})
    observed = {
        "begin_status": begin["status"],
        "change_status": change["status"],
        "change_rows": change.get("rows"),
        "change_error": (change.get("error") or {}).get("message"),
        "inside_connection": harness.rows(inside),
        "in_transaction_after_pragma": after["in_transaction"],
        "rollback_status": rolled["status"],
        "writer_after": harness.rows(writer_after),
        "observer_foreign_keys": harness.observer_rows(observer, "foreign_keys"),
    }
    return _package(observed, session, None, observer, after, after_rollback)


def _schema_names(entry: dict) -> list:
    return [row[1] for row in harness.rows(entry) if len(row) > 1]


def _observer_schema_names(report: dict | None) -> list | None:
    if report is None:
        return None
    rows = harness.observer_rows(report, "schema")
    if rows is None:
        return None
    return [row[1] for row in rows if len(row) > 1]


def _package(observed, session, pending, after, left, right) -> dict:
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": {"left": left, "right": right},
        "steps": {},
        "observers": {"pending": pending, "after": after},
        "session": session.dump(),
    }
