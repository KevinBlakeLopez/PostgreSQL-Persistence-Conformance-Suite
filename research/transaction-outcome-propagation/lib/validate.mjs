import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import Ajv2020 from 'ajv/dist/2020.js'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const SCHEMA_DIR = join(HERE, '..', 'schema')

const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true })
const compile = (file) => ajv.compile(JSON.parse(readFileSync(join(SCHEMA_DIR, file), 'utf8')))

const validators = {
  record: compile('propagation.v1.schema.json'),
  run: compile('run.v1.schema.json'),
  capability: compile('capability.v1.schema.json'),
}

export function schemaErrors(kind, value) {
  const validate = validators[kind]
  if (!validate) throw new Error(`unknown schema kind ${kind}`)
  return validate(value) ? [] : validate.errors.map((error) => `${error.instancePath || '/'} ${error.message}`)
}

export function containsSecret(value, secrets) {
  const text = JSON.stringify(value)
  return secrets.filter((secret) => secret && text.includes(secret))
}
