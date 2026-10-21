# Hibernate transaction recovery, PPCS run 2026-10-21T15-45-57Z-c3c03b

Hibernate ORM 7.4.13.Final, Jakarta Persistence 3.2.0, PostgreSQL JDBC 42.7.14, Java 21.0.12.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). HikariCP 7.1.0 is used only in the pooled mode. Three repetitions agreed. CTL-01 and `pg-control` held their gates for every Hibernate scenario result below.

Native mode is `Session.openSession` and `Transaction.begin` on a `DriverManager` DataSource. `hibernate.dialect` is not set. The factory selected `org.hibernate.dialect.PostgreSQLDialect`. Flush mode is `AUTO`. `hibernate.hbm2ddl.auto` and `jakarta.persistence.schema-generation.database.action` are `none`. The coordinator is `jdbc`. Connection handling is `DELAYED_ACQUISITION_AND_RELEASE_AFTER_TRANSACTION`. `hibernate.jpa.compliance.transaction` was read back false. `connectionProviderDisablesAutoCommit` was read back false, so Hibernate calls `Connection.setAutoCommit(false)` at begin.

A returning `Transaction.commit()` is reported committed. A returning `Transaction.rollback()`, followed by the application error, is reported rolled back. Any other exception is reported failed. TX-01A catches the unique violation and then calls `commit`. It does not call `rollback` first. CTL-01.rollback and TX-03 call `rollback` when the work throws and the transaction is still active.

`TX-01B.commit-reply-discarded` is NOT_RUN. On this server a successful `Connection.commit` moved pgjdbc from `OPEN` to `IDLE` before `commit()` returned (`commit_returned_while_in_progress=false`). pgjdbc does not return from `commit()` until `ReadyForQuery`. Closing the socket after `commit()` returns is not that case.

## Cases

| Case | Fault | Hibernate reported | PostgreSQL at report time, and after exit | Same backend reused | Invariant |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed. `Connection.commit` went `OPEN` to `IDLE`, then `setAutoCommit(true)` while `IDLE` | xid 15003 committed at `after-end`; marker visible. Pooled repetition xid 15015 committed | not a reuse case | CTL-01.1 held |
| `CTL-01.rollback` | none | rolled back (`AppException` after `Transaction.rollback()` returned) | xid 15027 aborted at `after-end`; marker absent. Pooled repetition xid 15039 aborted | not a reuse case | CTL-01.2 held |
| `TX-01A.caught-error-then-commit` | A, caught `23505` during `persist` | committed. `Transaction.commit()` returned. Trace: `Connection.rollback` `FAILED` to `IDLE`, then `setAutoCommit(true)` while `IDLE`. No `Connection.commit` | xid 15051 aborted at `before-end` (`idle in transaction (aborted)`) and at `after-end`; marker absent. The backend was gone at `after-end` | not a reuse case | TX-01A.1 failed. The runner's mechanism check is null: the session had closed |
| `TX-01B.conn-lost-before-commit` | B, backend terminated at `before-end` | failed (`TransactionException` `57P01`). `Connection.commit` threw while the driver state stayed `OPEN`. The following `Connection.rollback` threw the same way | xid 15063 aborted at `after-end`; marker absent | the terminated backend was not reused | TX-01B.1 held. TX-01B.2 is not an invariant of this case |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run | not run |
| `TX-02.savepoint-rollback-not-sent` | C | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-02.savepoint-rollback-rejected` | C | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-02.conn-lost-before-savepoint-rollback` | B | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-03.rollback-not-sent` | C, client-reject. Hibernate's `Connection.rollback` was withheld once. At `after-fault` the session was idle in transaction | failed (`TransactionException`: ROLLBACK was not sent). Unit 2 reported committed after the pool checkout | unit 1 xid 15076 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 15077 committed; next visible. At `after-unit1` the session was idle and its last statement was `ROLLBACK` | yes. Both units used pid 1235663 | TX-03.1 and TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` | C, client-reject after `23505`. At `after-fault` the session was idle in transaction (aborted) | failed (`TransactionException`: ROLLBACK was not sent). The statement error was `ConstraintViolationException` `23505`. Unit 2 reported committed | unit 1 xid 15091 aborted; doomed absent. Unit 2 xid 15092 committed; next visible. At `after-unit1` the session was idle and its last statement was `ROLLBACK` | yes. Both units used pid 1235810 | TX-03.1 and TX-03.2 held |
| `TX-03.conn-lost-in-transaction` | B, backend terminated at `unit1-after-write` | failed (`TransactionException` `57P01` from `rollback`) | unit 1 xid 15106 aborted; doomed absent. The terminated pid 1235957 was gone at `after-unit1`. Unit 2 xid 15107 committed on pid 1235966 | no | TX-03.1 and TX-03.2 held |
| `TX-04.nested-failure-contained` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-04.nested-released-outer-rollback` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-04.independent-inner` | none | UNSUPPORTED (not applicable by design) | not run | not run | not run |
| `TX-05.managed-serializable` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `TX-05.explicit-serializable` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-02.held` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-02.first-deployment` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-02.session-loss` | B | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-02.idle-session-timeout` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-03.valid-reversal` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-03.no-reversal` | none | UNSUPPORTED (capability absent) | not run | not run | not run |
| `MG-03.failing-reversal` | none | UNSUPPORTED (capability absent) | not run | not run | not run |

## TX-01A

The duplicate insert failed inside `persist` with `ConstraintViolationException` and SQLSTATE `23505`. `GenerationType.IDENTITY` executes the insert to obtain the key, so the exception is not deferred to `flush`. Before `commit`, the transaction status was `MARKED_ROLLBACK`, `getRollbackOnly()` was true, the session was open, and both the valid marker and the failed `Uniq` were still in the persistence context. The marker's in-memory id was `1`. At `before-end` PostgreSQL reported the session `idle in transaction (aborted)`, `pg_xact_status` was `aborted`, and the last statement was the failed `insert into uniq ... RETURNING *`.

`Transaction.commit()` then returned. The JDBC trace for that completion is Hibernate's `JdbcResourceLocalTransactionCoordinatorImpl`, not a pool:

1. `Connection.rollback`, driver state `FAILED` to `IDLE`.
2. `Connection.setAutoCommit(true)`, driver state already `IDLE`.
3. `Connection.close`, from `DataSourceConnectionProvider`, which is the release after the transaction.

There is no `Connection.commit`. xid 15051 stayed aborted and the marker was absent. After `commit()` returned, and before `session.close`, the status was `NOT_ACTIVE`, `contains(marker)` was false, and the Java object's id was still `1`. `SessionImpl.afterTransactionCompletion` calls `internalClear()` when the completion is not successful and the session is still open. The in-memory id is not evidence that PostgreSQL committed.

The runner records `mechanism_exercised` null, with the detail that the session had closed when the API returned. Release-after-transaction closes this mode's `DriverManager` connection inside `commit`, so `after-end` cannot see a last statement. The adapter trace is the evidence that `COMMIT` was not sent. This is not the COMMIT-answered-ROLLBACK ending: PostgreSQL was not asked to commit.

The PPCS invariant still fails. The adapter reports committed because `commit()` returned, and xid 15051 was aborted. That report is the application-visible return value. It is the behavior of `commitRollbackOnly` when `hibernate.jpa.compliance.transaction` is false: roll back, and do not throw. The flag was read back false. A FAIL here is the PPCS counterexample to reporting success. It is not, on this evidence, a violation of that Hibernate source path. The JPA `EntityTransaction` contract would throw `RollbackException`. Hibernate applies that contract only when the compliance flag is on. This adapter does not turn the flag on. Doing so would be a different mode.

## Native SQL diagnostic

The probe repeats the caught-error-then-commit shape three ways. It is not a catalog mode and it does not replace the entity result. All three left the transaction `MARKED_ROLLBACK`, called `rollback` rather than `commit`, reported committed because `commit()` returned, and left `pg_xact_status` `aborted` with the marker absent.

| Path | Where `23505` was raised | `commit` sent | `rollback` sent | Fate |
| --- | --- | --- | --- | --- |
| `session.persist` of `Uniq` | `persist` | no | yes, `FAILED` to `IDLE` | aborted |
| `createNativeMutationQuery(...).executeUpdate()` | `executeUpdate` | no | yes, `FAILED` to `IDLE` | aborted |
| `session.doWork` running the insert | `doWork` | no | yes, `FAILED` to `IDLE` | aborted |

`doWork` is JDBC on the session's connection. `JdbcCoordinatorImpl.coordinateWork` calls `afterFailedStatementExecution`, and `PostgreSQLDialect.causesRollback` returns true, so the work is marked rollback-only before the exception reaches the application. It is not a bypass of Hibernate's transaction state. On these versions the entity path and the native SQL path do not differ in the transaction outcome.

## TX-01B

`Connection.commit` was attempted after the runner had terminated the backend. pgjdbc threw `PSQLException` and the driver state stayed `OPEN`. Hibernate's `commitConnection` then attempted `Connection.rollback`, which threw the same way, and reported `TransactionException` with SQLSTATE `57P01` (`Unable to commit against JDBC Connection`). The adapter reported failed. It did not report committed, and it did not report rolled back. xid 15063 was aborted and the marker was absent. TX-01B.1 held.

The lost-reply case is NOT_RUN. A successful commit in the probe returned only after the driver state was `IDLE`.

## TX-03

The fault withholds `Connection.rollback` on the connection Hibernate calls, once, before pgjdbc sends. Hibernate's `rollback` throws `TransactionException`, status becomes `FAILED_ROLLBACK`, and `afterCompletion` does not run. Hibernate therefore does not call `setAutoCommit(true)` on that failure. The trace's later `setAutoCommit(true)` is `com.zaxxer.hikari.pool.PoolBase`.

HikariCP 7.1.0 `ProxyConnection.close` does this when the connection is returned:

```java
if (isCommitStateDirty && !isAutoCommit) {
    delegate.rollback();
}
if (dirtyBits != 0) {
    poolEntry.resetConnectionState(this, dirtyBits);
}
```

`markCommitStateDirty` runs from statement execution when autocommit is off. `resetConnectionState` calls `setAutoCommit(true)` only when the autocommit bit is dirty. On the withheld-rollback case the order observed on the physical connection was:

1. `Connection.rollback`, `OPEN` to `IDLE`, caller `ProxyConnection`. This is the pool's `close`, not Hibernate's withheld call.
2. `Connection.setAutoCommit(true)`, `IDLE` to `IDLE`, caller `PoolBase`.

The doomed marker stayed absent. Unit 2 reused pid 1235663 under a new xid, 15077, and committed. At `after-unit1` the session was idle and its last statement was `ROLLBACK`.

The statement-error case is the same shape with the driver state `FAILED` rather than `OPEN` at the pool's rollback: the unique violation had already aborted the transaction, and Hikari's `rollback` ended the aborted block (`FAILED` to `IDLE`) before `setAutoCommit(true)`. Unit 2 reused pid 1235810 under xid 15092.

The connection-loss case is different. Hikari's `rollback` threw (`OPEN` stayed `OPEN`, `57P01`) and `PoolBase` closed the broken connection. Unit 2 used a new backend, pid 1235966.

Hibernate did not restore autocommit after the failed rollback, so the sequence that committed Spring's withheld transaction was not Hibernate's `afterCompletion`. The `ROLLBACK` that reached PostgreSQL was HikariCP's. The following `setAutoCommit(true)` ran only after that rollback had already left the driver `IDLE`. This pass does not show Hibernate discarding the connection on its own.

## Unsupported cases

`Transaction` has no savepoint operation. Its javadoc says there is at most one uncommitted transaction for a `Session`. `beginTransaction` returns the active transaction when one exists. TX-02 and the two savepoint TX-04 cases are capability-absent. JDBC savepoints through `doWork` were not used. They would not be Hibernate's transaction API.

`TX-04.independent-inner` is not applicable by design. There is no propagation mode that promises an independent transaction while an outer one stays open. A second `Session` would be application code coordinating two physical transactions. The adapter does not add that coordination.

`Session.inTransaction`, `SessionFactory.inTransaction`, `beginTransaction`, and `Transaction` accept no isolation level. `hibernate.connection.isolation` is a connection-provider setting, and `JdbcSettings` says `DataSourceConnectionProvider` does not apply it. This adapter uses a DataSource. Both TX-05 cases are capability-absent. No `SET TRANSACTION` was added to manufacture a level.

MG-02 and MG-03 are capability-absent. Hibernate is not a migration runner. Schema export stays off. Flyway and Liquibase are not on the classpath.

## Comparison

These are the cases that exercise the same mechanism. Pass counts are not a ranking.

`TX-01A`. Plain JDBC `correct` reads `PgConnection.getTransactionState()` `FAILED` before `commit` and reports rolled back. `unsafe`, Spring JDBC, and Spring transaction management call `Connection.commit` after the transaction is aborted and report committed. SQLAlchemy ORM rolls the transaction back inside the flush, before `before-end`, so that run is INCONCLUSIVE. Hibernate reaches `before-end` still aborted, then `commit()` sends `ROLLBACK` instead of `COMMIT` and returns. The application sees a normal return. Spring and plain JDBC `unsafe` exercise COMMIT-answered-ROLLBACK. Hibernate does not. The PPCS failure is the return value, not a commit command tag.

`TX-03.rollback-not-sent`. Spring's cleanup calls `setAutoCommit(true)` while the withheld transaction is still open. pgjdbc commits it, the doomed marker is visible, and the invariant fails. Hibernate skips `afterCompletion` when `rollback` throws, so it does not make that `setAutoCommit` call. HikariCP then rolls the connection back on `close` and only afterwards sets autocommit, with the driver already `IDLE`. The doomed marker is absent and the next unit has its own xid. The protection that reached PostgreSQL is the pool's. Hibernate's contribution on this path is that it did not restore autocommit after the failed rollback.

`TX-04`. Spring transaction management's `PROPAGATION_REQUIRES_NEW` commits the inner transaction on a second connection and rolls the outer one back. Native Hibernate has no such propagation mode and no savepoint API. Those cases are unsupported here. They are not a measured difference in an equivalent call.

## Upstream

No issue is filed.

The TX-01A return is the source path `JdbcResourceLocalTransactionCoordinatorImpl.commitRollbackOnly` in 7.4.13.Final: if the transaction is marked rollback-only, call `rollback()` and return; throw `RollbackException` only when JPA transaction compliance is enabled. A caller that only sees `commit()` return, and then `getStatus()` `NOT_ACTIVE`, sees the same shape as a commit that succeeded. `wasSuccessful()` is true only for `COMMITTED`, and both the successful CTL-01 commit and this rollback leave `NOT_ACTIVE` after `afterCompletion` restores autocommit, so that flag is not available after the call returns either. `contains(marker)` is true after a real commit and false after this rollback, because the unsuccessful completion clears the persistence context.

A minimal reproduction is the TX-01A sequence in this adapter: persist and flush a valid `item`, persist a duplicate `uniq.code`, catch `ConstraintViolationException`, call `Transaction.commit()` with `hibernate.jpa.compliance.transaction` false. PostgreSQL's xid is aborted. `Connection.commit` is not called. Whether a returning `commit()` should be distinguishable from a successful commit, under the default compliance setting, is a question for Hibernate's maintainers against that source and against the JPA contract the compliance flag selects. This run does not treat the PPCS FAIL as that defect.

TX-03 does not add a Hibernate question. The rollback Hibernate attempted was withheld in this process. The rollback PostgreSQL executed was HikariCP's.

## Limitations

- No savepoint or nested-transaction API, so TX-02 and the savepoint TX-04 cases are not measured.
- No independent-transaction propagation, so `TX-04.independent-inner` is not measured. A second `Session` was not used as a substitute.
- No per-transaction isolation API. `hibernate.connection.isolation` was not set.
- No migration runner. MG-02 and MG-03 are not measured.
- Lost commit replies cannot be observed through pgjdbc 42.7.14. `TX-01B.commit-reply-discarded` is NOT_RUN.
- The runner cannot see the last statement of native TX-01A at `after-end`, because release-after-transaction closes the `DriverManager` connection inside `commit`. The JDBC trace is the evidence that `COMMIT` was not sent.
- On TX-03, Hibernate, pgjdbc, and HikariCP all run. The `ROLLBACK` that reached the server after the withhold is HikariCP's. Hibernate's skipped `afterCompletion` is a separate fact. The pass is not Hibernate discarding the connection by itself.
- Entity persist, native SQL, and `doWork` agreed on this server. That is one version, not a claim about every Hibernate release.
