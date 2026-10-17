// Runs one case on one adapter in one execution mode, and returns its evidence record (schema/result.v1.schema.json).
//
// 1. A fresh database, owned by this run, with the catalog's fixture, fingerprinted.
// 2. The adapter process, given the case, its connection and its markers (adapter-process.mjs).
// 3. At each checkpoint the adapter reports, from inside the transaction, its backend PID and pg_current_xact_id().
//    The runner then takes a snapshot of the server: that backend's session and locks, and, for every transaction
//    captured so far, its fate and its session's state. The snapshot at `after-end`, which the adapter sends as soon
//    as the framework's API has returned, is the state *at report time*.
// 4. After the adapter has exited and its sessions have closed: pg_xact_status() for every captured transaction ID,
//    the visibility and xmin of every marker, any other row in the marker table, all read through new connections,
//    and the fixture's fingerprint again.
// 5. The database is dropped, and the evidence is classified (classify.mjs).
import { randomBytes } from 'node:crypto'
import { runAdapter } from './adapter-process.mjs'
import { classify, REPORT_POINT } from './classify.mjs'

export const RESULT_SCHEMA = 'ppcs-result/1'
const UNKNOWN = 'UNKNOWN'

export async function runCase({ instance, observer, catalog, adapter, mode, kase, runId, timeoutMs = 60000 }) {
  const startedAt = new Date()
  const tag = randomBytes(3).toString('hex')
  const markers = Object.fromEntries(kase.markers.map((label) => [label, `${label}-${tag}`]))
  const observed = { checkpoints: {}, transactions: {}, markers: null, marker_xmin: null, stray_rows: null, sessions_at_end: null, fixture: { before: null, after: null } }
  const runnerErrors = []
  // `after-end` is a checkpoint of every case: the adapter sends it when the framework's API has returned.
  const declaredCheckpoints = { ...(kase.checkpoints ?? {}), [REPORT_POINT]: { implicit: true } }
  let record
  const database = await instance.createDatabase(`ppcs_${kase.id.replace(/[^A-Za-z0-9]+/g, '_')}`)
  try {
    await instance.query(database, catalog.fixture.sql)
    observed.fixture.before = await observer.fixtureFingerprint(database)

    const snapshot = async (pid, xid) => {
      const safe = (p) => p.catch((e) => ({ error: String(e.message) }))
      const transactionsNow = {}
      for (const [label, tx] of Object.entries(observed.transactions)) {
        transactionsNow[label] = {
          fate: await observer.fate(database, tx.xid).catch(() => null),
          session: await safe(observer.session(database, tx.pid)),
        }
      }
      return {
        session: await safe(observer.session(database, pid, xid)),
        locks: await safe(observer.locks(database, pid)),
        transactions_now: transactionsNow,
        adapter_sessions: (await observer.sessions(database).catch(() => [])).length,
      }
    }

    const onCheckpoint = async (msg) => {
      if (observed.checkpoints[msg.name]) {
        // A checkpoint is reported once: a second report (a retried transaction body, for example) would silently
        // replace the evidence the case is judged on.
        runnerErrors.push(`checkpoint "${msg.name}" reported more than once`)
        return { actions: [] }
      }
      const declared = declaredCheckpoints[msg.name]
      const reported = { pid: Number.isInteger(msg.pid) ? msg.pid : null, xid: typeof msg.xid === 'string' ? msg.xid : null }
      const entry = { reported }
      observed.checkpoints[msg.name] = entry
      if (!declared) { runnerErrors.push(`undeclared checkpoint "${msg.name}"`); return { actions: [] } }
      if (declared.captures) {
        // The capture comes first, so that the snapshot includes the transaction being captured.
        observed.transactions[declared.captures] = { xid: reported.xid, pid: reported.pid, captured_at: msg.name, session_xid_matches: null, fate: null }
      }
      Object.assign(entry, await snapshot(reported.pid, reported.xid))
      if (declared.captures) {
        const tx = observed.transactions[declared.captures]
        tx.session_xid_matches = entry.session?.xid_matches ?? null
        tx.backend_start = entry.session?.backend_start ?? null
      }
      const actions = []
      if (declared.action === 'terminate_backend') {
        // Category B: a real server-side termination, scoped to this case's database (Instance.terminateBackend).
        const terminated = await instance.terminateBackend(database, reported.pid)
        const gone = terminated ? await observer.waitGone(database, reported.pid) : false
        entry.action = { action: 'terminate_backend', pid: reported.pid, terminated, gone }
        actions.push(entry.action)
      }
      return { actions }
    }

    record = await runAdapter({
      command: adapter.command,
      cwd: adapter.dir,
      timeoutMs,
      redact: [instance.settings.password],
      onCheckpoint,
      message: {
        case: { id: kase.id, family: kase.family, version: kase.version, title: kase.title, settings: kase.settings ?? {} },
        mode: mode.id,
        connection: instance.connection(database, 'ppcs-adapter'),
        markers,
      },
    })

    observed.sessions_at_end = await observer.settle(database)
    for (const tx of Object.values(observed.transactions)) {
      try { tx.fate = await observer.fate(database, tx.xid) } catch (e) { tx.fate = null; tx.fate_error = String(e.message) }
    }
    try {
      observed.markers = await observer.markers(database, markers)
      observed.marker_xmin = await observer.markerXmins(database, markers)
      observed.stray_rows = await observer.strayRows(database, markers)
    } catch (e) { observed.markersError = String(e.message) }
    observed.fixture.after = await observer.fixtureFingerprint(database).catch((e) => `error: ${String(e.message)}`)
  } finally {
    if (!process.env.PPCS_KEEP_DB) await instance.dropDatabase(database)
  }

  const result = record.result ?? {}
  const completed = result.status === 'completed'
  // An optional checkpoint may legitimately not be reached: a next unit of work that never gets a connection is the
  // finding, not missing evidence.
  const missingCheckpoints = completed ? Object.entries(declaredCheckpoints).filter(([n, cp]) => !cp.optional && !observed.checkpoints[n]).map(([n]) => n) : []
  const protocolErrors = [...record.protocolErrors, ...runnerErrors]
  if (result.status === 'unsupported') protocolErrors.push('the adapter reported "unsupported" at run time; only its manifest may declare a case unsupported')
  const evidence = {
    case: kase,
    adapterStatus: result.status ?? null,
    adapterReason: result.reason ?? null,
    adapterError: result.error ? `${result.error.class ?? 'Error'}: ${result.error.message ?? ''}` : null,
    reported: result.reported ?? null,
    apiError: result.api_error ?? null,
    steps: result.steps ?? {},
    observed,
    adapter: { rollbackClaimChannels: adapter.rollback_claim_channels ?? [] },
    harness: { timedOut: record.timedOut, timeoutMs, helloReceived: !!record.hello, exit: record.exit, protocolErrors, missingCheckpoints },
  }
  const evaluation = classify(evidence, catalog.statements)
  const hello = record.hello ?? {}
  const finishedAt = new Date()

  return {
    schema: RESULT_SCHEMA,
    run_id: runId,
    specification: {
      id: kase.id,
      version: kase.version,
      family: kase.family,
      family_title: catalog.families[kase.family]?.title ?? UNKNOWN,
      family_version: catalog.families[kase.family]?.version ?? UNKNOWN,
      kind: kase.kind,
      title: kase.title,
      steps: kase.steps,
      invariants: kase.invariants.map((id) => ({ id, statement: catalog.statements[id] ?? UNKNOWN })),
      catalog: catalog.path,
      catalog_sha256: catalog.sha256,
    },
    subject: {
      adapter: { name: adapter.name, version: hello.adapter?.version ?? UNKNOWN, source_sha256: adapter.sourceSha256 },
      framework: { name: hello.framework?.name ?? UNKNOWN, version: hello.framework?.version ?? UNKNOWN },
      driver: { name: hello.driver?.name ?? UNKNOWN, version: hello.driver?.version ?? UNKNOWN },
      components: hello.components ?? {},
      runtime: { name: hello.runtime?.name ?? UNKNOWN, version: hello.runtime?.version ?? UNKNOWN },
    },
    execution: {
      mode: mode.id,
      kind: mode.kind,
      description: mode.description,
      configuration: hello.configuration ?? {},
    },
    configuration: kase.settings ?? {},
    server: { ...instance.server, image: instance.settings.image ?? UNKNOWN },
    fault: kase.fault,
    knowledge: kase.knowledge ?? null,
    api_outcome: {
      reported: result.reported ?? UNKNOWN,
      basis: result.basis ?? null,
      contract: result.contract ?? null,
      error: result.api_error ?? null,
      steps: result.steps ?? {}, // what the API did at intermediate steps, as the adapter observed it
    },
    database_outcome: observed,
    evaluation: {
      ...evaluation,
      contract_basis: evaluation.classification === 'FAIL'
        ? { invariants: evaluation.invariants.filter((i) => i.holds === false).map((i) => `${i.id}: ${i.statement}`), framework: result.contract ?? UNKNOWN }
        : null,
    },
    reproduction: {
      command: `node harness/run.mjs --adapter=${adapter.name} --mode=${mode.id} --case=${kase.id}`,
      requires: 'pnpm run setup, then pnpm run pg:up (README.md)',
    },
    diagnostics: {
      adapter: result.diagnostics ?? null,
      stderr: record.stderr || null,
      stdout: record.stdout.length ? record.stdout : null,
      protocol_errors: protocolErrors,
      exit: record.exit,
      timed_out: record.timedOut,
    },
    timing: { started_at: startedAt.toISOString(), finished_at: finishedAt.toISOString(), duration_ms: finishedAt - startedAt },
  }
}
