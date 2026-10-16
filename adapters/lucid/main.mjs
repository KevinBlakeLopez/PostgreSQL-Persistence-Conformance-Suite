// PPCS adapter for Lucid (@adonisjs/lucid), used standalone. Each case is the Lucid-native form of a catalog case
// (specifications/transactions.v1.json), adapted from the reused experiments (docs/provenance.md).
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { ProtocolError, boundedUnit, main, managedOutcome } from '../node-kit/adapter-main.mjs'
import { instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { Item, Uniq, openDatabase } from './lucid.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const LUCID = packageDir(HERE, '@adonisjs/lucid')
const KNEX = packageDir(LUCID, 'knex')
// knex loads `pg` with require(). The trace sees knex's statements only if both resolve to the same pg module, which
// pnpm's single pg@8.23.1 directory provides. describe() records whether that holds.
const pgTrace = instrument(pg)
const samePg = realpathSync(createRequire(import.meta.url).resolve('pg')) === realpathSync(createRequire(`${KNEX}/`).resolve('pg'))

const MANAGED = {
  call: 'db.transaction(callback)',
  contract: 'In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback\'s value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid\'s report that the transaction committed.',
}
const NESTED_API = {
  call: 'db.transaction(callback) with a nested trx.transaction(callback)',
  contract: 'In @adonisjs/lucid 22.4.2, transaction() on a transaction client "Returns another instance of transaction with save point" (src/transaction_client/index.js), which knex implements with SAVEPOINT; its managed form commits (releases) when the callback returns and rolls back when it throws.',
}

/** pg_current_xact_id() and the backend PID, read through the transaction's own client (PostgreSQL 13 or later). */
async function identify(trx) {
  const { rows: [r] } = await trx.rawQuery('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: r.pid }
}

const managed = ({ db }) => (callback) => db.transaction(callback)

// TX-02. Experiments LR1a (the savepoint rollback fails on the client), LT5b (PostgreSQL rejects it) and LR1b (the
// backend is terminated). The outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the
// outer scope handles the error and ends normally.
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings }) => {
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    await Item.create({ name: markers.outer }, { client: t })
    id = await identify(t)
    await checkpoint('outer-after-write', id)
    try {
      await t.transaction(async (n) => {
        await Item.create({ name: markers.inner }, { client: n })
        if (fault === 'conn-lost') { await checkpoint('inner-after-write', { pid: id.pid }); await sleep(settings.settle_ms ?? 100) }
        else armed = savepointRollbackFault(pgTrace, fault)
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
  return { ...outcome, steps: { nested, ...(armed ? { fault: { mode: armed.mode, fired: armed.fired ?? 0 } } : {}) } }
}

// TX-03. Experiments LT5c (the ROLLBACK fails on the client) and LR1c (the backend is terminated before it). Unit 1
// fails and its ROLLBACK fails too; then the next unit of work runs on the same pool of one connection.
const failedUnitThenNext = (failure) => async (ctx, { markers, checkpoint, settings }) => {
  let fault = null
  let id = null
  const unit1 = await managedOutcome(managed(ctx), async (t) => {
    await Item.create({ name: markers.doomed }, { client: t })
    id = await identify(t)
    await checkpoint('unit1-after-write', id)
    if (failure === 'rollback-not-sent') fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject' })
    else await sleep(settings.settle_ms ?? 100)
    throw new Error('application error: unit 1 fails')
  }, MANAGED)
  pgTrace.clearFaults() // an unfired fault must not reach unit 2
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => managedOutcome(managed(ctx), async (t) => {
    await Item.create({ name: markers.next }, { client: t })
    await cp('unit2-after-write', await identify(t))
  }, MANAGED))
  return { ...unit1, steps: { unit2, ...(fault ? { fault: { mode: 'client-reject', fired: fault.fired ?? 0 } } : {}) } }
}

// TX-04. Experiment LT2b (a failing nested transaction), and a nested transaction released before the outer one fails.
const nestedScope = (variant) => async (ctx, { markers, checkpoint }) => {
  const nested = { caught: false, completed: false }
  const outcome = await managedOutcome(managed(ctx), async (t) => {
    await Item.create({ name: markers.outer }, { client: t })
    try {
      await t.transaction(async (n) => {
        await Item.create({ name: markers.inner }, { client: n })
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
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (trx) => {
    await Item.create({ name: markers.tx }, { client: trx })
    await checkpoint('before-end', await identify(trx))
  }, MANAGED),

  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (trx) => {
    await Item.create({ name: markers.tx }, { client: trx })
    await checkpoint('before-end', await identify(trx))
    throw new Error('application error: the request fails')
  }, MANAGED),

  // Experiment LT1a: a caught unique violation, then the callback returns. LT1c's probe is the pre-commit-probe mode.
  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint, mode }) => {
    const steps = {}
    const outcome = await managedOutcome(managed(ctx), async (trx) => {
      await Item.create({ name: markers.tx }, { client: trx })
      const id = await identify(trx)
      await checkpoint('after-write', id)
      try { await Uniq.create({ code: 'taken' }, { client: trx }) } catch (e) { steps.violation = errInfo(e) }
      await checkpoint('before-end', { pid: id.pid })
      if (mode === 'pre-commit-probe') await trx.rawQuery('select 1') // fails with 25P02 when the transaction is aborted
    }, MANAGED)
    return { ...outcome, steps }
  },

  // Experiment LR1d: the backend is terminated after the last write (by the runner, at the checkpoint).
  'TX-01B.conn-lost-before-commit': (ctx, { markers, checkpoint, settings }) => managedOutcome(managed(ctx), async (trx) => {
    await Item.create({ name: markers.tx }, { client: trx })
    await checkpoint('before-end', await identify(trx))
    await sleep(settings.settle_ms ?? 100)
  }, MANAGED),

  // The reused experiments' reply-lost fault (LH1e): a client-side simulation, category D.
  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint }) => {
    let fault = null
    const outcome = await managedOutcome(managed(ctx), async (trx) => {
      await Item.create({ name: markers.tx }, { client: trx })
      await checkpoint('before-end', await identify(trx))
      fault = pgTrace.addFault({ match: /^commit;?$/i, mode: 'reply-lost' })
    }, MANAGED)
    return { ...outcome, steps: { fault: { mode: 'reply-lost', fired: fault?.fired ?? 0 } } }
  },

  'TX-02.savepoint-rollback-not-sent': nestedFailure('not-sent'),
  'TX-02.savepoint-rollback-rejected': nestedFailure('rejected'),
  'TX-02.conn-lost-before-savepoint-rollback': nestedFailure('conn-lost'),

  'TX-03.rollback-not-sent': failedUnitThenNext('rollback-not-sent'),
  'TX-03.conn-lost-in-transaction': failedUnitThenNext('conn-lost'),

  'TX-04.nested-failure-contained': nestedScope('nested-fails'),
  'TX-04.nested-released-outer-rollback': nestedScope('outer-fails'),
}

await main({
  describe: () => ({
    adapter: { name: 'lucid', version: JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version },
    framework: { name: '@adonisjs/lucid', version: packageVersion(HERE, '@adonisjs/lucid') },
    driver: { name: 'pg', version: packageVersion(HERE, 'pg') },
    components: {
      knex: packageVersion(LUCID, 'knex'),
      tarn: packageVersion(KNEX, 'tarn'),
      'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool'),
      '@adonisjs/core': packageVersion(HERE, '@adonisjs/core'),
      luxon: packageVersion(HERE, 'luxon'),
    },
  }),
  modes: {
    native: { configuration: {} },
    'pre-commit-probe': { configuration: { pre_commit_probe: 'the callback runs `select 1` as its last statement, so an aborted transaction makes it throw (25P02) instead of returning' } },
  },
  open: (message) => {
    const logLines = []
    const db = openDatabase(message.connection, { poolMax: message.case.settings?.pool_max ?? 1, logLines })
    return {
      context: { db },
      close: () => db.manager.closeAll(),
      diagnostics: () => ({ trace: pgTrace.trace(), commit_replies: pgTrace.commitReplies(), trace_sees_framework_pg: samePg, logs: logLines.filter((l) => l.level !== 'info') }),
    }
  },
  cases,
})
