// CodeIgniter nested transaction depth beside a mysqli SAVEPOINT.
// This does not score the case as MySQL MX-04, and it does not rewrite earlier evidence.

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

const phpScript = fileURLToPath(new URL('../php/bin/nested.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3
const scenarios = [
  'mysqli-savepoint-rollback',
  'ci4-managed-nested-success',
  'ci4-managed-nested-failure',
  'ci4-manual-inner-rollback',
  'ci4-manual-inner-commit',
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
  for (const scenario of scenarios) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const schema = await setup(root.conn, schemaName(scenario, repetition))
      try {
        const php = await runPhp(scenario, schema)
        const statements = php.api?.failed ? [] : await statementHistory(php.api?.connection_id)
        if (php.api && !php.api.failed) php.api.statements = statements
        php.send('go\n')
        const phpExit = await php.close()
        const fresh = await freshMarkerRead(instance, endpoint, schema)
        const names = fresh.rows.map((row) => row.name)
        if (!versions && php.api?.versions) versions = php.api.versions
        const verdict = score(scenario, php.api, names)
        runs.push({
          scenario,
          repetition,
          schema,
          expectation_basis: basis(scenario),
          matched_expectation: verdict.matched,
          reason: verdict.reason,
          final_names: names,
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
          final_names: [],
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
    not_scored_as: 'MX-04',
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json', 'evidence/php-concurrency.json', 'evidence/php-update-batch.json', 'evidence/php-connection.json'],
    score_meaning: 'matched_expectation compares CodeIgniter depth with a mysqli SAVEPOINT. It is not a defect verdict. The user guide says only the outermost transaction commands are executed.',
    server_version: serverRows[0].version,
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-nested.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

function score(scenario, api, finalNames) {
  if (!api || api.failed) return { matched: false, reason: api?.message ?? 'the PHP subject failed' }
  const sql = (api.statements ?? []).map((row) => row.sql_text).join('\n')
  const sameFinal = sameNames(finalNames, api.other_after_outer_end)
  if (scenario === 'mysqli-savepoint-rollback') {
    const ok = sameFinal
      && sameNames(api.subject_after_rollback_to, ['outer'])
      && api.other_before_outer_end.length === 0
      && sameNames(api.other_after_outer_end, ['after', 'outer'])
      && /SAVEPOINT/i.test(sql)
      && /ROLLBACK\s+TO/i.test(sql)
    return { matched: ok, reason: ok
      ? 'ROLLBACK TO SAVEPOINT removed the inner marker and the outer commit kept the rest'
      : 'mysqli savepoint rollback did not match MX-04' }
  }
  const noSavepoint = !/SAVEPOINT/i.test(sql)
  if (scenario === 'ci4-managed-nested-success') {
    const ok = sameFinal && noSavepoint
      && api.inner_complete === true
      && api.after_inner?.state?.trans_depth === 1
      && sameNames(api.after_inner?.subject, ['inside', 'outer'])
      && api.other_before_outer_end.length === 0
      && api.outer_complete === true
      && sameNames(api.other_after_outer_end, ['after', 'inside', 'outer'])
      && countStatements(sql, /^\s*COMMIT\b/i) === 1
    return { matched: ok, reason: ok
      ? 'the inner transComplete did not end a server transaction; the outer commit kept the inner marker'
      : 'managed nested success did not match the depth-counter contract' }
  }
  if (scenario === 'ci4-managed-nested-failure') {
    const ok = sameFinal && noSavepoint
      && api.duplicate?.returned === false
      && Number(api.duplicate?.error_code) === 1062
      && api.inner_complete === false
      && api.after_inner?.state?.trans_depth === 1
      && api.after_inner?.state?.trans_status === false
      && sameNames(api.after_inner?.subject, ['inside', 'outer'])
      && api.after_inner?.other.length === 0
      && api.outer_complete === false
      && api.other_after_outer_end.length === 0
      && /ROLLBACK/i.test(sql)
      && !/ROLLBACK\s+TO/i.test(sql)
    return { matched: ok, reason: ok
      ? 'the inner failure did not undo only the inner write; the outer rollback removed both'
      : 'managed nested failure did not match the depth-counter contract' }
  }
  if (scenario === 'ci4-manual-inner-rollback') {
    const ok = sameFinal && noSavepoint
      && api.inner_rollback === true
      && api.after_inner?.state?.trans_depth === 1
      && sameNames(api.after_inner?.subject, ['inside', 'outer'])
      && api.after_inner?.other.length === 0
      && api.outer_commit === true
      && sameNames(api.other_after_outer_end, ['inside', 'outer'])
      && countStatements(sql, /^\s*COMMIT\b/i) === 1
      && !/^\s*ROLLBACK\b/im.test(sql)
    return { matched: ok, reason: ok
      ? 'the inner transRollback returned true and the outer commit kept the inner marker'
      : 'manual inner rollback did not match the depth-counter contract' }
  }
  const ok = sameFinal && noSavepoint
    && api.inner_commit === true
    && api.after_inner?.state?.trans_depth === 1
    && sameNames(api.after_inner?.subject, ['inside', 'outer'])
    && api.after_inner?.other.length === 0
    && api.outer_commit === true
    && sameNames(api.other_after_outer_end, ['inside', 'outer'])
    && countStatements(sql, /^\s*COMMIT\b/i) === 1
  return { matched: ok, reason: ok
    ? 'the inner transCommit returned true without committing; the outer commit kept both markers'
    : 'manual inner commit did not match the depth-counter contract' }
}

function basis(scenario) {
  if (scenario === 'mysqli-savepoint-rollback') {
    return 'mysqli SAVEPOINT, then ROLLBACK TO SAVEPOINT. The inner marker is undone. The outer commit keeps the outer marker and the marker inserted after the rollback. This is the MySQL savepoint behavior. It is not the CodeIgniter nested-call contract.'
  }
  if (scenario === 'ci4-managed-nested-success') {
    return 'CodeIgniter user guide, Nested Transactions: an inner transStart/transComplete does not start or end a server transaction. The outer commit keeps the inner insert. No SAVEPOINT is sent.'
  }
  if (scenario === 'ci4-managed-nested-failure') {
    return 'A failed statement sets the one transStatus flag. The inner transComplete only decrements depth, so the same connection still sees the inner insert. The outer transComplete then sends ROLLBACK and removes both markers. That is not a savepoint rollback of the inner write alone.'
  }
  if (scenario === 'ci4-manual-inner-rollback') {
    return 'Inner transRollback, while depth is greater than 1, returns true and does not send ROLLBACK. The inner insert remains and the outer transCommit keeps it.'
  }
  return 'Inner transCommit, while depth is greater than 1, returns true and does not send COMMIT. Another connection sees nothing until the outer transCommit. That commit keeps both markers.'
}

function countStatements(sql, pattern) {
  return sql.split('\n').filter((line) => pattern.test(line)).length
}

function sameNames(actual, expected) {
  if (!Array.isArray(actual)) return false
  const left = [...actual].sort()
  const right = [...expected].sort()
  return left.length === right.length && left.every((name, index) => name === right[index])
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
  return `mxnest_${scenario.replaceAll('-', '_')}_r${repetition}`
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
    while (waiters.length) waiters.shift().reject(new Error(`php nested subject closed: ${stderr.slice(0, 300)}`))
  })

  function send(text) {
    child.stdin.write(text)
  }

  async function close() {
    child.stdin.end()
    if (child.exitCode == null) {
      await withTimeout(new Promise((resolve) => child.once('close', resolve)), 3000, 'php exit').catch(() => child.kill())
    }
    return exitCode
  }

  const api = withTimeout(new Promise((resolve, reject) => {
    waiters.push({ resolve, reject })
  }), 10000, scenario)

  return api.then((value) => ({ api: value, send, close }))
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

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs} ms`)), timeoutMs)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}
