// Deadlock and lock-wait for mysqli, PDO MySQL, and CodeIgniter 4.
// Node holds the other session. PHP is the subject, one command at a time.
// This file does not import the PostgreSQL harness and does not rewrite
// evidence/php-mx01.json or evidence/suite.json.
//
// matched_expectation is the pre-stated contract for that mode. It is not a defect verdict.

import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  assertNoSecrets,
  closeClient,
  freshMarkerRead,
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

const phpScript = fileURLToPath(new URL('../php/bin/session.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3

const INSERT_VICTIM = "INSERT INTO marker (name) VALUES ('victim')"
const INSERT_AFTER_DEADLOCK = "INSERT INTO marker (name) VALUES ('after-deadlock')"
const INSERT_BEFORE = "INSERT INTO marker (name) VALUES ('before')"
const INSERT_AFTER = "INSERT INTO marker (name) VALUES ('after')"
const LOCK_DL_1 = 'UPDATE dl SET v = v + 1 WHERE id = 1'
const LOCK_DL_2 = 'UPDATE dl SET v = v + 1 WHERE id = 2'
const LOCK_LK = 'UPDATE lk SET v = 2 WHERE id = 1'
const SET_TIMEOUT = 'SET SESSION innodb_lock_wait_timeout = 2'

const instance = loadInstance()
const secrets = [instance.password, instance.root_password, instance.token]
const endpoint = instance.default
const rollbackEndpoint = instance.rollback_on_timeout

const root = await openClient(instance, endpoint, 'root', 'root')
const rootOn = await openClient(instance, rollbackEndpoint, 'root-on', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
const observerOn = await openClient(instance, rollbackEndpoint, 'observer-on', 'root')
await requireToken(root.conn, instance.token)
await requireToken(rootOn.conn, instance.token)

const runs = []
try {
  const [serverRows] = await root.conn.query(`SELECT VERSION() AS version,
    @@global.innodb_rollback_on_timeout AS innodb_rollback_on_timeout,
    @@global.transaction_isolation AS transaction_isolation,
    @@global.autocommit AS autocommit`)
  const [serverOnRows] = await rootOn.conn.query('SELECT @@global.innodb_rollback_on_timeout AS innodb_rollback_on_timeout')
  if (Number(serverRows[0].innodb_rollback_on_timeout) !== 0) throw new Error('default server rollback-on-timeout is not off')
  if (Number(serverOnRows[0].innodb_rollback_on_timeout) !== 1) throw new Error('rollback-on-timeout server is not on')

  let versions = null
  for (const mode of ['mysqli', 'pdo', 'ci4-managed', 'ci4-manual-documented', 'ci4-manual-unchecked']) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const result = await runDeadlock(mode, repetition)
      if (!versions && result.versions) versions = result.versions
      runs.push(result)
      console.error(`${result.matched_expectation ? 'MATCH' : 'DIFFER'}  deadlock  ${mode}  r${repetition}  ${result.reason}`)
    }
  }
  for (const rollbackOn of [false, true]) {
    for (const mode of ['mysqli', 'pdo', 'ci4-managed', 'ci4-manual-documented']) {
      for (let repetition = 1; repetition <= repetitions; repetition += 1) {
        const result = await runLockWait(mode, repetition, rollbackOn)
        if (!versions && result.versions) versions = result.versions
        runs.push(result)
        console.error(`${result.matched_expectation ? 'MATCH' : 'DIFFER'}  lock-wait  ${rollbackOn ? 'on' : 'off'}  ${mode}  r${repetition}  ${result.reason}`)
      }
    }
  }

  const mismatched = runs.filter((row) => !row.matched_expectation).map((row) => `${row.case} ${row.mode}#${row.repetition}`)
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json'],
    score_meaning: 'matched_expectation compares the run with expectation_basis. It is not a framework-defect verdict.',
    server: plain(serverRows[0]),
    rollback_on_timeout_server: plain(serverOnRows[0]),
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-concurrency.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(rootOn)
  await closeClient(observer)
  await closeClient(observerOn)
}

async function runDeadlock(mode, repetition) {
  const schema = await setup(root.conn, schemaName('mx02', mode, repetition), 'dl')
  const fixture = await openClient(instance, endpoint, 'dl-fixture', 'app')
  await useSchema(fixture, schema)
  const session = startSession(schema, endpoint.port)
  const basis = deadlockBasis(mode)
  try {
    await fixture.conn.query('START TRANSACTION')
    for (let n = 0; n < 8; n += 1) await fixture.conn.query('INSERT INTO ballast (n) VALUES (?)', [n])
    await fixture.conn.query('UPDATE dl SET v = v + 1 WHERE id = 1')
    const opened = await session.request({ op: 'open', driver: driverOf(mode), debug: true })
    await session.request({ op: 'begin', api: beginApi(mode) })
    const victimInsert = await session.request({ op: 'query', sql: INSERT_VICTIM })
    const subjectLock = await session.request({ op: 'query', sql: LOCK_DL_2 })
    const fixtureWait = request(fixture.conn, LOCK_DL_2)
    const waited = await waitFor(async () => {
      const rows = await lockWaitsFor(observer, fixture.id)
      return rows.length ? rows : null
    }, 5000)
    const cross = await session.request({ op: 'query', sql: LOCK_DL_1 }, 15000)
    const fixtureCross = await fixtureWait
    const stateAfterError = await transactionState(observer, opened.connection_id)
    const followUp = await session.request({ op: 'query', sql: INSERT_AFTER_DEADLOCK })
    const visibleBeforeEnd = (await visibleMarkers(observer, schema)).map((row) => row.name)
    const completed = await session.request({ op: 'complete', api: completeApi(mode) })
    await fixture.conn.query('COMMIT')
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const names = fresh.rows.map((row) => row.name)
    const closed = await session.close()
    const observed = {
      opened, victimInsert, subjectLock, fixture_wait_found: waited.found, cross, fixture_cross: fixtureOutcome(fixtureCross),
      state_after_error: stateAfterError, follow_up: followUp, visible_before_end: visibleBeforeEnd,
      completed, names, closed,
    }
    const verdict = scoreDeadlock(mode, observed)
    return row('MX-02.deadlock-victim', mode, repetition, schema, false, basis, verdict, observed, opened.versions ?? null)
  } catch (error) {
    await session.close()
    try { await fixture.conn.query('ROLLBACK') } catch { /* the fixture may already have finished */ }
    return row('MX-02.deadlock-victim', mode, repetition, schema, false, basis, { matched: false, reason: String(error?.message ?? error) }, { failed: true }, null)
  } finally {
    await closeClient(fixture)
  }
}

async function runLockWait(mode, repetition, rollbackOn) {
  const which = rollbackOn ? rollbackEndpoint : endpoint
  const rootConn = rollbackOn ? rootOn.conn : root.conn
  const eyes = rollbackOn ? observerOn : observer
  const schema = await setup(rootConn, schemaName(rollbackOn ? 'mx03on' : 'mx03off', mode, repetition), 'lk')
  const holder = await openClient(instance, which, 'lk-holder', 'app')
  await useSchema(holder, schema)
  const session = startSession(schema, which.port)
  const basis = lockWaitBasis(mode, rollbackOn)
  try {
    await holder.conn.query('START TRANSACTION')
    await holder.conn.query('UPDATE lk SET v = 1 WHERE id = 1')
    const opened = await session.request({ op: 'open', driver: driverOf(mode), debug: true })
    const timeoutSet = await session.request({ op: 'query', sql: SET_TIMEOUT })
    await session.request({ op: 'begin', api: beginApi(mode) })
    const before = await session.request({ op: 'query', sql: INSERT_BEFORE })
    const pending = session.request({ op: 'query', sql: LOCK_LK }, 15000)
    const waited = await waitFor(async () => {
      const rows = await lockWaitsFor(eyes, opened.connection_id)
      return rows.length ? rows : null
    }, 5000)
    const timed = await pending
    const stateAfterError = await transactionState(eyes, opened.connection_id)
    const followUp = await session.request({ op: 'query', sql: INSERT_AFTER })
    const visibleBeforeEnd = (await visibleMarkers(eyes, schema)).map((row) => row.name)
    const completed = await session.request({ op: 'complete', api: completeApi(mode) })
    await holder.conn.query('ROLLBACK')
    const fresh = await freshMarkerRead(instance, which, schema)
    const names = fresh.rows.map((row) => row.name)
    const closed = await session.close()
    const observed = {
      opened, timeoutSet, before, fixture_wait_found: waited.found, timed, state_after_error: stateAfterError,
      follow_up: followUp, visible_before_end: visibleBeforeEnd, completed, names, closed,
    }
    const verdict = scoreLockWait(mode, rollbackOn, observed)
    return row(rollbackOn ? 'MX-03.lock-wait-transaction-rollback' : 'MX-03.lock-wait-statement-rollback', mode, repetition, schema, rollbackOn, basis, verdict, observed, opened.versions ?? null)
  } catch (error) {
    await session.close()
    try { await holder.conn.query('ROLLBACK') } catch { /* holder may already have finished */ }
    return row(rollbackOn ? 'MX-03.lock-wait-transaction-rollback' : 'MX-03.lock-wait-statement-rollback', mode, repetition, schema, rollbackOn, basis, { matched: false, reason: String(error?.message ?? error) }, { failed: true }, null)
  } finally {
    await closeClient(holder)
  }
}

function scoreDeadlock(mode, observed) {
  const cross = observed.cross ?? {}
  const code = Number(cross.error_code)
  const victim = sameNames(observed.names, ['after-deadlock'])
  const visible = observed.visible_before_end.includes('after-deadlock') && !observed.visible_before_end.includes('victim')
  const driverError = cross.threw === true && code === 1213 && cross.sqlstate === '40001'
  const ci4Error = cross.threw === false && cross.returned === false && code === 1213
  const depthHeld = observed.cross?.state?.trans_depth === 1 && observed.cross?.state?.trans_status === false
  const closedClean = observed.closed?.left_transaction_open === false
  const followAccepted = observed.follow_up?.returned === true && observed.follow_up?.threw !== true
  const common = observed.fixture_wait_found === true && victim && visible && followAccepted && closedClean
    && observed.fixture_cross?.errno == null
  if (mode === 'mysqli') {
    const committed = observed.completed?.choice === 'commit' && observed.completed?.returned === true && observed.completed?.threw !== true
    const ok = common && driverError && committed
    return { matched: ok, reason: ok
      ? '1213 rolled the victim back before the next insert; mysqli commit returned true and did not restore it'
      : 'mysqli deadlock did not match MX-02' }
  }
  if (mode === 'pdo') {
    const refused = observed.completed?.threw === true && observed.completed?.message === 'There is no active transaction'
    const ok = common && driverError && refused
    return { matched: ok, reason: ok
      ? '1213 ended the transaction; PDO commit threw because none remained, and the victim marker is absent'
      : 'PDO deadlock did not match the driver behavior' }
  }
  const ended = mode === 'ci4-managed'
    ? observed.completed?.choice === 'trans_complete' && observed.completed?.returned === false
    : mode === 'ci4-manual-documented'
      ? observed.completed?.choice === 'rollback' && observed.completed?.returned === true
      : observed.completed?.choice === 'trans_commit' && observed.completed?.returned === true && observed.completed?.status?.trans_status === false
  const ok = common && ci4Error && depthHeld && ended
  return { matched: ok, reason: ok
    ? 'CodeIgniter still had depth 1 after 1213; the victim row was already gone and the next insert autocommitted'
    : 'CodeIgniter deadlock did not match the source-reading prediction' }
}

function scoreLockWait(mode, rollbackOn, observed) {
  const timed = observed.timed ?? {}
  const code = Number(timed.error_code)
  const waitedLongEnough = Number(timed.elapsed_ms) >= 1500
  const state = observed.state_after_error?.transaction?.[0]?.STATE ?? null
  const driverError = timed.threw === true && code === 1205 && timed.sqlstate === 'HY000'
  const ci4Error = timed.threw === false && timed.returned === false && code === 1205
  const depthHeld = timed.state?.trans_depth === 1 && timed.state?.trans_status === false
  const closedClean = observed.closed?.left_transaction_open === false
  const followAccepted = observed.follow_up?.returned === true && observed.follow_up?.threw !== true
  const sawWait = observed.fixture_wait_found === true
  if (mode === 'mysqli' || mode === 'pdo') {
    const committed = observed.completed?.returned === true && observed.completed?.threw !== true
    const refused = observed.completed?.threw === true && observed.completed?.message === 'There is no active transaction'
    const end = mode === 'pdo' && rollbackOn ? refused : committed
    const statement = !rollbackOn && state === 'ACTIVE' && !observed.visible_before_end.includes('after') && sameNames(observed.names, ['before', 'after'])
    const whole = rollbackOn && state === 'ROLLED BACK' && observed.visible_before_end.includes('after') && sameNames(observed.names, ['after'])
    const ok = sawWait && waitedLongEnough && driverError && end && followAccepted && closedClean && (rollbackOn ? whole : statement)
    return { matched: ok, reason: ok
      ? (rollbackOn
        ? (mode === 'pdo'
          ? '1205 rolled the transaction back; the later insert autocommitted and PDO commit threw'
          : '1205 rolled the transaction back and the later insert autocommitted')
        : '1205 left the transaction open and commit kept both markers')
      : 'driver lock wait did not match the server setting' }
  }
  const ended = mode === 'ci4-managed'
    ? observed.completed?.choice === 'trans_complete' && observed.completed?.returned === false
    : observed.completed?.choice === 'rollback' && observed.completed?.returned === true
  const statement = !rollbackOn && state === 'ACTIVE' && !observed.visible_before_end.includes('after') && observed.names.length === 0
  const whole = rollbackOn && state === 'ROLLED BACK' && observed.visible_before_end.includes('after') && sameNames(observed.names, ['after'])
  const ok = sawWait && waitedLongEnough && ci4Error && depthHeld && ended && followAccepted && closedClean && (rollbackOn ? whole : statement)
  return { matched: ok, reason: ok
    ? (rollbackOn
      ? 'CodeIgniter rolled its group back after the server had already aborted the transaction; the later insert autocommitted'
      : 'CodeIgniter rolled the still-open transaction back on 1205, so neither marker remained')
    : 'CodeIgniter lock wait did not match the source-reading prediction' }
}

function deadlockBasis(mode) {
  if (mode === 'mysqli') {
    return 'MX-02. The subject is the lighter transaction and is the deadlock victim. Errno 1213 means that transaction is already rolled back. The next insert autocommits. mysqli commit returns true. That acknowledgement is not the victim commit, and the victim marker does not remain.'
  }
  if (mode === 'pdo') {
    return 'MX-02. The subject is the lighter transaction and is the deadlock victim. Errno 1213 means that transaction is already rolled back. The next insert autocommits and the victim marker does not remain. PDO::commit() throws "There is no active transaction" because the server transaction is already gone. A first execution of this harness saw that exception and dropped the surrounding steps; this expectation keeps the exception as the driver result.'
  }
  if (mode === 'ci4-managed') {
    return 'CodeIgniter managed default does not throw. The failed statement sets transStatus false and leaves transDepth at 1, because the framework does not see that InnoDB already rolled the victim back. transComplete then returns false. The victim marker is absent. The insert after the error autocommits.'
  }
  if (mode === 'ci4-manual-documented') {
    return 'The user-guide manual branch sees transStatus false and calls transRollback. InnoDB has already removed the victim marker. The insert after the error autocommits. transRollback returns true.'
  }
  return 'transCommit does not read transStatus. After 1213 it still returns true. That acknowledgement is not the victim transaction, whose marker is absent. transStatus stays false. The insert after the error autocommits.'
}

function lockWaitBasis(mode, rollbackOn) {
  const server = rollbackOn
    ? 'innodb_rollback_on_timeout is ON. Errno 1205 rolls the whole transaction back. The marker written before the wait does not remain. An insert after the error autocommits.'
    : 'innodb_rollback_on_timeout is OFF. Errno 1205 rolls back only the waiting statement. The transaction stays open. A later commit keeps the marker written before the wait and the marker written after it.'
  if (mode === 'mysqli') return `MX-03. ${server} mysqli commit returns true in both settings. When the server has already aborted the transaction, that return is not a commit of the earlier marker.`
  if (mode === 'pdo' && rollbackOn) {
    return `${server} PDO::commit() throws "There is no active transaction" after the server abort. The later insert has already autocommitted. The earlier marker does not remain.`
  }
  if (mode === 'pdo') return `MX-03. ${server} The transaction is still open, so PDO commit succeeds and both markers remain.`
  if (rollbackOn) {
    return `${server} CodeIgniter still reports transStatus false at depth 1. The documented end path rolls the group back. The earlier marker is already gone. The later insert autocommits.`
  }
  return `${server} CodeIgniter treats the failed statement as a failed group. transStatus is false at depth 1, and the documented end path rolls the still-open transaction back. Neither marker remains. The driver control on this server commits both.`
}

function row(caseId, mode, repetition, schema, rollbackOn, basis, verdict, observed, versions) {
  return {
    case: caseId,
    mode,
    repetition,
    schema,
    innodb_rollback_on_timeout: rollbackOn,
    expectation_basis: basis,
    matched_expectation: verdict.matched,
    reason: verdict.reason,
    versions,
    observed,
  }
}

function driverOf(mode) {
  if (mode === 'mysqli') return 'mysqli'
  if (mode === 'pdo') return 'pdo'
  return 'ci4'
}

function beginApi(mode) {
  if (mode === 'ci4-managed') return 'managed'
  if (mode === 'mysqli' || mode === 'pdo') return 'driver'
  return 'manual'
}

function completeApi(mode) {
  if (mode === 'ci4-managed') return 'managed'
  if (mode === 'ci4-manual-documented') return 'documented'
  if (mode === 'ci4-manual-unchecked') return 'manual'
  return 'driver'
}

function fixtureOutcome(step) {
  if (step?.driver?.outcome === 'resolved') return { errno: null, outcome: 'resolved' }
  return { errno: step?.driver?.error?.errno ?? null, sqlstate: step?.driver?.error?.sqlState ?? null, outcome: step?.driver?.outcome ?? null }
}

function sameNames(actual, expected) {
  const left = [...actual].sort()
  const right = [...expected].sort()
  return left.length === right.length && left.every((name, index) => name === right[index])
}

async function transactionState(observerClient, connectionId) {
  const [threads] = await observerClient.conn.query(
    'SELECT THREAD_ID, PROCESSLIST_ID, PROCESSLIST_COMMAND, PROCESSLIST_STATE FROM performance_schema.threads WHERE PROCESSLIST_ID = ?',
    [Number(connectionId)],
  )
  const threadId = threads[0]?.THREAD_ID ?? null
  let transaction = []
  if (threadId != null) {
    const [rows] = await observerClient.conn.query(
      'SELECT STATE, AUTOCOMMIT, ISOLATION_LEVEL FROM performance_schema.events_transactions_current WHERE THREAD_ID = ?',
      [threadId],
    )
    transaction = rows
  }
  return { thread: plain(threads[0] ?? null), transaction: plain(transaction) }
}

async function setup(rootConn, name, kind) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.marker (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
  if (kind === 'dl') {
    await rootConn.query(`CREATE TABLE \`${schema}\`.dl (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
    await rootConn.query(`INSERT INTO \`${schema}\`.dl (id, v) VALUES (1, 0), (2, 0)`)
    await rootConn.query(`CREATE TABLE \`${schema}\`.ballast (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB`)
  } else {
    await rootConn.query(`CREATE TABLE \`${schema}\`.lk (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
    await rootConn.query(`INSERT INTO \`${schema}\`.lk (id, v) VALUES (1, 0)`)
  }
  return schema
}

function schemaName(prefix, mode, repetition) {
  return `${prefix}_${mode.replaceAll('-', '_')}_r${repetition}`
}

function startSession(database, port) {
  const child = spawn('php', [phpScript], {
    cwd,
    env: {
      ...process.env,
      MPCS_HOST: endpoint.host,
      MPCS_PORT: String(port),
      MPCS_USER: instance.user,
      MPCS_PASSWORD: instance.password,
      MPCS_DATABASE: database,
    },
  })
  let buffer = ''
  let stderr = ''
  const waiters = []
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    buffer += chunk
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline)
      buffer = buffer.slice(newline + 1)
      const waiter = waiters.shift()
      if (waiter) {
        try {
          assertNoSecrets(line, secrets)
          const message = JSON.parse(line)
          if (message.ok === false) waiter.reject(new Error(message.message ?? 'php session command failed'))
          else waiter.resolve(message)
        } catch (error) {
          waiter.reject(error)
        }
      }
      newline = buffer.indexOf('\n')
    }
  })
  child.stderr.on('data', (chunk) => { stderr += chunk })
  child.on('error', (error) => {
    while (waiters.length) waiters.shift().reject(error)
  })
  child.on('close', () => {
    while (waiters.length) waiters.shift().reject(new Error('php session closed'))
  })

  function request(command, timeoutMs = 10000) {
    return withTimeout(new Promise((resolve, reject) => {
      waiters.push({ resolve, reject })
      child.stdin.write(`${JSON.stringify(command)}\n`)
    }), timeoutMs, command.op ?? 'command')
  }

  async function close() {
    if (child.exitCode != null || child.killed) return { left_transaction_open: null, stderr: stderr.slice(0, 500) }
    let reply = null
    try { reply = await request({ op: 'close' }, 5000) } catch { /* the process may already be failing */ }
    child.stdin.end()
    if (child.exitCode == null) {
      await withTimeout(new Promise((resolve) => child.once('close', resolve)), 3000, 'php exit').catch(() => child.kill())
    }
    const text = stderr.slice(0, 500)
    assertNoSecrets(text, secrets)
    return { ...(reply ?? {}), stderr: text }
  }

  return { request, close }
}

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs} ms`)), timeoutMs)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}
