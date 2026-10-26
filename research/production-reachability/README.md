# Production-reachable transaction outcomes

This run asks whether ordinary application code, using a supported transaction API and a real PostgreSQL unique violation, can observe a successful transaction completion when PostgreSQL rolled the transaction back. It does not use protocol interception, withheld statements, or patched driver transaction methods.

The established PPCS cases are unchanged. `TX-01A.caught-error-then-commit` remains the suite's category A case, and its classifications are not reinterpreted here. This catalog lives outside `specifications/`, so the default suite's catalog digest is unchanged. `harness/lib/classify.mjs` gained a `PR-01` family. A harness PASS on that family means the independent evidence is complete and the marker visibility agrees with `pg_xact_status()`. It does not mean the framework reported the commit correctly. The verdicts below are the contract assessment.

## How it was run

PostgreSQL 18.6, the disposable server from `pnpm run pg:up`. Each executed case ran three times on a fresh database. Repetitions agreed.

- Main run: `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` (87 harness PASS, 3 harness INCONCLUSIVE).
- Django explicit follow-up: `research/production-reachability/runs/2026-10-19T20-58-26Z-508b7a`. The first attempt called `on_commit()` under manual transaction management. Django raises `TransactionManagementError` for that call, before the scenario's write. The follow-up does not register `on_commit` on the manual API.
- MikroORM follow-up: `research/production-reachability/runs/2026-10-22T12-18-31Z-928c75`. `@mikro-orm/core`, `@mikro-orm/postgresql`, `@mikro-orm/sql`, and `@mikro-orm/migrations` 7.2.6-dev.19, kysely 0.29.7, pg 8.23.1. Six harness results, three repetitions, all agreed. npm `latest` was still 7.2.5. `7.2.6-dev.20` also contains the client change, but `@mikro-orm/core@7.2.6-dev.20` was not published, so this run used dev.19. That build contains the `PostgreSqlClient` from #8499. It does not contain the #8462 savepoint change.

Standalone checks, outside the harness, are in `reproductions/` and were executed against the same server. They printed:

- node-postgres 8.23.1: `COMMIT` resolved, command tag `ROLLBACK`, the kept row was not visible.
- Knex 3.3.0: `transaction(callback)` resolved after a caught `23505`, and the kept row was not visible.
- Kysely 0.29.6: `commit().execute()` did not throw, `isCommitted` was `true`, and the kept row was not visible.
- SQLAlchemy 2.1.5 Core: `Connection.begin()` returned without an exception, and the kept row was not visible.
- SQLAlchemy 2.1.5 ORM: `Session.begin()` returned without an exception after a caught flush error, and the kept row was not visible.

## What PostgreSQL does

A unique violation (`23505`) aborts the transaction unless it happens inside a savepoint that the application then rolls back. This run observed the command tag on node-postgres: `Result.command` was `ROLLBACK`, and `Client.query('COMMIT')` resolved. The PostgreSQL 18 `COMMIT` reference page does not state that tag. psycopg `Connection.commit()` and pgjdbc `Connection.commit()` do not expose that tag. For those drivers the evidence is the session state (`INERROR` to idle, last statement `COMMIT`) plus `pg_xact_status()`.

A later transaction on the same backend committed its own row after these completions. The connection was not left `idle in transaction (aborted)`. `COMMIT` of an aborted transaction ends the transaction, so the pool can reuse the connection. The hazard is a false success report, including commit hooks, not a poisoned connection.

Savepoint recovery was included so a legitimate commit after `23505` is not called a defect. Where the framework's savepoint API ran, the outer transaction committed and the earlier marker was visible. The exception was Spring's declarative nested transaction, below.

## Matrix

Versions are the ones the adapters loaded. The driver is pg 8.23.1 on Node, psycopg 3.3.6 on Python, and PostgreSQL JDBC 42.7.14 on the JVM. "App outcome" is what the transaction API did. "DB outcome" is `pg_xact_status()` and whether an independent connection saw the marker.

| Framework | Version | Scenario | API | App outcome | DB outcome | Contract assessment | Reachability | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pg, reading `Result.command` | 8.23.1 | caught `23505`, then `COMMIT` | `Client.query` | resolved, tag `ROLLBACK`; reported rollback | aborted, marker absent | The driver exposes the tag. Reading it matches PostgreSQL. | R1 | PASS |
| pg, ignoring the tag | 8.23.1 | caught `23505`, then `COMMIT` | `Client.query` | resolved, tag `ROLLBACK`; treated as success | aborted, marker absent | The tag is on the `Result`. Treating resolution alone as a commit discards it. | R1 | APPLICATION MISUSE |
| Knex | 3.3.0 | managed catch, then return | `knex.transaction(callback)` | callback resolved; SQL trace ends in `COMMIT;` | aborted, marker absent | `transaction.js` resolves the transaction when the `COMMIT` query resolves and does not read the command tag. | R1 | FAIL |
| Knex | 3.3.0 | explicit catch, then `trx.commit()` | `knex.transaction()` / `trx.commit()` | `commit()` resolved | aborted, marker absent | Same `commit()` path. Related, but not the same, as Knex issue 6141 (a `COMMIT` that throws, especially deferred constraints). This `COMMIT` does not throw. | R1 | FAIL |
| Kysely | 0.29.6 | managed catch, then return | `db.transaction().execute(callback)` | promise resolved | aborted, marker absent | `TransactionBuilder.execute` sets its internal committed flag after `commitTransaction` resolves. | R1 | FAIL |
| Kysely | 0.29.6 | explicit catch, then commit | `startTransaction()` / `commit().execute()` | did not throw; `isCommitted === true` | aborted, marker absent | `ControlledTransaction.commit()` sets the public `isCommitted` flag after `commit` resolves. The flag's documented meaning is that the transaction was committed. | R1 | FAIL |
| Lucid | 22.4.2 | managed and explicit catch, then complete | `db.transaction(callback)` and `trx.commit()` | call resolved; a `commit` listener ran; first command tag `ROLLBACK` | aborted, marker absent | Lucid's managed contract treats a resolved call as a committed transaction. The pg result is not read. | R1 | FAIL |
| MikroORM | 7.2.5 | managed and explicit catch, then complete | `em.transactional()` and `em.begin()` / `em.commit()` | call resolved; command tag `ROLLBACK` | aborted, marker absent | A resolved `transactional()` or `commit()` is MikroORM's report that the transaction committed. This form flushes the duplicate in the same callback. It is not the nested `REQUIRED` form of the existing TX-01A case. | R1 | FAIL |
| MikroORM | 7.2.6-dev.19 | managed and explicit catch, then complete | `em.transactional()` and `em.begin()` / `em.commit()` | both calls rejected `25P02`, "COMMIT was answered with ROLLBACK". Managed then sent `rollback`. Explicit's last statement stayed `commit`. | aborted, marker absent | Follow-up on 2026-10-22. The 7.2.5 row is unchanged. npm `latest` was still 7.2.5. The harness marks the managed case "mechanism not exercised" because the last statement was `rollback`, not `commit`. The call no longer reports a commit. Savepoint recovery still committed the earlier marker. | R1 | PASS |
| TypeORM | 1.1.2 | managed and explicit catch, then complete | `ds.transaction(callback)` and `QueryRunner.commitTransaction()` | call resolved; `afterTransactionCommit` ran; `afterTransactionRollback` did not; command tag `ROLLBACK` | aborted, marker absent | `commitTransaction()` executes `COMMIT` and does not read the command tag, then broadcasts `AfterTransactionCommit`. | R1 | FAIL |
| SQLAlchemy Core | 2.1.5 | managed and explicit catch, then complete | `Connection.begin()` and `Transaction.commit()` | block or `commit()` returned; connection `commit` event fired; trace `COMMIT (INERROR -> IDLE)` | aborted, marker absent | `TransactionalContext.__exit__` commits when the block returns and the transaction is still active. Core leaves it active after a caught `IntegrityError`. psycopg's `commit()` returns on command tag `ROLLBACK`. | R1 | FAIL |
| SQLAlchemy ORM | 2.1.5 | managed catch, then return | `Session.begin()` | block returned; `after_commit` did not run; `after_rollback` did; trace `ROLLBACK (INERROR)`; session already idle before the block ended | aborted, marker absent | `Session._flush` rolls the transaction back when flush fails and raises `IntegrityError`, which the application caught. `__exit__` commits only while the transaction is still active (`sqlalchemy/engine/util.py`), so it neither committed nor raised. A normal exit here is not an `after_commit`. | R1 | DOCUMENTED / EXPECTED |
| SQLAlchemy ORM | 2.1.5 | explicit catch, then `commit()` | `SessionTransaction.commit()` | `commit()` raised; `after_rollback` ran | aborted, marker absent | The explicit commit reports that it did not complete. | R1 | PASS |
| Django | 6.1.2 | managed catch, then return | `transaction.atomic()` | block returned; `Atomic.__exit__` called `rollback()`; `on_commit` did not run | aborted, marker absent | Django's `atomic()` contract commits only when the block does not raise and `needs_rollback` is false. A database error inside the block sets that flag even if the application catches it. The docs tell applications not to catch database errors inside `atomic()` without a savepoint. | R1 | PASS |
| Django | 6.1.2 | explicit catch, then `commit()` | `set_autocommit(False)` / `transaction.commit()` | `commit()` returned; last statement `COMMIT` | aborted, marker absent | Manual `commit()` is a documented API. It returned while PostgreSQL had aborted the transaction. `on_commit()` is rejected in this mode (`TransactionManagementError`). | R2 | FAIL |
| Spring JDBC | 7.0.9 | managed and explicit catch, then complete | `TransactionTemplate.execute` and `PlatformTransactionManager.commit` | call returned; `afterCommit` ran; `afterCompletion` was `committed` | aborted, marker absent | Spring commits when the callback returns, and `afterCommit` means the transaction committed. pgjdbc `Connection.commit()` is void and did not throw. Same result with `DriverManagerDataSource` and HikariCP size 1. | R1 | FAIL |
| Spring transaction management | 7.0.9 | managed catch, then return | `TransactionTemplate` and `@Transactional` | call returned; `afterCommit` ran; `afterCompletion` was `committed` | aborted, marker absent | Same commit rule, without `JdbcTemplate`. A caught `SQLException` does not leave the callback, so the default rollback rule is not involved. | R1 | FAIL |
| Spring transaction management | 7.0.9 | explicit catch, then commit | `getTransaction` / `commit` | `commit` returned; `afterCommit` ran | aborted, marker absent | The shared result text still says `TransactionTemplate`, because `Boundaries.map` uses that sentence for every programmatic success. The case form is `getTransaction` / `commit`. The hook and the database outcome are the evidence. | R1 | FAIL |
| Spring transaction management | 7.0.9 | declarative explicit | `@Transactional` | not implemented | none | `@Transactional` does not return a `TransactionStatus`. | — | UNSUPPORTED |
| Spring transaction management | 7.0.9 | declarative uncaught `SQLException` | `@Transactional` | the method's exception left the proxy; `afterCommit` still ran and `afterCompletion` was `committed` | aborted, marker absent | Default `rollbackOn` is false for a checked `SQLException`, so the interceptor commits and rethrows. The caller sees the exception. An `afterCommit` listener does not. | R2 | FAIL |
| Spring transaction management | 7.0.9 | declarative savepoint | `@Transactional` `PROPAGATION_NESTED` | outer proxy returned; `afterCommit` ran | aborted, marker absent; session was already `idle in transaction (aborted)` before the end | The nested checked `SQLException` does not mark the savepoint rollback-only. Spring tried to release the savepoint and got `25P02`. The message also contains the unique violation. The harness records this INCONCLUSIVE because the outer SQLSTATE is `25P02`, not `23505`. Three repetitions agreed on that record. | R2 | FAIL |

Every uncaught control except that declarative Spring row reported rollback, left the marker absent, and let the next transaction commit. Every savepoint recovery except declarative Spring committed the outer marker and left the session `idle in transaction` before the commit, which is the state of a transaction that is still usable.

## Answers

Frameworks that distinguished an aborted transaction from a commit, for a caught `23505` followed by the normal completion path:

- node-postgres, when the application reads `Result.command`.
- Django `transaction.atomic()`, which rolls the transaction back itself.
- SQLAlchemy ORM `SessionTransaction.commit()`, which raises after flush has rolled the transaction back.
- MikroORM 7.2.6-dev.19 `em.transactional()` and `em.commit()`, which reject when the command tag is `ROLLBACK`. The 7.2.5 release still resolved. npm `latest` on 2026-10-22 was 7.2.5.
- SQLAlchemy ORM's `after_commit` / `after_rollback` events. The context manager's normal return does not.

Frameworks that presented a successful completion, or ran a commit hook, when PostgreSQL had aborted the transaction:

- Knex, Kysely (`isCommitted`), Lucid, MikroORM 7.2.5, and TypeORM (`afterTransactionCommit`).
- SQLAlchemy Core, including the connection `commit` event.
- Spring JDBC and Spring `DataSourceTransactionManager`, including `afterCommit` and `afterCompletion(STATUS_COMMITTED)`.
- Django's manual `transaction.commit()`, which is a different API from `atomic()`.

Those caught-then-complete failures are reachable in ordinary code: begin a transaction, catch a unique violation, and let the supported API finish. They do not require fault injection. The Spring declarative rows that depend on a checked `SQLException` and the default rollback rule are R2: the API supports them, and the Spring reference says a checked exception does not roll back. Django's manual commit is R2 for the same reason: it is documented, and `atomic()` is the API Django tells applications to use.

The earlier PPCS category A result, `TX-01A.caught-error-then-commit`, is this same PostgreSQL behavior. It does not depend on client-side injection. Category C results still do: withheld or rewritten `ROLLBACK` / `ROLLBACK TO SAVEPOINT` (`TX-02`, `TX-03`). Category B and D results still do: terminated backends and a discarded commit reply (`TX-01B`). This run does not move those into production-reachable defects.

Deadlock (`40P01`), serialization failure (`40001`), and statement timeout (`57014`) were not executed. Each aborts the transaction the way `23505` does, and a later `COMMIT` is the same command-tag path. The framework difference already observed is Spring's checked-exception rollback rule, which this run covered. Connection loss during `COMMIT` remains an operational fault, not a no-fault scenario.

## Upstream

No issues were filed.

- Kysely's public `isCommitted` flag is the clearest false report. A search did not find an existing report of `isCommitted` remaining true when PostgreSQL answered `COMMIT` with `ROLLBACK`.
- Knex issue [6141](https://github.com/knex/knex/issues/6141) is adjacent: a `COMMIT` that throws, including deferred constraints, is swallowed by manual `trx.commit()`. The case here does not throw.
- pgx treats command tag `ROLLBACK` as a failed commit. node-postgres, psycopg, and pgjdbc leave that tag for the caller, or do not surface it. Lucid, MikroORM, TypeORM, Knex, Kysely, SQLAlchemy Core, and Spring then treat a resolved commit as success.
- Spring's `afterCommit` ran for a transaction `pg_xact_status()` reported aborted. That is the hook an application would use to send mail or enqueue work.

### Filing status, recorded 2026-10-23

The sentence "No issues were filed" is the state of this investigation when the run report was written. It is not the current filing status. Current status is [`docs/upstream-submissions.md`](../../docs/upstream-submissions.md). This note did not re-query GitHub. The links are the tracker's record.

Overlapping findings were filed from other writeups, or from the drafts in [`upstream-drafts/`](upstream-drafts/README.md). Do not file a second copy:

- Knex `transaction()` resolving on this `COMMIT` is [knex#6547](https://github.com/knex/knex/issues/6547) (K1, submitted 2026-10-17). [`upstream-drafts/knex.md`](upstream-drafts/knex.md) restates it and must not be filed.
- MikroORM `em.transactional()` resolving on this `COMMIT` is [mikro-orm#8476](https://github.com/mikro-orm/mikro-orm/issues/8476) (M3, submitted 2026-10-18). Closed 2026-10-22 as completed via [#8499](https://github.com/mikro-orm/mikro-orm/pull/8499). The 7.2.6-dev.19 follow-up rejects both calls. npm `latest` was still 7.2.5.
- Lucid reporting success, and running `after('commit')`, is [lucid#1205](https://github.com/adonisjs/lucid/issues/1205) (L2, submitted 2026-10-21).
- Whether pgjdbc `Connection.commit()` should report the rollback tag is [pgjdbc#4494](https://github.com/pgjdbc/pgjdbc/issues/4494) (J1, submitted 2026-10-19). The use case was answered on 2026-10-21. No second pgjdbc issue.
- Kysely `isCommitted` is [kysely#2157](https://github.com/kysely-org/kysely/issues/2157) (Y2, filed 2026-10-21).
- psycopg `Connection.commit()` is [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453) (P1, filed 2026-10-21).
- TypeORM `afterTransactionCommit` is [typeorm#12992](https://github.com/typeorm/typeorm/issues/12992) (T3, filed 2026-10-21).
- Drizzle `db.transaction()` is [drizzle-orm#6572](https://github.com/drizzle-team/drizzle-orm/issues/6572) (D1, filed 2026-10-22).
- Prisma `$transaction()` was posted as a [comment on prisma/orm#20496](https://github.com/prisma/orm/issues/20496#issuecomment-6372520392) (PI1, 2026-10-23), an existing report of the same case, not as a new issue.

Still a draft, not a submission: Spring `afterCommit` (S1). Filing it needs explicit approval of the exact text. S1 waits on pgjdbc #4494.

## Next step

Score this pattern in the longitudinal persistence ownership benchmark: catch a real database error inside a supported transaction API, finish that API normally, and compare the return value and commit hooks with an independent read of what was committed. Keep connection reuse as a separate score. The reuse observed here was safe, so a benchmark that only checks the next request would miss the false commit.

Do not add adapters to this catalog before that scoring exists. Drizzle, Prisma, and Hibernate were out of scope for these rows. Another SQLSTATE would repeat this mechanism unless a framework branches on it, and the branch this run found is Spring's checked-exception rule.

Recorded 2026-10-23. Later PPCS adapters, including Drizzle, Prisma, and Hibernate, are in the root README. They are not rows in this catalog. This catalog was not rerun.

Sequencing, and the rule that the benchmark is a separate program, are in [`docs/research-master-plan.md`](../../docs/research-master-plan.md) and [`docs/research-roadmap.md`](../../docs/research-roadmap.md). Writing those plans does not authorize new adapters or a new run of this catalog.
