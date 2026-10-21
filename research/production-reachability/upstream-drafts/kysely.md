# Draft: Kysely

**Not filed.**

Suggested title: `commit()` sets `isCommitted` when PostgreSQL rolls the transaction back

Suggested labels: `bug`, `postgres`, `built-in dialect`

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and then commits, PostgreSQL accepts `COMMIT` and reports command tag `ROLLBACK`. No exception is raised. The effect is a rollback, and the earlier writes are gone.

Kysely 0.29.6 treats that `COMMIT` as success.

`PostgresDriver.commitTransaction` runs `commit` and does not read the command tag (`dist/dialect/postgres/postgres-driver.js`). `ControlledTransaction.commit()` then sets `isCommitted` to `true` (`dist/kysely.js`). `db.transaction().execute(callback)` does the same with its internal flag and resolves the promise.

node-postgres exposes the tag on `Result.command`. For this `COMMIT` the tag is `ROLLBACK`.

### Versions

- Kysely 0.29.6
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6: in an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### Reproduction

```js
import { Kysely, PostgresDialect, sql } from 'kysely'
import pg from 'pg'

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL })
const db = new Kysely({ dialect: new PostgresDialect({ pool }) })

await sql`create table item (id serial primary key, name text not null)`.execute(db)
await sql`create table uniq (id serial primary key, code text not null unique)`.execute(db)
await sql`insert into uniq (code) values ('taken')`.execute(db)

const trx = await db.startTransaction().execute()
await trx.insertInto('item').values({ name: 'kept' }).execute()
try {
  await trx.insertInto('uniq').values({ code: 'taken' }).execute()
} catch (error) {
  // 23505 unique_violation. The application catches it and continues.
  console.log(error.code)
}
await trx.commit().execute()

console.log(trx.isCommitted) // true
const visible = await sql`select name from item`.execute(db)
console.log(visible.rows) // []
```

The same ending happens with `db.transaction().execute(callback)` when the callback catches `23505` and returns. The promise resolves, and the `item` row is not visible to another connection.

This was repeated three times. A savepoint recovery on the same versions does commit the kept row: `savepoint()`, catch the unique violation, `rollbackToSavepoint()`, then `commit()`. So a real commit is distinguishable from this one.

A reduced script printed:

```json
{
  "api": "kysely ControlledTransaction.commit()",
  "version": "0.29.6",
  "sqlstate": "23505",
  "commit_threw": false,
  "isCommitted": true,
  "visible": []
}
```

### Expected

`commit().execute()` should reject, and `isCommitted` should stay `false`, when PostgreSQL answers `COMMIT` with `ROLLBACK`. `db.transaction().execute()` should reject in that case instead of resolving.

`commit()` is documented as committing the transaction. `isCommitted` is the public flag for that outcome.

### Actual

`commit().execute()` resolves, `isCommitted` is `true`, and the insert from inside the transaction is not visible.

### Why it matters

Application code that catches a unique violation and then commits is a normal way to try an insert and keep the rest of the transaction. After `isCommitted` becomes true, that code can send mail, return success, or enqueue work for a row that was not stored. The connection itself is usable afterward: PostgreSQL has ended the transaction, so the next transaction on that connection can commit its own row. The failure is the success flag, not a poisoned connection.

### What this is not

This is not a failed savepoint. Rolling back to a savepoint and then committing does persist the earlier write.

I did not find an existing Kysely issue for `isCommitted` remaining true when PostgreSQL answers `COMMIT` with `ROLLBACK`.
