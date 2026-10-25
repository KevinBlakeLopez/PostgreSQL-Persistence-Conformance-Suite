# CHK-3 facts: SQLAlchemy's PostgreSQL reset-on-return recipe (PY-5)

Compiled 2026-10-24 (US Pacific); runs and checks at 2026-10-25 01:14–01:46 UTC. Revised the same night after an outside review, with supplement runs at 03:21 UTC. Written by: Claude Opus 5.5 (max).

This file lists facts for the author's own write-up. It is not text to post. SQLAlchemy's `.github/CONTRIBUTING.md` (its AI section, lines 48–65) and `.github/CODE_OF_CONDUCT.md` require its discussions, issues and PRs to be written in the poster's own words. Paths are relative to this directory. Labels:

- **Obs:** observed in a run recorded here;
- **Src:** source reading;
- **Doc:** quoted documentation;
- **Judg:** judgment.

**Scope.** The main runs measure five items of session state: the role, a custom GUC, `search_path`, `statement_timeout` and a temp table. They do not show that the recipe resets nothing in every case:
- its `CLOSE ALL` does close WITH HOLD cursors (fact 26);
- on an AUTOCOMMIT engine, it resets everything measured except the role (fact 27).

## Versions and SHAs checked

| Item | Value | Checked |
| --- | --- | --- |
| SQLAlchemy run | 2.1.6, the latest release on PyPI (uploaded 2026-10-21) | 2026-10-25 01:14 UTC |
| Tag `rel_2_1_6` | `2f6968cc126d4da2d2eabc5a51285472bb9bfc9e` | 2026-10-25 |
| Tag `rel_2_1_5` | `4fbf72c07f5bebcabb02e35ee8b742a217ac649d` | 2026-10-25 |
| `main` | `10f4d1e2d706a7722ca78e79ce05b00333a7aa5b` (committed 2026-10-23) | 2026-10-25 01:16 UTC |
| `dialects/postgresql/base.py` | byte-identical on all three revisions, SHA-256 `cc06667e263a6424e149355a95493987ab1220097568be9603b6b99a60228575` | 2026-10-25 |
| `doc/build/core/pooling.rst` | byte-identical on all three revisions, SHA-256 `804c416269960c2de351c62e39cf4c6ee3873a8860650b6c29804e375ffe17f0` | 2026-10-25 |
| psycopg 3 | 3.3.6, with psycopg-binary 3.3.6 (libpq 18.6, `180006`). 3.3.6 is the latest release | 2026-10-25 |
| psycopg2 | psycopg2-binary 2.9.13 (libpq 17.11, `170011`). 2.9.13 is the latest release | 2026-10-25 |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg13+2), aarch64, image digest `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` | 2026-10-25 |
| Python, OS | 3.13.11; macOS arm64 (colima VM) | — |
| Login | `app_login`, not a superuser, a member of the NOLOGIN role `tenant_a` | before the runs |

## Observed facts

**How many runs.**
- Facts 1–21 and 25 held in 3 of 3 runs of the program or the demo, on each driver they apply to.
- Facts 22–24 come from one run of `psql_checks.sql`.
- Facts 26–30 held in 3 of 3 runs each.

The program's arms used a pool of one and `pool_reset_on_return=None`, except where an arm says otherwise.

**(a) The documented recipe on psycopg 3, on a transactional (default) engine**

1. The `reset` hook ran on every return: 2 calls per arm, each of which returned normally. The pool logged no error, and no invalidation (`output/psycopg.rep*.out`, arm `documented`: `reset_calls`, `pool_events`, `pool_log`).
2. On each return, the hook's session sent `BEGIN`, `CLOSE ALL`, `RESET ALL`, `DISCARD TEMP` and `ROLLBACK`, all under one virtual transaction ID (`output/server-log-summary.psycopg.rep*.txt`, `documented`). `DISCARD TEMP` was given an xid. In run 1 these were vxid `9/4` and xid 778, then `9/6` and xid 780.
3. All six of those reset transactions are `aborted`, read with `psql` (`output/psql-xact-status.txt`).
4. **The next checkout saw unit 1's state:** `current_user` tenant_a, `app.tenant_id` `a`, `search_path` `tenant_s, public`, `statement_timeout` 54321ms, and the temp table present. It was the same backend (`output/psycopg.rep*.out`).
5. **The witness agrees.**
   - The next checkout's unqualified row landed in `tenant_s.item`, with `inserted_by` tenant_a.
   - Unit 1's temp table was still in `pg_class` after the next checkout.
   - `psql` reads the same rows (`output/psql-item-rows.txt`).
6. **The default reset (`rollback`, no hook) left all five items in place, on both drivers** (`default` arms).
   - On psycopg 3 the documented recipe gave the same state.
   - On psycopg2 it did not: the connection was discarded, and the next checkout was clean (facts 7–10).
   - On both drivers the default reset sent nothing on return, because unit 1 had committed and the connection was idle (server-log summaries, `default`).

**(b) The documented recipe, verbatim, on psycopg2 with `postgresql+psycopg2://`**

7. **Every call raised.** Both calls in each run raised `AttributeError: 'psycopg2.extensions.connection' object has no attribute 'execute'` at the recipe's first statement, `dbapi_connection.execute("CLOSE ALL")`. The `after` listener never ran (`output/psycopg2.rep*.out`, arm `documented`: `reset_calls`, `pool_log[*].traceback`).
8. **The pool's response.**
   - On each return the pool logged "Exception during reset or similar" and fired `invalidate (AttributeError)`. That is twice per run: once for unit 1's connection, once for unit 2's (`pool_events`, `pool_log`).
   - The returned connection's backend disconnected, having sent no statement on return (`output/server-log-summary.psycopg2.rep*.txt`, `documented`).
9. **The next checkout was a new connection on a new backend.** Unit 1's backend had exited. The new session showed none of unit 1's state:
   - `current_user` app_login;
   - `app.tenant_id` unset (`NULL`);
   - `search_path` `"$user", public`;
   - `statement_timeout` 0;
   - no temp table.

   Its row landed in `public.item` by app_login (`output/psycopg2.rep*.out`; `output/psql-item-rows.txt`).
10. **Each tested return discarded the connection.** In every run, two units of work made 2 connects and 2 invalidations (`pool_events`). So unit 2 never reused unit 1's connection, and none of the five items reached it. Not covered: `terminate_only` resets, and other configurations.

**(c) The corrected example (roadmap §7), on both drivers**

11. **All five measured items were reset.** The next checkout, on the same backend and the same DBAPI connection, saw:
    - `current_user` app_login;
    - `app.tenant_id` `''`;
    - `search_path` `"$user", public`;
    - `statement_timeout` 0;
    - no temp table.

    The temp table was gone from `pg_class`, and the row landed in `public.item` by app_login (`output/<driver>.rep*.out`, arm `corrected`).
12. **What it sent.** On each return the hook sent only `DISCARD ALL`, under its own vxid, outside any transaction block. Its leading `rollback()` sent nothing, because the connection was idle (server-log summaries, `corrected`).

**(d) The corrected example on `isolation_level="AUTOCOMMIT"`**

13. **Autocommit survived the return,** on both drivers:
    - the driver's `autocommit` was True in unit 1 and in unit 2;
    - unit 2's row was visible to the witness before unit 2 ended;
    - none of unit 2's statements were wrapped in `BEGIN` (`corrected-autocommit`; server-log summaries).

    All five state items were reset.
14. **The negative control.** P7's variant sets `autocommit = False` after its reset. On an AUTOCOMMIT engine (psycopg 3), unit 2 ran with autocommit False, inside `BEGIN … COMMIT`, and its row was not visible before it ended (`p7-variant-autocommit`). The measurement in fact 13 does detect a lost autocommit.

**(e) Connect-time `search_path`**

15. **Under the corrected example, the docs' connect handler's `search_path` was lost after the first return,** on both drivers. "Setting Alternate Search Paths on Connect" is the handler that runs `SET SESSION search_path='tenant_s'`.
    - Unit 1 began with `search_path` `tenant_s`. Unit 2 saw `"$user", public`, and its row landed in `public.item`.
    - The `SET SESSION` statement was sent once, at connect, and not again (`corrected-connect-search-path`; server-log summaries).
16. **`connect_args={"options": "-csearch_path=tenant_s"}` survived `DISCARD ALL`,** on both drivers. Unit 2 saw `tenant_s`, and its row landed in `tenant_s.item` by app_login (`corrected-options-search-path`).
17. **`application_name`, passed as a connection parameter, also kept its value after `DISCARD ALL`.** The server log's `app=` field is unchanged on the statements that follow each `DISCARD ALL` (`output/server-log.<driver>.rep*.txt`).
18. In these runs neither dialect sent a session-level `SET` at connect. Every `SET` in the log came from the test, the docs' connect handler, or psycopg2 (fact 20). So `DISCARD ALL` undid no setting SQLAlchemy had made.

**Added beyond the brief**

19. **`isolation_level="REPEATABLE READ"` survived the corrected example,** on both drivers. Unit 2's `transaction_isolation` was `repeatable read`. Both drivers start each transaction with `BEGIN ISOLATION LEVEL REPEATABLE READ`, so no session setting is involved (`corrected-repeatable-read`; server-log summaries).
20. **On psycopg2 with REPEATABLE READ,** each return sent `SET default_transaction_isolation TO DEFAULT` after `DISCARD ALL`, and the next transaction was still REPEATABLE READ (server-log summary, psycopg2 `corrected-repeatable-read`).
    - Src: psycopg2 sends it when the hook restores `autocommit = False` on a connection with a non-default isolation level (`psycopg/connection_int.c:1321-1330`).
    - That is one extra round trip per return.
21. **On psycopg 3, after psycopg had prepared a statement server-side,** the corrected example's `DISCARD ALL` was followed by `DEALLOCATE ALL`.
    - The next checkout started with 0 prepared statements on the server.
    - It ran the same query 8 times without error, and the statement was prepared again under a new name: `_pg3_1` after `_pg3_0` (`corrected-prepared`; server-log summary).
    - Src: psycopg clears its prepared-statement state when it sees the `DISCARD ALL` command status, and schedules that `DEALLOCATE ALL` (`_preparing.py:82-100`, `176-189`).

**PostgreSQL itself** (`output/psql-checks.out`; one run, `psql` as app_login, no Python)

22. **Inside a block that rolls back,** `begin; close all; reset all; discard temp; rollback;` left the role, the GUC, `search_path`, `statement_timeout` and a temp table unchanged.
23. **Outside a transaction block,** `close all; reset all; discard temp;` reset the GUC, `search_path` and `statement_timeout`, and dropped the temp table. The role stayed tenant_a.
24. **`DISCARD ALL` inside a transaction block fails** with `ERROR:  DISCARD ALL cannot run inside a transaction block`. Outside one, it reset the role and dropped a temp table. `RESET ROLE` also reset the role.

**The demo** (`demo_reset_recipe.py`; `output/demo/`)

25. **The 64-line demo reproduces facts 4, 9 and 11,** 3 of 3 per driver, with byte-identical stdout.
    - On psycopg 3 the documented hook's six reset transactions are `aborted`.
    - On psycopg2, each returned connection's backend disconnected (`output/demo/server-log-summary.txt`, `output/demo/psql-xact-status.txt`).

**The supplement, after the outside review** (`supplement/`)

26. **`CLOSE ALL` takes effect even though the recipe's block rolls back** (`supplement/output/psql-hold-cursor.rep*.out`; `psql` as app_login).
    - A WITH HOLD cursor, declared in a committed transaction, was gone after `begin; close all; reset all; discard temp; rollback;`.
    - Controls: the cursor survived `begin; rollback;`, and `CLOSE ALL` alone in a rolled-back block also closed it.
    - So on psycopg 3 the recipe does close holdable cursors. What it leaves in place are the GUCs, `search_path`, `statement_timeout`, the role and temp tables.
27. **The documented recipe on an AUTOCOMMIT engine (psycopg 3).**
    - It sent `CLOSE ALL`, `RESET ALL` and `DISCARD TEMP` each outside a transaction block, and no `ROLLBACK` (`supplement/output/server-log-summary.psycopg.rep*.txt`, `s-documented-autocommit`).
    - The next checkout saw the GUC, `search_path`, `statement_timeout` and the temp table reset. The role was still tenant_a: its row landed in `public.item` by tenant_a (`supplement/output/psycopg.rep*.out`; `supplement/output/psql-item-rows.txt`).
    - This matches `psql` fact 23.
28. **The corrected example with the default `pool_reset_on_return="rollback"`** reset all five items on both drivers. On each return the log shows only the hook's `DISCARD ALL`. The pool's own rollback sent nothing, because the connection was idle (`s-corrected-default-reset`).
29. **A connection returned with its transaction open.** Unit 1 committed its session state, then left an uncommitted insert open when its `with engine.connect()` block ended.
    - `close()` sent `ROLLBACK`. The reset call then received `transaction_was_reset=True`, on an idle connection (`reset_calls`; server-log summaries).
    - The uncommitted row never became visible to the witness. `psql` reads all 18 of those transactions as `aborted` (`supplement/output/psql-xact-status.txt`).
30. **In that flow,** without a hook (the control), all five items carried over on both drivers. With the corrected example, under `pool_reset_on_return=None` or the default, all five were reset on the same DBAPI connection (`default-open-transaction`, `corrected-open-transaction`, `corrected-open-transaction-default-reset`).

## Source lines

**SQLAlchemy 2.1.6,** identical on `main`:
- **The recipe:** `lib/sqlalchemy/dialects/postgresql/base.py:275-336`.
  - The heading is at 277.
  - "The implementation will end transactions in progress as well as discard temporary tables" is at 295–298.
  - The URL `postgresql+psycopg2://` is at 311, and `pool_reset_on_return=None` at 313.
  - The hook is at 317–326: its `dbapi_connection.execute(...)` calls at 320–322, and `dbapi_connection.rollback()` at 326.
  - The `versionchanged:: 2.0.0b3` note is at 328–332.
- **"Setting Alternate Search Paths on Connect":** `dialects/postgresql/base.py:338-371`. The handler is at 359–366. Its rationale, that it runs outside any transaction "and therefore will not be reverted when the DBAPI connection has a rollback", is at 368–371.
- **The SQL Server example of the same shape:** `doc/build/core/pooling.rst:209-235`, `dbapi_connection.execute("{call sys.sp_reset_connection}")` then `dbapi_connection.rollback()`. "Reset On Return" is at 128–144.
- **The `reset` event is dispatched before the pool's own reset-on-return:** `lib/sqlalchemy/pool/base.py:1465-1474`, then 1479–1499. Both are in `_ConnectionFairy._reset`, at 1458–1499.
- **An exception from the hook** is logged as "Exception during reset or similar" (`pool/base.py:1041-1044`). For an `Exception`, the record is then invalidated (1059–1060). Both are in `_finalize_fairy` (955–1094), called at 1020–1025.
- **`PoolResetState`,** with its fields `transaction_was_reset`, `terminate_only` and `asyncio_safe`: `pool/base.py:48-90`.

**psycopg 3.3.6:**
- **`_preparing.py:82-100`** (`_should_discard`). It clears the prepared-statement state when a command status matches `^(?:DROP|ALTER|ROLLBACK|DISCARD ALL|DEALLOCATE ALL)\b`.
- **`_preparing.py:176-189`** (`clear()`).
- **`_connection_base.py:557-575`** (`_get_tx_start_command`) builds `BEGIN ISOLATION LEVEL …`.

**psycopg2 2.9.13:** `psycopg/connection_int.c:1321-1330`. On leaving autocommit with a non-default isolation level, it sets `default_transaction_isolation` back to `default`. The file was fetched from tag `2.9.13` (SHA-256 `989b0c6207c478e30313ff6122275dad9140166ab40204880eae8d18d0b2f82a`).

## History of the recipe

Src: the commits, issues and discussions below were read at their pinned versions, read-only. Dates are committer dates unless stated.

- **Added** in `b4261c45a` (Mike Bayer, committed 2022-10-30, "ensure pool.reset event always called for reset"), for issue #8717. The URL was then `postgresql+pyscopg2://`, and the hook was named `_reset_mssql`.
- **Renamed** to `_reset_postgresql` in `7249fa4a5` (2022-11-02), after a comment on #8717 pointed out the name.
- **URL typo fixed** to `postgresql+psycopg2://` by PR #12526 (`f2a9ecde29`, merged 2025-04-15). Its description: "the first example in the documentation of a particular connector, which [might] result in copy+pastes". The reviewer replied: "strange that it wasn't noticed before!".
- **The 1.4 branch** carries a variant (`rel_1_4_54`). It has no `terminate_only` check, and a `versionchanged:: 1.4.43` note. Its PostgreSQL dialect directory has no psycopg 3 module (`psycopg.py`); 2.0.0 does.
- **The motivating issue** is #8693 (open since 2022-10-21: SQL Server, `sp_reset_connection`). There the maintainer wrote that he was "doing better docs for 'how to make your own reset'".
- **Discussion #6905.** The thread began in 2021; the exchange cited here is from 2022-08-15/16, before the recipe existed.
  - A maintainer suggested a `checkin` handler running `DISCARD TEMPORARY` through a cursor.
  - The user reported that the temp tables persisted.
  - The maintainer replied "in the event hook, call commit", and the user confirmed "This is working!".

## Upstream search

`output/github-search.txt`; GraphQL, read-only, 2026-10-25 01:24:21–01:24:56 UTC.

- **The queries.** Twelve, each over issues and pull requests, and over discussions, for all time:
  - `reset_on_return`;
  - `DISCARD`;
  - `"RESET ALL"`;
  - `reset event psycopg`;
  - `"DISCARD ALL"`;
  - `"DISCARD TEMP"`;
  - `postgresql_reset_on_return`;
  - `"Resource Reset"`;
  - `"CLOSE ALL"`;
  - `pool reset event postgresql`;
  - `pool_reset_on_return psycopg`;
  - `_reset_postgresql`.
- **The recorded queries found no report** that the recipe leaves session state in place on psycopg 3, or that it raises on psycopg2. This is a search result, not proof that no report exists.
- **The nearest items:**
  - #8693 and #8717 (the recipe's origin);
  - discussion #6905 (above);
  - PR #12526 (the typo fix in the recipe's URL);
  - discussion #12486 (2025-03-31). A user reported that `SET ROLE` and `search_path` carried over to the next pooled checkout.
    - The maintainer explained that PostgreSQL session state persists unless the pool resets it. He named `DISCARD ALL`, and pointed to "a [custom reset scheme]" and "a [detailed recipe]". The second link targets `dialects/postgresql.html#postgresql-reset-on-return`, this recipe.
    - The user chose not to use it. They ran `RESET ROLE; SET search_path TO DEFAULT;` in a transaction of their own instead;
  - discussion #11680 (2024-08). An idle-in-transaction timeout. It names its test hook `_reset_postgresql`, but does not use the recipe.

## Scripts and outputs the author can paste

- **`demo_reset_recipe.py`** (64 lines) and its outputs:
  - `output/demo/psycopg.rep1.stdout` and `output/demo/psycopg2.rep1.stdout`, 4 lines each;
  - on psycopg2, `output/demo/psycopg2.rep1.stderr`, the two tracebacks with the paths masked.

  It needs the two roles described in its header, and a passfile or `PGPASSWORD`. Its URL uses `127.0.0.1:55492/chk3`.
- **`psql_checks.sql`** and `output/psql-checks.out,` for the PostgreSQL mechanism without SQLAlchemy.
- **`supplement/psql_hold_cursor.sql`** and `supplement/output/psql-hold-cursor.rep1.out,` for `CLOSE ALL` and WITH HOLD cursors.
- **The server-log lines for fact 2.** From `output/server-log.psycopg.rep1.txt`, search for `app=chk3-psycopg-documented-r1`. Its `BEGIN … ROLLBACK` block under vxid `9/4` is five lines.
- **The full program** (`chk3_reset_recipe.py`, about 260 lines) and `supplement/chk3_supplement.py` are the evidence, not paste candidates.

## Open questions, and contradictions of earlier claims

- **One earlier claim was too broad.** The roadmap (§1, §3.2 E) and the tracker said that the recipe "resets nothing" on psycopg 3. CHK-3 supports that only for the five measured items, on a transactional engine:
  - its `CLOSE ALL` does close WITH HOLD cursors (fact 26);
  - on an AUTOCOMMIT engine it resets everything measured except the role (fact 27).
- **What held, as measured:**
  - **H-d (roadmap §3.2).** On psycopg2, each tested return raised before sending any SQL, and the pool discarded the connection (facts 7–10). Nothing measured leaked, because no connection was reused.
  - **"The hook ran"** was an inference in P7 and in the roadmap (§3.1, §3.2 E). It is now observed (facts 1–2).
  - **"Startup options survive"** was Judg in roadmap §3.2 E.3. It is now observed for `DISCARD ALL` (fact 16).
  - **psycopg's prepared statements after `DISCARD`.**
    - They were Src in roadmap §3.2 E.3, citing `_preparing.py:82-99`, and are now observed (fact 21).
    - In 3.3.6 the function spans lines 82–100.
    - The same regex also matches `ROLLBACK`, `DROP`, `ALTER` and `DEALLOCATE ALL`.
- **Line numbers.** Before this check, the tracker's PY-5 cited 2.1.5 lines in `pool/base.py` (`1043-1053`, `1451-1467`). The updated tracker cites 2.1.6's: 1041–1060 and 1458–1474. The recipe's own lines (275–336) are unchanged.
- **Not run:**
  - asyncpg, pg8000, and psycopg's async connection. The roadmap's §7 says the example is not meant for asyncpg (#270);
  - pgbouncer, other PostgreSQL versions, Linux clients, and pools larger than one;
  - `terminate_only=True`;
  - `LISTEN` and advisory locks under the documented recipe. It sends neither `UNLISTEN` nor an advisory unlock;
  - a `checkout` handler as the alternative to a connect-time `SET SESSION` (roadmap §7);
  - whether the SQL Server example works on pyodbc.
