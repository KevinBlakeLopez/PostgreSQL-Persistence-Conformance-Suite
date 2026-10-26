# Real-world evidence for the Python items

Compiled 2026-10-26. Written by: Claude Opus 5.5 (max).

This page records what public GitHub shows about whether the items in [the tracker](../../python-upstream-contribution-tracker.md) happen outside PPCS's reproductions: incident reports, project audits, code that turns a finding into damage, and fixes in other languages' drivers. The searches are in [`searches/`](searches/searches.txt). Nothing was posted.

**Kinds of evidence, strongest first:**

- **Production:** a report that quotes production logs or metrics.
- **Incident:** a person or project describes data loss on a real deployment.
- **Audit:** a project's own report, checked against its code.
- **Acknowledged:** a maintainer states the pattern exists in their code, without a stated consequence.
- **Harmful consumer:** real code that turns the behaviour into damage.
- **Other ecosystem:** the same mechanism reported or fixed in another language's driver.
- **Pattern count:** GitHub code-search totals. These count files where all the terms co-occur, not proven exposure, and some include vendored copies of SQLAlchemy.

Several reports below are code-audit findings rather than incident reports. Where a report quotes production data, that data was not checked beyond the report. A search that finds nothing is a search result, not proof of absence.

## Summary

| Item | Strongest real-world evidence | Kind |
| --- | --- | --- |
| PY-2 (asyncpg) | A production batch writer on SQLAlchemy's asyncio engine and asyncpg loses whole batches after one caught deadlock, while its counters report the writes | Production |
| PY-1 (psycopg; psycopg2 per CHK-9) | A project's batch writer on SQLAlchemy and psycopg2 drops a batch after one row's error and reports it saved; Airflow's scheduler has the catch-and-continue pattern | Audit; acknowledged |
| PY-7 (P5a) | On SQLite, a `COMMIT` refused with "database is locked" leaves the write open, and the next session commits it | Incident (reproduced by the project) |
| PY-6 (asyncpg `SET ROLE`) | A project's changelog records a pooled connection left in the previous caller's role | Incident (the project's changelog) |
| PY-4 (`after_rollback`) | Applications and a library delete uploaded files on `after_rollback` or `after_soft_rollback`; DuckLake deletes committed files after a lost `COMMIT` reply | Harmful consumer; other ecosystem |
| PY-5 (SQLAlchemy reset recipe) | A project adopts the recipe on psycopg 3 with a `READ_COMMITTED` engine; a maintainer pointed a user to it | Adoption |
| PY-3 (Tortoise) | The same symptom from a different cause | — |
| PY-24 (sqlalchemy-file) | Widely used; no incident in its tracker | Usage |
| PY-8, PY-15, PY-20 to PY-23 | None found | — |

## PY-1 and PY-2 (and PY-9): the false commit

A per-item `try/except` inside one transaction, followed by a commit, is a common batch shape. Every database error caught that way aborts the transaction: deadlocks, serialization failures, timeouts, constraint violations, values that are too long. Later items may then fail loudly with `InFailedSqlTransaction`, but the loss of the earlier items is silent, and counters report success.

- **Production, SQLAlchemy's asyncio engine on asyncpg** (CHK-10's path).
  - [alexander-bain/bainluck#8935](https://github.com/alexander-bain/bainluck/issues/8935) (2026-09-26) quotes production task metrics: one `DeadlockDetectedError`, then 18 `InFailedSQLTransactionError`s in the same batch.
  - Its cause section: the per-event loop runs in one transaction with `except Exception: ... continue`, "the batch ends with a single `await session.commit()`", and "the closing `COMMIT` on an aborted transaction is a silent `ROLLBACK`. So every event written EARLIER in that batch is thrown away too, while `events_processed` still counts it."
  - [#8129](https://github.com/alexander-bain/bainluck/issues/8129) (2026-09-23) quotes production worker logs of the same class: one deadlock, seven collateral failures in 150 ms. #8796 and #8913 are earlier reports of the class.
- **Audit, asyncpg.** [ValNyz/ldvelh#24](https://github.com/ValNyz/ldvelh/issues/24) (2026-10-14, verified on `dev` @ `a1af3f4`): per-item `try/except Exception` inside `async with conn.transaction()`, without savepoints; "the final COMMIT silently becomes a ROLLBACK, and `run()` still returns `success: True`".
- **Audit, SQLAlchemy on psycopg2** (CHK-9's path). [imanueldrexel/news-scraping#36](https://github.com/imanueldrexel/news-scraping/issues/36) (2026-09-16): per-row `try/except BaseException: log; continue` around `pg_insert(...)`, with one `session.commit()` after the loop; the batch is "silently drop[ped] … and now reports it as saved".
- **Acknowledged, Apache Airflow.** [apache/airflow#59120](https://github.com/apache/airflow/issues/59120) (2025-12-05, by an Airflow committer): the scheduler's `_create_dag_runs` does `except Exception: ... continue`, which "does not work when the exception is the result of a db error". It does not state what is lost.
- **Other ecosystems.** Driver maintainers treat the same mechanism as a bug:
  - [pgjdbc#4499](https://github.com/pgjdbc/pgjdbc/pull/4499) (2026-10-22, by pgjdbc maintainer vlsi) adds `raiseExceptionOnSilentRollback`;
  - pgx (Go) returns `ErrTxCommitRollback`, "commit unexpectedly resulted in rollback" (`tx.go`, lines 114–117 and 237);
  - [rust-postgres#1342](https://github.com/rust-postgres/rust-postgres/pull/1342) returns an error on `CommandComplete("ROLLBACK")`;
  - [postgres.js#1217](https://github.com/porsager/postgres/issues/1217) reports `sql.begin()` resolving when `COMMIT` returns `ROLLBACK`;
  - the 2020 pgsql-hackers thread "Error on failed COMMIT" discussed raising an error in the server, with the pgjdbc and Npgsql maintainers taking part.
- **Pattern counts,** files:
  - asyncpg's `async with conn.transaction()` with `except asyncpg.UniqueViolationError`: 670;
  - the same with `except asyncio.TimeoutError` and `timeout=`, CHK-11's trigger: 353;
  - psycopg2's `except psycopg2.errors.UniqueViolation` with `pass` and `conn.commit()`: 1,236;
  - psycopg 3's `except psycopg.errors.UniqueViolation` with `pass`: 1,210; `with conn.transaction()` with `except psycopg.errors`: 686;
  - SQLAlchemy's `except IntegrityError` with `continue` and `session.commit()`: 11,627; with `await session.commit()`: 2,221.

  Spot checks show these overstate exposure: PostHog (`products/warehouse_sources_queue/backend/core/jobs_db.py` @ `aa86410b6a`) and Datadog integrations-core (`postgres/datadog_checks/postgres/data_observability.py` @ `3a5556f9ad`) catch outside the transaction block, which is correct.
- **Not found:** a production report on psycopg 3 itself. Django's ORM paths are protected (PY-10). CHK-12's raw-SQL case in Django was not searched for.

## PY-7: a commit that fails before it is applied (P5a)

- **Incident, SQLite.** [lumenpearson/lessons#378](https://github.com/lumenpearson/lessons/issues/378) (2026-10-09): "a `COMMIT` the database refuses with «database is locked» does not end the transaction. The connection goes back to SQLAlchemy's pool still inside it, and the pool records it as reset, so it skips its own rollback. The next session to take that connection commits the failed write along with its own." The report says this happens although "the caller rolls back as it should". The project reproduced it while fixing a lost-row bug (its #373). This matches CHK-13, which ran later and independently.
- **Related symptoms, other causes:**
  - [open-webui#32741](https://github.com/open-webui/open-webui/issues/32741): a cancelled chat-message write can leave SQLite write-locked until a restart;
  - [Calibre-Web-NextGen#2631](https://github.com/new-usemame/Calibre-Web-NextGen/pull/2631): a shared session left inactive after a failed flush answers 500 until a restart.
- **PostgreSQL triggers:** no real-world signal. Of the 120 files that register a `commit` listener, the two well-known ones inspected cannot raise:
  - Close.io sync-engine, `inbox/sqlalchemy_ext/util.py` @ `9ca4df48ae`, only logs;
  - OpenStack oslo.db, `oslo_db/sqlalchemy/engines.py` @ `a91be4f9f0`, only clears a marker.

## PY-6: asyncpg keeps a role after `Connection.reset()`

- **Incident, from the project's changelog.** Percolation-Labs/percolate, `core/CHANGELOG.md` @ `0d736a3269`, lines 536–538: "A streamed turn no longer hands its connection back still as `authenticated`. A pooled connection left in a caller's role is the next caller's identity." Its test `core/tests/test_startup_refuses_a_database_it_cannot_serve.py` simulates the error a missing privilege produces, "permission denied for function set_config" (lines 47–51, 130–133).
- **Pattern counts,** files that also use asyncpg: `SET ROLE` with `acquire`, 579; `SET LOCAL ROLE`, 477; `RESET ROLE`, 338. Session-level roles are common, and many projects already reset them by hand.

## PY-5: the documented PostgreSQL reset recipe

- **Adoption.** zachatkinson/csfrace-scrape, `backend/src/database/models/engine.py` @ `3e3d802356`, describes its setup as "following SQLAlchemy 2.0 best practices" (line 4). It sets `isolation_level="READ_COMMITTED"` (line 42), and its `_reset_postgresql` runs `RESET ALL` and `DISCARD TEMP` (lines 52–61). Its URL uses `postgresql+psycopg` (`backend/src/database/utils.py`). That is CHK-3's no-reset configuration. Their code was not run, and whether they set session state was not checked.
- **Recommended for this problem.** In SQLAlchemy discussion [#12486](https://github.com/sqlalchemy/sqlalchemy/discussions/12486) (2025-03), a maintainer pointed a user, whose `SET ROLE` and `search_path` carried over, to this recipe.
- The code counts for the recipe's statements (5,344) and for `_reset_postgresql` (5,600) are mostly vendored copies of SQLAlchemy, whose dialect carries the recipe in a docstring. They do not measure adoption.

## PY-4 and PY-24: rollback hooks after a commit whose outcome is unknown

- **Harmful consumers.** Real handlers delete files when the session reports a rollback:
  - neelpote/nyayagraph, `apps/api/app/storage/transactional.py` @ `bd6b670052`, lines 24–35: `_remove_orphaned_storage_writes` deletes each object written during the transaction;
  - Ecronika/ticketsystem, `ticketsystem/extensions.py` @ `675532eef9`, lines 24–34: "Delete files that were saved during a rolled-back transaction";
  - the sqlalchemy-file library: its `after_soft_rollback` listener deletes uploads; CHK-14 showed the deletion after a lost `COMMIT` reply (PY-24).

  Under PY-4, these delete files that committed rows refer to. Code search finds 18 files with `after_rollback`, `listens_for` and `os.remove`.
- **Other ecosystems, the same consequence:**
  - [duckdb/ducklake#1802](https://github.com/duckdb/ducklake/issues/1802) (2026-10-18): the catalog committed, the reply was lost, DuckLake deleted the transaction's Parquet files, and "every read of the table then fails";
  - [block/buzz#3785](https://github.com/block/buzz/issues/3785) (Rust, sqlx): an in-doubt commit during a production PostgreSQL failover.
- **PY-24, usage:** sqlalchemy-file had about 90,000 downloads in the month before 2026-10-26 (pypistats). 370 files import it, including its own examples and starlette-admin's integration. By title, none of the 157 issues and pull requests in its tracker reports deleted files after a failed commit; the one deletion-related title, #84, is about files generated by its processors.
- **Not found:** a Python report of `after_rollback` firing on a committed transaction.

## PY-3: Tortoise `save()` after a rolled-back transaction

- **The same symptom, a different cause.** [tortoise-orm#1094](https://github.com/tortoise/tortoise-orm/issues/1094) (2022, open): "when I try to `save` data it says `saved` but actually isn't", alongside "Resetting connection with an active transaction". A 2023 comment reports `bulk_create` data not saved.
- **Pattern count:** 59 files combine `from tortoise`, `in_transaction`, `retry` and `.save()`. The top ten are Tortoise itself, four of PPCS's own programs, and five projects not inspected.

## Items with no signal

- **PY-8:** 15 files combine `from tortoise` with `DEFERRABLE`. Besides PPCS's programs, one project (michael-sulyak/anekrin) uses deferrable constraints with Tortoise; it was not inspected. No issue reports.
- **PY-15:** the trigger, a `rollback()` that raises before sending, has no distinctive search target.
- **PY-20:** nothing relevant.
- **PY-21:** no report of the SAVEPOINT loop losing records after SQLite ended a transaction. ComfyUI's [#16788](https://github.com/Comfy-Org/ComfyUI/pull/16788) (dropped batches, `no such savepoint`) has a different cause: threads sharing one in-memory connection.
- **PY-22:** the search was too broad to mean anything.
- **PY-23:** `sqlite3.connect(` with `autocommit=False` co-occurs in 5,088 files, which includes other libraries' parameters. The CPython tracker has only the issues that added the attribute (#83638, #93823).

## Related cases with other mechanisms

- **The response is sent before the commit.** [sneg55/pingcrm#165](https://github.com/sneg55/pingcrm/issues/165): a user self-hosting FastAPI with SQLAlchemy 2.0 and asyncpg imported 2,772 rows. About 2,676 looked successful, and the database held 0. The errors came from `flush()`, so SQLAlchemy raised `PendingRollbackError`, but the commit ran in a dependency teardown after the HTTP 200 had been sent.
- **A library swallows the commit error.** [celery/kombu#2793](https://github.com/celery/kombu/pull/2793): the SQLAlchemy transport's `_put` rolls back on `OperationalError` and returns normally, so a message that was never stored is reported as published.
- **A framework's unit of work.** [proteanhq/protean#1631](https://github.com/proteanhq/protean/issues/1631): an outer commit of a transaction marked rollback-only returns without raising; one user "lost writes this way in two batch handlers and a saga".

## Method

Read-only GitHub searches through `gh api search/issues` and `search/code`, run on 2026-10-26 (UTC), with `searches/rw_search.py`. The queries are in `searches/q-batch*.json`. `searches/searches.txt` lists each query with its total and the hits it showed. `searches/sqlalchemy-file-titles.txt` lists the titles of all 157 issues and pull requests in sqlalchemy-file's tracker, as read that day. One code query (`"statusmessage" "ROLLBACK"`) failed twice with GitHub's "too many shards failed" (HTTP 503) and has no result. The asyncpg, psycopg2, Tortoise, reset-recipe and role queries repeat those of an earlier pass on 2026-10-25, whose totals were within 16 files of these.
