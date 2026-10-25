-- CHK-3 psql checks: what the recipe's statements do inside and outside a transaction block.
-- Run as app_login (not a superuser), on the CHK-3 server, with no SQLAlchemy or Python involved:
--   docker exec -i ppcs-chk3-sa-reset-pg psql -U app_login -d chk3 -X -e < psql_checks.sql

\echo == 1. session state, then the recipe statements inside a transaction block that rolls back
set role tenant_a;
set app.tenant_id = 'a';
set search_path = tenant_s, public;
set statement_timeout = '54321';
create temp table psql_tmp (x int);
begin;
close all;
reset all;
discard temp;
rollback;
select current_user, current_setting('app.tenant_id', true) as tenant_id, current_setting('search_path') as search_path,
       current_setting('statement_timeout') as statement_timeout, to_regclass('pg_temp.psql_tmp') is not null as temp_table;

\echo == 2. the same statements outside a transaction block
close all;
reset all;
discard temp;
select current_user, current_setting('app.tenant_id', true) as tenant_id, current_setting('search_path') as search_path,
       current_setting('statement_timeout') as statement_timeout, to_regclass('pg_temp.psql_tmp') is not null as temp_table;

\echo == 3. DISCARD ALL inside a transaction block
begin;
discard all;
rollback;

\echo == 4. DISCARD ALL outside a transaction block, with the role still set
create temp table psql_tmp2 (x int);
select current_user, session_user;
discard all;
select current_user, session_user, to_regclass('pg_temp.psql_tmp2') is not null as temp_table;

\echo == 5. RESET ROLE outside a transaction block
set role tenant_a;
reset role;
select current_user, session_user;
