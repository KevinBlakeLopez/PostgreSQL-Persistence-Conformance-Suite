// Runs the production-reachability catalog. It does not load specifications/*.json, so the
// default suite's catalog digest and adapter manifests stay unchanged.
//
//   node research/production-reachability/run.mjs
//   node research/production-reachability/run.mjs --repeat=1 --adapter=pg,knex
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { ROOT, loadAdapters } from '../../harness/lib/catalog.mjs'
import { runSuite } from '../../harness/lib/suite.mjs'

const PR = [
  'PR-01.managed-catch-commit',
  'PR-01.explicit-catch-commit',
  'PR-01.uncaught-control',
  'PR-01.savepoint-recovery',
]
const WANTED = {
  lucid: ['native'],
  mikroorm: ['native'],
  typeorm: ['native'],
  sqlalchemy: ['native'],
  'sqlalchemy-core': ['native'],
  django: ['native'],
  'spring-jdbc': ['native', 'pooled'],
  'spring-tx': ['native', 'declarative', 'pooled'],
}

for (const bin of ['/opt/homebrew/opt/openjdk@21/bin', '/opt/homebrew/opt/openjdk/bin']) {
  if (existsSync(`${bin}/java`) && !process.env.PATH.split(':').includes(bin)) {
    process.env.PATH = `${bin}:${process.env.PATH}`
    process.env.JAVA_HOME = bin.slice(0, -'/bin'.length)
  }
}

const args = Object.fromEntries(process.argv.slice(2).map((arg) => {
  const [key, value = ''] = arg.replace(/^--/, '').split(/=(.*)/s)
  return [key, value]
}))
const repetitions = args.repeat ? Number(args.repeat) : 3
const only = args.adapter ? args.adapter.split(',').filter(Boolean) : null

function enable(adapter) {
  const modeIds = WANTED[adapter.name]
  if (!modeIds) return null
  const command = adapter.name === 'sqlalchemy-core'
    ? [resolve(ROOT, 'adapters/sqlalchemy/.venv/bin/python'), 'main.py']
    : adapter.command
  const modes = adapter.modes.filter((mode) => modeIds.includes(mode.id)).map((mode) => (
    mode.cases ? { ...mode, cases: [...new Set([...mode.cases, ...PR])] } : mode
  ))
  return { ...adapter, command, modes, expectations: {}, implements: [...new Set([...adapter.implements, ...PR])] }
}

const existing = loadAdapters().map(enable).filter(Boolean)
const drivers = loadAdapters(resolve(ROOT, 'research/production-reachability/drivers'))
const adapters = [...drivers, ...existing].filter((adapter) => !only || only.includes(adapter.name))

const { runDir, manifest } = await runSuite({
  catalogFile: 'research/production-reachability/catalog.json',
  adapters,
  caseFilter: args.case ? args.case.split(',').filter(Boolean) : [],
  outDir: resolve(ROOT, 'research/production-reachability/runs'),
  repetitions,
  log: (line) => console.log(line),
})
console.log(`\n${Object.entries(manifest.counts).map(([k, n]) => `${k} ${n}`).join(', ')}`)
console.log(runDir)
