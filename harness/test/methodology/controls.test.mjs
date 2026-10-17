// Methodology tests: the whole runner, against the real disposable server. Needs `pnpm run pg:up`; without it, the
// tests fail (they are never skipped, so a missing server cannot pass for a green run).
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ROOT, loadAdapters } from '../../lib/catalog.mjs'
import { runSuite } from '../../lib/suite.mjs'
import { checkRunDir, resultErrors } from '../evidence-checks.mjs'

const outDir = mkdtempSync(join(tmpdir(), 'ppcs-methodology-'))
// PPCS_KEEP_TEST_RESULTS=1 keeps the runs these tests write, for inspection.
after(() => { if (process.env.PPCS_KEEP_TEST_RESULTS) console.log(`methodology runs kept in ${outDir}`); else rmSync(outDir, { recursive: true, force: true }) })
const byKey = (results) => Object.fromEntries(results.map((r) => [`${r.specification.id} ${r.subject.adapter.name}/${r.execution.mode}`, r]))
const violated = (r, id) => r.evaluation.invariants.some((i) => i.id === id && i.holds === false)

test('controls: every pg-control expectation holds; the known-good implementation passes, the known-bad one is detected', async () => {
  const { results, runDir } = await runSuite({ adapterFilter: ['pg-control'], outDir })
  assert.deepEqual(checkRunDir(runDir), [], 'every file matches its schema, and none contains the password')
  const r = byKey(results)
  const pg = loadAdapters().find((a) => a.name === 'pg-control')
  for (const [id, byMode] of Object.entries(pg.expectations)) {
    for (const [mode, expected] of Object.entries(byMode)) {
      const x = r[`${id} pg-control/${mode}`]
      assert.equal(x.evaluation.classification, expected, `${id} ${mode}: ${x.evaluation.reason}`)
    }
  }
  // TX-01A: the unsafe control reports a commit of a transaction PostgreSQL aborted; COMMIT reached the server.
  const negative = r['TX-01A.caught-error-then-commit pg-control/unsafe']
  assert.equal(negative.database_outcome.transactions.tx.fate, 'aborted')
  assert.equal(negative.database_outcome.markers.tx, false)
  assert.equal(negative.evaluation.mechanism_exercised, true)
  assert.equal(r['TX-01A.caught-error-then-commit pg-control/correct'].evaluation.mechanism_exercised, true)
  // TX-01B: conn-lost is a known outcome, so the unsafe control's "rolled back" is true; after a discarded reply it is not.
  assert.deepEqual(r['TX-01B.conn-lost-before-commit pg-control/unsafe'].evaluation.invariants.map((i) => i.id), ['TX-01B.1'])
  const discarded = r['TX-01B.commit-reply-discarded pg-control/unsafe']
  assert.equal(discarded.database_outcome.transactions.tx.fate, 'committed')
  assert.ok(violated(discarded, 'TX-01B.2'))
  assert.deepEqual(r['TX-01B.commit-reply-discarded pg-control/correct'].evaluation.not_exercised, [], 'the control declares its rollback-claim channel')
  // TX-02: the fault's effect is observed on the server, at the checkpoint after the nested scope.
  assert.equal(r['TX-02.savepoint-rollback-not-sent pg-control/correct'].database_outcome.checkpoints['after-fault'].locks.xids.length, 2)
  assert.ok(r['TX-02.savepoint-rollback-rejected pg-control/correct'].api_outcome.steps.fault.reply_codes.includes('3B001'))
  // TX-03: unsafe connection reuse, observed server-side: the next unit runs inside the failed transaction, and commits it.
  const reuse = r['TX-03.rollback-not-sent pg-control/unsafe']
  const { unit1, unit2 } = reuse.database_outcome.transactions
  assert.equal(unit2.xid, unit1.xid, 'the next unit ran inside the failed transaction')
  assert.equal(unit1.fate, 'committed')
  assert.equal(reuse.database_outcome.markers.doomed, true)
  assert.ok(violated(reuse, 'TX-03.1'))
  assert.match(reuse.evaluation.reason, /open at report time \(`after-unit1`: xid \d+ in progress\); committed by later work in the case/)
  // TX-04: the unsafe control's deferred caller write is rolled back with the failed nested scope: a lost write.
  const lost = r['TX-04.nested-failure-contained pg-control/unsafe']
  assert.ok(violated(lost, 'TX-04.1'))
  assert.equal(lost.database_outcome.markers.outer, false)
  assert.equal(lost.api_outcome.reported, 'committed')
  const na = r['TX-04.independent-inner pg-control/correct']
  assert.equal(na.evaluation.classification, 'UNSUPPORTED')
  // The schema check is not vacuous: it rejects an unknown classification, and a FAIL without its contract basis.
  assert.notDeepEqual(resultErrors({ ...negative, evaluation: { ...negative.evaluation, classification: 'MAYBE' } }), [])
  assert.notDeepEqual(resultErrors({ ...negative, evaluation: { ...negative.evaluation, contract_basis: null } }), [])
})

test('misbehaving adapters: never PASS; UNSUPPORTED is not FAIL; unimplemented is NOT_RUN', async () => {
  const fixtures = loadAdapters(join(ROOT, 'harness/test/fixtures/adapters'))
  const { results, runDir } = await runSuite({ adapters: fixtures, outDir, timeoutMs: 4000 })
  assert.deepEqual(checkRunDir(runDir), [], 'every file matches its schema, and none contains the password')
  const r = byKey(results)
  const cls = (key) => r[key]?.evaluation.classification
  assert.equal(cls('CTL-01.commit misbehaving/ok'), 'PASS', 'the fixture itself works')
  const inconclusive = {
    hang: /did not finish within 4000 ms/,
    crash: /exited without a result/,
    'skip-checkpoint': /checkpoint "before-end" was not reached/,
    'bogus-xid': /pg_xact_status\(\) for transaction "tx" is unknown/,
    'drop-table': /marker visibility could not be read/,
    garbage: /unknown message type "telemetry"/,
    'undeclared-checkpoint': /undeclared checkpoint "not-in-the-catalog"/,
    'no-marker': /precondition not established: the write of marker "tx" had reached PostgreSQL/,
    'escaped-checkpoint': /transaction "tx" is not bound to its session/,
    'extra-connection': /adapter sessions, more than pool_max \(1\)/,
    'repeated-checkpoint': /checkpoint "before-end" reported more than once/,
  }
  for (const [mode, reason] of Object.entries(inconclusive)) {
    const e = r[`CTL-01.commit misbehaving/${mode}`].evaluation
    assert.equal(e.classification, 'INCONCLUSIVE', mode)
    assert.match(e.reason, reason, mode)
  }
  assert.equal(cls('CTL-01.commit misbehaving/lying'), 'FAIL', 'a false report is caught by the independent observation')
  assert.equal(cls('CTL-01.rollback misbehaving/ok'), 'UNSUPPORTED')
  assert.equal(cls('TX-01A.caught-error-then-commit misbehaving/ok'), 'NOT_RUN')
})
