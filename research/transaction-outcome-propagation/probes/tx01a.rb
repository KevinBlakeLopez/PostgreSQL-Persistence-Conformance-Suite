# TX-01A through the ruby pg gem. Prints one JSON object. Does not print the password.
require 'pg'
require 'json'

conn = PG.connect(
  host: ENV.fetch('PPCS_HOST'),
  port: ENV.fetch('PPCS_PORT'),
  dbname: ENV.fetch('PPCS_DATABASE'),
  user: ENV.fetch('PPCS_USER'),
  password: ENV.fetch('PPCS_PASSWORD')
)
marker = ENV.fetch('PPCS_MARKER')
conn.exec('BEGIN')
conn.exec_params('insert into item (name) values ($1)', [marker])
id = conn.exec('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid').first
sqlstate = nil
begin
  conn.exec("insert into uniq (code) values ('taken')")
rescue PG::Error => error
  sqlstate = error.result&.result_error_field(PG::PG_DIAG_SQLSTATE)
end
commit_error = nil
result = nil
begin
  result = conn.exec('COMMIT')
rescue PG::Error => error
  commit_error = error.message.to_s.split("\n").first&.slice(0, 200)
end
puts({
  xid: id['xid'],
  pid: id['pid'].to_i,
  sqlstate: sqlstate,
  cmd_status: result&.cmd_status,
  transaction_status: conn.transaction_status,
  commit_error: commit_error,
  pg_version: PG::VERSION
}.to_json)
conn.close
