// Production-reachability cases. Existing catalog cases do not call this module.
import { ProtocolError, managedOutcome } from '../node-kit/adapter-main.mjs'
import { prCaseHandlers, violationInfo } from '../../research/production-reachability/js/variants.mjs'
import { Item, Uniq } from './lucid.mjs'

const MANAGED = 'In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback\'s value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid\'s report that the transaction committed. The pg Result of COMMIT is not read.'
const EXPLICIT = 'In @adonisjs/lucid 22.4.2, db.transaction() with no callback returns a transaction client. trx.commit() commits it and trx.rollback() rolls it back (src/transaction_client/index.js). A resolved commit() is Lucid\'s report that the transaction committed.'

async function identify(trx) {
  const { rows: [r] } = await trx.rawQuery('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')
  return { xid: r.xid, pid: Number(r.pid) }
}

export function lucidPrCases() {
  return prCaseHandlers(({ db }) => {
    const hooks = { registered: false, commit: 0, rollback: 0 }
    const listen = (trx) => {
      if (hooks.registered || typeof trx.on !== 'function') return
      hooks.registered = true
      trx.on('commit', () => { hooks.commit += 1 })
      trx.on('rollback', () => { hooks.rollback += 1 })
    }
    return {
      forms: {
        managed: 'db.transaction(callback). The callback catches the unique violation and returns. This is not the pre-commit-probe mode.',
        explicit: 'const trx = await db.transaction(); the unique violation is caught; await trx.commit().',
        control: 'db.transaction(callback). The unique violation leaves the callback.',
        savepoint: 'db.transaction(callback), then trx.transaction(callback) for the failing insert. The inner error is caught and the outer callback returns.',
      },
      contracts: { managed: MANAGED, explicit: EXPLICIT, control: MANAGED, savepoint: MANAGED },
      unsupported: {},
      managed: (body) => managedOutcome(
        (callback) => db.transaction(async (trx) => { listen(trx); return callback(trx) }),
        body,
        { call: 'db.transaction(callback)', contract: MANAGED },
      ),
      explicit: {
        names: { start: 'db.transaction()', commit: 'trx.commit()', rollback: 'trx.rollback()' },
        contract: EXPLICIT,
        start: async () => { const trx = await db.transaction(); listen(trx); return trx },
        commit: (trx) => trx.commit(),
        rollback: (trx) => trx.rollback(),
      },
      async savepoint(trx) {
        try {
          await trx.transaction(async (nested) => { await Uniq.create({ code: 'taken' }, { client: nested }) })
        } catch (e) {
          if (e instanceof ProtocolError) throw e
          return { recovered: true, violation: violationInfo(e) }
        }
        throw new ProtocolError('the duplicate insert did not raise')
      },
      write: (trx, name) => Item.create({ name }, { client: trx }),
      insertTaken: (trx) => Uniq.create({ code: 'taken' }, { client: trx }),
      identify,
      async probe() {
        if (typeof db.rawQuery !== 'function') return { supported: false, reason: 'the next transaction is the reuse probe' }
        try {
          await db.rawQuery('select 1 as ok')
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
          const outcome = await managedOutcome((callback) => db.transaction(callback), async (trx) => {
            await Item.create({ name }, { client: trx })
            const id = await identify(trx)
            pid = id.pid
            await checkpoint('reuse-after-write', { xid: String(id.xid), pid: id.pid })
          }, { call: 'db.transaction(callback)', contract: MANAGED })
          return { attempted: true, elapsed_ms: Date.now() - started, reported: outcome.reported, error: outcome.api_error ?? null, pid }
        } catch (e) {
          if (e instanceof ProtocolError) throw e
          return { attempted: true, elapsed_ms: Date.now() - started, reported: 'failed', error: violationInfo(e), pid }
        }
      },
      hooks: () => ({ supported: hooks.registered, commit: hooks.commit, rollback: hooks.rollback }),
      commandTag: () => null,
    }
  })
}
