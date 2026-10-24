// One migration case. Each role is its own adapter process, named by application_name ppcs-A, ppcs-B or ppcs-C.
//
// When the case has a SQL gate, the runner holds advisory lock 77002002 on its own session. The migration waits on
// that lock after inserting its marker, so a second connection can see who is inside the migration. The runner's
// session is not one of them: its PID is one of the runner's connections and its name is ppcs-observer.
//
// Session-loss repeats the scenario once per session of A that was connected at the gate, each time on a fresh
// database, and keeps the worst result. The session is chosen by its place in PID order.
//
// First-deployment starts with no history storage. The runner creates a table with the adapter's history-table name
// in its own transaction and holds it uncommitted, so both runners find no history storage and wait on that creation,
// or on the framework's own coordination. Rolling it back makes their creations collide, whatever their start times.
import { runAdapter } from './adapter-process.mjs'
import { classify } from './classify.mjs'
import { RESULT_SCHEMA } from './run-case.mjs'

const UNKNOWN = 'UNKNOWN'
const GATE = 77002002
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const roleOf = (name) => (typeof name === 'string' && name.startsWith('ppcs-') ? name.slice('ppcs-'.length) : null)

export async function runMigrationCase({ instance, observer, catalog, adapter, mode, kase, runId, harness, repetition = 1, timeoutMs = 60000 }) {
  const startedAt = new Date()
  const indexes = kase.settings?.enumerate === 'sessions-of-A' ? [0] : [null]
  const runs = []
  for (let i = 0; i < indexes.length; i += 1) {
    const run = await oneDatabase({ instance, observer, catalog, adapter, mode, kase, repetition, timeoutMs, terminateIndex: indexes[i] })
    runs.push(run)
    if (i === 0 && kase.settings?.enumerate === 'sessions-of-A') {
      for (let j = 1; j < run.sessionCount; j += 1) indexes.push(j)
    }
  }
  const worst = runs.find((r) => r.evaluation?.classification === 'FAIL')
    ?? runs.find((r) => r.evaluation?.classification === 'INCONCLUSIVE')
    ?? runs[runs.length - 1]
  // Classification is applied once, on the chosen run, inside finishRecord.
  return finishRecord(worst, { instance, catalog, adapter, mode, kase, runId, harness, repetition, startedAt })
}

async function oneDatabase({ instance, observer, catalog, adapter, mode, kase, repetition, timeoutMs, terminateIndex }) {
  const tag = `${repetition.toString(36)}${terminateIndex ?? 'x'}${Math.random().toString(16).slice(2, 6)}`
  const markers = Object.fromEntries(kase.markers.map((label) => [label, `${label}-${tag}`]))
  const database = await instance.createDatabase(`ppcs_${kase.id.replace(/[^A-Za-z0-9]+/g, '_')}`)
  const useGate = kase.settings?.gate === 'sql'
  let held = null
  const protocolErrors = []
  const childRecords = []
  try {
    await instance.query(database, catalog.fixture.sql)
    await instance.query(database, 'create table if not exists ppcs_undo (id bigserial primary key, name text not null)')
    // An uninitialized database has no history storage, not even the controls' (MG-02.first-deployment).
    if (kase.settings?.database !== 'uninitialized') await instance.query(database, 'create table if not exists ppcs_history (name text not null)')
    const observed = {
      checkpoints: {}, transactions: {}, markers: null, marker_xmin: null, stray_rows: null, sessions_at_end: null,
      fixture: { before: await observer.fixtureFingerprint(database), after: null },
      marker_counts: {}, history_counts: {}, inside_migration: [], session_ended: false,
    }
    const launch = (role, operation) => launchRole({ instance, adapter, mode, kase, database, markers, repetition, timeoutMs, role, operation })
    const runners = {}
    let sessionCount = 0
    const bound = kase.settings?.bound_ms ?? 3000
    if (useGate) {
      held = await instance.borrow(database)
      await held.query('select pg_advisory_lock($1)', [GATE])
    }

    if (kase.family === 'MG-03') {
      const applied = await launch('A', 'apply')
      childRecords.push(applied)
      observed.apply_reported = outcomeOf(applied).reported
      const reverted = await launch('A', 'revert')
      childRecords.push(reverted)
      observed.after_revert = await counts(observer, database, adapter, markers)
      if (kase.id !== 'MG-03.failing-reversal') childRecords.push(await launch('A', 'apply'))
      runners.A = outcomeOf(reverted)
    } else if (kase.id === 'MG-02.first-deployment') {
      const hold = kase.settings?.hold === 'history-table' ? await holdCreation(instance, database, adapter.history?.table) : null
      const finished = {}
      const pending = kase.settings.runners.map((role) => launch(role, 'apply').then((record) => { finished[role] = record; return record }))
      if (hold) {
        try {
          observed.creation_hold = { table: adapter.history.table, ...await awaitHold(observer, database, kase.settings.runners, finished, kase.settings.hold_ms ?? 10000) }
        } finally {
          await hold.query('rollback').catch(() => {})
          await hold.end().catch(() => {})
        }
      }
      observed.inside_migration = await watchRoles(observer, database, bound)
      await unlock(held)
      const gate = held
      held = null
      childRecords.push(...await Promise.all(pending))
      await gate?.end().catch(() => {})
      for (const record of childRecords) runners[record.role] = outcomeOf(record)
    } else {
      const pendingA = launch('A', 'apply')
      await waitForRole(observer, database, 'A', bound)
      const atGate = await observer.roleSessions(database, 'A')
      sessionCount = atGate.length
      if (kase.id === 'MG-02.idle-session-timeout') observed.session_ended = await sessionDisappears(observer, database, atGate.map((s) => s.pid), 4000)
      const pendingB = launch('B', 'apply')
      observed.inside_migration = await watchRoles(observer, database, bound)
      if (Number.isInteger(terminateIndex)) {
        const sessions = await observer.roleSessions(database, 'A')
        sessionCount = Math.max(sessionCount, sessions.length)
        const target = sessions[Math.min(terminateIndex, sessions.length - 1)]
        if (target) {
          const terminated = await instance.terminateBackend(database, target.pid)
          const gone = terminated ? await observer.waitGone(database, target.pid) : false
          observed.session_ended = gone
          observed.terminated = { pid: target.pid, gone }
        }
      }
      await unlock(held)
      const gate = held
      held = null
      childRecords.push(await pendingA, await pendingB)
      await gate?.end().catch(() => {})
      if (kase.settings.runners.includes('C')) childRecords.push(await launch('C', 'apply'))
      for (const record of childRecords) runners[record.role] = outcomeOf(record)
    }

    const finalCounts = await counts(observer, database, adapter, markers)
    observed.marker_counts = finalCounts.marker_counts
    observed.history_counts = finalCounts.history_counts
    observed.markers = Object.fromEntries(kase.markers.map((label) => [label, (observed.marker_counts[label] ?? 0) > 0]))
    observed.stray_rows = await observer.strayRows(database, markers)
    observed.sessions_at_end = await observer.settle(database)
    observed.fixture.after = await observer.fixtureFingerprint(database).catch((e) => `error: ${String(e.message)}`)
    const sessions = await observer.sessions(database)
    observed.checkpoints['inside-A'] = { reported: { pid: null, xid: null }, adapter_sessions: sessions.length, sessions }
    observed.checkpoints['after-end'] = { reported: { pid: null, xid: null }, adapter_sessions: observed.sessions_at_end.length, sessions: observed.sessions_at_end }
    return { observed, runners, childRecords, protocolErrors, sessionCount }
  } finally {
    await unlock(held)
    await held?.end().catch(() => {})
    if (!process.env.PPCS_KEEP_DB) await instance.dropDatabase(database)
  }
}

/** A transaction on the runner's own connection that creates `table` and stays open, uncommitted. */
async function holdCreation(instance, database, table) {
  if (!/^[a-z_][a-z0-9_]*$/.test(table ?? '')) throw new Error(`history table is not an identifier: ${JSON.stringify(table)}`)
  const c = await instance.borrow(database)
  try {
    await c.query('begin')
    await c.query(`create table ${table} (ppcs_creation_hold integer)`)
    return c
  } catch (e) {
    await c.end().catch(() => {})
    throw e
  }
}

/**
 * Waits until each role has a session waiting on a lock or has already reported failure, with at least one role
 * waiting, or until `waitMs` has passed. A runner that the framework's coordination refuses outright exits with a
 * failure instead of waiting.
 */
async function awaitHold(observer, database, roles, finished, waitMs) {
  const started = Date.now()
  let blocked = []
  let failed = []
  const established = () => blocked.length > 0 && roles.every((r) => blocked.includes(r) || failed.includes(r))
  while (Date.now() - started < waitMs) {
    blocked = await observer.blockedRoles(database, roles)
    failed = roles.filter((r) => finished[r] && outcomeOf(finished[r]).exit_code !== 0)
    if (established()) break
    await sleep(50)
  }
  return { blocked_roles: blocked, failed_before_release: failed, established: established(), waited_ms: Date.now() - started }
}

async function unlock(held) {
  if (held) await held.query('select pg_advisory_unlock($1)', [GATE]).catch(() => {})
}

function launchRole({ instance, adapter, mode, kase, database, markers, repetition, timeoutMs, role, operation }) {
  const options = kase.settings?.connection_options?.[role]
  return runAdapter({
    command: adapter.command,
    cwd: adapter.dir,
    timeoutMs,
    redact: [instance.settings.password],
    onCheckpoint: async () => ({ actions: [] }),
    message: {
      case: { id: kase.id, family: kase.family, version: kase.version, title: kase.title, settings: kase.settings ?? {} },
      mode: mode.id,
      repetition,
      connection: { ...instance.connection(database, `ppcs-${role}`), ...(options ? { options } : {}) },
      markers,
      migration: {
        role, operation, gate: GATE, migrationId: 'm1',
        reversal: kase.settings?.reversal?.m1 ?? 'valid',
        transactional: kase.settings?.transactional === true,
        hold: kase.settings?.gate === 'sql' && operation === 'apply',
      },
    },
  }).then((record) => ({ ...record, role }))
}

async function waitForRole(observer, database, role, boundMs) {
  const deadline = Date.now() + boundMs
  while (Date.now() < deadline) {
    const rows = await observer.gateWaiters(database, GATE)
    if (rows.some((r) => roleOf(r.application_name) === role)) return true
    await sleep(50)
  }
  return false
}

/** Roles waiting on the gate. Returns early once two roles are waiting; otherwise waits out the bound. */
async function watchRoles(observer, database, boundMs) {
  const deadline = Date.now() + boundMs
  let best = []
  while (Date.now() < deadline) {
    const rows = await observer.gateWaiters(database, GATE)
    const now = [...new Set(rows.map((r) => roleOf(r.application_name)).filter(Boolean))]
    if (now.length > best.length) best = now
    if (best.length >= 2) return best
    await sleep(50)
  }
  return best
}

async function sessionDisappears(observer, database, pids, waitMs) {
  const deadline = Date.now() + waitMs
  const initial = new Set(pids)
  while (Date.now() < deadline) {
    const now = new Set((await observer.roleSessions(database, 'A')).map((s) => s.pid))
    if ([...initial].some((pid) => !now.has(pid))) return true
    await sleep(100)
  }
  return false
}

async function counts(observer, database, adapter, markers) {
  const marker_counts = {}
  for (const [label, value] of Object.entries(markers)) marker_counts[label] = await observer.markerCount(database, value)
  const history_counts = {}
  for (const label of Object.keys(markers)) history_counts[label] = await observer.historyCount(database, adapter.history.table)
  return { marker_counts, history_counts }
}

function outcomeOf(record) {
  const result = record?.result ?? {}
  if (!record || record.timedOut) return { reported: 'pending', exit_code: 1, api_error: { class: 'Timeout', code: null, message: 'the runner did not finish' } }
  const exitCode = Number.isInteger(result.exit_code) ? result.exit_code : (record.exit?.code ?? 1)
  if (result.status !== 'completed') return { reported: 'failed', exit_code: exitCode || 1, api_error: result.error ?? { class: 'Error', code: null, message: result.reason ?? 'the runner did not complete' } }
  return { reported: result.reported, exit_code: exitCode, api_error: result.api_error ?? null, basis: result.basis ?? null, contract: result.contract ?? null }
}

function finishRecord(run, { instance, catalog, adapter, mode, kase, runId, harness, repetition, startedAt }) {
  const primary = run.childRecords.find((r) => r.role === 'A') ?? run.childRecords[0] ?? {}
  const result = primary.result ?? {}
  const hello = primary.hello ?? {}
  const evidence = {
    case: kase,
    adapterStatus: run.childRecords.length && run.childRecords.every((r) => r.result) ? 'completed' : 'error',
    adapterReason: result.reason ?? null,
    adapterError: result.error ? `${result.error.class ?? 'Error'}: ${result.error.message ?? ''}` : null,
    reported: result.reported ?? null,
    apiError: result.api_error ?? null,
    runners: run.runners,
    steps: {},
    observed: run.observed,
    adapter: { rollbackClaimChannels: adapter.rollback_claim_channels ?? [] },
    harness: {
      timedOut: run.childRecords.some((r) => r.timedOut),
      timeoutMs: 60000,
      helloReceived: run.childRecords.some((r) => r.hello),
      exit: primary.exit ?? null,
      protocolErrors: [...run.protocolErrors, ...run.childRecords.flatMap((r) => r.protocolErrors ?? [])],
      missingCheckpoints: [],
    },
  }
  const evaluation = classify(evidence, catalog.statements)
  const finishedAt = new Date()
  return {
    schema: RESULT_SCHEMA,
    run_id: runId,
    harness,
    specification: {
      id: kase.id, version: kase.version, family: kase.family,
      family_title: catalog.families[kase.family]?.title ?? UNKNOWN,
      family_version: catalog.families[kase.family]?.version ?? UNKNOWN,
      kind: kase.kind, title: kase.title, steps: kase.steps,
      invariants: kase.invariants.map((id) => ({ id, statement: catalog.statements[id] ?? UNKNOWN })),
      catalog: catalog.path, catalog_sha256: catalog.sha256,
    },
    subject: {
      adapter: { name: adapter.name, version: hello.adapter?.version ?? UNKNOWN, source_sha256: adapter.sourceSha256 },
      framework: { name: hello.framework?.name ?? UNKNOWN, version: hello.framework?.version ?? UNKNOWN },
      driver: { name: hello.driver?.name ?? UNKNOWN, version: hello.driver?.version ?? UNKNOWN },
      components: hello.components ?? {},
      runtime: { name: hello.runtime?.name ?? UNKNOWN, version: hello.runtime?.version ?? UNKNOWN },
    },
    execution: { mode: mode.id, kind: mode.kind, description: mode.description, configuration: hello.configuration ?? {}, form: result.form ?? null },
    configuration: kase.settings ?? {},
    server: { ...instance.server, image: instance.settings.image ?? UNKNOWN },
    fault: kase.fault,
    knowledge: kase.knowledge ?? null,
    api_outcome: {
      reported: run.runners.A?.reported ?? result.reported ?? UNKNOWN,
      basis: run.runners.A?.basis ?? result.basis ?? null,
      contract: run.runners.A?.contract ?? result.contract ?? null,
      error: run.runners.A?.api_error ?? result.api_error ?? null,
      steps: { runners: run.runners, enumerations: run.sessionCount, repetition },
    },
    database_outcome: run.observed,
    evaluation: {
      ...evaluation,
      contract_basis: evaluation.classification === 'FAIL'
        ? { invariants: evaluation.invariants.filter((i) => i.holds === false).map((i) => `${i.id}: ${i.statement}`), framework: run.runners.A?.contract ?? result.contract ?? UNKNOWN }
        : null,
    },
    reproduction: { command: `node harness/run.mjs --adapter=${adapter.name} --mode=${mode.id} --case=${kase.id}`, requires: 'pnpm run setup, then pnpm run pg:up (README.md)' },
    diagnostics: {
      adapter: result.diagnostics ?? null,
      stderr: run.childRecords.map((r) => r.stderr).filter(Boolean).join('\n') || null,
      stdout: run.childRecords.flatMap((r) => r.stdout ?? []),
      protocol_errors: evidence.harness.protocolErrors,
      exit: primary.exit ?? null,
      timed_out: evidence.harness.timedOut,
    },
    timing: { started_at: startedAt.toISOString(), finished_at: finishedAt.toISOString(), duration_ms: finishedAt - startedAt },
  }
}
