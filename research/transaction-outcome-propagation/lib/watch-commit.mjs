// Statement-completion watch for the TypeORM subject.
// The wrapper records Result.command on the object Client.query returns.
// It is diagnostic instrumentation. It is not a TypeORM API, and it does not
// change the result the framework receives.

const COMMIT = /^commit\b/i

export function watchCommits(pgModule) {
  const original = pgModule.Client.prototype.query
  const seen = []
  pgModule.Client.prototype.query = function patchedQuery(...args) {
    const config = args[0]
    const text = typeof config === 'string' ? config : config?.text
    const result = original.apply(this, args)
    if (typeof text === 'string' && COMMIT.test(text.trim())) {
      const client = this
      const sql = text.trim().slice(0, 80)
      const record = (res, err) => {
        try {
          seen.push({
            sql,
            command_tag: res && typeof res.command === 'string' ? res.command : null,
            command_present: Boolean(res && Object.prototype.hasOwnProperty.call(res, 'command')),
            row_count: res && Object.prototype.hasOwnProperty.call(res, 'rowCount') ? res.rowCount : null,
            row_count_present: Boolean(res && Object.prototype.hasOwnProperty.call(res, 'rowCount')),
            error_code: err?.code ?? null,
            settled: err ? 'rejected' : 'resolved',
            transaction_status: typeof client.getTransactionStatus === 'function' ? client.getTransactionStatus() : null,
          })
        } catch {
          seen.push({
            sql,
            command_tag: null,
            command_present: false,
            row_count: null,
            row_count_present: false,
            error_code: null,
            settled: 'record_failed',
            transaction_status: null,
          })
        }
      }
      if (result && typeof result.then === 'function') {
        result.then((res) => record(res, null), (err) => record(null, err))
      } else {
        seen.push({
          sql,
          command_tag: null,
          command_present: false,
          row_count: null,
          row_count_present: false,
          error_code: null,
          settled: 'not_a_promise',
          transaction_status: null,
        })
      }
    }
    return result
  }
  return {
    seen,
    restore() {
      pgModule.Client.prototype.query = original
    },
  }
}
