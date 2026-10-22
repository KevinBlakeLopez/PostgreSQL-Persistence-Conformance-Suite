# JVM persistence comparison

Recorded jOOQ run: [`reports/examples/2026-10-22T12-58-46Z-d4a7fc`](../../reports/examples/2026-10-22T12-58-46Z-d4a7fc/summary.md), jOOQ 3.21.9, pgjdbc 42.7.14, Java 27, PostgreSQL 18.6. Three repetitions agreed. CTL-01 and `pg-control` held.

The other columns are earlier recordings, not the same process. They use the same catalog and the same PostgreSQL 18.6 image unless a finding says otherwise. Versions and run ids:

| Adapter | Run | Versions |
| --- | --- | --- |
| JDBC control | [`2026-10-19T12-51-00Z-0a0698`](../../reports/examples/2026-10-19T12-51-00Z-0a0698/summary.md) | pgjdbc 42.7.14. `correct` reads `PgConnection.getTransactionState()` before `commit()`. `unsafe` treats a returning `commit()` as success and calls `setAutoCommit(true)` after a failed `rollback()`. |
| Spring JDBC | [`2026-10-18T16-08-25Z-9b025d`](../../reports/examples/2026-10-18T16-08-25Z-9b025d/summary.md) | Spring Framework 7.0.9 `TransactionTemplate` and `JdbcTemplate` |
| Spring transaction management | [`2026-10-19T15-02-38Z-8a2f4d`](../../reports/examples/2026-10-19T15-02-38Z-8a2f4d/summary.md) | Spring Framework 7.0.9 `DataSourceTransactionManager`. The cells below are the programmatic mode. Declarative agreed on every case it ran. |
| Hibernate | [`2026-10-21T15-45-57Z-c3c03b`](../../reports/examples/2026-10-21T15-45-57Z-c3c03b/summary.md) | Hibernate ORM 7.4.13.Final, Java 21.0.12.1 |
| jOOQ | [`2026-10-22T12-58-46Z-d4a7fc`](../../reports/examples/2026-10-22T12-58-46Z-d4a7fc/summary.md) | jOOQ 3.21.9. The cells below are `DSLContext.transaction` unless the cell says `jdbc`. |

Per-case reports: [`jdbc-control/FINDINGS.md`](../jdbc-control/FINDINGS.md), [`spring-jdbc/FINDINGS.md`](../spring-jdbc/FINDINGS.md), [`spring-tx/FINDINGS.md`](../spring-tx/FINDINGS.md), [`hibernate/FINDINGS.md`](../hibernate/FINDINGS.md), [`FINDINGS.md`](FINDINGS.md).

## Transaction completion

TX-01A catches a unique violation and lets the normal completion path run. PostgreSQL has already aborted the transaction. A later `COMMIT` is answered with command tag `ROLLBACK` and persists nothing.

| Adapter | Reported | What reached PostgreSQL | Mechanism |
| --- | --- | --- | --- |
| JDBC `correct` | rolled back | `COMMIT` was sent. `commit()` returned. The policy reported rolled back because the driver state was `FAILED` before the call | exercised. Last statement `COMMIT` |
| JDBC `unsafe` | committed | the same `commit()` return | exercised |
| Spring JDBC | committed | `Connection.commit` then `setAutoCommit(true)`. The session had closed at `after-end` | null |
| Spring TX | committed | the same trace | null |
| Hibernate | committed | `Connection.rollback` from `FAILED` to `IDLE`. No `Connection.commit`. `hibernate.jpa.compliance.transaction` was false, so `commit()` did not throw | null. The session had closed |
| jOOQ `native` | committed | `Connection.commit` from `FAILED` to `IDLE`, then `setAutoCommit(true)`. `commitEnd` ran. xid 33422 aborted | null. The session had closed |
| jOOQ `jdbc` | committed | the application called `Connection.commit()`. xid 33435 aborted. Last statement `COMMIT` | exercised |

jOOQ's two modes agree with each other and with Spring and with `jdbc-control` `unsafe`. Hibernate's failure is a different completion: the transaction is marked rollback-only, `ROLLBACK` is sent, and the method still returns. jOOQ sends `COMMIT` and reports the void return.

When the `23505` is allowed to leave the jOOQ callback, the probe recorded `rollback_calls=1`, `commit_calls=0`, fate `aborted`, marker absent. That path is not the catalog case. Spring's uncaught path and jOOQ's escaping path both roll back. The catalog case is the catch.

## Failure propagation

pgjdbc 42.7.14 `Connection.commit()` does not return the command tag. `Statement.execute("COMMIT")` on an aborted transaction stored update count 0 and no warning, in the jOOQ probe and in the earlier JDBC-control probe. `DefaultConnectionProvider.commit` wraps an `SQLException` and otherwise returns. On TX-01A there was no `SQLException`.

`jdbc-control` `correct` avoids the false success by reading `PgConnection.getTransactionState()` before `commit()`. That read is driver-specific. jOOQ's `DefaultTransactionProvider` does not do it. Spring's `DataSourceTransactionManager` does not do it. The tag is not sitting in an object jOOQ then drops.

On `TX-01B.commit-reply-unseen`, jOOQ, Spring, and Hibernate all reported `failed` after pgjdbc threw. The transaction had committed. TX-01B.2 was not exercised for those adapters. jOOQ's `commitEnd` ran from a `finally` even though `commit()` threw, and a cleanup `rollback` also threw. The result mapping uses the exception, not `commitEnd`.

`TX-01B.commit-reply-discarded` is NOT_RUN for every JVM adapter in this table. `commit()` does not return while the driver still reports a transaction in progress.

## Connection safety

TX-03 withholds the top-level `ROLLBACK` once. The transaction stays open. The next unit uses the same pool of one connection.

| Adapter | Unit 1 fate | Doomed marker | Same backend | Classification |
| --- | --- | --- | --- | --- |
| JDBC `correct` | aborted. The connection is closed. `setAutoCommit(true)` is not called | absent | no | PASS |
| JDBC `unsafe` | committed. `setAutoCommit(true)` after the failed `rollback()` | visible | yes | FAIL |
| Spring JDBC pooled | committed. Spring restores autocommit after `rollback()` throws | visible | yes | FAIL |
| Spring TX pooled | committed. The trace after the withhold is `setAutoCommit(true)` | visible | yes | FAIL |
| Hibernate pooled | aborted. Hibernate does not restore autocommit. HikariCP rolls back on `close` | absent | yes | PASS |
| jOOQ `pooled` | committed. `brace` calls `setAutoCommit(true)` from driver state `OPEN`. Last statement `COMMIT`. The API still reported rolled back | visible | yes, pid 1723032 | FAIL |
| jOOQ `jdbc-pooled` | aborted. The application closes without `setAutoCommit(true)`. Last statement `ROLLBACK` | absent | yes, pid 1723171 | PASS |

The jOOQ pooled failure is the Spring and `unsafe` ending. The JDBC-owned pool mode is the Hibernate ending: close the connection, and HikariCP sends `ROLLBACK`. The difference is who calls `setAutoCommit(true)` after `rollback()` has thrown. pgjdbc implements that call as `commit()` when a transaction is still open.

The statement-error case passes for Spring, Hibernate, jOOQ `pooled`, and jOOQ `jdbc-pooled`. The transaction is already aborted. A later `COMMIT` does not persist the row. jOOQ `pooled` still shows last statement `COMMIT` on that pass. The pass is the aborted fate, not a `ROLLBACK` statement from jOOQ.

## Savepoints

jOOQ nested `transaction()` and Spring `PROPAGATION_NESTED` are JDBC savepoints. Hibernate has no savepoint API in its adapter and declares TX-02 and TX-04 unsupported.

| Case | JDBC `correct` | Spring JDBC | Spring TX | jOOQ `native` and `jdbc` |
| --- | --- | --- | --- | --- |
| TX-02 withhold | PASS. The outer transaction is rolled back after the savepoint rollback throws | FAIL. Both markers committed | FAIL. Both markers committed | FAIL. Both markers committed |
| TX-02 rewrite `3B001` | PASS. The outer transaction is rolled back | FAIL. Reported commit, fate aborted, neither marker | FAIL. Same | FAIL. Same. `commit()` returned from `FAILED` |
| TX-04 nested failure contained | PASS | NOT_RUN | PASS | PASS. Outer marker visible, inner absent |
| TX-04 nested released, outer rollback | PASS | NOT_RUN | PASS | PASS. Neither marker visible |
| TX-04 independent inner | UNSUPPORTED | NOT_RUN | PASS (`REQUIRES_NEW`) | UNSUPPORTED |

On the jOOQ withhold, `transactionResult0` rethrows the callback exception and suppresses `DataAccessException: Cannot rollback transaction`. The outer callback sees the original application error, which is also what a completed savepoint rollback looks like, and returns. The outer `commit()` then persists the inner write. The JDBC `correct` policy rolls the outer transaction back when `rollback(Savepoint)` throws. jOOQ's provider does not.

TX-04 shows the savepoint path when `rollback(Savepoint)` returns. The nested failure is contained. That is the same shape as Spring TX.

## Isolation

| Adapter | Managed `SERIALIZABLE` | Explicit `SERIALIZABLE` |
| --- | --- | --- |
| JDBC `correct` | PASS. `setTransactionIsolation` before `setAutoCommit(false)` | PASS. The same calls. JDBC has no separate handle |
| JDBC `unsafe` | FAIL. Isolation is not requested | FAIL |
| Spring JDBC | NOT_RUN | NOT_RUN |
| Spring TX | PASS | PASS in the programmatic mode |
| Hibernate | UNSUPPORTED | UNSUPPORTED |
| jOOQ `native` | PASS. `setTransactionIsolation(8)` while autocommit was still true, then `setAutoCommit(false)`. `current_setting` was `serializable`. `SIReadLock` on `item` | not run. `transaction()` returns no handle |
| jOOQ `jdbc` | PASS. The application calls `setTransactionIsolation` before `setAutoCommit(false)` | PASS. The same calls |

The probe set isolation after a statement had opened the transaction. pgjdbc threw `25001` and the level stayed `read committed`. jOOQ's `brace` method does not use that order. The catalog pass is the order above. Requesting the level is not itself the proof. The proof in the run is `current_setting('transaction_isolation')` plus the runner's `SIReadLock`.

## Outcome observability

`Connection.commit()` does not tell the caller whether PostgreSQL's command tag was `COMMIT` or `ROLLBACK`. jOOQ adds `commitStart` and `commitEnd`. `commitEnd` also runs when `commit()` throws, because it is in a `finally`. On TX-01A it ran after `commit()` returned. On the lost reply it ran after `commit()` threw, and the method still threw. The result this adapter reports follows the exception, not the listener.

jOOQ has no public flag in this adapter's path that distinguishes a `FAILED` transaction from an open one before `commit()`. `PgConnection.getTransactionState()` can. The JDBC `correct` policy uses it. jOOQ's default provider does not.

A reported rollback is not a database rollback. On pooled TX-03, jOOQ rethrew the callback exception, `rollbackEnd` ran, and PostgreSQL committed the doomed row because `setAutoCommit(true)` sent `COMMIT`.

## Where the transaction owner sits

jOOQ 3.21's manual says the library can use an existing JDBC transaction or its own `transaction` API. `DefaultTransactionProvider` is documented as entirely based on JDBC, for `DefaultConnectionProvider`. The measured path is:

1. PostgreSQL aborts the transaction on `23505` and, if `COMMIT` is sent, completes that command with tag `ROLLBACK` without a new error.
2. pgjdbc `PgConnection.commit` sends `COMMIT`, applies `ReadyForQuery`, and returns void. The tag is not a return value. This is [pgjdbc#4494](https://github.com/pgjdbc/pgjdbc/issues/4494), already submitted. No second pgjdbc issue.
3. `DefaultTransactionProvider.commit` calls `connection.commit()` for the outermost scope. `DefaultConnectionProvider.commit` returns when `commit()` returns.
4. `DefaultDSLContext.transactionResult0` returns normally. This adapter maps that return to `committed`.

The JDBC-owned mode stops at step 2 and the application treats the return as success. The DSL insert is the same. The transaction outcome follows the commit call, not the way the `INSERT` was built.

Hibernate's TX-01A path does not reach step 2. `Transaction.commit()` sends `ROLLBACK` and returns because the session is rollback-only and JPA transaction compliance is off. That is entity-session state, not the SQL dialect. It is still a reported commit of an aborted transaction. It is a different mechanism.

Spring reaches step 2 through `DataSourceTransactionManager` and also reports success. jOOQ's provider is a thinner wrapper around the same JDBC calls, including `setAutoCommit(true)` in `brace` after a failed rollback. That cleanup is why pooled TX-03 commits the open transaction. Hibernate skips that restore, and HikariCP's close rolls the connection back.

Nothing in these runs shows the SQL DSL producing a stricter transaction result than the JDBC calls underneath it. The runs do show two transaction-owner differences that are measured: jOOQ rolls back when the callback throws and commits when it returns, and jOOQ's provider restores autocommit after rollback, which pgjdbc can turn into `COMMIT` if the transaction is still open.
