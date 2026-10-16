// TypeORM construction and entities, as the reused experiments defined them (docs/provenance.md). Entities are
// EntitySchema definitions (plain JavaScript, no decorators) for the runner's fixture tables.
import { DataSource, EntitySchema } from 'typeorm'

const id = { type: Number, primary: true, generated: 'increment' }
export const Item = new EntitySchema({ name: 'Item', tableName: 'item', columns: { id, name: { type: String }, qty: { type: Number, default: 0 } } })
export const Uniq = new EntitySchema({ name: 'Uniq', tableName: 'uniq', columns: { id, code: { type: String, unique: true } } })

export async function openDataSource(connection, { poolMax, logLines }) {
  const { host, port, user, password, database, application_name } = connection
  const ds = new DataSource({
    type: 'postgres',
    host, port, username: user, password, database,
    applicationName: application_name,
    entities: [Item, Uniq],
    synchronize: false,
    poolSize: poolMax,
    logger: {
      logQuery() {},
      logQueryError: (error, query) => logLines.push({ level: 'error', msg: `${String(error?.message ?? error).slice(0, 200)} | ${String(query).slice(0, 100)}` }),
      logQuerySlow() {},
      logSchemaBuild() {},
      logMigration() {},
      log: (level, message) => { if (level !== 'info' && level !== 'log') logLines.push({ level, msg: String(message).slice(0, 300) }) },
    },
  })
  await ds.initialize()
  return ds
}
