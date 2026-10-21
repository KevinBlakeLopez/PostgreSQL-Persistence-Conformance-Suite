# frozen_string_literal: true

$LOAD_PATH.unshift(File.expand_path('../lib', __dir__))
require 'ppcs'

failures = []

def check(failures, label)
  yield
rescue StandardError => e
  failures << "#{label}: #{e.class}: #{e.message}"
end

check(failures, 'correct COMMIT tag') do
  got = Ppcs::CommitOutcome.classify('correct', tag: 'COMMIT', error: nil)
  raise got.inspect unless got[:reported] == 'committed'
end

check(failures, 'correct ROLLBACK tag') do
  got = Ppcs::CommitOutcome.classify('correct', tag: 'ROLLBACK', error: nil)
  raise got.inspect unless got[:reported] == 'rolled_back'
end

check(failures, 'correct ambiguous tag') do
  got = Ppcs::CommitOutcome.classify('correct', tag: nil, error: nil)
  raise got.inspect unless got[:reported] == 'failed'
  got = Ppcs::CommitOutcome.classify('correct', tag: 'INSERT 0 1', error: nil)
  raise got.inspect unless got[:reported] == 'failed'
end

check(failures, 'correct raised commit') do
  got = Ppcs::CommitOutcome.classify('correct', tag: nil, error: StandardError.new('connection lost'))
  raise got.inspect unless got[:reported] == 'failed'
end

check(failures, 'unsafe ignores tag') do
  got = Ppcs::CommitOutcome.classify('unsafe', tag: 'ROLLBACK', error: nil)
  raise got.inspect unless got[:reported] == 'committed'
end

check(failures, 'unsafe reports a raised commit as rollback') do
  got = Ppcs::CommitOutcome.classify('unsafe', tag: nil, error: StandardError.new('connection lost'))
  raise got.inspect unless got[:reported] == 'rolled_back'
end

check(failures, 'rollback fault does not match rollback to savepoint') do
  raise 'plain rollback' unless Ppcs::ROLLBACK_SQL.match?('ROLLBACK')
  raise 'savepoint' if Ppcs::ROLLBACK_SQL.match?('ROLLBACK TO SAVEPOINT active_record_1')
  raise 'savepoint pattern' unless Ppcs::SAVEPOINT_ROLLBACK_SQL.match?('ROLLBACK TO SAVEPOINT active_record_1')
  raise 'commit' unless Ppcs::COMMIT_SQL.match?('COMMIT')
  raise 'commit and extra' if Ppcs::COMMIT_SQL.match?('COMMIT WORK')
end

if failures.empty?
  puts 'ok'
  exit 0
end
warn failures.join("\n")
exit 1
