// Capability verdicts for pg.Client from one TX-01A observation.
// Untested capabilities stay UNKNOWN. A null row count is still an exposed field
// when the property was present on the result.

export const CAPABILITY_KEYS = [
  'command_tag',
  'affected_row_count',
  'sqlstate',
  'transaction_status',
  'connection_failure',
  'commit_acknowledgment',
  'unknown_commit_outcome',
  'rollback_acknowledgment',
  'connection_invalidation',
  'pool_reset',
  'savepoint_failure',
  'nested_transactions',
]

function sawCommand(obs) {
  return obs.commandTagObservation === 'OBSERVED'
    && obs.commandPresent === true
    && typeof obs.commandTag === 'string'
    && obs.commandTag.length > 0
}

function sawStatus(obs) {
  return typeof obs.statusAfterError === 'string' && obs.statusAfterError.length > 0
    && typeof obs.statusAfterCommit === 'string' && obs.statusAfterCommit.length > 0
}

/** @param {object} obs pg-read-tag observation, including commandPresent and rowCountPresent. */
export function pgCapabilityReport(obs) {
  const commandExposed = sawCommand(obs)
  const rowExposed = obs.rowCountPresent === true
  const sqlExposed = obs.sqlstate === '23505'
  const statusExposed = sawStatus(obs)
  const capabilities = {
    command_tag: commandExposed ? 'EXPOSED' : 'UNKNOWN',
    affected_row_count: rowExposed ? 'EXPOSED' : 'UNKNOWN',
    sqlstate: sqlExposed ? 'EXPOSED' : 'UNKNOWN',
    transaction_status: statusExposed ? 'EXPOSED' : 'UNKNOWN',
    connection_failure: 'UNKNOWN',
    commit_acknowledgment: commandExposed ? 'EXPOSED' : 'UNKNOWN',
    unknown_commit_outcome: 'UNKNOWN',
    rollback_acknowledgment: 'UNKNOWN',
    connection_invalidation: 'UNKNOWN',
    pool_reset: 'NOT_APPLICABLE',
    savepoint_failure: 'UNKNOWN',
    nested_transactions: 'NOT_APPLICABLE',
  }
  const notes = {
    command_tag: commandExposed
      ? `Client.query('COMMIT') resolved with Result.command ${JSON.stringify(obs.commandTag)}. The application can read that field on the public result.`
      : 'This run did not observe a command tag on Result.command.',
    affected_row_count: rowExposed
      ? `Result.rowCount is a separate field from Result.command. On this COMMIT result it was ${obs.rowCount === null || obs.rowCount === undefined ? 'null' : String(obs.rowCount)}.`
      : 'This run did not observe Result.rowCount.',
    sqlstate: sqlExposed
      ? 'The error caught from the duplicate insert has code 23505.'
      : `The caught error code was ${obs.sqlstate == null ? 'absent' : obs.sqlstate}.`,
    transaction_status: statusExposed
      ? `Client.getTransactionStatus() returned ${JSON.stringify(obs.statusAfterError)} after the statement error once Client.readyForQuery was true, and ${JSON.stringify(obs.statusAfterCommit)} after COMMIT. The method returns the ReadyForQuery status byte Client stored. The query promise can reject on ErrorResponse before that byte is updated.`
      : 'This run did not observe Client.getTransactionStatus().',
    connection_failure: 'TX-01A does not drop the connection. Distinguishing connection loss from a server-reported transaction failure was not tested.',
    commit_acknowledgment: commandExposed
      ? 'The acknowledgment recorded here is Result.command on the resolved COMMIT query.'
      : 'A COMMIT acknowledgment was not observed on Result.command.',
    unknown_commit_outcome: 'TX-01B was not run. Whether this driver can represent an unknown commit without asserting success or failure is UNKNOWN in this inventory.',
    rollback_acknowledgment: 'This scenario sends COMMIT after the statement error. A ROLLBACK command tag was not requested, so rollback acknowledgment was not tested.',
    connection_invalidation: 'Removing an unsafe connection from a pool was not tested.',
    pool_reset: 'This inventory is pg.Client. Pool reset is not a Client operation. The TypeORM subject uses pg-pool beside the driver, and this scenario does not record a reset statement.',
    savepoint_failure: 'TX-02 was not run.',
    nested_transactions: 'pg.Client executes the SQL it is given. It has no nested-transaction API of its own, so a nesting guarantee is not a Client capability.',
  }
  return { capabilities, notes }
}
