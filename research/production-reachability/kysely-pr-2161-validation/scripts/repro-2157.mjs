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
