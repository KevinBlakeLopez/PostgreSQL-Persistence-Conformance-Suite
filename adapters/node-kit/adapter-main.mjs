// The entry point shared by the JavaScript adapters: read the case, say hello, open the framework, run the case's
// native implementation, send the result, close the framework within a bound, exit.
//
// An adapter supplies:
//   describe()            -> { adapter, framework, driver, components }   versions, read from the installed packages
//   modes                 -> { [modeId]: { configuration } }               what each execution mode changes
//   open(message, mode)   -> { context, close(), diagnostics() }           framework setup for one case
//   cases                 -> { [caseId]: async (context, tools) => ({ reported, basis, api_error?, steps?, form? }) }
//
// `form` names the native form a case implementation used, where the case leaves the framework a choice (for example,
// a flushed or a pending write), with the reason for the choice. The runner records it in the result.
//
// As soon as the case implementation has returned (the framework's API has returned), main() sends the checkpoint
// `after-end`, so that the runner can record the state at report time, before the framework is closed.
import { readCase, hello, checkpoint as sendCheckpoint, finish } from './protocol.mjs'
import { errInfo, withTimeout } from './util.mjs'

/** A failure of the protocol itself. It must surface as an adapter error, never as the framework's outcome. */
export class ProtocolError extends Error {}

export async function main({ describe, modes, open, cases, closeTimeoutMs = 5000 }) {
  const message = await readCase()
  const mode = modes[message.mode]
  const info = describe()
  await hello({ ...info, runtime: { name: 'node', version: process.version }, mode: message.mode, configuration: mode?.configuration ?? {} })

  const impl = cases[message.case.id]
  if (!mode) return exit({ status: 'error', error: { class: 'AdapterError', code: null, message: `unknown mode "${message.mode}"` } })
  if (!impl) return exit({ status: 'not_implemented', reason: `this adapter does not implement ${message.case.id}` })

  const checkpoint = async (name, data = {}) => {
    try { return await sendCheckpoint(name, data) } catch (e) { throw new ProtocolError(`checkpoint "${name}": ${e.message}`) }
  }
  let opened = null
  let result
  try {
    opened = await open(message, mode)
    const outcome = await impl(opened.context, { markers: message.markers, settings: message.case.settings ?? {}, mode: message.mode, repetition: message.repetition ?? 1, checkpoint, ProtocolError })
    await checkpoint('after-end', {})
    result = { status: 'completed', ...outcome }
  } catch (e) {
    result = { status: 'error', error: { ...errInfo(e), protocol: e instanceof ProtocolError } }
  }
  const diagnostics = opened?.diagnostics?.() ?? {}
  if (opened?.close) {
    const closed = await withTimeout(opened.close(), closeTimeoutMs)
    if (closed.timedOut) diagnostics.close = `the framework did not close within ${closeTimeoutMs} ms`
    else if (closed.error) diagnostics.close = `closing the framework failed: ${closed.error.message}`
  }
  return exit({ ...result, diagnostics })
}

/**
 * Runs a unit of work within `boundMs`: `run(checkpoint)` must return a managedOutcome() result. Returns that result with
 * { outcome: 'completed', elapsed_ms }, or { outcome: 'pending', elapsed_ms } if the bound passes first. A pending unit
 * is abandoned: if it gets a connection later, its checkpoints are refused, so it cannot interleave with the result.
 */
export async function boundedUnit(boundMs, checkpoint, run) {
  let abandoned = false
  const guarded = (name, data) => (abandoned ? Promise.reject(new ProtocolError(`checkpoint "${name}" after the unit was abandoned`)) : checkpoint(name, data))
  const started = Date.now()
  const settled = await withTimeout(run(guarded), boundMs)
  if (settled.timedOut) {
    abandoned = true
    return { outcome: 'pending', elapsed_ms: boundMs }
  }
  if (settled.error) throw new ProtocolError(`the unit of work failed outside the framework: ${settled.error.message}`)
  return { outcome: 'completed', elapsed_ms: Date.now() - started, ...settled.value }
}

async function exit(result) {
  await finish(result)
  process.exit(0)
}

/**
 * Runs an explicit transaction: `start()` returns a transaction handle, `body(handle)` is the case's work, `commit(handle)`
 * commits it, and `rollback(handle)` rolls it back. Maps what the API did onto PPCS's reported outcome:
 *   commit resolved                        -> committed
 *   start raised, or commit raised         -> failed (no outcome asserted)
 * An error from the body is the case's own failure, not the framework's outcome: the transaction is rolled back and the
 * error rethrown. `state.started` is set once start() has returned a handle (TX-05 needs to know).
 *
 * `api` names the calls and states the framework's contract: { start, commit, contract }.
 */
export async function explicitOutcome({ start, commit, rollback }, body, api, state = {}) {
  let handle
  try {
    handle = await start()
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    return { reported: 'failed', basis: `${api.start} raised before it returned a transaction`, contract: api.contract, api_error: errInfo(e) }
  }
  state.started = true
  try {
    await body(handle)
  } catch (e) {
    await Promise.resolve().then(() => rollback(handle)).catch(() => {})
    throw e
  }
  try {
    await commit(handle)
    return { reported: 'committed', basis: `${api.commit} resolved`, contract: api.contract }
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    return { reported: 'failed', basis: `${api.commit} raised`, contract: api.contract, api_error: errInfo(e) }
  }
}

/**
 * TX-05: a transaction at a requested isolation level, run by `attempt(state)`, which sets `state.started` as soon as the
 * framework's API has started the transaction (its callback ran, or its handle came back). If the API raised before that,
 * `plain()` runs a transaction through the same API form with no isolation level, and reports the checkpoint `baseline`.
 * If the plain transaction works, the database and the API form work, so the runner can read the rejection as one of
 * the requested level. A failure of the plain transaction is reported in steps.baseline.
 */
export async function requestedLevel(attempt, plain) {
  const state = { started: false }
  const outcome = await attempt(state)
  if (state.started || outcome.reported !== 'failed') return outcome
  try {
    await plain()
    return outcome
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    return { ...outcome, steps: { ...(outcome.steps ?? {}), baseline: { error: errInfo(e) } } }
  }
}

/**
 * Runs a managed (callback) transaction and maps what the API did onto PPCS's reported outcome:
 *   resolved                                   -> committed
 *   rejected with the callback's own error      -> rolled_back (the managed-transaction contract: roll back, rethrow)
 *   rejected with any other error               -> failed (no outcome asserted)
 * A ProtocolError is rethrown, so that it can never be read as the framework's outcome.
 *
 * `api` names the call and states the framework's contract for it: { call: 'db.transaction(callback)', contract: '...' }.
 * The result's `basis` is what was observed; `contract` is what gives it its meaning, and the report quotes it as the
 * contract basis of a FAIL.
 */
export async function managedOutcome(run, body, api) {
  let thrown = null
  try {
    await run(async (...args) => {
      try { return await body(...args) } catch (e) { thrown = e; throw e }
    })
    return { reported: 'committed', basis: `${api.call} resolved`, contract: api.contract }
  } catch (e) {
    if (e instanceof ProtocolError || thrown instanceof ProtocolError) throw thrown ?? e
    if (e === thrown) return { reported: 'rolled_back', basis: `${api.call} rejected with the error the callback threw`, contract: api.contract, api_error: errInfo(e) }
    return { reported: 'failed', basis: `${api.call} rejected with an error the callback did not throw`, contract: api.contract, api_error: errInfo(e) }
  }
}
