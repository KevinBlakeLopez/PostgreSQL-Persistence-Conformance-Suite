// Lucid 22.4.2 managed db.transaction(callback) on MySQL, beside the Knex 3.3.0
// run in evidence/knex.json. Same three cases. This is not a PPCS adapter.
//
// Lucid's query client (build/src/query_client/index.js) awaits
// knex.transaction(), runs the callback itself, commits when the callback
// returns, and rolls back then rethrows when the callback throws.

import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { Database } from '@adonisjs/lucid/database'
import {
  MYSQL2_VERSION,
  assertNoSecrets,
  closeClient,
  connectionOptions,
  describeError,
  describeResult,
  freshMarkerRead,
  independentState,
  loadInstance,
  lockWaitsFor,
  openClient,
  plain,
  recreateSchema,
  request,
  requireToken,
  useSchema,
  visibleMarkers,
  waitFor,
} from './lib.mjs'

const require = createRequire(import.meta.url)
const LUCID_VERSION = JSON.parse(readFileSync(new URL('../node_modules/@adonisjs/lucid/package.json', import.meta.url), 'utf8')).version
const KNEX_VERSION = require('knex/package.json').version
const evidenceDir = new URL('../evidence/', import.meta.url)

if (LUCID_VERSION !== '22.4.2' || KNEX_VERSION !== '3.3.0' || MYSQL2_VERSION !== '3.24.6') {
  throw new Error(`Refusing to run: lucid ${LUCID_VERSION}, knex ${KNEX_VERSION}, mysql2 ${MYSQL2_VERSION}`)
}

const instance = loadInstance()
const secrets = [instance.password, instance.root_password]
const endpoint = instance.default
const root = await openClient(instance, endpoint, 'root', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
await requireToken(root.conn, instance.token)

try {
  const [version] = await root.conn.query('SELECT VERSION() AS version')
  const cases = [
    await caughtDuplicate(),
    await deadlock(),
    await rollbackNotSent(),
  ]
  writeJson('lucid.json', {
    finished_at: new Date().toISOString(),
    not_a_ppcs_adapter: true,
    server_version: version[0].version,
    lucid: LUCID_VERSION,
    knex: KNEX_VERSION,
    mysql2: MYSQL2_VERSION,
    lucid_contract: 'Lucid 22.4.2 db.transaction(callback) commits when the callback returns and rolls back, then rethrows, when the callback throws.',
    cases,
    comparison_with_knex: compareWithKnex(cases),
  })
} finally {
  await closeClient(root)
  await closeClient(observer)
}

async function caughtDuplicate() {
  const schema = await setup(root.conn, 'ldup')
  const { db, queries } = openLucid(schema)
  try {
    let api
    try {
      await db.transaction(async (trx) => {
        await trx.table('marker').insert({ name: 'lucid-marker' })
        try {
          await trx.table('uniq_row').insert({ code: 'taken' })
        } catch {
          // The callback returns. Lucid commits.
        }
      })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeAny(error) }
    }
    return finish('caught-duplicate-then-return', api, queries, schema, api.outcome === 'resolved' ? 'committed' : 'failed', api.outcome === 'resolved'
      ? 'db.transaction resolved, which is Lucid committing the callback'
      : 'db.transaction rejected')
  } finally {
    await db.manager.closeAll()
  }
}

async function deadlock() {
  const schema = await setup(root.conn, 'ldl')
  const fixture = await openClient(instance, endpoint, 'ldl-fixture', 'app')
  await useSchema(fixture, schema)
  const { db, queries } = openLucid(schema)
  try {
    await fixture.conn.query('START TRANSACTION')
    for (let n = 0; n < 8; n += 1) await fixture.conn.query('INSERT INTO ballast (n) VALUES (?)', [n])
    await fixture.conn.query('UPDATE dl SET v = v + 1 WHERE id = 1')
    let subjectId = null
    let fixtureWait = null
    let api
    try {
      await db.transaction(async (trx) => {
        await trx.table('marker').insert({ name: 'lucid-victim' })
        const rows = await rowsOf(trx.rawQuery('SELECT CONNECTION_ID() AS connection_id'))
        subjectId = Number(rows[0].connection_id)
        await trx.rawQuery('UPDATE dl SET v = v + 1 WHERE id = ?', [2])
        fixtureWait = request(fixture.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
        const waited = await waitFor(async () => {
          const locks = await lockWaitsFor(observer, fixture.id)
          return locks.length ? locks : null
        }, 5000)
        if (!waited.found) throw new Error('fixture did not enter a lock wait')
        await trx.rawQuery('UPDATE dl SET v = v + 1 WHERE id = ?', [1])
      })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeAny(error) }
    }
    const fixtureCross = fixtureWait ? await fixtureWait : null
    try {
      await fixture.conn.query('COMMIT')
    } catch (error) {
      api.fixture_commit_error = describeAny(error)
    }
    const victim = queries.find((entry) => entry.event === 'query-error' && entry.error?.errno === 1213)
    if (!victim) throw new Error('lucid subject was not the deadlock victim')
    const [dl] = await observer.conn.query(`SELECT id, v FROM \`${schema}\`.dl ORDER BY id`)
    const result = await finish('deadlock', api, queries, schema, api.outcome === 'resolved' ? 'committed' : 'failed', api.outcome === 'resolved'
      ? 'db.transaction resolved'
      : 'db.transaction rejected after the callback threw')
    return { ...result, subject_connection_id: subjectId, fixture_cross: fixtureCross, dl: plain(dl), after: subjectId == null ? null : await independentState(observer, subjectId) }
  } finally {
    await db.manager.closeAll()
    await closeClient(fixture)
  }
}

async function rollbackNotSent() {
  const schema = await setup(root.conn, 'lsk')
  const { db, queries } = openLucid(schema)
  let connection
  try {
    const write = db.connection().getWriteClient()
    connection = await write.client.acquireConnection()
    const setupSteps = []
    setupSteps.push(await queryConnection(connection, 'BEGIN'))
    setupSteps.push(await queryConnection(connection, 'INSERT INTO marker (name) VALUES (?)', ['lucid-doomed']))
    const idStep = await queryConnection(connection, 'SELECT CONNECTION_ID() AS connection_id')
    setupSteps.push(idStep)
    const connectionId = Number(idStep.driver.result.rows[0].connection_id)
    let api
    try {
      await db.transaction(async (trx) => {
        await trx.table('marker').insert({ name: 'lucid-next' })
        throw new Error('second unit fails')
      }, { connection })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeAny(error) }
    }
    const after = await independentState(observer, connectionId)
    const visible = await visibleMarkers(observer, schema)
    const result = await finish('rollback-not-sent', api, queries, schema, api.outcome === 'resolved' ? 'committed' : 'failed', api.outcome === 'resolved'
      ? 'db.transaction resolved'
      : 'db.transaction rejected')
    return {
      ...result,
      note: 'The first unit is BEGIN plus an insert on a Lucid pool connection, with no ROLLBACK. The second unit is db.transaction on that same connection. Lucid asks Knex to begin it.',
      setup_steps: setupSteps,
      after,
      visible_after_api: visible,
    }
  } finally {
    if (connection) {
      await queryConnection(connection, 'ROLLBACK').catch(() => {})
      await db.connection().getWriteClient().client.releaseConnection(connection)
    }
    await db.manager.closeAll()
  }
}

async function finish(id, api, queries, schema, claimed, basis) {
  const fresh = await freshMarkerRead(instance, endpoint, schema)
  return { id, claimed, basis, api, queries, fresh_reader: fresh }
}

function compareWithKnex(cases) {
  const knexRun = JSON.parse(readFileSync(new URL('knex.json', evidenceDir), 'utf8'))
  return cases.map((lucidCase) => {
    const knexCase = knexRun.cases.find((entry) => entry.id === lucidCase.id)
    const knexNative = knexCase?.drivers?.['knex-native']
    return {
      id: lucidCase.id,
      lucid_claimed: lucidCase.claimed,
      knex_claimed: knexNative?.claimed ?? null,
      claims_match: lucidCase.claimed === knexNative?.claimed,
      lucid_marker_count: lucidCase.fresh_reader.rows.length,
      knex_marker_count: knexNative?.fresh_reader?.rows?.length ?? null,
      marker_counts_match: lucidCase.fresh_reader.rows.length === (knexNative?.fresh_reader?.rows?.length ?? -1),
    }
  })
}

async function setup(rootConn, name) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.marker (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
  await rootConn.query(`CREATE TABLE \`${schema}\`.uniq_row (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    UNIQUE KEY uniq_code (code)
  ) ENGINE=InnoDB`)
  await rootConn.query(`INSERT INTO \`${schema}\`.uniq_row (code) VALUES ('taken')`)
  await rootConn.query(`CREATE TABLE \`${schema}\`.dl (
    id INT NOT NULL PRIMARY KEY,
    v INT NOT NULL
  ) ENGINE=InnoDB`)
  await rootConn.query(`INSERT INTO \`${schema}\`.dl (id, v) VALUES (1, 0), (2, 0)`)
  await rootConn.query(`CREATE TABLE \`${schema}\`.ballast (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    n INT NOT NULL
  ) ENGINE=InnoDB`)
  return schema
}

function openLucid(database) {
  const options = connectionOptions(instance, endpoint, 'app')
  const lines = []
  const db = new Database({
    connection: 'mysql',
    connections: {
      mysql: {
        client: 'mysql2',
        connection: { ...options, database },
        pool: { min: 0, max: 1 },
      },
    },
  }, captureLogger(lines), { emit() {}, hasListeners() { return false } })
  const queries = []
  const write = db.connection().getWriteClient()
  write.on('query', (query) => {
    queries.push({ event: 'query', sql: query.sql, method: query.method ?? null })
  })
  write.on('query-error', (error, query) => {
    queries.push({ event: 'query-error', sql: query?.sql ?? null, error: describeAny(error) })
  })
  write.on('query-response', (response, query) => {
    queries.push({ event: 'query-response', sql: query?.sql ?? null, response: describeKnexResponse(response) })
  })
  return { db, queries, lines }
}

function captureLogger(lines) {
  const at = (level) => (...args) => {
    const [first, second] = args
    const msg = typeof first === 'string' ? first : (typeof second === 'string' ? second : '')
    lines.push({ level, msg: String(msg).slice(0, 300) })
  }
  const logger = { trace() {}, debug() {}, info: at('info'), warn: at('warn'), error: at('error'), fatal: at('fatal'), isLevelEnabled: () => true }
  logger.child = () => logger
  return logger
}

async function rowsOf(query) {
  const result = await query
  if (Array.isArray(result) && Array.isArray(result[0])) return result[0]
  if (Array.isArray(result)) return result
  return result?.rows ?? []
}

function describeAny(error) {
  const out = describeError(error)
  if (error?.original) out.original = describeError(error.original)
  return out
}

function describeKnexResponse(response) {
  if (Array.isArray(response)) return { kind: 'array', length: response.length }
  if (response && typeof response === 'object' && 'serverStatus' in response) {
    return { kind: 'header', serverStatus: response.serverStatus, affectedRows: response.affectedRows ?? null }
  }
  return { kind: response == null ? 'empty' : typeof response }
}

function queryConnection(connection, sql, params) {
  return new Promise((resolve) => {
    const done = (error, rows, fields) => {
      if (error) resolve({ requested: { sql, params: params ?? null }, driver: { outcome: 'rejected', error: describeAny(error) } })
      else resolve({ requested: { sql, params: params ?? null }, driver: { outcome: 'resolved', result: describeResult([rows, fields]) } })
    }
    if (params === undefined) connection.query(sql, done)
    else connection.query(sql, params, done)
  })
}

function writeJson(name, value) {
  const text = `${JSON.stringify(plain(value), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(evidenceDir, { recursive: true })
  writeFileSync(new URL(name, evidenceDir), text)
}
