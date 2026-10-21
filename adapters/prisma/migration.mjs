// MG-02 through `prisma migrate deploy`. The migration directory is generated for the case.
// The schema engine takes a session advisory lock, pg_advisory_lock(72707369), before it applies SQL.
// Migration files are forward SQL only. This module does not invent a down migration.
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { errInfo } from '../node-kit/util.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const PRISMA_BIN = fileURLToPath(new URL('./node_modules/prisma/build/index.js', import.meta.url))
const CONTRACT = 'Prisma Migrate 7.10.1 `migrate deploy` applies pending migration.sql files and records them in _prisma_migrations. The schema engine takes SELECT pg_advisory_lock(72707369) before applying. A migration directory contains migration.sql and no down file.'
const FORM = 'prisma migrate deploy on a generated migration. migration.sql inserts the marker and waits on pg_advisory_xact_lock. The schema engine holds pg_advisory_lock(72707369) for the deploy. An empty _prisma_migrations table is created first when it is absent, because deploy returns P3005 when item already exists and that table does not.'
const HISTORY_DDL = `CREATE TABLE IF NOT EXISTS "_prisma_migrations" (
  id varchar(36) PRIMARY KEY NOT NULL,
  checksum varchar(64) NOT NULL,
  finished_at timestamptz,
  migration_name varchar(255) NOT NULL,
  logs text,
  rolled_back_at timestamptz,
  started_at timestamptz NOT NULL DEFAULT now(),
  applied_steps_count integer NOT NULL DEFAULT 0
)`

function databaseUrl(connection) {
  const user = encodeURIComponent(connection.user)
  const password = encodeURIComponent(connection.password)
  const params = new URLSearchParams()
  if (connection.application_name) params.set('application_name', connection.application_name)
  if (connection.options) params.set('options', connection.options)
  const query = params.toString()
  return `postgresql://${user}:${password}@${connection.host}:${connection.port}/${connection.database}${query ? `?${query}` : ''}`
}

function writeProject(root, { marker, gate, hold }) {
  const insert = `INSERT INTO item (name) VALUES ('${String(marker).replaceAll("'", "''")}');`
  const sql = hold ? `${insert}\nSELECT pg_advisory_xact_lock(${Number(gate)});\n` : `${insert}\n`
  const migrations = join(root, 'prisma', 'migrations')
  mkdirSync(join(migrations, '20200101000000_m1'), { recursive: true })
  writeFileSync(join(migrations, 'migration_lock.toml'), 'provider = "postgresql"\n')
  writeFileSync(join(migrations, '20200101000000_m1', 'migration.sql'), sql)
  writeFileSync(join(root, 'schema.prisma'), 'datasource db {\n  provider = "postgresql"\n}\n')
  writeFileSync(join(root, 'prisma.config.ts'), `import { defineConfig, env } from 'prisma/config'

export default defineConfig({
  schema: 'schema.prisma',
  migrations: { path: 'prisma/migrations' },
  datasource: { url: env('DATABASE_URL') },
})
`)
}

function deploy(cwd, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [PRISMA_BIN, 'migrate', 'deploy'], {
      cwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }))
  })
}

async function withClient(connection, fn) {
  const client = new pg.Client({
    host: connection.host,
    port: connection.port,
    user: connection.user,
    password: connection.password,
    database: connection.database,
    application_name: 'ppcs-count',
  })
  await client.connect()
  try {
    return await fn(client)
  } finally {
    await client.end()
  }
}

async function ensureHistory(connection) {
  await withClient(connection, (client) => client.query(HISTORY_DDL))
}

function redact(text, password) {
  return password ? text.split(password).join('[redacted]') : text
}

export async function runPrismaMigration(connection, { markers, migration }) {
  const root = mkdtempSync(join(tmpdir(), 'ppcs-prisma-mg-'))
  const url = databaseUrl(connection)
  try {
    writeProject(root, { marker: markers.m1, gate: migration.gate, hold: migration.hold === true })
    await ensureHistory(connection)
    const result = await deploy(root, {
      ...process.env,
      DATABASE_URL: url,
      NODE_PATH: join(HERE, 'node_modules'),
    })
    if (result.code !== 0) {
      const message = redact(result.stderr, connection.password).trim().split('\n').filter(Boolean).slice(-3).join(' ').slice(0, 500)
      return {
        reported: 'failed',
        exit_code: result.code,
        basis: 'prisma migrate deploy exited non-zero',
        contract: CONTRACT,
        form: FORM,
        api_error: { class: 'PrismaMigrateError', code: null, message: message || `exit ${result.code}` },
      }
    }
    const applied = result.stdout.includes('Applying migration')
    return {
      reported: applied ? 'applied' : 'nothing_to_do',
      exit_code: 0,
      basis: applied ? 'prisma migrate deploy applied the migration' : 'prisma migrate deploy reported no pending migration',
      contract: CONTRACT,
      form: FORM,
    }
  } catch (error) {
    return { reported: 'failed', exit_code: 1, basis: 'prisma migrate deploy threw', contract: CONTRACT, form: FORM, api_error: errInfo(error) }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}
