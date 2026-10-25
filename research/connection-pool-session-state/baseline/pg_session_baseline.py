"""PostgreSQL session-state baseline, with no pool and no framework.

One physical session S changes each category of session state and then ends transactions in different ways.
An independent observer connection O (a superuser) reads S's state from outside where that is possible
(pg_stat_activity, pg_locks, pg_class). A third connection C competes for advisory locks. Every connection runs in
autocommit mode and sends BEGIN, COMMIT and ROLLBACK itself, so the driver adds no statements.

The output contains no PIDs, timestamps or OIDs, so repetitions can be compared byte for byte.

Usage: python -I pg_session_baseline.py <instance-file>
"""

import json
import sys

import psycopg

INST = json.load(open(sys.argv[1]))


def connect(role="app", application_name="ssc_baseline_s"):
    if role == "app":
        user, password = INST["user"], INST["password"]
    else:
        user, password = INST["superuser"], INST["superuser_password"]
    conn = psycopg.connect(
        host=INST["host"], port=INST["port"], dbname=INST["database"], user=user, password=password,
        autocommit=True, application_name=application_name,
    )
    token = conn.execute("select current_setting('cluster_name')").fetchone()[0]
    if token != INST["token"]:
        raise SystemExit(f"refusing: cluster_name {token!r} is not this investigation's server")
    return conn


def one(conn, sql, params=None):
    return conn.execute(sql, params).fetchone()[0]


def try_sql(conn, sql):
    """Runs sql and returns 'ok' or the SQLSTATE of the error."""
    try:
        conn.execute(sql)
        return "ok"
    except psycopg.Error as exc:
        return exc.sqlstate or type(exc).__name__


def out(category, step, observed):
    print(f"{category:<22} {step:<58} {observed}")


O = connect("super", "ssc_baseline_o")
C = connect("app", "ssc_baseline_c")


def pid(conn):
    return one(conn, "select pg_backend_pid()")


def observed_app_name(s_pid):
    return one(O, "select application_name from pg_stat_activity where pid = %s", (s_pid,))


def held_advisory(s_pid):
    rows = O.execute(
        "select objid from pg_locks where locktype = 'advisory' and pid = %s and granted order by objid",
        (s_pid,),
    ).fetchall()
    return [r[0] for r in rows] or "none"


def temp_tables(s_pid):
    # Temporary tables of S, read from the catalogs by O: pg_temp_<backend id> is S's temporary schema.
    rows = O.execute(
        """
        select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'pg_temp_' || (select b from pg_stat_get_backend_idset() b
                                        where pg_stat_get_backend_pid(b) = %s)
          and c.relkind = 'r'
        order by 1
        """,
        (s_pid,),
    ).fetchall()
    return [r[0] for r in rows] or "none"


def landed(label):
    rows = O.execute(
        """
        select 'public', inserted_by from public.item where label = %(l)s
        union all select 'tenant_a', inserted_by from tenant_a.item where label = %(l)s
        union all select 'tenant_b', inserted_by from tenant_b.item where label = %(l)s
        order by 1
        """,
        {"l": label},
    ).fetchall()
    return [f"{schema}/{who}" for schema, who in rows] or "nowhere visible"


print("server:", one(O, "select version()").split(" on ")[0])

# A. Session configuration (application_name), observed through pg_stat_activity.
S = connect()
p = pid(S)
S.execute("SET application_name = 'ppcs_borrower_a'")
out("A application_name", "after SET (no transaction)", observed_app_name(p))
S.execute("BEGIN"); S.execute("SET application_name = 'set_in_committed_tx'"); S.execute("COMMIT")
out("A application_name", "after BEGIN; SET; COMMIT", observed_app_name(p))
S.execute("BEGIN"); S.execute("SET application_name = 'set_in_rolled_back_tx'"); S.execute("ROLLBACK")
out("A application_name", "after BEGIN; SET; ROLLBACK", observed_app_name(p))
S.execute("BEGIN"); S.execute("SET application_name = 'set_in_failed_tx'")
out("A application_name", "failing statement in that transaction", try_sql(S, "select 1/0"))
S.execute("ROLLBACK")
out("A application_name", "after the failed transaction's ROLLBACK", observed_app_name(p))
S.execute("RESET ALL")
out("A application_name", "after RESET ALL", observed_app_name(p))
S.execute("SET application_name = 'ppcs_borrower_a'")
S.execute("DISCARD ALL")
out("A application_name", "after SET then DISCARD ALL", observed_app_name(p))
S.close()

# B. search_path, observed by where an unqualified insert lands.
S = connect()
S.execute("SET search_path TO tenant_a, public")
S.execute("insert into item(label) values ('B-after-set')")
out("B search_path", "unqualified insert after SET", landed("B-after-set"))
S.execute("BEGIN"); S.execute("SET search_path TO tenant_b, public"); S.execute("ROLLBACK")
S.execute("insert into item(label) values ('B-after-rollback')")
out("B search_path", "after BEGIN; SET tenant_b; ROLLBACK", landed("B-after-rollback"))
S.execute("BEGIN"); S.execute("SET search_path TO tenant_b, public"); S.execute("COMMIT")
S.execute("insert into item(label) values ('B-after-commit')")
out("B search_path", "after BEGIN; SET tenant_b; COMMIT", landed("B-after-commit"))
S.execute("RESET ALL")
S.execute("insert into item(label) values ('B-after-reset-all')")
out("B search_path", "after RESET ALL", landed("B-after-reset-all"))
S.execute("SET search_path TO tenant_a, public"); S.execute("DISCARD ALL")
S.execute("insert into item(label) values ('B-after-discard-all')")
out("B search_path", "after SET tenant_a then DISCARD ALL", landed("B-after-discard-all"))
S.close()

# C. Session-level advisory locks, observed in pg_locks by O and contested by C.
S = connect()
p = pid(S)
S.execute("select pg_advisory_lock(123456)")
out("C advisory lock", "after pg_advisory_lock(123456) outside a transaction", held_advisory(p))
S.execute("BEGIN"); S.execute("select 1"); S.execute("COMMIT")
out("C advisory lock", "after BEGIN; SELECT 1; COMMIT", held_advisory(p))
S.execute("BEGIN"); try_sql(S, "select 1/0"); S.execute("ROLLBACK")
out("C advisory lock", "after a failed transaction and ROLLBACK", held_advisory(p))
out("C advisory lock", "competing connection pg_try_advisory_lock(123456)", one(C, "select pg_try_advisory_lock(123456)"))
out("C advisory lock", "same session pg_try_advisory_lock(123456) (reentrant)", one(S, "select pg_try_advisory_lock(123456)"))
S.execute("BEGIN"); S.execute("select pg_advisory_lock(123457)"); S.execute("ROLLBACK")
out("C advisory lock", "lock taken inside a transaction, then ROLLBACK", held_advisory(p))
S.execute("BEGIN"); try_sql(S, "select 1/0")
out("C advisory lock", "pg_advisory_unlock_all() inside an aborted block", try_sql(S, "select pg_advisory_unlock_all()"))
S.execute("ROLLBACK")
out("C advisory lock", "after that ROLLBACK", held_advisory(p))
S.execute("RESET ALL")
out("C advisory lock", "after RESET ALL", held_advisory(p))
S.execute("select pg_advisory_unlock_all()")
out("C advisory lock", "after pg_advisory_unlock_all()", held_advisory(p))
S.execute("select pg_advisory_lock(123456)"); S.execute("DISCARD ALL")
out("C advisory lock", "after re-lock then DISCARD ALL", held_advisory(p))
S.close()

# D. Temporary tables, observed in the catalogs by O.
S = connect()
p = pid(S)
S.execute("CREATE TEMP TABLE ppcs_session_probe (id integer)")
out("D temp table", "after CREATE TEMP TABLE (no transaction)", temp_tables(p))
S.execute("BEGIN"); S.execute("CREATE TEMP TABLE ppcs_probe_rolled_back (id integer)"); S.execute("ROLLBACK")
out("D temp table", "after BEGIN; CREATE TEMP TABLE second; ROLLBACK", temp_tables(p))
S.execute("CREATE TEMP TABLE item (id bigserial, label text, inserted_by name default current_user)")
S.execute("insert into item(label) values ('D-shadowed')")
out("D temp table", "unqualified insert with a temp 'item' present", landed("D-shadowed"))
S.execute("RESET ALL")
out("D temp table", "after RESET ALL", temp_tables(p))
S.execute("DISCARD ALL")
out("D temp table", "after DISCARD ALL", temp_tables(p))
S.close()

# E. LISTEN registrations: pg_listening_channels() in S, and a notification sent by O.
S = connect()
S.execute("LISTEN ppcs_probe_channel")
out("E LISTEN", "channels after LISTEN (no transaction)", one(S, "select array_agg(c order by c) from pg_listening_channels() c"))
S.execute("BEGIN"); S.execute("LISTEN ppcs_probe_rolled_back"); S.execute("ROLLBACK")
out("E LISTEN", "after BEGIN; LISTEN second; ROLLBACK", one(S, "select array_agg(c order by c) from pg_listening_channels() c"))
S.execute("RESET ALL")
O.execute("select pg_notify('ppcs_probe_channel', 'after-reset-all')")
got = [n.payload for n in S.notifies(timeout=2.0, stop_after=1)]
out("E LISTEN", "notification delivered after RESET ALL", got or "none")
S.execute("DISCARD ALL")
out("E LISTEN", "channels after DISCARD ALL", one(S, "select array_agg(c order by c) from pg_listening_channels() c"))
S.close()

# F. Transaction-local state.
S = connect()
S.execute("BEGIN"); S.execute("SET LOCAL application_name = 'ppcs_transaction_local'")
out("F SET LOCAL", "inside the transaction", one(S, "show application_name"))
S.execute("ROLLBACK")
out("F SET LOCAL", "after ROLLBACK", one(S, "show application_name"))
S.execute("BEGIN"); S.execute("SET LOCAL application_name = 'ppcs_transaction_local'"); S.execute("COMMIT")
out("F SET LOCAL", "after COMMIT", one(S, "show application_name"))
S.execute("BEGIN"); S.execute("select set_config('app.tenant_id', 'tenant_a', true)"); S.execute("COMMIT")
out("F SET LOCAL", "set_config(..., is_local=true) after COMMIT", one(S, "select current_setting('app.tenant_id', true)"))
S.execute("select set_config('app.tenant_id', 'tenant_a', false)")
out("F SET LOCAL", "set_config(..., is_local=false), no transaction", one(S, "select current_setting('app.tenant_id', true)"))
S.execute("RESET ALL")
out("F SET LOCAL", "custom GUC after RESET ALL", repr(one(S, "select current_setting('app.tenant_id', true)")))
S.close()

# G. Role and session authorization.
S = connect()
S.execute("SET ROLE ssc_tenant_a")
out("G role", "current_user after SET ROLE ssc_tenant_a", one(S, "select current_user"))
S.execute("RESET ALL")
out("G role", "current_user after RESET ALL", one(S, "select current_user"))
S.execute("insert into public.item(label) values ('G-after-reset-all')")
out("G role", "inserted_by of an insert after RESET ALL", landed("G-after-reset-all"))
S.execute("DISCARD ALL")
out("G role", "current_user after DISCARD ALL", one(S, "select current_user"))
S.execute("BEGIN"); S.execute("SET ROLE ssc_tenant_a"); S.execute("ROLLBACK")
out("G role", "after BEGIN; SET ROLE; ROLLBACK", one(S, "select current_user"))
S.execute("SET ROLE ssc_tenant_a"); S.execute("RESET ROLE")
out("G role", "after SET ROLE then RESET ROLE", one(S, "select current_user"))
S.close()
SU = connect("super", "ssc_baseline_su")
SU.execute("SET SESSION AUTHORIZATION ssc_app")
out("G session authz", "session_user after SET SESSION AUTHORIZATION", one(SU, "select session_user"))
SU.execute("RESET ALL")
out("G session authz", "session_user after RESET ALL", one(SU, "select session_user"))
SU.execute("DISCARD ALL")
out("G session authz", "session_user after DISCARD ALL", one(SU, "select session_user"))
SU.close()

# H. Transaction characteristics and other session defaults.
S = connect()
S.execute("SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL SERIALIZABLE")
S.execute("BEGIN")
out("H tx characteristics", "isolation of the next transaction", one(S, "show transaction_isolation"))
S.execute("COMMIT")
S.execute("SET statement_timeout = '50ms'")
out("H tx characteristics", "statement_timeout leak: pg_sleep(0.2)", try_sql(S, "select pg_sleep(0.2)"))
S.execute("RESET ALL")
S.execute("BEGIN")
out("H tx characteristics", "isolation after RESET ALL", one(S, "show transaction_isolation"))
S.execute("COMMIT")
out("H tx characteristics", "statement_timeout after RESET ALL", one(S, "show statement_timeout"))
S.close()

# I. Prepared statements and WITH HOLD cursors.
S = connect()
S.execute("PREPARE ppcs_p1 AS SELECT 1")
S.execute("BEGIN"); S.execute("PREPARE ppcs_p2 AS SELECT 2"); S.execute("ROLLBACK")
out("I prepared", "SQL PREPAREs after one in a rolled-back tx",
    one(S, "select array_agg(name order by name) from pg_prepared_statements where name like 'ppcs%%'"))
S.execute("BEGIN"); S.execute("DECLARE ppcs_c1 CURSOR WITH HOLD FOR SELECT 1"); S.execute("COMMIT")
out("I cursor", "WITH HOLD cursor after COMMIT",
    one(S, "select array_agg(name order by name) from pg_cursors where name like 'ppcs%%'"))
S.execute("RESET ALL")
out("I prepared", "after RESET ALL",
    one(S, "select array_agg(name order by name) from pg_prepared_statements where name like 'ppcs%%'"))
out("I cursor", "after RESET ALL", one(S, "select array_agg(name order by name) from pg_cursors where name like 'ppcs%%'"))
S.execute("CLOSE ALL")
out("I cursor", "after CLOSE ALL", one(S, "select array_agg(name order by name) from pg_cursors where name like 'ppcs%%'"))
S.execute("DISCARD ALL")
out("I prepared", "after DISCARD ALL",
    one(S, "select array_agg(name order by name) from pg_prepared_statements where name like 'ppcs%%'"))
S.close()

# J. An open transaction handed to the next unit of work on the same session, with no reset in between.
S = connect()
notices = []
S.add_notice_handler(lambda d: notices.append(d.sqlstate))
S.execute("BEGIN"); S.execute("insert into public.item(label) values ('J-unit1-uncommitted')")
xid1 = one(S, "select pg_current_xact_id()::text")
# The "next borrower" now uses the same session:
out("J open transaction", "next unit's BEGIN: result, notices", f"{try_sql(S, 'BEGIN')}, {notices}")
S.execute("insert into public.item(label) values ('J-unit2')")
same = one(S, "select pg_current_xact_id()::text") == xid1
out("J open transaction", "next unit runs in unit 1's transaction ID", same)
S.execute("COMMIT")
out("J open transaction", "unit 1's row after unit 2's COMMIT", landed("J-unit1-uncommitted"))
out("J open transaction", "unit 1's transaction fate (pg_xact_status)", one(O, "select pg_xact_status(%s::xid8)", (xid1,)))
S.close()

# K. Connection termination: a new physical session starts with defaults.
S = connect()
p = pid(S)
S.execute("SET ROLE ssc_tenant_a"); S.execute("SET search_path TO tenant_a"); S.execute("select pg_advisory_lock(42)")
S.execute("CREATE TEMP TABLE ppcs_session_probe (id int)"); S.execute("LISTEN ppcs_probe_channel")
O.execute("select pg_terminate_backend(%s)", (p,))
while one(O, "select count(*) from pg_stat_activity where pid = %s", (p,)):
    O.execute("select pg_sleep(0.05)")
try:
    S.execute("select 1")
    gone = "ok (session still alive)"
except psycopg.Error as exc:
    gone = f"raised {type(exc).__name__}"
out("K termination", "old session's statement after pg_terminate_backend", gone)
S.close()
S = connect()
p2 = pid(S)
state = one(S, "select current_user || ' | ' || current_setting('search_path') || ' | ' || "
               "coalesce((select string_agg(c, ',') from pg_listening_channels() c), 'no channels')")
out("K termination", "new session: role | search_path | channels", state)
out("K termination", "new session's advisory locks", held_advisory(p2))
out("K termination", "new session's temp tables", temp_tables(p2))
out("K termination", "advisory lock 42 free for a competitor", one(C, "select pg_try_advisory_lock(42)"))
C.execute("select pg_advisory_unlock_all()")
S.close()

C.close()
O.execute("delete from public.item"); O.execute("delete from tenant_a.item"); O.execute("delete from tenant_b.item")
O.close()
