# Spring transaction management, PPCS run 2026-10-19T15-02-38Z-8a2f4d

Spring Framework 7.0.9 (`spring-tx` 7.0.9, `spring-jdbc` 7.0.9, `spring-aop` 7.0.9, `spring-context` 7.0.9), PostgreSQL JDBC 42.7.14, HikariCP 7.1.0 in the pooled modes, Java 21.0.12.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Three repetitions agreed. CTL-01 and pg-control held their gates for every Spring transaction result below.

`native` is `TransactionTemplate` on `DataSourceTransactionManager` over `DriverManagerDataSource`. `declarative` is `@Transactional` through a JDK proxy and `TransactionInterceptor` on that same manager. Writes are `PreparedStatement` calls on `DataSourceUtils.getConnection`. `JdbcTemplate` is not used. No pool in those modes. The outer boundary is `PROPAGATION_REQUIRED`. A nested scope is `PROPAGATION_NESTED`. An independent inner transaction is `PROPAGATION_REQUIRES_NEW`. `TX-03` runs only in `pooled` and `declarative-pooled` (HikariCP 7.1.0, `maximumPoolSize` 1). The declarative statement-error method uses `rollbackFor = Exception.class`. Category C is a client-side injection in this process, fired once, before pgjdbc sends. A withhold does not reach PostgreSQL. A rewrite does, and PostgreSQL answers. Spring's report is not the verdict.

`TX-01B.commit-reply-discarded` is NOT_RUN. On this server, `Connection.commit()` returned with transaction state `IDLE` after it had been `OPEN`.

## Cases

Declarative matched programmatic on every case both modes ran. The table's report is the programmatic one. The declarative row had the same classification, the same PostgreSQL fate, and the same marker visibility.

| Case | Fault | Spring reported | PostgreSQL at report time, and after exit | Same backend reused | Invariant | Beside plain JDBC `correct` and Spring JDBC |
| --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed | committed; marker visible; session closed in native. Thread-local state clear | not a reuse case | held | same ending |
| `CTL-01.rollback` | none | rolled back (`AppException`) | aborted; marker absent | not a reuse case | held | same ending |
| `TX-01A.caught-error-then-commit` | A, caught `23505` | committed. The boundary returned. Trace: `Connection.commit`, then `Connection.setAutoCommit(true)` | xid 9352 / 9364 aborted at `before-end` (`idle in transaction (aborted)`) and after exit; marker absent. The session was closed at `after-end`, so the runner's mechanism check is null | not a reuse case | TX-01A.1 failed | same ending as Spring JDBC and as `jdbc-control` `unsafe`. `correct` reads `PgConnection.getTransactionState()` `FAILED` and reports rolled back |
| `TX-01B.conn-lost-before-commit` | B | failed (`TransactionSystemException` `57P01`) | aborted; marker absent | the terminated backend was not reused | held | same ending |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run | not run | same as Spring JDBC and plain JDBC. pgjdbc does not return from `commit()` until `ReadyForQuery` |
| `TX-02.savepoint-rollback-not-sent` | C, withhold once. At `after-fault` the session was idle in transaction | committed. Nested call failed (`TransactionSystemException`, application `AppException`) | committed; both markers visible; session closed at `after-outer` | not a reuse case | TX-02.1 failed. TX-02.2 held | same ending as Spring JDBC, Django, and SQLAlchemy. `correct` rolls the outer transaction back |
| `TX-02.savepoint-rollback-rejected` | C, rewrite, reply `3B001`. At `after-fault` the session was idle in transaction (aborted) | committed. Nested call failed (`TransactionSystemException` `3B001`, application `AppException`) | aborted; neither marker visible; session closed | not a reuse case | TX-02.1 failed. TX-02.2 held | same ending as Spring JDBC and SQLAlchemy. The session was closed, not left idle in transaction |
| `TX-02.conn-lost-before-savepoint-rollback` | B | failed (`TransactionSystemException` `08003`). Nested call failed first (`57P01`, application `AppException`) | aborted; neither marker visible; session closed. Trace: `Connection.rollback(Savepoint)` was invoked on the closed connection, then `Connection.commit`, which failed | the terminated backend was not reused | held | the API did not report a commit |
| `TX-03.rollback-not-sent` (pooled) | C, withhold `ROLLBACK` once | failed (`TransactionSystemException`, application `AppException`). Unit 2 committed after 45 ms / 41 ms | unit 1 committed; doomed visible. At `after-unit1` the session was idle. Trace after the withhold: `Connection.setAutoCommit(true)`. Programmatic pids 254455 and 254455 | yes | TX-03.1 failed. TX-03.2 held | same ending as Spring JDBC. `correct` closes the connection and does not call `setAutoCommit(true)` |
| `TX-03.statement-error-rollback-not-sent` (pooled) | C, withhold after `23505` | failed. Programmatic application exception `SqlUnchecked`. Declarative application exception `PSQLException` | unit 1 aborted; doomed absent; unit 2 committed on the same backend | yes | held | same PostgreSQL ending as Spring JDBC. The declarative method's `rollbackFor = Exception.class` is why `ROLLBACK` was the command. The default checked-exception rule was not used |
| `TX-03.conn-lost-in-transaction` (pooled) | B | failed (`TransactionSystemException` `57P01`, application `AppException`) | unit 1 aborted; doomed absent; unit 2 committed on a new backend | no | held | same PostgreSQL ending. The application error did not leave the boundary. The rollback's `57P01` did |
| `TX-04.nested-failure-contained` | none | committed. Nested call rolled back (`AppException`) | committed; outer visible; inner absent. Trace: `Connection.rollback(Savepoint)` then `Connection.commit` | not a reuse case | held | Spring JDBC does not run TX-04. Plain JDBC `correct` passes. `unsafe` fails by putting the outer write inside the savepoint |
| `TX-04.nested-released-outer-rollback` | none | rolled back | both markers absent | not a reuse case | held | same ending as plain JDBC `correct` |
| `TX-04.independent-inner` | none | rolled back. Inner call committed | inner visible; outer absent. Trace: a second `Connection.setAutoCommit(false)`, inner `Connection.commit`, outer `Connection.rollback` | the inner transaction used a second connection. `pool_max` is 2 | held | plain JDBC declares this not applicable by design. Spring has `PROPAGATION_REQUIRES_NEW`. It was not replaced with `NESTED` |
| `TX-05.managed-serializable` | none | committed | PostgreSQL reported `serializable` and held an `SIReadLock` on `item`. Declarative interceptor invocations: 1 | not a reuse case | held | same ending as plain JDBC `correct` |
| `TX-05.explicit-serializable` | none | committed, `native` only | the same two observations, through `getTransaction` and `commit` | not a reuse case | held | declarative does not run this form. `@Transactional` does not return a handle |
| `MG-02.*`, `MG-03.*` | | UNSUPPORTED, capability absent | not run | not run | not a failure | same class as plain JDBC |

Native `TX-03` was not executed. The release probe, on this server, released a connection whose autocommit was false:

```text
release_open_pid=238508
release_open_closed=true
release_open_present=false
release_template1_pid=238509
release_template1_present_after_return=false
release_template2_pid=238510
release_template_same_backend=false
```

`DriverManagerDataSource` cannot hand that connection to later work.

## Programmatic and declarative

The catalog classifications do not diverge. A failed rollback replaces the application throwable with `TransactionSystemException` in both modes, and `initApplicationException` keeps the original class (`AppException`, or `PSQLException` on the declarative statement-error case, or `SqlUnchecked` on the programmatic one). The original throwable is not what leaves the boundary.

The declarative difference that the catalog does not run is the default rollback rule. A probe called `@Transactional` with no `rollbackFor`, and let a real `23505` escape:

```text
checked_sql_escaped=PSQLException
checked_sql_code=23505
checked_sql_fate=aborted
checked_sql_visible=0
checked_sql_trace=[Connection.setAutoCommit(false), Connection.commit, Connection.setAutoCommit(true)]
```

Spring called `Connection.commit`, not `Connection.rollback`. `commit()` returned. PostgreSQL's fate was `aborted`. The caller received the `PSQLException`, not a normal return. That is not a report of success. It is also not the statement-error case: that case needs `ROLLBACK` to be the command, so the declarative method sets `rollbackFor = Exception.class`. `TransactionCallback` cannot throw `SQLException`. The programmatic case rethrows it as `SqlUnchecked` so the template's `RuntimeException` rule sees it. That wrap is application code, not `JdbcTemplate`.

An inner `PROPAGATION_REQUIRED` that throws, caught by the outer callback, is also not a catalog case. Programmatic and declarative both threw `UnexpectedRollbackException`. The fate was `aborted`, neither marker was visible, and thread-local state was clear. Spring did not report a successful commit of a transaction PostgreSQL rolled back. `globalRollbackOnParticipationFailure` was true, the recorded default. This is not `PROPAGATION_NESTED`.

## Layer

The four FAILs are not an instrumentation artifact. Each category C fault fired once, and the runner confirmed its server-side signature before Spring saw the error. Declarative calls entered `TransactionInterceptor`.

pgjdbc 42.7.14 does not throw from `Connection.commit()` when the driver state is `FAILED`, and it does not return the command tag. `PgConnection.setAutoCommit(true)` calls `commit()` when autocommit is off. The plain JDBC `correct` policy reads the driver state and, after a thrown `rollback()`, closes the connection instead of restoring autocommit. `unsafe` does neither, and fails the same four shapes.

Spring calls `commit` when the callback or method returns, calls `rollback(Savepoint)` for `PROPAGATION_NESTED`, and does not mark the outer transaction rollback-only when that savepoint rollback throws. `doCleanupAfterCompletion` restores autocommit after `rollback()` has thrown. Those are the Spring calls in the traces above. The declarative interceptor uses the same manager methods. On these catalog cases it does not add a different PostgreSQL outcome.

Spring JDBC's recording used `JdbcTemplate`, so a unique violation arrived as `DataAccessException`. The transaction endings match. Spring JDBC does not run TX-04 or TX-05. The passes there are this adapter's, on `DataSourceTransactionManager`, not a result about `JdbcTemplate`.

## Contract beside the failures

`TX-02.savepoint-rollback-not-sent` is the counterexample that matches Spring JDBC. The nested boundary left with `TransactionSystemException`. The outer callback returned. Spring called `Connection.commit`. PostgreSQL committed both markers. TX-02.2 held: the session was closed.

The 7.0.9 `Propagation.NESTED` javadoc says a nested transaction executes within the current one. `DataSourceTransactionManager` implements that with a JDBC savepoint. A thrown `rollback(Savepoint)` does not mark the outer transaction rollback-only. The outer callback's normal return then commits. When `rollback(Savepoint)` returns, as in `TX-04.nested-failure-contained`, the outer commit keeps the outer marker and not the inner one.

`TX-02.savepoint-rollback-rejected` is the other ending. PostgreSQL's `3B001` aborted the transaction before the outer boundary returned. The outer callback still returned, so Spring reported a commit. Neither marker remains.

`TX-01A` is the same commit return in a smaller shape. The callback caught `23505`, sent nothing else, and returned. `Connection.commit` did not throw. The probe, with the connection still open inside the callback, read driver state `FAILED` before that return. PostgreSQL's fate was `aborted` and the marker was absent. The session had closed by report time in the suite, so the last statement was not observed there. The trace still records `Connection.commit`.

`TX-03.rollback-not-sent` is the cleanup path. The withheld `ROLLBACK` left the session idle in transaction. The boundary reported failure. `doCleanupAfterCompletion` then called `Connection.setAutoCommit(true)`. At `after-unit1` the session was idle, the transaction was committed, and the doomed marker was visible. HikariCP checked that backend out again. The statement-error case ran the same cleanup on a transaction PostgreSQL had already aborted, and that transaction stayed aborted.

Category B aborted the transaction. The boundary did not report a commit.

Thread-local cleanup held after every recorded case, including the FAILs: no bound resource, synchronization inactive, no actual transaction. That does not say what PostgreSQL committed.

## Recommendation

Keep the cases in PPCS. Do not file an issue.

The four FAILs are counterexamples to PPCS invariants. Spring 7.0.9 says `commit` runs when the callback or the intercepted method returns, and `Connection.commit` is void. pgjdbc does not surface the command tag. A failed nested savepoint rollback is an exception from that nested scope, and the outer scope in these cases catches it and returns. Whether that should mark the outer transaction rollback-only, and whether autocommit should be restored after `rollback()` has thrown, are questions against that text. They are the same questions as the Spring JDBC recording. This run adds that the declarative interceptor does not change the answers, and that the default checked-exception rule calls `commit` and then rethrows the `SQLException` when `commit()` returns.

Category C does not say how often the fault occurs, and it is not a network failure. A lost `COMMIT` reply, after the server has executed the command and before the client has seen it, was not established. `commit()` does not return until the driver is `IDLE`.
