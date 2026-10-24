"""P7: does SQLAlchemy's documented PostgreSQL reset-on-return recipe reset session state on psycopg 3?

Premise probe for the gap analysis. The recipe is copied from the SQLAlchemy 2.1.5 PostgreSQL
dialect docs ("Temporary Table / Resource Reset for Connection Pooling"), with the URL changed
from psycopg2 to psycopg. Variant B is a corrected reset that runs outside a transaction.
Pool size 1, so unit 2 gets unit 1's connection. Login is a non-superuser member of tenant_a.
"""
import json, os, sys

import psycopg
import sqlalchemy as sa
from sqlalchemy import event, text

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
APP = f"postgresql+psycopg://app_login:app-login-probe-only@127.0.0.1:{PORT}/probe2"
UNIT1 = ["SET ROLE tenant_a", "SET app.tenant_id = 'a'", "SET search_path = tenant_s, public",
         "SET statement_timeout = '54321'", "CREATE TEMP TABLE IF NOT EXISTS scratch_tmp (x int)"]
READ = text("select current_user::text, coalesce(current_setting('app.tenant_id', true), '<unset>'),"
            " current_setting('search_path'), current_setting('statement_timeout'),"
            " (to_regclass('pg_temp.scratch_tmp') is not null), pg_backend_pid()")


def documented_recipe(engine):
    @event.listens_for(engine, "reset")
    def _reset_postgresql(dbapi_connection, connection_record, reset_state):
        if not reset_state.terminate_only:
            dbapi_connection.execute("CLOSE ALL")
            dbapi_connection.execute("RESET ALL")
            dbapi_connection.execute("DISCARD TEMP")

        # so that the DBAPI itself knows that the connection has been
        # reset
        dbapi_connection.rollback()


def corrected_reset(engine):
    @event.listens_for(engine, "reset")
    def _reset(dbapi_connection, connection_record, reset_state):
        dbapi_connection.rollback()
        if not reset_state.terminate_only:
            dbapi_connection.autocommit = True
            try:
                dbapi_connection.execute("DISCARD ALL")
            finally:
                dbapi_connection.autocommit = False


def run(label, install):
    kw = {"pool_size": 1, "max_overflow": 0}
    if install is not None:
        kw["pool_reset_on_return"] = None
    eng = sa.create_engine(APP, **kw)
    if install is not None:
        install(eng)
    errors = []
    event.listen(eng.pool, "invalidate", lambda *a, **k: errors.append("pool.invalidate"))
    with eng.begin() as c:
        pid1 = c.execute(text("select pg_backend_pid()")).scalar()
        for s in UNIT1:
            c.execute(text(s))
    with eng.begin() as c:
        row = c.execute(READ).one()
    eng.dispose()
    return {"variant": label, "same_backend": row[5] == pid1, "invalidations": errors,
            "unit2_saw": dict(zip(("role", "app.tenant_id", "search_path", "statement_timeout", "temp_table"), row[:5]))}


if __name__ == "__main__":
    out = [run("default (reset_on_return rollback)", None),
           run("documented recipe on psycopg 3", documented_recipe),
           run("corrected: rollback, then DISCARD ALL in autocommit", corrected_reset)]
    print(json.dumps({"versions": {"sqlalchemy": sa.__version__, "psycopg": psycopg.__version__}, "results": out}, indent=1))
