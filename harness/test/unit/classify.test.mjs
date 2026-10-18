// Unit tests for the classification rules (harness/lib/classify.mjs). No database: evidence is built by hand, in the
// shape run-case.mjs assembles. Tests named H1 to H9 port the harness counterexamples of the independent methodology
// review (ppcs-methodology-review, evidence/harness-counterexamples.mjs); each must now give the result it calls for.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classify, fateStory } from '../../lib/classify.mjs'
import { loadCatalog } from '../../lib/catalog.mjs'

const catalog = loadCatalog()
const kase = (id) => catalog.cases.find((c) => c.id === id)
const run = (ev) => classify(ev, catalog.statements)

const PID = 10
const API_ERROR = { class: 'Error', code: null, message: 'raised by the API' }
const HARNESS = { timedOut: false, timeoutMs: 60000, helloReceived: true, exit: { code: 0, signal: null }, protocolErrors: [], missingCheckpoints: [] }

// Sessions as Observer.session() reports them.
const inTx = (xid, extra = {}) => ({ pid: PID, present: true, state: 'idle in transaction', in_transaction: true, backend_xid: xid, xid_matches: null, backend_start: 'T0', query: 'insert into item', application_name: 'ppcs-adapter', ...extra })
const aborted = (extra = {}) => ({ pid: PID, present: true, state: 'idle in transaction (aborted)', in_transaction: true, backend_xid: null, xid_matches: null, backend_start: 'T0', query: 'insert into uniq', application_name: 'ppcs-adapter', ...extra })
const idle = (query, extra = {}) => ({ pid: PID, present: true, state: 'idle', in_transaction: false, backend_xid: null, xid_matches: null, backend_start: 'T0', query, application_name: 'ppcs-adapter', ...extra })
const closed = { pid: PID, present: false }
// Locks as Observer.locks() reports them.
const wrote = (...xids) => ({ wrote_item: true, xids })
const noWrite = (...xids) => ({ wrote_item: false, xids })

/** A checkpoint entry as run-case.mjs records it. `now` maps transaction labels to [fate, session]. */
function point({ pid = PID, xid = null, session = null, locks = null, now = {}, sessions = 1, action } = {}) {
  return {
    reported: { pid, xid },
    session,
    locks,
    transactions_now: Object.fromEntries(Object.entries(now).map(([label, [fate, s]]) => [label, { fate, session: s }])),
    adapter_sessions: sessions,
    ...(action ? { action } : {}),
  }
}

/** Replaces parts of `base`: objects merge recursively; arrays, nulls and other values replace. */
function merge(base, over) {
  if (over === undefined) return base
  if (over === null || typeof over !== 'object' || Array.isArray(over) || base === null || typeof base !== 'object' || Array.isArray(base)) return over
  const out = { ...base }
  for (const [k, v] of Object.entries(over)) out[k] = merge(base[k], v)
  return out
}

/** Complete evidence for case `id`: the case's normal, passing run, with `over` merged in. */
function evidence(id, observed, rest = {}, over = {}) {
  const base = {
    case: kase(id),
    adapterStatus: 'completed',
    adapterReason: null,
    adapterError: null,
    reported: 'committed',
    apiError: null,
    steps: {},
    observed: { markers: {}, marker_xmin: {}, stray_rows: [], sessions_at_end: [], fixture: { before: 'fx', after: 'fx' }, ...observed },
    adapter: { rollbackClaimChannels: [] },
    harness: HARNESS,
    ...rest,
  }
  return merge(base, over)
}

const tx = (xid, capturedAt, fate, extra = {}) => ({ xid, pid: PID, captured_at: capturedAt, session_xid_matches: true, backend_start: 'T0', fate, ...extra })

// CTL-01: one transaction writes the marker, then commits or rolls back.
function ctl(id, over = {}) {
  const commit = id === 'CTL-01.commit'
  const fate = commit ? 'committed' : 'aborted'
  return evidence(id, {
    checkpoints: {
      'before-end': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: wrote('700'), now: { tx: ['in progress', inTx('700')] } }),
      'after-end': point({ pid: null, now: { tx: [fate, idle(commit ? 'COMMIT' : 'ROLLBACK')] } }),
    },
    transactions: { tx: tx('700', 'before-end', fate) },
    markers: { tx: commit },
    marker_xmin: { tx: commit ? '700' : null },
  }, { reported: commit ? 'committed' : 'rolled_back', apiError: commit ? null : API_ERROR }, over)
}

test('CTL-01: a genuinely committed marker passes, and a genuinely rolled-back one passes', () => {
  assert.equal(run(ctl('CTL-01.commit')).classification, 'PASS')
  assert.equal(run(ctl('CTL-01.rollback')).classification, 'PASS')
})

test('CTL-01: a report the database contradicts is a FAIL', () => {
  const r = run(ctl('CTL-01.commit', { observed: { transactions: { tx: { fate: 'aborted' } }, checkpoints: { 'after-end': { transactions_now: { tx: { fate: 'aborted' } } } }, markers: { tx: false }, marker_xmin: { tx: null } } }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.reason, /CTL-01\.1 violated/)
})

test('a reported commit whose confirmed write is not visible is a FAIL (a lost write)', () => {
  const r = run(ctl('CTL-01.commit', { observed: { markers: { tx: false }, marker_xmin: { tx: null } } }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.reason, /CTL-01\.1 violated/)
})

test('a missing marker whose write was never confirmed is INCONCLUSIVE, not a lost write', () => {
  const r = run(ctl('CTL-01.commit', { observed: { checkpoints: { 'before-end': { locks: noWrite('700') } }, markers: { tx: false }, marker_xmin: { tx: null } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /write of marker "tx" had reached PostgreSQL at `before-end`/)
})

test('rows in the marker table that are not markers make the case INCONCLUSIVE', () => {
  const r = run(ctl('CTL-01.commit', { observed: { stray_rows: ['tx-wrong'], markers: { tx: false }, marker_xmin: { tx: null } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /not the case's markers/)
})

test('a missing observation is never PASS: unknown fate, uncaptured ID, missing checkpoint, unreadable markers', () => {
  const inconclusive = (ev, reason) => { const r = run(ev); assert.equal(r.classification, 'INCONCLUSIVE'); assert.match(r.reason, reason) }
  for (const fate of [null, 'in progress']) inconclusive(ctl('CTL-01.commit', { observed: { transactions: { tx: { fate } } } }), /pg_xact_status\(\) for transaction "tx" is/)
  inconclusive(ctl('CTL-01.commit', { observed: { transactions: { tx: { xid: null } } } }), /was not captured inside it/)
  inconclusive(ctl('CTL-01.commit', { harness: { missingCheckpoints: ['after-end'] } }), /checkpoint "after-end" was not reached/)
  inconclusive(ctl('CTL-01.commit', { observed: { markers: null, markersError: 'relation "item" does not exist' } }), /marker visibility could not be read/)
})

test('a visible row inserted by a transaction PostgreSQL reports aborted means the observations are wrong', () => {
  const r = run(ctl('CTL-01.commit', { observed: { transactions: { tx: { fate: 'aborted' } } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /inserted by transaction "tx" \(xid 700\), which pg_xact_status\(\) reports as aborted/)
})

test('binding: a transaction ID that is not its session\'s transaction is INCONCLUSIVE', () => {
  for (const [why, over] of [
    ['xid mismatch', { observed: { transactions: { tx: { session_xid_matches: false } } } }],
    ['xid not compared', { observed: { transactions: { tx: { session_xid_matches: null } } } }],
    ['session not in a transaction', { observed: { checkpoints: { 'before-end': { session: idle('select pg_current_xact_id()') } } } }],
    ['no such session', { observed: { checkpoints: { 'before-end': { session: closed } } } }],
  ]) {
    const r = run(ctl('CTL-01.commit', over))
    assert.equal(r.classification, 'INCONCLUSIVE', why)
    assert.match(r.reason, /not bound/, why)
  }
})

test('H1: an escaped checkpoint (an autocommit xid; the marker inserted by another transaction) is INCONCLUSIVE', () => {
  const r = run(ctl('CTL-01.commit', { observed: {
    checkpoints: { 'before-end': { session: idle('select pg_current_xact_id()', { xid_matches: null }), locks: wrote('809') } },
    transactions: { tx: { xid: '810', session_xid_matches: null } },
    marker_xmin: { tx: '809' },
  } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /not bound/)
  assert.match(r.reason, /inserted by transaction 809, not by the case's transaction "tx"/)
})

test('attribution: a visible top-level marker inserted by a different transaction is INCONCLUSIVE', () => {
  const r = run(ctl('CTL-01.commit', { observed: { marker_xmin: { tx: '699' } } }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /inserted by transaction 699/)
})

test('a timeout, an adapter error, a protocol error or a missing hello is never a result', () => {
  assert.match(run(ctl('CTL-01.commit', { adapterStatus: null, reported: null, harness: { timedOut: true, exit: { code: null, signal: 'SIGKILL' } } })).reason, /did not finish within/)
  assert.match(run(ctl('CTL-01.commit', { adapterStatus: 'error', adapterError: 'Error: boom' })).reason, /the adapter reported an error: Error: boom/)
  assert.match(run(ctl('CTL-01.commit', { harness: { protocolErrors: ['unknown message type "x"'] } })).reason, /protocol: unknown message type/)
  assert.match(run(ctl('CTL-01.commit', { harness: { helloReceived: false } })).reason, /no hello message/)
})

test('H4: a runtime "unsupported" never overrides the evidence: INCONCLUSIVE', () => {
  const r = run(evidence('TX-01A.caught-error-then-commit', { checkpoints: {}, transactions: {}, markers: null, marker_xmin: null }, {
    adapterStatus: 'unsupported', adapterReason: 'not today', reported: null,
    harness: { ...HARNESS, protocolErrors: ['the adapter reported "unsupported" at run time; only its manifest may declare a case unsupported'], missingCheckpoints: [] },
  }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /only its manifest may declare a case unsupported/)
})

test('H9: an adapter status the classifier does not know (not_implemented) is INCONCLUSIVE', () => {
  const r = run(evidence('CTL-01.commit', { checkpoints: {}, transactions: {}, markers: { tx: false }, marker_xmin: { tx: null } }, { adapterStatus: 'not_implemented', adapterReason: 'no such case', reported: null }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /status "not_implemented"/)
})

test('H6: "failed" or "rolled_back" without the error the API raised is INCONCLUSIVE; so are "pending" and unknown outcomes', () => {
  assert.match(run(ctl('CTL-01.rollback', { apiError: null })).reason, /without the error the API raised/)
  assert.match(run(txA('failed', { apiError: null })).reason, /reported "failed" without the error the API raised/)
  assert.match(run(ctl('CTL-01.commit', { reported: 'pending' })).reason, /had not returned/)
  assert.match(run(ctl('CTL-01.commit', { reported: 'maybe' })).reason, /did not report the API outcome/)
})

test('H5: invariants the rules do not evaluate are never passed over: INCONCLUSIVE', () => {
  const ev = txA('rolled_back')
  ev.case = { ...ev.case, invariants: ['TX-01A.1', 'CTL-01.2'] }
  const r = run(ev)
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /CTL-01\.2/)
})

test('runner robustness: leftover sessions, too many sessions, another backend under the same PID, a changed fixture', () => {
  assert.match(run(ctl('CTL-01.commit', { observed: { sessions_at_end: [{ pid: 11 }] } })).reason, /still connected/)
  assert.match(run(ctl('CTL-01.commit', { observed: { checkpoints: { 'before-end': { adapter_sessions: 2 } } } })).reason, /more than pool_max \(1\)/)
  assert.match(run(ctl('CTL-01.commit', { observed: { transactions: { tx: { backend_start: 'T1' } } } })).reason, /belongs to a different backend/)
  assert.match(run(ctl('CTL-01.commit', { observed: { fixture: { after: 'changed' } } })).reason, /fixture's tables or constraints changed/)
})

// TX-01A: the write, a caught unique violation, then the end of the callback.
function txA(reported, { state = aborted(), fateBefore = 'aborted', violation = '23505', after = idle('COMMIT'), apiError, ...over } = {}) {
  return evidence('TX-01A.caught-error-then-commit', {
    checkpoints: {
      'after-write': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: wrote('700'), now: { tx: ['in progress', inTx('700')] } }),
      'before-end': point({ session: state, locks: noWrite(), now: { tx: [fateBefore, state] } }),
      'after-end': point({ pid: null, now: { tx: ['aborted', after] } }),
    },
    transactions: { tx: tx('700', 'after-write', 'aborted') },
    markers: { tx: false },
    marker_xmin: { tx: null },
  }, { reported, apiError: apiError !== undefined ? apiError : reported === 'committed' ? null : API_ERROR, steps: { violation: violation ? { code: violation } : undefined } }, over)
}

test('TX-01A: reporting a commit of an aborted transaction is a FAIL, and the mechanism ran', () => {
  const r = run(txA('committed'))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-01A.1' && i.holds === false))
  assert.equal(r.mechanism_exercised, true)
})

test('TX-01A: reporting a rollback or a failure after COMMIT passes, with the mechanism exercised', () => {
  for (const reported of ['rolled_back', 'failed']) {
    const r = run(txA(reported))
    assert.equal(r.classification, 'PASS', reported)
    assert.equal(r.mechanism_exercised, true, reported)
  }
})

test('H3: a failure before COMMIT was sent passes, but is recorded as "mechanism not exercised"', () => {
  for (const after of [idle('ROLLBACK'), aborted({ query: 'select 1' })]) {
    const r = run(txA('failed', { after }))
    assert.equal(r.classification, 'PASS')
    assert.equal(r.mechanism_exercised, false)
    assert.match(r.mechanism_detail, /last statement/)
  }
})

test('TX-01A: without the aborted state before the end, or without the violation, INCONCLUSIVE', () => {
  assert.match(run(txA('committed', { state: inTx('700'), fateBefore: 'in progress' })).reason, /precondition not established: the top-level transaction was aborted before it ended/)
  assert.match(run(txA('committed', { violation: null })).reason, /precondition not established: the duplicate insert failed with unique_violation/)
})

// TX-01B: the commit's outcome reaches the client only through what the API reports.
function txB(id, reported, { fate, reportFate, terminated = true, gone = true, fired = 1, channels = [] } = {}) {
  const c = kase(id)
  const isB = c.fault.category === 'B'
  const f = fate ?? c.expected.fate
  return evidence(id, {
    checkpoints: {
      'before-end': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: wrote('700'), now: { tx: ['in progress', inTx('700')] }, ...(isB ? { action: { action: 'terminate_backend', pid: PID, terminated, gone } } : {}) }),
      'after-end': point({ pid: null, sessions: isB ? 0 : 1, now: { tx: [reportFate ?? f, isB ? closed : idle('COMMIT')] } }),
    },
    transactions: { tx: tx('700', 'before-end', f) },
    markers: { tx: f === 'committed' },
    marker_xmin: { tx: f === 'committed' ? '700' : null },
  }, { reported, apiError: reported === 'committed' ? null : API_ERROR, steps: isB ? {} : { fault: { mode: 'reply-lost', fired } }, adapter: { rollbackClaimChannels: channels } })
}

test('TX-01B: a commit reported after the connection or the reply was lost is a FAIL of TX-01B.1', () => {
  for (const id of ['TX-01B.conn-lost-before-commit', 'TX-01B.commit-reply-discarded']) {
    const r = run(txB(id, 'committed'))
    assert.equal(r.classification, 'FAIL', id)
    assert.ok(r.invariants.some((i) => i.id === 'TX-01B.1' && i.holds === false), id)
  }
})

test('H2: conn-lost-before-commit is a known outcome, so a truthful "rolled_back" passes', () => {
  const r = run(txB('TX-01B.conn-lost-before-commit', 'rolled_back'))
  assert.equal(r.classification, 'PASS')
  assert.deepEqual(r.invariants.map((i) => i.id), ['TX-01B.1'])
})

test('TX-01B.2: a confirmed rollback of a commit that may have happened is a FAIL, whatever the declared channels', () => {
  for (const channels of [[], ['result']]) {
    const r = run(txB('TX-01B.commit-reply-discarded', 'rolled_back', { channels }))
    assert.equal(r.classification, 'FAIL', String(channels))
    assert.ok(r.invariants.some((i) => i.id === 'TX-01B.2' && i.holds === false))
  }
})

test('TX-01B.2: without a declared rollback-claim channel, a failure report leaves TX-01B.2 not exercised, never held', () => {
  const r = run(txB('TX-01B.commit-reply-discarded', 'failed'))
  assert.equal(r.classification, 'PASS')
  assert.deepEqual(r.not_exercised, ['TX-01B.2'])
  const i = r.invariants.find((x) => x.id === 'TX-01B.2')
  assert.equal(i.holds, null)
  assert.equal(i.not_exercised, true)
  const withChannel = run(txB('TX-01B.commit-reply-discarded', 'failed', { channels: ['result'] }))
  assert.equal(withChannel.classification, 'PASS')
  assert.deepEqual(withChannel.not_exercised, [])
})

test('TX-01B: a fault that did not take effect, or a fate other than the case produces, is INCONCLUSIVE', () => {
  assert.match(run(txB('TX-01B.conn-lost-before-commit', 'committed', { terminated: false, gone: false })).reason, /the runner terminated the backend at `before-end`/)
  assert.match(run(txB('TX-01B.conn-lost-before-commit', 'committed', { gone: false })).reason, /terminated: true; gone: false/)
  assert.match(run(txB('TX-01B.commit-reply-discarded', 'committed', { fired: 0 })).reason, /fired exactly once \(fired: 0\)/)
  assert.match(run(txB('TX-01B.commit-reply-discarded', 'failed', { reportFate: 'in progress' })).reason, /PostgreSQL's outcome is the one the case produces \(committed\)/)
})

// TX-02: the outer scope writes; a nested scope writes and fails; its savepoint rollback fails.
function txTwo(id, { reported = 'committed', fate = 'committed', reportFate, outer = true, inner = false, after = idle('COMMIT'), faultSession, faultLocks, faultFate = 'in progress', innerLocks = wrote('700', '701'), caught = true, fired = 1, gone = true, replyCodes = ['3B001'] } = {}) {
  const c = kase(id)
  const isB = c.fault.category === 'B'
  const mode = id.endsWith('not-sent') ? 'client-reject' : 'rewrite'
  const atReport = reportFate ?? fate
  const checkpoints = {
    'outer-after-write': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: wrote('700'), now: { tx: ['in progress', inTx('700')] } }),
    'inner-after-write': point({ session: inTx('700'), locks: innerLocks, now: { tx: ['in progress', inTx('700')] }, ...(isB ? { action: { action: 'terminate_backend', pid: PID, terminated: true, gone } } : {}) }),
  }
  if (!isB) {
    // The signature of the fault as it fires: a withheld ROLLBACK TO leaves the savepoint live; a rejected one aborts it.
    const fs = faultSession ?? (mode === 'client-reject' ? inTx('700') : aborted({ backend_xid: '700' }))
    checkpoints['after-fault'] = point({ session: fs, locks: faultLocks ?? (mode === 'client-reject' ? wrote('700', '701') : wrote('700')), now: { tx: [faultFate, fs] } })
  }
  return evidence(id, {
    checkpoints: {
      ...checkpoints,
      'after-outer': point({ session: after, locks: after?.present ? noWrite() : null, now: { tx: [atReport, after] } }),
      'after-end': point({ pid: null, now: { tx: [atReport, after] } }),
    },
    transactions: { tx: tx('700', 'outer-after-write', fate) },
    markers: { outer, inner },
    marker_xmin: { outer: outer ? '700' : null, inner: inner ? '701' : null },
  }, {
    reported,
    apiError: reported === 'committed' ? null : API_ERROR,
    steps: { nested: { caught, error: caught ? { class: 'Error' } : undefined }, ...(isB ? {} : { fault: { mode, fired, ...(mode === 'rewrite' ? { reply_codes: replyCodes } : {}) } }) },
  })
}

test('TX-02: a reported commit that includes the failed scope\'s writes is a FAIL of TX-02.1', () => {
  const r = run(txTwo('TX-02.savepoint-rollback-not-sent', { inner: true }))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-02.1' && i.holds === false))
})

test('H7: a commit reported while the transaction was still open is a FAIL, described as decided at teardown', () => {
  const r = run(txTwo('TX-02.savepoint-rollback-not-sent', { fate: 'aborted', reportFate: 'in progress', outer: false, after: inTx('700', { query: 'RELEASE SAVEPOINT typeorm_1' }) }))
  assert.equal(r.classification, 'FAIL')
  const tx1 = r.invariants.find((i) => i.id === 'TX-02.1')
  assert.equal(tx1.holds, false)
  assert.match(tx1.detail, /open at report time \(`after-outer`: xid 700 in progress\); rolled back at teardown/)
  assert.ok(r.invariants.some((i) => i.id === 'TX-02.2' && i.holds === false))
})

test('TX-02: a session left inside its transaction after the API returned is a FAIL of TX-02.2, even when the failure was reported', () => {
  const r = run(txTwo('TX-02.savepoint-rollback-rejected', { reported: 'failed', fate: 'aborted', reportFate: 'in progress', outer: false, after: aborted({ backend_xid: '700' }) }))
  assert.equal(r.classification, 'FAIL')
  assert.deepEqual(r.invariants.filter((i) => i.holds === false).map((i) => i.id), ['TX-02.2'])
})

test('TX-02: a failure reported, nothing committed, and the session out of its transaction passes', () => {
  assert.equal(run(txTwo('TX-02.savepoint-rollback-rejected', { reported: 'rolled_back', fate: 'aborted', outer: false, after: idle('ROLLBACK') })).classification, 'PASS')
  assert.equal(run(txTwo('TX-02.savepoint-rollback-not-sent', { reported: 'rolled_back', fate: 'aborted', outer: false, after: idle('ROLLBACK') })).classification, 'PASS')
  assert.equal(run(txTwo('TX-02.conn-lost-before-savepoint-rollback', { reported: 'failed', fate: 'aborted', outer: false, after: closed })).classification, 'PASS')
})

test('TX-02: a fault that fired without its effect on the server is INCONCLUSIVE', () => {
  const rejected = { reported: 'rolled_back', fate: 'aborted', outer: false, after: idle('ROLLBACK') }
  // client-reject: as the fault fired, the savepoint's subtransaction lock was already gone
  assert.match(run(txTwo('TX-02.savepoint-rollback-not-sent', { faultLocks: wrote('700') })).reason, /left the savepoint live/)
  // rewrite: PostgreSQL did not reject the rewritten statement, or the rejection did not abort the subtransaction
  assert.match(run(txTwo('TX-02.savepoint-rollback-rejected', { ...rejected, replyCodes: ['ok'] })).reason, /rejected the rewritten ROLLBACK TO SAVEPOINT/)
  assert.match(run(txTwo('TX-02.savepoint-rollback-rejected', { ...rejected, faultSession: inTx('700') })).reason, /aborted only the subtransaction/)
  assert.match(run(txTwo('TX-02.savepoint-rollback-rejected', { ...rejected, faultFate: 'aborted' })).reason, /top-level pg_xact_status: aborted/)
  // termination: the backend had not gone when the adapter resumed
  assert.match(run(txTwo('TX-02.conn-lost-before-savepoint-rollback', { reported: 'failed', fate: 'aborted', outer: false, after: closed, gone: false })).reason, /terminated: true; gone: false/)
  // the fault's own checkpoint could not be reported
  const hook = txTwo('TX-02.savepoint-rollback-not-sent')
  hook.steps.fault.hook_error = 'checkpoint "after-fault": the runner closed the protocol stream'
  assert.match(run(hook).reason, /could not report the fault's checkpoint/)
})

test('TX-02: a framework that reacts to the failed savepoint rollback at once still passes: the signature is read as the fault fires', () => {
  // The outer scope's error handling ran after a framework that rolled the whole transaction back immediately.
  assert.equal(run(txTwo('TX-02.savepoint-rollback-not-sent', { reported: 'rolled_back', fate: 'aborted', outer: false, after: idle('ROLLBACK') })).classification, 'PASS')
})

test('TX-02: without the nested write, the nested failure reaching the outer scope, or the session observation, INCONCLUSIVE', () => {
  assert.match(run(txTwo('TX-02.savepoint-rollback-not-sent', { innerLocks: wrote('700') })).reason, /marker "inner" had reached PostgreSQL/)
  assert.match(run(txTwo('TX-02.savepoint-rollback-not-sent', { caught: false })).reason, /precondition not established: the nested scope's error reached the outer scope/)
  assert.match(run(txTwo('TX-02.savepoint-rollback-not-sent', { after: null })).reason, /observed the transaction's session after the outer API returned/)
})

// TX-03: unit 1 fails and its rollback fails; unit 2 is the next unit of work on the same pool.
function txThree(id, { unit1Fate = 'aborted', u1Session, u1Fate, faultSession = inTx('700'), faultFate = 'in progress', violation, unit2 = { xid: '701', fate: 'committed' }, next = { outcome: 'completed', reported: 'committed', elapsed_ms: 10 }, doomed = false, nextVisible = true, fired = 1 } = {}) {
  const isB = kase(id).fault.category === 'B'
  const atUnit1 = u1Session ?? (isB ? closed : inTx('700'))
  const transactions = { unit1: tx('700', 'unit1-after-write', unit1Fate) }
  const checkpoints = {
    'unit1-after-write': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: wrote('700'), now: { unit1: ['in progress', inTx('700')] }, ...(isB ? { action: { action: 'terminate_backend', pid: PID, terminated: true, gone: true } } : {}) }),
    ...(isB ? {} : { 'after-fault': point({ session: faultSession, locks: faultFate === 'aborted' ? noWrite() : wrote('700'), now: { unit1: [faultFate, faultSession] } }) }),
    'after-unit1': point({ session: atUnit1, locks: isB || !atUnit1.present ? null : wrote('700'), now: { unit1: [u1Fate ?? (isB || !atUnit1.present ? 'aborted' : 'in progress'), atUnit1] } }),
  }
  if (unit2) {
    const pid2 = isB ? 12 : PID
    transactions.unit2 = { ...tx(unit2.xid, 'unit2-after-write', unit2.fate), pid: pid2, backend_start: isB ? 'T2' : 'T0' }
    const s2 = { ...inTx(unit2.xid, { xid_matches: true }), pid: pid2, backend_start: isB ? 'T2' : 'T0' }
    checkpoints['unit2-after-write'] = point({ pid: pid2, xid: unit2.xid, session: s2, locks: wrote(unit2.xid), now: { unit1: [unit2.xid === '700' ? 'in progress' : unit1Fate, atUnit1], unit2: ['in progress', s2] } })
  }
  checkpoints['after-end'] = point({ pid: null, now: { unit1: [unit1Fate, idle('COMMIT')], ...(unit2 ? { unit2: [unit2.fate, idle('COMMIT')] } : {}) } })
  return evidence(id, { checkpoints, transactions, markers: { doomed, next: nextVisible }, marker_xmin: { doomed: doomed ? '700' : null, next: nextVisible ? unit2?.xid ?? null : null } }, {
    reported: 'rolled_back', apiError: API_ERROR, steps: { unit2: next, ...(violation ? { violation: { code: violation } } : {}), ...(isB ? {} : { fault: { mode: 'client-reject', fired } }) },
  })
}

test('TX-03: the next unit running inside the failed transaction is a FAIL of TX-03.1, decided by later work', () => {
  const r = run(txThree('TX-03.rollback-not-sent', { unit1Fate: 'committed', unit2: { xid: '700', fate: 'committed' }, doomed: true }))
  assert.equal(r.classification, 'FAIL')
  const i = r.invariants.find((x) => x.id === 'TX-03.1')
  assert.equal(i.holds, false)
  assert.match(i.detail, /open at report time \(`after-unit1`: xid 700 in progress\); committed by later work in the case/)
})

test('TX-03: a next unit still pending at the bound is a FAIL of TX-03.2, and its checkpoint may be missing', () => {
  const r = run(txThree('TX-03.conn-lost-in-transaction', { unit2: null, next: { outcome: 'pending', elapsed_ms: 5000 }, nextVisible: false }))
  assert.equal(r.classification, 'FAIL')
  assert.ok(r.invariants.some((i) => i.id === 'TX-03.2' && i.holds === false))
  assert.ok(r.invariants.some((i) => i.id === 'TX-03.1' && i.holds === true))
})

test('TX-03: a fresh transaction for the next unit, and the failed one rolled back, passes', () => {
  assert.equal(run(txThree('TX-03.rollback-not-sent')).classification, 'PASS')
  assert.equal(run(txThree('TX-03.conn-lost-in-transaction')).classification, 'PASS')
})

test('TX-03: a fault that never fired, or did not leave unit 1 open on the server as it fired, is INCONCLUSIVE', () => {
  assert.match(run(txThree('TX-03.rollback-not-sent', { fired: 0 })).reason, /fired exactly once \(fired: 0\)/)
  assert.match(run(txThree('TX-03.rollback-not-sent', { faultSession: idle('ROLLBACK') })).reason, /the withheld ROLLBACK left unit 1's transaction open/)
  assert.match(run(txThree('TX-03.rollback-not-sent', { faultSession: inTx('699') })).reason, /backend_xid 699/)
})

test('TX-03: a framework that discards the connection inside its API passes: the signature is read as the fault fires, not when the API returns', () => {
  assert.equal(run(txThree('TX-03.rollback-not-sent', { u1Session: closed })).classification, 'PASS')
})

// TX-03, aborted block: unit 1's failing statement aborts its transaction before the withheld ROLLBACK.
const ABORTED_LEAK = 'TX-03.statement-error-rollback-not-sent'
const abortedLeak = (over = {}) => txThree(ABORTED_LEAK, { faultSession: aborted(), faultFate: 'aborted', violation: '23505', ...over })

test('TX-03, aborted block: a connection discarded after the withheld ROLLBACK passes', () => {
  assert.equal(run(abortedLeak({ u1Session: closed })).classification, 'PASS')
})

test('TX-03, aborted block: handing the connection on as it is fails loudly, a FAIL of TX-03.2 naming the error', () => {
  const r = run(abortedLeak({ u1Session: aborted(), u1Fate: 'aborted', unit2: null, nextVisible: false, next: { outcome: 'completed', reported: 'failed', elapsed_ms: 1, api_error: { class: 'Error', code: '25P02', message: 'current transaction is aborted' } } }))
  assert.equal(r.classification, 'FAIL')
  const i = r.invariants.find((x) => x.id === 'TX-03.2')
  assert.equal(i.holds, false)
  assert.match(i.detail, /reported failed \(25P02\)/)
  assert.ok(r.invariants.some((x) => x.id === 'TX-03.1' && x.holds === true))
})

test('TX-03, aborted block: an open block at the fault, or no unique violation, is INCONCLUSIVE', () => {
  assert.match(run(abortedLeak({ faultSession: inTx('700'), faultFate: 'in progress' })).reason, /left unit 1's aborted transaction block in place/)
  assert.match(run(abortedLeak({ violation: undefined })).reason, /failing statement failed with unique_violation/)
  // The open-block case keeps its own signature: an aborted block there is not the fault it injects.
  assert.match(run(txThree('TX-03.rollback-not-sent', { faultSession: aborted(), faultFate: 'aborted' })).reason, /left unit 1's transaction open/)
})

// TX-04: nested and independent scopes, no fault.
function txFour(id, { reported, fate, outer, inner, nested, innerLocks = wrote('700', '701'), outerXmin } = {}) {
  if (id === 'TX-04.independent-inner') {
    return evidence(id, {
      checkpoints: {
        'inner-after-write': point({ pid: 11, xid: '800', session: { ...inTx('800', { xid_matches: true }), pid: 11 }, locks: noWrite('800'), sessions: 2, now: { inner: ['in progress', { ...inTx('800'), pid: 11 }] } }),
        'after-end': point({ pid: null, now: { inner: ['committed', { ...idle('COMMIT'), pid: 11 }] } }),
      },
      transactions: { inner: { ...tx('800', 'inner-after-write', 'committed'), pid: 11 } },
      markers: { outer, inner },
      marker_xmin: { outer: outer ? outerXmin ?? '800' : null, inner: inner ? '800' : null },
    }, { reported, apiError: reported === 'committed' ? null : API_ERROR, steps: { nested } })
  }
  return evidence(id, {
    checkpoints: {
      'inner-after-write': point({ xid: '700', session: inTx('700', { xid_matches: true }), locks: innerLocks, now: { tx: ['in progress', inTx('700')] } }),
      'after-end': point({ pid: null, now: { tx: [fate, idle(fate === 'committed' ? 'COMMIT' : 'ROLLBACK')] } }),
    },
    transactions: { tx: tx('700', 'inner-after-write', fate) },
    markers: { outer, inner },
    marker_xmin: { outer: outer ? outerXmin ?? '700' : null, inner: inner ? '701' : null },
  }, { reported, apiError: reported === 'committed' ? null : API_ERROR, steps: { nested } })
}

test('TX-04.1: a caller write lost with the failed nested scope is a FAIL', () => {
  const r = run(txFour('TX-04.nested-failure-contained', { reported: 'committed', fate: 'committed', outer: false, inner: false, nested: { caught: true } }))
  assert.equal(r.classification, 'FAIL')
})

test('TX-04.2: a released nested scope surviving the outer rollback is a FAIL', () => {
  const r = run(txFour('TX-04.nested-released-outer-rollback', { reported: 'rolled_back', fate: 'committed', outer: false, inner: true, nested: { completed: true } }))
  assert.equal(r.classification, 'FAIL')
})

test('TX-04.2: a unit-of-work mutant that never sends the inner write is INCONCLUSIVE, not PASS', () => {
  const r = run(txFour('TX-04.nested-released-outer-rollback', { reported: 'rolled_back', fate: 'aborted', outer: false, inner: false, nested: { completed: true }, innerLocks: noWrite('700') }))
  assert.equal(r.classification, 'INCONCLUSIVE')
  assert.match(r.reason, /marker "inner" had reached PostgreSQL at `inner-after-write` \(a subtransaction lock/)
})

test('TX-04.3: an outer write committed by the independent inner transaction is a FAIL, attributed by xmin', () => {
  const r = run(txFour('TX-04.independent-inner', { reported: 'rolled_back', outer: true, inner: true, nested: { completed: true } }))
  assert.equal(r.classification, 'FAIL')
  assert.match(r.invariants[0].detail, /inserted by transaction 800, the inner transaction/)
})

test('TX-04: a deferred write may land in a subtransaction created after the last checkpoint; it is not misattributed', () => {
  // MikroORM clear-forks: after ROLLBACK TO the savepoint stays established, so the pending outer insert runs in a new
  // subtransaction (702), which no checkpoint saw, and commits with the transaction.
  const r = run(txFour('TX-04.nested-failure-contained', { reported: 'committed', fate: 'committed', outer: true, inner: false, nested: { caught: true }, outerXmin: '702' }))
  assert.equal(r.classification, 'PASS')
})

test('TX-04: the promised boundaries pass', () => {
  assert.equal(run(txFour('TX-04.nested-failure-contained', { reported: 'committed', fate: 'committed', outer: true, inner: false, nested: { caught: true } })).classification, 'PASS')
  assert.equal(run(txFour('TX-04.nested-released-outer-rollback', { reported: 'rolled_back', fate: 'aborted', outer: false, inner: false, nested: { completed: true } })).classification, 'PASS')
  assert.equal(run(txFour('TX-04.independent-inner', { reported: 'rolled_back', outer: false, inner: true, nested: { completed: true } })).classification, 'PASS')
})

test('fateStory: the same fate at report time and at the end, or the moment that decided it', () => {
  const k = { family: 'CTL-01' }
  const obs = (atReport, atEnd, end) => ({ transactions: { tx: { xid: '7', fate: end } }, checkpoints: { 'after-end': { transactions_now: { tx: { fate: atEnd } } } }, ...(atReport ? {} : {}) })
  assert.equal(fateStory(obs(null, 'committed', 'committed'), k, 'tx'), 'xid 7 committed at report time (`after-end`)')
  assert.match(fateStory(obs(null, 'in progress', 'aborted'), k, 'tx'), /open at report time \(`after-end`: xid 7 in progress\); rolled back at teardown/)
  assert.match(fateStory({ transactions: { tx: { xid: '7', fate: 'aborted' } }, checkpoints: {} }, k, 'tx'), /not observed at report time/)
})

// TX-05: the requested isolation level. A transaction requests SERIALIZABLE, writes `tx`, reads it back, and reports
// PostgreSQL's own current_setting('transaction_isolation') with its ID at `after-read`; or the API rejects the
// request, and a plain transaction through the same API form is reported at `baseline`.
const TX05 = ['TX-05.managed-serializable', 'TX-05.explicit-serializable']
/** SIReadLocks as Observer.locks() reports them; `on_item` is whether the relation is item or one of its indexes. */
const siread = (...relations) => relations.map((relation) => ({ locktype: 'relation', relation, page: null, tuple: null, on_item: relation === 'item' || relation === 'item_pkey' }))

/** A started TX-05 transaction. `level` is what PostgreSQL reported; by default the locks agree with it. */
function tx5(id, { level = 'serializable', locks = {}, session, over = {} } = {}) {
  const held = { wrote_item: true, xids: ['900'], read_item: true, siread: level === 'serializable' ? siread('item') : [], ...locks }
  const afterRead = { ...point({ xid: '900', session: session ?? inTx('900', { xid_matches: true }), locks: held, now: { tx: ['in progress', inTx('900')] } }), reported: { pid: PID, xid: '900', transaction_isolation: level } }
  return evidence(id, {
    checkpoints: { 'after-read': afterRead, 'after-end': point({ pid: null, now: { tx: ['committed', idle('COMMIT')] } }) },
    transactions: { tx: tx('900', 'after-read', 'committed') },
    markers: { tx: true },
    marker_xmin: { tx: '900' },
  }, {}, over)
}

/** A rejected TX-05 request. With `baseline`, a plain transaction through the same API form was reported and bound. */
function tx5Rejected(id, { apiError = { class: 'Error', code: null, message: 'this isolation level is not supported' }, baseline = true, steps = {} } = {}) {
  return evidence(id, {
    checkpoints: {
      ...(baseline ? { baseline: point({ xid: '901', session: inTx('901', { xid_matches: true }), locks: noWrite('901'), now: { baseline: ['in progress', inTx('901')] } }) } : {}),
      'after-end': point({ pid: null, now: baseline ? { baseline: ['committed', idle('COMMIT')] } : {} }),
    },
    transactions: baseline ? { baseline: tx('901', 'baseline', 'committed') } : {},
    markers: { tx: false },
    marker_xmin: { tx: null },
  }, { reported: 'failed', apiError, steps })
}

test('TX-05: PostgreSQL reports SERIALIZABLE and the backend holds an SIReadLock on item: PASS, in both forms', () => {
  for (const id of TX05) {
    const r = run(tx5(id))
    assert.equal(r.classification, 'PASS', `${id}: ${r.reason}`)
    assert.equal(r.inconclusive_reason, null)
    assert.deepEqual(r.invariants.map((i) => [i.id, i.holds]), [['TX-05.1', true], ['TX-05.2', true]])
    assert.match(r.reason, /SIReadLock on relation:item/)
  }
})

test('TX-05: an SIReadLock on an index of item corroborates SERIALIZABLE; one beside it on another table changes nothing', () => {
  assert.equal(run(tx5(TX05[0], { locks: { siread: siread('item_pkey') } })).classification, 'PASS')
  assert.equal(run(tx5(TX05[0], { locks: { siread: siread('item', 'other_table') } })).classification, 'PASS')
})

test('TX-05: a weaker level, reported honestly and with no SIReadLock, is a FAIL of TX-05.1: the Lucid explicit-form bug', () => {
  for (const level of ['read committed', 'repeatable read', 'read uncommitted']) {
    const r = run(tx5(TX05[1], { level }))
    assert.equal(r.classification, 'FAIL', `${level}: ${r.reason}`)
    assert.deepEqual(r.invariants.map((i) => [i.id, i.holds]), [['TX-05.1', false], ['TX-05.2', true]])
    assert.match(r.reason, new RegExp(`PostgreSQL ran the transaction at ${level}.*no SIReadLock although it had read item`))
  }
})

test('TX-05: a report the locks contradict is INCONCLUSIVE (observation-conflict), never PASS', () => {
  const conflicts = {
    'serializable claimed, no SIReadLock': tx5(TX05[0], { locks: { siread: [] } }),
    'serializable claimed, SIReadLocks only on another table': tx5(TX05[0], { locks: { siread: siread('other_table') } }),
    'a weaker level claimed, with an SIReadLock on item': tx5(TX05[0], { level: 'read committed', locks: { siread: siread('item') } }),
  }
  for (const [what, ev] of Object.entries(conflicts)) {
    const r = run(ev)
    assert.equal(r.classification, 'INCONCLUSIVE', `${what}: ${r.classification}`)
    assert.equal(r.inconclusive_reason, 'observation-conflict', what)
  }
})

test('TX-05: missing evidence is INCONCLUSIVE (evidence-missing): no confirmed read, no report of the level, a session not idle, an unbound ID', () => {
  const missing = {
    'no AccessShareLock on item': tx5(TX05[0], { locks: { read_item: false } }),
    'no report of the level': tx5(TX05[0], { over: { observed: { checkpoints: { 'after-read': { reported: { transaction_isolation: null } } } } } }),
    'an unknown level name': tx5(TX05[0], { over: { observed: { checkpoints: { 'after-read': { reported: { transaction_isolation: 'snapshot' } } } } } }),
    'a session not idle in its transaction': tx5(TX05[0], { session: aborted({ backend_xid: '900', xid_matches: true }) }),
    'an ID not bound to its session': tx5(TX05[0], { over: { observed: { transactions: { tx: { session_xid_matches: false } } } } }),
    'the write not confirmed': tx5(TX05[0], { locks: { wrote_item: false } }),
    'a case that requests a level the runner cannot corroborate': tx5(TX05[0], { over: { case: { settings: { isolation_level: 'repeatable read' } } } }),
  }
  for (const [what, ev] of Object.entries(missing)) {
    const r = run(ev)
    assert.equal(r.classification, 'INCONCLUSIVE', `${what}: ${r.classification} (${r.reason})`)
    assert.equal(r.inconclusive_reason, 'evidence-missing', `${what}: ${r.inconclusive_reason}`)
  }
})

test('TX-05: a rejection with an established cause is a FAIL of TX-05.2, with TX-05.1 not exercised', () => {
  for (const id of TX05) {
    for (const code of [null, 'E_UNSUPPORTED_ISOLATION_LEVEL']) {
      const r = run(tx5Rejected(id, { apiError: { class: 'Error', code, message: 'this isolation level is not supported' } }))
      assert.equal(r.classification, 'FAIL', `${id} ${code}: ${r.reason}`)
      assert.deepEqual(r.invariants.map((i) => [i.id, i.holds]), [['TX-05.1', null], ['TX-05.2', false]])
      assert.deepEqual(r.not_exercised, ['TX-05.1'])
      assert.match(r.reason, /the API raised instead of starting the transaction .*while a plain transaction through the same API form started \(xid 901\)/)
    }
  }
})

test('TX-05: a rejection whose cause is the environment, or unknown, is INCONCLUSIVE with that reason', () => {
  const cases = {
    'a PostgreSQL SQLSTATE': [tx5Rejected(TX05[1], { apiError: { class: 'DatabaseError', code: '42601', message: 'syntax error' } }), 'environment'],
    'a connection error code': [tx5Rejected(TX05[1], { apiError: { class: 'Error', code: 'ECONNREFUSED', message: 'connect ECONNREFUSED' } }), 'environment'],
    'a DNS error code': [tx5Rejected(TX05[1], { apiError: { class: 'Error', code: 'EAI_AGAIN', message: 'getaddrinfo EAI_AGAIN' } }), 'environment'],
    'the plain transaction failed too': [tx5Rejected(TX05[1], { baseline: false, steps: { baseline: { error: { class: 'Error', code: null, message: 'Connection terminated unexpectedly' } } } }), 'environment'],
    'no plain transaction reported': [tx5Rejected(TX05[1], { baseline: false }), 'cause-not-established'],
  }
  for (const [what, [ev, reason]] of Object.entries(cases)) {
    const r = run(ev)
    assert.equal(r.classification, 'INCONCLUSIVE', `${what}: ${r.classification} (${r.reason})`)
    assert.equal(r.inconclusive_reason, reason, `${what}: ${r.inconclusive_reason}`)
  }
  // A rejection reported without the API's error, and a success reported without `after-read`, are missing evidence.
  for (const ev of [tx5Rejected(TX05[0], { apiError: null }), merge(tx5Rejected(TX05[0]), { reported: 'committed', apiError: null })]) {
    const r = run(ev)
    assert.equal(r.classification, 'INCONCLUSIVE', r.reason)
    assert.equal(r.inconclusive_reason, 'evidence-missing')
  }
})

test('TX-05 records why it is INCONCLUSIVE, other families do not yet, and no recorded precondition carries its kind', () => {
  const r = run(tx5(TX05[0], { locks: { siread: [] } }))
  assert.equal(r.inconclusive_reason, 'observation-conflict')
  for (const p of r.preconditions) assert.deepEqual(Object.keys(p).sort(), ['description', 'detail', 'met'])
  const other = run(merge(ctl('CTL-01.commit'), { observed: { transactions: { tx: { fate: null } } } }))
  assert.equal(other.classification, 'INCONCLUSIVE')
  assert.equal(other.inconclusive_reason, null)
  assert.equal(run(ctl('CTL-01.commit')).inconclusive_reason, null)
})
