"""CHK-only, PY-8 check 1: a nested block exits normally on an aborted transaction.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python chk_nested_release.py [asyncpg|psycopg] [develop|C1|C2|C3]

The program drops any database named py8_nested_release, creates it, and drops it at the
end. Tortoise uses a pool of one connection, so the follow-up transaction runs on the same
pool. The application_name is py8-nested-<backend>-<candidate>, followed by -r<PY8_REP>
when PY8_REP is set, for the server log.

The outer in_transaction() writes a row. A nested in_transaction() then runs an INSERT that
violates an immediate foreign key and catches the IntegrityError, so PostgreSQL has aborted
the transaction when the nested block exits normally, and its RELEASE SAVEPOINT fails with
SQLSTATE 25P02. The program prints the exception that reaches the application, and every
Python log record of WARNING or above emitted meanwhile (asyncio's exception handler and
psycopg_pool log there). A separate connection then reads pg_xact_status() of the outer
transaction and counts the outer row. Finally a follow-up in_transaction() writes another
row, and the program reports whether it ran on the same backend.
"""

import asyncio
import logging
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg  # noqa: E402
from tortoise import Tortoise, fields  # noqa: E402
from tortoise.exceptions import IntegrityError  # noqa: E402
from tortoise.models import Model  # noqa: E402
from tortoise.transactions import in_transaction  # noqa: E402

import candidates  # noqa: E402
from tortoise_commit_translation import describe, qualname  # noqa: E402

NAME = "py8_nested_release"
DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "CREATE TABLE immediate_child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id))",
    "CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)",
]


class ImmediateChild(Model):
    id = fields.IntField(primary_key=True, generated=False)
    parent_id = fields.IntField()

    class Meta:
        table = "immediate_child"


class Note(Model):
    id = fields.IntField(primary_key=True, generated=False)
    body = fields.TextField()

    class Meta:
        table = "note"


class Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        message = re.sub(r"0x[0-9a-f]+", "0x…", record.getMessage())
        self.records.append(f"{record.levelname} {record.name}: {message}")

    def flush_to_stdout(self, when):
        print(f"  log records {when}: {len(self.records)}")
        for line in self.records:
            print(f"    {line}")
        self.records.clear()


async def one_value(conn, sql, key):
    return (await conn.execute_query_dict(sql))[0][key]


async def scalar(witness, sql, args=()):
    return (await (await witness.execute(sql, args)).fetchone())[0]


async def run(backend, candidate):
    print(candidates.apply(candidate, backend))
    handler = Records()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.WARNING)

    url = os.environ["DATABASE_URL"]
    admin = await psycopg.AsyncConnection.connect(url, autocommit=True, application_name="py8-admin")
    await admin.execute(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {NAME}")
    witness = await psycopg.AsyncConnection.connect(
        url, dbname=NAME, autocommit=True, application_name="py8-witness"
    )
    for statement in DDL:
        await witness.execute(statement)

    app = f"py8-nested-{backend}-{candidate}" + (f"-r{os.environ['PY8_REP']}" if os.environ.get("PY8_REP") else "")
    parts = urlsplit(url)
    db_url = urlunsplit(
        (backend, parts.netloc, f"/{NAME}", f"application_name={app}&minsize=1&maxsize=1", "")
    )
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})

    print("outer block writes note 1; a nested block catches IntegrityError, then exits normally")
    xid = pid = None
    try:
        async with in_transaction() as outer:
            xid = await one_value(outer, "SELECT pg_current_xact_id()::text AS v", "v")
            pid = await one_value(outer, "SELECT pg_backend_pid() AS v", "v")
            await Note.create(id=1, body="outer write", using_db=outer)
            async with in_transaction() as inner:
                try:
                    await ImmediateChild.create(id=1, parent_id=999, using_db=inner)
                except IntegrityError as exc:
                    print(f"  the nested INSERT raised {qualname(exc)}; the nested block catches it")
            print("  the nested block exited normally")
        print("  the outer block exited normally")
    except Exception as exc:  # noqa: BLE001
        describe(exc)
    handler.flush_to_stdout("while the blocks exited")
    print(f"  outer transaction pg_xact_status({xid}): {await scalar(witness, 'SELECT pg_xact_status(%s::xid8)', (xid,))}")
    print(f"  rows in note with id=1: {await scalar(witness, 'SELECT count(*) FROM note WHERE id = 1')}")
    print(f"  backends of this pool still connected: {await scalar(witness, 'SELECT count(*) FROM pg_stat_activity WHERE application_name = %s', (app,))}")

    print("follow-up: in_transaction() writes note 2, on the same pool of one connection")
    try:
        async with in_transaction() as conn:
            xid2 = await one_value(conn, "SELECT pg_current_xact_id()::text AS v", "v")
            pid2 = await one_value(conn, "SELECT pg_backend_pid() AS v", "v")
            await Note.create(id=2, body="follow-up", using_db=conn)
        print("  the follow-up block exited normally")
        print(f"  same backend as the first transaction: {pid2 == pid}")
        print(f"  follow-up pg_xact_status({xid2}): {await scalar(witness, 'SELECT pg_xact_status(%s::xid8)', (xid2,))}")
    except Exception as exc:  # noqa: BLE001
        describe(exc)
    print(f"  rows in note with id=2: {await scalar(witness, 'SELECT count(*) FROM note WHERE id = 2')}")
    handler.flush_to_stdout("during the follow-up")

    await Tortoise.close_connections()
    handler.flush_to_stdout("while closing")
    await witness.close()
    await admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
    await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    candidate = sys.argv[2] if len(sys.argv) > 2 else "develop"
    if backend not in ("asyncpg", "psycopg") or candidate not in ("develop", "C1", "C2", "C3"):
        sys.exit("usage: chk_nested_release.py [asyncpg|psycopg] [develop|C1|C2|C3]")
    asyncio.run(run(backend, candidate))


if __name__ == "__main__":
    main()
