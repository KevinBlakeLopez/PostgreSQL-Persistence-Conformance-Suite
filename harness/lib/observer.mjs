// Independent observation: what PostgreSQL itself says happened, read through the runner's own connections.
//
// The adapter reports each transaction's ID from inside it (pg_current_xact_id(), read through the framework's own
// connection). Everything here reads from separate connections, never through the framework:
// - fate(): pg_xact_status() for that ID: 'committed', 'aborted', 'in progress', or null when PostgreSQL no longer
//   knows. Both functions need PostgreSQL 13 or later (docs/methodology.md, "Requirements and limitations").
// - markers() and markerXmins(): which marker rows a new READ COMMITTED connection can see, and the ID of the
//   transaction that inserted each one, so that "committed" means visible to others, and attributable.
// - locks(): the locks a backend holds. A RowExclusiveLock on `item` shows that a write reached the server; a second
//   transactionid lock shows a write inside a savepoint (an assigned subtransaction ID). An AccessShareLock on `item`
//   shows a read of it, and an SIReadLock on `item` or one of its indexes shows that PostgreSQL's predicate locking,
//   which only SERIALIZABLE transactions take part in, covered that read (TX-05). Other sessions cannot see
//   uncommitted rows, but they can see these locks.
// - session(): pg_stat_activity, as a supplementary check of a backend's state, to cross-check the reported ID, and
//   to identify the backend (backend_start) across checkpoints. It never identifies a transaction alone. Its
//   backend_xmin is recorded as a diagnostic only.
import { createHash } from 'node:crypto'

const XID_MOD = 2n ** 32n

/** The low 32 bits of an xid8, as text, for comparison with a 32-bit xid such as xmin or backend_xid. */
export const low32 = (xid8) => (typeof xid8 === 'string' && /^\d+$/.test(xid8) ? String(BigInt(xid8) % XID_MOD) : null)

export class Observer {
  constructor(instance) {
    this.instance = instance
  }

  /** pg_xact_status() for a transaction ID reported as text (xid8). Returns null if the status is unknown. */
  async fate(database, xid) {
    if (typeof xid !== 'string' || !/^\d+$/.test(xid)) return null
    const rows = await this.instance.query(database, 'select pg_xact_status($1::xid8) as status', [xid])
    return rows[0]?.status ?? null
  }

  /** How many rows of `item` have this marker value. A migration's execution count. */
  async markerCount(database, name) {
    const rows = await this.instance.query(database, 'select count(*)::int as n from item where name = $1', [name])
    return rows[0].n
  }

  /**
   * How many rows the framework's history table holds. A missing table is zero: the database has no history yet.
   * `table` is the adapter's declared history table, and it must be a plain identifier.
   */
  async historyCount(database, table) {
    if (!/^[a-z_][a-z0-9_]*$/.test(table ?? '')) throw new Error(`history table is not an identifier: ${JSON.stringify(table)}`)
    const rel = await this.instance.query(database, 'select to_regclass($1) as rel', [table])
    if (!rel[0].rel) return 0
    const rows = await this.instance.query(database, `select count(*)::int as n from ${table}`)
    return rows[0].n
  }

  /**
   * Sessions waiting on advisory lock `key`, other than the runner's own connections. The gate is that lock: a
   * migration that has reached its hold point waits on it, and the runner's own session holds it.
   */
  async gateWaiters(database, key) {
    const runner = this.instance.runnerSessions?.() ?? { pids: [], applicationName: 'ppcs-observer' }
    return this.instance.query(database, `select a.pid, a.application_name, a.state, l.granted
      from pg_locks l join pg_stat_activity a using (pid)
      where l.locktype = 'advisory' and l.classid = 0 and l.objid = $1 and a.datname = current_database()
        and not (a.pid = any($2::int[]) and a.application_name = $3)
      order by a.pid`, [key, runner.pids, runner.applicationName])
  }

  /** Client sessions of one role. The role's application_name is `ppcs-` plus the role. */
  async roleSessions(database, role) {
    return this.instance.query(database, `select pid, state from pg_stat_activity
      where datname = current_database() and backend_type = 'client backend' and application_name = $1
      order by pid`, [`ppcs-${role}`])
  }

  /** Which of the case's markers an independent connection sees: { label: true | false }. */
  async markers(database, markers) {
    const rows = await this.instance.query(database, 'select name from item where name = any($1)', [Object.values(markers)])
    const seen = new Set(rows.map((r) => r.name))
    return Object.fromEntries(Object.entries(markers).map(([label, value]) => [label, seen.has(value)]))
  }

  /**
   * For each visible marker, the ID of the transaction that inserted its row (the row's xmin, 32 bits), or null. It
   * attributes a committed write to the transaction that committed it. A row written inside a savepoint carries the
   * savepoint's subtransaction ID, not the top-level one.
   */
  async markerXmins(database, markers) {
    const rows = await this.instance.query(database, 'select name, xmin::text as xmin from item where name = any($1)', [Object.values(markers)])
    const byName = new Map(rows.map((r) => [r.name, r.xmin]))
    return Object.fromEntries(Object.entries(markers).map(([label, value]) => [label, byName.get(value) ?? null]))
  }

  /**
   * Visible rows of the marker table that are not this case's markers. The table starts empty, so a row here is a write
   * the case did not declare (an adapter writing the wrong value, for example), which would make "marker not visible"
   * mean the wrong thing.
   */
  async strayRows(database, markers) {
    const rows = await this.instance.query(database, 'select name from item where name <> all($1) order by id limit 5', [Object.values(markers)])
    return rows.map((r) => r.name)
  }

  /**
   * The pg_stat_activity row of `pid`, if it is connected to `database`. `xid_matches` compares its backend_xid (32 bits)
   * with the low 32 bits of the xid8 the adapter reported, when both are known.
   */
  async session(database, pid, reportedXid = null) {
    if (!Number.isInteger(pid)) return null
    const rows = await this.instance.query(database, `select pid, state, backend_xid::text as backend_xid, backend_xmin::text as backend_xmin,
      backend_start::text as backend_start, (xact_start is not null or state like 'idle in transaction%') as in_transaction,
      left(query, 80) as query, application_name
      from pg_stat_activity where pid = $1 and datname = current_database()`, [pid])
    const s = rows[0]
    if (!s) return { pid, present: false }
    let xidMatches = null
    if (s.backend_xid != null && low32(reportedXid) != null) xidMatches = low32(reportedXid) === s.backend_xid
    // backend_xmin, the backend's snapshot horizon, is not an isolation-level field: it is kept as a diagnostic.
    return { pid, present: true, state: s.state, in_transaction: s.in_transaction, backend_xid: s.backend_xid, xid_matches: xidMatches,
      backend_xmin: s.backend_xmin, backend_start: s.backend_start, query: s.query, application_name: s.application_name }
  }

  /**
   * The evidence that backend `pid` holds in pg_locks:
   * - `wrote_item`: a RowExclusiveLock on the marker table;
   * - `xids`: the transaction IDs whose transactionid locks it holds (the top-level ID, then one per open
   *   subtransaction that has written);
   * - `read_item`: an AccessShareLock on the marker table, which a read of it takes;
   * - `siread`: its SIReadLocks, each with its target (lock type, relation, page, tuple) and `on_item`, whether that
   *   relation is the marker table or one of its indexes. They are attributed by target, never counted: PostgreSQL can
   *   change their granularity.
   */
  async locks(database, pid) {
    if (!Number.isInteger(pid)) return null
    const rows = await this.instance.query(database, `select locktype, mode, relation::regclass::text as relation, transactionid::text as xid,
      page, tuple, coalesce(relation = 'item'::regclass or relation in (select indexrelid from pg_index where indrelid = 'item'::regclass), false) as on_item
      from pg_locks where pid = $1 and granted`, [pid])
    return {
      wrote_item: rows.some((r) => r.locktype === 'relation' && r.relation === 'item' && r.mode === 'RowExclusiveLock'),
      xids: rows.filter((r) => r.locktype === 'transactionid').map((r) => r.xid).sort((a, b) => Number(a) - Number(b)),
      read_item: rows.some((r) => r.locktype === 'relation' && r.relation === 'item' && r.mode === 'AccessShareLock'),
      siread: rows.filter((r) => r.mode === 'SIReadLock').map((r) => ({ locktype: r.locktype, relation: r.relation, page: r.page, tuple: r.tuple, on_item: r.on_item }))
        .sort((a, b) => `${a.relation}:${a.locktype}:${a.page}:${a.tuple}`.localeCompare(`${b.relation}:${b.locktype}:${b.page}:${b.tuple}`)),
    }
  }

  /** Client sessions connected to `database`, other than the runner's own connections. */
  async sessions(database) {
    // A session is the runner's only if both its PID is one of the runner's own connections and it carries the runner's
    // application_name. An adapter connection that uses that name is still counted, and so is a backend that reuses an
    // old runner PID.
    const runner = this.instance.runnerSessions?.() ?? { pids: [], applicationName: 'ppcs-observer' }
    return this.instance.query(database, `select pid, state, (xact_start is not null or state like 'idle in transaction%') as in_transaction, application_name
      from pg_stat_activity where datname = current_database() and backend_type = 'client backend' and pid <> pg_backend_pid()
      and not (pid = any($1::int[]) and application_name = $2) order by pid`, [runner.pids, runner.applicationName])
  }

  /**
   * A digest of the fixture's tables, columns and constraints. The runner compares it before and after the adapter
   * runs: an adapter that changed the schema (a framework synchronizing its model, for example) is detected.
   */
  async fixtureFingerprint(database) {
    const columns = await this.instance.query(database, `select table_name, column_name, data_type, is_nullable, column_default from information_schema.columns
      where table_schema = 'public' and table_name in ('item', 'uniq') order by table_name, column_name`)
    const constraints = await this.instance.query(database, `select conrelid::regclass::text as rel, conname, pg_get_constraintdef(oid) as def from pg_constraint
      where conrelid in (select oid from pg_class where relname in ('item', 'uniq') and relnamespace = 'public'::regnamespace) order by 1, 2`)
    return createHash('sha256').update(JSON.stringify({ columns, constraints })).digest('hex')
  }

  /** Waits until backend `pid` is no longer connected to `database`. Returns true if it went within `timeoutMs`. */
  async waitGone(database, pid, timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs
    for (;;) {
      const rows = await this.instance.query(database, 'select 1 from pg_stat_activity where pid = $1 and datname = current_database()', [pid])
      if (!rows.length) return true
      if (Date.now() >= deadline) return false
      await new Promise((r) => setTimeout(r, 25))
    }
  }

  /**
   * Waits until no client session other than the runner's is connected to `database`, so that a transaction a closed
   * session left open has ended before its fate is read. Returns the sessions still connected at the deadline.
   */
  async settle(database, timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs
    let left = await this.sessions(database)
    while (left.length > 0 && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 50))
      left = await this.sessions(database)
    }
    return left
  }
}
