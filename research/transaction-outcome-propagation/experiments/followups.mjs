// TX-01B, TX-02, TX-03 on node-postgres and TypeORM, plus a TX-01A command-tag
// probe for the drivers this machine can run (PHP pdo_pgsql and ruby pg).
//
//   pnpm run pg:up
//   node research/transaction-outcome-propagation/experiments/followups.mjs
//
// Does not change the PPCS harness. The unseen-reply case calls the existing
// proxy in harness/lib/pg-wire-proxy.mjs and does not modify it.
import { execFileSync, spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomBytes } from 'node:crypto'
import { CAPABILITY_KEYS } from '../lib/capabilities.mjs'
import { classifyBoundary, verifiedOutcome } from '../lib/boundary.mjs'
import { FIXTURE_SQL, loadInstance, observerClient, readOutcome, subjectClient, verifyInstance, withFreshDatabase } from '../lib/instance.mjs'
import { instrumentPg } from '../lib/instrument.mjs'
import { decisionInput, propagationRecord, tag } from '../lib/record.mjs'
import { renderReport } from '../lib/report.mjs'
import { containsSecret, schemaErrors } from '../lib/validate.mjs'
import { startCommitReplyProxy } from '../../../harness/lib/pg-wire-proxy.mjs'

const root = fileURLToPath(new URL('../../..', import.meta.url))
const requireAdapter = createRequire(join(root, 'adapters/typeorm/package.json'))
const pg = requireAdapter('pg')
const { DataSource, EntitySchema } = requireAdapter('typeorm')
const pgPackage = requireAdapter('pg/package.json')
const rubyVersion = execFileSync('ruby', ['-e', 'print RUBY_VERSION'], { encoding: 'utf8' }).trim()
const typeormPackage = JSON.parse(readFileSync(join(root, 'adapters/typeorm/node_modules/typeorm/package.json'), 'utf8'))
const COMMAND = 'node research/transaction-outcome-propagation/experiments/followups.mjs'
const REPETITIONS = 3
const COMPARED = ['verified_outcome', 'application_reported', 'information_loss_boundary', 'driver_command_tag']

const idColumn = { type: Number, primary: true, generated: 'increment' }
const Item = new EntitySchema({ name: 'Item', tableName: 'item', columns: { id: idColumn, name: { type: String }, qty: { type: Number, default: 0 } } })
const Uniq = new EntitySchema({ name: 'Uniq', tableName: 'uniq', columns: { id: idColumn, code: { type: String, unique: true } } })
const silentLogger = { logQuery() {}, logQueryError() {}, logQuerySlow() {}, logSchemaBuild() {}, logMigration() {}, log() {} }

function blankCapabilities(partial = {}, notes = {}) {
  const capabilities = {}
  const fullNotes = {}
  for (const key of CAPABILITY_KEYS) {
    capabilities[key] = partial[key] ?? 'UNKNOWN'
    fullNotes[key] = notes[key] ?? 'This scenario did not establish this capability.'
  }
  return { capabilities, notes: fullNotes }
}

function evidenceItem(fields) {
  return { package: null, version: null, git_head: null, path: null, symbol: null, line: null, ...fields }
}

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)) }

function lastOf(seen, pattern) {
  const rows = seen.filter((row) => pattern.test(row.sql))
  return rows.at(-1) ?? null
}

function driverView(command) {
  if (command?.command_tag) {
    return { tag: command.command_tag, observation: 'OBSERVED', access: 'diagnostic_wrapper', settled: command.settled }
  }
  if (command?.settled === 'rejected' || command?.settled === 'not_sent') {
    return { tag: null, observation: 'NOT_OBSERVED', access: 'diagnostic_wrapper', settled: command.settled }
  }
  return { tag: null, observation: 'NOT_OBSERVED', access: 'not_applicable', settled: 'not_observed' }
}

function openDataSource(settings, database, port = settings.port) {
  return new DataSource({
    type: 'postgres',
    host: settings.host,
    port,
    username: settings.user,
    password: settings.password,
    database,
    applicationName: 'ppcs-propagation-typeorm',
    entities: [Item, Uniq],
    synchronize: false,
    poolSize: 1,
    logger: silentLogger,
  })
}

async function identify(queryable) {
  const rows = typeof queryable.query === 'function' && queryable.getRepository
    ? await queryable.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    : (await queryable.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')).rows
  const row = Array.isArray(rows) ? rows[0] : rows
  return { xid: row?.xid ?? null, pid: Number.isInteger(Number(row?.pid)) ? Number(row.pid) : null }
}

function spawnJson(command, args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: root, env })
    let out = ''
    let err = ''
    child.stdout.on('data', (chunk) => { out += chunk })
    child.stderr.on('data', (chunk) => { err += chunk })
    child.on('error', reject)
    child.on('close', (code) => {
      const line = out.trim().split('\n').filter(Boolean).at(-1)
      if (code !== 0 || !line) {
        reject(new Error(`${command} exited ${code}: ${err.slice(0, 300) || out.slice(0, 300)}`))
        return
      }
      resolve(JSON.parse(line))
    })
  })
}

function childEnv(settings, database, marker) {
  return {
    ...process.env,
    PPCS_HOST: settings.host,
    PPCS_PORT: String(settings.port),
    PPCS_USER: settings.user,
    PPCS_PASSWORD: settings.password,
    PPCS_DATABASE: database,
    PPCS_MARKER: marker,
  }
}

async function connLostPg({ settings, database, observer, marker }) {
  const client = subjectClient(pg, settings, database, 'ppcs-propagation-pg')
  await client.connect()
  const watch = instrumentPg(pg)
  try {
    await client.query('begin')
    await client.query('insert into item (name) values ($1)', [marker])
    const id = await identify(client)
    await observer.query('select pg_terminate_backend($1)', [id.pid])
    await sleep(200)
    let error = null
    try { await client.query('COMMIT') } catch (caught) { error = caught }
    const outcome = await readOutcome(observer, { xid: id.xid, marker, pid: id.pid })
    const commit = lastOf(watch.seen, /^commit\b/i)
    const view = driverView(commit)
    const message = String(error?.message ?? '').split('\n')[0].slice(0, 180)
    return baseObs({
      subjectId: 'tx01b-conn-lost-pg',
      kind: 'driver_control',
      scenario: 'TX-01B.conn-lost-before-commit',
      framework: false,
      sqlstate: error?.code ?? null,
      sqlstateBasis: message || 'COMMIT did not throw.',
      commandTag: view.tag,
      commandTagObservation: view.observation,
      commandTagAccess: view.tag ? 'public_return_value' : 'not_applicable',
      querySettled: error ? 'rejected' : 'resolved',
      applicationReported: error ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS',
      applicationBasis: error ? `Client.query('COMMIT') rejected: ${message}` : 'Client.query(\'COMMIT\') resolved after the backend was terminated.',
      interpretationNote: 'The backend was terminated before COMMIT. A rejection is a failure report, not a confirmed rollback tag.',
      clientKnowledge: 'KNOWN',
      preconditionsMet: Boolean(error) && outcome.fate === 'aborted' && outcome.markerVisible === false,
      capability: blankCapabilities({
        connection_failure: error ? 'EXPOSED' : 'UNKNOWN',
        commit_acknowledgment: view.tag ? 'EXPOSED' : 'UNKNOWN',
      }, {
        connection_failure: error ? `COMMIT rejected (${message}).` : 'COMMIT did not reject.',
        commit_acknowledgment: view.tag ? `Result.command was ${view.tag}.` : 'No COMMIT command tag was observed. The call rejected.',
      }),
      ...id,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    watch.restore()
    await client.end().catch(() => {})
  }
}

async function connLostTypeorm({ settings, database, observer, marker }) {
  const ds = openDataSource(settings, database)
  await ds.initialize()
  const watch = instrumentPg(pg)
  let id = { xid: null, pid: null }
  let threw = false
  let message = ''
  try {
    try {
      await ds.transaction(async (manager) => {
        await manager.query('insert into item (name) values ($1)', [marker])
        id = await identify(manager)
        await observer.query('select pg_terminate_backend($1)', [id.pid])
        await sleep(200)
        return 'sentinel'
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
    }
    const outcome = await readOutcome(observer, { xid: id.xid, marker, pid: id.pid })
    const commit = lastOf(watch.seen, /^commit\b/i)
    const view = driverView(commit)
    return baseObs({
      subjectId: 'tx01b-conn-lost-typeorm',
      kind: 'framework',
      scenario: 'TX-01B.conn-lost-before-commit',
      framework: true,
      sqlstate: null,
      sqlstateBasis: message || 'DataSource.transaction did not throw.',
      commandTag: view.tag,
      commandTagObservation: view.observation,
      commandTagAccess: 'diagnostic_wrapper',
      querySettled: view.settled === 'resolved' || view.settled === 'rejected' ? view.settled : 'not_observed',
      applicationReported: threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS',
      applicationBasis: threw ? `DataSource.transaction threw: ${message}` : 'DataSource.transaction resolved after the backend was terminated.',
      interpretationNote: 'The backend was terminated inside the callback, before TypeORM sent COMMIT. The recorded result is whatever the transaction call did next.',
      clientKnowledge: 'KNOWN',
      driverCallRejected: view.settled === 'rejected',
      preconditionsMet: outcome.fate === 'aborted' && outcome.markerVisible === false,
      capability: blankCapabilities({ connection_failure: 'EXPOSED' }, {
        connection_failure: 'pg_terminate_backend ran before the callback returned. The driver then had a dead connection.',
      }),
      instrumentation: 'diagnostic_wrapper',
      ...id,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    watch.restore()
    await ds.destroy().catch(() => {})
  }
}

async function unseenOn(port, settings, database, marker, observer, kind) {
  if (kind === 'pg') {
    const client = new pg.Client({
      host: settings.host,
      port,
      user: settings.user,
      password: settings.password,
      database,
      application_name: 'ppcs-propagation-pg',
    })
    client.on('error', () => {})
    await client.connect()
    try {
      await client.query('begin')
      await client.query('insert into item (name) values ($1)', [marker])
      const id = await identify(client)
      let error = null
      try { await client.query('COMMIT') } catch (caught) { error = caught }
      const outcome = await readOutcome(observer, { xid: id.xid, marker, pid: id.pid })
      const message = String(error?.message ?? '').split('\n')[0].slice(0, 180)
      return { threw: Boolean(error), message, id, outcome, commandTag: null }
    } finally {
      await client.end().catch(() => {})
    }
  }
  const ds = openDataSource(settings, database, port)
  await ds.initialize()
  let id = { xid: null, pid: null }
  let threw = false
  let message = ''
  try {
    try {
      await ds.transaction(async (manager) => {
        await manager.query('insert into item (name) values ($1)', [marker])
        id = await identify(manager)
        return 'sentinel'
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
    }
    const outcome = await readOutcome(observer, { xid: id.xid, marker, pid: id.pid })
    return { threw, message, id, outcome, commandTag: null }
  } finally {
    await ds.destroy().catch(() => {})
  }
}

async function unseen({ settings, database, observer, marker, kind }) {
  const proxy = await startCommitReplyProxy({ host: settings.host, port: settings.port })
  try {
    const result = await unseenOn(proxy.port, settings, database, marker, observer, kind)
    const dropped = proxy.dropped()
    const reported = result.threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS'
    return baseObs({
      subjectId: kind === 'pg' ? 'tx01b-unseen-pg' : 'tx01b-unseen-typeorm',
      kind: kind === 'pg' ? 'driver_control' : 'framework',
      scenario: 'TX-01B.commit-reply-unseen',
      framework: kind !== 'pg',
      sqlstate: null,
      sqlstateBasis: result.message || 'The ending call did not throw.',
      commandTag: null,
      commandTagObservation: 'NOT_OBSERVED',
      commandTagAccess: 'not_applicable',
      querySettled: result.threw ? 'rejected' : 'resolved',
      applicationReported: reported,
      applicationBasis: result.threw
        ? `The ending call rejected after the proxy dropped the COMMIT reply: ${result.message}`
        : 'The ending call resolved. The proxy was asked to drop the COMMIT reply.',
      interpretationNote: 'The proxy forwards COMMIT, then closes the client socket before the client parses ReadyForQuery. The second connection can still see the database outcome. The client cannot.',
      clientKnowledge: 'UNKNOWN',
      preconditionsMet: dropped >= 1 && result.outcome.fate === 'committed' && result.outcome.markerVisible === true,
      capability: blankCapabilities({
        unknown_commit_outcome: result.threw ? 'EXPOSED' : 'UNKNOWN',
        commit_acknowledgment: 'UNKNOWN',
      }, {
        unknown_commit_outcome: result.threw
          ? 'The ending call rejected, so the application can avoid reporting success or a confirmed rollback.'
          : 'The ending call resolved, so this run did not see the driver represent the missing reply as uncertainty.',
        commit_acknowledgment: `The proxy dropped ${dropped} COMMIT reply batch(es). No command tag was parsed by the client.`,
      }),
      ...result.id,
      ...result.outcome,
      verifiedOutcome: verifiedOutcome(result.outcome),
    })
  } finally {
    await proxy.close()
  }
}

async function savepointPg({ settings, database, observer, marker }) {
  const outer = `${marker}-outer`
  const inner = `${marker}-inner`
  const client = subjectClient(pg, settings, database, 'ppcs-propagation-pg')
  await client.connect()
  try {
    await client.query('begin')
    await client.query('insert into item (name) values ($1)', [outer])
    const id = await identify(client)
    await client.query('savepoint ppcs_nested')
    await client.query('insert into item (name) values ($1)', [inner])
    let sqlstate = null
    try { await client.query('rollback to savepoint ppcs_no_such_savepoint') } catch (error) { sqlstate = error.code ?? null }
    let reply = null
    let commitError = null
    try { reply = await client.query('COMMIT') } catch (error) { commitError = error }
    const outcome = await readOutcome(observer, { xid: id.xid, marker: outer, pid: id.pid })
    const innerRow = await observer.query('select exists(select 1 from item where name = $1) as visible', [inner])
    const commandTag = typeof reply?.command === 'string' ? reply.command : null
    const reported = commandTag === 'ROLLBACK' ? 'REPORTED_ROLLBACK' : commandTag === 'COMMIT' ? 'REPORTED_SUCCESS' : commitError ? 'REPORTED_FAILURE' : 'REPORTED_UNKNOWN'
    return baseObs({
      subjectId: 'tx02-rejected-pg',
      kind: 'driver_control',
      scenario: 'TX-02.savepoint-rollback-rejected',
      framework: false,
      sqlstate,
      sqlstateBasis: 'error.code from ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint.',
      commandTag,
      commandTagObservation: commandTag ? 'OBSERVED' : 'NOT_OBSERVED',
      commandTagAccess: 'public_return_value',
      querySettled: commitError ? 'rejected' : 'resolved',
      applicationReported: reported,
      applicationBasis: `The subject reads Result.command after the rejected savepoint rollback. Inner marker visible ${innerRow.rows[0].visible}.`,
      interpretationNote: 'The missing savepoint name is sent on purpose so PostgreSQL rejects it. This subject shows what pg exposes. It is a client-triggered 3B001, not a network fault.',
      clientKnowledge: 'KNOWN',
      preconditionsMet: sqlstate === '3B001' && commandTag === 'ROLLBACK' && outcome.fate === 'aborted' && outcome.markerVisible === false,
      capability: blankCapabilities({
        command_tag: commandTag ? 'EXPOSED' : 'UNKNOWN',
        sqlstate: sqlstate ? 'EXPOSED' : 'UNKNOWN',
        savepoint_failure: sqlstate === '3B001' ? 'EXPOSED' : 'UNKNOWN',
      }, {
        command_tag: commandTag ? `COMMIT resolved with Result.command ${commandTag}.` : 'No COMMIT command tag.',
        sqlstate: `ROLLBACK TO the missing savepoint raised ${sqlstate ?? 'no code'}.`,
        savepoint_failure: 'The error code is on the rejected query. The following COMMIT tag is a separate result.',
      }),
      ...id,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    await client.end().catch(() => {})
  }
}

async function savepointTypeorm({ settings, database, observer, marker }) {
  const outer = `${marker}-outer`
  const inner = `${marker}-inner`
  const ds = openDataSource(settings, database)
  await ds.initialize()
  const watch = instrumentPg(pg, { rewriteRollbackTo: true })
  let id = { xid: null, pid: null }
  let threw = false
  let message = ''
  try {
    try {
      await ds.transaction(async (manager) => {
        await manager.query('insert into item (name) values ($1)', [outer])
        id = await identify(manager)
        try {
          await manager.transaction(async (nested) => {
            await nested.query('insert into item (name) values ($1)', [inner])
            throw new Error('nested scope fails')
          })
        } catch (error) {
          message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
        }
        return 'outer-sentinel'
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
    }
    const outcome = await readOutcome(observer, { xid: id.xid, marker: outer, pid: id.pid })
    const commit = lastOf(watch.seen, /^commit\b/i)
    const view = driverView(commit)
    const rollback = watch.seen.find((row) => /ppcs_no_such_savepoint/i.test(row.sql))
    return baseObs({
      subjectId: 'tx02-rejected-typeorm',
      kind: 'framework',
      scenario: 'TX-02.savepoint-rollback-rejected',
      framework: true,
      sqlstate: rollback?.error_code ?? null,
      sqlstateBasis: message || 'No error text.',
      commandTag: view.tag,
      commandTagObservation: view.observation,
      commandTagAccess: 'diagnostic_wrapper',
      querySettled: view.settled === 'resolved' || view.settled === 'rejected' ? view.settled : 'not_observed',
      applicationReported: threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS',
      applicationBasis: `${threw ? 'DataSource.transaction threw' : 'DataSource.transaction resolved'}: ${message}. Driver statements: ${watch.seen.map((row) => `${row.sql} [${row.settled}${row.command_tag ? ` ${row.command_tag}` : ''}]`).join('; ') || 'none'}.`,
      interpretationNote: 'The wrapper rewrote TypeORM\'s ROLLBACK TO SAVEPOINT to a missing name before PostgreSQL saw it. That injection is client-side. The question is what TypeORM does with PostgreSQL\'s error and with the later COMMIT tag.',
      clientKnowledge: 'KNOWN',
      driverCallRejected: view.settled === 'rejected',
      preconditionsMet: watch.state.rewrote && outcome.fate != null,
      capability: blankCapabilities({
        command_tag: view.tag ? 'EXPOSED' : 'UNKNOWN',
        savepoint_failure: watch.state.rewrote ? 'EXPOSED' : 'UNKNOWN',
      }, {
        command_tag: view.tag ? `The wrapper saw Result.command ${view.tag} for COMMIT.` : 'No COMMIT command tag was observed.',
        savepoint_failure: watch.state.rewrote ? 'The rewritten ROLLBACK TO was sent through pg.Client.query.' : 'The rewrite did not fire.',
      }),
      instrumentation: 'diagnostic_wrapper',
      ...id,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    watch.restore()
    await ds.destroy().catch(() => {})
  }
}

async function rollbackPg({ settings, database, observer, marker }) {
  const client = subjectClient(pg, settings, database, 'ppcs-propagation-pg')
  await client.connect()
  const watch = instrumentPg(pg, { rejectTopLevelRollback: true })
  try {
    await client.query('begin')
    await client.query('insert into item (name) values ($1)', [marker])
    const id = await identify(client)
    let rollbackError = null
    try { await client.query('ROLLBACK') } catch (error) { rollbackError = error }
    const beforeClose = await readOutcome(observer, { xid: id.xid, marker, pid: id.pid })
    await client.end().catch(() => {})
    const outcome = await readOutcome(observer, { xid: id.xid, marker, pid: null })
    return baseObs({
      subjectId: 'tx03-rollback-not-sent-pg',
      kind: 'driver_control',
      scenario: 'TX-03.rollback-not-sent',
      framework: false,
      sqlstate: null,
      sqlstateBasis: String(rollbackError?.message ?? '').slice(0, 180),
      commandTag: null,
      commandTagObservation: 'NOT_OBSERVED',
      commandTagAccess: 'not_applicable',
      querySettled: 'rejected',
      applicationReported: rollbackError ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS',
      applicationBasis: `ROLLBACK was rejected before send. Before the client closed, session state was ${beforeClose.sessionState ?? 'absent'} and fate was ${beforeClose.fate ?? 'null'}.`,
      interpretationNote: 'The injection does not send ROLLBACK. This subject closes the client afterward and does not start another transaction on it. Closing the backend rolls the open transaction back.',
      clientKnowledge: 'KNOWN',
      preconditionsMet: watch.state.rejected && outcome.fate === 'aborted' && outcome.markerVisible === false,
      capability: blankCapabilities({
        rollback_acknowledgment: 'EXPOSED',
        connection_invalidation: 'NOT_APPLICABLE',
      }, {
        rollback_acknowledgment: 'The ROLLBACK call rejected. There is no command tag because the statement was not sent.',
        connection_invalidation: 'This subject uses pg.Client. There is no pool to remove the connection from.',
      }),
      sessionState: beforeClose.sessionState,
      sessionQuery: beforeClose.sessionQuery,
      ...id,
      fate: outcome.fate,
      markerVisible: outcome.markerVisible,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    watch.restore()
    if (!client.ended) await client.end().catch(() => {})
  }
}

async function rollbackTypeorm({ settings, database, observer, marker }) {
  const doomed = `${marker}-doomed`
  const next = `${marker}-next`
  const ds = openDataSource(settings, database)
  await ds.initialize()
  const watch = instrumentPg(pg, { rejectTopLevelRollback: true })
  let id = { xid: null, pid: null }
  let unit1Threw = false
  let unit1Message = ''
  let unit2Threw = false
  let unit2Message = ''
  try {
    try {
      await ds.transaction(async (manager) => {
        await manager.query('insert into item (name) values ($1)', [doomed])
        id = await identify(manager)
        throw new Error('unit 1 fails')
      })
    } catch (error) {
      unit1Threw = true
      unit1Message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
    }
    try {
      await ds.transaction(async (manager) => {
        await manager.query('insert into item (name) values ($1)', [next])
        return 'unit2'
      })
    } catch (error) {
      unit2Threw = true
      unit2Message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
    }
    const outcome = await readOutcome(observer, { xid: id.xid, marker: doomed, pid: id.pid })
    const nextRow = await observer.query('select exists(select 1 from item where name = $1) as visible', [next])
    const later = outcome.markerVisible === true && outcome.fate === 'committed'
    return baseObs({
      subjectId: 'tx03-rollback-not-sent-typeorm',
      kind: 'framework',
      scenario: 'TX-03.rollback-not-sent',
      framework: true,
      sqlstate: null,
      sqlstateBasis: unit1Message,
      commandTag: null,
      commandTagObservation: 'NOT_OBSERVED',
      commandTagAccess: 'diagnostic_wrapper',
      querySettled: 'rejected',
      applicationReported: unit1Threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS',
      applicationBasis: `Unit 1 ${unit1Threw ? 'threw' : 'resolved'} (${unit1Message}). Unit 2 ${unit2Threw ? 'threw' : 'resolved'} (${unit2Message}). Next marker visible ${nextRow.rows[0].visible}. Driver statements: ${watch.seen.map((row) => `${row.sql} [${row.settled}${row.command_tag ? ` ${row.command_tag}` : ''}]`).join('; ') || 'none'}.`,
      interpretationNote: 'ROLLBACK was rejected inside pg.Client.query and was not sent. TypeORM 1.1.2 EntityManager.transaction calls queryRunner.release() with no error, and release() forwards that empty argument to pg-pool.',
      clientKnowledge: 'KNOWN',
      laterUnitCommittedEarlierWrite: later,
      preconditionsMet: watch.state.rejected && unit1Threw,
      capability: blankCapabilities({
        rollback_acknowledgment: 'EXPOSED',
        pool_reset: 'UNKNOWN',
        connection_invalidation: later ? 'NOT_EXPOSED' : 'UNKNOWN',
      }, {
        rollback_acknowledgment: 'The injected rejection is the driver-visible result of ROLLBACK. No command tag exists because the statement was not sent.',
        pool_reset: 'No pool reset statement was recorded between the two transaction calls.',
        connection_invalidation: later
          ? 'The earlier write became visible, so the connection was reused while its transaction was still open.'
          : 'This run did not show the earlier write being committed by the next unit.',
      }),
      instrumentation: 'diagnostic_wrapper',
      ...id,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    })
  } finally {
    watch.restore()
    await ds.destroy().catch(() => {})
  }
}

async function phpProbe({ settings, database, observer, marker }) {
  const env = childEnv(settings, database, marker)
  const printed = await spawnJson('php', [join(root, 'research/transaction-outcome-propagation/probes/tx01a.php')], env)
  const outcome = await readOutcome(observer, { xid: printed.xid, marker, pid: printed.pid })
  const success = printed.commit_threw !== true && printed.commit_return === true
  return baseObs({
    subjectId: 'tx01a-php-pdo',
    kind: 'driver_control',
    scenario: 'TX-01A.caught-error-then-commit',
    framework: false,
    driverName: 'pdo_pgsql',
    driverVersion: printed.php,
    sqlstate: printed.sqlstate == null ? null : String(printed.sqlstate),
    sqlstateBasis: 'PDOException::getCode on the duplicate insert.',
    commandTag: null,
    commandTagObservation: 'NOT_EXPOSED',
    commandTagAccess: 'not_applicable',
    querySettled: printed.commit_threw ? 'rejected' : 'resolved',
    applicationReported: printed.commit_threw ? 'REPORTED_FAILURE' : success ? 'REPORTED_SUCCESS' : 'REPORTED_UNKNOWN',
    applicationBasis: `PDO::commit() ${printed.commit_threw ? 'threw' : `returned ${JSON.stringify(printed.commit_return)}`}. The method has no command-tag field.`,
    interpretationNote: 'pdo_pgsql does not expose PQcmdStatus. A true return is the only success signal this call gives. This run does not capture the protocol message libpq parsed.',
    clientKnowledge: 'KNOWN',
    preconditionsMet: String(printed.sqlstate) === '23505',
    capability: blankCapabilities({
      command_tag: 'NOT_EXPOSED',
      sqlstate: String(printed.sqlstate) === '23505' ? 'EXPOSED' : 'UNKNOWN',
      commit_acknowledgment: 'NOT_EXPOSED',
    }, {
      command_tag: 'PDO::commit() returns a boolean. There is no command tag on the public result.',
      sqlstate: `The caught insert code was ${printed.sqlstate ?? 'absent'}.`,
      commit_acknowledgment: 'The boolean return is not PostgreSQL\'s command tag.',
    }),
    commandTagCapability: 'NOT_EXPOSED',
    ...outcome,
    xid: printed.xid,
    pid: printed.pid,
    verifiedOutcome: verifiedOutcome(outcome),
  })
}

async function rubyProbe({ settings, database, observer, marker }) {
  const printed = await spawnJson('ruby', [join(root, 'research/transaction-outcome-propagation/probes/tx01a.rb')], childEnv(settings, database, marker))
  const outcome = await readOutcome(observer, { xid: printed.xid, marker, pid: printed.pid })
  const commandTag = typeof printed.cmd_status === 'string' && printed.cmd_status.length > 0 ? printed.cmd_status : null
  const reported = printed.commit_error ? 'REPORTED_FAILURE' : commandTag === 'ROLLBACK' ? 'REPORTED_ROLLBACK' : commandTag === 'COMMIT' ? 'REPORTED_SUCCESS' : 'REPORTED_UNKNOWN'
  return baseObs({
    subjectId: 'tx01a-ruby-pg',
    kind: 'driver_control',
    scenario: 'TX-01A.caught-error-then-commit',
    framework: false,
    driverName: 'pg',
    driverVersion: printed.pg_version,
    sqlstate: printed.sqlstate,
    sqlstateBasis: 'PG::Result#result_error_field(PG::PG_DIAG_SQLSTATE).',
    commandTag,
    commandTagObservation: commandTag ? 'OBSERVED' : 'NOT_OBSERVED',
    commandTagAccess: 'public_return_value',
    querySettled: printed.commit_error ? 'rejected' : 'resolved',
    applicationReported: reported,
    applicationBasis: `PG::Result#cmd_status was ${commandTag ?? 'absent'}. transaction_status was ${printed.transaction_status}.`,
    interpretationNote: 'The subject reads cmd_status. transaction_status is a separate integer and is not the command tag.',
    clientKnowledge: 'KNOWN',
    preconditionsMet: printed.sqlstate === '23505' && commandTag === 'ROLLBACK',
    capability: blankCapabilities({
      command_tag: commandTag ? 'EXPOSED' : 'UNKNOWN',
      sqlstate: printed.sqlstate === '23505' ? 'EXPOSED' : 'UNKNOWN',
      transaction_status: Number.isInteger(printed.transaction_status) ? 'EXPOSED' : 'UNKNOWN',
      commit_acknowledgment: commandTag ? 'EXPOSED' : 'UNKNOWN',
    }, {
      command_tag: commandTag ? `cmd_status was ${commandTag}.` : 'cmd_status was absent.',
      sqlstate: `The caught insert SQLSTATE was ${printed.sqlstate ?? 'absent'}.`,
      transaction_status: `PG::Connection#transaction_status returned ${printed.transaction_status} after COMMIT.`,
      commit_acknowledgment: 'cmd_status is the acknowledgment this API exposes for COMMIT.',
    }),
    statusAfter: String(printed.transaction_status),
    ...outcome,
    xid: printed.xid,
    pid: printed.pid,
    verifiedOutcome: verifiedOutcome(outcome),
  })
}

function baseObs(fields) {
  return {
    framework: false,
    driverName: 'pg',
    driverVersion: pgPackage.version,
    driverCallRejected: false,
    laterUnitCommittedEarlierWrite: false,
    instrumentation: 'none',
    commandTagCapability: fields.commandTag ? 'EXPOSED' : fields.commandTagObservation === 'NOT_EXPOSED' ? 'NOT_EXPOSED' : 'UNKNOWN',
    sessionState: null,
    sessionQuery: null,
    ...fields,
  }
}

function absentFramework() {
  return {
    present: false,
    reported: 'NOT_APPLICABLE',
    call: null,
    threw: null,
    resolved_value: null,
    command_tag: tag({ observation: 'NOT_APPLICABLE', access: 'not_applicable', basis: 'This subject does not call a persistence framework.' }),
    after_transaction_commit: null,
    after_transaction_rollback: null,
    basis: null,
  }
}

function toRecord(obs, { server, repetitions }) {
  const framework = obs.framework === true
  const querySettled = obs.querySettled === 'resolved' || obs.querySettled === 'rejected' ? obs.querySettled : 'not_observed'
  return propagationRecord({
    scenario: obs.scenario,
    subject: {
      id: obs.subjectId,
      kind: obs.kind,
      framework: framework ? { name: 'typeorm', version: typeormPackage.version, git_head: typeormPackage.gitHead ?? null } : null,
      driver: { name: obs.driverName, version: obs.driverVersion, git_head: obs.driverName === 'pg' && obs.driverVersion === pgPackage.version ? (pgPackage.gitHead ?? null) : null },
      pool: framework ? { name: 'pg-pool', version: '3.14.0' } : null,
      runtime: {
        name: obs.driverName === 'pdo_pgsql' ? 'php' : obs.subjectId.includes('ruby') ? 'ruby' : 'node',
        version: obs.driverName === 'pdo_pgsql' ? obs.driverVersion : obs.subjectId.includes('ruby') ? rubyVersion : process.version,
      },
      server,
    },
    verifiedOutcome: obs.verifiedOutcome,
    fate: obs.fate,
    markerVisible: obs.markerVisible,
    xid: obs.xid,
    pid: obs.pid,
    sessionState: obs.sessionState ?? obs.session_state ?? null,
    sessionQuery: obs.sessionQuery ?? null,
    clientKnowledge: obs.clientKnowledge,
    serverCommandTag: obs.commandTag
      ? tag({ value: obs.commandTag, observation: 'INFERRED', access: 'source_inspection', basis: 'Inferred from the driver command tag. This run did not capture the protocol packet.' })
      : tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'No driver command tag was observed, so no server command tag is inferred.' }),
    capabilityScope: `${obs.driverName} ${obs.driverVersion}, from this scenario only.`,
    capabilityReport: obs.capability,
    commandTag: obs.commandTag,
    commandTagObservation: obs.commandTagObservation,
    commandTagCapability: obs.commandTagCapability,
    frameworkPresent: framework,
    frameworkReported: framework ? obs.applicationReported : 'NOT_APPLICABLE',
    applicationReported: obs.applicationReported,
    driverCallRejected: obs.driverCallRejected,
    laterUnitCommittedEarlierWrite: obs.laterUnitCommittedEarlierWrite,
    poolMaskedCommandTag: null,
    scenarioPreconditionsMet: obs.preconditionsMet,
    supportingContradiction: false,
    driverObservation: {
      command_tag: tag({
        value: obs.commandTag,
        observation: obs.commandTagObservation,
        access: obs.commandTagAccess,
        basis: obs.commandTagAccess === 'diagnostic_wrapper' ? 'Diagnostic wrapper on pg.Client.prototype.query.' : obs.commandTagAccess === 'public_return_value' ? 'Public driver result.' : 'This API does not expose a command tag.',
      }),
      row_count: tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'Row count was not the measurement in this scenario.' }),
      sqlstate: tag({ value: obs.sqlstate, observation: obs.sqlstate ? 'OBSERVED' : 'NOT_OBSERVED', access: 'public_return_value', basis: obs.sqlstateBasis }),
      transaction_status_after_statement_error: tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'Not sampled at the statement error in this scenario.' }),
      transaction_status_after_commit: tag({ value: obs.statusAfter ?? null, observation: obs.statusAfter ? 'OBSERVED' : 'NOT_OBSERVED', access: obs.statusAfter ? 'public_return_value' : 'not_applicable', basis: obs.statusAfter ? 'Driver transaction-status value after the ending call.' : 'Not sampled.' }),
      query_settled: querySettled,
      instrumentation: obs.instrumentation,
      commits: [],
    },
    frameworkObservation: framework ? {
      present: true,
      reported: obs.applicationReported,
      call: 'DataSource.transaction(callback)',
      threw: obs.applicationReported === 'REPORTED_FAILURE',
      resolved_value: obs.applicationReported === 'REPORTED_SUCCESS' ? 'callback_or_commit' : null,
      command_tag: tag({ value: null, observation: 'NOT_EXPOSED', access: 'public_return_value', basis: 'DataSource.transaction does not return a command tag.' }),
      after_transaction_commit: null,
      after_transaction_rollback: null,
      basis: obs.applicationBasis,
    } : absentFramework(),
    applicationObservation: { reported: obs.applicationReported, basis: obs.applicationBasis },
    intermediateLayers: framework ? [{
      layer: 'POOL',
      component: 'pg-pool',
      version: '3.14.0',
      observation: 'NOT_OBSERVED',
      note: 'TypeORM uses pg-pool with poolSize 1. Reset statements were not recorded.',
    }] : [],
    interpretationNote: obs.interpretationNote,
    evidence: [evidenceItem({
      id: 'runtime',
      kind: 'runtime',
      layer: 'database',
      statement: `pg_xact_status() ${obs.fate ?? 'null'}, marker visible ${obs.markerVisible}, session ${obs.sessionState ?? 'absent'}, xid ${obs.xid ?? 'null'}.`,
    })],
    limits: [
      'Java and .NET are not installed in this environment, so pgjdbc and Npgsql were not executed.',
      'The system Python has no psycopg module, so psycopg was not executed.',
      'No packet capture. A server command tag is inferred only when a driver command tag was observed.',
      'TX-02\'s missing savepoint name and TX-03\'s withheld ROLLBACK are client-side injections.',
      'TX-01B.commit-reply-unseen uses harness/lib/pg-wire-proxy.mjs unchanged.',
    ],
    repetitions,
  })
}

function summarize(obs) {
  const decision = classifyBoundary(decisionInput({
    ...obs,
    scenarioPreconditionsMet: obs.preconditionsMet,
    frameworkPresent: obs.framework === true,
    frameworkReported: obs.framework === true ? obs.applicationReported : 'NOT_APPLICABLE',
  }))
  return {
    repetition: obs.repetition,
    verified_outcome: obs.verifiedOutcome,
    driver_command_tag: obs.commandTag,
    sqlstate: obs.sqlstate,
    application_reported: obs.applicationReported,
    framework_reported: obs.framework === true ? obs.applicationReported : 'NOT_APPLICABLE',
    information_loss_boundary: decision.boundary,
    confidence: decision.confidence,
  }
}

const settings = loadInstance()
const serverInfo = await verifyInstance(pg, settings)
const server = {
  version: serverInfo.version,
  server_version: serverInfo.server_version,
  server_version_num: serverInfo.server_version_num,
  image: serverInfo.image,
}

const subjects = [
  ['tx01b-conn-lost-pg', (args) => connLostPg(args)],
  ['tx01b-conn-lost-typeorm', (args) => connLostTypeorm(args)],
  ['tx01b-unseen-pg', (args) => unseen({ ...args, kind: 'pg' })],
  ['tx01b-unseen-typeorm', (args) => unseen({ ...args, kind: 'typeorm' })],
  ['tx02-rejected-pg', (args) => savepointPg(args)],
  ['tx02-rejected-typeorm', (args) => savepointTypeorm(args)],
  ['tx03-rollback-not-sent-pg', (args) => rollbackPg(args)],
  ['tx03-rollback-not-sent-typeorm', (args) => rollbackTypeorm(args)],
  ['tx01a-php-pdo', (args) => phpProbe(args)],
  ['tx01a-ruby-pg', (args) => rubyProbe(args)],
]

const attempts = []
for (let repetition = 1; repetition <= REPETITIONS; repetition += 1) {
  for (const [id, run] of subjects) {
    const marker = `prop-${id}-${repetition}-${randomBytes(2).toString('hex')}`
    const observation = await withFreshDatabase(pg, settings, async (database) => {
      const observer = observerClient(pg, settings, database)
      await observer.connect()
      try {
        await observer.query(FIXTURE_SQL)
        return await run({ settings, database, observer, marker })
      } finally {
        await observer.end().catch(() => {})
      }
    })
    attempts.push({ ...observation, repetition })
    console.log(`${id} repetition ${repetition}: fate ${observation.fate} marker ${observation.markerVisible} tag ${observation.commandTag ?? 'none'} app ${observation.applicationReported} preconditions ${observation.preconditionsMet}`)
  }
}

const records = []
for (const [id] of subjects) {
  const runs = attempts.filter((attempt) => attempt.subjectId === id).sort((a, b) => a.repetition - b.repetition)
  const summaries = runs.map(summarize)
  const agreed = summaries.every((summary) => COMPARED.every((key) => summary[key] === summaries[0][key]))
  records.push(toRecord(runs[0], {
    server,
    repetitions: { count: REPETITIONS, agreed, compared: COMPARED, runs: summaries },
  }))
}

const problems = records.flatMap((record) => schemaErrors('record', record).map((error) => `${record.subject.id}: ${error}`))
if (problems.length > 0) {
  console.error(problems.join('\n'))
  process.exit(1)
}
const secrets = containsSecret(records, [settings.password, settings.token])
if (secrets.length > 0) {
  console.error('Refusing to write: a secret would be included.')
  process.exit(1)
}

const runId = `${new Date().toISOString().replace(/\.\d{3}Z$/, 'Z').replaceAll(':', '-')}-${randomBytes(3).toString('hex')}`
const run = {
  schema: 'ppcs-propagation-run/1',
  run_id: runId,
  scenario: 'TX-01B TX-02 TX-03 and driver probes',
  command: COMMAND,
  started_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
  server,
  runtime: { name: 'node', version: process.version },
  driver: { name: 'pg', version: pgPackage.version, git_head: pgPackage.gitHead ?? null },
  framework: { name: 'typeorm', version: typeormPackage.version, git_head: typeormPackage.gitHead ?? null },
  records: records.map((record) => `records/${record.subject.id}.json`),
  capability: 'capabilities/followups.json',
}
const capability = {
  schema: 'ppcs-driver-capability/1',
  driver: { name: 'mixed', version: 'see records', git_head: null },
  scenario: run.scenario,
  scope: 'Per-scenario capabilities are on each record. This file is only an index.',
  capabilities: blankCapabilities().capabilities,
  notes: blankCapabilities().notes,
  evidence_from: 'records/',
}
const dir = join(root, 'research/transaction-outcome-propagation/runs', runId)
mkdirSync(join(dir, 'records'), { recursive: true })
mkdirSync(join(dir, 'capabilities'), { recursive: true })
const json = (value) => `${JSON.stringify(value, null, 2)}\n`
for (const record of records) writeFileSync(join(dir, 'records', `${record.subject.id}.json`), json(record))
writeFileSync(join(dir, run.capability), json(capability))
writeFileSync(join(dir, 'run.json'), json(run))
writeFileSync(join(dir, 'summary.md'), renderReport({ run, records, capability }))
console.log(dir)
const failed = records.filter((record) => record.repetitions.agreed === false || record.boundary_basis.startsWith('The scenario preconditions'))
if (failed.length > 0) {
  console.error(failed.map((record) => `${record.subject.id}: ${record.boundary_basis}`).join('\n'))
  process.exit(1)
}
