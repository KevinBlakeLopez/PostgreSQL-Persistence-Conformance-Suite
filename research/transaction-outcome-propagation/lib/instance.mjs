// Disposable-server access for the propagation experiment.
// Refuses a server whose cluster_name is not the token in .ppcs-instance.json.
// Does not import the PPCS harness, so the suite digest stays unchanged.

import { existsSync, readFileSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const INSTANCE_FILE = fileURLToPath(new URL('../../../.ppcs-instance.json', import.meta.url))

export const FIXTURE_SQL = "create table item (id serial primary key, name text not null, qty int not null default 0); create table uniq (id serial primary key, code text not null unique); insert into uniq (code) values ('taken');"

export function loadInstance() {
  if (!existsSync(INSTANCE_FILE)) {
    throw new Error('No .ppcs-instance.json. Start the disposable server with `pnpm run pg:up`.')
  }
  const file = JSON.parse(readFileSync(INSTANCE_FILE, 'utf8'))
  if (!file.token || !file.password) {
    throw new Error('The instance file has no token or password. Start the disposable server with `pnpm run pg:up`.')
  }
  return {
    token: file.token,
    host: file.host ?? '127.0.0.1',
    port: Number(file.port ?? 55435),
    user: file.user ?? 'postgres',
    password: file.password,
    image: file.image ?? null,
  }
}

function openClient(pg, settings, database, applicationName, { statementTimeout = false } = {}) {
  const client = new pg.Client({
    host: settings.host,
    port: settings.port,
    user: settings.user,
    password: settings.password,
    database,
    application_name: applicationName,
    connectionTimeoutMillis: 10000,
    query_timeout: 20000,
    ...(statementTimeout ? { statement_timeout: 15000 } : {}),
  })
  client.on('error', () => {})
  return client
}

export async function verifyInstance(pg, settings) {
  const client = openClient(pg, settings, 'postgres', 'ppcs-propagation-admin', { statementTimeout: true })
  try {
    await client.connect()
  } catch (e) {
    throw new Error(`Refusing to run: could not connect to the disposable instance at ${settings.host}:${settings.port}. Start it with \`pnpm run pg:up\`.`)
  }
  try {
    const row = (await client.query(`select current_setting('cluster_name') as name, version() as version,
      current_setting('server_version') as server_version, current_setting('server_version_num')::int as server_version_num`)).rows[0]
    if (row.name !== settings.token) {
      throw new Error(`Refusing to run: cluster_name at ${settings.host}:${settings.port} does not match the disposable instance token.`)
    }
    return {
      version: row.version,
      server_version: row.server_version,
      server_version_num: row.server_version_num,
      image: settings.image,
    }
  } finally {
    await client.end().catch(() => {})
  }
}

export async function withFreshDatabase(pg, settings, fn) {
  const admin = openClient(pg, settings, 'postgres', 'ppcs-propagation-admin', { statementTimeout: true })
  await admin.connect()
  const name = `ppcs_prop_${randomBytes(4).toString('hex')}`
  if (!/^ppcs_prop_[0-9a-f]{8}$/.test(name)) throw new Error('refusing an unexpected database name')
  await admin.query(`create database ${name}`)
  let failed = null
  let result
  try {
    result = await fn(name)
  } catch (e) {
    failed = e
  }
  try {
    await admin.query(`drop database ${name} with (force)`)
  } catch (e) {
    console.error(`drop database ${name} failed: ${String(e.message).split('\n')[0]}`)
  }
  await admin.end().catch(() => {})
  if (failed) throw failed
  return result
}

export function observerClient(pg, settings, database) {
  return openClient(pg, settings, database, 'ppcs-propagation-observer', { statementTimeout: true })
}

export function subjectClient(pg, settings, database, applicationName) {
  return openClient(pg, settings, database, applicationName)
}

export async function readOutcome(client, { xid, marker, pid }) {
  let fate = null
  if (typeof xid === 'string' && /^\d+$/.test(xid)) {
    const fateRow = await client.query('select pg_xact_status($1::xid8) as status', [xid])
    fate = fateRow.rows[0]?.status ?? null
  }
  const markerRow = await client.query('select exists(select 1 from item where name = $1) as visible', [marker])
  let session = null
  if (Number.isInteger(pid)) {
    const sessionRow = await client.query('select state, query from pg_stat_activity where pid = $1', [pid])
    session = sessionRow.rows[0] ?? null
  }
  return {
    fate,
    markerVisible: markerRow.rows[0]?.visible ?? null,
    sessionState: session?.state ?? null,
    sessionQuery: session?.query ? String(session.query).replace(/\s+/g, ' ').slice(0, 300) : null,
  }
}
