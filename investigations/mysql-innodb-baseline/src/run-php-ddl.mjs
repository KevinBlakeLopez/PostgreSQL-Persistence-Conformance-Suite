// DDL inside a transaction. mysqli is the control. CodeIgniter runs MigrationRunner.
// Not scored as PostgreSQL MG-03. Does not rewrite earlier evidence.

import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  assertNoSecrets,
  closeClient,
  freshMarkerRead,
  loadInstance,
  openClient,
  plain,
  recreateSchema,
  requireToken,
} from './lib.mjs'

const phpScript = fileURLToPath(new URL('../php/bin/ddl.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3

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
  for (const scenario of ['mysqli', 'ci4-migration']) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const schema = await setup(root.conn, schemaName(scenario, repetition))
      try {
        const php = await runPhp(scenario, schema)
        const statements = await statementHistory(php.api?.connection_id)
        if (php.api && !php.api.failed) php.api.statements = statements
        const tables = await tablesIn(schema)
        php.send('go\n')
        const phpExit = await php.close()
        const fresh = await freshMarkerRead(instance, endpoint, schema)
        const names = fresh.rows.map((row) => row.name)
        if (!versions && php.api?.versions) versions = php.api.versions
        const verdict = score(scenario, php.api, names, tables)
        runs.push({
          scenario,
          repetition,
          schema,
          expectation_basis: basis(scenario),
          matched_expectation: verdict.matched,
          reason: verdict.reason,
          final_names: names,
          final_tables: tables,
          api: stripClose(php.api),
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
          final_names: [],
          final_tables: [],
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
    not_scored_as: 'MG-03',
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json', 'evidence/php-concurrency.json', 'evidence/php-update-batch.json', 'evidence/php-connection.json', 'evidence/php-nested.json'],
    score_meaning: 'matched_expectation compares the run with MySQL implicit commit. It is not a defect verdict.',
    server_version: serverRows[0].version,
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-ddl.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

function score(scenario, api, finalNames, tables) {
  if (!api || api.failed) return { matched: false, reason: api?.message ?? 'the PHP subject failed' }
  const sql = (api.statements ?? []).map((row) => row.sql_text).join('\n')
  const hasCreate = /CREATE TABLE .*ddl_side/i.test(sql)
  const hasRollback = api.statements.some((row) => /^\s*ROLLBACK\b/i.test(row.sql_text) && !/ROLLBACK\s+TO/i.test(row.sql_text))
  const tableRemains = tables.some((row) => row.table_name === 'ddl_side')
  if (scenario === 'mysqli') {
    const ok = api.before_ddl?.names?.length === 0
      && api.before_ddl?.table === false
      && sameNames(api.after_ddl?.names, ['ddl-marker'])
      && api.after_ddl?.table === true
      && api.duplicate?.threw === true
      && Number(api.duplicate?.error_code) === 1062
      && api.rollback_returned === true
      && sameNames(api.after_rollback?.names, ['ddl-marker'])
      && api.after_rollback?.table === true
      && sameNames(finalNames, ['ddl-marker'])
      && tableRemains
      && hasCreate
      && hasRollback
    return { matched: ok, reason: ok
      ? 'CREATE TABLE committed the marker, and ROLLBACK removed neither the row nor the table'
      : 'mysqli DDL implicit commit did not match MX-07' }
  }
  const notes = api.notes ?? {}
  const history = api.history ?? []
  const recorded = history.some((row) => String(row.class).includes('DdlThenFail'))
  const ok = api.runner_returned === false
    && api.runner_exception?.message === 'migration failed after schema change'
    && notes.other_before_ddl?.length === 0
    && notes.table_before_ddl === false
    && sameNames(notes.other_after_ddl, ['ddl-marker'])
    && notes.table_after_ddl === true
    && notes.duplicate_returned === false
    && Number(notes.duplicate_error?.code) === 1062
    && notes.complete === false
    && sameNames(notes.other_after_complete, ['ddl-marker'])
    && notes.table_after_complete === true
    && !recorded
    && sameNames(api.after_runner?.names, ['ddl-marker'])
    && api.after_runner?.table === true
    && sameNames(finalNames, ['ddl-marker'])
    && tableRemains
    && hasCreate
    && hasRollback
  return { matched: ok, reason: ok
    ? 'the migration reported failure and recorded no history, and the marker and table remained'
    : 'the migration DDL outcome did not match implicit commit' }
}

function basis(scenario) {
  if (scenario === 'mysqli') {
    return 'MX-07. CREATE TABLE implicitly commits. The marker is visible to another connection before ROLLBACK. ROLLBACK removes neither the marker nor the new table. The duplicate key is errno 1062 and does not change that.'
  }
  return 'MigrationRunner::force() calls up() and records history only when up() returns. This up() starts a transaction, inserts a marker, creates a table, hits a duplicate key, calls transComplete(), then throws. MySQL has already committed the marker and the table. transComplete() returns false. The runner does not record the migration. This is not PostgreSQL MG-03.'
}

function sameNames(actual, expected) {
  if (!Array.isArray(actual)) return false
  const left = [...actual].sort()
  const right = [...expected].sort()
  return left.length === right.length && left.every((name, index) => name === right[index])
}

function stripClose(api) {
  if (!api || typeof api !== 'object') return api
  const copy = { ...api }
  delete copy.close
  return copy
}

async function setup(rootConn, name) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.marker (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
  await rootConn.query(`CREATE TABLE \`${schema}\`.uniq_row (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    UNIQUE KEY uniq_code (code)
  ) ENGINE=InnoDB`)
  await rootConn.query(`INSERT INTO \`${schema}\`.uniq_row (code) VALUES ('taken')`)
  return schema
}

function schemaName(scenario, repetition) {
  return `mxddl_${scenario.replaceAll('-', '_')}_r${repetition}`
}

async function tablesIn(schema) {
  const [rows] = await observer.conn.query(
    `SELECT TABLE_NAME AS table_name, ENGINE AS engine
     FROM information_schema.tables WHERE TABLE_SCHEMA = ? ORDER BY TABLE_NAME`,
    [schema],
  )
  return plain(rows)
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
    while (waiters.length) waiters.shift().reject(new Error(`php ddl subject closed: ${stderr.slice(0, 400)}`))
  })
  const api = withTimeout(new Promise((resolve, reject) => {
    waiters.push({ resolve, reject })
  }), 20000, scenario)
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
