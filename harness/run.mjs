// PPCS runner.
//
//   node harness/run.mjs                                   every case on every adapter
//   node harness/run.mjs --adapter=lucid --case=TX-01A     filter by adapter, case ID prefix, or mode (comma-separated)
//   node harness/run.mjs --expect=reports/examples/<run>/run.json   also compare classifications with an earlier run
//   node harness/run.mjs --timeout=60000                   per-case limit in ms (default 60000)
//   node harness/run.mjs --repeat=3                        repetitions of every case (default 3); they must agree
//
// Needs the disposable server from `pnpm run pg:up`. Writes results/<run id>/ (or --out=<dir>/<run id>/).
//
// Exit codes:
//   0  the run completed. FAIL results are findings, not errors
//   1  the run completed, but --expect found classifications that differ from the earlier run
//   2  setup or safety failure; nothing ran (wrong server, no token, bad arguments, unknown adapter or case), or
//      --expect names a run made with a different harness or catalog, which cannot be compared
import { readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import { ROOT, harnessSha256, loadCatalog } from './lib/catalog.mjs'
import { SafetyError } from './lib/instance.mjs'
import { SetupError, compareWith, incomparable, runSuite } from './lib/suite.mjs'

const fail = (code, message) => { console.error(message); process.exit(code) }
const list = (v) => v.split(',').map((s) => s.trim()).filter(Boolean)

const options = { adapterFilter: [], caseFilter: [], modeFilter: [] }
let expectFile = null
for (const a of process.argv.slice(2)) {
  const [k, v = ''] = a.split(/=(.*)/s)
  if (k === '--adapter') options.adapterFilter = list(v)
  else if (k === '--case') options.caseFilter = list(v)
  else if (k === '--mode') options.modeFilter = list(v)
  else if (k === '--out') options.outDir = resolve(v)
  else if (k === '--timeout') options.timeoutMs = Number(v)
  else if (k === '--repeat') options.repetitions = Number(v)
  else if (k === '--expect') expectFile = resolve(v)
  else fail(2, `Unknown argument ${a}`)
}
if (options.timeoutMs !== undefined && !(options.timeoutMs > 0)) fail(2, '--timeout must be a positive number of milliseconds')
if (options.repetitions !== undefined && !(Number.isInteger(options.repetitions) && options.repetitions > 0)) fail(2, '--repeat must be a positive integer')
// An expected run made with a different harness or catalog is refused before anything runs.
const expected = expectFile ? JSON.parse(readFileSync(expectFile, 'utf8')) : null
if (expected) {
  const reasons = incomparable({ harness: { sha256: harnessSha256() }, catalog: { sha256: loadCatalog().sha256 } }, expected)
  if (reasons.length) fail(2, `Cannot compare with ${relative(ROOT, expectFile)}: ${reasons.join('; ')}.`)
}

let run
try {
  run = await runSuite({ ...options, log: (line) => console.log(line) })
} catch (e) {
  if (e instanceof SafetyError || e instanceof SetupError) fail(2, e.message)
  fail(2, String(e?.stack ?? e))
}
const { manifest, runDir } = run
console.log(`\n${Object.entries(manifest.counts).map(([k, n]) => `${k} ${n}`).join(', ')}`)
console.log(`Summary: ${relative(ROOT, runDir)}/summary.md`)

if (expected) {
  const diffs = compareWith(manifest, expected)
  if (diffs.length) {
    console.log(`\nDifferences from ${relative(ROOT, expectFile)}:\n${diffs.map((d) => `  ${d}`).join('\n')}`)
    process.exit(1)
  }
  console.log(`Classifications match ${relative(ROOT, expectFile)}.`)
}
process.exit(0)
