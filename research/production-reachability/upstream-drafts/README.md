# Upstream drafts

These files are the draft texts. Filing status is [`docs/upstream-submissions.md`](../../../docs/upstream-submissions.md). A banner that says "Filed" is that file's record of a post. A banner that says "Not filed" means that text has not been posted. If this page and the tracker disagree, the tracker is the filing log.

The Knex draft below restates [knex#6547](https://github.com/knex/knex/issues/6547) and is not a new submission.

| Draft | Filing, per the tracker | Suggested destination | Title |
| --- | --- | --- | --- |
| [kysely.md](kysely.md) | Filed 2026-10-21 as #2157 | [kysely-org/kysely](https://github.com/kysely-org/kysely/issues/2157) | `commit()` sets `isCommitted` when PostgreSQL rolls the transaction back |
| [spring-framework.md](spring-framework.md) | Not filed. S1 | [spring-projects/spring-framework](https://github.com/spring-projects/spring-framework/issues/new) | `afterCommit` runs when PostgreSQL rolls back an aborted transaction on `COMMIT` |
| [knex.md](knex.md) | Do not file. Restates #6547 | [knex/knex](https://github.com/knex/knex/issues/6547) | `transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [typeorm.md](typeorm.md) | Filed 2026-10-21 as #12992 | [typeorm/typeorm](https://github.com/typeorm/typeorm/issues/12992) | `afterTransactionCommit` runs when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [psycopg.md](psycopg.md) | Filed 2026-10-21 as #1453. Closed 2026-10-27 by `dvarrazzo`; no code change | [psycopg/psycopg](https://github.com/psycopg/psycopg/issues/1453) | `Connection.commit()` returns when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [drizzle.md](drizzle.md) | Filed 2026-10-22 as #6572 | [drizzle-team/drizzle-orm](https://github.com/drizzle-team/drizzle-orm/issues/6572) | `db.transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| [prisma.md](prisma.md) | Posted 2026-10-23 as a comment on #20496 (PI1), not as a new issue | [prisma/orm](https://github.com/prisma/orm/issues/20496#issuecomment-6372520392) | `$transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` |

Before Y2 was filed, a search of Kysely issues for `isCommitted` and `ROLLBACK` did not find this case. Spring issue [28685](https://github.com/spring-projects/spring-framework/issues/28685) is different: there, `afterCommit` itself throws, and `afterCompletion` is still `STATUS_COMMITTED`. Knex issue [6141](https://github.com/knex/knex/issues/6141) is a `COMMIT` that throws. These drafts are a `COMMIT` that does not throw.

Lucid 22.4.2 shows the same ending through Knex, and MikroORM 7.2.5 shows it through its PostgreSQL driver. Those are not separate drafts. Drizzle and Prisma are separate drafts because each drops the tag in its own client. Drizzle is filed as #6572. Prisma's case was posted as a comment on the existing #20496. A fix in Knex or Kysely is what their commit path would see. SQLAlchemy's ORM flush path is not in the psycopg draft: flush rolls the transaction back itself, and `after_commit` does not run. Django `atomic()` is not in that draft either: it calls `rollback()` when a database error has set `needs_rollback`. The Django case in the psycopg draft is manual `transaction.commit()`.
