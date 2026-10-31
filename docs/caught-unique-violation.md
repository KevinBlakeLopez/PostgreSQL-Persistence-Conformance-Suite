# A caught unique violation can be reported as a commit

Recorded 2026-10-19. PostgreSQL 18.6. Versions are in the run summary linked below.

Catch a unique violation (`23505`) inside a transaction, then let the framework's normal transaction API finish. PostgreSQL accepts `COMMIT` on the aborted transaction and returns command tag `ROLLBACK`. It does not raise a new error. The earlier write is gone.

Some APIs still report success. A resolved call, a public `isCommitted` flag, or an after-commit hook can all fire. A later transaction on that connection can still commit. That later commit means the connection was usable again. It does not mean the first transaction committed.

Rolling the failed statement back to a savepoint, then committing the outer transaction, does persist the earlier write. That recovery is a separate case.

The authoritative run is [`research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174`](../research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174/summary.md). Three repetitions agreed. A harness PASS on `PR-01` means the evidence is complete. It does not mean the commit report was right. The contract reading is [`research/production-reachability/README.md`](../research/production-reachability/README.md). Django's manual `commit()` is the follow-up [`2026-10-19T20-58-26Z-508b7a`](../research/production-reachability/runs/2026-10-19T20-58-26Z-508b7a/summary.md).

MikroORM 7.2.6-dev.19 is a later follow-up, [`2026-10-22T12-18-31Z-928c75`](../research/production-reachability/runs/2026-10-22T12-18-31Z-928c75/summary.md). `em.transactional()` and `em.commit()` rejected with `25P02` and the message `COMMIT was answered with ROLLBACK`. The marker was absent. Savepoint recovery still committed. npm `latest` on that day was still 7.2.5, so the 7.2.5 line below remains the published release. The managed case's last statement was `rollback`, because `transactional()` sent `rollback` after the rejected `commit`. The harness records that case as mechanism not exercised.

In that run, these reported a successful completion, or ran a commit hook, while `pg_xact_status()` was `aborted` and the marker was absent:

- Knex 3.3.0 `transaction()`
- Kysely 0.29.6, including `isCommitted === true` on the explicit `commit()`
- Lucid 22.4.2, including a commit listener
- MikroORM 7.2.5 `em.transactional()` and `em.commit()`
- TypeORM 1.1.2, including `afterTransactionCommit`
- SQLAlchemy Core 2.1.5, including the connection commit event
- Spring Framework 7.0.9 JDBC and `DataSourceTransactionManager`, including `afterCommit` and `afterCompletion(STATUS_COMMITTED)`
- Django 6.1.2 manual `transaction.commit()`, in the follow-up run

These did not treat that completion as a commit:

- node-postgres 8.23.1, when the application reads `Result.command` (`ROLLBACK`)
- Django 6.1.2 `transaction.atomic()`, which rolls the transaction back
- SQLAlchemy ORM 2.1.5 explicit `SessionTransaction.commit()`, which raises
- SQLAlchemy ORM's `after_commit` on the managed path. The block can return after flush has rolled the transaction back. `after_commit` did not run.
- pgx v5.11.0 `Tx.Commit`, and through it Go `database/sql` and GORM v1.31.2. The suite run [`reports/examples/2026-10-22T13-24-28Z-606909`](../reports/examples/2026-10-22T13-24-28Z-606909/summary.md) reports `rolled_back` because `Commit` returns `ErrTxCommitRollback`. The tracer recorded command tag `ROLLBACK`. The comparison is [`docs/go-persistence.md`](go-persistence.md).

## Reports already submitted

| Project | Link |
| --- | --- |
| Knex | https://github.com/knex/knex/issues/6547 |
| MikroORM | https://github.com/mikro-orm/mikro-orm/issues/8476 Closed 2026-10-22 as completed via https://github.com/mikro-orm/mikro-orm/pull/8499 |
| Lucid | https://github.com/adonisjs/lucid/issues/1205 |
| PostgreSQL JDBC | https://github.com/pgjdbc/pgjdbc/issues/4494 |
| Kysely | https://github.com/kysely-org/kysely/issues/2157 The maintainer's fix PR https://github.com/kysely-org/kysely/pull/2161 is open |
| TypeORM | https://github.com/typeorm/typeorm/issues/12992 |
| Drizzle | https://github.com/drizzle-team/drizzle-orm/issues/6572 |
| Prisma | A comment on the existing report https://github.com/prisma/orm/issues/20496#issuecomment-6372520392 |
| psycopg | https://github.com/psycopg/psycopg/issues/1453 |
| asyncpg | https://github.com/MagicStack/asyncpg/issues/1400 |

Updated 2026-10-26 from [`upstream-submissions.md`](upstream-submissions.md) and the Python tracker. Filing status for every item, including drafts that have not been posted, is [`upstream-submissions.md`](upstream-submissions.md). The Knex draft in `research/production-reachability/upstream-drafts/knex.md` restates #6547 and is not a second report.

These are different reports: [knex#6546](https://github.com/knex/knex/issues/6546) is a connection returned to the pool with a transaction still open, and [kysely#1990](https://github.com/kysely-org/kysely/issues/1990) is a `ROLLBACK` that never completed.

## Production relevance

Judged 2026-10-26 under [`production-relevance.md`](production-relevance.md). The library-by-library ratings are in [`research/filed-items-production-relevance/`](../research/filed-items-production-relevance/README.md) and, for psycopg, in the [Python tracker](../research/python-upstream-contribution-tracker.md).

A unique violation is an ordinary database error. The silent success report needs a further choice in the application: catch that error inside the transaction, send no later statement, and let the transaction API finish. PostgreSQL then answers `COMMIT` with `ROLLBACK` and does not raise. A later statement in the same transaction fails with `25P02`, so the false success appears when the caught error is the last statement, or when later errors are caught too. Work that has to persist belongs in the transaction and is not wrapped in that catch. The usual alternatives are to rethrow, to roll the failed statement back to a savepoint, or to use `ON CONFLICT`.

The same search found no production report of this silent form at the top of the filed Node and Java ratings. Production reports found for Prisma and Drizzle were the loud form, `25P02`. Likelihood judgments for the catch-and-finish shape were low, or low to moderate where the evidence was a small project's own report ([warden#148](https://github.com/laclemen92/warden/pull/148), on Kysely) or a few projects catching per item inside one batch (psycopg, revised the same day). A separate Lucid report, where `COMMIT` itself fails, is a different trigger and is rated low to moderate. These are judgments about the code that was inspected. They are not measured frequencies. The Python tracker records [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453) closed on 2026-10-27 by the maintainer, with no code change: a caller who traps the error owns the connection state.

## A scripted copy is not a result

The draft in [`ownership-benchmark/`](ownership-benchmark/) specifies a transaction task that catches the violation inside the transaction and lets the API finish. An implementation that follows those steps reproduces the library behavior on this page. The task records the library under that script. It does not show that an application writes those steps, and it does not show what an agent writes when the requirement is only that a duplicate fails. This repository does not count that task as evidence of production frequency, of ownership cost, or of agent behavior. The draft is not a result.
