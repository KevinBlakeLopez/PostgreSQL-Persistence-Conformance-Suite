"""asyncpg Pool cleanup-failure probes: does a connection whose release-time reset failed, timed out, was cancelled
or was interrupted ever reach the next acquirer with the previous borrower's session state?

Pool of one connection (min_size=max_size=1). Borrower A changes session state, then the scenario interferes with
the release. Borrower B acquires next. Evidence:

- B's own reads through its connection;
- an independent observer connection (superuser, outside the pool): pg_stat_activity, pg_locks, the tables;
- physical identity: the server PID reported by the driver (BackendKeyData, no SQL) plus that backend's
  backend_start as the observer reads it;
- the server's statement log (read separately, by application_name).

The output has no PIDs, timestamps or transaction IDs, so repetitions can be compared byte for byte.

Usage: python -I asyncpg_pool_probe.py <instance-file> <scenario>
"""

import asyncio
import json
import sys

import asyncpg

INST = json.load(open(sys.argv[1]))
SCENARIO = sys.argv[2]
APP = f"ssc-asyncpg-{SCENARIO}"
LOCK_KEY = 4711


def out(who, step, observed):
    print(f"{who:<9} {step:<84} {observed}")


async def observer():
    con = await asyncpg.connect(
        host=INST["host"], port=INST["port"], database=INST["database"], user=INST["superuser"],
        password=INST["superuser_password"], server_settings={"application_name": "ssc-asyncpg-observer"},
    )
    token = await con.fetchval("select current_setting('cluster_name')")
    if token != INST["token"]:
        raise SystemExit("refusing: cluster_name is not this investigation's server")
    return con


async def make_pool(reset=None):
    kwargs = {} if reset is None else {"reset": reset}
    return await asyncpg.create_pool(
        host=INST["host"], port=INST["port"], database=INST["database"], user=INST["user"],
        password=INST["password"], min_size=1, max_size=1, server_settings={"application_name": APP}, **kwargs,
    )


async def identity(obs, con):
    pid = con.get_server_pid()
    start = await obs.fetchval("select backend_start::text from pg_stat_activity where pid = $1", pid)
    return pid, start


async def advisory_holders(obs):
    """Backends of this scenario's pool that hold LOCK_KEY, as seen by the observer."""
    n = await obs.fetchval(
        "select count(*) from pg_locks l join pg_stat_activity a using (pid) "
        "where l.locktype = 'advisory' and l.objid = $1 and l.granted and a.application_name = $2", LOCK_KEY, APP)
    return f"{n} backend(s) of the pool"


async def landed(obs, label):
    rows = await obs.fetch(
        "select 'public' s from public.item where label = $1 union all "
        "select 'tenant_a' from tenant_a.item where label = $1 order by 1", label)
    return ", ".join(r["s"] for r in rows) or "not visible"


async def pool_backends(obs):
    rows = await obs.fetch(
        "select state from pg_stat_activity where application_name = $1 and datname = current_database()", APP)
    return ", ".join(r["state"] or "none" for r in rows) or "no backend"


async def dirty(con):
    """Borrower A's session changes, each confirmed through A's own connection."""
    await con.execute("SET search_path TO tenant_a, public")
    await con.execute("select pg_advisory_lock($1)", LOCK_KEY)
    await con.execute("LISTEN ppcs_probe_channel")
    await con.execute("select set_config('app.tenant_id', 'tenant_a', false)")
    return await con.fetchval("select current_setting('search_path') || ' | ' || current_setting('app.tenant_id')")


async def inspect_b(obs, pool, a_ident):
    con = await pool.acquire()
    b_ident = await identity(obs, con)
    out("B", "same physical session as A", b_ident == a_ident)
    state = await obs.fetchrow("select state, xact_start is not null as xact from pg_stat_activity where pid = $1",
                               b_ident[0])
    out("observer", "B's backend at checkout, before B's first statement",
        f"state={state['state']} xact_open={state['xact']}")
    out("observer", "A's original backend still exists while B holds its connection",
        await obs.fetchval("select count(*) > 0 from pg_stat_activity where pid = $1", a_ident[0])
        if b_ident != a_ident else "same backend")
    out("B", "search_path | app.tenant_id",
        await con.fetchval("select current_setting('search_path') || ' | ' || "
                           "coalesce(current_setting('app.tenant_id', true), '<undefined>')"))
    out("B", "listening channels", await con.fetchval("select coalesce(string_agg(c, ','), 'none') from pg_listening_channels() c"))
    out("observer", f"advisory lock {LOCK_KEY} holders while B holds the connection", await advisory_holders(obs))
    out("B", f"pg_try_advisory_lock({LOCK_KEY})", await con.fetchval("select pg_try_advisory_lock($1)", LOCK_KEY))
    await con.execute("select pg_advisory_unlock_all()")
    await con.execute("insert into item(label) values ('B-unqualified')")
    out("observer", "where B's unqualified insert landed", await landed(obs, "B-unqualified"))
    await pool.release(con)


async def main():
    obs = await observer()
    await obs.execute("delete from public.item; delete from tenant_a.item; delete from tenant_b.item")
    print("scenario:", SCENARIO)

    if SCENARIO == "normal-release":
        pool = await make_pool()
        a = await pool.acquire()
        a_ident = await identity(obs, a)
        out("A", "state after the session changes", await dirty(a))
        await pool.release(a)
        out("A", "release()", "returned")
        await inspect_b(obs, pool, a_ident)

    elif SCENARIO == "open-transaction":
        pool = await make_pool()
        a = await pool.acquire()
        a_ident = await identity(obs, a)
        await a.execute("BEGIN")
        await a.execute("insert into item(label) values ('A-uncommitted')")
        out("A", "state after the session changes", await dirty(a))
        await pool.release(a)
        out("A", "release() with a raw BEGIN still open", "returned")
        out("observer", "A's uncommitted insert after release", await landed(obs, "A-uncommitted"))
        await inspect_b(obs, pool, a_ident)

    elif SCENARIO in ("reset-raises", "reset-timeout", "reset-timeout-long", "cancel-during-reset"):
        calls = []

        async def slow_or_failing_reset(con):
            calls.append(1)
            if SCENARIO == "reset-raises" and len(calls) == 1:
                raise RuntimeError("custom reset failed")   # only A's release fails
            if len(calls) == 1:   # only A's release is slow
                await con.execute("select pg_sleep(5)" if SCENARIO == "reset-timeout-long" else "select pg_sleep(0.5)")
            await con.execute(con.get_reset_query())

        pool = await make_pool(reset=slow_or_failing_reset)
        a = await pool.acquire()
        a_ident = await identity(obs, a)
        out("A", "state after the session changes", await dirty(a))
        if SCENARIO == "reset-raises":
            try:
                await pool.release(a)
                out("A", "release() with a reset that raises", "returned")
            except Exception as exc:
                out("A", "release() with a reset that raises", f"raised {type(exc).__name__}: {exc}")
        elif SCENARIO in ("reset-timeout", "reset-timeout-long"):
            length = "5 s" if SCENARIO == "reset-timeout-long" else "0.5 s"
            loop = asyncio.get_running_loop()
            try:
                await pool.release(a, timeout=0.1)
                out("A", f"release(timeout=0.1) with a {length} reset", "returned")
            except BaseException as exc:
                out("A", f"release(timeout=0.1) with a {length} reset", f"raised {type(exc).__name__}")
            if SCENARIO == "reset-timeout-long":
                timed_out_at = loop.time()
                while await obs.fetchval("select count(*) from pg_stat_activity where pid = $1", a_ident[0]):
                    await asyncio.sleep(0.05)
                gone_after = loop.time() - timed_out_at
                out("observer", "A's original backend still alive 1 s after the release timed out", gone_after > 1.0)
                out("observer", "A's original backend gone within 6 s of the release timeout", gone_after < 6.0)
        else:
            task = asyncio.create_task(pool.release(a))
            async def acquire_b():
                return await pool.acquire()

            waiter = asyncio.create_task(acquire_b())   # B queues behind the release
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
                out("A", "release() cancelled 0.1 s into a 0.5 s reset", "returned")
            except asyncio.CancelledError:
                out("A", "release() cancelled 0.1 s into a 0.5 s reset", "raised CancelledError")
            out("observer", "advisory lock holders right after A's cancellation", await advisory_holders(obs))
            b = await waiter
            out("B", "acquired only after the shielded reset finished", await b.fetchval("select current_setting('search_path')"))
            await pool.release(b)
        await asyncio.sleep(0.2)
        await inspect_b(obs, pool, a_ident)

    elif SCENARIO == "backend-killed":
        pool = await make_pool()
        a = await pool.acquire()
        a_ident = await identity(obs, a)
        out("A", "state after the session changes", await dirty(a))
        await obs.execute("select pg_terminate_backend($1)", a_ident[0])
        while await obs.fetchval("select count(*) from pg_stat_activity where pid = $1", a_ident[0]):
            await asyncio.sleep(0.05)
        try:
            await pool.release(a)
            out("A", "release() after the backend was terminated", "returned")
        except Exception as exc:
            out("A", "release() after the backend was terminated", f"raised {type(exc).__name__}")
        await inspect_b(obs, pool, a_ident)

    elif SCENARIO == "cancelled-query":
        pool = await make_pool()
        a = await pool.acquire()
        a_ident = await identity(obs, a)
        out("A", "state after the session changes", await dirty(a))
        query = asyncio.create_task(a.fetch("select pg_sleep(5)"))
        await asyncio.sleep(0.3)
        query.cancel()
        try:
            await query
        except asyncio.CancelledError:
            out("A", "long query cancelled after 0.3 s", "CancelledError")
        await pool.release(a)
        out("A", "release() immediately after the cancellation", "returned")
        await inspect_b(obs, pool, a_ident)

    else:
        raise SystemExit(f"unknown scenario {SCENARIO}")

    out("observer", "pool backends at the end", await pool_backends(obs))
    await pool.close()
    await obs.close()


asyncio.run(main())
