// The server finishes COMMIT. The proxy does not write that OK packet to the client.
// A direct connection then reads the marker. That read is not what the client knew.

import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import mysql from 'mysql2/promise'
import knex from 'knex'
import { Database } from '@adonisjs/lucid/database'
import { startCommitReplyProxy } from './commit-reply-proxy.mjs'
import {
  MYSQL2_VERSION,
  assertNoSecrets,
  closeClient,
  connectionOptions,
  describeError,
  freshMarkerRead,
  loadInstance,
  openClient,
  plain,
  recreateSchema,
  requireToken,
} from './lib.mjs'

const require = createRequire(import.meta.url)
const KNEX_VERSION = require('knex/package.json').version
const LUCID_VERSION = JSON.parse(require('fs').readFileSync(new URL('../node_modules/@adonisjs/lucid/package.json', import.meta.url))).version

const instance = loadInstance()
const secrets = [instance.password, instance.root_password]
const endpoint = instance.default
const root = await openClient(instance, endpoint, 'root', 'root')
await requireToken(root.conn, instance.token)
const proxy = await startCommitReplyProxy({ host: endpoint.host, port: endpoint.port })

try {
  const [version] = await root.conn.query('SELECT VERSION() AS version')
  const schema = await setup(root.conn, 'mlost')
  const clients = []
  clients.push(await mysql2Control(schema))
  clients.push(await mysql2Lost(schema))
  clients.push(await knexLost(schema))
  clients.push(await lucidLost(schema))
  const text = `${JSON.stringify(plain({
    finished_at: new Date().toISOString(),
    not_a_ppcs_adapter: true,
    server_version: version[0].version,
    mysql2: MYSQL2_VERSION,
    knex: KNEX_VERSION,
    lucid: LUCID_VERSION,
    proxy: 'The COMMIT query is forwarded. The server packet that answers it is not written to the client, and the client socket is closed.',
    drops: proxy.drops,
    clients,
  }), null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(new URL('../evidence/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../evidence/lost-commit.json', import.meta.url), text)
} finally {
  await proxy.close()
  await closeClient(root)
}

async function mysql2Control(schema) {
  const conn = await openThroughProxy(schema)
  try {
    await conn.query('START TRANSACTION')
    await conn.query(`INSERT INTO marker (name) VALUES ('control-marker')`)
    const commit = await conn.query('COMMIT')
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return {
      client: 'mysql2',
      mode: 'proxy-forwards-commit',
      api: { outcome: 'resolved', serverStatus: commit[0].serverStatus ?? null },
      fresh_reader: fresh,
    }
  } finally {
    await conn.end().catch(() => {})
  }
}

async function mysql2Lost(schema) {
  const conn = await openThroughProxy(schema)
  try {
    await conn.query('START TRANSACTION')
    await conn.query(`INSERT INTO marker (name) VALUES ('mysql2-lost')`)
    proxy.arm()
    let api
    try {
      const commit = await withTimeout(conn.query('COMMIT'), 5000)
      api = { outcome: 'resolved', serverStatus: commit[0].serverStatus ?? null }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return { client: 'mysql2', mode: 'commit-reply-dropped', api, fresh_reader: fresh, drops_so_far: proxy.drops.length }
  } finally {
    await conn.end().catch(() => {})
  }
}

async function knexLost(schema) {
  const options = connectionOptions(instance, endpoint, 'app')
  const db = knex({
    client: 'mysql2',
    connection: { ...options, port: proxy.port, database: schema },
    pool: { min: 0, max: 1 },
  })
  const queries = []
  db.on('query', (query) => queries.push(query.sql))
  try {
    proxy.arm()
    let api
    try {
      await withTimeout(db.transaction(async (trx) => {
        await trx('marker').insert({ name: 'knex-lost' })
      }), 5000)
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return { client: 'knex', mode: 'commit-reply-dropped', api, queries, fresh_reader: fresh, drops_so_far: proxy.drops.length }
  } finally {
    await db.destroy()
  }
}

async function lucidLost(schema) {
  const options = connectionOptions(instance, endpoint, 'app')
  const lines = []
  const db = new Database({
    connection: 'mysql',
    connections: {
      mysql: {
        client: 'mysql2',
        connection: { ...options, port: proxy.port, database: schema },
        pool: { min: 0, max: 1 },
      },
    },
  }, captureLogger(lines), { emit() {}, hasListeners() { return false } })
  const queries = []
  db.connection().getWriteClient().on('query', (query) => queries.push(query.sql))
  try {
    proxy.arm()
    let api
    try {
      await withTimeout(db.transaction(async (trx) => {
        await trx.table('marker').insert({ name: 'lucid-lost' })
      }), 5000)
      api = { outcome: 'resolved' }
    } catch (error) {
      api = { outcome: 'rejected', error: describeError(error) }
    }
    const fresh = await freshMarkerRead(instance, endpoint, schema)
    return { client: 'lucid', mode: 'commit-reply-dropped', api, queries, fresh_reader: fresh, drops_so_far: proxy.drops.length }
  } finally {
    await db.manager.closeAll()
  }
}

async function openThroughProxy(database) {
  const options = connectionOptions(instance, endpoint, 'app')
  return mysql.createConnection({ ...options, port: proxy.port, database })
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

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timed out after ${ms} ms`)), ms)
    promise.then((value) => { clearTimeout(timer); resolve(value) }, (error) => { clearTimeout(timer); reject(error) })
  })
}

function captureLogger(lines) {
  const at = (level) => (...args) => {
    const text = args.map((arg) => typeof arg === 'string' ? arg : '').join(' ')
    lines.push({ level, msg: text.slice(0, 300) })
  }
  const logger = { trace() {}, debug() {}, info: at('info'), warn: at('warn'), error: at('error'), fatal: at('fatal'), isLevelEnabled: () => true }
  logger.child = () => logger
  return logger
}
