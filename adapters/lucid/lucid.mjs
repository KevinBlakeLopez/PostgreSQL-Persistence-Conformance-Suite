// Lucid without an AdonisJS application, as the reused experiments constructed it (docs/provenance.md).
//
// Lucid's Database needs a logger and an emitter. Outside AdonisJS there is no container to provide them, so these are
// plain objects with the methods Lucid calls. BaseModel.useAdapter() is what DatabaseServiceProvider.boot() does.
import { Database } from '@adonisjs/lucid/database'
import { BaseModel, column } from '@adonisjs/lucid/orm'

export function captureLogger(lines) {
  const at = (level) => (...args) => {
    const [first, second] = args
    const msg = typeof first === 'string' ? first : (typeof second === 'string' ? second : '')
    lines.push({ level, msg: String(msg).slice(0, 300) })
  }
  const logger = { trace() {}, debug() {}, info: at('info'), warn: at('warn'), error: at('error'), fatal: at('fatal'), isLevelEnabled: () => true }
  logger.child = () => logger
  return logger
}
export const NOOP_EMITTER = { emit() {}, hasListeners() { return false } }

/** A standalone Database for the case's connection: the constructor call DatabaseServiceProvider.register() makes. */
export function openDatabase(connection, { poolMax, logLines }) {
  const { host, port, user, password, database, application_name } = connection
  const config = {
    connection: 'pg',
    connections: {
      pg: { client: 'pg', connection: { host, port, user, password, database, application_name }, pool: { min: 0, max: poolMax } },
    },
  }
  const db = new Database(config, captureLogger(logLines), NOOP_EMITTER)
  BaseModel.useAdapter(db.modelAdapter())
  return db
}

// Lucid's `column` is a legacy decorator, `(target, property) => ...`. Applying it by hand is what TypeScript's emitted
// __decorate does under experimentalDecorators. Columns are not declared as class fields: a field initializer would
// write through the model proxy.
const columns = (Model, defs) => { for (const [name, opts] of Object.entries(defs)) column(opts)(Model.prototype, name) }

export class Item extends BaseModel { static table = 'item' }
columns(Item, { id: { isPrimary: true }, name: {}, qty: {} })

export class Uniq extends BaseModel { static table = 'uniq' }
columns(Uniq, { id: { isPrimary: true }, code: {} })
