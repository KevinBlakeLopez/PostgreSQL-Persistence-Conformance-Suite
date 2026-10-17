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

test('controls: the known-good implementation passes, the known-bad one is detected', async () => {
  const { results, runDir } = await runSuite({ adapterFilter: ['pg-control'], outDir })
  assert.deepEqual(checkRunDir(runDir), [], 'every file matches its schema, and none contains the password')
  const r = byKey(results)
  const cls = (key) => r[key].evaluation.classification
  assert.equal(cls('CTL-01.commit pg-control/correct'), 'PASS', 'a genuinely committed marker is detected')
  assert.equal(cls('CTL-01.rollback pg-control/correct'), 'PASS', 'a genuinely rolled-back marker is absent')
  // TX-01A: the unsafe control reports a commit of a transaction PostgreSQL aborted; COMMIT reached the server.
  assert.equal(cls('TX-01A.caught-error-then-commit pg-control/correct'), 'PASS', 'positive control')
  const negative = r['TX-01A.caught-error-then-commit pg-control/unsafe']
  assert.equal(negative.evaluation.classification, 'FAIL', 'negative control')
  assert.equal(negative.database_outcome.transactions.tx.fate, 'aborted')
  assert.equal(negative.database_outcome.markers.tx, false)
  assert.equal(negative.evaluation.mechanism_exercised, true)
  assert.equal(r['TX-01A.caught-error-then-commit pg-control/correct'].evaluation.mechanism_exercised, true)
  // TX-01B: conn-lost is a known outcome, so the unsafe control's "rolled back" is true; after a discarded reply it is not.
  for (const id of ['TX-01B.conn-lost-before-commit', 'TX-01B.commit-reply-discarded']) assert.equal(cls(`${id} pg-control/correct`), 'PASS', `${id} positive control`)
  const known = r['TX-01B.conn-lost-before-commit pg-control/unsafe']
  assert.equal(known.evaluation.classification, 'PASS')
  assert.deepEqual(known.evaluation.invariants.map((i) => i.id), ['TX-01B.1'])
  const discarded = r['TX-01B.commit-reply-discarded pg-control/unsafe']
  assert.equal(discarded.evaluation.classification, 'FAIL')
  assert.equal(discarded.database_outcome.transactions.tx.fate, 'committed')
  assert.ok(violated(discarded, 'TX-01B.2'))
  assert.deepEqual(r['TX-01B.commit-reply-discarded pg-control/correct'].evaluation.not_exercised, [], 'the control declares its rollback-claim channel')
  // TX-02: after a failed savepoint rollback, the correct control refuses to commit; the unsafe one commits anyway. The
  // fault's effect is observed on the server as the fault fires.
  for (const id of ['TX-02.savepoint-rollback-not-sent', 'TX-02.savepoint-rollback-rejected', 'TX-02.conn-lost-before-savepoint-rollback']) {
    assert.equal(cls(`${id} pg-control/correct`), 'PASS', `${id} positive control`)
  }
  for (const id of ['TX-02.savepoint-rollback-not-sent', 'TX-02.savepoint-rollback-rejected']) assert.equal(cls(`${id} pg-control/unsafe`), 'FAIL', `${id} negative control`)
  assert.equal(r['TX-02.savepoint-rollback-not-sent pg-control/correct'].database_outcome.checkpoints['after-fault'].locks.xids.length, 2)
  assert.ok(r['TX-02.savepoint-rollback-rejected pg-control/correct'].api_outcome.steps.fault.reply_codes.includes('3B001'))
  // TX-03: unsafe connection reuse, observed server-side: the next unit runs inside the failed transaction, and commits it.
  for (const id of ['TX-03.rollback-not-sent', 'TX-03.conn-lost-in-transaction']) {
    assert.equal(cls(`${id} pg-control/correct`), 'PASS', `${id} positive control`)
    assert.equal(cls(`${id} pg-control/unsafe`), 'FAIL', `${id} negative control`)
  }
  const reuse = r['TX-03.rollback-not-sent pg-control/unsafe']
  const { unit1, unit2 } = reuse.database_outcome.transactions
  assert.equal(unit2.xid, unit1.xid, 'the next unit ran inside the failed transaction')
  assert.equal(unit1.fate, 'committed')
  assert.equal(reuse.database_outcome.markers.doomed, true)
  assert.ok(violated(reuse, 'TX-03.1'))
  assert.match(reuse.evaluation.reason, /open at report time \(`after-unit1`: xid \d+ in progress\); committed by later work in the case/)
  // TX-04: no fault is injected, so both modes keep the savepoint boundaries; the control declares no propagation modes,
  // and that is recorded as UNSUPPORTED, not FAIL.
  for (const id of ['TX-04.nested-failure-contained', 'TX-04.nested-released-outer-rollback']) {
    for (const mode of ['correct', 'unsafe']) assert.equal(cls(`${id} pg-control/${mode}`), 'PASS', `${id} ${mode}`)
  }
  assert.equal(cls('TX-04.independent-inner pg-control/correct'), 'UNSUPPORTED')
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
