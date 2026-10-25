"""Tortoise ORM: save() after a rolled-back transaction returns normally and writes nothing.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python tortoise_save_after_rollback.py [asyncpg|psycopg]

DATABASE_URL must be able to create a database. The program first drops any database
named tortoise_save_after_rollback, creates it, and drops it at the end. Tortoise uses
the backend named on the command line. A separate asyncpg connection, in autocommit,
reads what PostgreSQL did.

In each arm, save() runs inside in_transaction(), or inside a nested in_transaction()
(a savepoint), and the block then raises, so the INSERT is rolled back. The same
instance is then saved again. The witness reads pg_xact_status() of the transaction IDs
captured inside the transactions, and counts the arm's rows.
"""

import asyncio
import os
import platform
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import tortoise
from tortoise import Tortoise, fields
from tortoise.exceptions import IntegrityError
from tortoise.models import Model
from tortoise.transactions import in_transaction

URL = os.environ["DATABASE_URL"]
NAME = "tortoise_save_after_rollback"


class Item(Model):
    id = fields.IntField(primary_key=True)
    arm = fields.TextField()
    value = fields.IntField()

    class Meta:
        table = "item"


class AppError(Exception):
    pass


async def current_xid(conn):
    rows = await conn.execute_query_dict("select pg_current_xact_id()::text as xid")
    return rows[0]["xid"]


async def fate(witness, xid):
    status = await witness.fetchval("select pg_xact_status($1::text::xid8)", xid)
    return f"pg_xact_status({xid}) {status}"


async def rows(witness, arm):
    count = await witness.fetchval("select count(*) from item where arm = $1", arm)
    return f"rows with arm={arm!r}: {count}"


async def failed_attempt(witness, obj):
    try:
        async with in_transaction() as conn:
            await obj.save()
            xid = await current_xid(conn)
            raise AppError("the application fails after save()")
    except AppError:
        pass
    print(f"  first save() returned, pk={obj.pk}; the block raised AppError")
    print(f"  first transaction: {await fate(witness, xid)}")
    print(f"  after the rollback: pk={obj.pk}, _saved_in_db={obj._saved_in_db}, {await rows(witness, obj.arm)}")


async def retry(witness, change=False):
    arm = "retry-changed" if change else "retry"
    print(f"{arm}: save() in in_transaction(), the block raises; then"
          + (" value = 2 and" if change else "") + " save() again in a new in_transaction()")
    obj = Item(arm=arm, value=1)
    await failed_attempt(witness, obj)
    if change:
        obj.value = 2
    async with in_transaction() as conn:
        await obj.save()
        xid = await current_xid(conn)
    print("  second save() returned normally")
    print(f"  second transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, arm)}")


async def savepoint(witness, change=False):
    arm = "savepoint-changed" if change else "savepoint"
    print(f"{arm}: in an outer in_transaction(), save() in a nested in_transaction() that raises;"
          " the error is caught; then" + (" value = 2 and" if change else "") + " save() again in the outer block")
    obj = Item(arm=arm, value=1)
    async with in_transaction() as conn:
        try:
            async with in_transaction():
                await obj.save()
                raise AppError("the application fails after save()")
        except AppError:
            pass
        print(f"  first save() returned, pk={obj.pk}; the nested block raised AppError")
        print(f"  after the savepoint rollback: pk={obj.pk}, _saved_in_db={obj._saved_in_db}")
        if change:
            obj.value = 2
        await obj.save()
        xid = await current_xid(conn)
        print("  second save() returned normally")
    print("  the outer block exited normally")
    print(f"  outer transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, arm)}")


async def control(witness):
    print("control: save() of a new instance in in_transaction()")
    obj = Item(arm="control", value=1)
    async with in_transaction() as conn:
        await obj.save()
        xid = await current_xid(conn)
    print(f"  save() returned, pk={obj.pk}")
    print(f"  transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, 'control')}")


async def force_update(witness):
    print("force_update: as retry, but the second call is save(force_update=True)")
    obj = Item(arm="force_update", value=1)
    await failed_attempt(witness, obj)
    try:
        async with in_transaction() as conn:
            xid = await current_xid(conn)
            await obj.save(force_update=True)
        print("  second save(force_update=True) returned normally")
    except IntegrityError as exc:
        print(f"  second save(force_update=True) raised IntegrityError: {exc}")
    print(f"  second transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, 'force_update')}")


async def run(backend):
    if backend == "psycopg":
        import psycopg
        import psycopg_pool

        driver = f"psycopg {psycopg.__version__}, psycopg_pool {psycopg_pool.__version__}"
    else:
        driver = f"asyncpg {asyncpg.__version__}"
    print(
        f"python {platform.python_version()}, tortoise-orm {tortoise.__version__},"
        f" backend {backend} ({driver}), {platform.system()} {platform.machine()}"
    )
    admin = await asyncpg.connect(URL, server_settings={"application_name": "repro-admin"})
    print(f"server_version {await admin.fetchval('show server_version')}")
    await admin.execute(f"drop database if exists {NAME} with (force)")
    await admin.execute(f"create database {NAME}")

    url = urlsplit(URL)
    scheme = "postgres" if backend == "asyncpg" else "psycopg"
    db_url = urlunsplit((scheme, url.netloc, f"/{NAME}", "application_name=repro-tortoise", ""))
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})
    await Tortoise.generate_schemas()

    witness = await asyncpg.connect(
        URL, database=NAME, server_settings={"application_name": "repro-witness"}
    )
    await retry(witness)
    await retry(witness, change=True)
    await savepoint(witness)
    await savepoint(witness, change=True)
    await control(witness)
    await force_update(witness)
    await witness.close()

    await Tortoise.close_connections()
    await admin.execute(f"drop database {NAME} with (force)")
    await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg"):
        sys.exit("usage: tortoise_save_after_rollback.py [asyncpg|psycopg]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
