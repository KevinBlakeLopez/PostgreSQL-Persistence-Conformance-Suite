# frozen_string_literal: true

# ruby-pg control. Transactions are explicit SQL on a PG::Connection.
# correct reads PG::Result#cmd_status and refuses to call an ambiguous COMMIT a
# commit or a rollback. unsafe treats a COMMIT that does not raise as success.
$LOAD_PATH.unshift(File.expand_path('../ruby/lib', __dir__))
require 'ppcs'

Ppcs::Instrument.install!

CONTRACT = {
  'correct' => 'The correct control reports committed only when PG::Result#cmd_status for COMMIT is COMMIT. A command tag of ROLLBACK is a rollback. Any other tag, or a COMMIT that raises, is a failure: the control does not treat an ambiguous outcome as a confirmed commit or a confirmed rollback. After a failed savepoint rollback it sends ROLLBACK instead of COMMIT. It starts a transaction at the isolation level requested of it.',
  'unsafe' => 'The unsafe control reports committed whenever COMMIT does not raise, whatever PG::Result#cmd_status is, and reports a rollback whenever COMMIT raises. It ignores a failed savepoint rollback, returns a connection whose ROLLBACK failed, and defers a write made before a nested scope into that scope\'s savepoint. It starts every transaction with a plain BEGIN.'
}.freeze

POOL_CONTRACT = {
  'correct' => 'The correct control discards a connection whose ROLLBACK failed, so that transaction can only end by the session closing, and reports a unit whose body threw as rolled back.',
  'unsafe' => 'The unsafe control returns a connection whose ROLLBACK failed and reports a unit whose body threw as rolled back.'
}.freeze

LEVELS = ['read uncommitted', 'read committed', 'repeatable read', 'serializable'].freeze

class OneConnectionPool
  def initialize(spec, mode)
    @spec = spec
    @mode = mode
    @conn = nil
  end

  def acquire
    return @conn if @conn
    @conn = Ppcs.connect(@spec)
  end

  def release(broken)
    return unless broken && @mode == 'correct'
    conn = @conn
    @conn = nil
    conn&.close
  rescue StandardError
    nil
  end

  def close
    @conn&.close
  rescue StandardError
    nil
  end
end

def rolled_back_error(message)
  { 'class' => 'TransactionRolledBackError', 'code' => nil, 'message' => message }
end

def with_outcome(classified, contract, error: nil)
  out = {
    'reported' => classified[:reported],
    'basis' => classified[:basis],
    'contract' => contract
  }
  if classified[:reported] != 'committed'
    out['api_error'] = error ? Ppcs.err_info(error) : rolled_back_error(classified[:basis])
  end
  out
end

def transaction(conn, mode, begin_sql: 'BEGIN')
  state = {}
  contract = CONTRACT.fetch(mode)
  conn.exec(begin_sql)
  body_error = nil
  begin
    yield(conn, state)
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    body_error = e
    begin
      conn.exec('ROLLBACK')
    rescue StandardError
      nil
    end
  end
  if body_error
    return with_outcome(
      { reported: 'rolled_back', basis: 'the body threw, and the control sent ROLLBACK' },
      contract,
      error: body_error
    )
  end
  if mode == 'correct' && state[:rollback_only]
    begin
      conn.exec('ROLLBACK')
    rescue StandardError
      nil
    end
    return with_outcome(
      { reported: 'rolled_back', basis: 'a savepoint rollback had failed, so the control ended the transaction with ROLLBACK instead of COMMIT' },
      contract
    )
  end
  begin
    result = conn.exec('COMMIT')
    tag = result.cmd_status
    Ppcs.last_commit = {
      'cmd_status' => tag,
      'result_status' => (PG::Result.res_status(result.result_status) rescue result.result_status),
      'transaction_status' => Ppcs.transaction_status_name(conn)
    }
    with_outcome(Ppcs::CommitOutcome.classify(mode, tag: tag, error: nil), contract)
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    Ppcs.last_commit = { 'error' => Ppcs.err_info(e), 'transaction_status' => (Ppcs.transaction_status_name(conn) rescue 'unavailable') }
    with_outcome(Ppcs::CommitOutcome.classify(mode, tag: nil, error: e), contract, error: e)
  end
end

def nested_scope(conn, state)
  conn.exec('SAVEPOINT ppcs_nested')
  begin
    yield conn
    conn.exec('RELEASE SAVEPOINT ppcs_nested')
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    begin
      conn.exec('ROLLBACK TO SAVEPOINT ppcs_nested')
    rescue Ppcs::ProtocolError
      raise
    rescue StandardError => rollback_error
      state[:rollback_only] = Ppcs.err_info(rollback_error)
    end
    raise e
  end
end

def identify(conn, isolation: false)
  sql = if isolation
          "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation"
        else
          'select pg_current_xact_id()::text as xid, pg_backend_pid() as pid'
        end
  row = conn.exec(sql).first
  out = { 'xid' => row['xid'].to_s, 'pid' => Integer(row['pid']) }
  out['transaction_isolation'] = row['transaction_isolation'] if isolation
  out
end

def nested_failure(fault)
  lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    mode = tools['mode']
    state = {}
    nested = { 'caught' => false }
    armed = nil
    id = nil
    outcome = transaction(ctx.client, mode) do |conn, txn_state|
      state = txn_state
      conn.exec_params('insert into item (name) values ($1)', [markers['outer']])
      id = identify(conn)
      Ppcs.checkpoint('outer-after-write', id)
      begin
        nested_scope(conn, state) do |inner|
          inner.exec_params('insert into item (name) values ($1)', [markers['inner']])
          Ppcs.checkpoint('inner-after-write', { 'pid' => id['pid'] })
          if fault == 'conn-lost'
            sleep((tools['settings']['settle_ms'] || 100) / 1000.0)
          else
            armed = Ppcs::Instrument.savepoint_rollback_fault(fault) do
              Ppcs.checkpoint('after-fault', { 'pid' => id['pid'] })
            end
          end
          raise 'application error: the nested scope fails'
        end
      rescue Ppcs::ProtocolError
        raise
      rescue StandardError => e
        nested['caught'] = true
        nested['error'] = Ppcs.err_info(e)
      end
    end
    Ppcs::Instrument.clear_faults!
    Ppcs.checkpoint('after-outer', { 'pid' => id&.dig('pid') })
    steps = { 'nested' => nested }
    steps['fault'] = Ppcs::Instrument.fault_report(armed) if armed
    outcome.merge('steps' => steps)
  end
end

def failed_unit_then_next(failure)
  lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    mode = tools['mode']
    pool = ctx.pool(mode)
    fault = nil
    id = nil
    violation = nil
    unit1 = pooled_unit(pool, mode) do |conn|
      conn.exec_params('insert into item (name) values ($1)', [markers['doomed']])
      id = identify(conn)
      Ppcs.checkpoint('unit1-after-write', id)
      if failure == 'conn-lost'
        sleep((tools['settings']['settle_ms'] || 100) / 1000.0)
      else
        fault = Ppcs::Instrument.add_fault(match: Ppcs::ROLLBACK_SQL, mode: 'client-reject', on_fire: lambda {
          Ppcs.checkpoint('after-fault', { 'pid' => id['pid'] })
        })
      end
      if failure == 'statement-error'
        begin
          conn.exec("insert into uniq (code) values ('taken')")
        rescue StandardError => e
          violation = Ppcs.err_info(e)
          raise
        end
      end
      raise 'application error: unit 1 fails'
    end
    Ppcs::Instrument.clear_faults!
    Ppcs.checkpoint('after-unit1', { 'pid' => id&.dig('pid') })
    unit2 = Ppcs.bounded_unit(tools['settings']['bound_ms'] || 5000) do
      pooled_unit(pool, mode) do |conn|
        conn.exec_params('insert into item (name) values ($1)', [markers['next']])
        Ppcs.checkpoint('unit2-after-write', identify(conn))
      end
    end
    steps = { 'unit2' => unit2 }
    steps['violation'] = violation if violation
    steps['fault'] = Ppcs::Instrument.fault_report(fault) if fault
    unit1.merge('steps' => steps)
  end
end

def pooled_unit(pool, mode)
  contract = POOL_CONTRACT.fetch(mode)
  client = nil
  begin
    client = pool.acquire
    client.exec('BEGIN')
  rescue StandardError => e
    pool.release(true) if client
    return {
      'reported' => 'failed',
      'basis' => 'the unit could not start a transaction',
      'contract' => contract,
      'api_error' => Ppcs.err_info(e)
    }
  end
  broken = false
  begin
    yield client
    client.exec('COMMIT')
    { 'reported' => 'committed', 'basis' => 'COMMIT succeeded', 'contract' => contract }
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    begin
      client.exec('ROLLBACK')
    rescue StandardError
      broken = true
    end
    {
      'reported' => 'rolled_back',
      'basis' => broken ? "the body threw; ROLLBACK failed, and the connection was #{mode == 'correct' ? 'discarded' : 'kept'}" : 'the body threw; ROLLBACK succeeded',
      'contract' => contract,
      'api_error' => Ppcs.err_info(e)
    }
  ensure
    pool.release(broken)
  end
end

def nested_only(variant)
  lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    mode = tools['mode']
    nested = { 'caught' => false, 'completed' => false }
    deferred = []
    outcome = transaction(ctx.client, mode) do |conn, _state|
      if mode == 'unsafe'
        deferred << markers['outer']
      else
        conn.exec_params('insert into item (name) values ($1)', [markers['outer']])
      end
      begin
        nested_scope(conn, {}) do |inner|
          until deferred.empty?
            inner.exec_params('insert into item (name) values ($1)', [deferred.shift])
          end
          inner.exec_params('insert into item (name) values ($1)', [markers['inner']])
          Ppcs.checkpoint('inner-after-write', identify(inner))
          raise 'application error: the nested scope fails' if variant == 'nested-fails'
        end
        nested['completed'] = true
      rescue Ppcs::ProtocolError
        raise
      rescue StandardError
        nested['caught'] = true
      end
      raise 'application error: the outer scope fails' if variant == 'outer-fails'
    end
    outcome.merge('steps' => { 'nested' => nested })
  end
end

def requested_level(ctx, message)
  tools = Ppcs.case_tools(message)
  markers = tools['markers']
  mode = tools['mode']
  level = tools['settings']['isolation_level']
  raise Ppcs::ProtocolError, "the case requests an unknown isolation level: #{level.inspect}" unless LEVELS.include?(level)
  begin_sql = mode == 'correct' ? "BEGIN ISOLATION LEVEL #{level.upcase}" : 'BEGIN'
  outcome = transaction(ctx.client, mode, begin_sql: begin_sql) do |conn, _state|
    conn.exec_params('insert into item (name) values ($1)', [markers['tx']])
    conn.exec_params('select name from item where name = $1', [markers['tx']])
    Ppcs.checkpoint('after-read', identify(conn, isolation: true))
  end
  outcome.merge('steps' => { 'begin' => begin_sql })
end

require_relative 'migrations'

CASES = {
  'CTL-01.commit' => lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    transaction(ctx.client, tools['mode']) do |conn, _state|
      conn.exec_params('insert into item (name) values ($1)', [tools['markers']['tx']])
      Ppcs.checkpoint('before-end', identify(conn))
    end
  end,
  'CTL-01.rollback' => lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    transaction(ctx.client, tools['mode']) do |conn, _state|
      conn.exec_params('insert into item (name) values ($1)', [tools['markers']['tx']])
      Ppcs.checkpoint('before-end', identify(conn))
      raise 'application error: the request fails'
    end
  end,
  'TX-01A.caught-error-then-commit' => lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    steps = {}
    outcome = transaction(ctx.client, tools['mode']) do |conn, _state|
      conn.exec_params('insert into item (name) values ($1)', [tools['markers']['tx']])
      id = identify(conn)
      Ppcs.checkpoint('after-write', id)
      begin
        conn.exec("insert into uniq (code) values ('taken')")
      rescue StandardError => e
        steps['violation'] = Ppcs.err_info(e)
      end
      Ppcs.checkpoint('before-end', { 'pid' => id['pid'] })
    end
    outcome.merge('steps' => steps)
  end,
  'TX-01B.conn-lost-before-commit' => lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    transaction(ctx.client, tools['mode']) do |conn, _state|
      conn.exec_params('insert into item (name) values ($1)', [tools['markers']['tx']])
      Ppcs.checkpoint('before-end', identify(conn))
      sleep((tools['settings']['settle_ms'] || 100) / 1000.0)
    end
  end,
  'TX-01B.commit-reply-discarded' => lambda do |ctx, message|
    tools = Ppcs.case_tools(message)
    fault = nil
    outcome = transaction(ctx.client, tools['mode']) do |conn, _state|
      conn.exec_params('insert into item (name) values ($1)', [tools['markers']['tx']])
      Ppcs.checkpoint('before-end', identify(conn))
      fault = Ppcs::Instrument.add_fault(match: Ppcs::COMMIT_SQL, mode: 'reply-lost')
    end
    outcome.merge('steps' => { 'fault' => { 'mode' => 'reply-lost', 'fired' => fault ? fault[:fired] : 0 } })
  end,
  'TX-02.savepoint-rollback-not-sent' => nested_failure('not-sent'),
  'TX-02.savepoint-rollback-rejected' => nested_failure('rejected'),
  'TX-02.conn-lost-before-savepoint-rollback' => nested_failure('conn-lost'),
  'TX-03.rollback-not-sent' => failed_unit_then_next('rollback-not-sent'),
  'TX-03.statement-error-rollback-not-sent' => failed_unit_then_next('statement-error'),
  'TX-03.conn-lost-in-transaction' => failed_unit_then_next('conn-lost'),
  'TX-04.nested-failure-contained' => nested_only('nested-fails'),
  'TX-04.nested-released-outer-rollback' => nested_only('outer-fails'),
  'TX-05.managed-serializable' => method(:requested_level),
  'TX-05.explicit-serializable' => method(:requested_level)
}.merge(MIGRATION_CASES)

class ControlContext
  def initialize(spec)
    @spec = spec
    @client = nil
    @pool = nil
  end

  def connection
    @spec
  end

  def client
    @client ||= Ppcs.connect(@spec)
  end

  def pool(mode)
    @pool ||= OneConnectionPool.new(@spec, mode)
  end

  def close
    begin
      @client&.close
    rescue StandardError
      nil
    end
    @pool&.close
  end
end

Ppcs.last_commit = nil

def self.pg_version
  Gem.loaded_specs['pg'].version.to_s
end

Ppcs.run(
  describe: lambda do
    {
      'adapter' => { 'name' => 'ruby-pg-control', 'version' => '0.1.0' },
      'framework' => { 'name' => 'ruby-pg-control', 'version' => '0.1.0' },
      'driver' => { 'name' => 'pg', 'version' => pg_version },
      'components' => {
        'ruby' => RUBY_DESCRIPTION,
        'pg' => pg_version,
        'libpq' => PG.library_version.to_s
      }
    }
  end,
  modes: {
    'correct' => {
      configuration: {
        'commit_reply' => 'cmd_status checked; only COMMIT is a commit, only ROLLBACK is a rollback',
        'commit_error' => 'reported as a failure',
        'failed_savepoint_rollback' => 'transaction ended with ROLLBACK',
        'failed_rollback' => 'connection discarded',
        'write_before_nested_scope' => 'sent at once',
        'isolation_level' => 'sent with BEGIN'
      }
    },
    'unsafe' => {
      configuration: {
        'commit_reply' => 'ignored',
        'commit_error' => 'reported as a rollback',
        'failed_savepoint_rollback' => 'ignored',
        'failed_rollback' => 'connection kept',
        'write_before_nested_scope' => 'deferred into the nested scope savepoint',
        'isolation_level' => 'ignored: plain BEGIN'
      }
    }
  },
  open: lambda do |message, _mode|
    ctx = ControlContext.new(message['connection'])
    {
      context: ctx,
      close: -> { ctx.close },
      diagnostics: lambda do
        {
          'trace' => Ppcs::Instrument.trace,
          'commit_replies' => Ppcs::Instrument.commit_replies,
          'last_commit' => Ppcs.last_commit,
          'note' => 'PG::Connection#transaction_status is IDLE after both a COMMIT tag and a ROLLBACK tag. cmd_status is the public field that distinguishes them.'
        }
      end
    }
  end,
  cases: CASES
)
