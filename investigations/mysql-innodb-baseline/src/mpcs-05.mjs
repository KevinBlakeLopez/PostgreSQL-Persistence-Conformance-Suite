// MPCS-05. What mysql2 returns for COMMIT and ROLLBACK.
//
// Successful acknowledgment, a server-side rollback that already happened (deadlock is MPCS-02;
// this file repeats only the COMMIT that follows an explicit ROLLBACK), and connection failure
// are separate variants. A lost COMMIT response is not attempted.

import {
  closeClient,
  createMarkerTable,
  describeError,
  freshMarkerRead,
  independentState,
  recreateSchema,
  request,
  sleep,
  useSchema,
  visibleMarkers,
  waitFor,
} from './lib.mjs'

const SCHEMA = 'mpcs05'

export async function mpcs05(ctx) {
  const schema = await recreateSchema(ctx.root.conn, SCHEMA)
  const variants = []
  variants.push(await commandShapes(ctx, schema))
  variants.push(await explicitRollback(ctx, schema))
  variants.push(await killThenCommit(ctx, schema))
  variants.push(await destroyThenCommit(ctx, schema))
  variants.push(await historyAfterDisconnect(ctx, schema))
  return {
    experiment: 'MPCS-05',
    title: 'mysql2 COMMIT and ROLLBACK results, plus connection failure',
    schema,
    lost_response_experiment: 'not run in this phase',
    variants,
  }
}

async function commandShapes(ctx, schema) {
  const subject = await ctx.open('mpcs05-shapes')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'commit-with-no-explicit-transaction', 'COMMIT'))
    steps.push(await warnings(subject))
    steps.push(await capture(ctx, subject, schema, 'rollback-with-no-explicit-transaction', 'ROLLBACK'))
    steps.push(await warnings(subject))
    steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('commit-shape')`))
    steps.push(await capture(ctx, subject, schema, 'select', `SELECT id, name FROM marker WHERE name = 'commit-shape'`))
    steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
    steps.push(await warnings(subject))
    const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
    return {
      name: 'command-shapes',
      steps,
      fresh_reader: fresh,
      connection_errors: subject.connectionErrors,
    }
  } finally {
    await closeClient(subject)
  }
}

async function explicitRollback(ctx, schema) {
  const subject = await ctx.open('mpcs05-rollback')
  await useSchema(subject, schema)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('rolled-back')`))
    steps.push(await capture(ctx, subject, schema, 'rollback', 'ROLLBACK'))
    steps.push(await warnings(subject))
    const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
    return { name: 'explicit-rollback', steps, fresh_reader: fresh, connection_errors: subject.connectionErrors }
  } finally {
    await closeClient(subject)
  }
}

async function killThenCommit(ctx, schema) {
  const subject = await ctx.open('mpcs05-kill')
  await useSchema(subject, schema)
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('killed-before-commit')`))
  const kill = await request(ctx.observer.conn, `KILL ${subject.id}`)
  const gone = await waitFor(async () => {
    const [rows] = await ctx.observer.conn.query(
      'SELECT PROCESSLIST_ID AS id FROM performance_schema.threads WHERE PROCESSLIST_ID = ?',
      [subject.id],
    )
    return rows.length === 0 ? { gone: true } : null
  }, 2000)
  const commit = await request(subject.conn, 'COMMIT')
  const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
  await closeClient(subject)
  return {
    name: 'kill-then-commit',
    note: 'The observer issues KILL, waits up to 2s for the server thread to disappear, then the subject sends COMMIT. This is a connection failure. It is not a discarded COMMIT reply.',
    steps,
    kill,
    server_thread_gone_before_commit: gone,
    commit,
    fresh_reader: fresh,
    connection_errors: subject.connectionErrors,
  }
}

async function destroyThenCommit(ctx, schema) {
  const subject = await ctx.open('mpcs05-destroy')
  await useSchema(subject, schema)
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('destroyed-before-commit')`))
  subject.conn.destroy()
  const commit = await request(subject.conn, 'COMMIT')
  const gone = await waitFor(async () => {
    const [rows] = await ctx.observer.conn.query(
      'SELECT PROCESSLIST_ID AS id FROM performance_schema.threads WHERE PROCESSLIST_ID = ?',
      [subject.id],
    )
    return rows.length === 0 ? { gone: true } : null
  }, 3000)
  const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
  return {
    name: 'client-destroy-then-commit',
    note: 'PromiseConnection.destroy() delegates to Connection.close(), which ends the socket and rejects later commands. COMMIT is attempted after that call. This is a client-side connection failure, not a lost response.',
    steps,
    commit,
    server_thread_gone_after_destroy: gone,
    fresh_reader: fresh,
    connection_errors: subject.connectionErrors,
  }
}

async function historyAfterDisconnect(ctx, schema) {
  const subject = await ctx.open('mpcs05-history')
  await useSchema(subject, schema)
  const threadBefore = await independentState(ctx.observer, subject.id)
  await request(subject.conn, 'START TRANSACTION')
  await request(subject.conn, `INSERT INTO marker (name) VALUES ('history-after-close')`)
  const beforeCommit = await independentState(ctx.observer, subject.id)
  const commit = await request(subject.conn, 'COMMIT')
  const afterCommit = await independentState(ctx.observer, subject.id)
  const threadId = afterCommit.thread?.THREAD_ID ?? beforeCommit.thread?.THREAD_ID ?? null
  await closeClient(subject)
  await sleep(200)
  let historyAfterClose = null
  let historyError = null
  try {
    const [rows] = await ctx.observer.conn.query(
      `SELECT EVENT_ID, STATE, TRX_ID, GTID, ACCESS_MODE, ISOLATION_LEVEL, AUTOCOMMIT
       FROM performance_schema.events_transactions_history WHERE THREAD_ID = ? ORDER BY EVENT_ID DESC LIMIT 4`,
      [threadId],
    )
    historyAfterClose = rows
  } catch (error) {
    historyError = describeError(error)
  }
  const [stillThere] = await ctx.observer.conn.query(
    'SELECT THREAD_ID, PROCESSLIST_ID FROM performance_schema.threads WHERE THREAD_ID = ? OR PROCESSLIST_ID = ?',
    [threadId, subject.id],
  )
  const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
  return {
    name: 'history-after-disconnect',
    note: 'The history read happens after the subject connection has closed. A visible marker in fresh_reader is a later observation, not the COMMIT packet.',
    thread_id: threadId,
    before_commit: beforeCommit,
    commit,
    after_commit_before_close: afterCommit,
    thread_row_after_close: stillThere,
    history_after_close: historyAfterClose,
    history_error: historyError,
    fresh_reader: fresh,
    visible_to_long_lived_observer: await visibleMarkers(ctx.observer, schema),
  }
}

async function capture(ctx, subject, schema, name, sql, params) {
  const sent = await request(subject.conn, sql, params)
  return {
    name,
    ...sent,
    independent_observation: await independentState(ctx.observer, subject.id),
    visible_markers: await visibleMarkers(ctx.observer, schema),
  }
}

async function warnings(subject) {
  const sent = await request(subject.conn, 'SHOW WARNINGS')
  return { name: 'show-warnings', note: 'A later statement on the same connection. Not part of the previous OK packet.', ...sent }
}
