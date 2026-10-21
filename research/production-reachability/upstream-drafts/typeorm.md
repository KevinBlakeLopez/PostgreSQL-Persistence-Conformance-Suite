# Draft: TypeORM

**Not filed.**

Suggested title: `afterTransactionCommit` runs when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [typeorm/typeorm](https://github.com/typeorm/typeorm/issues/new)

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and TypeORM then commits, PostgreSQL accepts `COMMIT` and reports command tag `ROLLBACK`. No error is raised. The effect is a rollback, and the earlier writes are gone.

TypeORM 1.1.2 treats that as a committed transaction. `PostgresQueryRunner.commitTransaction` runs `query("COMMIT")`, sets `isTransactionActive` to false, and broadcasts `AfterTransactionCommit` (`driver/postgres/PostgresQueryRunner.js`). The `query()` result includes node-postgres `Result.command`, and `query()` already switches on `raw.command` for `UPDATE` and `DELETE`. `commitTransaction()` ignores it.

`ds.transaction(callback)` uses that method when the callback returns. A resolved call is TypeORM's report that the transaction committed.

### Versions

- TypeORM 1.1.2
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6. In an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### Reproduction

```js
await dataSource.transaction(async (manager) => {
  await manager.getRepository(Item).insert({ name: 'kept', qty: 0 })
  try {
    await manager.getRepository(Uniq).insert({ code: 'taken' })
  } catch (error) {
    // QueryFailedError, code 23505. 'taken' already exists.
  }
})
```

Observed on three repetitions:

- `ds.transaction()` resolved
- a subscriber's `afterTransactionCommit` ran
- `afterTransactionRollback` did not run for that completion
- node-postgres reported command tag `ROLLBACK` for that `COMMIT`
- before the API returned, the session was `idle in transaction (aborted)`
- `pg_xact_status()` was `aborted`
- another connection did not see the `kept` row

`QueryRunner.commitTransaction()` after the same caught error did the same thing.

A nested `manager.transaction()` around the duplicate insert, with that error caught by the outer callback, committed the `kept` row. The outer command tag was `COMMIT`, and both the rollback subscriber and the commit subscriber ran, which matches a savepoint rollback followed by a real commit.

### Expected

`ds.transaction()` should reject, and `afterTransactionCommit` should not run, when PostgreSQL answers `COMMIT` with `ROLLBACK`.

### Actual

The call resolves, `afterTransactionCommit` runs, and the insert is not visible.

### Why it matters

`afterTransactionCommit` is the callback an application uses for work that should follow a successful commit. Here it runs for a transaction PostgreSQL rolled back. The connection is not left aborted: the next transaction on that pool can commit its own row, so checking only the next request misses the lost write.
