# PPCS adapter for SQLAlchemy 2.1 Core. Speaks protocol version 1 on stdin/stdout.
# node-kit is not imported. The ORM Session adapter is not imported.
#
# The transaction under test is Connection.begin() / Connection.begin_nested().
# There is no Session, no unit of work, and no flush.
#
# Category C faults are injected in this process, once, before Core sees the
# error. ROLLBACK TO SAVEPOINT reaches before_cursor_execute:
# DefaultDialect.do_rollback_to_savepoint executes the clause (default.py).
# A top-level ROLLBACK does not. DefaultDialect.do_rollback calls
# dbapi_connection.rollback(). That withhold is on psycopg.Connection.rollback,
# before send. The cursor hook does not also match it. Commit is traced, not
# altered: psycopg.Connection.commit waits until COMMIT finishes, so this
# adapter does not implement the node-postgres reply-lost simulation.

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "production-reachability" / "py"))
from pr01 import run_pr  # noqa: E402
import re
import sys
import threading
import time
from typing import Any, Callable

import psycopg
import sqlalchemy
from psycopg.pq import TransactionStatus
from sqlalchemy import Column, Integer, MetaData, Table, Text, event, insert, select, text
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import IntegrityError

PROTOCOL = 1
ROLLBACK_TO = re.compile(r"^rollback to (savepoint )?", re.IGNORECASE)
_STATUS = {value: name for name, value in TransactionStatus.__members__.items()}

# Connection.begin() returns a RootTransaction. As a context manager,
# TransactionalContext.__exit__ (sqlalchemy/engine/util.py, 2.1.5) commits
# when the block exits without an exception and the transaction is still
# active, and rolls back when the block exits with one. If commit() raises,
# that method calls rollback() when it can and propagates the error from
# that exit. Connection.begin_nested() returns a NestedTransaction: commit
# releases the savepoint and rollback executes ROLLBACK TO SAVEPOINT
# (sqlalchemy/engine/base.py). A failure of that rollback propagates.
CONTRACT = (
    "Connection.begin() as a context manager commits when the block exits without "
    "an exception and the transaction is still active, and rolls back when the block "
    "exits with one. Connection.begin_nested() is a SAVEPOINT; an exception there "
    "rolls back to the savepoint, and a failure of that rollback propagates. "
    "If commit() raises on the way out, TransactionalContext.__exit__ calls "
    "rollback() when it can and propagates the error from that exit."
)

# Connection.begin() also returns a handle the application commits itself.
# Transaction.commit() and Transaction.rollback() are the explicit boundary
# (sqlalchemy/engine/base.py, 2.1.5).
EXPLICIT_CONTRACT = (
    "Connection.begin() returns a RootTransaction. Transaction.commit() commits it "
    "and Transaction.rollback() rolls it back. A commit that returns is a reported "
    "commit. A commit that raises asserts neither outcome."
)

# Documented PostgreSQL isolation API: Connection.execution_options(isolation_level=...)
# before begin(). sqlalchemy/dialects/postgresql/base.py, "Transaction Isolation Level".
# The psycopg dialect assigns the DBAPI isolation level so the next BEGIN carries it
# (sqlalchemy/dialects/postgresql/psycopg.py, set_isolation_level).
ISOLATION_CONTRACT = (
    CONTRACT
    + " The isolation level is Connection.execution_options(isolation_level=...), "
    "set before begin(). PostgreSQL accepts SERIALIZABLE there."
)
EXPLICIT_ISOLATION_CONTRACT = (
    EXPLICIT_CONTRACT
    + " The isolation level is Connection.execution_options(isolation_level=...), "
    "set before begin(). PostgreSQL accepts SERIALIZABLE there."
)

# Case settings use PostgreSQL's names. Core's documented values are the
# uppercase spellings in the PostgreSQL dialect.
SA_LEVELS = {
    "read uncommitted": "READ UNCOMMITTED",
    "read committed": "READ COMMITTED",
    "repeatable read": "REPEATABLE READ",
    "serializable": "SERIALIZABLE",
}

TX04_FORM = (
    "Outer Connection.begin() and Connection.begin_nested(). begin_nested() is the "
    "documented SAVEPOINT, not an independent transaction. insert() sends the outer "
    "row before the savepoint, because Core has no unit of work."
)
TX05_MANAGED_FORM = (
    "Connection.execution_options(isolation_level=...) then Connection.begin() as a "
    "context manager. The marker is inserted with insert() and read back with select()."
)
TX05_EXPLICIT_FORM = (
    "Connection.execution_options(isolation_level=...) then Connection.begin(), "
    "which returns a RootTransaction committed with Transaction.commit(). "
    "The marker is inserted with insert() and read back with select()."
)

METADATA = MetaData()
ITEM = Table(
    "item",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("qty", Integer, nullable=False),
)
UNIQ = Table(
    "uniq",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("code", Text, nullable=False),
)

INSTRUMENTATION = (
    "ROLLBACK TO SAVEPOINT is withheld or rewritten in before_cursor_execute, "
    "before psycopg sends it. A top-level ROLLBACK is withheld on "
    "psycopg.Connection.rollback, because DefaultDialect.do_rollback calls "
    "dbapi_connection.rollback() and does not pass the cursor event. "
    "psycopg.Connection.commit is traced and not altered."
)


class ProtocolError(Exception):
    pass


class AppError(Exception):
    pass


class Fault:
    def __init__(self) -> None:
        self.kind: str | None = None
        self.mode_name: str | None = None
        self.armed = False
        self.fired = 0
        self.pid: int | None = None
        self.trace: list[str] = []
        self.withheld: list[str] = []
        self.rewritten: list[str] = []
        self.reply_codes: list[str] = []
        self.awaiting_reply = False
        self.abandoned = False
        self.commit_calls = 0
        self.rollback_calls = 0


current_fault: Fault | None = None
_patched = False


def send(msg: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"ppcs": PROTOCOL, **msg}) + "\n")
    sys.stdout.flush()


def read_message() -> dict[str, Any]:
    while True:
        line = sys.stdin.readline()
        if line == "":
            raise ProtocolError("the runner closed the protocol stream")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict) and msg.get("ppcs") == PROTOCOL:
            return msg


def checkpoint(name: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if current_fault is not None and current_fault.abandoned:
        raise ProtocolError(f'checkpoint "{name}" after the unit was abandoned')
    body: dict[str, Any] = {"type": "checkpoint", "name": name}
    if data:
        body.update(data)
    send(body)
    msg = read_message()
    if msg.get("type") != "resume" or msg.get("name") != name:
        raise ProtocolError(
            f'expected resume for checkpoint "{name}", got {json.dumps(msg)}'
        )
    return msg


def walk_exceptions(exc: BaseException | None):
    seen: set[int] = set()
    stack: list[BaseException] = []
    if exc is not None:
        stack.append(exc)
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        yield cur
        orig = getattr(cur, "orig", None)
        if isinstance(orig, BaseException) and orig is not cur:
            stack.append(orig)
        if cur.__cause__ is not None and cur.__cause__ is not cur:
            stack.append(cur.__cause__)
        if cur.__context__ is not None and cur.__context__ is not cur.__cause__:
            stack.append(cur.__context__)


def sqlstate(exc: BaseException | None) -> str | None:
    """SQLSTATE of this error, or of the DBAPI error it wraps.

    __context__ is not followed. A later error chained there is a different
    failure, and its SQLSTATE does not belong to this one.
    """
    seen: set[int] = set()
    stack: list[BaseException] = []
    if exc is not None:
        stack.append(exc)
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        state = getattr(cur, "sqlstate", None) or getattr(cur, "pgcode", None)
        if isinstance(state, str) and state:
            return state
        orig = getattr(cur, "orig", None)
        if isinstance(orig, BaseException) and orig is not cur:
            stack.append(orig)
        if cur.__cause__ is not None and cur.__cause__ is not cur:
            stack.append(cur.__cause__)
    return None


def raise_if_protocol(exc: BaseException) -> None:
    for cur in walk_exceptions(exc):
        if isinstance(cur, ProtocolError):
            raise cur


def err_info(exc: BaseException) -> dict[str, Any]:
    return {
        "class": type(exc).__name__,
        "code": sqlstate(exc),
        "message": " ".join(str(exc).split())[:500],
    }


def integrity_error(exc: BaseException) -> BaseException | None:
    for cur in walk_exceptions(exc):
        state = getattr(cur, "sqlstate", None) or getattr(cur, "pgcode", None)
        if isinstance(cur, IntegrityError) or state == "23505":
            return cur
    return None


def fault_report(fault: Fault) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": fault.mode_name,
        "fired": fault.fired,
        "withheld": list(fault.withheld),
    }
    if fault.rewritten:
        report["rewritten"] = list(fault.rewritten)
    if fault.reply_codes:
        report["reply_codes"] = list(fault.reply_codes)
    return report


def install_fault(engine: Engine, fault: Fault) -> None:
    global _patched

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def _before(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> tuple[Any, Any]:
        sql = " ".join(str(statement).split())
        if fault.kind == "savepoint" and fault.armed and ROLLBACK_TO.match(sql):
            fault.armed = False
            fault.fired += 1
            if fault.mode_name == "client-reject":
                fault.withheld.append(sql)
                fault.trace.append(f"{sql}  -- WITHHELD before send")
                checkpoint("after-fault", {"pid": fault.pid})
                raise RuntimeError(
                    "injected client-side failure: ROLLBACK TO SAVEPOINT was not sent"
                )
            rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint"
            fault.withheld.append(sql)
            fault.rewritten.append(rewritten)
            fault.trace.append(f"{rewritten}  -- REWRITE of: {sql}")
            fault.awaiting_reply = True
            return rewritten, parameters
        fault.trace.append(sql)
        return statement, parameters

    @event.listens_for(engine, "handle_error")
    def _on_error(context: Any) -> None:
        # After PostgreSQL has answered the rewritten ROLLBACK TO SAVEPOINT,
        # and before that error returns to Connection.begin_nested().
        if not fault.awaiting_reply:
            return None
        fault.awaiting_reply = False
        fault.reply_codes.append(sqlstate(context.original_exception) or "error")
        checkpoint("after-fault", {"pid": fault.pid})
        return None

    if _patched:
        return
    original_rollback = psycopg.Connection.rollback
    original_commit = psycopg.Connection.commit

    def patched_rollback(self: Any) -> None:
        fault.rollback_calls += 1
        if fault.kind == "root" and fault.armed:
            fault.armed = False
            fault.fired += 1
            fault.withheld.append("ROLLBACK")
            status = _STATUS.get(self.info.transaction_status, str(self.info.transaction_status))
            fault.trace.append(f"ROLLBACK  -- WITHHELD before send ({status})")
            checkpoint("after-fault", {"pid": fault.pid})
            raise RuntimeError("injected client-side failure: ROLLBACK was not sent")
        status = _STATUS.get(self.info.transaction_status, str(self.info.transaction_status))
        fault.trace.append(f"ROLLBACK ({status})")
        return original_rollback(self)

    def patched_commit(self: Any) -> None:
        fault.commit_calls += 1
        before = _STATUS.get(self.info.transaction_status, str(self.info.transaction_status))
        try:
            return original_commit(self)
        finally:
            after = _STATUS.get(self.info.transaction_status, str(self.info.transaction_status))
            fault.trace.append(f"COMMIT ({before} -> {after})")

    psycopg.Connection.rollback = patched_rollback  # type: ignore[method-assign]
    psycopg.Connection.commit = patched_commit  # type: ignore[method-assign]
    _patched = True


def open_engine(connection: dict[str, Any], pool_max: int) -> Engine:
    url = URL.create(
        "postgresql+psycopg",
        username=connection["user"],
        password=connection["password"],
        host=connection["host"],
        port=int(connection["port"]),
        database=connection["database"],
    )
    return sqlalchemy.create_engine(
        url,
        pool_size=pool_max,
        max_overflow=0,
        pool_pre_ping=False,
        connect_args={"application_name": connection["application_name"]},
    )


def identify(conn: Connection, *, isolation: bool = False) -> dict[str, Any]:
    sql = (
        "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, "
        "current_setting('transaction_isolation') as transaction_isolation"
        if isolation
        else "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid"
    )
    row = conn.execute(text(sql)).mappings().one()
    out: dict[str, Any] = {"xid": row["xid"], "pid": int(row["pid"])}
    if isolation:
        out["transaction_isolation"] = row["transaction_isolation"]
    return out


def write_marker(conn: Connection, name: str) -> None:
    conn.execute(insert(ITEM).values(name=name, qty=0))


def read_marker(conn: Connection, name: str) -> None:
    got = conn.execute(select(ITEM.c.name).where(ITEM.c.name == name)).scalar_one()
    if got != name:
        raise RuntimeError("the marker read did not return the written value")


def sleep_ms(settings: dict[str, Any]) -> None:
    time.sleep((settings.get("settle_ms") or 100) / 1000)


def sa_level(settings: dict[str, Any]) -> str:
    requested = settings.get("isolation_level")
    level = SA_LEVELS.get(requested) if isinstance(requested, str) else None
    if level is None:
        raise ProtocolError(
            f"the case requests an unknown isolation level: {json.dumps(requested)}"
        )
    return level


def map_begin_exit(thrown: BaseException | None, escaped: BaseException | None) -> dict[str, Any]:
    """Map Connection.begin()'s exit. A clean exit is committed. The block's own
    exception is rolled back. Any other error from ending the transaction is failed.
    """
    if escaped is None:
        return {
            "reported": "committed",
            "basis": "Connection.begin() exited without an exception, so it committed",
            "contract": CONTRACT,
        }
    raise_if_protocol(escaped)
    # Identity, not __context__. An error raised while __exit__ ends the
    # transaction is chained as __context__ and is not the block's exception.
    same = thrown is not None and escaped is thrown
    return {
        "reported": "rolled_back" if same else "failed",
        "basis": (
            "Connection.begin() exited with the exception raised inside it, so it rolled back"
            if same
            else "Connection.begin() exited with an error the block did not raise"
        ),
        "contract": CONTRACT,
        "api_error": err_info(thrown if same and thrown is not None else escaped),
    }


def run_begin(engine: Engine, body: Callable[[Connection], None]) -> dict[str, Any]:
    """Run body inside Connection.begin(). Map the context manager's exit.

    The connection returns to the pool when this function returns. That is
    Engine.connect()'s context manager, the ordinary end of a checkout.
    """
    thrown: BaseException | None = None
    with engine.connect() as conn:
        try:
            with conn.begin():
                try:
                    body(conn)
                except Exception as exc:
                    raise_if_protocol(exc)
                    thrown = exc
                    raise
            return map_begin_exit(None, None)
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            return map_begin_exit(thrown, exc)


def case_commit(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(conn: Connection) -> None:
        write_marker(conn, message["markers"]["tx"])
        checkpoint("before-end", identify(conn))

    return run_begin(engine, body)


def case_rollback(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(conn: Connection) -> None:
        write_marker(conn, message["markers"]["tx"])
        checkpoint("before-end", identify(conn))
        raise AppError("application error: the request fails")

    return run_begin(engine, body)


def case_caught_error(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    violation: dict[str, BaseException | None] = {"exc": None}

    def body(conn: Connection) -> None:
        write_marker(conn, message["markers"]["tx"])
        ident = identify(conn)
        checkpoint("after-write", ident)
        try:
            conn.execute(insert(UNIQ).values(code="taken"))
        except IntegrityError as exc:
            violation["exc"] = exc
        # Nothing else is sent. The block then returns, so begin() commits.
        checkpoint("before-end", {"pid": ident["pid"]})

    outcome = run_begin(engine, body)
    found = violation["exc"]
    if found is None:
        raise RuntimeError("the duplicate insert did not raise IntegrityError")
    outcome["steps"] = {"violation": err_info(found)}
    return outcome


def case_conn_lost_before_commit(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(conn: Connection) -> None:
        write_marker(conn, message["markers"]["tx"])
        checkpoint("before-end", identify(conn))
        sleep_ms(message["case"].get("settings") or {})

    return run_begin(engine, body)


def case_savepoint(engine: Engine, message: dict[str, Any], fault: Fault, kind: str) -> dict[str, Any]:
    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False}
    pid: int | None = None
    escaped: BaseException | None = None
    conn = engine.connect()
    try:
        try:
            with conn.begin():
                write_marker(conn, markers["outer"])
                ident = identify(conn)
                pid = ident["pid"]
                fault.pid = pid
                checkpoint("outer-after-write", ident)
                try:
                    with conn.begin_nested():
                        write_marker(conn, markers["inner"])
                        checkpoint("inner-after-write", {"pid": pid})
                        if kind == "conn-lost":
                            sleep_ms(message["case"].get("settings") or {})
                        elif kind == "not-sent":
                            fault.kind = "savepoint"
                            fault.mode_name = "client-reject"
                            fault.armed = True
                        else:
                            fault.kind = "savepoint"
                            fault.mode_name = "rewrite"
                            fault.armed = True
                        raise AppError("application error: the nested scope fails")
                except ProtocolError:
                    raise
                except Exception as exc:
                    raise_if_protocol(exc)
                    nested["caught"] = True
                    nested["error"] = err_info(exc)
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            escaped = exc
        # Disarm before the connection returns to the pool, so a pool reset
        # is not the fault the case armed for the savepoint rollback.
        fault.armed = False
        checkpoint("after-outer", {"pid": pid})
        outcome = map_begin_exit(None, escaped)
        steps: dict[str, Any] = {"nested": nested}
        if kind != "conn-lost":
            steps["fault"] = fault_report(fault)
        outcome["steps"] = steps
        return outcome
    finally:
        conn.close()


def case_reuse(engine: Engine, message: dict[str, Any], fault: Fault, kind: str) -> dict[str, Any]:
    markers = message["markers"]
    settings = message["case"].get("settings") or {}
    violation: dict[str, BaseException | None] = {"exc": None}
    pids: dict[str, int | None] = {"unit1": None, "unit2": None}

    def unit1(conn: Connection) -> None:
        write_marker(conn, markers["doomed"])
        ident = identify(conn)
        pids["unit1"] = ident["pid"]
        fault.pid = ident["pid"]
        checkpoint("unit1-after-write", ident)
        if kind == "conn-lost":
            sleep_ms(settings)
        else:
            fault.kind = "root"
            fault.mode_name = "client-reject"
            fault.armed = True
        if kind == "statement-error":
            try:
                conn.execute(insert(UNIQ).values(code="taken"))
            except ProtocolError:
                raise
            except Exception as exc:
                raise_if_protocol(exc)
                found = integrity_error(exc)
                if found is not None:
                    violation["exc"] = found
                raise
        raise AppError("application error: unit 1 fails")

    outcome = run_begin(engine, unit1)
    fault.armed = False
    fault.kind = None
    checkpoint("after-unit1", {"pid": pids["unit1"]})

    def unit2() -> dict[str, Any]:
        def body(conn: Connection) -> None:
            write_marker(conn, markers["next"])
            ident = identify(conn)
            pids["unit2"] = ident["pid"]
            checkpoint("unit2-after-write", ident)

        return run_begin(engine, body)

    started = time.monotonic()
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = unit2()
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    bound_ms = settings.get("bound_ms") or 5000
    thread.join(bound_ms / 1000)
    if thread.is_alive():
        fault.abandoned = True
        unit2_outcome: dict[str, Any] = {"outcome": "pending", "elapsed_ms": bound_ms}
    elif "error" in box:
        raise box["error"]
    else:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        unit2_outcome = {"outcome": "completed", "elapsed_ms": elapsed_ms, **box["value"]}
    steps: dict[str, Any] = {
        "unit2": unit2_outcome,
        "reuse": {
            "unit1_pid": pids["unit1"],
            "unit2_pid": pids["unit2"],
            "same_backend": pids["unit1"] is not None and pids["unit2"] == pids["unit1"],
        },
    }
    found = violation["exc"]
    if found is not None:
        steps["violation"] = err_info(found)
    if kind != "conn-lost":
        steps["fault"] = fault_report(fault)
    outcome["steps"] = steps
    return outcome


def case_nested(engine: Engine, message: dict[str, Any], fault: Fault, variant: str) -> dict[str, Any]:
    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False, "completed": False}

    def body(conn: Connection) -> None:
        write_marker(conn, markers["outer"])
        try:
            with conn.begin_nested():
                write_marker(conn, markers["inner"])
                checkpoint("inner-after-write", identify(conn))
                if variant == "nested-fails":
                    raise AppError("application error: the nested scope fails")
            nested["completed"] = True
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            nested["caught"] = True
            nested["error"] = err_info(exc)
        if variant == "outer-fails":
            raise AppError("application error: the outer scope fails")

    outcome = run_begin(engine, body)
    outcome["steps"] = {"nested": nested}
    outcome["form"] = TX04_FORM
    return outcome


def level_work(conn: Connection, message: dict[str, Any], checkpoint_name: str, *, with_isolation: bool) -> None:
    marker = message["markers"]["tx"]
    write_marker(conn, marker)
    read_marker(conn, marker)
    checkpoint(checkpoint_name, identify(conn, isolation=with_isolation))


def case_managed_serializable(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    settings = message["case"].get("settings") or {}
    level = sa_level(settings)
    state = {"started": False}

    def attempt() -> dict[str, Any]:
        thrown: BaseException | None = None
        with engine.connect() as conn:
            try:
                conn.execution_options(isolation_level=level)
            except Exception as exc:
                raise_if_protocol(exc)
                return {
                    "reported": "failed",
                    "basis": "Connection.execution_options(isolation_level=...) raised before the transaction started",
                    "contract": ISOLATION_CONTRACT,
                    "api_error": err_info(exc),
                }
            try:
                with conn.begin():
                    state["started"] = True
                    try:
                        level_work(conn, message, "after-read", with_isolation=True)
                    except Exception as exc:
                        raise_if_protocol(exc)
                        thrown = exc
                        raise
                outcome = map_begin_exit(None, None)
            except ProtocolError:
                raise
            except Exception as exc:
                raise_if_protocol(exc)
                outcome = map_begin_exit(thrown, exc)
        outcome["contract"] = ISOLATION_CONTRACT
        return outcome

    def plain() -> None:
        with engine.connect() as conn:
            with conn.begin():
                checkpoint("baseline", identify(conn))

    return _requested_level(attempt, plain, state, TX05_MANAGED_FORM)


def case_explicit_serializable(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    settings = message["case"].get("settings") or {}
    level = sa_level(settings)
    state = {"started": False}

    def attempt() -> dict[str, Any]:
        conn = engine.connect()
        trans = None
        try:
            try:
                conn.execution_options(isolation_level=level)
            except Exception as exc:
                raise_if_protocol(exc)
                return {
                    "reported": "failed",
                    "basis": "Connection.execution_options(isolation_level=...) raised before the transaction started",
                    "contract": EXPLICIT_ISOLATION_CONTRACT,
                    "api_error": err_info(exc),
                }
            try:
                trans = conn.begin()
            except Exception as exc:
                raise_if_protocol(exc)
                return {
                    "reported": "failed",
                    "basis": "Connection.begin() raised before it returned a transaction",
                    "contract": EXPLICIT_ISOLATION_CONTRACT,
                    "api_error": err_info(exc),
                }
            state["started"] = True
            try:
                level_work(conn, message, "after-read", with_isolation=True)
            except Exception as exc:
                raise_if_protocol(exc)
                try:
                    trans.rollback()
                except Exception:
                    pass
                raise
            try:
                trans.commit()
            except Exception as exc:
                raise_if_protocol(exc)
                return {
                    "reported": "failed",
                    "basis": "Transaction.commit() raised",
                    "contract": EXPLICIT_ISOLATION_CONTRACT,
                    "api_error": err_info(exc),
                }
            return {
                "reported": "committed",
                "basis": "Transaction.commit() returned",
                "contract": EXPLICIT_ISOLATION_CONTRACT,
            }
        finally:
            conn.close()

    def plain() -> None:
        conn = engine.connect()
        try:
            trans = conn.begin()
            checkpoint("baseline", identify(conn))
            trans.commit()
        finally:
            conn.close()

    return _requested_level(attempt, plain, state, TX05_EXPLICIT_FORM)


def _requested_level(
    attempt: Callable[[], dict[str, Any]],
    plain: Callable[[], None],
    state: dict[str, bool],
    form: str,
) -> dict[str, Any]:
    outcome = attempt()
    outcome["form"] = form
    if state["started"] or outcome.get("reported") != "failed":
        return outcome
    try:
        plain()
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        outcome["steps"] = {**(outcome.get("steps") or {}), "baseline": {"error": err_info(exc)}}
    return outcome


EXPLICIT_CONTRACT = (
    "Connection.begin() returns a RootTransaction. Transaction.commit() commits it "
    "and Transaction.rollback() rolls it back (sqlalchemy/engine/base.py). "
    "A returned commit() is Core's report that the transaction committed. "
    "psycopg Connection.commit executes COMMIT and does not read the command tag."
)


def _is_protocol(exc: BaseException) -> bool:
    try:
        raise_if_protocol(exc)
    except ProtocolError:
        return True
    return False


def _listen_connection(conn: Connection, hooks: dict[str, int]) -> None:
    event.listen(conn, "commit", lambda _c: hooks.__setitem__("commit", hooks["commit"] + 1))
    event.listen(conn, "rollback", lambda _c: hooks.__setitem__("rollback", hooks["rollback"] + 1))


def _core_pr(kind: str, engine: Engine, message: dict[str, Any]) -> dict[str, Any]:
    hooks = {"commit": 0, "rollback": 0}
    seen: dict[str, int] = {}

    def insert_taken(conn: Connection) -> None:
        conn.execute(insert(UNIQ).values(code="taken"))

    def savepoint(conn: Connection) -> dict[str, Any]:
        try:
            with conn.begin_nested():
                insert_taken(conn)
        except IntegrityError as exc:
            return {"recovered": True, "violation": err_info(exc)}
        raise RuntimeError("the duplicate insert did not raise")

    def managed(work: Callable[[Connection], None]) -> dict[str, Any]:
        conn = engine.connect()
        _listen_connection(conn, hooks)
        thrown: BaseException | None = None
        try:
            with conn.begin():
                try:
                    work(conn)
                except Exception as exc:
                    raise_if_protocol(exc)
                    thrown = exc
                    raise
            return map_begin_exit(None, None)
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            return map_begin_exit(thrown, exc)
        finally:
            seen.update(hooks)
            conn.close()

    def explicit(work: Callable[[Connection], None]) -> dict[str, Any]:
        conn = engine.connect()
        _listen_connection(conn, hooks)
        trans = conn.begin()
        thrown: BaseException | None = None
        try:
            try:
                work(conn)
            except Exception as exc:
                raise_if_protocol(exc)
                thrown = exc
                raise
            trans.commit()
            return {
                "reported": "committed",
                "basis": "Transaction.commit() returned",
                "contract": EXPLICIT_CONTRACT,
            }
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            if thrown is not None and exc is thrown:
                try:
                    trans.rollback()
                except Exception:
                    pass
                return {
                    "reported": "rolled_back",
                    "basis": "the body threw and Transaction.rollback() was called",
                    "contract": EXPLICIT_CONTRACT,
                    "api_error": err_info(thrown),
                }
            return {
                "reported": "failed",
                "basis": "Transaction.commit() raised",
                "contract": EXPLICIT_CONTRACT,
                "api_error": err_info(exc),
            }
        finally:
            seen.update(hooks)
            conn.close()

    def probe() -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            return {"supported": True, "ok": True, "error": None}
        except Exception as exc:
            if _is_protocol(exc):
                raise
            return {"supported": True, "ok": False, "error": err_info(exc)}

    def reuse(name: str, cp: Callable[..., Any]) -> dict[str, Any]:
        started = time.monotonic()
        box: dict[str, int | None] = {"pid": None}

        def body(conn: Connection) -> None:
            write_marker(conn, name)
            ident = identify(conn)
            box["pid"] = ident["pid"]
            cp("reuse-after-write", ident)

        try:
            outcome = run_begin(engine, body)
            return {
                "attempted": True,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "reported": outcome["reported"],
                "error": outcome.get("api_error"),
                "pid": box["pid"],
            }
        except Exception as exc:
            if _is_protocol(exc):
                raise
            return {
                "attempted": True,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "reported": "failed",
                "error": err_info(exc),
                "pid": box["pid"],
            }

    forms = {
        "managed": "with conn.begin(): catch IntegrityError from the duplicate insert, then leave the block.",
        "explicit": "trans = conn.begin(); catch IntegrityError; trans.commit().",
        "control": "with conn.begin(): the IntegrityError leaves the block.",
        "savepoint": "with conn.begin(): with conn.begin_nested() around the duplicate. The nested error is caught and the outer block returns.",
    }
    return run_pr(
        kind,
        message,
        checkpoint,
        boundary=explicit if kind == "explicit" else managed,
        write=write_marker,
        insert_taken=insert_taken,
        identify=identify,
        reuse=reuse,
        err_info=err_info,
        is_protocol=_is_protocol,
        savepoint=savepoint,
        probe=probe,
        hooks=lambda: {"supported": True, **seen},
        form=forms[kind],
    )


CASES = {
    "CTL-01.commit": case_commit,
    "CTL-01.rollback": case_rollback,
    "TX-01A.caught-error-then-commit": case_caught_error,
    "PR-01.managed-catch-commit": lambda engine, message, fault: _core_pr("managed", engine, message),
    "PR-01.explicit-catch-commit": lambda engine, message, fault: _core_pr("explicit", engine, message),
    "PR-01.uncaught-control": lambda engine, message, fault: _core_pr("control", engine, message),
    "PR-01.savepoint-recovery": lambda engine, message, fault: _core_pr("savepoint", engine, message),
    "TX-01B.conn-lost-before-commit": case_conn_lost_before_commit,
    "TX-02.savepoint-rollback-not-sent": lambda engine, message, fault: case_savepoint(engine, message, fault, "not-sent"),
    "TX-02.savepoint-rollback-rejected": lambda engine, message, fault: case_savepoint(engine, message, fault, "rejected"),
    "TX-02.conn-lost-before-savepoint-rollback": lambda engine, message, fault: case_savepoint(engine, message, fault, "conn-lost"),
    "TX-03.rollback-not-sent": lambda engine, message, fault: case_reuse(engine, message, fault, "rollback-not-sent"),
    "TX-03.statement-error-rollback-not-sent": lambda engine, message, fault: case_reuse(engine, message, fault, "statement-error"),
    "TX-03.conn-lost-in-transaction": lambda engine, message, fault: case_reuse(engine, message, fault, "conn-lost"),
    "TX-04.nested-failure-contained": lambda engine, message, fault: case_nested(engine, message, fault, "nested-fails"),
    "TX-04.nested-released-outer-rollback": lambda engine, message, fault: case_nested(engine, message, fault, "outer-fails"),
    "TX-05.managed-serializable": case_managed_serializable,
    "TX-05.explicit-serializable": case_explicit_serializable,
}


def diagnostics(fault: Fault) -> dict[str, Any]:
    return {
        "instrumentation": INSTRUMENTATION,
        "trace": fault.trace,
        "withheld": fault.withheld,
        "rewritten": fault.rewritten,
        "reply_codes": fault.reply_codes,
        "commit_calls": fault.commit_calls,
        "rollback_calls": fault.rollback_calls,
        "trace_sees_framework_statements": any(
            sql.startswith("INSERT")
            or sql.startswith("SELECT")
            or sql.startswith("SAVEPOINT")
            or "WITHHELD" in sql
            or "REWRITE" in sql
            or sql.startswith("COMMIT")
            or sql.startswith("ROLLBACK")
            for sql in fault.trace
        ),
    }


def main() -> None:
    global current_fault
    message = read_message()
    if message.get("type") != "case":
        raise ProtocolError(f'expected a case message, got "{message.get("type")}"')
    pool_max = message["case"].get("settings", {}).get("pool_max", 1)
    send(
        {
            "type": "hello",
            "adapter": {"name": "sqlalchemy-core", "version": "0.1.0"},
            "framework": {"name": "sqlalchemy", "version": sqlalchemy.__version__},
            "driver": {"name": "psycopg", "version": psycopg.__version__},
            "components": {},
            "runtime": {"name": "python", "version": sys.version.split()[0]},
            "mode": message.get("mode"),
            "configuration": {
                "api": "Connection.begin()",
                "nested_api": "Connection.begin_nested()",
                "pool_size": pool_max,
                "max_overflow": 0,
                "pool_pre_ping": False,
            },
        }
    )
    fault = Fault()
    current_fault = fault
    engine: Engine | None = None
    try:
        if message.get("mode") != "native":
            result: dict[str, Any] = {
                "status": "error",
                "error": {
                    "class": "AdapterError",
                    "code": None,
                    "message": f'unknown mode "{message.get("mode")}"',
                    "protocol": False,
                },
            }
        else:
            impl = CASES.get(message["case"]["id"])
            if impl is None:
                result = {
                    "status": "not_implemented",
                    "reason": f'this adapter does not implement {message["case"]["id"]}',
                }
            else:
                engine = open_engine(message["connection"], pool_max)
                install_fault(engine, fault)
                outcome = impl(engine, message, fault)
                checkpoint("after-end", {})
                result = {"status": "completed", **outcome}
    except Exception as exc:
        result = {
            "status": "error",
            "error": {**err_info(exc), "protocol": isinstance(exc, ProtocolError)},
        }
    fault.armed = False
    if engine is not None:
        engine.dispose()
    result["diagnostics"] = diagnostics(fault)
    send({"type": "result", **result})
    raise SystemExit(0)


if __name__ == "__main__":
    try:
        main()
    except ProtocolError as exc:
        send(
            {
                "type": "result",
                "status": "error",
                "error": {**err_info(exc), "protocol": True},
            }
        )
        raise SystemExit(0)
