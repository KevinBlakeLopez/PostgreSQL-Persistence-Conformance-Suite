# frozen_string_literal: true

# Active Record adapter. Scored cases use ActiveRecord::Base.transaction and
# ActiveRecord::MigrationContext. Category C and D faults are injected on the
# PG::Connection Active Record uses, before Active Record sees the error.
# The statement trace is diagnostic. The reported outcome is the Active Record
# API result, not the command tag.
$LOAD_PATH.unshift(File.expand_path('../ruby/lib', __dir__))
require 'active_record'
require 'ppcs'

Ppcs::Instrument.install!
ActiveRecord::Migration.verbose = false
ActiveRecord::Base.logger = nil

CONTRACT = 'ActiveRecord::Base.transaction commits when the block returns. It rolls back and re-raises when the block raises, except ActiveRecord::Rollback, which rolls back and is not re-raised. Rails documents that rescuing ActiveRecord::StatementInvalid inside the block does not roll the transaction back, and that on PostgreSQL a statement error aborts the transaction until the whole transaction is restarted. A nested transaction joins the parent unless requires_new: true, which is a savepoint. https://api.rubyonrails.org/v8.1.4/classes/ActiveRecord/Transactions/ClassMethods.html'

SAVEPOINT_FORM = {
  'name' => 'transaction(requires_new: true)',
  'reason' => 'A nested transaction block joins the parent transaction. requires_new: true is the documented savepoint form.'
}.freeze

class Item < ActiveRecord::Base
  self.table_name = 'item'
end

class Uniq < ActiveRecord::Base
  self.table_name = 'uniq'
end

def establish(message)
  spec = message['connection']
  settings = message.dig('case', 'settings') || {}
  config = {
    adapter: 'postgresql',
    host: spec['host'],
    port: spec['port'],
    username: spec['user'],
    password: spec['password'],
    database: spec['database'],
    application_name: spec['application_name'],
    pool: settings['pool_max'] || 1,
    checkout_timeout: 5
  }
  config[:options] = spec['options'] if spec['options']
  ActiveRecord::Base.establish_connection(config)
end

def identify(isolation: false)
  sql = if isolation
          "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as transaction_isolation"
        else
          'select pg_current_xact_id()::text as xid, pg_backend_pid() as pid'
        end
  row = ActiveRecord::Base.with_connection { |connection| connection.select_one(sql) }
  row = row.transform_keys(&:to_s)
  out = { 'xid' => row['xid'].to_s, 'pid' => Integer(row['pid']) }
  out['transaction_isolation'] = row['transaction_isolation'] if isolation
  out
end

def managed(model = Item, **options)
  thrown = nil
  begin
    model.transaction(**options) do
      begin
        yield
      rescue StandardError => e
        thrown = e
        raise
      end
    end
    { 'reported' => 'committed', 'basis' => 'ActiveRecord::Base.transaction returned', 'contract' => CONTRACT }
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    same = thrown && (e.equal?(thrown) || e.cause&.equal?(thrown))
    if same
      {
        'reported' => 'rolled_back',
        'basis' => 'ActiveRecord::Base.transaction raised the error the block raised',
        'contract' => CONTRACT,
        'api_error' => Ppcs.err_info(e)
      }
    else
      {
        'reported' => 'failed',
        'basis' => 'ActiveRecord::Base.transaction raised an error the block did not raise',
        'contract' => CONTRACT,
        'api_error' => Ppcs.err_info(e)
      }
    end
  end
end

def nested_failure(fault)
  lambda do |_ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    nested = { 'caught' => false }
    armed = nil
    id = nil
    outcome = managed do
      Item.create!(name: markers['outer'])
      id = identify
      Ppcs.checkpoint('outer-after-write', id)
      begin
        Item.transaction(requires_new: true) do
          Item.create!(name: markers['inner'])
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
    outcome.merge('steps' => steps, 'form' => SAVEPOINT_FORM)
  end
end

def failed_unit_then_next(failure)
  lambda do |_ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    fault = nil
    id = nil
    violation = nil
    unit1 = managed do
      Item.create!(name: markers['doomed'])
      id = identify
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
          Uniq.create!(code: 'taken')
        rescue ActiveRecord::StatementInvalid => e
          violation = Ppcs.err_info(e)
          raise
        end
      end
      raise 'application error: unit 1 fails'
    end
    Ppcs::Instrument.clear_faults!
    Ppcs.checkpoint('after-unit1', { 'pid' => id&.dig('pid') })
    unit2 = Ppcs.bounded_unit(tools['settings']['bound_ms'] || 5000) do
      managed do
        Item.create!(name: markers['next'])
        Ppcs.checkpoint('unit2-after-write', identify)
      end
    end
    steps = { 'unit2' => unit2 }
    steps['violation'] = violation if violation
    steps['fault'] = Ppcs::Instrument.fault_report(fault) if fault
    unit1.merge('steps' => steps)
  end
end

def nested_only(variant)
  lambda do |_ctx, message|
    tools = Ppcs.case_tools(message)
    markers = tools['markers']
    nested = { 'caught' => false, 'completed' => false }
    outcome = managed do
      Item.create!(name: markers['outer'])
      begin
        Item.transaction(requires_new: true) do
          Item.create!(name: markers['inner'])
          Ppcs.checkpoint('inner-after-write', identify)
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
    outcome.merge('steps' => { 'nested' => nested }, 'form' => SAVEPOINT_FORM)
  end
end

def requested_level(_ctx, message)
  tools = Ppcs.case_tools(message)
  markers = tools['markers']
  level = tools['settings']['isolation_level']
  raise Ppcs::ProtocolError, "the case requests an unknown isolation level: #{level.inspect}" unless level.is_a?(String)
  started = false
  outcome = managed(isolation: level.tr(' ', '_').to_sym) do
    started = true
    Item.create!(name: markers['tx'])
    Item.where(name: markers['tx']).pick(:name)
    Ppcs.checkpoint('after-read', identify(isolation: true))
  end
  return outcome if started || outcome['reported'] != 'failed'
  begin
    managed do
      Item.create!(name: markers['tx'])
      Ppcs.checkpoint('baseline', identify)
    end
    outcome
  rescue Ppcs::ProtocolError
    raise
  rescue StandardError => e
    outcome.merge('steps' => { 'baseline' => { 'error' => Ppcs.err_info(e) } })
  end
end

require_relative 'migrations'

CASES = {
  'CTL-01.commit' => lambda do |_ctx, message|
    markers = Ppcs.case_tools(message)['markers']
    managed do
      Item.create!(name: markers['tx'])
      Ppcs.checkpoint('before-end', identify)
    end
  end,
  'CTL-01.rollback' => lambda do |_ctx, message|
    markers = Ppcs.case_tools(message)['markers']
    managed do
      Item.create!(name: markers['tx'])
      Ppcs.checkpoint('before-end', identify)
      raise 'application error: the request fails'
    end
  end,
  'TX-01A.caught-error-then-commit' => lambda do |_ctx, message|
    markers = Ppcs.case_tools(message)['markers']
    steps = {}
    outcome = managed do
      Item.create!(name: markers['tx'])
      id = identify
      Ppcs.checkpoint('after-write', id)
      begin
        Uniq.create!(code: 'taken')
      rescue ActiveRecord::StatementInvalid => e
        steps['violation'] = Ppcs.err_info(e)
      end
      Ppcs.checkpoint('before-end', { 'pid' => id['pid'] })
    end
    outcome.merge('steps' => steps)
  end,
  'TX-01B.conn-lost-before-commit' => lambda do |_ctx, message|
    tools = Ppcs.case_tools(message)
    managed do
      Item.create!(name: tools['markers']['tx'])
      Ppcs.checkpoint('before-end', identify)
      sleep((tools['settings']['settle_ms'] || 100) / 1000.0)
    end
  end,
  'TX-01B.commit-reply-discarded' => lambda do |_ctx, message|
    markers = Ppcs.case_tools(message)['markers']
    fault = nil
    outcome = managed do
      Item.create!(name: markers['tx'])
      Ppcs.checkpoint('before-end', identify)
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
  'TX-05.managed-serializable' => method(:requested_level)
}.merge(MIGRATION_CASES)

Ppcs.run(
  describe: lambda do
    {
      'adapter' => { 'name' => 'activerecord', 'version' => '0.1.0' },
      'framework' => { 'name' => 'activerecord', 'version' => Gem.loaded_specs['activerecord'].version.to_s },
      'driver' => { 'name' => 'pg', 'version' => Gem.loaded_specs['pg'].version.to_s },
      'components' => {
        'ruby' => RUBY_DESCRIPTION,
        'activerecord' => Gem.loaded_specs['activerecord'].version.to_s,
        'pg' => Gem.loaded_specs['pg'].version.to_s,
        'libpq' => PG.library_version.to_s
      }
    }
  end,
  modes: {
    'native' => {
      configuration: {
        'api' => 'ActiveRecord::Base.transaction',
        'nested' => 'transaction(requires_new: true) savepoint',
        'pool' => 'connection pool size from the case pool_max',
        'faults' => 'category C and D faults are injected on PG::Connection before Active Record sees the error',
        'migrations' => 'ActiveRecord::MigrationContext'
      }
    }
  },
  open: lambda do |message, _mode|
    establish(message)
    {
      context: Object.new,
      close: lambda do
        ActiveRecord::Base.connection_pool.disconnect!
      rescue StandardError
        nil
      end,
      diagnostics: lambda do
        {
          'trace' => Ppcs::Instrument.trace,
          'commit_replies' => Ppcs::Instrument.commit_replies
        }
      end
    }
  end,
  cases: CASES
)
