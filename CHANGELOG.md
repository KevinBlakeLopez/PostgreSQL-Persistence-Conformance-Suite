# Changelog

Results from different versions are not comparable: each version can change what the evidence must show before a case passes or fails. Every run records the harness digest that identifies its rules, and `--expect` refuses to compare runs whose digests differ.

## Unreleased

- **Plain JDBC runs a positive and a negative transaction policy.** PostgreSQL JDBC 42.7.14 on Java 21, with `DriverManager` and no pool, is recorded in `reports/examples/2026-10-19T12-51-00Z-0a0698`. `correct` passes every case it executes. It reports a rollback when `PgConnection.getTransactionState()` was `FAILED` before `Connection.commit()` returned, and it closes a connection whose `rollback()` threw instead of calling `setAutoCommit(true)`. `unsafe` fails eight cases. Those include the Spring JDBC endings for an aborted `COMMIT` reported as success, a withheld savepoint rollback that commits both markers, a rejected savepoint rollback reported as a commit, and a withheld top-level `ROLLBACK` followed by `COMMIT` when autocommit is restored. `TX-01B.commit-reply-discarded` is NOT_RUN. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent. The per-case report is `adapters/jdbc-control/FINDINGS.md`.
- **SQLAlchemy Core runs the transaction cases without an ORM Session.** SQLAlchemy 2.1.5 `Connection.begin()` and `Connection.begin_nested()`, through psycopg 3.3.6, is recorded in `reports/examples/2026-10-19T12-35-51Z-64c5c5`. Three framework FAILs: `TX-01A.caught-error-then-commit`, with the COMMIT-answered-ROLLBACK mechanism exercised, and both savepoint-rollback cases. The withheld savepoint rollback commits both markers. The rejected savepoint rollback, and TX-01A, report a commit after `commit()` returns while the connection is `INERROR` and PostgreSQL has aborted the transaction. Those two endings match the ORM adapter's rejected-savepoint FAIL. The ORM run left TX-01A INCONCLUSIVE because `Session._flush` rolled back before `before-end`. `TX-01B.commit-reply-discarded` is NOT_RUN. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent. The per-case report is `adapters/sqlalchemy-core/FINDINGS.md`.
- **Spring JDBC runs the transaction-failure cases.** Spring Framework 7.0.9 `TransactionTemplate` on `DataSourceTransactionManager`, with `JdbcTemplate` and PostgreSQL JDBC 42.7.14, is recorded in `reports/examples/2026-10-18T16-08-25Z-9b025d`. Native mode is `DriverManagerDataSource`. TX-03 runs only in the pooled mode, HikariCP 7.1.0 with `maximumPoolSize` 1. Four framework FAILs: `TX-01A.caught-error-then-commit`, both savepoint-rollback cases, and `TX-03.rollback-not-sent`. The withheld savepoint rollback commits both markers. The rejected savepoint rollback reports a commit of a transaction PostgreSQL aborted. The withheld top-level `ROLLBACK` is followed by pgjdbc's `COMMIT` when autocommit is restored, so the failed transaction is committed and the pool reuses the backend. `TX-01B.commit-reply-discarded` is NOT_RUN. The per-case report is `adapters/spring-jdbc/FINDINGS.md`.
- **Django and SQLAlchemy run the transaction-failure cases.** Django 6.1.2 `transaction.atomic()` is recorded in `reports/examples/2026-10-18T13-08-22Z-6d8443`. Its one framework FAIL is `TX-02.savepoint-rollback-not-sent`. SQLAlchemy 2.1.5 `Session.begin()` is recorded in `reports/examples/2026-10-19T00-49-25Z-3673a3`. It fails both TX-02 cases. The withheld-savepoint ending matches the Node adapters that commit both markers. The rejected-savepoint ending is different: the API reports a commit, the session is idle, and PostgreSQL aborted the transaction. `TX-01B.commit-reply-discarded` is NOT_RUN for both. The per-case reports are `adapters/django/FINDINGS.md` and `adapters/sqlalchemy/FINDINGS.md`.
- **MG-02 and MG-03 run on Lucid and `pg-control`.** Seven cases: a held migration, a first deployment, a lost session, an idle-session timeout, a valid reversal, a migration with no reversal, and a reversal that fails. Each role is its own process, named `ppcs-A`, `ppcs-B` or `ppcs-C`. The harness's own sessions stay excluded by backend PID together with `ppcs-observer`. On Lucid 22.4.2 the idle-session timeout is inconclusive, because the session inside the migration is not idle, and a migration with no reversal is reported reverted while its marker remains. The recorded run is `reports/examples/2026-10-18T00-11-46Z-95887b`.

## 0.3.0 (unreleased)

A requested isolation level.

- **New family: TX-05.** Two cases, one per API form (managed and explicit), request SERIALIZABLE.
  - **TX-05.1.** On PostgreSQL, a transaction the API started at a requested level runs at that level or a stricter one. A PASS needs two observations that agree: `current_setting('transaction_isolation')`, read in the same statement as the captured ID, and an `SIReadLock` the runner sees on `item` or one of its indexes, after a confirmed read of `item`.
  - **TX-05.2.** An API whose documentation accepts a level PostgreSQL supports does not reject a valid request. A rejection fails it only when its cause is established: the error carries no PostgreSQL SQLSTATE and no operating-system error code, and a plain transaction through the same form was bound at `baseline`.
- **INCONCLUSIVE reasons.** A TX-05 result records why it is INCONCLUSIVE, in `evaluation.inconclusive_reason`: `observation-conflict`, `evidence-missing`, `environment`, or `cause-not-established`. Other families keep none.
- **Evidence.** The observer records each `SIReadLock`'s target, whether the backend held an `AccessShareLock` on `item`, and `backend_xmin` as a diagnostic. A checkpoint that declares `captures_isolation` carries `transaction_isolation`.
- **Adapters.** Lucid, MikroORM and TypeORM implement both forms. `pg-control` `correct` starts the transaction with `BEGIN ISOLATION LEVEL SERIALIZABLE`; `unsafe` sends a plain `BEGIN`.

Results under 0.2.0 and 0.3.0 are not comparable: the harness digest changed.

## 0.2.0 (2026-10-17)

Hardening after an independent methodology review.

- **New case: `TX-03.statement-error-rollback-not-sent`.** A failed statement leaves unit 1 in an aborted transaction block when its `ROLLBACK` is withheld; the open-block case leaves an open transaction. A unit of work handed the connection then fails loudly with `25P02`, instead of silently joining a transaction. The case's fault declares the signature it must leave (`aborted-block`).
- **Runner sessions.** These are now identified by backend PID together with the runner's `application_name`. An adapter connection that uses the runner's name is counted against the pool.
- **Evidence.**
  - Fates are recorded at report time (`after-end`), when the framework's API returns, as well as after the framework has gone. A fate decided at teardown is reported as such.
  - A captured transaction ID must belong to the session that reported it.
  - Writes are confirmed in `pg_locks`. Visible markers are attributed by `xmin`. The runner checks for stray rows and fixture changes.
  - Client-side faults are confirmed on the server, at `after-fault`, before the framework sees their error.
  - TX-01A records whether COMMIT reached the server.
- **Classification.**
  - `TX-01B.conn-lost-before-commit` is a known outcome: a truthful report of rollback passes.
  - Without a declared rollback-claim channel, TX-01B.2 is "not exercised", never held.
  - The invariants evaluated must equal those the case declares.
  - A runtime `unsupported` and a repeated checkpoint are protocol errors. `pending` is an outcome of its own.
- **Run gates.**
  - Every case runs three times.
  - A result counts only if the run's own controls held.
  - Runs record the harness digest.
  - The server profile is asserted, and the runner's connections have timeouts.
- **Labels.**
  - Unsupported cases have a class: `capability-absent` or `not-applicable-by-design`.
  - `recommended` modes cite documentation.
  - Native forms are recorded.

## 0.1.0 (2026-10-16)

The initial suite:

- the observation controls (CTL-01), and TX-01A, TX-01B, TX-02, TX-03 and TX-04;
- adapters for Lucid, MikroORM and TypeORM;
- `pg-control`, with positive and negative control modes.
