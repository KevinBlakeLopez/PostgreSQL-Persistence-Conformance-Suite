"""CHK-3 supplement: the arms an outside review asked about, on psycopg 3 and psycopg2.

Usage: python -I chk3_supplement.py <psycopg|psycopg2> <rep>

The same server, roles, measurement and witness as ../chk3_reset_recipe.py; run ../chk3_setup.py
first. The two hooks are copied unchanged from that program (see verbatim_check.py). Arms:

  documented-autocommit                 the documented recipe on an isolation_level="AUTOCOMMIT"
                                        engine (psycopg 3 only: on psycopg2 the hook raises first)
  corrected-default-reset               the corrected example with the default
                                        pool_reset_on_return="rollback"
  default-open-transaction              control: no hook; unit 1 returns its connection with a
                                        transaction still open
  corrected-open-transaction            the corrected example, connection returned with a
                                        transaction open, pool_reset_on_return=None
  corrected-open-transaction-default-reset   the same, with the default reset

In the "open" arms unit 1 sets the session state and commits, then inserts a row it never
commits, and leaves its `with engine.connect()` block with that transaction open. The pool then
reports transaction_was_reset=True. The witness checks that the uncommitted row never appears.
application_name is chk3-<driver>-s-<arm>-r<rep>, so ../server_log_extract.py can attribute
sessions. The printed output holds no PIDs, timestamps or rep numbers.
"""
import json, logging, os, sys, time, traceback, warnings

import sqlalchemy as sa
from sqlalchemy import event, text

DRIVER, REP = sys.argv[1], sys.argv[2]
HOST, PORT, DB = "127.0.0.1", 55492, "chk3"
if DRIVER == "psycopg":
    import psycopg as dbapi
elif DRIVER == "psycopg2":
    import psycopg2 as dbapi
else:
    sys.exit("driver must be psycopg or psycopg2")
URL = f"postgresql+{DRIVER}://app_login@{HOST}:{PORT}/{DB}"
HERE = os.path.dirname(os.path.abspath(__file__))


# ---- the code under test, copied unchanged from ../chk3_reset_recipe.py ---------------------
def documented_recipe(postgresql_engine):
    # SQLAlchemy 2.1.6, lib/sqlalchemy/dialects/postgresql/base.py lines 317-326 (same on main)
    @event.listens_for(postgresql_engine, "reset")
    def _reset_postgresql(dbapi_connection, connection_record, reset_state):
        if not reset_state.terminate_only:
            dbapi_connection.execute("CLOSE ALL")
            dbapi_connection.execute("RESET ALL")
            dbapi_connection.execute("DISCARD TEMP")

        # so that the DBAPI itself knows that the connection has been
        # reset
        dbapi_connection.rollback()


def corrected_example(postgresql_engine):
    # research/python-upstream-contribution-roadmap.md, section 7, PY-5
    @event.listens_for(postgresql_engine, "reset")
    def _reset_postgresql(dbapi_connection, connection_record, reset_state):
        # end the transaction first, so that the reset below is not undone by it
        dbapi_connection.rollback()
        if not reset_state.terminate_only:
            # DISCARD ALL cannot run inside a transaction block
            autocommit = dbapi_connection.autocommit
            dbapi_connection.autocommit = True
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("DISCARD ALL")
                cursor.close()
            finally:
                dbapi_connection.autocommit = autocommit


# ---- arms ---------------------------------------------------------------------------------
FULL = ["SET ROLE tenant_a", "SET app.tenant_id = 'a'", "SET search_path = tenant_s, public",
        "SET statement_timeout = '54321'", "CREATE TEMP TABLE {tmp} (x int)"]
NONE = {"pool_reset_on_return": None}
ARMS = [
    dict(name="documented-autocommit", drivers=("psycopg",),
         what="the documented recipe on an AUTOCOMMIT engine",
         engine={**NONE, "isolation_level": "AUTOCOMMIT"}, install=[documented_recipe], flow="committed"),
    dict(name="corrected-default-reset", what="the corrected example with the default pool_reset_on_return",
         engine={}, install=[corrected_example], flow="committed"),
    dict(name="default-open-transaction", what="control: no hook; connection returned with a transaction open",
         engine={}, install=[], flow="open"),
    dict(name="corrected-open-transaction",
         what="the corrected example; connection returned with a transaction open",
         engine=NONE, install=[corrected_example], flow="open"),
    dict(name="corrected-open-transaction-default-reset",
         what="the corrected example with the default reset; connection returned with a transaction open",
         engine={}, install=[corrected_example], flow="open"),
]

READ = ("select current_user::text, session_user::text, coalesce(current_setting('app.tenant_id', true), '<unset>'),"
        " current_setting('search_path'), current_setting('statement_timeout'),"
        " to_regclass('pg_temp.{tmp}') is not null, current_setting('transaction_isolation'), pg_backend_pid()")
FIELDS = ("current_user", "session_user", "app.tenant_id", "search_path", "statement_timeout",
          "temp_table_visible", "transaction_isolation")
LANDED = ("select 'public', inserted_by::text from public.item where name = %s union all"
          " select 'tenant_s', inserted_by::text from tenant_s.item where name = %s")


# ---- helpers, as in ../chk3_reset_recipe.py -----------------------------------------------
def scrub(s):
    return s.replace(sys.prefix, "<venv>").replace(HERE, "<here>").replace(sys.base_prefix, "<python>")


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        entry = {"logger": record.name, "level": record.levelname, "message": record.getMessage()}
        if record.exc_info:
            entry["exception"] = scrub(traceback.format_exception_only(*record.exc_info[:2])[-1].strip())
            entry["traceback"] = [scrub(l) for l in "".join(traceback.format_exception(*record.exc_info)).splitlines()]
        self.records.append(entry)


CAPTURE = Capture()
logging.getLogger("sqlalchemy").addHandler(CAPTURE)
logging.getLogger("sqlalchemy").propagate = False

STATUS = {0: "IDLE", 1: "ACTIVE", 2: "INTRANS", 3: "INERROR", 4: "UNKNOWN"}


def tx_status(raw):
    s = raw.info.transaction_status
    return s.name if hasattr(s, "name") else STATUS[s]


def witness():
    kw = dict(host=HOST, port=PORT, dbname=DB, user="postgres", application_name=f"chk3-witness-{DRIVER}-r{REP}")
    if DRIVER == "psycopg":
        return dbapi.connect(**kw, autocommit=True)
    c = dbapi.connect(**kw)
    c.autocommit = True
    return c


W = witness()


def wq(sql, *params):
    cur = W.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def backend_exited(pid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while wq("select count(*) from pg_stat_activity where pid = %s", pid)[0][0]:
        if time.monotonic() > deadline:
            return False
        time.sleep(0.01)
    return True


def landed(marker):
    return [f"{s}.item by {by}" for s, by in wq(LANDED, marker, marker)] or ["NOT VISIBLE"]


# ---- one arm ------------------------------------------------------------------------------
def run(arm):
    slug = arm["name"].replace("-", "_")
    tmp, marker = f"t_{DRIVER}_s_{slug}_r{REP}", f"{DRIVER}-s-{arm['name']}-r{REP}"
    eng = sa.create_engine(URL, pool_size=1, max_overflow=0,
                           connect_args={"application_name": f"chk3-{DRIVER}-s-{arm['name']}-r{REP}"},
                           **arm["engine"])
    calls, events = [], []

    def before(dbapi_connection, connection_record, reset_state):
        events.append("reset")
        calls.append({"terminate_only": reset_state.terminate_only,
                      "transaction_was_reset": reset_state.transaction_was_reset,
                      "status_before": tx_status(dbapi_connection),
                      "autocommit_before": dbapi_connection.autocommit, "later_listeners_returned": False})

    def after(dbapi_connection, connection_record, reset_state):
        calls[-1].update(later_listeners_returned=True, status_after=tx_status(dbapi_connection),
                         autocommit_after=dbapi_connection.autocommit)

    event.listen(eng, "reset", before)
    for install in arm["install"]:
        install(eng)
    event.listen(eng, "reset", after)
    event.listen(eng, "connect", lambda *a: events.append("connect"))
    event.listen(eng, "checkout", lambda *a: events.append("checkout"))
    event.listen(eng, "checkin", lambda *a: events.append("checkin"))
    event.listen(eng, "invalidate", lambda c, r, e: events.append(f"invalidate ({type(e).__name__})"))
    CAPTURE.records = []
    result = {"arm": arm["name"], "what": arm["what"], "engine": dict(arm["engine"]), "flow": arm["flow"]}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # unit 1
        with eng.connect() as c:
            raw1 = c.connection.driver_connection
            pid1 = c.execute(text("select pg_backend_pid()")).scalar()
            for s in FULL:
                c.execute(text(s.format(tmp=tmp)))
            c.commit()
            unit1 = {"autocommit": raw1.autocommit}
            if arm["flow"] == "open":
                c.execute(text("insert into item (name) values (:m)"), {"m": marker + "-uncommitted"})
                unit1["status_when_returned"] = tx_status(raw1)
            # leaving the block returns the connection; an open transaction is rolled back by close()
        result["unit1"] = unit1

        # unit 2
        unit2 = {}
        try:
            with eng.begin() as c:
                raw2 = c.connection.driver_connection
                row = c.execute(text(READ.format(tmp=tmp))).one()
                unit2.update(same_backend=row[-1] == pid1, same_dbapi_connection=raw2 is raw1,
                             autocommit=raw2.autocommit, saw=dict(zip(FIELDS, row[:-1])))
                c.execute(text("insert into item (name) values (:m)"), {"m": marker})
                unit2["row_visible_to_witness_before_unit_ended"] = len(wq(LANDED, marker, marker)) > 0
        except Exception as exc:
            unit2["error"] = scrub(f"{type(exc).__name__}: {exc}".splitlines()[0])
        result["unit2"] = unit2

        result["witness"] = {
            "unit2_row": landed(marker),
            "unit1_uncommitted_row": landed(marker + "-uncommitted") if arm["flow"] == "open" else "n/a",
            "unit1_backend_exited_within_5s": (not wq("select count(*) from pg_stat_activity where pid = %s", pid1)[0][0])
            if unit2.get("same_backend") else backend_exited(pid1),
            "unit1_temp_table_in_pg_class": wq(
                "select count(*) from pg_class where relname = %s and relpersistence = 't'", tmp)[0][0],
        }
        eng.dispose()
    result["reset_calls"] = calls
    result["pool_events"] = events
    result["pool_log"] = CAPTURE.records
    result["warnings"] = [scrub(f"{w.category.__name__}: {w.message}") for w in caught]
    return result


if __name__ == "__main__":
    if DRIVER == "psycopg":
        drv = {"psycopg": dbapi.__version__, "impl": dbapi.pq.__impl__, "libpq": dbapi.pq.version()}
    else:
        drv = {"psycopg2": dbapi.__version__, "libpq": dbapi.extensions.libpq_version()}
    out = {"program": "chk3_supplement.py", "driver": DRIVER,
           "versions": {"python": sys.version.split()[0], "sqlalchemy": sa.__version__, **drv,
                        "server": wq("show server_version")[0][0]},
           "results": [run(a) for a in ARMS if DRIVER in a.get("drivers", ("psycopg", "psycopg2"))]}
    W.close()
    print(json.dumps(out, indent=1, default=str))
