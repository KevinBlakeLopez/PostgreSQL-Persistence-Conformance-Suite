"""SQLITE-06: Django transaction.atomic() after SQLite ends the transaction.

The SQLITE-01 schema and trigger, through unmanaged models (repro/sdapp).
Inside an outer atomic() block the application records ledger row A and
registers transaction.on_commit(), whose callback writes to an independent
sink (layer D). Then the fault runs:

    orm  Account.objects.filter(id=2).update(balance=F("balance") - amount)
    raw  connection.cursor().execute("UPDATE accounts ...")

Handling:

    nested-catch       the documented pattern: try: with atomic(): fault
                       except IntegrityError: ...; then record ledger row B
    nested-catch-no-b  the same, with no query after the handled error
    plain-catch        try: fault except IntegrityError inside the outer block,
                       then B (Django's docs warn against this)
    escape             the error leaves the outer block

Each repetition runs in a fresh subprocess, so Django's settings and
connection state start clean.

    .venv/bin/python -I repro/sqlite06_django.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
import sqlite01_raw  # noqa: E402


FAULTS = sqlite01_raw.FAULTS
PATHS = ("orm", "raw")
ARMS = ("nested-catch", "nested-catch-no-b", "plain-catch", "escape")


def child(db: str, sink_path: str, token: str, fault: str, path_kind: str, arm: str) -> dict[str, Any]:
    import django
    from django.conf import settings

    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": db}},
        INSTALLED_APPS=["sdapp"],
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
    )
    django.setup()
    from django.db import IntegrityError, connection, transaction
    from django.db.models import F
    from sdapp.models import Account, Ledger

    amount = FAULTS[fault][1]
    sink = common.Sink(Path(sink_path))
    trace: list[str] = []
    record: dict[str, Any] = {"steps": []}

    def sqlite_state() -> Any:
        raw = connection.connection
        return None if raw is None else common.in_transaction(raw)

    def django_state(label: str) -> None:
        record[label] = {
            "needs_rollback": connection.needs_rollback,
            "in_atomic_block": connection.in_atomic_block,
            "savepoint_ids": len(connection.savepoint_ids),
            "get_autocommit": connection.get_autocommit(),
            "sqlite_in_transaction": sqlite_state(),
        }

    def run_fault() -> None:
        if path_kind == "orm":
            Account.objects.filter(id=2).update(balance=F("balance") - amount)
        else:
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE accounts SET balance = balance - {amount} WHERE id = 2")

    def write(step: str) -> None:
        """Record the write, then let any error propagate as it would in an application."""
        try:
            Ledger.objects.create(token=token, step=step)
        except Exception as exc:
            record["steps"].append({"step": f"write {step}", "status": "error", "error": common.error_dict(exc)})
            raise
        record["steps"].append({"step": f"write {step}", "status": "ok"})

    def body() -> None:
        connection.ensure_connection()
        connection.connection.set_trace_callback(trace.append)
        with transaction.atomic():
            write("A")
            transaction.on_commit(lambda: sink.record(token, "on_commit"))
            django_state("before_fault")
            if arm == "escape":
                run_fault()
                return
            handled = None
            if arm in ("nested-catch", "nested-catch-no-b"):
                try:
                    with transaction.atomic():
                        run_fault()
                except IntegrityError as exc:  # the documented pattern
                    handled = exc
            else:
                try:
                    run_fault()
                except IntegrityError as exc:  # the pattern Django's docs warn against
                    handled = exc
            record["handled"] = common.error_dict(handled)
            django_state("after_fault")
            if arm != "nested-catch-no-b":
                write("B")
                django_state("after_write_b")

    outcome = common.call("atomic", body)
    record["outcome"] = outcome
    record["after_block"] = {
        "needs_rollback": connection.needs_rollback,
        "in_atomic_block": connection.in_atomic_block,
        "get_autocommit": connection.get_autocommit(),
        "sqlite_in_transaction": sqlite_state(),
    }
    record["trace"] = trace
    record["django"] = django.get_version()
    connection.close()
    return record


def scenario(fault: str, path_kind: str, arm: str) -> Callable[[Path, str], dict[str, Any]]:
    action = FAULTS[fault][0]

    def run(work: Path, token: str) -> dict[str, Any]:
        db = work / "db.sqlite"
        sink_path = work / "sink.sqlite"
        common.Sink(sink_path)
        sqlite01_raw.setup(db, action)
        proc = subprocess.run(
            [sys.executable, "-I", __file__, "--child", str(db), str(sink_path), token, fault, path_kind, arm],
            capture_output=True, text=True, timeout=120)
        try:
            doc = json.loads(proc.stdout)
        except json.JSONDecodeError:
            doc = {"stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
        q = sqlite01_raw.queries(token)
        final = common.observe(db, q)
        sink = common.Sink(sink_path).read(token)
        outcome = doc.get("outcome") or {}
        steps = {s["step"]: s for s in doc.get("steps", [])}

        def short(entry: dict[str, Any] | None) -> Any:
            if entry is None:
                return "not-run"
            if entry.get("status") == "ok":
                return "ok"
            return (entry.get("error") or {}).get("chain", [None])[0]

        observed = {
            "django": doc.get("django"),
            "handled": None if not doc.get("handled") else doc["handled"]["chain"][:2],
            "state_after_fault": doc.get("after_fault"),
            "write_b": short(steps.get("write B")),
            "atomic_outcome": short(outcome) if outcome else "child failed",
            "atomic_outcome_chain": (outcome.get("error") or {}).get("chain"),
            "after_block": doc.get("after_block"),
            "on_commit_ran": [row[0] for row in sink],
            "persisted": {k: final[k] for k in ("balances", "ledger")},
            "child_returncode": proc.returncode,
        }
        return {"observed": observed, "child": doc, "stderr_tail": proc.stderr.splitlines()[-5:]}

    return run


def main() -> None:
    variants = [
        (f"{fault}.{path_kind}.{arm}", scenario(fault, path_kind, arm))
        for fault in FAULTS
        for path_kind in PATHS
        for arm in ARMS
    ]
    common.run_experiment("sqlite06-django", variants)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        print(json.dumps(common.jsonable(child(*sys.argv[2:8]))))
    else:
        main()
