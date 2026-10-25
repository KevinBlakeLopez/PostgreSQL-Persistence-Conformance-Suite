"""Session.close() keeps the pooled connection when the rollback inside it raises.

Engine: connect_args={"autocommit": False} (SQLAlchemy's SQLite docs), a pool
of one. Inside `with Session(engine)`, session.execute() runs an INSERT that
violates UNIQUE ... ON CONFLICT ROLLBACK, so SQLite rolls the transaction back
itself. The error leaves the block; the rollback that Session.close()
performs then fails with sqlite3's "cannot rollback - no transaction is
active". The pooled connection stays checked out until the garbage collector
frees the Session.

(Through session.flush() instead, the flush rolls back first and close() does
return the connection; this script uses session.execute().)

    python sa_session_close_leak.py
"""

import gc
import logging
import os
import tempfile

from sqlalchemy import String, create_engine, insert, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class PoolMessages(logging.Handler):
    """Print what the pool logs as one line, instead of a full traceback."""

    def emit(self, record: logging.LogRecord) -> None:
        exc = record.exc_info[1] if record.exc_info else None
        print(f"pool logged: {record.getMessage()} ({type(exc).__name__}: {exc})" if exc
              else f"pool logged: {record.getMessage()}")


logging.getLogger("sqlalchemy.pool").addHandler(PoolMessages())


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, sqlite_on_conflict_unique="ROLLBACK")


path = os.path.join(tempfile.mkdtemp(), "demo.db")
engine = create_engine(f"sqlite:///{path}", connect_args={"autocommit": False},
                       pool_size=1, max_overflow=0, pool_timeout=1)
Base.metadata.create_all(engine)

try:
    with Session(engine) as session:
        session.execute(insert(Item).values(code="a"))
        session.execute(insert(Item).values(code="a"))  # violates the constraint
        session.commit()
except Exception as exc:
    print("left the block:", type(exc).__name__, "-", str(exc).splitlines()[0])
    chain, link = [], exc
    while link is not None:
        chain.append(f"{type(link).__module__.split('.')[0]}.{type(link).__name__}")
        link = link.__cause__ or link.__context__
    print("exception chain:", " <- ".join(chain))
    del exc, link

print("checked out after the block:", engine.pool.checkedout())
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("next checkout: ok")
except Exception as exc:
    print("next checkout:", type(exc).__name__)

gc.collect()
print("checked out after gc.collect():", engine.pool.checkedout())
with engine.connect() as conn:
    print("next checkout after gc.collect():", conn.execute(text("SELECT 1")).scalar())
engine.dispose()
