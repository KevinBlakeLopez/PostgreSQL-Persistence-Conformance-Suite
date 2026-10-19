// PPCS adapter for Drizzle ORM 1.0.0-rc.4 with node-postgres. Each case calls db.transaction() or
// tx.transaction() as that release ships them. Nothing here inspects COMMIT's command tag, discards a
// connection, or adds a rollback. drizzle() in this release takes { client }, not a positional Pool.
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { eq, sql } from 'drizzle-orm'
import { drizzle } from 'drizzle-orm/node-postgres'
import pg from 'pg'
import { ProtocolError, boundedUnit, main, managedOutcome, requestedLevel } from '../node-kit/adapter-main.mjs'
import { faultReport, instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { item, uniq } from './schema.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const DRIZZLE = packageDir(HERE, 'drizzle-orm')
const DRIZZLE_VERSION = packageVersion(HERE, 'drizzle-orm')
// drizzle-orm imports the peer `pg`. Pinning the same pg@8.23.1 makes that the module this file imports, so the
// trace sees Drizzle's statements. describe() records whether that holds.
const pgTrace = instrument(pg)
const samePg = realpathSync(createRequire(import.meta.url).resolve('pg')) === realpathSync(createRequire(`${DRIZZLE}/node-postgres/session.js`).resolve('pg'))

const MANAGED = {
  call: 'db.transaction(callback)',
  contract: `In Drizzle ORM ${DRIZZLE_VERSION}, db.transaction(callback) (NodePgSession.transaction in drizzle-orm/node-postgres/session.js) checks a client out of a pg.Pool when the client is a pool, executes BEGIN, runs the callback, executes COMMIT, and returns the callback's result. If the callback throws, it executes ROLLBACK and rethrows that error. The pg Result of COMMIT, including its command tag, is not read. A resolved call is Drizzle's report that the callback returned and COMMIT did not throw.`,
}
const NESTED_API = {
  call: 'db.transaction(callback) with a nested tx.transaction(callback)',
  contract: `In Drizzle ORM ${DRIZZLE_VERSION}, tx.transaction(callback) (NodePgTransaction.transaction in drizzle-orm/node-postgres/session.js) executes SAVEPOINT spN, RELEASE SAVEPOINT spN when the callback returns, and ROLLBACK TO SAVEPOINT spN when it throws. Drizzle's transaction documentation calls this nested form savepoints.`,
}
const LEVELS = new Set(['read uncommitted', 'read committed', 'repeatable read', 'serializable'])
const LEVEL_MANAGED = {
  call: 'db.transaction(callback, { isolationLevel })',
  contract: `In Drizzle ORM ${DRIZZLE_VERSION}, db.transaction(callback, config) appends PgTransactionConfig to BEGIN. isolationLevel is one of 'read uncommitted' | 'read committed' | 'repeatable read' | 'serializable' (pg-core/session.d.ts). getTransactionConfigSQL emits "isolation level " plus that value (pg-core/session.js). A resolved call is the same report as db.transaction(callback).`,
}
const TX05_MANAGED_FORM = 'db.transaction(callback, { isolationLevel }). The marker is inserted with tx.insert(item), then read back with tx.select().from(item).'

const drizzleLevel = (level) => {
  if (!LEVELS.has(level)) throw new ProtocolError(`the case requests an unknown isolation level: ${JSON.stringify(level)}`)
  return level
}

/** The PostgreSQL error under a DrizzleQueryError, when Drizzle wrapped one. */
const pgError = (e) => (e?.cause?.code ? e.cause : e)

/** pg_current_xact_id() and the backend PID, read through the transaction's own connection. */
async function identify(tx, isolation = false) {
  const query = isolation
    ? sql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation`
    : sql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`
  const { rows: [r] } = await tx.execute(query)
  return isolation
    ? { xid: r.xid, pid: r.pid, transaction_isolation: r.transaction_isolation }
    : { xid: r.xid, pid: r.pid }
}

const managed = ({ db }) => (callback) => db.transaction(callback)

const requestedLevelWork = async (tx, { markers, checkpoint }) => {
  await tx.insert(item).values({ name: markers.tx })
  await tx.select().from(item).where(eq(item.name, markers.tx))
  await checkpoint('after-read', await identify(tx, true))
}

// TX-02. The outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the outer scope
// handles the error and ends normally. When the fault fires, the driver reports `after-fault`.
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings }) => {
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.outer })
    id = await identify(tx)
    await checkpoint('outer-after-write', id)
    try {
      await tx.transaction(async (inner) => {
        await inner.insert(item).values({ name: markers.inner })
        await checkpoint('inner-after-write', { pid: id.pid })
        if (fault === 'conn-lost') await sleep(settings.settle_ms ?? 100)
        else armed = savepointRollbackFault(pgTrace, fault, () => checkpoint('after-fault', { pid: id.pid }))
        throw new Error('application error: the nested scope fails')
      })
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
      nested.error = { ...errInfo(pgError(e)), code: pgError(e)?.code ?? null }
    }
  }, MANAGED)
  pgTrace.clearFaults()
  await checkpoint('after-outer', { pid: id?.pid ?? null })
  return { ...outcome, steps: { nested, ...(armed ? { fault: faultReport(armed) } : {}) } }
}

// TX-03. Unit 1 fails and its ROLLBACK fails too; then the next unit of work runs on the same pool.
// The statement-error variant fails unit 1 with an uncaught unique violation, so the withheld ROLLBACK leaves an
// aborted transaction block rather than an open transaction.
const failedUnitThenNext = (failure) => async (ctx, { markers, checkpoint, settings }) => {
  let fault = null
  let id = null
  let violation = null
  const unit1 = await managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.doomed })
    id = await identify(tx)
    await checkpoint('unit1-after-write', id)
    if (failure === 'conn-lost') await sleep(settings.settle_ms ?? 100)
    else fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject', onFire: () => checkpoint('after-fault', { pid: id.pid }) })
    if (failure === 'statement-error') {
      try { await tx.insert(uniq).values({ code: 'taken' }) } catch (e) { violation = { ...errInfo(pgError(e)), code: pgError(e)?.code ?? null }; throw e }
    }
    throw new Error('application error: unit 1 fails')
  }, MANAGED)
  pgTrace.clearFaults()
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.next })
    await cp('unit2-after-write', await identify(tx))
  }, MANAGED))
  return { ...unit1, steps: { unit2, ...(violation ? { violation } : {}), ...(fault ? { fault: faultReport(fault) } : {}) } }
}

const nestedScope = (variant) => async (ctx, { markers, checkpoint }) => {
  const nested = { caught: false, completed: false }
  const outcome = await managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.outer })
    try {
      await tx.transaction(async (inner) => {
        await inner.insert(item).values({ name: markers.inner })
        await checkpoint('inner-after-write', await identify(inner))
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
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.tx })
    await checkpoint('before-end', await identify(tx))
  }, MANAGED),

  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.tx })
    await checkpoint('before-end', await identify(tx))
    throw new Error('application error: the request fails')
  }, MANAGED),

  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint }) => {
    const steps = {}
    const outcome = await managedOutcome(managed(ctx), async (tx) => {
      await tx.insert(item).values({ name: markers.tx })
      const id = await identify(tx)
      await checkpoint('after-write', id)
      try { await tx.insert(uniq).values({ code: 'taken' }) } catch (e) { steps.violation = { ...errInfo(pgError(e)), code: pgError(e)?.code ?? null } }
      await checkpoint('before-end', { pid: id.pid })
    }, MANAGED)
    return { ...outcome, steps }
  },

  'TX-01B.conn-lost-before-commit': (ctx, { markers, checkpoint, settings }) => managedOutcome(managed(ctx), async (tx) => {
    await tx.insert(item).values({ name: markers.tx })
    await checkpoint('before-end', await identify(tx))
    await sleep(settings.settle_ms ?? 100)
  }, MANAGED),

  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint }) => {
    let fault = null
    const outcome = await managedOutcome(managed(ctx), async (tx) => {
      await tx.insert(item).values({ name: markers.tx })
      await checkpoint('before-end', await identify(tx))
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

  'TX-05.managed-serializable': async ({ db }, tools) => ({
    ...await requestedLevel(
      (state) => managedOutcome((callback) => db.transaction(async (tx) => { state.started = true; return callback(tx) }, { isolationLevel: drizzleLevel(tools.settings.isolation_level) }), (tx) => requestedLevelWork(tx, tools), LEVEL_MANAGED),
      () => db.transaction(async (tx) => { await tools.checkpoint('baseline', await identify(tx)) }),
    ),
    form: TX05_MANAGED_FORM,
  }),
}

await main({
  describe: () => ({
    adapter: { name: 'drizzle-rc', version: JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version },
    framework: { name: 'drizzle-orm', version: DRIZZLE_VERSION },
    driver: { name: 'pg', version: packageVersion(HERE, 'pg') },
    components: { 'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool') },
  }),
  modes: { native: { configuration: { client: 'drizzle({ client: pg.Pool })', transaction: 'db.transaction(callback)' } } },
  open: async (message) => {
    const { host, port, user, password, database, application_name } = message.connection
    const pool = new pg.Pool({
      host, port, user, password, database, application_name,
      max: message.case.settings?.pool_max ?? 1,
    })
    // node-postgres emits 'error' on the pool when a client connection fails. Without a listener the process
    // dies on that event, before db.transaction() can reject. The listener does not roll back or discard.
    pool.on('error', () => {})
    const db = drizzle({ client: pool })
    return {
      context: { db, pool },
      close: () => pool.end(),
      diagnostics: () => ({ trace: pgTrace.trace(), commit_replies: pgTrace.commitReplies(), trace_sees_framework_pg: samePg }),
    }
  },
  cases,
})
