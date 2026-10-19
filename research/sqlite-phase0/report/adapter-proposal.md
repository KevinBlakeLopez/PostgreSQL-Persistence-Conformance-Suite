# SQLite adapter proposal

Phase 0 does not add an adapter. This is the smallest later step that the baseline supports. It does not require a persistence framework, a change to the PostgreSQL adapters, a change to their expected results, a new report schema, or a shared API that hides the differences.

## What can be added without touching shared PPCS code

A sibling directory, on the pattern of this `research/sqlite-phase0/controls/` package:

- One program, standard-library `sqlite3` only.
- `autocommit=True` and SQL `BEGIN` / `COMMIT` / `ROLLBACK`.
- File-backed databases, one file per case per repetition.
- A second connection as the observer.
- The same JSON shape this baseline already writes: requested SQL, driver exception and `sqlite_errorcode` / `sqlite_errorname`, `in_transaction` before and after, and the second connection's rows.

That program does not speak the PPCS protocol, because the protocol's checkpoint requires `pg_backend_pid` and `pg_current_xact_id`. Inventing those fields for SQLite would be the shared change this proposal refuses.

Estimated shared-infrastructure change: none for that control.

Dependency: Python 3.12 or newer, so `autocommit` and `sqlite_errorcode` exist. No package install.

## First adapters, in order

Runtime behavior below is the sqlite3 baseline. Framework notes are source inspections of packages already installed for the PostgreSQL adapters. They were not executed on SQLite in this phase.

### 1. `sqlite3` control

The baseline is that control. Promote it only by copying the scripts into an adapter directory when someone wants it in the tree as a supported check. Keep it out of `harness/run.mjs`.

It can test the questions the matrix marks as portable or adaptable: commit and rollback visibility, caught unique violation then `COMMIT`, `ROLLBACK TO` a missing savepoint, savepoint release then outer rollback, close or rollback before reuse, and transactional DDL including a caught error then `COMMIT` versus `ROLLBACK`.

### 2. SQLAlchemy Core

Source: SQLAlchemy 2.1.5, `dialects/sqlite/pysqlite.py` and `dialects/sqlite/base.py`, from the PostgreSQL adapter's virtualenv.

- The dialect's documented recipe sets `isolation_level = None` and emits `BEGIN` from the `begin` event. On this Python, `isolation_level=None` leaves `autocommit` at legacy `-1`, and `Connection.commit()` then does trace `COMMIT` and clear `in_transaction` (SQLITE-06 `method-commit-isolation-level-none`). That is the mode the recipe is written for.
- `autocommit=True` is a different mode. In that mode `commit()` and `rollback()` did not end a SQL `BEGIN`. The same source file says not to move `Connection.autocommit` off `LEGACY_TRANSACTION_CONTROL` when using SQLAlchemy's AUTOCOMMIT isolation.
- Isolation values the dialect will set are `READ UNCOMMITTED` and `SERIALIZABLE`, implemented as `PRAGMA read_uncommitted`. That is not TX-05.

Enough information to test: `Connection.begin()`, `commit()`, `rollback()`, and `begin_nested()` emit SQL the second connection can check. Phase 1 should record the trace, because the dialect's begin path is the thing that can disagree with `autocommit=True`.

Do not modify `adapters/sqlalchemy-core`. A SQLite module would be a new adapter, or a later mode, after the control exists.

### 3. Django ORM

Source: Django 6.1.2, `django/db/backends/sqlite3/base.py`, from the Django adapter virtualenv.

- `_set_autocommit` writes `isolation_level` `None` or `""`. It does not set `Connection.autocommit`.
- `_start_transaction_under_autocommit` executes `BEGIN` while leaving autocommit mode on, with a comment that disabling autocommit breaks savepoints.
- `_savepoint_allowed` is true only inside an atomic block.
- `disable_constraint_checking` sets `PRAGMA foreign_keys=OFF` and reads the pragma back, because the assignment does not take effect inside a transaction. SQLITE-05 observed that: `PRAGMA foreign_keys=OFF` inside a transaction returned success and the connection still read `1`.

`transaction.atomic()` is explicit SQL plus savepoints, which this baseline can score. The PostgreSQL adapter's `atomic()` behavior must not be copied across as the expected SQLite result. A caught `IntegrityError` will leave the SQLite transaction open.

### 4. SQLAlchemy ORM

Not separately executed. `Session.begin()` / `begin_nested()` sit on the same SQLite dialect as Core. Do this after Core, and only to see whether the session emits its own `BEGIN` or relies on legacy implicit `BEGIN`. The trace callback is the check. No new abstraction.

### 5. Tortoise ORM

Source: Tortoise 1.1.9, `tortoise/backends/sqlite/client.py`, from the Tortoise adapter virtualenv. It uses aiosqlite.

- `begin` calls `commit()` and then executes `BEGIN`.
- Nested work uses `SAVEPOINT`, `ROLLBACK TO`, and `RELEASE`.
- The client takes an `asyncio.Lock` around the connection because one connection cannot hold two transactions.
- `capabilities` sets `can_rollback_ddl=True`. SQLITE-05 agrees for `CREATE TABLE` and `ALTER TABLE` inside an explicit transaction. It does not agree for every `PRAGMA`.

Aiosqlite was not run. The SQL is visible in source. A Phase 1 experiment should still trace it, because `begin()` commits first.

### Node

`better-sqlite3` is not installed here. Do not treat its transaction wrapper as measured. Kysely 0.29.6's `SqliteDriver` (`dist/dialect/sqlite/sqlite-driver.js`) calls `prepare` / `run` and sends `begin`, `commit`, `rollback`, `savepoint`, `rollback to`, and `release`. That is the better-sqlite3 API shape in source. It returns `changes` and `lastInsertRowid`, not a command tag. Pin and run `better-sqlite3` before a Kysely adapter.

Knex 3.3.0, `lib/dialects/sqlite3/execution/sqlite-transaction.js`: `begin` sends `BEGIN;`, warns if an isolation level was requested, and refuses to change `foreign_keys` inside a nested transaction. That matches SQLITE-05's foreign-key observation. A Knex control is reasonable after a sqlite3 or better-sqlite3 control, because Knex is the layer Lucid uses.

Lucid 22.4.2, the version pinned by `adapters/lucid`, recognizes dialect names `sqlite3`, `better-sqlite3`, and `libsql` in `query_runner/index.js`, and has a SQLite schema dump that shells out to the `sqlite3` CLI. The PPCS Lucid adapter sets `client: 'pg'`. SQLite support in that package is real source, and it was not run. It is in scope only after Knex's SQLite transaction path has a control. It does not belong in Phase 1.

## What a SQLite adapter must record

From SQLITE-06, the evidence that distinguishes outcomes is:

| Question | Evidence that exists | Evidence that does not exist |
| --- | --- | --- |
| Confirmed commit | SQL `COMMIT` succeeded, or `commit()` traced `COMMIT`, and `in_transaction` is false. A second connection sees the row. | A command tag. A transaction id. |
| Confirmed rollback | SQL `ROLLBACK` succeeded, or `OR ROLLBACK` fired, and `in_transaction` is false. The second connection does not see the pending row. | A `ROLLBACK` command tag on `COMMIT`. |
| Unknown outcome | Not observed for a living caller. | A lost network reply. |
| Failed cleanup | `in_transaction` still true after the API returned, or the connection is closed (`ProgrammingError`). | `25P02`. |
| Unsafe reuse | The next unit's `COMMIT` made the previous unit's row visible, and the second `BEGIN` raised `cannot start a transaction within a transaction` or was skipped. | `backend_xid` equality. |

## Shared changes that would eventually be required, and are not proposed for implementation

The current harness cannot host these cases without a real edit:

1. `harness/lib/observer.mjs` reads `pg_xact_status`, `pg_stat_activity`, and `pg_locks`. SQLite has no equivalent service. A second connection has to live beside the adapter, in the adapter's process or in a small SQLite-only runner.
2. The protocol checkpoint requires `pid` and `xid`. SQLite checkpoints would carry `in_transaction` and nothing that can be confirmed from outside the connection except row visibility.
3. `schema/result.v1.schema.json` requires transaction ids, fates, and SQLSTATE-oriented fields. Forcing SQLite results through that schema either invents values or marks every case `INCONCLUSIVE`.
4. Category B faults call `pg_terminate_backend`. Category C and D faults wrap `pg.Client.prototype.query`. Neither wrapper exists for `sqlite3`.

The smallest compatible modification, if a shared runner is ever approved, is optional: a database field on the case, an observer implementation selected by that field, and optional checkpoint fields. It is not a new framework, and it is not an edit to PostgreSQL expectations. It should not be written until a SQLite control has a stable set of cases worth running beside PostgreSQL.

Until that approval, SQLite stays a separate program and a separate evidence directory.
