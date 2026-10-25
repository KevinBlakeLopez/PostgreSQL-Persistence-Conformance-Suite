// node-postgres (pg 8.23.1, pg-pool 3.14.0) session-state probe.
//
// pg-pool documents no reset on release: client.release() returns the client as it is, and client.release(err)
// with a truthy err destroys it. These probes confirm that baseline with independent evidence.
//
// Pool of one client (max: 1). Borrower A changes session state and leaves a transaction open (or aborted), then
// releases. Borrower B checks out next. Evidence: B's reads, an independent observer client (superuser, outside the
// pool), physical identity from the driver-reported PID (BackendKeyData) plus that backend's backend_start.
//
// Usage: node pg_pool_probe.mjs <instance-file> <scenario>

import { readFileSync } from 'node:fs'
import pg from 'pg'

const inst = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const scenario = process.argv[3]
const app = `ssc-node-${scenario}`
const base = { host: inst.host, port: inst.port, database: inst.database }

const out = (who, step, observed) => console.log(`${who.padEnd(9)} ${step.padEnd(84)} ${observed}`)

const obs = new pg.Client({ ...base, user: inst.superuser, password: inst.superuser_password, application_name: 'ssc-node-observer' })
await obs.connect()
if ((await obs.query("select current_setting('cluster_name') t")).rows[0].t !== inst.token) {
  throw new Error("refusing: cluster_name is not this investigation's server")
}
await obs.query('delete from public.item; delete from tenant_a.item; delete from tenant_b.item')

const backendStart = async (pid) =>
  (await obs.query('select backend_start::text s from pg_stat_activity where pid = $1', [pid])).rows[0].s
const landed = async (label) => {
  const r = await obs.query(`select 'public' s from public.item where label = $1 union all
                             select 'tenant_a' from tenant_a.item where label = $1 order by 1`, [label])
  return r.rows.map((x) => x.s).join(', ') || 'not visible'
}

const pool = new pg.Pool({ ...base, user: inst.user, password: inst.password, application_name: app, max: 1 })
console.log(`scenario: ${scenario}`)

const a = await pool.connect()
const aIdent = [a.processID, await backendStart(a.processID)]
await a.query('SET ROLE ssc_tenant_a')
await a.query('SET search_path TO tenant_a, public')
await a.query('BEGIN')
await a.query("insert into item(label) values ('A-uncommitted')")
if (scenario === 'aborted-transaction') {
  try { await a.query('select 1/0') } catch (e) { out('A', 'failing statement inside the transaction', `error ${e.code}`) }
}
out('A', 'SET ROLE, SET search_path, BEGIN, insert (no COMMIT or ROLLBACK)', 'done')
if (scenario === 'release-err') {
  a.release(new Error('application error'))
  out('A', 'release(err)', 'returned')
} else {
  a.release()
  out('A', 'release()', 'returned')
}

const b = await pool.connect()
out('B', 'same physical session as A', b.processID === aIdent[0] && (await backendStart(b.processID)) === aIdent[1])
const state = await obs.query('select state from pg_stat_activity where pid = $1', [b.processID])
out('observer', "B's backend at checkout, before B's first statement", state.rows[0].state)
try {
  out('B', 'current_user | search_path',
    (await b.query("select current_user || ' | ' || current_setting('search_path') v")).rows[0].v)
  await b.query("insert into item(label) values ('B-unqualified')")
  out('B', 'insert (B expects autocommit)', 'ok')
} catch (e) {
  out('B', 'first statement', `error ${e.code}`)
}
out('observer', "where B's insert is visible", await landed('B-unqualified'))
out('observer', "A's insert", await landed('A-uncommitted'))
b.release()
await pool.end()
out('observer', "A's insert after pool.end() closed the connection", await landed('A-uncommitted'))
await obs.end()
