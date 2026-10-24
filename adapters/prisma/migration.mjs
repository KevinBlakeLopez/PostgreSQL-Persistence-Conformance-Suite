// MG-02 through `prisma migrate deploy`. The migration directory is generated for the case.
// The schema engine takes a session advisory lock, pg_advisory_lock(72707369), before it applies SQL.
// The PPCS fixture tables make the database non-empty, and deploy refuses a non-empty database that has no
// _prisma_migrations (P3005). Each runner baselines it the way Prisma documents for an existing database: an empty
// 0_baseline migration, marked applied with `prisma migrate resolve --applied`, which creates _prisma_migrations.
// A runner that finds the baseline already recorded (P3008) carries on to deploy.
// Migration files are forward SQL only. This module does not invent a down migration.
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { errInfo } from '../node-kit/util.mjs'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const PRISMA_BIN = fileURLToPath(new URL('./node_modules/prisma/build/index.js', import.meta.url))
const CONTRACT = 'Prisma Migrate 7.10.1 `migrate deploy` applies pending migration.sql files and records them in _prisma_migrations. The schema engine takes SELECT pg_advisory_lock(72707369) before applying. `migrate resolve --applied` records a migration as applied without running it, creating _prisma_migrations when it is absent, and returns P3008 when the migration is already recorded. A migration directory contains migration.sql and no down file.'
const FORM = 'prisma migrate resolve --applied 0_baseline, then prisma migrate deploy on a generated migration. The empty 0_baseline migration is the documented baseline for an existing database: deploy returns P3005 when the schema is not empty and has no _prisma_migrations. A P3008 answer to resolve, baseline already recorded, is not an error. migration.sql inserts the marker and waits on pg_advisory_xact_lock. The schema engine holds pg_advisory_lock(72707369) for the deploy.'
const BASELINE = '0_baseline'
// Prisma's answer when a migration is already recorded as applied (prisma.io/docs, baselining).
const ALREADY_BASELINED = /\bP3008\b/

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
  mkdirSync(join(migrations, BASELINE), { recursive: true })
  writeFileSync(join(migrations, BASELINE, 'migration.sql'), '-- The PPCS fixture tables exist before Prisma Migrate runs. This migration is marked applied, never executed.\n')
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

function prismaCli(cwd, env, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [PRISMA_BIN, ...args], {
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

function redact(text, password) {
  return password ? text.split(password).join('[redacted]') : text
}

export async function runPrismaMigration(connection, { markers, migration }) {
  const root = mkdtempSync(join(tmpdir(), 'ppcs-prisma-mg-'))
  const url = databaseUrl(connection)
  try {
    writeProject(root, { marker: markers.m1, gate: migration.gate, hold: migration.hold === true })
    const env = { ...process.env, DATABASE_URL: url, NODE_PATH: join(HERE, 'node_modules') }
    const baseline = await prismaCli(root, env, ['migrate', 'resolve', '--applied', BASELINE])
    if (baseline.code !== 0 && !ALREADY_BASELINED.test(`${baseline.stdout}\n${baseline.stderr}`)) {
      const message = redact(baseline.stderr, connection.password).trim().split('\n').filter(Boolean).slice(-3).join(' ').slice(0, 500)
      return { reported: 'failed', exit_code: baseline.code, basis: 'prisma migrate resolve --applied 0_baseline exited non-zero', contract: CONTRACT, form: FORM, api_error: { class: 'PrismaMigrateError', code: null, message: message || `exit ${baseline.code}` } }
    }
    const baselined = baseline.code === 0 ? 'migrate resolve recorded 0_baseline' : 'migrate resolve found 0_baseline already recorded (P3008)'
    const result = await prismaCli(root, env, ['migrate', 'deploy'])
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
      basis: `${applied ? 'prisma migrate deploy applied the migration' : 'prisma migrate deploy reported no pending migration'}; ${baselined}`,
      contract: CONTRACT,
      form: FORM,
    }
  } catch (error) {
    return { reported: 'failed', exit_code: 1, basis: 'prisma migrate deploy threw', contract: CONTRACT, form: FORM, api_error: errInfo(error) }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}
