"""Tortoise ORM: an integrity error raised by COMMIT reaches the application untranslated.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python tortoise_commit_translation.py [asyncpg|psycopg|sqlite]

For asyncpg and psycopg, DATABASE_URL must be able to create a database. The program
drops any database named tortoise_commit_translation, creates it, and drops it at the
end. For sqlite, it uses a file in a new temporary directory, and removes the directory
at the end; DATABASE_URL is not used.

A foreign key declared DEFERRABLE INITIALLY DEFERRED is checked when the transaction
commits. An INSERT that violates it succeeds, and the COMMIT sent when the block exits
fails. The same INSERT against a foreign key that is not deferred fails at the INSERT.
For each arm the program prints the exception that reaches the application, with its
__cause__ and __context__, and the frames it was raised through. A separate connection
then reads what the database holds: on PostgreSQL, pg_xact_status() of the transaction
ID captured inside the transaction, and the row count; on SQLite, the row count, read
through the sqlite3 module. Each arm uses a new Tortoise.init(), so that no arm runs on
a connection that an earlier arm left behind. Tortoise's PostgreSQL sessions use the
application_name in PY8_APP, or py8-tortoise.
"""

import asyncio
import os
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
import traceback
from urllib.parse import urlsplit, urlunsplit

import tortoise
from tortoise import Tortoise, fields
from tortoise.exceptions import BaseORMException, IntegrityError
from tortoise.models import Model
from tortoise.transactions import in_transaction

NAME = "tortoise_commit_translation"
APP = os.environ.get("PY8_APP", "py8-tortoise")
DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "CREATE TABLE deferred_child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED)",
    "CREATE TABLE immediate_child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id))",
]


class DeferredChild(Model):
    id = fields.IntField(primary_key=True, generated=False)
    parent_id = fields.IntField()

    class Meta:
        table = "deferred_child"


class ImmediateChild(Model):
    id = fields.IntField(primary_key=True, generated=False)
    parent_id = fields.IntField()

    class Meta:
        table = "immediate_child"


def qualname(exc):
    return None if exc is None else f"{type(exc).__module__}.{type(exc).__qualname__}"


def frames(exc):
    """The frames the exception was raised through, leaving out this directory's programs."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = []
    for fs in traceback.extract_tb(exc.__traceback__):
        if os.path.dirname(os.path.abspath(fs.filename)) == here:
            continue
        path = re.sub(
            r"^.*?/(?=(?:tortoise|asyncpg|psycopg|psycopg_pool|aiosqlite|asyncio)/|contextlib\.py$)",
            "",
            fs.filename,
        )
        out.append(f"{path}:{fs.lineno} {fs.name}")
    return out


def describe(exc):
    print(f"  raised {qualname(exc)}: {str(exc).splitlines()[0] if str(exc) else ''}")
    print(f"  isinstance(exc, tortoise.exceptions.IntegrityError): {isinstance(exc, IntegrityError)}")
    print(f"  __cause__: {qualname(exc.__cause__)}")
    print(f"  __context__: {qualname(exc.__context__)}")
    wrapped = isinstance(exc, BaseORMException) and exc.args and isinstance(exc.args[0], Exception)
    driver = exc.args[0] if wrapped else exc
    code = getattr(driver, "sqlstate", None) or getattr(driver, "sqlite_errorname", None)
    print(f"  driver error code: {code}")
    print("  raised through:")
    for line in frames(exc):
        print(f"    {line}")


class Witness:
    """A separate connection that reads what the database holds."""

    def __init__(self, backend, url, path):
        self.backend, self.url, self.path = backend, url, path

    async def open(self):
        if self.backend == "sqlite":
            self.conn = sqlite3.connect(self.path)
            for statement in DDL:
                self.conn.execute(statement)
            self.conn.commit()
            return
        import psycopg

        self.admin = await psycopg.AsyncConnection.connect(
            self.url, autocommit=True, application_name="py8-admin"
        )
        print(f"server_version {(await (await self.admin.execute('show server_version')).fetchone())[0]}")
        await self.admin.execute(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)")
        await self.admin.execute(f"CREATE DATABASE {NAME}")
        self.conn = await psycopg.AsyncConnection.connect(
            self.url, dbname=NAME, autocommit=True, application_name="py8-witness"
        )
        for statement in DDL:
            await self.conn.execute(statement)

    async def scalar(self, sql, args=()):
        if self.backend == "sqlite":
            return self.conn.execute(sql.replace("%s", "?"), args).fetchone()[0]
        return (await (await self.conn.execute(sql, args)).fetchone())[0]

    async def report(self, table, pk, xid=None):
        if xid is not None:
            print(f"  pg_xact_status({xid}): {await self.scalar('SELECT pg_xact_status(%s::xid8)', (xid,))}")
        print(f"  rows in {table} with id={pk}: {await self.scalar(f'SELECT count(*) FROM {table} WHERE id = %s', (pk,))}")

    async def close(self):
        if self.backend == "sqlite":
            self.conn.close()
            return
        await self.conn.close()
        await self.admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
        await self.admin.close()


async def current_xid(conn, backend):
    if backend == "sqlite":
        return None
    rows = await conn.execute_query_dict("SELECT pg_current_xact_id()::text AS xid")
    return rows[0]["xid"]


async def arm_in_transaction(witness, backend, model, pk):
    print(f"{model.__name__}.create(parent_id=999) inside in_transaction()")
    xid = None
    try:
        async with in_transaction() as conn:
            xid = await current_xid(conn, backend)
            await model.create(id=pk, parent_id=999, using_db=conn)
            print("  create() returned; the block exits normally")
        print("  the block exited normally")
    except Exception as exc:  # noqa: BLE001 - the point is to show which class arrives
        describe(exc)
    await witness.report(model.Meta.table, pk, xid)


async def arm_get_or_create(witness, backend, model, pk):
    print(f"{model.__name__}.get_or_create(id={pk}, defaults={{'parent_id': 999}})")
    try:
        obj, created = await model.get_or_create(id=pk, defaults={"parent_id": 999})
        print(f"  returned created={created}")
    except Exception as exc:  # noqa: BLE001
        describe(exc)
    await witness.report(model.Meta.table, pk)


ARMS = [
    (arm_in_transaction, DeferredChild, 1),
    (arm_in_transaction, ImmediateChild, 1),
    (arm_get_or_create, DeferredChild, 2),
    (arm_get_or_create, ImmediateChild, 2),
]


async def run(backend):
    if backend == "asyncpg":
        import asyncpg

        driver = f"asyncpg {asyncpg.__version__}"
    elif backend == "psycopg":
        import psycopg
        import psycopg_pool

        driver = f"psycopg {psycopg.__version__}, psycopg_pool {psycopg_pool.__version__}"
    else:
        import aiosqlite

        driver = f"aiosqlite {aiosqlite.__version__}, SQLite {sqlite3.sqlite_version}"
    print(
        f"python {platform.python_version()}, tortoise-orm {tortoise.__version__},"
        f" backend {backend} ({driver}), {platform.system()} {platform.machine()}"
    )
    tmp = None
    if backend == "sqlite":
        tmp = tempfile.mkdtemp(prefix="py8-")
        path = os.path.join(tmp, f"{NAME}.sqlite3")
        db_url = f"sqlite://{path}"
        witness = Witness(backend, None, path)
    else:
        url = urlsplit(os.environ["DATABASE_URL"])
        db_url = urlunsplit((backend, url.netloc, f"/{NAME}", f"application_name={APP}", ""))
        witness = Witness(backend, os.environ["DATABASE_URL"], None)
    await witness.open()
    try:
        for arm, model, pk in ARMS:
            await Tortoise.init(db_url=db_url, modules={"models": [__name__]})
            try:
                await arm(witness, backend, model, pk)
            finally:
                await Tortoise.close_connections()
    finally:
        await witness.close()
        if tmp:
            shutil.rmtree(tmp)


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg", "sqlite"):
        sys.exit("usage: tortoise_commit_translation.py [asyncpg|psycopg|sqlite]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
