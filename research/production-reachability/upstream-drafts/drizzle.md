# Draft: Drizzle

**Not filed.**

Suggested title: `db.transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [drizzle-team/drizzle-orm](https://github.com/drizzle-team/drizzle-orm/issues/new)

**Before posting:**

- Issue only. A callback that catches an error and returns resolves today, and reporting the rollback would make that call reject. Do not open a pull request until the maintainers agree.
- This draft is the command tag only. It does not include a failed `ROLLBACK` returned to the pool, a `BEGIN` that throws before `release()`, or the process exit on a checked-out client's `'error'` event. Those are separate.
- **Duplicate search (2026-10-21), not exhaustive.** A search of `drizzle-team/drizzle-orm` for this `COMMIT` tag did not surface it. Nearby and different: #6083 (a transaction handle still accepts queries after the transaction has ended) and #1450 (closed; whether an exception rolls the callback back). Search again in the minutes before posting.
- Versions below are the ones that were run. Recheck the current release before posting. 0.45.4 and 1.0.0-rc.4 agreed.

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and the Drizzle callback then returns, PostgreSQL accepts `COMMIT` and reports command tag `ROLLBACK`. No error is raised. The effect is a rollback, and the earlier writes are gone.

Drizzle treats that `COMMIT` as success. `db.transaction()` resolves with the callback's value.

`NodePgSession.transaction` sends `COMMIT` and returns that value. It does not read the `pg` `Result`, including `command`. In 0.45.4 that function is `node-postgres/session.js` lines 180–194. In 1.0.0-rc.4 it is lines 50–65, and the control flow is the same. 1.0.0-rc.4 `session.execute` can return the full `pg` result for mode `"raw"`. `transaction()` still ignores it.

node-postgres exposes the tag on `Result.command`. For this `COMMIT` the tag is `ROLLBACK`.

### Versions

- Drizzle ORM 0.45.4 and 1.0.0-rc.4, `drizzle-orm/node-postgres`
- pg 8.23.1, pg-pool 3.14.0
- Node.js 24.14.1
- PostgreSQL 18.6

The two versions classified the same on this case. 1.0.0-rc.4 is called as `drizzle({ client: pool })`. 0.45.4 is called as `drizzle(pool)`.

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6. In an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### Reproduction

`uniq.code` is unique, and the row `code = 'taken'` is already committed.

```js
await db.transaction(async (tx) => {
  await tx.insert(item).values({ name: 'kept' })
  try {
    await tx.insert(uniq).values({ code: 'taken' })
  } catch (error) {
    // 23505. Caught inside the callback.
  }
})
```

Observed on three repetitions, on both 0.45.4 and 1.0.0-rc.4:

- `db.transaction()` resolved
- the reply to `commit` was command tag `ROLLBACK`
- before the API returned, the session was `idle in transaction (aborted)`
- after it returned, the session was idle and its last statement was `commit`
- `pg_xact_status()` was `aborted`
- another connection did not see the `kept` row

A nested `tx.transaction()` around the duplicate insert, with that error caught by the outer callback, committed the `kept` row. The outer command tag was `COMMIT`. That path is a real commit after a savepoint rollback.

### Expected

`db.transaction()` should reject when PostgreSQL answers `COMMIT` with `ROLLBACK`. The insert should not be reported as committed.

A callback that catches the error and returns resolves today. Reporting this rollback would make that call reject. I have not opened a pull request.

### Actual

The call resolves, and the insert is not visible. The connection is not left aborted: the next transaction on that pool can commit its own row, so checking only the next request misses the lost write.
