// Runs the MySQL 8.4 / InnoDB baseline and writes evidence/*.json.
// This does not start a PPCS adapter and does not classify PPCS cases.

import { mkdirSync, writeFileSync } from 'node:fs'
import {
  MYSQL2_VERSION,
  assertNoSecrets,
  closeClient,
  collectServerConfig,
  loadInstance,
  openClient,
  plain,
  publicOptions,
  connectionOptions,
  requireToken,
} from './lib.mjs'
import { mpcs01 } from './mpcs-01.mjs'
import { mpcs02 } from './mpcs-02.mjs'
import { mpcs03 } from './mpcs-03.mjs'
import { mpcs04 } from './mpcs-04.mjs'
import { mpcs05 } from './mpcs-05.mjs'
import { probes } from './probes.mjs'

const evidenceDir = new URL('../evidence/', import.meta.url)
const instance = loadInstance()
const secrets = [instance.password, instance.root_password]
const failures = []

const rootDefault = await openClient(instance, instance.default, 'root', 'root')
const observerDefault = await openClient(instance, instance.default, 'observer', 'root')
const rootOn = await openClient(instance, instance.rollback_on_timeout, 'root-on', 'root')
const observerOn = await openClient(instance, instance.rollback_on_timeout, 'observer-on', 'root')

try {
  await requireToken(rootDefault.conn, instance.token)
  await requireToken(rootOn.conn, instance.token)
  const configDefault = await collectServerConfig(rootDefault.conn, { probeDynamic: true })
  const configOn = await collectServerConfig(rootOn.conn, { probeDynamic: false })
  if (Number(configDefault.variables.innodb_rollback_on_timeout) !== 0 && configDefault.variables.innodb_rollback_on_timeout !== 'OFF') {
    throw new Error(`Default server innodb_rollback_on_timeout is ${configDefault.variables.innodb_rollback_on_timeout}, expected OFF.`)
  }
  if (Number(configOn.variables.innodb_rollback_on_timeout) !== 1 && configOn.variables.innodb_rollback_on_timeout !== 'ON') {
    throw new Error(`Rollback-on-timeout server innodb_rollback_on_timeout is ${configOn.variables.innodb_rollback_on_timeout}, expected ON.`)
  }
  writeJson('server-config.json', {
    captured_at: new Date().toISOString(),
    node: process.version,
    mysql2: MYSQL2_VERSION,
    image: instance.image,
    image_id: instance.image_id,
    token: instance.token,
    connection_options: publicOptions(connectionOptions(instance, instance.default, 'app')),
    default_server: { endpoint: instance.default, ...configDefault },
    rollback_on_timeout_server: { endpoint: instance.rollback_on_timeout, ...configOn },
  })

  const ctx = makeCtx(instance.default, rootDefault, observerDefault)
  await run('mpcs-01.json', () => mpcs01(ctx))
  await run('mpcs-02.json', () => mpcs02(ctx))
  await run('mpcs-03.json', async () => ({
    experiment: 'MPCS-03',
    title: 'Lock wait timeout, default rollback scope and innodb_rollback_on_timeout ON',
    variants: [
      await mpcs03(ctx, { schema: 'mpcs03_default_timeout', variant: 'default-timeout-rollback-off', sessionLockWaitTimeout: null }),
      await mpcs03(ctx, { schema: 'mpcs03_short_timeout', variant: 'session-timeout-2s-rollback-off', sessionLockWaitTimeout: 2 }),
      await mpcs03(makeCtx(instance.rollback_on_timeout, rootOn, observerOn), {
        schema: 'mpcs03_rollback_on',
        variant: 'session-timeout-2s-rollback-on',
        sessionLockWaitTimeout: 2,
      }),
    ],
  }))
  await run('mpcs-04.json', () => mpcs04(ctx))
  await run('mpcs-05.json', () => mpcs05(ctx))
  await run('probes.json', () => probes(ctx))
} finally {
  await closeClient(rootDefault)
  await closeClient(observerDefault)
  await closeClient(rootOn)
  await closeClient(observerOn)
}

writeJson('run.json', {
  finished_at: new Date().toISOString(),
  node: process.version,
  mysql2: MYSQL2_VERSION,
  image: instance.image,
  failures,
  evidence: [
    'server-config.json',
    'mpcs-01.json',
    'mpcs-02.json',
    'mpcs-03.json',
    'mpcs-04.json',
    'mpcs-05.json',
    'probes.json',
  ],
})

if (failures.length) {
  console.error(`Baseline finished with ${failures.length} failed experiment(s).`)
  process.exit(1)
}
console.error('Baseline finished.')

function makeCtx(endpoint, root, observer) {
  return {
    instance,
    endpoint,
    root,
    observer,
    open(role) { return openClient(instance, endpoint, role, 'app') },
  }
}

async function run(file, fn) {
  const started = new Date().toISOString()
  console.error(`running ${file}`)
  try {
    const body = await fn()
    writeJson(file, { started_at: started, finished_at: new Date().toISOString(), ok: true, ...plain(body) })
  } catch (error) {
    failures.push({ file, message: String(error?.message ?? error) })
    writeJson(file, {
      started_at: started,
      finished_at: new Date().toISOString(),
      ok: false,
      error: { message: String(error?.message ?? error), stack: String(error?.stack ?? '') },
    })
    console.error(`failed ${file}: ${error?.message ?? error}`)
  }
}

function writeJson(name, value) {
  const text = `${JSON.stringify(value, null, 2)}\n`
  assertNoSecrets(text, secrets)
  mkdirSync(evidenceDir, { recursive: true })
  writeFileSync(new URL(name, evidenceDir), text)
  console.error(`wrote ${name}`)
}
