// Connection and observation helpers. Adapted from investigations/mysql-innodb-baseline/src/lib.mjs,
// with a port guard and the statement and transaction history reads this study adds.
//
// The observer is a separate connection in autocommit mode. What it reads is what the server did. It is not
// recorded as something the subject knew when its call returned.

import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import mysql from 'mysql2/promise'

const require = createRequire(import.meta.url)

export const MYSQL2_VERSION = require('mysql2/package.json').version

// Another project's MySQL listens on 3306 on this machine. Nothing here may connect anywhere else.
const ALLOWED_PORTS = new Set([13316, 13317])

const INSTANCE_URL = new URL('./.mysd-instance.json', import.meta.url)

export function loadInstance() {
  const file = JSON.parse(readFileSync(INSTANCE_URL, 'utf8'))
  if (!file?.token || !file?.off?.port || !file?.on?.port) {
    throw new Error('Refusing to run: .mysd-instance.json is missing. Start the servers with scripts/mysql-up.sh.')
  }
  for (const endpoint of [file.off, file.on]) assertEndpoint(endpoint)
  return file
}

export function assertEndpoint(endpoint) {
  if (endpoint?.host !== '127.0.0.1' || !ALLOWED_PORTS.has(Number(endpoint?.port))) {
    throw new Error(`Refusing to connect to ${endpoint?.host}:${endpoint?.port}: not one of this study's servers.`)
  }
}

export function connectionOptions(instance, endpoint, user) {
  assertEndpoint(endpoint)
  return {
    host: endpoint.host,
    port: Number(endpoint.port),
    user: user === 'root' ? instance.root_user : instance.user,
    password: user === 'root' ? instance.root_password : instance.password,
    database: instance.database,
    connectTimeout: 10000,
    supportBigNumbers: true,
    bigNumberStrings: true,
    dateStrings: true,
    charset: 'utf8mb4',
    multipleStatements: false,
  }
}

export function plain(value) {
  if (value == null) return value
  if (typeof value === 'bigint') return value.toString()
  if (value instanceof Date) return value.toISOString()
  if (Buffer.isBuffer(value)) return { type: 'Buffer', hex: value.toString('hex') }
  if (Array.isArray(value)) return value.map(plain)
  if (typeof value === 'object') {
    const out = {}
    for (const key of Object.keys(value)) out[key] = plain(value[key])
    return out
  }
  return value
}

export function describeError(error) {
  if (!error || typeof error !== 'object') return { message: String(error) }
  const out = { name: error.name ?? null }
  for (const key of ['message', 'code', 'errno', 'sqlState', 'sqlMessage', 'fatal']) {
    if (key in error) out[key] = error[key] ?? null
  }
  return plain(out)
}

/** Send one statement and return only what the driver said. */
export async function request(conn, sql, params = undefined) {
  const started = Date.now()
  try {
    const [rows] = params === undefined ? await conn.query(sql) : await conn.query(sql, params)
    return { sql, outcome: 'resolved', elapsed_ms: Date.now() - started, server_status: rows?.serverStatus ?? null }
  } catch (error) {
    return { sql, outcome: 'rejected', elapsed_ms: Date.now() - started, error: describeError(error) }
  }
}

export async function openClient(instance, endpoint, role, user) {
  const conn = await mysql.createConnection(connectionOptions(instance, endpoint, user))
  const connectionErrors = []
  conn.on('error', (error) => { connectionErrors.push(describeError(error)) })
  const [rows] = await conn.query('SELECT CONNECTION_ID() AS id')
  return { conn, role, connectionErrors, id: Number(rows[0].id) }
}

export async function closeClient(client) {
  if (!client?.conn) return
  await client.conn.end().catch((error) => { client.connectionErrors.push(describeError(error)) })
}

export function assertSchema(name) {
  if (!/^[a-z][a-z0-9_]*$/.test(name)) throw new Error(`schema name is not an identifier: ${name}`)
  return name
}

export async function requireToken(root, token) {
  const [rows] = await root.query('SELECT token FROM mysd_meta.instance WHERE id = 1')
  if (rows[0]?.token !== token) {
    throw new Error('Refusing to run: this server does not have the token written by scripts/mysql-up.sh.')
  }
}

export async function threadIdOf(observer, connectionId) {
  const [rows] = await observer.query('SELECT THREAD_ID FROM performance_schema.threads WHERE PROCESSLIST_ID = ?', [Number(connectionId)])
  return rows[0]?.THREAD_ID == null ? null : Number(rows[0].THREAD_ID)
}

/** The subject thread's transaction as the server reports it, read from the observer connection. */
export async function transactionSnapshot(observer, threadId, connectionId) {
  const [current] = await observer.query(
    `SELECT EVENT_ID, STATE, TRX_ID, AUTOCOMMIT, NUMBER_OF_SAVEPOINTS, NUMBER_OF_ROLLBACK_TO_SAVEPOINT,
            NUMBER_OF_RELEASE_SAVEPOINT
     FROM performance_schema.events_transactions_current WHERE THREAD_ID = ?`,
    [threadId],
  )
  const [trx] = await observer.query(
    `SELECT trx_id, trx_state, trx_rows_modified, trx_rows_locked, trx_lock_structs
     FROM information_schema.innodb_trx WHERE trx_mysql_thread_id = ?`,
    [Number(connectionId)],
  )
  const [locks] = await observer.query(
    `SELECT ENGINE_TRANSACTION_ID, LOCK_TYPE, LOCK_MODE, LOCK_STATUS, OBJECT_NAME, INDEX_NAME, LOCK_DATA
     FROM performance_schema.data_locks WHERE THREAD_ID = ? ORDER BY OBJECT_NAME, LOCK_TYPE, LOCK_DATA`,
    [threadId],
  )
  return { events_transactions_current: plain(current), innodb_trx: plain(trx), data_locks: plain(locks) }
}

export async function markerNames(client, schema) {
  const [rows] = await client.query(`SELECT name FROM \`${assertSchema(schema)}\`.marker ORDER BY id`)
  return rows.map((row) => row.name)
}

export async function sinkRows(client, schema) {
  const [rows] = await client.query(`SELECT seq, callback FROM \`${assertSchema(schema)}\`.callback_sink ORDER BY id`)
  return plain(rows)
}

/** The statements the subject thread sent, as performance_schema recorded them. */
export async function statementHistory(observer, threadId) {
  const [rows] = await observer.query(
    `SELECT EVENT_ID, EVENT_NAME, LEFT(SQL_TEXT, 200) AS SQL_TEXT, MYSQL_ERRNO, RETURNED_SQLSTATE, NESTING_EVENT_ID
     FROM performance_schema.events_statements_history_long WHERE THREAD_ID = ? ORDER BY EVENT_ID`,
    [threadId],
  )
  return plain(rows)
}

export async function transactionHistory(observer, threadId) {
  const [rows] = await observer.query(
    `SELECT EVENT_ID, STATE, AUTOCOMMIT, NUMBER_OF_SAVEPOINTS, NUMBER_OF_ROLLBACK_TO_SAVEPOINT, NUMBER_OF_RELEASE_SAVEPOINT
     FROM performance_schema.events_transactions_history_long WHERE THREAD_ID = ? ORDER BY EVENT_ID`,
    [threadId],
  )
  return plain(rows)
}

export async function lockWaitsFor(observer, connectionId) {
  const [rows] = await observer.query(
    `SELECT w.REQUESTING_ENGINE_TRANSACTION_ID AS requesting_trx, w.BLOCKING_ENGINE_TRANSACTION_ID AS blocking_trx,
            w.REQUESTING_THREAD_ID AS requesting_thread, w.BLOCKING_THREAD_ID AS blocking_thread
     FROM performance_schema.data_lock_waits w
     JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID
     WHERE t.PROCESSLIST_ID = ?`,
    [Number(connectionId)],
  )
  return plain(rows)
}

export async function latestDeadlock(observer) {
  const [rows] = await observer.query('SHOW ENGINE INNODB STATUS')
  const text = String(rows[0]?.Status ?? '')
  const start = text.indexOf('LATEST DETECTED DEADLOCK')
  if (start < 0) return { present: false }
  const end = text.indexOf('\n------------\n', start + 30)
  const section = text.slice(start, end > start ? end : start + 6000)
  const victim = section.match(/WE ROLL BACK TRANSACTION \((\d+)\)/)
  const threads = [...section.matchAll(/MySQL thread id (\d+)/g)].map((match) => Number(match[1]))
  return { present: true, we_roll_back_transaction: victim ? Number(victim[1]) : null, mysql_thread_ids: threads, section }
}

export async function waitFor(predicate, timeoutMs, intervalMs = 25) {
  const started = Date.now()
  let last = null
  while (Date.now() - started < timeoutMs) {
    last = await predicate()
    if (last) return { found: true, elapsed_ms: Date.now() - started, value: last }
    await sleep(intervalMs)
  }
  return { found: false, elapsed_ms: Date.now() - started, value: last }
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function assertNoSecrets(text, secrets) {
  for (const secret of secrets) {
    if (secret && text.includes(secret)) throw new Error('Refusing to write evidence that contains a password or the token.')
  }
}
