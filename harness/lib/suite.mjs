// Runs a selection of cases, one at a time, and writes the run directory. Used by harness/run.mjs and by the
// methodology tests.
//
// Every executed case runs `repetitions` times (default 3), each time on a fresh database; repetitions that disagree
// make the result INCONCLUSIVE. Then two gates apply to the scenario results of the run (docs/methodology.md, "Gates"):
//  - controls: the CTL-01 cases of the same adapter and mode PASSed in this run;
//  - case controls: every control adapter that states an expectation for the case met it in this run.
// A result that fails a gate is INCONCLUSIVE; the classification it would have had is kept as `evaluation.ungated`.
import { readFileSync, writeFileSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import { join } from 'node:path'
import { CONTROL_FAMILY, ROOT, harnessSha256, isControlAdapter, loadAdapters, loadCatalog, plan } from './catalog.mjs'
import { Instance, loadSettings } from './instance.mjs'
import { Observer } from './observer.mjs'
import { runCase, RESULT_SCHEMA } from './run-case.mjs'
import { CLASSIFICATIONS, RECORDS_INCONCLUSIVE_REASON, notRun } from './classify.mjs'
import { RUN_SCHEMA, caseFileName, prepareRunDir, renderSummary, writeJson } from './report.mjs'

export class SetupError extends Error {}
export const PPCS_VERSION = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version
export const DEFAULT_REPETITIONS = 3

const newRunId = () => `${new Date().toISOString().replace(/\.\d+Z$/, 'Z').replace(/:/g, '-')}-${randomBytes(3).toString('hex')}`

/** A result record for a case whose evidence was not collected: UNSUPPORTED or NOT_RUN (from the plan), or
 * INCONCLUSIVE when the runner itself failed while running it. */
function notExecuted(item, { runId, catalog, server, image, harness }, evaluation) {
  const { adapter, mode, kase } = item
  const now = new Date().toISOString()
  return {
    schema: RESULT_SCHEMA,
    run_id: runId,
    harness,
    specification: {
      id: kase.id, version: kase.version, family: kase.family, family_title: catalog.families[kase.family].title, family_version: catalog.families[kase.family].version,
      kind: kase.kind, title: kase.title, steps: kase.steps, invariants: kase.invariants.map((id) => ({ id, statement: catalog.statements[id] })), catalog: catalog.path, catalog_sha256: catalog.sha256,
    },
    subject: {
      adapter: { name: adapter.name, version: 'UNKNOWN', source_sha256: adapter.sourceSha256 },
      framework: { name: adapter.framework ?? 'UNKNOWN', version: 'UNKNOWN' }, driver: { name: 'UNKNOWN', version: 'UNKNOWN' }, components: {}, runtime: { name: 'UNKNOWN', version: 'UNKNOWN' },
    },
    execution: { mode: mode.id, kind: mode.kind, description: mode.description, configuration: {}, form: null },
    configuration: kase.settings ?? {},
    server: { ...server, image: image ?? 'UNKNOWN' },
    fault: kase.fault,
    knowledge: kase.knowledge ?? null,
    api_outcome: { reported: 'UNKNOWN', basis: null, contract: null, error: null, steps: {} },
    database_outcome: { checkpoints: {}, transactions: {}, markers: null, marker_xmin: null, stray_rows: null, sessions_at_end: null, fixture: { before: null, after: null } },
    evaluation: { not_exercised: [], mechanism_exercised: null, ...evaluation, contract_basis: null },
    repetitions: null,
    reproduction: { command: `node harness/run.mjs --adapter=${adapter.name} --mode=${mode.id} --case=${kase.id}`, requires: 'pnpm run setup, then pnpm run pg:up (README.md)' },
    diagnostics: { adapter: null, stderr: null, stdout: null, protocol_errors: [], exit: null, timed_out: false },
    timing: { started_at: now, finished_at: now, duration_ms: 0 },
  }
}

const planned = (item) => (item.plan === 'unsupported'
  ? { classification: 'UNSUPPORTED', reason: item.reason, unsupported_class: item.unsupportedClass, preconditions: [], invariants: [] }
  : notRun(item.reason))

/** What must agree across repetitions: the classification and the qualifiers that change its meaning. */
const agreementKey = (e) => JSON.stringify([e.classification, e.mechanism_exercised ?? null, [...(e.not_exercised ?? [])].sort()])

/** Runs one item `repetitions` times, each on a fresh database. */
async function runRepeated(args, repetitions) {
  const records = []
  for (let n = 1; n <= repetitions; n += 1) records.push(await runCase({ ...args, repetition: n }))
  return combineRepetitions(records)
}

/** Combines the records of one item's repetitions: the first one's evidence, and every repetition's summary. */
export function combineRepetitions(records) {
  const repetitions = records.length
  const [first] = records
  const last = records[records.length - 1]
  const runs = records.map((r, i) => ({
    repetition: i + 1,
    classification: r.evaluation.classification,
    reason: r.evaluation.reason,
    mechanism_exercised: r.evaluation.mechanism_exercised ?? null,
    not_exercised: r.evaluation.not_exercised ?? [],
    reported: r.api_outcome.reported,
    fates: Object.fromEntries(Object.entries(r.database_outcome.transactions).map(([label, t]) => [label, t.fate])),
    markers: r.database_outcome.markers,
    duration_ms: r.timing.duration_ms,
  }))
  const agreed = records.every((r) => agreementKey(r.evaluation) === agreementKey(first.evaluation))
  const combined = {
    ...first,
    // Repetitions that disagree keep their full records, so that the difference can be examined.
    repetitions: { count: repetitions, agreed, runs, ...(agreed ? {} : { records: records.slice(1) }) },
    timing: { started_at: first.timing.started_at, finished_at: last.timing.finished_at, duration_ms: Date.parse(last.timing.finished_at) - Date.parse(first.timing.started_at) },
  }
  if (!agreed) {
    const label = (s) => `#${s.repetition} ${s.classification}${s.mechanism_exercised === false ? ' (mechanism not exercised)' : ''}${s.not_exercised.length ? ` (${s.not_exercised.join(', ')} not exercised)` : ''}`
    // Repetitions that disagree are observations that contradict each other.
    const inconclusiveReason = RECORDS_INCONCLUSIVE_REASON.has(first.specification?.family) ? 'observation-conflict' : (first.evaluation.inconclusive_reason ?? null)
    combined.evaluation = { ...first.evaluation, classification: 'INCONCLUSIVE', reason: `the repetitions disagree: ${runs.map(label).join('; ')}`, contract_basis: null, inconclusive_reason: inconclusiveReason }
  }
  return combined
}

const keyOf = (r) => `${r.specification.id}|${r.subject.adapter.name}|${r.execution.mode}`
const decided = (r) => r.evaluation.classification === 'PASS' || r.evaluation.classification === 'FAIL'

/**
 * Applies the run-level gates to `results` in place. Every result that ran gets `evaluation.gates`; a PASS or FAIL
 * whose gate failed becomes INCONCLUSIVE, keeping the classification it would have had as `evaluation.ungated`.
 */
export function applyGates(results, catalog, adapters) {
  const byKey = new Map(results.map((r) => [keyOf(r), r]))
  const ctlIds = catalog.cases.filter((c) => c.family === CONTROL_FAMILY).map((c) => c.id)
  const gate = (r, name, held, detail) => {
    r.evaluation.gates = { ...(r.evaluation.gates ?? {}), [name]: { held, detail } }
    if (held === false && decided(r)) {
      r.evaluation.ungated = { classification: r.evaluation.classification, reason: r.evaluation.reason }
      r.evaluation.classification = 'INCONCLUSIVE'
      r.evaluation.reason = `${name === 'controls' ? 'the observation controls' : 'the case controls'} did not hold in this run (${detail}); ungated: ${r.evaluation.ungated.classification}`
      r.evaluation.contract_basis = null
      // A gate that did not hold means the run's own apparatus did not support a conclusion.
      if (RECORDS_INCONCLUSIVE_REASON.has(r.specification?.family)) r.evaluation.inconclusive_reason = 'environment'
    }
  }
  const ran = (r) => r.repetitions != null

  // 1. The CTL-01 cases of the same adapter and mode, every one of which must PASS.
  for (const r of results) {
    if (!ran(r) || r.specification.family === CONTROL_FAMILY) continue
    const missing = []
    for (const id of ctlIds) {
      const c = byKey.get(`${id}|${r.subject.adapter.name}|${r.execution.mode}`)
      if (c?.evaluation.classification !== 'PASS') missing.push(`${id} ${c ? c.evaluation.classification : 'not run'}`)
    }
    gate(r, 'controls', missing.length === 0, missing.length ? missing.join(', ') : `${ctlIds.join(' and ')} PASSed for ${r.subject.adapter.name} (${r.execution.mode})`)
  }

  // 2. The control adapters' expectations for the same case, after their own controls gate.
  const controls = adapters.filter((a) => isControlAdapter(a) && a.expectations)
  for (const r of results) {
    if (!ran(r) || r.specification.family === CONTROL_FAMILY || r.execution.kind === 'control') continue
    const checks = []
    for (const a of controls) {
      for (const [mode, expected] of Object.entries(a.expectations[r.specification.id] ?? {})) {
        const c = byKey.get(`${r.specification.id}|${a.name}|${mode}`)
        checks.push({ met: c?.evaluation.classification === expected, text: `${a.name} (${mode}) expected ${expected}, got ${c ? c.evaluation.classification : 'not run'}` })
      }
    }
    if (!checks.length) gate(r, 'case_controls', null, 'no control adapter states an expectation for this case')
    else gate(r, 'case_controls', checks.every((x) => x.met), checks.filter((x) => !x.met).map((x) => x.text).join(', ') || checks.map((x) => x.text).join(', '))
  }
}

export async function runSuite({ adapterFilter = [], caseFilter = [], modeFilter = [], outDir = join(ROOT, 'results'), timeoutMs = 60000, repetitions = DEFAULT_REPETITIONS, adapters = null, catalogFile, log = () => {} } = {}) {
  if (!Number.isInteger(repetitions) || repetitions < 1) throw new SetupError('repetitions must be a positive integer')
  const catalog = loadCatalog(catalogFile)
  const all = adapters ?? loadAdapters()
  const unknown = adapterFilter.filter((a) => !all.some((x) => x.name === a))
  if (unknown.length) throw new SetupError(`Unknown adapter: ${unknown.join(', ')}`)
  const items = plan(catalog, all, { adapterFilter, caseFilter, modeFilter })
  if (!items.length) throw new SetupError('No case matches the filters.')

  const instance = new Instance(loadSettings())
  const server = await instance.verify()
  const observer = new Observer(instance)

  const runId = newRunId()
  const runDir = join(outDir, runId)
  prepareRunDir(runDir)
  const started = new Date()
  const harness = { ppcs_version: PPCS_VERSION, sha256: harnessSha256() }
  const manifest = {
    schema: RUN_SCHEMA,
    run_id: runId,
    ppcs_version: PPCS_VERSION,
    harness,
    runner_runtime: process.version,
    status: 'running',
    started_at: started.toISOString(),
    finished_at: null,
    duration_ms: null,
    filters: { adapters: adapterFilter, cases: caseFilter, modes: modeFilter },
    repetitions,
    server: { ...server, image: instance.settings.image ?? 'UNKNOWN' },
    catalog: { path: catalog.path, sha256: catalog.sha256 },
    adapters: [...new Set(items.map((i) => i.adapter))].map((a) => ({ name: a.name, manifest: a.manifestPath, source_sha256: a.sourceSha256 })),
    results: [],
    counts: Object.fromEntries(CLASSIFICATIONS.map((c) => [c, 0])),
  }
  writeJson(join(runDir, 'run.json'), manifest)

  const context = { runId, catalog, server, image: instance.settings.image, harness }
  const results = []
  for (const item of items) {
    let r
    if (item.plan !== 'run') r = notExecuted(item, context, planned(item))
    else {
      try {
        r = await runRepeated({ instance, observer, catalog, adapter: item.adapter, mode: item.mode, kase: item.kase, runId, harness, timeoutMs }, repetitions)
      } catch (e) {
        // A failure of the runner itself (for example, the server went away) is recorded, never silently dropped.
        r = notExecuted(item, context, { classification: 'INCONCLUSIVE', reason: `the runner failed while running this case: ${String(e?.message ?? e).split('\n')[0]}`, preconditions: [], invariants: [] })
      }
    }
    writeJson(join(runDir, 'cases', caseFileName(r)), r) // rewritten below, once the gates have been applied
    results.push(r)
    log(`${r.evaluation.classification.padEnd(12)} ${r.specification.id}  ${r.subject.adapter.name} (${r.execution.mode})  ${r.timing.duration_ms} ms`)
  }

  applyGates(results, catalog, all)
  for (const r of results) {
    const file = caseFileName(r)
    writeJson(join(runDir, 'cases', file), r)
    manifest.results.push({ case: r.specification.id, adapter: r.subject.adapter.name, mode: r.execution.mode, classification: r.evaluation.classification, ...(r.evaluation.ungated ? { ungated: r.evaluation.ungated.classification } : {}), file: `cases/${file}` })
    manifest.counts[r.evaluation.classification] += 1
    if (r.evaluation.ungated) log(`gated: ${r.specification.id}  ${r.subject.adapter.name} (${r.execution.mode}) ${r.evaluation.ungated.classification} -> INCONCLUSIVE`)
  }
  const finished = new Date()
  Object.assign(manifest, { status: 'completed', finished_at: finished.toISOString(), duration_ms: finished - started })
  writeJson(join(runDir, 'run.json'), manifest)
  writeFileSync(join(runDir, 'summary.md'), renderSummary(manifest, results))
  return { runId, runDir, manifest, results }
}

/**
 * Why an earlier run.json cannot be compared with this run: a different harness or catalog makes a classification
 * difference meaningless (it may come from the rules, not from the subject). Returns the reasons; empty means comparable.
 */
export function incomparable(manifest, expectedManifest) {
  const reasons = []
  if (expectedManifest.harness?.sha256 !== manifest.harness.sha256) reasons.push(`the harness differs (expected run: ${expectedManifest.harness?.sha256 ?? 'not recorded'}; this run: ${manifest.harness.sha256})`)
  if (expectedManifest.catalog?.sha256 !== manifest.catalog.sha256) reasons.push(`the catalog differs (expected run: ${expectedManifest.catalog?.sha256 ?? 'not recorded'}; this run: ${manifest.catalog.sha256})`)
  return reasons
}

/** Differences in classification between this run and an earlier run.json, keyed by case, adapter and mode. */
export function compareWith(manifest, expectedManifest) {
  const key = (x) => `${x.case} | ${x.adapter} | ${x.mode}`
  const expected = new Map(expectedManifest.results.map((x) => [key(x), x.classification]))
  const diffs = []
  for (const x of manifest.results) {
    const was = expected.get(key(x))
    if (was === undefined) diffs.push(`${key(x)}: not in the expected run (now ${x.classification})`)
    else if (was !== x.classification) diffs.push(`${key(x)}: expected ${was}, got ${x.classification}`)
  }
  return diffs
}
