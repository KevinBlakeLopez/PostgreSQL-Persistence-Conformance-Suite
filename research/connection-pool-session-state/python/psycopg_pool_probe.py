"""psycopg_pool cleanup-failure probes.

psycopg_pool rolls back a connection returned inside a transaction and discards it if the rollback fails. It runs
a user-supplied `reset` callback, if any, and discards the connection if the callback fails or leaves a transaction
open. Without a callback it does not reset session state (documented). These probes check the failure paths.

Pool of one connection (min_size=max_size=1). Borrower A commits a session-level SET search_path, leaves an insert
uncommitted, and returns the connection while the scenario interferes. Borrower B checks out next. Evidence: B's
reads, an independent observer connection (superuser, outside the pool), driver-reported PID plus backend_start.

Usage: python -I psycopg_pool_probe.py <instance-file> <scenario>
"""

import asyncio
import json
import sys

import psycopg
from psycopg_pool import AsyncConnectionPool, ConnectionPool

INST = json.load(open(sys.argv[1]))
SCENARIO = sys.argv[2]
APP = f"ssc-pp-{SCENARIO}"
CONNINFO = psycopg.conninfo.make_conninfo(host=INST["host"], port=INST["port"], dbname=INST["database"],
                                          user=INST["user"], password=INST["password"], application_name=APP)


def out(who, step, observed):
    print(f"{who:<9} {step:<84} {observed}")


OBS = psycopg.connect(host=INST["host"], port=INST["port"], dbname=INST["database"], user=INST["superuser"],
                      password=INST["superuser_password"], autocommit=True, application_name="ssc-pp-observer")
if OBS.execute("select current_setting('cluster_name')").fetchone()[0] != INST["token"]:
    raise SystemExit("refusing: cluster_name is not this investigation's server")
OBS.execute("delete from public.item; delete from tenant_a.item; delete from tenant_b.item")


def ident(conn):
    pid = conn.info.backend_pid
    return pid, OBS.execute("select backend_start::text from pg_stat_activity where pid = %s", (pid,)).fetchone()[0]


def landed(label):
    rows = OBS.execute("select 'public' from public.item where label = %(l)s union all "
                       "select 'tenant_a' from tenant_a.item where label = %(l)s order by 1", {"l": label}).fetchall()
    return ", ".join(r[0] for r in rows) or "not visible"


def report_b(b_ident, a_ident, search_path):
    out("B", "same physical session as A", b_ident == a_ident)
    out("B", "search_path", search_path)


print("scenario:", SCENARIO)

if SCENARIO.startswith("sync-"):
    reset_calls = []

    def failing_reset(conn):
        reset_calls.append(1)
        if len(reset_calls) == 1:
            raise RuntimeError("custom reset failed")   # only A's return fails

    pool = ConnectionPool(CONNINFO, min_size=1, max_size=1, open=True,
                          reset=failing_reset if SCENARIO == "sync-reset-raises" else None)
    pool.wait()
    try:
        with pool.connection() as a:
            a_ident = ident(a)
            a.execute("SET search_path TO tenant_a, public")
            a.commit()
            a.execute("insert into item(label) values ('A-uncommitted')")
            out("A", "committed SET search_path; insert left uncommitted", "done")
            if SCENARIO == "sync-rollback-fails":
                OBS.execute("select pg_terminate_backend(%s)", (a_ident[0],))
                while OBS.execute("select count(*) from pg_stat_activity where pid = %s", (a_ident[0],)).fetchone()[0]:
                    OBS.execute("select pg_sleep(0.05)")
                out("observer", "terminated A's backend inside the block", "done")
            raise RuntimeError("application error")   # the block exits with an error: rollback, then return
    except RuntimeError:
        out("A", "block exited with an application error", "done")
    except psycopg.Error as exc:
        out("A", "block exited with", type(exc).__name__)
    pool.wait()
    out("observer", "A's uncommitted insert after the return", landed("A-uncommitted"))
    with pool.connection() as b:
        report_b(ident(b), a_ident, b.execute("select current_setting('search_path')").fetchone()[0])
        b.execute("insert into item(label) values ('B-unqualified')")
    out("observer", "where B's committed insert landed", landed("B-unqualified"))
    pool.close()

else:
    async def main():
        reset_calls = []

        async def slow_reset(conn):
            reset_calls.append(1)
            if len(reset_calls) == 1:
                await asyncio.sleep(0.5)
            await conn.execute("RESET ALL")
            await conn.commit()   # the pool discards a connection that its reset leaves inside a transaction

        pool = AsyncConnectionPool(CONNINFO, min_size=1, max_size=1, open=False,
                                   reset=slow_reset if SCENARIO == "async-reset-cancelled" else None)
        await pool.open(wait=True)
        a_ident = None

        async def borrower_a():
            nonlocal a_ident
            async with pool.connection() as a:
                a_ident = ident(a)
                await a.execute("SET search_path TO tenant_a, public")
                await a.commit()
                if SCENARIO == "async-cancel-in-query":
                    await a.execute("insert into item(label) values ('A-uncommitted')")
                    out("A", "committed SET search_path; insert left uncommitted; long query", "done")
                    await a.execute("select pg_sleep(5)")
                else:
                    out("A", "committed SET search_path; the block then exits normally", "done")
            if SCENARIO == "async-reset-cancelled":
                out("A", "connection returned; the 0.5 s reset runs in the pool's worker", "done")
            await asyncio.sleep(5)   # A is cancelled here, while the reset is still running

        task = asyncio.create_task(borrower_a())
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
            out("A", "task", "completed")
        except asyncio.CancelledError:
            out("A", "task cancelled 0.3 s in", "CancelledError")
        out("observer", "A's uncommitted insert after the return", landed("A-uncommitted"))
        async with pool.connection() as b:
            sp = (await (await b.execute("select current_setting('search_path')")).fetchone())[0]
            report_b(ident(b), a_ident, sp)
            await b.execute("insert into item(label) values ('B-unqualified')")
        out("observer", "where B's committed insert landed", landed("B-unqualified"))
        await pool.close()

    asyncio.run(main())

OBS.close()
