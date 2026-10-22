// Records transaction-control results on the pg Client the caller already uses.
// Two optional faults are client-side injections, labeled as such by the experiment:
// rewrite the next ROLLBACK TO SAVEPOINT, or reject the next top-level ROLLBACK
// without sending it.

const CONTROL = /^(begin|start transaction|commit|end|rollback|savepoint|release)\b/i

function seenRow(sql, res, err, settled) {
  return {
    sql: String(sql).slice(0, 120),
    command_tag: typeof res?.command === 'string' ? res.command : null,
    command_present: Boolean(res && Object.prototype.hasOwnProperty.call(res, 'command')),
    row_count: res && Object.prototype.hasOwnProperty.call(res, 'rowCount') ? res.rowCount : null,
    row_count_present: Boolean(res && Object.prototype.hasOwnProperty.call(res, 'rowCount')),
    error_code: err?.code ?? null,
    settled,
    transaction_status: null,
  }
}

export function instrumentPg(pgModule, hooks = {}) {
  const original = pgModule.Client.prototype.query
  const seen = []
  const state = { rewrote: false, rejected: false }
  pgModule.Client.prototype.query = function patchedQuery(...args) {
    let text = typeof args[0] === 'string' ? args[0] : args[0]?.text
    const originalText = typeof text === 'string' ? text.trim() : ''
    if (originalText && hooks.rewriteRollbackTo && !state.rewrote && /^rollback to savepoint\b/i.test(originalText)) {
      state.rewrote = true
      const rewritten = 'ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint'
      if (typeof args[0] === 'string') args[0] = rewritten
      else args[0] = { ...args[0], text: rewritten }
      text = rewritten
    }
    if (originalText && hooks.rejectTopLevelRollback && !state.rejected && /^rollback;?$/i.test(originalText)) {
      state.rejected = true
      seen.push(seenRow(originalText, null, null, 'not_sent'))
      return Promise.reject(new Error('injected client-side failure: ROLLBACK was not sent'))
    }
    const client = this
    const sql = (typeof text === 'string' ? text : originalText).trim().slice(0, 120)
    const record = (res, err) => {
      const row = seenRow(sql, res, err, err ? 'rejected' : 'resolved')
      row.transaction_status = typeof client.getTransactionStatus === 'function' ? client.getTransactionStatus() : null
      seen.push(row)
    }
    const callbackIndex = args.findIndex((arg) => typeof arg === 'function')
    if (originalText && CONTROL.test(typeof text === 'string' ? text.trim() : originalText)) {
      if (callbackIndex >= 0) {
        const originalCallback = args[callbackIndex]
        args[callbackIndex] = (err, res) => {
          record(res, err)
          return originalCallback.call(this, err, res)
        }
      }
    }
    const result = original.apply(this, args)
    if (callbackIndex < 0 && originalText && CONTROL.test(typeof text === 'string' ? text.trim() : originalText) && result?.then) {
      result.then((res) => record(res, null), (err) => record(null, err))
    }
    return result
  }
  return {
    seen,
    state,
    restore() { pgModule.Client.prototype.query = original },
  }
}
