// Scores mysqli, PDO MySQL, and CodeIgniter 4 against the duplicate-key case.
// This file does not import the PostgreSQL harness and does not rewrite evidence/suite.json.
//
// The score is whether the pre-stated expectation held. It is not a defect verdict.
// InnoDB keeps the transaction usable after errno 1062. CodeIgniter's managed API
// treats that failure as a failed group. Those are different contracts.

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

const phpScript = fileURLToPath(new URL('../php/bin/mx01.php', import.meta.url))
const cwd = fileURLToPath(new URL('..', import.meta.url))
const repetitions = 3

const expectations = {
  'mysqli-commit-after-1062': {
    basis: 'MX-01. A caught duplicate key leaves the InnoDB transaction open. COMMIT keeps both markers. The duplicate row does not appear.',
    check: driverCommit,
  },
  'pdo-commit-after-1062': {
    basis: 'MX-01, through PDO MySQL with ERRMODE_EXCEPTION. Same server outcome as the mysqli control.',
    check: driverCommit,
  },
  'ci4-managed-default': {
    basis: 'CodeIgniter user guide: queries between transStart and transComplete are committed or rolled back together, and a query error does not throw by default. The insert after the error can still succeed inside the open InnoDB transaction. transComplete then rolls the group back.',
    check(api, names) {
      const steps = api.steps ?? {}
      const duplicateFalse = steps.duplicate?.threw === false && steps.duplicate?.returned === false && Number(steps.duplicate?.error_code) === 1062
      const afterAccepted = steps.after_error?.threw === false && steps.after_error?.returned === true
      const rolled = steps.trans_status_after_duplicate === false && steps.trans_complete === false && names.length === 0
      const ok = duplicateFalse && afterAccepted && rolled && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'transComplete returned false and neither marker remained'
        : 'managed default did not match the documented group rollback' }
    },
  },
  'ci4-managed-exception': {
    basis: 'CodeIgniter user guide, transException(true): a query error rolls the group back and throws DatabaseException.',
    check(api, names) {
      const duplicate = api.steps?.duplicate ?? {}
      const ok = duplicate.threw === true
        && duplicate.class === 'CodeIgniter\\Database\\Exceptions\\DatabaseException'
        && Number(duplicate.code) === 1062
        && names.length === 0
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? `DatabaseException 1062 and the marker is absent; sqlstate ${duplicate.sqlstate ?? 'not exposed'}`
        : 'transException did not match the documented rollback-and-throw behavior' }
    },
  },
  'ci4-managed-strict-second': {
    basis: 'CodeIgniter user guide, strict mode default: after one group fails, a later transStart/transComplete group is rolled back too. resetTransStatus was not called.',
    check(api, names) {
      const steps = api.steps ?? {}
      const ok = steps.first_complete === false
        && steps.trans_status_between === false
        && steps.second_insert?.returned === true
        && steps.second_complete === false
        && names.length === 0
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'the second strict group rolled back'
        : 'strict mode did not roll back the following group' }
    },
  },
  'ci4-managed-reset': {
    basis: 'CodeIgniter user guide, resetTransStatus since 4.6.0: after a failed strict group, resetting the status lets the next group commit. The failed group stays rolled back.',
    check(api, names) {
      const steps = api.steps ?? {}
      const ok = steps.first_complete === false
        && steps.trans_status_after_reset === true
        && steps.second_complete === true
        && sameNames(names, ['second-group'])
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'resetTransStatus let the second group commit'
        : 'resetTransStatus did not restore the next group' }
    },
  },
  'ci4-managed-nonstrict': {
    basis: 'CodeIgniter user guide: with strict mode off, a failed group rolls back and the status flag is cleared, so the next group can commit.',
    check(api, names) {
      const steps = api.steps ?? {}
      const ok = api.flags?.transStrict === false
        && steps.first_complete === false
        && steps.trans_status_between === true
        && steps.second_complete === true
        && sameNames(names, ['second-group'])
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'non-strict mode cleared the status and committed the next group'
        : 'non-strict mode did not treat the next group independently' }
    },
  },
  'ci4-manual-documented': {
    basis: 'CodeIgniter user guide manual example: transBegin, then transRollback when transStatus is false. DBDebug is true. The guide text shows this example with DBDebug false; this run records the true setting used by an ordinary debug configuration.',
    check: manualRollback,
  },
  'ci4-manual-documented-debug-off': {
    basis: 'The same manual example with DBDebug false, which is the setting named in the user guide.',
    check: manualRollback,
  },
  'ci4-manual-documented-then-managed': {
    basis: 'Strict mode keeps transStatus false after transRollback. The documented manual rollback, then a later managed group on the same connection without resetTransStatus, rolls that later group back.',
    check(api, names) {
      const steps = api.steps ?? {}
      const ok = steps.manual_rollback === true
        && steps.trans_status_after_rollback === false
        && steps.second_insert?.returned === true
        && steps.second_complete === false
        && names.length === 0
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'the rollback left transStatus false and the next managed group rolled back'
        : 'a documented rollback did not leave the documented strict-mode status' }
    },
  },
  'ci4-manual-unchecked-then-managed': {
    basis: 'transCommit sends COMMIT and does not read transStatus. The user guide example checks transStatus first; this run skips that check. The earlier marker stays. Strict mode still makes the next managed group roll back.',
    check(api, names) {
      const steps = api.steps ?? {}
      const duplicateFalse = steps.duplicate?.returned === false && Number(steps.duplicate?.error_code) === 1062
      const ok = duplicateFalse
        && steps.trans_status_before_commit === false
        && steps.trans_commit === true
        && steps.trans_status_after_commit === false
        && steps.second_complete === false
        && sameNames(names, ['before-error'])
        && !api.left_transaction_open
      return { matched: ok, reason: ok
        ? 'unchecked transCommit kept the earlier marker and the next managed group rolled back'
        : 'unchecked transCommit did not match the source-reading prediction' }
    },
  },
}

function driverCommit(api, names, taken) {
  const duplicate = api.duplicate ?? {}
  const ok = duplicate.threw === true
    && Number(duplicate.errno) === 1062
    && duplicate.sqlstate === '23000'
    && api.after_error_insert === true
    && api.commit === true
    && sameNames(names, ['before-error', 'after-error'])
    && taken === 1
  return { matched: ok, reason: ok
    ? 'COMMIT kept both markers after 1062'
    : 'the driver control did not match MX-01' }
}

function manualRollback(api, names) {
  const steps = api.steps ?? {}
  const ok = steps.choice === 'rollback'
    && steps.end_call === true
    && steps.duplicate?.returned === false
    && Number(steps.duplicate?.error_code) === 1062
    && names.length === 0
    && !api.left_transaction_open
  return { matched: ok, reason: ok
    ? 'the documented manual branch rolled back and the marker is absent'
    : 'the documented manual branch did not roll back' }
}

function sameNames(actual, expected) {
  const left = [...actual].sort()
  const right = [...expected].sort()
  return left.length === right.length && left.every((name, index) => name === right[index])
}

const instance = loadInstance()
const secrets = [instance.password, instance.root_password, instance.token]
const endpoint = instance.default
const root = await openClient(instance, endpoint, 'root', 'root')
const observer = await openClient(instance, endpoint, 'observer', 'root')
await requireToken(root.conn, instance.token)

const runs = []
try {
  const [serverRows] = await root.conn.query(`SELECT VERSION() AS version,
    @@global.innodb_rollback_on_timeout AS innodb_rollback_on_timeout,
    @@global.transaction_isolation AS transaction_isolation,
    @@global.autocommit AS autocommit,
    @@global.innodb_lock_wait_timeout AS innodb_lock_wait_timeout`)
  let versions = null
  for (const scenario of Object.keys(expectations)) {
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const schema = schemaName(scenario, repetition)
      await setup(root.conn, schema)
      const php = await runPhp(scenario, schema)
      const fresh = await freshMarkerRead(instance, endpoint, schema)
      const [uniqRows] = await observer.conn.query(
        `SELECT code, COUNT(*) AS n FROM \`${schema}\`.uniq_row GROUP BY code ORDER BY code`,
      )
      const names = fresh.rows.map((row) => row.name)
      const taken = Number(uniqRows.find((row) => row.code === 'taken')?.n ?? 0)
      const verdict = php.api?.failed
        ? { matched: false, reason: 'the PHP subject failed before it could be scored' }
        : expectations[scenario].check(php.api, names, taken)
      if (!versions && php.api?.versions) versions = php.api.versions
      runs.push({
        scenario,
        repetition,
        schema,
        expectation_basis: expectations[scenario].basis,
        matched_expectation: verdict.matched,
        reason: verdict.reason,
        marker_names: names,
        uniq_rows: plain(uniqRows),
        fresh_reader: fresh,
        api: php.api,
        php_exit: php.code,
        stderr: php.stderr,
      })
      console.error(`${verdict.matched ? 'MATCH' : 'DIFFER'}  ${scenario}  r${repetition}  ${verdict.reason}`)
    }
  }
  const mismatched = runs.filter((row) => !row.matched_expectation).map((row) => `${row.scenario}#${row.repetition}`)
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_the_ppcs_harness: true,
    does_not_replace: 'evidence/suite.json',
    score_meaning: 'matched_expectation compares the run with the expectation_basis. It is not a framework-defect verdict.',
    server: plain(serverRows[0]),
    versions,
    repetitions,
    mismatched,
    runs,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/php-mx01.json', import.meta.url), text)
  if (mismatched.length) process.exitCode = 1
} finally {
  await closeClient(root)
  await closeClient(observer)
}

function schemaName(scenario, repetition) {
  return `mx01_${scenario.replaceAll('-', '_')}_r${repetition}`
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

function runPhp(scenario, database) {
  return new Promise((resolve, reject) => {
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
    let stdout = ''
    let stderr = ''
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => {
      const combined = `${stdout}\n${stderr}`
      try {
        assertNoSecrets(combined, secrets)
      } catch (error) {
        reject(error)
        return
      }
      let api = null
      try {
        api = JSON.parse(stdout)
      } catch {
        api = { failed: true, message: 'stdout was not JSON', stdout: stdout.slice(0, 2000) }
      }
      resolve({ code, api, stderr: stderr.slice(0, 2000) })
    })
  })
}
