// Production-reachability cases. The ordinary form flushes the duplicate in the same callback.
// It is not the nested REQUIRED form used by the existing TX-01A case.
import { ProtocolError, managedOutcome } from '../node-kit/adapter-main.mjs'
import { prCaseHandlers, violationInfo } from '../../research/production-reachability/js/variants.mjs'
import { Item, Uniq, inRequest } from './orm.mjs'

const MANAGED = 'In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows. A resolved call is MikroORM\'s report that the transaction committed. The driver result of COMMIT is not read.'
const EXPLICIT = 'In MikroORM 7.2.5, em.begin() "Starts new transaction bound to this EntityManager" and em.commit() "Commits the transaction bound to this EntityManager. Flushes before doing the actual commit query." (EntityManager.d.ts). A resolved em.commit() is MikroORM\'s report that the transaction committed.'
const SAVEPOINT = 'MikroORM 7.2.5 documents a nested em.transactional() as a savepoint by default (EntityManager.transactional, TransactionPropagation.NESTED).'

async function identify(em) {
  const r = await em.getConnection().execute('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid', [], 'get', em.getTransactionContext())
  return { xid: r.xid, pid: Number(r.pid) }
}

async function write(em, name) {
  em.create(Item, { name, qty: 0 })
  await em.flush()
}

async function insertTaken(em) {
  em.create(Uniq, { code: 'taken' })
  await em.flush()
}

export function mikroPrCases() {
  return prCaseHandlers(({ orm }) => ({
    forms: {
      managed: 'em.transactional(callback) on the request EntityManager. The duplicate is created and flushed in that same callback, and the callback catches the error. This is not the nested REQUIRED form of the existing TX-01A case.',
      explicit: 'em.fork(), em.begin(), catch the flush error, em.commit().',
      control: 'em.transactional(callback). The flush error leaves the callback.',
      savepoint: 'em.transactional(callback) with a nested em.transactional() around the duplicate. The nested error is caught and the outer callback returns.',
    },
    contracts: { managed: MANAGED, explicit: EXPLICIT, control: MANAGED, savepoint: `${MANAGED} ${SAVEPOINT}` },
    unsupported: {},
    managed: (body) => managedOutcome(
      (callback) => inRequest(orm, () => orm.em.transactional(callback)),
      body,
      { call: 'em.transactional(callback)', contract: MANAGED },
    ),
    explicit: {
      names: { start: 'em.begin()', commit: 'em.commit()', rollback: 'em.rollback()' },
      contract: EXPLICIT,
      start: async () => { const em = orm.em.fork(); await em.begin(); return em },
      commit: (em) => em.commit(),
      rollback: (em) => em.rollback(),
    },
    async savepoint(em) {
      try {
        await em.transactional(async (nested) => { await insertTaken(nested) })
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { recovered: true, violation: violationInfo(e) }
      }
      throw new ProtocolError('the duplicate insert did not raise')
    },
    write,
    insertTaken,
    identify,
    async probe() {
      try {
        await orm.em.getConnection().execute('select 1 as ok')
        return { supported: true, ok: true, error: null }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { supported: true, ok: false, error: violationInfo(e) }
      }
    },
    async reuse(name, checkpoint) {
      const started = Date.now()
      let pid = null
      try {
        const outcome = await managedOutcome(
          (callback) => inRequest(orm, () => orm.em.transactional(callback)),
          async (em) => {
            await write(em, name)
            const id = await identify(em)
            pid = id.pid
            await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
          },
          { call: 'em.transactional(callback)', contract: MANAGED },
        )
        return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid }
      } catch (e) {
        if (e instanceof ProtocolError) throw e
        return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid }
      }
    },
    hooks: () => ({ supported: false, reason: 'This case uses the resolved or rejected transactional() call as the outcome. No MikroORM event subscriber was registered.' }),
    commandTag: () => null,
  }))
}
