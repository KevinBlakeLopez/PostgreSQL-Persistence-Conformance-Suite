// Shared bodies for the production-reachability cases.
//
// A harness PASS on PR-01 means the independent evidence is complete. It does not mean the
// framework reported the commit correctly. research/production-reachability/reachability.mjs
// reads the recorded outcome and classifies the contract.
import { ProtocolError, managedOutcome } from '../../../adapters/node-kit/adapter-main.mjs'

export function violationInfo(e) {
  const seen = new Set()
  const stack = [e]
  let code = null
  while (stack.length) {
    const cur = stack.pop()
    if (!cur || typeof cur !== 'object' || seen.has(cur)) continue
    seen.add(cur)
    for (const key of ['code', 'sqlState', 'sqlstate']) {
      if (code == null && typeof cur[key] === 'string' && /^[0-9A-Z]{5}$/.test(cur[key])) code = cur[key]
    }
    for (const next of [cur.driverError, cur.cause, cur.original, cur.parent]) if (next) stack.push(next)
  }
  return { class: e?.constructor?.name ?? 'Error', code, message: String(e?.message ?? e).split('\n')[0].slice(0, 500) }
}

function unsupported(reason) {
  return { status: 'not_implemented', reason }
}

async function explicitRun(api, body) {
  const names = api.explicit.names
  const contract = api.explicit.contract
  let handle
  try {
    handle = await api.explicit.start()
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    return { reported: 'failed', basis: `${names.start} raised before it returned a transaction`, contract, api_error: violationInfo(e) }
  }
  let thrown = null
  try {
    await body(handle)
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    thrown = e
  }
  if (thrown) {
    try {
      await api.explicit.rollback(handle)
    } catch (e) {
      if (e instanceof ProtocolError) throw e
      return {
        reported: 'failed',
        basis: `${names.rollback} raised after the body threw`,
        contract,
        api_error: violationInfo(e),
        steps: { body_error: violationInfo(thrown) },
      }
    }
    return { reported: 'rolled_back', basis: `the body threw and ${names.rollback} completed`, contract, api_error: violationInfo(thrown) }
  }
  try {
    const commitResult = await api.explicit.commit(handle)
    if (commitResult?.reported) return { ...commitResult, contract: commitResult.contract ?? contract }
  } catch (e) {
    if (e instanceof ProtocolError) throw e
    return { reported: 'failed', basis: `${names.commit} raised`, contract, api_error: violationInfo(e) }
  }
  return { reported: 'committed', basis: `${names.commit} resolved`, contract }
}

/**
 * `kind` is managed, explicit, control, or savepoint.
 * Control uses the managed API and lets the unique violation leave the callback.
 * Savepoint uses the managed API unless `api.savepointOn` is `explicit`.
 */
export async function runPr(kind, api, { markers, checkpoint }) {
  if (kind === 'explicit' && !api.explicit) return unsupported(api.unsupported?.explicit ?? 'this framework has no explicit transaction API')
  if (kind === 'savepoint' && !api.savepoint) return unsupported(api.unsupported?.savepoint ?? 'this framework has no savepoint API')

  const steps = { variant: kind }
  let pid = null
  const body = async (handle) => {
    await api.write(handle, markers.tx)
    const id = await api.identify(handle)
    if (!id?.xid || !Number.isInteger(id.pid)) throw new ProtocolError('identify did not return xid and pid')
    pid = id.pid
    await checkpoint('after-write', { xid: String(id.xid), pid: id.pid })
    if (kind === 'control') {
      try {
        await api.insertTaken(handle)
        throw new ProtocolError('the duplicate insert did not raise')
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        steps.violation = violationInfo(e)
        throw e
      }
    }
    if (kind === 'savepoint') {
      try {
        steps.savepoint = await api.savepoint(handle)
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        steps.savepoint = { recovered: false, error: violationInfo(e) }
        steps.violation = violationInfo(e)
        await checkpoint('before-end', { pid })
        throw e
      }
      steps.violation = steps.savepoint?.violation ?? null
      if (steps.violation?.code !== '23505') throw new ProtocolError(`the savepoint statement did not raise 23505 (${steps.violation?.code ?? 'nothing'})`)
    } else {
      try {
        await api.insertTaken(handle)
        throw new ProtocolError('the duplicate insert did not raise')
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        steps.violation = violationInfo(e)
      }
    }
    await checkpoint('before-end', { pid })
  }

  const useExplicit = kind === 'explicit' || (kind === 'savepoint' && api.savepointOn === 'explicit')
  const outcome = useExplicit ? await explicitRun(api, body) : await api.managed(body)
  await checkpoint('after-api', pid == null ? {} : { pid })
  let probe = { supported: false }
  if (api.probe) {
    try { probe = await api.probe() } catch (e) {
      if (e instanceof ProtocolError) throw e
      probe = { supported: true, ok: false, error: violationInfo(e) }
    }
  }
  steps.probe = probe
  steps.hooks = api.hooks?.() ?? { supported: false }
  steps.command_tag = api.commandTag?.() ?? null
  steps.driver = api.extras?.() ?? null
  steps.reuse = await api.reuse(markers.reuse, checkpoint)
  if (pid != null && steps.reuse) steps.reuse.same_backend = steps.reuse.pid == null ? null : steps.reuse.pid === pid
  const form = api.forms?.[kind] ?? null
  const contract = outcome.contract ?? api.contracts?.[kind] ?? api.contracts?.managed
  return { ...outcome, contract, steps: { ...(outcome.steps ?? {}), ...steps }, ...(form ? { form } : {}) }
}

export function prCaseHandlers(apiFor) {
  return {
    'PR-01.managed-catch-commit': (ctx, tools) => runPr('managed', apiFor(ctx, tools), tools),
    'PR-01.explicit-catch-commit': (ctx, tools) => runPr('explicit', apiFor(ctx, tools), tools),
    'PR-01.uncaught-control': (ctx, tools) => runPr('control', apiFor(ctx, tools), tools),
    'PR-01.savepoint-recovery': (ctx, tools) => runPr('savepoint', apiFor(ctx, tools), tools),
  }
}

/** A managed transaction whose resolved call is reported as committed. Used by the research drivers' CTL-01. */
export function driverManaged(run, body, api) {
  return managedOutcome(run, body, api)
}
