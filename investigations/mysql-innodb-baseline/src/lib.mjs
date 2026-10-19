// Observation helpers for the MySQL 8.4 / InnoDB baseline.
//
// Four things stay in separate fields on every step:
//   requested                  the SQL the experiment sent
//   driver                     what mysql2 resolved or rejected, and nothing else
//   subject_session            a later statement on the same connection, when one is needed
//   independent_observation    a different connection, after the driver call returned
//
// A row visible to the independent connection is not recorded as something the client knew
// when mysql2 returned. The client knew only the driver field.

import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import mysql from 'mysql2/promise'

const require = createRequire(import.meta.url)
const mysql2Pkg = require('mysql2/package.json')

export const MYSQL2_VERSION = mysql2Pkg.version

const INSTANCE_URL = new URL('../.mpcs-instance.json', import.meta.url)

export function loadInstance() {
  const file = JSON.parse(readFileSync(INSTANCE_URL, 'utf8'))
  if (!file?.token || !file?.default?.port || !file?.rollback_on_timeout?.port) {
    throw new Error('Refusing to run: .mpcs-instance.json is missing. Start the servers with scripts/mysql-up.sh.')
  }
  return file
}

export function connectionOptions(instance, endpoint, user = 'app') {
  return {
    host: endpoint.host,
    port: endpoint.port,
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

export function publicOptions(options) {
  const { password, ...rest } = options
  return rest
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
  for (const key of ['message', 'code', 'errno', 'sqlState', 'sqlMessage', 'sql', 'fatal']) {
    if (key in error) out[key] = error[key] ?? null
  }
  return plain(out)
}

export function describeResult(tuple) {
  const rows = tuple?.[0]
  const fields = tuple?.[1]
  if (Array.isArray(rows)) {
    return {
      kind: 'rows',
      constructor: rows[0]?.constructor?.name ?? 'Array',
      row_count: rows.length,
      rows: plain(rows),
      fields: (fields ?? []).map((field) => ({
        name: field.name ?? null,
        columnType: field.columnType ?? field.type ?? null,
        flags: field.flags ?? null,
      })),
    }
  }
  return {
    kind: 'ok',
    constructor: rows?.constructor?.name ?? null,
    enumerable_keys: rows && typeof rows === 'object' ? Object.keys(rows) : [],
    own_property_names: rows && typeof rows === 'object' ? Object.getOwnPropertyNames(rows) : [],
    header: plain(rows),
    fields: fields ?? null,
  }
}

/**
 * Send one statement. The return value contains only the request and the driver outcome.
 * It does not read the server again.
 */
export async function request(conn, sql, params = undefined) {
  const started = Date.now()
  try {
    const result = params === undefined ? await conn.query(sql) : await conn.query(sql, params)
    return {
      requested: { sql, params: params === undefined ? null : params },
      driver: { outcome: 'resolved', elapsed_ms: Date.now() - started, result: describeResult(result) },
    }
  } catch (error) {
    return {
      requested: { sql, params: params === undefined ? null : params },
      driver: { outcome: 'rejected', elapsed_ms: Date.now() - started, error: describeError(error) },
    }
  }
}

export async function openClient(instance, endpoint, role, user = 'app') {
  const options = connectionOptions(instance, endpoint, user)
  const conn = await mysql.createConnection(options)
  const connectionErrors = []
  conn.on('error', (error) => { connectionErrors.push(describeError(error)) })
  const [rows] = await conn.query(
    'SELECT CONNECTION_ID() AS connection_id, @@autocommit AS autocommit, @@transaction_isolation AS transaction_isolation, @@session.innodb_lock_wait_timeout AS innodb_lock_wait_timeout',
  )
  return {
    conn,
    role,
    user: options.user,
    connectionErrors,
    id: Number(rows[0].connection_id),
    session_at_connect: plain(rows[0]),
  }
}

export async function closeClient(client) {
  if (!client?.conn) return
  await client.conn.end().catch((error) => { client.connectionErrors.push(describeError(error)) })
}

export function assertSchema(name) {
  if (!/^[a-z][a-z0-9_]*$/.test(name)) throw new Error(`schema name is not an identifier: ${name}`)
  return name
}

export async function recreateSchema(root, name) {
  const schema = assertSchema(name)
  await root.query(`DROP DATABASE IF EXISTS \`${schema}\``)
  await root.query(`CREATE DATABASE \`${schema}\``)
  await root.query(`GRANT ALL PRIVILEGES ON \`${schema}\`.* TO 'mpcs'@'%'`)
  return schema
}

export async function useSchema(client, schema) {
  await client.conn.query(`USE \`${assertSchema(schema)}\``)
}

export async function createMarkerTable(client) {
  await client.conn.query(`CREATE TABLE marker (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
}

export async function tableEngines(observer, schema) {
  const [rows] = await observer.conn.query(
    `SELECT TABLE_NAME AS table_name, ENGINE AS engine, TABLE_COLLATION AS collation
     FROM information_schema.tables WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME`,
    [schema],
  )
  return plain(rows)
}

/**
 * What a different connection can see about `connectionId` after a driver call has returned.
 * The observer connection stays in autocommit. It never starts a transaction.
 */
export async function independentState(observer, connectionId) {
  const id = Number(connectionId)
  const [autocommitRows] = await observer.conn.query('SELECT @@autocommit AS autocommit, @@transaction_isolation AS transaction_isolation')
  const [trx] = await observer.conn.query('SELECT * FROM information_schema.innodb_trx WHERE trx_mysql_thread_id = ?', [id])
  const [threads] = await observer.conn.query(
    `SELECT THREAD_ID, PROCESSLIST_ID, PROCESSLIST_USER, PROCESSLIST_COMMAND, PROCESSLIST_STATE, PROCESSLIST_INFO
     FROM performance_schema.threads WHERE PROCESSLIST_ID = ?`,
    [id],
  )
  const threadId = threads[0]?.THREAD_ID ?? null
  let transactionCurrent = []
  let transactionHistory = []
  let dataLocks = []
  let historyError = null
  if (threadId != null) {
    try {
      const [current] = await observer.conn.query('SELECT * FROM performance_schema.events_transactions_current WHERE THREAD_ID = ?', [threadId])
      const [history] = await observer.conn.query(
        'SELECT * FROM performance_schema.events_transactions_history WHERE THREAD_ID = ? ORDER BY EVENT_ID DESC LIMIT 6',
        [threadId],
      )
      const [locks] = await observer.conn.query(
        `SELECT ENGINE_TRANSACTION_ID, LOCK_TYPE, LOCK_MODE, LOCK_STATUS, OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME, LOCK_DATA
         FROM performance_schema.data_locks WHERE THREAD_ID = ?`,
        [threadId],
      )
      transactionCurrent = current
      transactionHistory = history
      dataLocks = locks
    } catch (error) {
      historyError = describeError(error)
    }
  }
  return {
    taken_after_driver_returned: true,
    client_knowledge: false,
    observer_session: plain(autocommitRows[0]),
    innodb_trx: plain(trx),
    thread: plain(threads[0] ?? null),
    events_transactions_current: summarizeTransactions(transactionCurrent),
    events_transactions_history: summarizeTransactions(transactionHistory),
    data_locks: plain(dataLocks),
    ...(historyError ? { performance_schema_error: historyError } : {}),
  }
}

function summarizeTransactions(rows) {
  return plain(rows).map((row) => ({
    EVENT_ID: row.EVENT_ID ?? null,
    STATE: row.STATE ?? null,
    TRX_ID: row.TRX_ID ?? null,
    GTID: row.GTID ?? null,
    ACCESS_MODE: row.ACCESS_MODE ?? null,
    ISOLATION_LEVEL: row.ISOLATION_LEVEL ?? null,
    AUTOCOMMIT: row.AUTOCOMMIT ?? null,
    NUMBER_OF_SAVEPOINTS: row.NUMBER_OF_SAVEPOINTS ?? null,
    NUMBER_OF_ROLLBACK_TO_SAVEPOINT: row.NUMBER_OF_ROLLBACK_TO_SAVEPOINT ?? null,
    NUMBER_OF_RELEASE_SAVEPOINT: row.NUMBER_OF_RELEASE_SAVEPOINT ?? null,
  }))
}

export async function visibleMarkers(reader, schema) {
  const [rows] = await reader.conn.query(`SELECT id, name FROM \`${assertSchema(schema)}\`.marker ORDER BY id, name`)
  return plain(rows)
}

/** A connection opened after the step, so its read cannot have been part of the call that just returned. */
export async function freshMarkerRead(instance, endpoint, schema) {
  const reader = await openClient(instance, endpoint, 'fresh-reader', 'app')
  try {
    const rows = await visibleMarkers(reader, schema)
    return {
      opened_after_driver_returned: true,
      client_knowledge: false,
      reader: { connection_id: reader.id, session_at_connect: reader.session_at_connect },
      rows,
    }
  } finally {
    await closeClient(reader)
  }
}

export async function waitFor(predicate, timeoutMs, intervalMs = 50) {
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

export async function lockWaitsFor(observer, connectionId) {
  const [rows] = await observer.conn.query(
    `SELECT w.REQUESTING_ENGINE_TRANSACTION_ID AS requesting_trx,
            w.BLOCKING_ENGINE_TRANSACTION_ID AS blocking_trx,
            w.REQUESTING_THREAD_ID AS requesting_thread,
            w.BLOCKING_THREAD_ID AS blocking_thread
     FROM performance_schema.data_lock_waits w
     JOIN performance_schema.threads t ON t.THREAD_ID = w.REQUESTING_THREAD_ID
     WHERE t.PROCESSLIST_ID = ?`,
    [Number(connectionId)],
  )
  return plain(rows)
}

export async function latestDeadlock(observer) {
  const [rows] = await observer.conn.query('SHOW ENGINE INNODB STATUS')
  const text = String(rows[0]?.Status ?? '')
  const start = text.indexOf('LATEST DETECTED DEADLOCK')
  if (start < 0) return { present: false }
  const end = text.indexOf('\n--------\n', start)
  const section = text.slice(start, end > start ? end : start + 5000)
  const victim = section.match(/WE ROLL BACK TRANSACTION \((\d+)\)/)
  return { present: true, we_roll_back_transaction: victim ? Number(victim[1]) : null, section }
}

export function assertNoSecrets(text, secrets) {
  for (const secret of secrets) {
    if (secret && text.includes(secret)) throw new Error('Refusing to write evidence that contains a password.')
  }
}

export async function requireToken(root, token) {
  const [rows] = await root.query('SELECT token FROM mpcs_meta.instance WHERE id = 1')
  if (rows[0]?.token !== token) {
    throw new Error('Refusing to run: this server does not have the token written by scripts/mysql-up.sh.')
  }
}

export async function collectServerConfig(root, { probeDynamic = false } = {}) {
  const [version] = await root.query('SELECT VERSION() AS version, @@version_comment AS version_comment, @@version_compile_os AS compile_os, @@version_compile_machine AS compile_machine')
  const [globals] = await root.query('SHOW GLOBAL VARIABLES')
  const [consumersBefore] = await root.query(
    `SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_consumers
     WHERE NAME LIKE '%transaction%' OR NAME LIKE '%statement%' ORDER BY NAME`,
  )
  await root.query(
    `UPDATE performance_schema.setup_consumers SET ENABLED = 'YES'
     WHERE NAME IN ('events_transactions_current', 'events_transactions_history', 'events_transactions_history_long')`,
  )
  const [consumersAfter] = await root.query(
    `SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_consumers
     WHERE NAME LIKE '%transaction%' OR NAME LIKE '%statement%' ORDER BY NAME`,
  )
  const [instruments] = await root.query(
    `SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_instruments
     WHERE NAME = 'transaction' OR NAME LIKE 'wait/lock/innodb%' ORDER BY NAME`,
  )
  let rollbackDynamic = { probed: false }
  const [beforeToggle] = await root.query('SELECT @@global.innodb_rollback_on_timeout AS value')
  if (probeDynamic) {
    const original = Number(beforeToggle[0].value) === 1 ? 'ON' : 'OFF'
    const next = original === 'ON' ? 'OFF' : 'ON'
    try {
      await root.query(`SET GLOBAL innodb_rollback_on_timeout = ${next}`)
      const [changed] = await root.query('SELECT @@global.innodb_rollback_on_timeout AS value')
      await root.query(`SET GLOBAL innodb_rollback_on_timeout = ${original}`)
      const [restored] = await root.query('SELECT @@global.innodb_rollback_on_timeout AS value')
      rollbackDynamic = {
        probed: true,
        set_global_succeeded: true,
        value_before: beforeToggle[0].value,
        value_after_set: changed[0].value,
        value_after_restore: restored[0].value,
      }
    } catch (error) {
      await root.query(`SET GLOBAL innodb_rollback_on_timeout = ${original}`).catch(() => {})
      const [restored] = await root.query('SELECT @@global.innodb_rollback_on_timeout AS value')
      rollbackDynamic = {
        probed: true,
        set_global_succeeded: false,
        value_before: beforeToggle[0].value,
        value_after_failed_probe: restored[0].value,
        error: describeError(error),
      }
    }
  }
  const [users] = await root.query(`SELECT user, host, plugin FROM mysql.user WHERE user IN ('root', 'mpcs') ORDER BY user, host`)
  return {
    version: plain(version[0]),
    variables: Object.fromEntries(globals.map((row) => [row.Variable_name, row.Value])),
    transaction_consumers_before: plain(consumersBefore),
    transaction_consumers_after_enable: plain(consumersAfter),
    transaction_instruments: plain(instruments),
    innodb_rollback_on_timeout_dynamic_probe: rollbackDynamic,
    accounts: plain(users),
  }
}
