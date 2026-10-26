"""Follow-ups. One per process:  python followups.py preping|alarm_outcome|asyncio"""

from __future__ import annotations

import asyncio
import signal
import sys
import time

import psycopg
from sqlalchemy import create_engine, text

PORT = 55454
DSN = f"postgresql://postgres@127.0.0.1:{PORT}/scratch"
URL = f"postgresql+psycopg://postgres@127.0.0.1:{PORT}/scratch"
TABLE = "p5a_review_f"

W = psycopg.connect(DSN, autocommit=True)


def setup():
    W.execute(f"drop table if exists {TABLE}")
    W.execute(f"create table {TABLE} (code text primary key)")
    W.execute(
        f"create or replace function {TABLE}_slow() returns trigger"
        " language plpgsql as $$ begin perform pg_sleep(3); return null; end $$"
    )
    W.execute(
        f"create constraint trigger {TABLE}_slow after insert on {TABLE}"
        " deferrable initially deferred for each row when (new.code = 'slow')"
        f" execute function {TABLE}_slow()"
    )


def visible():
    return [r[0] for r in W.execute(f"select code from {TABLE} order by code")]


def state(pid):
    row = W.execute("select state from pg_stat_activity where pid = %s", (pid,)).fetchone()
    return None if row is None else row[0]


def fail_commit_once(raw):  # the draft's injection, verbatim
    original = raw.commit

    def commit():
        raw.commit = original
        raise RuntimeError("COMMIT was not sent")

    raw.commit = commit


def preping():
    engine = create_engine(URL, pool_size=1, max_overflow=0, pool_pre_ping=True, pool_timeout=3)
    conn = engine.connect()
    trans = conn.begin()
    conn.execute(text(f"insert into {TABLE} (code) values ('doomed')"))
    raw = conn.connection.driver_connection
    pid = raw.info.backend_pid
    fail_commit_once(raw)
    try:
        trans.commit()
    except RuntimeError as e:
        print("commit raised:", e)
    conn.close()
    print("after close | server:", state(pid), "| psycopg:", raw.info.transaction_status.name)
    for n in (1, 2):
        try:
            c = engine.connect()
        except Exception as e:
            print(f"checkout {n} raised: {type(e).__name__}: {str(e).splitlines()[0]}")
            print(f"  old pid {pid} server state now:", state(pid), "| visible:", visible())
            continue
        r = c.connection.driver_connection
        print(f"checkout {n}: same pid:", r.info.backend_pid == pid, "| psycopg:", r.info.transaction_status.name)
        with c.begin():
            c.execute(text(f"insert into {TABLE} (code) values ('next')"))
        c.close()
        print("  visible:", visible())
    engine.dispose()


def alarm_outcome():
    class RequestTimeout(Exception):
        pass

    def handler(signum, frame):
        raise RequestTimeout("request timeout")

    engine = create_engine(URL, pool_size=1, max_overflow=0, pool_timeout=3)
    conn = engine.connect()
    trans = conn.begin()
    conn.execute(text(f"insert into {TABLE} (code) values ('doomed')"))
    conn.execute(text(f"insert into {TABLE} (code) values ('slow')"))
    raw = conn.connection.driver_connection
    pid = raw.info.backend_pid
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 1.0)
    t = time.monotonic()
    try:
        trans.commit()
    except RequestTimeout as e:
        print(f"commit raised after {time.monotonic() - t:.2f}s: {type(e).__name__}")
    signal.setitimer(signal.ITIMER_REAL, 0)
    print("server:", state(pid), "| psycopg:", raw.info.transaction_status.name, "| visible:", visible())
    conn.close()
    print("close returned | server:", state(pid), "| visible:", visible())
    time.sleep(3.0)
    print("after 3 s | server:", state(pid), "| visible:", visible())
    try:
        with engine.connect() as c:
            same = c.connection.driver_connection is raw
            print("next checkout same dbapi:", same, "| psycopg:", c.connection.driver_connection.info.transaction_status.name)
            print("next statement:", c.execute(text("select 1")).scalar())
    except Exception as e:
        print(f"next checkout/statement raised: {type(e).__name__}: {str(e).splitlines()[0]}")
    engine.dispose()
    print("final visible:", visible())


def asyncio_case():
    from sqlalchemy.ext.asyncio import create_async_engine

    async def main():
        engine = create_async_engine(URL, pool_size=1, max_overflow=0, pool_timeout=3)
        conn = await engine.connect()
        trans = await conn.begin()
        await conn.execute(text(f"insert into {TABLE} (code) values ('doomed')"))
        raw = (await conn.get_raw_connection()).driver_connection
        pid = raw.info.backend_pid
        original = raw.commit

        async def commit():
            raw.commit = original
            raise RuntimeError("COMMIT was not sent")

        raw.commit = commit
        try:
            await trans.commit()
        except RuntimeError as e:
            print("async commit raised:", e)
        print("after commit | psycopg:", raw.info.transaction_status.name, "| server:", state(pid))
        await conn.close()
        print("close returned | server:", state(pid))
        conn2 = await engine.connect()
        raw2 = (await conn2.get_raw_connection()).driver_connection
        print("same dbapi:", raw2 is raw, "| psycopg:", raw2.info.transaction_status.name)
        async with conn2.begin():
            await conn2.execute(text(f"insert into {TABLE} (code) values ('next')"))
        await conn2.close()
        print("visible:", visible())
        await engine.dispose()

    asyncio.run(main())


if __name__ == "__main__":
    setup()
    {"preping": preping, "alarm_outcome": alarm_outcome, "asyncio": asyncio_case}[sys.argv[1]]()
