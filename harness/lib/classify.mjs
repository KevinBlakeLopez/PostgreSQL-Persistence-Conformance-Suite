// Classification: turns one case's evidence into PASS, FAIL, UNSUPPORTED, INCONCLUSIVE or NOT_RUN. Pure functions, so
// harness/test/classify.test.mjs can check every rule without a database.
//
// The order of the checks is the methodology (docs/methodology.md, "Classification"):
//  1. UNSUPPORTED: the adapter states that the framework's supported API lacks the capability. Never a FAIL.
//  2. INCONCLUSIVE: the run itself did not produce trustworthy evidence. That covers a timeout, a protocol error, a
//     missing result or checkpoint, a transaction ID that was not captured, a fate PostgreSQL could not report, or a
//     fate that disagrees with marker visibility.
//  3. INCONCLUSIVE: a precondition of the case did not hold, so its invariants do not apply.
//  4. FAIL: an invariant was violated, with complete and consistent observations.
//  5. PASS: every invariant held.

export const CLASSIFICATIONS = ['PASS', 'FAIL', 'UNSUPPORTED', 'INCONCLUSIVE', 'NOT_RUN']

const check = (description, met, detail = null) => ({ description, met: met === true, detail })
const invariant = (id, statement, holds, detail) => ({ id, statement, holds, detail })

/** Family-specific preconditions and invariants. `ev` is the evidence object assembled by run-case.mjs. */
const FAMILIES = {
  'CTL-01': (ev, statements) => {
    const { expected } = ev.case
    const tx = ev.observed.transactions.tx
    const preconditions = [check(`the API reported "${expected.reported}"`, ev.reported === expected.reported, `reported: ${ev.reported ?? 'nothing'}`)]
    const committed = tx.fate === 'committed' && ev.observed.markers.tx === true
    const invariants = expected.reported === 'committed'
      ? [invariant('CTL-01.1', statements['CTL-01.1'], committed, `pg_xact_status: ${tx.fate}; marker visible: ${ev.observed.markers.tx}`)]
      : [invariant('CTL-01.2', statements['CTL-01.2'], tx.fate === 'aborted' && ev.observed.markers.tx === false, `pg_xact_status: ${tx.fate}; marker visible: ${ev.observed.markers.tx}`)]
    return { preconditions, invariants }
  },

  'TX-01A': (ev, statements) => {
    const tx = ev.observed.transactions.tx
    const atEnd = ev.observed.checkpoints['before-end']?.session
    const violation = ev.steps?.violation
    const preconditions = [
      check('the duplicate insert failed with unique_violation (23505), as reported by the adapter', violation?.code === '23505', `caught: ${violation?.code ?? 'nothing'}`),
      check('the server-side transaction was aborted before it ended (pg_stat_activity at before-end)', atEnd?.state === 'idle in transaction (aborted)', `state: ${atEnd?.present === false ? 'no such session' : atEnd?.state ?? 'not observed'}`),
      check('PostgreSQL did not commit the transaction', tx.fate === 'aborted' && ev.observed.markers.tx === false, `pg_xact_status: ${tx.fate}; marker visible: ${ev.observed.markers.tx}`),
    ]
    const invariants = [invariant('TX-01A.1', statements['TX-01A.1'], ev.reported !== 'committed', `the API reported: ${ev.reported}`)]
    return { preconditions, invariants }
  },

  'TX-01B': (ev, statements) => {
    const tx = ev.observed.transactions.tx
    const preconditions = [
      faultTookEffect(ev, 'before-end'),
      check(`PostgreSQL's outcome is the one the case produces (${ev.case.expected.fate})`, tx.fate === ev.case.expected.fate, `pg_xact_status: ${tx.fate}; marker visible: ${ev.observed.markers.tx}`),
    ]
    const invariants = [
      invariant('TX-01B.1', statements['TX-01B.1'], ev.reported !== 'committed', `the API reported: ${ev.reported}`),
      invariant('TX-01B.2', statements['TX-01B.2'], ev.reported !== 'rolled_back', `the API reported: ${ev.reported}`),
    ]
    return { preconditions, invariants }
  },

  'TX-02': (ev, statements) => {
    const tx = ev.observed.transactions.tx
    const m = ev.observed.markers
    const after = ev.observed.checkpoints['after-outer']?.session
    const preconditions = [
      faultTookEffect(ev, 'inner-after-write'),
      check('the nested scope\'s error reached the outer scope, which handled it', ev.steps?.nested?.caught === true, `nested scope: ${ev.steps?.nested?.caught ? `raised ${ev.steps.nested.error?.class ?? 'an error'}` : 'no error reached the outer scope'}`),
      check('the runner observed the transaction\'s session after the outer API returned', after != null && typeof after.present === 'boolean', `session: ${after ? (after.present ? after.state : 'closed') : 'not observed'}`),
    ]
    const committedAsReported = tx.fate === 'committed' && m.outer === true && m.inner === false
    const invariants = [
      invariant('TX-02.1', statements['TX-02.1'], ev.reported !== 'committed' || committedAsReported,
        `the API reported: ${ev.reported}; pg_xact_status: ${tx.fate}; outer visible: ${m.outer}; inner (failed scope) visible: ${m.inner}`),
      invariant('TX-02.2', statements['TX-02.2'], !(after?.present && after?.in_transaction),
        `the session after the outer API returned: ${after?.present === false ? 'closed' : after?.present ? `"${after.state}"` : 'not observed'}`),
    ]
    return { preconditions, invariants }
  },

  'TX-04': (ev, statements) => {
    const m = ev.observed.markers
    const nested = ev.steps?.nested
    const [id] = ev.case.invariants
    if (id === 'TX-04.1') {
      const tx = ev.observed.transactions.tx
      return {
        preconditions: [check('the nested scope\'s error reached the outer scope, which handled it', nested?.caught === true, `nested scope: ${nested?.caught ? 'raised' : 'no error reached the outer scope'}`)],
        invariants: [invariant(id, statements[id], ev.reported === 'committed' && tx.fate === 'committed' && m.outer === true && m.inner === false,
          `the API reported: ${ev.reported}; pg_xact_status: ${tx.fate}; outer visible: ${m.outer}; inner (failed scope) visible: ${m.inner}`)],
      }
    }
    if (id === 'TX-04.2') {
      const tx = ev.observed.transactions.tx
      return {
        preconditions: [check('the nested scope completed normally', nested?.completed === true, `nested scope: ${nested?.completed ? 'completed' : 'did not complete'}`)],
        invariants: [invariant(id, statements[id], m.inner === false && m.outer === false,
          `the API reported: ${ev.reported}; pg_xact_status: ${tx.fate}; outer visible: ${m.outer}; inner (released scope) visible: ${m.inner}`)],
      }
    }
    // TX-04.3. A visible outer marker's row xmin names the transaction that committed it.
    const inner = ev.observed.transactions.inner
    const outerXmin = ev.observed.marker_xmin?.outer ?? null
    const byInner = outerXmin != null && inner?.xid != null && BigInt(inner.xid) % 2n ** 32n === BigInt(outerXmin)
    return {
      preconditions: [check('the inner transaction completed, and PostgreSQL committed it', nested?.completed === true && inner?.fate === 'committed', `inner: ${nested?.completed ? 'completed' : 'did not complete'}, pg_xact_status ${inner?.fate}`)],
      invariants: [invariant(id, statements[id], m.inner === true && m.outer === false,
        `inner visible: ${m.inner}; outer visible after the outer rollback: ${m.outer}${m.outer ? ` (inserted by transaction ${outerXmin}${byInner ? ', the inner transaction' : ''})` : ''}`)],
    }
  },

  'TX-03': (ev, statements) => {
    const { unit1, unit2 } = ev.observed.transactions
    const next = ev.steps?.unit2
    const markers = ev.observed.markers
    const bound = ev.case.settings.bound_ms
    const preconditions = [faultTookEffect(ev, 'unit1-after-write'), check('the next unit of work was attempted', !!next, `next unit: ${next?.outcome ?? 'not attempted'}`)]
    // Unsafe reuse, observed server-side: the next unit's pg_current_xact_id() is the failed transaction's ID.
    const sameTransaction = !!unit2 && unit2.xid === unit1.xid
    const invariants = [
      invariant('TX-03.1', statements['TX-03.1'], unit1.fate !== 'committed' && markers.doomed === false && !sameTransaction,
        `failed transaction ${unit1.xid}: pg_xact_status ${unit1.fate}; doomed visible: ${markers.doomed}; next unit's transaction: ${unit2 ? `${unit2.xid}${sameTransaction ? ' (the failed transaction itself)' : ''}` : 'not reached'}`),
      invariant('TX-03.2', statements['TX-03.2'], next?.outcome === 'completed' && next.reported === 'committed' && unit2?.fate === 'committed' && markers.next === true,
        `next unit: ${next?.outcome === 'pending' ? `still pending after ${bound} ms` : `${next?.outcome}, reported ${next?.reported}${next?.elapsed_ms != null ? ` after ${next.elapsed_ms} ms` : ''}`}; its transaction: ${unit2 ? `${unit2.xid} ${unit2.fate}` : 'not reached'}; next visible: ${markers.next}`),
    ]
    return { preconditions, invariants }
  },
}

/** The precondition that a case's fault took effect: the runner's termination at `checkpoint` (category B), or the
 * adapter's client-side fault, which reports how often it fired (categories C and D). */
function faultTookEffect(ev, checkpoint) {
  if (ev.case.fault.category === 'B') {
    const a = ev.observed.checkpoints[checkpoint]?.action
    return check(`the runner terminated the backend at ${checkpoint}, and it had gone before the adapter resumed`, a?.terminated === true && a?.gone === true, `terminated: ${a?.terminated ?? 'not attempted'}; gone: ${a?.gone ?? 'not checked'}`)
  }
  const f = ev.steps?.fault
  return check(`the client-side fault (${f?.mode ?? 'none'}) fired`, f?.fired >= 1, `fired: ${f?.fired ?? 0}`)
}

/**
 * Evidence problems that make any conclusion unreliable. Returns a list of reasons; empty means the evidence is
 * complete and self-consistent.
 */
export function evidenceProblems(ev) {
  const problems = []
  const h = ev.harness
  if (h.timedOut) problems.push(`the adapter did not finish within ${h.timeoutMs} ms and was killed`)
  if (!h.helloReceived) problems.push('the adapter sent no hello message')
  if (!ev.adapterStatus) problems.push(`the adapter exited without a result (exit code ${h.exit?.code ?? 'none'}, signal ${h.exit?.signal ?? 'none'})`)
  if (ev.adapterStatus === 'error') problems.push(`the adapter reported an error: ${ev.adapterError ?? 'no detail'}`)
  else if (ev.adapterStatus && ev.adapterStatus !== 'completed') problems.push(`the adapter returned status "${ev.adapterStatus}"${ev.adapterReason ? `: ${ev.adapterReason}` : ''}`)
  for (const e of h.protocolErrors ?? []) problems.push(`protocol: ${e}`)
  for (const name of h.missingCheckpoints ?? []) problems.push(`checkpoint "${name}" was not reached`)
  if (ev.adapterStatus === 'completed' && !['committed', 'rolled_back', 'failed'].includes(ev.reported)) problems.push(`the adapter did not report the API outcome (got ${JSON.stringify(ev.reported)})`)
  for (const [label, tx] of Object.entries(ev.observed?.transactions ?? {})) {
    if (!tx.xid) { problems.push(`the ID of transaction "${label}" was not captured inside it`); continue }
    if (tx.fate !== 'committed' && tx.fate !== 'aborted') problems.push(`pg_xact_status() for transaction "${label}" is ${tx.fate === null ? 'unknown' : `"${tx.fate}"`}${tx.fate_error ? ` (${tx.fate_error})` : ''}`)
    if (tx.session_xid_matches === false) problems.push(`the transaction ID reported for "${label}" does not match its session's backend_xid in pg_stat_activity`)
  }
  if (ev.observed?.markersError) problems.push(`marker visibility could not be read: ${ev.observed.markersError}`)
  // The only combination PostgreSQL cannot produce: a visible row inserted (xmin) by a transaction that pg_xact_status()
  // reports as aborted. It means the observations themselves are wrong. A committed transaction whose marker is missing
  // is not an inconsistency: it is a lost write, which the family's invariants judge. A visible marker inserted by a
  // different transaction is not one either: it is an attribution, which the evidence records.
  for (const [label, xmin] of Object.entries(ev.observed?.marker_xmin ?? {})) {
    if (xmin == null) continue
    for (const [name, t] of Object.entries(ev.observed?.transactions ?? {})) {
      if (t.fate === 'aborted' && typeof t.xid === 'string' && /^\d+$/.test(t.xid) && BigInt(t.xid) % 2n ** 32n === BigInt(xmin)) {
        problems.push(`marker "${label}" is visible, but it was inserted by transaction "${name}" (xid ${t.xid}), which pg_xact_status() reports as aborted`)
      }
    }
  }
  return problems
}

/** Classifies one executed case. `statements` maps invariant IDs to their text (from the catalog). */
export function classify(ev, statements) {
  if (ev.adapterStatus === 'unsupported') {
    return { classification: 'UNSUPPORTED', reason: ev.adapterReason ?? 'the adapter reports the capability as unsupported', preconditions: [], invariants: [] }
  }
  const problems = evidenceProblems(ev)
  if (problems.length) return { classification: 'INCONCLUSIVE', reason: problems.join('; '), preconditions: [], invariants: [] }

  const family = FAMILIES[ev.case.family]
  if (!family) return { classification: 'INCONCLUSIVE', reason: `no classification rules for family ${ev.case.family}`, preconditions: [], invariants: [] }
  const { preconditions, invariants } = family(ev, statements)
  const unmet = preconditions.filter((p) => !p.met)
  if (unmet.length) {
    return { classification: 'INCONCLUSIVE', reason: `precondition not established: ${unmet.map((p) => `${p.description} (${p.detail})`).join('; ')}`, preconditions, invariants: [] }
  }
  const violated = invariants.filter((i) => i.holds === false)
  if (violated.length) return { classification: 'FAIL', reason: violated.map((i) => `${i.id} violated: ${i.detail}`).join('; '), preconditions, invariants }
  if (invariants.some((i) => i.holds !== true)) return { classification: 'INCONCLUSIVE', reason: 'an invariant could not be evaluated', preconditions, invariants }
  return { classification: 'PASS', reason: invariants.map((i) => `${i.id} held: ${i.detail}`).join('; '), preconditions, invariants }
}

export const notRun = (reason) => ({ classification: 'NOT_RUN', reason, preconditions: [], invariants: [] })
