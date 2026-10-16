// Unit tests for the classification rules (harness/lib/classify.mjs). No database: evidence is built by hand.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classify } from '../../lib/classify.mjs'
import { loadCatalog } from '../../lib/catalog.mjs'

const catalog = loadCatalog()
const caseById = (id) => catalog.cases.find((c) => c.id === id)

/** Evidence for a completed single-transaction case; `over` replaces parts of it. */
function evidence(caseId, over = {}) {
  const base = {
    case: caseById(caseId),
    adapterStatus: 'completed',
    reported: 'committed',
    steps: {},
    observed: {
      checkpoints: { 'before-end': { reported: { pid: 10, xid: '700' }, session: { present: true, state: 'idle in transaction' } } },
      transactions: { tx: { xid: '700', pid: 10, captured_at: 'before-end', session_xid_matches: true, fate: 'committed' } },
      markers: { tx: true },
      sessions_at_end: [],
    },
    harness: { timedOut: false, timeoutMs: 60000, helloReceived: true, exit: { code: 0, signal: null }, protocolErrors: [], missingCheckpoints: [] },
  }
  const observed = { ...base.observed, ...over.observed, transactions: { tx: { ...base.observed.transactions.tx, ...over.observed?.transactions?.tx } } }
  // A visible marker was inserted by transaction tx; an invisible one has no row, so no xmin.
  if (!over.observed?.marker_xmin) observed.marker_xmin = Object.fromEntries(Object.entries(observed.markers ?? {}).map(([k, v]) => [k, v ? observed.transactions.tx.xid : null]))
  return { ...base, ...over, observed, harness: { ...base.harness, ...over.harness } }
}
const run = (ev) => classify(ev, catalog.statements)

test('a genuinely committed marker is detected: CTL-01.commit passes', () => {
  assert.equal(run(evidence('CTL-01.commit')).classification, 'PASS')
})

test('a genuinely rolled-back marker is absent: CTL-01.rollback passes', () => {
  const r = run(evidence('CTL-01.rollback', { reported: 'rolled_back', observed: { markers: { tx: false }, transactions: { tx: { fate: 'aborted' } } } }))
  assert.equal(r.classification, 'PASS')
})

test('a report the database contradicts is a FAIL', () => {
  const r = run(evidence('CTL-01.commit', { observed: { markers: { tx: false }, transactions: { tx: { fate: 'aborted' } } } }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.reason, /CTL-01\.1 violated/)
})

test('a missing observation is never PASS: unknown pg_xact_status()', () => {
  for (const fate of [null, 'in progress']) {
    const r = run(evidence('CTL-01.commit', { observed: { transactions: { tx: { fate } } } }))
    assert.equal(r.classification, 'INCONCLUSIVE', String(fate))
  }
})

test('a missing observation is never PASS: transaction ID not captured, checkpoint missing, markers unreadable', () => {
  assert.equal(run(evidence('CTL-01.commit', { observed: { transactions: { tx: { xid: null } } } })).classification, 'INCONCLUSIVE')
  assert.equal(run(evidence('CTL-01.commit', { harness: { missingCheckpoints: ['before-end'] } })).classification, 'INCONCLUSIVE')
  assert.equal(run(evidence('CTL-01.commit', { observed: { markers: null, markersError: 'relation "item" does not exist' } })).classification, 'INCONCLUSIVE')
})

test('a reported commit whose marker is not visible is a FAIL (a lost write), never PASS', () => {
  const r = run(evidence('CTL-01.commit', { observed: { markers: { tx: false } } }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.reason, /CTL-01\.1 violated/)
})

test('a visible row inserted by a transaction PostgreSQL reports aborted means the observations are wrong: INCONCLUSIVE', () => {
  const r = run(evidence('CTL-01.commit', { observed: { markers: { tx: true }, marker_xmin: { tx: '700' }, transactions: { tx: { fate: 'aborted' } } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /inserted by transaction "tx" \(xid 700\), which pg_xact_status\(\) reports as aborted/)
})

test('a transaction ID that does not match its session is INCONCLUSIVE', () => {
  assert.equal(run(evidence('CTL-01.commit', { observed: { transactions: { tx: { session_xid_matches: false } } } })).classification, 'INCONCLUSIVE')
})

test('a timeout is never success', () => {
  const r = run(evidence('CTL-01.commit', { adapterStatus: null, reported: null, harness: { timedOut: true, exit: { code: null, signal: 'SIGKILL' } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /did not finish within/)
})

test('an adapter error or protocol error is INCONCLUSIVE', () => {
  assert.equal(run(evidence('CTL-01.commit', { adapterStatus: 'error', adapterError: 'Error: boom' })).classification, 'INCONCLUSIVE')
  assert.equal(run(evidence('CTL-01.commit', { harness: { protocolErrors: ['unknown message type "x"'] } })).classification, 'INCONCLUSIVE')
  assert.equal(run(evidence('CTL-01.commit', { harness: { helloReceived: false } })).classification, 'INCONCLUSIVE')
})

test('an unsupported capability is UNSUPPORTED, never FAIL', () => {
  const r = run(evidence('TX-01A.caught-error-then-commit', { adapterStatus: 'unsupported', adapterReason: 'no such API', reported: 'committed', observed: { markers: { tx: false }, transactions: { tx: { fate: 'aborted' } } } }))
  assert.equal(r.classification, 'UNSUPPORTED')
})

// TX-01A: evidence of an aborted transaction whose end the framework reported as `reported`.
function aborted(reported, { state = 'idle in transaction (aborted)', violation = '23505' } = {}) {
  return evidence('TX-01A.caught-error-then-commit', {
    reported,
    steps: { violation: { code: violation } },
    observed: {
      checkpoints: {
        'after-write': { reported: { pid: 10, xid: '700' }, session: { present: true, state: 'idle in transaction' } },
        'before-end': { reported: { pid: 10, xid: null }, session: { present: true, state } },
      },
      transactions: { tx: { captured_at: 'after-write', fate: 'aborted' } },
      markers: { tx: false },
    },
  })
}

test('TX-01A: reporting a commit of an aborted transaction is a FAIL', () => {
  const r = run(aborted('committed'))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-01A.1' && i.holds === false))
})

test('TX-01A: reporting a rollback or a failure passes', () => {
  assert.equal(run(aborted('rolled_back')).classification, 'PASS')
  assert.equal(run(aborted('failed')).classification, 'PASS')
})

test('TX-01A: without the aborted state, the invariant does not apply (INCONCLUSIVE, even if a commit is reported)', () => {
  assert.equal(run(aborted('committed', { state: 'idle in transaction' })).classification, 'INCONCLUSIVE')
  assert.equal(run(aborted('committed', { violation: null })).classification, 'INCONCLUSIVE')
})

// TX-01B: evidence of a commit whose reply the client never received.
function unknown(caseId, reported, { fate, terminated = true, gone = true, fired = 1 } = {}) {
  const kase = caseById(caseId)
  const isB = kase.fault.category === 'B'
  const f = fate ?? kase.expected.fate
  return evidence(caseId, {
    reported,
    steps: isB ? {} : { fault: { mode: 'reply-lost', fired } },
    observed: {
      checkpoints: { 'before-end': { reported: { pid: 10, xid: '700' }, session: { present: true, state: 'idle in transaction' }, ...(isB ? { action: { action: 'terminate_backend', pid: 10, terminated, gone } } : {}) } },
      transactions: { tx: { fate: f } },
      markers: { tx: f === 'committed' },
    },
  })
}

test('TX-01B: an unknown outcome reported as success is a FAIL, whatever PostgreSQL did', () => {
  for (const id of ['TX-01B.conn-lost-before-commit', 'TX-01B.commit-reply-discarded']) {
    const r = run(unknown(id, 'committed'))
    assert.equal(r.classification, 'FAIL', id)
    assert.ok(r.invariants.some((i) => i.id === 'TX-01B.1' && i.holds === false), id)
  }
})

test('TX-01B: an unknown outcome is not converted to a confirmed rollback', () => {
  for (const id of ['TX-01B.conn-lost-before-commit', 'TX-01B.commit-reply-discarded']) {
    const r = run(unknown(id, 'rolled_back'))
    assert.equal(r.classification, 'FAIL', id)
    assert.ok(r.invariants.some((i) => i.id === 'TX-01B.2' && i.holds === false), id)
  }
})

test('TX-01B: reporting a failure without asserting an outcome passes', () => {
  assert.equal(run(unknown('TX-01B.conn-lost-before-commit', 'failed')).classification, 'PASS')
  assert.equal(run(unknown('TX-01B.commit-reply-discarded', 'failed')).classification, 'PASS')
})

test('TX-01B: a fault that did not take effect makes the case INCONCLUSIVE', () => {
  assert.equal(run(unknown('TX-01B.conn-lost-before-commit', 'committed', { terminated: false, gone: false })).classification, 'INCONCLUSIVE')
  assert.equal(run(unknown('TX-01B.conn-lost-before-commit', 'committed', { gone: false })).classification, 'INCONCLUSIVE')
  assert.equal(run(unknown('TX-01B.commit-reply-discarded', 'committed', { fired: 0 })).classification, 'INCONCLUSIVE')
})

// TX-03: unit 1 failed (and its rollback failed); unit 2 is the next unit of work on the same pool.
function reuse(caseId, { unit1Fate = 'aborted', unit2 = { xid: '701', fate: 'committed' }, next = { outcome: 'completed', reported: 'committed', elapsed_ms: 10 }, doomed = false, nextVisible = true, fired = 1 } = {}) {
  const kase = caseById(caseId)
  const transactions = { unit1: { xid: '700', pid: 10, captured_at: 'unit1-after-write', session_xid_matches: true, fate: unit1Fate } }
  if (unit2) transactions.unit2 = { pid: 10, captured_at: 'unit2-after-write', session_xid_matches: true, ...unit2 }
  const isB = kase.fault.category === 'B'
  return {
    ...evidence(caseId),
    reported: 'rolled_back',
    steps: { unit2: next, ...(isB ? {} : { fault: { mode: 'client-reject', fired } }) },
    observed: {
      checkpoints: { 'unit1-after-write': { reported: { pid: 10, xid: '700' }, ...(isB ? { action: { action: 'terminate_backend', pid: 10, terminated: true, gone: true } } : {}) }, 'after-unit1': { reported: { pid: 10 } } },
      transactions,
      markers: { doomed, next: nextVisible },
      sessions_at_end: [],
    },
  }
}

test('TX-03: the next unit running inside the failed transaction is a FAIL of TX-03.1', () => {
  const r = run(reuse('TX-03.rollback-not-sent', { unit1Fate: 'committed', unit2: { xid: '700', fate: 'committed' }, doomed: true }))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-03.1' && i.holds === false))
})

test('TX-03: a next unit still pending at the bound is a FAIL of TX-03.2, not INCONCLUSIVE', () => {
  const r = run(reuse('TX-03.conn-lost-in-transaction', { unit2: null, next: { outcome: 'pending', elapsed_ms: 5000 }, nextVisible: false }))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-03.2' && i.holds === false))
  assert.ok(r.invariants.some((i) => i.id === 'TX-03.1' && i.holds === true))
})

test('TX-03: a fresh transaction for the next unit, and the failed one rolled back, passes', () => {
  assert.equal(run(reuse('TX-03.rollback-not-sent')).classification, 'PASS')
  assert.equal(run(reuse('TX-03.conn-lost-in-transaction')).classification, 'PASS')
})

test('TX-03: a client-side fault that never fired makes the case INCONCLUSIVE', () => {
  assert.equal(run(reuse('TX-03.rollback-not-sent', { fired: 0 })).classification, 'INCONCLUSIVE')
})

// TX-02: an outer transaction whose nested scope failed, and whose savepoint rollback failed.
function savepointCase(caseId, { reported = 'committed', fate = 'committed', outer = true, inner = false, after = { present: true, state: 'idle', in_transaction: false }, caught = true, fired = 1 } = {}) {
  const kase = caseById(caseId)
  const isB = kase.fault.category === 'B'
  return {
    ...evidence(caseId),
    reported,
    steps: { nested: { caught, error: caught ? { class: 'Error' } : undefined }, ...(isB ? {} : { fault: { mode: 'client-reject', fired } }) },
    observed: {
      checkpoints: {
        'outer-after-write': { reported: { pid: 10, xid: '700' } },
        ...(isB ? { 'inner-after-write': { reported: { pid: 10 }, action: { action: 'terminate_backend', pid: 10, terminated: true, gone: true } } } : {}),
        'after-outer': { reported: { pid: 10 }, session: after },
      },
      transactions: { tx: { xid: '700', pid: 10, captured_at: 'outer-after-write', session_xid_matches: true, fate } },
      markers: { outer, inner },
      sessions_at_end: [],
    },
  }
}

test('TX-02: a reported commit that includes the failed scope\'s writes is a FAIL of TX-02.1', () => {
  const r = run(savepointCase('TX-02.savepoint-rollback-not-sent', { inner: true }))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-02.1' && i.holds === false))
})

test('TX-02: a connection left inside a transaction after the API returned is a FAIL of TX-02.2, even when the failure was reported', () => {
  const r = run(savepointCase('TX-02.savepoint-rollback-rejected', { reported: 'failed', fate: 'aborted', outer: false, after: { present: true, state: 'idle in transaction', in_transaction: true } }))
  assert.equal(r.classification, 'FAIL')
  assert.deepEqual(r.invariants.filter((i) => i.holds === false).map((i) => i.id), ['TX-02.2'])
})

test('TX-02: a failure reported, nothing committed, and the connection out of its transaction passes', () => {
  assert.equal(run(savepointCase('TX-02.savepoint-rollback-rejected', { reported: 'rolled_back', fate: 'aborted', outer: false })).classification, 'PASS')
  assert.equal(run(savepointCase('TX-02.conn-lost-before-savepoint-rollback', { reported: 'failed', fate: 'aborted', outer: false, after: { present: false } })).classification, 'PASS')
})

test('TX-02: without the nested failure reaching the outer scope, or without the session observation, INCONCLUSIVE', () => {
  assert.equal(run(savepointCase('TX-02.savepoint-rollback-not-sent', { caught: false })).classification, 'INCONCLUSIVE')
  assert.equal(run(savepointCase('TX-02.savepoint-rollback-not-sent', { after: null })).classification, 'INCONCLUSIVE')
})

// TX-04: nested and independent scopes, no fault.
function nestedCase(caseId, { reported, fate, outer, inner, nested, innerTx } = {}) {
  const kase = caseById(caseId)
  const transactions = innerTx ? { inner: { xid: '800', pid: 11, captured_at: 'inner-after-write', session_xid_matches: true, fate: innerTx } } : { tx: { xid: '700', pid: 10, captured_at: 'inner-after-write', session_xid_matches: true, fate } }
  return {
    ...evidence(caseId),
    case: kase,
    reported,
    steps: { nested },
    observed: { checkpoints: { 'inner-after-write': { reported: { pid: 10, xid: '700' } } }, transactions, markers: { outer, inner }, marker_xmin: { outer: outer ? '800' : null, inner: inner ? '800' : null }, sessions_at_end: [] },
  }
}

test('TX-04.1: a caller write lost with the failed nested scope is a FAIL', () => {
  const r = run(nestedCase('TX-04.nested-failure-contained', { reported: 'committed', fate: 'committed', outer: false, inner: false, nested: { caught: true } }))
  assert.equal(r.classification, 'FAIL')
})

test('TX-04.2: a released nested scope surviving the outer rollback is a FAIL', () => {
  const r = run(nestedCase('TX-04.nested-released-outer-rollback', { reported: 'rolled_back', fate: 'aborted', outer: false, inner: true, nested: { completed: true } }))
  assert.equal(r.classification, 'FAIL')
})

test('TX-04.3: an outer write committed by the independent inner transaction is a FAIL, and is attributed by xmin', () => {
  const r = run(nestedCase('TX-04.independent-inner', { reported: 'rolled_back', outer: true, inner: true, nested: { completed: true }, innerTx: 'committed' }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.invariants[0].detail, /inserted by transaction 800, the inner transaction/)
})

test('TX-04: the promised boundaries passes', () => {
  assert.equal(run(nestedCase('TX-04.nested-failure-contained', { reported: 'committed', fate: 'committed', outer: true, inner: false, nested: { caught: true } })).classification, 'PASS')
  assert.equal(run(nestedCase('TX-04.nested-released-outer-rollback', { reported: 'rolled_back', fate: 'aborted', outer: false, inner: false, nested: { completed: true } })).classification, 'PASS')
  assert.equal(run(nestedCase('TX-04.independent-inner', { reported: 'rolled_back', outer: false, inner: true, nested: { completed: true }, innerTx: 'committed' })).classification, 'PASS')
})

test('an unexpected adapter status (for example not_implemented) is INCONCLUSIVE, never evaluated', () => {
  const r = run(evidence('TX-01A.caught-error-then-commit', { adapterStatus: 'not_implemented', adapterReason: 'no such case', reported: null, observed: { transactions: {} } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /status "not_implemented"/)
})
