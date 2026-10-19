# Plain JDBC transaction policy, PPCS run 2026-10-19T12-51-00Z-0a0698

PostgreSQL JDBC 42.7.14, Java 21.0.12.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Three repetitions agreed. CTL-01 and `pg-control` held their gates for every executed JDBC scenario. No result was INCONCLUSIVE.

`correct` and `unsafe` are one `DriverManager` connection each, with no pool. Category C is a client-side injection in this process, fired once, on `Connection.rollback()` or `Connection.rollback(Savepoint)`, before pgjdbc sends. Category B is the runner's `pg_terminate_backend`. The adapter's report is not the verdict.

`TX-01B.commit-reply-discarded` is NOT_RUN. A probe on this server, in a database created for the probe and then dropped, called `Connection.commit()` after a caught `23505`. It recorded `aborted_commit_state_before=FAILED`, `aborted_commit_threw=false`, `aborted_commit_state_after=IDLE`, `aborted_commit_warning=none`, and `aborted_marker_visible=false`. `Statement.execute("COMMIT")` on an aborted transaction returned update count 0 and no warning. The command-status string is not on the statement. In the suite, `TX-01A` `correct` sent `COMMIT`, `commit()` returned, and at report time the session was idle with last statement `COMMIT`. `commit()` had already applied `ReadyForQuery` before it returned. Closing the socket after that return is not the discarded-reply case.

pgjdbc 42.7.14 `PgConnection.commit` sends `COMMIT` through `executeTransactionCommand` when `getTransactionState()` is not `IDLE` (`PgConnection.java` lines 1035-1046). `TransactionCommandHandler` implements `handleWarning` only (lines 1278-1283). `handleCommandStatus` stays the empty method on `ResultHandlerBase`. The driver sets `IDLE`, `OPEN`, or `FAILED` from `ReadyForQuery` `I`, `T`, or `E` (`QueryExecutorImpl.receiveRFQ`, lines 3041-3067). A `COMMIT` that PostgreSQL answers with the command tag `ROLLBACK` is not an error, so `commit()` returns. After that return the state is `IDLE` either way. The public JDBC method does not expose the tag. `PgConnection.getTransactionState()` does expose `FAILED` before the call. That method is public on the driver class. `java.sql.Connection` does not have it.

## Cases

Evidence is `reports/examples/2026-10-19T12-51-00Z-0a0698/cases/`. The xids below are repetition 1. The three repetitions agreed on the classification.

| Case | Fault | Policy reported | PostgreSQL | Connection | Invariant |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` (both) | none | committed | xid committed; marker visible | held until `after-end` | CTL-01.1 held |
| `CTL-01.rollback` (both) | none | rolled back | xid aborted; marker absent | held until `after-end` | CTL-01.2 held |
| `TX-01A` `correct` | A, caught `23505` | rolled back. State before `commit()` was `FAILED`. `commit()` returned. Last statement at report time was `COMMIT` | xid 3885 aborted; marker absent. At `before-end` the session was idle in transaction (aborted) | same backend until `after-end` | TX-01A.1 held. Mechanism exercised |
| `TX-01A` `unsafe` | A, caught `23505` | committed. State before `commit()` was `FAILED`. `commit()` returned. Last statement was `COMMIT` | xid 3897 aborted; marker absent | same backend until `after-end` | TX-01A.1 failed. Mechanism exercised |
| `TX-01B.conn-lost-before-commit` `correct` | B | failed (`57P01`: terminating connection due to administrator command) | xid 3909 aborted; marker absent | closed after `commit()` threw | TX-01B.1 held |
| `TX-01B.conn-lost-before-commit` `unsafe` | B | rolled back (`57P01`) | aborted; marker absent | kept; the case ends | TX-01B.1 held |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run | not run |
| `TX-02.savepoint-rollback-not-sent` `correct` | C, withheld `ROLLBACK TO SAVEPOINT "ppcs_nested"` once | rolled back. Outer `Connection.rollback()` after the savepoint rollback threw | aborted; neither marker visible | not left in a transaction | TX-02.1 and TX-02.2 held |
| `TX-02.savepoint-rollback-not-sent` `unsafe` | C, same withhold | committed. The failed savepoint rollback was ignored | xid 3948 committed; both markers visible. At `after-outer` the session was idle and its last statement was `COMMIT` | not left in a transaction | TX-02.1 failed. TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` `correct` | C, rewrite, reply `3B001` | rolled back. Outer `Connection.rollback()` | aborted; neither marker visible | not left in a transaction | TX-02.1 and TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` `unsafe` | C, reply `3B001`. At `after-fault` the session was idle in transaction (aborted) and the top-level transaction was in progress | committed. State before `commit()` was `FAILED` | xid 3978 aborted; neither marker visible. At `after-outer` the session was idle and its last statement was `COMMIT` | not left in a transaction | TX-02.1 failed. TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` `correct` | B | failed. The outer `rollback()` could not be completed and the connection was closed | aborted; neither marker visible | closed | TX-02.1 and TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` `unsafe` | B | rolled back. `commit()` threw on the closed connection | aborted; neither marker visible | kept | TX-02.1 and TX-02.2 held |
| `TX-03.rollback-not-sent` `correct` | C, withheld `ROLLBACK` once. At `after-fault` the session was idle in transaction on xid 4024 | failed (ROLLBACK was not sent). Unit 2 committed | unit 1 aborted; doomed absent. Unit 2 xid 4025 committed; next visible | unit 1 pid 161647 was closed before `after-unit1`. Unit 2 pid 161663 | TX-03.1 and TX-03.2 held |
| `TX-03.rollback-not-sent` `unsafe` | C, same withhold | failed (ROLLBACK was not sent). `setAutoCommit(true)` returned. Unit 2 committed | unit 1 xid 4039 committed at `after-unit1`; doomed visible. The session was idle and its last statement was `COMMIT`. Unit 2 xid 4040 committed; next visible | same backend, pid 161781 | TX-03.1 failed. TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` `correct` | C, after `23505`. At `after-fault` the session was idle in transaction (aborted), no backend xid, unit 1 already aborted | failed. Unit 2 committed | unit 1 aborted; doomed absent. Unit 2 committed on a new backend | closed, then a new connection | both held |
| `TX-03.statement-error-rollback-not-sent` `unsafe` | C, same | failed. `setAutoCommit(true)` returned. Unit 2 committed | unit 1 xid 4069 aborted at `after-unit1`; last statement `COMMIT`; doomed absent. Unit 2 xid 4070 committed | same backend, pid 162046 | both held |
| `TX-03.conn-lost-in-transaction` `correct` | B | failed (`rollback` on the terminated backend). Unit 2 committed | unit 1 aborted; doomed absent. Unit 2 committed | terminated backend was not reused | both held |
| `TX-03.conn-lost-in-transaction` `unsafe` | B | failed. `setAutoCommit(true)` threw `08003` (this connection has been closed). Unit 2 failed `08003` after 2 ms | unit 1 aborted; doomed absent; next absent | the closed connection was kept. Unit 2 did not get a backend | TX-03.1 held. TX-03.2 failed |
| `TX-04.nested-failure-contained` `correct` | none | committed | committed; outer visible; inner absent | not a reuse case | TX-04.1 held |
| `TX-04.nested-failure-contained` `unsafe` | none | committed | committed; both markers absent. The outer write ran inside the savepoint | not a reuse case | TX-04.1 failed |
| `TX-04.nested-released-outer-rollback` (both) | none | rolled back | aborted; both markers absent | not a reuse case | TX-04.2 held |
| `TX-04.independent-inner` | none | UNSUPPORTED, not applicable by design | not run | not run | not run |
| `TX-05` `correct` (both forms) | none | committed | `current_setting` `serializable`; one relation `SIReadLock` on `item` | not a reuse case | TX-05.1 and TX-05.2 held |
| `TX-05` `unsafe` (both forms) | none | committed | `current_setting` `read committed`; no `SIReadLock` | not a reuse case | TX-05.1 failed. TX-05.2 held |
| `MG-02.*`, `MG-03.*` | | UNSUPPORTED, capability absent | not run | not run | not run |

`unsafe` fails eight cases: `TX-01A`, both client-side `TX-02` cases, `TX-03.rollback-not-sent`, `TX-03.conn-lost-in-transaction`, `TX-04.nested-failure-contained`, and both `TX-05` cases. It does not fail `TX-03.statement-error-rollback-not-sent`. `setAutoCommit(true)` there sent `COMMIT`, and PostgreSQL left xid 4069 aborted.

## Autocommit after a withheld rollback

The probe and `TX-03.rollback-not-sent` `unsafe` are the same sequence, one without a fault and one with the rollback withheld.

Java 21 `Connection.setAutoCommit` says: "If this method is called during a transaction and the auto-commit mode is changed, the transaction is committed." pgjdbc 42.7.14 `PgConnection.setAutoCommit` calls `commit()` when auto-commit is currently off (lines 985-987), then sets the flag. That matches the javadoc for an open transaction. The probe's open transaction became visible to another connection (`autocommit_open_visible=true`, state before `OPEN`, `setAutoCommit(true)` did not throw).

On an aborted transaction the same call does not throw and the row does not become visible (`autocommit_failed_state_before=FAILED`, `autocommit_failed_visible=false`). `commit()` sent `COMMIT`. PostgreSQL cannot commit a failed transaction block. The driver reports neither the `ROLLBACK` tag nor a warning.

`TX-03.rollback-not-sent` `unsafe` withheld `ROLLBACK` while xid 4039 was open. `setAutoCommit(true)` then returned. At `after-unit1` the same session was idle, its last statement was `COMMIT`, xid 4039 was committed, and the doomed marker was visible. Unit 2 committed xid 4040 on pid 161781. TX-03.1 failed because unit 1 committed. Unit 2 did not join unit 1. The two xids differ.

`correct` did not call `setAutoCommit`. It closed the connection. At `after-unit1` pid 161647 was gone, xid 4024 was aborted, and the doomed marker was absent. Unit 2 used pid 161663. Both TX-03 invariants held. Closing the connection is what PostgreSQL did with the open transaction on session end. JDBC says the result of `close()` during an active transaction is implementation-defined. This run observed an abort. It does not show that a pool would hand the same connection out safely. There is no pool here.

Spring JDBC's pooled `TX-03.rollback-not-sent` (`reports/examples/2026-10-18T16-08-25Z-9b025d`) is the same PostgreSQL ending: a withheld `ROLLBACK`, then `COMMIT` as the last statement, unit 1 committed, the same backend reused for a later transaction. `DataSourceTransactionManager.doCleanupAfterCompletion` restores auto-commit after `rollback()` has thrown. The `COMMIT` is pgjdbc's `setAutoCommit(true)`, which the JDBC javadoc requires when auto-commit changes during a transaction. The policy that calls it after a rollback that did not complete is Spring's cleanup. A direct JDBC policy can skip that call and close the connection. The statement-error row is the contrast on both adapters: the same `COMMIT` does not commit a transaction PostgreSQL has already aborted.

## Comparison with Spring JDBC

The Spring recording is `2026-10-18T16-08-25Z-9b025d`. Same PostgreSQL image and the same pgjdbc 42.7.14. Spring's native mode has no pool. Its TX-03 rows are HikariCP `maximumPoolSize` 1. This adapter has no HikariCP. Matching endings are not the same cause.

| Case | Spring JDBC | Plain JDBC `correct` | What the two runs show |
| --- | --- | --- | --- |
| `TX-01A` | FAIL. `execute` returned. PostgreSQL had aborted the transaction | PASS. `commit()` was sent. The policy reported rolled back because the driver state was `FAILED` | `commit()` returns in both. Spring treats that return as success. The tag is not available. `getTransactionState()` before the call is enough to avoid reporting success. The mechanism still ran: the last statement was `COMMIT` |
| `TX-01B` connection loss | PASS. `TransactionSystemException` `57P01` | PASS. `failed`, `57P01` | Neither reports a commit. The transaction aborted. `unsafe` reports rolled back and also passes TX-01B.1. That case has no TX-01B.2 |
| `TX-01B` reply discarded | NOT_RUN | NOT_RUN | `commit()` does not return while the driver still reports a transaction in progress |
| `TX-02` rollback not sent | FAIL. Outer `execute` returned. Both markers committed | PASS. Outer `rollback()` after the savepoint rollback threw. Neither marker remains | Spring does not mark the outer transaction rollback-only when `rollback(Savepoint)` throws. The JDBC policy can |
| `TX-02` rollback rejected | FAIL. Outer `execute` returned. PostgreSQL aborted the transaction. Neither marker remains | PASS. Outer `rollback()` | The `unsafe` row matches Spring: `commit()` returned, state had been `FAILED`, PostgreSQL aborted xid 3978, last statement `COMMIT` |
| `TX-02` connection loss | PASS. The API did not report a commit | PASS. `failed` | The backend was terminated. Nothing committed |
| `TX-03` rollback not sent | FAIL (pooled). Unit 1 committed by the autocommit restore. Same backend reused | PASS. Connection closed. Unit 1 aborted. Unit 2 was a new backend | `unsafe` matches the Spring ending, without HikariCP: `setAutoCommit(true)` committed xid 4039, and the same pid ran unit 2's xid 4040. The driver call is the same. Spring's cleanup is what invokes it. This adapter's `correct` path never does |
| `TX-03` statement error | PASS (pooled). Unit 1 stayed aborted. Same backend reused | PASS. Connection closed. Unit 2 was a new backend | `unsafe` also passes, on the same backend. The later `COMMIT` did not commit the aborted transaction. Reuse here is one held `DriverManager` connection, not a pool checkout |
| `TX-03` connection loss | PASS (pooled). Unit 2 used a new backend | PASS. Unit 2 used a new connection | `unsafe` fails TX-03.2. It kept the closed connection, `setAutoCommit(true)` threw `08003`, and unit 2 failed on that connection. Spring's pool did not hand that terminated backend out again |

## What the public API can and cannot establish

`Connection.commit()`, `rollback()`, `rollback(Savepoint)`, `setSavepoint`, `releaseSavepoint`, `setTransactionIsolation`, and `close()` are enough for the savepoint, isolation, and disposal cases above.

They are not enough to read the command tag of `COMMIT`. The correct policy does not pretend they are. It reads `PgConnection.getTransactionState()` before `commit()`. `FAILED` means `ReadyForQuery` `E` has already arrived. If `commit()` then returns, the policy reports rolled back. That is driver state from the failed statement, not the tag on the `COMMIT` reply. The suite still records the mechanism as exercised, because the last statement was `COMMIT`.

A lost reply cannot be represented with this `commit()`. The method returns only after `ReadyForQuery`. Closing the socket after that is not `TX-01B.commit-reply-discarded`.

`TX-01B.conn-lost-before-commit` `correct` reports `failed`, not rolled back. `commit()` threw `57P01`. That is a failed call. It is not, by itself, a command tag or a server reply that says `ROLLBACK`. The case allows a rollback report. `unsafe` makes one and passes TX-01B.1. The positive policy does not.

## The smallest policy that passed

On this run, `correct` is that policy:

1. `DriverManager.getConnection`. No pool.
2. `setTransactionIsolation` while the driver state is `IDLE`, then `setAutoCommit(false)`. pgjdbc throws if isolation is changed in the middle of a transaction (`PgConnection.setTransactionIsolation`, lines 1111-1118) and sends `SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL`.
3. Do the work on that connection. A savepoint is `setSavepoint` / `rollback(Savepoint)` / `releaseSavepoint` on the same connection.
4. If `rollback(Savepoint)` throws, call `rollback()` on the surrounding transaction. Do not call `commit()`.
5. If the body throws and `rollback()` returns, report rolled back.
6. If `rollback()` throws, close the connection. Do not call `setAutoCommit(true)`. Report `failed`.
7. Otherwise read `getTransactionState()`, call `commit()`, and report committed only when the state was `OPEN`. If it was `FAILED` and `commit()` returns, report rolled back. If `commit()` throws, report `failed` and close the connection.

Removing Spring does not remove those steps. Spring's `TransactionTemplate` was doing them, and on this driver its completion treats a normal `commit()` as success and restores auto-commit after a thrown `rollback()`. The JDBC policy has to make both decisions itself. The run shows that those two decisions, plus closing a connection whose rollback did not finish, are enough for the cases this adapter can express. It does not show that a pooled checkout of the same connection would be safe. That was not run.

No upstream issue is proposed. `setAutoCommit(true)` committing an open transaction is the JDBC javadoc, and pgjdbc implements it by calling `commit()`. The missing command tag is a gap between PostgreSQL's `COMMIT` reply and `Connection.commit()`'s `void` return. Spring's TX-01A and TX-02 rejected rows follow from reporting that return as success. Spring's TX-03 rollback-not-sent row follows from calling `setAutoCommit(true)` after `rollback()` threw. Both are visible here without Spring, on `unsafe`, and avoided on `correct`.
