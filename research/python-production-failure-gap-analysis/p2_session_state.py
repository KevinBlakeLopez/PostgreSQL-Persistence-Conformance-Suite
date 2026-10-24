"""P2: does session state set by one unit of work survive the pool into the next unit?

Premise probe for the gap analysis, not a PPCS case. Unit 1 sets session state and commits
(or runs in autocommit), as ordinary application code would, then returns the connection.
Unit 2 checks out the next connection from the same pool (size 1), reads its state, and
inserts an unqualified row. A separate superuser witness records:
  - which table received unit 2's row (public.item or tenant_s.item), and its inserted_by
    column (DEFAULT current_user), an independent record of the role unit 2 ran as;
  - advisory locks held by unit 1's backend after unit 1 returned it;
  - whether unit 2 ran on the same backend.
"""
import asyncio, json, os, sys

import asyncpg
import psycopg
import psycopg_pool
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
APP_PW = "app-login-probe-only"
ADMIN = f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/probe2"
APP = f"postgresql://app_login:{APP_PW}@127.0.0.1:{PORT}/probe2"

SET_STATE_T = ("SET ROLE tenant_a; SET app.tenant_id = 'a'; SET search_path = tenant_s, public;"
             " SET statement_timeout = '54321'; SELECT pg_advisory_lock({key});"
             " CREATE TEMP TABLE IF NOT EXISTS scratch_tmp (x int)")
KEYS = iter(range(5001, 5100))


def SET_STATE_NEXT():
    return SET_STATE_T.format(key=next(KEYS))


SET_STATE = SET_STATE_T
READ_STATE = ("select current_user::text, coalesce(current_setting('app.tenant_id', true), '<unset>'),"
              " current_setting('search_path'), current_setting('statement_timeout'),"
              " (to_regclass('pg_temp.scratch_tmp') is not null), pg_backend_pid()")
FIELDS = ("current_user", "app.tenant_id", "search_path", "statement_timeout", "temp_table_visible", "pid")


def setup():
    with psycopg.connect(f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/postgres", autocommit=True) as c:
        c.execute("drop database if exists probe2")
        c.execute("create database probe2")
        c.execute(f"alter role app_login password '{APP_PW}'")
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute("create schema tenant_s")
        for s in ("public", "tenant_s"):
            c.execute(f"create table {s}.item (name text not null, inserted_by name not null default current_user)")
        c.execute("grant usage, create on schema public, tenant_s to app_login, tenant_a")
        c.execute("grant select, insert on all tables in schema public, tenant_s to app_login, tenant_a")


def witness_landing(marker):
    with psycopg.connect(ADMIN, autocommit=True) as c:
        rows = c.execute("select 'public' as s, inserted_by::text from public.item where name=%s union all "
                         "select 'tenant_s', inserted_by::text from tenant_s.item where name=%s",
                         (marker, marker)).fetchall()
        return [f"{s}.item by {by}" for s, by in rows] or ["NOT VISIBLE"]


def witness_advisory(pid):
    with psycopg.connect(ADMIN, autocommit=True) as c:
        return c.execute("select count(*) from pg_locks where locktype='advisory' and pid=%s", (pid,)).fetchone()[0]


def summarize(flavor, pid1, state2, marker):
    st = dict(zip(FIELDS, state2))
    return {"flavor": flavor, "same_backend": st.pop("pid") == pid1,
            "unit2_saw": st, "unit2_row": witness_landing(marker)}


# ---- flavors -------------------------------------------------------------------------------
async def f_asyncpg_pool():
    pool = await asyncpg.create_pool(APP, min_size=1, max_size=1)
    async with pool.acquire() as c:
        pid1 = await c.fetchval("select pg_backend_pid()")
        await c.execute(SET_STATE_NEXT())
    adv = witness_advisory(pid1)
    async with pool.acquire() as c:
        state2 = tuple(await c.fetchrow(READ_STATE))
        await c.execute("insert into item(name) values ('u2-asyncpg')")
    await pool.close()
    return {**summarize("asyncpg Pool (reset: RESET ALL etc.)", pid1, state2, "u2-asyncpg"), "advisory_locks_after_unit1": adv}


def f_psycopg_pool():
    with psycopg_pool.ConnectionPool(APP, min_size=1, max_size=1, open=True) as pool:
        with pool.connection() as c:  # commits on exit
            pid1 = c.execute("select pg_backend_pid()").fetchone()[0]
            c.execute(SET_STATE_NEXT())
        adv = witness_advisory(pid1)
        with pool.connection() as c:
            state2 = c.execute(READ_STATE).fetchone()
            c.execute("insert into item(name) values ('u2-psycopg-pool')")
    return {**summarize("psycopg_pool ConnectionPool (default, no reset)", pid1, state2, "u2-psycopg-pool"), "advisory_locks_after_unit1": adv}


def f_sqlalchemy_queuepool():
    eng = sa.create_engine(APP.replace("postgresql://", "postgresql+psycopg://"), pool_size=1, max_overflow=0)
    with eng.begin() as c:
        pid1 = c.execute(text("select pg_backend_pid()")).scalar()
        for stmt in SET_STATE_NEXT().split(";"):
            c.execute(text(stmt))
    adv = witness_advisory(pid1)
    with eng.begin() as c:
        state2 = tuple(c.execute(text(READ_STATE)).one())
        c.execute(text("insert into item(name) values ('u2-sa-psycopg')"))
    eng.dispose()
    return {**summarize("SQLAlchemy QueuePool + psycopg (reset_on_return rollback)", pid1, state2, "u2-sa-psycopg"), "advisory_locks_after_unit1": adv}


async def f_sqlalchemy_asyncpg():
    eng = create_async_engine(APP.replace("postgresql://", "postgresql+asyncpg://"), pool_size=1, max_overflow=0)
    async with eng.begin() as c:
        pid1 = (await c.execute(text("select pg_backend_pid()"))).scalar()
        for stmt in SET_STATE_NEXT().split(";"):
            await c.execute(text(stmt))
    adv = witness_advisory(pid1)
    async with eng.begin() as c:
        state2 = tuple((await c.execute(text(READ_STATE))).one())
        await c.execute(text("insert into item(name) values ('u2-sa-asyncpg')"))
    await eng.dispose()
    return {**summarize("SQLAlchemy AsyncAdaptedQueuePool + asyncpg", pid1, state2, "u2-sa-asyncpg"), "advisory_locks_after_unit1": adv}


def f_django():
    import django
    from django.conf import settings
    base = {"ENGINE": "django.db.backends.postgresql", "NAME": "probe2", "USER": "app_login",
            "PASSWORD": APP_PW, "HOST": "127.0.0.1", "PORT": str(PORT)}
    settings.configure(
        DATABASES={"default": {**base, "CONN_MAX_AGE": None},
                   "pooled": {**base, "CONN_MAX_AGE": 0, "OPTIONS": {"pool": {"min_size": 1, "max_size": 1}}}},
        INSTALLED_APPS=[], USE_TZ=True)
    django.setup()
    from django.db import close_old_connections, connections, transaction
    out = []
    for alias, label in (("default", "Django persistent connection (CONN_MAX_AGE None)"),
                         ("pooled", "Django native pool (OPTIONS pool, psycopg_pool)")):
        conn = connections[alias]
        # request 1: autocommit cursor, as a view or middleware would run it
        with conn.cursor() as cur:
            cur.execute("select pg_backend_pid()")
            pid1 = cur.fetchone()[0]
            for stmt in SET_STATE_NEXT().split(";"):
                cur.execute(stmt)
        close_old_connections()  # what request_finished runs
        adv = witness_advisory(pid1)
        # request 2
        marker = f"u2-django-{alias}"
        with transaction.atomic(using=alias):
            with conn.cursor() as cur:
                cur.execute(READ_STATE)
                state2 = cur.fetchone()
                cur.execute("insert into item(name) values (%s)", [marker])
        close_old_connections()
        out.append({**summarize(label, pid1, state2, marker), "advisory_locks_after_unit1": adv})
    for c in connections.all():
        c.close()
    connections["pooled"].close_pool()
    return out


async def main():
    setup()
    results = [await f_asyncpg_pool(), f_psycopg_pool(), f_sqlalchemy_queuepool(), await f_sqlalchemy_asyncpg()]
    results += await asyncio.to_thread(f_django)
    import django
    print(json.dumps({"versions": {"asyncpg": asyncpg.__version__, "psycopg": psycopg.__version__,
                                   "psycopg_pool": psycopg_pool.__version__, "sqlalchemy": sa.__version__,
                                   "django": django.get_version(), "python": sys.version.split()[0]},
                      "unit1_sets": SET_STATE, "results": results}, indent=1))


asyncio.run(main())
