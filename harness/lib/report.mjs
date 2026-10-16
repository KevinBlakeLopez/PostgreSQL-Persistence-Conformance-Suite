// Writes a run's evidence: one JSON file per case (schema/result.v1.schema.json), the run manifest run.json
// (schema/run.v1.schema.json), and summary.md, which links every classification to its case file.
//
// Each FAIL in summary.md answers four questions separately, because they are different claims: what the API
// reported, what PostgreSQL did, what the application could have known at the time, and which contract was violated.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

export const RUN_SCHEMA = 'ppcs-run/1'

export const caseFileName = (r) => `${r.specification.id}.${r.subject.adapter.name}.${r.execution.mode}.json`

export function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

export function prepareRunDir(dir) {
  mkdirSync(join(dir, 'cases'), { recursive: true })
}

const columnOf = (r) => `${r.subject.adapter.name} (${r.execution.mode})`
const cell = (r) => `[${r.evaluation.classification}](cases/${caseFileName(r)})`

function versionLine(r) {
  const s = r.subject
  return [`${s.framework.name} ${s.framework.version}`, ...Object.entries(s.components).map(([k, v]) => `${k} ${v}`), `${s.driver.name} ${s.driver.version}`, `${s.runtime.name} ${s.runtime.version}`].join(', ')
}

/** What PostgreSQL did, from the runner's own observations. */
function serverSide(r) {
  const o = r.database_outcome
  const parts = Object.entries(o.transactions ?? {}).map(([label, tx]) => `transaction \`${label}\` (xid ${tx.xid ?? 'not captured'}, read inside it at \`${tx.captured_at}\`): pg_xact_status() **${tx.fate ?? 'unknown'}**`)
  if (o.markers) parts.push(`markers visible to a separate connection: ${Object.entries(o.markers).map(([k, v]) => `\`${k}\` ${v ? `yes (inserted by xid ${o.marker_xmin?.[k] ?? 'unknown'})` : 'no'}`).join(', ')}`)
  const sessions = Object.entries(o.checkpoints ?? {}).filter(([, cp]) => cp.session).map(([name, cp]) => `at \`${name}\` ${cp.session.present ? `"${cp.session.state}"` : 'no such session'}`)
  return `${parts.join('; ')}.${sessions.length ? ` Session state (pg_stat_activity, supplementary): ${sessions.join(', ')}.` : ''}`
}

/** What the application could have known: the case's statement, plus what the adapter's driver trace recorded. */
function knowledge(r) {
  const replies = r.diagnostics.adapter?.commit_replies
  const trace = Array.isArray(replies) && replies.length ? ` The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ${replies.join(', ')}.` : ''
  return `${r.knowledge ?? 'Not stated by the case.'}${trace}`
}

export function renderSummary(manifest, results) {
  const columns = [...new Set(results.map(columnOf))]
  const caseIds = [...new Set(results.map((r) => r.specification.id))]
  const byKey = new Map(results.map((r) => [`${r.specification.id}|${columnOf(r)}`, r]))
  const server = manifest.server ?? {}
  const out = []
  out.push(`# PPCS run ${manifest.run_id}`, '')
  out.push(`- **PostgreSQL:** ${server.server_version ?? 'UNKNOWN'} (\`${server.image ?? 'UNKNOWN'}\`)`)
  out.push(`- **Catalog:** \`${manifest.catalog.path}\`, sha256 \`${manifest.catalog.sha256.slice(0, 12)}…\``)
  out.push(`- **Runner:** PPCS ${manifest.ppcs_version}, Node ${manifest.runner_runtime}`)
  out.push(`- **Started:** ${manifest.started_at}; duration ${Math.round((manifest.duration_ms ?? 0) / 1000)} s`)
  out.push(`- **Counts:** ${Object.entries(manifest.counts).filter(([, n]) => n).map(([k, n]) => `${k} ${n}`).join(', ')}`, '')
  out.push('Each cell links to that case\'s evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).')
  if (results.some((r) => r.execution.kind === 'control')) out.push('', 'Columns of kind `control` are the suite\'s own positive and negative controls: the negative control is expected to FAIL, which shows that the runner detects a known-bad implementation.')
  out.push('', '## Results', '')
  out.push(`| Case | ${columns.join(' | ')} |`)
  out.push(`| --- | ${columns.map(() => '---').join(' | ')} |`)
  for (const id of caseIds) out.push(`| \`${id}\` | ${columns.map((c) => (byKey.has(`${id}|${c}`) ? cell(byKey.get(`${id}|${c}`)) : '—')).join(' | ')} |`)
  out.push('')

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
      out.push(`- **Fault:** ${r.fault.category === 'none' ? 'none' : `category ${r.fault.category}. ${r.fault.mechanism}`}`)
      out.push(`- **Conditions:** ${versionLine(r)}; mode \`${r.execution.mode}\` (${r.execution.kind}); settings \`${JSON.stringify(r.configuration)}\``)
      out.push(`- **Reproduce:** \`${r.reproduction.command}\``)
      out.push(`- **Evidence:** [cases/${caseFileName(r)}](cases/${caseFileName(r)})`, '')
    }
  }

  const other = results.filter((r) => !['PASS', 'FAIL'].includes(r.evaluation.classification))
  if (other.length) {
    out.push('## Inconclusive, unsupported and not run', '')
    for (const r of other) out.push(`- \`${r.specification.id}\` on ${columnOf(r)}: **${r.evaluation.classification}**. ${r.evaluation.reason}`)
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
