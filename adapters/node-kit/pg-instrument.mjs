// Statement tracing and client-side fault injection for adapters whose framework uses node-postgres (`pg`).
// Ported from the reused experiment harnesses (docs/provenance.md). The adapter passes in the `pg` module its framework
// resolves, so the patch sees every statement the framework sends, tagged with the backend PID that ran it.
//
// The trace is adapter-side diagnostic evidence: what the driver sent and what it received. Classification never
// depends on it; the runner's own observations decide.
//
// Fault modes. Each one is client-side injection (categories C and D in docs/methodology.md), never a real network
// failure:
//   client-reject  the statement is not sent; the driver reports an error, as a failed send would
//   rewrite        the statement is altered before it is sent, so that PostgreSQL rejects it
//   reply-lost     the statement is sent and completes on the server; then the client closes its own connection and
//                  discards the reply (a simulation inside the driver, not a network fault)
//
// A fault can carry an `onFire` hook (client-reject and rewrite). It runs once the fault has taken effect (the
// statement withheld, or PostgreSQL's reply to the rewritten one received) and before the framework sees the error,
// so the adapter can report the checkpoint `after-fault` and the runner can observe the fault's effect on the server
// before the framework reacts to it.
const TX_CONTROL = /^(begin|start transaction|commit|end|rollback|savepoint|release)\b/i

/**
 * The two savepoint-rollback faults of TX-02, as the reused experiments injected them: `not-sent` fails the next
 * ROLLBACK TO SAVEPOINT without sending it; `rejected` rewrites it to name a savepoint that does not exist, so that
 * PostgreSQL rejects it.
 */
export function savepointRollbackFault(tracer, kind, onFire) {
  const match = /^rollback to (savepoint )?/i
  return kind === 'not-sent'
    ? tracer.addFault({ match, mode: 'client-reject', onFire })
    : tracer.addFault({ match, mode: 'rewrite', rewrite: () => 'ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint', onFire })
}

/** A fault as the adapter reports it in `steps.fault`: its mode, how often it fired, and, for a rewrite, PostgreSQL's replies. */
export const faultReport = (fault) => ({ mode: fault.mode, fired: fault.fired ?? 0, ...(fault.reply_codes ? { reply_codes: [...fault.reply_codes] } : {}), ...(fault.hook_error ? { hook_error: fault.hook_error } : {}) })

export function instrument(pg) {
  const entries = []
  const faults = []
  const originalQuery = pg.Client.prototype.query

  const record = (client, text, kind = 'sql') => {
    entries.push({ pid: client.processID ?? null, sql: String(text).trim().replace(/\s+/g, ' ').slice(0, 300), kind })
  }
  const observe = (client, text, err, res) => {
    if (err) record(client, `-> ERROR ${err.code ?? ''} ${String(err.message).split('\n')[0]}`, 'error')
    else if (res && typeof text === 'string' && TX_CONTROL.test(text.trim()) && res.command) record(client, `-> command tag ${res.command} for: ${text.trim()}`, 'reply')
  }
  // Runs the fault's onFire hook. A failure of the hook (a protocol failure) is recorded on the fault, never thrown
  // into the framework, which must see only the injected error.
  const fire = async (fault) => {
    if (!fault.onFire) return
    try { await fault.onFire() } catch (e) { fault.hook_error = String(e?.message ?? e) }
  }
  const issue = (client, config, vals, cb, text) => {
    if (cb) {
      const wrapped = (err, res) => { observe(client, text, err, res); cb(err, res) }
      return vals === undefined ? originalQuery.call(client, config, wrapped) : originalQuery.call(client, config, vals, wrapped)
    }
    const result = vals === undefined ? originalQuery.call(client, config) : originalQuery.call(client, config, vals)
    if (result && typeof result.then === 'function') result.then((r) => observe(client, text, null, r), (e) => observe(client, text, e))
    return result
  }

  // knex calls client.query(config, callback); MikroORM (Kysely) and TypeORM use the promise form. Both are handled.
  pg.Client.prototype.query = function patchedQuery(config, values, callback) {
    const text = typeof config === 'string' ? config : config?.text
    const cb = typeof values === 'function' ? values : callback
    const vals = typeof values === 'function' ? undefined : values
    if (typeof text !== 'string') return issue(this, config, vals, cb, text)
    const fault = faults.find((f) => !f.used && f.match.test(text.trim()))
    if (fault) {
      if (fault.once) fault.used = true
      fault.fired = (fault.fired ?? 0) + 1
      if (fault.mode === 'client-reject') {
        record(this, `${text}  -- INJECTED client-side failure, statement NOT sent`, 'fault')
        const err = new Error(`injected client-side failure for: ${text.trim().slice(0, 60)}`)
        if (cb) { fire(fault).then(() => cb(err)); return undefined }
        return fire(fault).then(() => { throw err })
      }
      if (fault.mode === 'rewrite') {
        const rewritten = fault.rewrite(text)
        record(this, `${rewritten}  -- INJECTED rewrite of: ${text.trim()}`, 'fault')
        // PostgreSQL's reply to the rewritten statement (its SQLSTATE, or "ok") is the evidence that the fault took effect.
        fault.reply_codes = fault.reply_codes ?? []
        const note = (err) => fault.reply_codes.push(err ? (err.code ?? 'error') : 'ok')
        const rewrittenConfig = typeof config === 'string' ? rewritten : { ...config, text: rewritten }
        if (cb) return issue(this, rewrittenConfig, vals, (err, res) => { note(err); fire(fault).then(() => cb(err, res)) }, rewritten)
        return issue(this, rewrittenConfig, vals, undefined, rewritten).then(
          (res) => { note(null); return fire(fault).then(() => res) },
          (err) => { note(err); return fire(fault).then(() => { throw err }) },
        )
      }
      if (fault.mode === 'reply-lost') {
        record(this, `${text}  -- INJECTED (client-side simulation): sent, then the client closes its connection and discards the reply`, 'fault')
        const client = this
        const lost = () => new Error(`connection lost after sending: ${text.trim().slice(0, 60)}`)
        const finish = () => { client.end().catch(() => {}) }
        if (cb) {
          const callback = () => { finish(); process.nextTick(() => cb(lost())) }
          vals === undefined ? originalQuery.call(client, config, callback) : originalQuery.call(client, config, vals, callback)
          return undefined
        }
        const sent = vals === undefined ? originalQuery.call(client, config) : originalQuery.call(client, config, vals)
        return sent.then(() => { finish(); throw lost() }, () => { finish(); throw lost() })
      }
    }
    record(this, text)
    return issue(this, config, vals, cb, text)
  }

  return {
    /** Adds a fault: { match: RegExp, mode, rewrite?, onFire?, once = true }. Returns it, so its `fired` count can be read. */
    addFault(f) { const fault = { once: true, used: false, ...f }; faults.push(fault); return fault },
    clearFaults() { faults.length = 0 },
    /** The trace, with stable connection labels (c1, c2, ...) in order of first appearance. */
    trace() {
      const labels = new Map()
      return entries.map((e) => {
        if (e.pid != null && !labels.has(e.pid)) labels.set(e.pid, `c${labels.size + 1}`)
        return `${e.pid == null ? '??' : `${labels.get(e.pid)}(pid ${e.pid})`}: ${e.sql}`
      })
    },
    /** The command tags PostgreSQL returned for COMMIT statements, in order. */
    commitReplies: () => entries.filter((e) => e.kind === 'reply' && /for: (commit|end)\b/i.test(e.sql)).map((e) => e.sql.match(/command tag (\S+)/)[1]),
  }
}
