// Unit tests for the runner's handling of what an adapter sends (harness/lib/run-case.mjs): a scripted adapter against a
// stub instance and observer, so no database is needed. H4 and H8 port harness counterexamples of the independent
// methodology review (ppcs-methodology-review, evidence/harness-counterexamples.mjs).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { loadCatalog } from '../../lib/catalog.mjs'
import { runCase } from '../../lib/run-case.mjs'

const catalog = loadCatalog()

// The runner's own handling of what an adapter sends, with a scripted adapter and a stub server.
const SCRIPTED = `
import { createInterface } from 'node:readline'
const script = JSON.parse(process.argv[2])
const queue = []; const waiters = []
createInterface({ input: process.stdin }).on('line', (l) => { const m = JSON.parse(l); const w = waiters.shift(); w ? w(m) : queue.push(m) })
const next = () => (queue.length ? Promise.resolve(queue.shift()) : new Promise((r) => waiters.push(r)))
const send = (m) => new Promise((r) => process.stdout.write(JSON.stringify({ ppcs: 1, ...m }) + '\\n', r))
await next()
for (const m of script) { await send(m); if (m.type === 'checkpoint') await next() }
process.exit(0)
`

async function runScripted(caseId, script) {
  const dir = mkdtempSync(join(tmpdir(), 'ppcs-scripted-'))
  try {
    writeFileSync(join(dir, 'scripted.mjs'), SCRIPTED)
    const fates = { 100: 'aborted', 200: 'committed' }
    const instance = {
      settings: { password: 'not-a-real-password', image: 'stub' }, server: { version: 'stub', server_version: '18.6', server_version_num: 180006, settings: {} },
      connection: () => ({}), createDatabase: async () => 'stubdb', query: async () => [], dropDatabase: async () => {}, terminateBackend: async () => false,
    }
    const observer = {
      fixtureFingerprint: async () => 'fx',
      fate: async (_d, xid) => fates[xid] ?? null,
      session: async (_d, pid, xid) => (pid == null ? null : { pid, present: true, state: 'idle in transaction', in_transaction: true, backend_xid: xid, xid_matches: xid ? true : null, backend_start: 'T0', query: 'insert', application_name: 'ppcs-adapter' }),
      locks: async (_d, pid) => (pid == null ? null : { wrote_item: true, xids: ['100'] }),
      sessions: async () => [{ pid: 7 }],
      waitGone: async () => true,
      settle: async () => [],
      markers: async () => ({ tx: true }),
      markerXmins: async () => ({ tx: '200' }),
      strayRows: async () => [],
    }
    const adapter = { name: 'scripted', dir, command: ['node', 'scripted.mjs', JSON.stringify(script)], sourceSha256: '0'.repeat(64) }
    const kase = catalog.cases.find((c) => c.id === caseId)
    return await runCase({ instance, observer, catalog, adapter, mode: { id: 'native', kind: 'fixture', description: 'scripted' }, kase, runId: 'unit', harness: { ppcs_version: '0', sha256: '0'.repeat(64) }, timeoutMs: 10000 })
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

const HELLO = { type: 'hello', adapter: { version: '0' }, framework: { name: 'scripted', version: '0' } }

test('H8: a checkpoint reported twice (a retried transaction body) is a protocol error, and the first capture is kept', async () => {
  const r = await runScripted('CTL-01.commit', [
    HELLO,
    { type: 'checkpoint', name: 'before-end', pid: 7, xid: '100' }, // attempt 1, rolled back
    { type: 'checkpoint', name: 'before-end', pid: 7, xid: '200' }, // attempt 2, committed
    { type: 'checkpoint', name: 'after-end' },
    { type: 'result', status: 'completed', reported: 'committed', basis: 'resolved after a retry' },
  ])
  assert.equal(r.database_outcome.transactions.tx.xid, '100')
  assert.ok(r.diagnostics.protocol_errors.includes('checkpoint "before-end" reported more than once'))
  assert.equal(r.evaluation.classification, 'INCONCLUSIVE')
})

test('H4, through the runner: "unsupported" at run time is a protocol error', async () => {
  const r = await runScripted('CTL-01.commit', [HELLO, { type: 'result', status: 'unsupported', reason: 'not today' }])
  assert.equal(r.evaluation.classification, 'INCONCLUSIVE')
  assert.match(r.evaluation.reason, /only its manifest may declare a case unsupported/)
})

test('the runner requires the implicit after-end checkpoint of a completed case', async () => {
  const r = await runScripted('CTL-01.commit', [HELLO, { type: 'checkpoint', name: 'before-end', pid: 7, xid: '200' }, { type: 'result', status: 'completed', reported: 'committed', basis: 'resolved' }])
  assert.equal(r.evaluation.classification, 'INCONCLUSIVE')
  assert.match(r.evaluation.reason, /checkpoint "after-end" was not reached/)
})
