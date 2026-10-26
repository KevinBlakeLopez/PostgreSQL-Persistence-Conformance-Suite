"""CHK-12: a raw-SQL error caught inside Django's atomic(), then Django's commit.

    python django_raw_sql.py off|on

off: ATOMIC_REQUESTS off, and the view opens atomic().
on:  ATOMIC_REQUESTS on, and the view opens atomic() too (a savepoint) or does not.

Each arm sends one request through Django's request handling (django.test.Client),
on its own connection (application_name chk12-<arm>). The view creates an order, captures
pg_current_xact_id(), registers an on_commit callback, and records an analytics event
through a best-effort helper that catches DatabaseError: through the ORM, or in raw SQL.
The event name fits shop_event.name (varchar(32)) or is too long for it.

Prints what Django returned, whether the on_commit callback ran, and, from a separate
connection, pg_xact_status() of the transaction and whether the order is visible.
Needs DATABASE_URL (a server's postgres database). Creates database django_raw_sql and
drops it at the end.
"""

import json
import logging
import os
import secrets
import sys
from urllib.parse import urlsplit

import psycopg

MODE = sys.argv[1] if len(sys.argv) == 2 else ""
if MODE not in ("off", "on"):
    sys.exit("usage: django_raw_sql.py off|on")
URL = os.environ["DATABASE_URL"]
DB = "django_raw_sql"

with psycopg.connect(URL, autocommit=True, application_name="chk12-setup") as admin:
    admin.execute(f"drop database if exists {DB} with (force)")
    admin.execute(f"create database {DB}")

import django  # noqa: E402
from django.conf import settings  # noqa: E402

_url = urlsplit(URL)
settings.configure(
    DEBUG=False,
    ALLOWED_HOSTS=["testserver"],
    ROOT_URLCONF=__name__,
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB,
            "USER": _url.username,
            "PASSWORD": _url.password,
            "HOST": _url.hostname,
            "PORT": _url.port,
            "ATOMIC_REQUESTS": MODE == "on",
            "OPTIONS": {"application_name": "chk12-setup"},
        }
    },
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()

from django.db import DatabaseError, connection, models, transaction  # noqa: E402
from django.db.backends.postgresql.psycopg_any import is_psycopg3  # noqa: E402
from django.http import JsonResponse  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import path  # noqa: E402

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="  log %(levelname)s: %(message)s")
logging.getLogger("django.request").disabled = True  # a 500 is printed from exc_info instead
log = logging.getLogger("shop")
CALLBACKS = []  # on_commit callbacks that ran
XIDS = []  # pg_current_xact_id(), captured inside the transaction


class Order(models.Model):
    marker = models.CharField(max_length=80)

    class Meta:
        app_label = "shop"


class Event(models.Model):
    name = models.CharField(max_length=32)
    props = models.JSONField()

    class Meta:
        app_label = "shop"


def record_event(name, **props):
    """Best-effort analytics through the ORM: never fail a request because of them."""
    try:
        Event.objects.create(name=name, props=props)
    except DatabaseError as e:
        log.warning("could not record event %s: %s", name, e)


def record_event_sql(name, **props):
    """The same helper, in raw SQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into shop_event (name, props) values (%s, %s::jsonb)",
                [name, json.dumps(props)],
            )
    except DatabaseError as e:
        log.warning("could not record event %s: %s", name, e)


def create_order(marker, channel, record):
    order = Order.objects.create(marker=marker)
    with connection.cursor() as cursor:
        cursor.execute("select pg_current_xact_id()::text")
        XIDS.append(cursor.fetchone()[0])
    transaction.on_commit(lambda: CALLBACKS.append(f"order {order.id} confirmed"))
    record(f"order_placed.{channel}", order_id=order.id)
    return order.id


def order_view(request):
    record = {"orm": record_event, "sql": record_event_sql}[request.GET["helper"]]
    args = (request.GET["marker"], request.GET["channel"], record)
    if request.GET["view_atomic"] == "yes":
        with transaction.atomic():
            order_id = create_order(*args)
    else:  # ATOMIC_REQUESTS: the request is the transaction
        order_id = create_order(*args)
    return JsonResponse({"order_id": order_id})


urlpatterns = [path("order", order_view)]

# "order_placed." plus the long channel is 35 characters; shop_event.name is varchar(32).
CHANNELS = {"ok": "web", "long": "partner_marketplace_eu"}
# setup: (mode, atomic() in the view, description)
SETUPS = {
    "atomic": ("off", "yes", "ATOMIC_REQUESTS off, atomic() in the view"),
    "nested": ("on", "yes", "ATOMIC_REQUESTS on, atomic() in the view (a savepoint)"),
    "request": ("on", "no", "ATOMIC_REQUESTS on, no atomic() in the view"),
}
HELPERS = {"orm": "ORM helper", "sql": "raw-SQL helper"}


def witness(sql, params):
    with psycopg.connect(URL, dbname=DB, autocommit=True, application_name="chk12-witness") as w:
        return w.execute(sql, params).fetchone()[0]


def run_arm(setup, helper, channel):
    arm = f"{setup}.{helper}.{channel}"
    marker = f"{arm}-{secrets.token_hex(6)}"
    _, view_atomic, describe = SETUPS[setup]
    name = "too long" if channel == "long" else "fits"
    print(f"\n{arm}: {describe}; {HELPERS[helper]}; event name {name}")
    connection.close()
    connection.settings_dict["OPTIONS"]["application_name"] = f"chk12-{arm}"
    CALLBACKS.clear()
    XIDS.clear()
    response = Client(raise_request_exception=False).get(
        "/order",
        {"helper": helper, "view_atomic": view_atomic, "channel": CHANNELS[channel], "marker": marker},
    )
    connection.close()  # the session ends with the request's last statement
    if response.exc_info:
        exc = response.exc_info[1]
        print(f"  Django: HTTP {response.status_code} {type(exc).__name__}: {str(exc).splitlines()[0]}")
    else:
        print(f"  Django: HTTP {response.status_code} {response.content.decode()}")
    print(f"  on_commit callback ran: {bool(CALLBACKS)}")
    xid = XIDS[0]
    fate = witness("select pg_xact_status(%s::xid8)::text", [xid])
    visible = witness("select count(*) from shop_order where marker = %s", [marker]) == 1
    print(f"  witness: pg_xact_status({xid}) {fate}, marker visible {visible}")


def main():
    print(
        f"mode {MODE}: Django {django.get_version()}, psycopg {psycopg.__version__}, "
        f"psycopg 3 backend {is_psycopg3}, ATOMIC_REQUESTS {MODE == 'on'}"
    )
    with connection.schema_editor() as editor:
        editor.create_model(Order)
        editor.create_model(Event)
    for setup, (mode, _, _) in SETUPS.items():
        if mode == MODE:
            for helper in HELPERS:
                for channel in CHANNELS:
                    run_arm(setup, helper, channel)
    connection.close()
    with psycopg.connect(URL, autocommit=True, application_name="chk12-setup") as admin:
        admin.execute(f"drop database {DB} with (force)")


main()
