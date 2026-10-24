"""P1: caught 23505 inside a transaction, then the API's normal completion.

Premise probe for the gap analysis, not a PPCS case. Subjects:
  A asyncpg `async with conn.transaction()`      B asyncpg Transaction.start()/commit()
  C asyncpg raw execute('COMMIT') status string  D asyncpg savepoint-recovery control
  E SQLAlchemy Core postgresql+asyncpg engine.begin()
  F SQLAlchemy ORM AsyncSession.begin(), error from Session.execute() (not flush)
  G SQLAlchemy ORM Session.begin() on psycopg, error from Session.execute() (not flush)
  H SQLAlchemy ORM Session.begin() on psycopg, error from flush (PR-01's path, control)
Independent witness: a separate autocommit asyncpg connection reads pg_xact_status,
marker visibility, and the backend's state and last statement.
"""
import asyncio, json, os, sys

import asyncpg
import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
assert PORT == 55483
DSN = f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/probe"


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class Uniq(Base):
    __tablename__ = "uniq"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)


async def witness(w, xid, pid, marker):
    fate = await w.fetchval("select pg_xact_status($1::text::xid8)", str(xid))
    vis = await w.fetchval("select count(*) from item where name=$1", marker)
    row = await w.fetchrow("select state, query from pg_stat_activity where pid=$1", pid)
    return {"fate": fate, "marker_visible": bool(vis),
            "backend": None if row is None else {"state": row["state"], "last": row["query"].strip()}}


async def reset(w):
    await w.execute("truncate item, uniq restart identity; insert into uniq(code) values ('taken')")


async def asyncpg_cases(w, rep):
    out = {}
    # A: managed block
    c = await asyncpg.connect(DSN)
    pid = await c.fetchval("select pg_backend_pid()")
    tx = c.transaction()
    raised = None
    try:
        async with tx:
            await c.execute("insert into item(name) values ($1)", f"A{rep}")
            xid = await c.fetchval("select pg_current_xact_id()::text")
            try:
                await c.execute("insert into uniq(code) values ('taken')")
            except asyncpg.UniqueViolationError as e:
                caught = e.sqlstate
    except BaseException as e:  # noqa
        raised = repr(e)
    out["A_asyncpg_managed"] = {"caught": caught, "block_raised": raised, "tx_repr": repr(tx),
                                **await witness(w, xid, pid, f"A{rep}")}
    await c.close()
    # B: explicit start/commit
    c = await asyncpg.connect(DSN)
    pid = await c.fetchval("select pg_backend_pid()")
    tx = c.transaction()
    await tx.start()
    await c.execute("insert into item(name) values ($1)", f"B{rep}")
    xid = await c.fetchval("select pg_current_xact_id()::text")
    try:
        await c.execute("insert into uniq(code) values ('taken')")
    except asyncpg.UniqueViolationError as e:
        caught = e.sqlstate
    try:
        ret = await tx.commit()
        commit = f"returned {ret!r}"
    except BaseException as e:  # noqa
        commit = f"raised {e!r}"
    out["B_asyncpg_explicit"] = {"caught": caught, "commit": commit, "tx_repr": repr(tx),
                                 **await witness(w, xid, pid, f"B{rep}")}
    await c.close()
    # C: raw statements; the driver's execute() returns the status string
    c = await asyncpg.connect(DSN)
    pid = await c.fetchval("select pg_backend_pid()")
    await c.execute("BEGIN")
    await c.execute("insert into item(name) values ($1)", f"C{rep}")
    xid = await c.fetchval("select pg_current_xact_id()::text")
    try:
        await c.execute("insert into uniq(code) values ('taken')")
    except asyncpg.UniqueViolationError as e:
        caught = e.sqlstate
    status = await c.execute("COMMIT")
    out["C_asyncpg_raw"] = {"caught": caught, "commit_status": status, **await witness(w, xid, pid, f"C{rep}")}
    await c.close()
    # D: savepoint recovery control
    c = await asyncpg.connect(DSN)
    pid = await c.fetchval("select pg_backend_pid()")
    tx = c.transaction()
    async with tx:
        await c.execute("insert into item(name) values ($1)", f"D{rep}")
        xid = await c.fetchval("select pg_current_xact_id()::text")
        try:
            async with c.transaction():
                await c.execute("insert into uniq(code) values ('taken')")
        except asyncpg.UniqueViolationError as e:
            caught = e.sqlstate
    out["D_asyncpg_savepoint_control"] = {"caught": caught, "tx_repr": repr(tx), **await witness(w, xid, pid, f"D{rep}")}
    await c.close()
    return out


def listeners(target, log, names):
    for n in names:
        event.listen(target, n, (lambda n: lambda *a, **k: log.append(n))(n))


async def sqlalchemy_async_cases(w, rep):
    out = {}
    engine = create_async_engine(DSN.replace("postgresql://", "postgresql+asyncpg://"), pool_size=1, max_overflow=0)
    # E: Core
    log = []
    listeners(engine.sync_engine, log, ["begin", "commit", "rollback"])
    raised = None
    try:
        async with engine.begin() as conn:
            pid = (await conn.execute(text("select pg_backend_pid()"))).scalar()
            await conn.execute(text("insert into item(name) values (:n)"), {"n": f"E{rep}"})
            xid = (await conn.execute(text("select pg_current_xact_id()::text"))).scalar()
            try:
                await conn.execute(text("insert into uniq(code) values ('taken')"))
            except IntegrityError as e:
                caught = getattr(e.orig, "sqlstate", None)
    except BaseException as e:  # noqa
        raised = repr(e)
    out["E_sa_core_asyncpg"] = {"caught": caught, "block_raised": raised, "core_events": log,
                                **await witness(w, xid, pid, f"E{rep}")}
    # F: ORM AsyncSession, error from Session.execute()
    slog = []
    raised = None
    s = AsyncSession(engine)
    listeners(s.sync_session, slog, ["after_begin", "after_commit", "after_rollback", "after_soft_rollback"])
    try:
        async with s.begin():
            s.add(Item(name=f"F{rep}"))
            await s.flush()
            pid = (await s.execute(text("select pg_backend_pid()"))).scalar()
            xid = (await s.execute(text("select pg_current_xact_id()::text"))).scalar()
            try:
                await s.execute(text("insert into uniq(code) values ('taken')"))
            except IntegrityError as e:
                caught = getattr(e.orig, "sqlstate", None)
    except BaseException as e:  # noqa
        raised = repr(e)
    await s.close()
    out["F_sa_orm_asyncpg_execute_error"] = {"caught": caught, "block_raised": raised, "session_events": slog,
                                             **await witness(w, xid, pid, f"F{rep}")}
    await engine.dispose()
    return out


def sqlalchemy_sync_cases(rep):
    out = {}
    engine = sa.create_engine(DSN.replace("postgresql://", "postgresql+psycopg://"), pool_size=1, max_overflow=0)
    for key, via_flush in (("G_sa_orm_psycopg_execute_error", False), ("H_sa_orm_psycopg_flush_error_control", True)):
        slog = []
        s = Session(engine)
        listeners(s, slog, ["after_begin", "after_commit", "after_rollback", "after_soft_rollback"])
        raised = None
        marker = f"{key[0]}{rep}"
        try:
            with s.begin():
                s.add(Item(name=marker))
                s.flush()
                pid = s.execute(text("select pg_backend_pid()")).scalar()
                xid = s.execute(text("select pg_current_xact_id()::text")).scalar()
                try:
                    if via_flush:
                        s.add(Uniq(code="taken"))
                        s.flush()
                    else:
                        s.execute(text("insert into uniq(code) values ('taken')"))
                except IntegrityError as e:
                    caught = getattr(e.orig, "sqlstate", None)
        except BaseException as e:  # noqa
            raised = repr(e)
        s.close()
        out[key] = {"caught": caught, "block_raised": raised, "session_events": slog, "xid": xid, "pid": pid, "marker": marker}
    engine.dispose()
    return out


async def main():
    w = await asyncpg.connect(DSN)
    await w.execute("drop table if exists item, uniq; create table item(id serial primary key, name text not null);"
                    " create table uniq(id serial primary key, code text not null unique)")
    results = []
    for rep in range(1, 4):
        await reset(w)
        r = await asyncpg_cases(w, rep)
        r.update(await sqlalchemy_async_cases(w, rep))
        sync = await asyncio.to_thread(sqlalchemy_sync_cases, rep)
        for k, v in sync.items():
            r[k] = {kk: vv for kk, vv in v.items() if kk not in ("xid", "pid", "marker")}
            r[k].update(await witness(w, v["xid"], v["pid"], v["marker"]))
        results.append(r)
    await w.close()
    versions = {"asyncpg": asyncpg.__version__, "sqlalchemy": sa.__version__, "python": sys.version.split()[0]}
    print(json.dumps({"versions": versions, "repetitions": results}, indent=1))


asyncio.run(main())
