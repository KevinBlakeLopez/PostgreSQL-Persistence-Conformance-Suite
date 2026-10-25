# Run with:  python demo_reset_recipe.py psycopg   (or psycopg2)
#
# Setup, as a superuser (app_login must not be a superuser):
#   create role tenant_a nologin;
#   create role app_login login password '<password>';
#   grant tenant_a to app_login;
# The password is read by libpq from PGPASSWORD or a passfile.
import sys

from sqlalchemy import create_engine, event, text

driver = sys.argv[1]
url = f"postgresql+{driver}://app_login@127.0.0.1:55492/chk3"


def documented_recipe(postgresql_engine):
    @event.listens_for(postgresql_engine, "reset")
    def _reset_postgresql(dbapi_connection, connection_record, reset_state):
        if not reset_state.terminate_only:
            dbapi_connection.execute("CLOSE ALL")
            dbapi_connection.execute("RESET ALL")
            dbapi_connection.execute("DISCARD TEMP")

        # so that the DBAPI itself knows that the connection has been
        # reset
        dbapi_connection.rollback()


def rollback_then_discard_all(postgresql_engine):
    @event.listens_for(postgresql_engine, "reset")
    def _reset_postgresql(dbapi_connection, connection_record, reset_state):
        dbapi_connection.rollback()
        if not reset_state.terminate_only:
            autocommit = dbapi_connection.autocommit
            dbapi_connection.autocommit = True
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("DISCARD ALL")
                cursor.close()
            finally:
                dbapi_connection.autocommit = autocommit


for install in (documented_recipe, rollback_then_discard_all):
    engine = create_engine(url, pool_size=1, max_overflow=0, pool_reset_on_return=None)
    install(engine)
    with engine.begin() as conn:
        pid = conn.execute(text("select pg_backend_pid()")).scalar()
        conn.execute(text("SET ROLE tenant_a"))
        conn.execute(text("SET app.tenant_id = 'a'"))
        conn.execute(text("SET search_path = tenant_s, public"))
        conn.execute(text("SET statement_timeout = '54321'"))
        conn.execute(text("CREATE TEMP TABLE scratch_tmp (x int)"))
    with engine.begin() as conn:
        row = conn.execute(text(
            "select pg_backend_pid(), current_user, current_setting('app.tenant_id', true),"
            " current_setting('search_path'), current_setting('statement_timeout'),"
            " to_regclass('pg_temp.scratch_tmp') is not null"
        )).one()
    print(f"{driver} | {install.__name__}")
    print(f"  next checkout: same backend: {row[0] == pid} | current_user: {row[1]}"
          f" | app.tenant_id: {row[2]!r} | search_path: {row[3]}"
          f" | statement_timeout: {row[4]} | temp table: {row[5]}")
    engine.dispose()
