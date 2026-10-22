// PPCS control adapter: transactions written directly against node-postgres, in two deliberately different ways.
//
//                                    correct (positive control)            unsafe (negative control)
//   reply to COMMIT is ROLLBACK      reports a rollback                    reports committed
//   COMMIT raises (outcome unknown)  reports a failure, asserting nothing  reports a rollback
//   ROLLBACK TO SAVEPOINT fails      ends with ROLLBACK, not COMMIT        commits anyway
//   top-level ROLLBACK fails         discards the connection               returns it to the pool as it is
//   a write before a nested scope    sends it at once                      defers it, then sends it inside the nested
//                                                                          scope's savepoint, as a unit of work might
//   a requested isolation level      sends it with BEGIN                   sends a plain BEGIN, ignoring it
//
// A rollback the control reports without the body having thrown (from the reply to COMMIT, or after a failed savepoint
// rollback) is raised to the caller as a TransactionRolledBackError, as an API would raise it.
//
// The controls show that the runner passes a known-good implementation and detects a known-bad one. They are not a
// framework, and not a recommendation.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { ProtocolError, boundedUnit, main } from '../node-kit/adapter-main.mjs'
import { faultReport, instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { migrationCases } from './migration.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const pgTrace = instrument(pg)

async function identify(client) {
  const { rows: [r] } = await client.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: r.pid }
}

const CONTRACT = {
  correct: 'The correct control reports committed only when PostgreSQL answers COMMIT with the command tag COMMIT, reports any other tag as a rollback, and reports a COMMIT that raised as a failure. After a failed savepoint rollback, it ends the transaction with ROLLBACK instead of COMMIT. It starts a transaction at the isolation level requested of it.',
  unsafe: 'The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope\'s savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.',
}

const rolledBackError = (message) => ({ class: 'TransactionRolledBackError', code: null, message })

/**
 * BEGIN, the body, then COMMIT, reporting the outcome as the mode dictates. `state.rollbackOnly` is set by nestedScope().
 * `begin` is the statement that starts the transaction (TX-05 passes one with an isolation level).
 */
async function transaction(client, mode, body, state = {}, begin = 'BEGIN') {
  const contract = CONTRACT[mode]
  await client.query(begin)
  try {
    await body(client)
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    await client.query('ROLLBACK').catch(() => {})
    return { reported: 'rolled_back', basis: 'the body threw, and the control sent ROLLBACK', contract, api_error: errInfo(e) }
  }
  if (mode === 'correct' && state.rollbackOnly) {
    await client.query('ROLLBACK').catch(() => {})
    return { reported: 'rolled_back', basis: 'a savepoint rollback had failed, so the control ended the transaction with ROLLBACK instead of COMMIT', contract, api_error: rolledBackError('a savepoint rollback failed, so the transaction was rolled back') }
  }
  let reply
  try {
    reply = await client.query('COMMIT')
  } catch (e) {
    if (mode === 'unsafe') return { reported: 'rolled_back', basis: 'COMMIT raised an error, which the unsafe control reports as a rollback', contract, api_error: errInfo(e) }
    return { reported: 'failed', basis: 'COMMIT raised an error', contract, api_error: errInfo(e) }
  }
  if (mode === 'correct' && reply.command !== 'COMMIT') {
    return { reported: 'rolled_back', basis: `COMMIT was answered with the command tag ${reply.command}`, contract, api_error: rolledBackError(`COMMIT was answered with ${reply.command}: the transaction was rolled back`) }
  }
  return { reported: 'committed', basis: `COMMIT did not raise (command tag ${reply.command})`, contract }
}

/** A nested scope on the control's own savepoint. A failed ROLLBACK TO SAVEPOINT marks the transaction rollback-only. */
async function nestedScope(client, state, body) {
  await client.query('SAVEPOINT ppcs_nested')
  try {
    await body(client)
    await client.query('RELEASE SAVEPOINT ppcs_nested')
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    try { await client.query('ROLLBACK TO SAVEPOINT ppcs_nested') } catch (re) { state.rollbackOnly = errInfo(re) }
    throw e
  }
}

/**
 * A pool of one connection, for TX-03. After a unit's ROLLBACK fails, `correct` discards the connection (closing the
 * session makes PostgreSQL roll its transaction back) and opens a new one for the next unit; `unsafe` hands it out
 * again as it is.
 */
class OneConnectionPool {
  constructor(connection, mode) { this.connection = connection; this.mode = mode; this.client = null }
  async acquire() {
    if (!this.client) {
      const c = new pg.Client(this.connection)
      c.on('error', () => {})
      await c.connect()
      this.client = c
    }
    return this.client
  }
  /** Discarding waits until the connection has closed, so that the next unit never runs beside it. */
  async release(broken) {
    if (broken && this.mode === 'correct') { const c = this.client; this.client = null; await c.end().catch(() => {}) }
  }
  close() { return this.client?.end() }
}

const POOL_CONTRACT = {
  correct: 'The correct control discards a connection whose ROLLBACK failed, so its transaction can only end in a rollback, and reports a unit whose body threw as rolled back.',
  unsafe: 'The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.',
}

/** One unit of work on the pool: BEGIN, the body, COMMIT; on an error, ROLLBACK, and release as the mode dictates. */
async function pooledUnit(pool, mode, body) {
  const contract = POOL_CONTRACT[mode]
  let client
  try {
    client = await pool.acquire()
    await client.query('BEGIN')
  } catch (e) {
    if (client) await pool.release(true)
    return { reported: 'failed', basis: 'the unit could not start a transaction', contract, api_error: errInfo(e) }
  }
  let broken = false
  try {
    await body(client)
    await client.query('COMMIT')
    return { reported: 'committed', basis: 'COMMIT succeeded', contract }
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    try { await client.query('ROLLBACK') } catch { broken = true }
    return { reported: 'rolled_back', basis: broken ? `the body threw; ROLLBACK failed, and the connection was ${mode === 'correct' ? 'discarded' : 'kept'}` : 'the body threw; ROLLBACK succeeded', contract, api_error: errInfo(e) }
  } finally {
    await pool.release(broken)
  }
}

// TX-02: the outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the outer scope handles
// the error. When the fault fires, the driver reports `after-fault`.
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings, mode }) => {
  const state = {}
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await transaction(await ctx.client(), mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.outer])
    id = await identify(c)
    await checkpoint('outer-after-write', id)
    try {
      await nestedScope(c, state, async (n) => {
        await n.query('insert into item (name) values ($1)', [markers.inner])
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
  }, state)
  pgTrace.clearFaults()
  await checkpoint('after-outer', { pid: id?.pid ?? null })
  return { ...outcome, steps: { nested, ...(armed ? { fault: faultReport(armed) } : {}) } }
}

// TX-03: unit 1 fails and its ROLLBACK fails too; then the next unit of work runs on the same pool of one connection.
// The statement-error variant, new in PPCS 0.2 with no reused experiment, fails unit 1 with an uncaught unique
// violation instead, so the withheld ROLLBACK leaves an aborted transaction block rather than an open transaction.
const failedUnitThenNext = (failure) => async (ctx, { markers, checkpoint, settings, mode }) => {
  const pool = ctx.pool(mode)
  let fault = null
  let id = null
  let violation = null
  const unit1 = await pooledUnit(pool, mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.doomed])
    id = await identify(c)
    await checkpoint('unit1-after-write', id)
    if (failure === 'conn-lost') await sleep(settings.settle_ms ?? 100)
    else fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject', onFire: () => checkpoint('after-fault', { pid: id.pid }) })
    if (failure === 'statement-error') {
      // Not caught: the unique violation aborts the transaction, and the failing unit's ROLLBACK is then withheld.
      try { await c.query(`insert into uniq (code) values ('taken')`) } catch (e) { violation = errInfo(e); throw e }
    }
    throw new Error('application error: unit 1 fails')
  })
  pgTrace.clearFaults()
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => pooledUnit(pool, mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.next])
    await cp('unit2-after-write', await identify(c))
  }))
  return { ...unit1, steps: { unit2, ...(violation ? { violation } : {}), ...(fault ? { fault: faultReport(fault) } : {}) } }
}

// TX-04.1 and TX-04.2 on the control's own savepoints. No fault is injected. `correct` sends the outer write at once;
// `unsafe` defers it and sends it inside the nested scope's savepoint, so a failing nested scope rolls it back too (the
// lost write TX-04.1 targets).
const nestedOnly = (variant) => async (ctx, { markers, checkpoint, mode }) => {
  const nested = { caught: false, completed: false }
  const deferred = []
  const outcome = await transaction(await ctx.client(), mode, async (c) => {
    if (mode === 'unsafe') deferred.push(markers.outer)
    else await c.query('insert into item (name) values ($1)', [markers.outer])
    try {
      await nestedScope(c, {}, async (n) => {
        for (const name of deferred.splice(0)) await n.query('insert into item (name) values ($1)', [name])
        await n.query('insert into item (name) values ($1)', [markers.inner])
        await checkpoint('inner-after-write', await identify(n))
        if (variant === 'nested-fails') throw new Error('application error: the nested scope fails')
      })
      nested.completed = true
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
    }
    if (variant === 'outer-fails') throw new Error('application error: the outer scope fails')
  })
  return { ...outcome, steps: { nested } }
}

// TX-05: the requested isolation level. `correct` sends it with BEGIN; `unsafe` sends a plain BEGIN, the shape of an API
// that drops the request. Both report PostgreSQL's own current_setting('transaction_isolation') honestly, read in the
// statement that captures the ID. The control has no API forms, so both TX-05 cases run this same transaction.
const LEVELS = ['read uncommitted', 'read committed', 'repeatable read', 'serializable']
const requestedLevel = async (ctx, { markers, checkpoint, settings, mode }) => {
  const level = settings.isolation_level
  if (!LEVELS.includes(level)) throw new ProtocolError(`the case requests an unknown isolation level: ${JSON.stringify(level)}`)
  const begin = mode === 'correct' ? `BEGIN ISOLATION LEVEL ${level.toUpperCase()}` : 'BEGIN'
  const outcome = await transaction(await ctx.client(), mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.tx])
    await c.query('select name from item where name = $1', [markers.tx])
    const { rows: [r] } = await c.query("select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation")
    await checkpoint('after-read', r)
  }, {}, begin)
  return { ...outcome, steps: { begin } }
}

const cases = {
  'CTL-01.commit': async (ctx, { markers, checkpoint, mode }) => transaction(await ctx.client(), mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c))
  }),

  'TX-01B.commit-reply-unseen': async (ctx, tools) => cases['CTL-01.commit'](ctx, tools),

  'CTL-01.rollback': async (ctx, { markers, checkpoint, mode }) => transaction(await ctx.client(), mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c))
    throw new Error('application error: the request fails')
  }),

  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint, mode }) => {
    const steps = {}
    const outcome = await transaction(await ctx.client(), mode, async (c) => {
      await c.query('insert into item (name) values ($1)', [markers.tx])
      const id = await identify(c)
      await checkpoint('after-write', id)
      try { await c.query(`insert into uniq (code) values ('taken')`) } catch (e) { steps.violation = errInfo(e) }
      await checkpoint('before-end', { pid: id.pid })
    })
    return { ...outcome, steps }
  },

  'TX-01B.conn-lost-before-commit': async (ctx, { markers, checkpoint, mode, settings }) => transaction(await ctx.client(), mode, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c))
    await sleep(settings.settle_ms ?? 100)
  }),

  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint, mode }) => {
    let fault = null
    const outcome = await transaction(await ctx.client(), mode, async (c) => {
      await c.query('insert into item (name) values ($1)', [markers.tx])
      await checkpoint('before-end', await identify(c))
      fault = pgTrace.addFault({ match: /^commit;?$/i, mode: 'reply-lost' })
    })
    return { ...outcome, steps: { fault: { mode: 'reply-lost', fired: fault?.fired ?? 0 } } }
  },

  'TX-02.savepoint-rollback-not-sent': nestedFailure('not-sent'),
  'TX-02.savepoint-rollback-rejected': nestedFailure('rejected'),
  'TX-02.conn-lost-before-savepoint-rollback': nestedFailure('conn-lost'),

  'TX-03.rollback-not-sent': failedUnitThenNext('rollback-not-sent'),
  'TX-03.statement-error-rollback-not-sent': failedUnitThenNext('statement-error'),
  'TX-03.conn-lost-in-transaction': failedUnitThenNext('conn-lost'),

  'TX-04.nested-failure-contained': nestedOnly('nested-fails'),
  'TX-04.nested-released-outer-rollback': nestedOnly('outer-fails'),

  'TX-05.managed-serializable': requestedLevel,
  'TX-05.explicit-serializable': requestedLevel,

  ...migrationCases,
}

const version = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version

await main({
  describe: () => ({
    adapter: { name: 'pg-control', version },
    framework: { name: 'pg-control', version },
    driver: { name: 'pg', version: packageVersion(HERE, 'pg') },
    components: { 'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool') },
  }),
  modes: {
    correct: { configuration: { commit_reply: 'checked', commit_error: 'reported as a failure', failed_savepoint_rollback: 'transaction ended with ROLLBACK', failed_rollback: 'connection discarded', write_before_nested_scope: 'sent at once', isolation_level: 'sent with BEGIN' } },
    unsafe: { configuration: { commit_reply: 'ignored', commit_error: 'reported as a rollback', failed_savepoint_rollback: 'ignored', failed_rollback: 'connection returned to the pool', write_before_nested_scope: 'deferred into the nested scope\'s savepoint', isolation_level: 'ignored: plain BEGIN' } },
  },
  open: (message) => {
    let client = null
    let pool = null
    const context = {
      connection: message.connection,
      // A terminated connection is reported through the failing query, not as a crash.
      client: async () => { if (!client) { client = new pg.Client(message.connection); client.on('error', () => {}); await client.connect() } return client },
      pool: (mode) => (pool ??= new OneConnectionPool(message.connection, mode)),
    }
    return {
      context,
      close: async () => { await client?.end(); await pool?.close() },
      diagnostics: () => ({ trace: pgTrace.trace(), commit_replies: pgTrace.commitReplies() }),
    }
  },
  cases,
})
