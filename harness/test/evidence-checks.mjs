// Checks applied to every run directory the methodology tests produce: each file conforms to its schema, and no file
// contains the instance password.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import Ajv2020 from 'ajv/dist/2020.js'
import { ROOT } from '../lib/catalog.mjs'
import { loadSettings } from '../lib/instance.mjs'

const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true })
const load = (file) => ajv.compile(JSON.parse(readFileSync(join(ROOT, 'schema', file), 'utf8')))
const validators = { result: load('result.v1.schema.json'), run: load('run.v1.schema.json') }

/** Validates one result record; returns the list of schema errors (empty when valid). */
export function resultErrors(record) {
  return validators.result(record) ? [] : validators.result.errors.map((e) => `${e.instancePath || '/'} ${e.message}`)
}

const describe = (errors) => errors.map((e) => `${e.instancePath || '/'} ${e.message}`).join('; ')

/** Every problem found in `runDir`: schema violations, and any file that contains the password. */
export function checkRunDir(runDir) {
  const problems = []
  const password = loadSettings().password
  const files = []
  const walk = (d) => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p); else files.push(p) } }
  walk(runDir)
  for (const file of files) {
    const text = readFileSync(file, 'utf8')
    if (password && text.includes(password)) problems.push(`${file} contains the instance password`)
    if (!file.endsWith('.json')) continue
    const validate = file.endsWith('run.json') ? validators.run : validators.result
    if (!validate(JSON.parse(text))) problems.push(`${file}: ${describe(validate.errors)}`)
  }
  if (!files.some((f) => f.endsWith('summary.md'))) problems.push(`${runDir} has no summary.md`)
  return problems
}
