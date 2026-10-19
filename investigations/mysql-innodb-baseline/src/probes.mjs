// Supplementary probes. These are not MPCS cases. They exist so the portability notes for
// TX-03, TX-05, MG-02, and MG-03 rest on a run rather than on the MySQL manual alone.

import {
  closeClient,
  createMarkerTable,
  freshMarkerRead,
  independentState,
  recreateSchema,
  request,
  useSchema,
  visibleMarkers,
} from './lib.mjs'

export async function probes(ctx) {
  const results = []
  results.push(await implicitCommitOnStart(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_start')))
  results.push(await ddlImplicitCommit(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_ddl')))
  results.push(await isolationLocks(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_iso')))
  results.push(await namedLockSurvivesRollback(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_lock')))
  results.push(await sessionIsolation(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_session_iso')))
  results.push(await releasedSavepointThenOuterRollback(ctx, await recreateSchema(ctx.root.conn, 'mpcs_probe_outer_rollback')))
  return { experiment: 'probes', results }
}

async function implicitCommitOnStart(ctx, schema) {
  const subject = await ctx.open('probe-implicit-start')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'start-1', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert-doomed', `INSERT INTO marker (name) VALUES ('implicit-doomed')`))
    steps.push(await capture(ctx, subject, schema, 'start-2', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert-next', `INSERT INTO marker (name) VALUES ('implicit-next')`))
    steps.push(await capture(ctx, subject, schema, 'rollback', 'ROLLBACK'))
    return {
      name: 'start-transaction-while-a-transaction-is-open',
      steps,
      fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema),
    }
  } finally {
    await closeClient(subject)
  }
}

async function ddlImplicitCommit(ctx, schema) {
  const subject = await ctx.open('probe-ddl')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('ddl-marker')`))
    steps.push(await capture(ctx, subject, schema, 'create-table', 'CREATE TABLE ddl_side (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB'))
    steps.push(await capture(ctx, subject, schema, 'rollback', 'ROLLBACK'))
    const [tables] = await ctx.observer.conn.query(
      `SELECT TABLE_NAME AS table_name, ENGINE AS engine FROM information_schema.tables
       WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME`,
      [schema],
    )
    return {
      name: 'ddl-inside-a-transaction',
      steps,
      tables_after_rollback: tables,
      fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema),
    }
  } finally {
    await closeClient(subject)
  }
}

async function isolationLocks(ctx, schema) {
  const setup = await ctx.open('probe-iso-setup')
  await useSchema(setup, schema)
  await createMarkerTable(setup)
  await closeClient(setup)
  const levels = ['READ UNCOMMITTED', 'READ COMMITTED', 'REPEATABLE READ', 'SERIALIZABLE']
  const runs = []
  for (const level of levels) {
    const subject = await ctx.open(`probe-iso-${level.replaceAll(' ', '-').toLowerCase()}`)
    await useSchema(subject, schema)
    const marker = `iso-${level.toLowerCase().replaceAll(' ', '-')}`
    try {
      await ctx.root.conn.query(`DELETE FROM \`${schema}\`.marker`)
      const setLevel = await request(subject.conn, `SET TRANSACTION ISOLATION LEVEL ${level}`)
      const start = await request(subject.conn, 'START TRANSACTION')
      const insert = await request(subject.conn, 'INSERT INTO marker (name) VALUES (?)', [marker])
      const read = await request(subject.conn, 'SELECT id, name FROM marker WHERE name = ?', [marker])
      const reported = await request(subject.conn, 'SELECT @@transaction_isolation AS transaction_isolation')
      const observation = await independentState(ctx.observer, subject.id)
      const commit = await request(subject.conn, 'COMMIT')
      runs.push({
        requested_level: level,
        set_transaction: setLevel,
        start,
        insert,
        read,
        reported_by_same_connection: reported,
        independent_observation: observation,
        commit,
      })
    } finally {
      await closeClient(subject)
    }
  }

  const inside = await ctx.open('probe-iso-inside')
  await useSchema(inside, schema)
  let setInside = null
  try {
    await request(inside.conn, 'START TRANSACTION')
    setInside = await request(inside.conn, 'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    const reported = await request(inside.conn, 'SELECT @@transaction_isolation AS transaction_isolation')
    await request(inside.conn, 'ROLLBACK')
    setInside = { set_inside_transaction: setInside, reported }
  } finally {
    await closeClient(inside)
  }
  return { name: 'isolation-and-data-locks', runs, set_transaction_while_already_open: setInside }
}

async function namedLockSurvivesRollback(ctx, schema) {
  const holder = await ctx.open('probe-get-lock')
  const other = await ctx.open('probe-get-lock-other')
  await useSchema(holder, schema)
  await createMarkerTable(holder)
  try {
    const steps = []
    steps.push(await request(holder.conn, `SELECT GET_LOCK('mpcs_probe_lock', 2) AS got`))
    steps.push(await request(holder.conn, 'START TRANSACTION'))
    steps.push(await request(holder.conn, `INSERT INTO marker (name) VALUES ('lock-marker')`))
    const otherWhileHeld = await request(other.conn, `SELECT GET_LOCK('mpcs_probe_lock', 1) AS got`)
    const rollback = await request(holder.conn, 'ROLLBACK')
    const otherAfterRollback = await request(other.conn, `SELECT GET_LOCK('mpcs_probe_lock', 1) AS got`)
    const release = await request(holder.conn, `SELECT RELEASE_LOCK('mpcs_probe_lock') AS released`)
    const otherAfterRelease = await request(other.conn, `SELECT GET_LOCK('mpcs_probe_lock', 1) AS got`)
    await request(other.conn, `SELECT RELEASE_LOCK('mpcs_probe_lock')`)
    return {
      name: 'get-lock-and-rollback',
      holder_steps: steps,
      rollback,
      other_while_held: otherWhileHeld,
      other_after_rollback: otherAfterRollback,
      release,
      other_after_release: otherAfterRelease,
      marker_after_rollback: await visibleMarkers(ctx.observer, schema),
    }
  } finally {
    await closeClient(holder)
    await closeClient(other)
  }
}

async function releasedSavepointThenOuterRollback(ctx, schema) {
  const subject = await ctx.open('probe-outer-rollback')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert-outer', `INSERT INTO marker (name) VALUES ('outer-rollback-outer')`))
    steps.push(await capture(ctx, subject, schema, 'savepoint', 'SAVEPOINT sp_done'))
    steps.push(await capture(ctx, subject, schema, 'insert-inner', `INSERT INTO marker (name) VALUES ('outer-rollback-inner')`))
    steps.push(await capture(ctx, subject, schema, 'release', 'RELEASE SAVEPOINT sp_done'))
    steps.push(await capture(ctx, subject, schema, 'rollback', 'ROLLBACK'))
    return {
      name: 'released-savepoint-then-outer-rollback',
      steps,
      fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema),
    }
  } finally {
    await closeClient(subject)
  }
}

async function sessionIsolation(ctx, schema) {
  const subject = await ctx.open('probe-session-iso')
  await useSchema(subject, schema)
  await createMarkerTable(subject)
  try {
    const steps = []
    steps.push(await capture(ctx, subject, schema, 'set-session', `SET SESSION transaction_isolation = 'SERIALIZABLE'`))
    steps.push(await capture(ctx, subject, schema, 'variable-before-start', 'SELECT @@transaction_isolation AS transaction_isolation'))
    steps.push(await capture(ctx, subject, schema, 'start', 'START TRANSACTION'))
    steps.push(await capture(ctx, subject, schema, 'insert', `INSERT INTO marker (name) VALUES ('session-serializable')`))
    steps.push(await capture(ctx, subject, schema, 'read', `SELECT id, name FROM marker WHERE name = 'session-serializable'`))
    steps.push(await capture(ctx, subject, schema, 'variable-inside', 'SELECT @@transaction_isolation AS transaction_isolation'))
    steps.push(await capture(ctx, subject, schema, 'commit', 'COMMIT'))
    return { name: 'set-session-transaction-isolation', steps, fresh_reader: await freshMarkerRead(ctx.instance, ctx.endpoint, schema) }
  } finally {
    await closeClient(subject)
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
