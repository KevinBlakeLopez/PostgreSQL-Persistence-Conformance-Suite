# frozen_string_literal: true

require 'fileutils'
require 'tmpdir'

MIGRATION_CONTRACT = 'ActiveRecord::MigrationContext runs migrations from files. On PostgreSQL the migration and its schema_migrations change share a transaction unless disable_ddl_transaction is set. Migrator#with_advisory_lock calls PostgreSQLAdapter#get_advisory_lock, which is pg_try_advisory_lock. A second process that does not get the lock raises ActiveRecord::ConcurrentMigrationError instead of waiting. https://api.rubyonrails.org/v8.1.4/classes/ActiveRecord/Migration.html'

VERSION = '20260101000000'

def migration_outcome(reported, exit_code, basis, error = nil)
  out = {
    'reported' => reported,
    'exit_code' => exit_code,
    'basis' => basis,
    'contract' => MIGRATION_CONTRACT
  }
  out['api_error'] = error.is_a?(Hash) ? error : Ppcs.err_info(error) if error
  out
end

def write_migration(dir, marker:, gate:, hold:, reversal:)
  hold_line = hold ? "execute(\"SELECT pg_advisory_xact_lock(#{Integer(gate)})\")" : ''
  down = case reversal
         when 'none'
           <<~RUBY
             def down
               raise ActiveRecord::IrreversibleMigration, 'the migration has no reversal'
             end
           RUBY
         when 'partial-then-error'
           <<~RUBY
             def down
               execute("DELETE FROM item WHERE name = " + connection.quote(#{marker.inspect}))
               raise 'the reversal failed on purpose after deleting the marker'
             end
           RUBY
         else
           <<~RUBY
             def down
               execute("DELETE FROM item WHERE name = " + connection.quote(#{marker.inspect}))
             end
           RUBY
         end
  File.write(File.join(dir, "#{VERSION}_ppcs_marker.rb"), <<~RUBY)
    class PpcsMarker < ActiveRecord::Migration[8.1]
      def up
        execute("INSERT INTO item (name) VALUES (" + connection.quote(#{marker.inspect}) + ")")
        #{hold_line}
      end
      #{down}
    end
  RUBY
end

def run_migration(_ctx, message)
  tools = Ppcs.case_tools(message)
  migration = tools['migration'] || {}
  marker = tools['markers']['m1']
  dir = Dir.mktmpdir('ppcs-ar-migration')
  begin
    write_migration(
      dir,
      marker: marker,
      gate: migration['gate'],
      hold: migration['hold'] == true,
      reversal: migration['reversal']
    )
    context = ActiveRecord::MigrationContext.new(dir)
    if migration['operation'] == 'revert'
      context.rollback
      return migration_outcome('reverted', 0, 'MigrationContext#rollback returned')
    end
    already = context.get_all_versions.include?(VERSION.to_i)
    context.migrate
    if already
      return migration_outcome('nothing_to_do', 0, 'schema_migrations already recorded this version, so MigrationContext#migrate changed nothing')
    end
    migration_outcome('applied', 0, 'MigrationContext#migrate returned')
  rescue ActiveRecord::ConcurrentMigrationError => e
    migration_outcome('failed', 1, 'Migrator#with_advisory_lock raised ConcurrentMigrationError', e)
  rescue ActiveRecord::IrreversibleMigration => e
    migration_outcome('refused', 1, 'the migration has no reversal, so Active Record raised IrreversibleMigration', e)
  rescue StandardError => e
    if e.cause.is_a?(ActiveRecord::IrreversibleMigration) || e.message.include?('IrreversibleMigration')
      migration_outcome('refused', 1, 'the migration has no reversal, so Active Record raised IrreversibleMigration', e.cause || e)
    elsif e.message.include?('ConcurrentMigrationError')
      migration_outcome('failed', 1, 'Migrator#with_advisory_lock raised ConcurrentMigrationError', e)
    else
      migration_outcome('failed', 1, 'the migration raised', e)
    end
  ensure
    FileUtils.remove_entry(dir) if dir
  end
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
