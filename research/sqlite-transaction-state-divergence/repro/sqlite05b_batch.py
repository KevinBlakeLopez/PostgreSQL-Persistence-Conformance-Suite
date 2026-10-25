"""SQLITE-05b: SQLAlchemy's documented SAVEPOINT batch patterns when one record ends the transaction.

SQLAlchemy 2.1's ORM guide, "Using SAVEPOINT"
(doc/build/orm/session_transaction.rst, rel_2_1_6, lines 157-168 and 177-188),
shows two loops that skip a failing record "without rolling back the whole
transaction":

    docs-merge-bare-except   for record in records:
                                 try:
                                     with session.begin_nested():
                                         session.merge(record)
                                 except:
                                     print("Skipped record %s" % record)
                             session.commit()

    docs-add-integrityerror  with session.begin():
                                 for record in records:
                                     try:
                                         with session.begin_nested():
                                             session.add(obj)
                                     except exc.IntegrityError:
                                         print(...)

    core-except-exception    the same loop in Core: engine.begin(),
                             conn.begin_nested(), except Exception

Ten records are imported. Record 5 carries a 256 KiB payload; the others carry
100 bytes. What makes record 5 fail:

    none            nothing: all ten fit (control)
    raise-abort     a BEFORE INSERT trigger: RAISE(ABORT, 'payload too large')
    raise-rollback  the same trigger with RAISE(ROLLBACK, ...)
    full            no trigger; PRAGMA max_page_count, set on every connection,
                    leaves room for the small records only: SQLITE_FULL

The application reports which records it imported and skipped and whether the
commit returned. An independent connection reads what was committed.

    .venv/bin/python -I repro/sqlite05b_batch.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
from sqlite02_core import Engine, require_versions, status, write_stray_pool_log  # noqa: E402

from sqlalchemy import event, exc, insert  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column  # noqa: E402


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str]
    seq: Mapped[int]
    payload: Mapped[bytes]


CONFIGS = ("default", "autocommit-false", "begin-recipe")
PATTERNS = ("docs-merge-bare-except", "docs-add-integrityerror", "core-except-exception")
TRIGGERS = ("none", "raise-abort", "raise-rollback", "full")
BIG = 5
SEQS = list(range(1, 11))


def setup(path: Path, trigger: str) -> int:
    conn = sqlite3.connect(str(path), autocommit=True)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, token TEXT NOT NULL, "
                     "seq INTEGER NOT NULL, payload BLOB NOT NULL)")
        if trigger in ("raise-abort", "raise-rollback"):
            action = "ABORT" if trigger == "raise-abort" else "ROLLBACK"
            conn.execute(
                "CREATE TRIGGER reject_large_payload BEFORE INSERT ON records "
                f"WHEN length(NEW.payload) > 100000 BEGIN SELECT RAISE({action}, 'payload too large'); END")
        return conn.execute("PRAGMA page_count").fetchone()[0]
    finally:
        conn.close()


def payload(seq: int) -> bytes:
    return bytes([seq % 256]) * (262144 if seq == BIG else 100)


def scenario(config: str, pattern: str, trigger: str) -> Callable[[Path, str], dict[str, Any]]:
    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        sink = common.Sink(work / "sink.sqlite")
        pages = setup(path, trigger)
        eng = Engine(path, config, token)
        limit = pages + 16
        if trigger == "full":
            @event.listens_for(eng.engine, "connect")
            def cap(dbapi_connection, record):
                dbapi_connection.execute(f"PRAGMA max_page_count = {limit}")

        per_record: list[dict[str, Any]] = []
        skipped: list[int] = []

        def sqlite_state() -> dict[str, Any]:
            return {f"dbapi{i}": common.in_transaction(c) for i, c in enumerate(eng.dbapi)}

        def note(seq: int, handled: BaseException | None, sa_in_tx: bool) -> None:
            per_record.append({
                "seq": seq,
                "handled": None if handled is None else common.error_dict(handled)["chain"][:3],
                "sa_in_transaction_after": sa_in_tx,
                "sqlite_in_transaction_after": sqlite_state(),
            })

        def after_commit(session) -> None:
            sink.record(token, "after_commit")

        event.listen(Session, "after_commit", after_commit)

        def docs_merge_bare_except() -> None:
            session = Session(eng.engine)
            try:
                for seq in SEQS:
                    handled = None
                    try:
                        with session.begin_nested():
                            session.merge(Record(token=token, seq=seq, payload=payload(seq)))
                    except:  # noqa: E722 -- the documented example's bare except
                        handled = sys.exc_info()[1]
                        skipped.append(seq)
                    note(seq, handled, session.in_transaction())
                session.commit()
            finally:
                session.close()

        def docs_add_integrityerror() -> None:
            with Session(eng.engine) as session:
                with session.begin():
                    for seq in SEQS:
                        handled = None
                        try:
                            with session.begin_nested():
                                session.add(Record(token=token, seq=seq, payload=payload(seq)))
                        except exc.IntegrityError as error:
                            handled = error
                            skipped.append(seq)
                        note(seq, handled, session.in_transaction())

        def core_except_exception() -> None:
            table = Record.__table__
            with eng.engine.begin() as conn:
                for seq in SEQS:
                    handled = None
                    try:
                        with conn.begin_nested():
                            conn.execute(insert(table).values(token=token, seq=seq, payload=payload(seq)))
                    except Exception as error:
                        handled = error
                        skipped.append(seq)
                    note(seq, handled, conn.in_transaction())

        body = {"docs-merge-bare-except": docs_merge_bare_except,
                "docs-add-integrityerror": docs_add_integrityerror,
                "core-except-exception": core_except_exception}[pattern]
        try:
            outcome = common.call("import", body)
        finally:
            event.remove(Session, "after_commit", after_commit)
            finished = eng.finish()

        committed = common.observe(path, {"seqs": f"SELECT seq FROM records WHERE token = '{token}' ORDER BY seq"})
        persisted = [row[0] for row in committed["seqs"]] if isinstance(committed["seqs"], list) else committed["seqs"]
        claimed = [seq for seq in SEQS if seq not in skipped] if outcome["status"] == "ok" else []
        if outcome["status"] == "ok":
            sink.record(token, "application-reported-import", f"imported {len(claimed)}, skipped {skipped}")
        observed = {
            "configuration": {"config": config, "pattern": pattern, "trigger": trigger,
                              "max_page_count": limit if trigger == "full" else None,
                              "dbapi_at_connect": eng.dbapi_config},
            "import_outcome": status(outcome),
            "import_error_chain": (outcome.get("error") or {}).get("chain"),
            "application_skipped": skipped,
            "application_claims_committed": claimed,
            "persisted_seqs": persisted,
            "claim_matches_database": claimed == persisted,
            "sink": sink.read(token),
            "per_record": per_record,
            "warnings": outcome.get("warnings"),
            "pool_at_end": finished,
        }
        return {
            "observed": observed,
            "trace": [f"dbapi{e['dbapi']}: {e['sql']}"[:160] for e in eng.trace],
            "events": eng.events,
            "pool_log_all": eng.pool_log,
        }

    return run


def main() -> None:
    require_versions()
    variants = [
        (f"{config}.{pattern}.{trigger}", scenario(config, pattern, trigger))
        for config in CONFIGS
        for pattern in PATTERNS
        for trigger in TRIGGERS
    ]
    run_dir = common.run_experiment("sqlite05b-batch", variants)
    write_stray_pool_log(run_dir)


if __name__ == "__main__":
    main()
