# Draft: TypeORM

**Filed 2026-10-21** as https://github.com/typeorm/typeorm/issues/12992 Posted as `KevinBlakeLopez`. No pull request. The checks below are from that day. The body cites the transactions tutorial for the aborted transaction block. The command tag is from the run.

Duplicate search on 2026-10-21, `typeorm/typeorm`, open and closed. `afterTransactionCommit ROLLBACK` and `unique violation commit` returned nothing. `afterTransactionCommit` returned #2816, #8661, #10150, #10490, and #7749. None reports a PostgreSQL `COMMIT` tag of `ROLLBACK`. `ROLLBACK commit` also returned #12913, #9010, #10364, and #12959. #10364 is a savepoint conflict. #12959 is SQLite `RAISE(ROLLBACK)` and `SQLITE_FULL`, where the runner keeps `isTransactionActive` true. #12976, #12977, #12978, and #12979 do not report this.

npm `latest` on 2026-10-21 was 1.1.2, published 2026-10-08T07:24:58Z. The GitHub release `1.1.2` was published 2026-10-08T07:21:48Z. `dev` was `1.1.2-nightly.20261021`. The default branch `package.json` still said `1.1.2`.

https://www.postgresql.org/docs/current/sql-commit.html on 2026-10-21 was the PostgreSQL 18 `COMMIT` page. It says `COMMIT` commits the current transaction. It does not say that a statement error aborts the transaction, or that `COMMIT` then completes with command tag `ROLLBACK`. The body cites the transactions tutorial instead, and only for the aborted state: https://www.postgresql.org/docs/current/tutorial-transactions.html

Notes for us, not for the issue body. Run `2026-10-19T18-15-49Z-b2c174`. The harness keeps full evidence for the first repetition only. All three repetitions of the managed and explicit cases resolved, with `pg_xact_status()` `aborted` and `markers.tx` false. Hook counts and the driver trace are the first repetition only. `api_outcome.steps.command_tag` is `null`. The trace is node-postgres `res.command` (`pg-instrument.mjs`). Managed first repetition: `after_commit` 1, `after_rollback` 0, trace `command tag ROLLBACK` for `COMMIT`, `commit_replies` `["ROLLBACK", "COMMIT"]`. Explicit `commitTransaction()` matches that split. Savepoint recovery: all three repetitions have `markers.tx` true and fate `committed`. First repetition only: one subscriber, `after_commit` 1 and `after_rollback` 1, outer trace tag `COMMIT`. #12976, #12977, #12978, and #12979 do not report this.

Suggested title: `afterTransactionCommit` runs when `COMMIT` completes with command tag `ROLLBACK`

Suggested repo: [typeorm/typeorm](https://github.com/typeorm/typeorm/issues/new)

## Body

### What happened

On PostgreSQL, a statement error puts the transaction block in an aborted state. https://www.postgresql.org/docs/current/tutorial-transactions.html If the application catches that error and TypeORM then commits, `COMMIT` completes with command tag `ROLLBACK` and does not raise. The earlier writes are gone.

TypeORM 1.1.2 treats that completion as a committed transaction. `PostgresQueryRunner.commitTransaction` calls `query("COMMIT")`, sets `isTransactionActive` to false, and broadcasts `AfterTransactionCommit` (`driver/postgres/PostgresQueryRunner.js`). `query("COMMIT")` uses the default `useStructuredResult = false`, so `query()` returns `raw.rows`. Inside `query()`, `raw.command` is switched on for `UPDATE` and `DELETE`. `COMMIT` takes the default branch. `commitTransaction()` never receives the command tag.

`dataSource.transaction()` awaits that commit when the callback returns. A resolved call is TypeORM's report that the transaction committed.

### Versions

- TypeORM 1.1.2
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

### Reproduction

This is the same sequence as the recorded run: insert a row, catch a unique violation, and let the callback return. It is not the code that was executed. The run passed `qty: 0`. The subscriber in the run counted calls to `afterTransactionCommit` and `afterTransactionRollback`. Between the two inserts the run sent `select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`, and after `COMMIT` it sent `select 1 as ok`. `Item` is an `EntitySchema` for table `item`: `id` serial primary key, `name` text not null, `qty` integer not null default 0. `Uniq` is an `EntitySchema` for table `uniq`: `id` serial primary key, `code` text not null unique. `taken` is already committed. `qty` defaults to 0 on the table and on the `Item` schema.

```js
dataSource.subscribers.push({
  afterTransactionCommit() { console.log("afterTransactionCommit") },
  afterTransactionRollback() { console.log("afterTransactionRollback") },
})

await dataSource.transaction(async (manager) => {
  await manager.getRepository(Item).insert({ name: "kept" })
  try {
    await manager.getRepository(Uniq).insert({ code: "taken" })
  } catch (error) {
    // 23505
  }
})
```

Three runs of that sequence resolved, and another connection did not see the inserted row. PostgreSQL reported the transaction aborted.

On one recorded execution, `afterTransactionCommit` ran and `afterTransactionRollback` did not. On that same execution, node-postgres reported command tag `ROLLBACK` for the `COMMIT`. The run did not record which of those two happened first. TypeORM did not return that tag from `query()`.

`QueryRunner.commitTransaction()` after the same caught error resolved, and the row was absent. On one recorded execution the same subscriber's commit method ran, and node-postgres reported command tag `ROLLBACK` for that `COMMIT`.

A nested `manager.transaction()` around the duplicate insert, with that error caught by the outer callback, is a real savepoint recovery. The outer transaction committed the earlier row. On one recorded execution the same subscriber's rollback method and commit method each ran once, and the outer command tag was `COMMIT`.

### Expected

`dataSource.transaction()` should not report a committed transaction, and `afterTransactionCommit` should not run, when `COMMIT` completes with command tag `ROLLBACK`.

### Actual

On three runs the call resolved and the inserted row was not visible. On one recorded execution, `afterTransactionCommit` ran and `afterTransactionRollback` did not.

### Why it matters

`afterTransactionCommit` is where an application sends mail or enqueues work that should happen only after a successful commit. On one recorded execution it ran for a transaction PostgreSQL rolled back.
