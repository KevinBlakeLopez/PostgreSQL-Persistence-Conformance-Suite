# Draft: Knex

**Not filed.** This draft restates knex#6547. Production relevance is K1 on the [filed-items page](../../filed-items-production-relevance/README.md) (2026-10-26, low). It was not searched again.

Suggested title: `transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [knex/knex](https://github.com/knex/knex/issues/new)

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and the Knex transaction then commits, Knex's `COMMIT` query resolves. No error is raised. The earlier writes are gone.

Knex 3.3.0 treats that as a successful transaction. `commit()` sends `COMMIT;` with status `1` (`lib/execution/transaction.js`). `query()` resolves the transaction promise when that query promise resolves. It does not read the command tag. The Knex rows in that run logged that `COMMIT` was sent and did not log a reply tag. The command tag `ROLLBACK` is the plain node-postgres control in the same run: `COMMIT` resolved with that tag, and that control reported `rolled_back`.

### Versions

- Knex 3.3.0
- pg 8.23.1
- Node.js 24.14.1
- PostgreSQL 18.6

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
