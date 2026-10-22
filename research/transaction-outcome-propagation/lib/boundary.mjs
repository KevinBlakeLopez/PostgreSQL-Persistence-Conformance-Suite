// Decides where a transaction outcome stopped matching what PostgreSQL did.
// The function sees only the fields below. A missing observation stays unknown;
// it is not treated as success.

export const DATABASE_OUTCOMES = ['COMMITTED', 'ROLLED_BACK', 'NOT_ATTEMPTED', 'UNKNOWN']
export const APPLICATION_REPORTS = ['REPORTED_SUCCESS', 'REPORTED_FAILURE', 'REPORTED_ROLLBACK', 'REPORTED_UNKNOWN', 'NO_RESULT', 'NOT_APPLICABLE']
export const BOUNDARIES = ['SERVER', 'PROTOCOL', 'DRIVER', 'POOL', 'TRANSACTION_MANAGER', 'FRAMEWORK', 'APPLICATION', 'MULTIPLE', 'NONE', 'UNDETERMINED']
export const CAPABILITIES = ['EXPOSED', 'INDIRECT', 'INTERNAL_ONLY', 'NOT_EXPOSED', 'UNKNOWN', 'NOT_APPLICABLE']
export const OBSERVATIONS = ['OBSERVED', 'INFERRED', 'NOT_OBSERVED', 'NOT_EXPOSED', 'NOT_APPLICABLE']

const PRESERVES_NON_COMMIT = new Set(['REPORTED_ROLLBACK', 'REPORTED_FAILURE'])

/**
 * Map an independent observer result to a database outcome.
 * Disagreement between pg_xact_status() and marker visibility is UNKNOWN.
 * NOT_ATTEMPTED is not inferred here: the caller has to have recorded that the
 * transaction was never started.
 */
export function verifiedOutcome({ fate, markerVisible }) {
  if (fate === 'aborted' && markerVisible === false) return 'ROLLED_BACK'
  if (fate === 'committed' && markerVisible === true) return 'COMMITTED'
  return 'UNKNOWN'
}

function showedRollback(input) {
  return input.driverCommandTag === 'ROLLBACK'
    && input.driverCommandTagObservation === 'OBSERVED'
    && (input.driverCommandTagCapability === 'EXPOSED' || input.driverCommandTagCapability === 'INDIRECT')
}

function frameworkPreserves(input) {
  return input.frameworkPresent === false
    || PRESERVES_NON_COMMIT.has(input.frameworkReported)
}

/**
 * @returns {{ boundary: string, confidence: string, basis: string }}
 */
export function classifyBoundary(input) {
  if (input.scenarioPreconditionsMet === false) {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The scenario preconditions were not met, so this record does not name a propagation boundary.',
    }
  }
  if (input.supportingContradiction === true) {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: input.contradiction || 'A supporting observation contradicted the commit-tag evidence.',
    }
  }

  if (input.clientKnowledge === 'UNKNOWN') {
    const reported = input.applicationReported
    if (reported === 'REPORTED_FAILURE' || reported === 'REPORTED_UNKNOWN') {
      return {
        boundary: 'NONE',
        confidence: 'HIGH',
        basis: 'The client did not receive the acknowledgment. The application reported a failure or uncertainty, rather than a successful commit or a confirmed rollback.',
      }
    }
    if (reported === 'REPORTED_SUCCESS' && input.frameworkPresent === true && input.frameworkReported === 'REPORTED_SUCCESS') {
      return {
        boundary: 'FRAMEWORK',
        confidence: 'HIGH',
        basis: 'The client did not receive the commit acknowledgment, and the framework reported success.',
      }
    }
    if (reported === 'REPORTED_SUCCESS' && input.frameworkPresent === false) {
      return {
        boundary: 'APPLICATION',
        confidence: 'HIGH',
        basis: 'The client did not receive the commit acknowledgment, and the application reported success.',
      }
    }
    if (reported === 'REPORTED_ROLLBACK' && input.frameworkPresent === true && input.frameworkReported === 'REPORTED_ROLLBACK') {
      return {
        boundary: 'FRAMEWORK',
        confidence: 'HIGH',
        basis: 'The client did not receive the commit acknowledgment, and the framework reported a confirmed rollback.',
      }
    }
    if (reported === 'REPORTED_ROLLBACK' && input.frameworkPresent === false) {
      return {
        boundary: 'APPLICATION',
        confidence: 'HIGH',
        basis: 'The client did not receive the commit acknowledgment, and the application reported a confirmed rollback.',
      }
    }
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The client did not receive the acknowledgment, and these reports do not identify one layer.',
    }
  }

  if (input.laterUnitCommittedEarlierWrite === true && input.frameworkPresent === true) {
    return {
      boundary: 'FRAMEWORK',
      confidence: 'HIGH',
      basis: 'A later unit of work committed the earlier write after the first unit reported failure and its ROLLBACK did not reach PostgreSQL. The framework released that connection back to the pool.',
    }
  }

  const verified = input.verifiedOutcome
  const application = input.applicationReported
  const applicationSuccess = application === 'REPORTED_SUCCESS'
  const applicationUnknown = application === 'REPORTED_UNKNOWN'

  if (verified === 'UNKNOWN') {
    if (applicationUnknown) {
      return {
        boundary: 'NONE',
        confidence: 'HIGH',
        basis: 'The independent check could not establish the outcome, and the application reported that uncertainty.',
      }
    }
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The independent check could not establish the outcome. A definite application report is not assigned to a layer from this input.',
    }
  }

  if (verified === 'NOT_ATTEMPTED') {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The transaction was not attempted. This input does not name a propagation boundary.',
    }
  }

  if (verified === 'COMMITTED' && applicationSuccess) {
    return {
      boundary: 'NONE',
      confidence: 'HIGH',
      basis: 'The application reported success and the independent check found a commit.',
    }
  }

  if (verified === 'COMMITTED' && application !== 'REPORTED_SUCCESS') {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The independent check found a commit, and the application reported something else. This input does not name the layer that produced that report.',
    }
  }

  if (verified === 'ROLLED_BACK' && PRESERVES_NON_COMMIT.has(application) && frameworkPreserves(input)) {
    return {
      boundary: 'NONE',
      confidence: 'HIGH',
      basis: 'The independent check found a rollback, and the application-visible result reports a rollback or a failure.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && input.frameworkPresent === true && PRESERVES_NON_COMMIT.has(input.frameworkReported) && showedRollback(input)) {
    return {
      boundary: 'APPLICATION',
      confidence: 'HIGH',
      basis: 'The driver exposed command tag ROLLBACK, the framework reported a non-commit, and the application reported success.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && showedRollback(input) && input.poolMaskedCommandTag === true) {
    if (input.frameworkPresent === true && input.frameworkReported === 'REPORTED_SUCCESS') {
      return {
        boundary: 'MULTIPLE',
        confidence: 'MEDIUM',
        basis: 'The driver exposed command tag ROLLBACK, the pool is recorded as having masked it, and the framework reported success.',
      }
    }
    return {
      boundary: 'POOL',
      confidence: 'MEDIUM',
      basis: 'The driver exposed command tag ROLLBACK and the pool is recorded as having masked that result before the caller could use it.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && input.frameworkPresent === true && input.frameworkReported === 'REPORTED_SUCCESS' && input.driverCallRejected === true) {
    return {
      boundary: 'FRAMEWORK',
      confidence: 'HIGH',
      basis: 'The driver rejected the ending call and the database rolled back. The framework still reported success.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && showedRollback(input) && input.frameworkPresent === true && input.frameworkReported === 'REPORTED_SUCCESS') {
    return {
      boundary: 'FRAMEWORK',
      confidence: 'HIGH',
      basis: 'The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && showedRollback(input) && input.frameworkPresent === false) {
    return {
      boundary: 'APPLICATION',
      confidence: 'HIGH',
      basis: 'The driver exposed command tag ROLLBACK on the public query result, and the application reported success.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess && input.driverCommandTagObservation === 'NOT_EXPOSED' && input.driverCommandTagCapability === 'NOT_EXPOSED') {
    return {
      boundary: 'DRIVER',
      confidence: 'MEDIUM',
      basis: 'The independent check found a rollback and the application reported success. The examined driver API does not expose the command tag. This input does not show the protocol message itself.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationSuccess) {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The application reported success after a verified rollback, and the driver command tag was not observed as an exposed ROLLBACK.',
    }
  }

  if (verified === 'ROLLED_BACK' && applicationUnknown) {
    return {
      boundary: 'UNDETERMINED',
      confidence: 'LOW',
      basis: 'The independent check found a rollback and the application reported uncertainty. This input does not name the layer that hid the outcome.',
    }
  }

  return {
    boundary: 'UNDETERMINED',
    confidence: 'LOW',
    basis: 'The observations do not match a classified propagation pattern.',
  }
}

export function interpretationKind(boundary, verified, clientKnowledge) {
  if (boundary === 'NONE' && clientKnowledge === 'UNKNOWN') return 'uncertainty_preserved'
  if (boundary === 'NONE' && verified === 'UNKNOWN') return 'uncertainty_preserved'
  if (boundary === 'NONE') return 'outcome_preserved'
  if (boundary === 'APPLICATION') return 'application_discarded_driver_result'
  if (boundary === 'FRAMEWORK') return 'framework_discarded_driver_result'
  if (boundary === 'DRIVER') return 'driver_did_not_expose'
  if (boundary === 'POOL') return 'pool_masked_driver_result'
  if (boundary === 'MULTIPLE') return 'multiple_layers'
  if (boundary === 'TRANSACTION_MANAGER') return 'transaction_manager_discarded_driver_result'
  if (boundary === 'SERVER') return 'server_outcome_insufficient'
  if (boundary === 'PROTOCOL') return 'protocol_outcome_insufficient'
  return 'undetermined'
}
