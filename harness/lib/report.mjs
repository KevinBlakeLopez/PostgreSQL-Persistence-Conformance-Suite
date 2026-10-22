// Writes a run's evidence: one JSON file per case (schema/result.v1.schema.json), the run manifest run.json
// (schema/run.v1.schema.json), and summary.md, which links every classification to its case file.
//
// Each FAIL in summary.md answers four questions separately, because they are different claims: what the API
// reported, what PostgreSQL did (at report time, and after the adapter exited), what the application could have known
// at the time, and which contract was violated.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fateStory } from './classify.mjs'

export const RUN_SCHEMA = 'ppcs-run/1'

export const caseFileName = (r) => `${r.specification.id}.${r.subject.adapter.name}.${r.execution.mode}.json`

export function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

export function prepareRunDir(dir) {
  mkdirSync(join(dir, 'cases'), { recursive: true })
}

const columnOf = (r) => `${r.subject.adapter.name} (${r.execution.mode})`

/** The qualifiers that change what a classification means. A PASS whose mechanism did not run is not a full PASS. */
export function qualifiers(r) {
  const e = r.evaluation
  const q = []
  if (e.classification === 'PASS' && e.mechanism_exercised === false) q.push('mechanism not exercised')
  if ((e.classification === 'PASS' || e.classification === 'FAIL') && e.not_exercised?.length) q.push(`${e.not_exercised.join(', ')} not exercised`)
  if (e.classification === 'UNSUPPORTED' && e.unsupported_class === 'not-applicable-by-design') q.push('not applicable by design')
  if (e.ungated) q.push(`gated; ungated ${e.ungated.classification}`)
  if (r.repetitions && !r.repetitions.agreed) q.push('repetitions disagree')
  return q
}

const label = (r) => `${r.evaluation.classification}${qualifiers(r).length ? ` (${qualifiers(r).join('; ')})` : ''}`
const cell = (r) => `[${label(r)}](cases/${caseFileName(r)})`
const FAULT_LABELS = { none: 'none', A: 'A (PostgreSQL error)', B: 'B (server-side termination)', C: 'C (client-side injection)', D: 'D (client-side simulation)' }

function versionLine(r) {
  const s = r.subject
  return [`${s.framework.name} ${s.framework.version}`, ...Object.entries(s.components).map(([k, v]) => `${k} ${v}`), `${s.driver.name} ${s.driver.version}`, `${s.runtime.name} ${s.runtime.version}`].join(', ')
}

/** What PostgreSQL did, from the runner's own observations: each transaction at report time and at the end. */
function serverSide(r) {
  const o = r.database_outcome
  const kase = { family: r.specification.family }
  const parts = Object.entries(o.transactions ?? {}).map(([name, tx]) => `transaction \`${name}\` (its ID read inside it at \`${tx.captured_at}\`): ${fateStory(o, kase, name)}`)
  if (o.markers) parts.push(`markers visible to a separate connection after the adapter exited: ${Object.entries(o.markers).map(([k, v]) => `\`${k}\` ${v ? `yes (inserted by xid ${o.marker_xmin?.[k] ?? 'unknown'})` : 'no'}`).join(', ')}`)
  const sessions = Object.entries(o.checkpoints ?? {}).filter(([, cp]) => cp.session).map(([name, cp]) => `at \`${name}\` ${cp.session.present ? `"${cp.session.state}"` : 'no such session'}`)
  return `${parts.join('; ')}.${sessions.length ? ` Session state (pg_stat_activity, supplementary): ${sessions.join(', ')}.` : ''}`
}

/** What the application could have known: the case's statement, plus what the adapter's driver trace recorded. */
function knowledge(r) {
  const replies = r.diagnostics.adapter?.commit_replies
  const trace = Array.isArray(replies) && replies.length ? ` The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ${replies.join(', ')}.` : ''
  return `${r.knowledge ?? 'Not stated by the case.'}${trace}`
}

/** The controls section: the observation controls per adapter and mode, and the control adapters' expectations. */
function controlsSection(results) {
  const out = ['## Controls in this run', '']
  const gated = results.filter((r) => r.evaluation.gates)
  const byColumn = new Map()
  for (const r of gated) if (r.evaluation.gates.controls) byColumn.set(columnOf(r), r.evaluation.gates.controls)
  if (byColumn.size) {
    out.push('Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:', '')
    for (const [column, g] of byColumn) out.push(`- ${column}: ${g.held ? 'held' : `**did not hold**: ${g.detail}`}`)
    out.push('')
  }
  const caseGates = new Map()
  for (const r of gated) if (r.evaluation.gates.case_controls) caseGates.set(r.specification.id, r.evaluation.gates.case_controls)
  if (caseGates.size) {
    out.push('Case controls. A framework\'s result for a case counts only if the control adapters\' expectations for that case held in this run:', '')
    for (const [id, g] of caseGates) out.push(`- \`${id}\`: ${g.held === null ? g.detail : g.held ? `held (${g.detail})` : `**did not hold**: ${g.detail}`}`)
    out.push('')
  }
  return byColumn.size || caseGates.size ? out : []
}

export function renderSummary(manifest, results) {
  const columns = [...new Set(results.map(columnOf))]
  const caseIds = [...new Set(results.map((r) => r.specification.id))]
  const byKey = new Map(results.map((r) => [`${r.specification.id}|${columnOf(r)}`, r]))
  const faultOf = new Map(results.map((r) => [r.specification.id, r.fault.category]))
  const server = manifest.server ?? {}
  const notApplicable = results.filter((r) => r.evaluation.unsupported_class === 'not-applicable-by-design').length
  const out = []
  out.push(`# PPCS run ${manifest.run_id}`, '')
  out.push(`- **PostgreSQL:** ${server.server_version ?? 'UNKNOWN'} (\`${server.image ?? 'UNKNOWN'}\`)`)
  out.push(`- **Catalog:** \`${manifest.catalog.path}\`, sha256 \`${manifest.catalog.sha256.slice(0, 12)}…\``)
  out.push(`- **Runner:** PPCS ${manifest.ppcs_version}, harness sha256 \`${manifest.harness.sha256.slice(0, 12)}…\`, Node ${manifest.runner_runtime}`)
  out.push(`- **Repetitions:** every executed case ran ${manifest.repetitions === 1 ? 'once' : `${manifest.repetitions} times`}, each time on a fresh database; a result counts only if its repetitions agree`)
  out.push(`- **Started:** ${manifest.started_at}; duration ${Math.round((manifest.duration_ms ?? 0) / 1000)} s`)
  out.push(`- **Counts:** ${Object.entries(manifest.counts).filter(([, n]) => n).map(([k, n]) => `${k} ${n}${k === 'UNSUPPORTED' && notApplicable ? ` (${notApplicable} not applicable by design, outside coverage)` : ''}`).join(', ')}`, '')
  out.push('Each cell links to that case\'s evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).')
  out.push('', 'A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case\'s mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run\'s controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).')
  if (results.some((r) => r.execution.kind === 'control')) out.push('', 'Columns of kind `control` are the suite\'s own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.')
  out.push('', '## Results', '')
  out.push(`| Case | Fault | ${columns.join(' | ')} |`)
  out.push(`| --- | --- | ${columns.map(() => '---').join(' | ')} |`)
  for (const id of caseIds) out.push(`| \`${id}\` | ${FAULT_LABELS[faultOf.get(id)] ?? faultOf.get(id)} | ${columns.map((c) => (byKey.has(`${id}|${c}`) ? cell(byKey.get(`${id}|${c}`)) : '—')).join(' | ')} |`)
  out.push('')
  out.push(...controlsSection(results))

  const fails = results.filter((r) => r.evaluation.classification === 'FAIL')
  if (fails.length) {
    out.push('## Findings (FAIL)', '')
    for (const r of fails) {
      const violated = r.evaluation.invariants.filter((x) => x.holds === false)
      out.push(`### \`${r.specification.id}\` on ${columnOf(r)}`, '')
      const next = r.api_outcome.steps?.unit2
      out.push(`1. **What the API reported:** ${r.api_outcome.reported}: ${r.api_outcome.basis ?? 'no detail'}.${next ? ` The next unit of work: ${next.outcome === 'pending' ? `still pending after ${next.elapsed_ms} ms` : `${next.reported ?? next.outcome}, after ${next.elapsed_ms} ms`}.` : ''}`)
      out.push(`2. **What PostgreSQL did:** ${serverSide(r)}`)
      out.push(`3. **What the application could know:** ${knowledge(r)}`)
      out.push(`4. **Contract:** ${violated.map((i) => `${i.id} violated: ${i.statement}`).join(' ')} Framework contract: ${r.evaluation.contract_basis?.framework ?? 'UNKNOWN'}`, '')
      out.push(`- **Fault:** ${r.fault.category === 'none' ? 'none' : `category ${FAULT_LABELS[r.fault.category] ?? r.fault.category}. ${r.fault.mechanism}`}`)
      if (r.execution.form) out.push(`- **Form:** ${r.execution.form}`)
      out.push(`- **Conditions:** ${versionLine(r)}; mode \`${r.execution.mode}\` (${r.execution.kind}); settings \`${JSON.stringify(r.configuration)}\``)
      out.push(`- **Repetitions:** ${r.repetitions ? `${r.repetitions.runs.filter((x) => x.classification === 'FAIL').length} of ${r.repetitions.count} FAILed` : 'not recorded'}`)
      out.push(`- **Reproduce:** \`${r.reproduction.command}\``)
      out.push(`- **Evidence:** [cases/${caseFileName(r)}](cases/${caseFileName(r)})`, '')
    }
  }

  const qualifiedPasses = results.filter((r) => r.evaluation.classification === 'PASS' && qualifiers(r).length)
  if (qualifiedPasses.length) {
    out.push('## Qualified passes', '')
    for (const r of qualifiedPasses) {
      const notes = [...(r.evaluation.mechanism_exercised === false ? [r.evaluation.mechanism_detail ?? 'the mechanism did not run'] : []), ...r.evaluation.invariants.filter((i) => i.not_exercised).map((i) => `${i.id}: ${i.detail}`)]
      out.push(`- \`${r.specification.id}\` on ${columnOf(r)}: **${label(r)}**. ${notes.join('; ')}`)
    }
    out.push('')
  }

  const other = results.filter((r) => !['PASS', 'FAIL'].includes(r.evaluation.classification))
  if (other.length) {
    out.push('## Inconclusive, unsupported and not run', '')
    for (const r of other) out.push(`- \`${r.specification.id}\` on ${columnOf(r)}: **${label(r)}**. ${r.evaluation.reason}`)
    out.push('')
  }

  out.push('## Subjects', '')
  out.push('| Adapter (mode) | Kind | Versions | Adapter source sha256 |')
  out.push('| --- | --- | --- | --- |')
  const seen = new Set()
  for (const r of results) {
    const key = columnOf(r)
    if (seen.has(key) || r.subject.framework.version === 'UNKNOWN') continue
    seen.add(key)
    out.push(`| ${key} | ${r.execution.kind} | ${versionLine(r)} | \`${r.subject.adapter.source_sha256.slice(0, 12)}…\` |`)
  }
  out.push('')
  return `${out.join('\n')}\n`
}
