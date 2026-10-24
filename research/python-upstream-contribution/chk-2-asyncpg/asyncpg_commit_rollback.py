"""asyncpg: the transaction API returns normally after PostgreSQL answers COMMIT with ROLLBACK.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python asyncpg_commit_rollback.py [asyncio|uvloop]

DATABASE_URL must be able to create a database. The program connects to it, creates
database asyncpg_commit_rollback, and drops that database at the end.

Each arm runs on its own connection. It inserts a marker row, then inserts a duplicate
key and catches UniqueViolationError, then finishes the transaction the arm's way.
A separate connection then reads what PostgreSQL did: pg_xact_status() of the
transaction ID captured inside the transaction, whether the marker row is visible, and
the session's state and last statement in pg_stat_activity.
"""

import asyncio
import os
import platform
import sys

import asyncpg

URL = os.environ["DATABASE_URL"]
NAME = "asyncpg_commit_rollback"


async def connect(app, database=NAME):
    return await asyncpg.connect(
        URL, database=database, server_settings={"application_name": app}
    )


async def insert_marker(con, marker):
    await con.execute("insert into item (name) values ($1)", marker)
    return await con.fetchval("select pg_current_xact_id()::text")


async def insert_duplicate(con):
    try:
        await con.execute("insert into uniq (code) values ('taken')")
    except asyncpg.UniqueViolationError as exc:
        return f"caught {type(exc).__name__} ({exc.sqlstate})"
    return "no error"


async def insert_duplicate_in_savepoint(con):
    try:
        async with con.transaction():
            await con.execute("insert into uniq (code) values ('taken')")
    except asyncpg.UniqueViolationError as exc:
        return f"caught {type(exc).__name__} ({exc.sqlstate}) outside the savepoint block"
    return "no error"


async def report(probe, con, xid, marker):
    fate = await probe.fetchval("select pg_xact_status($1::text::xid8)", xid)
    seen = await probe.fetchval("select count(*) from item where name = $1", marker)
    row = await probe.fetchrow(
        "select state, query from pg_stat_activity where pid = $1", con.get_server_pid()
    )
    print(
        f"  PostgreSQL: pg_xact_status({xid}) {fate}, marker visible {bool(seen)},"
        f" session {row['state']}, last statement {row['query']!r}"
    )


async def managed(probe):
    print("managed: async with con.transaction(), error caught inside the block")
    con = await connect("repro-managed")
    try:
        async with con.transaction():
            xid = await insert_marker(con, "managed")
            print(f"  {await insert_duplicate(con)}")
        print("  the block exited normally")
    except Exception as exc:
        print(f"  the block raised {type(exc).__name__}: {exc}")
    await report(probe, con, xid, "managed")
    await con.close()


async def explicit(probe):
    print("explicit: tr.start(), error caught, tr.commit()")
    con = await connect("repro-explicit")
    tr = con.transaction()
    await tr.start()
    xid = await insert_marker(con, "explicit")
    print(f"  {await insert_duplicate(con)}")
    try:
        print(f"  commit() returned {await tr.commit()!r}")
    except Exception as exc:
        print(f"  commit() raised {type(exc).__name__}: {exc}")
    try:
        await tr.rollback()
        print("  rollback() afterwards returned")
    except asyncpg.InterfaceError as exc:
        print(f"  rollback() afterwards raised InterfaceError: {exc}")
    await report(probe, con, xid, "explicit")
    await con.close()


async def raw(probe):
    print("raw: execute('BEGIN'), error caught, execute('COMMIT')")
    con = await connect("repro-raw")
    await con.execute("BEGIN")
    xid = await insert_marker(con, "raw")
    print(f"  {await insert_duplicate(con)}")
    print(f"  execute('COMMIT') returned {await con.execute('COMMIT')!r}")
    await report(probe, con, xid, "raw")
    await con.close()


async def control(probe):
    print("control: async with con.transaction(), error caught around a nested con.transaction() (savepoint)")
    con = await connect("repro-control")
    try:
        async with con.transaction():
            xid = await insert_marker(con, "control")
            print(f"  {await insert_duplicate_in_savepoint(con)}")
        print("  the block exited normally")
    except Exception as exc:
        print(f"  the block raised {type(exc).__name__}: {exc}")
    await report(probe, con, xid, "control")
    await con.close()


async def run():
    loop = asyncio.get_running_loop()
    uvloop = sys.modules.get("uvloop")
    print(
        f"python {platform.python_version()}, asyncpg {asyncpg.__version__},"
        f" event loop {type(loop).__module__}.{type(loop).__qualname__}"
        + (f" (uvloop {uvloop.__version__})" if uvloop else "")
        + f", {platform.system()} {platform.machine()}"
    )
    admin = await connect("repro-admin", database=None)
    print(f"server_version {await admin.fetchval('show server_version')}")
    await admin.execute(f"drop database if exists {NAME} with (force)")
    await admin.execute(f"create database {NAME}")

    setup = await connect("repro-setup")
    await setup.execute("create table item (id serial primary key, name text not null)")
    await setup.execute("create table uniq (id serial primary key, code text not null unique)")
    await setup.execute("insert into uniq (code) values ('taken')")
    await setup.close()

    probe = await connect("repro-witness")
    for arm in (managed, explicit, raw, control):
        await arm(probe)
    await probe.close()

    await admin.execute(f"drop database {NAME} with (force)")
    await admin.close()


def main():
    loop = sys.argv[1] if len(sys.argv) > 1 else "asyncio"
    if loop == "asyncio":
        asyncio.run(run())
    elif loop == "uvloop":
        import uvloop

        uvloop.run(run())
    else:
        sys.exit("usage: asyncpg_commit_rollback.py [asyncio|uvloop]")


if __name__ == "__main__":
    main()
