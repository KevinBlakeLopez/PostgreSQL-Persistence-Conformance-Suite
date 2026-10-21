// Kysely's transaction API, using the kysely 0.29.6 already installed for MikroORM. Client.query is not patched.
import { createRequire } from 'node:module'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { ProtocolError, main, managedOutcome } from '../../../../adapters/node-kit/adapter-main.mjs'
import { prCaseHandlers, violationInfo } from '../../js/variants.mjs'

const pg = createRequire(new URL('../../../../package.json', import.meta.url))('pg')
const pnpmRoot = fileURLToPath(new URL('../../../../adapters/mikroorm/node_modules/.pnpm/', import.meta.url))
const kyselyDir = readdirSync(pnpmRoot).find((name) => name.startsWith('kysely@'))
const kyselyPkg = join(pnpmRoot, kyselyDir, 'node_modules/kysely')
const { Kysely, PostgresDialect, sql } = await import(pathToFileURL(join(kyselyPkg, 'dist/index.js')).href)
const KYSELY_VERSION = JSON.parse(readFileSync(join(kyselyPkg, 'package.json'), 'utf8')).version
const PG_VERSION = JSON.parse(readFileSync(createRequire(new URL('../../../../package.json', import.meta.url)).resolve('pg/package.json'), 'utf8')).version

const MANAGED_CONTRACT = `Kysely ${KYSELY_VERSION} db.transaction().execute(callback) (TransactionBuilder.execute) calls driver.beginTransaction, awaits the callback, then driver.commitTransaction. PostgresDriver.commitTransaction executes the SQL 'commit' and does not read a command tag. If that call resolves, execute sets its internal isCommitted flag and resolves with the callback's result. If the callback throws, it calls rollbackTransaction and rethrows.`
const EXPLICIT_CONTRACT = `Kysely ${KYSELY_VERSION} db.startTransaction().execute() returns a ControlledTransaction. trx.commit().execute() calls the same commitTransaction and then sets the public isCommitted flag. trx.rollback().execute() rolls back. The callback form of transaction() throws if called on an existing Transaction; savepoints are ControlledTransaction.savepoint().`

async function identify(handle) {
  const result = await sql`select pg_current_xact_id()::text as xid, pg_backend_pid() as pid`.execute(handle)
  const r = result.rows[0]
  return { xid: r.xid, pid: Number(r.pid) }
}

const write = (handle, name) => handle.insertInto('item').values({ name, qty: 0 }).execute()

function apiFor(ctx) {
  const { db, state } = ctx
  return {
    savepointOn: 'explicit',
    forms: {
      managed: 'db.transaction().execute(callback). The callback catches 23505 and returns.',
      explicit: 'const trx = await db.startTransaction().execute(); catch 23505; await trx.commit().execute().',
      control: 'db.transaction().execute(callback). The unique violation leaves the callback.',
      savepoint: 'db.startTransaction().execute(), trx.savepoint(\'ppcs_sp\').execute(), catch 23505, rollbackToSavepoint, then trx.commit().execute(). The managed Transaction class has no savepoint method.',
    },
    contracts: { managed: MANAGED_CONTRACT, explicit: EXPLICIT_CONTRACT, control: MANAGED_CONTRACT, savepoint: EXPLICIT_CONTRACT },
    unsupported: {},
    managed: (body) => managedOutcome((callback) => db.transaction().execute(callback), body, { call: 'db.transaction().execute(callback)', contract: MANAGED_CONTRACT }),
    explicit: {
      names: { start: 'db.startTransaction().execute()', commit: 'trx.commit().execute()', rollback: 'trx.rollback().execute()' },
      contract: EXPLICIT_CONTRACT,
      start: () => db.startTransaction().execute(),
      commit: async (trx) => {
        await trx.commit().execute()
        state.isCommitted = trx.isCommitted
      },
      rollback: (trx) => trx.rollback().execute(),
    },
    async savepoint(trx) {
      const sp = await trx.savepoint('ppcs_sp').execute()
      try {
        await sp.insertInto('uniq').values({ code: 'taken' }).execute()
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        await sp.rollbackToSavepoint('ppcs_sp').execute()
        return { recovered: true, violation: violationInfo(e) }
      }
      throw new ProtocolError('the duplicate insert did not raise')
    },
    write,
    insertTaken: (handle) => handle.insertInto('uniq').values({ code: 'taken' }).execute(),
    identify,
    async probe() {
      try {
        await sql`select 1 as ok`.execute(db)
        return { supported: true, ok: true, error: null }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { supported: true, ok: false, error: violationInfo(e) }
      }
    },
    async reuse(name, checkpoint) {
      const started = Date.now()
      let pid = null
      try {
        const outcome = await managedOutcome((callback) => db.transaction().execute(callback), async (trx) => {
          await write(trx, name)
          const id = await identify(trx)
          pid = id.pid
          await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
        }, { call: 'db.transaction().execute(callback)', contract: MANAGED_CONTRACT })
        return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid }
      }
    },
    hooks: () => ({ supported: false, reason: 'Kysely exposes ControlledTransaction.isCommitted after commit().execute(). It has no commit or rollback callback.' }),
    commandTag: () => null,
    extras: () => ({ isCommitted: state.isCommitted }),
  }
}

const cases = {
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome((callback) => ctx.db.transaction().execute(callback), async (trx) => {
    await write(trx, markers.tx)
    const id = await identify(trx)
    await checkpoint('before-end', { xid: String(id.xid), pid: id.pid })
  }, { call: 'db.transaction().execute(callback)', contract: MANAGED_CONTRACT }),
  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome((callback) => ctx.db.transaction().execute(callback), async (trx) => {
    await write(trx, markers.tx)
    const id = await identify(trx)
    await checkpoint('before-end', { xid: String(id.xid), pid: id.pid })
    throw new Error('application error: the request fails')
  }, { call: 'db.transaction().execute(callback)', contract: MANAGED_CONTRACT }),
  ...prCaseHandlers(apiFor),
}

await main({
  describe: () => ({
    adapter: { name: 'kysely', version: '0.1.0' },
    framework: { name: 'kysely', version: KYSELY_VERSION },
    driver: { name: 'pg', version: PG_VERSION },
    components: { kysely: KYSELY_VERSION },
  }),
  modes: { native: { configuration: { transaction: 'db.transaction().execute(callback)', explicit: 'db.startTransaction().execute()' } } },
  open: async (message) => {
    const { host, port, user, password, database, application_name } = message.connection
    const pool = new pg.Pool({ host, port, user, password, database, application_name, max: message.case.settings?.pool_max ?? 2 })
    const db = new Kysely({ dialect: new PostgresDialect({ pool }) })
    return {
      context: { db, state: { isCommitted: null } },
      close: async () => { await db.destroy() },
    }
  },
  cases,
})
