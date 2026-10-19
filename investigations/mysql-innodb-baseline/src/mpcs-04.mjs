// MPCS-04. Savepoints.
//
// Ordinary ROLLBACK TO and RELEASE run in their own transactions. A missing savepoint is a
// separate transaction: the experiment records the driver error, then sends another insert and
// COMMIT without an intervening ROLLBACK, to see whether that transaction is still usable.

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

const SCHEMA = 'mpcs04'

export async function mpcs04(ctx) {
  const schema = await recreateSchema(ctx.root.conn, SCHEMA)
  const subject = await ctx.open('mpcs04-subject')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  const engines = await tableEngines(ctx.observer, schema)
  try {
    const variants = [
      await rollbackTo(ctx, subject, schema),
      await release(ctx, subject, schema),
      await missingRollback(ctx, subject, schema),
      await missingRelease(ctx, subject, schema),
    ]
    return { experiment: 'MPCS-04', title: 'Savepoint create, rollback, release, and a missing savepoint', schema, engines, variants }
  } finally {
    await closeClient(subject)
  }
}

async function rollbackTo(ctx, subject, schema) {
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert-base', `INSERT INTO marker (name) VALUES ('rollback-base')`))
  steps.push(await capture(ctx, subject, schema, 'savepoint', 'SAVEPOINT sp1'))
  steps.push(await capture(ctx, subject, schema, 'insert-inside', `INSERT INTO marker (name) VALUES ('rollback-inside')`))
  const ownReadBefore = await request(subject.conn, 'SELECT id, name FROM marker ORDER BY id')
  steps.push({ name: 'same-connection-read-before-rollback', ...ownReadBefore, note: 'This read uses the transaction connection. It is not an independent observation.' })
  steps.push(await capture(ctx, subject, schema, 'rollback-to', 'ROLLBACK TO SAVEPOINT sp1'))
  const ownReadAfter = await request(subject.conn, 'SELECT id, name FROM marker ORDER BY id')
  steps.push({ name: 'same-connection-read-after-rollback', ...ownReadAfter, note: 'This read uses the transaction connection. It is not an independent observation.' })
  steps.push(await capture(ctx, subject, schema, 'insert-after', `INSERT INTO marker (name) VALUES ('rollback-after')`))
  steps.push(await capture(ctx, subject, schema, 'release', 'RELEASE SAVEPOINT sp1'))
  steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
  return { name: 'rollback-to-savepoint', steps, fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema) }
}

async function release(ctx, subject, schema) {
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert-base', `INSERT INTO marker (name) VALUES ('release-base')`))
  steps.push(await capture(ctx, subject, schema, 'savepoint', 'SAVEPOINT sp2'))
  steps.push(await capture(ctx, subject, schema, 'insert-inside', `INSERT INTO marker (name) VALUES ('release-inside')`))
  steps.push(await capture(ctx, subject, schema, 'release', 'RELEASE SAVEPOINT sp2'))
  steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
  return { name: 'release-savepoint', steps, fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema) }
}

async function missingRollback(ctx, subject, schema) {
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert-outer', `INSERT INTO marker (name) VALUES ('missing-outer')`))
  steps.push(await capture(ctx, subject, schema, 'savepoint', 'SAVEPOINT sp_real'))
  steps.push(await capture(ctx, subject, schema, 'insert-after-real', `INSERT INTO marker (name) VALUES ('missing-after-real')`))
  steps.push(await capture(ctx, subject, schema, 'rollback-to-missing', 'ROLLBACK TO SAVEPOINT does_not_exist'))
  steps.push(await capture(ctx, subject, schema, 'insert-after-error', `INSERT INTO marker (name) VALUES ('missing-after-error')`))
  steps.push(await capture(ctx, subject, schema, 'rollback-to-real', 'ROLLBACK TO SAVEPOINT sp_real'))
  steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
  return { name: 'rollback-to-missing-savepoint', steps, fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema) }
}

async function missingRelease(ctx, subject, schema) {
  const steps = []
  steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
  steps.push(await capture(ctx, subject, schema, 'insert-outer', `INSERT INTO marker (name) VALUES ('release-missing-outer')`))
  steps.push(await capture(ctx, subject, schema, 'release-missing', 'RELEASE SAVEPOINT does_not_exist'))
  steps.push(await capture(ctx, subject, schema, 'insert-after-error', `INSERT INTO marker (name) VALUES ('release-missing-after-error')`))
  steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
  return { name: 'release-missing-savepoint', steps, fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema) }
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
