# PPCS adapter for SQLAlchemy 2.1. Speaks protocol version 1 on stdin/stdout.
# node-kit is not imported.
#
# Category C faults are injected in this process, once, before the framework
# sees the error. ROLLBACK TO SAVEPOINT reaches before_cursor_execute
# (DefaultDialect.do_rollback_to_savepoint executes the clause). A top-level
# ROLLBACK does not: DefaultDialect.do_rollback (default.py) calls
# dbapi_connection.rollback(). That path was confirmed on SQLAlchemy 2.1.5
# and psycopg 3.3.6: the cursor event saw ROLLBACK TO SAVEPOINT, and the root
# ROLLBACK arrived only as Connection.rollback(). The root withhold is on
# Connection.rollback, before send, and the cursor hook does not also match it.

from __future__ import annotations

import json
import re
import sys
import threading
import time
from typing import Any, Callable

import psycopg
import sqlalchemy
from psycopg.pq import TransactionStatus
from sqlalchemy import Integer, Text, event, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

PROTOCOL = 1
ROLLBACK_TO = re.compile(r"^rollback to (savepoint )?", re.IGNORECASE)
_STATUS = {value: name for name, value in TransactionStatus.__members__.items()}

# Session.begin() is a SessionTransaction. TransactionalContext.__exit__
# (sqlalchemy/engine/util.py, 2.1.5) commits when the block exits without an
# exception and the transaction is still active, and rolls back when the block
# exits with one. If commit() raises, that method calls rollback() when
# rollback can be called and then propagates the error from that exit
# (util.py __exit__, with sqlalchemy.util.safe_reraise). Session.begin_nested()
# (session.py) begins a SAVEPOINT. An exception there calls
# SessionTransaction.rollback(), which executes ROLLBACK TO SAVEPOINT
# (default.py do_rollback_to_savepoint). If that call raises, the exception
# propagates.
CONTRACT = (
    "Session.begin() as a context manager commits when the block exits without "
    "an exception and rolls back when the block exits with one. "
    "Session.begin_nested() is a SAVEPOINT; an exception there rolls back to "
    "the savepoint, and a failure of that rollback propagates. "
    "If commit() raises on the way out, TransactionalContext.__exit__ calls "
    "rollback() when it can and propagates the error from that exit."
)


class ProtocolError(Exception):
    pass


class AppError(Exception):
    pass


class Item(DeclarativeBase):
    pass


class Marker(Item):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)


class Uniq(Item):
    __tablename__ = "uniq"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)


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
        # and before that error returns to Session.begin_nested().
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
        connect_args={"application_name": connection["application_name"]},
    )


def identify(session: Session) -> dict[str, Any]:
    row = session.execute(
        text("select pg_current_xact_id()::text as xid, pg_backend_pid() as pid")
    ).mappings().one()
    return {"xid": row["xid"], "pid": int(row["pid"])}


def write_marker(session: Session, name: str) -> None:
    session.add(Marker(name=name, qty=0))
    session.flush()


def sleep_ms(settings: dict[str, Any]) -> None:
    time.sleep((settings.get("settle_ms") or 100) / 1000)


def map_begin_exit(thrown: BaseException | None, escaped: BaseException | None) -> dict[str, Any]:
    """Map Session.begin()'s exit. A clean exit is committed. The block's own
    exception is rolled back. Any other error from ending the transaction is failed.
    """
    if escaped is None:
        return {
            "reported": "committed",
            "basis": "Session.begin() exited without an exception, so it committed",
            "contract": CONTRACT,
        }
    raise_if_protocol(escaped)
    # Identity, not __context__. An error raised while __exit__ ends the
    # transaction is chained as __context__ and is not the block's exception.
    same = thrown is not None and escaped is thrown
    return {
        "reported": "rolled_back" if same else "failed",
        "basis": (
            "Session.begin() exited with the exception raised inside it, so it rolled back"
            if same
            else "Session.begin() exited with an error the block did not raise"
        ),
        "contract": CONTRACT,
        "api_error": err_info(thrown if same and thrown is not None else escaped),
    }


def run_begin(engine: Engine, body: Callable[[Session], None]) -> dict[str, Any]:
    """Run body inside Session.begin(). Map the context manager's exit."""
    session = Session(engine)
    thrown: BaseException | None = None
    try:
        with session.begin():
            try:
                body(session)
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
        session.close()


def case_commit(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(session: Session) -> None:
        write_marker(session, message["markers"]["tx"])
        checkpoint("before-end", identify(session))

    return run_begin(engine, body)


def case_rollback(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(session: Session) -> None:
        write_marker(session, message["markers"]["tx"])
        checkpoint("before-end", identify(session))
        raise AppError("application error: the request fails")

    return run_begin(engine, body)


def case_caught_error(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    violation: dict[str, BaseException | None] = {"exc": None}

    def body(session: Session) -> None:
        write_marker(session, message["markers"]["tx"])
        ident = identify(session)
        checkpoint("after-write", ident)
        try:
            session.add(Uniq(code="taken"))
            session.flush()
        except IntegrityError as exc:
            violation["exc"] = exc
        checkpoint("before-end", {"pid": ident["pid"]})

    outcome = run_begin(engine, body)
    found = violation["exc"]
    if found is None:
        raise RuntimeError("the duplicate insert did not raise IntegrityError")
    outcome["steps"] = {"violation": err_info(found)}
    return outcome


def case_conn_lost_before_commit(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    def body(session: Session) -> None:
        write_marker(session, message["markers"]["tx"])
        checkpoint("before-end", identify(session))
        sleep_ms(message["case"].get("settings") or {})

    return run_begin(engine, body)


def case_savepoint(engine: Engine, message: dict[str, Any], fault: Fault, kind: str) -> dict[str, Any]:
    markers = message["markers"]
    session = Session(engine)
    nested: dict[str, Any] = {"caught": False}
    pid: int | None = None
    escaped: BaseException | None = None
    try:
        with session.begin():
            write_marker(session, markers["outer"])
            ident = identify(session)
            pid = ident["pid"]
            fault.pid = pid
            checkpoint("outer-after-write", ident)
            try:
                with session.begin_nested():
                    write_marker(session, markers["inner"])
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
    checkpoint("after-outer", {"pid": pid})
    session.close()
    # The nested error was caught inside the block. An exception here was
    # raised while Session.begin() ended the outer transaction.
    outcome = map_begin_exit(None, escaped)
    steps: dict[str, Any] = {"nested": nested}
    if kind != "conn-lost":
        steps["fault"] = fault_report(fault)
    outcome["steps"] = steps
    return outcome


def case_reuse(engine: Engine, message: dict[str, Any], fault: Fault, kind: str) -> dict[str, Any]:
    markers = message["markers"]
    settings = message["case"].get("settings") or {}
    violation: dict[str, BaseException | None] = {"exc": None}
    pids: dict[str, int | None] = {"unit1": None, "unit2": None}

    def unit1(session: Session) -> None:
        write_marker(session, markers["doomed"])
        ident = identify(session)
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
                session.add(Uniq(code="taken"))
                session.flush()
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
        def body(session: Session) -> None:
            write_marker(session, markers["next"])
            ident = identify(session)
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


CASES = {
    "CTL-01.commit": case_commit,
    "CTL-01.rollback": case_rollback,
    "TX-01A.caught-error-then-commit": case_caught_error,
    "TX-01B.conn-lost-before-commit": case_conn_lost_before_commit,
    "TX-02.savepoint-rollback-not-sent": lambda engine, message, fault: case_savepoint(engine, message, fault, "not-sent"),
    "TX-02.savepoint-rollback-rejected": lambda engine, message, fault: case_savepoint(engine, message, fault, "rejected"),
    "TX-02.conn-lost-before-savepoint-rollback": lambda engine, message, fault: case_savepoint(engine, message, fault, "conn-lost"),
    "TX-03.rollback-not-sent": lambda engine, message, fault: case_reuse(engine, message, fault, "rollback-not-sent"),
    "TX-03.statement-error-rollback-not-sent": lambda engine, message, fault: case_reuse(engine, message, fault, "statement-error"),
    "TX-03.conn-lost-in-transaction": lambda engine, message, fault: case_reuse(engine, message, fault, "conn-lost"),
}


def diagnostics(fault: Fault) -> dict[str, Any]:
    return {
        "trace": fault.trace,
        "withheld": fault.withheld,
        "rewritten": fault.rewritten,
        "reply_codes": fault.reply_codes,
        "commit_calls": fault.commit_calls,
        "rollback_calls": fault.rollback_calls,
        "trace_sees_framework_statements": any(
            sql.startswith("INSERT")
            or sql.startswith("SAVEPOINT")
            or "WITHHELD" in sql
            or "REWRITE" in sql
            for sql in fault.trace
        ),
    }


def main() -> None:
    global current_fault
    message = read_message()
    if message.get("type") != "case":
        raise ProtocolError(f'expected a case message, got "{message.get("type")}"')
    send(
        {
            "type": "hello",
            "adapter": {"name": "sqlalchemy", "version": "0.1.0"},
            "framework": {"name": "sqlalchemy", "version": sqlalchemy.__version__},
            "driver": {"name": "psycopg", "version": psycopg.__version__},
            "components": {},
            "runtime": {"name": "python", "version": sys.version.split()[0]},
            "mode": message.get("mode"),
            "configuration": {
                "pool_size": message["case"].get("settings", {}).get("pool_max", 1),
                "max_overflow": 0,
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
                engine = open_engine(
                    message["connection"],
                    message["case"].get("settings", {}).get("pool_max", 1),
                )
                install_fault(engine, fault)
                outcome = impl(engine, message, fault)
                checkpoint("after-end", {})
                result = {"status": "completed", **outcome}
    except Exception as exc:
        result = {
            "status": "error",
            "error": {**err_info(exc), "protocol": isinstance(exc, ProtocolError)},
        }
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
