// Loads the specification catalog (specifications/*.json) and the adapter manifests (adapters/*/adapter.json), checks
// their structure, computes the source digests that every result records, and plans which cases run.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const ROOT = fileURLToPath(new URL('../..', import.meta.url))
export const DEFAULT_CATALOG = 'specifications/transactions.v1.json'
/** The family whose cases gate every other result of the same adapter and mode (suite.mjs). */
export const CONTROL_FAMILY = 'CTL-01'

export class CatalogError extends Error {}

/** What the runner can do at a checkpoint, besides observing (run-case.mjs). */
export const CHECKPOINT_ACTIONS = ['terminate_backend']
/** The checkpoint every case has implicitly: the adapter sends it as soon as the framework's API has returned. */
export const IMPLICIT_CHECKPOINT = 'after-end'
/** What a withheld top-level ROLLBACK must have left on the server (TX-03): an open transaction, or an aborted block. */
export const FAULT_SIGNATURES = ['open-block', 'aborted-block']
export const UNSUPPORTED_CLASSES = ['capability-absent', 'not-applicable-by-design']

const sha256 = (data) => createHash('sha256').update(data).digest('hex')

/** SHA-256 over every file below `paths` (files or directories; sorted relative paths and contents), excluding node_modules. */
export function treeSha256(paths) {
  const files = []
  const walk = (p) => {
    if (statSync(p).isFile()) { files.push(p); return }
    for (const entry of readdirSync(p).sort()) {
      if (entry === 'node_modules') continue
      walk(join(p, entry))
    }
  }
  for (const p of paths) walk(p)
  const h = createHash('sha256')
  for (const f of files.sort()) h.update(relative(ROOT, f)).update('\0').update(readFileSync(f)).update('\0')
  return h.digest('hex')
}

/** The digest of the code that observes and classifies: the runner and its library, not its tests. */
export const harnessSha256 = () => treeSha256([join(ROOT, 'harness', 'lib'), join(ROOT, 'harness', 'run.mjs')])

/** One catalog file. A path other than the default is loaded alone, so a test can hand the loader a rewritten copy. */
function loadOne(file) {
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
    const checkpoints = c.checkpoints ?? {}
    if (checkpoints[IMPLICIT_CHECKPOINT]) throw new CatalogError(`${c.id}: "${IMPLICIT_CHECKPOINT}" is implicit in every case and must not be declared`)
    for (const [name, cp] of Object.entries(checkpoints)) {
      if (cp.action && !CHECKPOINT_ACTIONS.includes(cp.action)) throw new CatalogError(`${c.id}: checkpoint "${name}" has unknown action "${cp.action}"`)
      // PostgreSQL's report of the isolation level is read in the same statement as the captured ID (TX-05).
      if (cp.captures_isolation !== undefined && (typeof cp.captures_isolation !== 'boolean' || !cp.captures)) throw new CatalogError(`${c.id}: checkpoint "${name}" declares captures_isolation, which must be a boolean on a checkpoint that captures a transaction`)
    }
    if (c.fault?.signature !== undefined && !FAULT_SIGNATURES.includes(c.fault.signature)) throw new CatalogError(`${c.id}: unknown fault signature "${c.fault.signature}"`)
    const captured = new Set(Object.values(checkpoints).map((cp) => cp.captures).filter(Boolean))
    const writes = c.marker_writes ?? {}
    if (Object.keys(writes).sort().join() !== [...c.markers].sort().join()) throw new CatalogError(`${c.id}: marker_writes must describe exactly the markers`)
    for (const [marker, w] of Object.entries(writes)) {
      if (!['top', 'savepoint'].includes(w.level)) throw new CatalogError(`${c.id}: marker "${marker}" has level "${w.level}"`)
      if (w.sent !== 'possibly-pending' && !checkpoints[w.sent]) throw new CatalogError(`${c.id}: marker "${marker}" is confirmed at undeclared checkpoint "${w.sent}"`)
      if (w.sent !== 'possibly-pending' && !captured.has(w.transaction)) throw new CatalogError(`${c.id}: marker "${marker}" is written by "${w.transaction}", which no checkpoint captures`)
    }
  }
  return { ...catalog, path: relative(ROOT, path), sha256: sha256(text), statements, text }
}

/**
 * The default catalog is every file in specifications/, transaction families first. A migration case counts marker
 * rows after the run, so its writes are possibly-pending: any runner may insert them. The fixture is the transaction
 * catalog's. A migration case creates its own extra tables.
 */
function loadMerged() {
  const dir = join(ROOT, 'specifications')
  const files = readdirSync(dir).filter((f) => f.endsWith('.json')).sort()
  const ordered = [...files.filter((f) => f.startsWith('transactions')), ...files.filter((f) => !f.startsWith('transactions'))]
  const parts = ordered.map((f) => loadOne(join('specifications', f)))
  const families = {}
  const cases = []
  const ids = new Set()
  for (const part of parts) {
    for (const [id, family] of Object.entries(part.families)) {
      if (families[id]) throw new CatalogError(`family ${id} is declared in more than one catalog`)
      families[id] = family
    }
    for (const c of part.cases) {
      if (ids.has(c.id)) throw new CatalogError(`duplicate case ID ${c.id}`)
      ids.add(c.id)
      cases.push(c)
    }
  }
  const statements = {}
  for (const family of Object.values(families)) Object.assign(statements, family.invariants)
  const fixture = parts.find((p) => p.fixture)?.fixture
  return { catalog: 'ppcs-specifications/1', fixture, families, cases, path: 'specifications', sha256: sha256(parts.map((p) => p.text).join('\n')), statements }
}

export function loadCatalog(file = DEFAULT_CATALOG) {
  if (resolve(ROOT, file) === resolve(ROOT, DEFAULT_CATALOG)) return loadMerged()
  const one = loadOne(file)
  delete one.text
  return one
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
    // RECOMMENDED claims that the framework's documentation recommends the mode for the pattern, so it must cite it.
    for (const mode of m.modes) if (mode.kind === 'recommended' && !mode.documentation) throw new CatalogError(`${where}: mode "${mode.id}" is of kind recommended, so it must cite the framework's documentation (documentation)`)
    // An UNSUPPORTED declaration states why: the capability is absent from the supported API, or the hazard the case
    // targets cannot arise by the framework's design (for example, no deferred writes).
    const unsupported = Object.fromEntries(Object.entries(m.unsupported ?? {}).map(([id, u]) => [id, typeof u === 'string' ? { reason: u, class: 'capability-absent' } : u]))
    for (const [id, u] of Object.entries(unsupported)) if (!UNSUPPORTED_CLASSES.includes(u.class) || !u.reason) throw new CatalogError(`${where}: unsupported ${id} needs a reason and a class among ${UNSUPPORTED_CLASSES.join(', ')}`)
    if (m.rollback_claim_channels && !Array.isArray(m.rollback_claim_channels)) throw new CatalogError(`${where}: rollback_claim_channels must be an array`)
    // A control adapter states the classification it expects in each mode, per case; suite.mjs checks them in every run.
    for (const [id, byMode] of Object.entries(m.expectations ?? {})) {
      if (!m.implements?.includes(id)) throw new CatalogError(`${where}: an expectation for ${id}, which the adapter does not implement`)
      for (const [modeId, cls] of Object.entries(byMode)) {
        if (!m.modes.some((x) => x.id === modeId)) throw new CatalogError(`${where}: an expectation for unknown mode "${modeId}" in ${id}`)
        if (!['PASS', 'FAIL'].includes(cls)) throw new CatalogError(`${where}: the expectation for ${id} in mode "${modeId}" must be PASS or FAIL`)
      }
    }
    const dir = join(base, name)
    const shared = (m.shared ?? []).map((p) => resolve(dir, p))
    adapters.push({ ...m, unsupported, rollback_claim_channels: m.rollback_claim_channels ?? [], dir, manifestPath: where, sourceSha256: treeSha256([dir, ...shared]) })
  }
  return adapters
}

export const isControlAdapter = (adapter) => adapter.modes.every((m) => m.kind === 'control')

/**
 * The cases to run, as { adapter, mode, kase, plan, auto } where plan is 'run', 'unsupported' or 'not-run'.
 * - A case the adapter declares unsupported, or does not implement, appears once, under the adapter's first mode.
 * - An implemented case runs in every mode that applies to it: a mode that lists cases applies only to those, plus the
 *   observation controls.
 * - Controls always run with what they gate (`auto: true` when the filters did not select them): the CTL-01 cases of
 *   every selected adapter and mode, and the control adapters, in all their modes, on every selected scenario case.
 *   A mode filter applies to a control adapter only when it is selected by name.
 */
export function plan(catalog, adapters, { adapterFilter = [], caseFilter = [], modeFilter = [] } = {}) {
  const items = []
  const ctlIds = catalog.cases.filter((c) => c.family === CONTROL_FAMILY).map((c) => c.id)
  const matchCase = (id) => !caseFilter.length || caseFilter.some((f) => id.startsWith(f)) // "TX-01" selects TX-01A.* and TX-01B.*
  const scenarios = catalog.cases.filter((c) => c.family !== CONTROL_FAMILY && matchCase(c.id)).map((c) => c.id)
  for (const adapter of adapters) {
    const named = adapterFilter.includes(adapter.name)
    const selected = !adapterFilter.length || named
    const control = isControlAdapter(adapter)
    const asControl = !selected && control && scenarios.length > 0
    if (!selected && !asControl) continue
    const modes = adapter.modes.filter((m) => (control && !named) || !modeFilter.length || modeFilter.includes(m.id))
    if (!modes.length) continue
    for (const kase of catalog.cases) {
      const wanted = asControl ? scenarios.includes(kase.id) || ctlIds.includes(kase.id) : matchCase(kase.id) || (scenarios.length > 0 && ctlIds.includes(kase.id))
      if (!wanted) continue
      const auto = asControl || !matchCase(kase.id)
      const unsupported = adapter.unsupported?.[kase.id]
      if (unsupported) { if (!asControl) items.push({ adapter, mode: modes[0], kase, plan: 'unsupported', reason: unsupported.reason, unsupportedClass: unsupported.class, auto }); continue }
      if (!adapter.implements?.includes(kase.id)) { if (!auto) items.push({ adapter, mode: modes[0], kase, plan: 'not-run', reason: 'the adapter does not implement this case', auto }); continue }
      for (const mode of modes) if (!mode.cases || mode.cases.includes(kase.id) || ctlIds.includes(kase.id)) items.push({ adapter, mode, kase, plan: 'run', auto })
    }
  }
  return items
}
