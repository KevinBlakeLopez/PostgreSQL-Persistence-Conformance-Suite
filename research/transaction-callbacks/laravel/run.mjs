// Runs this study's Laravel and PDO scenarios against its own PostgreSQL container.
//
//   sh research/transaction-callbacks/tools/container.sh up
//   node research/transaction-callbacks/laravel/run.mjs [--repeat=3] [--scenario=name,name]
//   sh research/transaction-callbacks/tools/container.sh down
//
// Each repetition of each scenario gets a fresh database and a fresh PHP process. The subject connection
// goes through the wire recorder. The observer and the sink go straight to PostgreSQL. The output
// directory gets results.jsonl (one object per repetition, with its subject connection's wire events),
// wire.ndjson (every recorded event), server.log (the statement log for this run's databases),
// versions.json, and summary.md.
import { execFile } from 'node:child_process'
import { createHash, randomBytes } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import pg from 'pg'
import { startRecorder } from '../tools/pg-tag-recorder.mjs'

const exec = promisify(execFile)
// The PHP that runs the scenarios. CB_PHP and CB_PHP_ARGS select another build, for example one that loads
// a patched pdo_pgsql with -dextension=<path>. CB_DRIVER_LABEL names the build in versions.json.
const php = { binary: process.env.CB_PHP ?? 'php', args: (process.env.CB_PHP_ARGS ?? '').split(' ').filter(Boolean) }
const here = path.dirname(fileURLToPath(import.meta.url))
const study = path.dirname(here)
const repo = path.resolve(study, '..', '..')

const SCENARIOS = [
  'laravel.commit',
  'laravel.error-escapes',
  'laravel.caught-error',
  'laravel.explicit-caught-error',
  'laravel.savepoint-recovery',
  'laravel.deferred-fk',
  'laravel.explicit-deferred-fk',
  'pdo.commit',
  'pdo.caught-error',
  'pdo.deferred-fk',
]

const options = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    const [key, value] = arg.replace(/^--/, '').split('=')
    return [key, value]
  }),
)
const repeat = Number(options.repeat ?? 3)
const scenarios = options.scenario ? options.scenario.split(',') : SCENARIOS
for (const scenario of scenarios) {
  if (!SCENARIOS.includes(scenario)) throw new Error(`unknown scenario ${scenario}`)
}

const instance = JSON.parse(readFileSync(path.join(study, '.instance.json'), 'utf8'))
if (instance.host !== '127.0.0.1' || instance.port !== 55491) {
  throw new Error('this runner only uses the study container on 127.0.0.1:55491')
}
const direct = { host: instance.host, port: instance.port, user: instance.user, password: instance.password }

const admin = new pg.Client({ ...direct, database: 'postgres', application_name: 'cb-runner' })
await admin.connect()
if ((await admin.query('show cluster_name')).rows[0].cluster_name !== instance.token) {
  throw new Error('cluster_name does not match .instance.json; refusing to run')
}

const runId = `${new Date().toISOString().replace(/\.\d+Z$/, 'Z').replace(/:/g, '-')}-${randomBytes(3).toString('hex')}`
const out = path.join(here, 'output', runId)
mkdirSync(out, { recursive: true })

const wire = []
const recorder = await startRecorder({ host: instance.host, port: instance.port, onEvent: (event) => wire.push(event) })

const results = []
const databases = []
try {
  for (const scenario of scenarios) {
    for (let rep = 1; rep <= repeat; rep++) {
      const database = `cb_${databases.length + 1}_${randomBytes(2).toString('hex')}`
      databases.push(database)
      await admin.query(`create database ${database}`)
      const setup = new pg.Client({ ...direct, database, application_name: 'cb-setup' })
      await setup.connect()
      await setup.query(`
        create table item (id serial primary key, name text not null, qty int not null default 0);
        create table uniq (id serial primary key, code text not null unique);
        insert into uniq (code) values ('taken');
        create table parent (id int primary key);
        create table child (
          id serial primary key,
          parent_id int not null references parent (id) deferrable initially deferred
        );
        create table callback_log (
          id serial primary key, scenario text not null, rep int not null, event text not null,
          logged_at timestamptz not null default clock_timestamp()
        );`)
      await setup.end()

      const env = {
        ...process.env,
        PGGSSENCMODE: 'disable',
        CB_HOST: instance.host,
        CB_DIRECT_PORT: String(instance.port),
        CB_SUBJECT_PORT: String(recorder.port),
        CB_USER: instance.user,
        CB_PASSWORD: instance.password,
        CB_DATABASE: database,
        CB_TOKEN: instance.token,
      }
      let result
      try {
        const { stdout } = await exec(php.binary, [...php.args, path.join(here, 'scenario.php'), scenario, String(rep)], { env, timeout: 60_000 })
        result = JSON.parse(stdout)
      } catch (error) {
        result = { scenario, rep, process_error: { message: error.message, stdout: error.stdout, stderr: error.stderr } }
      }
      const subject = `cb-${scenario}-r${rep}-subject`
      const conns = new Set(wire.filter((e) => e.msg === 'Startup' && e.application_name === subject).map((e) => e.conn))
      result.database = database
      result.wire = wire.filter((e) => conns.has(e.conn))
      results.push(result)

      await admin.query('select pg_terminate_backend(pid) from pg_stat_activity where datname = $1 and pid <> pg_backend_pid()', [database])
      await admin.query(`drop database ${database}`)
    }
  }
} finally {
  await recorder.close()
}

const serverVersion = (await admin.query('show server_version')).rows[0].server_version
await admin.end()

// The server writes its log to stderr. Keep only the lines of this run's databases.
const logs = await exec('docker', ['--context', 'colima', 'logs', instance.container], { maxBuffer: 64 * 1024 * 1024 })
const wanted = new Set(databases)
const serverLog = `${logs.stdout}${logs.stderr}`
  .split('\n')
  .filter((line) => {
    const match = line.match(/ db=(\S+) /)
    return match && wanted.has(match[1])
  })

const sha256 = (file) => createHash('sha256').update(readFileSync(file)).digest('hex')
const versions = {
  run_id: runId,
  finished_at: new Date().toISOString(),
  repetitions: repeat,
  server_version: serverVersion,
  image: instance.image,
  node: process.version,
  pg_for_runner: JSON.parse(readFileSync(path.join(repo, 'node_modules/pg/package.json'), 'utf8')).version,
  subject: results.find((r) => r.versions)?.versions ?? null,
  php_binary: php.binary,
  php_args: php.args,
  driver_label: process.env.CB_DRIVER_LABEL ?? 'stock',
  loaded_extension_sha256: Object.fromEntries(
    php.args.map((arg) => arg.match(/extension=(.+)$/)?.[1]).filter(Boolean).map((file) => [file, sha256(file)]),
  ),
  adapters_php_composer_lock_sha256: sha256(path.join(repo, 'adapters/php/composer.lock')),
  scenario_php_sha256: sha256(path.join(here, 'scenario.php')),
  run_mjs_sha256: sha256(fileURLToPath(import.meta.url)),
  recorder_sha256: sha256(path.join(study, 'tools/pg-tag-recorder.mjs')),
}

writeFileSync(path.join(out, 'results.jsonl'), results.map((r) => JSON.stringify(r)).join('\n') + '\n')
writeFileSync(path.join(out, 'wire.ndjson'), wire.map((e) => JSON.stringify(e)).join('\n') + '\n')
writeFileSync(path.join(out, 'server.log'), serverLog.join('\n') + '\n')
writeFileSync(path.join(out, 'versions.json'), JSON.stringify(versions, null, 2) + '\n')
writeFileSync(path.join(out, 'summary.md'), summarize(results, versions))
console.log(`wrote ${path.relative(repo, out)}`)
console.log(readFileSync(path.join(out, 'summary.md'), 'utf8'))

// Each COMMIT or ROLLBACK that the subject sent as a simple query: the ReadyForQuery status the server had
// reported before it (T in a transaction, E in a failed transaction), and the CommandComplete tag or error
// that answered it.
function transactionEnds(events) {
  const ends = []
  let status = null
  events.forEach((event, i) => {
    if (event.dir === 'B' && event.msg === 'ReadyForQuery') status = event.status
    if (event.dir === 'F' && event.msg === 'Query' && /^(commit|rollback)\b/i.test(event.sql.trim())) {
      const reply = events.slice(i + 1).find((e) => e.dir === 'B' && (e.msg === 'CommandComplete' || e.msg === 'ErrorResponse'))
      const answer = reply?.msg === 'CommandComplete' ? reply.tag : `error ${reply?.sqlstate ?? 'none'}`
      ends.push(`${event.sql.trim()} [${status}] -> ${answer}`)
    }
  })
  return ends
}

function row(result) {
  if (result.process_error) return { error: result.process_error.message }
  const before = result.checkpoints['before-end'] ?? {}
  const after = result.checkpoints['after-end'] ?? {}
  const reuse = result.checkpoints['after-reuse']
  const api = result.api.outcome === 'returned' ? 'returned' : `raised ${result.api.class.split('\\').pop()} ${result.api.sqlstate ?? ''}`.trim()
  return {
    api,
    caught: result.caught?.sqlstate ?? '-',
    commit_return: result.driver ? String(result.driver.commit_return) : '-',
    session_before_end: before.session?.state ?? 'gone',
    fate_before_end: before.xact_status?.tx ?? '-',
    ends: transactionEnds(result.wire).join('; '),
    fate_after_end: after.xact_status?.tx ?? '-',
    marker_after_end: Object.values(after.markers ?? {}).join(','),
    callbacks_after_end: (after.callback_log ?? []).join(', ') || 'none',
    reuse: reuse
      ? `${reuse.xact_status.reuse}; markers ${Object.values(reuse.markers).join(',')}; log ${reuse.callback_log.join(', ')}`
      : '-',
    manager_after_end: result.manager_after_end ? `${result.manager_after_end.pending}/${result.manager_after_end.committed}` : '-',
    manager_after: result.manager_after ? `${result.manager_after.pending}/${result.manager_after.committed}` : '-',
  }
}

function summarize(all, versions) {
  const columns = [
    ['api', 'API'],
    ['caught', 'Caught'],
    ['commit_return', 'PDO::commit()'],
    ['session_before_end', 'Session before end'],
    ['fate_before_end', 'Fate before end'],
    ['ends', 'Wire: end statement [status before] -> reply'],
    ['fate_after_end', 'Fate after end'],
    ['marker_after_end', 'Marker visible'],
    ['callbacks_after_end', 'Callback log after end'],
    ['reuse', 'Reuse'],
    ['manager_after_end', 'Manager pending/committed after end'],
    ['manager_after', 'Manager pending/committed at exit'],
  ]
  const lines = [
    `# Run ${versions.run_id}`,
    '',
    `PostgreSQL ${versions.server_version}, PHP ${versions.subject?.php}, pdo_pgsql ${versions.subject?.pdo_pgsql} (driver build: ${versions.driver_label}), libpq ${versions.subject?.libpq}, illuminate/database ${versions.subject?.['illuminate/database']}. ${versions.repetitions} repetitions per scenario. "Fate" is pg_xact_status() of the transaction ID captured inside the transaction, read on the observer's own connection. "Marker visible" and "Callback log" are read on that connection too.`,
    '',
    `| Scenario | Repetitions agreeing | ${columns.map(([, title]) => title).join(' | ')} |`,
    `| --- | --- | ${columns.map(() => '---').join(' | ')} |`,
  ]
  for (const scenario of [...new Set(all.map((r) => r.scenario))]) {
    const rows = all.filter((r) => r.scenario === scenario).map(row)
    const signatures = rows.map((r) => JSON.stringify(r))
    const agreeing = signatures.filter((s) => s === signatures[0]).length
    const first = rows[0]
    const cells = first.error ? columns.map(() => first.error) : columns.map(([key]) => String(first[key]).replace(/\|/g, '\\|'))
    lines.push(`| \`${scenario}\` | ${agreeing} of ${rows.length} | ${cells.join(' | ')} |`)
  }
  return lines.join('\n') + '\n'
}
