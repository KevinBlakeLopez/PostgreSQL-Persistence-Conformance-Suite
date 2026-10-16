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

test('controls: the known-good implementation passes, the known-bad one is detected', async () => {
  const { results, runDir } = await runSuite({ adapterFilter: ['pg-control'], outDir })
  assert.deepEqual(checkRunDir(runDir), [], 'every file matches its schema, and none contains the password')
  const r = byKey(results)
  assert.equal(r['CTL-01.commit pg-control/correct'].evaluation.classification, 'PASS', 'a genuinely committed marker is detected')
  assert.equal(r['CTL-01.rollback pg-control/correct'].evaluation.classification, 'PASS', 'a genuinely rolled-back marker is absent')
  assert.equal(r['TX-01A.caught-error-then-commit pg-control/correct'].evaluation.classification, 'PASS', 'positive control')
  const negative = r['TX-01A.caught-error-then-commit pg-control/unsafe']
  assert.equal(negative.evaluation.classification, 'FAIL', 'negative control')
  assert.equal(negative.database_outcome.transactions.tx.fate, 'aborted')
  assert.equal(negative.database_outcome.markers.tx, false)
  // TX-01B: the correct control reports a failure without asserting an outcome; the unsafe one converts the unknown
  // outcome into a confirmed rollback, and is caught, including when PostgreSQL in fact committed.
  for (const id of ['TX-01B.conn-lost-before-commit', 'TX-01B.commit-reply-discarded']) {
    assert.equal(r[`${id} pg-control/correct`].evaluation.classification, 'PASS', `${id} positive control`)
    const unsafe = r[`${id} pg-control/unsafe`]
    assert.equal(unsafe.evaluation.classification, 'FAIL', `${id} negative control`)
    assert.ok(unsafe.evaluation.invariants.some((i) => i.id === 'TX-01B.2' && i.holds === false), `${id}: unknown outcome converted to a rollback`)
  }
  assert.equal(r['TX-01B.commit-reply-discarded pg-control/unsafe'].database_outcome.transactions.tx.fate, 'committed')
  // TX-02: after a failed savepoint rollback, the correct control refuses to commit; the unsafe one commits anyway.
  for (const id of ['TX-02.savepoint-rollback-not-sent', 'TX-02.savepoint-rollback-rejected', 'TX-02.conn-lost-before-savepoint-rollback']) {
    assert.equal(r[`${id} pg-control/correct`].evaluation.classification, 'PASS', `${id} positive control`)
  }
  for (const id of ['TX-02.savepoint-rollback-not-sent', 'TX-02.savepoint-rollback-rejected']) {
    assert.equal(r[`${id} pg-control/unsafe`].evaluation.classification, 'FAIL', `${id} negative control`)
  }
  // TX-03: a deliberately unsafe connection reuse is detected by the observer. The next unit reports the failed
  // transaction's own ID from inside its transaction, and pg_xact_status() shows that transaction committed.
  for (const id of ['TX-03.rollback-not-sent', 'TX-03.conn-lost-in-transaction']) {
    assert.equal(r[`${id} pg-control/correct`].evaluation.classification, 'PASS', `${id} positive control`)
    assert.equal(r[`${id} pg-control/unsafe`].evaluation.classification, 'FAIL', `${id} negative control`)
  }
  const reuse = r['TX-03.rollback-not-sent pg-control/unsafe']
  const { unit1, unit2 } = reuse.database_outcome.transactions
  assert.equal(unit2.xid, unit1.xid, 'the next unit ran inside the failed transaction')
  assert.equal(unit1.fate, 'committed')
  assert.equal(reuse.database_outcome.markers.doomed, true)
  assert.ok(reuse.evaluation.invariants.some((i) => i.id === 'TX-03.1' && i.holds === false))
  // TX-04: no fault is injected, so both modes keep the savepoint boundaries; the control declares no propagation modes,
  // and that is recorded as UNSUPPORTED, not FAIL.
  for (const id of ['TX-04.nested-failure-contained', 'TX-04.nested-released-outer-rollback']) {
    for (const mode of ['correct', 'unsafe']) assert.equal(r[`${id} pg-control/${mode}`].evaluation.classification, 'PASS', `${id} ${mode}`)
  }
  assert.equal(r['TX-04.independent-inner pg-control/correct'].evaluation.classification, 'UNSUPPORTED')
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
  }
  for (const [mode, reason] of Object.entries(inconclusive)) {
    const e = r[`CTL-01.commit misbehaving/${mode}`].evaluation
    assert.equal(e.classification, 'INCONCLUSIVE', mode)
    assert.match(e.reason, reason, mode)
  }
  assert.equal(cls('CTL-01.commit misbehaving/lying'), 'FAIL', 'a false report is caught by the independent observation')
  assert.equal(cls('CTL-01.commit misbehaving/no-marker'), 'FAIL', 'a reported commit whose write is not visible is a lost write')
  assert.equal(cls('CTL-01.rollback misbehaving/ok'), 'UNSUPPORTED')
  assert.equal(cls('TX-01A.caught-error-then-commit misbehaving/ok'), 'NOT_RUN')
})
