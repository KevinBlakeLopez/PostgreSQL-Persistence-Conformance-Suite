"""SQLITE-03: SQLAlchemy ORM Session after SQLite ends the transaction.

The SQLITE-01 schema and trigger, mapped as Account and Ledger. Unit 1 loads
account 1, debits it, adds ledger row A and flushes (write A is sent). The
fault then reaches the Session through one of two paths:

    execute  session.execute(update(Account)...): an ORM-enabled UPDATE
    flush    account 2's balance is changed and session.flush() sends it

Handling after the fault:

    continue      catch the DBAPIError, add ledger row B, complete
    rollback      catch, session.rollback(), add ledger row B, complete
    escape        the error leaves the unit

APIs: "commit" is session.commit() inside `with Session(engine)`; "begin" is
`with Session(engine) as s, s.begin():` (commits on a clean exit; used with
continue and escape only). Session events after_commit, after_rollback,
after_soft_rollback and after_begin write to an independent sink (layer D).
Three fresh Sessions then run on the same pool of one: N1 commits, N2 flushes
and rolls back, N3 commits.

    .venv/bin/python -I repro/sqlite03_session.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
import sqlite01_raw  # noqa: E402
from sqlite02_core import AppError, Engine, require_versions, status, write_stray_pool_log  # noqa: E402

from sqlalchemy import event, inspect, update  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column  # noqa: E402


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int]


class Ledger(Base):
    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str]
    step: Mapped[str]


CONFIGS = ("default", "autocommit-false", "begin-recipe")
PATHS = ("execute", "flush")
FAULTS = sqlite01_raw.FAULTS
ARMS = (("commit", "continue"), ("commit", "rollback"), ("commit", "escape"),
        ("begin", "continue"), ("begin", "escape"))
LATER_UNITS = (("N1", "commit"), ("N2", "rollback"), ("N3", "commit"))


def object_state(obj: Any) -> dict[str, Any] | None:
    """Identity-map facts about one object, read without loading anything."""
    if obj is None:
        return None
    insp = inspect(obj)
    return {
        "transient": insp.transient,
        "pending": insp.pending,
        "persistent": insp.persistent,
        "detached": insp.detached,
        "deleted": insp.deleted,
        "modified": insp.modified,
        "expired_attributes": sorted(insp.expired_attributes),
        "loaded": {key: insp.dict[key] for key in ("id", "balance", "step") if key in insp.dict},
    }


def session_state(session: Session, eng: Engine) -> dict[str, Any]:
    """Layer B through public Session APIs, plus layer A read from the DBAPI connections.

    Nothing here calls session.connection(), which could begin a transaction.
    """
    tx = session.get_transaction()
    return {
        "sa_session_in_transaction": session.in_transaction(),
        "sa_session_is_active": session.is_active,
        "sa_tx_is_active": None if tx is None else tx.is_active,
        "new": len(session.new),
        "dirty": len(session.dirty),
        "identity_map_size": len(session.identity_map),
        # private, research only: the SessionTransaction state
        "private_session_tx_state": None if tx is None else str(getattr(tx, "_state", None)),
        "sqlite_in_transaction": {f"dbapi{i}": common.in_transaction(c) for i, c in enumerate(eng.dbapi)},
    }


def scenario(config: str, path_kind: str, fault: str, api: str, handling: str) -> Callable[[Path, str], dict[str, Any]]:
    action, amount = FAULTS[fault]

    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        sink = common.Sink(work / "sink.sqlite")
        sqlite01_raw.setup(path, action)
        q = sqlite01_raw.queries(token)
        eng = Engine(path, config, token)
        steps: list[dict[str, Any]] = []
        checkpoints: dict[str, Any] = {}
        observers: dict[str, Any] = {}
        objects: dict[str, Any] = {}
        current_unit = {"label": "unit-1"}

        def hook(name: str) -> Callable[..., None]:
            def handler(session, *args) -> None:
                sink.record(token, f"{current_unit['label']}:{name}")
            return handler

        hooks = {name: hook(name) for name in ("after_begin", "after_commit", "after_rollback", "after_soft_rollback")}
        for name, handler in hooks.items():
            event.listen(Session, name, handler)

        def step(label: str, fn: Callable[[], Any], session: Session) -> dict[str, Any]:
            start = len(eng.trace)
            entry = common.call(label, fn)
            entry["sql_started"] = [e["sql"] for e in eng.trace[start:]]
            entry["state_after"] = session_state(session, eng)
            steps.append(entry)
            return entry

        def fault_call(session: Session) -> Callable[[], Any]:
            if path_kind == "execute":
                stmt = update(Account).where(Account.id == 2).values(balance=Account.balance - amount)
                return lambda: session.execute(stmt).rowcount

            def via_flush() -> None:
                acc2 = session.get(Account, 2)
                objects["acc2"] = acc2
                acc2.balance -= amount
                session.flush()
            return via_flush

        def unit_one(session: Session) -> None:
            acc1 = session.get(Account, 1)
            objects["acc1"] = acc1
            acc1.balance -= 30
            ledger_a = Ledger(token=token, step="A")
            objects["ledger_a"] = ledger_a
            session.add(ledger_a)
            step("flush write A", session.flush, session)
            checkpoints["before-fault"] = {"session": session_state(session, eng)}
            if handling == "escape":
                steps.append({"step": "fault (not caught)"})
                fault_call(session)()
                return
            start = len(eng.trace)
            entry: dict[str, Any] = {"step": "fault", "status": "ok"}
            try:
                fault_call(session)()
            except DBAPIError as exc:  # the application catches the database error
                entry = {"step": "fault", "status": "caught", "error": common.error_dict(exc)}
            entry["sql_started"] = [e["sql"] for e in eng.trace[start:]]
            steps.append(entry)
            checkpoints["after-fault"] = {
                "session": session_state(session, eng),
                "objects": {k: object_state(v) for k, v in objects.items()},
            }
            observers["after-fault"] = common.observe(path, q)
            if handling == "rollback":
                step("session.rollback()", session.rollback, session)
                checkpoints["after-app-rollback"] = {"session": session_state(session, eng)}
            ledger_b = Ledger(token=token, step="B")
            objects["ledger_b"] = ledger_b
            step("add B", lambda: session.add(ledger_b), session)

        def run_unit(label: str, body: Callable[[Session], None], ending: str) -> dict[str, Any]:
            current_unit["label"] = label
            record: dict[str, Any] = {"unit": label, "ending": ending}
            start = len(eng.trace)

            def commit_api() -> None:
                with Session(eng.engine) as session:
                    record["session"] = session
                    body(session)
                    record["end_from"] = len(eng.trace)
                    try:
                        session.commit() if ending == "commit" else session.rollback()
                    finally:
                        record["state_after_end"] = session_state(session, eng)
                        record["objects_after_end"] = {k: object_state(v) for k, v in objects.items()} if label == "unit-1" else None

            def begin_api() -> None:
                with Session(eng.engine) as session:
                    record["session"] = session
                    try:
                        with session.begin():
                            body(session)
                            record["end_from"] = len(eng.trace)
                            if ending == "rollback":
                                raise AppError("the application rolls this unit back")
                    finally:
                        record["state_after_end"] = session_state(session, eng)
                        record["objects_after_end"] = {k: object_state(v) for k, v in objects.items()} if label == "unit-1" else None

            outcome = common.call(label, commit_api if api == "commit" else begin_api)
            record.pop("session", None)
            record["outcome"] = status(outcome)
            if outcome.get("error") and outcome["error"]["type"].endswith("AppError"):
                record["outcome"] = "rolled back by AppError"
            record["error"] = outcome.get("error")
            record["warnings"] = outcome.get("warnings")
            record["sql_started"] = [e["sql"] for e in eng.trace[start:]]
            record["end_sql_started"] = [e["sql"] for e in eng.trace[record.get("end_from", len(eng.trace)):]]
            record["dbapi_serials"] = sorted({e["dbapi"] for e in eng.trace[start:]})
            return record

        def later_body(label: str, ending: str) -> Callable[[Session], None]:
            def body(session: Session) -> None:
                session.add(Ledger(token=token, step=label))
                if ending == "rollback":
                    session.flush()  # the write reaches SQLite before the rollback
            return body

        try:
            unit1 = run_unit("unit-1", unit_one, "commit")
            observers["after-unit-1"] = common.observe(path, q)
            if unit1["error"] is None:
                sink.record(token, "application-confirmed-transfer", "unit 1 completion returned normally")
            events_unit1 = list(eng.events)
            later = []
            for label, ending in LATER_UNITS:
                later.append(run_unit(label, later_body(label, ending), ending))
                observers[f"after-{label}"] = common.observe(path, q)
        finally:
            for name, handler in hooks.items():
                event.remove(Session, name, handler)
            finished = eng.finish()
        observers["final"] = common.observe(path, q)

        fault_entry = next((s for s in steps if s["step"].startswith("fault")), None)
        after_fault = checkpoints.get("after-fault") or {}
        observed = {
            "configuration": {"config": config, "path": path_kind, "api": api, "handling": handling,
                              "dbapi_at_connect": eng.dbapi_config},
            "fault": "not caught: see unit 1 outcome" if handling == "escape" else status(fault_entry),
            "fault_sql_started": None if fault_entry is None else fault_entry.get("sql_started"),
            "before_fault": checkpoints.get("before-fault"),
            "after_fault_session": after_fault.get("session"),
            "after_fault_objects": after_fault.get("objects"),
            "after_app_rollback": checkpoints.get("after-app-rollback"),
            "unit_1": {
                "outcome": unit1["outcome"],
                "warnings": sorted({w for s in steps for w in s.get("warnings", [])} | set(unit1["warnings"] or [])),
                "end_sql_started": unit1["end_sql_started"],
                "state_after_end": unit1.get("state_after_end"),
                "objects_after_end": unit1.get("objects_after_end"),
                "persisted": {k: observers["after-unit-1"][k] for k in ("balances", "ledger")},
            },
            "sink": sink.read(token),
            "pool_events_through_unit_1": events_unit1,
            "later_units": [
                {
                    "unit": unit["unit"],
                    "ending": unit["ending"],
                    "dbapi_serials": unit["dbapi_serials"],
                    "outcome": unit["outcome"],
                    "end_sql_started": unit["end_sql_started"],
                    "ledger_after": observers[f"after-{unit['unit']}"]["ledger"],
                }
                for unit in later
            ],
            "unit_1_dbapi_serials": unit1["dbapi_serials"],
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
            "steps": steps,
            "units": [unit1, *later],
            "checkpoints": checkpoints,
            "observers": observers,
            "pool_log_all": eng.pool_log,
        }

    return run


def main() -> None:
    require_versions()
    variants = [
        (f"{config}.{path_kind}.{fault}.{api}-{handling}", scenario(config, path_kind, fault, api, handling))
        for config in CONFIGS
        for path_kind in PATHS
        for fault in FAULTS
        for api, handling in ARMS
    ]
    run_dir = common.run_experiment("sqlite03-session", variants)
    write_stray_pool_log(run_dir)


if __name__ == "__main__":
    main()
