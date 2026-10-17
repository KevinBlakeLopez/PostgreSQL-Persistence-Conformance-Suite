// Unit tests for the server profile the runner asserts before anything runs (harness/lib/instance.mjs). No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SERVER_PROFILE, profileProblems } from '../../lib/instance.mjs'

test('server profile: the expected settings pass; any one of them changed stops the run', () => {
  assert.deepEqual(profileProblems({ ...SERVER_PROFILE }), [])
  const { transaction_timeout: _, ...before17 } = SERVER_PROFILE
  assert.deepEqual(profileProblems(before17), [], 'transaction_timeout exists only from PostgreSQL 17')
  const changed = { synchronous_commit: 'off', fsync: 'off', track_activities: 'off', default_transaction_isolation: 'repeatable read', default_transaction_read_only: 'on', statement_timeout: '1000', lock_timeout: '1000', idle_in_transaction_session_timeout: '1000', transaction_timeout: '1000', synchronous_standby_names: 'standby1' }
  for (const [name, value] of Object.entries(changed)) {
    const problems = profileProblems({ ...SERVER_PROFILE, [name]: value })
    assert.equal(problems.length, 1, name)
    assert.match(problems[0], new RegExp(`^${name} is "${value}"`), name)
  }
  const { fsync: __, ...noFsync } = SERVER_PROFILE
  assert.deepEqual(profileProblems(noFsync), ['fsync is missing'])
})

test('sessions: only a session with both a runner PID and the runner\'s name is the runner\'s own', async () => {
  const { Observer } = await import('../../lib/observer.mjs')
  const calls = []
  const instance = { runnerSessions: () => ({ pids: [41, 42], applicationName: 'ppcs-observer' }), query: async (db, text, params) => { calls.push({ text, params }); return [] } }
  await new Observer(instance).sessions('db')
  assert.equal(calls.length, 1)
  assert.match(calls[0].text, /not \(pid = any\(\$1::int\[\]\) and application_name = \$2\)/)
  assert.deepEqual(calls[0].params, [[41, 42], 'ppcs-observer'])
})
