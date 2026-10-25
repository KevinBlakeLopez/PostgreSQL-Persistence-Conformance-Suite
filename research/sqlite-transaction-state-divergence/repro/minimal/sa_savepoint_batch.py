"""The documented SAVEPOINT loop on SQLite, when one record makes SQLite end the transaction.

Engine setup: the "BEGIN" recipe from SQLAlchemy's SQLite dialect docs
("Enabling Non-Legacy SQLite Transactional Modes"). Loop: the first example in
the ORM guide's "Using SAVEPOINT" section. Record "b" appears twice; what
makes the second "b" fail:

    on-conflict  UNIQUE ... ON CONFLICT ROLLBACK, declared with
                 sqlite_on_conflict_unique="ROLLBACK"
    page-limit   PRAGMA max_page_count leaves no room for record "big":
                 SQLITE_FULL ("database or disk is full")

    python sa_savepoint_batch.py on-conflict
    python sa_savepoint_batch.py page-limit
"""

import os
import sqlite3
import sys
import tempfile

from sqlalchemy import LargeBinary, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

trigger = sys.argv[1] if len(sys.argv) > 1 else "on-conflict"


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "record"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String, unique=True,
        sqlite_on_conflict_unique="ROLLBACK" if trigger == "on-conflict" else None)
    payload: Mapped[bytes] = mapped_column(LargeBinary)


path = os.path.join(tempfile.mkdtemp(), "demo.db")
engine = create_engine(f"sqlite:///{path}")


@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None  # the recipe: sqlite3 emits no BEGIN
    if trigger == "page-limit":
        dbapi_connection.execute("PRAGMA max_page_count = 16")  # room for small rows only


@event.listens_for(engine, "begin")
def do_begin(conn):
    conn.exec_driver_sql("BEGIN")  # the recipe: SQLAlchemy emits BEGIN


Base.metadata.create_all(engine)

if trigger == "on-conflict":
    records = [("a", b"."), ("b", b"."), ("c", b"."), ("b", b"."), ("d", b"."), ("e", b".")]
else:
    records = [("a", b"."), ("b", b"."), ("c", b"."), ("big", b"x" * 262144), ("d", b"."), ("e", b".")]

session = Session(engine)
for code, payload in records:
    try:
        with session.begin_nested():
            session.merge(Record(code=code, payload=payload))
    except:  # noqa: E722 -- as in the documented example
        print("Skipped record %s" % code)
session.commit()
print("session.commit() returned")
session.close()
engine.dispose()

check = sqlite3.connect(path)
print("committed:", [row[0] for row in check.execute("SELECT code FROM record ORDER BY id")])
check.close()
