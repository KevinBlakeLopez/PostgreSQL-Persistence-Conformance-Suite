# frozen_string_literal: true

# Not a PPCS case. Three follow-ups on one disposable database:
# the documented restart-outside-the-transaction pattern, after_commit /
# after_rollback when a statement error is rescued inside the block, and the
# in-memory Item after that block returns. A second PG::Connection reads the
# rows. Nothing here is a harness classification.
$LOAD_PATH.unshift(File.expand_path('../../ruby/lib', __dir__))
require 'active_record'
require 'json'
require 'pg'
require 'ppcs'

Ppcs::Instrument.install!
ActiveRecord::Base.logger = nil

ROOT = File.expand_path('../../..', __dir__)
INST = JSON.parse(File.read(File.join(ROOT, '.ppcs-instance.json')))

def connect(dbname)
  PG.connect(
    host: INST['host'], port: INST['port'], user: INST['user'],
    password: INST['password'], dbname: dbname
  )
end

admin = connect('postgres')
abort 'refusing a server that is not this disposable instance' unless admin.exec('show cluster_name').getvalue(0, 0) == INST['token']
db = "ppcs_ar_probe_#{Process.pid}"
admin.exec("create database #{db}")

begin
  ActiveRecord::Base.establish_connection(
    adapter: 'postgresql',
    host: INST['host'], port: INST['port'], username: INST['user'], password: INST['password'],
    database: db, pool: 1
  )
  ActiveRecord::Base.connection.execute(<<~SQL)
    create table item (id serial primary key, name text, qty int);
    create table uniq (id serial primary key, code text unique);
    insert into uniq (code) values ('taken');
  SQL

  class Item < ActiveRecord::Base
    self.table_name = 'item'
  end

  class Uniq < ActiveRecord::Base
    self.table_name = 'uniq'
  end

  observer = connect(db)

  def observer.names
    exec('select name from item order by id').map { |row| row['name'] }
  end

  commits = []
  rollbacks = []
  Item.after_commit { commits << { name: name, id: id } }
  Item.after_rollback { rollbacks << { name: name, id: id } }

  safe = {}
  begin
    Item.transaction do
      Item.create!(name: 'safe-first')
      Uniq.create!(code: 'taken')
    end
    safe['first_returned'] = true
  rescue ActiveRecord::StatementInvalid => e
    safe['first_error'] = e.class.name
    safe['first_sqlstate'] = Ppcs.sqlstate(e)
    Item.transaction { Item.create!(name: 'safe-restart') }
    safe['restart_returned'] = true
  end
  safe['rows'] = observer.names
  safe['commit_replies_so_far'] = Ppcs::Instrument.commit_replies.dup

  caught = {}
  record = nil
  returned = false
  begin
    Item.transaction do
      record = Item.create!(name: 'caught')
      begin
        Uniq.create!(code: 'taken')
      rescue ActiveRecord::StatementInvalid => e
        caught['rescued'] = { 'class' => e.class.name, 'sqlstate' => Ppcs.sqlstate(e) }
      end
    end
    returned = true
  rescue StandardError => e
    caught['escaped'] = { 'class' => e.class.name, 'sqlstate' => Ppcs.sqlstate(e) }
  end
  caught['transaction_returned'] = returned
  caught['rows'] = observer.names
  caught['in_memory'] = {
    'class' => record.class.name,
    'id' => record.id,
    'persisted' => record.persisted?,
    'previously_new_record' => record.previously_new_record?,
    'destroyed' => record.destroyed?,
    'name' => record.name,
    'changed' => record.changed?,
    'previously_persisted' => (record.previously_persisted? if record.respond_to?(:previously_persisted?))
  }
  begin
    caught['reload'] = record.reload.name
  rescue StandardError => e
    caught['reload_error'] = "#{e.class}: #{e.message.split("\n").first}"
  end
  begin
    record.name = 'caught-again'
    record.save!
    caught['later_save'] = 'returned'
  rescue StandardError => e
    caught['later_save'] = "#{e.class}: #{e.message.split("\n").first}"
  end
  caught['rows_after_later_save'] = observer.names
  caught['commit_replies'] = Ppcs::Instrument.commit_replies.dup
  caught['callbacks'] = { 'after_commit' => commits.dup, 'after_rollback' => rollbacks.dup }
  caught['statements'] = Ppcs::Instrument.trace.grep(/INSERT|UPDATE|COMMIT|ROLLBACK|ERROR|INJECTED/)

  nested = { 'after_commit' => [], 'after_rollback' => [] }
  Item.reset_callbacks(:commit)
  Item.reset_callbacks(:rollback)
  Item.after_commit { nested['after_commit'] << name }
  Item.after_rollback { nested['after_rollback'] << name }
  Item.transaction do
    Item.create!(name: 'nested-outer')
    Item.transaction(requires_new: true) do
      Item.create!(name: 'nested-inner')
      raise ActiveRecord::Rollback
    end
  end
  nested['rows'] = observer.names

  puts JSON.generate({
    'ruby' => RUBY_DESCRIPTION,
    'activerecord' => Gem.loaded_specs['activerecord'].version.to_s,
    'pg' => Gem.loaded_specs['pg'].version.to_s,
    'libpq' => PG.library_version,
    'server' => admin.exec('show server_version').getvalue(0, 0),
    'safe_restart' => safe,
    'caught_statement_error' => caught,
    'nested_rollback' => nested
  })
ensure
  ActiveRecord::Base.connection_pool.disconnect! rescue nil
  observer&.close rescue nil
  admin.exec("drop database if exists #{db}") rescue nil
  admin.close rescue nil
end
