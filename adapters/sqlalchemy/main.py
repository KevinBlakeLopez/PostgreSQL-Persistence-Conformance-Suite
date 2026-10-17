# PPCS adapter for SQLAlchemy 2.1. Speaks protocol version 1 on stdin/stdout.
# node-kit is not imported. Category C faults are withheld here, before psycopg
# sends the statement, which is what pg-instrument.mjs does for node-postgres.

from __future__ import annotations

import json
import re
import sys
from typing import Any

import psycopg
import sqlalchemy
from sqlalchemy import Integer, Text, event, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

PROTOCOL = 1
ROLLBACK_TO = re.compile(r"^rollback to (savepoint )?", re.IGNORECASE)

# Session.begin() is a SessionTransaction. TransactionalContext.__exit__
# (sqlalchemy/engine/util.py) commits when the block exits without an exception
# and rolls back when it exits with one. Session.begin_nested() (session.py)
# begins a SAVEPOINT. An exception in that block calls
# SessionTransaction.rollback(), which executes ROLLBACK TO SAVEPOINT
# (default.py do_rollback_to_savepoint). If that call raises, the exception
# propagates and the nested transaction is closed.
CONTRACT = (
    "Session.begin() as a context manager commits when the block exits without "
    "an exception and rolls back when the block exits with one. "
    "Session.begin_nested() is a SAVEPOINT; an exception there rolls back to "
    "the savepoint, and a failure of that rollback propagates."
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


class Fault:
    def __init__(self) -> None:
        self.armed = False
        self.fired = 0
        self.pid: int | None = None
        self.trace: list[str] = []
        self.withheld: list[str] = []


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


def err_info(exc: BaseException) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if code is not None:
        code = str(code)
    return {
        "class": type(exc).__name__,
        "code": code,
        "message": " ".join(str(exc).split())[:500],
    }


def install_fault(engine: Engine, fault: Fault) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        sql = " ".join(str(statement).split())
        if fault.armed and ROLLBACK_TO.match(sql):
            fault.armed = False
            fault.fired += 1
            fault.withheld.append(sql)
            fault.trace.append(f"{sql}  -- WITHHELD before send")
            checkpoint("after-fault", {"pid": fault.pid})
            raise RuntimeError(
                "injected client-side failure: ROLLBACK TO SAVEPOINT was not sent"
            )
        fault.trace.append(sql)


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


def run_begin(engine: Engine, body: Any) -> dict[str, Any]:
    """Run body inside Session.begin(). Map the context manager's exit."""
    session = Session(engine)
    thrown: BaseException | None = None
    try:
        with session.begin():
            try:
                body(session)
            except Exception as exc:
                thrown = exc
                raise
        return {
            "reported": "committed",
            "basis": "Session.begin() exited without an exception, so it committed",
            "contract": CONTRACT,
        }
    except ProtocolError:
        raise
    except Exception as exc:
        same = thrown is not None and (exc is thrown or exc.__cause__ is thrown or exc.__context__ is thrown)
        return {
            "reported": "rolled_back" if same else "failed",
            "basis": (
                "Session.begin() exited with the exception raised inside it, so it rolled back"
                if same
                else "Session.begin() exited with an error the block did not raise"
            ),
            "contract": CONTRACT,
            "api_error": err_info(thrown if same and thrown is not None else exc),
        }
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


def case_savepoint_not_sent(engine: Engine, message: dict[str, Any], fault: Fault) -> dict[str, Any]:
    markers = message["markers"]
    session = Session(engine)
    nested: dict[str, Any] = {"caught": False}
    pid: int | None = None
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
                    fault.armed = True
                    raise AppError("application error: the nested scope fails")
            except ProtocolError:
                raise
            except Exception as exc:
                nested["caught"] = True
                nested["error"] = err_info(exc)
        outcome = {
            "reported": "committed",
            "basis": "Session.begin() exited without an exception, so it committed",
            "contract": CONTRACT,
        }
    except ProtocolError:
        raise
    except Exception as exc:
        outcome = {
            "reported": "failed",
            "basis": "Session.begin() raised while ending the outer transaction",
            "contract": CONTRACT,
            "api_error": err_info(exc),
        }
    checkpoint("after-outer", {"pid": pid})
    session.close()
    return {
        **outcome,
        "steps": {
            "nested": nested,
            "fault": {"mode": "client-reject", "fired": fault.fired},
        },
    }


CASES = {
    "CTL-01.commit": case_commit,
    "CTL-01.rollback": case_rollback,
    "TX-02.savepoint-rollback-not-sent": case_savepoint_not_sent,
}


def diagnostics(fault: Fault) -> dict[str, Any]:
    return {
        "trace": fault.trace,
        "withheld": fault.withheld,
        "trace_sees_framework_statements": any(
            sql.startswith("INSERT") or sql.startswith("SAVEPOINT") or "WITHHELD" in sql
            for sql in fault.trace
        ),
    }


def main() -> None:
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
            "configuration": {"pool_size": message["case"].get("settings", {}).get("pool_max", 1), "max_overflow": 0},
        }
    )
    fault = Fault()
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
