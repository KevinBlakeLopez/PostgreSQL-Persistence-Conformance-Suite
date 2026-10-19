// MPCS-03. InnoDB lock-wait timeout.
//
// One session holds a row lock. Another session, inside a transaction that has already inserted
// a marker, waits for that row. The wait uses either the server's innodb_lock_wait_timeout or a
// shorter session value. innodb_rollback_on_timeout is whatever the connected server was started
// with; this file does not change it.

import {
  closeClient,
  createMarkerTable,
  freshMarkerRead,
  independentState,
  lockWaitsFor,
  recreateSchema,
  request,
  tableEngines,
  useSchema,
  visibleMarkers,
  waitFor,
} from './lib.mjs'

export async function mpcs03(ctx, { schema, variant, sessionLockWaitTimeout }) {
  const name = await recreateSchema(ctx.root.conn, schema)
  const holder = await ctx.open('mpcs03-holder')
  const waiter = await ctx.open('mpcs03-waiter')
  await useSchema(holder, name)
  await useSchema(waiter, name)
  await createMarkerTable(holder)
  await holder.conn.query('CREATE TABLE lk (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB')
  await holder.conn.query('INSERT INTO lk (id, v) VALUES (1, 0)')
  const engines = await tableEngines(ctx.observer, name)
  const [settings] = await ctx.root.conn.query(
    `SELECT @@global.innodb_rollback_on_timeout AS global_rollback_on_timeout,
            @@global.innodb_lock_wait_timeout AS global_lock_wait_timeout,
            @@global.lock_wait_timeout AS global_metadata_lock_wait_timeout`,
  )

  let sessionSetting = null
  if (sessionLockWaitTimeout != null) {
    const seconds = Number(sessionLockWaitTimeout)
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 50) throw new Error(`refusing lock wait timeout ${sessionLockWaitTimeout}`)
    sessionSetting = await request(waiter.conn, `SET SESSION innodb_lock_wait_timeout = ${seconds}`)
  }
  const [waiterSettings] = await waiter.conn.query(
    'SELECT @@session.innodb_lock_wait_timeout AS innodb_lock_wait_timeout, @@session.autocommit AS autocommit',
  )

  try {
    const holderStart = await request(holder.conn, 'START TRANSACTION')
    const holderLock = await request(holder.conn, 'UPDATE lk SET v = 1 WHERE id = 1')
    const waiterStart = await request(waiter.conn, 'START TRANSACTION')
    const marker = `${variant}-before-timeout`
    const markerAfter = `${variant}-after-timeout`
    const waiterInsert = await request(waiter.conn, 'INSERT INTO marker (name) VALUES (?)', [marker])
    const beforeWait = {
      waiter: await independentState(ctx.observer, waiter.id),
      holder: await independentState(ctx.observer, holder.id),
      visible_markers: await visibleMarkers(ctx.observer, name),
    }

    const pending = request(waiter.conn, 'UPDATE lk SET v = 2 WHERE id = 1')
    const sawWait = await waitFor(async () => {
      const rows = await lockWaitsFor(ctx.observer, waiter.id)
      if (rows.length) return { data_lock_waits: rows }
      const [trx] = await ctx.observer.conn.query(
        `SELECT trx_id, trx_state, trx_query FROM information_schema.innodb_trx WHERE trx_mysql_thread_id = ? AND trx_state = 'LOCK WAIT'`,
        [waiter.id],
      )
      return trx.length ? { innodb_trx: trx } : null
    }, 5000)
    const duringWait = {
      waiter: await independentState(ctx.observer, waiter.id),
      visible_markers: await visibleMarkers(ctx.observer, name),
    }
    const timedOut = await pending
    const afterTimeout = {
      waiter: await independentState(ctx.observer, waiter.id),
      visible_markers: await visibleMarkers(ctx.observer, name),
      lk: await lkRows(ctx, name),
    }
    const sessionAfter = await request(
      waiter.conn,
      'SELECT @@autocommit AS autocommit, @@session.innodb_lock_wait_timeout AS innodb_lock_wait_timeout, CONNECTION_ID() AS connection_id',
    )
    const insertAfter = await request(waiter.conn, 'INSERT INTO marker (name) VALUES (?)', [markerAfter])
    const afterInsert = {
      waiter: await independentState(ctx.observer, waiter.id),
      visible_markers: await visibleMarkers(ctx.observer, name),
    }
    const commit = await request(waiter.conn, 'COMMIT')
    const afterCommit = {
      waiter: await independentState(ctx.observer, waiter.id),
      visible_markers: await visibleMarkers(ctx.observer, name),
      lk: await lkRows(ctx, name),
    }
    const holderRollback = await request(holder.conn, 'ROLLBACK')
    const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, name)
    const lkAfterHolderRollback = await lkRows(ctx, name)

    return {
      experiment: 'MPCS-03',
      variant,
      schema: name,
      engines,
      server_settings: settings[0],
      session_lock_wait_assignment: sessionSetting,
      waiter_settings_before_transaction: waiterSettings[0],
      sessions: {
        holder: { connection_id: holder.id, connection_errors: holder.connectionErrors },
        waiter: { connection_id: waiter.id, connection_errors: waiter.connectionErrors },
      },
      holder_start: holderStart,
      holder_lock: holderLock,
      waiter_start: waiterStart,
      waiter_insert: waiterInsert,
      before_wait: beforeWait,
      lock_wait_observed: sawWait,
      during_wait: duringWait,
      timed_out_statement: timedOut,
      after_timeout: afterTimeout,
      session_after_timeout: sessionAfter,
      insert_after_timeout: insertAfter,
      after_insert: afterInsert,
      waiter_commit: commit,
      after_commit: afterCommit,
      holder_rollback: holderRollback,
      fresh_reader: fresh,
      lk_after_holder_rollback: lkAfterHolderRollback,
    }
  } finally {
    await closeClient(holder)
    await closeClient(waiter)
  }
}

async function lkRows(ctx, schema) {
  const [rows] = await ctx.observer.conn.query(`SELECT id, v FROM \`${schema}\`.lk ORDER BY id`)
  return rows.map((row) => ({ id: Number(row.id), v: Number(row.v) }))
}
