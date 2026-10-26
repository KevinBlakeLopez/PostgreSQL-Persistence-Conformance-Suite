"""CHK-16: Procrastinate's queueing lock inside the caller's transaction, with
AlreadyEnqueued ignored as its documentation allows.

    python procrastinate_queueing_lock.py

An order and its follow-up job commit together: the job recomputes the customer's stats,
and a per-customer queueing lock keeps at most one such job queued. On a repeat order,
while the first job is still queued, defer() raises AlreadyEnqueued and the code ignores
it. Each arm runs on its own connection (application_name chk16-<arm>); a repeat arm's
earlier order runs first, on its own connection (chk16-seed).

  django.first, django.repeat, django.repeat_savepoint
      Procrastinate's Django integration. Its connector runs on Django's connection, so
      the job is inserted inside the order's atomic() block.
  psycopg.first, psycopg.repeat, psycopg.repeat_savepoint
      Procrastinate's external-connection API, configure(connection=conn), on a psycopg
      connection, as in its documentation's example.

Prints what the code returned, whether the on_commit callback ran (Django only), and, from
a separate connection, pg_xact_status() of the transaction, whether the order is visible,
and how many jobs with the customer's queueing lock exist. Needs DATABASE_URL (a server's
postgres database). Creates database procrastinate_queueing_lock and drops it at the end.
"""

import itertools
import logging
import os
import sys
from urllib.parse import urlsplit

import psycopg
from psycopg.conninfo import make_conninfo

URL = os.environ["DATABASE_URL"]
DB = "procrastinate_queueing_lock"
DB_URL = make_conninfo(URL, dbname=DB)
with psycopg.connect(URL, autocommit=True, application_name="chk16-setup") as admin:
    admin.execute(f"drop database if exists {DB} with (force)")
    admin.execute(f"create database {DB}")

import django  # noqa: E402
from django.conf import settings  # noqa: E402

_url = urlsplit(URL)
settings.configure(
    DEBUG=False,
    USE_TZ=True,
    INSTALLED_APPS=["procrastinate.contrib.django"],
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB,
            "USER": _url.username,
            "PASSWORD": _url.password,
            "HOST": _url.hostname,
            "PORT": _url.port,
            "OPTIONS": {"application_name": "chk16-setup"},
        }
    },
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()

import procrastinate  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection, models, transaction  # noqa: E402
from importlib.metadata import version  # noqa: E402
from procrastinate import exceptions  # noqa: E402
from procrastinate.contrib.django import app  # noqa: E402

logging.basicConfig(stream=sys.stdout, level=logging.WARNING, format="  log %(levelname)s: %(message)s")
CALLBACKS = []  # on_commit callbacks that ran
XIDS = []  # pg_current_xact_id(), captured inside the transaction


class Order(models.Model):
    customer_id = models.IntegerField()

    class Meta:
        app_label = "shop"


# --- the application, on Procrastinate's Django integration ---------------------------


@app.task(name="recompute_customer_stats")
def recompute_customer_stats(customer_id): ...


def place_order(customer_id, savepoint=False):
    with transaction.atomic():
        order = Order.objects.create(customer_id=customer_id)
        with connection.cursor() as c:  # instrumentation: the transaction's ID
            c.execute("select pg_current_xact_id()::text")
            XIDS.append(c.fetchone()[0])
        transaction.on_commit(lambda: CALLBACKS.append(order.id))
        job = recompute_customer_stats.configure(queueing_lock=f"stats-{customer_id}")
        try:
            if savepoint:
                with transaction.atomic():
                    job.defer(customer_id=customer_id)
            else:
                job.defer(customer_id=customer_id)
        except exceptions.AlreadyEnqueued:
            pass  # one is already queued; the docs say this can be ignored
    return order.id


# --- the application, on the external-connection API ----------------------------------

ext_app = procrastinate.App(connector=procrastinate.SyncPsycopgConnector(conninfo=DB_URL))


@ext_app.task(name="recompute_customer_stats")
def recompute_customer_stats_ext(customer_id): ...


def place_order_psycopg(conn, customer_id, savepoint=False):
    order_id = conn.execute(
        "insert into shop_order (customer_id) values (%s) returning id", [customer_id]
    ).fetchone()[0]
    XIDS.append(conn.execute("select pg_current_xact_id()::text").fetchone()[0])  # instrumentation
    job = recompute_customer_stats_ext.configure(connection=conn, queueing_lock=f"stats-{customer_id}")
    try:
        if savepoint:
            with conn.transaction():
                job.defer(customer_id=customer_id)
        else:
            job.defer(customer_id=customer_id)
    except exceptions.AlreadyEnqueued:
        pass  # one is already queued; the docs say this can be ignored
    conn.commit()  # both the order and the job are committed together
    return order_id


# --- harness ---------------------------------------------------------------------------

CUSTOMERS = itertools.count(1)


def witness(xid, order_id, customer_id):
    with psycopg.connect(DB_URL, autocommit=True, application_name="chk16-witness") as w:
        fate = w.execute("select pg_xact_status(%s::xid8)::text", [xid]).fetchone()[0]
        visible = w.execute("select count(*) from shop_order where id = %s", [order_id]).fetchone()[0] == 1
        jobs = w.execute("select count(*) from procrastinate_jobs where queueing_lock = %s",
                         [f"stats-{customer_id}"]).fetchone()[0]
    return fate, visible, jobs


def django_call(customer, app_name, savepoint):
    connection.close()
    connection.settings_dict["OPTIONS"]["application_name"] = app_name
    try:
        return place_order(customer, savepoint=savepoint)
    finally:
        connection.close()  # the session ends with this order's transaction


def psycopg_call(customer, app_name, savepoint):
    with psycopg.connect(DB_URL, application_name=app_name) as conn:
        return place_order_psycopg(conn, customer, savepoint=savepoint)


def run(arm):
    kind, case = arm.split(".")
    call = django_call if kind == "django" else psycopg_call
    savepoint = case == "repeat_savepoint"
    customer = next(CUSTOMERS)
    if case != "first":  # the customer's earlier order queued the job
        call(customer, "chk16-seed", savepoint=False)
    CALLBACKS.clear()
    XIDS.clear()
    print(f"\n{arm}")
    try:
        outcome = f"returned order {call(customer, f'chk16-{arm}', savepoint)}"
    except Exception as e:  # noqa: BLE001 - reported
        outcome = f"raised {type(e).__name__}: {str(e).splitlines()[0]}"
    order_id = int(outcome.rsplit(" ", 1)[1]) if outcome.startswith("returned") else -1
    fate, visible, jobs = witness(XIDS[0], order_id, customer)
    ran = bool(CALLBACKS) if kind == "django" else "-"
    print(f"  code: {outcome}; on_commit ran {ran}")
    print(f"  witness: pg_xact_status({XIDS[0]}) {fate}, order visible {visible}, queued jobs for the customer {jobs}")


def main():
    print(f"procrastinate {version('procrastinate')}, Django {django.get_version()}, psycopg {psycopg.__version__}")
    call_command("migrate", verbosity=0)  # Procrastinate's schema, through its Django migrations
    with connection.schema_editor() as editor:
        editor.create_model(Order)
    connection.close()
    ext_app.open()
    for arm in ("django.first", "django.repeat", "django.repeat_savepoint",
                "psycopg.first", "psycopg.repeat", "psycopg.repeat_savepoint"):
        run(arm)
    ext_app.close()
    with psycopg.connect(URL, autocommit=True, application_name="chk16-setup") as admin:
        admin.execute(f"drop database {DB} with (force)")


main()
