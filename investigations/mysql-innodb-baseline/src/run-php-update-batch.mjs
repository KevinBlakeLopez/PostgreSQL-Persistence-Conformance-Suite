// updateBatch() after where(), on a synthetic table.
// CodeIgniter 4.7.4 throws DatabaseException for that combination.
// This file does not import the PostgreSQL harness and does not rewrite earlier evidence.

import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  assertNoSecrets,
  closeClient,
  loadInstance,
  openClient,
  plain,
  recreateSchema,
  requireToken,
} from './lib.mjs'

const phpScript = fileURLToPath(new URL('../php/bin/update-batch.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3
const expectedMessage = 'updateBatch() cannot be safely combined with existing Query Builder WHERE conditions. '
  + 'Use updateBatch($data, $constraints), onConstraint(), or include all required constraint fields in the batch data.'
const seeded = [
  { scope_id: '1', code: 'a', label: 'alpha' },
  { scope_id: '1', code: 'b', label: 'gamma' },
  { scope_id: '2', code: 'a', label: 'beta' },
]

const instance = loadInstance()
const secrets = [instance.password, instance.root_password, instance.token]
const endpoint = instance.default
const root = await openClient(instance, endpoint, 'root', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
await requireToken(root.conn, instance.token)

const runs = []
try {
  const [serverRows] = await root.conn.query('SELECT VERSION() AS version')
  let versions = null
  for (let repetition = 1; repetition <= repetitions; repetition += 1) {
    const schema = await setup(root.conn, `mxqb_batch_r${repetition}`)
    const php = await runPhp(schema)
    const [finalRows] = await observer.conn.query(
      `SELECT scope_id, code, label FROM \`${schema}\`.item ORDER BY scope_id, code`,
    )
    if (!versions && php.api?.versions) versions = php.api.versions
    const verdict = score(php.api, plain(finalRows))
    runs.push({
      repetition,
      schema,
      matched_expectation: verdict.matched,
      reason: verdict.reason,
      final_rows: plain(finalRows),
      api: php.api,
      php_exit: php.code,
    })
    console.error(`${verdict.matched ? 'MATCH' : 'DIFFER'}  update-batch  r${repetition}  ${verdict.reason}`)
  }
  const mismatched = runs.filter((row) => !row.matched_expectation).map((row) => `r${row.repetition}`)
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json', 'evidence/php-concurrency.json'],
    score_meaning: 'matched_expectation compares the run with the 4.7.4 contract: where() before updateBatch() throws, and no row changes.',
    changelog: 'CodeIgniter 4.7.4: updateBatch() after Query Builder where() conditions throws DatabaseException.',
    framework_test: 'tests/system/Database/Builder/UpdateTest.php testUpdateBatchThrowsExceptionWithWhere',
    server_version: serverRows[0].version,
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-update-batch.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

function score(api, finalRows) {
  if (!api || api.failed) return { matched: false, reason: api?.message ?? 'the PHP subject failed' }
  const on = threwUnchanged(api.chained_where_debug_on)
  const off = threwUnchanged(api.chained_where_debug_off)
  const reused = api.reused_builder?.first?.threw === true
    && api.reused_builder?.second_without_a_new_where?.threw === true
    && api.reused_builder?.second_without_a_new_where?.message === expectedMessage
    && sameRows(api.reused_builder?.rows_after, seeded)
  const bothScopes = sameRows(api.constraint_only?.rows_after, [
    { scope_id: '1', code: 'a', label: 'changed' },
    { scope_id: '1', code: 'b', label: 'gamma' },
    { scope_id: '2', code: 'a', label: 'changed' },
  ]) && api.constraint_only?.call?.threw === false
  const oneScope = sameRows(api.composite_constraint?.rows_after, [
    { scope_id: '1', code: 'a', label: 'only-scope-1' },
    { scope_id: '1', code: 'b', label: 'gamma' },
    { scope_id: '2', code: 'a', label: 'beta' },
  ]) && api.composite_constraint?.call?.threw === false
  const finalOk = sameRows(finalRows, api.composite_constraint?.rows_after)
  const ok = on && off && reused && bothScopes && oneScope && finalOk
  return { matched: ok, reason: ok
    ? 'where() before updateBatch() threw, the rows stayed, and the constraint argument did the matching'
    : 'updateBatch where() did not match the 4.7.5 exception contract' }
}

function threwUnchanged(step) {
  return step?.call?.threw === true
    && step?.call?.class === 'CodeIgniter\\Database\\Exceptions\\DatabaseException'
    && step?.call?.message === expectedMessage
    && step?.sql_unchanged === true
    && sameRows(step?.rows_after, seeded)
}

function sameRows(actual, expected) {
  const left = normalize(actual)
  const right = normalize(expected)
  if (left.length !== right.length) return false
  return left.every((row, index) => row.scope_id === right[index].scope_id
    && row.code === right[index].code
    && row.label === right[index].label)
}

function normalize(rows) {
  if (!Array.isArray(rows)) return []
  return rows.map((row) => ({
    scope_id: String(row.scope_id),
    code: String(row.code),
    label: String(row.label),
  }))
}

async function setup(rootConn, name) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.item (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    scope_id INT NOT NULL,
    code VARCHAR(32) NOT NULL,
    label VARCHAR(64) NOT NULL,
    UNIQUE KEY item_scope_code (scope_id, code)
  ) ENGINE=InnoDB`)
  await rootConn.query(
    `INSERT INTO \`${schema}\`.item (scope_id, code, label) VALUES (1, 'a', 'alpha'), (2, 'a', 'beta'), (1, 'b', 'gamma')`,
  )
  return schema
}

function runPhp(database) {
  return new Promise((resolve, reject) => {
    const child = spawn('php', [phpScript], {
      cwd,
      env: {
        ...process.env,
        MPCS_HOST: endpoint.host,
        MPCS_PORT: String(endpoint.port),
        MPCS_USER: instance.user,
        MPCS_PASSWORD: instance.password,
        MPCS_DATABASE: database,
      },
    })
    let stdout = ''
    let stderr = ''
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => {
      try {
        assertNoSecrets(`${stdout}\n${stderr}`, secrets)
      } catch (error) {
        reject(error)
        return
      }
      let api = null
      try {
        api = JSON.parse(stdout)
      } catch {
        api = { failed: true, message: 'stdout was not JSON', stdout: stdout.slice(0, 2000), stderr: stderr.slice(0, 500) }
      }
      resolve({ code, api })
    })
  })
}
