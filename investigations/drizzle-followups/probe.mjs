// Follow-ups that are not PPCS cases. Uses the disposable server from .ppcs-instance.json and the
// Drizzle install in adapters/drizzle. Does not change the adapter.
//
//   node investigations/drizzle-followups/probe.mjs
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { fileURLToPath } from 'node:url'

const adapterDir = fileURLToPath(new URL('../../adapters/drizzle/', import.meta.url))
const require = createRequire(`${adapterDir}package.json`)
const pg = require('pg')
// pg-pool removes its Client error listener while a client is checked out, and Drizzle does not add one.
// This process adds one so cleanup, and the connection-loss probe, can terminate a backend without discarding
// the probe's output. The PPCS adapter does not add it. Those suite cases exit on the unhandled error event.
const connect = pg.Client.prototype.connect
pg.Client.prototype.connect = function (cb) {
  this.on('error', () => {})
  return connect.call(this, cb)
}
const { drizzle } = await import(pathToFileURL(`${adapterDir}node_modules/drizzle-orm/node-postgres/index.js`))
const { sql } = await import(pathToFileURL(`${adapterDir}node_modules/drizzle-orm/sql/index.js`))

const inst = JSON.parse(readFileSync(new URL('../../.ppcs-instance.json', import.meta.url), 'utf8'))
const admin = { host: inst.host, port: inst.port, user: inst.user, password: inst.password, database: 'postgres' }
const dbname = `drizzle_probe_${process.pid}`

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const errText = (e) => {
  const cause = e?.cause
  return {
    class: e?.constructor?.name ?? null,
    code: cause?.code ?? e?.code ?? null,
    message: String(e?.message ?? e).split('\n')[0].slice(0, 240),
    cause: cause ? String(cause.message ?? cause).split('\n')[0].slice(0, 240) : null,
  }
}

async function withTimeout(promise, ms) {
  let timer
  const timeout = new Promise((resolve) => { timer = setTimeout(() => resolve({ timedOut: true }), ms) })
  try {
    return await Promise.race([
      Promise.resolve(promise).then((value) => ({ value }), (error) => ({ error })),
      timeout,
    ])
  } finally {
    clearTimeout(timer)
  }
}

console.log('probe database', dbname)
const root = new pg.Client({ ...admin, connectionTimeoutMillis: 5000 })
await root.connect()
await root.query(`create database ${dbname}`)
await root.end()

const base = { host: inst.host, port: inst.port, user: inst.user, password: inst.password, database: dbname }
const out = []
const record = (name, value) => { out.push({ name, ...value }); console.log(`\n## ${name}\n${JSON.stringify(value, null, 2)}`) }

async function observe(label) {
  const c = new pg.Client({ ...base, application_name: 'probe-observer' })
  await c.connect()
  const rows = await c.query('select name from probe_item order by id')
  const sessions = await c.query(`select pid, state, query, application_name from pg_stat_activity
    where datname = current_database() and application_name like 'probe%' and pid <> pg_backend_pid()`)
  await c.end()
  return { label, rows: rows.rows.map((r) => r.name), sessions: sessions.rows }
}

async function terminateProbeBackends() {
  const c = new pg.Client({ ...admin, connectionTimeoutMillis: 5000 })
  await c.connect()
  const act = await c.query('select pid from pg_stat_activity where datname = $1 and pid <> pg_backend_pid()', [dbname])
  for (const row of act.rows) await c.query('select pg_terminate_backend($1)', [row.pid])
  await c.end()
}

async function resetTable() {
  await terminateProbeBackends()
  const c = new pg.Client({ ...base, connectionTimeoutMillis: 5000 })
  await c.connect()
  await c.query('set lock_timeout = 2000')
  await c.query('drop table if exists probe_item')
  await c.query('create table probe_item (id serial primary key, name text not null)')
  await c.end()
}

// query_timeout is a node-postgres client option. A statement that outlives it rejects on the client
// while PostgreSQL may still be running it. Drizzle's catch then sends ROLLBACK on that same client.
async function queryTimeout(kind) {
  await resetTable()
  const trace = []
  const original = pg.Client.prototype.query
  pg.Client.prototype.query = function traced(config, values, cb) {
    const text = typeof config === 'string' ? config : config?.text
    if (typeof text === 'string' && !text.includes('pg_stat_activity')) trace.push(text.replace(/\s+/g, ' ').slice(0, 160))
    return original.call(this, config, values, cb)
  }
  const pool = kind === 'pool'
    ? new pg.Pool({ ...base, max: 1, query_timeout: 300, application_name: 'probe-drizzle' })
    : null
  if (pool) pool.on('error', () => {})
  const client = kind === 'client'
    ? new pg.Client({ ...base, query_timeout: 300, application_name: 'probe-drizzle' })
    : null
  if (client) { client.on('error', () => {}); await client.connect() }
  const db = drizzle(pool ?? client)
  const first = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('abandoned')`)
    await tx.execute(sql`select pg_sleep(2)`)
  }), 8000)
  const mid = await observe('after-first')
  const second = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('next')`)
  }), 8000)
  await sleep(2500)
  const end = await observe('after-settle')
  const later = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('later')`)
  }), 8000)
  const afterLater = await observe('after-later')
  if (pool) await withTimeout(pool.end(), 1000)
  if (client) await withTimeout(client.end(), 1000)
  pg.Client.prototype.query = original
  await terminateProbeBackends()
  return {
    kind,
    trace,
    query_timeout_ms: 300,
    first: first.timedOut ? { timedOut: true } : first.error ? { error: errText(first.error) } : { resolved: true },
    second: second.timedOut ? { timedOut: true } : second.error ? { error: errText(second.error) } : { resolved: true },
    later: later.timedOut ? { timedOut: true } : later.error ? { error: errText(later.error) } : { resolved: true },
    mid,
    end,
    afterLater,
  }
}

// statement_timeout is a PostgreSQL startup parameter. The server cancels the statement.
// The pool case above checks out again while pg_sleep is still running, and that BEGIN is outside
// Drizzle's try/finally, so the client stays checked out. This variant waits until the session is
// idle in transaction, then starts one later transaction. That is the checkout a later request makes.
async function queryTimeoutPoolAfterIdle() {
  await resetTable()
  const trace = []
  const original = pg.Client.prototype.query
  pg.Client.prototype.query = function traced(config, values, cb) {
    const text = typeof config === 'string' ? config : config?.text
    if (typeof text === 'string' && !text.includes('pg_stat_activity') && !text.includes('probe_item order')) trace.push(text.replace(/\s+/g, ' ').slice(0, 160))
    return original.call(this, config, values, cb)
  }
  const pool = new pg.Pool({ ...base, max: 1, query_timeout: 300, application_name: 'probe-drizzle' })
  pool.on('error', () => {})
  const db = drizzle(pool)
  const first = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('abandoned')`)
    await tx.execute(sql`select pg_sleep(2)`)
  }), 8000)
  let idle = null
  for (let i = 0; i < 20; i++) {
    idle = await observe('wait-idle')
    if (idle.sessions.some((s) => s.state === 'idle in transaction')) break
    await sleep(200)
  }
  const later = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('later')`)
  }), 8000)
  const afterLater = await observe('after-later')
  await withTimeout(pool.end(), 1000)
  pg.Client.prototype.query = original
  await terminateProbeBackends()
  return {
    first: first.timedOut ? { timedOut: true } : first.error ? { error: errText(first.error) } : { resolved: true },
    idle,
    later: later.timedOut ? { timedOut: true } : later.error ? { error: errText(later.error) } : { resolved: true },
    afterLater,
    trace,
  }
}

async function statementTimeout() {
  await resetTable()
  const pool = new pg.Pool({ ...base, max: 1, statement_timeout: 300, application_name: 'probe-drizzle' })
  pool.on('error', () => {})
  const db = drizzle(pool)
  const first = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('abandoned')`)
    await tx.execute(sql`select pg_sleep(2)`)
  }), 8000)
  const second = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('next')`)
  }), 8000)
  const end = await observe('statement-timeout')
  await withTimeout(pool.end(), 1000)
  await terminateProbeBackends()
  return {
    statement_timeout_ms: 300,
    first: first.timedOut ? { timedOut: true } : first.error ? { error: errText(first.error) } : { resolved: true },
    second: second.timedOut ? { timedOut: true } : second.error ? { error: errText(second.error) } : { resolved: true },
    end,
  }
}

async function isolation() {
  const pool = new pg.Pool({ ...base, max: 1, application_name: 'probe-drizzle' })
  pool.on('error', () => {})
  const db = drizzle(pool)
  const configs = [
    undefined,
    { isolationLevel: 'read committed' },
    { isolationLevel: 'repeatable read' },
    { isolationLevel: 'serializable' },
    { isolationLevel: 'serializable', accessMode: 'read only' },
    { isolationLevel: 'serializable', accessMode: 'read only', deferrable: true },
    { isolationLevel: 'serializable', accessMode: 'read write', deferrable: false },
  ]
  const rows = []
  for (const config of configs) {
    const seen = await db.transaction(async (tx) => {
      const res = await tx.execute(sql`select current_setting('transaction_isolation') as isolation, current_setting('transaction_read_only') as read_only, current_setting('transaction_deferrable') as deferrable`)
      return res.rows[0]
    }, config)
    rows.push({ config: config ?? null, server: seen })
  }
  await pool.end()
  return { rows }
}

// pg-pool removes its error listener while a client is checked out (pg-pool _acquireClient).
// This probe adds one, which Drizzle does not, so the process can survive pg_terminate_backend
// and the return value of db.transaction can be observed. It is not the adapter.
async function terminateWithListener() {
  await resetTable()
  const pool = new pg.Pool({ ...base, max: 1, application_name: 'probe-drizzle' })
  pool.on('error', () => {})
  const db = drizzle(pool)
  const killer = new pg.Client({ ...base, application_name: 'probe-killer' })
  await killer.connect()
  const outcome = await withTimeout(db.transaction(async (tx) => {
    await tx.execute(sql`insert into probe_item (name) values ('abandoned')`)
    const { rows } = await tx.execute(sql`select pg_backend_pid() as pid`)
    await killer.query('select pg_terminate_backend($1)', [rows[0].pid])
    await sleep(200)
  }), 8000)
  const end = await observe('after-terminate')
  await killer.end()
  await withTimeout(pool.end(), 1000)
  await terminateProbeBackends()
  return {
    listener: 'added by this probe on Client.connect, not by Drizzle',
    outcome: outcome.timedOut ? { timedOut: true } : outcome.error ? { error: errText(outcome.error) } : { resolved: true },
    end,
  }
}

const only = process.argv[2] ?? 'all'
if (only === 'all' || only === 'pool') {
  const timeoutRuns = []
  for (let i = 0; i < 3; i++) {
    console.log('query_timeout pool run', i + 1)
    timeoutRuns.push(await queryTimeout('pool'))
    console.log('query_timeout pool run', i + 1, 'done', JSON.stringify({ first: timeoutRuns[i].first, second: timeoutRuns[i].second, later: timeoutRuns[i].later, afterLater: timeoutRuns[i].afterLater }))
  }
  record('query_timeout pool x3', { runs: timeoutRuns })
}
if (only === 'all' || only === 'client') {
  const clientRuns = []
  for (let i = 0; i < 3; i++) {
    console.log('query_timeout client run', i + 1)
    clientRuns.push(await queryTimeout('client'))
    console.log('query_timeout client run', i + 1, 'done', JSON.stringify({ later: clientRuns[i].later, afterLater: clientRuns[i].afterLater, trace: clientRuns[i].trace }))
  }
  record('query_timeout direct client x3', { runs: clientRuns })
}
if (only === 'pool-later') {
  const runs = []
  for (let i = 0; i < 3; i++) {
    console.log('pool after idle', i + 1)
    runs.push(await queryTimeoutPoolAfterIdle())
    console.log('pool after idle', i + 1, 'done', JSON.stringify({ later: runs[i].later, afterLater: runs[i].afterLater, trace: runs[i].trace }))
  }
  record('query_timeout pool after idle x3', { runs })
}
if (only === 'all' || only === 'rest') {
  record('statement_timeout pool', await statementTimeout())
  record('isolation and access options', await isolation())
  record('terminate with an added client error listener', await terminateWithListener())
}

const drop = new pg.Client({ ...admin, connectionTimeoutMillis: 5000 })
await drop.connect()
await terminateProbeBackends()
await drop.query(`drop database ${dbname} with (force)`)
await drop.end()
console.log('dropped', dbname)
