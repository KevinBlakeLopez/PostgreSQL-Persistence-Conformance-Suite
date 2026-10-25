"""SQLITE-04: a savepoint inside a transaction that SQLite then destroys.

The SQLITE-01 schema and trigger. The outer scope records ledger row A. A
nested scope (begin_nested(): SAVEPOINT) records ledger row I and then runs
the fault. The outer scope catches the error that leaves the nested scope,
records ledger row B, and completes. With RAISE(ABORT) the savepoint still
exists, so the nested scope's rollback removes I and the outer transaction
continues (the TX-04.1 shape). With RAISE(ROLLBACK) the savepoint and the
outer transaction are gone before the nested scope tries to roll back.

    layer core     with engine.begin() as conn:  with conn.begin_nested(): ...
    layer session  with Session(engine) as s, s.begin():  with s.begin_nested(): ...
                   the fault through session.execute() or through a flush

    catch broad     the outer scope catches sqlalchemy.exc.DBAPIError
    catch specific  the outer scope catches sqlalchemy.exc.IntegrityError only

A later unit then writes N1 and rolls back on the same pool of one.

    .venv/bin/python -I repro/sqlite04_savepoint.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
import sqlite01_raw  # noqa: E402
from sqlite02_core import AppError, Engine, require_versions, status, write_stray_pool_log  # noqa: E402
from sqlite03_session import Account, Ledger, session_state  # noqa: E402

from sqlalchemy import event, text, update  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


CONFIGS = ("default", "autocommit-false", "begin-recipe")
FAULTS = sqlite01_raw.FAULTS
CATCHES = {"broad": DBAPIError, "specific": IntegrityError}
LAYERS = (("core", None), ("session", "execute"), ("session", "flush"))


def core_state(conn, eng: Engine) -> dict[str, Any]:
    return {
        "sa_in_transaction": conn.in_transaction(),
        "sa_in_nested_transaction": conn.in_nested_transaction(),
        "sqlite_in_transaction": {f"dbapi{i}": common.in_transaction(c) for i, c in enumerate(eng.dbapi)},
    }


def scenario(config: str, layer: str, path_kind: str | None, fault: str, catch: str) -> Callable[[Path, str], dict[str, Any]]:
    action, amount = FAULTS[fault]
    caught_type = CATCHES[catch]

    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        sink = common.Sink(work / "sink.sqlite")
        sqlite01_raw.setup(path, action)
        q = sqlite01_raw.queries(token)
        eng = Engine(path, config, token)
        checkpoints: dict[str, Any] = {}
        observers: dict[str, Any] = {}
        marks: dict[str, int] = {}
        current = {"label": "unit-1"}

        def hook(name: str) -> Callable[..., None]:
            def handler(session, *args) -> None:
                sink.record(token, f"{current['label']}:{name}")
            return handler

        hooks = {name: hook(name) for name in ("after_commit", "after_rollback", "after_soft_rollback")}
        for name, handler in hooks.items():
            event.listen(Session, name, handler)

        def insert_core(conn, label: str) -> None:
            conn.execute(text("INSERT INTO ledger(token, step) VALUES (:t, :s)"), {"t": token, "s": label})

        def core_unit() -> None:
            with eng.engine.begin() as conn:
                insert_core(conn, "A")
                handled = None
                marks["nested_start"] = len(eng.trace)
                try:
                    with conn.begin_nested():
                        insert_core(conn, "I")
                        checkpoints["inside-nested"] = core_state(conn, eng)
                        conn.execute(text(f"UPDATE accounts SET balance = balance - {amount} WHERE id = 2"))
                except caught_type as exc:  # the outer scope handles the nested failure
                    handled = common.error_dict(exc)
                marks["nested_end"] = len(eng.trace)
                checkpoints["after-nested"] = {"handled": handled, **core_state(conn, eng)}
                observers["after-nested"] = common.observe(path, q)
                insert_core(conn, "B")
                checkpoints["after-write-b"] = core_state(conn, eng)
                observers["after-write-b"] = common.observe(path, q)
                marks["outer_end"] = len(eng.trace)

        def session_unit() -> None:
            with Session(eng.engine) as session:
                with session.begin():
                    session.add(Ledger(token=token, step="A"))
                    session.flush()
                    handled = None
                    marks["nested_start"] = len(eng.trace)
                    try:
                        with session.begin_nested():
                            session.add(Ledger(token=token, step="I"))
                            session.flush()
                            checkpoints["inside-nested"] = session_state(session, eng)
                            if path_kind == "execute":
                                session.execute(update(Account).where(Account.id == 2)
                                                .values(balance=Account.balance - amount))
                            else:
                                acc2 = session.get(Account, 2)
                                acc2.balance -= amount
                                session.flush()
                    except caught_type as exc:  # the outer scope handles the nested failure
                        handled = common.error_dict(exc)
                    marks["nested_end"] = len(eng.trace)
                    checkpoints["after-nested"] = {
                        "handled": handled,
                        "sa_in_nested_transaction": session.in_nested_transaction(),
                        **session_state(session, eng),
                    }
                    observers["after-nested"] = common.observe(path, q)
                    session.add(Ledger(token=token, step="B"))
                    marks["outer_end"] = len(eng.trace)

        try:
            unit1 = common.call("unit-1", core_unit if layer == "core" else session_unit)
            observers["after-unit-1"] = common.observe(path, q)
            if unit1["status"] == "ok":
                sink.record(token, "application-confirmed", "unit 1 completion returned normally")
            current["label"] = "N1"

            def later() -> None:
                with eng.engine.begin() as conn:
                    insert_core(conn, "N1")
                    raise AppError("the application rolls this unit back")

            n1_start = len(eng.trace)
            n1 = common.call("N1", later)
            n1_sql = [e["sql"] for e in eng.trace[n1_start:]]
            n1_serials = sorted({e["dbapi"] for e in eng.trace[n1_start:]})
            observers["after-N1"] = common.observe(path, q)
        finally:
            for name, handler in hooks.items():
                event.remove(Session, name, handler)
            finished = eng.finish()
        observers["final"] = common.observe(path, q)

        def sql(a: str, b: str) -> list[str]:
            return [e["sql"] for e in eng.trace[marks.get(a, 0):marks.get(b, len(eng.trace))]]

        after_nested = checkpoints.get("after-nested") or {}
        handled = after_nested.get("handled")
        observed = {
            "configuration": {"config": config, "layer": layer, "path": path_kind, "catch": catch,
                              "dbapi_at_connect": eng.dbapi_config},
            "inside_nested": checkpoints.get("inside-nested"),
            "nested_sql_started": sql("nested_start", "nested_end"),
            "handled_by_outer": None if handled is None else {"type": handled["type"], "chain": handled["chain"]},
            "after_nested": {k: v for k, v in after_nested.items() if k != "handled"},
            "b_visible_to_observer_before_completion": ["B"] in (observers.get("after-write-b", {}).get("ledger") or []),
            "unit_1": {
                "outcome": status(unit1),
                "chain": (unit1.get("error") or {}).get("chain"),
                "completion_sql_started": [e["sql"] for e in eng.trace[marks.get("outer_end", len(eng.trace)):n1_start]],
                "warnings": unit1.get("warnings"),
                "persisted": {k: observers["after-unit-1"][k] for k in ("balances", "ledger")},
            },
            "sink": sink.read(token),
            "later_unit_N1": {
                "outcome": "rolled back by AppError" if (n1.get("error") or {}).get("type", "").endswith("AppError") else status(n1),
                "dbapi_serials": n1_serials,
                "sql_started": n1_sql,
                "ledger_after": observers["after-N1"]["ledger"],
            },
            "persisted_final": {k: observers["final"][k] for k in ("balances", "ledger")},
            "pool_at_end": finished,
            "pool_log": [
                {"level": r["level"], "message": r["message"], "exception": (r["exception"] or {}).get("message")}
                for r in eng.pool_log if r["level"] in ("WARNING", "ERROR", "CRITICAL")
            ],
        }
        return {
            "observed": observed,
            "trace": [f"dbapi{e['dbapi']}: {e['sql']}" for e in eng.trace],
            "trace_events": eng.trace,
            "events": eng.events,
            "unit_1_record": unit1,
            "checkpoints": checkpoints,
            "observers": observers,
            "pool_log_all": eng.pool_log,
        }

    return run


def main() -> None:
    require_versions()
    variants = [
        (f"{config}.{layer}{'-' + path_kind if path_kind else ''}.{fault}.catch-{catch}",
         scenario(config, layer, path_kind, fault, catch))
        for config in CONFIGS
        for layer, path_kind in LAYERS
        for fault in FAULTS
        for catch in CATCHES
    ]
    run_dir = common.run_experiment("sqlite04-savepoint", variants)
    write_stray_pool_log(run_dir)


if __name__ == "__main__":
    main()
