// Knex 3.3.0, the version @adonisjs/lucid 22.4.2 depends on, against the same three
// MySQL cases as a direct mysql2 control. This is not a PPCS adapter.
//
// Knex's mysql2 transaction (lib/execution/transaction.js) sends BEGIN, calls
// commit when the callback resolves, and sends ROLLBACK when the callback rejects.
// The mysql2 dialect swallows ER_SP_DOES_NOT_EXIST on those transaction statements
// (lib/dialects/mysql2/transaction.js). These runs do not hit that path.
//
// mysql2-correct reports a commit only when the COMMIT it sent is acknowledged, and
// it sends ROLLBACK after an application error. mysql2-unsafe reports a commit when
// COMMIT does not throw, including after a deadlock, and it does not send ROLLBACK
// before the next transaction.

import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import knex from 'knex'
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
const KNEX_VERSION = require('knex/package.json').version
const evidenceDir = new URL('../evidence/', import.meta.url)

const instance = loadInstance()
const secrets = [instance.password, instance.root_password]
const endpoint = instance.default
const root = await openClient(instance, endpoint, 'root', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
await requireToken(root.conn, instance.token)

const ctx = {
  instance,
  endpoint,
  root,
  observer,
  open(role) { return openClient(instance, endpoint, role, 'app') },
}

try {
  const [version] = await root.conn.query('SELECT VERSION() AS version')
  const cases = []
  cases.push(await caughtDuplicate())
  cases.push(await deadlock())
  cases.push(await rollbackNotSent())
  writeJson('knex.json', {
    finished_at: new Date().toISOString(),
    not_a_ppcs_adapter: true,
    server_version: version[0].version,
    mysql2: MYSQL2_VERSION,
    knex: KNEX_VERSION,
    knex_contract: 'Knex 3.3.0 mysql2 sends BEGIN, commits when the callback resolves, and sends ROLLBACK when the callback rejects.',
    cases,
  })
} finally {
  await closeClient(root)
  await closeClient(observer)
}

async function caughtDuplicate() {
  return {
    id: 'caught-duplicate-then-return',
    drivers: {
      'mysql2-correct': await mysql2Duplicate('correct'),
      'mysql2-unsafe': await mysql2Duplicate('unsafe'),
      'knex-native': await knexDuplicate(),
    },
  }
}

async function mysql2Duplicate(mode) {
  const schema = await setup(ctx.root.conn, `kdup_${mode}`)
  const subject = await ctx.open(`dup-${mode}`)
  await useSchema(subject, schema)
  try {
    const steps = []
    steps.push(await capture(subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(subject, schema, 'insert-marker', 'INSERT INTO marker (name) VALUES (?)', [`${mode}-marker`]))
    steps.push(await capture(subject, schema, 'duplicate-key', `INSERT INTO uniq_row (code) VALUES ('taken')`))
    steps.push(await capture(subject, schema, 'commit', 'COMMIT'))
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const claim = claimFromCommit(mode, steps.at(-1))
    return {
      mode,
      claimed: claim.outcome,
      basis: claim.basis,
      commit_server_status: claim.serverStatus,
      steps,
      fresh_reader: fresh,
    }
  } finally {
    await closeClient(subject)
  }
}

async function knexDuplicate() {
  const schema = await setup(ctx.root.conn, 'kdup_knex')
  const { db, queries } = makeKnex(schema)
  try {
    let api
    try {
      await db.transaction(async (trx) => {
        await trx('marker').insert({ name: 'knex-marker' })
        try {
          await trx('uniq_row').insert({ code: 'taken' })
        } catch {
          // The callback returns. Knex commits.
        }
      })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return {
      mode: 'knex-native',
      claimed: api.outcome === 'resolved' ? 'committed' : 'failed',
      basis: api.outcome === 'resolved'
        ? 'knex.transaction resolved, which is Knex committing the callback'
        : 'knex.transaction rejected',
      api,
      queries,
      fresh_reader: fresh,
    }
  } finally {
    await db.destroy()
  }
}

async function deadlock() {
  return {
    id: 'deadlock',
    drivers: {
      'mysql2-correct': await mysql2Deadlock('correct'),
      'mysql2-unsafe': await mysql2Deadlock('unsafe'),
      'knex-native': await knexDeadlock(),
    },
  }
}

async function mysql2Deadlock(mode) {
  const schema = await setup(ctx.root.conn, `kdl_${mode}`)
  const fixture = await ctx.open(`dl-fixture-${mode}`)
  const subject = await ctx.open(`dl-subject-${mode}`)
  await useSchema(fixture, schema)
  await useSchema(subject, schema)
  try {
    const steps = []
    steps.push(await capture(fixture, schema, 'fixture-start', 'START TRANSACTION'))
    for (let n = 0; n < 8; n += 1) steps.push(await capture(fixture, schema, `fixture-ballast-${n}`, 'INSERT INTO ballast (n) VALUES (?)', [n]))
    steps.push(await capture(fixture, schema, 'fixture-lock-1', 'UPDATE dl SET v = v + 1 WHERE id = 1'))
    steps.push(await capture(subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(subject, schema, 'insert-marker', 'INSERT INTO marker (name) VALUES (?)', [`${mode}-victim`]))
    steps.push(await capture(subject, schema, 'lock-2', 'UPDATE dl SET v = v + 1 WHERE id = 2'))
    const fixtureWait = request(fixture.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
    const waited = await waitFor(async () => {
      const rows = await lockWaitsFor(observer, fixture.id)
      return rows.length ? rows : null
    }, 5000)
    steps.push(await capture(subject, schema, 'update-1', 'UPDATE dl SET v = v + 1 WHERE id = 1'))
    const fixtureCross = await fixtureWait
    const deadlockError = steps.at(-1).driver.error
    let followup = null
    if (mode === 'unsafe') followup = await capture(subject, schema, 'commit-after-deadlock', 'COMMIT')
    steps.push(await capture(fixture, schema, 'fixture-commit', 'COMMIT'))
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const [dl] = await observer.conn.query(`SELECT id, v FROM \`${schema}\`.dl ORDER BY id`)
    const sawDeadlock = deadlockError?.errno === 1213
    if (!sawDeadlock) throw new Error(`${mode} subject was not the deadlock victim`)
    return {
      mode,
      saw_deadlock: sawDeadlock,
      fixture_entered_lock_wait: waited,
      fixture_cross: fixtureCross,
      claimed: mode === 'correct'
        ? 'failed'
        : (followup?.driver.outcome === 'resolved' ? 'committed' : 'failed'),
      basis: mode === 'correct'
        ? 'the deadlock error was returned and COMMIT was not sent'
        : 'the deadlock was caught and COMMIT did not throw',
      followup,
      steps,
      fresh_reader: fresh,
      dl: plain(dl),
    }
  } finally {
    await closeClient(subject)
    await closeClient(fixture)
  }
}

async function knexDeadlock() {
  const schema = await setup(ctx.root.conn, 'kdl_knex')
  const fixture = await ctx.open('dl-fixture-knex')
  await useSchema(fixture, schema)
  const { db, queries } = makeKnex(schema)
  try {
    await fixture.conn.query('START TRANSACTION')
    for (let n = 0; n < 8; n += 1) await fixture.conn.query('INSERT INTO ballast (n) VALUES (?)', [n])
    await fixture.conn.query('UPDATE dl SET v = v + 1 WHERE id = 1')
    let subjectId = null
    let fixtureWait = null
    let api
    try {
      await db.transaction(async (trx) => {
        await trx('marker').insert({ name: 'knex-victim' })
        const [rows] = await trx.raw('SELECT CONNECTION_ID() AS connection_id')
        subjectId = Number(rows[0].connection_id)
        await trx('dl').where({ id: 2 }).update({ v: db.raw('v + 1') })
        fixtureWait = request(fixture.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
        const waited = await waitFor(async () => {
          const locks = await lockWaitsFor(observer, fixture.id)
          return locks.length ? locks : null
        }, 5000)
        if (!waited.found) throw new Error('fixture did not enter a lock wait')
        await trx('dl').where({ id: 1 }).update({ v: db.raw('v + 1') })
      })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const fixtureCross = fixtureWait ? await fixtureWait : null
    try {
      await fixture.conn.query('COMMIT')
    } catch (error) {
      api.fixture_commit_error = describeError(error)
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const [dl] = await observer.conn.query(`SELECT id, v FROM \`${schema}\`.dl ORDER BY id`)
    const after = subjectId == null ? null : await independentState(observer, subjectId)
    const victimError = queries.find((entry) => entry.event === 'query-error' && entry.error?.errno === 1213)
    if (!victimError) throw new Error('knex subject was not the deadlock victim')
    return {
      mode: 'knex-native',
      claimed: api.outcome === 'resolved' ? 'committed' : 'failed',
      basis: api.outcome === 'resolved'
        ? 'knex.transaction resolved'
        : 'knex.transaction rejected after the callback threw',
      subject_connection_id: subjectId,
      fixture_cross: fixtureCross,
      api,
      after,
      queries,
      fresh_reader: fresh,
      dl: plain(dl),
    }
  } finally {
    await db.destroy()
    await closeClient(fixture)
  }
}

async function rollbackNotSent() {
  return {
    id: 'rollback-not-sent',
    drivers: {
      'mysql2-correct': await mysql2Skipped('correct'),
      'mysql2-unsafe': await mysql2Skipped('unsafe'),
      'knex-native': await knexSkipped(),
    },
  }
}

async function mysql2Skipped(mode) {
  const schema = await setup(ctx.root.conn, `ksk_${mode}`)
  const subject = await ctx.open(`skip-${mode}`)
  await useSchema(subject, schema)
  try {
    const steps = []
    steps.push(await capture(subject, schema, 'start-1', 'START TRANSACTION'))
    steps.push(await capture(subject, schema, 'insert-doomed', 'INSERT INTO marker (name) VALUES (?)', [`${mode}-doomed`]))
    if (mode === 'correct') steps.push(await capture(subject, schema, 'rollback-1', 'ROLLBACK'))
    steps.push(await capture(subject, schema, 'start-2', 'START TRANSACTION'))
    const afterSecondStart = await visibleMarkers(observer, schema)
    steps.push(await capture(subject, schema, 'insert-next', 'INSERT INTO marker (name) VALUES (?)', [`${mode}-next`]))
    steps.push(await capture(subject, schema, 'rollback-2', 'ROLLBACK'))
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const firstRollback = steps.find((step) => step.name === 'rollback-1')
    const secondRollback = steps.find((step) => step.name === 'rollback-2')
    return {
      mode,
      claimed: 'rolled_back',
      basis: mode === 'correct'
        ? 'the first unit\'s ROLLBACK was sent and acknowledged'
        : 'ROLLBACK was not sent for the first unit; the second unit\'s ROLLBACK was acknowledged',
      first_rollback: firstRollback ?? null,
      second_rollback: secondRollback,
      visible_after_second_start: afterSecondStart,
      steps,
      fresh_reader: fresh,
    }
  } finally {
    await closeClient(subject)
  }
}

async function knexSkipped() {
  const schema = await setup(ctx.root.conn, 'ksk_knex')
  const { db, queries } = makeKnex(schema)
  let connection
  try {
    connection = await db.client.acquireConnection()
    const setupSteps = []
    setupSteps.push(await queryConnection(connection, 'BEGIN'))
    setupSteps.push(await queryConnection(connection, 'INSERT INTO marker (name) VALUES (?)', ['knex-doomed']))
    const idStep = await queryConnection(connection, 'SELECT CONNECTION_ID() AS connection_id')
    setupSteps.push(idStep)
    const connectionId = Number(idStep.driver.result.rows[0].connection_id)
    let api
    try {
      await db.transaction(async (trx) => {
        await trx('marker').insert({ name: 'knex-next' })
        throw new Error('second unit fails')
      }, { connection })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const after = await independentState(observer, connectionId)
    const visible = await visibleMarkers(observer, schema)
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return {
      mode: 'knex-native',
      note: 'The first unit is BEGIN plus an insert on a Knex pool connection, with no ROLLBACK. The second unit is knex.transaction on that same connection. Knex sends BEGIN for it.',
      claimed: api.outcome === 'resolved' ? 'committed' : 'failed',
      basis: api.outcome === 'resolved'
        ? 'knex.transaction resolved'
        : 'knex.transaction rejected',
      setup_steps: setupSteps,
      api,
      after,
      visible_after_api: visible,
      queries,
      fresh_reader: fresh,
    }
  } finally {
    if (connection) {
      await queryConnection(connection, 'ROLLBACK').catch(() => {})
      await db.client.releaseConnection(connection)
    }
    await db.destroy()
  }
}

function claimFromCommit(mode, step) {
  if (step.driver.outcome !== 'resolved') {
    return { outcome: 'failed', basis: 'COMMIT rejected', serverStatus: null }
  }
  if (mode === 'unsafe') return { outcome: 'committed', basis: 'COMMIT did not throw', serverStatus: step.driver.result.header.serverStatus }
  return { outcome: 'committed', basis: 'COMMIT resolved with an OK packet', serverStatus: step.driver.result.header.serverStatus }
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

async function capture(client, schema, name, sql, params) {
  const sent = await request(client.conn, sql, params)
  return {
    name,
    ...sent,
    independent_observation: await independentState(observer, client.id),
    visible_markers: await visibleMarkers(observer, schema),
  }
}

function makeKnex(database) {
  const options = connectionOptions(instance, endpoint, 'app')
  const db = knex({
    client: 'mysql2',
    connection: { ...options, database },
    pool: { min: 0, max: 1 },
  })
  const queries = []
  db.on('query', (query) => {
    queries.push({ event: 'query', sql: query.sql, method: query.method ?? null })
  })
  db.on('query-error', (error, query) => {
    queries.push({ event: 'query-error', sql: query?.sql ?? null, error: describeError(error) })
  })
  db.on('query-response', (response, query) => {
    queries.push({ event: 'query-response', sql: query?.sql ?? null, response: describeKnexResponse(response) })
  })
  return { db, queries }
}

function describeKnexResponse(response) {
  if (Array.isArray(response)) {
    const header = response.find((item) => item && typeof item === 'object' && 'serverStatus' in item)
    return { kind: 'array', length: response.length, serverStatus: header?.serverStatus ?? null }
  }
  if (response && typeof response === 'object' && 'serverStatus' in response) {
    return { kind: 'header', serverStatus: response.serverStatus, affectedRows: response.affectedRows ?? null }
  }
  return { kind: response == null ? 'empty' : typeof response }
}

function queryConnection(connection, sql, params) {
  return new Promise((resolve, reject) => {
    const done = (error, rows, fields) => {
      if (error) resolve({ requested: { sql, params: params ?? null }, driver: { outcome: 'rejected', error: describeError(error) } })
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
