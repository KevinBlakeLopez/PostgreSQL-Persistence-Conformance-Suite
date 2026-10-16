// Test fixture for the methodology tests (harness/test/methodology/): an adapter that implements CTL-01.commit
// correctly in mode `ok`, and in every other mode breaks in one specific way that the runner must never classify as
// PASS. It resolves `pg` from the harness's own node_modules.
import pg from 'pg'
import { main } from '../../../../../adapters/node-kit/adapter-main.mjs'
import { checkpoint as rawCheckpoint } from '../../../../../adapters/node-kit/protocol.mjs'

async function identify(client) {
  const { rows: [r] } = await client.query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: r.pid }
}

const committed = { reported: 'committed', basis: 'fixture' }

const behaviours = {
  ok: async (c, { markers, checkpoint }) => {
    await c.query('begin'); await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c)); await c.query('commit'); return committed
  },
  // Never finishes: the runner's timeout must end it, and the case must not be a result.
  hang: () => new Promise(() => {}),
  // Exits without a result.
  crash: () => process.exit(3),
  // Commits correctly but never reports the checkpoint, so no transaction ID is captured.
  'skip-checkpoint': async (c, { markers }) => {
    await c.query('begin'); await c.query('insert into item (name) values ($1)', [markers.tx]); await c.query('commit'); return committed
  },
  // Reports a transaction ID that does not exist (in the future), so pg_xact_status() cannot answer.
  'bogus-xid': async (c, { markers, checkpoint }) => {
    await c.query('begin'); await c.query('insert into item (name) values ($1)', [markers.tx])
    const id = await identify(c)
    await checkpoint('before-end', { pid: id.pid, xid: '4000000000' }); await c.query('commit'); return committed
  },
  // Commits a transaction that never wrote the marker, and reports a commit: a lost write, which must be a FAIL.
  'no-marker': async (c, { checkpoint }) => {
    await c.query('begin'); await checkpoint('before-end', await identify(c)); await c.query('commit'); return committed
  },
  // Commits correctly, then drops the marker table, so marker visibility cannot be read.
  'drop-table': async (c, { markers, checkpoint }) => {
    await c.query('begin'); await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c)); await c.query('commit'); await c.query('drop table item'); return committed
  },
  // Sends lines that are not protocol messages, and a protocol message of an unknown type.
  garbage: async (c, ctx) => {
    process.stdout.write('this line is not JSON\n')
    process.stdout.write(`${JSON.stringify({ ppcs: 1, type: 'telemetry', data: 1 })}\n`)
    return behaviours.ok(c, ctx)
  },
  // Rolls the transaction back, but reports it as committed: the observer must catch the false report.
  lying: async (c, { markers, checkpoint }) => {
    await c.query('begin'); await c.query('insert into item (name) values ($1)', [markers.tx])
    await checkpoint('before-end', await identify(c)); await c.query('rollback'); return committed
  },
  // Reports a checkpoint the case does not declare.
  'undeclared-checkpoint': async (c, ctx) => {
    await rawCheckpoint('not-in-the-catalog', {})
    return behaviours.ok(c, ctx)
  },
}

await main({
  describe: () => ({ adapter: { name: 'misbehaving', version: '0.0.0' }, framework: { name: 'fixture', version: '0.0.0' }, driver: { name: 'pg', version: 'fixture' }, components: {} }),
  modes: Object.fromEntries(Object.keys(behaviours).map((m) => [m, { configuration: { behaviour: m } }])),
  open: async (message) => {
    const client = new pg.Client(message.connection)
    client.on('error', () => {})
    await client.connect()
    return { context: { client }, close: () => client.end() }
  },
  cases: { 'CTL-01.commit': ({ client }, tools) => behaviours[tools.mode](client, tools) },
})
