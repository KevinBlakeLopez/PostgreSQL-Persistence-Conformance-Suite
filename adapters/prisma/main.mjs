// PPCS adapter for Prisma ORM. Each case calls prisma.$transaction() as Prisma Client 7.10.1 ships it.
// Nothing here reads COMMIT's command tag, discards a connection, or adds a rollback.
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { PrismaPg } from '@prisma/adapter-pg'
import pg from 'pg'
import { ProtocolError, boundedUnit, main, managedOutcome, requestedLevel } from '../node-kit/adapter-main.mjs'
import { faultReport, instrument, savepointRollbackFault } from '../node-kit/pg-instrument.mjs'
import { errInfo, packageDir, packageVersion, sleep } from '../node-kit/util.mjs'
import { Prisma, PrismaClient } from './generated/prisma/client.ts'
import { runPrismaMigration } from './migration.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const require = createRequire(import.meta.url)
const CLIENT_VERSION = packageVersion(HERE, '@prisma/client')
const ADAPTER_VERSION = packageVersion(HERE, '@prisma/adapter-pg')
const PG_VERSION = packageVersion(HERE, 'pg')
const CLI_VERSION = packageVersion(HERE, 'prisma')
// @prisma/adapter-pg requires('pg'). Instrument that module so the trace sees Prisma's statements.
const adapterPgEntry = createRequire(require.resolve('@prisma/adapter-pg')).resolve('pg')
const ourPgEntry = require.resolve('pg')
const samePg = realpathSync(adapterPgEntry) === realpathSync(ourPgEntry)
const pgTrace = instrument(pg)

const MANAGED = {
  call: 'prisma.$transaction(async (tx) => ...)',
  contract: `In Prisma Client ${CLIENT_VERSION}, prisma.$transaction(async (tx) => ...) (_transactionWithCallback in @prisma/client/runtime/client.mjs) starts an interactive transaction, runs the callback, and on return calls the engine commit. The transaction manager sends the SQL COMMIT through the driver adapter's executeRaw and, if that promise resolves, calls transaction.commit(), which in @prisma/adapter-pg ${ADAPTER_VERSION} is client.release() with no error. PgQueryable.executeRaw returns rowCount and does not read the pg Result command tag. A resolved call is Prisma's report that the callback returned and COMMIT did not throw. If the callback throws, Prisma sends ROLLBACK, releases the connection, and rethrows that error. The default interactive-transaction timeout is 5000 ms and maxWait is 2000 ms. This adapter does not change them.`,
}
const NESTED_API = {
  call: 'prisma.$transaction(callback) with a nested tx.$transaction(callback)',
  contract: `In Prisma Client ${CLIENT_VERSION}, a nested tx.$transaction(callback) reuses the open transaction and calls the driver adapter's createSavepoint. @prisma/adapter-pg ${ADAPTER_VERSION} sends SAVEPOINT prisma_sp_N, RELEASE SAVEPOINT prisma_sp_N when the nested callback returns, and ROLLBACK TO SAVEPOINT prisma_sp_N followed by RELEASE SAVEPOINT prisma_sp_N when it throws. Prisma ORM 7.5.0 added this nested-transaction rollback and described it as savepoints.`,
}
const LEVELS = {
  'read uncommitted': 'ReadUncommitted',
  'read committed': 'ReadCommitted',
  'repeatable read': 'RepeatableRead',
  serializable: 'Serializable',
}
const LEVEL_MANAGED = {
  call: 'prisma.$transaction(callback, { isolationLevel })',
  contract: `In Prisma Client ${CLIENT_VERSION}, prisma.$transaction(callback, { isolationLevel }) passes isolationLevel to the driver adapter. The documented values are Prisma.TransactionIsolationLevel.ReadUncommitted, ReadCommitted, RepeatableRead, and Serializable. @prisma/adapter-pg ${ADAPTER_VERSION} sends BEGIN and then SET TRANSACTION ISOLATION LEVEL with that value. A resolved call is the same report as prisma.$transaction(callback).`,
}
const TX05_MANAGED_FORM = 'prisma.$transaction(callback, { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }). The marker is inserted with tx.$executeRaw, then read back with tx.$queryRaw.'

const prismaLevel = (level) => {
  const mapped = LEVELS[level]
  if (!mapped || Prisma.TransactionIsolationLevel[mapped] !== mapped) throw new ProtocolError(`the case requests an isolation level Prisma's TransactionIsolationLevel does not name: ${JSON.stringify(level)}`)
  return Prisma.TransactionIsolationLevel[mapped]
}

// Prisma Client codes are P followed by four digits (P2010). A PostgreSQL SQLSTATE is five characters and is not that shape.
const isSqlState = (value) => typeof value === 'string' && /^[0-9A-Z]{5}$/.test(value) && !/^P[0-9]{4}$/.test(value)

/** The PostgreSQL SQLSTATE on a Prisma error. Raw queries put it in the message and on driverAdapterError.cause.originalCode. */
const sqlState = (e) => {
  const seen = new Set()
  const stack = [e]
  while (stack.length) {
    const cur = stack.pop()
    if (!cur || typeof cur !== 'object' || seen.has(cur)) continue
    seen.add(cur)
    if (isSqlState(cur.originalCode)) return cur.originalCode
    if (isSqlState(cur.code)) return cur.code
    if (cur.meta) stack.push(cur.meta)
    if (cur.cause) stack.push(cur.cause)
    if (cur.driverAdapterError) stack.push(cur.driverAdapterError)
  }
  const fromMessage = String(e?.message ?? '').match(/Code: `([0-9A-Z]{5})`/)
  return fromMessage && isSqlState(fromMessage[1]) ? fromMessage[1] : null
}

const caught = (e) => {
  const lines = String(e?.message ?? '').split('\n').map((line) => line.trim()).filter(Boolean)
  const message = (lines.find((line) => line.includes('Code:')) ?? lines[0] ?? '').slice(0, 300)
  return { ...errInfo(e), message, code: sqlState(e), prisma_code: e?.code ?? null }
}

/** pg_current_xact_id() and the backend PID, read through the transaction's own connection. */
async function identify(tx, isolation = false) {
  const rows = isolation
    ? await tx.$queryRaw`select pg_current_xact_id()::text as xid, pg_backend_pid()::int as pid, current_setting('transaction_isolation') as transaction_isolation`
    : await tx.$queryRaw`select pg_current_xact_id()::text as xid, pg_backend_pid()::int as pid`
  const r = Array.isArray(rows) ? rows[0] : null
  if (!r?.xid) throw new ProtocolError('pg_current_xact_id() returned no row')
  return isolation
    ? { xid: String(r.xid), pid: Number(r.pid), transaction_isolation: String(r.transaction_isolation) }
    : { xid: String(r.xid), pid: Number(r.pid) }
}

const managed = ({ prisma }) => (callback) => prisma.$transaction(callback)

const requestedLevelWork = async (tx, { markers, checkpoint }) => {
  await tx.$executeRaw`insert into item (name) values (${markers.tx})`
  await tx.$queryRaw`select name from item where name = ${markers.tx}`
  await checkpoint('after-read', await identify(tx, true))
}

// TX-02. The outer scope writes; a nested scope writes and fails; its savepoint rollback fails; the outer scope
// handles the error and ends normally. When the fault fires, the driver reports `after-fault`.
const nestedFailure = (fault) => async (ctx, { markers, checkpoint, settings }) => {
  let armed = null
  let id = null
  const nested = { caught: false }
  const outcome = await managedOutcome(managed(ctx), async (tx) => {
    await tx.$executeRaw`insert into item (name) values (${markers.outer})`
    id = await identify(tx)
    await checkpoint('outer-after-write', id)
    try {
      await tx.$transaction(async (inner) => {
        await inner.$executeRaw`insert into item (name) values (${markers.inner})`
        await checkpoint('inner-after-write', { pid: id.pid })
        if (fault === 'conn-lost') await sleep(settings.settle_ms ?? 100)
        else armed = savepointRollbackFault(pgTrace, fault, () => checkpoint('after-fault', { pid: id.pid }))
        throw new Error('application error: the nested scope fails')
      })
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      nested.caught = true
      nested.error = caught(e)
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
    await tx.$executeRaw`insert into item (name) values (${markers.doomed})`
    id = await identify(tx)
    await checkpoint('unit1-after-write', id)
    if (failure === 'conn-lost') await sleep(settings.settle_ms ?? 100)
    else fault = pgTrace.addFault({ match: /^rollback;?$/i, mode: 'client-reject', onFire: () => checkpoint('after-fault', { pid: id.pid }) })
    if (failure === 'statement-error') {
      try { await tx.$executeRaw`insert into uniq (code) values ('taken')` } catch (e) { violation = caught(e); throw e }
    }
    throw new Error('application error: unit 1 fails')
  }, MANAGED)
  pgTrace.clearFaults()
  await checkpoint('after-unit1', { pid: id?.pid ?? null })
  const unit2 = await boundedUnit(settings.bound_ms ?? 5000, checkpoint, (cp) => managedOutcome(managed(ctx), async (tx) => {
    await tx.$executeRaw`insert into item (name) values (${markers.next})`
    await cp('unit2-after-write', await identify(tx))
  }, MANAGED))
  return { ...unit1, steps: { unit2, ...(violation ? { violation } : {}), ...(fault ? { fault: faultReport(fault) } : {}) } }
}

const nestedScope = (variant) => async (ctx, { markers, checkpoint }) => {
  const nested = { caught: false, completed: false }
  const outcome = await managedOutcome(managed(ctx), async (tx) => {
    await tx.$executeRaw`insert into item (name) values (${markers.outer})`
    try {
      await tx.$transaction(async (inner) => {
        await inner.$executeRaw`insert into item (name) values (${markers.inner})`
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
    await tx.$executeRaw`insert into item (name) values (${markers.tx})`
    await checkpoint('before-end', await identify(tx))
  }, MANAGED),

  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome(managed(ctx), async (tx) => {
    await tx.$executeRaw`insert into item (name) values (${markers.tx})`
    await checkpoint('before-end', await identify(tx))
    throw new Error('application error: the request fails')
  }, MANAGED),

  'TX-01A.caught-error-then-commit': async (ctx, { markers, checkpoint }) => {
    const steps = {}
    const outcome = await managedOutcome(managed(ctx), async (tx) => {
      await tx.$executeRaw`insert into item (name) values (${markers.tx})`
      const id = await identify(tx)
      await checkpoint('after-write', id)
      try { await tx.$executeRaw`insert into uniq (code) values ('taken')` } catch (e) { steps.violation = caught(e) }
      await checkpoint('before-end', { pid: id.pid })
    }, MANAGED)
    return { ...outcome, steps }
  },

  'TX-01B.conn-lost-before-commit': (ctx, { markers, checkpoint, settings }) => managedOutcome(managed(ctx), async (tx) => {
    await tx.$executeRaw`insert into item (name) values (${markers.tx})`
    await checkpoint('before-end', await identify(tx))
    await sleep(settings.settle_ms ?? 100)
  }, MANAGED),

  'TX-01B.commit-reply-discarded': async (ctx, { markers, checkpoint }) => {
    let fault = null
    const outcome = await managedOutcome(managed(ctx), async (tx) => {
      await tx.$executeRaw`insert into item (name) values (${markers.tx})`
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

  'TX-05.managed-serializable': async ({ prisma }, tools) => ({
    ...await requestedLevel(
      (state) => managedOutcome((callback) => prisma.$transaction(async (tx) => { state.started = true; return callback(tx) }, { isolationLevel: prismaLevel(tools.settings.isolation_level) }), (tx) => requestedLevelWork(tx, tools), LEVEL_MANAGED),
      () => prisma.$transaction(async (tx) => { await tools.checkpoint('baseline', await identify(tx)) }),
    ),
    form: TX05_MANAGED_FORM,
  }),

  ...Object.fromEntries(['MG-02.held', 'MG-02.first-deployment', 'MG-02.session-loss', 'MG-02.idle-session-timeout'].map((id) => [id, (ctx, tools) => runPrismaMigration(ctx.connection, tools)])),
}

await main({
  describe: () => ({
    adapter: { name: 'prisma', version: JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version },
    framework: { name: '@prisma/client', version: CLIENT_VERSION },
    driver: { name: 'pg', version: PG_VERSION },
    components: {
      '@prisma/adapter-pg': ADAPTER_VERSION,
      prisma: CLI_VERSION,
      'pg-pool': packageVersion(packageDir(HERE, 'pg'), 'pg-pool'),
    },
  }),
  modes: {
    native: {
      configuration: {
        client: 'PrismaClient',
        adapter: 'PrismaPg(pg.Pool)',
        transaction: 'prisma.$transaction(async (tx) => ...)',
        query_compiler: 'client',
        compilerBuild: 'fast',
        engine: 'no Rust query engine',
        pool: 'pg.Pool, max = case pool_max, external pool not disposed by the adapter',
        interactive_transaction_timeout_ms: 5000,
        interactive_transaction_max_wait_ms: 2000,
      },
    },
  },
  open: async (message) => {
    const { host, port, user, password, database, application_name } = message.connection
    const pool = new pg.Pool({
      host, port, user, password, database, application_name,
      max: message.case.settings?.pool_max ?? 1,
    })
    // PrismaPg.connect() also listens for idle-client errors. This listener covers the interval before connect().
    // It does not roll back or discard. Checked-out clients get a separate listener inside the driver adapter.
    pool.on('error', () => {})
    const adapter = new PrismaPg(pool)
    const prisma = new PrismaClient({ adapter })
    return {
      context: { prisma, pool, connection: message.connection },
      close: async () => {
        await prisma.$disconnect()
        await pool.end()
      },
      diagnostics: () => ({
        trace: pgTrace.trace(),
        commit_replies: pgTrace.commitReplies(),
        trace_sees_framework_pg: samePg,
        external_pool: adapter.externalPool === pool,
      }),
    }
  },
  cases,
})
