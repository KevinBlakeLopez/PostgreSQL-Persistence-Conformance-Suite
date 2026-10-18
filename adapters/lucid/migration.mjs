// MG-02 and MG-03 through Lucid's MigrationRunner. The case's migration file is generated into a throwaway app
// directory. up() inserts the marker and, when the case has a gate, waits on it inside the migration's transaction.
// The runner's own session holds that lock. Lucid's advisory lock is the framework's coordination, and this file
// does not take another one.
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, relative } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { MigrationRunner } from '@adonisjs/lucid/migration'
import { errInfo } from '../node-kit/util.mjs'

const HERE = new URL('.', import.meta.url)
const CONTRACT = 'In @adonisjs/lucid 22.4.2, MigrationRunner.run() executes pending migrations (direction up) or reverts a batch (direction down). status is completed when files ran, skipped when none did, and error when a migration threw (build/src/migration/runner.js).'

function appEnvironment(appRoot) {
  return {
    appRoot: pathToFileURL(appRoot.endsWith('/') ? appRoot : `${appRoot}/`),
    inProduction: false,
    migrationsPath: (...p) => join(appRoot, 'database', 'migrations', ...p),
    relativePath: (p) => relative(appRoot, p),
    makePath: (...p) => join(appRoot, ...p),
  }
}

function source({ marker, gate, hold, reversal }) {
  const wait = hold ? `\n      await db.rawQuery('select pg_advisory_xact_lock(?)', [${Number(gate)}])` : ''
  const downs = {
    valid: `
  async down() {
    this.defer(async (db) => {
      await db.rawQuery('delete from item where name = ?', [${JSON.stringify(marker)}])
      await db.rawQuery('insert into ppcs_undo (name) values (?)', [${JSON.stringify(marker)}])
    })
  }`,
    none: '',
    'partial-then-error': `
  async down() {
    this.defer(async (db) => {
      await db.rawQuery('delete from item where name = ?', [${JSON.stringify(marker)}])
      await db.rawQuery('insert into ppcs_undo (name) values (?)', [${JSON.stringify(marker)}])
      throw new Error('the reversal failed on purpose after deleting the marker')
    })
  }`,
  }
  return `import { BaseSchema } from '@adonisjs/lucid/schema'

export default class extends BaseSchema {
  async up() {
    this.defer(async (db) => {
      await db.rawQuery('insert into item (name) values (?)', [${JSON.stringify(marker)}])${wait}
    })
  }
${downs[reversal] ?? downs.valid}
}
`
}

function writeApp(marker, migration) {
  const root = mkdtempSync(join(tmpdir(), 'ppcs-mg-'))
  writeFileSync(join(root, 'package.json'), JSON.stringify({ name: 'ppcs-mg', private: true, type: 'module' }))
  symlinkSync(fileURLToPath(new URL('./node_modules', HERE)), join(root, 'node_modules'))
  const dir = join(root, 'database', 'migrations')
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, '1000_m1.js'), source({ marker, gate: migration.gate, hold: migration.hold === true, reversal: migration.reversal ?? 'valid' }))
  return root
}

function outcome(runner) {
  if (runner.status === 'error') {
    return { reported: 'failed', exit_code: 1, basis: `MigrationRunner status ${runner.status}`, contract: CONTRACT, api_error: errInfo(runner.error) }
  }
  if (runner.direction === 'down') {
    return runner.status === 'completed'
      ? { reported: 'reverted', exit_code: 0, basis: 'MigrationRunner status completed for direction down', contract: CONTRACT }
      : { reported: 'nothing_to_do', exit_code: 0, basis: `MigrationRunner status ${runner.status} for direction down`, contract: CONTRACT }
  }
  return runner.status === 'completed'
    ? { reported: 'applied', exit_code: 0, basis: 'MigrationRunner status completed', contract: CONTRACT }
    : { reported: 'nothing_to_do', exit_code: 0, basis: `MigrationRunner status ${runner.status}`, contract: CONTRACT }
}

async function migrate({ db }, { markers, migration }) {
  const root = writeApp(markers.m1, migration)
  try {
    const runner = new MigrationRunner(db, appEnvironment(root), { direction: migration.operation === 'revert' ? 'down' : 'up', connectionName: 'pg' })
    await runner.run()
    return { ...outcome(runner), form: 'MigrationRunner.run() on a standalone Database. The migration file is generated for the case.' }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

const ids = ['MG-02.held', 'MG-02.first-deployment', 'MG-02.session-loss', 'MG-02.idle-session-timeout', 'MG-03.valid-reversal', 'MG-03.no-reversal', 'MG-03.failing-reversal']
export const migrationCases = Object.fromEntries(ids.map((id) => [id, migrate]))
