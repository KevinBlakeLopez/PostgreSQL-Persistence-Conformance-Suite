# Draft: Kysely

**Filed 2026-10-21** as https://github.com/kysely-org/kysely/issues/2157. Duplicate search the same day: `isCommitted` returned only #1990, the closed connection-leak report. `ROLLBACK` with commit returned #1894, a migrations lock issue. `23505` returned nothing. `command tag` returned #428, a MySQL row-count request. npm `latest` was 0.29.7. No pull request.

Suggested title: `commit()` sets `isCommitted` when the transaction did not commit

Suggested labels: `bug`, `postgres`, `built-in dialect`

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and then commits, the `COMMIT` completes without raising. The earlier writes are gone.

Kysely 0.29.6 treats that completion as success.

Two call paths were recorded, three times each, on Kysely 0.29.6, pg 8.23.1, Node.js 24.14.1, and PostgreSQL 18.6. The run is `2026-10-19T18-15-49Z-b2c174`.

**Explicit `commit().execute()`.** `trx.commit().execute()` resolved. The public `isCommitted` flag was `true`. An independent connection did not see the row written before the caught `23505`. After the call returned, the session was idle and its last statement was `commit`. `pg_xact_status()` for that transaction was `aborted`. The Kysely case file's `command_tag` is `null`.

**Managed `db.transaction().execute(callback)`.** The callback caught `23505` and returned. The promise resolved. The row was absent, the session was idle, its last statement was `commit`, and `pg_xact_status()` was `aborted`. This case file also has `command_tag: null`. Its `driver.isCommitted` is `null`. The managed callback receives a `Transaction`. In 0.29.6 that class, which starts at `dist/kysely.js` line 541, has no `isCommitted` getter. The public getter is only on `ControlledTransaction`, lines 742–744. That is source, not a logged flag. In `dist/kysely.js` `TransactionBuilder.execute` (0.29.6, lines 668–692), after `commitTransaction` resolves, the method sets a local `state.isCommitted = true` and returns the callback's result. That assignment is source, not a value this run logged.

In the same run, a raw node-postgres `COMMIT` after a caught `23505` logged `command_tag: "ROLLBACK"` and did not throw. That is the pg control, not a field on the Kysely result. Kysely's `PostgresDriver.commitTransaction` (`dist/dialect/postgres/postgres-driver.js`, lines 55–57) awaits `executeQuery` of `commit` and does not use the returned result. `ControlledTransaction.commit()` (`dist/kysely.js`, lines 772–778) then sets `this.#state.isCommitted = true`. The public getter is lines 742–744. The doc comment on `commit()` begins at line 748, and line 749 says "Commits the transaction."

A savepoint recovery on these versions does commit the kept row. `savepoint('ppcs_sp')`, catch `23505`, `rollbackToSavepoint()`, then `commit()`. The case file shows the row visible, `pg_xact_status()` `committed`, and `driver.isCommitted: true`.

### Versions

- Kysely 0.29.6, the version that was run
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

On 2026-10-21, npm `latest` is 0.29.7. Its `PostgresDriver.commitTransaction` still awaits `executeQuery` of `commit` and does not use the result. `ControlledTransaction.commit` still sets `isCommitted` after that call. The line numbers below are from the 0.29.6 build.

### Reproduction

The recorded explicit path is `startTransaction().execute()`, an insert, a caught unique violation, then `commit().execute()`. The recorded managed path is `db.transaction().execute(callback)` with the same catch and a normal return. Visibility was read from another connection. The script `reproductions/node-commit-tag.mjs` has that explicit shape. Its stdout was not saved. The case files are the record.

### Expected

`commit().execute()` should not report that the transaction committed when the row is absent and `pg_xact_status()` is `aborted`. `isCommitted` should not be `true` in that case. `db.transaction().execute()` should not resolve as a successful commit for that same outcome.

### Actual

`commit().execute()` resolved and `isCommitted` was `true`. The row was absent.

`db.transaction().execute()` resolved. The row was absent. No public `isCommitted` value was logged for that path.

### Why it matters

Application code that catches a unique violation and then commits can treat `isCommitted` as proof that the earlier write was stored. The explicit path recorded that flag as `true` while an independent connection did not see the row.

### What this is not

Rolling back to a savepoint and then committing does persist the earlier write. That recovery was recorded separately, with the row visible and `isCommitted` true.
