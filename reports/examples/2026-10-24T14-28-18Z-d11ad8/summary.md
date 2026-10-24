# PPCS run 2026-10-24T14-28-18Z-d11ad8

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `2d44447a84ed…`
- **Runner:** PPCS 0.3.0, harness sha256 `ca9a464603c5…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-24T14:28:18.378Z; duration 152 s
- **Counts:** PASS 54, FAIL 25, UNSUPPORTED 8 (1 not applicable by design, outside coverage), NOT_RUN 1

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | jooq (native) | jooq (jdbc) | jooq (pooled) | jooq (jdbc-pooled) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.jooq.native.json) | [PASS](cases/CTL-01.commit.jooq.jdbc.json) | [PASS](cases/CTL-01.commit.jooq.pooled.json) | [PASS](cases/CTL-01.commit.jooq.jdbc-pooled.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.jooq.native.json) | [PASS](cases/CTL-01.rollback.jooq.jdbc.json) | [PASS](cases/CTL-01.rollback.jooq.pooled.json) | [PASS](cases/CTL-01.rollback.jooq.jdbc-pooled.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [FAIL](cases/TX-01A.caught-error-then-commit.jooq.native.json) | [FAIL](cases/TX-01A.caught-error-then-commit.jooq.jdbc.json) | — | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.jooq.native.json) | [PASS](cases/TX-01B.conn-lost-before-commit.jooq.jdbc.json) | — | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [NOT_RUN](cases/TX-01B.commit-reply-discarded.jooq.native.json) | — | — | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.jooq.native.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.jooq.jdbc.json) | — | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.jooq.native.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.jooq.jdbc.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-rejected.jooq.native.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.jooq.jdbc.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.jooq.native.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.jooq.jdbc.json) | — | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | — | — | [FAIL](cases/TX-03.rollback-not-sent.jooq.pooled.json) | [PASS](cases/TX-03.rollback-not-sent.jooq.jdbc-pooled.json) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | — | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.jooq.pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.jooq.jdbc-pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | — | — | [PASS](cases/TX-03.conn-lost-in-transaction.jooq.pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.jooq.jdbc-pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.jooq.native.json) | [PASS](cases/TX-04.nested-failure-contained.jooq.jdbc.json) | — | — | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.jooq.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.jooq.jdbc.json) | — | — | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.jooq.native.json) | — | — | — | — | — |
| `TX-05.managed-serializable` | none | [PASS](cases/TX-05.managed-serializable.jooq.native.json) | [PASS](cases/TX-05.managed-serializable.jooq.jdbc.json) | — | — | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) |
| `TX-05.explicit-serializable` | none | — | [PASS](cases/TX-05.explicit-serializable.jooq.jdbc.json) | — | — | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) |
| `MG-02.held` | none | [UNSUPPORTED](cases/MG-02.held.jooq.native.json) | — | — | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) |
| `MG-02.first-deployment` | none | [UNSUPPORTED](cases/MG-02.first-deployment.jooq.native.json) | — | — | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) |
| `MG-02.session-loss` | B (server-side termination) | [UNSUPPORTED](cases/MG-02.session-loss.jooq.native.json) | — | — | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) |
| `MG-02.idle-session-timeout` | none | [UNSUPPORTED](cases/MG-02.idle-session-timeout.jooq.native.json) | — | — | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) |
| `MG-03.valid-reversal` | none | [UNSUPPORTED](cases/MG-03.valid-reversal.jooq.native.json) | — | — | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) |
| `MG-03.no-reversal` | none | [UNSUPPORTED](cases/MG-03.no-reversal.jooq.native.json) | — | — | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) |
| `MG-03.failing-reversal` | none | [UNSUPPORTED](cases/MG-03.failing-reversal.jooq.native.json) | — | — | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- jooq (native): held
- jooq (jdbc): held
- jooq (pooled): held
- jooq (jdbc-pooled): held
- pg-control (correct): held
- pg-control (unsafe): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01A.caught-error-then-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.conn-lost-before-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-01B.commit-reply-unseen`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-rejected`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.conn-lost-before-savepoint-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-03.rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.statement-error-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.conn-lost-in-transaction`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-failure-contained`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-released-outer-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-05.managed-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-05.explicit-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on jooq (native)

1. **What the API reported:** committed: DSLContext.transaction returned normally, so jOOQ committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 6327 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: jOOQ 3.21 manual, Transaction management: a callback that returns is an implicit commit, and an uncaught exception rolls the transactional scope back. DSLContext.transaction javadoc: a runtime exception thrown by the transactional logic indicates that a rollback has occurred, and a checked exception is wrapped in DataAccessException with the same meaning. DefaultTransactionProvider.commit calls Connection.commit when the savepoint stack is empty. Connection.commit() is void and does not return a command tag. DefaultTransactionProvider models a nested transaction() as a JDBC Savepoint. It does not open a second connection.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Top-level transaction, then an insert into item through the DSL. Native mode is DSLContext.transaction. JDBC mode is Connection.setAutoCommit(false) and Connection.commit, with the same DSL insert.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.jooq.native.json](cases/TX-01A.caught-error-then-commit.jooq.native.json)

### `TX-01A.caught-error-then-commit` on jooq (jdbc)

1. **What the API reported:** committed: Connection.commit() returned, so the application reported a commit.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 6339 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: jOOQ 3.21 manual, Transaction management: jOOQ can run on a JDBC connection whose transaction the application already owns, by calling Connection.commit and Connection.rollback rather than DSLContext.transaction. This mode does not call DSLContext.transaction. A returning Connection.commit() is reported committed. The application's exception is reported rolled back only when Connection.rollback() returns. A thrown Connection.rollback() or Connection.commit() is reported failed: it asserts neither outcome. Connection.commit() is void and does not return a command tag. A nested scope is Connection.setSavepoint on the same connection.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Top-level transaction, then an insert into item through the DSL. Native mode is DSLContext.transaction. JDBC mode is Connection.setAutoCommit(false) and Connection.commit, with the same DSL insert.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `jdbc` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=jdbc --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.jooq.jdbc.json](cases/TX-01A.caught-error-then-commit.jooq.jdbc.json)

### `TX-02.savepoint-rollback-not-sent` on jooq (native)

1. **What the API reported:** committed: DSLContext.transaction returned normally, so jOOQ committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6399 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 6399), `inner` yes (inserted by xid 6400). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: jOOQ 3.21 manual, Transaction management: a callback that returns is an implicit commit, and an uncaught exception rolls the transactional scope back. DSLContext.transaction javadoc: a runtime exception thrown by the transactional logic indicates that a rollback has occurred, and a checked exception is wrapped in DataAccessException with the same meaning. DefaultTransactionProvider.commit calls Connection.commit when the savepoint stack is empty. Connection.commit() is void and does not return a command tag. DefaultTransactionProvider models a nested transaction() as a JDBC Savepoint. It does not open a second connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Outer transaction and a nested DSLContext.transaction, which DefaultTransactionProvider implements as a JDBC savepoint. JDBC mode uses Connection.setSavepoint on the same connection. The outer callback catches the nested failure and returns.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.jooq.native.json](cases/TX-02.savepoint-rollback-not-sent.jooq.native.json)

### `TX-02.savepoint-rollback-not-sent` on jooq (jdbc)

1. **What the API reported:** committed: Connection.commit() returned, so the application reported a commit.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6414 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 6414), `inner` yes (inserted by xid 6415). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: jOOQ 3.21 manual, Transaction management: jOOQ can run on a JDBC connection whose transaction the application already owns, by calling Connection.commit and Connection.rollback rather than DSLContext.transaction. This mode does not call DSLContext.transaction. A returning Connection.commit() is reported committed. The application's exception is reported rolled back only when Connection.rollback() returns. A thrown Connection.rollback() or Connection.commit() is reported failed: it asserts neither outcome. Connection.commit() is void and does not return a command tag. A nested scope is Connection.setSavepoint on the same connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Outer transaction and a nested DSLContext.transaction, which DefaultTransactionProvider implements as a JDBC savepoint. JDBC mode uses Connection.setSavepoint on the same connection. The outer callback catches the nested failure and returns.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `jdbc` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=jdbc --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.jooq.jdbc.json](cases/TX-02.savepoint-rollback-not-sent.jooq.jdbc.json)

### `TX-02.savepoint-rollback-rejected` on jooq (native)

1. **What the API reported:** committed: DSLContext.transaction returned normally, so jOOQ committed.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6429 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` no such session.
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: jOOQ 3.21 manual, Transaction management: a callback that returns is an implicit commit, and an uncaught exception rolls the transactional scope back. DSLContext.transaction javadoc: a runtime exception thrown by the transactional logic indicates that a rollback has occurred, and a checked exception is wrapped in DataAccessException with the same meaning. DefaultTransactionProvider.commit calls Connection.commit when the savepoint stack is empty. Connection.commit() is void and does not return a command tag. DefaultTransactionProvider models a nested transaction() as a JDBC Savepoint. It does not open a second connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Outer transaction and a nested DSLContext.transaction, which DefaultTransactionProvider implements as a JDBC savepoint. JDBC mode uses Connection.setSavepoint on the same connection. The outer callback catches the nested failure and returns.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.jooq.native.json](cases/TX-02.savepoint-rollback-rejected.jooq.native.json)

### `TX-02.savepoint-rollback-rejected` on jooq (jdbc)

1. **What the API reported:** committed: Connection.commit() returned, so the application reported a commit.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6444 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: jOOQ 3.21 manual, Transaction management: jOOQ can run on a JDBC connection whose transaction the application already owns, by calling Connection.commit and Connection.rollback rather than DSLContext.transaction. This mode does not call DSLContext.transaction. A returning Connection.commit() is reported committed. The application's exception is reported rolled back only when Connection.rollback() returns. A thrown Connection.rollback() or Connection.commit() is reported failed: it asserts neither outcome. Connection.commit() is void and does not return a command tag. A nested scope is Connection.setSavepoint on the same connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Outer transaction and a nested DSLContext.transaction, which DefaultTransactionProvider implements as a JDBC savepoint. JDBC mode uses Connection.setSavepoint on the same connection. The outer callback catches the nested failure and returns.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `jdbc` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=jdbc --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.jooq.jdbc.json](cases/TX-02.savepoint-rollback-rejected.jooq.jdbc.json)

### `TX-03.rollback-not-sent` on jooq (pooled)

1. **What the API reported:** rolled_back: DSLContext.transaction rethrew the exception raised inside the callback, so jOOQ rolled back. The next unit of work: committed, after 41 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 6490 committed at report time (`after-unit1`); transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 6491 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 6490), `next` yes (inserted by xid 6491). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: jOOQ 3.21 manual, Transaction management: a callback that returns is an implicit commit, and an uncaught exception rolls the transactional scope back. DSLContext.transaction javadoc: a runtime exception thrown by the transactional logic indicates that a rollback has occurred, and a checked exception is wrapped in DataAccessException with the same meaning. DefaultTransactionProvider.commit calls Connection.commit when the savepoint stack is empty. Connection.commit() is void and does not return a command tag. DefaultTransactionProvider models a nested transaction() as a JDBC Savepoint. It does not open a second connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Top-level transaction, then an insert into item through the DSL. Native mode is DSLContext.transaction. JDBC mode is Connection.setAutoCommit(false) and Connection.commit, with the same DSL insert.
- **Conditions:** jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1; mode `pooled` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jooq --mode=pooled --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.jooq.pooled.json](cases/TX-03.rollback-not-sent.jooq.pooled.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 6737 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 6785 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 6785). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 6809 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 6809). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6836 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 6836), `inner` yes (inserted by xid 6837). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 6866 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 29 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 6926 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 6926 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 6926), `next` yes (inserted by xid 6926). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 6953 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 6980 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 7007 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 7064 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 7064). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 7088 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 7088). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
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
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.pg-control.unsafe.json](cases/MG-02.held.pg-control.unsafe.json)

### `MG-02.first-deployment` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see the other's uncommitted creation of the history table, so both conclude the database is new. Only one creation can commit, and the other fails with a unique violation. What the second runner does with that error decides the case. If it reports failure, or waits on the framework's own coordination, the migration runs once. If it treats the error as "the table already exists" and continues, it finds no history row and executes the migration while the first runner is inside it. A second runner that starts after the history table exists is MG-02.held. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized","hold":"history-table","hold_ms":10000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.pg-control.unsafe.json](cases/MG-02.first-deployment.pg-control.unsafe.json)

### `MG-02.session-loss` on pg-control (unsafe)

1. **What the API reported:** failed: the migration raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.pg-control.unsafe.json](cases/MG-02.session-loss.pg-control.unsafe.json)

### `MG-02.idle-session-timeout` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.pg-control.unsafe.json](cases/MG-02.idle-session-timeout.pg-control.unsafe.json)

### `MG-03.valid-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported revert says the migration's effects are gone. The next apply is what shows that history and the database agree: the migration runs again. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"valid"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.valid-reversal`
- **Evidence:** [cases/MG-03.valid-reversal.pg-control.unsafe.json](cases/MG-03.valid-reversal.pg-control.unsafe.json)

### `MG-03.no-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.pg-control.unsafe.json](cases/MG-03.no-reversal.pg-control.unsafe.json)

### `MG-03.failing-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported failure says the revert did not complete. For a transactional migration, the caller can treat the migration as still applied. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.3 violated: If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"partial-then-error"},"transactional":true}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.failing-reversal`
- **Evidence:** [cases/MG-03.failing-reversal.pg-control.unsafe.json](cases/MG-03.failing-reversal.pg-control.unsafe.json)

## Qualified passes

- `TX-01B.commit-reply-unseen` on jooq (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on jooq (jdbc): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Inconclusive, unsupported and not run

- `TX-01B.commit-reply-discarded` on jooq (native): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on jooq (native): **UNSUPPORTED (not applicable by design)**. jOOQ 3.21.9 DefaultTransactionProvider has no propagation mode that commits an inner transaction on a second connection while an outer transaction stays open. A nested DSLContext.transaction is a JDBC savepoint on the same connection, which the manual documents. JDBC Connection has no such propagation mode either. Opening a second connection and committing it is application code coordinating two physical transactions, not a framework propagation mode. This adapter does not manufacture that mode.
- `MG-02.held` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a migration history or a multi-process advisory-lock protocol. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-02.first-deployment` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a migration history or a multi-process advisory-lock protocol. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-02.session-loss` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a migration history or a multi-process advisory-lock protocol. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-02.idle-session-timeout` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a migration history or a multi-process advisory-lock protocol. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-03.valid-reversal` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a reversible migration history. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-03.no-reversal` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a reversible migration history. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.
- `MG-03.failing-reversal` on jooq (native): **UNSUPPORTED**. This adapter evaluates jOOQ's transaction API and JDBC-owned transactions. It does not drive a reversible migration history. jOOQ Open Source Edition 3.21.9 contains org.jooq.Migrations; that API is not this adapter.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| jooq (native) | native | jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `cabb28669315…` |
| jooq (jdbc) | native | jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `cabb28669315…` |
| jooq (pooled) | configured | jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `cabb28669315…` |
| jooq (jdbc-pooled) | configured | jooq 3.21.9, jooq 3.21.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `cabb28669315…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |

