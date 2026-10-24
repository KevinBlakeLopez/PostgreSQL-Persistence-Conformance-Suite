"""P6: are 57014, 40P01 and 40001 the same path as PR-01's caught 23505?

Premise probe for the gap analysis, not a PPCS case. Each SQLSTATE is produced by PostgreSQL
itself, at statement level, with no injection:
  57014  SET LOCAL statement_timeout = '50ms', then a statement that sleeps 1 s
  40P01  a real deadlock with a second connection R; this session's deadlock_timeout is 50 ms,
         R's is the default 1 s, and R is already waiting when the cycle closes, so this
         session is the victim
  40001  REPEATABLE READ; a second connection commits an UPDATE of the same row after this
         transaction's snapshot; this transaction's UPDATE fails
The application catches the error and lets the transaction API complete normally.
Usage: p6_other_sqlstates.py <subject> <sqlstate> <rep>   subject: sa-core | django | asyncpg | tortoise
"""
import asyncio, json, os, sys, threading, time

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
DB = "probe6"
DSN = f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/{DB}"


def admin(sql, args=()):
    with psycopg.connect(DSN, autocommit=True) as c:
        cur = c.execute(sql, args)
        return cur.fetchall() if cur.description else []


def setup():
    with psycopg.connect(f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/postgres", autocommit=True) as c:
        if not c.execute("select 1 from pg_database where datname=%s", (DB,)).fetchone():
            c.execute(f"create database {DB}")
    admin("drop table if exists d, item; create table d (id int primary key, v int not null);"
          " insert into d values (1, 0), (2, 0); create table item (name text not null)")


class Deadlocker:
    """Connection R: locks row 2, then waits on row 1 (held by the subject)."""

    def __init__(self):
        self.c = psycopg.connect(DSN)
        self.c.execute("update d set v = v where id = 2")
        self.pid = self.c.info.backend_pid
        self.t = threading.Thread(target=self._wait_on_row1, daemon=True)

    def _wait_on_row1(self):
        try:
            self.c.execute("update d set v = v where id = 1")
        except Exception:  # noqa
            pass

    def start_and_wait_until_blocked(self):
        self.t.start()
        for _ in range(500):
            if admin("select wait_event_type from pg_stat_activity where pid=%s", (self.pid,)) == [("Lock",)]:
                return
            time.sleep(0.01)
        raise RuntimeError("R did not block")

    def finish(self):
        self.t.join(5)
        self.c.rollback()
        self.c.close()


def concurrent_update_row1():
    admin("update d set v = v + 1 where id = 1")


# ---- subjects: each returns (xid, pid, caught_sqlstate, api_outcome) -----------------------------
def sa_core(sqlstate, marker):
    import sqlalchemy as sa
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    eng = sa.create_engine(DSN.replace("postgresql://", "postgresql+psycopg://"), pool_size=1, max_overflow=0)
    conn = eng.connect()
    if sqlstate == "40001":
        conn = conn.execution_options(isolation_level="REPEATABLE READ")
    caught, r = None, None
    try:
        with conn.begin():
            conn.execute(text("insert into item values (:m)"), {"m": marker})
            xid, pid = conn.execute(text("select pg_current_xact_id()::text, pg_backend_pid()")).one()
            try:
                if sqlstate == "57014":
                    conn.execute(text("set local statement_timeout = '50ms'"))
                    conn.execute(text("select pg_sleep(1)"))
                elif sqlstate == "40P01":
                    conn.execute(text("set local deadlock_timeout = '50ms'"))
                    conn.execute(text("update d set v = v where id = 1"))
                    r = Deadlocker(); r.start_and_wait_until_blocked()
                    conn.execute(text("update d set v = v where id = 2"))
                else:
                    conn.execute(text("select v from d where id = 1"))
                    concurrent_update_row1()
                    conn.execute(text("update d set v = v + 1 where id = 1"))
            except DBAPIError as e:
                caught = getattr(e.orig, "sqlstate", None)
        api = "returned normally"
    except Exception as e:  # noqa
        api = f"raised {type(e).__name__}"
    if r:
        r.finish()
    conn.close(); eng.dispose()
    return xid, pid, caught, api


_django_ready = False


def django(sqlstate, marker):
    global _django_ready
    import django as dj
    from django.conf import settings
    if not _django_ready:
        base = {"ENGINE": "django.db.backends.postgresql", "NAME": DB, "USER": "postgres", "PASSWORD": PW,
                "HOST": "127.0.0.1", "PORT": str(PORT)}
        import psycopg as _p
        settings.configure(DATABASES={"default": base,
                                      "rr": {**base, "OPTIONS": {"isolation_level": _p.IsolationLevel.REPEATABLE_READ}}},
                           INSTALLED_APPS=[], USE_TZ=True)
        dj.setup()
        _django_ready = True
    from django.db import DatabaseError, connections, models, transaction
    from django.db.models import F
    from django.db.models.expressions import RawSQL

    class D(models.Model):
        id = models.IntegerField(primary_key=True)
        v = models.IntegerField()

        class Meta:
            app_label = "probe6"
            db_table = "d"
            managed = False

    class Item(models.Model):
        name = models.TextField(primary_key=True)

        class Meta:
            app_label = "probe6"
            db_table = "item"
            managed = False

    alias = "rr" if sqlstate == "40001" else "default"
    caught, r = None, None
    hooks = []
    try:
        with transaction.atomic(using=alias):
            Item.objects.using(alias).create(name=marker)
            with connections[alias].cursor() as cur:
                cur.execute("select pg_current_xact_id()::text, pg_backend_pid()")
                xid, pid = cur.fetchone()
            transaction.on_commit(lambda: hooks.append("on_commit"), using=alias)
            try:  # the failing statement is an ORM QuerySet.update(), not a raw cursor
                if sqlstate == "57014":
                    with connections[alias].cursor() as cur:
                        cur.execute("set local statement_timeout = '50ms'")
                    D.objects.using(alias).filter(id=1).update(v=RawSQL("(select 0 from pg_sleep(1))", []))
                elif sqlstate == "40P01":
                    with connections[alias].cursor() as cur:
                        cur.execute("set local deadlock_timeout = '50ms'")
                    D.objects.using(alias).filter(id=1).update(v=F("v"))
                    r = Deadlocker(); r.start_and_wait_until_blocked()
                    D.objects.using(alias).filter(id=2).update(v=F("v"))
                else:
                    list(D.objects.using(alias).filter(id=1))
                    concurrent_update_row1()
                    D.objects.using(alias).filter(id=1).update(v=F("v") + 1)
            except DatabaseError as e:
                caught = getattr(e.__cause__, "sqlstate", None)
        api = "returned normally"
    except Exception as e:  # noqa
        api = f"raised {type(e).__name__}"
    if r:
        r.finish()
    connections[alias].close()
    return xid, pid, caught, api + (f"; on_commit={hooks}")


async def _asyncpg_body(c, sqlstate, marker):
    import asyncpg
    await c.execute("insert into item values ($1)", marker)
    xid, pid = await c.fetchrow("select pg_current_xact_id()::text, pg_backend_pid()")
    caught, r = None, None
    try:
        if sqlstate == "57014":
            await c.execute("set local statement_timeout = '50ms'")
            await c.execute("select pg_sleep(1)")
        elif sqlstate == "40P01":
            await c.execute("set local deadlock_timeout = '50ms'")
            await c.execute("update d set v = v where id = 1")
            r = Deadlocker()
            await asyncio.to_thread(r.start_and_wait_until_blocked)
            await c.execute("update d set v = v where id = 2")
        else:
            await c.execute("select v from d where id = 1")
            await asyncio.to_thread(concurrent_update_row1)
            await c.execute("update d set v = v + 1 where id = 1")
    except asyncpg.PostgresError as e:
        caught = e.sqlstate
    return xid, pid, caught, r


def asyncpg_subject(sqlstate, marker):
    import asyncpg

    async def run():
        c = await asyncpg.connect(DSN)
        tx = c.transaction(isolation="repeatable_read" if sqlstate == "40001" else None)
        try:
            async with tx:
                xid, pid, caught, r = await _asyncpg_body(c, sqlstate, marker)
            api = f"returned normally; {tx!r}"
        except Exception as e:  # noqa
            api = f"raised {type(e).__name__}"
        if r:
            await asyncio.to_thread(r.finish)
        await c.close()
        return xid, pid, caught, api
    return asyncio.run(run())


def tortoise_subject(sqlstate, marker):
    from tortoise import Tortoise
    from tortoise.transactions import in_transaction

    async def run():
        await Tortoise.init(db_url=DSN.replace("postgresql://", "postgres://") + "?minsize=1&maxsize=1",
                            modules={"models": ["__main__"]})
        try:
            async with in_transaction() as conn:
                raw = conn._connection  # the asyncpg connection Tortoise checked out for this transaction
                if sqlstate == "40001":  # in_transaction() accepts no isolation level
                    await raw.execute("set transaction isolation level repeatable read")
                xid, pid, caught, r = await _asyncpg_body(raw, sqlstate, marker)
            api = "returned normally"
        except Exception as e:  # noqa
            api = f"raised {type(e).__name__}: {str(e)[:80]}"
        if r:
            await asyncio.to_thread(r.finish)
        await Tortoise.close_connections()
        return xid, pid, caught, api
    return asyncio.run(run())


try:
    from tortoise import fields as _tf
    from tortoise.models import Model as _TModel

    class ProbeItem(_TModel):
        name = _tf.TextField(primary_key=True)

        class Meta:
            table = "item"
except Exception:  # noqa
    pass

SUBJECTS = {"sa-core": sa_core, "django": django, "asyncpg": asyncpg_subject, "tortoise": tortoise_subject}

if __name__ == "__main__":
    subject, sqlstate, rep = sys.argv[1], sys.argv[2], int(sys.argv[3])
    setup()
    marker = f"{subject}-{sqlstate}-{rep}"
    xid, pid, caught, api = SUBJECTS[subject](sqlstate, marker)
    fate = admin("select pg_xact_status(%s::xid8)", (xid,))[0][0]
    vis = bool(admin("select 1 from item where name=%s", (marker,)))
    last = admin("select state, query from pg_stat_activity where pid=%s", (pid,))
    print(json.dumps({"subject": subject, "sqlstate": sqlstate, "rep": rep, "caught": caught, "api": api,
                      "fate": fate, "marker_visible": vis, "backend_after": last[0] if last else None}))
