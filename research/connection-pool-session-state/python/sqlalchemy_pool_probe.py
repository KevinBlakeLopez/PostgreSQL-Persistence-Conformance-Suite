"""SQLAlchemy pool cleanup-failure probes.

SQLAlchemy's documented reset-on-return is a rollback ("reset_on_return='rollback'"). Session state such as
search_path is documented to carry over. These probes ask what happens when that rollback does not complete:
an asyncio cancellation of AsyncConnection.close() during the reset, and a backend terminated before close().
Each has a normal-close control on the same engine settings.

Pool of one connection (pool_size=1, max_overflow=0). Borrower A commits a session-level SET search_path, then
leaves an uncommitted insert open and closes. Borrower B checks out next. Evidence: B's reads, an independent
observer connection (superuser, outside the pool), and physical identity (driver-reported PID plus backend_start).

Usage: python -I sqlalchemy_pool_probe.py <instance-file> <scenario>
"""

import asyncio
import json
import sys

import psycopg
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.util import await_

INST = json.load(open(sys.argv[1]))
SCENARIO = sys.argv[2]
APP = f"ssc-sa-{SCENARIO}"


def out(who, step, observed):
    print(f"{who:<9} {step:<84} {observed}")


OBS = psycopg.connect(host=INST["host"], port=INST["port"], dbname=INST["database"], user=INST["superuser"],
                      password=INST["superuser_password"], autocommit=True, application_name="ssc-sa-observer")
if OBS.execute("select current_setting('cluster_name')").fetchone()[0] != INST["token"]:
    raise SystemExit("refusing: cluster_name is not this investigation's server")
OBS.execute("delete from public.item; delete from tenant_a.item; delete from tenant_b.item")


def url(driver):
    return URL.create(f"postgresql+{driver}", username=INST["user"], password=INST["password"], host=INST["host"],
                      port=INST["port"], database=INST["database"])


def backend_start(pid):
    return OBS.execute("select backend_start::text from pg_stat_activity where pid = %s", (pid,)).fetchone()[0]


def landed(label):
    rows = OBS.execute("select 'public' from public.item where label = %(l)s union all "
                       "select 'tenant_a' from tenant_a.item where label = %(l)s order by 1", {"l": label}).fetchall()
    return ", ".join(r[0] for r in rows) or "not visible"


def wait_gone(pid):
    while OBS.execute("select count(*) from pg_stat_activity where pid = %s", (pid,)).fetchone()[0]:
        OBS.execute("select pg_sleep(0.05)")


print("scenario:", SCENARIO)

if SCENARIO.startswith("async-"):
    async def main():
        engine = create_async_engine(url("asyncpg"), pool_size=1, max_overflow=0,
                                     connect_args={"server_settings": {"application_name": APP}})
        slow_once = []

        @event.listens_for(engine.sync_engine, "reset")
        def slow_reset(dbapi_conn, record, reset_state):
            if SCENARIO == "async-cancel-close" and not slow_once:
                slow_once.append(1)
                await_(asyncio.sleep(0.5))   # widens the reset-on-return so the cancellation lands inside it

        async def pid_of(conn):
            raw = await conn.get_raw_connection()
            return raw.driver_connection.get_server_pid()

        a = await engine.connect()
        a_pid = await pid_of(a)
        a_ident = (a_pid, backend_start(a_pid))
        await a.execute(text("SET search_path TO tenant_a, public"))
        await a.commit()
        await a.execute(text("insert into item(label) values ('A-uncommitted')"))
        out("A", "committed SET search_path; insert left uncommitted", "done")
        if SCENARIO == "async-cancel-close":
            task = asyncio.create_task(a.close())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
                out("A", "close() cancelled 0.1 s into a 0.5 s reset", "returned")
            except asyncio.CancelledError:
                out("A", "close() cancelled 0.1 s into a 0.5 s reset", "raised CancelledError")
        else:
            await a.close()
            out("A", "close()", "returned")
        out("observer", "A's uncommitted insert after close", landed("A-uncommitted"))

        b = await engine.connect()
        b_pid = await pid_of(b)
        out("B", "same physical session as A", (b_pid, backend_start(b_pid)) == a_ident)
        out("B", "search_path", (await b.execute(text("select current_setting('search_path')"))).scalar())
        await b.execute(text("insert into item(label) values ('B-unqualified')"))
        await b.commit()
        out("observer", "where B's committed insert landed", landed("B-unqualified"))
        out("observer", "A's insert after B's commit", landed("A-uncommitted"))
        await b.close()
        await engine.dispose()

    asyncio.run(main())

else:
    engine = create_engine(url("psycopg"), pool_size=1, max_overflow=0,
                           connect_args={"application_name": APP})
    a = engine.connect()
    a_pid = a.connection.driver_connection.info.backend_pid
    a_ident = (a_pid, backend_start(a_pid))
    a.execute(text("SET search_path TO tenant_a, public"))
    a.commit()
    a.execute(text("insert into item(label) values ('A-uncommitted')"))
    out("A", "committed SET search_path; insert left uncommitted", "done")
    if SCENARIO == "sync-rollback-fails":
        OBS.execute("select pg_terminate_backend(%s)", (a_pid,))
        wait_gone(a_pid)
        out("observer", "terminated A's backend before close()", "done")
    try:
        a.close()
        out("A", "close()", "returned")
    except Exception as exc:
        out("A", "close()", f"raised {type(exc).__name__}")
    out("observer", "A's uncommitted insert after close", landed("A-uncommitted"))

    b = engine.connect()
    b_pid = b.connection.driver_connection.info.backend_pid
    out("B", "same physical session as A", (b_pid, backend_start(b_pid)) == a_ident)
    out("B", "search_path", b.execute(text("select current_setting('search_path')")).scalar())
    b.execute(text("insert into item(label) values ('B-unqualified')"))
    b.commit()
    out("observer", "where B's committed insert landed", landed("B-unqualified"))
    out("observer", "A's insert after B's commit", landed("A-uncommitted"))
    b.close()
    engine.dispose()

OBS.close()
