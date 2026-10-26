"""asyncpg: a client-side timeout caught inside a transaction, then the transaction API's normal completion.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python asyncpg_client_timeout.py [asyncio|uvloop]

DATABASE_URL must be able to create a database. The program connects to it, creates
database asyncpg_client_timeout, and drops that database at the end.

Each arm runs on its own connection. It inserts a marker row, then runs
select pg_sleep(10) under a 0.2 s client-side timeout and catches TimeoutError, then
finishes the transaction the arm's way. A separate connection then reads what
PostgreSQL did: pg_xact_status() of the transaction ID captured inside the
transaction, whether the marker row is visible, and the session's state and last
statement in pg_stat_activity.
"""

import asyncio
import os
import platform
import sys
import time

import asyncpg

URL = os.environ["DATABASE_URL"]
NAME = "asyncpg_client_timeout"
SLOW = "select pg_sleep(10)"
LIMIT = 0.2


async def connect(app, database=NAME, **kwargs):
    return await asyncpg.connect(
        URL, database=database, server_settings={"application_name": app}, **kwargs
    )


async def insert_marker(con, marker):
    await con.execute("insert into item (name) values ($1)", marker)
    return await con.fetchval("select pg_current_xact_id()::text")


async def slow(con, how):
    if how == "timeout":
        await con.fetch(SLOW, timeout=LIMIT)
    elif how == "command_timeout":
        await con.fetch(SLOW)
    elif how == "wait_for":
        await asyncio.wait_for(con.fetch(SLOW), LIMIT)
    elif how == "fast":
        await con.fetch("select pg_sleep(0.01)", timeout=5)


async def slow_caught(con, how):
    started = time.monotonic()
    try:
        await slow(con, how)
    except TimeoutError as exc:
        return f"caught {type(exc).__name__}, before the sleep ended: {time.monotonic() - started < 5}"
    return "no error"


async def slow_in_savepoint(con):
    try:
        async with con.transaction():
            await slow(con, "timeout")
    except TimeoutError as exc:
        return f"caught {type(exc).__name__} outside the savepoint block"
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


async def rollback_afterwards(tr):
    try:
        await tr.rollback()
        print("  rollback() afterwards returned")
    except asyncpg.InterfaceError as exc:
        print(f"  rollback() afterwards raised InterfaceError: {exc}")


async def block(probe, name, describe, inside, **connect_kwargs):
    print(f"{name}: {describe}")
    con = await connect(f"repro-{name}", **connect_kwargs)
    tr = con.transaction()
    xid = None
    try:
        async with tr:
            xid = await insert_marker(con, name)
            print(f"  {await inside(con)}")
        print("  the block exited normally")
    except Exception as exc:
        print(f"  the block raised {type(exc).__name__}: {exc}")
    await rollback_afterwards(tr)
    await report(probe, con, xid, name)
    await con.close()


async def managed(probe):
    await block(probe, "managed", "async with con.transaction(), fetch(timeout=0.2) caught inside the block",
                lambda con: slow_caught(con, "timeout"))


async def command_timeout(probe):
    await block(probe, "command_timeout", "connect(command_timeout=0.2), async with con.transaction(), fetch() caught inside",
                lambda con: slow_caught(con, "command_timeout"), command_timeout=LIMIT)


async def wait_for(probe):
    await block(probe, "wait_for", "async with con.transaction(), asyncio.wait_for(fetch(), 0.2) caught inside",
                lambda con: slow_caught(con, "wait_for"))


async def explicit(probe):
    print("explicit: tr.start(), fetch(timeout=0.2) caught, tr.commit()")
    con = await connect("repro-explicit")
    tr = con.transaction()
    await tr.start()
    xid = await insert_marker(con, "explicit")
    print(f"  {await slow_caught(con, 'timeout')}")
    try:
        print(f"  commit() returned {await tr.commit()!r}")
    except Exception as exc:
        print(f"  commit() raised {type(exc).__name__}: {exc}")
    await rollback_afterwards(tr)
    await report(probe, con, xid, "explicit")
    await con.close()


async def raw(probe):
    print("raw: execute('BEGIN'), fetch(timeout=0.2) caught, execute('COMMIT')")
    con = await connect("repro-raw")
    await con.execute("BEGIN")
    xid = await insert_marker(con, "raw")
    print(f"  {await slow_caught(con, 'timeout')}")
    print(f"  execute('COMMIT') returned {await con.execute('COMMIT')!r}")
    await report(probe, con, xid, "raw")
    await con.close()


async def control_savepoint(probe):
    await block(probe, "control_savepoint", "async with con.transaction(), fetch(timeout=0.2) caught around a nested con.transaction() (savepoint)",
                slow_in_savepoint)


async def control_fast(probe):
    await block(probe, "control_fast", "async with con.transaction(), fetch(timeout=5) of select pg_sleep(0.01): no timeout fires",
                lambda con: slow_caught(con, "fast"))


async def control_uncaught(probe):
    await block(probe, "control_uncaught", "async with con.transaction(), fetch(timeout=0.2) not caught",
                lambda con: slow(con, "timeout"))


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
    await setup.close()

    probe = await connect("repro-witness")
    for arm in (managed, explicit, raw, command_timeout, wait_for,
                control_savepoint, control_fast, control_uncaught):
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
        sys.exit("usage: asyncpg_client_timeout.py [asyncio|uvloop]")


if __name__ == "__main__":
    main()
