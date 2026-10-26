"""CHK-12 re-run with a reasonable trigger: a once-only first-order bonus, caught as
"already awarded" inside Django's atomic(), then Django's commit.

    python django_once_only.py off|on

off: ATOMIC_REQUESTS off, and the view opens atomic().
on:  ATOMIC_REQUESTS on, and the view opens atomic() too (a savepoint) or does not.

Each arm sends one request through Django's request handling (django.test.Client), on its
own connection (application_name chk12r-<arm>). The view places an order and, as its last
step, awards the customer's first-order bonus. The bonus belongs in the order's transaction;
its primary key on customer_id makes it once-only, and the view treats IntegrityError as
"already awarded". The bonus is written through the ORM or in raw SQL. In the "dup" arms
the customer already has a bonus from an earlier order, so the insert fails with 23505.

Prints what Django returned, whether the on_commit callback ran, and, from a separate
connection, pg_xact_status() of the transaction and whether the new order is visible.
Needs DATABASE_URL (a server's postgres database). Creates database django_once_only and
drops it at the end.
"""

import itertools
import logging
import os
import secrets
import sys
from urllib.parse import urlsplit

import psycopg

MODE = sys.argv[1] if len(sys.argv) == 2 else ""
if MODE not in ("off", "on"):
    sys.exit("usage: django_once_only.py off|on")
URL = os.environ["DATABASE_URL"]
DB = "django_once_only"

with psycopg.connect(URL, autocommit=True, application_name="chk12r-setup") as admin:
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
            "OPTIONS": {"application_name": "chk12r-setup"},
        }
    },
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()

from django.db import IntegrityError, connection, models, transaction  # noqa: E402
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
    customer_id = models.IntegerField()

    class Meta:
        app_label = "shop"


class FirstOrderBonus(models.Model):
    customer_id = models.IntegerField(primary_key=True)  # one bonus per customer
    order_id = models.IntegerField()

    class Meta:
        app_label = "shop"


def award_bonus(customer_id, order_id):
    """The first-order bonus, through the ORM. The primary key makes it once-only."""
    try:
        FirstOrderBonus.objects.create(customer_id=customer_id, order_id=order_id)
    except IntegrityError:
        log.info("customer %s already had the first-order bonus", customer_id)


def award_bonus_sql(customer_id, order_id):
    """The same, in raw SQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into shop_firstorderbonus (customer_id, order_id) values (%s, %s)",
                [customer_id, order_id],
            )
    except IntegrityError:
        log.info("customer %s already had the first-order bonus", customer_id)


def place_order(marker, customer_id, award):
    order = Order.objects.create(marker=marker, customer_id=customer_id)
    with connection.cursor() as cursor:
        cursor.execute("select pg_current_xact_id()::text")
        XIDS.append(cursor.fetchone()[0])
    transaction.on_commit(lambda: CALLBACKS.append(f"order {order.id} confirmed"))
    award(customer_id, order.id)  # the last step
    return order.id


def order_view(request):
    award = {"orm": award_bonus, "sql": award_bonus_sql}[request.GET["helper"]]
    args = (request.GET["marker"], int(request.GET["customer"]), award)
    if request.GET["view_atomic"] == "yes":
        with transaction.atomic():
            order_id = place_order(*args)
    else:  # ATOMIC_REQUESTS: the request is the transaction
        order_id = place_order(*args)
    return JsonResponse({"order_id": order_id})


urlpatterns = [path("order", order_view)]

# setup: (mode, atomic() in the view, description)
SETUPS = {
    "atomic": ("off", "yes", "ATOMIC_REQUESTS off, atomic() in the view"),
    "nested": ("on", "yes", "ATOMIC_REQUESTS on, atomic() in the view (a savepoint)"),
    "request": ("on", "no", "ATOMIC_REQUESTS on, no atomic() in the view"),
}
HELPERS = {"orm": "ORM bonus", "sql": "raw-SQL bonus"}
CASES = {"ok": "first order", "dup": "repeat customer"}
CUSTOMERS = itertools.count(100)


def witness(sql, params):
    with psycopg.connect(URL, dbname=DB, autocommit=True, application_name="chk12r-witness") as w:
        return w.execute(sql, params).fetchone()[0]


def run_arm(setup, helper, case):
    arm = f"{setup}.{helper}.{case}"
    marker = f"{arm}-{secrets.token_hex(6)}"
    customer = next(CUSTOMERS)
    _, view_atomic, describe = SETUPS[setup]
    print(f"\n{arm}: {describe}; {HELPERS[helper]}; {CASES[case]}")
    if case == "dup":  # an earlier order already earned this customer's bonus
        with psycopg.connect(URL, dbname=DB, autocommit=True, application_name="chk12r-setup") as s:
            earlier = s.execute("insert into shop_order (marker, customer_id) values (%s, %s) returning id",
                                [f"earlier-{marker}", customer]).fetchone()[0]
            s.execute("insert into shop_firstorderbonus (customer_id, order_id) values (%s, %s)", [customer, earlier])
    connection.close()
    connection.settings_dict["OPTIONS"]["application_name"] = f"chk12r-{arm}"
    CALLBACKS.clear()
    XIDS.clear()
    response = Client(raise_request_exception=False).get(
        "/order", {"helper": helper, "view_atomic": view_atomic, "customer": customer, "marker": marker})
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
        editor.create_model(FirstOrderBonus)
    for setup, (mode, _, _) in SETUPS.items():
        if mode == MODE:
            for helper in HELPERS:
                for case in CASES:
                    run_arm(setup, helper, case)
    connection.close()
    with psycopg.connect(URL, autocommit=True, application_name="chk12r-setup") as admin:
        admin.execute(f"drop database {DB} with (force)")


main()
