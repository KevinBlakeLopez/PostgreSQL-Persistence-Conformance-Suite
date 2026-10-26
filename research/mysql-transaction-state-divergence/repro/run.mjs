// Laravel's transaction state after InnoDB rolls back a statement or a whole transaction.
//
// Node holds the other session (a row-lock holder for errno 1205, a deadlock fixture for 1213) and observes
// the server from its own connections. PHP is the subject, one process per run (php/subject.php). This file
// does not import the PostgreSQL harness or the MySQL baseline.
//
// Every scenario states its expected observations below, before the run. They are predictions from source
// reading (illuminate/database 13.38.0, PHP's PDO and mysqlnd) and from the MySQL manual and the baseline's
// recordings. matched_expectation says whether a run agreed with that prediction. It is not a defect verdict.
//
//   node run.mjs                                 every scenario, 3 repetitions, into output/<run id>/
//   node run.mjs --only <id>[,<id>] --reps 1 --out <dir>    a subset, for development

import { spawn } from 'node:child_process'
import { createHash, randomBytes } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  MYSQL2_VERSION,
  assertNoSecrets,
  assertSchema,
  closeClient,
  describeError,
  latestDeadlock,
  loadInstance,
  lockWaitsFor,
  markerNames,
  openClient,
  plain,
  request,
  requireToken,
  sinkRows,
  statementHistory,
  threadIdOf,
  transactionHistory,
  transactionSnapshot,
  waitFor,
} from './lib.mjs'

const REPRO = dirname(fileURLToPath(import.meta.url))
const STUDY = dirname(REPRO)
const PHP_DIR = join(REPRO, 'php')
const SUBJECT = join(PHP_DIR, 'subject.php')

const LARAVEL_FILES = [
  'vendor/illuminate/database/Concerns/ManagesTransactions.php',
  'vendor/illuminate/database/ConcurrencyErrorDetector.php',
  'vendor/illuminate/database/DatabaseTransactionsManager.php',
]

const after = ['afterCommit:next']

const SCENARIOS = [
  {
    id: 'pdo.savepoint-1205.rollback-to',
    fixture: 'lock-wait',
    basis: 'Plain PDO, the statements Laravel would send for a savepoint, then ROLLBACK TO SAVEPOINT after the failure. Manual and baseline MPCS-03: with innodb_rollback_on_timeout OFF, 1205 rolls back only the statement, so the savepoint still exists and the rollback removes only the inner marker. With it ON, the whole transaction is gone: the savepoint rollback fails with 1305, the next insert autocommits, and PDO::commit() throws because that insert left no transaction.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ACTIVE', rollback_to_savepoint: 'returned', after_visible_before_end: false, main: 'returned', final_markers: ['after', 'outer'] },
      on: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ROLLED BACK', rollback_to_savepoint: 'raised:1305', after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after'] },
    },
  },
  {
    id: 'pdo.savepoint-1205.skip',
    fixture: 'lock-wait',
    basis: 'Plain PDO, as above, but nothing is sent after the 1205. OFF: the transaction and the savepoint are still open, so COMMIT keeps the inner marker written before the timeout. This is the server-side consequence of not sending ROLLBACK TO SAVEPOINT. ON: there is nothing left to keep; the next insert autocommits and PDO::commit() throws.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ACTIVE', after_visible_before_end: false, main: 'returned', final_markers: ['after', 'inner', 'outer'], rollback_to_savepoint_sent: false },
      on: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ROLLED BACK', after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after'], rollback_to_savepoint_sent: false },
    },
  },
  {
    id: 'pdo.savepoint-1213',
    fixture: 'deadlock',
    basis: 'Plain PDO savepoint, then the subject is the deadlock victim. 1213 rolls back the whole transaction, savepoints included, so ROLLBACK TO SAVEPOINT fails with 1305, the next insert autocommits, and PDO::commit() throws.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, state_after_error: 'ROLLED BACK', rollback_to_savepoint: 'raised:1305', after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after'] },
    },
  },
  {
    id: 'pdo.caught-1213.commit',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'Plain PDO: the deadlock error is caught and commit() is called with no statement in between. Source reading: pdo_mysql decides whether a transaction is active from the server-status bit mysqlnd kept from the last OK packet, and an error packet carries no status. The bit still says "in transaction", so PDO sends COMMIT, the server acknowledges a COMMIT with no transaction, and commit() returns true. Not run before: the baseline always inserted a row first.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, state_after_error: 'ROLLED BACK', pdo_in_transaction_after_error: true, main: 'returned', final_markers: [] },
    },
  },
  {
    id: 'pdo.caught-1205.commit',
    fixture: 'lock-wait',
    basis: 'Plain PDO: the 1205 is caught and commit() follows directly. OFF: the transaction is open, so commit keeps the marker. ON: the transaction is gone, and by the same source reading as pdo.caught-1213.commit, commit() still returns true.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ACTIVE', pdo_in_transaction_after_error: true, main: 'returned', final_markers: ['tx'] },
      on: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ROLLED BACK', pdo_in_transaction_after_error: true, main: 'returned', final_markers: [] },
    },
  },
  {
    id: 'laravel.commit',
    fixture: null,
    basis: 'Control. DB::transaction() commits, afterCommit runs once, afterRollBack does not, and the next transaction is unaffected.',
    expect: {
      off: { main: 'returned', final_markers: ['next', 'tx'], sink_after_end: ['afterCommit:tx'], sink_final: ['afterCommit:tx', ...after] },
    },
  },
  {
    id: 'laravel.nested-1205-caught',
    fixture: 'lock-wait',
    basis: 'The candidate. ConcurrencyErrorDetector matches "Lock wait timeout exceeded". At level 2, handleTransactionException lowers the level, runs the inner afterRollBack callbacks, drops the inner afterCommit callbacks and throws DeadlockException without sending ROLLBACK TO SAVEPOINT. OFF: the transaction and savepoint survive the 1205, so when the outer closure catches and returns, COMMIT keeps the inner marker after afterRollBack:inner has run. ON: InnoDB already rolled everything back; the next insert autocommits, PDO::commit() throws, and the outer afterCommit stays in the manager until the next commit (the laravel/framework#61964 path).',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', state_after_error: 'ACTIVE', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: false, main: 'returned', rollback_to_savepoint_sent: false, final_markers: ['after', 'inner', 'next', 'outer'], sink_after_end: ['afterRollBack:inner', 'afterCommit:outer'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
      on: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', state_after_error: 'ROLLED BACK', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after', 'next'], sink_after_end: ['afterRollBack:inner'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
    },
  },
  {
    id: 'laravel.nested-1205-caught.server-timeout',
    fixture: 'lock-wait',
    lockWait: 'server-default',
    basis: 'laravel.nested-1205-caught with the server\'s default innodb_lock_wait_timeout (50 s) instead of the session setting of 2 s, so the result does not depend on the shortened wait. Baseline MPCS-03 found the same rollback scope for 50 s and 2 s.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', state_after_error: 'ACTIVE', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: false, main: 'returned', rollback_to_savepoint_sent: false, final_markers: ['after', 'inner', 'next', 'outer'], sink_after_end: ['afterRollBack:inner', 'afterCommit:outer'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
    },
  },
  {
    id: 'laravel.nested-1205-caught.outer-rollback',
    fixture: 'lock-wait',
    basis: 'Control requested in the refinement: the outer transaction rolls back explicitly after catching the inner timeout. Outer DB::beginTransaction(), inner DB::transaction() that fails with 1205, caught, then DB::rollBack(). The inner unit gets the same DeadlockException and afterRollBack:inner as in the candidate. rollBack() to level 0 sends ROLLBACK (PDO still reports a transaction: really open with OFF, stale with ON), so neither marker remains and afterRollBack:outer runs.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', state_after_error: 'ACTIVE', sink_after_error: ['afterRollBack:inner'], main: 'returned', rollback_sent: true, rollback_to_savepoint_sent: false, final_markers: ['next'], sink_after_end: ['afterRollBack:inner', 'afterRollBack:outer'], sink_final: ['afterRollBack:inner', 'afterRollBack:outer', ...after] },
      on: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', state_after_error: 'ROLLED BACK', sink_after_error: ['afterRollBack:inner'], main: 'returned', rollback_sent: true, rollback_to_savepoint_sent: false, final_markers: ['next'], sink_after_end: ['afterRollBack:inner', 'afterRollBack:outer'], sink_final: ['afterRollBack:inner', 'afterRollBack:outer', ...after] },
    },
  },
  {
    id: 'laravel.nested-1205-escapes',
    fixture: 'lock-wait',
    basis: 'Control for the candidate. The DeadlockException leaves the outer closure too. At level 1 it is a concurrency error, so Laravel calls rollBack(), and PDO still reports a transaction (really open with OFF, the stale status bit with ON), so ROLLBACK is sent. Nothing commits, afterRollBack runs for both levels, and the exception reaches the caller.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', main: 'raised:DeadlockException', rollback_to_savepoint_sent: false, rollback_sent: true, final_markers: ['next'], sink_after_end: ['afterRollBack:inner', 'afterRollBack:outer'], sink_final: ['afterRollBack:inner', 'afterRollBack:outer', ...after] },
      on: { trigger_errno: 1205, subject_waited: true, inner: 'raised:DeadlockException', main: 'raised:DeadlockException', rollback_to_savepoint_sent: false, rollback_sent: true, final_markers: ['next'], sink_after_end: ['afterRollBack:inner', 'afterRollBack:outer'], sink_final: ['afterRollBack:inner', 'afterRollBack:outer', ...after] },
    },
  },
  {
    id: 'laravel.nested-explicit-1205',
    fixture: 'lock-wait',
    basis: 'Control for the candidate. The same savepoint through beginTransaction() and rollBack(): rollBack() to level 1 sends ROLLBACK TO SAVEPOINT trans2 whatever the error was. OFF: the inner marker is removed and the outer transaction commits. ON: the savepoint is gone, so ROLLBACK TO SAVEPOINT fails with 1305; rollBack() rethrows before it lowers the level, and the outer handler sends the same statement again and fails the same way. The PDOException with 1305 reaches the caller, the 1205 is not in its cause chain, and the level stays at 2. The next DB::transaction() is then a savepoint (SAVEPOINT trans3, a no-op outside a transaction) whose insert autocommits; no COMMIT is sent and no callback runs. This is the failure mode laravel/framework#61829 reports for SQL Server.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ACTIVE', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: false, main: 'returned', rollback_to_savepoint_sent: true, final_markers: ['after', 'next', 'outer'], sink_after_end: ['afterRollBack:inner', 'afterCommit:outer'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
      on: { trigger_errno: 1205, subject_waited: true, main: 'raised:PDOException', rollback_to_savepoint_sent: true, final_markers: ['next'], sink_after_end: [], sink_final: [] },
    },
  },
  {
    id: 'laravel.nested-duplicate-caught',
    fixture: null,
    basis: 'Control for the candidate: the same application code, with a duplicate key (1062) as the inner failure. That is not a concurrency error, so handleTransactionException calls rollBack(), which sends ROLLBACK TO SAVEPOINT trans2. The inner marker is removed and the outer transaction commits.',
    expect: {
      off: { trigger_errno: 1062, inner: 'raised:UniqueConstraintViolationException', state_after_error: 'ACTIVE', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: false, main: 'returned', rollback_to_savepoint_sent: true, final_markers: ['after', 'next', 'outer'], sink_after_end: ['afterRollBack:inner', 'afterCommit:outer'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
    },
  },
  {
    id: 'laravel.caught-1213',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'The deadlock error is caught inside DB::transaction() and one more marker is written. That insert autocommits and refreshes the status bit, so PDO::commit() throws "There is no active transaction". handleCommitTransactionException does not tell the transactions manager, so afterCommit:tx stays pending and runs at the next commit (laravel/framework#61964).',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, state_after_error: 'ROLLED BACK', after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after', 'next'], sink_after_end: [], sink_final: ['afterCommit:tx', ...after] },
    },
  },
  {
    id: 'laravel.caught-1213-return',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'The deadlock error is caught inside DB::transaction() and the closure returns with no further statement. By the source reading in pdo.caught-1213.commit, PDO::commit() returns true, so DB::transaction() returns and afterCommit:tx runs while InnoDB has rolled the transaction back.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, state_after_error: 'ROLLED BACK', pdo_in_transaction_after_error: true, main: 'returned', final_markers: ['next'], sink_after_end: ['afterCommit:tx'], sink_final: ['afterCommit:tx', ...after] },
    },
  },
  {
    id: 'laravel.nested-1213-caught',
    fixture: 'deadlock',
    basis: 'Deadlock inside the inner DB::transaction(), caught by the outer closure. InnoDB rolled everything back, which is the premise of Laravel\'s DeadlockException branch. The next insert autocommits, PDO::commit() throws, and the outer afterCommit stays pending until the next commit.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, inner: 'raised:DeadlockException', state_after_error: 'ROLLED BACK', sink_after_error: ['afterRollBack:inner'], after_visible_before_end: true, main: 'raised:PDOException', final_markers: ['after', 'next'], sink_after_end: ['afterRollBack:inner'], sink_final: ['afterRollBack:inner', 'afterCommit:outer', ...after] },
    },
  },
  {
    id: 'laravel.explicit-caught-1213',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'DB::beginTransaction() and DB::commit() with the documented catch that calls DB::rollBack(). The insert after the caught deadlock autocommits. commit() throws before it lowers the level; rollBack() then sees PDO out of a transaction, sends nothing, and tells the manager, so afterRollBack:tx runs and afterCommit:tx is dropped.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, state_after_error: 'ROLLED BACK', after_visible_before_end: true, main: 'raised:PDOException', rollback_sent: false, final_markers: ['after', 'next'], sink_after_end: ['afterRollBack:tx'], sink_final: ['afterRollBack:tx', ...after] },
    },
  },
  {
    id: 'laravel.caught-1205-return',
    fixture: 'lock-wait',
    basis: 'The 1205 is caught inside DB::transaction() and the closure returns. OFF: the transaction is open and its marker commits; afterCommit is correct. ON: InnoDB rolled the transaction back, and by the source reading in pdo.caught-1213.commit, PDO::commit() returns true and afterCommit:tx runs.',
    expect: {
      off: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ACTIVE', main: 'returned', final_markers: ['next', 'tx'], sink_after_end: ['afterCommit:tx'], sink_final: ['afterCommit:tx', ...after] },
      on: { trigger_errno: 1205, subject_waited: true, state_after_error: 'ROLLED BACK', pdo_in_transaction_after_error: true, main: 'returned', final_markers: ['next'], sink_after_end: ['afterCommit:tx'], sink_final: ['afterCommit:tx', ...after] },
    },
  },
  {
    id: 'laravel.escaped-1213',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'Control. The deadlock error leaves the closure, which is the documented path. rollBack() runs; by the stale-bit source reading, PDO still believes it is in a transaction and sends ROLLBACK, which the server acknowledges. afterRollBack runs and the QueryException reaches the caller. The subject names this single attempt attempt-1.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, main: 'raised:QueryException', rollback_sent: true, final_markers: ['next'], sink_after_end: ['afterRollBack:attempt-1'], sink_final: ['afterRollBack:attempt-1', ...after] },
    },
  },
  {
    id: 'laravel.escaped-1213-retry',
    scope: 'secondary',
    fixture: 'deadlock',
    basis: 'Control. DB::transaction($callback, 2): the first attempt is the deadlock victim and is rolled back; the second attempt commits. afterRollBack runs for the first attempt and afterCommit for the second.',
    expect: {
      off: { victim: 'subject', trigger_errno: 1213, main: 'returned', final_markers: ['attempt-2', 'next'], sink_after_end: ['afterRollBack:attempt-1', 'afterCommit:attempt-2'], sink_final: ['afterRollBack:attempt-1', 'afterCommit:attempt-2', ...after] },
    },
  },
]

const args = parseArgs(process.argv.slice(2))
const instance = loadInstance()
const secrets = [instance.password, instance.root_password, instance.token]
const runId = `${new Date().toISOString().replace(/\.\d+Z$/, 'Z').replaceAll(':', '-')}-${randomBytes(3).toString('hex')}`
const outDir = args.out ?? join(STUDY, 'output', runId)

const servers = {}
for (const key of ['off', 'on']) {
  const endpoint = instance[key]
  const root = await openClient(instance, endpoint, `root-${key}`, 'root')
  await requireToken(root.conn, instance.token)
  const observer = await openClient(instance, endpoint, `observer-${key}`, 'root')
  servers[key] = { endpoint, root, observer }
}

const runs = []
let serverConfig = null
try {
  serverConfig = await collectServerConfig()
  if (serverConfig.off.innodb_rollback_on_timeout !== 0 || serverConfig.on.innodb_rollback_on_timeout !== 1) {
    throw new Error('innodb_rollback_on_timeout is not OFF on 13316 and ON on 13317')
  }
  const selected = SCENARIOS.filter((scenario) => (!args.only || args.only.includes(scenario.id))
    && (args.scope === 'all' || (scenario.scope ?? 'refined') === args.scope))
  for (const scenario of selected) {
    for (const server of Object.keys(scenario.expect)) {
      for (let repetition = 1; repetition <= args.reps; repetition += 1) {
        const record = await runOne(scenario, server, repetition)
        runs.push(record)
        const tag = record.matched_expectation ? 'MATCH ' : 'DIFFER'
        console.error(`${tag} ${scenario.id} ${server} r${repetition}${record.mismatches.length ? `  ${JSON.stringify(record.mismatches)}` : ''}`)
      }
    }
  }
} finally {
  for (const { root, observer } of Object.values(servers)) {
    await closeClient(root)
    await closeClient(observer)
  }
}

writeOutputs()
if (runs.some((record) => !record.matched_expectation)) process.exitCode = 1

async function runOne(scenario, server, repetition) {
  const { endpoint, root, observer } = servers[server]
  const schema = assertSchema(`mysd_${scenario.id.replace(/[.-]/g, '_')}_${server}_r${repetition}`)
  await createSchema(root.conn, schema)
  const record = {
    scenario: scenario.id,
    server,
    innodb_rollback_on_timeout: server === 'on',
    repetition,
    schema,
    basis: scenario.basis,
    expected: scenario.expect[server],
    other_session: null,
    checkpoints: [],
    notices: [],
  }
  const other = await prepareOtherSession(scenario.fixture, endpoint, schema, record)
  const subject = startSubject(scenario.id, endpoint, schema, scenario.lockWait ?? '2')
  let subjectId = null
  let threadId = null
  let blockingPoll = null
  let fixtureCross = null
  try {
    for (;;) {
      const message = await subject.next(120000)
      if (message.type === 'hello') {
        subjectId = message.subject_connection_id
        threadId = await threadIdOf(observer.conn, subjectId)
        record.subject = { connection_id: subjectId, thread_id: threadId, sink_connection_id: message.sink_connection_id }
        subject.resume()
      } else if (message.type === 'notice') {
        record.notices.push(message)
        if (message.name === 'blocking') {
          blockingPoll = waitFor(async () => {
            const rows = await lockWaitsFor(observer.conn, subjectId)
            return rows.length ? rows : null
          }, 5000)
        }
      } else if (message.type === 'checkpoint') {
        if (blockingPoll) {
          const waited = await blockingPoll
          record.subject_lock_wait = { found: waited.found, elapsed_ms: waited.elapsed_ms, rows: waited.value }
          blockingPoll = null
        }
        const entry = { name: message.name, subject: { state: message.state, fired: message.fired } }
        if (message.name === 'holding-row-2') {
          fixtureCross = request(other.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
          const waited = await waitFor(async () => {
            const rows = await lockWaitsFor(observer.conn, other.id)
            return rows.length ? rows : null
          }, 5000)
          entry.fixture_wait = { found: waited.found, elapsed_ms: waited.elapsed_ms, rows: waited.value }
        }
        entry.server = {
          transaction: await transactionSnapshot(observer.conn, threadId, subjectId),
          markers: await markerNames(observer.conn, schema),
          sink: await sinkRows(observer.conn, schema),
        }
        if (message.name === 'final') {
          record.statements = await statementHistory(observer.conn, threadId)
          record.transactions = await transactionHistory(observer.conn, threadId)
        }
        record.checkpoints.push(entry)
        subject.resume()
      } else if (message.type === 'result') {
        record.result = message
        break
      } else {
        record.notices.push(message)
      }
    }
    record.exit = await subject.exit()
  } catch (error) {
    record.runner_error = describeError(error)
    record.exit = await subject.kill()
  } finally {
    if (fixtureCross) record.fixture_cross = await fixtureCross
    if (other) {
      record.other_session.end = await request(other.conn, 'ROLLBACK')
      await closeClient(other)
    }
  }
  if (scenario.fixture === 'deadlock') record.deadlock = await latestDeadlock(observer.conn)
  // A connection opened after the subject exited, so its read cannot be part of anything the subject did.
  const reader = await openClient(instance, endpoint, 'fresh-reader', 'root')
  try {
    record.final = { opened_after_subject_exit: true, markers: await markerNames(reader.conn, schema), sink: await sinkRows(reader.conn, schema) }
  } finally {
    await closeClient(reader)
  }
  record.observed = extract(record, scenario.fixture)
  record.mismatches = compare(record.expected, record.observed)
  record.matched_expectation = record.mismatches.length === 0 && !record.runner_error
  return record
}

async function prepareOtherSession(fixture, endpoint, schema, record) {
  if (!fixture) return null
  const other = await openClient(instance, endpoint, fixture === 'deadlock' ? 'deadlock-fixture' : 'lock-holder', 'app')
  await other.conn.query(`USE \`${schema}\``)
  const steps = [await request(other.conn, 'START TRANSACTION')]
  if (fixture === 'deadlock') {
    // Eight more rows than the subject writes, so InnoDB rolls back the subject when the cycle closes.
    for (let n = 0; n < 8; n += 1) steps.push(await request(other.conn, 'INSERT INTO ballast (n) VALUES (?)', [n]))
    steps.push(await request(other.conn, 'UPDATE dl SET v = v + 1 WHERE id = 1'))
  } else {
    steps.push(await request(other.conn, 'UPDATE lk SET v = v + 1 WHERE id = 1'))
  }
  record.other_session = { role: other.role, connection_id: other.id, setup: steps.map(({ sql, outcome, error }) => ({ sql, outcome, error })) }
  if (steps.some((step) => step.outcome !== 'resolved')) throw new Error(`${other.role} setup failed`)
  return other
}

async function createSchema(root, schema) {
  await root.query(`DROP DATABASE IF EXISTS \`${schema}\``)
  await root.query(`CREATE DATABASE \`${schema}\``)
  await root.query(`GRANT ALL PRIVILEGES ON \`${schema}\`.* TO 'mysd'@'%'`)
  await root.query(`CREATE TABLE \`${schema}\`.marker (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, name VARCHAR(64) NOT NULL, UNIQUE KEY marker_name (name)) ENGINE=InnoDB`)
  await root.query(`CREATE TABLE \`${schema}\`.dl (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
  await root.query(`INSERT INTO \`${schema}\`.dl (id, v) VALUES (1, 0), (2, 0)`)
  await root.query(`CREATE TABLE \`${schema}\`.lk (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB`)
  await root.query(`INSERT INTO \`${schema}\`.lk (id, v) VALUES (1, 0)`)
  await root.query(`CREATE TABLE \`${schema}\`.ballast (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB`)
  await root.query(`CREATE TABLE \`${schema}\`.uniq_row (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, code VARCHAR(32) NOT NULL, UNIQUE KEY uniq_code (code)) ENGINE=InnoDB`)
  await root.query(`INSERT INTO \`${schema}\`.uniq_row (code) VALUES ('taken')`)
  await root.query(`CREATE TABLE \`${schema}\`.callback_sink (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, seq INT NOT NULL, callback VARCHAR(64) NOT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)) ENGINE=InnoDB`)
}

/** The values the expectations are compared with. Each one is read from a recorded field named alongside. */
function extract(record, fixture) {
  const steps = record.result?.steps ?? []
  const step = (name) => steps.find((entry) => entry.step === name) ?? null
  const checkpoint = (name) => record.checkpoints.find((entry) => entry.name === name) ?? null
  const trigger = step('trigger')
  const statements = record.statements ?? []
  const observed = {
    main: outcome(step('main')),
    trigger_errno: errnoOf(trigger),
    inner: outcome(step('inner transaction')),
    rollback_to_savepoint: step('rollback to savepoint') ? outcome(step('rollback to savepoint'), true) : null,
    state_after_error: checkpoint('after-error')?.server.transaction.events_transactions_current[0]?.STATE ?? null,
    pdo_in_transaction_after_error: checkpoint('after-error')?.subject.state.pdo_in_transaction ?? null,
    sink_after_error: checkpoint('after-error')?.server.sink.map((row) => row.callback) ?? null,
    after_visible_before_end: checkpoint('after-continue') ? checkpoint('after-continue').server.markers.includes('after') : null,
    sink_after_end: checkpoint('after-end')?.server.sink.map((row) => row.callback) ?? null,
    final_markers: [...(record.final?.markers ?? [])].sort(),
    sink_final: (record.final?.sink ?? []).map((row) => row.callback),
    rollback_to_savepoint_sent: statements.some((row) => row.EVENT_NAME === 'statement/sql/rollback_to_savepoint'),
    rollback_sent: statements.some((row) => row.EVENT_NAME === 'statement/sql/rollback'),
    subject_waited: record.subject_lock_wait ? record.subject_lock_wait.found : null,
    victim: null,
  }
  if (fixture === 'deadlock') {
    const fixtureGot1213 = record.fixture_cross?.outcome === 'rejected' && record.fixture_cross.error?.errno === 1213
    const fixtureWaited = record.checkpoints.some((entry) => entry.fixture_wait?.found)
    if (fixtureWaited && observed.trigger_errno === 1213 && record.fixture_cross?.outcome === 'resolved') observed.victim = 'subject'
    else if (fixtureGot1213) observed.victim = 'fixture'
    else observed.victim = 'none'
  }
  return observed
}

function outcome(step, withErrno = false) {
  if (!step) return null
  if (step.outcome === 'returned') return 'returned'
  if (withErrno) return `raised:${errnoOf(step)}`
  return `raised:${step.error.class.split('\\').pop()}`
}

function errnoOf(step) {
  if (!step || step.outcome !== 'raised') return null
  if (step.error.errno != null) return Number(step.error.errno)
  const cause = step.error.previous.find((entry) => entry.errno != null)
  return cause ? Number(cause.errno) : null
}

function compare(expected, observed) {
  const mismatches = []
  for (const [field, value] of Object.entries(expected)) {
    if (JSON.stringify(observed[field]) !== JSON.stringify(value)) mismatches.push({ field, expected: value, observed: observed[field] })
  }
  return mismatches
}

function startSubject(scenarioId, endpoint, schema, lockWait) {
  const child = spawn('php', [SUBJECT, scenarioId], {
    cwd: PHP_DIR,
    env: {
      PATH: process.env.PATH,
      MYSD_HOST: endpoint.host,
      MYSD_PORT: String(endpoint.port),
      MYSD_USER: instance.user,
      MYSD_PASSWORD: instance.password,
      MYSD_DATABASE: schema,
      MYSD_LOCK_WAIT: lockWait,
    },
  })
  const queue = []
  const waiters = []
  let buffer = ''
  let stderr = ''
  let exited = null
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    buffer += chunk
    for (let newline = buffer.indexOf('\n'); newline >= 0; newline = buffer.indexOf('\n')) {
      const line = buffer.slice(0, newline)
      buffer = buffer.slice(newline + 1)
      if (!line.trim()) continue
      assertNoSecrets(line, secrets)
      let message
      try { message = JSON.parse(line) } catch { message = { type: 'unparsed', line } }
      const waiter = waiters.shift()
      if (waiter) waiter.resolve(message)
      else queue.push(message)
    }
  })
  child.stderr.on('data', (chunk) => { stderr += chunk })
  const closed = new Promise((resolve) => {
    child.on('close', (code, signal) => {
      exited = { code, signal }
      while (waiters.length) waiters.shift().reject(new Error(`subject exited (${code ?? signal}) before its next message`))
      resolve(exited)
    })
  })
  const finish = (result) => ({ ...result, stderr: sanitize(stderr).slice(0, 2000) })
  return {
    next(timeoutMs) {
      if (queue.length) return Promise.resolve(queue.shift())
      if (exited) return Promise.reject(new Error('subject already exited'))
      return withTimeout(new Promise((resolve, reject) => waiters.push({ resolve, reject })), timeoutMs, 'subject message')
    },
    resume() { child.stdin.write('resume\n') },
    async exit() {
      child.stdin.end()
      return finish(await withTimeout(closed, 10000, 'subject exit').catch(() => { child.kill('SIGKILL'); return closed }))
    },
    async kill() {
      child.kill('SIGKILL')
      return finish(await closed)
    },
  }
}

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs} ms`)), timeoutMs)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}

async function collectServerConfig() {
  const out = {}
  for (const [key, { root }] of Object.entries(servers)) {
    const [consumersBefore] = await root.conn.query(`SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_consumers
      WHERE NAME LIKE 'events_transactions%' OR NAME LIKE 'events_statements%' ORDER BY NAME`)
    await root.conn.query(`UPDATE performance_schema.setup_consumers SET ENABLED = 'YES'
      WHERE NAME IN ('events_transactions_current', 'events_transactions_history', 'events_transactions_history_long',
                     'events_statements_current', 'events_statements_history', 'events_statements_history_long')`)
    const [consumersAfter] = await root.conn.query(`SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_consumers
      WHERE NAME LIKE 'events_transactions%' OR NAME LIKE 'events_statements%' ORDER BY NAME`)
    const [instruments] = await root.conn.query(`SELECT NAME AS name, ENABLED AS enabled FROM performance_schema.setup_instruments
      WHERE NAME = 'transaction' ORDER BY NAME`)
    const [rows] = await root.conn.query(`SELECT VERSION() AS version, @@version_comment AS version_comment,
      @@global.innodb_rollback_on_timeout AS innodb_rollback_on_timeout, @@global.innodb_lock_wait_timeout AS innodb_lock_wait_timeout,
      @@global.innodb_deadlock_detect AS innodb_deadlock_detect, @@global.transaction_isolation AS transaction_isolation,
      @@global.autocommit AS autocommit, @@global.performance_schema AS performance_schema,
      @@global.performance_schema_events_statements_history_long_size AS statements_history_long_size,
      @@global.sql_mode AS sql_mode, @@global.binlog_format AS binlog_format, @@global.log_bin AS log_bin`)
    out[key] = {
      ...plain(rows[0]),
      innodb_rollback_on_timeout: Number(rows[0].innodb_rollback_on_timeout),
      port: servers[key].endpoint.port,
      container: instance[key].container,
      consumers_before: plain(consumersBefore),
      consumers_after_enable: plain(consumersAfter),
      transaction_instrument: plain(instruments),
    }
  }
  return out
}

function writeOutputs() {
  const firstResult = runs.find((record) => record.result?.versions)?.result.versions ?? null
  const versions = {
    node: process.version,
    mysql2: MYSQL2_VERSION,
    php_subject: firstResult,
    image: instance.image,
    image_id: instance.image_id,
    laravel_source_sha256: Object.fromEntries(LARAVEL_FILES.map((file) => [file, sha256(join(PHP_DIR, file))])),
    composer_lock_sha256: sha256(join(PHP_DIR, 'composer.lock')),
    pnpm_lock_sha256: sha256(join(REPRO, 'pnpm-lock.yaml')),
    study_source_sha256: Object.fromEntries(['run.mjs', 'lib.mjs', 'php/subject.php'].map((file) => [file, sha256(join(REPRO, file))])),
  }
  const groups = new Map()
  for (const record of runs) {
    const key = `${record.scenario} ${record.server}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(record)
  }
  const summary = [...groups.values()].map((records) => {
    const first = records[0]
    const fields = Object.keys(first.observed)
    const agreeing = fields.filter((field) => records.every((record) => JSON.stringify(record.observed[field]) === JSON.stringify(first.observed[field])))
    return {
      scenario: first.scenario,
      server: first.server,
      repetitions: records.length,
      matched: records.filter((record) => record.matched_expectation).length,
      observed_repetition_1: first.observed,
      fields_that_differ_between_repetitions: fields.filter((field) => !agreeing.includes(field)),
      mismatches: records.flatMap((record) => record.mismatches.map((entry) => ({ repetition: record.repetition, ...entry }))),
      runner_errors: records.filter((record) => record.runner_error).map((record) => ({ repetition: record.repetition, error: record.runner_error })),
    }
  })
  const meta = {
    run_id: runId,
    finished_at: new Date().toISOString(),
    command: `node run.mjs${process.argv.slice(2).length ? ` ${process.argv.slice(2).join(' ')}` : ''}`,
    not_the_ppcs_harness: true,
    score_meaning: 'matched_expectation compares a run with the prediction stated in run.mjs before the run. It is not a defect verdict.',
    repetitions: args.reps,
    scope: args.scope,
    runs: runs.length,
    mismatched: runs.filter((record) => !record.matched_expectation).map((record) => `${record.scenario} ${record.server} r${record.repetition}`),
  }
  mkdirSync(outDir, { recursive: true })
  write('runs.json', { ...meta, runs })
  write('summary.json', { ...meta, summary })
  write('server-config.json', serverConfig)
  write('versions.json', versions)
  console.error(`${meta.runs - meta.mismatched.length}/${meta.runs} runs matched. Output: ${sanitize(outDir)}`)
}

function write(name, value) {
  const text = sanitize(`${JSON.stringify(plain(value), null, 2)}\n`)
  assertNoSecrets(text, secrets)
  writeFileSync(join(outDir, name), text)
}

/** Recorded files name this study's directory as $STUDY, not as a path on the machine that ran it. */
function sanitize(text) {
  return String(text).replaceAll(STUDY, '$STUDY')
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

function parseArgs(argv) {
  const out = { reps: 3, only: null, out: null, scope: 'all' }
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (flag === '--reps') { out.reps = Number(value); index += 1 }
    else if (flag === '--only') { out.only = value.split(','); index += 1 }
    else if (flag === '--out') { out.out = value; index += 1 }
    else if (flag === '--scope') { out.scope = value; index += 1 }
    else throw new Error(`unknown argument ${flag}`)
  }
  if (!Number.isInteger(out.reps) || out.reps < 1) throw new Error('--reps must be a positive integer')
  // refined: the 1205 and nested-transaction question. secondary: deadlock (1213) scenarios recorded in the
  // first run, outside the refined question.
  if (!['all', 'refined', 'secondary'].includes(out.scope)) throw new Error('--scope must be all, refined or secondary')
  if (out.only) {
    const known = new Set(SCENARIOS.map((scenario) => scenario.id))
    for (const id of out.only) if (!known.has(id)) throw new Error(`unknown scenario ${id}`)
  }
  return out
}
