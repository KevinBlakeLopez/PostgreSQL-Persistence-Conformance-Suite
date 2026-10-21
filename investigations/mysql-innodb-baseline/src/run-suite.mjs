// Executes the MySQL case list and scores mysql2, Knex, and Lucid.
// This file does not import the PostgreSQL harness.

import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import mysql from 'mysql2/promise'
import knex from 'knex'
import { Database } from '@adonisjs/lucid/database'
import { startCommitReplyProxy } from './commit-reply-proxy.mjs'
import {
  assertNoSecrets,
  closeClient,
  connectionOptions,
  describeError,
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
  waitFor,
} from './lib.mjs'

const require = createRequire(import.meta.url)
const KNEX_VERSION = require('knex/package.json').version
const LUCID_VERSION = JSON.parse(readFileSync(new URL('../node_modules/@adonisjs/lucid/package.json', import.meta.url), 'utf8')).version
const catalog = JSON.parse(readFileSync(new URL('../catalog/transactions.v1.json', import.meta.url), 'utf8'))

const instance = loadInstance()
const secrets = [instance.password, instance.root_password]
const endpoint = instance.default
const rollbackEndpoint = instance.rollback_on_timeout
const root = await openClient(instance, endpoint, 'root', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
const rootOn = await openClient(instance, rollbackEndpoint, 'root-on', 'root')
await requireToken(root.conn, instance.token)
await requireToken(rootOn.conn, instance.token)

const scores = []
let activeProxy = null
try {
  const [version] = await root.conn.query('SELECT VERSION() AS version')
  const [rollbackFlag] = await rootOn.conn.query('SELECT @@global.innodb_rollback_on_timeout AS value')
  if (Number(rollbackFlag[0].value) !== 1) throw new Error('rollback-on-timeout server is not ON')
  await scoreDuplicate()
  await scoreDeadlock()
  await scoreLockWait(endpoint, root.conn, false)
  await scoreLockWait(rollbackEndpoint, rootOn.conn, true)
  await scoreSavepoints()
  await scoreCommitPacket()
  await scoreClosedBeforeCommit()
  await scoreLostCommit()
  await scoreImplicitCommit()
  await scoreDdl()
  await scoreIsolation()
  const covered = new Set(scores.map((row) => row.id))
  const missing = catalog.cases.map((item) => item.id).filter((id) => !covered.has(id))
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    catalog: catalog.catalog,
    server_version: version[0].version,
    knex: KNEX_VERSION,
    lucid: LUCID_VERSION,
    missing_cases: missing,
    scores,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/suite.json', import.meta.url), text)
  for (const row of scores) console.error(`${row.score.toUpperCase()}  ${row.id}  ${row.client}  ${row.reason}`)
  if (missing.length || scores.some((row) => row.score === 'error')) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
  await closeClient(rootOn)
}

function record(id, client, score, reason, observed = {}) {
  scores.push({ id, client, score, reason, observed })
}

async function guard(id, client, fn) {
  try {
    await fn()
  } catch (error) {
    record(id, client, 'error', String(error?.message ?? error))
  }
}

async function scoreDuplicate() {
  const id = 'MX-01.duplicate-key-then-commit'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_dup_m', { uniq: true })
    const subject = await openClient(instance, endpoint, 's-dup', 'app')
    await useSchema(subject, schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('dup-marker')`)
      const dup = await request(subject.conn, `INSERT INTO uniq_row (code) VALUES ('taken')`)
      const commit = await request(subject.conn, 'COMMIT')
      const fresh = await freshMarkerRead(instance, endpoint, schema)
      const visible = fresh.rows.some((row) => row.name === 'dup-marker')
      const ok = dup.driver.error?.errno === 1062 && dup.driver.error?.sqlState === '23000'
        && commit.driver.outcome === 'resolved' && commit.driver.result.header.serverStatus === 16386
        && !commit.driver.result.enumerable_keys.includes('command') && visible
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'COMMIT kept the marker after 1062' : 'duplicate-key commit did not match the expectation', {
        errno: dup.driver.error?.errno, sqlState: dup.driver.error?.sqlState, serverStatus: commit.driver.result?.header?.serverStatus, visible,
      })
    } finally { await closeClient(subject) }
  })
  await guard(id, 'knex', () => callbackDuplicate(id, 'knex', 's_dup_k'))
  await guard(id, 'lucid', () => callbackDuplicate(id, 'lucid', 's_dup_l'))
}

async function callbackDuplicate(id, client, schemaName) {
  const schema = await setup(root.conn, schemaName, { uniq: true })
  const db = client === 'knex' ? openKnex(schema) : openLucid(schema)
  const queries = []
  listen(db, queries)
  try {
    let api = 'resolved'
    try {
      await db.transaction(async (trx) => {
        if (client === 'knex') {
          await trx('marker').insert({ name: 'dup-marker' })
          try { await trx('uniq_row').insert({ code: 'taken' }) } catch { /* return */ }
        } else {
          await trx.table('marker').insert({ name: 'dup-marker' })
          try { await trx.table('uniq_row').insert({ code: 'taken' }) } catch { /* return */ }
        }
      })
    } catch (error) {
      api = describeError(error)
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const visible = fresh.rows.some((row) => row.name === 'dup-marker')
    const sawDup = queries.some((entry) => entry.error?.errno === 1062)
    const sawCommit = queries.some((entry) => entry.sql === 'COMMIT;' || entry.sql === 'COMMIT')
    const ok = api === 'resolved' && visible && sawDup && sawCommit
    record(id, client, ok ? 'pass' : 'fail', ok ? 'callback returned and the marker committed' : 'managed transaction did not commit the marker after the caught duplicate key', { api, visible, sawDup, sawCommit })
  } finally { await closeDb(db) }
}

async function scoreDeadlock() {
  const id = 'MX-02.deadlock-victim'
  await guard(id, 'mysql2', () => mysqlDeadlock(id, 'mysql2', false))
  await guard(id, 'mysql2-unsafe', () => mysqlDeadlock(id, 'mysql2-unsafe', true))
  await guard(id, 'knex', () => frameworkDeadlock(id, 'knex'))
  await guard(id, 'lucid', () => frameworkDeadlock(id, 'lucid'))
}

async function mysqlDeadlock(id, client, unsafe) {
  const schema = await setup(root.conn, unsafe ? 's_dl_u' : 's_dl_m', { dl: true })
  const fixture = await openClient(instance, endpoint, 's-dl-f', 'app')
  const subject = await openClient(instance, endpoint, 's-dl-s', 'app')
  await useSchema(fixture, schema)
  await useSchema(subject, schema)
  try {
    await fixture.conn.query('START TRANSACTION')
    for (let n = 0; n < 8; n += 1) await fixture.conn.query('INSERT INTO ballast (n) VALUES (?)', [n])
    await fixture.conn.query('UPDATE dl SET v = v + 1 WHERE id = 1')
    await subject.conn.query('START TRANSACTION')
    await subject.conn.query(`INSERT INTO marker (name) VALUES ('victim')`)
    await subject.conn.query('UPDATE dl SET v = v + 1 WHERE id = 2')
    const waiting = request(fixture.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
    const waited = await waitFor(async () => {
      const rows = await lockWaitsFor(observer, fixture.id)
      return rows.length ? rows : null
    }, 5000)
    const update = await request(subject.conn, 'UPDATE dl SET v = v + 1 WHERE id = 1')
    await waiting
    let follow = null
    if (unsafe) follow = await request(subject.conn, 'COMMIT')
    await fixture.conn.query('COMMIT')
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const visible = fresh.rows.some((row) => row.name === 'victim')
    const victim = update.driver.error?.errno === 1213 && update.driver.error?.sqlState === '40001'
    if (!waited.found || !victim) throw new Error('subject was not the deadlock victim')
    const reportedCommit = follow?.driver.outcome === 'resolved'
    const ok = !unsafe && !visible && !reportedCommit
    const bad = unsafe && !visible && reportedCommit
    record(id, client, (unsafe ? bad : ok) ? (unsafe ? 'fail' : 'pass') : 'fail',
      unsafe
        ? 'COMMIT after 1213 was acknowledged and the victim marker is absent'
        : '1213 rolled back the victim and COMMIT was not sent',
      { errno: update.driver.error?.errno, sqlState: update.driver.error?.sqlState, visible, commitStatus: follow?.driver.result?.header?.serverStatus ?? null })
  } finally {
    await closeClient(subject)
    await closeClient(fixture)
  }
}

async function frameworkDeadlock(id, client) {
  const schema = await setup(root.conn, client === 'knex' ? 's_dl_k' : 's_dl_l', { dl: true })
  const fixture = await openClient(instance, endpoint, 's-dl-ff', 'app')
  await useSchema(fixture, schema)
  const db = client === 'knex' ? openKnex(schema) : openLucid(schema)
  const queries = []
  listen(db, queries)
  try {
    await fixture.conn.query('START TRANSACTION')
    for (let n = 0; n < 8; n += 1) await fixture.conn.query('INSERT INTO ballast (n) VALUES (?)', [n])
    await fixture.conn.query('UPDATE dl SET v = v + 1 WHERE id = 1')
    let fixtureWait = null
    let api = null
    try {
      await db.transaction(async (trx) => {
        if (client === 'knex') await trx('marker').insert({ name: 'victim' })
        else await trx.table('marker').insert({ name: 'victim' })
        if (client === 'knex') await trx('dl').where({ id: 2 }).update({ v: db.raw('v + 1') })
        else await trx.rawQuery('UPDATE dl SET v = v + 1 WHERE id = ?', [2])
        fixtureWait = request(fixture.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
        const waited = await waitFor(async () => {
          const rows = await lockWaitsFor(observer, fixture.id)
          return rows.length ? rows : null
        }, 5000)
        if (!waited.found) throw new Error('fixture did not enter a lock wait')
        if (client === 'knex') await trx('dl').where({ id: 1 }).update({ v: db.raw('v + 1') })
        else await trx.rawQuery('UPDATE dl SET v = v + 1 WHERE id = ?', [1])
      })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    if (fixtureWait) await fixtureWait
    await fixture.conn.query('COMMIT')
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const visible = fresh.rows.some((row) => row.name === 'victim')
    const errno = api.error?.errno
    const ok = api.outcome === 'rejected' && errno === 1213 && !visible
    record(id, client, ok ? 'pass' : 'fail', ok ? 'callback rejection carried 1213 and the victim marker is absent' : 'deadlock report did not match the expectation', { api, visible })
  } finally {
    await closeDb(db)
    await closeClient(fixture)
  }
}

async function scoreLockWait(which, rootConn, rollbackOn) {
  const id = rollbackOn ? 'MX-03.lock-wait-transaction-rollback' : 'MX-03.lock-wait-statement-rollback'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(rootConn, rollbackOn ? 's_lk_on' : 's_lk_off', { lk: true })
    const holder = await openClient(instance, which, 's-hold', 'app')
    const waiter = await openClient(instance, which, 's-wait', 'app')
    await useSchema(holder, schema)
    await useSchema(waiter, schema)
    try {
      await waiter.conn.query('SET SESSION innodb_lock_wait_timeout = 2')
      await holder.conn.query('START TRANSACTION')
      await holder.conn.query('UPDATE lk SET v = 1 WHERE id = 1')
      await waiter.conn.query('START TRANSACTION')
      await waiter.conn.query(`INSERT INTO marker (name) VALUES ('before')`)
      const timed = await request(waiter.conn, 'UPDATE lk SET v = 2 WHERE id = 1')
      const after = await request(waiter.conn, `INSERT INTO marker (name) VALUES ('after')`)
      const commit = await request(waiter.conn, 'COMMIT')
      await holder.conn.query('ROLLBACK')
      const fresh = await freshMarkerRead(instance, which, schema)
      const names = fresh.rows.map((row) => row.name)
      const errorOk = timed.driver.error?.errno === 1205 && timed.driver.error?.sqlState === 'HY000'
      const statementScope = errorOk && after.driver.result?.header?.serverStatus === 3 && names.includes('before') && names.includes('after')
      const transactionScope = errorOk && !names.includes('before')
      const ok = rollbackOn ? transactionScope : statementScope
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok
        ? (rollbackOn ? '1205 rolled back the whole transaction' : '1205 left the transaction open and the earlier marker committed')
        : 'lock-wait outcome did not match the server setting',
      { errno: timed.driver.error?.errno, sqlState: timed.driver.error?.sqlState, afterStatus: after.driver.result?.header?.serverStatus ?? null, names, commit: commit.driver.outcome })
    } finally {
      await closeClient(holder)
      await closeClient(waiter)
    }
  })
  record(id, 'knex', 'not_run', 'the expectation is the server rollback scope, measured with mysql2')
  record(id, 'lucid', 'not_run', 'the expectation is the server rollback scope, measured with mysql2')
}

async function scoreSavepoints() {
  await guard('MX-04.savepoint-rollback', 'mysql2', async () => {
    const schema = await setup(root.conn, 's_sp_rb')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('outer')`)
      await subject.conn.query('SAVEPOINT sp1')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('inside')`)
      await subject.conn.query('ROLLBACK TO SAVEPOINT sp1')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('after')`)
      await subject.conn.query('COMMIT')
      const names = await namesOf(schema)
      const ok = names.includes('outer') && names.includes('after') && !names.includes('inside')
      record('MX-04.savepoint-rollback', 'mysql2', ok ? 'pass' : 'fail', ok ? 'commit kept the outer write and the write after rollback-to' : `markers ${names.join(',')}`, { names })
    } finally { await closeClient(subject) }
  })
  await guard('MX-04.savepoint-release', 'mysql2', async () => {
    const schema = await setup(root.conn, 's_sp_rel')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('outer')`)
      await subject.conn.query('SAVEPOINT sp1')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('inside')`)
      await subject.conn.query('RELEASE SAVEPOINT sp1')
      const before = await freshMarkerRead(instance, endpoint, schema)
      await subject.conn.query('COMMIT')
      const names = await namesOf(schema)
      const ok = before.rows.length === 0 && names.includes('outer') && names.includes('inside')
      record('MX-04.savepoint-release', 'mysql2', ok ? 'pass' : 'fail', ok ? 'release did not commit; the outer commit kept both markers' : `markers ${names.join(',')}`, { names })
    } finally { await closeClient(subject) }
  })
  await guard('MX-04.released-then-outer-rollback', 'mysql2', async () => {
    const schema = await setup(root.conn, 's_sp_out')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('outer')`)
      await subject.conn.query('SAVEPOINT sp1')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('inside')`)
      await subject.conn.query('RELEASE SAVEPOINT sp1')
      const rolled = await request(subject.conn, 'ROLLBACK')
      const names = await namesOf(schema)
      const ok = rolled.driver.outcome === 'resolved' && names.length === 0
      record('MX-04.released-then-outer-rollback', 'mysql2', ok ? 'pass' : 'fail', ok ? 'outer rollback removed the released savepoint write' : `markers ${names.join(',')}`, { names })
    } finally { await closeClient(subject) }
  })
  await guard('MX-04.missing-savepoint', 'mysql2', async () => {
    const schema = await setup(root.conn, 's_sp_miss')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('outer')`)
      await subject.conn.query('SAVEPOINT sp_real')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('after-real')`)
      const missing = await request(subject.conn, 'ROLLBACK TO SAVEPOINT does_not_exist')
      const next = await request(subject.conn, `INSERT INTO marker (name) VALUES ('after-error')`)
      await subject.conn.query('ROLLBACK TO SAVEPOINT sp_real')
      await subject.conn.query('COMMIT')
      const names = await namesOf(schema)
      const ok = missing.driver.error?.errno === 1305 && missing.driver.error?.sqlState === '42000'
        && next.driver.outcome === 'resolved' && next.driver.result.header.serverStatus === 3
        && names.includes('outer') && !names.includes('after-real') && !names.includes('after-error')
      record('MX-04.missing-savepoint', 'mysql2', ok ? 'pass' : 'fail', ok ? '1305 left the transaction usable and the real savepoint still rolled back' : `markers ${names.join(',')}`, { errno: missing.driver.error?.errno, sqlState: missing.driver.error?.sqlState, names })
    } finally { await closeClient(subject) }
  })
  for (const id of ['MX-04.savepoint-rollback', 'MX-04.savepoint-release', 'MX-04.released-then-outer-rollback', 'MX-04.missing-savepoint']) {
    record(id, 'knex', 'not_run', 'measured with mysql2; Knex was not part of this expectation')
    record(id, 'lucid', 'not_run', 'measured with mysql2; Lucid was not part of this expectation')
  }
}

async function scoreCommitPacket() {
  const id = 'MX-05.commit-and-rollback-packet'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_pkt')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('kept')`)
      const commit = await request(subject.conn, 'COMMIT')
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('gone')`)
      const rollback = await request(subject.conn, 'ROLLBACK')
      const names = await namesOf(schema)
      const commitHeader = commit.driver.result?.header
      const rollbackHeader = rollback.driver.result?.header
      const ok = commit.driver.outcome === 'resolved' && rollback.driver.outcome === 'resolved'
        && commitHeader?.serverStatus === 16386 && rollbackHeader?.serverStatus === 16386
        && !commit.driver.result.enumerable_keys.includes('command')
        && !rollback.driver.result.enumerable_keys.includes('command')
        && names.includes('kept') && !names.includes('gone')
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'COMMIT and ROLLBACK were both OK packets at 16386 with no command tag' : 'packet shape or marker visibility did not match', {
        commitStatus: commitHeader?.serverStatus, rollbackStatus: rollbackHeader?.serverStatus, names,
      })
    } finally { await closeClient(subject) }
  })
  record(id, 'knex', 'not_run', 'the packet shape is a mysql2 result')
  record(id, 'lucid', 'not_run', 'the packet shape is a mysql2 result')
}

async function scoreClosedBeforeCommit() {
  const id = 'MX-05.connection-closed-before-commit'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_kill')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('killed')`)
      await observer.conn.query(`KILL ${subject.id}`)
      const commit = await request(subject.conn, 'COMMIT')
      const names = await namesOf(schema)
      const ok = commit.driver.outcome === 'rejected' && !names.includes('killed') && commit.driver.error?.sqlState == null
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'COMMIT was not acknowledged and the marker is absent' : 'closed-connection commit did not match', {
        message: commit.driver.error?.message, fatal: commit.driver.error?.fatal, names,
      })
    } finally { await closeClient(subject) }
  })
  record(id, 'knex', 'not_run', 'measured with mysql2')
  record(id, 'lucid', 'not_run', 'measured with mysql2')
}

async function scoreLostCommit() {
  const id = 'MX-05.lost-commit-reply'
  const proxy = await startCommitReplyProxy({ host: endpoint.host, port: endpoint.port })
  activeProxy = proxy
  try {
    const schema = await setup(root.conn, 's_lost')
    await guard(id, 'mysql2', async () => {
      const options = connectionOptions(instance, endpoint, 'app')
      const conn = await mysql.createConnection({ ...options, port: proxy.port, database: schema })
      try {
        await conn.query('START TRANSACTION')
        await conn.query(`INSERT INTO marker (name) VALUES ('mysql2-lost')`)
        proxy.arm()
        let api
        try {
          await withTimeout(conn.query('COMMIT'), 5000)
          api = { outcome: 'resolved' }
        } catch (error) {
          api = { outcome: 'rejected', error: describeError(error) }
        }
        const visible = (await namesOf(schema)).includes('mysql2-lost')
        const dropped = proxy.drops.at(-1)
        const ok = api.outcome === 'rejected' && api.error?.code === 'PROTOCOL_CONNECTION_LOST' && visible && dropped?.looks_like_ok
        record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'COMMIT was not acknowledged; the marker is visible afterward' : 'lost reply did not match', { api, visible, dropped })
      } finally { await conn.end().catch(() => {}) }
    })
    await guard(id, 'knex', async () => {
      const row = await frameworkLost(schema, 'knex', 'knex-lost', 'callback')
      const ok = row.api.outcome === 'rejected' && row.api.error?.code === 'PROTOCOL_CONNECTION_LOST' && row.visible && row.dropped?.looks_like_ok
      record(id, 'knex', ok ? 'pass' : 'fail', ok ? 'knex.transaction rejected the lost COMMIT reply' : 'knex.transaction did not reject the lost reply', row)
    })
    await guard(id, 'knex-commit', async () => {
      const row = await explicitCommitLost(schema)
      const reportedSuccess = row.api.outcome === 'resolved'
      const serverCommitted = row.visible && row.dropped?.looks_like_ok
      record(id, 'knex-commit', reportedSuccess && serverCommitted ? 'fail' : 'pass', reportedSuccess
        ? 'trx.commit() resolved without the OK packet'
        : 'trx.commit() did not resolve', row)
    })
    await guard(id, 'lucid', async () => {
      const row = await frameworkLost(schema, 'lucid', 'lucid-lost', 'callback')
      const reportedSuccess = row.api.outcome === 'resolved'
      const serverCommitted = row.visible && row.dropped?.looks_like_ok
      record(id, 'lucid', reportedSuccess && serverCommitted ? 'fail' : 'pass', reportedSuccess
        ? 'db.transaction resolved without the OK packet'
        : 'db.transaction did not resolve', row)
    })
  } finally {
    activeProxy = null
    await proxy.close()
  }
}

async function frameworkLost(schema, client, marker, kind) {
  const db = client === 'knex' ? openKnex(schema, proxyPort()) : openLucid(schema, proxyPort())
  const queries = []
  listen(db, queries)
  try {
    proxyArm()
    let api
    try {
      await withTimeout(db.transaction(async (trx) => {
        if (client === 'knex') await trx('marker').insert({ name: marker })
        else await trx.table('marker').insert({ name: marker })
      }), 5000)
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    return { kind, api, visible: (await namesOf(schema)).includes(marker), dropped: lastDrop(), queries }
  } finally { await closeDb(db) }
}

function proxyArm() { activeProxy.arm() }
function proxyPort() { return activeProxy.port }
function lastDrop() { return activeProxy.drops.at(-1) ?? null }

async function explicitCommitLost(schema) {
  const db = openKnex(schema, proxyPort())
  const queries = []
  listen(db, queries)
  try {
    const trx = await db.transaction()
    await trx('marker').insert({ name: 'knex-explicit-lost' })
    proxyArm()
    let api
    try {
      await withTimeout(trx.commit(), 5000)
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    return { api, visible: (await namesOf(schema)).includes('knex-explicit-lost'), dropped: lastDrop(), queries }
  } finally { await closeDb(db) }
}

async function scoreImplicitCommit() {
  const id = 'MX-06.second-transaction-implicit-commit'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_imp_m')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('doomed')`)
      await subject.conn.query('ROLLBACK')
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('next')`)
      await subject.conn.query('ROLLBACK')
      const names = await namesOf(schema)
      const ok = names.length === 0
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'ROLLBACK before the next transaction left neither marker' : `markers ${names.join(',')}`, { names })
    } finally { await closeClient(subject) }
  })
  await guard(id, 'mysql2-unsafe', async () => {
    const schema = await setup(root.conn, 's_imp_u')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('doomed')`)
      await subject.conn.query('START TRANSACTION')
      const midway = await namesOf(schema)
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('next')`)
      const rolled = await request(subject.conn, 'ROLLBACK')
      const names = await namesOf(schema)
      const wrong = midway.includes('doomed') && names.includes('doomed') && !names.includes('next') && rolled.driver.outcome === 'resolved'
      record(id, 'mysql2-unsafe', wrong ? 'fail' : 'pass', wrong ? 'the second ROLLBACK was acknowledged and the first marker remains' : 'unsafe implicit commit did not occur', { midway, names })
    } finally { await closeClient(subject) }
  })
  await guard(id, 'knex', () => dirtySecond(id, 'knex', 's_imp_k'))
  await guard(id, 'lucid', () => dirtySecond(id, 'lucid', 's_imp_l'))
}

async function dirtySecond(id, client, schemaName) {
  const schema = await setup(root.conn, schemaName)
  const db = client === 'knex' ? openKnex(schema) : openLucid(schema)
  let connection
  try {
    const write = client === 'knex' ? db : db.connection().getWriteClient()
    connection = await write.client.acquireConnection()
    await queryConnection(connection, 'BEGIN')
    await queryConnection(connection, `INSERT INTO marker (name) VALUES ('doomed')`)
    let api
    try {
      await db.transaction(async (trx) => {
        if (client === 'knex') await trx('marker').insert({ name: 'next' })
        else await trx.table('marker').insert({ name: 'next' })
        throw new Error('second unit fails')
      }, { connection })
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const names = await namesOf(schema)
    const firstRemains = names.includes('doomed') && !names.includes('next')
    const onlySecondFailure = api.outcome === 'rejected' && api.error?.errno == null
    const ok = firstRemains && onlySecondFailure
    record(id, client, ok ? 'fail' : 'pass', ok
      ? 'the second unit failed and the first marker stayed committed'
      : 'implicit commit on the second transaction did not match', { api, names })
  } finally {
    if (connection) {
      await queryConnection(connection, 'ROLLBACK').catch(() => {})
      const write = client === 'knex' ? db : db.connection().getWriteClient()
      await write.client.releaseConnection(connection)
    }
    await closeDb(db)
  }
}

async function scoreDdl() {
  const id = 'MX-07.ddl-implicit-commit'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_ddl')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('ddl-marker')`)
      const created = await request(subject.conn, 'CREATE TABLE ddl_side (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB')
      const afterCreate = await namesOf(schema)
      const rolled = await request(subject.conn, 'ROLLBACK')
      const afterRollback = await namesOf(schema)
      const [tables] = await observer.conn.query(`SELECT TABLE_NAME AS table_name FROM information_schema.tables WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'ddl_side'`, [schema])
      const ok = created.driver.result?.header?.serverStatus === 16386 && afterCreate.includes('ddl-marker')
        && rolled.driver.result?.header?.serverStatus === 2 && afterRollback.includes('ddl-marker') && tables.length === 1
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'CREATE TABLE committed the insert and ROLLBACK removed neither' : 'DDL implicit commit did not match', { afterCreate, afterRollback, tables: tables.length })
    } finally { await closeClient(subject) }
  })
  record(id, 'knex', 'not_run', 'measured with mysql2')
  record(id, 'lucid', 'not_run', 'measured with mysql2')
}

async function scoreIsolation() {
  const id = 'MX-08.isolation-report'
  await guard(id, 'mysql2', async () => {
    const schema = await setup(root.conn, 's_iso')
    const subject = await openOn(schema)
    try {
      await subject.conn.query('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
      await subject.conn.query('START TRANSACTION')
      await subject.conn.query(`INSERT INTO marker (name) VALUES ('iso')`)
      const variable = await request(subject.conn, 'SELECT @@transaction_isolation AS transaction_isolation')
      const state = await independentState(observer, subject.id)
      await subject.conn.query('ROLLBACK')
      const session = await openOn(schema)
      let sessionLevel = null
      let sessionPs = null
      try {
        await session.conn.query(`SET SESSION transaction_isolation = 'SERIALIZABLE'`)
        await session.conn.query('START TRANSACTION')
        const reported = await request(session.conn, 'SELECT @@transaction_isolation AS transaction_isolation')
        sessionLevel = reported.driver.result.rows[0].transaction_isolation
        sessionPs = (await independentState(observer, session.id)).events_transactions_current[0]?.ISOLATION_LEVEL
        await session.conn.query('ROLLBACK')
      } finally { await closeClient(session) }
      const inside = await openOn(schema)
      let insideError = null
      try {
        await inside.conn.query('START TRANSACTION')
        const set = await request(inside.conn, 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        insideError = set.driver.error
        await inside.conn.query('ROLLBACK')
      } finally { await closeClient(inside) }
      const ps = state.events_transactions_current[0]?.ISOLATION_LEVEL
      const sessionVariable = variable.driver.result.rows[0].transaction_isolation
      const ok = ps === 'SERIALIZABLE' && sessionVariable === 'REPEATABLE-READ'
        && sessionLevel === 'SERIALIZABLE' && sessionPs === 'SERIALIZABLE'
        && insideError?.errno === 1568 && insideError?.sqlState === '25001'
      record(id, 'mysql2', ok ? 'pass' : 'fail', ok ? 'performance schema reported the SET TRANSACTION level and @@transaction_isolation did not' : 'isolation observations did not agree with the expectation', {
        ps, sessionVariable, sessionLevel, sessionPs, insideErrno: insideError?.errno,
      })
    } finally { await closeClient(subject) }
  })
  record(id, 'knex', 'not_run', 'measured with mysql2')
  record(id, 'lucid', 'not_run', 'measured with mysql2')
}

async function setup(rootConn, name, { uniq = false, dl = false, lk = false } = {}) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.marker (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
  if (uniq) {
    await rootConn.query(`CREATE TABLE \`${schema}\`.uniq_row (
      id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      code VARCHAR(64) NOT NULL,
      UNIQUE KEY uniq_code (code)
    ) ENGINE=InnoDB`)
    await rootConn.query(`INSERT INTO \`${schema}\`.uniq_row (code) VALUES ('taken')`)
  }
  if (dl) {
    await rootConn.query(`CREATE TABLE \`${schema}\`.dl (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
    await rootConn.query(`INSERT INTO \`${schema}\`.dl (id, v) VALUES (1, 0), (2, 0)`)
    await rootConn.query(`CREATE TABLE \`${schema}\`.ballast (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB`)
  }
  if (lk) {
    await rootConn.query(`CREATE TABLE \`${schema}\`.lk (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
    await rootConn.query(`INSERT INTO \`${schema}\`.lk (id, v) VALUES (1, 0)`)
  }
  return schema
}

async function openOn(schema) {
  const subject = await openClient(instance, endpoint, 's-subject', 'app')
  await useSchema(subject, schema)
  return subject
}

async function namesOf(schema) {
  const fresh = await freshMarkerRead(instance, endpoint, schema)
  return fresh.rows.map((row) => row.name)
}

function openKnex(database, port = endpoint.port) {
  const options = connectionOptions(instance, endpoint, 'app')
  const db = knex({ client: 'mysql2', connection: { ...options, port, database }, pool: { min: 0, max: 1 } })
  db.kind = 'knex'
  return db
}

function openLucid(database, port = endpoint.port) {
  const options = connectionOptions(instance, endpoint, 'app')
  const logger = { trace() {}, debug() {}, info() {}, warn() {}, error() {}, fatal() {}, isLevelEnabled: () => true }
  logger.child = () => logger
  const db = new Database({
    connection: 'mysql',
    connections: { mysql: { client: 'mysql2', connection: { ...options, port, database }, pool: { min: 0, max: 1 } } },
  }, logger, { emit() {}, hasListeners() { return false } })
  db.kind = 'lucid'
  return db
}

function listen(db, queries) {
  const client = db.kind === 'knex' ? db : db.connection().getWriteClient()
  client.on('query', (query) => queries.push({ sql: query.sql }))
  client.on('query-error', (error, query) => queries.push({ sql: query?.sql, error: describeError(error) }))
}

async function closeDb(db) {
  if (db.kind === 'knex') await db.destroy()
  else await db.manager.closeAll()
}

function queryConnection(connection, sql, params) {
  return new Promise((resolve) => {
    const done = (error) => resolve(error)
    if (params === undefined) connection.query(sql, done)
    else connection.query(sql, params, done)
  })
}

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timed out after ${ms} ms`)), ms)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}
