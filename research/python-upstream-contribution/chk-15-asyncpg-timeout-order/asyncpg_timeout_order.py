"""CHK-13: which timeout fires first, the near-miss race and asyncio.timeout(), then
asyncpg's transaction API.

    python asyncpg_timeout_order.py asyncio|uvloop arms|race

arms: one transaction per arm, each on its own connection (application_name chk13-<arm>).
      Each inserts an order, then runs a query under a 0.5 s client deadline and catches
      TimeoutError. In every arm but the control, the query waits for a lock that another
      session holds. The arms differ in the server timeouts set on the connection, and one
      uses asyncio.timeout() instead of fetch(timeout=).
race: on one connection (application_name chk13-race-<loop>), the same transaction with
      pg_sleep() of 61 durations from 0.185 to 0.215 s, four times each, under a 0.2 s
      fetch(timeout=).

Prints what asyncpg reported and, from a separate connection, pg_xact_status() of the
transaction and whether the order is visible. Needs DATABASE_URL (a server's postgres
database). Creates database timeout_order and drops it at the end.
"""

import asyncio
import os
import sys
import time

import asyncpg

LOOP, MODE = (sys.argv[1:3] + ["", ""])[:2]
if LOOP not in ("asyncio", "uvloop") or MODE not in ("arms", "race"):
    sys.exit("usage: asyncpg_timeout_order.py asyncio|uvloop arms|race")
URL = os.environ["DATABASE_URL"]
DB = "timeout_order"
LOCKED_QUERY = "select sku from products order by popularity desc limit 3"
CLIENT_TIMEOUT = 0.5
# arm: (server settings on the subject connection, products locked, deadline)
ARMS = {
    "control_unlocked": ({}, False, "fetch(timeout=)"),
    "client_first": ({}, True, "fetch(timeout=)"),
    "server_lock_timeout_first": ({"lock_timeout": "200ms"}, True, "fetch(timeout=)"),
    "server_statement_timeout_first": ({"statement_timeout": "200ms"}, True, "fetch(timeout=)"),
    "server_lock_timeout_later": ({"lock_timeout": "2s"}, True, "fetch(timeout=)"),
    "server_statement_timeout_later": ({"statement_timeout": "2s"}, True, "fetch(timeout=)"),
    "asyncio_timeout": ({}, True, "asyncio.timeout()"),
}
RACE_TIMEOUT = 0.2
RACE_SLEEPS = [round(0.185 + i * 0.0005, 4) for i in range(61)]  # 0.185 .. 0.215 s
RACE_REPS = 4


async def connect(app, **settings):
    return await asyncpg.connect(URL, database=DB, server_settings={"application_name": app, **settings})


async def checkout(conn, marker, seen, deadline, timeout, query, *args):
    """An optional query with a client deadline inside the transaction; TimeoutError is caught."""
    async with conn.transaction():
        await conn.execute("insert into orders (marker) values ($1)", marker)
        seen["xid"] = await conn.fetchval("select pg_current_xact_id()::text")
        try:
            if deadline == "asyncio.timeout()":
                async with asyncio.timeout(timeout):
                    await conn.fetch(query, *args)
            else:
                await conn.fetch(query, *args, timeout=timeout)
            seen["query"] = "returned"
        except TimeoutError:
            seen["query"] = "caught TimeoutError"


async def attempt(coro):
    try:
        await coro
    except Exception as e:  # noqa: BLE001 - reported as what the block raised
        return e
    return None


def describe(exc):
    if exc is None:
        return "exited normally"
    state = getattr(exc, "sqlstate", None)
    return f"raised {type(exc).__name__}{f' ({state})' if state else ''}: {str(exc).splitlines()[0]}"


async def fates(witness, xids, markers):
    rows = await witness.fetch(
        "select x, pg_xact_status(x::xid8)::text as fate from unnest($1::text[]) as x", xids)
    visible = {r["marker"] for r in await witness.fetch(
        "select marker from orders where marker = any($1::text[])", markers)}
    return {r["x"]: r["fate"] for r in rows}, visible


async def run_arms(witness):
    for arm, (settings, locked, deadline) in ARMS.items():
        migration = None
        if locked:
            # Another session holds the lock that an ALTER TABLE on products takes.
            migration = await connect("chk13-migration")
            await migration.execute("begin")
            await migration.execute("lock table products in access exclusive mode")
        conn = await connect(f"chk13-{arm}", **settings)
        marker, seen = f"{arm}-{LOOP}", {"query": "-"}
        exc = await attempt(checkout(conn, marker, seen, deadline, CLIENT_TIMEOUT, LOCKED_QUERY))
        await conn.close()
        if migration is not None:
            await migration.execute("rollback")
            await migration.close()
        fate, visible = await fates(witness, [seen["xid"]], [marker])
        print(f"{arm}: query {seen['query']}; block {describe(exc)}; "
              f"pg_xact_status({seen['xid']}) {fate[seen['xid']]}, marker visible {marker in visible}")


async def run_race(witness):
    conn = await connect(f"chk13-race-{LOOP}")
    trials = []
    for rep in range(1, RACE_REPS + 1):
        for sleep in RACE_SLEEPS:
            marker, seen = f"race-{rep}-{sleep}", {"query": "-"}
            start = time.perf_counter()
            exc = await attempt(checkout(conn, marker, seen, "fetch(timeout=)", RACE_TIMEOUT,
                                         "select pg_sleep($1)", sleep))
            trials.append((sleep, rep, marker, seen, exc, time.perf_counter() - start))
            if exc is not None and conn.is_closed():
                conn = await connect(f"chk13-race-{LOOP}")
            elif exc is not None and conn.is_in_transaction():
                await conn.execute("rollback")
    await conn.close()
    fate, visible = await fates(witness, [t[3]["xid"] for t in trials], [t[2] for t in trials])
    counts = {}
    for sleep, rep, marker, seen, exc, elapsed in trials:
        f, v = fate[seen["xid"]], marker in visible
        if exc is not None:
            cls = "E"  # the block raised
        elif seen["query"] == "returned" and f == "committed" and v:
            cls = "R"  # the query returned in time; committed
        elif seen["query"] == "caught TimeoutError" and f == "aborted" and not v:
            cls = "TA"  # timeout; the cancel reached the statement; aborted
        elif seen["query"] == "caught TimeoutError" and f == "committed" and v:
            cls = "TC"  # timeout, but the statement had finished; committed
        else:
            cls = "?"
        counts.setdefault(sleep, {}).setdefault(cls, 0)
        counts[sleep][cls] += 1
        print(f"race sleep {sleep:.4f} rep{rep}: {cls}; query {seen['query']}; block {describe(exc)}; "
              f"pg_xact_status({seen['xid']}) {f}, marker visible {v}; client {elapsed * 1000:.1f} ms")
    print(f"\nrace summary ({LOOP}, client timeout {RACE_TIMEOUT} s, {RACE_REPS} trials per sleep):")
    for sleep in RACE_SLEEPS:
        print(f"  sleep {sleep:.4f} s: " + ", ".join(f"{k} {n}" for k, n in sorted(counts[sleep].items())))
    totals = {}
    for c in counts.values():
        for k, n in c.items():
            totals[k] = totals.get(k, 0) + n
    print("  totals: " + ", ".join(f"{k} {n}" for k, n in sorted(totals.items())))


async def main():
    admin = await asyncpg.connect(URL, server_settings={"application_name": "chk13-setup"})
    await admin.execute(f"drop database if exists {DB} with (force)")
    await admin.execute(f"create database {DB}")
    setup = await connect("chk13-setup")
    await setup.execute("create table orders (id serial primary key, marker text not null)")
    await setup.execute("create table products (sku text primary key, popularity int not null)")
    await setup.execute("insert into products values ('mug', 3), ('tee', 2), ('cap', 1)")
    await setup.close()
    print(f"{LOOP} {MODE}: asyncpg {asyncpg.__version__}, server {await admin.fetchval('show server_version')}")
    witness = await connect("chk13-witness")
    await (run_arms(witness) if MODE == "arms" else run_race(witness))
    await witness.close()
    await admin.execute(f"drop database {DB} with (force)")
    await admin.close()


if LOOP == "uvloop":
    import uvloop

    uvloop.run(main())
else:
    asyncio.run(main())
