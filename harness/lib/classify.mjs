// Classification: turns one case's evidence into PASS, FAIL, INCONCLUSIVE (UNSUPPORTED and NOT_RUN come from the plan,
// before anything runs). Pure functions, so harness/test/unit/ can check every rule without a database.
//
// The order of the checks is the methodology (docs/methodology.md, "Classification"):
//  1. INCONCLUSIVE: the run itself did not produce trustworthy evidence. That covers a timeout, a protocol error
//     (including a runtime "unsupported" and a repeated checkpoint), a missing result or checkpoint, an outcome the
//     adapter did not support with the API's error, a transaction ID not bound to its session, a visible marker not
//     written by its declared transaction, rows that are not markers, an unknown fate, leftover sessions, more
//     sessions than the pool allows, a changed fixture, and observations PostgreSQL cannot produce.
//  2. INCONCLUSIVE: a precondition of the case did not hold, so its invariants do not apply. Preconditions come from
//     the runner's own observations: write evidence in pg_locks, fault effects, session states, fates.
//  3. INCONCLUSIVE: the invariants evaluated are not exactly the ones the case declares, or none was exercised.
//  4. FAIL: an invariant was violated, with complete and consistent observations.
//  5. PASS: every exercised invariant held. An invariant the adapter cannot exercise is recorded as not exercised,
//     never as held.
// Run-level gates (controls, repetitions) are applied afterwards, in suite.mjs.
import { low32 } from './observer.mjs'

export const CLASSIFICATIONS = ['PASS', 'FAIL', 'UNSUPPORTED', 'INCONCLUSIVE', 'NOT_RUN']
export const REPORTED = ['committed', 'rolled_back', 'failed', 'pending']
/** The checkpoint every adapter sends when the framework's API has returned: the state at report time. */
export const REPORT_POINT = 'after-end'

const check = (description, met, detail = null) => ({ description, met: met === true, detail })
const invariant = (id, statement, holds, detail) => ({ id, statement, holds, detail })
const notExercised = (id, statement, detail) => ({ id, statement, holds: null, detail, not_exercised: true })

const checkpoint = (ev, name) => ev.observed.checkpoints?.[name]
/** The fate of transaction `label` as observed at checkpoint `name`, or undefined if not observed there. */
const fateAt = (ev, name, label) => checkpoint(ev, name)?.transactions_now?.[label]?.fate
const sessionText = (s) => (!s ? 'not observed' : s.present === false ? 'closed' : `"${s.state}"`)
const FATE_WORDS = { committed: 'committed', aborted: 'rolled back', 'in progress': 'in progress' }
const fateWord = (f) => FATE_WORDS[f] ?? 'unknown'

/** The checkpoint at which the API reported transaction `label`'s outcome: as soon as that API call had returned. */
export function reportPointOf(kase, label) {
  if (kase.family === 'TX-02') return 'after-outer'
  if (kase.family === 'TX-03' && label === 'unit1') return 'after-unit1'
  return REPORT_POINT
}

/**
 * A transaction's fate at report time and after the adapter exited (pg_xact_status). When the two differ, the fate
 * was decided after the API returned: by later work in the case if it had changed by `after-end`, or at teardown if
 * the transaction was still open then, and closing the framework ended it.
 */
export function fateStory(observed, kase, label) {
  const t = observed.transactions?.[label]
  const point = reportPointOf(kase, label)
  const at = (name) => observed.checkpoints?.[name]?.transactions_now?.[label]?.fate
  const atReport = at(point)
  const end = t?.fate ?? null
  const xid = t?.xid ?? 'not captured'
  if (atReport === undefined) return `xid ${xid} ${fateWord(end)} after the adapter exited (not observed at report time)`
  if (atReport === end) return `xid ${xid} ${fateWord(end)} at report time (\`${point}\`)`
  const atCaseEnd = at(REPORT_POINT)
  const by = atReport === 'in progress' && (atCaseEnd === undefined || atCaseEnd === 'in progress') ? 'at teardown' : 'by later work in the case, before teardown'
  const then = atReport === 'in progress' ? `open at report time (\`${point}\`: xid ${xid} in progress)` : `${fateWord(atReport)} at report time (\`${point}\`: xid ${xid})`
  return `${then}; ${fateWord(end)} ${by}, so decided after the API returned, not by the reported operation`
}

/** The precondition that a case's fault took effect: the runner's termination at `name` (category B), or the
 * adapter's client-side fault, which must have fired exactly once (categories C and D). */
function faultTookEffect(ev, name) {
  if (ev.case.fault.category === 'B') {
    const a = checkpoint(ev, name)?.action
    return check(`the runner terminated the backend at \`${name}\`, and it had gone before the adapter resumed`, a?.terminated === true && a?.gone === true, `terminated: ${a?.terminated ?? 'not attempted'}; gone: ${a?.gone ?? 'not checked'}`)
  }
  const f = ev.steps?.fault
  return check(`the client-side fault (${f?.mode ?? 'none'}) fired exactly once`, f?.fired === 1, `fired: ${f?.fired ?? 0}`)
}

/**
 * The server-side signature of a client-side fault, read at `after-fault`: the checkpoint the adapter's driver layer
 * reports as the fault fires, before the framework sees its error. Reading it any later would mix the fault's effect
 * with the framework's reaction to it: a framework that correctly discards the connection, or rolls back at once, would
 * look like a fault that changed nothing. Category B faults are shown by the runner's own termination instead.
 */
function faultSignature(ev) {
  const f = ev.steps?.fault
  if (ev.case.fault.category !== 'C' || !f) return []
  const at = checkpoint(ev, 'after-fault')
  const s = at?.session
  const xids = at?.locks?.xids ?? []
  const where = `at \`after-fault\`: session ${sessionText(s)}, backend_xid ${s?.backend_xid ?? 'NULL'}; transactionid locks [${xids.join(', ')}]`
  if (ev.case.family === 'TX-03') {
    const unit1 = ev.observed.transactions.unit1
    return [check('the withheld ROLLBACK left unit 1\'s transaction open: its session was in a transaction holding unit 1\'s ID', s?.state === 'idle in transaction' && s?.backend_xid === low32(unit1?.xid), where)]
  }
  if (f.mode === 'client-reject') {
    return [check('the withheld ROLLBACK TO SAVEPOINT left the savepoint live: the session was in its transaction, holding the savepoint\'s subtransaction lock', s?.state === 'idle in transaction' && xids.length >= 2, where)]
  }
  if (f.mode === 'rewrite') {
    const fate = at?.transactions_now?.tx?.fate
    return [
      check('PostgreSQL rejected the rewritten ROLLBACK TO SAVEPOINT (3B001)', (f.reply_codes ?? []).includes('3B001'), `replies: [${(f.reply_codes ?? []).join(', ')}]`),
      check('the rejection aborted only the subtransaction: the session was "idle in transaction (aborted)", and the top-level transaction was still in progress', s?.state === 'idle in transaction (aborted)' && fate === 'in progress', `${where}; top-level pg_xact_status: ${fate ?? 'not observed'}`),
    ]
  }
  return [check(`the fault's server-side effect is known for mode ${f.mode}`, false, 'no signature is defined for this fault mode')]
}

/** Evaluates exactly the invariants the case declares, from a map of evaluators keyed by invariant ID. */
function evaluateDeclared(ev, statements, evaluators) {
  return ev.case.invariants.map((id) => (evaluators[id] ? evaluators[id](statements[id]) : invariant(id, statements[id], null, 'no rule evaluates this invariant')))
}

/** Family-specific preconditions and invariants. `ev` is the evidence object assembled by run-case.mjs. */
const FAMILIES = {
  'CTL-01': (ev, statements) => {
    const { expected } = ev.case
    const t = ev.observed.transactions.tx
    const atReport = fateAt(ev, REPORT_POINT, 'tx')
    const visible = ev.observed.markers.tx
    const story = fateStory(ev.observed, ev.case, 'tx')
    return {
      preconditions: [check(`the API reported "${expected.reported}"`, ev.reported === expected.reported, `reported: ${ev.reported ?? 'nothing'}`)],
      invariants: evaluateDeclared(ev, statements, {
        'CTL-01.1': (s) => invariant('CTL-01.1', s, atReport === 'committed' && t.fate === 'committed' && visible === true, `${story}; marker visible: ${visible}`),
        'CTL-01.2': (s) => invariant('CTL-01.2', s, atReport === 'aborted' && t.fate === 'aborted' && visible === false, `${story}; marker visible: ${visible}`),
      }),
    }
  },

  'TX-01A': (ev, statements) => {
    const t = ev.observed.transactions.tx
    const atEnd = checkpoint(ev, 'before-end')
    const violation = ev.steps?.violation
    // The top-level transaction is aborted at the failed statement: before COMMIT, PostgreSQL already reports it aborted.
    const abortedBeforeEnd = atEnd?.session?.state === 'idle in transaction (aborted)' && fateAt(ev, 'before-end', 'tx') === 'aborted'
    // Whether COMMIT reached the server: after the API returned, the same backend is idle, and its last statement was COMMIT.
    const after = checkpoint(ev, REPORT_POINT)?.transactions_now?.tx?.session
    const mechanismExercised = after?.present ? (!after.in_transaction && /^\s*(commit|end)\b/i.test(after.query ?? '')) : null
    return {
      preconditions: [
        check('the duplicate insert failed with unique_violation (23505), as reported by the adapter', violation?.code === '23505', `caught: ${violation?.code ?? 'nothing'}`),
        check('the top-level transaction was aborted before it ended: at `before-end` the session was "idle in transaction (aborted)" and pg_xact_status() already reported it aborted', abortedBeforeEnd, `state: ${sessionText(atEnd?.session)}; pg_xact_status: ${fateAt(ev, 'before-end', 'tx') ?? 'not observed'}`),
        check('PostgreSQL did not commit the transaction', t.fate === 'aborted' && ev.observed.markers.tx === false, `pg_xact_status: ${t.fate}; marker visible: ${ev.observed.markers.tx}`),
      ],
      invariants: evaluateDeclared(ev, statements, {
        'TX-01A.1': (s) => invariant('TX-01A.1', s, ev.reported !== 'committed', `the API reported: ${ev.reported}`),
      }),
      mechanismExercised,
      mechanismDetail: after?.present ? `after the API returned, the session was "${after.state}", and its last statement was "${after.query}"` : 'the session had closed when the API returned',
    }
  },

  'TX-01B': (ev, statements) => {
    const t = ev.observed.transactions.tx
    const atReport = fateAt(ev, REPORT_POINT, 'tx')
    const channels = ev.adapter?.rollbackClaimChannels ?? []
    return {
      preconditions: [
        faultTookEffect(ev, 'before-end'),
        check(`PostgreSQL's outcome is the one the case produces (${ev.case.expected.fate}), at report time and after the adapter exited`, atReport === ev.case.expected.fate && t.fate === ev.case.expected.fate, `${fateStory(ev.observed, ev.case, 'tx')}; marker visible: ${ev.observed.markers.tx}`),
      ],
      invariants: evaluateDeclared(ev, statements, {
        'TX-01B.1': (s) => invariant('TX-01B.1', s, ev.reported !== 'committed', `the API reported: ${ev.reported}`),
        // A rollback reported through the result always violates it. Otherwise the invariant held only if the adapter
        // observes a channel through which the framework could have claimed a rollback (its manifest declares them).
        'TX-01B.2': (s) => (ev.reported === 'rolled_back' || channels.length
          ? invariant('TX-01B.2', s, ev.reported !== 'rolled_back', `the API reported: ${ev.reported}${channels.length ? ` (channels observed: ${channels.join(', ')})` : ''}`)
          : notExercised('TX-01B.2', s, 'the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised')),
      }),
    }
  },

  'TX-02': (ev, statements) => {
    const t = ev.observed.transactions.tx
    const m = ev.observed.markers
    const reportPoint = reportPointOf(ev.case, 'tx')
    const atReport = fateAt(ev, reportPoint, 'tx')
    const after = checkpoint(ev, reportPoint)?.session
    const preconditions = [
      faultTookEffect(ev, 'inner-after-write'),
      check('the nested scope\'s error reached the outer scope, which handled it', ev.steps?.nested?.caught === true, `nested scope: ${ev.steps?.nested?.caught ? `raised ${ev.steps.nested.error?.class ?? 'an error'}` : 'no error reached the outer scope'}`),
      check('the runner observed the transaction\'s session after the outer API returned', after != null && typeof after.present === 'boolean', `session: ${sessionText(after)}`),
      ...faultSignature(ev),
    ]
    return {
      preconditions,
      invariants: evaluateDeclared(ev, statements, {
        'TX-02.1': (s) => invariant('TX-02.1', s, ev.reported !== 'committed' || (atReport === 'committed' && t.fate === 'committed' && m.outer === true && m.inner === false),
          `the API reported: ${ev.reported}; ${fateStory(ev.observed, ev.case, 'tx')}; outer visible: ${m.outer}; inner (failed scope) visible: ${m.inner}`),
        'TX-02.2': (s) => invariant('TX-02.2', s, !(after?.present && after?.in_transaction), `the session after the outer API returned: ${sessionText(after)}`),
      }),
    }
  },

  'TX-03': (ev, statements) => {
    const { unit1, unit2 } = ev.observed.transactions
    const next = ev.steps?.unit2
    const markers = ev.observed.markers
    const bound = ev.case.settings.bound_ms
    const u1AtReport = checkpoint(ev, reportPointOf(ev.case, 'unit1'))?.transactions_now?.unit1
    const preconditions = [faultTookEffect(ev, 'unit1-after-write'), check('the next unit of work was attempted', !!next, `next unit: ${next?.outcome ?? 'not attempted'}`), ...faultSignature(ev)]
    // Unsafe reuse, observed server-side: the next unit's pg_current_xact_id() is the failed transaction's ID.
    const sameTransaction = !!unit2 && unit2.xid === unit1.xid
    return {
      preconditions,
      invariants: evaluateDeclared(ev, statements, {
        'TX-03.1': (s) => invariant('TX-03.1', s, unit1.fate !== 'committed' && markers.doomed === false && !sameTransaction,
          `failed transaction: ${fateStory(ev.observed, ev.case, 'unit1')}; doomed visible: ${markers.doomed}; next unit's transaction: ${unit2 ? `${unit2.xid}${sameTransaction ? ' (the failed transaction itself)' : ''}` : 'not reached'}`),
        'TX-03.2': (s) => invariant('TX-03.2', s, next?.outcome === 'completed' && next.reported === 'committed' && unit2?.fate === 'committed' && markers.next === true,
          `next unit: ${next?.outcome === 'pending' ? `still pending after ${bound} ms` : `${next?.outcome}, reported ${next?.reported}${next?.elapsed_ms != null ? ` after ${next.elapsed_ms} ms` : ''}`}; its transaction: ${unit2 ? `${unit2.xid} ${unit2.fate}` : 'not reached'}; next visible: ${markers.next}`),
      }),
    }
  },

  'TX-04': (ev, statements) => {
    const m = ev.observed.markers
    const nested = ev.steps?.nested
    const tx = ev.observed.transactions.tx
    const inner = ev.observed.transactions.inner
    const outerXmin = ev.observed.marker_xmin?.outer ?? null
    const byInner = outerXmin != null && low32(inner?.xid) === outerXmin
    const preconditions = []
    if (ev.case.invariants.includes('TX-04.1')) preconditions.push(check('the nested scope\'s error reached the outer scope, which handled it', nested?.caught === true, `nested scope: ${nested?.caught ? 'raised' : 'no error reached the outer scope'}`))
    if (ev.case.invariants.includes('TX-04.2')) preconditions.push(check('the nested scope completed normally', nested?.completed === true, `nested scope: ${nested?.completed ? 'completed' : 'did not complete'}`))
    if (ev.case.invariants.includes('TX-04.3')) preconditions.push(check('the inner transaction completed, and PostgreSQL committed it', nested?.completed === true && inner?.fate === 'committed', `inner: ${nested?.completed ? 'completed' : 'did not complete'}, pg_xact_status ${inner?.fate}`))
    return {
      preconditions,
      invariants: evaluateDeclared(ev, statements, {
        'TX-04.1': (s) => invariant('TX-04.1', s, ev.reported === 'committed' && fateAt(ev, REPORT_POINT, 'tx') === 'committed' && tx.fate === 'committed' && m.outer === true && m.inner === false,
          `the API reported: ${ev.reported}; ${fateStory(ev.observed, ev.case, 'tx')}; outer visible: ${m.outer}; inner (failed scope) visible: ${m.inner}`),
        'TX-04.2': (s) => invariant('TX-04.2', s, m.inner === false && m.outer === false, `the API reported: ${ev.reported}; ${fateStory(ev.observed, ev.case, 'tx')}; outer visible: ${m.outer}; inner (released scope) visible: ${m.inner}`),
        // A visible outer marker's row xmin names the transaction that committed it.
        'TX-04.3': (s) => invariant('TX-04.3', s, m.inner === true && m.outer === false,
          `inner visible: ${m.inner}; outer visible after the outer rollback: ${m.outer}${m.outer ? ` (inserted by transaction ${outerXmin}${byInner ? ', the inner transaction' : ''})` : ''}`),
      }),
    }
  },
}

/** The subtransaction IDs seen in backend `pid`'s locks at any checkpoint, other than the top-level ID. */
function subxidsSeen(ev, pid, top) {
  const all = Object.values(ev.observed.checkpoints ?? {}).filter((c) => c.reported?.pid === pid).flatMap((c) => c.locks?.xids ?? [])
  return [...new Set(all)].filter((x) => x !== top)
}

/** Preconditions on the writes a case declares as sent: the writer's backend held the write's lock at that checkpoint. */
export function writePreconditions(ev) {
  const out = []
  for (const [marker, w] of Object.entries(ev.case.marker_writes ?? {})) {
    if (w.sent === 'possibly-pending') continue
    const entry = checkpoint(ev, w.sent)
    if (!entry && ev.case.checkpoints?.[w.sent]?.optional) continue // e.g. a next unit of work that never got a connection
    const locks = entry?.locks
    const sent = w.level === 'savepoint' ? (locks?.xids?.length ?? 0) >= 2 : locks?.wrote_item === true
    out.push(check(`the write of marker "${marker}" had reached PostgreSQL at \`${w.sent}\` (${w.level === 'savepoint' ? 'a subtransaction lock' : 'a row lock on item'}, in pg_locks)`, sent,
      `locks at \`${w.sent}\`: ${locks && !locks.error ? `item ${locks.wrote_item ? 'locked' : 'not locked'}; transactionid [${locks.xids.join(', ')}]` : 'not observed'}`))
  }
  return out
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
  if (ev.steps?.fault?.hook_error) problems.push(`the adapter could not report the fault's checkpoint: ${ev.steps.fault.hook_error}`)
  for (const name of h.missingCheckpoints ?? []) problems.push(`checkpoint "${name}" was not reached`)
  if (ev.adapterStatus === 'completed') {
    if (!REPORTED.includes(ev.reported)) problems.push(`the adapter did not report the API outcome (got ${JSON.stringify(ev.reported)})`)
    if (ev.reported === 'pending') problems.push('the API call had not returned when the adapter stopped waiting for it')
    if ((ev.reported === 'failed' || ev.reported === 'rolled_back') && !ev.apiError) problems.push(`the adapter reported "${ev.reported}" without the error the API raised`)
  }
  const transactions = ev.observed?.transactions ?? {}
  for (const [label, tx] of Object.entries(transactions)) {
    if (!tx.xid) { problems.push(`the ID of transaction "${label}" was not captured inside it`); continue }
    if (tx.fate !== 'committed' && tx.fate !== 'aborted') problems.push(`pg_xact_status() for transaction "${label}" is ${tx.fate === null ? 'unknown' : `"${tx.fate}"`}${tx.fate_error ? ` (${tx.fate_error})` : ''}`)
    // Binding: the ID was read inside a transaction on the reporting session, and is that session's transaction.
    const s = checkpoint(ev, tx.captured_at)?.session
    if (!s?.present) problems.push(`transaction "${label}" is not bound to a session: no session ${tx.pid} at \`${tx.captured_at}\``)
    else if (!s.in_transaction) problems.push(`transaction "${label}" is not bound to its session: at \`${tx.captured_at}\` the session was "${s.state}", not in a transaction`)
    else if (tx.session_xid_matches !== true) problems.push(`transaction "${label}" is not bound to its session: pg_current_xact_id() reported ${tx.xid}, but the session's backend_xid at \`${tx.captured_at}\` is ${s.backend_xid ?? 'NULL'}`)
  }
  if (ev.observed?.markersError) problems.push(`marker visibility could not be read: ${ev.observed.markersError}`)
  // The only combination PostgreSQL cannot produce: a visible row inserted (xmin) by a transaction that pg_xact_status()
  // reports as aborted. It means the observations themselves are wrong.
  for (const [label, xmin] of Object.entries(ev.observed?.marker_xmin ?? {})) {
    if (xmin == null) continue
    for (const [name, t] of Object.entries(transactions)) {
      if (t.fate === 'aborted' && low32(t.xid) === xmin) problems.push(`marker "${label}" is visible, but it was inserted by transaction "${name}" (xid ${t.xid}), which pg_xact_status() reports as aborted`)
    }
  }
  // Attribution: a visible marker whose write the case confirms at a checkpoint must have been inserted by the
  // transaction the case says writes it (its top-level ID, or a subtransaction seen in its locks). Otherwise the
  // observation is about some other transaction. A write the framework may defer (possibly-pending) is not attributed:
  // where it lands is what TX-04 observes, and it can land in a subtransaction created after the last checkpoint.
  for (const [marker, w] of Object.entries(ev.case.marker_writes ?? {})) {
    const xmin = ev.observed?.marker_xmin?.[marker]
    const writer = transactions[w.transaction]
    if (xmin == null || !writer?.xid || w.sent === 'possibly-pending') continue
    const top = low32(writer.xid)
    const subs = subxidsSeen(ev, writer.pid, top)
    const allowed = w.level === 'savepoint' ? subs : [top]
    if (!allowed.includes(xmin)) problems.push(`marker "${marker}" is visible, but its row was inserted by transaction ${xmin}, not by the case's transaction "${w.transaction}" (${top}${subs.length ? `, subtransactions ${subs.join(', ')}` : ''})`)
  }
  if (ev.observed?.stray_rows?.length) problems.push(`the marker table holds rows that are not the case's markers (${ev.observed.stray_rows.map((n) => JSON.stringify(n)).join(', ')}), so an invisible marker would not show what the case wrote`)
  if (Array.isArray(ev.observed?.sessions_at_end) && ev.observed.sessions_at_end.length) problems.push(`${ev.observed.sessions_at_end.length} session(s) were still connected to the case's database after the adapter exited`)
  const poolMax = ev.case.settings?.pool_max
  for (const [name, c] of Object.entries(ev.observed?.checkpoints ?? {})) {
    if (Number.isInteger(poolMax) && c.adapter_sessions > poolMax) problems.push(`at \`${name}\` the case's database had ${c.adapter_sessions} adapter sessions, more than pool_max (${poolMax})`)
    // The same PID must be the same backend wherever a checkpoint reports it.
    for (const [label, t] of Object.entries(transactions)) {
      if (c.reported?.pid === t.pid && c.session?.present && t.backend_start && c.session.backend_start !== t.backend_start) problems.push(`at \`${name}\`, PID ${t.pid} belongs to a different backend than transaction "${label}"'s`)
    }
  }
  const fx = ev.observed?.fixture
  if (fx && fx.before && fx.after && fx.before !== fx.after) problems.push(`the fixture's tables or constraints changed during the run${String(fx.after).startsWith('error') ? ` (${fx.after})` : ''}`)
  return problems
}

/** Classifies one executed case. `statements` maps invariant IDs to their text (from the catalog). */
export function classify(ev, statements) {
  const base = { preconditions: [], invariants: [], not_exercised: [], mechanism_exercised: null }
  const problems = evidenceProblems(ev)
  if (problems.length) return { ...base, classification: 'INCONCLUSIVE', reason: problems.join('; ') }

  const family = FAMILIES[ev.case.family]
  if (!family) return { ...base, classification: 'INCONCLUSIVE', reason: `no classification rules for family ${ev.case.family}` }
  const result = family(ev, statements)
  const preconditions = [...writePreconditions(ev), ...result.preconditions]
  const mechanism = { mechanism_exercised: result.mechanismExercised ?? null, ...(result.mechanismDetail ? { mechanism_detail: result.mechanismDetail } : {}) }
  const unmet = preconditions.filter((p) => !p.met)
  if (unmet.length) {
    return { ...base, ...mechanism, classification: 'INCONCLUSIVE', reason: `precondition not established: ${unmet.map((p) => `${p.description} (${p.detail})`).join('; ')}`, preconditions }
  }
  const { invariants } = result
  const evaluated = invariants.map((i) => i.id).sort().join(', ')
  const declared = [...ev.case.invariants].sort().join(', ')
  if (evaluated !== declared) return { ...base, ...mechanism, classification: 'INCONCLUSIVE', reason: `the rules evaluated [${evaluated}], but the case declares [${declared}]`, preconditions, invariants }
  const violated = invariants.filter((i) => i.holds === false)
  const notEx = invariants.filter((i) => i.not_exercised).map((i) => i.id)
  if (violated.length) return { ...mechanism, classification: 'FAIL', reason: violated.map((i) => `${i.id} violated: ${i.detail}`).join('; '), preconditions, invariants, not_exercised: notEx }
  if (invariants.some((i) => i.holds !== true && !i.not_exercised)) return { ...base, ...mechanism, classification: 'INCONCLUSIVE', reason: `an invariant could not be evaluated: ${invariants.filter((i) => i.holds !== true && !i.not_exercised).map((i) => `${i.id} (${i.detail})`).join('; ')}`, preconditions, invariants }
  if (!invariants.some((i) => i.holds === true)) return { ...base, ...mechanism, classification: 'INCONCLUSIVE', reason: 'no invariant was exercised', preconditions, invariants, not_exercised: notEx }
  const held = invariants.filter((i) => i.holds === true).map((i) => `${i.id} held: ${i.detail}`)
  const skipped = invariants.filter((i) => i.not_exercised).map((i) => `${i.id} not exercised: ${i.detail}`)
  return { ...mechanism, classification: 'PASS', reason: [...held, ...skipped].join('; '), preconditions, invariants, not_exercised: notEx }
}

export const notRun = (reason) => ({ classification: 'NOT_RUN', reason, preconditions: [], invariants: [], not_exercised: [], mechanism_exercised: null })
