# jOOQ transaction recovery, PPCS run 2026-10-22T12-58-46Z-d4a7fc

jOOQ Open Source Edition 3.21.9 (`org.jooq:jooq`), PostgreSQL JDBC 42.7.14, Java 27 (Homebrew OpenJDK, build 27, 2026-09-15). The compiler target is release 21, which is the Java version jOOQ 3.21's open-source edition supports. PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). HikariCP 7.1.0 is used only in `pooled` and `jdbc-pooled`. Transitive jars on the classpath, unused for transaction control: r2dbc-spi 1.0.0.RELEASE, reactive-streams 1.0.3, slf4j-api 2.0.17. No SLF4J provider was present. The probe logged the NOP logger warning on stderr.

The recording is [`reports/examples/2026-10-22T12-58-46Z-d4a7fc`](../../reports/examples/2026-10-22T12-58-46Z-d4a7fc/summary.md). Three repetitions agreed. `Probe.java` and these notes were added after that harness run. The source digest stored in the case files is the adapter tree at execution, which does not include the probe or this file. CTL-01 and `pg-control` held their gates for every jOOQ scenario result below. The harness counts for the whole run, including `pg-control`, are PASS 54, FAIL 25, UNSUPPORTED 8, NOT_RUN 1. The jOOQ scenario FAILs are the seven rows named below. No result was INCONCLUSIVE.

`native` and `pooled` call `DSLContext.transaction`. No `TransactionProvider` is installed. `Configuration.transactionProvider()` supplies `org.jooq.impl.DefaultTransactionProvider`, and `nested()` is true. A nested `transaction()` is a JDBC savepoint. `jdbc` and `jdbc-pooled` do not call `transaction()`. The application calls `Connection.setAutoCommit(false)` and `Connection.commit` or `Connection.rollback`. jOOQ executes the SQL. SQL in every mode is the DSL on plain names `item` and `uniq`. There is no generated catalog and no commercial artifact.

A returning `DSLContext.transaction` is reported committed. The callback's runtime exception, rethrown by `transaction()`, is reported rolled back. Any other exception is reported failed. In the JDBC-owned mode, a returning `Connection.commit()` is reported committed, a returning `Connection.rollback()` after the body threw is reported rolled back, and a thrown `commit()` or `rollback()` is reported failed. `TX-01A` catches the unique violation inside the callback and then lets the transaction finish. It does not call `rollback` first.

`TX-01B.commit-reply-discarded` is NOT_RUN. On this server, `Connection.commit()` after a caught `23505` moved pgjdbc from `FAILED` to `IDLE` before `commit()` returned, with no `SQLWarning`. `Statement.execute("COMMIT")` returned update count 0 and no warning. The command-status string is not on that API. Closing the socket after `commit()` returns is not that case.

## Cases

| Case | Fault | Reported | PostgreSQL | Invariant |
| --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed. `Connection.commit` went `OPEN` to `IDLE` | committed; marker visible. All four modes | CTL-01.1 held |
| `CTL-01.rollback` | none | rolled back | aborted; marker absent. All four modes | CTL-01.2 held |
| `TX-01A` `native` | A, caught `23505` | committed. `transaction()` returned. Trace: `Connection.commit` `FAILED` to `IDLE`, then `setAutoCommit(true)`. Listeners: `beginStart`, `commitStart`, `commitEnd` | xid 33422 aborted at `before-end` (`idle in transaction (aborted)`) and after exit; marker absent. The backend was gone at `after-end` | TX-01A.1 failed. The runner's mechanism check is null: the session had closed |
| `TX-01A` `jdbc` | A, caught `23505` | committed. `Connection.commit()` returned from `FAILED` to `IDLE`. No jOOQ transaction listener ran | xid 33435 aborted; marker absent. At `after-end` the session was idle and its last statement was `COMMIT` | TX-01A.1 failed. Mechanism exercised |
| `TX-01B.conn-lost-before-commit` | B | failed. `Connection.commit` threw `57P01` while the driver state was still `OPEN`. A following `rollback` threw `08003` | aborted; marker absent. `native` and `jdbc` | TX-01B.1 held |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run |
| `TX-01B.commit-reply-unseen` | E | failed. `Connection.commit` threw `08006`. `commitEnd` still ran, from `transactionResult0`'s `finally`, and the cleanup `rollback` threw `08003` | committed; marker visible. `native` and `jdbc` | TX-01B.1 held. TX-01B.2 not exercised |
| `TX-02.savepoint-rollback-not-sent` | C, withhold once | committed. Nested scope was caught. `native` reported the nested scope rolled back (`AppException`); the savepoint failure was suppressed (`DataAccessException`, "ROLLBACK TO SAVEPOINT was not sent") | committed; both markers visible. `jdbc` session idle, last statement `COMMIT`. `native` session closed at `after-outer` | TX-02.1 failed. TX-02.2 held. Both modes |
| `TX-02.savepoint-rollback-rejected` | C, rewrite, reply `3B001` | committed. `Connection.commit` went `FAILED` to `IDLE` | aborted; neither marker visible | TX-02.1 failed. TX-02.2 held. Both modes |
| `TX-02.conn-lost-before-savepoint-rollback` | B | failed. The outer `commit` threw `08003` on a closed connection | aborted; neither marker visible | TX-02.1 and TX-02.2 held. Both modes |
| `TX-03.rollback-not-sent` `pooled` | C, withhold `ROLLBACK` once | rolled back (`AppException` rethrown). Suppressed: `Cannot rollback transaction`. Listeners include `rollbackEnd` | unit 1 xid 33585 committed at `after-unit1`; last statement `COMMIT`; doomed visible. Unit 2 xid 33586 committed | TX-03.1 failed. TX-03.2 held. Same backend, pid 1723032 |
| `TX-03.rollback-not-sent` `jdbc-pooled` | C, same withhold | failed (`Connection.rollback()` threw). The body error is suppressed on that outcome | unit 1 xid 33601 aborted; last statement at `after-unit1` was `ROLLBACK`; doomed absent. Unit 2 xid 33602 committed | TX-03.1 and TX-03.2 held. Same backend, pid 1723171 |
| `TX-03.statement-error-rollback-not-sent` `pooled` | C, withhold after `23505` | rolled back. `setAutoCommit(true)` ran while the driver state was `FAILED` | unit 1 aborted; last statement `COMMIT`; doomed absent. Unit 2 committed | both invariants held. Same backend |
| `TX-03.statement-error-rollback-not-sent` `jdbc-pooled` | C, same withhold | failed | unit 1 aborted; last statement `ROLLBACK`; doomed absent. Unit 2 committed | both invariants held. Same backend |
| `TX-03.conn-lost-in-transaction` | B | `pooled` rolled back; `jdbc-pooled` failed | unit 1 aborted; unit 2 committed on a new backend | both invariants held |
| `TX-04.nested-failure-contained` | none | committed. Nested scope rolled back (`AppException`) | committed; outer visible; inner absent | TX-04.1 held. Both modes |
| `TX-04.nested-released-outer-rollback` | none | rolled back. Nested scope completed | aborted; neither marker visible | TX-04.2 held. Both modes |
| `TX-04.independent-inner` | none | UNSUPPORTED (not applicable by design) | not run | not run |
| `TX-05.managed-serializable` `native` | none | committed | `current_setting('transaction_isolation')` was `serializable`. An `SIReadLock` was held on `item`. Trace: `setTransactionIsolation(8)` while `IDLE autoCommit=true`, then `setAutoCommit(false)` | TX-05.1 and TX-05.2 held |
| `TX-05.managed-serializable` `jdbc` | none | committed | `serializable`, same call order, without `DSLContext.transaction` | held |
| `TX-05.explicit-serializable` `jdbc` | none | committed | `serializable`. `native` does not run this case | held |
| `MG-02`, `MG-03` |  | UNSUPPORTED (capability absent) | not run | not run |

## TX-01A

The duplicate insert failed inside the callback with `IntegrityConstraintViolationException` and SQLSTATE `23505`. The callback caught it and returned. At `before-end` the session was `idle in transaction (aborted)` and `pg_xact_status` was already `aborted`. The marker was absent after exit.

`native` then returned from `DSLContext.transaction`. The JDBC trace for that completion, on the connection jOOQ acquired, is:

1. `Connection.setAutoCommit(false)`, driver state `IDLE` to `IDLE`, autocommit true to false. This is `DefaultTransactionProvider.brace` at begin.
2. `Connection.commit`, `FAILED autoCommit=false` to `IDLE autoCommit=false`, returned, warning `none`.
3. `Connection.setAutoCommit(true)`, already `IDLE`.
4. `Connection.close`.

The transaction listeners were `beginStart`, `commitStart`, `commitEnd`. There was no `rollbackStart`. xid 33422 stayed aborted. The runner records `mechanism_exercised` null because `DataSourceConnectionProvider.release` closes this mode's `DriverManager` connection inside `transaction()`, so `after-end` cannot see a last statement. The trace is the evidence that `COMMIT` was sent. `commit()` returned. jOOQ treated that return as success.

`jdbc` is the same statement sequence and the same `commit()` trace, without steps 3 and 4 before `after-end`. The application called `Connection.commit()` itself. `DSLContext.transaction` was not used, and the listener list is empty. At `after-end` the session was idle and its last statement was `COMMIT`. xid 33435 was aborted and the marker was absent. The mechanism was exercised. The report is still committed.

So the false success is present when jOOQ owns `commit()` and when the application owns `commit()`. The inserts are the same DSL calls in both modes. The SQL text is not what selects the outcome.

### Which layer has the command tag

pgjdbc 42.7.14 `PgConnection.commit` calls `executeTransactionCommand(commitQuery)` when `QueryExecutor.getTransactionState()` is not `IDLE`. That call does not return a command tag. `Connection.commit()` is void. The probe's `Statement.execute("COMMIT")` on an aborted transaction stored update count 0 and no warning. The tag is not on the statement either. jOOQ's `DefaultConnectionProvider.commit` calls `connection.commit()` and, on `SQLException`, throws `DataAccessException("Cannot commit transaction", e)`. It does not read `PgConnection.getTransactionState()`. On this run `commit()` did not throw, so jOOQ had no exception and no tag to interpret.

`DefaultDSLContext.transactionResult0` in 3.21.9 sets `committed = true` only after `provider.commit(ctx)` returns, then returns the callback's value. A normal return is what this adapter maps to `committed`, matching the 3.21 manual: a callback that returns is an implicit commit. `commitEnd` is in a `finally` around that call. On `TX-01B.commit-reply-unseen` the same `commitEnd` ran after `commit()` had thrown `08006`, and the result was `failed` because the exception left `transaction()`. `commitEnd` by itself is not a successful commit. On TX-01A, `commit()` returned and no exception left `transaction()`.

This is the pgjdbc limitation already asked in [pgjdbc#4494](https://github.com/pgjdbc/pgjdbc/issues/4494). jOOQ does not discard a `ROLLBACK` tag it never receives. It reports the void return. The application caught the original `23505` and continued. That catch is the case. It is not a failure to read a tag the driver had already exposed.

The draft in [`upstream-draft.md`](upstream-draft.md) is not filed.

### Caught exception and escaping exception

The catalog case is the catch. The probe, on the same disposable server and the same jars, also let the `23505` leave the callback:

```text
escape_returned=false
escape_thrown=IntegrityConstraintViolationException 23505
escape_commit_calls=0
escape_rollback_calls=1
escape_fate=aborted
escape_visible=false
catch_violation=23505
catch_returned=true
catch_state_before_commit=FAILED
catch_commit_calls=1
catch_rollback_calls=0
catch_fate=aborted
catch_visible=false
```

An exception that leaves the callback is rolled back and rethrown. A caught exception and a normal return is a `commit()` from driver state `FAILED`. Those are different paths. The catalog path is the second one.

## TX-01B

`Connection.commit` was attempted after the runner had terminated the backend. pgjdbc threw `57P01` and the driver state went from `OPEN` to closed. jOOQ then attempted `rollback`, which threw `08003`, and `transaction()` threw the commit failure. The adapter reported failed. xid stayed aborted and the marker was absent.

On `TX-01B.commit-reply-unseen` the proxy dropped one `COMMIT` reply. `commit()` threw `08006`. The database outcome was committed and the marker was visible. The adapter reported failed. It did not report rolled back. TX-01B.2 is not exercised: `rollback_claim_channels` is empty. `rollbackEnd` did run, as the cleanup after the failed commit. That listener is recorded in `steps.listeners`. It is not mapped to `reported`.

The lost-reply simulation that closes the socket after the driver has already applied `ReadyForQuery` is NOT_RUN. The probe's `commit()` returned only after the driver state was `IDLE`.

## TX-02

Both client-side cases are injections in this process, fired once, before pgjdbc sends `ROLLBACK TO SAVEPOINT`. They are not production frequency.

`native` implements the nested scope as `configuration.dsl().transaction`. `DefaultTransactionProvider.rollback` pops the savepoint and calls `Connection.rollback(Savepoint)`. When that call throws, `transactionResult0` adds the failure as a suppressed exception and rethrows the callback's `AppException`. `rollbackEnd` still runs. The outer callback catches that `AppException` and returns, so the outer `transaction()` calls `Connection.commit()`.

On the withhold, both markers were committed. On the rewrite, PostgreSQL answered `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint` with `3B001`, the driver state was `FAILED`, and the outer `commit()` returned from `FAILED` to `IDLE`. Neither marker remained. The outer API reported committed in both cases. The session was not left inside a transaction, so TX-02.2 held.

`jdbc` uses `Connection.setSavepoint` and `Connection.rollback(Savepoint)` directly. A thrown savepoint rollback is reported `failed` for the nested scope, with the `3B001` as that scope's error. The outer body still returns and `Connection.commit()` runs. The database endings match `native`.

The savepoint cases that do not inject a fault are TX-04. Both passed. A nested failure that `rollback(Savepoint)` actually completes is contained: the outer commit keeps the outer marker and not the inner one. A nested scope that returns is released, and the outer rollback removes both markers.

## TX-03

Category C withholds `Connection.rollback()` once, before pgjdbc sends `ROLLBACK`. The transaction stays open. Category B terminates the backend. The statement-error case is a real `23505` followed by the same withhold, so the transaction is already aborted.

`pooled` is jOOQ's provider. After the withheld `rollback()`, `DefaultTransactionProvider.rollback`'s `finally` calls `brace`, which calls `setAutoCommit(true)` because the connection had started in autocommit. pgjdbc 42.7.14 `PgConnection.setAutoCommit(true)`, when autocommit is currently false, calls `commit()` before it flips the flag. On the open transaction the trace is `setAutoCommit(true)` from `OPEN` to `IDLE`, and `after-unit1` last statement is `COMMIT`. xid 33585 was committed. The doomed marker was visible. Unit 2 committed xid 33586 on the same backend. The application-facing result was still `rolled_back`, because `transaction()` rethrew the callback's `AppException`. `rollbackEnd` ran. The reported rollback and the committed row disagree.

`jdbc-pooled` does not call `setAutoCommit(true)` after the thrown `rollback()`. It closes the connection. At `after-unit1` the last statement was `ROLLBACK`, xid 33601 was aborted, and the doomed marker was absent. The same backend then ran unit 2. That `ROLLBACK` is not a jOOQ call. The adapter's trace shows `close` while the state was still `OPEN`, and no second `rollback` from this process's proxy. HikariCP 7.1.0 rolls a dirty connection back when it is returned. The pass belongs to that pool close, on a path that does not restore autocommit first.

The statement-error row is the contrast. `pooled` still calls `setAutoCommit(true)`, now from driver state `FAILED`. `after-unit1` last statement is `COMMIT`, and xid 33616 stayed aborted. The doomed marker was absent. The same `COMMIT` does not persist a transaction PostgreSQL has already aborted. `jdbc-pooled` closed from state `FAILED`, and the last statement was `ROLLBACK`.

`TX-03.conn-lost-in-transaction` passes in both pooled modes. The terminated backend is not reused. Unit 2 commits on a new backend.

## TX-05

`native` requests `Isolation.SERIALIZABLE` as a transaction property on `DSLContext.transaction`. `DefaultTransactionProvider.brace` calls `Connection.setTransactionIsolation(8)` while the driver is `IDLE` and autocommit is still true, then `setAutoCommit(false)`. PostgreSQL reported `serializable`. The runner saw an `SIReadLock` on `item` after the DSL `select`. After `commit()`, jOOQ restored isolation to `2` and then set autocommit true.

`jdbc` calls `Connection.setTransactionIsolation(TRANSACTION_SERIALIZABLE)` before `setAutoCommit(false)`. Managed and explicit use that same order. Both reported `serializable`. `native` has no method that returns a transaction handle, so explicit TX-05 is not in that mode.

The probe called `setTransactionIsolation(SERIALIZABLE)` after `setAutoCommit(false)` and a first statement. pgjdbc threw SQLSTATE `25001`, `Cannot change transaction isolation level in the middle of a transaction.` `current_setting('transaction_isolation')` stayed `read committed`. jOOQ's provider does not use that order. The catalog pass is the before-start order.

## What this does not show

The open-source jar contains `org.jooq.Migrations`. This adapter does not drive it. MG-02 and MG-03 are capability-absent for that reason. `TX-04.independent-inner` is not applicable by design: a nested `transaction()` is a savepoint on the same connection, and JDBC has no `REQUIRES_NEW` equivalent. Opening a second connection would be application code, not a propagation mode this adapter invents.

No upstream issue was filed. [`upstream-draft.md`](upstream-draft.md) is a draft. pgjdbc#4494 is already open. This repository does not open a second pgjdbc issue.
