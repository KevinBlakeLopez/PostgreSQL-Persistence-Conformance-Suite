// PR-01's harness classification is evidence completeness, not a judgment that a resolved
// commit was the right report. A resolved call over an aborted transaction can still PASS here.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classify } from '../../lib/classify.mjs'

const PID = 10
const HARNESS = { timedOut: false, timeoutMs: 60000, helloReceived: true, exit: { code: 0, signal: null }, protocolErrors: [], missingCheckpoints: [] }
const inTx = { pid: PID, present: true, state: 'idle in transaction', in_transaction: true, backend_xid: '700', xid_matches: true, backend_start: 'T0', query: 'insert into item', application_name: 'ppcs-adapter' }
const aborted = { pid: PID, present: true, state: 'idle in transaction (aborted)', in_transaction: true, backend_xid: null, xid_matches: null, backend_start: 'T0', query: 'insert into uniq', application_name: 'ppcs-adapter' }
const idle = { pid: PID, present: true, state: 'idle', in_transaction: false, backend_xid: null, xid_matches: null, backend_start: 'T0', query: 'COMMIT', application_name: 'ppcs-adapter' }
const wrote = { wrote_item: true, xids: ['700'] }

const kase = {
  id: 'PR-01.managed-catch-commit',
  family: 'PR-01',
  invariants: ['PR-01.1'],
  markers: ['tx', 'reuse'],
  marker_writes: {
    tx: { transaction: 'tx', level: 'top', sent: 'after-write' },
    reuse: { transaction: 'reuse', level: 'top', sent: 'possibly-pending' },
  },
  checkpoints: { 'after-write': { captures: 'tx' }, 'before-end': {}, 'after-api': {}, 'reuse-after-write': { captures: 'reuse', optional: true } },
  settings: { pool_max: 2 },
  fault: { category: 'A' },
}

function evidence(over = {}) {
  return {
    case: kase,
    adapterStatus: 'completed',
    reported: 'committed',
    apiError: null,
    steps: { violation: { code: '23505' } },
    observed: {
      checkpoints: {
        'after-write': { reported: { pid: PID, xid: '700' }, session: inTx, locks: wrote, transactions_now: { tx: { fate: 'in progress', session: inTx } }, adapter_sessions: 1 },
        'before-end': { reported: { pid: PID, xid: null }, session: aborted, locks: { wrote_item: false, xids: [] }, transactions_now: { tx: { fate: 'aborted', session: aborted } }, adapter_sessions: 1 },
        'after-api': { reported: { pid: PID, xid: null }, session: idle, locks: null, transactions_now: { tx: { fate: 'aborted', session: idle } }, adapter_sessions: 1 },
        'after-end': { reported: { pid: null, xid: null }, session: null, locks: null, transactions_now: { tx: { fate: 'aborted', session: idle } }, adapter_sessions: 0 },
      },
      transactions: { tx: { xid: '700', pid: PID, captured_at: 'after-write', session_xid_matches: true, backend_start: 'T0', fate: 'aborted' } },
      markers: { tx: false, reuse: false },
      marker_xmin: { tx: null, reuse: null },
      stray_rows: [],
      sessions_at_end: [],
      fixture: { before: 'fx', after: 'fx' },
    },
    adapter: { rollbackClaimChannels: [] },
    harness: HARNESS,
    ...over,
  }
}

const statements = { 'PR-01.1': 'recorded' }

test('PR-01 records a resolved call over an aborted transaction as complete evidence', () => {
  const result = classify(evidence(), statements)
  assert.equal(result.classification, 'PASS')
  assert.equal(result.mechanism_exercised, true)
})

test('PR-01 is inconclusive when the marker is visible but the transaction aborted', () => {
  const ev = evidence()
  ev.observed.markers.tx = true
  ev.observed.marker_xmin.tx = '700'
  const result = classify(ev, statements)
  assert.equal(result.classification, 'INCONCLUSIVE')
  assert.match(result.reason, /visibility agrees|visible/)
})
