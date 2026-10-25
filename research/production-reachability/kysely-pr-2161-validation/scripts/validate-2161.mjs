// Runs kysely#2157's reproduction and controls against one Kysely build.
// Usage: PGPASSWORD=... node validate-2161.mjs <pkgs-dir> <label> <port> [reps]
// Ground truth comes from an independent pg client: pg_xact_status() and row visibility.
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const [pkgsArg, label, portArg, repsArg] = process.argv.slice(2)
const PORT = Number(portArg)
const REPS = Number(repsArg ?? 3)
if (!pkgsArg || !label || !Number.isInteger(PORT) || PORT < 55000) {
  console.error('usage: node validate-2161.mjs <pkgs-dir> <label> <port, 55000+> [reps]')
  process.exit(2)
}

// This process may only reach its own container.
const connect = net.Socket.prototype.connect
net.Socket.prototype.connect = function (...args) {
  const o = typeof args[0] === 'object' && args[0] !== null ? args[0] : { port: args[0], host: args[1] }
  if (o.path || Number(o.port) !== PORT || o.host !== '127.0.0.1') {
    throw new Error(`net guard: refused ${o.path ?? `${o.host}:${o.port}`}`)
  }
  return connect.apply(this, args)
}

const pkgs = path.resolve(pkgsArg)
const require = createRequire(path.join(pkgs, 'package.json'))
const pg = require('pg')
const kyselyDir = path.join(pkgs, 'node_modules', 'kysely')
const K = await import(pathToFileURL(path.join(kyselyDir, 'dist', 'index.js')).href)
const { Kysely, PostgresDialect, sql } = K
const readVersion = (dir) => JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8')).version

const unhandled = []
process.on('unhandledRejection', (e) => unhandled.push(describe(e)))

const conn = { host: '127.0.0.1', port: PORT, user: 'k2161', database: 'k2161', password: process.env.PGPASSWORD }
const observer = new pg.Client({ ...conn, application_name: `k2161-${label}-observer` })
await observer.connect()

console.log(JSON.stringify({
  header: true,
  build: label,
  kysely: readVersion(kyselyDir),
  abortedTransactionErrorExported: typeof K.AbortedTransactionError === 'function',
  pg: readVersion(path.join(pkgs, 'node_modules', 'pg')),
  node: process.version,
  server: (await observer.query('show server_version')).rows[0].server_version,
  reps: REPS,
}))

await observer.query('drop table if exists item, child, parent')
await observer.query('create table item (id int primary key, note text)')
await observer.query('create table parent (id int primary key)')
await observer.query(
  'create table child (id int primary key, parent_id int references parent (id) deferrable initially deferred)',
)

function describe(e) {
  if (e == null) return null
  return { name: e.name ?? e.constructor?.name ?? null, code: e.code ?? null, message: String(e.message).split('\n')[0] }
}

function withTimeout(promise, ms, what) {
  let timer
  return Promise.race([
    promise,
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`timeout after ${ms} ms: ${what}`)), ms) }),
  ]).finally(() => clearTimeout(timer))
}

function makeDb(app) {
  // One connection, so the check after each scenario gets the same backend back.
  return new Kysely({ dialect: new PostgresDialect({ pool: new pg.Pool({ ...conn, max: 1, application_name: app }) }) })
}

async function txInfo(trx) {
  return (await sql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`.execute(trx)).rows[0]
}

async function insertDuplicate(trx) {
  try {
    await trx.insertInto('item').values({ id: 1, note: 'dup' }).execute()
    return null
  } catch (e) {
    return e.code ?? describe(e).message
  }
}

async function settle(fn) {
  try {
    const value = await fn()
    return { outcome: 'resolved', error: null, value: value ?? null }
  } catch (e) {
    return { outcome: 'rejected', error: describe(e), value: null }
  }
}

const scenarios = [
  ['explicit: caught 23505, then commit (#2157)', async (db) => {
    const trx = await db.startTransaction().execute()
    await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
    const info = await txInfo(trx)
    const caught = await insertDuplicate(trx)
    const commit = await settle(() => trx.commit().execute())
    return { ...info, caught, commit, isCommitted: trx.isCommitted, isRolledBack: trx.isRolledBack }
  }],
  ['managed: caught 23505, callback returns (#2157)', async (db) => {
    let info = {}
    let caught = null
    const commit = await settle(() => db.transaction().execute(async (trx) => {
      await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
      info = await txInfo(trx)
      caught = await insertDuplicate(trx)
      return 'callback-value'
    }))
    return { ...info, caught, commit }
  }],
  ['control: explicit commit', async (db) => {
    const trx = await db.startTransaction().execute()
    await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
    const info = await txInfo(trx)
    const commit = await settle(() => trx.commit().execute())
    return { ...info, commit, isCommitted: trx.isCommitted, isRolledBack: trx.isRolledBack }
  }],
  ['control: managed commit', async (db) => {
    let info = {}
    const commit = await settle(() => db.transaction().execute(async (trx) => {
      await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
      info = await txInfo(trx)
      return 'callback-value'
    }))
    return { ...info, commit }
  }],
  ['control: savepoint recovery, then commit', async (db) => {
    const trx = await db.startTransaction().execute()
    await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
    const info = await txInfo(trx)
    const sp = await trx.savepoint('sp1').execute()
    const caught = await insertDuplicate(sp)
    const back = await sp.rollbackToSavepoint('sp1').execute()
    const commit = await settle(() => back.commit().execute())
    return { ...info, caught, commit, isCommitted: back.isCommitted, isRolledBack: back.isRolledBack }
  }],
  ['control: explicit, deferred FK fails at COMMIT, caller rolls back', async (db) => {
    const trx = await db.startTransaction().execute()
    await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
    const info = await txInfo(trx)
    await trx.insertInto('child').values({ id: 1, parent_id: 99 }).execute()
    const commit = await settle(() => trx.commit().execute())
    const flags = { isCommitted: trx.isCommitted, isRolledBack: trx.isRolledBack }
    const rollback = await settle(() => trx.rollback().execute())
    return { ...info, commit, ...flags, rollback }
  }],
  ['control: managed, deferred FK fails at COMMIT', async (db) => {
    let info = {}
    const commit = await settle(() => db.transaction().execute(async (trx) => {
      await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
      info = await txInfo(trx)
      await trx.insertInto('child').values({ id: 1, parent_id: 99 }).execute()
      return 'callback-value'
    }))
    return { ...info, commit }
  }],
  ['compat: 0.29.7 docs pattern (rollback in catch) after caught 23505', async (db) => {
    const trx = await db.startTransaction().execute()
    await trx.insertInto('item').values({ id: 1, note: 'kept' }).execute()
    const info = await txInfo(trx)
    const caught = await insertDuplicate(trx)
    const surfaced = await settle(async () => {
      try {
        await trx.commit().execute()
      } catch (error) {
        await trx.rollback().execute()
        throw error
      }
    })
    return { ...info, caught, surfaced, isCommitted: trx.isCommitted, isRolledBack: trx.isRolledBack }
  }],
  ['compat: rows returned by raw sql`commit` and sql`rollback`', async (db) => {
    return db.connection().execute(async (c) => {
      const out = {}
      await sql`begin`.execute(c)
      out.commit = (await sql`commit`.execute(c)).rows
      await sql`begin`.execute(c)
      out.rollback = (await sql`rollback`.execute(c)).rows
      await sql`begin`.execute(c)
      await sql`savepoint s`.execute(c)
      out.rollbackToSavepoint = (await sql`rollback to savepoint s`.execute(c)).rows
      await sql`commit`.execute(c)
      return { raw: out }
    })
  }],
]

async function reuse(db, pid) {
  // The pool holds one connection: a hang here means it was never released.
  const now = (await withTimeout(sql`select pg_backend_pid() as pid`.execute(db), 5000, 'next checkout')).rows[0]
  const act = (await observer.query(
    'select state, backend_xid is null and xact_start is null as no_transaction from pg_stat_activity where pid = $1',
    [now.pid],
  )).rows[0]
  await withTimeout(db.insertInto('item').values({ id: 100, note: 'autocommit-after' }).execute(), 5000, 'autocommit write')
  const visible = (await observer.query('select count(*)::int as n from item where id = 100')).rows[0].n === 1
  return { sameBackend: now.pid === pid, state: act?.state ?? null, noTransaction: act?.no_transaction ?? null, autocommitWriteVisible: visible }
}

const results = []
for (const [si, [name, fn]] of scenarios.entries()) {
  for (let rep = 1; rep <= REPS; rep++) {
    await observer.query('truncate item, child, parent')
    const app = `k2161-${label}-s${si + 1}-r${rep}`
    const db = makeDb(app)
    let rec
    try {
      rec = await withTimeout(fn(db), 15000, name)
      if (rec.xid) rec.fate = (await observer.query('select pg_xact_status($1::xid8) as s', [rec.xid])).rows[0].s
      rec.rowsAfter = (await observer.query('select id, note from item order by id')).rows.map((r) => `${r.id}:${r.note}`)
      if (rec.pid) rec.reuse = await reuse(db, rec.pid)
    } catch (e) {
      rec = { ...(rec ?? {}), harnessError: describe(e) }
    }
    try {
      await withTimeout(db.destroy(), 5000, 'destroy')
    } catch (e) {
      rec.destroyError = describe(e)
    }
    results.push({ build: label, scenario: `s${si + 1}`, name, rep, app, ...rec })
    console.log(JSON.stringify(results.at(-1)))
  }
}

// Repetitions agree when everything except xid, pid and application name is identical.
const stable = (r) => JSON.stringify({ ...r, rep: 0, app: '', xid: r.xid ? 'x' : undefined, pid: r.pid ? 'p' : undefined })
for (const [si, [name]] of scenarios.entries()) {
  const reps = results.filter((r) => r.scenario === `s${si + 1}`)
  console.log(JSON.stringify({ summary: true, build: label, scenario: `s${si + 1}`, name, repsAgree: new Set(reps.map(stable)).size === 1, n: reps.length }))
}
console.log(JSON.stringify({ unhandledRejections: unhandled }))
await observer.end()
process.exitCode = unhandled.length ? 1 : 0
