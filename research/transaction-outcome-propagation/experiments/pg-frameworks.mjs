// TX-01A through the query builders and ORMs that call node-postgres directly:
// Knex 3.3.0, Kysely 0.29.6, Drizzle ORM 0.45.4, and Prisma Client 7.10.1.
//
//   node research/transaction-outcome-propagation/experiments/pg-frameworks.mjs
//
// Each subject uses the copy installed for its PPCS adapter. A wrapper on that
// copy's pg.Client.prototype.query records Result.command. The database outcome
// is read on a second connection.
import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomBytes } from 'node:crypto'
import { CAPABILITY_KEYS } from '../lib/capabilities.mjs'
import { classifyBoundary, verifiedOutcome } from '../lib/boundary.mjs'
import { FIXTURE_SQL, loadInstance, observerClient, readOutcome, verifyInstance, withFreshDatabase } from '../lib/instance.mjs'
import { instrumentPg } from '../lib/instrument.mjs'
import { decisionInput, propagationRecord, tag } from '../lib/record.mjs'
import { renderReport } from '../lib/report.mjs'
import { containsSecret, schemaErrors } from '../lib/validate.mjs'

const root = fileURLToPath(new URL('../../..', import.meta.url))
const requireRoot = createRequire(join(root, 'package.json'))
const rootPg = requireRoot('pg')
const rootPgPackage = requireRoot('pg/package.json')
const COMMAND = 'node research/transaction-outcome-propagation/experiments/pg-frameworks.mjs'
const REPETITIONS = 3
const COMPARED = ['verified_outcome', 'application_reported', 'information_loss_boundary', 'driver_command_tag']
const SCENARIO = 'TX-01A.caught-error-then-commit'

function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'))
}

function packageVersion(entry) {
  let dir = dirname(entry)
  for (let i = 0; i < 4; i += 1) {
    const file = join(dir, 'package.json')
    try {
      const pkg = readJson(file)
      if (pkg.name) return { pkg, dir }
    } catch { /* keep walking */ }
    dir = dirname(dir)
  }
  throw new Error(`no package.json above ${entry}`)
}

function poolVersion(pgEntry) {
  const req = createRequire(pgEntry)
  const found = packageVersion(req.resolve('pg-pool'))
  return found.pkg.version
}

function sqlstateOf(error) {
  const seen = new Set()
  const stack = [error]
  while (stack.length) {
    const current = stack.pop()
    if (!current || typeof current !== 'object' || seen.has(current)) continue
    seen.add(current)
    for (const key of ['code', 'originalCode']) {
      const value = current[key]
      if (typeof value === 'string' && /^[0-9A-Z]{5}$/.test(value) && !/^P[0-9]{4}$/.test(value)) return value
    }
    if (current.cause) stack.push(current.cause)
    if (current.driverAdapterError) stack.push(current.driverAdapterError)
    if (current.meta) stack.push(current.meta)
  }
  const match = String(error?.message ?? '').match(/Code: `([0-9A-Z]{5})`/)
  return match?.[1] ?? null
}

function lastCommit(seen) {
  return seen.filter((row) => /^commit\b/i.test(row.sql)).at(-1) ?? null
}

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

const lucidRequire = createRequire(join(root, 'adapters/lucid/package.json'))
const knexEntry = createRequire(lucidRequire.resolve('@adonisjs/lucid')).resolve('knex')
const knexRequire = createRequire(knexEntry)
const knex = knexRequire('knex')
const knexPg = knexRequire('pg')
const knexPackage = packageVersion(knexEntry).pkg

const mikroRequire = createRequire(join(root, 'adapters/mikroorm/package.json'))
const mikroPg = mikroRequire('pg')
const sqlEntry = createRequire(mikroRequire.resolve('@mikro-orm/postgresql')).resolve('@mikro-orm/sql')
const kyselyEntry = createRequire(sqlEntry).resolve('kysely')
const kyselyPackage = packageVersion(kyselyEntry).pkg

const drizzleRequire = createRequire(join(root, 'adapters/drizzle/package.json'))
const drizzlePg = drizzleRequire('pg')
const { drizzle } = drizzleRequire('drizzle-orm/node-postgres')
const { sql: drizzleSql } = drizzleRequire('drizzle-orm')
const drizzlePackage = readJson(join(root, 'adapters/drizzle/node_modules/drizzle-orm/package.json'))

const prismaRequire = createRequire(join(root, 'adapters/prisma/package.json'))
const adapterEntry = prismaRequire.resolve('@prisma/adapter-pg')
const prismaPg = createRequire(adapterEntry)('pg')
const { PrismaPg } = prismaRequire('@prisma/adapter-pg')
const adapterPackage = packageVersion(adapterEntry).pkg
const clientPackage = readJson(join(root, 'adapters/prisma/node_modules/@prisma/client/package.json'))

function connection(settings, database, applicationName) {
  return {
    host: settings.host,
    port: settings.port,
    user: settings.user,
    password: settings.password,
    database,
    application_name: applicationName,
  }
}

async function runKnex({ settings, database, observer, marker }) {
  const watch = instrumentPg(knexPg)
  const db = knex({
    client: 'pg',
    connection: connection(settings, database, 'ppcs-propagation-knex'),
    pool: { min: 0, max: 1 },
  })
  let id = { xid: null, pid: null }
  let sqlstate = null
  let threw = false
  let message = ''
  try {
    try {
      await db.transaction(async (trx) => {
        await trx('item').insert({ name: marker })
        const raw = await trx.raw('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
        const row = raw.rows?.[0] ?? raw[0]
        id = { xid: row?.xid ?? null, pid: Number(row?.pid) || null }
        try { await trx('uniq').insert({ code: 'taken' }) } catch (error) { sqlstate = sqlstateOf(error) }
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
      sqlstate = sqlstate ?? sqlstateOf(error)
    }
    return await finish({
      observer, marker, id, sqlstate, threw, message, watch,
      subjectId: 'tx01a-knex',
      frameworkName: 'knex',
      frameworkVersion: knexPackage.version,
      driverPg: knexPg,
      call: 'knex.transaction(callback)',
      pool: poolVersion(knexRequire.resolve('pg')),
    })
  } finally {
    watch.restore()
    await db.destroy().catch(() => {})
  }
}

async function runKysely({ settings, database, observer, marker }) {
  const { Kysely, PostgresDialect, sql } = await import(pathToFileURL(join(packageVersion(kyselyEntry).dir, 'dist/index.js')).href)
  const watch = instrumentPg(mikroPg)
  const pool = new mikroPg.Pool({ ...connection(settings, database, 'ppcs-propagation-kysely'), max: 1 })
  pool.on('error', () => {})
  const db = new Kysely({ dialect: new PostgresDialect({ pool }) })
  let id = { xid: null, pid: null }
  let sqlstate = null
  let threw = false
  let message = ''
  try {
    try {
      await db.transaction().execute(async (trx) => {
        await sql`insert into item (name) values (${marker})`.execute(trx)
        const found = await sql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`.execute(trx)
        const row = found.rows[0]
        id = { xid: row?.xid ?? null, pid: Number(row?.pid) || null }
        try { await sql`insert into uniq (code) values ('taken')`.execute(trx) } catch (error) { sqlstate = sqlstateOf(error) }
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
      sqlstate = sqlstate ?? sqlstateOf(error)
    }
    return await finish({
      observer, marker, id, sqlstate, threw, message, watch,
      subjectId: 'tx01a-kysely',
      frameworkName: 'kysely',
      frameworkVersion: kyselyPackage.version,
      driverPg: mikroPg,
      call: 'db.transaction().execute(callback)',
      pool: poolVersion(mikroRequire.resolve('pg')),
    })
  } finally {
    watch.restore()
    await pool.end().catch(() => {})
  }
}

async function runDrizzle({ settings, database, observer, marker }) {
  const watch = instrumentPg(drizzlePg)
  const pool = new drizzlePg.Pool({ ...connection(settings, database, 'ppcs-propagation-drizzle'), max: 1 })
  pool.on('error', () => {})
  const db = drizzle({ client: pool })
  let id = { xid: null, pid: null }
  let sqlstate = null
  let threw = false
  let message = ''
  try {
    try {
      await db.transaction(async (tx) => {
        await tx.execute(drizzleSql`insert into item (name) values (${marker})`)
        const found = await tx.execute(drizzleSql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`)
        const row = found.rows[0]
        id = { xid: row?.xid ?? null, pid: Number(row?.pid) || null }
        try { await tx.execute(drizzleSql`insert into uniq (code) values ('taken')`) } catch (error) { sqlstate = sqlstateOf(error) }
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
      sqlstate = sqlstate ?? sqlstateOf(error)
    }
    return await finish({
      observer, marker, id, sqlstate, threw, message, watch,
      subjectId: 'tx01a-drizzle',
      frameworkName: 'drizzle-orm',
      frameworkVersion: drizzlePackage.version,
      driverPg: drizzlePg,
      call: 'db.transaction(callback)',
      pool: poolVersion(drizzleRequire.resolve('pg')),
    })
  } finally {
    watch.restore()
    await pool.end().catch(() => {})
  }
}

async function runPrisma({ settings, database, observer, marker }) {
  const { PrismaClient } = await import(pathToFileURL(join(root, 'adapters/prisma/generated/prisma/client.ts')).href)
  const watch = instrumentPg(prismaPg)
  const pool = new prismaPg.Pool({ ...connection(settings, database, 'ppcs-propagation-prisma'), max: 1 })
  pool.on('error', () => {})
  const prisma = new PrismaClient({ adapter: new PrismaPg(pool) })
  let id = { xid: null, pid: null }
  let sqlstate = null
  let threw = false
  let message = ''
  try {
    try {
      await prisma.$transaction(async (tx) => {
        await tx.$executeRaw`insert into item (name) values (${marker})`
        const rows = await tx.$queryRaw`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`
        const row = rows[0]
        id = { xid: row?.xid ?? null, pid: Number(row?.pid) || null }
        try { await tx.$executeRaw`insert into uniq (code) values ('taken')` } catch (error) { sqlstate = sqlstateOf(error) }
        return 'callback-sentinel'
      })
    } catch (error) {
      threw = true
      message = String(error?.message ?? error).split('\n')[0].slice(0, 180)
      sqlstate = sqlstate ?? sqlstateOf(error)
    }
    const finished = await finish({
      observer, marker, id, sqlstate, threw, message, watch,
      subjectId: 'tx01a-prisma',
      frameworkName: '@prisma/client',
      frameworkVersion: clientPackage.version,
      driverPg: prismaPg,
      call: 'prisma.$transaction(callback)',
      pool: poolVersion(createRequire(adapterEntry).resolve('pg')),
      extraNote: `@prisma/adapter-pg ${adapterPackage.version} executes COMMIT. PgQueryable.executeRaw returns rowCount.`,
    })
    return finished
  } finally {
    watch.restore()
    await prisma.$disconnect().catch(() => {})
    await pool.end().catch(() => {})
  }
}

async function finish(ctx) {
  const outcome = await readOutcome(ctx.observer, { xid: ctx.id.xid, marker: ctx.marker, pid: ctx.id.pid })
  const commit = lastCommit(ctx.watch.seen)
  const commandTag = commit?.command_tag && commit.settled === 'resolved' ? commit.command_tag : null
  return {
    subjectId: ctx.subjectId,
    frameworkName: ctx.frameworkName,
    frameworkVersion: ctx.frameworkVersion,
    call: ctx.call,
    pool: ctx.pool,
    extraNote: ctx.extraNote ?? '',
    sqlstate: ctx.sqlstate,
    threw: ctx.threw,
    message: ctx.message,
    commandTag,
    querySettled: ctx.threw ? 'rejected' : 'resolved',
    ...ctx.id,
    ...outcome,
    verifiedOutcome: verifiedOutcome(outcome),
    preconditionsMet: ctx.sqlstate === '23505',
    statements: ctx.watch.seen.map((row) => `${row.sql} [${row.settled}${row.command_tag ? ` ${row.command_tag}` : ''}]`).join('; '),
  }
}

function toRecord(obs, { server, repetitions }) {
  const reported = obs.threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS'
  const capability = obs.commandTag ? 'EXPOSED' : 'UNKNOWN'
  return propagationRecord({
    scenario: SCENARIO,
    subject: {
      id: obs.subjectId,
      kind: 'framework',
      framework: { name: obs.frameworkName, version: obs.frameworkVersion, git_head: null },
      driver: { name: 'pg', version: rootPgPackage.version, git_head: rootPgPackage.gitHead ?? null },
      pool: { name: 'pg-pool', version: obs.pool },
      runtime: { name: 'node', version: process.version },
      server,
    },
    verifiedOutcome: obs.verifiedOutcome,
    fate: obs.fate,
    markerVisible: obs.markerVisible,
    xid: obs.xid,
    pid: obs.pid,
    sessionState: obs.sessionState ?? null,
    sessionQuery: obs.sessionQuery ?? null,
    clientKnowledge: 'KNOWN',
    serverCommandTag: obs.commandTag
      ? tag({ value: obs.commandTag, observation: 'INFERRED', access: 'source_inspection', basis: 'Inferred from Result.command on the pg result the framework received. No packet was captured.' })
      : tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'No COMMIT command tag was observed.' }),
    capabilityScope: `pg ${rootPgPackage.version} as required by ${obs.frameworkName} ${obs.frameworkVersion}.`,
    capabilityReport: blankCapabilities({
      command_tag: capability,
      sqlstate: obs.sqlstate === '23505' ? 'EXPOSED' : 'UNKNOWN',
      commit_acknowledgment: capability,
    }, {
      command_tag: obs.commandTag ? `The wrapper saw Result.command ${obs.commandTag} for COMMIT.` : 'No COMMIT command tag was observed.',
      sqlstate: `The caught insert SQLSTATE was ${obs.sqlstate ?? 'absent'}.`,
      commit_acknowledgment: obs.commandTag ? 'Result.command is the acknowledgment pg exposes. The framework call does not return it.' : 'No acknowledgment tag was observed.',
    }),
    commandTag: obs.commandTag,
    commandTagObservation: obs.commandTag ? 'OBSERVED' : 'NOT_OBSERVED',
    commandTagCapability: capability,
    frameworkPresent: true,
    frameworkReported: reported,
    applicationReported: reported,
    scenarioPreconditionsMet: obs.preconditionsMet && obs.verifiedOutcome === 'ROLLED_BACK',
    driverObservation: {
      command_tag: tag({
        value: obs.commandTag,
        observation: obs.commandTag ? 'OBSERVED' : 'NOT_OBSERVED',
        access: 'diagnostic_wrapper',
        basis: 'Diagnostic wrapper on the pg.Client.prototype.query this framework resolves.',
      }),
      row_count: tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'Row count was not the measurement.' }),
      sqlstate: tag({ value: obs.sqlstate, observation: obs.sqlstate ? 'OBSERVED' : 'NOT_OBSERVED', access: 'public_return_value', basis: 'SQLSTATE from the caught duplicate insert.' }),
      transaction_status_after_statement_error: tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'Not sampled.' }),
      transaction_status_after_commit: tag({ value: null, observation: 'NOT_OBSERVED', access: 'not_applicable', basis: 'Not sampled.' }),
      query_settled: obs.querySettled,
      instrumentation: 'diagnostic_wrapper',
      commits: [],
    },
    frameworkObservation: {
      present: true,
      reported,
      call: obs.call,
      threw: obs.threw,
      resolved_value: obs.threw ? null : 'callback_result',
      command_tag: tag({ value: null, observation: 'NOT_EXPOSED', access: 'public_return_value', basis: `${obs.call} does not return Result.command.` }),
      after_transaction_commit: null,
      after_transaction_rollback: null,
      basis: obs.threw ? `${obs.call} threw: ${obs.message}` : `${obs.call} resolved.`,
    },
    applicationObservation: {
      reported,
      basis: `${obs.call} ${obs.threw ? `threw: ${obs.message}` : 'resolved'}. Statements: ${obs.statements || 'none'}. ${obs.extraNote ?? ''}`.trim(),
    },
    intermediateLayers: [{
      layer: 'POOL',
      component: 'pg-pool',
      version: obs.pool,
      observation: 'NOT_OBSERVED',
      note: 'The framework uses a pg pool of one connection. Reset statements were not recorded. The command tag is read from Client.query before release.',
    }],
    interpretationNote: `${obs.frameworkName} ${obs.frameworkVersion} calls ${obs.call}. The pg result of COMMIT is recorded by the wrapper, not by the framework return value. ${obs.extraNote ?? ''} Defect claim: not made.`.replace(/\s+/g, ' ').trim(),
    evidence: [evidenceItem({
      id: 'runtime',
      kind: obs.commandTag ? 'diagnostic_instrumentation' : 'runtime',
      layer: 'driver',
      package: 'pg',
      version: rootPgPackage.version,
      git_head: rootPgPackage.gitHead ?? null,
      statement: `pg_xact_status() ${obs.fate ?? 'null'}, marker visible ${obs.markerVisible}, session ${obs.sessionState ?? 'absent'}. ${obs.statements || 'No driver statements recorded.'}`,
    })],
    limits: [
      'Drizzle 1.0.0-rc.4 was not repeated. The suite already recorded the same TX-01A shape for 0.45.4 and the release candidate.',
      'Lucid and MikroORM are not separate rows. Knex and Kysely are the libraries those adapters place on pg.',
      'No packet capture. The server command tag is inferred from Result.command.',
      'psycopg, asyncpg, pgjdbc, and Npgsql were not run.',
    ],
    repetitions,
  })
}

function summarize(obs) {
  const reported = obs.threw ? 'REPORTED_FAILURE' : 'REPORTED_SUCCESS'
  const decision = classifyBoundary(decisionInput({
    verifiedOutcome: obs.verifiedOutcome,
    commandTag: obs.commandTag,
    commandTagObservation: obs.commandTag ? 'OBSERVED' : 'NOT_OBSERVED',
    commandTagCapability: obs.commandTag ? 'EXPOSED' : 'UNKNOWN',
    frameworkPresent: true,
    frameworkReported: reported,
    applicationReported: reported,
    scenarioPreconditionsMet: obs.preconditionsMet && obs.verifiedOutcome === 'ROLLED_BACK',
    clientKnowledge: 'KNOWN',
  }))
  return {
    repetition: obs.repetition,
    verified_outcome: obs.verifiedOutcome,
    driver_command_tag: obs.commandTag,
    sqlstate: obs.sqlstate,
    application_reported: reported,
    framework_reported: reported,
    information_loss_boundary: decision.boundary,
    confidence: decision.confidence,
  }
}

const subjects = [
  ['tx01a-knex', runKnex],
  ['tx01a-kysely', runKysely],
  ['tx01a-drizzle', runDrizzle],
  ['tx01a-prisma', runPrisma],
]

const settings = loadInstance()
const serverInfo = await verifyInstance(rootPg, settings)
const server = {
  version: serverInfo.version,
  server_version: serverInfo.server_version,
  server_version_num: serverInfo.server_version_num,
  image: serverInfo.image,
}
const attempts = []
for (let repetition = 1; repetition <= REPETITIONS; repetition += 1) {
  for (const [id, run] of subjects) {
    const marker = `prop-${id}-${repetition}-${randomBytes(2).toString('hex')}`
    const observation = await withFreshDatabase(rootPg, settings, async (database) => {
      const observer = observerClient(rootPg, settings, database)
      await observer.connect()
      try {
        await observer.query(FIXTURE_SQL)
        return await run({ settings, database, observer, marker })
      } finally {
        await observer.end().catch(() => {})
      }
    })
    attempts.push({ ...observation, repetition })
    console.log(`${id} repetition ${repetition}: fate ${observation.fate} marker ${observation.markerVisible} tag ${observation.commandTag ?? 'none'} threw ${observation.threw} sqlstate ${observation.sqlstate}`)
  }
}

const records = []
for (const [id] of subjects) {
  const runs = attempts.filter((attempt) => attempt.subjectId === id).sort((a, b) => a.repetition - b.repetition)
  const summaries = runs.map(summarize)
  const agreed = summaries.every((summary) => COMPARED.every((key) => summary[key] === summaries[0][key]))
  records.push(toRecord(runs[0], { server, repetitions: { count: REPETITIONS, agreed, compared: COMPARED, runs: summaries } }))
}

const problems = records.flatMap((record) => schemaErrors('record', record).map((error) => `${record.subject.id}: ${error}`))
if (problems.length) {
  console.error(problems.join('\n'))
  process.exit(1)
}
if (containsSecret(records, [settings.password, settings.token]).length) {
  console.error('Refusing to write: a secret would be included.')
  process.exit(1)
}

const runId = `${new Date().toISOString().replace(/\.\d{3}Z$/, 'Z').replaceAll(':', '-')}-${randomBytes(3).toString('hex')}`
const run = {
  schema: 'ppcs-propagation-run/1',
  run_id: runId,
  scenario: SCENARIO,
  command: COMMAND,
  started_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
  server,
  runtime: { name: 'node', version: process.version },
  driver: { name: 'pg', version: rootPgPackage.version, git_head: rootPgPackage.gitHead ?? null },
  framework: { name: 'knex,kysely,drizzle-orm,@prisma/client', version: `${knexPackage.version}, ${kyselyPackage.version}, ${drizzlePackage.version}, ${clientPackage.version}`, git_head: null },
  records: records.map((record) => `records/${record.subject.id}.json`),
  capability: 'capabilities/pg-frameworks.json',
}
const capability = {
  schema: 'ppcs-driver-capability/1',
  driver: run.driver,
  scenario: SCENARIO,
  scope: 'Command-tag exposure is on each framework record. This file is the shared pg driver.',
  capabilities: blankCapabilities({ command_tag: 'EXPOSED', commit_acknowledgment: 'EXPOSED' }, {
    command_tag: 'pg Result.command, observed through the wrapper on each framework\'s pg module when COMMIT completed.',
    commit_acknowledgment: 'The same Result.command field.',
  }).capabilities,
  notes: blankCapabilities({ command_tag: 'EXPOSED', commit_acknowledgment: 'EXPOSED' }, {
    command_tag: 'pg Result.command, observed through the wrapper on each framework\'s pg module when COMMIT completed.',
    commit_acknowledgment: 'The same Result.command field.',
  }).notes,
  evidence_from: 'records/tx01a-knex.json',
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
const failed = records.filter((record) => !record.repetitions.agreed || record.boundary_basis.startsWith('The scenario preconditions'))
if (failed.length) {
  console.error(failed.map((record) => `${record.subject.id}: ${record.boundary_basis}`).join('\n'))
  process.exit(1)
}
