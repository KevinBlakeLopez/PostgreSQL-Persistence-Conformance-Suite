import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyBoundary, verifiedOutcome } from '../lib/boundary.mjs'
import { pgCapabilityReport } from '../lib/capabilities.mjs'
import { propagationRecord, tag } from '../lib/record.mjs'
import { renderReport } from '../lib/report.mjs'
import { containsSecret, schemaErrors } from '../lib/validate.mjs'

const caps = pgCapabilityReport({
  commandTagObservation: 'OBSERVED',
  commandPresent: true,
  commandTag: 'ROLLBACK',
  rowCountPresent: true,
  rowCount: null,
  sqlstate: '23505',
  statusAfterError: 'E',
  statusAfterCommit: 'I',
})

test('verified outcome stays unknown when fate and marker disagree', () => {
  assert.equal(verifiedOutcome({ fate: 'aborted', markerVisible: false }), 'ROLLED_BACK')
  assert.equal(verifiedOutcome({ fate: 'committed', markerVisible: true }), 'COMMITTED')
  assert.equal(verifiedOutcome({ fate: 'aborted', markerVisible: true }), 'UNKNOWN')
  assert.equal(verifiedOutcome({ fate: null, markerVisible: false }), 'UNKNOWN')
})

test('pg read-tag preserves a verified rollback', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    driverCommandTag: 'ROLLBACK',
    driverCommandTagObservation: 'OBSERVED',
    driverCommandTagCapability: 'EXPOSED',
    frameworkPresent: false,
    frameworkReported: 'NOT_APPLICABLE',
    applicationReported: 'REPORTED_ROLLBACK',
    poolMaskedCommandTag: null,
  })
  assert.equal(decision.boundary, 'NONE')
  assert.equal(decision.confidence, 'HIGH')
})

test('ignoring an exposed ROLLBACK tag is the application', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    driverCommandTag: 'ROLLBACK',
    driverCommandTagObservation: 'OBSERVED',
    driverCommandTagCapability: 'EXPOSED',
    frameworkPresent: false,
    frameworkReported: 'NOT_APPLICABLE',
    applicationReported: 'REPORTED_SUCCESS',
    poolMaskedCommandTag: null,
  })
  assert.equal(decision.boundary, 'APPLICATION')
  assert.equal(decision.confidence, 'HIGH')
})

test('a framework success on an exposed ROLLBACK tag is the framework', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    driverCommandTag: 'ROLLBACK',
    driverCommandTagObservation: 'OBSERVED',
    driverCommandTagCapability: 'EXPOSED',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    applicationReported: 'REPORTED_SUCCESS',
    poolMaskedCommandTag: null,
  })
  assert.equal(decision.boundary, 'FRAMEWORK')
  assert.equal(decision.confidence, 'HIGH')
})

test('a success report without a driver tag stays undetermined', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    applicationReported: 'REPORTED_SUCCESS',
    poolMaskedCommandTag: null,
  })
  assert.equal(decision.boundary, 'UNDETERMINED')
  assert.equal(decision.confidence, 'LOW')
})

test('reporting uncertainty for an unknown outcome preserves it', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'UNKNOWN',
    applicationReported: 'REPORTED_UNKNOWN',
    frameworkPresent: false,
    frameworkReported: 'NOT_APPLICABLE',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'NONE')
})

test('asserting success for an unknown outcome stays undetermined', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'UNKNOWN',
    applicationReported: 'REPORTED_SUCCESS',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'UNDETERMINED')
})

test('a thrown failure preserves rollback semantics without a command tag', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    applicationReported: 'REPORTED_FAILURE',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_FAILURE',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'NONE')
})

test('a lost commit acknowledgment reported as a failure preserves uncertainty', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'COMMITTED',
    clientKnowledge: 'UNKNOWN',
    applicationReported: 'REPORTED_FAILURE',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_FAILURE',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'NONE')
  assert.equal(decision.confidence, 'HIGH')
})

test('a lost commit acknowledgment reported as success is the framework', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'COMMITTED',
    clientKnowledge: 'UNKNOWN',
    applicationReported: 'REPORTED_SUCCESS',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'FRAMEWORK')
})

test('a later unit committing the failed unit is the framework', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'COMMITTED',
    laterUnitCommittedEarlierWrite: true,
    applicationReported: 'REPORTED_FAILURE',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_FAILURE',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_OBSERVED',
    driverCommandTagCapability: 'UNKNOWN',
  })
  assert.equal(decision.boundary, 'FRAMEWORK')
})

test('a driver that does not expose the tag is the driver boundary', () => {
  const decision = classifyBoundary({
    verifiedOutcome: 'ROLLED_BACK',
    applicationReported: 'REPORTED_SUCCESS',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    driverCommandTag: null,
    driverCommandTagObservation: 'NOT_EXPOSED',
    driverCommandTagCapability: 'NOT_EXPOSED',
  })
  assert.equal(decision.boundary, 'DRIVER')
  assert.equal(decision.confidence, 'MEDIUM')
})

function sample(over = {}) {
  const commandTag = over.commandTag ?? 'ROLLBACK'
  const applicationReported = over.applicationReported ?? 'REPORTED_ROLLBACK'
  const frameworkReported = over.frameworkReported ?? 'NOT_APPLICABLE'
  const frameworkPresent = over.frameworkPresent ?? false
  return propagationRecord({
    verifiedOutcome: 'ROLLED_BACK',
    fate: 'aborted',
    markerVisible: false,
    xid: '10',
    pid: 20,
    sessionState: 'idle',
    sessionQuery: 'COMMIT',
    commandTag,
    commandTagObservation: 'OBSERVED',
    commandTagCapability: 'EXPOSED',
    frameworkPresent,
    frameworkReported,
    applicationReported,
    scenarioPreconditionsMet: true,
    capabilityScope: 'pg.Client',
    capabilityReport: caps,
    subject: {
      id: over.id ?? 'pg-read-tag',
      kind: frameworkPresent ? 'framework' : 'driver_control',
      framework: frameworkPresent ? { name: 'typeorm', version: '1.1.2', git_head: null } : null,
      driver: { name: 'pg', version: '8.23.1', git_head: 'abc' },
      pool: null,
      runtime: { name: 'node', version: 'v24.0.0' },
      server: { version: 'PostgreSQL 18.6', server_version: '18.6', server_version_num: 180006, image: null },
    },
    serverCommandTag: tag({ value: 'ROLLBACK', observation: 'INFERRED', access: 'source_inspection', basis: 'inferred from Result.command' }),
    driverObservation: {
      command_tag: tag({ value: commandTag, observation: 'OBSERVED', access: 'public_return_value', basis: 'Result.command' }),
      row_count: tag({ value: null, observation: 'OBSERVED', access: 'public_return_value', basis: 'Result.rowCount' }),
      sqlstate: tag({ value: '23505', observation: 'OBSERVED', access: 'public_return_value', basis: 'error.code' }),
      transaction_status_after_statement_error: tag({ value: 'E', observation: 'OBSERVED', access: 'public_return_value', basis: 'getTransactionStatus' }),
      transaction_status_after_commit: tag({ value: 'I', observation: 'OBSERVED', access: 'public_return_value', basis: 'getTransactionStatus' }),
      query_settled: 'resolved',
      instrumentation: 'none',
      commits: [],
    },
    frameworkObservation: {
      present: frameworkPresent,
      reported: frameworkReported,
      call: frameworkPresent ? 'DataSource.transaction(callback)' : null,
      threw: frameworkPresent ? false : null,
      resolved_value: frameworkPresent ? 'callback-sentinel' : null,
      command_tag: tag({ value: null, observation: frameworkPresent ? 'NOT_EXPOSED' : 'NOT_APPLICABLE', access: frameworkPresent ? 'public_return_value' : 'not_applicable', basis: 'framework return' }),
      after_transaction_commit: frameworkPresent ? 1 : null,
      after_transaction_rollback: frameworkPresent ? 0 : null,
      basis: frameworkPresent ? 'resolved' : null,
    },
    applicationObservation: { reported: applicationReported, basis: 'sample' },
    intermediateLayers: [],
    interpretationNote: over.note ?? 'sample note',
    evidence: [{ id: 'e1', kind: 'runtime', layer: 'database', statement: 'rolled back', package: null, version: null, git_head: null, path: null, symbol: null, line: null }],
    limits: ['TX-01B was not run.'],
    repetitions: { count: 1, agreed: over.agreed ?? true, compared: ['verified_outcome'], runs: [{ repetition: 1, verified_outcome: 'ROLLED_BACK', driver_command_tag: commandTag, sqlstate: '23505', application_reported: applicationReported, framework_reported: frameworkReported, information_loss_boundary: 'NONE', confidence: 'HIGH' }] },
  })
}

test('a built record matches the propagation schema', () => {
  const record = sample()
  assert.deepEqual(schemaErrors('record', record), [])
  assert.equal(record.information_loss_boundary, 'NONE')
  assert.equal(record.interpretation.defect_claim, 'not_made')
})

test('a framework record validates and names the framework', () => {
  const record = sample({
    id: 'typeorm-transaction',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    applicationReported: 'REPORTED_SUCCESS',
  })
  assert.deepEqual(schemaErrors('record', record), [])
  assert.equal(record.information_loss_boundary, 'FRAMEWORK')
})

test('disagreement between repetitions lowers confidence', () => {
  const record = sample({ agreed: false })
  assert.equal(record.confidence, 'LOW')
  assert.match(record.boundary_basis, /Repetitions did not agree/)
})

test('the schema rejects an extra field', () => {
  const record = sample()
  record.extra = true
  assert.ok(schemaErrors('record', record).length > 0)
})

test('secret scan sees a password and ignores an empty secret', () => {
  assert.deepEqual(containsSecret({ password: 'hidden-value' }, ['hidden-value']), ['hidden-value'])
  assert.deepEqual(containsSecret({ ok: true }, ['']), [])
})

test('the report names the boundary and withholds a defect claim', () => {
  const record = sample({
    id: 'typeorm-transaction',
    frameworkPresent: true,
    frameworkReported: 'REPORTED_SUCCESS',
    applicationReported: 'REPORTED_SUCCESS',
    note: 'TypeORM resolved.',
  })
  const markdown = renderReport({
    run: {
      run_id: 'sample-run',
      driver: { version: '8.23.1', name: 'pg', git_head: 'abc' },
      framework: { version: '1.1.2', name: 'typeorm' },
      command: 'node experiment',
      server: { server_version: '18.6', image: 'postgres:18.6' },
      runtime: { name: 'node', version: 'v24.0.0' },
    },
    records: [record],
    capability: { scope: 'pg.Client', capabilities: caps.capabilities, notes: caps.notes, evidence_from: 'records/pg-read-tag.json', driver: { name: 'pg', version: '8.23.1', git_head: 'abc' } },
  })
  assert.match(markdown, /FRAMEWORK/)
  assert.match(markdown, /Defect claim: not made/)
  assert.match(markdown, /TypeORM resolved/)
})
