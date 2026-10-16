// Independent observation: what PostgreSQL itself says happened, read through the runner's own connections.
//
// The adapter reports each transaction's ID from inside it (pg_current_xact_id(), read through the framework's own
// connection). Everything here reads from separate connections, never through the framework:
// - fate(): pg_xact_status() for that ID: 'committed', 'aborted', 'in progress', or null when PostgreSQL no longer
//   knows. Both functions need PostgreSQL 13 or later (docs/methodology.md, "Requirements and limitations").
// - markers(): which marker rows a new READ COMMITTED connection can see, so "committed" means visible to others.
// - session(): pg_stat_activity, used only as a supplementary check of a backend's state (for example that it is
//   "idle in transaction (aborted)"), and to cross-check the reported ID. It never identifies the transaction alone.

const XID_MOD = 2n ** 32n

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

  /** Which of the case's markers an independent connection sees: { label: true | false }. */
  async markers(database, markers) {
    const rows = await this.instance.query(database, 'select name from item where name = any($1)', [Object.values(markers)])
    const seen = new Set(rows.map((r) => r.name))
    return Object.fromEntries(Object.entries(markers).map(([label, value]) => [label, seen.has(value)]))
  }

  /**
   * For each visible marker, the ID of the transaction that inserted its row (the row's xmin, 32 bits), or null. It
   * attributes a committed write to the transaction that committed it.
   */
  async markerXmins(database, markers) {
    const rows = await this.instance.query(database, 'select name, xmin::text as xmin from item where name = any($1)', [Object.values(markers)])
    const byName = new Map(rows.map((r) => [r.name, r.xmin]))
    return Object.fromEntries(Object.entries(markers).map(([label, value]) => [label, byName.get(value) ?? null]))
  }

  /**
   * The pg_stat_activity row of `pid`, if it is connected to `database`. `xidMatches` compares its backend_xid (32 bits)
   * with the low 32 bits of the xid8 the adapter reported, when both are known.
   */
  async session(database, pid, reportedXid = null) {
    if (!Number.isInteger(pid)) return null
    const rows = await this.instance.query(database, `select pid, state, backend_xid::text as backend_xid, (xact_start is not null or state like 'idle in transaction%') as in_transaction,
      application_name from pg_stat_activity where pid = $1 and datname = current_database()`, [pid])
    const s = rows[0]
    if (!s) return { pid, present: false }
    let xidMatches = null
    if (s.backend_xid != null && typeof reportedXid === 'string' && /^\d+$/.test(reportedXid)) {
      xidMatches = BigInt(reportedXid) % XID_MOD === BigInt(s.backend_xid)
    }
    return { pid, present: true, state: s.state, in_transaction: s.in_transaction, backend_xid: s.backend_xid, xid_matches: xidMatches, application_name: s.application_name }
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

  /** Client sessions connected to `database`, other than the runner's own. */
  async sessions(database) {
    return this.instance.query(database, `select pid, state, (xact_start is not null or state like 'idle in transaction%') as in_transaction, application_name
      from pg_stat_activity where datname = current_database() and backend_type = 'client backend' and pid <> pg_backend_pid() order by pid`)
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
