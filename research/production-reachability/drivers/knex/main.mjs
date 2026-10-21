// Knex's transaction API, using the knex 3.3.0 already installed for Lucid. Client.query is not patched.
import { createRequire } from 'node:module'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { ProtocolError, main, managedOutcome } from '../../../../adapters/node-kit/adapter-main.mjs'
import { prCaseHandlers, violationInfo } from '../../js/variants.mjs'

const pnpmRoot = fileURLToPath(new URL('../../../../adapters/lucid/node_modules/.pnpm/', import.meta.url))
const knexDir = readdirSync(pnpmRoot).find((name) => name.startsWith('knex@'))
const knexPkg = join(pnpmRoot, knexDir, 'node_modules/knex')
const knexFactory = createRequire(join(knexPkg, 'package.json'))(join(knexPkg, 'knex.js'))
const KNEX_VERSION = JSON.parse(readFileSync(join(knexPkg, 'package.json'), 'utf8')).version
const PG_VERSION = JSON.parse(readFileSync(join(pnpmRoot, knexDir, 'node_modules/pg/package.json'), 'utf8')).version

const MANAGED_CONTRACT = `Knex ${KNEX_VERSION} transaction(callback) (lib/execution/transaction.js) runs the callback and, when its promise resolves, calls commit(), which runs query(conn, 'COMMIT;', 1, value). That resolves the transaction promise with the callback's value when the query promise resolves. The query result's command tag is not consulted. A rejection of the callback runs ROLLBACK and rejects with that error.`
const EXPLICIT_CONTRACT = `Knex ${KNEX_VERSION} knex.transaction() with no callback returns a transaction promise's transactor. trx.commit() runs the same COMMIT query and resolves when that query resolves. trx.rollback() sends ROLLBACK.`

function rowsOf(result) {
  if (result?.rows) return result.rows
  if (Array.isArray(result) && result[0]?.xid) return result
  return result?.rows ?? []
}

function apiFor(ctx) {
  const { knex, state } = ctx
  const write = (handle, name) => handle('item').insert({ name, qty: 0 })
  const identify = async (handle) => {
    const result = await handle.raw('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    const [r] = rowsOf(result)
    return { xid: r.xid, pid: Number(r.pid) }
  }
  return {
    forms: {
      managed: 'knex.transaction(callback). The callback catches 23505 and returns.',
      explicit: 'const trx = await knex.transaction(); catch 23505; await trx.commit().',
      control: 'knex.transaction(callback). The unique violation leaves the callback.',
      savepoint: 'Inside knex.transaction(callback), trx.transaction(callback) is the savepoint. The inner callback throws 23505. The outer callback catches it and returns.',
    },
    contracts: { managed: MANAGED_CONTRACT, explicit: EXPLICIT_CONTRACT, control: MANAGED_CONTRACT, savepoint: MANAGED_CONTRACT },
    unsupported: {},
    managed: (body) => managedOutcome((callback) => knex.transaction(callback), body, { call: 'knex.transaction(callback)', contract: MANAGED_CONTRACT }),
    explicit: {
      names: { start: 'knex.transaction()', commit: 'trx.commit()', rollback: 'trx.rollback()' },
      contract: EXPLICIT_CONTRACT,
      start: () => knex.transaction(),
      commit: (trx) => trx.commit(),
      rollback: (trx) => trx.rollback(),
    },
    async savepoint(trx) {
      try {
        await trx.transaction(async (nested) => {
          await nested('uniq').insert({ code: 'taken' })
        })
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { recovered: true, violation: violationInfo(e) }
      }
      throw new ProtocolError('the duplicate insert did not raise')
    },
    write,
    insertTaken: (handle) => handle('uniq').insert({ code: 'taken' }),
    identify,
    async probe() {
      try {
        await knex.raw('select 1 as ok')
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
        const outcome = await managedOutcome((callback) => knex.transaction(callback), async (trx) => {
          await write(trx, name)
          const id = await identify(trx)
          pid = id.pid
          await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
        }, { call: 'knex.transaction(callback)', contract: MANAGED_CONTRACT })
        return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid }
      }
    },
    hooks: () => ({ supported: false, reason: 'Knex emits query, query-response, query-error, and start. It does not emit a commit or rollback hook.', events_seen: state.events.slice(0, 8) }),
    commandTag: () => state.tags.slice(),
    extras: () => ({ statements: state.statements.slice() }),
  }
}

const cases = {
  'CTL-01.commit': (ctx, { markers, checkpoint }) => managedOutcome((callback) => ctx.knex.transaction(callback), async (trx) => {
    await trx('item').insert({ name: markers.tx, qty: 0 })
    const result = await trx.raw('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    const [r] = rowsOf(result)
    await checkpoint('before-end', { xid: r.xid, pid: Number(r.pid) })
  }, { call: 'knex.transaction(callback)', contract: MANAGED_CONTRACT }),
  'CTL-01.rollback': (ctx, { markers, checkpoint }) => managedOutcome((callback) => ctx.knex.transaction(callback), async (trx) => {
    await trx('item').insert({ name: markers.tx, qty: 0 })
    const result = await trx.raw('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    const [r] = rowsOf(result)
    await checkpoint('before-end', { xid: r.xid, pid: Number(r.pid) })
    throw new Error('application error: the request fails')
  }, { call: 'knex.transaction(callback)', contract: MANAGED_CONTRACT }),
  ...prCaseHandlers(apiFor),
}

await main({
  describe: () => ({
    adapter: { name: 'knex', version: '0.1.0' },
    framework: { name: 'knex', version: KNEX_VERSION },
    driver: { name: 'pg', version: PG_VERSION },
    components: { knex: KNEX_VERSION },
  }),
  modes: { native: { configuration: { transaction: 'knex.transaction(callback) and knex.transaction()' } } },
  open: async (message) => {
    const { host, port, user, password, database, application_name } = message.connection
    const state = { tags: [], statements: [], events: [] }
    const knex = knexFactory({
      client: 'pg',
      connection: { host, port, user, password, database, application_name },
      pool: { min: 0, max: message.case.settings?.pool_max ?? 2 },
      acquireConnectionTimeout: 5000,
    })
    knex.on('query', (query) => {
      const sql = String(query?.sql ?? '').replace(/\s+/g, ' ').slice(0, 180)
      state.statements.push(sql)
      state.events.push('query')
    })
    knex.on('query-response', (response, query) => {
      const sql = String(query?.sql ?? '')
      if (/^\s*commit\b/i.test(sql) && response?.command) state.tags.push(response.command)
    })
    return { context: { knex, state }, close: () => knex.destroy() }
  },
  cases,
})
