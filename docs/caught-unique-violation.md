# A caught unique violation can be reported as a commit

Recorded 2026-10-19. PostgreSQL 18.6. Versions are in the run summary linked below.

Catch a unique violation (`23505`) inside a transaction, then let the framework's normal transaction API finish. PostgreSQL accepts `COMMIT` on the aborted transaction and returns command tag `ROLLBACK`. It does not raise a new error. The earlier write is gone.

Some APIs still report success. A resolved call, a public `isCommitted` flag, or an after-commit hook can all fire. A later transaction on that connection can still commit. That later commit means the connection was usable again. It does not mean the first transaction committed.

Rolling the failed statement back to a savepoint, then committing the outer transaction, does persist the earlier write. That recovery is a separate case.

The authoritative run is [`research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174`](../research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174/summary.md). Three repetitions agreed. A harness PASS on `PR-01` means the evidence is complete. It does not mean the commit report was right. The contract reading is [`research/production-reachability/README.md`](../research/production-reachability/README.md). Django's manual `commit()` is the follow-up [`2026-10-19T20-58-26Z-508b7a`](../research/production-reachability/runs/2026-10-19T20-58-26Z-508b7a/summary.md).

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

## Reports already submitted

| Project | Link |
| --- | --- |
| Knex | https://github.com/knex/knex/issues/6547 |
| MikroORM | https://github.com/mikro-orm/mikro-orm/issues/8476 |
| Lucid | https://github.com/adonisjs/lucid/issues/1205 |
| PostgreSQL JDBC | https://github.com/pgjdbc/pgjdbc/issues/4494 |

Filing status for every item, including drafts that have not been posted, is [`upstream-submissions.md`](upstream-submissions.md). The Knex draft in `research/production-reachability/upstream-drafts/knex.md` restates #6547 and is not a second report.

These are different reports: [knex#6546](https://github.com/knex/knex/issues/6546) is a connection returned to the pool with a transaction still open, and [kysely#1990](https://github.com/kysely-org/kysely/issues/1990) is a `ROLLBACK` that never completed.
