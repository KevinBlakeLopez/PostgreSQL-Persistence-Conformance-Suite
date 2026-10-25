// Regenerates summary.md from a propagation run directory.
//
//   node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/<id>
import { readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { renderReport } from './lib/report.mjs'

const dirArg = process.argv[2]
if (!dirArg) {
  console.error('usage: node research/transaction-outcome-propagation/report.mjs <run-directory>')
  process.exit(1)
}
const dir = resolve(dirArg)
const run = JSON.parse(readFileSync(join(dir, 'run.json'), 'utf8'))
const records = run.records.map((file) => JSON.parse(readFileSync(join(dir, file), 'utf8')))
const capability = JSON.parse(readFileSync(join(dir, run.capability), 'utf8'))
const markdown = renderReport({ run, records, capability })
writeFileSync(join(dir, 'summary.md'), markdown)
console.log(join(dir, 'summary.md'))
