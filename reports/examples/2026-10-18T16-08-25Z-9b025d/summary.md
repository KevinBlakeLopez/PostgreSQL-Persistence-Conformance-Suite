# PPCS run 2026-10-18T16-08-25Z-9b025d

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `b504ba4a1b60…`
- **Runner:** PPCS 0.3.0, harness sha256 `3c41c362e9c3…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-18T16:08:25.429Z; duration 35 s
- **Counts:** PASS 23, FAIL 11, NOT_RUN 1

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | pg-control (correct) | pg-control (unsafe) | spring-jdbc (native) | spring-jdbc (pooled) |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.spring-jdbc.native.json) | [PASS](cases/CTL-01.commit.spring-jdbc.pooled.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.native.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.pooled.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.spring-jdbc.native.json) | — |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) | [PASS](cases/TX-01B.conn-lost-before-commit.spring-jdbc.native.json) | — |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) | [NOT_RUN](cases/TX-01B.commit-reply-discarded.spring-jdbc.native.json) | — |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.spring-jdbc.native.json) | — |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.spring-jdbc.native.json) | — |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.spring-jdbc.native.json) | — |
| `TX-03.rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) | — | [FAIL](cases/TX-03.rollback-not-sent.spring-jdbc.pooled.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.spring-jdbc.pooled.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) | — | [PASS](cases/TX-03.conn-lost-in-transaction.spring-jdbc.pooled.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- pg-control (correct): held
- pg-control (unsafe): held
- spring-jdbc (native): held
- spring-jdbc (pooled): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01A.caught-error-then-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.conn-lost-before-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-02.savepoint-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-rejected`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.conn-lost-before-savepoint-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-03.rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.statement-error-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.conn-lost-in-transaction`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 899 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 947 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 947). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 974 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 974), `inner` yes (inserted by xid 975). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 1004 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 35 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 1064 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 1064 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 1064), `next` yes (inserted by xid 1064). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 1091 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 1118 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on spring-jdbc (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 1178 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) calls PlatformTransactionManager.commit only when the callback returns, and on a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. The 7.0.9 reference, Rolling Back a Declarative Transaction, states the default rule: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." The default tx:advice settings say: "Any RuntimeException triggers rollback, and any checked Exception does not." No custom rollback rule is installed. The nested TransactionTemplate uses PROPAGATION_NESTED. The 7.0.9 reference, Understanding PROPAGATION_NESTED, states: "PROPAGATION_NESTED uses a single physical transaction with multiple savepoints that it can roll back to. Such partial rollbacks let an inner transaction scope trigger a rollback for its scope, with the outer transaction being able to continue the physical transaction despite some operations having been rolled back. This setting is typically mapped onto JDBC savepoints, so it works only with JDBC resource transactions." DataSourceTransactionManager's class javadoc states: "This transaction manager supports nested transactions via the JDBC Savepoint mechanism."

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** TransactionTemplate with the default PROPAGATION_REQUIRED on DataSourceTransactionManager. Writes go through JdbcTemplate.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-jdbc --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.spring-jdbc.native.json](cases/TX-01A.caught-error-then-commit.spring-jdbc.native.json)

### `TX-02.savepoint-rollback-not-sent` on spring-jdbc (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 1202 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 1202), `inner` yes (inserted by xid 1203). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) calls PlatformTransactionManager.commit only when the callback returns, and on a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. The 7.0.9 reference, Rolling Back a Declarative Transaction, states the default rule: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." The default tx:advice settings say: "Any RuntimeException triggers rollback, and any checked Exception does not." No custom rollback rule is installed. The nested TransactionTemplate uses PROPAGATION_NESTED. The 7.0.9 reference, Understanding PROPAGATION_NESTED, states: "PROPAGATION_NESTED uses a single physical transaction with multiple savepoints that it can roll back to. Such partial rollbacks let an inner transaction scope trigger a rollback for its scope, with the outer transaction being able to continue the physical transaction despite some operations having been rolled back. This setting is typically mapped onto JDBC savepoints, so it works only with JDBC resource transactions." DataSourceTransactionManager's class javadoc states: "This transaction manager supports nested transactions via the JDBC Savepoint mechanism."

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Outer TransactionTemplate with the default PROPAGATION_REQUIRED, and a second TransactionTemplate with PROPAGATION_NESTED. Writes go through JdbcTemplate.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-jdbc --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.spring-jdbc.native.json](cases/TX-02.savepoint-rollback-not-sent.spring-jdbc.native.json)

### `TX-02.savepoint-rollback-rejected` on spring-jdbc (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 1217 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` no such session.
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) calls PlatformTransactionManager.commit only when the callback returns, and on a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. The 7.0.9 reference, Rolling Back a Declarative Transaction, states the default rule: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." The default tx:advice settings say: "Any RuntimeException triggers rollback, and any checked Exception does not." No custom rollback rule is installed. The nested TransactionTemplate uses PROPAGATION_NESTED. The 7.0.9 reference, Understanding PROPAGATION_NESTED, states: "PROPAGATION_NESTED uses a single physical transaction with multiple savepoints that it can roll back to. Such partial rollbacks let an inner transaction scope trigger a rollback for its scope, with the outer transaction being able to continue the physical transaction despite some operations having been rolled back. This setting is typically mapped onto JDBC savepoints, so it works only with JDBC resource transactions." DataSourceTransactionManager's class javadoc states: "This transaction manager supports nested transactions via the JDBC Savepoint mechanism."

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Outer TransactionTemplate with the default PROPAGATION_REQUIRED, and a second TransactionTemplate with PROPAGATION_NESTED. Writes go through JdbcTemplate.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-jdbc --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.spring-jdbc.native.json](cases/TX-02.savepoint-rollback-rejected.spring-jdbc.native.json)

### `TX-03.rollback-not-sent` on spring-jdbc (pooled)

1. **What the API reported:** failed: TransactionTemplate.execute threw an exception the callback did not throw. The next unit of work: committed, after 45 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 1248 committed at report time (`after-unit1`); transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 1249 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 1248), `next` yes (inserted by xid 1249). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) calls PlatformTransactionManager.commit only when the callback returns, and on a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. The 7.0.9 reference, Rolling Back a Declarative Transaction, states the default rule: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." The default tx:advice settings say: "Any RuntimeException triggers rollback, and any checked Exception does not." No custom rollback rule is installed. The nested TransactionTemplate uses PROPAGATION_NESTED. The 7.0.9 reference, Understanding PROPAGATION_NESTED, states: "PROPAGATION_NESTED uses a single physical transaction with multiple savepoints that it can roll back to. Such partial rollbacks let an inner transaction scope trigger a rollback for its scope, with the outer transaction being able to continue the physical transaction despite some operations having been rolled back. This setting is typically mapped onto JDBC savepoints, so it works only with JDBC resource transactions." DataSourceTransactionManager's class javadoc states: "This transaction manager supports nested transactions via the JDBC Savepoint mechanism."

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** TransactionTemplate with the default PROPAGATION_REQUIRED on DataSourceTransactionManager. Writes go through JdbcTemplate.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1; mode `pooled` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-jdbc --mode=pooled --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.spring-jdbc.pooled.json](cases/TX-03.rollback-not-sent.spring-jdbc.pooled.json)

## Inconclusive, unsupported and not run

- `TX-01B.commit-reply-discarded` on spring-jdbc (native): **NOT_RUN**. the adapter does not implement this case

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| spring-jdbc (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `23534b73bd69…` |
| spring-jdbc (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `23534b73bd69…` |

