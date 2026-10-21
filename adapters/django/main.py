# PPCS adapter for Django 6.1. Speaks protocol version 1 on stdin/stdout.
# node-kit is not imported. Category C faults are injected in this process,
# before psycopg sends the statement, the way adapters/sqlalchemy/main.py
# withholds ROLLBACK TO SAVEPOINT.

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "production-reachability" / "py"))
from pr01 import run_pr  # noqa: E402
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

PROTOCOL = 1
ROLLBACK_TO = re.compile(r"^rollback to (savepoint )?", re.IGNORECASE)

# django/db/transaction.py Atomic.__exit__, and docs/topics/db/transactions.txt.
# Commit only when the block exits with no exception and needs_rollback is false.
# A savepoint rollback that raises django.db.Error sets needs_rollback and does
# not replace the original exception. A root rollback that raises django.db.Error
# is swallowed and connection.close() is called. An exception that is not
# django.db.Error is not caught there, so needs_rollback stays false.
CONTRACT = (
    'Django documents transaction.atomic() as: "If the block of code is successfully '
    "completed, the changes are committed to the database. If there is an exception, the "
    'changes are rolled back." Atomic.__exit__ commits only when exc_type is None and '
    "needs_rollback is false; otherwise it rolls back (django/db/transaction.py). "
    "A savepoint rollback that raises django.db.Error sets needs_rollback and does not "
    "replace the original exception. A root rollback that raises django.db.Error is "
    "swallowed and connection.close() is called. An exception that is not django.db.Error "
    "is not caught, so needs_rollback stays false. "
    'The DatabaseError admonition says: "After such an error, the transaction is broken '
    'and Django will perform a rollback at the end of the atomic block." '
    "Model.save uses mark_for_rollback_on_error, which sets needs_rollback when a database "
    "error is raised inside an atomic block."
)

# docs/ref/databases.txt, Persistent connections. close_old_connections is what
# request_started and request_finished call. close_if_unusable_or_obsolete drops
# a connection whose autocommit was not restored.
CONTRACT_REUSE = (
    CONTRACT
    + " Persistent connections: the default CONN_MAX_AGE is 0, which closes the "
    "connection at the end of each request. CONN_MAX_AGE None keeps it with no maximum "
    "age (docs/ref/databases.txt). At the end of a request, close_old_connections calls "
    "close_if_unusable_or_obsolete. That method closes the connection when autocommit "
    "was not restored: \"If the application didn't restore the original autocommit "
    'setting, don\'t take chances, drop the connection" (django/db/backends/base/base.py).'
)


class ProtocolError(Exception):
    pass


class AppError(Exception):
    pass


@dataclass
class ExitTrace:
    commit_calls: int = 0
    rollback_calls: int = 0
    commit_error: BaseException | None = None
    rollback_error: BaseException | None = None

    def snapshot(self) -> "ExitTrace":
        return ExitTrace(
            self.commit_calls,
            self.rollback_calls,
            self.commit_error,
            self.rollback_error,
        )

    def reset(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.commit_error = None
        self.rollback_error = None


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


fault = Fault()
exit_trace = ExitTrace()
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


def sqlstate(exc: BaseException | None) -> str | None:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        state = getattr(cur, "sqlstate", None) or getattr(cur, "pgcode", None)
        if isinstance(state, str) and state:
            return state
        cur = cur.__cause__ or cur.__context__
    return None


def raise_if_protocol(exc: BaseException) -> None:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ProtocolError):
            raise cur
        cur = cur.__cause__ or cur.__context__


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


def install_patches() -> None:
    """Observe Django's commit and rollback, and withhold a root ROLLBACK once.

    Savepoint SQL goes through the cursor, so the execute wrapper sees it.
    A top-level ROLLBACK is connection.rollback(), which never reaches that wrapper.
    """
    global _patched
    if _patched:
        return
    import psycopg
    from django.db.backends.base.base import BaseDatabaseWrapper

    original_rollback = psycopg.Connection.rollback
    original_commit = BaseDatabaseWrapper._commit
    original_rollback_wrap = BaseDatabaseWrapper._rollback

    def patched_rollback(self: Any) -> None:
        if fault.kind == "root" and fault.armed:
            fault.armed = False
            fault.fired += 1
            fault.withheld.append("ROLLBACK")
            fault.trace.append("ROLLBACK  -- WITHHELD before send")
            checkpoint("after-fault", {"pid": fault.pid})
            raise RuntimeError("injected client-side failure: ROLLBACK was not sent")
        return original_rollback(self)

    def patched_commit(self: Any) -> Any:
        exit_trace.commit_calls += 1
        try:
            return original_commit(self)
        except Exception as exc:
            exit_trace.commit_error = exc
            raise

    def patched_rollback_wrap(self: Any) -> Any:
        exit_trace.rollback_calls += 1
        try:
            return original_rollback_wrap(self)
        except Exception as exc:
            exit_trace.rollback_error = exc
            raise

    psycopg.Connection.rollback = patched_rollback  # type: ignore[method-assign]
    BaseDatabaseWrapper._commit = patched_commit  # type: ignore[method-assign]
    BaseDatabaseWrapper._rollback = patched_rollback_wrap  # type: ignore[method-assign]
    _patched = True


def cursor_gate(execute: Callable[..., Any], sql: Any, params: Any, many: bool, context: Any) -> Any:
    text = " ".join(str(sql).split())
    if fault.kind == "savepoint" and fault.armed and ROLLBACK_TO.match(text):
        if fault.mode_name == "client-reject":
            fault.armed = False
            fault.fired += 1
            fault.withheld.append(text)
            fault.trace.append(f"{text}  -- WITHHELD before send")
            checkpoint("after-fault", {"pid": fault.pid})
            raise RuntimeError(
                "injected client-side failure: ROLLBACK TO SAVEPOINT was not sent"
            )
        if fault.mode_name == "rewrite":
            fault.armed = False
            fault.fired += 1
            rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint"
            fault.withheld.append(text)
            fault.rewritten.append(rewritten)
            fault.trace.append(f"{rewritten}  -- REWRITE of: {text}")
            try:
                return execute(rewritten, params, many, context)
            except Exception as exc:
                fault.reply_codes.append(sqlstate(exc) or "error")
                checkpoint("after-fault", {"pid": fault.pid})
                raise
    fault.trace.append(text)
    return execute(sql, params, many, context)


_migration_root: str | None = None

MIGRATION_CONTRACT = (
    "Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration "
    "runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in "
    "that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards "
    "transaction commits. The executor takes no advisory lock. RunPython without a reverse callable is not reversible: "
    "unapply raises IrreversibleError and does not record the migration as unapplied."
)
MIGRATION_FORM = (
    "MigrationExecutor.migrate on a generated ppcs_mg.0001_m1 RunPython migration. "
    "forwards inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock in that transaction."
)


def migration_source(marker: str, gate: int, hold: bool, reversal: str) -> str:
    reverse = ""
    if reversal == "valid":
        reverse = """

def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM item WHERE name = %s", [MARKER])
    schema_editor.execute("INSERT INTO ppcs_undo (name) VALUES (%s)", [MARKER])
"""
        operation = "migrations.RunPython(forwards, backwards)"
    elif reversal == "partial-then-error":
        reverse = """

def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM item WHERE name = %s", [MARKER])
    schema_editor.execute("INSERT INTO ppcs_undo (name) VALUES (%s)", [MARKER])
    raise RuntimeError("the reversal failed on purpose after deleting the marker")
"""
        operation = "migrations.RunPython(forwards, backwards)"
    else:
        operation = "migrations.RunPython(forwards)"
    return f"""from django.db import migrations

MARKER = {json.dumps(marker)}
GATE = {gate}
HOLD = {hold!r}

def forwards(apps, schema_editor):
    schema_editor.execute("INSERT INTO item (name) VALUES (%s)", [MARKER])
    if HOLD:
        schema_editor.execute("SELECT pg_advisory_xact_lock(%s)", [GATE])
{reverse}
class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        {operation},
    ]
"""


def prepare_migration_app(message: dict[str, Any]) -> list[str]:
    global _migration_root
    mig = message.get("migration") or {}
    root = tempfile.mkdtemp(prefix="ppcs-django-mg-")
    _migration_root = root
    package = Path(root) / "ppcs_mg"
    migrations = package / "migrations"
    migrations.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (migrations / "__init__.py").write_text("")
    (migrations / "0001_m1.py").write_text(
        migration_source(
            message["markers"]["m1"],
            int(mig.get("gate") or 0),
            mig.get("hold") is True,
            mig.get("reversal") or "valid",
        )
    )
    sys.path.insert(0, root)
    return ["ppcs_mg"]


def configure(message: dict[str, Any]) -> None:
    import django
    from django.conf import settings

    mode = message.get("mode")
    if mode not in ("native", "persistent"):
        raise RuntimeError(f'unknown mode "{mode}"')
    conn = message["connection"]
    if not settings.configured:
        options: dict[str, Any] = {"application_name": conn["application_name"]}
        if conn.get("options"):
            options["options"] = conn["options"]
        apps = ["djapp"]
        if str(message.get("case", {}).get("family", "")).startswith("MG-"):
            apps = prepare_migration_app(message)
        settings.configure(
            SECRET_KEY="ppcs-django-adapter",
            DEBUG=False,
            USE_TZ=False,
            DEFAULT_AUTO_FIELD="django.db.models.AutoField",
            INSTALLED_APPS=apps,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": conn["database"],
                    "USER": conn["user"],
                    "PASSWORD": conn["password"],
                    "HOST": conn["host"],
                    "PORT": str(conn["port"]),
                    "CONN_MAX_AGE": None if mode == "persistent" else 0,
                    "CONN_HEALTH_CHECKS": False,
                    "AUTOCOMMIT": True,
                    "OPTIONS": options,
                }
            },
        )
        django.setup()
    install_patches()


def identify(*, isolation: bool = False) -> dict[str, Any]:
    from django.db import connection

    sql = (
        "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
        if isolation
        else "select pg_current_xact_id()::text, pg_backend_pid()"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
    xid, pid = row[0], row[1]
    fault.pid = int(pid)
    out: dict[str, Any] = {"xid": str(xid), "pid": int(pid)}
    if isolation:
        out["transaction_isolation"] = row[2]
    return out


def backend_pid() -> int | None:
    from django.db import connection

    raw = connection.connection
    if raw is None:
        return None
    return int(raw.info.backend_pid)


def sleep_ms(settings: dict[str, Any]) -> None:
    time.sleep((settings.get("settle_ms") or 100) / 1000)


def map_exit(snap: ExitTrace, escaped: BaseException | None, caught: BaseException | None, contract: str) -> dict[str, Any]:
    if escaped is not None:
        raise_if_protocol(escaped)
        same = caught is not None and (
            escaped is caught or escaped.__cause__ is caught or escaped.__context__ is caught
        )
        if same and caught is not None:
            return {
                "reported": "rolled_back",
                "basis": "atomic() exited with the exception raised inside it, so Atomic.__exit__ rolled back",
                "contract": contract,
                "api_error": err_info(caught),
            }
        return {
            "reported": "failed",
            "basis": "atomic() exited with an error the block did not raise",
            "contract": contract,
            "api_error": err_info(escaped),
        }
    if snap.rollback_calls and not snap.commit_calls:
        if snap.rollback_error is None:
            observed = caught or RuntimeError("rollback without a captured error")
            return {
                "reported": "rolled_back",
                "basis": "atomic() returned without raising; Atomic.__exit__ called rollback() and it completed",
                "contract": contract,
                "api_error": err_info(observed),
            }
        return {
            "reported": "failed",
            "basis": "atomic() returned without raising; rollback() raised and Atomic.__exit__ dropped the connection",
            "contract": contract,
            "api_error": err_info(snap.rollback_error),
        }
    if snap.commit_calls and snap.commit_error is None:
        return {
            "reported": "committed",
            "basis": "atomic() returned without raising; Atomic.__exit__ called commit()",
            "contract": contract,
        }
    if snap.commit_error is not None:
        return {
            "reported": "failed",
            "basis": "atomic() returned without raising after commit() raised",
            "contract": contract,
            "api_error": err_info(snap.commit_error),
        }
    return {
        "reported": "failed",
        "basis": "atomic() returned without raising, and neither commit() nor rollback() was observed",
        "contract": contract,
        "api_error": err_info(RuntimeError("no commit or rollback observed")),
    }


def run_atomic(body: Callable[[], BaseException | None]) -> dict[str, Any]:
    from django.db.transaction import atomic

    exit_trace.reset()
    thrown: BaseException | None = None
    returned: BaseException | None = None
    try:
        with atomic():
            try:
                returned = body()
            except Exception as exc:
                thrown = exc
                raise
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        return map_exit(exit_trace.snapshot(), exc, thrown, CONTRACT)
    caught = returned if isinstance(returned, BaseException) else None
    return map_exit(exit_trace.snapshot(), None, caught, CONTRACT)


def case_commit(message: dict[str, Any]) -> dict[str, Any]:
    from djapp.models import Item

    def body() -> None:
        Item.objects.create(name=message["markers"]["tx"], qty=0)
        checkpoint("before-end", identify())
        return None

    return run_atomic(body)


def case_rollback(message: dict[str, Any]) -> dict[str, Any]:
    from djapp.models import Item

    def body() -> None:
        Item.objects.create(name=message["markers"]["tx"], qty=0)
        checkpoint("before-end", identify())
        raise AppError("application error: the request fails")

    return run_atomic(body)


def case_caught_error(message: dict[str, Any]) -> dict[str, Any]:
    from django.db import IntegrityError

    from djapp.models import Item, Uniq

    violation: BaseException | None = None

    def body() -> BaseException | None:
        nonlocal violation
        Item.objects.create(name=message["markers"]["tx"], qty=0)
        ident = identify()
        checkpoint("after-write", ident)
        try:
            Uniq.objects.create(code="taken")
        except IntegrityError as exc:
            violation = exc
        checkpoint("before-end", {"pid": ident["pid"]})
        return violation

    outcome = run_atomic(body)
    if violation is None:
        raise RuntimeError("the duplicate insert did not raise IntegrityError")
    outcome["steps"] = {"violation": err_info(violation)}
    return outcome


def case_conn_lost_before_commit(message: dict[str, Any]) -> dict[str, Any]:
    from djapp.models import Item

    def body() -> None:
        Item.objects.create(name=message["markers"]["tx"], qty=0)
        checkpoint("before-end", identify())
        sleep_ms(message["case"].get("settings") or {})
        return None

    return run_atomic(body)


def case_savepoint(message: dict[str, Any], kind: str) -> dict[str, Any]:
    from django.db.transaction import atomic

    from djapp.models import Item

    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False}
    pid: int | None = None
    caught: BaseException | None = None
    exit_trace.reset()
    escaped: BaseException | None = None
    try:
        with atomic():
            Item.objects.create(name=markers["outer"], qty=0)
            ident = identify()
            pid = ident["pid"]
            checkpoint("outer-after-write", ident)
            try:
                with atomic():
                    Item.objects.create(name=markers["inner"], qty=0)
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
                caught = exc
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        escaped = exc
    checkpoint("after-outer", {"pid": pid})
    outcome = map_exit(exit_trace.snapshot(), escaped, caught, CONTRACT)
    steps: dict[str, Any] = {"nested": nested}
    if kind != "conn-lost":
        steps["fault"] = fault_report()
    outcome["steps"] = steps
    return outcome


def case_reuse(message: dict[str, Any], kind: str) -> dict[str, Any]:
    from django.db import IntegrityError, close_old_connections, connection
    from django.db.transaction import atomic

    from djapp.models import Item, Uniq

    markers = message["markers"]
    settings = message["case"].get("settings") or {}
    violation: BaseException | None = None
    exit_trace.reset()
    escaped: BaseException | None = None
    unit1_pid: int | None = None
    try:
        with atomic():
            Item.objects.create(name=markers["doomed"], qty=0)
            ident = identify()
            unit1_pid = ident["pid"]
            checkpoint("unit1-after-write", ident)
            if kind == "conn-lost":
                sleep_ms(settings)
            else:
                fault.kind = "root"
                fault.mode_name = "client-reject"
                fault.armed = True
            if kind == "statement-error":
                try:
                    Uniq.objects.create(code="taken")
                except IntegrityError as exc:
                    violation = exc
                    raise
            raise AppError("application error: unit 1 fails")
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        escaped = exc

    unit1_trace = exit_trace.snapshot()
    fault.armed = False
    fault.kind = None
    autocommit_before = None
    if connection.connection is not None:
        autocommit_before = connection.get_autocommit()
    pid_before_close = backend_pid()
    close_old_connections()
    closed = connection.connection is None
    checkpoint("after-unit1", {"pid": unit1_pid})

    exit_trace.reset()
    started = time.monotonic()
    unit2_escaped: BaseException | None = None
    unit2_pid: int | None = None
    try:
        with atomic():
            Item.objects.create(name=markers["next"], qty=0)
            unit2_ident = identify()
            unit2_pid = unit2_ident["pid"]
            checkpoint("unit2-after-write", unit2_ident)
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        unit2_escaped = exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    unit2 = {
        "outcome": "completed",
        "elapsed_ms": elapsed_ms,
        **map_exit(exit_trace.snapshot(), unit2_escaped, None, CONTRACT_REUSE),
    }
    if escaped is None:
        outcome = {
            "reported": "failed",
            "basis": "unit 1's atomic() returned without raising, which this fault does not expect",
            "contract": CONTRACT_REUSE,
            "api_error": err_info(RuntimeError("unit 1 did not raise")),
        }
    elif isinstance(escaped, AppError):
        outcome = map_exit(unit1_trace, escaped, escaped, CONTRACT_REUSE)
    else:
        outcome = map_exit(unit1_trace, escaped, None, CONTRACT_REUSE)
    steps: dict[str, Any] = {
        "unit2": unit2,
        "unit1_exit": {
            "commit_calls": unit1_trace.commit_calls,
            "rollback_calls": unit1_trace.rollback_calls,
            "commit_error": err_info(unit1_trace.commit_error) if unit1_trace.commit_error else None,
            "rollback_error": err_info(unit1_trace.rollback_error) if unit1_trace.rollback_error else None,
        },
        "reuse": {
            "unit1_pid": unit1_pid,
            "pid_before_close": pid_before_close,
            "autocommit_before_close": autocommit_before,
            "closed_by_request_finished": closed,
            "unit2_pid": unit2_pid,
            "same_backend": unit1_pid is not None and unit2_pid == unit1_pid,
        },
    }
    if violation is not None:
        steps["violation"] = err_info(violation)
    if kind != "conn-lost":
        steps["fault"] = fault_report()
    outcome["steps"] = steps
    return outcome


# OPTIONS isolation_level is applied in get_new_connection, before autocommit
# (django/db/backends/postgresql/base.py). atomic() and set_autocommit() take
# no isolation argument. https://docs.djangoproject.com/en/6.1/ref/databases/#isolation-level
TX04_FORM = (
    "Outer transaction.atomic() and a nested transaction.atomic(). The nested "
    "block is a savepoint. Model.objects.create sends each INSERT when it is called."
)
TX05_MANAGED_FORM = (
    "DATABASES OPTIONS isolation_level is psycopg.IsolationLevel.SERIALIZABLE, "
    "applied when the connection is opened. The managed case then calls transaction.atomic(). "
    "atomic() takes no isolation argument."
)
TX05_EXPLICIT_FORM = (
    "DATABASES OPTIONS isolation_level is psycopg.IsolationLevel.SERIALIZABLE, "
    "applied when the connection is opened. The explicit case then calls set_autocommit(False) "
    "and transaction.commit(). Those methods take no isolation argument."
)
DJANGO_ISOLATION = (
    CONTRACT
    + " The isolation level is DATABASES OPTIONS isolation_level, a psycopg.IsolationLevel "
    "set before the connection is opened. transaction.atomic() takes no isolation argument."
)
DJANGO_EXPLICIT_ISOLATION = (
    "Django documents manual transaction management beside atomic(): set_autocommit(False), "
    "then commit() or rollback(), then set_autocommit(True). "
    "The isolation level is DATABASES OPTIONS isolation_level, a psycopg.IsolationLevel "
    "set before the connection is opened. set_autocommit() and commit() take no isolation argument."
)


def set_connection_isolation(level: str | None) -> None:
    import psycopg
    from django.conf import settings
    from django.db import connections

    wrapper = connections["default"]
    wrapper.close()
    options = wrapper.settings_dict["OPTIONS"]
    configured = settings.DATABASES["default"]["OPTIONS"]
    if level is None:
        options.pop("isolation_level", None)
        configured.pop("isolation_level", None)
        return
    mapped = {
        "read uncommitted": psycopg.IsolationLevel.READ_UNCOMMITTED,
        "read committed": psycopg.IsolationLevel.READ_COMMITTED,
        "repeatable read": psycopg.IsolationLevel.REPEATABLE_READ,
        "serializable": psycopg.IsolationLevel.SERIALIZABLE,
    }.get(level)
    if mapped is None:
        raise ProtocolError(f"the case requests an unknown isolation level: {json.dumps(level)}")
    options["isolation_level"] = mapped
    configured["isolation_level"] = mapped


def read_marker(name: str) -> None:
    from djapp.models import Item

    got = Item.objects.filter(name=name).values_list("name", flat=True).get()
    if got != name:
        raise RuntimeError("the marker read did not return the written value")


def level_work(message: dict[str, Any], checkpoint_name: str, *, with_isolation: bool) -> None:
    from djapp.models import Item

    marker = message["markers"]["tx"]
    Item.objects.create(name=marker, qty=0)
    read_marker(marker)
    checkpoint(checkpoint_name, identify(isolation=with_isolation))


def case_nested(message: dict[str, Any], variant: str) -> dict[str, Any]:
    from django.db.transaction import atomic

    from djapp.models import Item

    markers = message["markers"]
    nested: dict[str, Any] = {"caught": False, "completed": False}
    exit_trace.reset()
    escaped: BaseException | None = None
    outer_error: BaseException | None = None
    try:
        with atomic():
            Item.objects.create(name=markers["outer"], qty=0)
            try:
                with atomic():
                    Item.objects.create(name=markers["inner"], qty=0)
                    checkpoint("inner-after-write", identify())
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
                outer_error = AppError("application error: the outer scope fails")
                raise outer_error
    except ProtocolError:
        raise
    except Exception as exc:
        raise_if_protocol(exc)
        escaped = exc
    outcome = map_exit(
        exit_trace.snapshot(),
        escaped,
        outer_error if escaped is outer_error else None,
        CONTRACT,
    )
    outcome["steps"] = {"nested": nested}
    outcome["form"] = TX04_FORM
    return outcome


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


def case_managed_serializable(message: dict[str, Any]) -> dict[str, Any]:
    level = (message["case"].get("settings") or {}).get("isolation_level")
    state = {"started": False}

    def attempt() -> dict[str, Any]:
        set_connection_isolation(level if isinstance(level, str) else None)
        if not isinstance(level, str):
            raise ProtocolError(f"the case requests an unknown isolation level: {json.dumps(level)}")

        def body() -> None:
            state["started"] = True
            level_work(message, "after-read", with_isolation=True)
            return None

        outcome = run_atomic(body)
        outcome["contract"] = DJANGO_ISOLATION
        return outcome

    def plain() -> None:
        set_connection_isolation(None)

        def body() -> None:
            checkpoint("baseline", identify())
            return None

        outcome = run_atomic(body)
        if outcome.get("reported") != "committed":
            raise RuntimeError(outcome.get("basis") or "the plain transaction did not commit")

    return _requested_level(attempt, plain, state, TX05_MANAGED_FORM)


def case_explicit_serializable(message: dict[str, Any]) -> dict[str, Any]:
    from django.db import transaction

    level = (message["case"].get("settings") or {}).get("isolation_level")
    state = {"started": False}

    def attempt() -> dict[str, Any]:
        set_connection_isolation(level if isinstance(level, str) else None)
        if not isinstance(level, str):
            raise ProtocolError(f"the case requests an unknown isolation level: {json.dumps(level)}")
        opened = False
        try:
            transaction.set_autocommit(False)
            opened = True
            state["started"] = True
            level_work(message, "after-read", with_isolation=True)
            transaction.commit()
            return {
                "reported": "committed",
                "basis": "transaction.commit() returned",
                "contract": DJANGO_EXPLICIT_ISOLATION,
            }
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            if opened:
                try:
                    transaction.rollback()
                except Exception:
                    pass
            return {
                "reported": "failed",
                "basis": "set_autocommit(False) or transaction.commit() raised",
                "contract": DJANGO_EXPLICIT_ISOLATION,
                "api_error": err_info(exc),
            }
        finally:
            if opened:
                transaction.set_autocommit(True)

    def plain() -> None:
        set_connection_isolation(None)
        transaction.set_autocommit(False)
        try:
            checkpoint("baseline", identify())
            transaction.commit()
        finally:
            transaction.set_autocommit(True)

    return _requested_level(attempt, plain, state, TX05_EXPLICIT_FORM)


DJANGO_EXPLICIT = (
    "Django documents manual transaction management beside atomic(): set_autocommit(False), "
    "then commit() or rollback(), then set_autocommit(True) "
    "(docs/topics/db/transactions.txt, Controlling transactions explicitly). "
    "commit() is Django's report that it asked the database to commit."
)


def _is_protocol(exc: BaseException) -> bool:
    try:
        raise_if_protocol(exc)
    except ProtocolError:
        return True
    return False


def _django_pr(kind: str, message: dict[str, Any]) -> dict[str, Any]:
    from django.db import IntegrityError, connection, transaction

    from djapp.models import Item, Uniq

    hooks = {"on_commit": 0}

    def on_start(_handle: Any) -> None:
        transaction.on_commit(lambda: hooks.__setitem__("on_commit", hooks["on_commit"] + 1))

    def write(_handle: Any, name: str) -> None:
        Item.objects.create(name=name, qty=0)

    def insert_taken(_handle: Any) -> None:
        Uniq.objects.create(code="taken")

    def savepoint(_handle: Any) -> dict[str, Any]:
        try:
            with transaction.atomic():
                Uniq.objects.create(code="taken")
        except IntegrityError as exc:
            return {"recovered": True, "violation": err_info(exc)}
        raise RuntimeError("the duplicate insert did not raise")

    def managed(work: Callable[[Any], None]) -> dict[str, Any]:
        return run_atomic(lambda: work(None))

    def explicit(work: Callable[[Any], None]) -> dict[str, Any]:
        transaction.set_autocommit(False)
        thrown: BaseException | None = None
        try:
            try:
                work(None)
            except Exception as exc:
                raise_if_protocol(exc)
                thrown = exc
                raise
            transaction.commit()
            return {"reported": "committed", "basis": "transaction.commit() returned", "contract": DJANGO_EXPLICIT}
        except ProtocolError:
            raise
        except Exception as exc:
            raise_if_protocol(exc)
            try:
                transaction.rollback()
            except Exception:
                pass
            if thrown is not None and exc is thrown:
                return {
                    "reported": "rolled_back",
                    "basis": "the body threw and transaction.rollback() was called",
                    "contract": DJANGO_EXPLICIT,
                    "api_error": err_info(thrown),
                }
            return {
                "reported": "failed",
                "basis": "transaction.commit() raised",
                "contract": DJANGO_EXPLICIT,
                "api_error": err_info(exc),
            }
        finally:
            transaction.set_autocommit(True)

    def probe() -> dict[str, Any]:
        try:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
            return {
                "supported": True,
                "ok": True,
                "error": None,
                "needs_rollback": connection.needs_rollback,
                "backend_pid": backend_pid(),
            }
        except Exception as exc:
            if _is_protocol(exc):
                raise
            return {"supported": True, "ok": False, "error": err_info(exc), "needs_rollback": connection.needs_rollback}

    def reuse(name: str, cp: Callable[..., Any]) -> dict[str, Any]:
        started = time.monotonic()
        box: dict[str, int | None] = {"pid": None}

        def body() -> None:
            Item.objects.create(name=name, qty=0)
            ident = identify()
            box["pid"] = ident["pid"]
            cp("reuse-after-write", ident)

        try:
            outcome = run_atomic(body)
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
        "managed": "with transaction.atomic(): catch IntegrityError, then leave the block.",
        "explicit": "set_autocommit(False), catch IntegrityError, transaction.commit(), set_autocommit(True).",
        "control": "with transaction.atomic(): IntegrityError leaves the block.",
        "savepoint": "with transaction.atomic(): a nested atomic() around the duplicate. The nested IntegrityError is caught and the outer block returns.",
    }
    return run_pr(
        kind,
        message,
        checkpoint,
        boundary=explicit if kind == "explicit" else managed,
        write=write,
        insert_taken=insert_taken,
        identify=lambda _handle: identify(),
        reuse=reuse,
        err_info=err_info,
        is_protocol=_is_protocol,
        savepoint=savepoint,
        probe=probe,
        hooks=lambda: {"supported": True, "on_commit": hooks["on_commit"], "needs_rollback": connection.needs_rollback},
        on_start=None if kind == "explicit" else on_start,
        form=forms[kind],
    )


CASES = {
    "CTL-01.commit": case_commit,
    "CTL-01.rollback": case_rollback,
    "TX-01A.caught-error-then-commit": case_caught_error,
    "PR-01.managed-catch-commit": lambda message: _django_pr("managed", message),
    "PR-01.explicit-catch-commit": lambda message: _django_pr("explicit", message),
    "PR-01.uncaught-control": lambda message: _django_pr("control", message),
    "PR-01.savepoint-recovery": lambda message: _django_pr("savepoint", message),
    "TX-01B.conn-lost-before-commit": case_conn_lost_before_commit,
    "TX-02.savepoint-rollback-not-sent": lambda message: case_savepoint(message, "not-sent"),
    "TX-02.savepoint-rollback-rejected": lambda message: case_savepoint(message, "rejected"),
    "TX-02.conn-lost-before-savepoint-rollback": lambda message: case_savepoint(message, "conn-lost"),
    "TX-03.rollback-not-sent": lambda message: case_reuse(message, "rollback-not-sent"),
    "TX-03.statement-error-rollback-not-sent": lambda message: case_reuse(message, "statement-error"),
    "TX-03.conn-lost-in-transaction": lambda message: case_reuse(message, "conn-lost"),
    "TX-04.nested-failure-contained": lambda message: case_nested(message, "nested-fails"),
    "TX-04.nested-released-outer-rollback": lambda message: case_nested(message, "outer-fails"),
    "TX-05.managed-serializable": case_managed_serializable,
    "TX-05.explicit-serializable": case_explicit_serializable,
    "MG-02.held": lambda message: case_migrate(message),
    "MG-02.first-deployment": lambda message: case_migrate(message),
    "MG-02.session-loss": lambda message: case_migrate(message),
    "MG-02.idle-session-timeout": lambda message: case_migrate(message),
    "MG-03.valid-reversal": lambda message: case_migrate(message),
    "MG-03.no-reversal": lambda message: case_migrate(message),
    "MG-03.failing-reversal": lambda message: case_migrate(message),
}


def case_migrate(message: dict[str, Any]) -> dict[str, Any]:
    from django.db import connections
    from django.db.migrations.executor import MigrationExecutor

    operation = (message.get("migration") or {}).get("operation")
    executor = MigrationExecutor(connections["default"])
    target = [("ppcs_mg", None)] if operation == "revert" else [("ppcs_mg", "0001_m1")]
    try:
        plan = executor.migration_plan(target)
        if not plan:
            reported = "nothing_to_do"
            basis = "MigrationExecutor.migration_plan was empty"
        else:
            executor.migrate(target)
            reported = "reverted" if operation == "revert" else "applied"
            basis = "MigrationExecutor.migrate returned"
        return {
            "reported": reported,
            "exit_code": 0,
            "basis": basis,
            "contract": MIGRATION_CONTRACT,
            "form": MIGRATION_FORM,
        }
    except Exception as exc:
        raise_if_protocol(exc)
        return {
            "reported": "failed",
            "exit_code": 1,
            "basis": "MigrationExecutor.migrate raised",
            "contract": MIGRATION_CONTRACT,
            "form": MIGRATION_FORM,
            "api_error": err_info(exc),
        }


def diagnostics() -> dict[str, Any]:
    from django.db import connection

    raw = connection.connection
    return {
        "trace": fault.trace,
        "withheld": fault.withheld,
        "rewritten": fault.rewritten,
        "reply_codes": fault.reply_codes,
        "commit_calls": exit_trace.commit_calls,
        "rollback_calls": exit_trace.rollback_calls,
        "django": {
            "needs_rollback": connection.needs_rollback,
            "in_atomic_block": connection.in_atomic_block,
            "closed_in_transaction": connection.closed_in_transaction,
            "autocommit": connection.get_autocommit() if raw is not None else None,
            "backend_pid": int(raw.info.backend_pid) if raw is not None else None,
        },
        "trace_sees_framework_statements": any(
            sql.startswith("INSERT") or sql.startswith("SAVEPOINT") or "WITHHELD" in sql or "REWRITE" in sql
            for sql in fault.trace
        ),
    }


def run() -> None:
    import django
    import psycopg
    from django.db import connection, connections

    message = read_message()
    if message.get("type") != "case":
        raise ProtocolError(f'expected a case message, got "{message.get("type")}"')
    mode = message.get("mode")
    try:
        configure(message)
    except Exception as exc:
        send(
            {
                "type": "hello",
                "adapter": {"name": "django", "version": "0.1.0"},
                "framework": {"name": "django", "version": None},
                "driver": {"name": "psycopg", "version": psycopg.__version__},
                "components": {},
                "runtime": {"name": "python", "version": sys.version.split()[0]},
                "mode": mode,
                "configuration": {},
            }
        )
        send(
            {
                "type": "result",
                "status": "error",
                "error": {**err_info(exc), "protocol": isinstance(exc, ProtocolError)},
                "diagnostics": {},
            }
        )
        return

    send(
        {
            "type": "hello",
            "adapter": {"name": "django", "version": "0.1.0"},
            "framework": {"name": "django", "version": django.get_version()},
            "driver": {"name": "psycopg", "version": psycopg.__version__},
            "components": {},
            "runtime": {"name": "python", "version": sys.version.split()[0]},
            "mode": mode,
            "configuration": {
                "CONN_MAX_AGE": None if mode == "persistent" else 0,
                "pool": False,
                "request_boundary": "django.db.close_old_connections" if mode == "persistent" else None,
            },
        }
    )
    try:
        impl = CASES.get(message["case"]["id"])
        if impl is None:
            result: dict[str, Any] = {
                "status": "not_implemented",
                "reason": f'this adapter does not implement {message["case"]["id"]}',
            }
        else:
            with connection.execute_wrapper(cursor_gate):
                outcome = impl(message)
            checkpoint("after-end", {})
            result = {"status": "completed", **outcome}
    except Exception as exc:
        result = {
            "status": "error",
            "error": {**err_info(exc), "protocol": isinstance(exc, ProtocolError)},
        }
    result["diagnostics"] = diagnostics()
    try:
        connections.close_all()
    except Exception:
        pass
    if _migration_root is not None:
        shutil.rmtree(_migration_root, ignore_errors=True)
    send({"type": "result", **result})


if __name__ == "__main__":
    try:
        run()
    except ProtocolError as exc:
        send(
            {
                "type": "result",
                "status": "error",
                "error": {**err_info(exc), "protocol": True},
                "diagnostics": {},
            }
        )
    raise SystemExit(0)
