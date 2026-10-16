// Consistency of the catalog, its documentation and the adapter manifests. No database.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ROOT, loadAdapters, loadCatalog } from '../../lib/catalog.mjs'

const catalog = loadCatalog()
const ids = new Set(catalog.cases.map((c) => c.id))

test('every case is described in docs/specifications.md', () => {
  const doc = readFileSync(join(ROOT, 'docs/specifications.md'), 'utf8')
  for (const id of ids) assert.ok(doc.includes(`\`${id}\``), `${id} is missing from docs/specifications.md`)
  for (const [family, f] of Object.entries(catalog.families)) {
    assert.ok(doc.includes(`## ${family}`), `${family} has no section`)
    for (const inv of Object.keys(f.invariants)) assert.ok(doc.includes(`**${inv}**`), `${inv} is missing`)
  }
})

test('every case declares its fault, settings and checkpoints consistently', () => {
  for (const c of catalog.cases) {
    assert.ok(['none', 'A', 'B', 'C', 'D'].includes(c.fault.category), c.id)
    if (c.fault.category !== 'none') for (const k of ['mechanism', 'injection_point', 'expected_server', 'expected_client']) assert.ok(c.fault[k], `${c.id}: fault.${k}`)
    if (c.fault.category === 'B') assert.ok(Object.values(c.checkpoints).some((cp) => cp.action === 'terminate_backend'), `${c.id}: category B needs a terminate_backend checkpoint`)
    assert.ok(Number.isInteger(c.settings?.pool_max), `${c.id}: settings.pool_max`)
    assert.ok(Object.values(c.checkpoints).some((cp) => cp.captures), `${c.id}: no checkpoint captures a transaction ID`)
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
  }
})
