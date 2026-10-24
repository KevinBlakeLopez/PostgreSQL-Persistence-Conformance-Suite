// MG-02 and MG-03 for the control adapter. `correct` takes a transaction-scoped advisory lock on the migrating
// connection before it looks at history, so a second runner waits outside the migration. `unsafe` takes no lock, so
// both runners can be inside the migration at once. The SQL gate is the runner's lock, which the migration waits on
// after inserting its marker; it is not the control's coordination lock.
//
// History storage. The harness creates ppcs_history for every migration case except MG-02.first-deployment, whose
// database starts with none. `correct` creates the table inside its migration transaction, after taking its lock.
// `unsafe` creates it outside the migration and, when a concurrent creation fails with a unique violation, carries
// on as if the table had existed: the mistake MG-02.first-deployment looks for.
import pg from 'pg'
import { errInfo } from '../node-kit/util.mjs'

const FRAMEWORK_LOCK = 77002001
const CREATE_HISTORY = 'create table if not exists ppcs_history (name text not null)'
const CONTRACT = {
  correct: 'The correct control runs a migration in one transaction. It takes a transaction-scoped advisory lock, then creates its history table if it is missing, before it reads history, applies the migration only when history has no entry, and commits the marker and the history entry together. A reversal deletes the marker and the history entry, refuses a migration that has no reversal, and rolls back a reversal that raises.',
  unsafe: 'The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.',
}

const clientOf = (connection) => {
  const c = new pg.Client(connection)
  c.on('error', () => {})
  return c
}

async function withClient(connection, run) {
  const c = clientOf(connection)
  await c.connect()
  try { return await run(c) } finally { await c.end().catch(() => {}) }
}

/** An idle second session, opened first so its backend PID sorts first. idle_session_timeout can end it. */
async function spareSession(connection) {
  const c = clientOf(connection)
  await c.connect()
  await c.query('select 1')
  return c
}

async function apply(connection, { mode, marker, migrationId, gate, hold }) {
  const contract = CONTRACT[mode]
  const spare = mode === 'correct' ? await spareSession(connection) : null
  try {
    return await withClient(connection, async (c) => {
      if (mode === 'unsafe') {
        try {
          await c.query(CREATE_HISTORY)
        } catch (e) {
          if (e.code !== '23505' && e.code !== '42P07') return { reported: 'failed', exit_code: 1, basis: 'creating the history table raised', contract, api_error: errInfo(e) }
        }
      }
      await c.query('BEGIN')
      try {
        if (mode === 'correct') await c.query('select pg_advisory_xact_lock($1)', [FRAMEWORK_LOCK])
        if (mode === 'correct') await c.query(CREATE_HISTORY)
        const existing = await c.query('select 1 from ppcs_history where name = $1', [migrationId])
        if (existing.rowCount) {
          await c.query('COMMIT')
          return { reported: 'nothing_to_do', exit_code: 0, basis: 'history already held an entry, so the control applied nothing', contract }
        }
        await c.query('insert into item (name) values ($1)', [marker])
        if (hold) await c.query('select pg_advisory_xact_lock($1)', [gate])
        await c.query('insert into ppcs_history (name) values ($1)', [migrationId])
        await c.query('COMMIT')
        return { reported: 'applied', exit_code: 0, basis: 'the control committed the marker and a history entry', contract }
      } catch (e) {
        await c.query('ROLLBACK').catch(() => {})
        return { reported: 'failed', exit_code: 1, basis: 'the migration raised', contract, api_error: errInfo(e) }
      }
    })
  } finally {
    await spare?.end().catch(() => {})
  }
}

async function revert(connection, { mode, marker, migrationId, reversal }) {
  const contract = CONTRACT[mode]
  if (mode === 'unsafe') {
    return withClient(connection, async (c) => {
      await c.query('delete from ppcs_history where name = $1', [migrationId])
      return { reported: 'reverted', exit_code: 0, basis: 'the unsafe control deleted the history entry and reported a revert', contract }
    })
  }
  if (reversal === 'none') {
    return { reported: 'refused', exit_code: 1, basis: 'the migration has no reversal, so the control refused', contract, api_error: { class: 'Error', code: null, message: 'the migration has no reversal' } }
  }
  return withClient(connection, async (c) => {
    await c.query('BEGIN')
    try {
      await c.query('delete from item where name = $1', [marker])
      await c.query('insert into ppcs_undo (name) values ($1)', [marker])
      if (reversal === 'partial-then-error') throw new Error('the reversal failed on purpose after deleting the marker')
      await c.query('delete from ppcs_history where name = $1', [migrationId])
      await c.query('COMMIT')
      return { reported: 'reverted', exit_code: 0, basis: 'the control committed the reversal', contract }
    } catch (e) {
      await c.query('ROLLBACK').catch(() => {})
      return { reported: 'failed', exit_code: 1, basis: 'the reversal raised, and the control rolled it back', contract, api_error: errInfo(e) }
    }
  })
}

export const migrationCases = {
  'MG-02.held': run,
  'MG-02.first-deployment': run,
  'MG-02.session-loss': run,
  'MG-02.idle-session-timeout': run,
  'MG-03.valid-reversal': run,
  'MG-03.no-reversal': run,
  'MG-03.failing-reversal': run,
}

async function run(ctx, { markers, mode, migration }) {
  const marker = markers.m1
  const op = migration?.operation
  if (op === 'revert') return revert(ctx.connection, { mode, marker, migrationId: migration.migrationId, reversal: migration.reversal })
  return apply(ctx.connection, { mode, marker, migrationId: migration.migrationId, gate: migration.gate, hold: migration.hold === true })
}
