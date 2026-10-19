# PPCS run 2026-10-19T15-02-38Z-8a2f4d

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `b504ba4a1b60…`
- **Runner:** PPCS 0.3.0, harness sha256 `3c41c362e9c3…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-19T15:02:38.593Z; duration 137 s
- **Counts:** PASS 52, FAIL 25, UNSUPPORTED 7, NOT_RUN 1

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | pg-control (correct) | pg-control (unsafe) | spring-tx (native) | spring-tx (declarative) | spring-tx (pooled) | spring-tx (declarative-pooled) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.spring-tx.native.json) | [PASS](cases/CTL-01.commit.spring-tx.declarative.json) | [PASS](cases/CTL-01.commit.spring-tx.pooled.json) | [PASS](cases/CTL-01.commit.spring-tx.declarative-pooled.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.spring-tx.native.json) | [PASS](cases/CTL-01.rollback.spring-tx.declarative.json) | [PASS](cases/CTL-01.rollback.spring-tx.pooled.json) | [PASS](cases/CTL-01.rollback.spring-tx.declarative-pooled.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.spring-tx.native.json) | [FAIL](cases/TX-01A.caught-error-then-commit.spring-tx.declarative.json) | — | — |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) | [PASS](cases/TX-01B.conn-lost-before-commit.spring-tx.native.json) | [PASS](cases/TX-01B.conn-lost-before-commit.spring-tx.declarative.json) | — | — |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) | [NOT_RUN](cases/TX-01B.commit-reply-discarded.spring-tx.native.json) | — | — | — |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.spring-tx.native.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.spring-tx.declarative.json) | — | — |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.spring-tx.native.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.spring-tx.declarative.json) | — | — |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.spring-tx.native.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.spring-tx.declarative.json) | — | — |
| `TX-03.rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) | — | — | [FAIL](cases/TX-03.rollback-not-sent.spring-tx.pooled.json) | [FAIL](cases/TX-03.rollback-not-sent.spring-tx.declarative-pooled.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) | — | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.spring-tx.pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.spring-tx.declarative-pooled.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) | — | — | [PASS](cases/TX-03.conn-lost-in-transaction.spring-tx.pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.spring-tx.declarative-pooled.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-failure-contained.spring-tx.native.json) | [PASS](cases/TX-04.nested-failure-contained.spring-tx.declarative.json) | — | — |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-released-outer-rollback.spring-tx.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.spring-tx.declarative.json) | — | — |
| `TX-05.managed-serializable` | none | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) | [PASS](cases/TX-05.managed-serializable.spring-tx.native.json) | [PASS](cases/TX-05.managed-serializable.spring-tx.declarative.json) | — | — |
| `TX-05.explicit-serializable` | none | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) | [PASS](cases/TX-05.explicit-serializable.spring-tx.native.json) | — | — | — |
| `MG-02.held` | none | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-02.held.spring-tx.native.json) | — | — | — |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-02.first-deployment.spring-tx.native.json) | — | — | — |
| `MG-02.session-loss` | B (server-side termination) | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-02.session-loss.spring-tx.native.json) | — | — | — |
| `MG-02.idle-session-timeout` | none | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-02.idle-session-timeout.spring-tx.native.json) | — | — | — |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.valid-reversal.spring-tx.native.json) | — | — | — |
| `MG-03.no-reversal` | none | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.no-reversal.spring-tx.native.json) | — | — | — |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.failing-reversal.spring-tx.native.json) | — | — | — |
| `TX-04.independent-inner` | none | — | — | [PASS](cases/TX-04.independent-inner.spring-tx.native.json) | [PASS](cases/TX-04.independent-inner.spring-tx.declarative.json) | — | — |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- pg-control (correct): held
- pg-control (unsafe): held
- spring-tx (native): held
- spring-tx (declarative): held
- spring-tx (pooled): held
- spring-tx (declarative-pooled): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01A.caught-error-then-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.conn-lost-before-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-02.savepoint-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-rejected`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.conn-lost-before-savepoint-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-03.rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.statement-error-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.conn-lost-in-transaction`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-failure-contained`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-released-outer-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-04.independent-inner`: no control adapter states an expectation for this case
- `TX-05.managed-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-05.explicit-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 8605 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 8653 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8653). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8680 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 8680), `inner` yes (inserted by xid 8681). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8710 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 35 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 8771 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 8771 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 8771), `next` yes (inserted by xid 8771). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 8798 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 8825 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 8852 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8909 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8909). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8933 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8933). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.explicit-serializable`
- **Evidence:** [cases/TX-05.explicit-serializable.pg-control.unsafe.json](cases/TX-05.explicit-serializable.pg-control.unsafe.json)

### `MG-02.held` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.pg-control.unsafe.json](cases/MG-02.held.pg-control.unsafe.json)

### `MG-02.first-deployment` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see, before it starts, that the other is about to apply the same migration. The database starts with no history row that could tell it so. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.pg-control.unsafe.json](cases/MG-02.first-deployment.pg-control.unsafe.json)

### `MG-02.session-loss` on pg-control (unsafe)

1. **What the API reported:** failed: the migration raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.pg-control.unsafe.json](cases/MG-02.session-loss.pg-control.unsafe.json)

### `MG-02.idle-session-timeout` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.pg-control.unsafe.json](cases/MG-02.idle-session-timeout.pg-control.unsafe.json)

### `MG-03.valid-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported revert says the migration's effects are gone. The next apply is what shows that history and the database agree: the migration runs again. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"valid"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.valid-reversal`
- **Evidence:** [cases/MG-03.valid-reversal.pg-control.unsafe.json](cases/MG-03.valid-reversal.pg-control.unsafe.json)

### `MG-03.no-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.pg-control.unsafe.json](cases/MG-03.no-reversal.pg-control.unsafe.json)

### `MG-03.failing-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported failure says the revert did not complete. For a transactional migration, the caller can treat the migration as still applied. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.3 violated: If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"partial-then-error"},"transactional":true}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.failing-reversal`
- **Evidence:** [cases/MG-03.failing-reversal.pg-control.unsafe.json](cases/MG-03.failing-reversal.pg-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on spring-tx (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 9352 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) obtains a transaction, runs the callback, and calls PlatformTransactionManager.commit only when the callback returns. On a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. On any other throwable it rolls back and throws java.lang.reflect.UndeclaredThrowableException. If rollback throws TransactionSystemException, rollbackOnException stores the callback throwable with initApplicationException and throws the TransactionSystemException instead. DataSourceTransactionManager.doCommit calls Connection.commit and translateException wraps a SQLException as TransactionSystemException("JDBC commit failed", ex). Connection.commit is void and does not return a command tag. A normal return from execute is reported as committed. The callback's own throwable leaving execute is reported as rolled_back. Any other throwable leaving execute is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." Its note says actual nested transactions work on DataSourceTransactionManager. DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." No custom rollback rule is installed on the template. TransactionCallback cannot throw a checked SQLException. Where a case needs that error to leave the callback, the callback rethrows it as SqlUnchecked, a RuntimeException, so the template's RuntimeException rule sees it. That wrap is application code. It is not JdbcTemplate's exception translation.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Programmatic: TransactionTemplate on DataSourceTransactionManager. PROPAGATION_REQUIRED. Writes are PreparedStatement calls on the connection DataSourceUtils.getConnection returns.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.spring-tx.native.json](cases/TX-01A.caught-error-then-commit.spring-tx.native.json)

### `TX-01A.caught-error-then-commit` on spring-tx (declarative)

1. **What the API reported:** committed: the @Transactional proxy returned normally, so the interceptor committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 9364 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: Spring Framework 7.0.9 @Transactional methods run through TransactionInterceptor (org.springframework.transaction.interceptor.TransactionAspectSupport.completeTransactionAfterThrowing). The call is on a JDK proxy. The target is not invoked directly. If TransactionAttribute.rollbackOn returns true, the interceptor calls PlatformTransactionManager.rollback and rethrows the application throwable. If rollback throws TransactionSystemException, that exception replaces the application throwable and initApplicationException stores the original. If rollbackOn returns false, the interceptor calls commit. With no rollbackFor rules, RuleBasedTransactionAttribute.rollbackOn delegates to DefaultTransactionAttribute.rollbackOn, which is true for RuntimeException and Error only. The 7.0.9 reference, Rolling Back a Declarative Transaction, states: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." A normal return is reported as committed. The method's own throwable leaving the proxy is reported as rolled_back. Any other throwable leaving the proxy is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." The statement-error case uses rollbackFor = Exception.class so a checked SQLException takes the rollback path that case describes. The default rule would commit on that checked exception. That default is not substituted for the case.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Declarative: the call goes through a JDK proxy and TransactionInterceptor. PROPAGATION_REQUIRED. Writes are PreparedStatement calls on the connection DataSourceUtils.getConnection returns.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `declarative` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=declarative --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.spring-tx.declarative.json](cases/TX-01A.caught-error-then-commit.spring-tx.declarative.json)

### `TX-02.savepoint-rollback-not-sent` on spring-tx (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 9401 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 9401), `inner` yes (inserted by xid 9402). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) obtains a transaction, runs the callback, and calls PlatformTransactionManager.commit only when the callback returns. On a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. On any other throwable it rolls back and throws java.lang.reflect.UndeclaredThrowableException. If rollback throws TransactionSystemException, rollbackOnException stores the callback throwable with initApplicationException and throws the TransactionSystemException instead. DataSourceTransactionManager.doCommit calls Connection.commit and translateException wraps a SQLException as TransactionSystemException("JDBC commit failed", ex). Connection.commit is void and does not return a command tag. A normal return from execute is reported as committed. The callback's own throwable leaving execute is reported as rolled_back. Any other throwable leaving execute is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." Its note says actual nested transactions work on DataSourceTransactionManager. DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." No custom rollback rule is installed on the template. TransactionCallback cannot throw a checked SQLException. Where a case needs that error to leave the callback, the callback rethrows it as SqlUnchecked, a RuntimeException, so the template's RuntimeException rule sees it. That wrap is application code. It is not JdbcTemplate's exception translation.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Programmatic: TransactionTemplate on DataSourceTransactionManager. Outer PROPAGATION_REQUIRED. Inner PROPAGATION_NESTED, which DataSourceTransactionManager maps to a JDBC savepoint. Not PROPAGATION_REQUIRES_NEW.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.spring-tx.native.json](cases/TX-02.savepoint-rollback-not-sent.spring-tx.native.json)

### `TX-02.savepoint-rollback-not-sent` on spring-tx (declarative)

1. **What the API reported:** committed: the @Transactional proxy returned normally, so the interceptor committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 9416 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 9416), `inner` yes (inserted by xid 9417). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 @Transactional methods run through TransactionInterceptor (org.springframework.transaction.interceptor.TransactionAspectSupport.completeTransactionAfterThrowing). The call is on a JDK proxy. The target is not invoked directly. If TransactionAttribute.rollbackOn returns true, the interceptor calls PlatformTransactionManager.rollback and rethrows the application throwable. If rollback throws TransactionSystemException, that exception replaces the application throwable and initApplicationException stores the original. If rollbackOn returns false, the interceptor calls commit. With no rollbackFor rules, RuleBasedTransactionAttribute.rollbackOn delegates to DefaultTransactionAttribute.rollbackOn, which is true for RuntimeException and Error only. The 7.0.9 reference, Rolling Back a Declarative Transaction, states: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." A normal return is reported as committed. The method's own throwable leaving the proxy is reported as rolled_back. Any other throwable leaving the proxy is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." The statement-error case uses rollbackFor = Exception.class so a checked SQLException takes the rollback path that case describes. The default rule would commit on that checked exception. That default is not substituted for the case.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Declarative: the call goes through a JDK proxy and TransactionInterceptor. Outer PROPAGATION_REQUIRED. Inner PROPAGATION_NESTED, which DataSourceTransactionManager maps to a JDBC savepoint. Not PROPAGATION_REQUIRES_NEW.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `declarative` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=declarative --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.spring-tx.declarative.json](cases/TX-02.savepoint-rollback-not-sent.spring-tx.declarative.json)

### `TX-02.savepoint-rollback-rejected` on spring-tx (native)

1. **What the API reported:** committed: TransactionTemplate.execute returned normally, so the template committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 9431 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` no such session.
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) obtains a transaction, runs the callback, and calls PlatformTransactionManager.commit only when the callback returns. On a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. On any other throwable it rolls back and throws java.lang.reflect.UndeclaredThrowableException. If rollback throws TransactionSystemException, rollbackOnException stores the callback throwable with initApplicationException and throws the TransactionSystemException instead. DataSourceTransactionManager.doCommit calls Connection.commit and translateException wraps a SQLException as TransactionSystemException("JDBC commit failed", ex). Connection.commit is void and does not return a command tag. A normal return from execute is reported as committed. The callback's own throwable leaving execute is reported as rolled_back. Any other throwable leaving execute is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." Its note says actual nested transactions work on DataSourceTransactionManager. DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." No custom rollback rule is installed on the template. TransactionCallback cannot throw a checked SQLException. Where a case needs that error to leave the callback, the callback rethrows it as SqlUnchecked, a RuntimeException, so the template's RuntimeException rule sees it. That wrap is application code. It is not JdbcTemplate's exception translation.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Programmatic: TransactionTemplate on DataSourceTransactionManager. Outer PROPAGATION_REQUIRED. Inner PROPAGATION_NESTED, which DataSourceTransactionManager maps to a JDBC savepoint. Not PROPAGATION_REQUIRES_NEW.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.spring-tx.native.json](cases/TX-02.savepoint-rollback-rejected.spring-tx.native.json)

### `TX-02.savepoint-rollback-rejected` on spring-tx (declarative)

1. **What the API reported:** committed: the @Transactional proxy returned normally, so the interceptor committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 9446 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` no such session.
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Spring Framework 7.0.9 @Transactional methods run through TransactionInterceptor (org.springframework.transaction.interceptor.TransactionAspectSupport.completeTransactionAfterThrowing). The call is on a JDK proxy. The target is not invoked directly. If TransactionAttribute.rollbackOn returns true, the interceptor calls PlatformTransactionManager.rollback and rethrows the application throwable. If rollback throws TransactionSystemException, that exception replaces the application throwable and initApplicationException stores the original. If rollbackOn returns false, the interceptor calls commit. With no rollbackFor rules, RuleBasedTransactionAttribute.rollbackOn delegates to DefaultTransactionAttribute.rollbackOn, which is true for RuntimeException and Error only. The 7.0.9 reference, Rolling Back a Declarative Transaction, states: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." A normal return is reported as committed. The method's own throwable leaving the proxy is reported as rolled_back. Any other throwable leaving the proxy is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." The statement-error case uses rollbackFor = Exception.class so a checked SQLException takes the rollback path that case describes. The default rule would commit on that checked exception. That default is not substituted for the case.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Declarative: the call goes through a JDK proxy and TransactionInterceptor. Outer PROPAGATION_REQUIRED. Inner PROPAGATION_NESTED, which DataSourceTransactionManager maps to a JDBC savepoint. Not PROPAGATION_REQUIRES_NEW.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `declarative` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=declarative --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.spring-tx.declarative.json](cases/TX-02.savepoint-rollback-rejected.spring-tx.declarative.json)

### `TX-03.rollback-not-sent` on spring-tx (pooled)

1. **What the API reported:** failed: TransactionTemplate.execute threw a throwable the callback did not throw. The next unit of work: committed, after 45 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 9491 committed at report time (`after-unit1`); transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 9492 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 9491), `next` yes (inserted by xid 9492). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) obtains a transaction, runs the callback, and calls PlatformTransactionManager.commit only when the callback returns. On a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. On any other throwable it rolls back and throws java.lang.reflect.UndeclaredThrowableException. If rollback throws TransactionSystemException, rollbackOnException stores the callback throwable with initApplicationException and throws the TransactionSystemException instead. DataSourceTransactionManager.doCommit calls Connection.commit and translateException wraps a SQLException as TransactionSystemException("JDBC commit failed", ex). Connection.commit is void and does not return a command tag. A normal return from execute is reported as committed. The callback's own throwable leaving execute is reported as rolled_back. Any other throwable leaving execute is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." Its note says actual nested transactions work on DataSourceTransactionManager. DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." No custom rollback rule is installed on the template. TransactionCallback cannot throw a checked SQLException. Where a case needs that error to leave the callback, the callback rethrows it as SqlUnchecked, a RuntimeException, so the template's RuntimeException rule sees it. That wrap is application code. It is not JdbcTemplate's exception translation.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Programmatic: TransactionTemplate on DataSourceTransactionManager. PROPAGATION_REQUIRED. Writes are PreparedStatement calls on the connection DataSourceUtils.getConnection returns.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1; mode `pooled` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=pooled --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.spring-tx.pooled.json](cases/TX-03.rollback-not-sent.spring-tx.pooled.json)

### `TX-03.rollback-not-sent` on spring-tx (declarative-pooled)

1. **What the API reported:** failed: the @Transactional proxy threw a throwable the method did not throw. The next unit of work: committed, after 41 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 9506 committed at report time (`after-unit1`); transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 9507 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 9506), `next` yes (inserted by xid 9507). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: Spring Framework 7.0.9 @Transactional methods run through TransactionInterceptor (org.springframework.transaction.interceptor.TransactionAspectSupport.completeTransactionAfterThrowing). The call is on a JDK proxy. The target is not invoked directly. If TransactionAttribute.rollbackOn returns true, the interceptor calls PlatformTransactionManager.rollback and rethrows the application throwable. If rollback throws TransactionSystemException, that exception replaces the application throwable and initApplicationException stores the original. If rollbackOn returns false, the interceptor calls commit. With no rollbackFor rules, RuleBasedTransactionAttribute.rollbackOn delegates to DefaultTransactionAttribute.rollbackOn, which is true for RuntimeException and Error only. The 7.0.9 reference, Rolling Back a Declarative Transaction, states: "In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback)." A normal return is reported as committed. The method's own throwable leaving the proxy is reported as rolled_back. Any other throwable leaving the proxy is reported as failed. Propagation.NESTED, Spring Framework 7.0.9: "Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise." DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. Propagation.REQUIRES_NEW: "Create a new transaction, and suspend the current transaction if one exists." The statement-error case uses rollbackFor = Exception.class so a checked SQLException takes the rollback path that case describes. The default rule would commit on that checked exception. That default is not substituted for the case.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Declarative: the call goes through a JDK proxy and TransactionInterceptor. PROPAGATION_REQUIRED. Writes are PreparedStatement calls on the connection DataSourceUtils.getConnection returns.
- **Conditions:** spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1; mode `declarative-pooled` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=spring-tx --mode=declarative-pooled --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.spring-tx.declarative-pooled.json](cases/TX-03.rollback-not-sent.spring-tx.declarative-pooled.json)

## Inconclusive, unsupported and not run

- `TX-01B.commit-reply-discarded` on spring-tx (native): **NOT_RUN**. the adapter does not implement this case
- `MG-02.held` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.first-deployment` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.session-loss` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.idle-session-timeout` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-03.valid-reversal` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.no-reversal` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.failing-reversal` on spring-tx (native): **UNSUPPORTED**. Spring Framework transaction management has no migration runner or reversible migration history. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| spring-tx (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `0f4d555dfb54…` |
| spring-tx (declarative) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `0f4d555dfb54…` |
| spring-tx (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `0f4d555dfb54…` |
| spring-tx (declarative-pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `0f4d555dfb54…` |

