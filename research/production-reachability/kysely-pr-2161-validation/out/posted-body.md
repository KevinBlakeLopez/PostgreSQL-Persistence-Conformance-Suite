Thanks for the quick fix. I ran the two cases from #2157 against the pkg.pr.new build of `ef60ffe` and against 0.29.7. Both now reject with `AbortedTransactionError`, and a separate connection confirms the transaction was aborted and the row is gone.

```
0.29.7
startTransaction: commit resolved, isCommitted=true, isRolledBack=false, pg_xact_status=aborted, rows=0
transaction().execute(): resolved, pg_xact_status=aborted, rows=0

#2161 (ef60ffe)
startTransaction: commit rejected (AbortedTransactionError), isCommitted=false, isRolledBack=true, pg_xact_status=aborted, rows=0
transaction().execute(): rejected (AbortedTransactionError), pg_xact_status=aborted, rows=0
```

pg 8.23.1, Node 24.14.1, PostgreSQL 18.6. Three runs per build, same output each time.

A longer version of the script also checked plain commits, savepoint recovery, and a deferred FK failing at `COMMIT`. Those behave the same as on 0.29.7, and the pooled connection is idle and reusable after every case.

One thing existing code may hit: the current `commit()` docs example calls `trx.rollback()` in the `catch`. With this change that call throws `Transaction is already rolled back`, which replaces the `AbortedTransactionError`. The updated example avoids it, but code written against the old one will see the rollback error instead.

<details>
<summary>Script</summary>

```js
import pg from 'pg'
import { Kysely, PostgresDialect, sql } from 'kysely'

const config = {
  host: '127.0.0.1',
  port: Number(process.env.PGPORT),
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  database: process.env.PGDATABASE,
}
const db = new Kysely({ dialect: new PostgresDialect({ pool: new pg.Pool({ ...config, max: 1 }) }) })
const observer = new pg.Client(config) // independent connection for the ground truth
await observer.connect()
await observer.query('drop table if exists item; create table item (id int primary key)')

async function writeThenCatchDuplicate(trx) {
  await trx.insertInto('item').values({ id: 1 }).execute()
  const { xid } = (await sql`select pg_current_xact_id()::text as xid`.execute(trx)).rows[0]
  await trx.insertInto('item').values({ id: 1 }).execute().catch(() => {}) // 23505, caught
  return xid
}

async function outcome(fn) {
  try {
    await fn()
    return 'resolved'
  } catch (e) {
    return `rejected (${e.name})`
  }
}

async function groundTruth(xid) {
  const fate = (await observer.query('select pg_xact_status($1::xid8) as s', [xid])).rows[0].s
  const rows = (await observer.query('select count(*)::int as n from item')).rows[0].n
  return `pg_xact_status=${fate}, rows=${rows}`
}

await observer.query('truncate item')
const trx = await db.startTransaction().execute()
const xid1 = await writeThenCatchDuplicate(trx)
const commit = await outcome(() => trx.commit().execute())
console.log(`startTransaction: commit ${commit}, isCommitted=${trx.isCommitted}, isRolledBack=${trx.isRolledBack}, ${await groundTruth(xid1)}`)

await observer.query('truncate item')
let xid2
const managed = await outcome(() => db.transaction().execute(async (t) => { xid2 = await writeThenCatchDuplicate(t) }))
console.log(`transaction().execute(): ${managed}, ${await groundTruth(xid2)}`)

await observer.end()
await db.destroy()
```

</details>

