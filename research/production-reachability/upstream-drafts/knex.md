# Draft: Knex

**Not filed.**

Suggested title: `transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [knex/knex](https://github.com/knex/knex/issues/new)

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and the Knex transaction then commits, PostgreSQL accepts `COMMIT` and reports command tag `ROLLBACK`. No error is raised. The effect is a rollback, and the earlier writes are gone.

Knex 3.3.0 treats that as a successful transaction. `commit()` sends `COMMIT;` with status `1` (`lib/execution/transaction.js`). `query()` resolves the transaction promise when that query promise resolves. It does not read the command tag. node-postgres puts the tag on `Result.command`, and for this statement the tag is `ROLLBACK`.

### Versions

- Knex 3.3.0
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6. In an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### Reproduction

```js
import knex from 'knex'

const db = knex({ client: 'pg', connection: process.env.DATABASE_URL })

await db.raw('create table item (id serial primary key, name text not null)')
await db.raw('create table uniq (id serial primary key, code text not null unique)')
await db('uniq').insert({ code: 'taken' })

await db.transaction(async (trx) => {
  await trx('item').insert({ name: 'kept' })
  try {
    await trx('uniq').insert({ code: 'taken' })
  } catch (error) {
    // 23505 unique_violation
    console.log(error.code)
  }
})

const rows = await db('item').select('name')
console.log(rows) // []
```

The promise returned by `transaction()` resolved. The `kept` row was not visible from another connection. `trx.commit()` after the same caught error also resolved.

This was repeated three times. A nested `trx.transaction()` around the duplicate insert, with the inner error caught and the outer callback returning, did commit the `kept` row. A callback that does not catch the unique violation rejects, and Knex sends `ROLLBACK`.

A reduced script printed:

```json
{
  "api": "knex.transaction(callback)",
  "version": "3.3.0",
  "sqlstate": "23505",
  "callback_resolved": true,
  "visible": []
}
```

### Expected

`knex.transaction()` should reject when PostgreSQL answers `COMMIT` with `ROLLBACK`. The same should happen for an explicit `trx.commit()`.

### Actual

The transaction promise resolves, and the insert from inside the transaction is not visible.

### Why it matters

Catching a unique violation and letting the transaction finish is a normal way to try an insert and keep the rest of the unit of work. Code after the resolved promise can return success for a row that was not stored. The connection is usable afterward, so the next request on that pool can commit its own row and hide the lost write.

### Relation to issue 6141

[knex/knex#6141](https://github.com/knex/knex/issues/6141) is a `COMMIT` that throws, including a deferred constraint, where the promise returned by manual `trx.commit()` does not reject. This case does not throw. The query promise resolves, status stays `1`, and `_resolver` runs. The command tag is the part that says the transaction was rolled back.
