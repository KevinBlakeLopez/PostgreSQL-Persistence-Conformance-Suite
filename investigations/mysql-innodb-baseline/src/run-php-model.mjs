// CodeIgniter Model allowedFields, and a Model update inside a failed transaction.
// Does not rewrite earlier evidence.

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

const phpScript = fileURLToPath(new URL('../php/bin/model.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3
const scenarios = ['update-mixed', 'save-mixed', 'update-omitted-only', 'update-then-rollback']
const seeded = { id: '1', label: 'alpha', secret: 'keep' }

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
  for (const scenario of scenarios) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const schema = await setup(root.conn, schemaName(scenario, repetition))
      try {
        const php = await runPhp(scenario, schema)
        const statements = await statementHistory(php.api?.connection_id)
        if (php.api && !php.api.failed) php.api.statements = statements
        php.send('go\n')
        const phpExit = await php.close()
        const [rows] = await observer.conn.query(
          `SELECT id, label, secret FROM \`${schema}\`.item WHERE id = 1`,
        )
        const row = plain(rows[0] ?? null)
        if (!versions && php.api?.versions) versions = php.api.versions
        const verdict = score(scenario, php.api, row)
        runs.push({
          scenario,
          repetition,
          schema,
          expectation_basis: basis(scenario),
          matched_expectation: verdict.matched,
          reason: verdict.reason,
          final_row: row,
          api: php.api,
          php_exit: phpExit,
        })
        console.error(`${verdict.matched ? 'MATCH' : 'DIFFER'}  ${scenario}  r${repetition}  ${verdict.reason}`)
      } catch (error) {
        runs.push({
          scenario,
          repetition,
          schema,
          expectation_basis: basis(scenario),
          matched_expectation: false,
          reason: String(error?.message ?? error),
          final_row: null,
          api: { failed: true },
          php_exit: null,
        })
        console.error(`DIFFER  ${scenario}  r${repetition}  ${error?.message ?? error}`)
      }
    }
  }
  const mismatched = runs.filter((row) => !row.matched_expectation).map((row) => `${row.scenario}#${row.repetition}`)
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json', 'evidence/php-concurrency.json', 'evidence/php-update-batch.json', 'evidence/php-connection.json', 'evidence/php-nested.json', 'evidence/php-ddl.json'],
    score_meaning: 'matched_expectation compares the Model return with the row read by another connection. It is not a defect verdict.',
    server_version: serverRows[0].version,
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-model.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

function score(scenario, api, finalRow) {
  if (!api || api.failed) return { matched: false, reason: api?.message ?? 'the PHP subject failed' }
  const agrees = sameRow(finalRow, api.row_after)
  if (scenario === 'update-mixed' || scenario === 'save-mixed') {
    const changed = { id: '1', label: 'beta', secret: 'keep' }
    const sql = api.sql ?? ''
    const ok = agrees
      && api.call?.returned === true
      && api.call?.threw === false
      && sameRow(api.row_after, changed)
      && /`label`/.test(sql)
      && !/`secret`/.test(sql)
    return { matched: ok, reason: ok
      ? 'the Model returned true, label changed, and secret stayed'
      : 'the mixed Model write did not match allowedFields' }
  }
  if (scenario === 'update-omitted-only') {
    const ok = agrees
      && api.call?.threw === true
      && api.call?.class === 'CodeIgniter\\Database\\Exceptions\\DataException'
      && api.call?.message === 'There is no data to update.'
      && sameRow(api.row_after, seeded)
      && api.sql_before === api.sql_after
    return { matched: ok, reason: ok
      ? 'an update of only a protected field threw, and the row stayed'
      : 'the omitted-only update did not throw before writing' }
  }
  const ok = agrees
    && api.call?.returned === true
    && sameRow(api.other_before_complete, seeded)
    && api.duplicate_returned === false
    && Number(api.duplicate_error_code) === 1062
    && api.complete === false
    && sameRow(api.row_after, seeded)
  return { matched: ok, reason: ok
    ? 'the Model update returned true and the failed transaction left the original row'
    : 'the Model return and the transaction outcome were not separate' }
}

function basis(scenario) {
  if (scenario === 'update-mixed') {
    return 'ItemModel allows only label. update() with label and secret returns true. Another connection sees the new label and the original secret. The UPDATE does not name secret.'
  }
  if (scenario === 'save-mixed') {
    return 'save() with an id calls update(). The same allowedFields rule applies: secret is removed, the call returns true, and the stored secret is unchanged.'
  }
  if (scenario === 'update-omitted-only') {
    return 'update() with only secret leaves an empty dataset after allowedFields. CodeIgniter throws DataException, "There is no data to update.", and does not send UPDATE.'
  }
  return 'The Model update returns true inside transStart(). A later duplicate key makes transComplete() return false. Another connection never sees the new label. The original row remains. The Model return is not the transaction result.'
}

function sameRow(actual, expected) {
  if (!actual || !expected) return false
  return String(actual.id) === String(expected.id)
    && String(actual.label) === String(expected.label)
    && String(actual.secret) === String(expected.secret)
}

async function setup(rootConn, name) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.item (
    id INT NOT NULL PRIMARY KEY,
    label VARCHAR(64) NOT NULL,
    secret VARCHAR(64) NOT NULL
  ) ENGINE=InnoDB`)
  await rootConn.query(`INSERT INTO \`${schema}\`.item (id, label, secret) VALUES (1, 'alpha', 'keep')`)
  await rootConn.query(`CREATE TABLE \`${schema}\`.uniq_row (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    UNIQUE KEY uniq_code (code)
  ) ENGINE=InnoDB`)
  await rootConn.query(`INSERT INTO \`${schema}\`.uniq_row (code) VALUES ('taken')`)
  return schema
}

function schemaName(scenario, repetition) {
  return `mxmodel_${scenario.replaceAll('-', '_')}_r${repetition}`
}

async function statementHistory(connectionId) {
  const id = Number(connectionId)
  if (!Number.isInteger(id) || id <= 0) return []
  const [rows] = await observer.conn.query(
    `SELECT h.SQL_TEXT AS sql_text, h.MYSQL_ERRNO AS errno
     FROM performance_schema.events_statements_history h
     JOIN performance_schema.threads t ON t.THREAD_ID = h.THREAD_ID
     WHERE t.PROCESSLIST_ID = ?
     ORDER BY h.EVENT_ID`,
    [id],
  )
  return plain(rows).filter((row) => row.sql_text)
}

function runPhp(scenario, database) {
  const child = spawn('php', [phpScript, scenario], {
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
  let buffer = ''
  let stderr = ''
  let exitCode = null
  const waiters = []
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    buffer += chunk
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline)
      buffer = buffer.slice(newline + 1)
      const waiter = waiters.shift()
      if (waiter) {
        try {
          assertNoSecrets(line, secrets)
          waiter.resolve(JSON.parse(line))
        } catch (error) {
          waiter.reject(error)
        }
      }
      newline = buffer.indexOf('\n')
    }
  })
  child.stderr.on('data', (chunk) => { stderr += chunk })
  child.on('close', (code) => {
    exitCode = code
    while (waiters.length) waiters.shift().reject(new Error(`php model subject closed: ${stderr.slice(0, 400)}`))
  })
  const api = withTimeout(new Promise((resolve, reject) => {
    waiters.push({ resolve, reject })
  }), 15000, scenario)
  return api.then((value) => ({
    api: value,
    send(text) { child.stdin.write(text) },
    async close() {
      child.stdin.end()
      if (child.exitCode == null) {
        await withTimeout(new Promise((resolve) => child.once('close', resolve)), 3000, 'php exit').catch(() => child.kill())
      }
      return exitCode
    },
  }))
}

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs} ms`)), timeoutMs)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}
