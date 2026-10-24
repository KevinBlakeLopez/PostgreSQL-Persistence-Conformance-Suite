// Classification of MG-02 and MG-03, from hand-built evidence. No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classify } from '../../lib/classify.mjs'
import { loadCatalog } from '../../lib/catalog.mjs'

const catalog = loadCatalog()
const kase = (id) => catalog.cases.find((c) => c.id === id)
const HARNESS = { timedOut: false, timeoutMs: 60000, helloReceived: true, exit: { code: 0, signal: null }, protocolErrors: [], missingCheckpoints: [] }
const done = (reported, exitCode = 0, extra = {}) => ({
  reported,
  exit_code: exitCode,
  ...((reported === 'failed' || reported === 'refused') ? { api_error: { class: 'Error', code: null, message: reported } } : {}),
  ...extra,
})
const failed = (message) => done('failed', 1, { api_error: { class: 'Error', code: null, message } })

function evidence(id, { runners, observed = {}, harness = HARNESS }) {
  return {
    case: kase(id),
    adapterStatus: 'completed',
    runners,
    observed: {
      marker_counts: { m1: 1 },
      history_counts: { m1: 1 },
      inside_migration: ['A'],
      session_ended: false,
      stray_rows: [],
      sessions_at_end: [],
      checkpoints: { 'inside-A': { adapter_sessions: 2, sessions: [{ application_name: 'ppcs-A' }, { application_name: 'ppcs-B' }] } },
      fixture: { before: 'fx', after: 'fx' },
      ...observed,
    },
    adapter: { rollbackClaimChannels: [] },
    harness,
  }
}

const heldRunners = {
  A: done('applied'),
  B: done('nothing_to_do'),
  C: done('nothing_to_do'),
}

test('MG-02.held passes when one runner applied and the others found it applied', () => {
  const result = classify(evidence('MG-02.held', { runners: heldRunners }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-02.1 fails when the migration committed twice', () => {
  const result = classify(evidence('MG-02.held', { runners: heldRunners, observed: { marker_counts: { m1: 2 }, history_counts: { m1: 2 } } }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-02\.1/)
})

test('MG-02.2 fails when two runners report applied and only one commit exists', () => {
  const runners = { ...heldRunners, B: done('applied') }
  const result = classify(evidence('MG-02.held', { runners }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-02\.2/)
})

test('MG-02.5 fails when two roles are inside the migration at once', () => {
  const result = classify(evidence('MG-02.held', { runners: heldRunners, observed: { inside_migration: ['A', 'B'] } }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-02\.5/)
})

test('MG-02.held is INCONCLUSIVE when no runner reached the gate', () => {
  const result = classify(evidence('MG-02.held', { runners: heldRunners, observed: { inside_migration: [] } }), catalog.statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
  assert.match(result.reason, /reached the migration/)
})

const collision = (blocked = ['A', 'B'], failed = []) => ({ table: 'migrations', blocked_roles: blocked, failed_before_release: failed, established: blocked.length > 0 && blocked.length + failed.length === 2, waited_ms: 420 })
const firstRunners = { A: done('applied'), B: failed('duplicate key value violates unique constraint "pg_class_relname_nsp_index"') }

test('MG-02.first-deployment passes when both runners waited on the creation and the loser of the collision failed', () => {
  const result = classify(evidence('MG-02.first-deployment', { runners: firstRunners, observed: { creation_hold: collision() } }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-02.first-deployment fails when the loser of the collision carries on and executes the migration', () => {
  const runners = { A: done('applied'), B: done('applied') }
  const observed = { creation_hold: collision(), marker_counts: { m1: 2 }, history_counts: { m1: 2 }, inside_migration: ['A', 'B'] }
  const result = classify(evidence('MG-02.first-deployment', { runners, observed }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-02\.5/)
})

test('MG-02.first-deployment passes when the framework refused the second runner before the release', () => {
  const result = classify(evidence('MG-02.first-deployment', { runners: { A: done('applied'), B: failed('unable to acquire lock') }, observed: { creation_hold: collision(['A'], ['B']) } }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-02.first-deployment is INCONCLUSIVE when a runner neither waited nor reported failure before the release', () => {
  const result = classify(evidence('MG-02.first-deployment', { runners: firstRunners, observed: { creation_hold: collision(['A']) } }), catalog.statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
  assert.match(result.reason, /waiting on a lock/)
})

test('MG-02.first-deployment is INCONCLUSIVE when the creation hold was not observed', () => {
  const result = classify(evidence('MG-02.first-deployment', { runners: firstRunners }), catalog.statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
})

test('MG-02.idle-session-timeout is INCONCLUSIVE when no session of A ended, and the other invariants are recorded', () => {
  const result = classify(evidence('MG-02.idle-session-timeout', { runners: heldRunners, observed: { session_ended: false } }), catalog.statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
  assert.match(result.reason, /MG-02\.4/)
  assert.equal(result.invariants.find((i) => i.id === 'MG-02.1').holds, true)
})

test('MG-02.session-loss passes when a session of A ended and the marker count is 1', () => {
  const result = classify(evidence('MG-02.session-loss', { runners: heldRunners, observed: { session_ended: true } }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('a migration runner that reports failed without the error is INCONCLUSIVE', () => {
  const runners = { ...heldRunners, B: { reported: 'failed', exit_code: 1 } }
  const result = classify(evidence('MG-02.held', { runners }), catalog.statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
  assert.match(result.reason, /without the error/)
})

test('the session ceiling is per role', () => {
  const sessions = [...Array.from({ length: 10 }, () => ({ application_name: 'ppcs-A' })), { application_name: 'ppcs-B' }]
  const atCeiling = evidence('MG-02.held', { runners: heldRunners, observed: { checkpoints: { 'inside-A': { sessions } } } })
  assert.equal(classify(atCeiling, catalog.statements).classification, 'PASS')
  const over = evidence('MG-02.held', { runners: heldRunners, observed: { checkpoints: { 'inside-A': { sessions: [...sessions, { application_name: 'ppcs-A' }] } } } })
  const overCeiling = classify(over, catalog.statements)
  assert.equal(overCeiling.classification, 'INCONCLUSIVE')
  assert.match(overCeiling.reason, /ppcs-A had 11 sessions/)
})

function revert(id, reported, after, extra = {}) {
  const runners = { A: reported === 'failed' ? failed('the reversal raised') : done(reported) }
  return evidence(id, {
    runners,
        observed: {
      after_revert: { marker_counts: { m1: after.marker }, history_counts: { m1: after.history } },
      apply_reported: 'applied',
      inside_migration: undefined,
    },
    ...extra,
  })
}

test('MG-03.valid-reversal passes when the revert removed the marker and the history entry', () => {
  const result = classify(revert('MG-03.valid-reversal', 'reverted', { marker: 0, history: 0 }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-03.1 fails when a reported revert leaves the marker', () => {
  const result = classify(revert('MG-03.valid-reversal', 'reverted', { marker: 1, history: 0 }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-03\.1/)
})

test('MG-03.no-reversal fails when the revert reports success and the marker remains', () => {
  const result = classify(revert('MG-03.no-reversal', 'reverted', { marker: 1, history: 0 }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-03\.2/)
})

test('MG-03.no-reversal passes when the revert refuses and leaves the marker and the history entry', () => {
  const result = classify(revert('MG-03.no-reversal', 'refused', { marker: 1, history: 1 }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-03.failing-reversal passes when the failure leaves the history entry and the marker', () => {
  const result = classify(revert('MG-03.failing-reversal', 'failed', { marker: 1, history: 1 }), catalog.statements)
  assert.equal(result.classification, 'PASS')
})

test('MG-03.3 fails when a failed reversal drops the history entry', () => {
  const result = classify(revert('MG-03.failing-reversal', 'failed', { marker: 1, history: 0 }), catalog.statements)
  assert.equal(result.classification, 'FAIL')
  assert.match(result.reason, /MG-03\.3/)
})
