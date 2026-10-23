// Connection closed before COMMIT, and the next use after wait_timeout.
// This is not the lost COMMIT OK-packet case. It does not rewrite earlier evidence.

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
  waitFor,
} from './lib.mjs'

const phpScript = fileURLToPath(new URL('../php/bin/connection.php', import.meta.url))
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
  const [serverRows] = await root.conn.query(`SELECT VERSION() AS version, @@global.wait_timeout AS wait_timeout`)
  let versions = null
  for (const mode of ['mysqli', 'pdo', 'ci4-managed', 'ci4-manual']) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const result = await runKill(mode, repetition)
      if (!versions && result.versions) versions = result.versions
      runs.push(result)
      console.error(`${result.matched_expectation ? 'MATCH' : 'DIFFER'}  kill  ${mode}  r${repetition}  ${result.reason}`)
    }
  }
  for (const mode of ['mysqli', 'pdo', 'ci4-managed']) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const result = await runIdle(mode, repetition)
      if (!versions && result.versions) versions = result.versions
      runs.push(result)
      console.error(`${result.matched_expectation ? 'MATCH' : 'DIFFER'}  idle  ${mode}  r${repetition}  ${result.reason}`)
    }
  }
  for (const mode of ['ci4-managed', 'ci4-manual']) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const result = await runReconnect(mode, repetition)
      if (!versions && result.versions) versions = result.versions
      runs.push(result)
      console.error(`${result.matched_expectation ? 'MATCH' : 'DIFFER'}  reconnect  ${mode}  r${repetition}  ${result.reason}`)
    }
  }

  const mismatched = runs.filter((row) => !row.matched_expectation).map((row) => `${row.case} ${row.mode}#${row.repetition}`)
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    not_lost_commit_reply: true,
    does_not_replace: ['evidence/suite.json', 'evidence/php-mx01.json', 'evidence/php-concurrency.json', 'evidence/php-update-batch.json'],
    score_meaning: 'matched_expectation compares the run with expectation_basis. It is not a framework-defect verdict.',
    server: plain(serverRows[0]),
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-connection.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

async function runKill(mode, repetition) {
  const schema = await setup(root.conn, schemaName('mx05k', mode, repetition))
  const child = startPhp('kill', mode, schema)
  const basis = 'MX-05.connection-closed-before-commit. The server thread is killed after the insert and before COMMIT. The marker must be absent. The commit call must not return success.'
  try {
    const ready = await child.next(10000)
    const id = Number(ready.connection_id)
    if (!Number.isInteger(id) || id <= 0) throw new Error('connection id missing before kill')
    await observer.conn.query(`KILL ${id}`)
    const gone = await waitFor(async () => (await threadExists(id)) ? null : true, 2000)
    child.send('go\n')
    const result = await child.next(10000)
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const names = fresh.rows.map((row) => row.name)
    const observed = { ready, thread_gone_before_commit: gone.found === true, result, names }
    const verdict = scoreKill(observed)
    await child.close()
    return row('MX-05.connection-closed-before-commit', mode, repetition, schema, basis, verdict, observed, result.versions ?? null)
  } catch (error) {
    await child.close()
    return row('MX-05.connection-closed-before-commit', mode, repetition, schema, basis, { matched: false, reason: String(error?.message ?? error) }, { failed: true }, null)
  }
}

async function runIdle(mode, repetition) {
  const schema = await setup(root.conn, schemaName('mx05i', mode, repetition))
  const basis = 'The session wait_timeout is 1 second. After the insert the client sleeps 3 seconds, then sends SELECT 1 on the same handle. The server has closed the session, so the uncommitted marker is gone and the statement does not succeed.'
  try {
    const result = await runPhpToEnd('idle', mode, schema, 20000)
    const id = Number(result.connection_id)
    const gone = !(await threadExists(id))
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const names = fresh.rows.map((row) => row.name)
    const observed = { result, thread_gone: gone, names }
    const verdict = scoreIdle(observed)
    return row('MX-05.idle-wait-timeout', mode, repetition, schema, basis, verdict, observed, result.versions ?? null)
  } catch (error) {
    return row('MX-05.idle-wait-timeout', mode, repetition, schema, basis, { matched: false, reason: String(error?.message ?? error) }, { failed: true }, null)
  }
}

async function runReconnect(mode, repetition) {
  const schema = await setup(root.conn, schemaName('mx05r', mode, repetition))
  const basis = 'CodeIgniter reconnect() pings, and on failure closes and initializes a new connection. It does not change transDepth or transStatus. The marker inserted before wait_timeout is already gone. A later insert on the new connection autocommits. transComplete or transCommit then returns true because mysqli commit on the new connection succeeds. That true is not a commit of the timed-out transaction.'
  try {
    const result = await runPhpToEnd('reconnect', mode, schema, 20000)
    const oldId = Number(result.connection_id)
    const newId = Number(result.connection_id_after)
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    const names = fresh.rows.map((row) => row.name)
    const observed = {
      result,
      old_thread_gone: !(await threadExists(oldId)),
      new_thread_present: await threadExists(newId),
      names,
    }
    const verdict = scoreReconnect(observed)
    return row('MX-05.idle-then-reconnect', mode, repetition, schema, basis, verdict, observed, result.versions ?? null)
  } catch (error) {
    return row('MX-05.idle-then-reconnect', mode, repetition, schema, basis, { matched: false, reason: String(error?.message ?? error) }, { failed: true }, null)
  }
}

function scoreKill(observed) {
  const commit = observed.result?.commit ?? {}
  const ok = observed.thread_gone_before_commit === true
    && commit.returned !== true
    && commit.threw === true
    && !observed.names.includes('killed')
  return { matched: ok, reason: ok
    ? 'the commit call failed and the uncommitted marker is absent'
    : 'kill-before-commit did not match MX-05' }
}

function scoreIdle(observed) {
  const next = observed.result?.next ?? {}
  const failed = next.threw === true || next.returned === false
  const ok = failed && observed.thread_gone === true && !observed.names.includes('idle')
    && observed.result?.timeout?.returned === true
  return { matched: ok, reason: ok
    ? 'the same handle failed after wait_timeout and the uncommitted marker is absent'
    : 'idle timeout did not close the session' }
}

function scoreReconnect(observed) {
  const result = observed.result ?? {}
  const status = result.status_after_reconnect ?? {}
  const complete = result.complete ?? {}
  const follow = result.follow ?? {}
  const newId = Number(result.connection_id_after)
  const oldId = Number(result.connection_id)
  const ok = result.ping?.returned === false
    && result.reconnect?.threw !== true
    && newId > 0 && newId !== oldId
    && observed.old_thread_gone === true
    && status.trans_depth === 1
    && status.trans_status === true
    && follow.returned === true
    && complete.returned === true
    && complete.threw !== true
    && !observed.names.includes('idle')
    && observed.names.includes('after-reconnect')
  return { matched: ok, reason: ok
    ? 'reconnect opened a new connection, left depth at 1, and the completion call returned true without the timed-out marker'
    : 'reconnect after wait_timeout did not match the source-reading prediction' }
}

function row(caseId, mode, repetition, schema, basis, verdict, observed, versions) {
  return {
    case: caseId,
    mode,
    repetition,
    schema,
    expectation_basis: basis,
    matched_expectation: verdict.matched,
    reason: verdict.reason,
    versions,
    observed,
  }
}

async function threadExists(id) {
  if (!Number.isInteger(id) || id <= 0) return false
  const [rows] = await observer.conn.query(
    'SELECT PROCESSLIST_ID AS id FROM performance_schema.threads WHERE PROCESSLIST_ID = ?',
    [id],
  )
  return rows.length > 0
}

async function setup(rootConn, name) {
  const schema = await recreateSchema(rootConn, name)
  await rootConn.query(`CREATE TABLE \`${schema}\`.marker (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    UNIQUE KEY marker_name (name)
  ) ENGINE=InnoDB`)
  return schema
}

function schemaName(prefix, mode, repetition) {
  return `${prefix}_${mode.replaceAll('-', '_')}_r${repetition}`
}

function startPhp(kind, mode, database) {
  const child = spawn('php', [phpScript, kind, mode], {
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
  child.on('close', () => {
    while (waiters.length) waiters.shift().reject(new Error(`php connection subject closed: ${stderr.slice(0, 300)}`))
  })

  function next(timeoutMs) {
    return withTimeout(new Promise((resolve, reject) => {
      waiters.push({ resolve, reject })
    }), timeoutMs, kind)
  }

  function send(text) {
    child.stdin.write(text)
  }

  async function close() {
    child.stdin.end()
    if (child.exitCode == null) {
      await withTimeout(new Promise((resolve) => child.once('close', resolve)), 3000, 'php exit').catch(() => child.kill())
    }
  }

  return { next, send, close }
}

function runPhpToEnd(kind, mode, database, timeoutMs) {
  const child = startPhp(kind, mode, database)
  return child.next(timeoutMs).finally(() => child.close())
}

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs} ms`)), timeoutMs)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}
