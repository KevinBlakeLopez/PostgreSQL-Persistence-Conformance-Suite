// TX-01A propagation slice: pg.Client and TypeORM DataSource.transaction.
//
//   pnpm run pg:up
//   node research/transaction-outcome-propagation/experiments/tx01a-pg-typeorm.mjs
//
// Uses the disposable server and the TypeORM adapter's installed pg and typeorm.
// Does not import the PPCS harness.

import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomBytes } from 'node:crypto'
import { pgCapabilityReport } from '../lib/capabilities.mjs'
import { verifyInstance, loadInstance, withFreshDatabase, observerClient, subjectClient, readOutcome, FIXTURE_SQL } from '../lib/instance.mjs'
import { classifyBoundary, verifiedOutcome } from '../lib/boundary.mjs'
import { decisionInput, propagationRecord, tag, SCENARIO } from '../lib/record.mjs'
import { renderReport } from '../lib/report.mjs'
import { schemaErrors, containsSecret } from '../lib/validate.mjs'
import { watchCommits } from '../lib/watch-commit.mjs'

const root = fileURLToPath(new URL('../../..', import.meta.url))
const requireAdapter = createRequire(join(root, 'adapters/typeorm/package.json'))
const pg = requireAdapter('pg')
const { DataSource, EntitySchema } = requireAdapter('typeorm')
const pgPackage = requireAdapter('pg/package.json')
const typeormPackage = JSON.parse(readFileSync(join(root, 'adapters/typeorm/node_modules/typeorm/package.json'), 'utf8'))

const COMMAND = 'node research/transaction-outcome-propagation/experiments/tx01a-pg-typeorm.mjs'
const REPETITIONS = 3
const COMPARED = ['verified_outcome', 'driver_command_tag', 'sqlstate', 'application_reported', 'framework_reported', 'information_loss_boundary']
const CAPABILITY_SCOPE = 'pg.Client public API, taken from the pg-read-tag subject in this run and copied onto the other subjects. Untested capabilities stay UNKNOWN.'
const LIMITS = [
  'No packet capture. The server command tag is inferred from pg Result.command. Result.addCommandComplete stores the first token of the command-completion text.',
  'TX-01B, TX-02, and TX-03 were not run.',
  'Connection failure, unknown commit outcome, rollback acknowledgment, connection invalidation, and savepoint failure were not tested.',
  'The TypeORM command tag is read by a diagnostic wrapper around pg.Client.prototype.query. That wrapper is not a TypeORM API.',
  'Client.getTransactionStatus() returns the ReadyForQuery status byte the client stored. This run does not capture the ReadyForQuery packet.',
]

const idColumn = { type: Number, primary: true, generated: 'increment' }
const Item = new EntitySchema({ name: 'Item', tableName: 'item', columns: { id: idColumn, name: { type: String }, qty: { type: Number, default: 0 } } })
const Uniq = new EntitySchema({ name: 'Uniq', tableName: 'uniq', columns: { id: idColumn, code: { type: String, unique: true } } })

function packageRoot(requireFn, name) {
  let dir = dirname(requireFn.resolve(name))
  for (let i = 0; i < 6; i += 1) {
    const file = join(dir, 'package.json')
    if (existsSync(file)) {
      const pkg = JSON.parse(readFileSync(file, 'utf8'))
      if (pkg.name === name) return { pkg, dir }
    }
    dir = dirname(dir)
  }
  throw new Error(`package.json for ${name} was not found`)
}

function findLine(file, snippet) {
  if (!existsSync(file)) return null
  const index = readFileSync(file, 'utf8').split('\n').findIndex((line) => line.includes(snippet))
  return index === -1 ? null : index + 1
}

// The query promise rejects on ErrorResponse. ReadyForQuery, which carries the
// status byte, can arrive in a later packet. Wait until the client is ready
// again before reading it.
async function statusWhenReady(client) {
  const start = Date.now()
  while (client.readyForQuery !== true) {
    if (Date.now() - start > 1000) break
    await new Promise((resolve) => setImmediate(resolve))
  }
  const status = client.getTransactionStatus()
  return typeof status === 'string' && status.length > 0 ? status : null
}

function sqlstateOf(error) {
  if (!error) return { code: null, basis: 'No error object.' }
  if (typeof error.code === 'string') return { code: error.code, basis: 'The caught error has a string code property.' }
  if (typeof error.driverError?.code === 'string') return { code: error.driverError.code, basis: 'The caught error exposes code on driverError.' }
  return { code: null, basis: 'The caught error has no SQLSTATE code.' }
}

function evidenceItem(fields) {
  return {
    package: null,
    version: null,
    git_head: null,
    path: null,
    symbol: null,
    line: null,
    ...fields,
  }
}

function serverCommandTag(commandTag, commandTagObservation) {
  if (commandTagObservation === 'OBSERVED' && commandTag) {
    return tag({
      value: commandTag,
      observation: 'INFERRED',
      access: 'source_inspection',
      basis: 'pg Result.command is the first token of the command-completion text (Result.addCommandComplete). This run did not capture the protocol packet. The inferred tag is the driver field that was observed.',
    })
  }
  return tag({
    value: null,
    observation: 'NOT_OBSERVED',
    access: 'not_applicable',
    basis: 'The driver command tag was not observed, so no server command tag is inferred.',
  })
}

function absentFramework() {
  return {
    present: false,
    reported: 'NOT_APPLICABLE',
    call: null,
    threw: null,
    resolved_value: null,
    command_tag: tag({
      observation: 'NOT_APPLICABLE',
      access: 'not_applicable',
      basis: 'This subject does not call a persistence framework.',
    }),
    after_transaction_commit: null,
    after_transaction_rollback: null,
    basis: null,
  }
}

function commitRow({ sql, commandTag, commandPresent, rowCount, rowCountPresent, errorCode, settled, transactionStatus }) {
  return {
    sql,
    command_tag: commandTag,
    command_present: commandPresent,
    row_count: rowCount,
    row_count_present: rowCountPresent,
    error_code: errorCode,
    settled,
    transaction_status: transactionStatus,
  }
}

async function runPg({ settings, database, observer, marker, readTag }) {
  const client = subjectClient(pg, settings, database, 'ppcs-propagation-pg')
  await client.connect()
  try {
    await client.query('begin')
    await client.query('insert into item (name) values ($1)', [marker])
    const id = (await client.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')).rows[0]
    const xid = id?.xid ?? null
    const pid = Number.isInteger(Number(id?.pid)) ? Number(id.pid) : null
    let caught = null
    try {
      await client.query("insert into uniq (code) values ('taken')")
    } catch (error) {
      caught = error
    }
    const statusAfterError = await statusWhenReady(client)
    let reply = null
    let commitError = null
    try {
      reply = await client.query('COMMIT')
    } catch (error) {
      commitError = error
    }
    const statusAfterCommit = client.getTransactionStatus()
    const outcome = await readOutcome(observer, { xid, marker, pid })
    const rawTag = typeof reply?.command === 'string' ? reply.command : null
    const commandTag = rawTag && rawTag.length > 0 ? rawTag : null
    const commandPresent = Boolean(reply && Object.prototype.hasOwnProperty.call(reply, 'command'))
    const rowCountPresent = Boolean(reply && Object.prototype.hasOwnProperty.call(reply, 'rowCount'))
    const rowCount = rowCountPresent ? reply.rowCount : null
    const querySettled = commitError ? 'rejected' : 'resolved'
    const commandTagObservation = commandTag ? 'OBSERVED' : 'NOT_OBSERVED'
    const sql = sqlstateOf(caught)
    let applicationReported
    if (readTag) {
      if (querySettled === 'rejected') applicationReported = 'REPORTED_FAILURE'
      else if (commandTag === 'ROLLBACK') applicationReported = 'REPORTED_ROLLBACK'
      else if (commandTag === 'COMMIT') applicationReported = 'REPORTED_SUCCESS'
      else applicationReported = 'REPORTED_UNKNOWN'
    } else {
      applicationReported = querySettled === 'resolved' ? 'REPORTED_SUCCESS' : 'REPORTED_FAILURE'
    }
    const statusErrorObserved = typeof statusAfterError === 'string' && statusAfterError.length > 0
    const statusCommitObserved = typeof statusAfterCommit === 'string' && statusAfterCommit.length > 0
    const contradiction = statusCommitObserved && statusAfterCommit !== 'I'
      ? `Client.getTransactionStatus() after COMMIT was ${JSON.stringify(statusAfterCommit)}. An idle session is the letter I.`
      : null
    return {
      subjectId: readTag ? 'pg-read-tag' : 'pg-ignore-tag',
      kind: readTag ? 'driver_control' : 'application_control',
      sqlstate: sql.code,
      sqlstateBasis: sql.basis,
      commandTag,
      commandTagObservation,
      commandTagAccess: 'public_return_value',
      commandPresent,
      rowCount,
      rowCountPresent,
      querySettled,
      statusAfterError: statusErrorObserved ? statusAfterError : null,
      statusAfterErrorObservation: statusErrorObserved ? 'OBSERVED' : 'NOT_OBSERVED',
      statusAfterCommit: statusCommitObserved ? statusAfterCommit : null,
      statusAfterCommitObservation: statusCommitObserved ? 'OBSERVED' : 'NOT_OBSERVED',
      instrumentation: 'none',
      commits: [commitRow({
        sql: 'COMMIT',
        commandTag,
        commandPresent,
        rowCount,
        rowCountPresent,
        errorCode: commitError?.code ?? null,
        settled: querySettled,
        transactionStatus: statusCommitObserved ? statusAfterCommit : null,
      })],
      frameworkPresent: false,
      frameworkReported: 'NOT_APPLICABLE',
      frameworkObservation: absentFramework(),
      applicationReported,
      applicationBasis: readTag
        ? `The subject reads Result.command after Client.query('COMMIT'). The query ${querySettled} with command tag ${commandTag ?? 'absent'}.`
        : `The subject treats a resolved Client.query('COMMIT') as success and does not read Result.command. The query ${querySettled}. Result.command was ${commandTag ?? 'absent'}.`,
      interpretationNote: readTag
        ? 'The application report follows Result.command. ROLLBACK is a reported rollback. A resolved promise alone is not the report.'
        : 'The application reports success from promise resolution and leaves the exposed Result.command unread. That is application misuse of the driver result. Defect claim: not made.',
      intermediateLayers: [],
      supportingContradiction: contradiction != null,
      contradiction,
      xid,
      pid,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    }
  } finally {
    await client.end().catch(() => {})
  }
}

async function runTypeorm({ settings, database, observer, marker, poolVersion }) {
  const ds = new DataSource({
    type: 'postgres',
    host: settings.host,
    port: settings.port,
    username: settings.user,
    password: settings.password,
    database,
    applicationName: 'ppcs-propagation-typeorm',
    entities: [Item, Uniq],
    synchronize: false,
    poolSize: 1,
    logger: {
      logQuery() {},
      logQueryError() {},
      logQuerySlow() {},
      logSchemaBuild() {},
      logMigration() {},
      log() {},
    },
  })
  await ds.initialize()
  const watch = watchCommits(pg)
  const hooks = { afterCommit: 0, afterRollback: 0 }
  ds.subscribers.push({
    afterTransactionCommit() { hooks.afterCommit += 1 },
    afterTransactionRollback() { hooks.afterRollback += 1 },
  })
  let sqlstate = { code: null, basis: 'The callback did not catch an error.' }
  let threw = false
  let resolved = null
  let xid = null
  let pid = null
  try {
    try {
      resolved = await ds.transaction(async (manager) => {
        await manager.getRepository(Item).insert({ name: marker })
        const [id] = await manager.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
        xid = id?.xid ?? null
        pid = Number.isInteger(Number(id?.pid)) ? Number(id.pid) : null
        try {
          await manager.getRepository(Uniq).insert({ code: 'taken' })
        } catch (error) {
          sqlstate = sqlstateOf(error)
        }
        return 'callback-sentinel'
      })
    } catch (error) {
      threw = true
      if (sqlstate.code == null) sqlstate = sqlstateOf(error)
    }
    const seen = watch.seen.slice()
    const outcome = await readOutcome(observer, { xid, marker, pid })
    const one = seen.length === 1 ? seen[0] : null
    const commandTag = one && typeof one.command_tag === 'string' && one.command_tag.length > 0 ? one.command_tag : null
    const commandTagObservation = commandTag ? 'OBSERVED' : 'NOT_OBSERVED'
    const querySettled = one?.settled === 'resolved' || one?.settled === 'rejected' ? one.settled : 'not_observed'
    const statusAfterCommit = typeof one?.transaction_status === 'string' && one.transaction_status.length > 0 ? one.transaction_status : null
    let contradiction = null
    if (seen.length !== 1) contradiction = `The diagnostic wrapper saw ${seen.length} COMMIT results. The record needs one.`
    else if (one.settled === 'not_a_promise' || one.settled === 'record_failed') contradiction = `The diagnostic wrapper could not read the COMMIT result (${one.settled}).`
    else if (statusAfterCommit && statusAfterCommit !== 'I') contradiction = `getTransactionStatus() on the COMMIT result was ${JSON.stringify(statusAfterCommit)}.`
    const applicationReported = threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS'
    const frameworkObservation = {
      present: true,
      reported: applicationReported,
      call: 'DataSource.transaction(callback)',
      threw,
      resolved_value: threw ? null : (resolved === 'callback-sentinel' ? 'callback-sentinel' : 'other'),
      command_tag: tag({
        value: null,
        observation: 'NOT_EXPOSED',
        access: 'public_return_value',
        basis: 'DataSource.transaction resolves to the callback return value. The installed commitTransaction awaits query("COMMIT") and does not return that result.',
      }),
      after_transaction_commit: hooks.afterCommit,
      after_transaction_rollback: hooks.afterRollback,
      basis: `The call ${threw ? 'threw' : 'resolved'}. afterTransactionCommit ran ${hooks.afterCommit} time(s). afterTransactionRollback ran ${hooks.afterRollback} time(s).`,
    }
    return {
      subjectId: 'typeorm-transaction',
      kind: 'framework',
      sqlstate: sqlstate.code,
      sqlstateBasis: sqlstate.basis,
      commandTag,
      commandTagObservation,
      commandTagAccess: 'diagnostic_wrapper',
      commandPresent: Boolean(one?.command_present),
      rowCount: one?.row_count_present ? one.row_count : null,
      rowCountPresent: Boolean(one?.row_count_present),
      querySettled,
      statusAfterError: null,
      statusAfterErrorObservation: 'NOT_OBSERVED',
      statusAfterCommit,
      statusAfterCommitObservation: statusAfterCommit ? 'OBSERVED' : 'NOT_OBSERVED',
      instrumentation: 'diagnostic_wrapper',
      commits: seen.map((entry) => commitRow({
        sql: entry.sql,
        commandTag: entry.command_tag,
        commandPresent: entry.command_present,
        rowCount: entry.row_count,
        rowCountPresent: entry.row_count_present,
        errorCode: entry.error_code,
        settled: entry.settled,
        transactionStatus: entry.transaction_status,
      })),
      frameworkPresent: true,
      frameworkReported: applicationReported,
      frameworkObservation,
      applicationReported,
      applicationBasis: frameworkObservation.basis,
      interpretationNote: `DataSource.transaction ${threw ? 'threw' : 'resolved to the callback sentinel'}. afterTransactionCommit count ${hooks.afterCommit}. afterTransactionRollback count ${hooks.afterRollback}. The diagnostic wrapper saw command tag ${commandTag ?? 'none'} on the pg Result for COMMIT. Installed TypeORM ${typeormPackage.version} PostgresQueryRunner.commitTransaction awaits query("COMMIT") and does not inspect Result.command. Defect claim: not made.`,
      intermediateLayers: [{
        layer: 'POOL',
        component: 'pg-pool',
        version: poolVersion,
        observation: 'NOT_OBSERVED',
        note: 'TypeORM is configured with poolSize 1. This scenario does not record a pool reset statement. The wrapper reads Result.command when Client.query resolves, before the connection is released.',
      }],
      supportingContradiction: contradiction != null,
      contradiction,
      xid,
      pid,
      ...outcome,
      verifiedOutcome: verifiedOutcome(outcome),
    }
  } finally {
    watch.restore()
    await ds.destroy().catch(() => {})
  }
}

function summarize(obs, commandTagCapability) {
  const decision = classifyBoundary(decisionInput({
    ...obs,
    commandTagCapability,
    scenarioPreconditionsMet: obs.sqlstate === '23505' && obs.verifiedOutcome === 'ROLLED_BACK',
  }))
  return {
    repetition: obs.repetition,
    verified_outcome: obs.verifiedOutcome,
    driver_command_tag: obs.commandTag,
    sqlstate: obs.sqlstate,
    application_reported: obs.applicationReported,
    framework_reported: obs.frameworkReported,
    information_loss_boundary: decision.boundary,
    confidence: decision.confidence,
  }
}

function same(runs) {
  const first = runs[0]
  return runs.every((run) => COMPARED.every((key) => run[key] === first[key]))
}

function sourceEvidence(pgDir, poolVersion) {
  const typeormDir = join(root, 'adapters/typeorm/node_modules/typeorm')
  const resultFile = join(pgDir, 'lib/result.js')
  const clientFile = join(pgDir, 'lib/client.js')
  const runnerFile = join(typeormDir, 'driver/postgres/PostgresQueryRunner.js')
  const managerFile = join(typeormDir, 'entity-manager/EntityManager.js')
  return [
    evidenceItem({
      id: 'pg-command-complete',
      kind: 'source_inspection',
      layer: 'driver',
      package: 'pg',
      version: pgPackage.version,
      git_head: pgPackage.gitHead ?? null,
      path: 'lib/result.js',
      symbol: 'Result.addCommandComplete',
      line: findLine(resultFile, 'this.command = match[1]'),
      statement: 'Result.command is the first token of the command-completion text. Result.rowCount is parsed from the same message into a separate field.',
    }),
    evidenceItem({
      id: 'pg-ready-for-query',
      kind: 'source_inspection',
      layer: 'driver',
      package: 'pg',
      version: pgPackage.version,
      git_head: pgPackage.gitHead ?? null,
      path: 'lib/client.js',
      symbol: 'Client.getTransactionStatus',
      line: findLine(clientFile, 'getTransactionStatus()'),
      statement: 'getTransactionStatus() returns the status byte stored from ReadyForQuery in _handleReadyForQuery.',
    }),
    evidenceItem({
      id: 'typeorm-commit',
      kind: 'source_inspection',
      layer: 'framework',
      package: 'typeorm',
      version: typeormPackage.version,
      git_head: typeormPackage.gitHead ?? null,
      path: 'driver/postgres/PostgresQueryRunner.js',
      symbol: 'PostgresQueryRunner.commitTransaction',
      line: findLine(runnerFile, 'await this.query("COMMIT")'),
      statement: 'commitTransaction awaits query("COMMIT"), clears the transaction flag, and broadcasts AfterTransactionCommit. The query result is not inspected.',
    }),
    evidenceItem({
      id: 'typeorm-transaction',
      kind: 'source_inspection',
      layer: 'framework',
      package: 'typeorm',
      version: typeormPackage.version,
      git_head: typeormPackage.gitHead ?? null,
      path: 'entity-manager/EntityManager.js',
      symbol: 'EntityManager.transaction',
      line: findLine(managerFile, 'await queryRunner.commitTransaction()'),
      statement: 'transaction() awaits commitTransaction() and returns the callback result when the callback returns.',
    }),
    evidenceItem({
      id: 'typeorm-query-command',
      kind: 'source_inspection',
      layer: 'framework',
      package: 'typeorm',
      version: typeormPackage.version,
      git_head: typeormPackage.gitHead ?? null,
      path: 'driver/postgres/PostgresQueryRunner.js',
      symbol: 'PostgresQueryRunner.query',
      line: findLine(runnerFile, 'switch (raw.command)'),
      statement: 'query() reads raw.command for UPDATE and DELETE row counts. The default path returns raw.rows. commitTransaction ignores that return value.',
    }),
    evidenceItem({
      id: 'pool-version',
      kind: 'runtime',
      layer: 'pool',
      package: 'pg-pool',
      version: poolVersion,
      statement: 'The TypeORM subject sets poolSize 1, which uses pg-pool. Reset behavior was not recorded.',
    }),
  ]
}

function recordFrom(obs, { capabilityReport, server, repetitions, sources }) {
  const commandTagCapability = capabilityReport.capabilities.command_tag
  const runtime = evidenceItem({
    id: 'runtime-outcome',
    kind: 'runtime',
    layer: 'database',
    statement: `A second connection read pg_xact_status() ${obs.fate ?? 'null'} for xid ${obs.xid ?? 'null'} and marker visibility ${obs.markerVisible}. Session state ${obs.sessionState ?? 'absent'}.`,
  })
  const driverEvidence = evidenceItem({
    id: 'driver-command-tag',
    kind: obs.instrumentation === 'diagnostic_wrapper' ? 'diagnostic_instrumentation' : 'runtime',
    layer: 'driver',
    package: 'pg',
    version: pgPackage.version,
    git_head: pgPackage.gitHead ?? null,
    statement: obs.commandTagObservation === 'OBSERVED'
      ? `COMMIT ${obs.querySettled} with Result.command ${obs.commandTag}, read by ${obs.commandTagAccess}.`
      : `COMMIT command tag was ${obs.commandTagObservation}. query settled ${obs.querySettled}.`,
  })
  return propagationRecord({
    scenario: SCENARIO,
    repetitionRecorded: 1,
    subject: {
      id: obs.subjectId,
      kind: obs.kind,
      framework: obs.kind === 'framework' ? { name: 'typeorm', version: typeormPackage.version, git_head: typeormPackage.gitHead ?? null } : null,
      driver: { name: 'pg', version: pgPackage.version, git_head: pgPackage.gitHead ?? null },
      pool: obs.kind === 'framework' ? { name: 'pg-pool', version: obs.intermediateLayers[0].version } : null,
      runtime: { name: 'node', version: process.version },
      server,
    },
    verifiedOutcome: obs.verifiedOutcome,
    fate: obs.fate,
    markerVisible: obs.markerVisible,
    xid: obs.xid,
    pid: obs.pid,
    sessionState: obs.sessionState,
    sessionQuery: obs.sessionQuery,
    serverCommandTag: serverCommandTag(obs.commandTag, obs.commandTagObservation),
    capabilityScope: CAPABILITY_SCOPE,
    capabilityReport,
    driverObservation: {
      command_tag: tag({
        value: obs.commandTag,
        observation: obs.commandTagObservation,
        access: obs.commandTagAccess,
        basis: obs.commandTagAccess === 'diagnostic_wrapper'
          ? 'Diagnostic wrapper on pg.Client.prototype.query, reading Result.command on the object returned to the caller.'
          : 'Public return value of Client.query.',
      }),
      row_count: tag({
        value: obs.rowCountPresent ? obs.rowCount : null,
        observation: obs.rowCountPresent ? 'OBSERVED' : 'NOT_OBSERVED',
        access: obs.commandTagAccess,
        basis: obs.rowCountPresent ? 'Result.rowCount on the COMMIT result.' : 'Result.rowCount was not available on the COMMIT result.',
      }),
      sqlstate: tag({
        value: obs.sqlstate,
        observation: obs.sqlstate ? 'OBSERVED' : 'NOT_OBSERVED',
        access: 'public_return_value',
        basis: obs.sqlstateBasis,
      }),
      transaction_status_after_statement_error: tag({
        value: obs.statusAfterError,
        observation: obs.statusAfterErrorObservation,
        access: obs.statusAfterErrorObservation === 'OBSERVED' ? 'public_return_value' : 'not_applicable',
        basis: obs.statusAfterErrorObservation === 'OBSERVED'
          ? 'Client.getTransactionStatus() after the caught insert error, once Client.readyForQuery was true.'
          : 'Transaction status after the statement error was not read on this subject.',
      }),
      transaction_status_after_commit: tag({
        value: obs.statusAfterCommit,
        observation: obs.statusAfterCommitObservation,
        access: obs.statusAfterCommitObservation === 'OBSERVED'
          ? (obs.instrumentation === 'diagnostic_wrapper' ? 'diagnostic_wrapper' : 'public_return_value')
          : 'not_applicable',
        basis: obs.statusAfterCommitObservation === 'OBSERVED'
          ? 'Client.getTransactionStatus() after the COMMIT query settled.'
          : 'Transaction status after COMMIT was not read on this subject.',
      }),
      query_settled: obs.querySettled,
      instrumentation: obs.instrumentation,
      commits: obs.commits,
    },
    intermediateLayers: obs.intermediateLayers,
    frameworkObservation: obs.frameworkObservation,
    frameworkPresent: obs.frameworkPresent,
    frameworkReported: obs.frameworkReported,
    applicationObservation: { reported: obs.applicationReported, basis: obs.applicationBasis },
    applicationReported: obs.applicationReported,
    commandTag: obs.commandTag,
    commandTagObservation: obs.commandTagObservation,
    commandTagCapability,
    poolMaskedCommandTag: null,
    supportingContradiction: obs.supportingContradiction,
    contradiction: obs.contradiction,
    scenarioPreconditionsMet: obs.sqlstate === '23505' && obs.verifiedOutcome === 'ROLLED_BACK',
    interpretationNote: obs.interpretationNote,
    evidence: [runtime, driverEvidence, ...sources],
    limits: LIMITS,
    repetitions,
  })
}

function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

function makeRunId() {
  const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z').replaceAll(':', '-')
  return `${stamp}-${randomBytes(3).toString('hex')}`
}

const SUBJECTS = [
  { id: 'pg-read-tag', run: (args) => runPg({ ...args, readTag: true }) },
  { id: 'pg-ignore-tag', run: (args) => runPg({ ...args, readTag: false }) },
  { id: 'typeorm-transaction', run: (args) => runTypeorm(args) },
]

const settings = loadInstance()
const serverInfo = await verifyInstance(pg, settings)
const server = {
  version: serverInfo.version,
  server_version: serverInfo.server_version,
  server_version_num: serverInfo.server_version_num,
  image: serverInfo.image,
}
const pool = packageRoot(createRequire(requireAdapter.resolve('pg')), 'pg-pool')
const pgRoot = packageRoot(requireAdapter, 'pg')
const sources = sourceEvidence(pgRoot.dir, pool.pkg.version)
const startedAt = new Date().toISOString()
const attempts = []

for (let repetition = 1; repetition <= REPETITIONS; repetition += 1) {
  for (const subject of SUBJECTS) {
    const marker = `prop-${subject.id}-${repetition}-${randomBytes(2).toString('hex')}`
    const observation = await withFreshDatabase(pg, settings, async (database) => {
      const observer = observerClient(pg, settings, database)
      await observer.connect()
      try {
        await observer.query(FIXTURE_SQL)
        return await subject.run({ settings, database, observer, marker, poolVersion: pool.pkg.version })
      } finally {
        await observer.end().catch(() => {})
      }
    })
    attempts.push({ ...observation, repetition })
    console.log(`${subject.id} repetition ${repetition}: fate ${observation.fate} marker ${observation.markerVisible} tag ${observation.commandTag ?? 'none'} application ${observation.applicationReported}`)
  }
}

const capabilityReport = pgCapabilityReport(attempts.find((attempt) => attempt.subjectId === 'pg-read-tag' && attempt.repetition === 1))
const records = []
for (const subject of SUBJECTS) {
  const runs = attempts.filter((attempt) => attempt.subjectId === subject.id).sort((a, b) => a.repetition - b.repetition)
  const summaries = runs.map((attempt) => summarize(attempt, capabilityReport.capabilities.command_tag))
  const repetitions = { count: REPETITIONS, agreed: same(summaries), compared: COMPARED, runs: summaries }
  records.push(recordFrom(runs[0], { capabilityReport, server, repetitions, sources }))
}

const runId = makeRunId()
const run = {
  schema: 'ppcs-propagation-run/1',
  run_id: runId,
  scenario: SCENARIO,
  command: COMMAND,
  started_at: startedAt,
  finished_at: new Date().toISOString(),
  server,
  runtime: { name: 'node', version: process.version },
  driver: { name: 'pg', version: pgPackage.version, git_head: pgPackage.gitHead ?? null },
  framework: { name: 'typeorm', version: typeormPackage.version, git_head: typeormPackage.gitHead ?? null },
  records: records.map((record) => `records/${record.subject.id}.json`),
  capability: 'capabilities/pg-8.23.1.json',
}
const capability = {
  schema: 'ppcs-driver-capability/1',
  driver: run.driver,
  scenario: SCENARIO,
  scope: CAPABILITY_SCOPE,
  capabilities: capabilityReport.capabilities,
  notes: capabilityReport.notes,
  evidence_from: 'records/pg-read-tag.json',
}
const secrets = containsSecret({ records, run, capability }, [settings.password, settings.token])
if (secrets.length > 0) {
  console.error('Refusing to write the run: a secret would be included.')
  process.exit(1)
}
const problems = [
  ...schemaErrors('run', run),
  ...schemaErrors('capability', capability),
  ...records.flatMap((record) => schemaErrors('record', record).map((error) => `${record.subject.id}: ${error}`)),
]
if (problems.length > 0) {
  console.error(problems.join('\n'))
  process.exit(1)
}

const dir = join(root, 'research/transaction-outcome-propagation/runs', runId)
mkdirSync(join(dir, 'records'), { recursive: true })
mkdirSync(join(dir, 'capabilities'), { recursive: true })
for (const record of records) writeJson(join(dir, 'records', `${record.subject.id}.json`), record)
writeJson(join(dir, run.capability), capability)
writeJson(join(dir, 'run.json'), run)
writeFileSync(join(dir, 'summary.md'), renderReport({ run, records, capability }))

const expected = {
  'pg-read-tag': 'NONE',
  'pg-ignore-tag': 'APPLICATION',
  'typeorm-transaction': 'FRAMEWORK',
}
const failed = []
for (const record of records) {
  if (!record.repetitions.agreed) failed.push(`${record.subject.id} repetitions disagreed`)
  if (record.scenario !== SCENARIO) failed.push(`${record.subject.id} scenario changed`)
  const preconditions = record.evidence.length > 0 && record.verified_outcome === 'ROLLED_BACK' && record.driver_observation.sqlstate.value === '23505' && record.driver_observation.command_tag.value === 'ROLLBACK'
  if (!preconditions) failed.push(`${record.subject.id} did not record a 23505 rollback with command tag ROLLBACK`)
  if (record.information_loss_boundary !== expected[record.subject.id]) {
    failed.push(`${record.subject.id} boundary ${record.information_loss_boundary}, reference shape ${expected[record.subject.id]}`)
  }
}
console.log(dir)
if (failed.length > 0) {
  console.error(failed.join('\n'))
  process.exit(1)
}
