// MG-02 and MG-03 through DataSource.runMigrations() and undoLastMigration().
// TypeORM 1.1.2 runs every pending migration in one transaction by default and inserts the history
// row in that same transaction. It does not take an advisory lock. The case's migration waits on the
// runner's lock after inserting the marker. A migration with no down() is the no-reversal case:
// undoLastMigration() calls down and throws before it deletes the history row.
import { errInfo } from '../node-kit/util.mjs'

// The last 13 characters are the timestamp TypeORM requires in a migration name.
const MIGRATION_NAME = 'Ppcsm11700000000000'
const CONTRACT = 'TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.'
const FORM = 'DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.'

function migrationInstance({ marker, gate, hold, reversal }) {
  const instance = {
    name: MIGRATION_NAME,
    async up(queryRunner) {
      await queryRunner.query('insert into item (name) values ($1)', [marker])
      if (hold) await queryRunner.query('select pg_advisory_xact_lock($1)', [Number(gate)])
    },
  }
  if (reversal !== 'none') {
    instance.down = async (queryRunner) => {
      await queryRunner.query('delete from item where name = $1', [marker])
      await queryRunner.query('insert into ppcs_undo (name) values ($1)', [marker])
      if (reversal === 'partial-then-error') throw new Error('the reversal failed on purpose after deleting the marker')
    }
  }
  return instance
}

export async function runTypeormMigration(ctx, { markers, migration }) {
  const ds = ctx.ds
  ds.migrations = [migrationInstance({
    marker: markers.m1,
    gate: migration.gate,
    hold: migration.hold === true,
    reversal: migration.reversal ?? 'valid',
  })]
  // A terminated backend emits 'error' on the checked-out client. pg-pool removes its listener
  // while the client is checked out. This keeps the process alive so runMigrations() can reject.
  ds.driver.master?.on('connect', (client) => { client.on('error', () => {}) })
  try {
    if (migration.operation === 'revert') {
      await ds.undoLastMigration()
      return { reported: 'reverted', exit_code: 0, basis: 'undoLastMigration() returned', contract: CONTRACT, form: FORM }
    }
    const ran = await ds.runMigrations()
    return {
      reported: ran.length ? 'applied' : 'nothing_to_do',
      exit_code: 0,
      basis: ran.length ? `runMigrations() executed ${ran.map((m) => m.name).join(', ')}` : 'runMigrations() executed none',
      contract: CONTRACT,
      form: FORM,
    }
  } catch (error) {
    return {
      reported: 'failed',
      exit_code: 1,
      basis: migration.operation === 'revert' ? 'undoLastMigration() threw' : 'runMigrations() threw',
      contract: CONTRACT,
      form: FORM,
      api_error: errInfo(error),
    }
  }
}
