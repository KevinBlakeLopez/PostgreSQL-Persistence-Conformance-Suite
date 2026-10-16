// Runs one case on one adapter in one execution mode, and returns its evidence record (schema/result.v1.schema.json).
//
// 1. A fresh database, owned by this run, with the catalog's fixture.
// 2. The adapter process, given the case, its connection and its markers (adapter-process.mjs).
// 3. At each checkpoint the adapter reports, from inside the transaction, its backend PID and pg_current_xact_id().
//    The runner reads that session's state from pg_stat_activity, as a supplementary check, and resumes the adapter.
// 4. After the adapter has exited and its sessions have closed: pg_xact_status() for every captured transaction ID,
//    and the visibility of every marker, both read through new connections.
// 5. The database is dropped, and the evidence is classified (classify.mjs).
import { randomBytes } from 'node:crypto'
import { runAdapter } from './adapter-process.mjs'
import { classify } from './classify.mjs'

export const RESULT_SCHEMA = 'ppcs-result/1'
const UNKNOWN = 'UNKNOWN'

export async function runCase({ instance, observer, catalog, adapter, mode, kase, runId, timeoutMs = 60000 }) {
  const startedAt = new Date()
  const tag = randomBytes(3).toString('hex')
  const markers = Object.fromEntries(kase.markers.map((label) => [label, `${label}-${tag}`]))
  const observed = { checkpoints: {}, transactions: {}, markers: null, marker_xmin: null, sessions_at_end: null }
  const unexpectedCheckpoints = []
  let record
  const database = await instance.createDatabase(`ppcs_${kase.id.replace(/[^A-Za-z0-9]+/g, '_')}`)
  try {
    await instance.query(database, catalog.fixture.sql)

    const onCheckpoint = async (msg) => {
      const declared = kase.checkpoints?.[msg.name]
      const reported = { pid: Number.isInteger(msg.pid) ? msg.pid : null, xid: typeof msg.xid === 'string' ? msg.xid : null }
      const entry = { reported, session: await observer.session(database, reported.pid, reported.xid).catch((e) => ({ pid: reported.pid, error: String(e.message) })) }
      observed.checkpoints[msg.name] = entry
      if (!declared) { unexpectedCheckpoints.push(msg.name); return { actions: [] } }
      if (declared.captures) {
        observed.transactions[declared.captures] = { xid: reported.xid, pid: reported.pid, captured_at: msg.name, session_xid_matches: entry.session?.xid_matches ?? null, fate: null }
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
    } catch (e) { observed.markersError = String(e.message) }
  } finally {
    if (!process.env.PPCS_KEEP_DB) await instance.dropDatabase(database)
  }

  const result = record.result ?? {}
  const completed = result.status === 'completed'
  // An optional checkpoint may legitimately not be reached: a next unit of work that never gets a connection is the
  // finding, not missing evidence.
  const missingCheckpoints = completed ? Object.entries(kase.checkpoints ?? {}).filter(([n, cp]) => !cp.optional && !observed.checkpoints[n]).map(([n]) => n) : []
  const protocolErrors = [...record.protocolErrors, ...unexpectedCheckpoints.map((n) => `undeclared checkpoint "${n}"`)]
  const evidence = {
    case: kase,
    adapterStatus: result.status ?? null,
    adapterReason: result.reason ?? null,
    adapterError: result.error ? `${result.error.class ?? 'Error'}: ${result.error.message ?? ''}` : null,
    reported: result.reported ?? null,
    steps: result.steps ?? {},
    observed,
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
