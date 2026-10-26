"""False commit through SQLAlchemy's asyncio engine on asyncpg; raw asyncpg and SQLAlchemy on async psycopg as controls.

Usage: python -I false_commit_async.py <rep>      prints one JSON document; PGPASSFILE supplies the password

Each arm, as in CHK-9: in one transaction, write row X; run an insert that fails with a duplicate key
(23505), which the code catches and ignores; then commit through the API under test. PostgreSQL has
aborted the transaction, so it answers COMMIT with ROLLBACK and keeps nothing. The JSON records what the
API reported, and what an independent autocommit connection (the witness, sync psycopg) saw: whether row
X exists, and pg_xact_status of the transaction's id. Each arm sets application_name fc-<arm>-r<rep>.
"""
import asyncio, json, sys

import asyncpg
import psycopg
import sqlalchemy
from sqlalchemy import event, insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

HOST, PORT, DB, USER = "127.0.0.1", 55463, "fc", "postgres"
XID_SQL = "select pg_current_xact_id_if_assigned()::text"
DUP = 1
PQTRANS = {0: "IDLE", 1: "ACTIVE", 2: "INTRANS", 3: "INERROR", 4: "UNKNOWN"}
REP = sys.argv[1]
W = psycopg.connect(host=HOST, port=PORT, dbname=DB, user=USER, autocommit=True, application_name=f"fc-witness-r{REP}")


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "fc_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    arm: Mapped[str]


def setup():
    W.execute("drop table if exists fc_item")
    W.execute("create table fc_item (id int primary key, arm text not null)")
    W.execute("insert into fc_item values (%s, 'setup')", (DUP,))


def exc(e):
    first = str(e).splitlines()[0] if str(e) else ""
    return f"{type(e).__module__}.{type(e).__qualname__}: {first}"


def status(raw):
    """Driver-level transaction status. asyncpg exposes none publicly beyond is_in_transaction();
    its protocol's xact_status (libpq's PQTRANS values) is read when present, and labelled as such."""
    if isinstance(raw, psycopg.AsyncConnection):
        return raw.info.transaction_status.name
    xs = getattr(getattr(raw, "_protocol", None), "xact_status", None)
    if xs is not None:
        return f"{PQTRANS.get(xs, xs)} (protocol xact_status)"
    return f"is_in_transaction={raw.is_in_transaction()}"


def witness(x, xid):
    row = W.execute("select arm from fc_item where id = %s", (x,)).fetchone()
    fate = W.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0] if xid else None
    return {"row_x_exists": row is not None, "xact_status": fate}


def engine_for(driver, app):
    if driver == "asyncpg":
        return create_async_engine(f"postgresql+asyncpg://{USER}@{HOST}:{PORT}/{DB}", pool_size=1, max_overflow=0,
                                   connect_args={"server_settings": {"application_name": app}})
    return create_async_engine(f"postgresql+psycopg://{USER}@{HOST}:{PORT}/{DB}?application_name={app}",
                               pool_size=1, max_overflow=0)


async def driver_of(conn):
    raw = await conn.get_raw_connection()
    return raw.driver_connection


# ---- arms --------------------------------------------------------------------------------------


async def raw_asyncpg(app, x, how):
    conn = await asyncpg.connect(host=HOST, port=PORT, database=DB, user=USER, server_settings={"application_name": app})
    r, xid = {}, None

    async def body():
        nonlocal xid
        await conn.execute("insert into fc_item values ($1, $2)", x, app)
        xid = await conn.fetchval(XID_SQL)
        try:
            await conn.execute("insert into fc_item values ($1, $2)", DUP, app)
            r["failing_statement"] = "did not fail"
        except asyncpg.UniqueViolationError as e:
            r["failing_statement"] = f"caught {type(e).__name__}"
        r["driver_status_before_commit"] = status(conn)

    try:
        if how == "transaction-block":
            async with conn.transaction():
                await body()
            r["api"] = "block exited normally"
        elif how == "start-commit":
            tr = conn.transaction()
            await tr.start()
            await body()
            await tr.commit()
            r["api"] = "returned normally"
        else:  # SQL BEGIN ... COMMIT, to read the server's answer
            await conn.execute("BEGIN")
            await body()
            r["commit_command_status"] = await conn.execute("COMMIT")
            r["api"] = "returned normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["driver_status_after_commit"] = status(conn)
    await conn.close()
    return r, xid


async def core(driver, app, x, how, fail=True):
    engine = engine_for(driver, app)
    events, r, xid = [], {}, None
    event.listen(engine.sync_engine, "commit", lambda c: events.append("ConnectionEvents.commit"))
    event.listen(engine.sync_engine, "rollback", lambda c: events.append("ConnectionEvents.rollback"))

    async def body(c):
        nonlocal xid
        await c.execute(text("insert into fc_item values (:x, :a)"), {"x": x, "a": app})
        xid = (await c.execute(text(XID_SQL))).scalar()
        if fail:
            try:
                await c.execute(text("insert into fc_item values (:x, :a)"), {"x": DUP, "a": app})
                r["failing_statement"] = "did not fail"
            except IntegrityError as e:
                r["failing_statement"] = f"caught {type(e).__name__} ({type(e.orig).__name__})"
        r["driver_status_before_commit"] = status(await driver_of(c))

    try:
        if how == "connect-commit":
            async with engine.connect() as c:
                await body(c)
                r["sa_in_transaction_before_commit"] = c.in_transaction()
                await c.commit()
                r["api"] = "returned normally"
                r["sa_in_transaction_after_commit"] = c.in_transaction()
        else:
            async with engine.begin() as c:
                await body(c)
            r["api"] = "block exited normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["events"] = events
    await engine.dispose()
    return r, xid


async def orm(driver, app, x, how):
    engine = engine_for(driver, app)
    events, r, xid = [], {}, None
    event.listen(engine.sync_engine, "commit", lambda c: events.append("ConnectionEvents.commit"))
    event.listen(engine.sync_engine, "rollback", lambda c: events.append("ConnectionEvents.rollback"))
    ArmSession = type("ArmSession", (Session,), {})  # a class of its own, so these listeners see only this arm
    for name in ("after_commit", "after_rollback", "after_soft_rollback"):
        event.listen(ArmSession, name, (lambda n: lambda *a: events.append(f"SessionEvents.{n}"))(name))
    factory = async_sessionmaker(engine, sync_session_class=ArmSession)

    async def body(s):
        nonlocal xid
        s.add(Item(id=x, arm=app))
        await s.flush()
        xid = (await s.execute(text(XID_SQL))).scalar()
        try:
            if how == "flush":
                s.add(Item(id=DUP, arm=app))
                await s.flush()
            else:
                await s.execute(insert(Item).values(id=DUP, arm=app))
            r["failing_statement"] = "did not fail"
        except IntegrityError as e:
            r["failing_statement"] = f"caught {type(e).__name__} ({type(e.orig).__name__})"
        if how == "flush":
            r["driver_status_before_commit"] = "not read (the Session requires a rollback)"
        else:
            try:
                r["driver_status_before_commit"] = status(await driver_of(await s.connection()))
            except Exception as e:
                r["driver_status_before_commit"] = "probe raised " + exc(e)

    try:
        if how == "begin":
            async with factory.begin() as s:
                await body(s)
            r["api"] = "block exited normally"
        else:
            async with factory() as s:
                await body(s)
                await s.commit()
                r["api"] = "returned normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["events"] = events
    await engine.dispose()
    return r, xid


ARMS = [
    ("ap-raw-transaction-block", lambda a, x: raw_asyncpg(a, x, "transaction-block")),
    ("ap-raw-start-commit", lambda a, x: raw_asyncpg(a, x, "start-commit")),
    ("ap-raw-sql-commit", lambda a, x: raw_asyncpg(a, x, "sql")),
    ("ap-core-connect-commit", lambda a, x: core("asyncpg", a, x, "connect-commit")),
    ("ap-core-engine-begin", lambda a, x: core("asyncpg", a, x, "begin")),
    ("ap-orm-execute-commit", lambda a, x: orm("asyncpg", a, x, "commit")),
    ("ap-orm-sessionmaker-begin", lambda a, x: orm("asyncpg", a, x, "begin")),
    ("ap-orm-flush-control", lambda a, x: orm("asyncpg", a, x, "flush")),
    ("ap-core-no-error-control", lambda a, x: core("asyncpg", a, x, "connect-commit", fail=False)),
    ("pa-core-connect-commit", lambda a, x: core("psycopg", a, x, "connect-commit")),
    ("pa-orm-execute-commit", lambda a, x: orm("psycopg", a, x, "commit")),
]


async def main():
    setup()
    out = {"rep": REP, "versions": {
        "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__, "asyncpg": asyncpg.__version__,
        "psycopg": psycopg.__version__, "psycopg_impl": psycopg.pq.__impl__, "psycopg_libpq": psycopg.pq.version(),
        "server": W.execute("show server_version").fetchone()[0]}, "arms": []}
    for i, (name, fn) in enumerate(ARMS):
        x = 100 * (i + 1)
        app = f"fc-{name}-r{REP}"
        r, xid = await fn(app, x)
        out["arms"].append({"arm": name, "application_name": app, "row_x": x, "xid": xid, **r,
                            "witness": witness(x, xid)})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
