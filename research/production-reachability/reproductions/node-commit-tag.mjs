// Standalone reproduction of a caught unique violation followed by COMMIT.
// Uses the disposable PPCS PostgreSQL and the knex/kysely copies already installed
// for the Lucid and MikroORM adapters. It does not import the PPCS harness.
//
//   node research/production-reachability/reproductions/node-commit-tag.mjs
import { createRequire } from 'node:module'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomBytes } from 'node:crypto'

const root = fileURLToPath(new URL('../../..', import.meta.url))
const pg = createRequire(join(root, 'package.json'))('pg')
const instance = JSON.parse(readFileSync(join(root, '.ppcs-instance.json'), 'utf8'))
const knexRoot = join(root, 'adapters/lucid/node_modules/.pnpm')
const knexDir = readdirSync(knexRoot).find((name) => name.startsWith('knex@'))
const knexPkg = join(knexRoot, knexDir, 'node_modules/knex')
const knex = createRequire(join(knexPkg, 'package.json'))(join(knexPkg, 'knex.js'))
const kyselyRoot = join(root, 'adapters/mikroorm/node_modules/.pnpm')
const kyselyDir = readdirSync(kyselyRoot).find((name) => name.startsWith('kysely@'))
const kyselyPkg = join(kyselyRoot, kyselyDir, 'node_modules/kysely')
const { Kysely, PostgresDialect, sql } = await import(pathToFileURL(join(kyselyPkg, 'dist/index.js')).href)

const adminConfig = {
  host: instance.host ?? '127.0.0.1',
  port: instance.port ?? 55435,
  user: instance.user ?? 'postgres',
  password: instance.password,
  database: 'postgres',
}

async function withDatabase(fn) {
  const admin = new pg.Client(adminConfig)
  await admin.connect()
  const name = `ppcs_repro_${randomBytes(4).toString('hex')}`
  await admin.query(`create database ${name}`)
  try {
    return await fn({ ...adminConfig, database: name })
  } finally {
    await admin.query(`drop database ${name} with (force)`)
    await admin.end()
  }
}

async function setup(client) {
  await client.query('create table item (id serial primary key, name text not null)')
  await client.query('create table uniq (id serial primary key, code text not null unique)')
  await client.query("insert into uniq (code) values ('taken')")
}

async function visible(client) {
  const { rows } = await client.query('select name from item order by id')
  return rows.map((row) => row.name)
}

const report = []

await withDatabase(async (config) => {
  const client = new pg.Client(config)
  client.on('error', () => {})
  await client.connect()
  await setup(client)
  await client.query('begin')
  await client.query("insert into item (name) values ('kept')")
  let code = null
  try { await client.query("insert into uniq (code) values ('taken')") } catch (e) { code = e.code }
  const reply = await client.query('COMMIT')
  report.push({ api: 'pg Client.query', sqlstate: code, command_tag: reply.command, query_threw: false, visible: await visible(client) })
  await client.end()
})

await withDatabase(async (config) => {
  const db = knex({ client: 'pg', connection: config })
  const probe = new pg.Client(config)
  await probe.connect()
  await setup(probe)
  let code = null
  let threw = false
  try {
    await db.transaction(async (trx) => {
      await trx('item').insert({ name: 'kept' })
      try { await trx('uniq').insert({ code: 'taken' }) } catch (e) { code = e.code }
    })
  } catch (e) { threw = true; code = code ?? e.code }
  report.push({ api: 'knex.transaction(callback)', version: JSON.parse(readFileSync(join(knexPkg, 'package.json'), 'utf8')).version, sqlstate: code, callback_resolved: !threw, visible: await visible(probe) })
  await probe.end()
  await db.destroy()
})

await withDatabase(async (config) => {
  const pool = new pg.Pool(config)
  const db = new Kysely({ dialect: new PostgresDialect({ pool }) })
  const probe = new pg.Client(config)
  await probe.connect()
  await setup(probe)
  const trx = await db.startTransaction().execute()
  let code = null
  await trx.insertInto('item').values({ name: 'kept' }).execute()
  try { await trx.insertInto('uniq').values({ code: 'taken' }).execute() } catch (e) { code = e.code }
  let commitThrew = false
  try { await trx.commit().execute() } catch (e) { commitThrew = true }
  report.push({
    api: 'kysely ControlledTransaction.commit()',
    version: JSON.parse(readFileSync(join(kyselyPkg, 'package.json'), 'utf8')).version,
    sqlstate: code,
    commit_threw: commitThrew,
    isCommitted: trx.isCommitted,
    visible: await visible(probe),
  })
  await probe.end()
  await db.destroy()
})

console.log(JSON.stringify(report, null, 2))
