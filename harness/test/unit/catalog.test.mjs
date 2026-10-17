// Consistency of the catalog, its documentation and the adapter manifests. No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { CatalogError, DEFAULT_CATALOG, ROOT, loadAdapters, loadCatalog } from '../../lib/catalog.mjs'

const catalog = loadCatalog()
const ids = new Set(catalog.cases.map((c) => c.id))
const scratch = () => mkdtempSync(join(tmpdir(), 'ppcs-catalog-test-'))

test('every case is described in docs/specifications.md', () => {
  const doc = readFileSync(join(ROOT, 'docs/specifications.md'), 'utf8')
  for (const id of ids) assert.ok(doc.includes(`\`${id}\``), `${id} is missing from docs/specifications.md`)
  for (const [family, f] of Object.entries(catalog.families)) {
    assert.ok(doc.includes(`## ${family}`), `${family} has no section`)
    for (const inv of Object.keys(f.invariants)) assert.ok(doc.includes(`**${inv}**`), `${inv} is missing`)
  }
})

test('every case declares its fault, settings, checkpoints and writes consistently', () => {
  for (const c of catalog.cases) {
    assert.ok(['none', 'A', 'B', 'C', 'D'].includes(c.fault.category), c.id)
    if (c.fault.category !== 'none') for (const k of ['mechanism', 'injection_point', 'expected_server', 'expected_client']) assert.ok(c.fault[k], `${c.id}: fault.${k}`)
    if (c.fault.category === 'B') assert.ok(Object.values(c.checkpoints).some((cp) => cp.action === 'terminate_backend'), `${c.id}: category B needs a terminate_backend checkpoint`)
    assert.ok(Number.isInteger(c.settings?.pool_max), `${c.id}: settings.pool_max`)
    assert.ok(Object.values(c.checkpoints).some((cp) => cp.captures), `${c.id}: no checkpoint captures a transaction ID`)
    assert.ok(c.steps.at(-1).startsWith('Checkpoint `after-end`'), `${c.id}: the steps end with the implicit after-end checkpoint`)
  }
})

test('adapter manifests reference only catalog cases, and modes only implemented ones', () => {
  for (const a of [...loadAdapters(), ...loadAdapters(join(ROOT, 'harness/test/fixtures/adapters'))]) {
    for (const id of a.implements) assert.ok(ids.has(id), `${a.name} implements unknown case ${id}`)
    for (const id of Object.keys(a.unsupported ?? {})) {
      assert.ok(ids.has(id), `${a.name} declares unknown case ${id} unsupported`)
      assert.ok(!a.implements.includes(id), `${a.name}: ${id} is both implemented and unsupported`)
      assert.ok(a.unsupported[id].length > 20, `${a.name}: ${id} needs a reason`)
    }
    for (const m of a.modes) for (const id of m.cases ?? []) assert.ok(a.implements.includes(id), `${a.name} mode ${m.id} lists ${id}, which it does not implement`)
    assert.ok(Array.isArray(a.rollback_claim_channels), `${a.name}: rollback_claim_channels`)
  }
})

test('the control adapter states an expectation for every case it implements, in every mode', () => {
  const pg = loadAdapters().find((a) => a.name === 'pg-control')
  for (const id of pg.implements) for (const m of pg.modes) assert.ok(['PASS', 'FAIL'].includes(pg.expectations[id]?.[m.id]), `pg-control: ${id} in ${m.id}`)
})

/** Writes a copy of the catalog with `change` applied, and loads it. */
function loadChanged(change) {
  const dir = scratch()
  try {
    const c = JSON.parse(readFileSync(join(ROOT, DEFAULT_CATALOG), 'utf8'))
    change(c)
    const file = join(dir, 'catalog.json')
    writeFileSync(file, JSON.stringify(c))
    return loadCatalog(file)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}
const caseOf = (c, id) => c.cases.find((k) => k.id === id)

test('the catalog refuses marker writes it cannot confirm, and a declared after-end', () => {
  assert.throws(() => loadChanged((c) => { delete caseOf(c, 'CTL-01.commit').marker_writes.tx }), CatalogError)
  assert.throws(() => loadChanged((c) => { caseOf(c, 'CTL-01.commit').marker_writes.tx.level = 'nested' }), /level "nested"/)
  assert.throws(() => loadChanged((c) => { caseOf(c, 'CTL-01.commit').marker_writes.tx.sent = 'nowhere' }), /undeclared checkpoint "nowhere"/)
  assert.throws(() => loadChanged((c) => { caseOf(c, 'CTL-01.commit').marker_writes.tx.transaction = 'other' }), /which no checkpoint captures/)
  assert.throws(() => loadChanged((c) => { caseOf(c, 'CTL-01.commit').checkpoints['after-end'] = {} }), /implicit in every case/)
  assert.doesNotThrow(() => loadChanged(() => {}))
})

/** Loads a single adapter manifest from a scratch directory. */
function loadManifest(manifest) {
  const dir = scratch()
  try {
    mkdirSync(join(dir, manifest.name))
    writeFileSync(join(dir, manifest.name, 'adapter.json'), JSON.stringify(manifest))
    return loadAdapters(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}
const MANIFEST = { manifest: 'ppcs-adapter/1', name: 'probe', command: ['node', 'main.mjs'], modes: [{ id: 'native', kind: 'native', description: 'd' }], implements: ['CTL-01.commit'] }

test('manifests: malformed expectations are refused', () => {
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'TX-01A.caught-error-then-commit': { native: 'PASS' } } }), /does not implement/)
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'CTL-01.commit': { other: 'PASS' } } }), /unknown mode "other"/)
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'CTL-01.commit': { native: 'MAYBE' } } }), /must be PASS or FAIL/)
  assert.doesNotThrow(() => loadManifest({ ...MANIFEST, expectations: { 'CTL-01.commit': { native: 'PASS' } } }))
})
