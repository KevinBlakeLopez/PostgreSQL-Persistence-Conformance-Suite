// PPCS adapter for TypeORM. Each case is the TypeORM-native form of a catalog case (specifications/transactions.v1.json),
// adapted from the reused experiments (docs/provenance.md).
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { ProtocolError, boundedUnit, explicitOutcome, main, managedOutcome, requestedLevel } from '../node-kit/adapter-main.mjs'
import { faultReport, instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { runTypeormMigration } from './migration.mjs'
import { Item, Uniq, openDataSource } from './orm.mjs'
import { typeormPrCases } from './pr01.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const TYPEORM = packageDir(HERE, 'typeorm')
// TypeORM loads `pg` with require(); pnpm links one pg@8.23.1 for TypeORM and for this adapter, so the trace sees
// TypeORM's statements. describe() records whether that holds.
const pgTrace = instrument(pg)
const samePg = realpathSync(createRequire(import.meta.url).resolve('pg')) === realpathSync(createRequire(`${TYPEORM}/`).resolve('pg'))

const MANAGED = {
  call: 'ds.transaction(callback)',
  contract: 'In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback\'s result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM\'s report that the transaction committed.',
}
const NESTED_API = {
  call: 'ds.transaction(callback) with a nested manager.transaction(callback)',
  contract: 'In TypeORM 1.1.2, manager.transaction() on a transactional EntityManager reuses its query runner, whose startTransaction() issues SAVEPOINT when a transaction is already active (driver/postgres/PostgresQueryRunner.js); it commits (releases) when the callback returns and rolls back when it throws.',
}

/** pg_current_xact_id() and the backend PID, read through the transaction's own query runner (PostgreSQL 13 or later). */
async function identify(manager) {
  const [r] = await manager.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: r.pid }
}

const managed = ({ ds }) => (callback) => ds.transaction(callback)

// TX-05: the requested isolation level, in TypeORM's managed and explicit (query runner) transaction forms.
const LEVELS = { 'read uncommitted': 'READ UNCOMMITTED', 'read committed': 'READ COMMITTED', 'repeatable read': 'REPEATABLE READ', serializable: 'SERIALIZABLE' }
const LEVEL_TYPE = 'IsolationLevel is one of \'READ COMMITTED\' | \'READ UNCOMMITTED\' | \'REPEATABLE READ\' | \'SERIALIZABLE\' | \'SNAPSHOT\' (driver/types/IsolationLevel.d.ts)'
const LEVEL_MANAGED = {
  call: 'ds.transaction(isolationLevel, callback)',
  contract: `In TypeORM 1.1.2, DataSource.transaction(isolationLevel, runInTransaction) "Wraps given function execution (and all operations made there) into a transaction" (data-source/DataSource.d.ts); ${LEVEL_TYPE}. It resolves once the transaction has committed.`,
}
const LEVEL_EXPLICIT = {
  start: 'queryRunner.startTransaction(isolationLevel)',
  commit: 'queryRunner.commitTransaction()',
  contract: `In TypeORM 1.1.2, QueryRunner.startTransaction(isolationLevel?: IsolationLevel) "Starts transaction", and commitTransaction() commits it (query-runner/QueryRunner.d.ts); ${LEVEL_TYPE}.`,
}
const TX05_MANAGED_FORM = 'ds.transaction(isolationLevel, callback). The marker is inserted through the repository, then read back with findOneBy().'
const TX05_EXPLICIT_FORM = 'ds.createQueryRunner(), connect(), startTransaction(isolationLevel), then commitTransaction() and release(). The marker is inserted and read back through queryRunner.manager.'

const typeormLevel = (level) => {
  if (!LEVELS[level]) throw new ProtocolError(`the case requests an unknown isolation level: ${JSON.stringify(level)}`)
  return LEVELS[level]
}

/** The TX-05 transaction's work: insert the marker, read it back with a query, and report the ID with PostgreSQL's level. */
async function requestedLevelWork(manager, { markers, checkpoint }) {
  await manager.getRepository(Item).insert({ name: markers.tx })
  await manager.getRepository(Item).findOneBy({ name: markers.tx })
  const [r] = await manager.query("select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation")
  await checkpoint('after-read', { xid: r.xid, pid: r.pid, transaction_isolation: r.transaction_isolation })
}

/** Runs `run(queryRunner)` on a query runner of its own, and releases it afterwards: the pool holds one connection. */
async function onQueryRunner(ds, run) {
  const qr = ds.createQueryRunner()
  try { return await run(qr) } finally { await qr.release().catch(() => {}) }
}

// TX-02. Experiments TR1c (the savepoint rollback fails on the client), TR1b (PostgreSQL rejects it) and TR1c2 (the
// backend is terminated). The outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the
// outer scope handles the error and ends normally. When the fault fires, the driver reports `after-fault`.
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings }) => {
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    await t.getRepository(Item).insert({ name: markers.outer })
    id = await identify(t)
    await checkpoint('outer-after-write', id)
    try {
      await t.transaction(async (n) => {
        await n.getRepository(Item).insert({ name: markers.inner })
        await checkpoint('inner-after-write', { pid: id.pid })
        if (fault === 'conn-lost') await sleep(settings.settle_ms ?? 100)
        else armed = savepointRollbackFault(pgTrace, fault, () => checkpoint('after-fault', { pid: id.pid }))
        throw new Error('application error: the nested scope fails')
      })
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
      nested.error = errInfo(e)
    }
  }, MANAGED)
  pgTrace.clearFaults()
  await checkpoint('after-outer', { pid: id?.pid ?? null })
  return { ...outcome, steps: { nested, ...(armed ? { fault: faultReport(armed) } : {}) } }
}

// TX-03. Experiments TR1d (the ROLLBACK fails on the client) and TR1d2 (the backend is terminated before it). Unit 1
// fails and its ROLLBACK fails too; then the next unit of work runs on the same pool of one connection.
// The statement-error variant, new in PPCS 0.2 with no reused experiment, fails unit 1 with an uncaught unique
// violation instead, so the withheld ROLLBACK leaves an aborted transaction block rather than an open transaction.
const failedUnitThenNext = (failure) => async (ctx, { markers, checkpoint, settings }) => {
  let fault = null
  let id = null
  let violation = null
  const unit1 = await managedOutcome(managed(ctx), async (t) => {
    await t.getRepository(Item).insert({ name: markers.doomed })
    id = await identify(t)
    await checkpoint('unit1-after-write', id)
    if (failure === 'conn-lost') await sleep(settings.settle_ms ?? 100)
    else fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject', onFire: () => checkpoint('after-fault', { pid: id.pid }) })
    if (failure === 'statement-error') {
      // Not caught: the unique violation aborts the transaction, and the framework's ROLLBACK is then withheld.
      try { await t.getRepository(Uniq).insert({ code: 'taken' }) } catch (e) { violation = { ...errInfo(e), code: e.code ?? e.driverError?.code ?? null }; throw e }
    }
    throw new Error('application error: unit 1 fails')
  }, MANAGED)
  pgTrace.clearFaults() // an unfired fault must not reach unit 2
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => managedOutcome(managed(ctx), async (t) => {
    await t.getRepository(Item).insert({ name: markers.next })
    await cp('unit2-after-write', await identify(t))
  }, MANAGED))
  return { ...unit1, steps: { unit2, ...(violation ? { violation } : {}), ...(fault ? { fault: faultReport(fault) } : {}) } }
}

// TX-04. Experiment TT2b (a failing nested transaction), and a nested transaction released before the outer one fails.
const nestedScope = (variant) => async (ctx, { markers, checkpoint }) => {
  const nested = { caught: false, completed: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    await t.getRepository(Item).insert({ name: markers.outer })
    try {
      await t.transaction(async (n) => {
        await n.getRepository(Item).insert({ name: markers.inner })
        await checkpoint('inner-after-write', await identify(n))
        if (variant === 'nested-fails') throw new Error('application error: the nested scope fails')
      })
      nested.completed = true
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
    }
    if (variant === 'outer-fails') throw new Error('application error: the outer scope fails')
  }, NESTED_API)
  return { ...outcome, steps: { nested } }
}

const cases = {
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (m) => {
    await m.getRepository(Item).insert({ name: markers.tx })
    await checkpoint('before-end', await identify(m))
  }, MANAGED),

  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (m) => {
    await m.getRepository(Item).insert({ name: markers.tx })
    await checkpoint('before-end', await identify(m))
    throw new Error('application error: the request fails')
  }, MANAGED),

  // Experiment TT1a: a write, then a caught unique violation, then the callback returns.
  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint }) => {
    const steps = {}
    const outcome = await managedOutcome(managed(ctx), async (m) => {
      await m.getRepository(Item).insert({ name: markers.tx })
      const id = await identify(m)
      await checkpoint('after-write', id)
      try { await m.getRepository(Uniq).insert({ code: 'taken' }) } catch (e) { steps.violation = { ...errInfo(e), code: e.code ?? e.driverError?.code ?? null } }
      await checkpoint('before-end', { pid: id.pid })
    }, MANAGED)
    return { ...outcome, steps }
  },

  // Experiment TR1e: the backend is terminated after the last write (by the runner, at the checkpoint).
  'TX-01B.conn-lost-before-commit': (ctx, { markers, checkpoint, settings }) => managedOutcome(managed(ctx), async (m) => {
    await m.getRepository(Item).insert({ name: markers.tx })
    await checkpoint('before-end', await identify(m))
    await sleep(settings.settle_ms ?? 100)
  }, MANAGED),

  // Experiment TR1e3's reply-lost fault: a client-side simulation, category D.
  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint }) => {
    let fault = null
    const outcome = await managedOutcome(managed(ctx), async (m) => {
      await m.getRepository(Item).insert({ name: markers.tx })
      await checkpoint('before-end', await identify(m))
      fault = pgTrace.addFault({ match: /^commit;?$/i, mode: 'reply-lost' })
    }, MANAGED)
    return { ...outcome, steps: { fault: { mode: 'reply-lost', fired: fault?.fired ?? 0 } } }
  },

  'TX-02.savepoint-rollback-not-sent': nestedFailure('not-sent'),
  'TX-02.savepoint-rollback-rejected': nestedFailure('rejected'),
  'TX-02.conn-lost-before-savepoint-rollback': nestedFailure('conn-lost'),

  'TX-03.rollback-not-sent': failedUnitThenNext('rollback-not-sent'),
  'TX-03.statement-error-rollback-not-sent': failedUnitThenNext('statement-error'),
  'TX-03.conn-lost-in-transaction': failedUnitThenNext('conn-lost'),

  'TX-04.nested-failure-contained': nestedScope('nested-fails'),
  'TX-04.nested-released-outer-rollback': nestedScope('outer-fails'),

  'TX-05.managed-serializable': async ({ ds }, tools) => ({
    ...await requestedLevel(
      (state) => managedOutcome((callback) => ds.transaction(typeormLevel(tools.settings.isolation_level), async (m) => { state.started = true; return callback(m) }), (m) => requestedLevelWork(m, tools), LEVEL_MANAGED),
      () => ds.transaction(async (m) => { await tools.checkpoint('baseline', await identify(m)) }),
    ),
    form: TX05_MANAGED_FORM,
  }),

  // The attempt's query runner is released before the plain transaction starts, since the pool holds one connection.
  'TX-05.explicit-serializable': async ({ ds }, tools) => ({
    ...await requestedLevel(
      (state) => onQueryRunner(ds, (qr) => explicitOutcome({ start: async () => { await qr.connect(); await qr.startTransaction(typeormLevel(tools.settings.isolation_level)); return qr }, commit: (q) => q.commitTransaction(), rollback: (q) => q.rollbackTransaction() }, (q) => requestedLevelWork(q.manager, tools), LEVEL_EXPLICIT, state)),
      () => onQueryRunner(ds, async (plain) => { await plain.connect(); await plain.startTransaction(); await tools.checkpoint('baseline', await identify(plain.manager)); await plain.commitTransaction() }),
    ),
    form: TX05_EXPLICIT_FORM,
  }),
  ...typeormPrCases(),
  ...Object.fromEntries([
    'MG-02.held', 'MG-02.first-deployment', 'MG-02.session-loss', 'MG-02.idle-session-timeout',
    'MG-03.valid-reversal', 'MG-03.no-reversal', 'MG-03.failing-reversal',
  ].map((id) => [id, runTypeormMigration])),
}

await main({
  describe: () => ({
    adapter: { name: 'typeorm', version: JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version },
    framework: { name: 'typeorm', version: packageVersion(HERE, 'typeorm') },
    driver: { name: 'pg', version: packageVersion(HERE, 'pg') },
    components: { 'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool') },
  }),
  modes: { native: { configuration: {} } },
  open: async (message) => {
    const logLines = []
    const ds = await openDataSource(message.connection, { poolMax: message.case.settings?.pool_max ?? 1, logLines })
    return {
      context: { ds },
      close: () => ds.destroy(),
      diagnostics: () => ({ trace: pgTrace.trace(), commit_replies: pgTrace.commitReplies(), trace_sees_framework_pg: samePg, logs: logLines }),
    }
  },
  cases,
})
