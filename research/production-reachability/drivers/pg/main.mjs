// Direct node-postgres. Client.query is not patched. Result.command is the command tag.
import { createRequire } from 'node:module'
import { ProtocolError, main, managedOutcome } from '../../../../adapters/node-kit/adapter-main.mjs'
import { driverManaged, prCaseHandlers, violationInfo } from '../../js/variants.mjs'

const require = createRequire(new URL('../../../../package.json', import.meta.url))
const pg = require('pg')
const PG_VERSION = require('pg/package.json').version

const CHECK_CONTRACT = 'node-postgres Client.query (pg 8) resolves with a Result whose command property is PostgreSQL\'s command tag. This mode reports rolled_back when COMMIT resolves with a tag other than COMMIT, and failed when COMMIT rejects.'
const IGNORE_CONTRACT = 'node-postgres Client.query resolves without throwing when the server accepts the command, including a COMMIT whose command tag is ROLLBACK. This mode reports committed whenever that call resolves. Result.command is still on the Result; this mode does not read it.'

function finishCommit(reply, mode, state, contract) {
  state.commandTag = reply.command ?? null
  if (mode === 'check-tag' && reply.command !== 'COMMIT') {
    return {
      reported: 'rolled_back',
      basis: `COMMIT resolved with command tag ${reply.command}`,
      contract,
      api_error: { class: 'CommandTag', code: null, message: `COMMIT was answered with ${reply.command}` },
    }
  }
  return { reported: 'committed', basis: `COMMIT resolved with command tag ${reply.command}`, contract }
}

function apiFor(ctx, tools) {
  const mode = tools.mode
  const contract = mode === 'check-tag' ? CHECK_CONTRACT : IGNORE_CONTRACT
  const state = { commandTag: null }
  const client = () => ctx.client
  const write = (c, name) => c.query('insert into item (name) values ($1)', [name])
  const identify = async (c) => {
    const { rows: [r] } = await c.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    return { xid: r.xid, pid: Number(r.pid) }
  }
  return {
    forms: {
      managed: 'BEGIN, callback, COMMIT, on one Client. The callback catches 23505 and returns.',
      explicit: 'BEGIN, catch 23505, client.query(\'COMMIT\').',
      control: 'BEGIN, the unique violation leaves the callback, then ROLLBACK.',
      savepoint: 'SAVEPOINT ppcs_sp, catch 23505, ROLLBACK TO SAVEPOINT ppcs_sp, then COMMIT.',
    },
    contracts: { managed: contract, explicit: contract, control: contract, savepoint: contract },
    unsupported: {},
    async managed(body) {
      const c = client()
      await c.query('BEGIN')
      try {
        await body(c)
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        await c.query('ROLLBACK').catch(() => {})
        return { reported: 'rolled_back', basis: 'the body threw and the client sent ROLLBACK', contract, api_error: violationInfo(e) }
      }
      try {
        const reply = await c.query('COMMIT')
        return finishCommit(reply, mode, state, contract)
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { reported: 'failed', basis: 'COMMIT rejected', contract, api_error: violationInfo(e) }
      }
    },
    explicit: {
      names: { start: 'BEGIN', commit: "client.query('COMMIT')", rollback: "client.query('ROLLBACK')" },
      contract,
      start: async () => { await client().query('BEGIN'); return client() },
      commit: async (c) => finishCommit(await c.query('COMMIT'), mode, state, contract),
      rollback: (c) => c.query('ROLLBACK'),
    },
    async savepoint(c) {
      await c.query('SAVEPOINT ppcs_sp')
      try {
        await c.query("insert into uniq (code) values ('taken')")
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        await c.query('ROLLBACK TO SAVEPOINT ppcs_sp')
        return { recovered: true, violation: violationInfo(e) }
      }
      throw new ProtocolError('the duplicate insert did not raise')
    },
    write,
    insertTaken: (c) => c.query("insert into uniq (code) values ('taken')"),
    identify,
    async probe() {
      try {
        await client().query('select 1 as ok')
        return { supported: true, ok: true, error: null }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { supported: true, ok: false, error: violationInfo(e) }
      }
    },
    async reuse(name, checkpoint) {
      const started = Date.now()
      try {
        const outcome = await this.managed(async (c) => {
          await write(c, name)
          const id = await identify(c)
          await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
          this._reusePid = id.pid
        })
        return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid: this._reusePid ?? null }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid: null }
      }
    },
    hooks: () => ({ supported: false, reason: 'node-postgres has no transaction-commit hook' }),
    commandTag: () => state.commandTag,
  }
}

const cases = {
  'CTL-01.commit': async (ctx, { markers, checkpoint, mode }) => {
    const contract = mode === 'check-tag' ? CHECK_CONTRACT : IGNORE_CONTRACT
    return driverManaged(async (body) => {
      const outcome = await apiFor(ctx, { mode }).managed(body)
      if (outcome.reported !== 'committed') {
        const error = new Error(outcome.basis)
        error.code = outcome.api_error?.code ?? null
        throw error
      }
    }, async (c) => {
      await c.query('insert into item (name) values ($1)', [markers.tx])
      const { rows: [r] } = await c.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
      await checkpoint('before-end', { xid: r.xid, pid: Number(r.pid) })
    }, { call: "client.query('COMMIT')", contract })
  },
  'CTL-01.rollback': async (ctx, { markers, checkpoint }) => managedOutcome(async (body) => {
    const c = ctx.client
    await c.query('BEGIN')
    try { await body(c) } catch (e) {
      if (e instanceof ProtocolError) throw e
      await c.query('ROLLBACK').catch(() => {})
      throw e
    }
    await c.query('COMMIT')
  }, async (c) => {
    await c.query('insert into item (name) values ($1)', [markers.tx])
    const { rows: [r] } = await c.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    await checkpoint('before-end', { xid: r.xid, pid: Number(r.pid) })
    throw new Error('application error: the request fails')
  }, { call: 'BEGIN/ROLLBACK', contract: CHECK_CONTRACT }),
  ...prCaseHandlers(apiFor),
}

await main({
  describe: () => ({
    adapter: { name: 'pg', version: '0.1.0' },
    framework: { name: 'pg', version: PG_VERSION },
    driver: { name: 'pg', version: PG_VERSION },
    components: {},
  }),
  modes: {
    'check-tag': { configuration: { commit_reply: 'Result.command must be COMMIT' } },
    'ignore-tag': { configuration: { commit_reply: 'resolved query is reported as committed' } },
  },
  open: async (message) => {
    const client = new pg.Client(message.connection)
    client.on('error', () => {})
    await client.connect()
    return { context: { client }, close: () => client.end() }
  },
  cases,
})
