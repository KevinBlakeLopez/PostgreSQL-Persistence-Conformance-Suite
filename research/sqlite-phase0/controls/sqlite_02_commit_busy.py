"""SQLITE-02: COMMIT while another connection holds a read lock.

Rollback-journal mode is the case the assignment asks for. WAL mode is a
separate variant with its own result. Synchronization is threading.Event,
not a sleep. timeout=0 makes SQLite return SQLITE_BUSY instead of waiting.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import harness


QUERIES = {"item": harness.ITEM_ROWS}
BARRIER_SECONDS = 5.0


def variants() -> list[tuple[str, object]]:
    return [
        ("delete-journal-no-reader", lambda path: commit_contention(path, journal_mode="DELETE", with_reader=False)),
        ("delete-journal-reader-holds-shared", lambda path: commit_contention(path, journal_mode="DELETE", with_reader=True)),
        ("wal-reader-holds-snapshot", lambda path: commit_contention(path, journal_mode="WAL", with_reader=True)),
    ]


def commit_contention(path: Path, *, journal_mode: str, with_reader: bool) -> dict:
    setup = harness.Session(path, mode="explicit", timeout=0.0, name="setup")
    setup_steps = harness.apply_baseline_pragmas(setup, journal_mode=journal_mode)
    setup_steps.append(setup.sql("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"))
    setup_steps.append(setup.sql("INSERT INTO item(id, name) VALUES (1, 'seed')"))
    setup_state = setup.state("after-setup")
    journal = setup.sql("PRAGMA journal_mode")
    setup.close()

    writer_reserved = threading.Event()
    reader_holding = threading.Event()
    release_reader = threading.Event()
    reader_released = threading.Event()
    mailbox: queue.Queue[dict] = queue.Queue()

    def reader() -> None:
        session = harness.Session(path, mode="explicit", timeout=0.0, name="reader")
        try:
            if not writer_reserved.wait(BARRIER_SECONDS):
                mailbox.put({"event": "writer-reserved-timeout"})
                return
            begin = session.sql("BEGIN DEFERRED")
            read = session.sql("SELECT id, name FROM item ORDER BY id")
            lock_status = session.sql("PRAGMA lock_status")
            mailbox.put({
                "event": "holding",
                "begin": begin,
                "read": read,
                "lock_status": lock_status,
                "in_transaction": session.in_transaction(),
            })
            reader_holding.set()
            if not release_reader.wait(BARRIER_SECONDS):
                mailbox.put({"event": "release-timeout", "in_transaction": session.in_transaction()})
                return
            rolled = session.sql("ROLLBACK")
            mailbox.put({
                "event": "released",
                "rollback": rolled,
                "in_transaction": session.in_transaction(),
                "trace": session.trace,
                "calls": session.calls,
            })
        except Exception as exc:  # a barrier failure is evidence, not a retry
            mailbox.put({"event": "reader-error", "error": harness.error_dict(exc) if hasattr(exc, "sqlite_errorcode") or isinstance(exc, Exception) else str(exc), "message": str(exc), "type": type(exc).__name__})
        finally:
            reader_holding.set()
            reader_released.set()
            try:
                session.close()
            except Exception as exc:
                mailbox.put({"event": "reader-close-error", "message": str(exc), "type": type(exc).__name__})

    reader_thread = None
    if with_reader:
        reader_thread = threading.Thread(target=reader, name="sqlite-02-reader")
        reader_thread.start()

    writer = harness.Session(path, mode="explicit", timeout=0.0, name="writer")
    begin = writer.sql("BEGIN DEFERRED")
    marker = writer.sql("INSERT INTO item(id, name) VALUES (2, 'marker')")
    writer_lock_after_insert = writer.sql("PRAGMA lock_status")
    before_commit = writer.state("before-commit")
    writer_reserved.set()

    reader_events: list[dict] = []
    if with_reader:
        held = reader_holding.wait(BARRIER_SECONDS)
        if not held:
            reader_events.append({"event": "reader-holding-timeout"})
    else:
        held = True

    first_commit = writer.sql("COMMIT")
    writer_lock_after_first_commit = writer.sql("PRAGMA lock_status")
    after_first_commit = writer.state("after-first-commit")
    writer_view = writer.sql("SELECT id, name FROM item ORDER BY id")
    observer_during = harness.observe(path, QUERIES)

    if with_reader:
        release_reader.set()
        released = reader_released.wait(BARRIER_SECONDS)
        if reader_thread is not None:
            reader_thread.join(BARRIER_SECONDS)
        while not mailbox.empty():
            reader_events.append(mailbox.get())
    else:
        released = True

    if after_first_commit["in_transaction"] is True:
        retry = writer.sql("COMMIT")
    else:
        retry = {
            "status": "not-issued",
            "reason": "the first COMMIT left the connection outside a transaction",
            "in_transaction_before": after_first_commit["in_transaction"],
        }
    after_retry = writer.state("after-retry")
    observer_after = harness.observe(path, QUERIES)
    closed = writer.close()

    holding = next((item for item in reader_events if item.get("event") == "holding"), None)
    observed = {
        "journal_mode_requested": journal_mode,
        "journal_mode_reported": harness.rows(journal),
        "with_reader": with_reader,
        "reader_reached_holding_barrier": (holding is not None) if with_reader else None,
        "reader_released_barrier": bool(released) if with_reader else None,
        "reader_thread_alive_after_join": reader_thread.is_alive() if reader_thread is not None else False,
        "setup_in_transaction": setup_state["in_transaction"],
        "in_transaction_before_commit": before_commit["in_transaction"],
        "first_commit_status": first_commit["status"],
        "first_commit_error_type": (first_commit.get("error") or {}).get("type"),
        "first_commit_error_name": (first_commit.get("error") or {}).get("sqlite_errorname"),
        "first_commit_error_code": (first_commit.get("error") or {}).get("sqlite_errorcode"),
        "in_transaction_after_first_commit": after_first_commit["in_transaction"],
        "writer_sees_marker_after_first_commit": "marker" in (harness.names_from(harness.rows(writer_view)) or []),
        "writer_lock_after_insert": harness.rows(writer_lock_after_insert),
        "writer_lock_after_first_commit": harness.rows(writer_lock_after_first_commit),
        "reader_lock_while_holding": None if holding is None else harness.rows(holding.get("lock_status") or {}),
        "observer_during": harness.names_from(harness.observer_rows(observer_during, "item")),
        "observer_during_status": (observer_during.get("item") or {}).get("status"),
        "observer_during_error_name": ((observer_during.get("item") or {}).get("error") or {}).get("sqlite_errorname"),
        "reader_saw": None if holding is None else harness.names_from(harness.rows(holding.get("read") or {})),
        "retry_commit_status": retry["status"],
        "retry_commit_error_name": (retry.get("error") or {}).get("sqlite_errorname"),
        "in_transaction_after_retry": after_retry["in_transaction"],
        "observer_after_retry": harness.names_from(harness.observer_rows(observer_after, "item")),
        "implicit_begin_count": harness.implicit_begin_count(writer),
    }
    return {
        "status": "recorded",
        "observed": observed,
        "fingerprint": harness.fingerprint(observed),
        "checkpoints": {
            "after_setup": setup_state,
            "before_commit": before_commit,
            "after_first_commit": after_first_commit,
            "after_retry": after_retry,
        },
        "steps": {
            "setup": setup_steps,
            "begin": begin,
            "marker": marker,
            "first_commit": first_commit,
            "writer_view_after_first_commit": writer_view,
            "retry_commit": retry,
            "close": closed,
        },
        "reader_events": reader_events,
        "observers": {"during": observer_during, "after_retry": observer_after},
        "writer_session": writer.dump(),
        "lock_status_available": False,
        "interpretation": (
            "SQLite does not expose the connection's lock mode to this probe. "
            "The sequence above is the operation order and the errors it produced. "
            "Mapping those operations onto SHARED, RESERVED, PENDING, and EXCLUSIVE "
            "is an interpretation of SQLite's locking documentation, not a direct observation."
        ),
    }
