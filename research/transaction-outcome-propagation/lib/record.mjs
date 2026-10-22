// Assembles one ppcs-propagation/1 record. The boundary comes from classifyBoundary.
// Callers supply observations. They do not supply the boundary.

import { classifyBoundary, interpretationKind, verifiedOutcome } from './boundary.mjs'
import { CAPABILITY_KEYS } from './capabilities.mjs'

export const PROPAGATION_SCHEMA = 'ppcs-propagation/1'
export const SCENARIO = 'TX-01A.caught-error-then-commit'

export function tag({ value = null, observation, access, basis = null }) {
  return { value, observation, access, basis }
}

export function decisionInput(input) {
  return {
    scenarioPreconditionsMet: input.scenarioPreconditionsMet !== false,
    supportingContradiction: input.supportingContradiction === true,
    contradiction: input.contradiction ?? null,
    verifiedOutcome: input.verifiedOutcome,
    driverCommandTag: input.commandTag ?? null,
    driverCommandTagObservation: input.commandTagObservation,
    driverCommandTagCapability: input.commandTagCapability,
    frameworkPresent: input.frameworkPresent === true,
    frameworkReported: input.frameworkReported,
    applicationReported: input.applicationReported,
    poolMaskedCommandTag: input.poolMaskedCommandTag ?? null,
    clientKnowledge: input.clientKnowledge === 'UNKNOWN' ? 'UNKNOWN' : 'KNOWN',
    laterUnitCommittedEarlierWrite: input.laterUnitCommittedEarlierWrite === true,
    driverCallRejected: input.driverCallRejected === true,
  }
}

function stackLayers(subject) {
  const framework = subject.framework
  const pool = subject.pool
  return [
    {
      name: 'server',
      presence: 'separate',
      observed: true,
      folded_into: null,
      component: 'PostgreSQL',
      version: subject.server.server_version,
      note: 'The database outcome is pg_xact_status() and marker visibility on a second connection.',
    },
    {
      name: 'protocol',
      presence: 'separate',
      observed: false,
      folded_into: null,
      component: 'PostgreSQL frontend/backend protocol',
      version: null,
      note: 'This run does not capture packets. A command tag inferred from node-postgres is that driver parsing CommandComplete.',
    },
    {
      name: 'driver',
      presence: 'separate',
      observed: true,
      folded_into: null,
      component: subject.driver.name,
      version: subject.driver.version,
      note: 'Driver observations are fields on the pg query result, or Client.getTransactionStatus().',
    },
    {
      name: 'pool',
      presence: pool ? 'separate' : 'absent',
      observed: false,
      folded_into: null,
      component: pool?.name ?? null,
      version: pool?.version ?? null,
      note: pool
        ? 'A pool is in the process. This scenario does not record a reset statement. The command tag is read from the client result inside the transaction call, before the connection is released.'
        : 'This subject constructs a pg.Client. No pool is on the call path.',
    },
    {
      name: 'transaction_manager',
      presence: framework ? 'folded' : 'absent',
      observed: false,
      folded_into: framework ? 'framework' : null,
      component: null,
      version: null,
      note: framework
        ? 'PostgresQueryRunner.commitTransaction is TypeORM\'s transaction operation. It stays in the framework layer so the record does not invent a second boundary inside one library.'
        : 'This subject calls the driver. There is no transaction manager.',
    },
    {
      name: 'framework',
      presence: framework ? 'separate' : 'absent',
      observed: Boolean(framework),
      folded_into: null,
      component: framework?.name ?? null,
      version: framework?.version ?? null,
      note: framework
        ? 'The application-facing call is the framework transaction API.'
        : 'No persistence framework is on this call path.',
    },
    {
      name: 'application',
      presence: 'separate',
      observed: true,
      folded_into: null,
      component: subject.id,
      version: null,
      note: 'The application is the subject code in this experiment.',
    },
  ]
}

function requireKeys(object, keys, label) {
  for (const key of keys) {
    if (!(key in object)) throw new Error(`${label} is missing ${key}`)
  }
}

/**
 * Build the record and overwrite any boundary the caller might have included.
 */
export function propagationRecord(input) {
  const expected = verifiedOutcome({ fate: input.fate, markerVisible: input.markerVisible })
  if (input.verifiedOutcome !== expected) {
    throw new Error(`verified outcome ${input.verifiedOutcome} does not match observer fate ${input.fate} and marker visibility ${input.markerVisible}`)
  }
  if (input.driverObservation.command_tag.value !== (input.commandTag ?? null)) {
    throw new Error('driver observation command tag does not match the decision input')
  }
  if (input.applicationObservation.reported !== input.applicationReported) {
    throw new Error('application observation does not match the decision input')
  }
  if (input.frameworkObservation.reported !== input.frameworkReported) {
    throw new Error('framework observation does not match the decision input')
  }
  requireKeys(input.capabilityReport.capabilities, CAPABILITY_KEYS, 'capabilities')
  requireKeys(input.capabilityReport.notes, CAPABILITY_KEYS, 'capability notes')

  const decisionFields = decisionInput(input)
  let decision = classifyBoundary(decisionFields)
  if (input.repetitions?.agreed === false) {
    decision = {
      ...decision,
      confidence: 'LOW',
      basis: `${decision.basis} Repetitions did not agree, so this record keeps the first repetition and lowers confidence.`,
    }
  }

  return {
    schema: PROPAGATION_SCHEMA,
    scenario: input.scenario ?? SCENARIO,
    repetition_recorded: input.repetitionRecorded ?? 1,
    subject: input.subject,
    layers: stackLayers(input.subject),
    verified_outcome: input.verifiedOutcome,
    client_knowledge: decisionFields.clientKnowledge,
    verified_evidence: {
      pg_xact_status: input.fate,
      marker_visible: input.markerVisible,
      xid: input.xid,
      backend_pid: input.pid,
      session_state: input.sessionState ?? null,
      session_query: input.sessionQuery ?? null,
      observer: 'separate_connection',
    },
    server_command_tag: input.serverCommandTag,
    capability_scope: input.capabilityScope,
    driver_capabilities: input.capabilityReport.capabilities,
    capability_notes: input.capabilityReport.notes,
    driver_observation: input.driverObservation,
    intermediate_layers: input.intermediateLayers ?? [],
    framework_observation: input.frameworkObservation,
    application_observation: input.applicationObservation,
    interpretation: {
      kind: interpretationKind(decision.boundary, input.verifiedOutcome, decisionFields.clientKnowledge),
      defect_claim: 'not_made',
      note: input.interpretationNote,
    },
    information_loss_boundary: decision.boundary,
    confidence: decision.confidence,
    boundary_basis: decision.basis,
    evidence: input.evidence,
    limits: input.limits,
    repetitions: input.repetitions,
  }
}
