-- CHK-3 supplement: does the recipe's CLOSE ALL close a WITH HOLD cursor even though its block rolls back?
-- Run as app_login (not a superuser), each run in a new session, with no SQLAlchemy or Python involved:
--   docker exec -i ppcs-chk3-supplement-pg psql -U app_login -d chk3 -X -e < psql_hold_cursor.sql

\echo == 1. a WITH HOLD cursor, then the three recipe statements in a block that rolls back
begin;
declare keep_cursor cursor with hold for select 42;
commit;
select name, is_holdable from pg_cursors;
begin;
close all;
reset all;
discard temp;
rollback;
select count(*) as hold_cursors_after_rolled_back_reset from pg_cursors;

\echo == 2. control: a WITH HOLD cursor, then a block that rolls back with nothing in it
begin;
declare keep_cursor_2 cursor with hold for select 42;
commit;
begin;
rollback;
select count(*) as hold_cursors_after_empty_rollback from pg_cursors;

\echo == 3. CLOSE ALL alone, in a block that rolls back
begin;
close all;
rollback;
select count(*) as hold_cursors_after_rolled_back_close_all from pg_cursors;
