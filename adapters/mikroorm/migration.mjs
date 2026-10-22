// MG-02 and MG-03 through MikroORM's Migrator. up() queues the marker insert and then the gate
// lock; both run inside the migration transaction, and the history row is logged in that same
// transaction. There is no advisory lock of MikroORM's own. A migration that does not override
// down() uses Migration.down(), which throws "This migration cannot be reverted" before history
// is deleted. The schema snapshot is off: the migration is built in memory, and the fixture
// tables belong to the runner.
import { Migration, Migrator } from '@mikro-orm/migrations'
import { errInfo } from '../node-kit/util.mjs'

const MIGRATION_NAME = 'Migration20200101000000'
const CONTRACT = 'MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.'
const FORM = 'orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.'

function quote(value) {
  return String(value).replaceAll("'", "''")
}

function migrationClass({ marker, gate, hold, reversal }) {
  const safe = quote(marker)
  return class Ppcsm1 extends Migration {
    async up() {
      this.addSql(`insert into item (name) values ('${safe}')`)
      if (hold) this.addSql(`select pg_advisory_xact_lock(${Number(gate)})`)
    }

    async down() {
      if (reversal === 'none') return super.down()
      await this.execute(`delete from item where name = '${safe}'`)
      await this.execute(`insert into ppcs_undo (name) values ('${safe}')`)
      if (reversal === 'partial-then-error') throw new Error('the reversal failed on purpose after deleting the marker')
    }
  }
}

export async function runMikroMigration(ctx, { markers, migration }) {
  const orm = ctx.orm
  const options = orm.config.get('migrations')
  options.tableName = 'mikro_orm_migrations'
  options.transactional = true
  options.allOrNothing = true
  options.snapshot = false
  options.snapshotOnMigrate = false
  options.migrationsList = [{
    name: MIGRATION_NAME,
    class: migrationClass({
      marker: markers.m1,
      gate: migration.gate,
      hold: migration.hold === true,
      reversal: migration.reversal ?? 'valid',
    }),
  }]
  Migrator.register(orm)
  try {
    if (migration.operation === 'revert') {
      const ran = await orm.migrator.down()
      return ran.length
        ? { reported: 'reverted', exit_code: 0, basis: `migrator.down() reverted ${ran.map((m) => m.name).join(', ')}`, contract: CONTRACT, form: FORM }
        : { reported: 'nothing_to_do', exit_code: 0, basis: 'migrator.down() reverted nothing', contract: CONTRACT, form: FORM }
    }
    const ran = await orm.migrator.up()
    return ran.length
      ? { reported: 'applied', exit_code: 0, basis: `migrator.up() applied ${ran.map((m) => m.name).join(', ')}`, contract: CONTRACT, form: FORM }
      : { reported: 'nothing_to_do', exit_code: 0, basis: 'migrator.up() applied nothing', contract: CONTRACT, form: FORM }
  } catch (error) {
    return {
      reported: 'failed',
      exit_code: 1,
      basis: migration.operation === 'revert' ? 'migrator.down() threw' : 'migrator.up() threw',
      contract: CONTRACT,
      form: FORM,
      api_error: errInfo(error),
    }
  }
}
