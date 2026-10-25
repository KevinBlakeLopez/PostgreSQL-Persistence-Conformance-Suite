"""SQLITE-05c, container side: a real ENOSPC in the middle of a transaction.

Runs inside a disposable Linux container whose /data is a small tmpfs, so a
write SQLite makes can fail with ENOSPC ("database or disk is full"). Nothing
here injects a fault: a filler file leaves TARGET_FREE bytes free on the
tmpfs, and the transaction writes more than that. SQLite's default page cache
(2000 KiB) means the pages reach the file only when the cache spills, in the
middle of an INSERT.

    python -I sqlite05c_enospc_container.py <variant> <token>

variant: raw | default | autocommit-false | begin-recipe
Prints one JSON document on stdout. Self-contained: no study imports.

No `from __future__ import annotations` here: the ORM model is declared
inside a function, and its Mapped[...] annotations must be evaluated there.
"""

import json
import os
import sqlite3
import sys

DATA = "/data"
DB = os.path.join(DATA, "db.sqlite")
FILLER = os.path.join(DATA, "filler.bin")
TARGET_FREE = 3 * 1024 * 1024
RECORDS = 30
PAYLOAD = 200 * 1024


def free_bytes() -> int:
    st = os.statvfs(DATA)
    return st.f_bavail * st.f_frsize


def error(exc: BaseException | None) -> dict | None:
    if exc is None:
        return None
    chain, link, seen = [], exc, set()
    while link is not None and id(link) not in seen and len(chain) < 4:
        seen.add(id(link))
        chain.append(f"{type(link).__qualname__}: {str(link).splitlines()[0] if str(link) else ''}")
        link = link.__cause__ or link.__context__
    driver = exc if isinstance(exc, sqlite3.Error) else getattr(exc, "orig", None)
    return {
        "chain": chain,
        "sqlite_errorname": getattr(driver, "sqlite_errorname", None),
        "sqlite_errorcode": getattr(driver, "sqlite_errorcode", None),
    }


def prepare() -> dict:
    conn = sqlite3.connect(DB, autocommit=True)
    conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, token TEXT NOT NULL, "
                 "seq INTEGER NOT NULL, payload BLOB NOT NULL)")
    conn.close()
    before = free_bytes()
    with open(FILLER, "wb") as handle:
        remaining = before - TARGET_FREE
        chunk = b"\0" * (1024 * 1024)
        while remaining > 0:
            handle.write(chunk[:min(len(chunk), remaining)])
            remaining -= len(chunk)
    return {"free_before_filler": before, "free_after_filler": free_bytes(),
            "db_bytes": os.path.getsize(DB)}


def committed(token: str) -> list[int]:
    conn = sqlite3.connect(DB, autocommit=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        return [r[0] for r in conn.execute("SELECT seq FROM records WHERE token = ? ORDER BY seq", (token,))]
    finally:
        conn.close()


def raw(token: str) -> dict:
    """An explicit transaction: one INSERT per record until the first error."""
    conn = sqlite3.connect(DB, timeout=0.0, autocommit=True)
    conn.execute("BEGIN")
    first_error = None
    failed_seq = None
    for seq in range(1, RECORDS + 1):
        try:
            conn.execute("INSERT INTO records(token, seq, payload) VALUES (?, ?, randomblob(?))",
                         (token, seq, PAYLOAD))
        except sqlite3.Error as exc:
            first_error, failed_seq = error(exc), seq
            break
    in_tx_after_error = conn.in_transaction
    commit_error = None
    try:
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        commit_error = error(exc)
    conn.close()
    return {
        "failed_seq": failed_seq,
        "first_error": first_error,
        "in_transaction_after_error": in_tx_after_error,
        "commit_error": commit_error,
        "committed_seqs": committed(token),
    }


def documented_batch(config: str, token: str) -> dict:
    """SQLAlchemy's documented SAVEPOINT loop with a bare except (session_transaction.rst)."""
    import sqlalchemy
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

    class Base(DeclarativeBase):
        pass

    class Record(Base):
        __tablename__ = "records"
        id: Mapped[int] = mapped_column(primary_key=True)
        token: Mapped[str]
        seq: Mapped[int]
        payload: Mapped[bytes]

    kwargs = {"connect_args": {"autocommit": False}} if config == "autocommit-false" else {}
    engine = create_engine(f"sqlite:///{DB}", **kwargs)
    if config == "begin-recipe":
        @event.listens_for(engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def do_begin(conn):
            conn.exec_driver_sql("BEGIN")

    skipped: list[dict] = []
    session = Session(engine)
    commit_error = None
    try:
        for seq in range(1, RECORDS + 1):
            try:
                with session.begin_nested():
                    session.merge(Record(token=token, seq=seq, payload=os.urandom(PAYLOAD)))
            except:  # noqa: E722 -- the documented example's bare except
                skipped.append({"seq": seq, "error": error(sys.exc_info()[1])})
        try:
            session.commit()
        except Exception as exc:
            commit_error = error(exc)
    finally:
        session.close()
        engine.dispose()
    skipped_seqs = [s["seq"] for s in skipped]
    claimed = [s for s in range(1, RECORDS + 1) if s not in skipped_seqs] if commit_error is None else []
    persisted = committed(token)
    return {
        "sqlalchemy": sqlalchemy.__version__,
        "skipped": skipped,
        "commit_error": commit_error,
        "application_claims_committed": claimed,
        "committed_seqs": persisted,
        "claim_matches_database": claimed == persisted,
    }


def main() -> None:
    variant, token = sys.argv[1], sys.argv[2]
    out = {
        "variant": variant,
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "records": RECORDS,
        "payload_bytes": PAYLOAD,
        "target_free_bytes": TARGET_FREE,
        "setup": prepare(),
    }
    out["result"] = raw(token) if variant == "raw" else documented_batch(variant, token)
    out["free_at_end"] = free_bytes()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
