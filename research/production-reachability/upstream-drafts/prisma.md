# Draft: Prisma

**Not filed.**

Suggested title: `$transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [prisma/orm](https://github.com/prisma/orm/issues/new). `prisma/prisma` redirects there.

**Before posting:**

- Issue only. A callback that catches an error and returns resolves today, and reporting the rollback would make that call reject. Do not open a pull request until the maintainers agree.
- This draft is the command tag only. It does not include a failed `ROLLBACK` returned through `client.release()` with no error, or an outer callback that catches a failed savepoint rollback and then commits. Those are separate.
- **Duplicate search (2026-10-21), not exhaustive.** A search of `prisma/orm` for this `COMMIT` tag did not surface it. Nearby and different: #26366 (a deferred exclusion constraint does not throw inside an interactive transaction), #29762 (a statement can commit after a timeout rollback), and #7786 (closed; a unique-constraint error inside a transaction was not parsed). Search again in the minutes before posting.
- Versions below are the ones that were run. Recheck the current release before posting.

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and the Prisma callback then returns, `COMMIT` completes without an error. The earlier writes are gone.

Prisma Client treats that `COMMIT` as success. `prisma.$transaction()` resolves.

`_transactionWithCallback` calls `transaction("commit")` when the callback returns (`@prisma/client` `runtime/client.mjs`). For `@prisma/adapter-pg`, the transaction manager sends `{ sql: "COMMIT" }` through `executeRaw` and, if that promise resolves, calls `transaction.commit()`. `PgQueryable.executeRaw` returns `result.rowCount` and does not read `result.command` (`@prisma/adapter-pg` `dist/index.js`).

On the first repetition, node-postgres recorded `Result.command` `ROLLBACK` for that `COMMIT`. The query compiler is not on this path. `$executeRaw` and the transaction manager's `COMMIT` go to the driver adapter as SQL.

### Versions

- Prisma Client 7.10.1
- `@prisma/adapter-pg` 7.10.1
- pg 8.23.1, pg-pool 3.14.0
- Node.js 24.14.1
- PostgreSQL 18.6

### Reproduction

`uniq.code` is unique, and the row `code = 'taken'` is already committed. The pool is a `pg.Pool` passed to `new PrismaPg(pool)`.

```js
await prisma.$transaction(async (tx) => {
  await tx.$executeRaw`insert into item (name) values ('kept')`
  try {
    await tx.$executeRaw`insert into uniq (code) values ('taken')`
  } catch (error) {
    // Prisma P2010. The underlying SQLSTATE is 23505. Caught inside the callback.
  }
})
```

Three repetitions agreed that `prisma.$transaction()` resolved, `pg_xact_status()` was `aborted`, and another connection did not see the `kept` row. On the first repetition:

- the reply to `COMMIT` was command tag `ROLLBACK`
- after the API returned, the session was idle and its last statement was `COMMIT`

A nested `tx.$transaction()` around the duplicate insert, with that error caught by the outer callback, committed the `kept` row. On the first repetition the trace was `ROLLBACK TO SAVEPOINT`, `RELEASE SAVEPOINT`, then `COMMIT` with command tag `COMMIT`. That path is a real commit after a savepoint rollback.

### Expected

`prisma.$transaction()` should reject when PostgreSQL answers `COMMIT` with `ROLLBACK`. The insert should not be reported as committed.

A callback that catches the error and returns resolves today. Reporting this rollback would make that call reject. I have not opened a pull request.

### Actual

The call resolves, and the insert is not visible. The connection is not left aborted: the next transaction on that pool can commit its own row, so checking only the next request misses the lost write.
