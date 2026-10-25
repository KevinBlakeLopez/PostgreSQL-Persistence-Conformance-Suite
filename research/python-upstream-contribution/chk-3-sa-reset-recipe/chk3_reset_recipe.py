"""CHK-3: SQLAlchemy's PostgreSQL reset-on-return recipe, and a corrected example, on psycopg 3 and psycopg2.

Usage: python -I chk3_reset_recipe.py <psycopg|psycopg2> <rep>

Each arm builds its own engine with a pool of one, so unit 2 checks out the connection unit 1
returned unless the pool discarded it. Unit 1 sets session state and commits. Unit 2 reads that
state on the server, inserts an unqualified row, and commits. The login is `app_login`, a member
of the NOLOGIN role `tenant_a`, and not a superuser (see chk3_setup.py). libpq reads passwords
from PGPASSFILE.

Evidence that does not come from the subject connection's own report:
  - a witness, a raw autocommit connection as `postgres`, reads where unit 2's row landed and its
    `inserted_by` (DEFAULT current_user), whether it was visible before unit 2 ended, whether unit
    1's backend still exists, and whether unit 1's temp table still exists in pg_class;
  - the server's statement log; each engine sets application_name chk3-<driver>-<arm>-r<rep>.
Two listeners bracket the arm's own reset listener: `before` counts every reset call, and `after`
runs only if every listener before it returned. The pool's logger is captured, with the
virtualenv prefix shown as <venv> and this directory as <here>. The printed output holds no
PIDs, timestamps or rep numbers, so repetitions can be compared byte for byte.
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


# ---- the code under test, copied unchanged -------------------------------------------------
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


def search_path_on_connect(engine):
    # SQLAlchemy 2.1.6, dialects/postgresql/base.py lines 359-366, "Setting Alternate Search
    # Paths on Connect"; schema_name is the docs' free variable
    schema_name = "tenant_s"

    @event.listens_for(engine, "connect", insert=True)
    def set_search_path(dbapi_connection, connection_record):
        existing_autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION search_path='%s'" % schema_name)
        cursor.close()
        dbapi_connection.autocommit = existing_autocommit


def p7_variant(engine):
    # research/python-production-failure-gap-analysis/p7_sa_reset_recipe.py, corrected_reset
    @event.listens_for(engine, "reset")
    def _reset(dbapi_connection, connection_record, reset_state):
        dbapi_connection.rollback()
        if not reset_state.terminate_only:
            dbapi_connection.autocommit = True
            try:
                dbapi_connection.execute("DISCARD ALL")
            finally:
                dbapi_connection.autocommit = False


# ---- arms ---------------------------------------------------------------------------------
FULL = ["SET ROLE tenant_a", "SET app.tenant_id = 'a'", "SET search_path = tenant_s, public",
        "SET statement_timeout = '54321'", "CREATE TEMP TABLE {tmp} (x int)"]
NO_SEARCH_PATH = [s for s in FULL if "search_path" not in s]
NONE = {"pool_reset_on_return": None}
ARMS = [
    dict(name="default", what="control: the default reset (rollback), no reset listener",
         engine={}, install=[], unit1=FULL),
    dict(name="documented", what="(a) and (b): the documented recipe, with its pool_reset_on_return=None",
         engine=NONE, install=[documented_recipe], unit1=FULL),
    dict(name="corrected", what="(c): the corrected example",
         engine=NONE, install=[corrected_example], unit1=FULL),
    dict(name="corrected-autocommit", what="(d): the corrected example, isolation_level='AUTOCOMMIT'",
         engine={**NONE, "isolation_level": "AUTOCOMMIT"}, install=[corrected_example], unit1=FULL),
    dict(name="corrected-connect-search-path",
         what="(e): the corrected example, with the documented connect-time SET SESSION search_path recipe",
         engine=NONE, install=[search_path_on_connect, corrected_example], unit1=NO_SEARCH_PATH),
    dict(name="corrected-options-search-path", what="(e): the corrected example, search_path from startup options",
         engine=NONE, options="-csearch_path=tenant_s", install=[corrected_example], unit1=NO_SEARCH_PATH),
    dict(name="corrected-repeatable-read",
         what="added: the corrected example, isolation_level='REPEATABLE READ'",
         engine={**NONE, "isolation_level": "REPEATABLE READ"}, install=[corrected_example], unit1=FULL),
    dict(name="corrected-prepared", drivers=("psycopg",),
         what="added: the corrected example after psycopg has prepared a statement server-side",
         engine=NONE, install=[corrected_example], unit1=FULL, prepared=True),
    dict(name="p7-variant-autocommit", drivers=("psycopg",),
         what="control: P7's variant, which sets autocommit=False after its reset, on an AUTOCOMMIT engine",
         engine={**NONE, "isolation_level": "AUTOCOMMIT"}, install=[p7_variant], unit1=FULL),
]

READ = ("select current_user::text, session_user::text, coalesce(current_setting('app.tenant_id', true), '<unset>'),"
        " current_setting('search_path'), current_setting('statement_timeout'),"
        " to_regclass('pg_temp.{tmp}') is not null, current_setting('transaction_isolation'),"
        " (select count(*) from pg_prepared_statements), pg_backend_pid()")
FIELDS = ("current_user", "session_user", "app.tenant_id", "search_path", "statement_timeout",
          "temp_table_visible", "transaction_isolation", "server_prepared_statements")
PREPARED_QUERY = "select 1 as one"
LANDED = ("select 'public', inserted_by::text from public.item where name = %s union all"
          " select 'tenant_s', inserted_by::text from tenant_s.item where name = %s")


# ---- helpers ------------------------------------------------------------------------------
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


# ---- one arm ------------------------------------------------------------------------------
def run(arm):
    slug = arm["name"].replace("-", "_")
    tmp, marker = f"t_{DRIVER}_{slug}_r{REP}", f"{DRIVER}-{arm['name']}-r{REP}"
    connect_args = {"application_name": f"chk3-{DRIVER}-{arm['name']}-r{REP}"}
    if "options" in arm:
        connect_args["options"] = arm["options"]
    eng = sa.create_engine(URL, pool_size=1, max_overflow=0, connect_args=connect_args, **arm["engine"])

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
    result = {"arm": arm["name"], "what": arm["what"],
              "engine": {k: v for k, v in arm["engine"].items()} | ({"options": arm["options"]} if "options" in arm else {})}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # unit 1
        with eng.begin() as c:
            raw1 = c.connection.driver_connection
            sp, iso, pid1 = c.execute(text("select current_setting('search_path'),"
                                           " current_setting('transaction_isolation'), pg_backend_pid()")).one()
            unit1 = {"autocommit": raw1.autocommit, "search_path_at_start": sp, "transaction_isolation": iso}
            for s in arm["unit1"]:
                c.execute(text(s.format(tmp=tmp)))
            if arm.get("prepared"):
                unit1["prepare_threshold"] = raw1.prepare_threshold
                for _ in range(8):
                    c.execute(text(PREPARED_QUERY)).scalar()
                unit1["server_prepared_statements"] = c.execute(text("select count(*) from pg_prepared_statements")).scalar()
        result["unit1"] = unit1

        # unit 2
        unit2 = {}
        try:
            with eng.begin() as c:
                raw2 = c.connection.driver_connection
                row = c.execute(text(READ.format(tmp=tmp))).one()
                unit2.update(same_backend=row[-1] == pid1, same_dbapi_connection=raw2 is raw1,
                             autocommit=raw2.autocommit, saw=dict(zip(FIELDS, row[:-1])))
                if arm.get("prepared"):
                    for _ in range(8):
                        c.execute(text(PREPARED_QUERY)).scalar()
                    unit2["server_prepared_statements_after_8_runs"] = c.execute(
                        text("select count(*) from pg_prepared_statements")).scalar()
                c.execute(text("insert into item (name) values (:m)"), {"m": marker})
                unit2["row_visible_to_witness_before_unit_ended"] = len(wq(LANDED, marker, marker)) > 0
        except Exception as exc:
            unit2["error"] = scrub(f"{type(exc).__name__}: {exc}".splitlines()[0])
        result["unit2"] = unit2

        # witness, after unit 2, before dispose(). A discarded backend exits asynchronously, so
        # wait for it to leave pg_stat_activity before looking for its temp table.
        result["witness"] = {
            "unit2_row": [f"{s}.item by {by}" for s, by in wq(LANDED, marker, marker)] or ["NOT VISIBLE"],
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
    out = {"program": "chk3_reset_recipe.py", "driver": DRIVER,
           "versions": {"python": sys.version.split()[0], "sqlalchemy": sa.__version__, **drv,
                        "server": wq("show server_version")[0][0]},
           "results": [run(a) for a in ARMS if DRIVER in a.get("drivers", ("psycopg", "psycopg2"))]}
    W.close()
    print(json.dumps(out, indent=1, default=str))
