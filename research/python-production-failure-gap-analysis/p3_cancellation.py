"""P3: ordinary asyncio cancellation while a transaction is in flight.

Premise probe for the gap analysis, not a PPCS case. No client-side fault injection: the
application cancels its own task, as asyncio.timeout(), TaskGroup or an anyio cancel scope
would. A server-side gate makes the timing deterministic:
  - gate=commit: a DEFERRABLE INITIALLY DEFERRED constraint trigger on item runs
    pg_advisory_xact_lock(777) at COMMIT, while the runner holds advisory lock 777, so the
    subject's COMMIT is in flight (pg_stat_activity: query COMMIT, wait_event advisory).
  - gate=body: the transaction body runs pg_advisory_xact_lock(777) after its write.
The runner cancels once the witness sees the subject waiting, records what the application
saw and the transaction's fate, then releases the gate, records the final fate, and runs
unit 2 on the same pool (pool size 1).
Cancellation styles: edge = task.cancel() once; level = anyio.CancelScope.cancel() (anyio
re-delivers cancellation at every await inside the scope, including cleanup awaits).
Usage: p3_cancellation.py <subject> <gate> <style> <rep>
"""
import asyncio, json, os, sys, time, traceback

import anyio
import asyncpg

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
ADMIN = f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/probe3"
APP = ADMIN  # superuser is fine here; session state is not under test
EVENTS = []


def ev(name):
    EVENTS.append(name)


async def setup_db():
    c = await asyncpg.connect(ADMIN.replace("/probe3", "/postgres"))
    exists = await c.fetchval("select 1 from pg_database where datname='probe3'")
    if not exists:
        await c.execute("create database probe3")
    await c.close()
    c = await asyncpg.connect(ADMIN)
    await c.execute("""
      drop table if exists item;
      create table item (id serial primary key, name text not null);
      create or replace function gate() returns trigger language plpgsql as
        $$ begin perform pg_advisory_xact_lock(777); return null; end $$;
      create constraint trigger gate after insert on item deferrable initially deferred
        for each row when (new.name like 'slow%') execute function gate();""")
    await c.close()


# ---- subjects ---------------------------------------------------------------------------
class AsyncpgPool:
    name = "asyncpg Pool + Connection.transaction()"

    async def open(self):
        self.pool = await asyncpg.create_pool(APP, min_size=1, max_size=1)

    async def unit1(self, gate, marker, report):
        async with self.pool.acquire() as c:
            async with c.transaction():
                await c.execute("insert into item(name) values ($1)", marker)
                report.update(dict(zip(("pid", "xid"), await c.fetchrow(
                    "select pg_backend_pid(), pg_current_xact_id()::text"))))
                if gate == "body":
                    await c.execute("select pg_advisory_xact_lock(777)")

    async def unit2(self, marker):
        async with self.pool.acquire() as c:
            async with c.transaction():
                await c.execute("insert into item(name) values ($1)", marker)
                return dict(zip(("pid", "xid"), await c.fetchrow(
                    "select pg_backend_pid(), pg_current_xact_id()::text")))

    async def close(self):
        await self.pool.close()


class PsycopgAsyncPool:
    name = "psycopg AsyncConnectionPool + AsyncConnection.transaction()"

    async def open(self):
        import psycopg_pool
        self.pool = psycopg_pool.AsyncConnectionPool(APP, min_size=1, max_size=1, open=False)
        await self.pool.open()

    async def unit1(self, gate, marker, report):
        async with self.pool.connection() as c:
            async with c.transaction():
                await c.execute("insert into item(name) values (%s)", (marker,))
                row = await (await c.execute("select pg_backend_pid(), pg_current_xact_id()::text")).fetchone()
                report.update(pid=row[0], xid=row[1])
                if gate == "body":
                    await c.execute("select pg_advisory_xact_lock(777)")

    async def unit2(self, marker):
        async with self.pool.connection() as c:
            async with c.transaction():
                await c.execute("insert into item(name) values (%s)", (marker,))
                row = await (await c.execute("select pg_backend_pid(), pg_current_xact_id()::text")).fetchone()
                return {"pid": row[0], "xid": row[1]}

    async def close(self):
        await self.pool.close()


class SQLAlchemyAsync:
    def __init__(self, driver):
        self.driver = driver
        self.name = f"SQLAlchemy AsyncSession.begin() + {driver}"

    async def open(self):
        from sqlalchemy import event
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import Session
        self.engine = create_async_engine(APP.replace("postgresql://", f"postgresql+{self.driver}://"),
                                          pool_size=1, max_overflow=0)
        for n in ("commit", "rollback"):
            event.listen(self.engine.sync_engine, n, (lambda n: lambda *a, **k: ev(f"core.{n}"))(n))
        for n in ("checkin", "invalidate", "close", "reset", "soft_invalidate"):
            event.listen(self.engine.sync_engine.pool, n, (lambda n: lambda *a, **k: ev(f"pool.{n}"))(n))
        self.Session = Session
        for n in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.listen(Session, n, (lambda n: lambda *a, **k: ev(f"orm.{n}"))(n))

    async def _unit(self, marker, gate=None, report=None):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(self.engine) as s:
            async with s.begin():
                await s.execute(text("insert into item(name) values (:n)"), {"n": marker})
                row = (await s.execute(text("select pg_backend_pid(), pg_current_xact_id()::text"))).one()
                out = {"pid": row[0], "xid": row[1]}
                if report is not None:
                    report.update(out)
                if gate == "body":
                    await s.execute(text("select pg_advisory_xact_lock(777)"))
        return out

    async def unit1(self, gate, marker, report):
        await self._unit(marker, gate, report)

    async def unit2(self, marker):
        return await self._unit(marker)

    async def close(self):
        await self.engine.dispose()


try:
    from tortoise import fields as _tf
    from tortoise.models import Model as _TModel

    class ProbeItem(_TModel):
        id = _tf.IntField(primary_key=True)
        name = _tf.TextField()

        class Meta:
            table = "item"
except Exception:  # noqa
    pass


class TortoiseSubject:
    name = "Tortoise in_transaction() + asyncpg"

    async def open(self):
        from tortoise import Tortoise
        url = APP.replace("postgresql://", "postgres://") + "?minsize=1&maxsize=1"
        await Tortoise.init(db_url=url, modules={"models": ["__main__"]})

    async def unit1(self, gate, marker, report):
        from tortoise.transactions import in_transaction
        async with in_transaction() as conn:
            await conn.execute_query("insert into item(name) values ($1)", [marker])
            _, rows = await conn.execute_query("select pg_backend_pid() as pid, pg_current_xact_id()::text as xid")
            report.update(pid=rows[0]["pid"], xid=rows[0]["xid"])
            if gate == "body":
                await conn.execute_query("select pg_advisory_xact_lock(777)")

    async def unit2(self, marker):
        from tortoise.transactions import in_transaction
        async with in_transaction() as conn:
            await conn.execute_query("insert into item(name) values ($1)", [marker])
            _, rows = await conn.execute_query("select pg_backend_pid() as pid, pg_current_xact_id()::text as xid")
            return {"pid": rows[0]["pid"], "xid": rows[0]["xid"]}

    async def close(self):
        from tortoise import Tortoise
        await Tortoise.close_connections()


SUBJECTS = {"asyncpg": AsyncpgPool, "psycopg": PsycopgAsyncPool,
            "sa-asyncpg": lambda: SQLAlchemyAsync("asyncpg"), "sa-psycopg": lambda: SQLAlchemyAsync("psycopg"),
            "tortoise": TortoiseSubject}


# ---- runner --------------------------------------------------------------------------------
async def wait_until_gated(w, report, gate, deadline=10.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline:
        if "pid" in report:
            row = await w.fetchrow("select state, wait_event_type, wait_event, query from pg_stat_activity where pid=$1",
                                   report["pid"])
            if row and row["wait_event"] == "advisory":
                q = row["query"].strip().rstrip(";").upper()
                if (gate == "commit" and q == "COMMIT") or (gate == "body" and "PG_ADVISORY_XACT_LOCK" in q):
                    return {"state": row["state"], "wait": f'{row["wait_event_type"]}/{row["wait_event"]}', "query": row["query"].strip()}
        await asyncio.sleep(0.01)
    return None


async def snapshot(w, report, marker):
    fate = await w.fetchval("select pg_xact_status($1::text::xid8)", report["xid"]) if "xid" in report else None
    row = await w.fetchrow("select state, wait_event, query from pg_stat_activity where pid=$1", report.get("pid"))
    vis = await w.fetchval("select count(*) from item where name=$1", marker)
    return {"fate": fate, "marker_visible": bool(vis),
            "backend": None if row is None else f'{row["state"]}/{row["wait_event"]}/{row["query"].strip()[:40]}'}


async def main(subject_key, gate, style, rep):
    await setup_db()
    w = await asyncpg.connect(ADMIN)       # runner + witness
    await w.execute("select pg_advisory_lock(777)")
    subj = SUBJECTS[subject_key]()
    await subj.open()
    marker = f"{'slow' if gate == 'commit' else 'doomed'}-{subject_key}-{gate}-{style}-{rep}"
    report, holder, seen = {}, {}, {}

    async def run_unit1():
        try:
            if style == "level":
                with anyio.CancelScope() as scope:
                    holder["scope"] = scope
                    await subj.unit1(gate, marker, report)
                seen["app"] = "returned normally" + (" (scope cancelled)" if scope.cancelled_caught else "")
            else:
                await subj.unit1(gate, marker, report)
                seen["app"] = "returned normally"
        except BaseException as e:  # noqa: record what the application would see
            seen["app"] = f"{type(e).__module__}.{type(e).__name__}: {str(e)[:120]}"
            if not isinstance(e, asyncio.CancelledError):
                seen["tb"] = traceback.format_exc()[-600:]
            if isinstance(e, asyncio.CancelledError):
                return

    task = asyncio.ensure_future(run_unit1())
    gated = await wait_until_gated(w, report, gate)
    result = {"subject": subj.name, "gate": gate, "style": style, "rep": rep, "gated": gated}
    ev("--cancel--")
    if style == "level":
        holder["scope"].cancel()
    elif style == "edge":
        task.cancel()
    else:  # control: no cancellation; open the gate and let unit 1 finish
        await w.execute("select pg_advisory_unlock(777)")
        await w.execute("select pg_advisory_lock(777)")
    try:
        await asyncio.wait_for(asyncio.shield(task), 8)
        result["unit1_finished"] = True
    except (asyncio.TimeoutError, asyncio.CancelledError):
        result["unit1_finished"] = False
    result["app_saw"] = seen.get("app", "<task cancelled before recording>")
    if "tb" in seen:
        result["tb"] = seen["tb"]
    result["at_report"] = await snapshot(w, report, marker)
    ev("--gate released--")
    await w.execute("select pg_advisory_unlock(777)")
    await asyncio.sleep(0.5)
    if not result["unit1_finished"]:
        try:
            await asyncio.wait_for(task, 5)
            result["unit1_finished_after_release"] = True
            result["app_saw"] = seen.get("app")
        except BaseException as e:  # noqa
            result["unit1_finished_after_release"] = repr(e)
    result["after_release"] = await snapshot(w, report, marker)
    try:
        u2 = await asyncio.wait_for(subj.unit2(f"next-{marker}"), 8)
        result["unit2"] = {"ok": True, "same_backend": u2["pid"] == report.get("pid"),
                           "joined_unit1_xid": u2["xid"] == report.get("xid")}
    except BaseException as e:  # noqa
        result["unit2"] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}
    result["final_unit1_marker_visible"] = bool(await w.fetchval("select count(*) from item where name=$1", marker))
    result["final_fate"] = await w.fetchval("select pg_xact_status($1::text::xid8)", report["xid"]) if "xid" in report else None
    result["events"] = EVENTS
    try:
        await asyncio.wait_for(subj.close(), 8)
    except BaseException as e:  # noqa
        result["close_error"] = repr(e)
    await w.close()
    print(json.dumps(result))


if __name__ == "__main__":
    s, g, st, r = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    asyncio.run(main(s, g, st, r))
