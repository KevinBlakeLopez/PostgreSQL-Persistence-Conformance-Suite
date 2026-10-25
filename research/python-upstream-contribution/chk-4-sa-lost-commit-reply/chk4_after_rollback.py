"""CHK-4: does SQLAlchemy's ORM after_rollback fire when a COMMIT reply is lost and PostgreSQL commits?

Check CHK-4 from ../../python-upstream-contribution-roadmap.md §11, for PY-4. Not a PPCS case.
Nothing is cancelled. The lost reply comes from PPCS's category-E proxy, harness/lib/pg-wire-proxy.mjs,
run unchanged by commit_reply_proxy.mjs: it forwards COMMIT and, when the server's reply reports COMMIT,
drops that reply through ReadyForQuery and closes both sockets. PostgreSQL has committed by then.

Arms (unit 1):
  lost-reply  connection 1 goes through the proxy, so unit 1's COMMIT reply is dropped
  rejected    no proxy; COMMIT fails a deferred foreign key (23503) and PostgreSQL rolls back. Added beyond
              the brief. (Not through the proxy: unit 2 reuses connection 1, and the proxy would drop its reply.)
  no-fault    no proxy; COMMIT succeeds. The positive control
Stacks: sync-psycopg (Session), async-asyncpg and async-psycopg (AsyncSession). A pool of one, as in P3.
Unit 2 then commits a plain write on the same engine. Connections after the first go straight to
PostgreSQL: SQLAlchemy's do_connect event sets the port.
The observer is a separate psycopg connection, straight to PostgreSQL. It reads pg_xact_status() and the
marker rows. stdout has no PIDs, xids, tags or times, so repetitions compare byte for byte; those go to
the raw JSON file named on the command line.
Usage: chk4_after_rollback.py <stack> <arm> <raw.json>  |  chk4_after_rollback.py --versions
"""
import asyncio
import itertools
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import traceback
import warnings
from datetime import datetime, timezone

import psycopg
import sqlalchemy
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session

PG_PORT = 55494  # the CHK-4 container; the observer refuses a server whose cluster_name differs
HERE = os.path.dirname(os.path.abspath(__file__))
PROXY = os.path.join(HERE, "commit_reply_proxy.mjs")
NODE = shutil.which("node")
APP_PASSWORD = os.environ["CHK4_APP_PASSWORD"]
CLUSTER_NAME = os.environ["CHK4_CLUSTER_NAME"]
STACKS = ("sync-psycopg", "async-asyncpg", "async-psycopg")
ARMS = ("lost-reply", "rejected", "no-fault")
INSERT = text("insert into chk4_item(tag) values (:t)")
IDS = text("select pg_backend_pid(), pg_current_xact_id()::text")
DOOMED = text("insert into chk4_child(parent_id, tag) values (-1, :t)")
EVENTS: list[str] = []


def ev(name: str) -> None:
    EVENTS.append(name)


def qualname(obj) -> str:
    return f"{type(obj).__module__}.{type(obj).__qualname__}"


for _n in ("after_commit", "after_rollback", "after_soft_rollback"):
    event.listen(Session, _n, (lambda n: lambda *a, **k: ev(f"orm.{n}"))(_n))


def instrument(sync_engine, proxy_port):
    """P3's listeners, plus the dialect's DBAPI commit and rollback calls and each connection's route."""
    for n in ("commit", "rollback"):
        event.listen(sync_engine, n, (lambda n: lambda *a, **k: ev(f"core.{n}"))(n))
    for n in ("checkin", "invalidate", "close", "reset", "soft_invalidate"):
        event.listen(sync_engine.pool, n, (lambda n: lambda *a, **k: ev(f"pool.{n}"))(n))
    # Ahead of the engine's own first_connect handler, whose dialect initialization ends in do_rollback.
    event.listen(sync_engine.pool, "first_connect", lambda *a, **k: ev("pool.first_connect"), insert=True)
    dialect = sync_engine.dialect
    for name in ("do_commit", "do_rollback"):
        original = getattr(dialect, name)

        def wrapped(dbapi_connection, _original=original, _name=name):
            ev(f"dialect.{_name}")
            try:
                _original(dbapi_connection)
            except BaseException as exc:
                ev(f"dialect.{_name} raised {qualname(exc)}")
                raise

        setattr(dialect, name, wrapped)
    count = itertools.count(1)

    @event.listens_for(sync_engine, "do_connect")
    def route(dialect, conn_rec, cargs, cparams):
        i = next(count)
        if proxy_port is not None and i == 1:
            cparams["port"] = proxy_port
            ev(f"connect {i}: through the proxy")
        else:
            ev(f"connect {i}: direct")


def make_engine(stack, proxy_port):
    base = f"chk4_app:{APP_PASSWORD}@127.0.0.1:{PG_PORT}/chk4"
    libpq = "sslmode=disable&gssencmode=disable&application_name=chk4-subject"
    if stack == "sync-psycopg":
        engine = create_engine(f"postgresql+psycopg://{base}?{libpq}", pool_size=1, max_overflow=0)
        instrument(engine, proxy_port)
        return engine
    if stack == "async-psycopg":
        engine = create_async_engine(f"postgresql+psycopg://{base}?{libpq}", pool_size=1, max_overflow=0)
    else:
        engine = create_async_engine(f"postgresql+asyncpg://{base}", pool_size=1, max_overflow=0,
                                     connect_args={"ssl": False,
                                                   "server_settings": {"application_name": "chk4-subject"}})
    instrument(engine.sync_engine, proxy_port)
    return engine


def unit_sync(engine, tag, rejected, ids):
    with Session(engine) as session:
        with session.begin():
            session.execute(INSERT, {"t": tag})
            ids["pid"], ids["xid"] = session.execute(IDS).one()
            if rejected:
                session.execute(DOOMED, {"t": tag})


async def unit_async(engine, tag, rejected, ids):
    async with AsyncSession(engine) as session:
        async with session.begin():
            await session.execute(INSERT, {"t": tag})
            ids["pid"], ids["xid"] = (await session.execute(IDS)).one()
            if rejected:
                await session.execute(DOOMED, {"t": tag})


class Observer:
    def __init__(self):
        self.conn = psycopg.connect(host="127.0.0.1", port=PG_PORT, dbname="chk4", user="chk4_app",
                                    password=APP_PASSWORD, sslmode="disable", gssencmode="disable",
                                    application_name="chk4-observer", autocommit=True)
        if self.one("show cluster_name") != CLUSTER_NAME:
            raise SystemExit("refusing: this is not the CHK-4 server")

    def one(self, sql, *params):
        return self.conn.execute(sql, params or None).fetchone()[0]

    def fate(self, xid):
        return None if xid is None else self.one("select pg_xact_status(%s::text::xid8)", xid)

    def xmin(self, tag):
        row = self.conn.execute("select xmin::text from chk4_item where tag = %s", (tag,)).fetchone()
        return None if row is None else row[0]


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(f"{record.name} {record.levelname}: {record.getMessage().splitlines()[0][:160]}")


def describe(exc):
    if exc is None:
        return "returned normally"
    lines = str(exc).splitlines()
    out = {"class": qualname(exc), "message": lines[0][:200] if lines else ""}
    if getattr(exc, "orig", None) is not None:
        out["orig"] = qualname(exc.orig)
    if hasattr(exc, "connection_invalidated"):
        out["connection_invalidated"] = exc.connection_invalidated
    return out


def after_unit1(observer, exc, tag, ids):
    xmin = observer.xmin(tag)
    return {"app_saw": describe(exc), "fate_at_report": observer.fate(ids.get("xid")),
            "marker_visible_at_report": xmin is not None,
            "marker_xmin_is_unit1_xid": None if xmin is None else xmin == ids.get("xid")}


def after_unit2(observer, exc, tag, ids1, ids2):
    return {"app_saw": describe(exc), "fate": observer.fate(ids2.get("xid")),
            "marker_visible": observer.xmin(tag) is not None,
            "same_backend_as_unit1": ids2.get("pid") == ids1.get("pid") if ids2 else None,
            "joined_unit1_xid": ids2.get("xid") == ids1.get("xid") if ids2 else None}


def flow_sync(engine, observer, arm, tags, ids, out):
    ev("--unit 1--")
    exc1 = None
    try:
        unit_sync(engine, tags[0], arm == "rejected", ids[0])
    except Exception as exc:  # what the application sees
        exc1 = exc
    ev("--unit 1 ended--")
    out["unit1"] = after_unit1(observer, exc1, tags[0], ids[0])
    ev("--unit 2--")
    exc2 = None
    try:
        unit_sync(engine, tags[1], False, ids[1])
    except Exception as exc:
        exc2 = exc
    ev("--unit 2 ended--")
    out["unit2"] = after_unit2(observer, exc2, tags[1], ids[0], ids[1])
    engine.dispose()
    ev("--disposed--")


async def flow_async(engine, observer, arm, tags, ids, out, loop_errors):
    asyncio.get_running_loop().set_exception_handler(lambda loop, ctx: loop_errors.append(str(ctx.get("message"))))
    ev("--unit 1--")
    exc1 = None
    try:
        await unit_async(engine, tags[0], arm == "rejected", ids[0])
    except Exception as exc:
        exc1 = exc
    ev("--unit 1 ended--")
    out["unit1"] = after_unit1(observer, exc1, tags[0], ids[0])
    ev("--unit 2--")
    exc2 = None
    try:
        await unit_async(engine, tags[1], False, ids[1])
    except Exception as exc:
        exc2 = exc
    ev("--unit 2 ended--")
    out["unit2"] = after_unit2(observer, exc2, tags[1], ids[0], ids[1])
    await engine.dispose()
    ev("--disposed--")


def validity(arm, out):
    u1, u2, problems = out["unit1"], out["unit2"], []
    if arm == "lost-reply":
        if out["proxy"]["dropped"] != 1:
            problems.append("the proxy did not drop exactly one reply")
        if u1["fate_at_report"] != "committed":
            problems.append("unit 1 was not committed at report time")
        if u1["app_saw"] == "returned normally":
            problems.append("unit 1 did not raise")
    elif arm == "rejected":
        if u1["fate_at_report"] != "aborted":
            problems.append("unit 1 was not aborted at report time")
        if u1["app_saw"] == "returned normally":
            problems.append("unit 1 did not raise")
    elif u1["fate_at_report"] != "committed" or u1["app_saw"] != "returned normally":
        problems.append("the control did not commit normally")
    if u2["app_saw"] != "returned normally" or u2["fate"] != "committed" or not u2["marker_visible"]:
        problems.append("unit 2 did not commit normally")
    return "VALID" if not problems else "INVALID: " + "; ".join(problems)


def start_proxy():
    proc = subprocess.Popen([NODE, PROXY, str(PG_PORT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    return proc, json.loads(proc.stdout.readline())["listening"]


def stop_proxy(proc):
    proc.stdin.close()
    dropped = json.loads(proc.stdout.readline())["dropped"]
    proc.wait(timeout=10)
    return dropped


def driver_version(stack):
    if stack == "async-asyncpg":
        import asyncpg
        return f"asyncpg {asyncpg.__version__}"
    return f"psycopg {psycopg.__version__}"


def run(stack, arm, raw_path):
    assert stack in STACKS and arm in ARMS
    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    observer = Observer()
    proc, proxy_port = start_proxy() if arm == "lost-reply" else (None, None)
    tags = (f"u1-{secrets.token_hex(6)}", f"u2-{secrets.token_hex(6)}")
    ids, loop_errors = ({}, {}), []
    out = {"stack": stack, "arm": arm, "sqlalchemy": sqlalchemy.__version__, "driver": driver_version(stack)}
    capture = Capture()
    for name in ("sqlalchemy", "asyncpg", "psycopg"):
        logging.getLogger(name).addHandler(capture)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        engine = make_engine(stack, proxy_port)
        if stack == "sync-psycopg":
            flow_sync(engine, observer, arm, tags, ids, out)
        else:
            asyncio.run(flow_async(engine, observer, arm, tags, ids, out, loop_errors))
    out["proxy"] = {"used": False} if proc is None else {"used": True, "dropped": stop_proxy(proc)}
    out["unit1_final"] = {"fate": observer.fate(ids[0].get("xid")), "marker_visible": observer.xmin(tags[0]) is not None}
    begin, end = EVENTS.index("--unit 1--"), EVENTS.index("--unit 1 ended--")
    out["unit1_orm_events"] = [e for e in EVENTS[begin:end] if e.startswith("orm.")]
    out["events"] = EVENTS
    out["logged"] = capture.records
    out["warnings"] = [f"{w.category.__name__}: {str(w.message).splitlines()[0][:160]}" for w in caught]
    out["loop_errors"] = loop_errors
    out["validity"] = validity(arm, out)
    print(json.dumps(out, indent=1))
    raw = {"stack": stack, "arm": arm, "sqlalchemy": sqlalchemy.__version__, "started": started,
           "ended": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
           "observer_pid": observer.one("select pg_backend_pid()"), "tags": tags,
           "unit1": ids[0], "unit2": ids[1], "proxy_port": proxy_port}
    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=1)
        f.write("\n")


def versions():
    import asyncpg
    import greenlet
    observer = Observer()
    lib = psycopg.pq.version()
    info = {"python": sys.version.split()[0], "sqlalchemy": sqlalchemy.__version__,
            "psycopg": psycopg.__version__, "psycopg_impl": psycopg.pq.__impl__,
            "libpq": f"{lib // 10000}.{lib % 10000} ({lib})", "asyncpg": asyncpg.__version__,
            "greenlet": greenlet.__version__,
            "node": subprocess.run([NODE, "--version"], capture_output=True, text=True).stdout.strip()}
    for setting in ("server_version", "synchronous_commit", "client_connection_check_interval",
                    "default_transaction_isolation", "log_statement", "idle_in_transaction_session_timeout",
                    "statement_timeout"):
        info[setting] = observer.one(f"show {setting}")
    info["current_user"] = observer.one("select current_user")
    info["rolsuper"] = observer.one("select rolsuper from pg_roles where rolname = current_user")
    info["cluster_name_matches"] = True  # Observer() refuses otherwise
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    try:
        versions() if sys.argv[1:] == ["--versions"] else run(*sys.argv[1:4])
    except BaseException:
        masked = traceback.format_exc().replace(sys.prefix, "<venv>").replace(HERE, "<chk-4>")
        sys.stderr.write(masked.replace(APP_PASSWORD, "<password>"))
        sys.exit(1)
