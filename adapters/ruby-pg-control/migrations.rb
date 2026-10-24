# frozen_string_literal: true

# MG-02 and MG-03 for the ruby-pg control. correct takes a transaction-scoped
# advisory lock before it reads history. unsafe takes none. The SQL gate is the
# runner's lock, which the migration waits on after inserting its marker.
#
# History storage. The harness creates ppcs_history for every migration case
# except MG-02.first-deployment, whose database starts with none. correct
# creates the table inside its migration transaction, after taking its lock.
# unsafe creates it outside the migration and, when a concurrent creation fails
# with a unique violation, carries on as if the table had existed: the mistake
# MG-02.first-deployment looks for.
FRAMEWORK_LOCK = 77_002_001
CREATE_HISTORY = 'create table if not exists ppcs_history (name text not null)'

MIGRATION_CONTRACT = {
  'correct' => 'The correct control runs a migration in one transaction. It takes a transaction-scoped advisory lock, then creates its history table if it is missing, before it reads history, applies the migration only when history has no entry, and commits the marker and the history entry together. A reversal deletes the marker and the history entry, refuses a migration that has no reversal, and rolls back a reversal that raises.',
  'unsafe' => 'The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.'
}.freeze

def with_migration_client(spec)
  conn = Ppcs.connect(spec)
  # CREATE TABLE IF NOT EXISTS sends a NOTICE when the table exists. Keep it off stderr.
  conn.set_notice_processor { |_message| nil }
  begin
    yield conn
  ensure
    begin
      conn&.close
    rescue StandardError
      nil
    end
  end
end

def spare_session(spec)
  conn = Ppcs.connect(spec)
  conn.exec('select 1')
  conn
end

def migration_failure(contract, error)
  {
    'reported' => 'failed',
    'exit_code' => 1,
    'basis' => 'the migration raised',
    'contract' => contract,
    'api_error' => Ppcs.err_info(error)
  }
end

def apply_migration(spec, mode:, marker:, migration_id:, gate:, hold:)
  contract = MIGRATION_CONTRACT.fetch(mode)
  spare = mode == 'correct' ? spare_session(spec) : nil
  begin
    with_migration_client(spec) do |conn|
      if mode == 'unsafe'
        begin
          conn.exec(CREATE_HISTORY)
        rescue PG::UniqueViolation, PG::DuplicateTable
          nil
        rescue StandardError => e
          return migration_failure(contract, e)
        end
      end
      conn.exec('BEGIN')
      begin
        conn.exec_params('select pg_advisory_xact_lock($1)', [FRAMEWORK_LOCK]) if mode == 'correct'
        conn.exec(CREATE_HISTORY) if mode == 'correct'
        existing = conn.exec_params('select 1 from ppcs_history where name = $1', [migration_id])
        if existing.ntuples.positive?
          conn.exec('COMMIT')
          return {
            'reported' => 'nothing_to_do',
            'exit_code' => 0,
            'basis' => 'history already held an entry, so the control applied nothing',
            'contract' => contract
          }
        end
        conn.exec_params('insert into item (name) values ($1)', [marker])
        conn.exec_params('select pg_advisory_xact_lock($1)', [gate]) if hold
        conn.exec_params('insert into ppcs_history (name) values ($1)', [migration_id])
        conn.exec('COMMIT')
        {
          'reported' => 'applied',
          'exit_code' => 0,
          'basis' => 'the control committed the marker and a history entry',
          'contract' => contract
        }
      rescue StandardError => e
        begin
          conn.exec('ROLLBACK')
        rescue StandardError
          nil
        end
        migration_failure(contract, e)
      end
    end
  ensure
    begin
      spare&.close
    rescue StandardError
      nil
    end
  end
end

def revert_migration(spec, mode:, marker:, migration_id:, reversal:)
  contract = MIGRATION_CONTRACT.fetch(mode)
  if mode == 'unsafe'
    return with_migration_client(spec) do |conn|
      conn.exec_params('delete from ppcs_history where name = $1', [migration_id])
      {
        'reported' => 'reverted',
        'exit_code' => 0,
        'basis' => 'the unsafe control deleted the history entry and reported a revert',
        'contract' => contract
      }
    end
  end
  if reversal == 'none'
    return {
      'reported' => 'refused',
      'exit_code' => 1,
      'basis' => 'the migration has no reversal, so the control refused',
      'contract' => contract,
      'api_error' => { 'class' => 'Error', 'code' => nil, 'message' => 'the migration has no reversal' }
    }
  end
  with_migration_client(spec) do |conn|
    conn.exec('BEGIN')
    begin
      conn.exec_params('delete from item where name = $1', [marker])
      conn.exec_params('insert into ppcs_undo (name) values ($1)', [marker])
      raise 'the reversal failed on purpose after deleting the marker' if reversal == 'partial-then-error'
      conn.exec_params('delete from ppcs_history where name = $1', [migration_id])
      conn.exec('COMMIT')
      {
        'reported' => 'reverted',
        'exit_code' => 0,
        'basis' => 'the control committed the reversal',
        'contract' => contract
      }
    rescue StandardError => e
      begin
        conn.exec('ROLLBACK')
      rescue StandardError
        nil
      end
      {
        'reported' => 'failed',
        'exit_code' => 1,
        'basis' => 'the reversal raised, and the control rolled it back',
        'contract' => contract,
        'api_error' => Ppcs.err_info(e)
      }
    end
  end
end

def run_migration(ctx, message)
  tools = Ppcs.case_tools(message)
  migration = tools['migration'] || {}
  marker = tools['markers']['m1']
  if migration['operation'] == 'revert'
    return revert_migration(
      ctx.connection,
      mode: tools['mode'],
      marker: marker,
      migration_id: migration['migrationId'],
      reversal: migration['reversal']
    )
  end
  apply_migration(
    ctx.connection,
    mode: tools['mode'],
    marker: marker,
    migration_id: migration['migrationId'],
    gate: migration['gate'],
    hold: migration['hold'] == true
  )
end

MIGRATION_CASES = {
  'MG-02.held' => method(:run_migration),
  'MG-02.first-deployment' => method(:run_migration),
  'MG-02.session-loss' => method(:run_migration),
  'MG-02.idle-session-timeout' => method(:run_migration),
  'MG-03.valid-reversal' => method(:run_migration),
  'MG-03.no-reversal' => method(:run_migration),
  'MG-03.failing-reversal' => method(:run_migration)
}.freeze
