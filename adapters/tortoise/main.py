# PPCS adapter for Tortoise ORM 1.1.9. Speaks protocol version 1 on stdin/stdout.
# node-kit is not imported.
#
# The public API under test is tortoise.transactions.in_transaction. A nested
# call is a savepoint (NestedTransactionContext). atomic() is a decorator
# around the same function, so the context manager is the one form.
#
# Category C faults patch asyncpg.Connection.execute, which is what
# asyncpg.Transaction uses for BEGIN, SAVEPOINT, COMMIT, ROLLBACK, and
# ROLLBACK TO. A withheld statement raises before execute, so PostgreSQL
# never receives it. A rewritten ROLLBACK TO is sent, and after-fault is
# reported after PostgreSQL answers, before the exception reaches Tortoise.
#
# asyncpg.Transaction.__rollback sends "ROLLBACK;" for a top-level transaction
# and "ROLLBACK TO {name};" for a savepoint. Connection._reset, which the
# pool runs on release, sends "ROLLBACK" with no semicolon when the protocol
# is still in a transaction. The withhold matches only "ROLLBACK;", so the
# pool's recovery statement is the behavior under test and is not swallowed.
# in_transaction() does not return until that release has finished, so the
# last statement at after-end is often the pool reset query.

from __future__ import annotations

import asyncio
import json
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Awaitable, Callable

import asyncpg
import tortoise
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from models import Item, Uniq

PROTOCOL = 1

# tortoise/transactions.py, in_transaction, 1.1.9: "If error occurs transaction
# will rollback." TransactionContextPooled.__aexit__ (backends/base/client.py)
# commits when the block raises nothing, and calls rollback() when it raises,
# except TransactionManagementError, which skips that call. The exception
# still propagates. NestedTransactionContext does the same with
# savepoint_rollback() and release_savepoint(). The pool connection is
# released after that, in a finally. A clean exit is the report of a commit.
CONTRACT = (
    "Tortoise ORM 1.1.9 in_transaction() runs the block in one transaction and, "
    "as its docstring says, rolls back if an error occurs (tortoise/transactions.py). "
    "TransactionContextPooled.__aexit__ commits when the block exits without an "
    "exception and calls rollback() when it exits with one, except "
    "TransactionManagementError, which skips that call. The exception still "
    "propagates. NestedTransactionContext does the same with savepoint_rollback() "
    "and release_savepoint() (tortoise/backends/base/client.py). A nested "
    "in_transaction() is a savepoint. A clean exit is Tortoise's report that the "
    "transaction committed."
)

FORM = (
    "in_transaction() context manager. atomic() decorates the same function. "
    "A nested in_transaction() is the savepoint."
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
        self.abandoned = False


fault = Fault()
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


async def checkpoint(name: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if fault.abandoned:
        raise ProtocolError(f'checkpoint "{name}" after the unit was abandoned')
    body: dict[str, Any] = {"type": "checkpoint", "name": name}
    if data:
        body.update(data)
    send(body)
    msg = await asyncio.to_thread(read_message)
    if msg.get("type") != "resume" or msg.get("name") != name:
        raise ProtocolError(
            f'expected resume for checkpoint "{name}", got {json.dumps(msg)}'
        )
    return msg


def sqlstate(exc: BaseException | None) -> str | None:
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
        if cur.__cause__ is not None and cur.__cause__ is not cur:
            stack.append(cur.__cause__)
    return None


def raise_if_protocol(exc: BaseException) -> None:
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, ProtocolError):
            raise cur
        if cur.__cause__ is not None and cur.__cause__ is not cur:
            stack.append(cur.__cause__)
        if cur.__context__ is not None and cur.__context__ is not cur.__cause__:
            stack.append(cur.__context__)


def err_info(exc: BaseException) -> dict[str, Any]:
    return {
        "class": type(exc).__name__,
        "code": sqlstate(exc),
        "message": " ".join(str(exc).split())[:500],
    }


def fault_report() -> dict[str, Any]:
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


def one_line(query: str) -> str:
    return " ".join(query.split())


def is_rollback_to(query: str) -> bool:
    return one_line(query).upper().startswith("ROLLBACK TO")


def is_transaction_rollback(query: str) -> bool:
    """The transaction's own ROLLBACK, not the pool reset's.

    asyncpg.Transaction.__rollback sends ``ROLLBACK;``. Connection._reset
    sends ``ROLLBACK`` with no semicolon.
    """
    return one_line(query).upper() == "ROLLBACK;"


def install_patch() -> None:
    global _patched
    if _patched:
        return
    original_execute = asyncpg.Connection.execute

    async def execute(self: Any, query: str, *args: Any, timeout: float | None = None) -> str:
        text = query if isinstance(query, str) else str(query)
        if fault.kind == "savepoint" and fault.armed and is_rollback_to(text):
            fault.armed = False
            fault.fired += 1
            if fault.mode_name == "client-reject":
                fault.withheld.append(text)
                fault.trace.append(f"{one_line(text)}  -- WITHHELD before send")
                await checkpoint("after-fault", {"pid": fault.pid})
                raise RuntimeError(
                    "injected client-side failure: ROLLBACK TO SAVEPOINT was not sent"
                )
            rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint"
            fault.withheld.append(text)
            fault.rewritten.append(rewritten)
            fault.trace.append(f"{rewritten}  -- REWRITE of: {one_line(text)}")
            try:
                status = await original_execute(self, rewritten, *args, timeout=timeout)
            except Exception as exc:
                fault.reply_codes.append(sqlstate(exc) or "error")
                await checkpoint("after-fault", {"pid": fault.pid})
                raise
            fault.reply_codes.append(str(status))
            await checkpoint("after-fault", {"pid": fault.pid})
            return status
        if fault.kind == "root" and fault.armed and is_transaction_rollback(text):
            fault.armed = False
            fault.fired += 1
            fault.withheld.append(text)
            fault.trace.append("ROLLBACK;  -- WITHHELD before send")
            await checkpoint("after-fault", {"pid": fault.pid})
            raise RuntimeError("injected client-side failure: ROLLBACK was not sent")
        try:
            status = await original_execute(self, query, *args, timeout=timeout)
        except Exception as exc:
            fault.trace.append(f"{one_line(text)}  -- ERROR {sqlstate(exc) or type(exc).__name__}")
            raise
        fault.trace.append(f"{one_line(text)} -> {status}")
        return status

    asyncpg.Connection.execute = execute  # type: ignore[method-assign]
    _patched = True


def config(connection: dict[str, Any], pool_max: int) -> dict[str, Any]:
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "host": connection["host"],
                    "port": int(connection["port"]),
                    "user": connection["user"],
                    "password": connection["password"],
                    "database": connection["database"],
                    "minsize": 1,
                    "maxsize": pool_max,
                    "application_name": connection["application_name"],
                },
            }
        },
        "apps": {"models": {"models": ["models"]}},
        "use_tz": False,
    }


async def identify(conn: Any) -> dict[str, Any]:
    rows = await conn.execute_query_dict(
        "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid"
    )
    row = rows[0]
    pid = int(row["pid"])
    fault.pid = pid
    return {"xid": str(row["xid"]), "pid": pid}


async def write_marker(conn: Any, name: str) -> None:
    await Item.create(name=name, qty=0, using_db=conn)


async def sleep_ms(settings: dict[str, Any]) -> None:
    await asyncio.sleep((settings.get("settle_ms") or 100) / 1000)


def map_exit(thrown: BaseException | None, escaped: BaseException | None) -> dict[str, Any]:
    """Map in_transaction()'s exit. A clean exit is committed. The block's own
    exception is rolled back. Any other error from ending the transaction is failed.
    """
    if escaped is None:
        return {
            "reported": "committed",
            "basis": "in_transaction() exited without an exception, so it committed",
            "contract": CONTRACT,
            "form": FORM,
        }
    raise_if_protocol(escaped)
    # Identity, not __context__. An error raised while __aexit__ ends the
    # transaction is chained as __context__ and is not the block's exception.
    same = thrown is not None and escaped is thrown
    return {
        "reported": "rolled_back" if same else "failed",
        "basis": (
            "in_transaction() exited with the exception raised inside it, so it rolled back"
            if same
            else "in_transaction() exited with an error the block did not raise"
        ),
        "contract": CONTRACT,
        "form": FORM,
        "api_error": err_info(thrown if same and thrown is not None else escaped),
    }


async def run_in_transaction(body: Callable[[Any], Awaitable[None]]) -> dict[str, Any]:
    thrown: BaseException | None = None
    try:
        async with in_transaction() as conn:
            try:
                await body(conn)
            except Exception as exc:
                raise_if_protocol(exc)
                thrown = exc
                raise
        return map_exit(None, None)
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        return map_exit(thrown, exc)


async def case_commit(message: dict[str, Any]) -> dict[str, Any]:
    async def body(conn: Any) -> None:
        await write_marker(conn, message["markers"]["tx"])
        await checkpoint("before-end", await identify(conn))

    return await run_in_transaction(body)


async def case_rollback(message: dict[str, Any]) -> dict[str, Any]:
    async def body(conn: Any) -> None:
        await write_marker(conn, message["markers"]["tx"])
        await checkpoint("before-end", await identify(conn))
        raise AppError("application error: the request fails")

    return await run_in_transaction(body)


async def case_caught_error(message: dict[str, Any]) -> dict[str, Any]:
    violation: dict[str, BaseException | None] = {"exc": None}

    async def body(conn: Any) -> None:
        await write_marker(conn, message["markers"]["tx"])
        ident = await identify(conn)
        await checkpoint("after-write", ident)
        try:
            await Uniq.create(code="taken", using_db=conn)
        except IntegrityError as exc:
            violation["exc"] = exc
        await checkpoint("before-end", {"pid": ident["pid"]})

    outcome = await run_in_transaction(body)
    found = violation["exc"]
    if found is None:
        raise RuntimeError("the duplicate insert did not raise IntegrityError")
    outcome["steps"] = {"violation": err_info(found)}
    return outcome


async def case_conn_lost_before_commit(message: dict[str, Any]) -> dict[str, Any]:
    async def body(conn: Any) -> None:
        await write_marker(conn, message["markers"]["tx"])
        await checkpoint("before-end", await identify(conn))
        await sleep_ms(message["case"].get("settings") or {})

    return await run_in_transaction(body)


async def case_savepoint(message: dict[str, Any], kind: str) -> dict[str, Any]:
    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False}

    async def body(outer: Any) -> None:
        await write_marker(outer, markers["outer"])
        ident = await identify(outer)
        await checkpoint("outer-after-write", ident)
        try:
            async with in_transaction() as inner:
                await write_marker(inner, markers["inner"])
                await checkpoint("inner-after-write", {"pid": ident["pid"]})
                if kind == "conn-lost":
                    await sleep_ms(message["case"].get("settings") or {})
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

    outcome = await run_in_transaction(body)
    await checkpoint("after-outer", {"pid": fault.pid})
    steps: dict[str, Any] = {"nested": nested}
    if kind != "conn-lost":
        steps["fault"] = fault_report()
    outcome["steps"] = steps
    return outcome


async def case_reuse(message: dict[str, Any], kind: str) -> dict[str, Any]:
    markers = message["markers"]
    settings = message["case"].get("settings") or {}
    violation: dict[str, BaseException | None] = {"exc": None}
    pids: dict[str, int | None] = {"unit1": None, "unit2": None}

    async def unit1(conn: Any) -> None:
        await write_marker(conn, markers["doomed"])
        ident = await identify(conn)
        pids["unit1"] = ident["pid"]
        await checkpoint("unit1-after-write", ident)
        if kind == "conn-lost":
            await sleep_ms(settings)
        else:
            fault.kind = "root"
            fault.mode_name = "client-reject"
            fault.armed = True
        if kind == "statement-error":
            try:
                await Uniq.create(code="taken", using_db=conn)
            except ProtocolError:
                raise
            except Exception as exc:
                raise_if_protocol(exc)
                if isinstance(exc, IntegrityError) or sqlstate(exc) == "23505":
                    violation["exc"] = exc
                raise
        raise AppError("application error: unit 1 fails")

    outcome = await run_in_transaction(unit1)
    fault.armed = False
    fault.kind = None
    await checkpoint("after-unit1", {"pid": pids["unit1"]})

    async def unit2() -> dict[str, Any]:
        async def body(conn: Any) -> None:
            await write_marker(conn, markers["next"])
            ident = await identify(conn)
            pids["unit2"] = ident["pid"]
            await checkpoint("unit2-after-write", ident)

        return await run_in_transaction(body)

    started = time.monotonic()
    bound_ms = settings.get("bound_ms") or 5000
    try:
        value = await asyncio.wait_for(unit2(), timeout=bound_ms / 1000)
    except TimeoutError:
        fault.abandoned = True
        unit2_outcome: dict[str, Any] = {"outcome": "pending", "elapsed_ms": bound_ms}
    else:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        unit2_outcome = {"outcome": "completed", "elapsed_ms": elapsed_ms, **value}
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
        steps["fault"] = fault_report()
    outcome["steps"] = steps
    return outcome


async def case_nested(message: dict[str, Any], variant: str) -> dict[str, Any]:
    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False, "completed": False}

    async def body(outer: Any) -> None:
        await write_marker(outer, markers["outer"])
        try:
            async with in_transaction() as inner:
                await write_marker(inner, markers["inner"])
                await checkpoint("inner-after-write", await identify(inner))
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

    outcome = await run_in_transaction(body)
    outcome["steps"] = {"nested": nested}
    return outcome


CASES = {
    "CTL-01.commit": case_commit,
    "CTL-01.rollback": case_rollback,
    "TX-01A.caught-error-then-commit": case_caught_error,
    "TX-01B.conn-lost-before-commit": case_conn_lost_before_commit,
    "TX-02.savepoint-rollback-not-sent": lambda message: case_savepoint(message, "not-sent"),
    "TX-02.savepoint-rollback-rejected": lambda message: case_savepoint(message, "rejected"),
    "TX-02.conn-lost-before-savepoint-rollback": lambda message: case_savepoint(message, "conn-lost"),
    "TX-03.rollback-not-sent": lambda message: case_reuse(message, "rollback-not-sent"),
    "TX-03.statement-error-rollback-not-sent": lambda message: case_reuse(message, "statement-error"),
    "TX-03.conn-lost-in-transaction": lambda message: case_reuse(message, "conn-lost"),
    "TX-04.nested-failure-contained": lambda message: case_nested(message, "nested-fails"),
    "TX-04.nested-released-outer-rollback": lambda message: case_nested(message, "outer-fails"),
}


def diagnostics() -> dict[str, Any]:
    return {
        "trace": fault.trace,
        "withheld": fault.withheld,
        "rewritten": fault.rewritten,
        "reply_codes": fault.reply_codes,
        "trace_sees_transaction_statements": any(
            line.startswith("BEGIN")
            or line.startswith("SAVEPOINT")
            or line.startswith("COMMIT")
            or line.startswith("ROLLBACK")
            or "WITHHELD" in line
            or "REWRITE" in line
            for line in fault.trace
        ),
    }


def hello(mode: str | None, pool_max: int) -> None:
    send(
        {
            "type": "hello",
            "adapter": {"name": "tortoise", "version": "0.1.0"},
            "framework": {"name": "tortoise-orm", "version": tortoise.__version__},
            "driver": {"name": "asyncpg", "version": asyncpg.__version__},
            "components": _components(),
            "runtime": {"name": "python", "version": sys.version.split()[0]},
            "mode": mode,
            "configuration": {
                "engine": "tortoise.backends.asyncpg",
                "minsize": 1,
                "maxsize": pool_max,
            },
        }
    )


def _components() -> dict[str, str]:
    found: dict[str, str] = {}
    for dist in ("pypika-tortoise", "aiosqlite", "iso8601"):
        try:
            found[dist] = version(dist)
        except PackageNotFoundError:
            continue
    return found


async def close_tortoise() -> None:
    try:
        await asyncio.wait_for(Tortoise.close_connections(), timeout=5)
    except Exception:
        pass


async def main() -> None:
    message = await asyncio.to_thread(read_message)
    if message.get("type") != "case":
        raise ProtocolError(f'expected a case message, got "{message.get("type")}"')
    mode = message.get("mode")
    pool_max = int((message["case"].get("settings") or {}).get("pool_max") or 1)
    hello(mode, pool_max)
    try:
        if mode != "native":
            result: dict[str, Any] = {
                "status": "error",
                "error": {
                    "class": "AdapterError",
                    "code": None,
                    "message": f'unknown mode "{mode}"',
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
                install_patch()
                await Tortoise.init(config=config(message["connection"], pool_max))
                outcome = await impl(message)
                await checkpoint("after-end", {})
                result = {"status": "completed", **outcome}
    except Exception as exc:
        result = {
            "status": "error",
            "error": {**err_info(exc), "protocol": isinstance(exc, ProtocolError)},
        }
    await close_tortoise()
    result["diagnostics"] = diagnostics()
    send({"type": "result", **result})


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ProtocolError as exc:
        send(
            {
                "type": "result",
                "status": "error",
                "error": {**err_info(exc), "protocol": True},
                "diagnostics": diagnostics(),
            }
        )
    raise SystemExit(0)
