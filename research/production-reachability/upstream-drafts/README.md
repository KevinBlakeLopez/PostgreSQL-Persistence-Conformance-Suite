# Upstream drafts

These are drafts. They have not been filed, and no maintainer has been contacted.

Which items are already submitted, and which of these drafts are still waiting, is recorded in [`docs/upstream-submissions.md`](../../../docs/upstream-submissions.md). The Knex draft below restates [knex#6547](https://github.com/knex/knex/issues/6547) and is not a new submission.

| Draft | Suggested destination | Title |
| --- | --- | --- |
| [kysely.md](kysely.md) | [kysely-org/kysely](https://github.com/kysely-org/kysely/issues/new) | `commit()` sets `isCommitted` when PostgreSQL rolls the transaction back |
| [spring-framework.md](spring-framework.md) | [spring-projects/spring-framework](https://github.com/spring-projects/spring-framework/issues/new) | `afterCommit` runs when PostgreSQL rolls back an aborted transaction on `COMMIT` |
| [knex.md](knex.md) | [knex/knex](https://github.com/knex/knex/issues/new) | `transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [typeorm.md](typeorm.md) | [typeorm/typeorm](https://github.com/typeorm/typeorm/issues/new) | `afterTransactionCommit` runs when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [psycopg.md](psycopg.md) | [psycopg/psycopg](https://github.com/psycopg/psycopg/issues/new) | `Connection.commit()` returns when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [drizzle.md](drizzle.md) | [drizzle-team/drizzle-orm](https://github.com/drizzle-team/drizzle-orm/issues/new) | `db.transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [prisma.md](prisma.md) | [prisma/orm](https://github.com/prisma/orm/issues/new) | `$transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |

A search of Kysely issues for `isCommitted` and `ROLLBACK` did not find this case. Spring issue [28685](https://github.com/spring-projects/spring-framework/issues/28685) is different: there, `afterCommit` itself throws, and `afterCompletion` is still `STATUS_COMMITTED`. Knex issue [6141](https://github.com/knex/knex/issues/6141) is a `COMMIT` that throws. These drafts are a `COMMIT` that does not throw.

Lucid 22.4.2 shows the same ending through Knex, and MikroORM 7.2.5 shows it through its PostgreSQL driver. Those are not separate drafts. Drizzle and Prisma are separate drafts because each drops the tag in its own client. Neither draft is filed. A fix in Knex or Kysely is what their commit path would see. SQLAlchemy's ORM flush path is not in the psycopg draft: flush rolls the transaction back itself, and `after_commit` does not run. Django `atomic()` is not in that draft either: it calls `rollback()` when a database error has set `needs_rollback`. The Django case in the psycopg draft is manual `transaction.commit()`.
