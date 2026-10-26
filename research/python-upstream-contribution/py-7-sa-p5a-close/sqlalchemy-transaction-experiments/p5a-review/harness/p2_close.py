"""The draft's case 1 sequence with psycopg2, to compare SQLAlchemy versions.

psycopg2 connections cannot take instance attributes, so the commit failure
is injected through a connection_factory subclass. It raises RuntimeError
before psycopg2 sends COMMIT. rollback() is counted and passed through.

Usage: python p2_close.py [future]
"""

import sys

import psycopg2
import psycopg2.extensions as ext
import sqlalchemy
from sqlalchemy import create_engine, text

URL = "postgresql+psycopg2://postgres@127.0.0.1:55454/scratch"
TABLE = "p5a_review_p2"
STATUS = {0: "IDLE", 1: "ACTIVE", 2: "INTRANS", 3: "INERROR", 4: "UNKNOWN"}
FAIL = {"commit": 0}
CALLS = {"rollback": 0}


class Conn(ext.connection):
    def commit(self):
        if FAIL["commit"]:
            FAIL["commit"] -= 1
            raise RuntimeError("COMMIT was not sent")
        return super().commit()

    def rollback(self):
        CALLS["rollback"] += 1
        return super().rollback()


witness = psycopg2.connect("postgresql://postgres@127.0.0.1:55454/scratch")
witness.autocommit = True


def q(sql, *args):
    with witness.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def state(pid):
    rows = q("select state from pg_stat_activity where pid = %s", pid)
    return rows[0][0] if rows else None


def visible():
    return [r[0] for r in q(f"select code from {TABLE} order by code")]


def dbapi(conn):
    fairy = conn.connection
    return getattr(fairy, "dbapi_connection", None) or fairy.connection


q(f"drop table if exists {TABLE}")
q(f"create table {TABLE} (code text primary key)")

kw = {"future": True} if "future" in sys.argv[1:] else {}
engine = create_engine(
    URL, pool_size=1, max_overflow=0, pool_pre_ping=False,
    connect_args={"connection_factory": Conn}, **kw,
)
print("sqlalchemy", sqlalchemy.__version__, "| psycopg2", psycopg2.__version__.split()[0], "|", kw or "legacy/2.x default")

conn = engine.connect()
trans = conn.begin()
conn.execute(text(f"insert into {TABLE} (code) values ('doomed')"))
raw = dbapi(conn)
pid = raw.get_backend_pid()
FAIL["commit"] = 1
try:
    trans.commit()
except RuntimeError as exc:
    print("commit raised:", exc)
print("after commit | psycopg2:", STATUS[raw.get_transaction_status()], "| pg:", state(pid))
CALLS["rollback"] = 0
conn.close()
print("close returned | rollback() calls during close:", CALLS["rollback"],
      "| psycopg2:", STATUS[raw.get_transaction_status()], "| pg:", state(pid))
conn2 = engine.connect()
raw2 = dbapi(conn2)
print("next checkout | same dbapi:", raw2 is raw, "| same pid:", raw2.get_backend_pid() == pid,
      "| psycopg2:", STATUS[raw2.get_transaction_status()])
trans2 = conn2.begin()
conn2.execute(text(f"insert into {TABLE} (code) values ('next')"))
trans2.commit()
print("visible:", visible())
conn2.close()
engine.dispose()
