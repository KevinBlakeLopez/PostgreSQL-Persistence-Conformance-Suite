// Renders the human-readable report from propagation JSON. The wording follows
// the records. It does not upgrade a boundary into a confirmed defect.

const ORDER = ['pg-read-tag', 'pg-ignore-tag', 'typeorm-transaction']

const cell = (value) => String(value ?? '').replaceAll('|', '\\|')

function bySubject(records) {
  return [...records].sort((a, b) => {
    const scenario = a.scenario.localeCompare(b.scenario)
    if (scenario !== 0) return scenario
    const known = ORDER.indexOf(a.subject.id) - ORDER.indexOf(b.subject.id)
    if (ORDER.includes(a.subject.id) && ORDER.includes(b.subject.id)) return known
    return a.subject.id.localeCompare(b.subject.id)
  })
}

function tagOf(record) {
  const tag = record.driver_observation.command_tag
  if (tag.observation === 'OBSERVED' && tag.value != null) return `${tag.value} (${tag.access})`
  return tag.observation
}

export function renderReport({ run, records, capability }) {
  const rows = bySubject(records)
  const lines = []
  lines.push('# PostgreSQL Transaction Outcome Propagation: Driver and Framework Capability Matrix')
  lines.push('')
  lines.push(`${run.scenario} for ${run.driver.name} ${run.driver.version}. Frameworks: ${run.framework.name} ${run.framework.version}. Run \`${run.run_id}\`.`)
  lines.push('')
  lines.push('## Executive summary')
  lines.push('')
  lines.push('Each subject used a fresh database. A second connection read `pg_xact_status()` and marker visibility. The boundary is computed from those observations. `client_knowledge` UNKNOWN means the client did not receive the acknowledgment; the observer may still know the database outcome.')
  lines.push('')
  for (const record of rows) {
    const knowledge = record.client_knowledge ? `, client ${record.client_knowledge}` : ''
    lines.push(`- **${record.subject.id}** (${record.scenario}). Verified outcome ${record.verified_outcome}${knowledge}. Driver command tag ${tagOf(record)}. Application ${record.application_observation.reported}. Boundary **${record.information_loss_boundary}** (${record.confidence}).`)
  }
  lines.push('')
  lines.push('Defect claim: not made. A boundary names the layer where the recorded result stopped matching the verified database outcome.')
  lines.push('')
  lines.push('## Driver capability matrix')
  lines.push('')
  lines.push(`Scope: ${capability.scope}`)
  lines.push('')
  lines.push('| Capability | Verdict | Note |')
  lines.push('| --- | --- | --- |')
  for (const [name, verdict] of Object.entries(capability.capabilities)) {
    lines.push(`| ${cell(name)} | ${cell(verdict)} | ${cell(capability.notes[name])} |`)
  }
  lines.push('')
  lines.push(`Evidence subject: \`${capability.evidence_from}\`. Driver ${capability.driver.name} ${capability.driver.version}, git ${capability.driver.git_head ?? 'not recorded'}.`)
  lines.push('')
  lines.push('## Framework propagation matrix')
  lines.push('')
  lines.push('| Subject | Driver | Server outcome | Driver observation | Framework result | Application result | Boundary |')
  lines.push('| --- | --- | --- | --- | --- | --- | --- |')
  for (const record of rows) {
    const serverTag = record.server_command_tag
    const server = `${record.verified_outcome}; command tag ${serverTag.value ?? 'none'} (${serverTag.observation})`
    lines.push(`| ${cell(record.subject.id)} | ${cell(record.subject.driver.name)} ${cell(record.subject.driver.version)} | ${cell(server)} | ${cell(tagOf(record))} | ${cell(record.framework_observation.reported)} | ${cell(record.application_observation.reported)} | ${cell(record.information_loss_boundary)} |`)
  }
  lines.push('')
  if (rows.some((record) => record.repetitions.agreed === false)) {
    lines.push('At least one subject’s repetitions disagreed. That record keeps the first repetition and uses confidence LOW.')
    lines.push('')
  }
  lines.push('## Confirmed false-success cases')
  lines.push('')
  const falseSuccess = rows.filter((record) => record.verified_outcome === 'ROLLED_BACK' && record.application_observation.reported === 'REPORTED_SUCCESS')
  if (falseSuccess.length === 0) {
    lines.push('No subject reported success after a verified rollback.')
  } else {
    for (const record of falseSuccess) {
      lines.push(`### ${record.subject.id}`)
      lines.push('')
      lines.push(record.interpretation.note)
      lines.push('')
      lines.push(`Boundary: ${record.information_loss_boundary}. ${record.boundary_basis}`)
      lines.push('')
      lines.push(`Verified: pg_xact_status() ${record.verified_evidence.pg_xact_status}, marker visible ${record.verified_evidence.marker_visible}, xid ${record.verified_evidence.xid}.`)
      lines.push('')
    }
  }
  lines.push('## Correctly handled cases')
  lines.push('')
  const preserved = rows.filter((record) => record.information_loss_boundary === 'NONE')
  if (preserved.length === 0) {
    lines.push('No subject preserved the verified outcome.')
  } else {
    for (const record of preserved) {
      lines.push(`- **${record.subject.id}.** ${record.application_observation.basis}`)
    }
  }
  lines.push('')
  lines.push('## Unknown-outcome cases')
  lines.push('')
  const unknown = rows.filter((record) => record.verified_outcome === 'UNKNOWN')
  if (unknown.length === 0) {
    lines.push('This run has no UNKNOWN database outcome. TX-01B, the lost-commit-acknowledgment scenario, was not executed.')
  } else {
    for (const record of unknown) {
      lines.push(`- **${record.subject.id}.** Verified outcome UNKNOWN. Application ${record.application_observation.reported}.`)
    }
  }
  lines.push('')
  lines.push('## Architectural observations')
  lines.push('')
  lines.push('The three subjects share one driver and one PostgreSQL version. The direct client preserves the rollback when the application reads `Result.command`. The same resolved query is reported as success when that field is ignored. TypeORM’s transaction call is a third path: the diagnostic wrapper saw the driver result, and the framework call’s reported result is recorded above.')
  lines.push('')
  lines.push('That is one stack, not a comparison of abstraction styles. Pool reset, savepoints, and connection loss were not measured here.')
  lines.push('')
  lines.push('## Recommendations for framework maintainers')
  lines.push('')
  const typeorm = rows.find((record) => record.subject.id === 'typeorm-transaction')
  if (typeorm && typeorm.information_loss_boundary === 'FRAMEWORK' && typeorm.verified_outcome === 'ROLLED_BACK') {
    lines.push('For TypeORM ' + typeorm.subject.framework.version + ' on this evidence, `PostgresQueryRunner.commitTransaction` awaits `query("COMMIT")` and continues to `AfterTransactionCommit`. The pg result that call receives has a public `command` field. Two remediations fit this path:')
    lines.push('')
    lines.push('1. After `COMMIT`, inspect `Result.command`. When it is `ROLLBACK`, skip the after-commit signal and surface a rollback to the caller.')
    lines.push('2. Return an explicit transaction outcome from the transaction API, using the command tag as the input.')
    lines.push('')
    lines.push('Invalidating the connection is a different remedy. On this path the session was idle after the `ROLLBACK` completion, so the connection was usable again. That does not make the earlier transaction committed.')
  } else {
    lines.push('No framework false-success row is in this run, so this report does not recommend a TypeORM code change from these records.')
  }
  lines.push('')
  lines.push('For application code that calls node-postgres directly, read `Result.command` after `COMMIT`. A resolved promise means the client received ReadyForQuery. The command tag is the completion PostgreSQL sent.')
  lines.push('')
  lines.push('## Source evidence')
  lines.push('')
  for (const record of rows) {
    lines.push(`### ${record.subject.id}`)
    lines.push('')
    for (const item of record.evidence) {
      const where = [item.package, item.version, item.path, item.symbol, item.line == null ? null : `line ${item.line}`].filter(Boolean).join(' ')
      lines.push(`- ${item.kind}${where ? ` (${where})` : ''}: ${item.statement}`)
    }
    lines.push('')
  }
  lines.push('## Limitations')
  lines.push('')
  const limits = [...new Set(rows.flatMap((record) => record.limits))]
  for (const limit of limits) lines.push(`- ${limit}`)
  lines.push('')
  lines.push('## Reproduction')
  lines.push('')
  lines.push('```')
  lines.push(run.command)
  lines.push('```')
  lines.push('')
  lines.push(`Server: ${run.server.server_version}. Image: ${run.server.image ?? 'not recorded'}. Runtime: ${run.runtime.name} ${run.runtime.version}.`)
  lines.push('')
  lines.push('Regenerate this file from the JSON:')
  lines.push('')
  lines.push('```')
  lines.push(`node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/${run.run_id}`)
  lines.push('```')
  lines.push('')
  return `${lines.join('\n')}\n`
}
