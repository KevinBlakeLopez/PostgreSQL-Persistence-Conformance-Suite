"""Independent harness for the P5a review: failed commit, then close.

One case per process:  python p5a_review.py <case>
Prints one JSON document. Touches only table p5a_review in database
scratch on 127.0.0.1:55454. The probes record and then call the original
method; they do not change what is sent.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import sys
import threading
import time
import traceback

import psycopg
import sqlalchemy
from psycopg import pq
from psycopg._connection_base import BaseConnection
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

PORT = 55454
DSN = f"postgresql://postgres@127.0.0.1:{PORT}/scratch"
URL = f"postgresql+psycopg://postgres@127.0.0.1:{PORT}/scratch"
TABLE = "p5a_review"
XID_SQL = "select pg_current_xact_id_if_assigned()::text"

T0 = time.monotonic()
TIMELINE: list[dict] = []
IGNORE: set[int] = set()  # id() of witness and helper connections


def note(kind: str, **kw) -> None:
    TIMELINE.append({"t": round(time.monotonic() - T0, 3), "kind": kind, **kw})


def pid_of(raw) -> int | None:
    try:
        return raw.info.backend_pid
    except Exception:
        return None


def status_of(raw) -> str | None:
    if raw is None:
        return None
    try:
        return raw.info.transaction_status.name
    except Exception as e:
        return f"<{type(e).__name__}>"


def sa_caller() -> str:
    frames = traceback.extract_stack()[:-2]
    names = [f.name for f in frames if "/sqlalchemy/" in f.filename]
    return ">".join(names[-7:]) or "<harness>"


def exc_info(e: BaseException) -> dict:
    msg = str(e)
    d = {
        "type": f"{type(e).__module__}.{type(e).__qualname__}",
        "msg": msg.splitlines()[0] if msg else "",
    }
    orig = getattr(e, "orig", None)
    if orig is not None:
        d["orig"] = f"{type(orig).__module__}.{type(orig).__qualname__}"
        d["sqlstate"] = getattr(orig, "sqlstate", None)
    if hasattr(e, "connection_invalidated"):
        d["connection_invalidated"] = e.connection_invalidated
    return d


# ---- pass-through probes --------------------------------------------------

_orig_exec = BaseConnection._exec_command


def _probe_exec(self, command, result_format=pq.Format.TEXT):
    if id(self) not in IGNORE:
        cmd = command.decode() if isinstance(command, bytes) else str(command)
        note("psycopg.send", pid=pid_of(self), cmd=cmd, status_before=status_of(self))
    result = yield from _orig_exec(self, command, result_format)
    return result


BaseConnection._exec_command = _probe_exec


def _wrap_method(name: str) -> None:
    orig = getattr(psycopg.Connection, name)

    def wrapper(self, *a, **k):
        if id(self) in IGNORE:
            return orig(self, *a, **k)
        note(f"dbapi.{name}.call", pid=pid_of(self), status_before=status_of(self), caller=sa_caller())
        try:
            result = orig(self, *a, **k)
        except BaseException as e:
            note(f"dbapi.{name}.raised", exc=exc_info(e), status_after=status_of(self))
            raise
        note(f"dbapi.{name}.returned", status_after=status_of(self))
        return result

    setattr(psycopg.Connection, name, wrapper)


_wrap_method("commit")
_wrap_method("rollback")

# ---- witness (raw psycopg, autocommit, outside SQLAlchemy) ----------------

W = psycopg.connect(DSN, autocommit=True, application_name="p5a-review-witness")
IGNORE.add(id(W))


def activity(pid: int | None) -> dict | None:
    if pid is None:
        return None
    row = W.execute(
        "select state, backend_xid::text, xact_start, left(query, 60)"
        " from pg_stat_activity where pid = %s",
        (pid,),
    ).fetchone()
    if row is None:
        return None
    return {
        "state": row[0],
        "backend_xid": row[1],
        "xact_start": row[2].isoformat() if row[2] else None,
        "query": row[3],
    }


def visible() -> list[str]:
    return [r[0] for r in W.execute(f"select code from {TABLE} order by code")]


def setup() -> None:
    W.execute(f"drop table if exists {TABLE}")
    W.execute(
        f"create table {TABLE} (code text,"
        f" constraint {TABLE}_u unique (code) deferrable initially deferred)"
    )
    W.execute(
        f"create or replace function {TABLE}_slow() returns trigger"
        " language plpgsql as $$ begin perform pg_sleep(3); return null; end $$"
    )
    W.execute(
        f"create constraint trigger {TABLE}_slow after insert on {TABLE}"
        " deferrable initially deferred for each row when (new.code = 'slow')"
        f" execute function {TABLE}_slow()"
    )


def versions() -> dict:
    return {
        "python": sys.version.split()[0],
        "sqlalchemy": sqlalchemy.__version__,
        "sqlalchemy_file": sqlalchemy.__file__,
        "psycopg": psycopg.__version__,
        "psycopg_impl": pq.__impl__,
        "libpq": pq.version(),
        "server": W.execute("show server_version").fetchone()[0],
    }


def make_engine(**kw):
    opts = dict(pool_size=1, max_overflow=0, pool_pre_ping=False, pool_timeout=3)
    opts.update(kw)
    engine = create_engine(URL, **opts)
    event.listen(engine, "commit", lambda c: note("sa.ConnectionEvents.commit"))
    event.listen(engine, "rollback", lambda c: note("sa.ConnectionEvents.rollback"))

    @event.listens_for(engine.pool, "reset")
    def _reset(dbapi_conn, rec, state):
        note(
            "sa.PoolEvents.reset",
            pid=pid_of(dbapi_conn),
            transaction_was_reset=state.transaction_was_reset,
            terminate_only=state.terminate_only,
            psycopg=status_of(dbapi_conn),
        )

    @event.listens_for(engine.pool, "checkout")
    def _checkout(dbapi_conn, rec, proxy):
        note("sa.PoolEvents.checkout", pid=pid_of(dbapi_conn), psycopg=status_of(dbapi_conn))

    @event.listens_for(engine.pool, "checkin")
    def _checkin(dbapi_conn, rec):
        note(
            "sa.PoolEvents.checkin",
            pid=pid_of(dbapi_conn) if dbapi_conn is not None else None,
            psycopg=status_of(dbapi_conn),
        )

    @event.listens_for(engine.pool, "invalidate")
    def _invalidate(dbapi_conn, rec, exc):
        note("sa.PoolEvents.invalidate", pid=pid_of(dbapi_conn), exc=repr(exc))

    return engine


# ---- failures ---------------------------------------------------------------


class Failure:
    engine_kw: dict = {}

    def before(self) -> None:
        pass

    def work(self, execute) -> None:
        pass

    def arm(self, raw, conn: Connection) -> None:
        pass

    @contextlib.contextmanager
    def around_commit(self, raw, pid):
        yield


class NoFailure(Failure):
    pass


class Inject(Failure):
    """Same shape as the draft's fail_commit_once, with a chosen exception."""

    def __init__(self, factory):
        self.factory = factory

    def arm(self, raw, conn):
        original = raw.commit
        factory = self.factory

        def commit():
            raw.commit = original
            exc = factory()
            note("inject.commit_raises_before_send", exc=f"{type(exc).__module__}.{type(exc).__qualname__}")
            raise exc

        raw.commit = commit


class Listener(Failure):
    """A ConnectionEvents.commit listener raises. No DBAPI method is replaced."""

    def arm(self, raw, conn):
        fired: list[bool] = []

        def on_commit(c):
            if not fired:
                fired.append(True)
                note("inject.commit_listener_raises")
                raise RuntimeError("commit listener failed")

        event.listen(conn, "commit", on_commit)


class PsycopgTxnBlock(Failure):
    """Genuine psycopg ProgrammingError: commit() inside psycopg's transaction()."""

    @contextlib.contextmanager
    def around_commit(self, raw, pid):
        with raw.transaction():
            note("psycopg.transaction_block_entered", psycopg=status_of(raw))
            yield


class DeferredUnique(Failure):
    """Server rejects COMMIT: deferred unique constraint."""

    def before(self):
        W.execute(f"insert into {TABLE} (code) values ('dup')")

    def work(self, execute):
        execute(f"insert into {TABLE} (code) values ('dup')")


class Serialization(Failure):
    """Server rejects COMMIT: SERIALIZABLE pivot detected at commit."""

    engine_kw = {"isolation_level": "SERIALIZABLE"}

    def before(self):
        self.other = psycopg.connect(DSN, application_name="p5a-review-other")
        IGNORE.add(id(self.other))
        self.other.isolation_level = psycopg.IsolationLevel.SERIALIZABLE

    def work(self, execute):
        execute(f"select count(*) from {TABLE}")
        self.other.execute(f"select count(*) from {TABLE}")
        self.other.execute(f"insert into {TABLE} (code) values ('other')")
        self.other.commit()
        note("other.committed")


class TerminateIdle(Failure):
    """Backend terminated while idle in transaction, before commit()."""

    def arm(self, raw, conn):
        pid = pid_of(raw)
        W.execute("select pg_terminate_backend(%s)", (pid,))
        for _ in range(200):
            if activity(pid) is None:
                break
            time.sleep(0.02)
        note("server.terminated_before_commit", pid=pid, activity=activity(pid))


class DuringCommit(Failure):
    """COMMIT reaches the server; a deferred trigger sleeps 3 s; then act."""

    def __init__(self, action: str):
        self.action = action

    def work(self, execute):
        execute(f"insert into {TABLE} (code) values ('slow')")

    @contextlib.contextmanager
    def around_commit(self, raw, pid):
        done = threading.Event()
        fn = "pg_cancel_backend" if self.action == "cancel" else "pg_terminate_backend"

        def watch():
            with psycopg.connect(DSN, autocommit=True) as w2:
                IGNORE.add(id(w2))
                while not done.is_set():
                    row = w2.execute(
                        "select state, query from pg_stat_activity where pid = %s", (pid,)
                    ).fetchone()
                    if row and row[0] == "active" and row[1].strip().upper() == "COMMIT":
                        w2.execute(f"select {fn}(%s)", (pid,))
                        note(f"server.{fn}_during_commit", observed_state=row[0], observed_query=row[1])
                        return
                    time.sleep(0.02)

        t = threading.Thread(target=watch, daemon=True)
        t.start()
        try:
            yield
        finally:
            done.set()
            t.join(5)


class RequestTimeout(Exception):
    """A client-side timeout that is an Exception, not an exit exception."""


class AlarmDuringCommit(Failure):
    """COMMIT reaches the server; SIGALRM raises in the client while it waits."""

    def __init__(self, factory):
        self.factory = factory

    def work(self, execute):
        execute(f"insert into {TABLE} (code) values ('slow')")

    @contextlib.contextmanager
    def around_commit(self, raw, pid):
        def handler(signum, frame):
            act = activity(pid)
            exc = self.factory()
            note(
                "client.alarm_raises_during_commit",
                exc=f"{type(exc).__module__}.{type(exc).__qualname__}",
                server_activity=act,
            )
            raise exc

        old = signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, 1.0)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


class ClientClosed(Failure):
    """The DBAPI connection was closed client-side before commit()."""

    def arm(self, raw, conn):
        raw.close()
        note("client.closed_dbapi_connection_before_commit")


FAILURES = {
    "none": NoFailure(),
    "runtime": Inject(lambda: RuntimeError("COMMIT was not sent")),
    "psycopg_operational": Inject(lambda: psycopg.OperationalError("injected: COMMIT was not sent")),
    "psycopg_programming": Inject(lambda: psycopg.ProgrammingError("injected: COMMIT was not sent")),
    "psycopg_disconnect_message": Inject(
        lambda: psycopg.OperationalError(
            "server closed the connection unexpectedly\n"
            "\tThis probably means the server terminated abnormally\n"
            "\tbefore or while processing the request."
        )
    ),
    "keyboard_interrupt": Inject(KeyboardInterrupt),
    "cancelled_error": Inject(asyncio.CancelledError),
    "builtin_timeout_error": Inject(lambda: TimeoutError("timed out")),
    "listener": Listener(),
    "psycopg_txn_block": PsycopgTxnBlock(),
    "deferred_unique": DeferredUnique(),
    "serialization": Serialization(),
    "terminate_idle": TerminateIdle(),
    "cancel_during_commit": DuringCommit("cancel"),
    "terminate_during_commit": DuringCommit("terminate"),
    "client_exception_during_commit": AlarmDuringCommit(lambda: RequestTimeout("request timeout")),
    "keyboard_interrupt_during_commit": AlarmDuringCommit(KeyboardInterrupt),
    "client_closed": ClientClosed(),
}


# ---- first unit of work, by API path --------------------------------------


def describe(conn: Connection, raw, pid) -> dict:
    marker = None if conn.closed else conn.get_transaction()
    return {
        "in_transaction": None if conn.closed else conn.in_transaction(),
        "marker_present": marker is not None,
        "marker_active": None if marker is None else marker.is_active,
        "connection_invalidated": conn.invalidated,
        "psycopg": status_of(raw),
        "activity": activity(pid),
    }


def observe_close(engine, conn, raw, pid, out, key="close") -> None:
    mark = len(TIMELINE)
    try:
        conn.close()
        out[key] = "returned"
    except BaseException as e:
        out[key] = exc_info(e)
    out[f"after_{key}"] = {
        "psycopg": status_of(raw),
        "activity": activity(pid),
        "pool_checkedout": engine.pool.checkedout(),
    }
    out[f"events_during_{key}"] = TIMELINE[mark:]


def first_unit(api: str, fail: Failure, engine) -> tuple:
    out: dict = {}
    doomed = f"insert into {TABLE} (code) values ('doomed')"
    mark = len(TIMELINE)
    fail.before()

    def capture(conn, raw):
        pid = pid_of(raw)
        out["pid"] = pid
        out["xid"] = conn.execute(text(XID_SQL)).scalar()
        out["activity_before_commit"] = activity(pid)
        return pid

    def try_commit(call, raw, pid):
        t = time.monotonic()
        mark = len(TIMELINE)
        try:
            with fail.around_commit(raw, pid):
                call()
            out["commit"] = "returned"
        except BaseException as e:
            out["commit"] = exc_info(e)
        out["commit_seconds"] = round(time.monotonic() - t, 3)
        out["events_during_commit"] = TIMELINE[mark:]

    if api in ("explicit", "rollback_close", "rollback_reuse"):
        conn = engine.connect()
        trans = conn.begin()
        conn.execute(text(doomed))
        fail.work(lambda s: conn.execute(text(s)))
        raw = conn.connection.driver_connection
        pid = capture(conn, raw)
        fail.arm(raw, conn)
        try_commit(trans.commit, raw, pid)
        out["after_commit"] = describe(conn, raw, pid)
        if api in ("rollback_close", "rollback_reuse"):
            mark = len(TIMELINE)
            try:
                conn.rollback()
                out["rollback"] = "returned"
            except BaseException as e:
                out["rollback"] = exc_info(e)
            out["events_during_rollback"] = TIMELINE[mark:]
            out["after_rollback"] = describe(conn, raw, pid)
        if api == "rollback_reuse":
            try:
                out["reuse_xid_before_insert"] = conn.execute(text(XID_SQL)).scalar()
                conn.execute(text(f"insert into {TABLE} (code) values ('same-connection')"))
                conn.commit()
                out["reuse_commit"] = "returned"
            except BaseException as e:
                out["reuse_commit"] = exc_info(e)
            out["visible_after_reuse"] = visible()
        observe_close(engine, conn, raw, pid, out)

    elif api == "connect_ctx":
        raw = pid = None
        try:
            with engine.connect() as conn:
                conn.execute(text(doomed))
                fail.work(lambda s: conn.execute(text(s)))
                raw = conn.connection.driver_connection
                pid = capture(conn, raw)
                fail.arm(raw, conn)
                mark = len(TIMELINE)
                conn.commit()
        except BaseException as e:
            out["commit"] = exc_info(e)
            out["events_during_commit_and_exit"] = TIMELINE[mark:]
        out["after_with_exit"] = {
            "connection_closed": conn.closed,
            "psycopg": status_of(raw),
            "activity": activity(pid),
            "pool_checkedout": engine.pool.checkedout(),
        }

    elif api == "engine_begin":
        raw = pid = None
        try:
            with engine.begin() as conn:
                conn.execute(text(doomed))
                fail.work(lambda s: conn.execute(text(s)))
                raw = conn.connection.driver_connection
                pid = capture(conn, raw)
                fail.arm(raw, conn)
                mark = len(TIMELINE)
        except BaseException as e:
            out["commit"] = exc_info(e)
            out["events_during_commit_and_exit"] = TIMELINE[mark:]
        out["after_with_exit"] = {
            "psycopg": status_of(raw),
            "activity": activity(pid),
            "pool_checkedout": engine.pool.checkedout(),
        }

    elif api in ("orm_commit", "orm_begin"):
        raw = pid = None
        try:
            with Session(engine) as s:
                if api == "orm_commit":
                    s.execute(text(doomed))
                    conn = s.connection()
                    raw = conn.connection.driver_connection
                    pid = capture(conn, raw)
                    fail.arm(raw, conn)
                    mark = len(TIMELINE)
                    s.commit()
                else:
                    with s.begin():
                        s.execute(text(doomed))
                        conn = s.connection()
                        raw = conn.connection.driver_connection
                        pid = capture(conn, raw)
                        fail.arm(raw, conn)
                        mark = len(TIMELINE)
        except BaseException as e:
            out["commit"] = exc_info(e)
            out["events_during_commit_and_exit"] = TIMELINE[mark:]
        out["after_with_exit"] = {
            "psycopg": status_of(raw),
            "activity": activity(pid),
            "pool_checkedout": engine.pool.checkedout(),
        }

    elif api == "orm_rollback_close":
        s = Session(engine)
        s.execute(text(doomed))
        conn = s.connection()
        raw = conn.connection.driver_connection
        pid = capture(conn, raw)
        fail.arm(raw, conn)
        try:
            s.commit()
            out["commit"] = "returned"
        except BaseException as e:
            out["commit"] = exc_info(e)
        out["after_commit"] = {"psycopg": status_of(raw), "activity": activity(pid)}
        mark = len(TIMELINE)
        try:
            s.rollback()
            out["rollback"] = "returned"
        except BaseException as e:
            out["rollback"] = exc_info(e)
        out["after_rollback"] = {"psycopg": status_of(raw), "activity": activity(pid)}
        s.close()
        out["after_close"] = {
            "psycopg": status_of(raw),
            "activity": activity(pid),
            "pool_checkedout": engine.pool.checkedout(),
        }
        out["events_during_rollback_and_close"] = TIMELINE[mark:]

    else:
        raise SystemExit(f"unknown api {api}")

    return raw, pid, out.get("xid"), out


def second_checkout(engine, raw1, pid1, xid1) -> dict:
    rec: dict = {}
    mark = len(TIMELINE)
    try:
        conn2 = engine.connect()
    except BaseException as e:
        rec["checkout"] = exc_info(e)
        return rec
    raw2 = conn2.connection.driver_connection
    pid2 = pid_of(raw2)
    rec.update(
        same_dbapi_object=raw2 is raw1,
        pid=pid2,
        same_pid=pid2 == pid1,
        in_transaction=conn2.in_transaction(),
        psycopg=status_of(raw2),
        activity=activity(pid2),
    )
    try:
        trans2 = conn2.begin()
        seen = conn2.execute(text(XID_SQL)).scalar()
        rec["xid_seen_before_insert"] = seen
        rec["same_xid_as_first"] = xid1 is not None and seen == xid1
        conn2.execute(text(f"insert into {TABLE} (code) values ('next')"))
        trans2.commit()
        rec["next_commit"] = "returned"
    except BaseException as e:
        rec["next_commit"] = exc_info(e)
    rec["visible_after_next"] = visible()
    try:
        conn2.close()
        rec["close2"] = "returned"
    except BaseException as e:
        rec["close2"] = exc_info(e)
    rec["events"] = TIMELINE[mark:]
    return rec


CASES = {
    # control and the draft's case 1, explicit Transaction.commit() then close()
    "explicit-none": ("explicit", "none", {}),
    "explicit-runtime": ("explicit", "runtime", {}),
    "explicit-runtime-preping": ("explicit", "runtime", {"pool_pre_ping": True}),
    # exception type, same injection point
    "explicit-psycopg_operational": ("explicit", "psycopg_operational", {}),
    "explicit-psycopg_programming": ("explicit", "psycopg_programming", {}),
    "explicit-psycopg_disconnect_message": ("explicit", "psycopg_disconnect_message", {}),
    "explicit-keyboard_interrupt": ("explicit", "keyboard_interrupt", {}),
    "explicit-cancelled_error": ("explicit", "cancelled_error", {}),
    "explicit-builtin_timeout_error": ("explicit", "builtin_timeout_error", {}),
    # no DBAPI method replaced
    "explicit-listener": ("explicit", "listener", {}),
    "explicit-psycopg_txn_block": ("explicit", "psycopg_txn_block", {}),
    # real failures, no injection
    "explicit-deferred_unique": ("explicit", "deferred_unique", {}),
    "explicit-serialization": ("explicit", "serialization", {}),
    "explicit-terminate_idle": ("explicit", "terminate_idle", {}),
    "explicit-cancel_during_commit": ("explicit", "cancel_during_commit", {}),
    "explicit-terminate_during_commit": ("explicit", "terminate_during_commit", {}),
    "explicit-client_exception_during_commit": ("explicit", "client_exception_during_commit", {}),
    "explicit-keyboard_interrupt_during_commit": ("explicit", "keyboard_interrupt_during_commit", {}),
    "explicit-client_closed": ("explicit", "client_closed", {}),
    # API paths, draft's injection
    "connect_ctx-runtime": ("connect_ctx", "runtime", {}),
    "engine_begin-runtime": ("engine_begin", "runtime", {}),
    "rollback_close-runtime": ("rollback_close", "runtime", {}),
    "rollback_reuse-runtime": ("rollback_reuse", "runtime", {}),
    "orm_commit-runtime": ("orm_commit", "runtime", {}),
    "orm_begin-runtime": ("orm_begin", "runtime", {}),
    "orm_rollback_close-runtime": ("orm_rollback_close", "runtime", {}),
    # API paths, no injection (listener only) to confirm path independence
    "connect_ctx-listener": ("connect_ctx", "listener", {}),
    "orm_commit-listener": ("orm_commit", "listener", {}),
}


def main() -> None:
    name = sys.argv[1]
    api, failname, extra_kw = CASES[name]
    fail = FAILURES[failname]
    setup()
    engine_kw = {**fail.engine_kw, **extra_kw}
    engine = make_engine(**engine_kw)
    result: dict = {"case": name, "api": api, "failure": failname, "engine_kw": engine_kw, "versions": versions()}
    raw, pid, xid, first = first_unit(api, fail, engine)
    result["first"] = first
    result["visible_after_first_unit"] = visible()
    result["activity_first_pid_after_first_unit"] = activity(pid)
    result["second_checkout"] = second_checkout(engine, raw, pid, xid)
    engine.dispose()
    result["visible_final"] = visible()
    result["timeline"] = TIMELINE
    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
