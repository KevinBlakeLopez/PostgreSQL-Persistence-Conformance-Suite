// Cross-checks one recorded run's identities and correlations, repetition by repetition.
//
//   node research/transaction-callbacks/laravel/check-run.mjs research/transaction-callbacks/laravel/output/<run id>
//
// For every repetition it checks that:
// - the subject's own pg_backend_pid() is the pid in the recorder's BackendKeyData, and the observer's
//   pg_stat_activity row for that pid carries the subject's application_name;
// - the observer and the sink are other backends;
// - each captured transaction ID appears as the server log's %x on that backend's later statements in the
//   same transaction, including the statement that ended it;
// - every marker that is visible has an xmin equal to the transaction ID captured inside its transaction;
// - the callbacks the PHP process saw are the rows the observer read from callback_log;
// - no callback had run before the transaction ended, apart from savepoint-recovery's inner afterRollBack.
// Needs only the run directory. Prints one line per failed check and a total.
import { readFileSync } from 'node:fs'
import path from 'node:path'

const dir = process.argv[2]
if (!dir) throw new Error('usage: node check-run.mjs <run directory>')
const results = readFileSync(path.join(dir, 'results.jsonl'), 'utf8').trim().split('\n').map((line) => JSON.parse(line))
const log = readFileSync(path.join(dir, 'server.log'), 'utf8').split('\n')

let checks = 0
const failures = []
const notRecorded = new Set()
const check = (ok, label, r) => {
  checks++
  if (!ok) failures.push(`${r.scenario} r${r.rep}: ${label}`)
}

for (const r of results) {
  if (r.process_error) {
    check(false, `process error: ${r.process_error.message}`, r)
    continue
  }
  const keyData = r.wire.find((e) => e.dir === 'B' && e.msg === 'BackendKeyData')
  check(keyData?.pid === r.subject_pid, `BackendKeyData pid ${keyData?.pid} is the subject pid ${r.subject_pid}`, r)
  // Runs before 2026-10-25T06 did not record application_name, the observer's and sink's pids, or xmin.
  const sessions = Object.values(r.checkpoints).map((c) => c.session).filter(Boolean)
  if (sessions.length > 0 && sessions.every((s) => 'application_name' in s)) {
    check(sessions.every((s) => s.application_name === r.subject_application_name), 'observed session is the subject', r)
  } else {
    notRecorded.add('application_name of the observed session')
  }
  if ('observer_pid' in r) {
    check(r.observer_pid !== r.subject_pid && r.sink_pid !== r.subject_pid && r.observer_pid !== r.sink_pid, 'observer, sink and subject are three backends', r)
  } else {
    notRecorded.add('observer and sink pids')
  }

  const subjectLines = log.filter((line) => line.includes(`[${r.subject_pid}] db=${r.database} `))
  for (const [label, xid] of Object.entries(r.xids)) {
    const withXid = subjectLines.filter((line) => line.includes(` xid=${xid} `))
    check(withXid.length >= 2, `xid ${label}=${xid} on at least two of the subject's log lines (${withXid.length})`, r)
    const ended = withXid.some((line) => /LOG:  statement: (COMMIT|ROLLBACK)$/.test(line))
    check(ended, `the statement that ended xid ${label}=${xid} is logged with that xid`, r)
  }

  for (const [name, checkpoint] of Object.entries(r.checkpoints)) {
    for (const [marker, xmin] of Object.entries(checkpoint.marker_xmin ?? {})) {
      const label = marker.endsWith('-reuse') ? 'reuse' : 'tx'
      check(xmin === r.xids[label], `${name}: visible marker ${marker} has xmin ${xmin}, captured xid ${r.xids[label]}`, r)
    }
  }

  const last = r.checkpoints['after-reuse'] ?? r.checkpoints['after-end']
  check(JSON.stringify(last.callback_log) === JSON.stringify(r.callbacks_in_process), 'in-process callbacks equal callback_log', r)
  const early = r.checkpoints['before-end']?.callback_log ?? []
  const allowed = r.scenario === 'laravel.savepoint-recovery' ? ['afterRollBack:inner'] : []
  check(JSON.stringify(early) === JSON.stringify(allowed), `callbacks before the end: ${early.join(',') || 'none'}`, r)
}

for (const failure of failures) console.log(`FAILED ${failure}`)
if (notRecorded.size) console.log(`not recorded in this run, so not checked: ${[...notRecorded].join('; ')}`)
console.log(`${results.length} repetitions, ${checks} checks, ${failures.length} failed`)
process.exitCode = failures.length ? 1 : 0
