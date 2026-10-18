// Test fixture for the methodology tests (harness/test/methodology/): TX-05.explicit-serializable, correct in mode `ok`
// and broken in each other mode in one specific way, to show what the runner makes of it. The CTL-01 cases are correct
// in every mode, so that the observation-control gate holds and the TX-05 classifications show. It resolves `pg` from
// the harness's own node_modules.
import pg from 'pg'
import { main } from '../../../../../adapters/node-kit/adapter-main.mjs'
import { errInfo } from '../../../../../adapters/node-kit/util.mjs'

const identify = "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as level"

/** A started transaction: `begin`, a write of the marker, a read, and the capture checkpoint with a `claim` of the level
 * (undefined: report PostgreSQL's own; null: report none). */
const started = ({ begin = 'BEGIN ISOLATION LEVEL SERIALIZABLE', read = 'select name from item where name = $1', claim } = {}) => async (c, { markers, checkpoint }) => {
  await c.query(begin)
  await c.query('insert into item (name) values ($1)', [markers.tx])
  await c.query(read, read.includes('$1') ? [markers.tx] : [])
  const { rows: [r] } = await c.query(identify)
  await checkpoint('after-read', { xid: r.xid, pid: r.pid, ...(claim === null ? {} : { transaction_isolation: claim ?? r.level }) })
  await c.query('commit')
  return { reported: 'committed', basis: 'fixture' }
}

/** A rejected request: an error instead of a transaction, then, with `baseline`, a plain transaction through the same form. */
const rejected = ({ viaServer = false, baseline = true } = {}) => async (c, { checkpoint }) => {
  let error = Object.assign(new Error('fixture: the requested isolation level is not supported'), { code: 'E_UNSUPPORTED_ISOLATION_LEVEL' })
  // PostgreSQL rejects an invalid BEGIN with a SQLSTATE (42601), and no transaction starts.
  if (viaServer) { try { await c.query('BEGIN ISOLATION LEVEL BOGUS') } catch (e) { error = e } }
  if (baseline) {
    await c.query('begin')
    const { rows: [r] } = await c.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
    await checkpoint('baseline', { xid: r.xid, pid: r.pid })
    await c.query('commit')
  }
  return { reported: 'failed', basis: 'fixture: the API raised instead of starting the transaction', api_error: errInfo(error) }
}

const tx05 = {
  ok: started(),
  'repeatable-read': started({ begin: 'BEGIN ISOLATION LEVEL REPEATABLE READ' }),
  'claims-serializable': started({ begin: 'BEGIN', claim: 'serializable' }),
  'claims-weaker': started({ claim: 'read committed' }),
  'reads-other-table': started({ read: 'select code from uniq' }),
  'omits-level': started({ claim: null }),
  rejects: rejected(),
  'rejects-sqlstate': rejected({ viaServer: true }),
  'rejects-no-baseline': rejected({ baseline: false }),
}

const ctl = (fails) => async (c, { markers, checkpoint }) => {
  await c.query('begin')
  await c.query('insert into item (name) values ($1)', [markers.tx])
  const { rows: [r] } = await c.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  await checkpoint('before-end', { xid: r.xid, pid: r.pid })
  if (!fails) { await c.query('commit'); return { reported: 'committed', basis: 'fixture' } }
  await c.query('rollback')
  return { reported: 'rolled_back', basis: 'fixture', api_error: { class: 'Error', code: null, message: 'fixture: the request fails' } }
}

await main({
  describe: () => ({ adapter: { name: 'misbehaving-tx05', version: '0.0.0' }, framework: { name: 'fixture', version: '0.0.0' }, driver: { name: 'pg', version: 'fixture' }, components: {} }),
  modes: Object.fromEntries(Object.keys(tx05).map((m) => [m, { configuration: { behaviour: m } }])),
  open: async (message) => {
    const client = new pg.Client(message.connection)
    client.on('error', () => {})
    await client.connect()
    return { context: { client }, close: () => client.end() }
  },
  cases: {
    'CTL-01.commit': ({ client }, tools) => ctl(false)(client, tools),
    'CTL-01.rollback': ({ client }, tools) => ctl(true)(client, tools),
    'TX-05.explicit-serializable': ({ client }, tools) => tx05[tools.mode](client, tools),
  },
})
