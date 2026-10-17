// The disposable PostgreSQL instance, and the runner's own connections to it.
//
// The safety model comes from the reused experiment suites (docs/provenance.md):
// - Nothing is sent to a server until verify() has read its cluster_name and matched it against the random token that
//   scripts/pg-up.sh wrote to .ppcs-instance.json (or PPCS_INSTANCE_TOKEN, for a server started some other way).
// - The runner drops only databases it created in this process, and terminates sessions only inside those databases.
import { existsSync, readFileSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import pg from 'pg'

const INSTANCE_FILE = new URL('../../.ppcs-instance.json', import.meta.url)
export const OBSERVER_APP = 'ppcs-observer'

export class SafetyError extends Error {}

/**
 * The server settings every case assumes. A durable, synchronous commit with no replication wait; READ COMMITTED;
 * activity tracking (the observer reads pg_stat_activity); and no server-side timeout that could end a session or a
 * statement on its own, which would change the outcome a case observes. transaction_timeout exists from PostgreSQL 17.
 */
export const SERVER_PROFILE = {
  synchronous_commit: 'on',
  fsync: 'on',
  track_activities: 'on',
  default_transaction_isolation: 'read committed',
  default_transaction_read_only: 'off',
  statement_timeout: '0',
  lock_timeout: '0',
  idle_in_transaction_session_timeout: '0',
  transaction_timeout: '0',
  synchronous_standby_names: '',
}
const OPTIONAL_SETTINGS = new Set(['transaction_timeout'])

/** The differences between `settings` (name -> pg_settings.setting) and SERVER_PROFILE. */
export function profileProblems(settings) {
  const problems = []
  for (const [name, expected] of Object.entries(SERVER_PROFILE)) {
    if (!(name in settings)) { if (!OPTIONAL_SETTINGS.has(name)) problems.push(`${name} is missing`); continue }
    if (settings[name] !== expected) problems.push(`${name} is "${settings[name]}", expected "${expected}"`)
  }
  return problems
}

/** Connection settings for the disposable instance: environment variables first, then .ppcs-instance.json. */
export function loadSettings(env = process.env) {
  const file = existsSync(INSTANCE_FILE) ? JSON.parse(readFileSync(INSTANCE_FILE, 'utf8')) : {}
  const settings = {
    token: env.PPCS_INSTANCE_TOKEN ?? file.token,
    host: env.PPCS_PGHOST ?? file.host ?? '127.0.0.1',
    port: Number(env.PPCS_PGPORT ?? file.port ?? 55435),
    user: env.PPCS_PGUSER ?? file.user ?? 'postgres',
    password: env.PPCS_PGPASSWORD ?? file.password,
    image: env.PPCS_IMAGE ?? file.image ?? null,
  }
  if (!settings.token) throw new SafetyError('No disposable-instance token. Start the server with `pnpm run pg:up`, or set PPCS_INSTANCE_TOKEN.')
  if (!settings.password) throw new SafetyError('No password for the disposable instance. Start the server with `pnpm run pg:up`, or set PPCS_PGPASSWORD.')
  return settings
}

export class Instance {
  constructor(settings) {
    this.settings = settings
    this.verified = false
    this.owned = new Set()
    this.server = null
  }

  /** Connection parameters for `database`. Callers that pass them on must not record `password`. */
  connection(database, applicationName = OBSERVER_APP) {
    const { host, port, user, password } = this.settings
    return { host, port, user, password, database, application_name: applicationName }
  }

  async #connect(database, { serverTimeout = true } = {}) {
    // Bounded, so that a hung observation cannot stall the run. These limits apply only to the runner's connections,
    // never to the adapter's. verify() leaves out the server-side statement_timeout, which would otherwise show as the
    // session's own value when it reads the server's settings; the client-side query_timeout still bounds it.
    const c = new pg.Client({ ...this.connection(database), connectionTimeoutMillis: 10000, ...(serverTimeout ? { statement_timeout: 15000 } : {}), query_timeout: 20000 })
    c.on('error', () => {}) // a terminated or dropped connection must not crash the runner
    await c.connect()
    return c
  }

  /** Reads cluster_name and refuses the server unless it matches the token. Records the server's version and settings. */
  async verify() {
    let c
    try {
      c = await this.#connect('postgres', { serverTimeout: false })
    } catch (e) {
      // The password is random per start, so a stale .ppcs-instance.json fails here, before cluster_name is read.
      throw new SafetyError(`Refusing to run: could not connect to the disposable instance at ${this.settings.host}:${this.settings.port} (${String(e.message).split('\n')[0]}). Start it with \`pnpm run pg:up\`.`)
    }
    try {
      const actual = (await c.query(`select current_setting('cluster_name') as name`)).rows[0].name
      if (actual !== this.settings.token) {
        throw new SafetyError(`Refusing to run: the server at ${this.settings.host}:${this.settings.port} has cluster_name "${actual || '(empty)'}", not this run's disposable-instance token.`)
      }
      const info = (await c.query(`select version() as version, current_setting('server_version') as server_version,
        current_setting('server_version_num')::int as server_version_num`)).rows[0]
      const names = [...Object.keys(SERVER_PROFILE), 'max_connections', 'ssl']
      const rows = (await c.query(`select name, setting, unit from pg_settings where name = any($1) order by name`, [names])).rows
      const problems = profileProblems(Object.fromEntries(rows.map((s) => [s.name, s.setting])))
      if (problems.length) throw new SafetyError(`Refusing to run: the server's settings differ from the profile the cases assume (docs/methodology.md): ${problems.join('; ')}.`)
      this.server = { ...info, settings: Object.fromEntries(rows.map((s) => [s.name, s.unit ? `${s.setting} ${s.unit}` : s.setting])) }
    } finally {
      await c.end()
    }
    this.verified = true
    return this.server
  }

  #assertVerified() {
    if (!this.verified) throw new SafetyError('Refusing to touch the server before verify() has succeeded.')
  }

  async query(database, text, params = []) {
    this.#assertVerified()
    const c = await this.#connect(database)
    try { return (await c.query(text, params)).rows } finally { await c.end().catch(() => {}) }
  }

  async createDatabase(prefix) {
    this.#assertVerified()
    const name = `${prefix}_${Date.now().toString(36)}_${randomBytes(3).toString('hex')}`.toLowerCase().replace(/[^a-z0-9_]/g, '_')
    this.owned.add(name)
    await this.query('postgres', `create database "${name}"`)
    return name
  }

  async dropDatabase(name) {
    if (!this.owned.has(name)) throw new SafetyError(`Refusing to drop database "${name}": this run did not create it.`)
    await this.query('postgres', `drop database if exists "${name}" with (force)`)
    this.owned.delete(name)
  }

  /** Terminates a backend only if it is connected to `database`, which this run must own. */
  async terminateBackend(database, pid) {
    if (!this.owned.has(database)) throw new SafetyError(`Refusing to terminate sessions in "${database}": this run did not create it.`)
    if (!Number.isInteger(pid)) return false
    const rows = await this.query('postgres', 'select pg_terminate_backend(pid) as terminated from pg_stat_activity where pid = $1 and datname = $2', [pid, database])
    return rows[0]?.terminated === true
  }
}
