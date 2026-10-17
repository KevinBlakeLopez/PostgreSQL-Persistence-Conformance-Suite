// Consistency of the catalog, its documentation and the adapter manifests, the plan's controls, and the harness
// digest. No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { CatalogError, DEFAULT_CATALOG, ROOT, UNSUPPORTED_CLASSES, loadAdapters, loadCatalog, plan, treeSha256 } from '../../lib/catalog.mjs'

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

test('adapter manifests reference only catalog cases, and say why a case is unsupported', () => {
  for (const a of [...loadAdapters(), ...loadAdapters(join(ROOT, 'harness/test/fixtures/adapters'))]) {
    for (const id of a.implements) assert.ok(ids.has(id), `${a.name} implements unknown case ${id}`)
    for (const [id, u] of Object.entries(a.unsupported ?? {})) {
      assert.ok(ids.has(id), `${a.name} declares unknown case ${id} unsupported`)
      assert.ok(!a.implements.includes(id), `${a.name}: ${id} is both implemented and unsupported`)
      assert.ok(u.reason.length > 20, `${a.name}: ${id} needs a reason`)
      assert.ok(UNSUPPORTED_CLASSES.includes(u.class), `${a.name}: ${id} needs a class`)
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

test('manifests: a reasonless unsupported case, an uncited RECOMMENDED mode, and malformed expectations are refused', () => {
  assert.equal(loadManifest({ ...MANIFEST, unsupported: { 'TX-04.independent-inner': 'a reason long enough to be a reason' } })[0].unsupported['TX-04.independent-inner'].class, 'capability-absent')
  assert.throws(() => loadManifest({ ...MANIFEST, unsupported: { 'TX-04.independent-inner': { class: 'impossible', reason: 'a reason' } } }), /needs a reason and a class/)
  assert.throws(() => loadManifest({ ...MANIFEST, modes: [{ id: 'rec', kind: 'recommended', description: 'd' }] }), /must cite the framework's documentation/)
  assert.doesNotThrow(() => loadManifest({ ...MANIFEST, modes: [{ id: 'rec', kind: 'recommended', description: 'd', documentation: 'https://example.org/docs' }] }))
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'TX-01A.caught-error-then-commit': { native: 'PASS' } } }), /does not implement/)
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'CTL-01.commit': { other: 'PASS' } } }), /unknown mode "other"/)
  assert.throws(() => loadManifest({ ...MANIFEST, expectations: { 'CTL-01.commit': { native: 'MAYBE' } } }), /must be PASS or FAIL/)
})

const planned = (filters) => plan(catalog, loadAdapters(), filters).map((i) => `${i.adapter.name}/${i.mode.id} ${i.kase.id} ${i.plan}${i.auto ? ' auto' : ''}`)

test('plan: the observation controls run in every selected mode, including modes that list their cases', () => {
  const items = planned({ adapterFilter: ['lucid'], caseFilter: ['TX-01A'] })
  for (const mode of ['native', 'pre-commit-probe']) for (const id of ['CTL-01.commit', 'CTL-01.rollback']) assert.ok(items.includes(`lucid/${mode} ${id} run auto`), `${mode} ${id}`)
})

test('plan: the control adapter runs in all its modes beside the selected scenarios, without a mode filter of its own', () => {
  const items = planned({ adapterFilter: ['typeorm'], caseFilter: ['TX-02.savepoint-rollback-not-sent'], modeFilter: ['native'] })
  for (const mode of ['correct', 'unsafe']) {
    assert.ok(items.includes(`pg-control/${mode} TX-02.savepoint-rollback-not-sent run auto`), mode)
    assert.ok(items.includes(`pg-control/${mode} CTL-01.commit run auto`), mode)
  }
  assert.ok(!items.some((i) => i.includes('TX-04.independent-inner')), 'an auto-included control adds no unsupported entries')
  assert.ok(items.includes('typeorm/native TX-02.savepoint-rollback-not-sent run'))
})

test('the harness digest changes when the code that classifies changes', () => {
  const dir = scratch()
  try {
    cpSync(join(ROOT, 'harness', 'lib'), join(dir, 'lib'), { recursive: true })
    const before = treeSha256([join(dir, 'lib')])
    assert.equal(treeSha256([join(dir, 'lib')]), before, 'deterministic')
    writeFileSync(join(dir, 'lib', 'classify.mjs'), `${readFileSync(join(dir, 'lib', 'classify.mjs'), 'utf8')}\n// changed\n`)
    assert.notEqual(treeSha256([join(dir, 'lib')]), before)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
