// MPCS-01. Duplicate-key violation inside an explicit transaction.
//
// The application catches the statement error and then COMMITs. A second variant also sends
// another insert before COMMIT, to see whether the transaction is still usable. Neither variant
// sends ROLLBACK.

import {
  closeClient,
  createMarkerTable,
  freshMarkerRead,
  independentState,
  recreateSchema,
  request,
  tableEngines,
  useSchema,
  visibleMarkers,
} from './lib.mjs'

const SCHEMA = 'mpcs01'

export async function mpcs01(ctx) {
  const schema = await recreateSchema(ctx.root.conn, SCHEMA)
  const subject = await ctx.open('mpcs01-subject')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  await subject.conn.query(`CREATE TABLE uniq_row (
    id INT NOT NULL AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_code (code)
  ) ENGINE=InnoDB`)
  await subject.conn.query(`INSERT INTO uniq_row (code) VALUES ('taken')`)
  const engines = await tableEngines(ctx.observer, schema)

  const caughtThenCommit = await runVariant(ctx, subject, schema, 'caught-then-commit', false)
  await subject.conn.query('DELETE FROM marker')
  const caughtThenContinue = await runVariant(ctx, subject, schema, 'caught-then-another-insert-then-commit', true)

  await closeClient(subject)
  return {
    experiment: 'MPCS-01',
    title: 'Duplicate-key violation caught inside a transaction, then COMMIT',
    schema,
    engines,
    variants: [caughtThenCommit, caughtThenContinue],
  }
}

async function runVariant(ctx, subject, schema, name, insertAfterError) {
  const marker = `${name}-marker`
  const markerAfter = `${name}-after-error`
  const steps = []

  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert-marker', 'INSERT INTO marker (name) VALUES (?)', [marker]))
  steps.push(await capture(ctx, subject, schema, 'duplicate-key', `INSERT INTO uniq_row (code) VALUES ('taken')`))
  if (insertAfterError) {
    steps.push(await capture(ctx, subject, schema, 'insert-after-error', 'INSERT INTO marker (name) VALUES (?)', [markerAfter]))
  }
  steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
  const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
  return { name, marker, marker_after_error: insertAfterError ? markerAfter : null, steps, fresh_reader: fresh }
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
