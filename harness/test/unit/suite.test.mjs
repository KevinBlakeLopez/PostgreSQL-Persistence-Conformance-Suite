// Unit tests for the run-level rules: repetitions, the control gates, comparison with an earlier run, and the report's
// qualifiers (harness/lib/suite.mjs, report.mjs). No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyGates, combineRepetitions, incomparable } from '../../lib/suite.mjs'
import { loadAdapters, loadCatalog } from '../../lib/catalog.mjs'
import { qualifiers } from '../../lib/report.mjs'

const catalog = loadCatalog()
const adapters = loadAdapters()

/** A minimal result record, as applyGates and the report see it. */
function result(id, adapter, mode, classification, { kind = 'native', ...evaluation } = {}) {
  return {
    specification: { id, family: catalog.cases.find((c) => c.id === id).family },
    subject: { adapter: { name: adapter } },
    execution: { mode, kind },
    evaluation: { classification, reason: `${classification} for the test`, contract_basis: classification === 'FAIL' ? { invariants: ['x'], framework: 'y' } : null, not_exercised: [], mechanism_exercised: null, ...evaluation },
    repetitions: { count: 3, agreed: true, runs: [] },
  }
}

/** The controls of a run in which they all behave as expected. */
function controls() {
  const pg = adapters.find((a) => a.name === 'pg-control')
  const out = []
  for (const [id, byMode] of Object.entries(pg.expectations)) for (const [mode, cls] of Object.entries(byMode)) out.push(result(id, 'pg-control', mode, cls, { kind: 'control' }))
  return out
}
const ctlPasses = (adapter, mode) => [result('CTL-01.commit', adapter, mode, 'PASS'), result('CTL-01.rollback', adapter, mode, 'PASS')]
const find = (results, id, adapter, mode) => results.find((r) => r.specification.id === id && r.subject.adapter.name === adapter && r.execution.mode === mode)

test('gates: with the controls holding, results keep their classification, and the gates are recorded', () => {
  const results = [...controls(), ...ctlPasses('lucid', 'native'), result('TX-01A.caught-error-then-commit', 'lucid', 'native', 'FAIL')]
  applyGates(results, catalog, adapters)
  const r = find(results, 'TX-01A.caught-error-then-commit', 'lucid', 'native')
  assert.equal(r.evaluation.classification, 'FAIL')
  assert.equal(r.evaluation.gates.controls.held, true)
  assert.equal(r.evaluation.gates.case_controls.held, true)
  assert.equal(r.evaluation.ungated, undefined)
})

test('gates: a failed observation control makes that adapter and mode\'s results INCONCLUSIVE, and only those', () => {
  const results = [...controls(), result('CTL-01.commit', 'lucid', 'native', 'PASS'), result('CTL-01.rollback', 'lucid', 'native', 'FAIL'), ...ctlPasses('typeorm', 'native'),
    result('TX-01A.caught-error-then-commit', 'lucid', 'native', 'FAIL'), result('TX-01A.caught-error-then-commit', 'typeorm', 'native', 'FAIL')]
  applyGates(results, catalog, adapters)
  const gated = find(results, 'TX-01A.caught-error-then-commit', 'lucid', 'native')
  assert.equal(gated.evaluation.classification, 'INCONCLUSIVE')
  assert.deepEqual(gated.evaluation.ungated.classification, 'FAIL')
  assert.equal(gated.evaluation.contract_basis, null)
  assert.match(gated.evaluation.reason, /observation controls did not hold in this run \(CTL-01\.rollback FAIL\)/)
  assert.equal(find(results, 'TX-01A.caught-error-then-commit', 'typeorm', 'native').evaluation.classification, 'FAIL')
  assert.equal(find(results, 'CTL-01.rollback', 'lucid', 'native').evaluation.classification, 'FAIL', 'the controls themselves are not gated')
})

test('gates: a missing observation control is a failed gate', () => {
  const results = [...controls(), result('CTL-01.commit', 'lucid', 'pre-commit-probe', 'PASS'), result('TX-01A.caught-error-then-commit', 'lucid', 'pre-commit-probe', 'PASS')]
  applyGates(results, catalog, adapters)
  assert.match(find(results, 'TX-01A.caught-error-then-commit', 'lucid', 'pre-commit-probe').evaluation.reason, /CTL-01\.rollback not run/)
})

test('gates: a control that misses its expectation for a case gates every framework result for that case', () => {
  const results = [...controls(), ...ctlPasses('lucid', 'native'), result('TX-02.savepoint-rollback-not-sent', 'lucid', 'native', 'PASS'), result('TX-01A.caught-error-then-commit', 'lucid', 'native', 'FAIL')]
  find(results, 'TX-02.savepoint-rollback-not-sent', 'pg-control', 'unsafe').evaluation.classification = 'PASS' // expected FAIL
  applyGates(results, catalog, adapters)
  const gated = find(results, 'TX-02.savepoint-rollback-not-sent', 'lucid', 'native')
  assert.equal(gated.evaluation.classification, 'INCONCLUSIVE')
  assert.match(gated.evaluation.reason, /case controls did not hold in this run \(pg-control \(unsafe\) expected FAIL, got PASS\)/)
  assert.equal(find(results, 'TX-01A.caught-error-then-commit', 'lucid', 'native').evaluation.classification, 'FAIL', 'other cases are not affected')
  assert.equal(find(results, 'TX-02.savepoint-rollback-not-sent', 'pg-control', 'unsafe').evaluation.gates.case_controls, undefined, 'a control is not gated by its own expectations')
})

test('gates: a case no control covers records that, and is not gated by it', () => {
  const results = [...controls(), ...ctlPasses('mikroorm', 'native'), result('TX-04.independent-inner', 'mikroorm', 'native', 'FAIL')]
  applyGates(results, catalog, adapters)
  const r = find(results, 'TX-04.independent-inner', 'mikroorm', 'native')
  assert.equal(r.evaluation.classification, 'FAIL')
  assert.equal(r.evaluation.gates.case_controls.held, null)
})

/** A record as runCase returns it, reduced to what combineRepetitions reads. */
const record = (classification, extra = {}) => ({
  evaluation: { classification, reason: classification, not_exercised: [], mechanism_exercised: null, contract_basis: classification === 'FAIL' ? { invariants: ['x'], framework: 'y' } : null, ...extra },
  api_outcome: { reported: 'committed' },
  database_outcome: { transactions: { tx: { fate: 'committed' } }, markers: { tx: true } },
  timing: { started_at: '2026-10-16T00:00:00.000Z', finished_at: '2026-10-16T00:00:01.000Z', duration_ms: 1000 },
})

test('repetitions: agreement keeps the classification; any disagreement is INCONCLUSIVE, with the full records kept', () => {
  const same = combineRepetitions([record('FAIL'), record('FAIL'), record('FAIL')])
  assert.equal(same.evaluation.classification, 'FAIL')
  assert.equal(same.repetitions.agreed, true)
  assert.equal(same.repetitions.runs.length, 3)
  assert.equal(same.repetitions.records, undefined)
  const flaky = combineRepetitions([record('PASS'), record('FAIL'), record('PASS')])
  assert.equal(flaky.evaluation.classification, 'INCONCLUSIVE')
  assert.match(flaky.evaluation.reason, /the repetitions disagree: #1 PASS; #2 FAIL; #3 PASS/)
  assert.equal(flaky.evaluation.contract_basis, null)
  assert.equal(flaky.repetitions.records.length, 2)
  const qualified = combineRepetitions([record('PASS', { mechanism_exercised: true }), record('PASS', { mechanism_exercised: false }), record('PASS', { mechanism_exercised: true })])
  assert.equal(qualified.evaluation.classification, 'INCONCLUSIVE', 'a PASS whose mechanism did not run is not the same result')
})

test('comparison with an earlier run is refused when the harness or the catalog differs', () => {
  const now = { harness: { sha256: 'a'.repeat(64) }, catalog: { sha256: 'b'.repeat(64) } }
  assert.deepEqual(incomparable(now, now), [])
  assert.match(incomparable(now, { ...now, harness: { sha256: 'c'.repeat(64) } }).join(), /the harness differs/)
  assert.match(incomparable(now, { ...now, harness: undefined }).join(), /not recorded/)
  assert.match(incomparable(now, { ...now, catalog: { sha256: 'c'.repeat(64) } }).join(), /the catalog differs/)
})

test('report qualifiers: a PASS whose mechanism did not run, invariants not exercised, not applicable, gated', () => {
  assert.deepEqual(qualifiers(result('TX-01A.caught-error-then-commit', 'lucid', 'pre-commit-probe', 'PASS', { mechanism_exercised: false })), ['mechanism not exercised'])
  assert.deepEqual(qualifiers(result('TX-01B.commit-reply-discarded', 'lucid', 'native', 'PASS', { not_exercised: ['TX-01B.2'] })), ['TX-01B.2 not exercised'])
  assert.deepEqual(qualifiers({ ...result('TX-04.independent-inner', 'lucid', 'native', 'UNSUPPORTED', { unsupported_class: 'not-applicable-by-design' }), repetitions: null }), ['not applicable by design'])
  assert.deepEqual(qualifiers(result('TX-02.savepoint-rollback-not-sent', 'lucid', 'native', 'INCONCLUSIVE', { ungated: { classification: 'FAIL', reason: 'r' } })), ['gated; ungated FAIL'])
})
