// MikroORM construction and entities, as the reused experiments defined them (docs/provenance.md).
//
// Entities use defineEntity and map the runner's fixture tables, which the runner creates with plain SQL: the cases do
// not depend on MikroORM's schema generator.
import { MikroORM, RequestContext, defineEntity, p } from '@mikro-orm/postgresql'

export const Item = defineEntity({
  name: 'Item',
  tableName: 'item',
  properties: { id: p.integer().primary(), name: p.string(), qty: p.integer().default(0) },
})

export const Uniq = defineEntity({
  name: 'Uniq',
  tableName: 'uniq',
  properties: { id: p.integer().primary(), code: p.string().unique() },
})

export function openOrm(connection, { poolMax, logLines }) {
  const { host, port, user, password, database } = connection
  return MikroORM.init({
    host, port, user, password, dbName: database,
    entities: [Item, Uniq],
    pool: { min: 0, max: poolMax },
    ensureDatabase: false,
    allowGlobalContext: false,
    debug: false,
    logger: (message) => logLines.push(String(message).slice(0, 300)),
  })
}

/** A request context, as an HTTP handler would create one (the global EntityManager is not allowed outside one). */
export const inRequest = (orm, fn) => RequestContext.create(orm.em, fn)
