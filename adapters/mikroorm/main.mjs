// PPCS adapter for MikroORM (@mikro-orm/postgresql). Each case is the MikroORM-native form of a catalog case
// (specifications/transactions.v1.json), adapted from the reused experiments (docs/provenance.md).
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { TransactionPropagation } from '@mikro-orm/postgresql'
import { ProtocolError, boundedUnit, explicitOutcome, main, managedOutcome, requestedLevel } from '../node-kit/adapter-main.mjs'
import { faultReport, instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { Item, Uniq, inRequest, openOrm } from './orm.mjs'
import { mikroPrCases } from './pr01.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const MIKRO_PG = packageDir(HERE, '@mikro-orm/postgresql')
const MIKRO_SQL = packageDir(MIKRO_PG, '@mikro-orm/sql')
// @mikro-orm/postgresql pins pg 8.23.1, the version this adapter depends on, so both resolve to one pg module and the
// trace sees MikroORM's statements. describe() records whether that holds.
const pgTrace = instrument(pg)
const samePg = realpathSync(createRequire(import.meta.url).resolve('pg')) === realpathSync(createRequire(`${MIKRO_PG}/`).resolve('pg'))

const MANAGED = {
  call: 'em.transactional(callback)',
  contract: 'In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM\'s report that the transaction committed.',
}
const NESTED_API = {
  call: 'em.transactional(callback) with a nested em.transactional(callback), default propagation NESTED',
  contract: 'MikroORM 7.2.5 documents NESTED as "Create a nested savepoint within the current transaction, or a new transaction if none exists" (enums.d.ts, TransactionPropagation), and a nested em.transactional() as creating a savepoint by default (EntityManager.transactional).',
}
const REQUIRES_NEW_API = {
  call: 'em.transactional(callback) with an inner em.transactional(callback, { propagation: REQUIRES_NEW })',
  contract: 'MikroORM 7.2.5 documents REQUIRES_NEW as "Always create a new transaction, suspending the current one if it exists" (enums.d.ts, TransactionPropagation).',
}

// The native forms these cases use where the case leaves MikroORM a choice. Each result records its form.
const TX01A_FORM = 'Reused experiment T4f: the outer scope flushes its write; the duplicate insert runs in an inner em.transactional() with propagation REQUIRED, which joins the outer transaction; the outer scope catches the error and returns with nothing pending. Other forms (for example T4g) are not covered by this result.'
const TX02_FORM = 'The nested em.transactional() is called with { clear: true }, as in reused experiments R1a, T7c and R1e. The outer scope flushes its write before the nested scope starts, and the clear fork keeps the nested scope\'s flush to its own entity, so the case isolates the savepoint rollback from the pending-write hazard that TX-04 targets.'
const TX04_FORM = 'The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the nested scope flushes its own write.'
const TX04_INDEPENDENT_FORM = 'The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the inner transaction\'s write is flushed when it commits.'

/** pg_current_xact_id() and the backend PID, read on the transaction's own connection (PostgreSQL 13 or later). */
async function identify(em) {
  const r = await em.getConnection().execute('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid', [], 'get', em.getTransactionContext())
  return { xid: r.xid, pid: r.pid }
}

const managed = ({ orm }) => (callback) => inRequest(orm, () => orm.em.transactional(callback))

// TX-05: the requested isolation level, in MikroORM's managed and explicit transaction forms.
const LEVEL_OPTION = 'TransactionOptions.isolationLevel is IsolationLevel | `${IsolationLevel}`, whose values include SERIALIZABLE = "serializable" (core/enums.d.ts)'
const LEVEL_MANAGED = {
  call: 'em.transactional(callback, { isolationLevel })',
  contract: `In MikroORM 7.2.5, em.transactional(cb, options?: TransactionOptions) "Runs your callback wrapped inside a database transaction" (core/EntityManager.d.ts), and ${LEVEL_OPTION}. It resolves once the transaction has committed.`,
}
const LEVEL_EXPLICIT = {
  start: 'em.begin({ isolationLevel })',
  commit: 'em.commit()',
  contract: `In MikroORM 7.2.5, em.begin(options?: Omit<TransactionOptions, 'ignoreNestedTransactions'>) "Starts new transaction bound to this EntityManager", and em.commit() "Commits the transaction bound to this EntityManager. Flushes before doing the actual commit query." (core/EntityManager.d.ts). ${LEVEL_OPTION}.`,
}
const TX05_MANAGED_FORM = 'em.transactional(callback, { isolationLevel }) on the request context\'s EntityManager, with the default propagation. The marker is flushed, then read back with em.find().'
const TX05_EXPLICIT_FORM = 'em.begin({ isolationLevel }) on a fork of the EntityManager, then em.commit(). The marker is flushed, then read back with em.find().'

/** The TX-05 transaction's work: write and flush the marker, read it back with a query, and report the ID with PostgreSQL's level. */
async function requestedLevelWork(em, { markers, checkpoint }) {
  em.create(Item, { name: markers.tx })
  await em.flush()
  await em.find(Item, { name: markers.tx })
  const r = await em.getConnection().execute("select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation", [], 'get', em.getTransactionContext())
  await checkpoint('after-read', { xid: r.xid, pid: r.pid, transaction_isolation: r.transaction_isolation })
}

// TX-02. Experiments R1a (the savepoint rollback fails on the client), T7c (PostgreSQL rejects it) and R1e (the backend
// is terminated). The outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the outer
// scope handles the error and ends normally. When the fault fires, the driver reports `after-fault`. As in those
// experiments, the nested call uses { clear: true }, so the nested scope starts from a clear fork (TX02_FORM).
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings }) => {
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    t.create(Item, { name: markers.outer })
    await t.flush()
    id = await identify(t)
    await checkpoint('outer-after-write', id)
    try {
      await t.transactional(async (n) => {
        n.create(Item, { name: markers.inner })
        await n.flush()
        await checkpoint('inner-after-write', { pid: id.pid })
        if (fault === 'conn-lost') await sleep(settings.settle_ms ?? 100)
        else armed = savepointRollbackFault(pgTrace, fault, () => checkpoint('after-fault', { pid: id.pid }))
        throw new Error('application error: the nested scope fails')
      }, { clear: true })
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
      nested.error = errInfo(e)
    }
  }, MANAGED)
  pgTrace.clearFaults()
  await checkpoint('after-outer', { pid: id?.pid ?? null })
  return { ...outcome, steps: { nested, ...(armed ? { fault: faultReport(armed) } : {}) }, form: TX02_FORM }
}

// TX-03. Experiments P1a (the ROLLBACK fails on the client) and P1c (the backend is terminated before it). Unit 1 fails
// and its ROLLBACK fails too; then the next unit of work runs on the same pool of one connection.
// The statement-error variant, new in PPCS 0.2 with no reused experiment, fails unit 1 with an uncaught unique
// violation instead, so the withheld ROLLBACK leaves an aborted transaction block rather than an open transaction.
const failedUnitThenNext = (failure) => async (ctx, { markers, checkpoint, settings }) => {
  let fault = null
  let id = null
  let violation = null
  const unit1 = await managedOutcome(managed(ctx), async (t) => {
    t.create(Item, { name: markers.doomed })
    await t.flush()
    id = await identify(t)
    await checkpoint('unit1-after-write', id)
    if (failure === 'conn-lost') await sleep(settings.settle_ms ?? 100)
    else fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject', onFire: () => checkpoint('after-fault', { pid: id.pid }) })
    if (failure === 'statement-error') {
      // Not caught: the unique violation aborts the transaction, and the framework's ROLLBACK is then withheld.
      try { t.create(Uniq, { code: 'taken' }); await t.flush() } catch (e) { violation = { ...errInfo(e), code: e.code ?? null, sqlState: e.sqlState ?? null }; throw e }
    }
    throw new Error('application error: unit 1 fails')
  }, MANAGED)
  pgTrace.clearFaults() // an unfired fault must not reach unit 2
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => managedOutcome(managed(ctx), async (t) => {
    t.create(Item, { name: markers.next })
    await t.flush()
    await cp('unit2-after-write', await identify(t))
  }, MANAGED))
  return { ...unit1, steps: { unit2, ...(violation ? { violation } : {}), ...(fault ? { fault: faultReport(fault) } : {}) } }
}

// TX-04.1 and TX-04.2. Experiments T2a/T2b (a failing NESTED call after a pending outer write), and a nested call
// released before the outer scope fails. The outer write stays pending in the unit of work, as ordinary MikroORM code
// leaves it. Mode clear-forks passes { clear: true } to the nested call (T2b).
const nestedScope = (variant) => async (ctx, { markers, checkpoint, mode }) => {
  const nested = { caught: false, completed: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    t.create(Item, { name: markers.outer })
    try {
      await t.transactional(async (n) => {
        n.create(Item, { name: markers.inner })
        await n.flush()
        await checkpoint('inner-after-write', await identify(n))
        if (variant === 'nested-fails') throw new Error('application error: the nested scope fails')
      }, mode === 'clear-forks' ? { clear: true } : {})
      nested.completed = true
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
    }
    if (variant === 'outer-fails') throw new Error('application error: the outer scope fails')
  }, NESTED_API)
  return { ...outcome, steps: { nested }, form: TX04_FORM }
}

// TX-04.3. Experiments T1a/T1b: REQUIRES_NEW after a pending outer write, then the outer scope fails. Mode clear-forks
// passes { clear: true } to the inner call (T1b).
const independentInner = async (ctx, { markers, checkpoint, mode }) => {
  const nested = { completed: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    t.create(Item, { name: markers.outer })
    await t.transactional(async (n) => {
      n.create(Item, { name: markers.inner })
      await checkpoint('inner-after-write', await identify(n))
    }, { propagation: TransactionPropagation.REQUIRES_NEW, ...(mode === 'clear-forks' ? { clear: true } : {}) })
    nested.completed = true
    throw new Error('application error: the outer scope fails')
  }, REQUIRES_NEW_API)
  return { ...outcome, steps: { nested }, form: TX04_INDEPENDENT_FORM }
}

const cases = {
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (em) => {
    em.create(Item, { name: markers.tx })
    await em.flush()
    await checkpoint('before-end', await identify(em))
  }, MANAGED),

  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (em) => {
    em.create(Item, { name: markers.tx })
    await em.flush()
    await checkpoint('before-end', await identify(em))
    throw new Error('application error: the request fails')
  }, MANAGED),

  // Experiment T4f: the outer scope's write is flushed; an inner REQUIRED call hits a unique violation; the outer scope
  // catches it and returns with nothing pending.
  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint }) => {
    const steps = {}
    const outcome = await managedOutcome(managed(ctx), async (outer) => {
      outer.create(Item, { name: markers.tx })
      await outer.flush()
      const id = await identify(outer)
      await checkpoint('after-write', id)
      try {
        await outer.transactional(async (em) => { em.create(Uniq, { code: 'taken' }); await em.flush() }, { propagation: TransactionPropagation.REQUIRED })
      } catch (e) {
        steps.violation = { ...errInfo(e), code: e.code ?? null, sqlState: e.sqlState ?? null }
      }
      await checkpoint('before-end', { pid: id.pid })
    }, MANAGED)
    return { ...outcome, steps, form: TX01A_FORM }
  },

  // Experiment R1f: the backend is terminated after the last write (by the runner, at the checkpoint).
  'TX-01B.conn-lost-before-commit': (ctx, { markers, checkpoint, settings }) => managedOutcome(managed(ctx), async (em) => {
    em.create(Item, { name: markers.tx })
    await em.flush()
    await checkpoint('before-end', await identify(em))
    await sleep(settings.settle_ms ?? 100)
  }, MANAGED),

  // New in PPCS: the MikroORM suite had no reply-lost experiment. The fault is the Lucid and TypeORM harnesses'
  // reply-lost simulation (LH1e, TR1e3): client-side, category D.
  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint }) => {
    let fault = null
    const outcome = await managedOutcome(managed(ctx), async (em) => {
      em.create(Item, { name: markers.tx })
      await em.flush()
      await checkpoint('before-end', await identify(em))
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
  'TX-04.independent-inner': independentInner,

  'TX-05.managed-serializable': async ({ orm }, tools) => ({
    ...await requestedLevel(
      (state) => managedOutcome((callback) => inRequest(orm, () => orm.em.transactional(async (em) => { state.started = true; return callback(em) }, { isolationLevel: tools.settings.isolation_level })), (em) => requestedLevelWork(em, tools), LEVEL_MANAGED),
      () => inRequest(orm, () => orm.em.transactional(async (em) => { await tools.checkpoint('baseline', await identify(em)) })),
    ),
    form: TX05_MANAGED_FORM,
  }),

  'TX-05.explicit-serializable': async ({ orm }, tools) => ({
    ...await requestedLevel(
      (state) => explicitOutcome({ start: async () => { const em = orm.em.fork(); await em.begin({ isolationLevel: tools.settings.isolation_level }); return em }, commit: (em) => em.commit(), rollback: (em) => em.rollback() }, (em) => requestedLevelWork(em, tools), LEVEL_EXPLICIT, state),
      async () => { const em = orm.em.fork(); await em.begin(); await tools.checkpoint('baseline', await identify(em)); await em.commit() },
    ),
    form: TX05_EXPLICIT_FORM,
  }),
  ...mikroPrCases(),
}

await main({
  describe: () => ({
    adapter: { name: 'mikroorm', version: JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version },
    framework: { name: '@mikro-orm/core', version: packageVersion(HERE, '@mikro-orm/core') },
    driver: { name: 'pg', version: packageVersion(HERE, 'pg') },
    components: {
      '@mikro-orm/postgresql': packageVersion(HERE, '@mikro-orm/postgresql'),
      '@mikro-orm/sql': packageVersion(MIKRO_PG, '@mikro-orm/sql'),
      kysely: packageVersion(MIKRO_SQL, 'kysely'),
      'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool'),
    },
  }),
  modes: {
    native: { configuration: {} },
    'clear-forks': { configuration: { clear: true, applies_to: 'the nested or inner em.transactional() call of the TX-04 cases' } },
  },
  open: async (message) => {
    const logLines = []
    const orm = await openOrm(message.connection, { poolMax: message.case.settings?.pool_max ?? 1, logLines })
    return {
      context: { orm },
      close: () => orm.close(),
      diagnostics: () => ({ trace: pgTrace.trace(), commit_replies: pgTrace.commitReplies(), trace_sees_framework_pg: samePg, logs: logLines }),
    }
  },
  cases,
})
