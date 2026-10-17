// Runs a selection of cases, one at a time, and writes the run directory. Used by harness/run.mjs and by the
// methodology tests.
import { readFileSync, writeFileSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import { join } from 'node:path'
import { ROOT, loadAdapters, loadCatalog, plan } from './catalog.mjs'
import { Instance, loadSettings } from './instance.mjs'
import { Observer } from './observer.mjs'
import { runCase, RESULT_SCHEMA } from './run-case.mjs'
import { notRun } from './classify.mjs'
import { RUN_SCHEMA, caseFileName, prepareRunDir, renderSummary, writeJson } from './report.mjs'

export class SetupError extends Error {}
export const PPCS_VERSION = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version

const newRunId = () => `${new Date().toISOString().replace(/\.\d+Z$/, 'Z').replace(/:/g, '-')}-${randomBytes(3).toString('hex')}`

/** A result record for a case that was not executed: UNSUPPORTED (declared by the adapter) or NOT_RUN. */
function notExecuted(item, runId, catalog, server, image) {
  const { adapter, mode, kase } = item
  const evaluation = item.plan === 'unsupported'
    ? { classification: 'UNSUPPORTED', reason: item.reason, preconditions: [], invariants: [], not_exercised: [], mechanism_exercised: null, contract_basis: null }
    : { ...notRun(item.reason), contract_basis: null }
  const now = new Date().toISOString()
  return {
    schema: RESULT_SCHEMA,
    run_id: runId,
    specification: {
      id: kase.id, version: kase.version, family: kase.family, family_title: catalog.families[kase.family].title, family_version: catalog.families[kase.family].version,
      kind: kase.kind, title: kase.title, steps: kase.steps, invariants: kase.invariants.map((id) => ({ id, statement: catalog.statements[id] })), catalog: catalog.path, catalog_sha256: catalog.sha256,
    },
    subject: {
      adapter: { name: adapter.name, version: 'UNKNOWN', source_sha256: adapter.sourceSha256 },
      framework: { name: adapter.framework ?? 'UNKNOWN', version: 'UNKNOWN' }, driver: { name: 'UNKNOWN', version: 'UNKNOWN' }, components: {}, runtime: { name: 'UNKNOWN', version: 'UNKNOWN' },
    },
    execution: { mode: mode.id, kind: mode.kind, description: mode.description, configuration: {} },
    configuration: kase.settings ?? {},
    server: { ...server, image: image ?? 'UNKNOWN' },
    fault: kase.fault,
    knowledge: kase.knowledge ?? null,
    api_outcome: { reported: 'UNKNOWN', basis: null, contract: null, error: null, steps: {} },
    database_outcome: { checkpoints: {}, transactions: {}, markers: null, marker_xmin: null, stray_rows: null, sessions_at_end: null, fixture: { before: null, after: null } },
    evaluation,
    reproduction: { command: `node harness/run.mjs --adapter=${adapter.name} --mode=${mode.id} --case=${kase.id}`, requires: 'pnpm run setup, then pnpm run pg:up (README.md)' },
    diagnostics: { adapter: null, stderr: null, stdout: null, protocol_errors: [], exit: null, timed_out: false },
    timing: { started_at: now, finished_at: now, duration_ms: 0 },
  }
}

export async function runSuite({ adapterFilter = [], caseFilter = [], modeFilter = [], outDir = join(ROOT, 'results'), timeoutMs = 60000, adapters = null, catalogFile, log = () => {} } = {}) {
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
  const manifest = {
    schema: RUN_SCHEMA,
    run_id: runId,
    ppcs_version: PPCS_VERSION,
    runner_runtime: process.version,
    status: 'running',
    started_at: started.toISOString(),
    finished_at: null,
    duration_ms: null,
    filters: { adapters: adapterFilter, cases: caseFilter, modes: modeFilter },
    server: { ...server, image: instance.settings.image ?? 'UNKNOWN' },
    catalog: { path: catalog.path, sha256: catalog.sha256 },
    adapters: [...new Set(items.map((i) => i.adapter))].map((a) => ({ name: a.name, manifest: a.manifestPath, source_sha256: a.sourceSha256 })),
    results: [],
    counts: { PASS: 0, FAIL: 0, UNSUPPORTED: 0, INCONCLUSIVE: 0, NOT_RUN: 0 },
  }
  writeJson(join(runDir, 'run.json'), manifest)

  const results = []
  for (const item of items) {
    const r = item.plan === 'run'
      ? await runCase({ instance, observer, catalog, adapter: item.adapter, mode: item.mode, kase: item.kase, runId, timeoutMs })
      : notExecuted(item, runId, catalog, server, instance.settings.image)
    const file = caseFileName(r)
    writeJson(join(runDir, 'cases', file), r)
    results.push(r)
    manifest.results.push({ case: r.specification.id, adapter: r.subject.adapter.name, mode: r.execution.mode, classification: r.evaluation.classification, file: `cases/${file}` })
    manifest.counts[r.evaluation.classification] += 1
    log(`${r.evaluation.classification.padEnd(12)} ${r.specification.id}  ${r.subject.adapter.name} (${r.execution.mode})  ${r.timing.duration_ms} ms`)
  }

  const finished = new Date()
  Object.assign(manifest, { status: 'completed', finished_at: finished.toISOString(), duration_ms: finished - started })
  writeJson(join(runDir, 'run.json'), manifest)
  writeFileSync(join(runDir, 'summary.md'), renderSummary(manifest, results))
  return { runId, runDir, manifest, results }
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
