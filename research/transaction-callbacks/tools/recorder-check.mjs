// Checks pg-tag-recorder.mjs against node-postgres, which exposes each reply's command tag itself
// (Result.command). One healthy transaction and one aborted by a real error (division by zero), both
// ended with COMMIT. Prints the driver's tags and the recorder's events. Needs the study container.
//
//   node research/transaction-callbacks/tools/recorder-check.mjs
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { startRecorder } from './pg-tag-recorder.mjs'

const study = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const instance = JSON.parse(readFileSync(path.join(study, '.instance.json'), 'utf8'))
const events = []
const recorder = await startRecorder({ host: instance.host, port: instance.port, onEvent: (e) => events.push(e) })
const client = new pg.Client({
  host: '127.0.0.1',
  port: recorder.port,
  user: instance.user,
  password: instance.password,
  database: 'postgres',
  application_name: 'cb-recorder-check',
})
await client.connect()
if ((await client.query('show cluster_name')).rows[0].cluster_name !== instance.token) throw new Error('wrong server')
await client.query('BEGIN')
const healthy = await client.query('COMMIT')
await client.query('BEGIN')
try {
  await client.query('SELECT 1/0')
} catch (error) {
  console.log('caught', error.code)
}
const aborted = await client.query('COMMIT')
await client.end()
await recorder.close()

console.log(`node-postgres Result.command: healthy ${healthy.command}, aborted ${aborted.command}`)
const shown = ['Startup', 'Query', 'CommandComplete', 'ErrorResponse', 'ReadyForQuery']
for (const e of events.filter((event) => shown.includes(event.msg))) {
  console.log(e.dir, e.msg, e.sql ?? e.tag ?? e.sqlstate ?? e.status ?? e.application_name)
}
const tags = events.filter((e) => e.msg === 'CommandComplete' && (e.tag === 'COMMIT' || e.tag === 'ROLLBACK')).map((e) => e.tag)
const agree = tags.join(',') === `${healthy.command},${aborted.command}`
console.log(agree ? 'recorder agrees with node-postgres' : `MISMATCH: recorder saw ${tags.join(',')}`)
process.exitCode = agree ? 0 : 1
