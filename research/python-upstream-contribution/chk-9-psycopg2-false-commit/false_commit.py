"""False commit on psycopg2, directly and through SQLAlchemy Core and ORM; psycopg 3 as the positive control.

Usage: python -I false_commit.py <rep>      prints one JSON document; PGPASSFILE supplies the password

Each arm: in one transaction, write row X; run a statement that fails with a duplicate key (23505),
which the code catches and ignores; then commit through the API under test. PostgreSQL has aborted
the transaction, so it answers COMMIT with ROLLBACK and keeps nothing. The JSON records what the API
reported, and what an independent autocommit connection (the witness) saw: whether row X exists, and
pg_xact_status of the transaction's id. Every arm sets application_name fc-<arm>-r<rep> for the server log.
"""
import json, sys

import psycopg
import psycopg.errors
import psycopg2
import psycopg2.errors
import psycopg2.extensions as ext
import sqlalchemy
from sqlalchemy import create_engine, event, insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

HOST, PORT, DB, USER = "127.0.0.1", 55463, "fc", "postgres"
XID_SQL = "select pg_current_xact_id_if_assigned()::text"
DUP = 1  # committed by setup(); inserting it again raises 23505
P2_STATUS = {ext.TRANSACTION_STATUS_IDLE: "IDLE", ext.TRANSACTION_STATUS_ACTIVE: "ACTIVE",
             ext.TRANSACTION_STATUS_INTRANS: "INTRANS", ext.TRANSACTION_STATUS_INERROR: "INERROR",
             ext.TRANSACTION_STATUS_UNKNOWN: "UNKNOWN"}
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
    if isinstance(raw, psycopg.Connection):
        return raw.info.transaction_status.name
    return P2_STATUS.get(raw.info.transaction_status, str(raw.info.transaction_status))


def witness(x, xid):
    row = W.execute("select arm from fc_item where id = %s", (x,)).fetchone()
    fate = W.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0] if xid else None
    return {"row_x_exists": row is not None, "xact_status": fate}


def url(driver, app):
    return f"postgresql+{driver}://{USER}@{HOST}:{PORT}/{DB}?application_name={app}"


def sa_events(engine, out):
    event.listen(engine, "commit", lambda c: out.append("ConnectionEvents.commit"))
    event.listen(engine, "rollback", lambda c: out.append("ConnectionEvents.rollback"))


def orm_events(factory, out):
    for name in ("after_commit", "after_rollback", "after_soft_rollback"):
        event.listen(factory, name, (lambda n: lambda *a: out.append(f"SessionEvents.{n}"))(name))


# ---- arms --------------------------------------------------------------------------------------


def raw_commit(module, app, x, sql_commit=False):
    if module is psycopg2:
        conn = psycopg2.connect(host=HOST, port=PORT, dbname=DB, user=USER, application_name=app)
        cur = conn.cursor()
        run = lambda q, p=None: cur.execute(q, p)
        one = lambda: cur.fetchone()[0]
        unique = psycopg2.errors.UniqueViolation
    else:
        conn = psycopg.connect(host=HOST, port=PORT, dbname=DB, user=USER, application_name=app)
        cur = conn.cursor()
        run = lambda q, p=None: cur.execute(q, p)
        one = lambda: cur.fetchone()[0]
        unique = psycopg.errors.UniqueViolation
    r = {}
    run("insert into fc_item values (%s, %s)", (x, app))
    run(XID_SQL)
    xid = one()
    try:
        run("insert into fc_item values (%s, %s)", (DUP, app))
        r["failing_statement"] = "did not fail"
    except unique as e:
        r["failing_statement"] = f"caught {type(e).__name__}"
    r["driver_status_before_commit"] = status(conn)
    try:
        if sql_commit:
            run("COMMIT")
            r["commit_command_status"] = cur.statusmessage
        else:
            conn.commit()
        r["api"] = "returned normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["driver_status_after_commit"] = status(conn)
    conn.close()
    return r, xid


def p2_with_block(app, x):
    conn = psycopg2.connect(host=HOST, port=PORT, dbname=DB, user=USER, application_name=app)
    r = {}
    xid = None
    try:
        with conn:  # psycopg2 commits when the block exits without an exception
            with conn.cursor() as cur:
                cur.execute("insert into fc_item values (%s, %s)", (x, app))
                cur.execute(XID_SQL)
                xid = cur.fetchone()[0]
                try:
                    cur.execute("insert into fc_item values (%s, %s)", (DUP, app))
                    r["failing_statement"] = "did not fail"
                except psycopg2.errors.UniqueViolation as e:
                    r["failing_statement"] = f"caught {type(e).__name__}"
                r["driver_status_before_commit"] = status(conn)
        r["api"] = "block exited normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["driver_status_after_commit"] = status(conn)
    conn.close()
    return r, xid


def core(driver, app, x, how, fail=True):
    engine = create_engine(url(driver, app), pool_size=1, max_overflow=0)
    events, r, xid = [], {}, None
    sa_events(engine, events)
    try:
        if how == "connect-commit":
            with engine.connect() as c:
                c.execute(text("insert into fc_item values (:x, :a)"), {"x": x, "a": app})
                xid = c.execute(text(XID_SQL)).scalar()
                if fail:
                    try:
                        c.execute(text("insert into fc_item values (:x, :a)"), {"x": DUP, "a": app})
                        r["failing_statement"] = "did not fail"
                    except IntegrityError as e:
                        r["failing_statement"] = f"caught {type(e).__name__} ({type(e.orig).__name__})"
                r["sa_in_transaction_before_commit"] = c.in_transaction()
                r["driver_status_before_commit"] = status(c.connection.dbapi_connection)
                c.commit()
                r["api"] = "returned normally"
                r["sa_in_transaction_after_commit"] = c.in_transaction()
        else:  # engine.begin(): commits when the block exits without an exception
            with engine.begin() as c:
                c.execute(text("insert into fc_item values (:x, :a)"), {"x": x, "a": app})
                xid = c.execute(text(XID_SQL)).scalar()
                try:
                    c.execute(text("insert into fc_item values (:x, :a)"), {"x": DUP, "a": app})
                    r["failing_statement"] = "did not fail"
                except IntegrityError as e:
                    r["failing_statement"] = f"caught {type(e).__name__} ({type(e.orig).__name__})"
                r["driver_status_before_commit"] = status(c.connection.dbapi_connection)
            r["api"] = "block exited normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["events"] = events
    engine.dispose()
    return r, xid


def orm(driver, app, x, how):
    engine = create_engine(url(driver, app), pool_size=1, max_overflow=0)
    factory = sessionmaker(engine)
    events, r, xid = [], {}, None
    sa_events(engine, events)
    orm_events(factory, events)

    def body(s):
        nonlocal xid
        s.add(Item(id=x, arm=app))
        s.flush()
        xid = s.execute(text(XID_SQL)).scalar()
        try:
            if how == "flush":
                s.add(Item(id=DUP, arm=app))
                s.flush()
            else:
                s.execute(insert(Item).values(id=DUP, arm=app))
            r["failing_statement"] = "did not fail"
        except IntegrityError as e:
            r["failing_statement"] = f"caught {type(e).__name__} ({type(e.orig).__name__})"
        if how == "flush":
            r["driver_status_before_commit"] = "not read (the Session requires a rollback)"
        else:
            try:
                r["driver_status_before_commit"] = status(s.connection().connection.dbapi_connection)
            except Exception as e:
                r["driver_status_before_commit"] = "probe raised " + exc(e)

    try:
        if how == "begin":
            with factory.begin() as s:  # commits when the block exits without an exception
                body(s)
            r["api"] = "block exited normally"
        else:
            with factory() as s:
                body(s)
                s.commit()
                r["api"] = "returned normally"
    except Exception as e:
        r["api"] = "raised " + exc(e)
    r["events"] = events
    engine.dispose()
    return r, xid


ARMS = [  # (name, callable); row ids are 100 apart
    ("p2-raw-commit", lambda a, x: raw_commit(psycopg2, a, x)),
    ("p2-raw-with", lambda a, x: p2_with_block(a, x)),
    ("p2-raw-sql-commit", lambda a, x: raw_commit(psycopg2, a, x, sql_commit=True)),
    ("p2-core-connect-commit", lambda a, x: core("psycopg2", a, x, "connect-commit")),
    ("p2-core-engine-begin", lambda a, x: core("psycopg2", a, x, "begin")),
    ("p2-orm-execute-commit", lambda a, x: orm("psycopg2", a, x, "commit")),
    ("p2-orm-sessionmaker-begin", lambda a, x: orm("psycopg2", a, x, "begin")),
    ("p2-orm-flush-control", lambda a, x: orm("psycopg2", a, x, "flush")),
    ("p2-core-no-error-control", lambda a, x: core("psycopg2", a, x, "connect-commit", fail=False)),
    ("p3-raw-commit", lambda a, x: raw_commit(psycopg, a, x)),
    ("p3-raw-sql-commit", lambda a, x: raw_commit(psycopg, a, x, sql_commit=True)),
    ("p3-core-connect-commit", lambda a, x: core("psycopg", a, x, "connect-commit")),
    ("p3-orm-execute-commit", lambda a, x: orm("psycopg", a, x, "commit")),
]


def main():
    setup()
    out = {"rep": REP, "versions": {
        "python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
        "psycopg2": psycopg2.__version__.split()[0], "psycopg2_libpq": psycopg2.extensions.libpq_version(),
        "psycopg": psycopg.__version__, "psycopg_impl": psycopg.pq.__impl__, "psycopg_libpq": psycopg.pq.version(),
        "server": W.execute("show server_version").fetchone()[0]}, "arms": []}
    for i, (name, fn) in enumerate(ARMS):
        x = 100 * (i + 1)
        app = f"fc-{name}-r{REP}"
        r, xid = fn(app, x)
        out["arms"].append({"arm": name, "application_name": app, "row_x": x, "xid": xid, **r,
                            "witness": witness(x, xid)})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
