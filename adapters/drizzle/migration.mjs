// MG-02 through drizzle-orm migrate(). The journal and SQL are generated for the case.
// migrate() reads the latest history row outside a transaction, then runs pending statements and the
// history insert inside one transaction. It takes no advisory lock and has no down migration.
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { drizzle } from 'drizzle-orm/node-postgres'
import { migrate } from 'drizzle-orm/node-postgres/migrator'
import pg from 'pg'
import { errInfo } from '../node-kit/util.mjs'

const CONTRACT = 'drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration\'s statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.'
const FORM = 'migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.'

function sqlFor(marker, gate, hold) {
  const insert = `INSERT INTO item (name) VALUES ('${String(marker).replaceAll("'", "''")}');`
  if (!hold) return `${insert}\n`
  return `${insert}\n--> statement-breakpoint\nSELECT pg_advisory_xact_lock(${Number(gate)});\n`
}

async function historyCount(pool) {
  const result = await pool.query(`select to_regclass('drizzle_migrations') as rel`)
  if (!result.rows[0].rel) return 0
  const rows = await pool.query('select count(*)::int as n from drizzle_migrations')
  return rows.rows[0].n
}

export async function runDrizzleMigration(connection, { markers, migration, mode }) {
  const root = mkdtempSync(join(tmpdir(), 'ppcs-drizzle-mg-'))
  const folder = join(root, 'mig')
  mkdirSync(join(folder, 'meta'), { recursive: true })
  writeFileSync(join(folder, '0000_m1.sql'), sqlFor(markers.m1, migration.gate, migration.hold === true))
  writeFileSync(join(folder, 'meta', '_journal.json'), JSON.stringify({
    version: '7',
    dialect: 'postgresql',
    entries: [{ idx: 0, version: '7', when: 1000, tag: '0000_m1', breakpoints: true }],
  }))
  const pool = new pg.Pool({
    host: connection.host,
    port: connection.port,
    user: connection.user,
    password: connection.password,
    database: connection.database,
    application_name: connection.application_name,
    options: connection.options,
    max: 1,
  })
  pool.on('error', () => {})
  // pg-pool removes its client error listener while the client is checked out, and Drizzle adds none.
  // In native mode a terminated backend's 'error' on that client ends the process before migrate()
  // can reject. The configured mode adds the listener an application would add. It does not roll
  // the transaction back or discard the connection.
  if (mode === 'client-error-listener') pool.on('connect', (client) => { client.on('error', () => {}) })
  try {
    const before = await historyCount(pool)
    const db = drizzle(pool)
    await migrate(db, { migrationsFolder: folder, migrationsSchema: 'public', migrationsTable: 'drizzle_migrations' })
    const after = await historyCount(pool)
    const applied = after > before
    return {
      reported: applied ? 'applied' : 'nothing_to_do',
      exit_code: 0,
      basis: applied ? 'migrate() inserted a history row' : 'migrate() left the history count unchanged',
      contract: CONTRACT,
      form: FORM,
    }
  } catch (error) {
    return {
      reported: 'failed',
      exit_code: 1,
      basis: 'migrate() threw',
      contract: CONTRACT,
      form: FORM,
      api_error: errInfo(error),
    }
  } finally {
    await pool.end().catch(() => {})
    rmSync(root, { recursive: true, force: true })
  }
}
