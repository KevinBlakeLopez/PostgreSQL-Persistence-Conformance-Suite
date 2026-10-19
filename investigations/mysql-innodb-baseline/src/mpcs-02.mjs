// MPCS-02. Two-connection InnoDB deadlock.
//
// T1 locks row 1, T2 locks row 2, then each updates the other's row. The victim is whichever
// session mysql2 rejects. The victim then issues a statement on a table the survivor does not
// lock, and then COMMIT. Those two calls are how the experiment sees whether the victim
// transaction was already gone.

import {
  closeClient,
  createMarkerTable,
  freshMarkerRead,
  independentState,
  latestDeadlock,
  lockWaitsFor,
  recreateSchema,
  request,
  sleep,
  tableEngines,
  useSchema,
  visibleMarkers,
  waitFor,
} from './lib.mjs'

const SCHEMA = 'mpcs02'

export async function mpcs02(ctx) {
  const schema = await recreateSchema(ctx.root.conn, SCHEMA)
  const setup = await ctx.open('mpcs02-setup')
  await useSchema(setup, schema)
  await createMarkerTable(setup)
  await setup.conn.query('CREATE TABLE dl (id INT NOT NULL PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB')
  await setup.conn.query('INSERT INTO dl (id, v) VALUES (1, 0), (2, 0)')
  const engines = await tableEngines(ctx.observer, schema)
  await closeClient(setup)

  const repetitions = []
  for (let repetition = 1; repetition <= 3; repetition++) {
    repetitions.push(await oneDeadlock(ctx, schema, repetition))
  }
  return {
    experiment: 'MPCS-02',
    title: 'Deterministic two-connection InnoDB deadlock',
    schema,
    engines,
    repetitions,
  }
}

async function oneDeadlock(ctx, schema, repetition) {
  const t1 = await ctx.open('mpcs02-t1')
  const t2 = await ctx.open('mpcs02-t2')
  await useSchema(t1, schema)
  await useSchema(t2, schema)
  await ctx.root.conn.query(`DELETE FROM \`${schema}\`.marker`)
  await ctx.root.conn.query(`UPDATE \`${schema}\`.dl SET v = 0`)

  try {
    const start1 = await request(t1.conn, 'START TRANSACTION')
    const start2 = await request(t2.conn, 'START TRANSACTION')
    const lock1 = await request(t1.conn, 'UPDATE dl SET v = v + 1 WHERE id = 1')
    const lock2 = await request(t2.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
    const beforeCross = {
      t1: await independentState(ctx.observer, t1.id),
      t2: await independentState(ctx.observer, t2.id),
    }

    const pending1 = request(t1.conn, 'UPDATE dl SET v = v + 1 WHERE id = 2')
    const waited = await waitFor(async () => {
      const rows = await lockWaitsFor(ctx.observer, t1.id)
      if (rows.length) return { data_lock_waits: rows }
      const [trx] = await ctx.observer.conn.query(
        `SELECT trx_id, trx_state, trx_query FROM information_schema.innodb_trx WHERE trx_mysql_thread_id = ? AND trx_state = 'LOCK WAIT'`,
        [t1.id],
      )
      return trx.length ? { innodb_trx: trx } : null
    }, 5000)
    const pending2 = request(t2.conn, 'UPDATE dl SET v = v + 1 WHERE id = 1')
    const [cross1, cross2] = await Promise.all([pending1, pending2])
    await sleep(100)
    const after = {
      t1: await independentState(ctx.observer, t1.id),
      t2: await independentState(ctx.observer, t2.id),
      visible_dl: await dlRows(ctx, schema),
      deadlock_status: await latestDeadlock(ctx.observer),
    }

    const victim = cross1.driver.outcome === 'rejected' ? t1 : cross2.driver.outcome === 'rejected' ? t2 : null
    const survivor = victim === t1 ? t2 : victim === t2 ? t1 : null
    let continuation = null
    if (victim) {
      const marker = `rep${repetition}-after-deadlock`
      const session = await request(victim.conn, 'SELECT @@autocommit AS autocommit, @@transaction_isolation AS transaction_isolation, CONNECTION_ID() AS connection_id')
      const afterSession = await independentState(ctx.observer, victim.id)
      const insert = await request(victim.conn, 'INSERT INTO marker (name) VALUES (?)', [marker])
      const afterInsert = {
        observation: await independentState(ctx.observer, victim.id),
        visible_markers: await visibleMarkers(ctx.observer, schema),
      }
      const commit = await request(victim.conn, 'COMMIT')
      const afterCommit = {
        observation: await independentState(ctx.observer, victim.id),
        visible_markers: await visibleMarkers(ctx.observer, schema),
      }
      continuation = {
        victim_role: victim.role,
        marker,
        session_query: session,
        after_session_query: afterSession,
        insert,
        after_insert: afterInsert,
        commit,
        after_commit: afterCommit,
      }
    }
    let survivorCommit = null
    if (survivor) {
      survivorCommit = await request(survivor.conn, 'COMMIT')
    }
    const fresh = await freshMarkerRead(ctx.instance, ctx.endpoint, schema)
    const finalDl = await dlRows(ctx, schema)
    return {
      repetition,
      sessions: {
        t1: { connection_id: t1.id, connection_errors: t1.connectionErrors },
        t2: { connection_id: t2.id, connection_errors: t2.connectionErrors },
      },
      start1,
      start2,
      lock1,
      lock2,
      before_cross: beforeCross,
      t1_entered_lock_wait: waited,
      cross1,
      cross2,
      after_deadlock: after,
      victim_connection_id: victim?.id ?? null,
      survivor_connection_id: survivor?.id ?? null,
      continuation,
      survivor_commit: survivorCommit,
      fresh_reader: fresh,
      dl_after_survivor_commit: finalDl,
    }
  } finally {
    await closeClient(t1)
    await closeClient(t2)
  }
}

async function dlRows(ctx, schema) {
  const [rows] = await ctx.observer.conn.query(`SELECT id, v FROM \`${schema}\`.dl ORDER BY id`)
  return rows.map((row) => ({ id: Number(row.id), v: Number(row.v) }))
}
