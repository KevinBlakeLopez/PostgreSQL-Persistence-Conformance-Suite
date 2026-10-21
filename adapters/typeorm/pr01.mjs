// Production-reachability cases. Existing catalog cases do not call this module.
import { ProtocolError, managedOutcome } from '../node-kit/adapter-main.mjs'
import { prCaseHandlers, violationInfo } from '../../research/production-reachability/js/variants.mjs'
import { Item, Uniq } from './orm.mjs'

const MANAGED = 'In TypeORM 1.1.2, ds.transaction(callback) starts a transaction, runs the callback, calls commitTransaction() and returns the callback\'s result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). commitTransaction() executes COMMIT and does not read the command tag (driver/postgres/PostgresQueryRunner.js). A resolved call is TypeORM\'s report that the transaction committed.'
const EXPLICIT = 'In TypeORM 1.1.2, QueryRunner.startTransaction() starts a transaction and commitTransaction() executes COMMIT without reading the command tag (driver/postgres/PostgresQueryRunner.js). A resolved commitTransaction() is TypeORM\'s report that the transaction committed.'

function managerOf(handle) {
  return handle.manager ?? handle
}

async function identify(handle) {
  const [r] = await managerOf(handle).query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: Number(r.pid) }
}

function write(handle, name) {
  return managerOf(handle).getRepository(Item).insert({ name, qty: 0 })
}

function insertTaken(handle) {
  return managerOf(handle).getRepository(Uniq).insert({ code: 'taken' })
}

export function typeormPrCases() {
  return prCaseHandlers(({ ds }) => {
    const hooks = { afterCommit: 0, afterRollback: 0 }
    ds.subscribers.push({
      afterTransactionCommit() { hooks.afterCommit += 1 },
      afterTransactionRollback() { hooks.afterRollback += 1 },
    })
    return {
      forms: {
        managed: 'ds.transaction(callback). The callback catches the unique violation from repository.insert and returns.',
        explicit: 'createQueryRunner(), connect(), startTransaction(), catch the unique violation, commitTransaction(), release().',
        control: 'ds.transaction(callback). The unique violation leaves the callback.',
        savepoint: 'ds.transaction(callback), then manager.transaction(callback) around the duplicate. The inner error is caught and the outer callback returns. Nested startTransaction issues SAVEPOINT when a transaction is already active.',
      },
      contracts: { managed: MANAGED, explicit: EXPLICIT, control: MANAGED, savepoint: MANAGED },
      unsupported: {},
      managed: (body) => managedOutcome((callback) => ds.transaction(callback), body, { call: 'ds.transaction(callback)', contract: MANAGED }),
      explicit: {
        names: { start: 'queryRunner.startTransaction()', commit: 'queryRunner.commitTransaction()', rollback: 'queryRunner.rollbackTransaction()' },
        contract: EXPLICIT,
        start: async () => {
          const qr = ds.createQueryRunner()
          await qr.connect()
          await qr.startTransaction()
          return qr
        },
        commit: async (qr) => { try { await qr.commitTransaction() } finally { await qr.release() } },
        rollback: async (qr) => { try { await qr.rollbackTransaction() } finally { await qr.release() } },
      },
      async savepoint(handle) {
        try {
          await managerOf(handle).transaction(async (nested) => { await insertTaken(nested) })
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
          await ds.query('select 1 as ok')
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
          const outcome = await managedOutcome((callback) => ds.transaction(callback), async (manager) => {
            await write(manager, name)
            const id = await identify(manager)
            pid = id.pid
            await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
          }, { call: 'ds.transaction(callback)', contract: MANAGED })
          return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid }
        } catch (e) {
          if (e instanceof ProtocolError) throw e
          return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid }
        }
      },
      hooks: () => ({ supported: true, after_commit: hooks.afterCommit, after_rollback: hooks.afterRollback }),
      commandTag: () => null,
    }
  })
}
