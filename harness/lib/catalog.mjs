// Loads the specification catalog (specifications/*.json) and the adapter manifests (adapters/*/adapter.json), checks
// their structure, and computes the source digests that every result records.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const ROOT = fileURLToPath(new URL('../..', import.meta.url))
export const DEFAULT_CATALOG = 'specifications/transactions.v1.json'

export class CatalogError extends Error {}

/** What the runner can do at a checkpoint, besides observing (run-case.mjs). */
export const CHECKPOINT_ACTIONS = ['terminate_backend']

const sha256 = (data) => createHash('sha256').update(data).digest('hex')

/** SHA-256 over every file below `dirs` (sorted relative paths and contents), excluding node_modules. */
export function treeSha256(dirs) {
  const files = []
  const walk = (dir) => {
    for (const entry of readdirSync(dir).sort()) {
      if (entry === 'node_modules') continue
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) walk(full)
      else files.push(full)
    }
  }
  for (const d of dirs) walk(d)
  const h = createHash('sha256')
  for (const f of files.sort()) h.update(relative(ROOT, f)).update('\0').update(readFileSync(f)).update('\0')
  return h.digest('hex')
}

export function loadCatalog(file = DEFAULT_CATALOG) {
  const path = resolve(ROOT, file)
  const text = readFileSync(path, 'utf8')
  const catalog = JSON.parse(text)
  if (catalog.catalog !== 'ppcs-specifications/1') throw new CatalogError(`${file}: not a ppcs-specifications/1 catalog`)
  const statements = {}
  for (const family of Object.values(catalog.families)) Object.assign(statements, family.invariants)
  const ids = new Set()
  for (const c of catalog.cases) {
    if (ids.has(c.id)) throw new CatalogError(`${file}: duplicate case ID ${c.id}`)
    ids.add(c.id)
    if (!catalog.families[c.family]) throw new CatalogError(`${c.id}: unknown family ${c.family}`)
    for (const i of c.invariants) if (!statements[i]) throw new CatalogError(`${c.id}: unknown invariant ${i}`)
    if (!Array.isArray(c.markers) || !c.markers.length) throw new CatalogError(`${c.id}: no markers`)
    for (const [name, cp] of Object.entries(c.checkpoints ?? {})) {
      if (cp.action && !CHECKPOINT_ACTIONS.includes(cp.action)) throw new CatalogError(`${c.id}: checkpoint "${name}" has unknown action "${cp.action}"`)
    }
  }
  return { ...catalog, path: relative(ROOT, path), sha256: sha256(text), statements }
}

export const MODE_KINDS = ['native', 'recommended', 'configured', 'hardened', 'control', 'fixture']

export function loadAdapters(base = join(ROOT, 'adapters')) {
  const adapters = []
  for (const name of readdirSync(base).sort()) {
    const manifestPath = join(base, name, 'adapter.json')
    if (!existsSync(manifestPath)) continue
    const m = JSON.parse(readFileSync(manifestPath, 'utf8'))
    const where = relative(ROOT, manifestPath)
    if (m.manifest !== 'ppcs-adapter/1') throw new CatalogError(`${where}: not a ppcs-adapter/1 manifest`)
    if (m.name !== name) throw new CatalogError(`${where}: name "${m.name}" does not match its directory`)
    if (!Array.isArray(m.command) || !m.command.length) throw new CatalogError(`${where}: command must be a non-empty array`)
    if (!Array.isArray(m.modes) || !m.modes.length) throw new CatalogError(`${where}: needs at least one mode`)
    for (const mode of m.modes) if (!mode.id || !MODE_KINDS.includes(mode.kind)) throw new CatalogError(`${where}: mode "${mode.id}" needs a kind among ${MODE_KINDS.join(', ')}`)
    const dir = join(base, name)
    const shared = (m.shared ?? []).map((p) => resolve(dir, p))
    adapters.push({ ...m, dir, manifestPath: where, sourceSha256: treeSha256([dir, ...shared]) })
  }
  return adapters
}

/**
 * The cases to run, as { adapter, mode, kase, plan } where plan is 'run', 'unsupported' or 'not-run'.
 * - A case the adapter declares unsupported, or does not implement, appears once, under the adapter's first mode.
 * - An implemented case runs in every mode that applies to it: a mode that lists cases applies only to those.
 */
export function plan(catalog, adapters, { adapterFilter = [], caseFilter = [], modeFilter = [] } = {}) {
  const items = []
  const matchCase = (id) => !caseFilter.length || caseFilter.some((f) => id.startsWith(f)) // "TX-01" selects TX-01A.* and TX-01B.*
  for (const adapter of adapters) {
    if (adapterFilter.length && !adapterFilter.includes(adapter.name)) continue
    const modes = adapter.modes.filter((m) => !modeFilter.length || modeFilter.includes(m.id))
    if (!modes.length) continue
    for (const kase of catalog.cases) {
      if (!matchCase(kase.id)) continue
      if (adapter.unsupported?.[kase.id]) { items.push({ adapter, mode: modes[0], kase, plan: 'unsupported', reason: adapter.unsupported[kase.id] }); continue }
      if (!adapter.implements?.includes(kase.id)) { items.push({ adapter, mode: modes[0], kase, plan: 'not-run', reason: 'the adapter does not implement this case' }); continue }
      for (const mode of modes) if (!mode.cases || mode.cases.includes(kase.id)) items.push({ adapter, mode, kase, plan: 'run' })
    }
  }
  return items
}
