# PPCS run 2026-10-23T16-01-15Z-6fc728

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `46420e946083…`
- **Runner:** PPCS 0.3.0, harness sha256 `ece507a7bb9f…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-23T16:01:15.898Z; duration 484 s
- **Counts:** PASS 71, FAIL 49, UNSUPPORTED 3 (3 not applicable by design, outside coverage), INCONCLUSIVE 1, NOT_RUN 3

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | lucid (native) | lucid (pre-commit-probe) | mikroorm (native) | mikroorm (clear-forks) | pg-control (correct) | pg-control (unsafe) | typeorm (native) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.lucid.native.json) | [PASS](cases/CTL-01.commit.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.commit.mikroorm.native.json) | [PASS](cases/CTL-01.commit.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.typeorm.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.lucid.native.json) | [PASS](cases/CTL-01.rollback.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.rollback.mikroorm.native.json) | [PASS](cases/CTL-01.rollback.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.typeorm.native.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [FAIL](cases/TX-01A.caught-error-then-commit.lucid.native.json) | [PASS (mechanism not exercised)](cases/TX-01A.caught-error-then-commit.lucid.pre-commit-probe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.mikroorm.native.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.typeorm.native.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [FAIL](cases/TX-01B.conn-lost-before-commit.lucid.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.mikroorm.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) | [PASS](cases/TX-01B.conn-lost-before-commit.typeorm.native.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [FAIL (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.lucid.native.json) | — | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.mikroorm.native.json) | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.typeorm.native.json) |
| `TX-01B.commit-reply-unseen` | E | [NOT_RUN](cases/TX-01B.commit-reply-unseen.lucid.native.json) | — | [NOT_RUN](cases/TX-01B.commit-reply-unseen.mikroorm.native.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) | [NOT_RUN](cases/TX-01B.commit-reply-unseen.typeorm.native.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-rejected.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [FAIL](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.mikroorm.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.typeorm.native.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-03.rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-03.rollback-not-sent.typeorm.native.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [PASS](cases/TX-03.conn-lost-in-transaction.lucid.native.json) | — | [FAIL](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json) | — | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) | [PASS](cases/TX-03.conn-lost-in-transaction.typeorm.native.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.lucid.native.json) | — | [FAIL](cases/TX-04.nested-failure-contained.mikroorm.native.json) | [PASS](cases/TX-04.nested-failure-contained.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-failure-contained.typeorm.native.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.lucid.native.json) | — | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-released-outer-rollback.typeorm.native.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.lucid.native.json) | — | [FAIL](cases/TX-04.independent-inner.mikroorm.native.json) | [PASS](cases/TX-04.independent-inner.mikroorm.clear-forks.json) | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.pg-control.correct.json) | — | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.typeorm.native.json) |
| `TX-05.managed-serializable` | none | [PASS](cases/TX-05.managed-serializable.lucid.native.json) | — | [PASS](cases/TX-05.managed-serializable.mikroorm.native.json) | — | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) | [PASS](cases/TX-05.managed-serializable.typeorm.native.json) |
| `TX-05.explicit-serializable` | none | [FAIL](cases/TX-05.explicit-serializable.lucid.native.json) | — | [PASS](cases/TX-05.explicit-serializable.mikroorm.native.json) | — | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) | [PASS](cases/TX-05.explicit-serializable.typeorm.native.json) |
| `MG-02.held` | none | [PASS](cases/MG-02.held.lucid.native.json) | — | [FAIL](cases/MG-02.held.mikroorm.native.json) | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) | [FAIL](cases/MG-02.held.typeorm.native.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.lucid.native.json) | — | [FAIL](cases/MG-02.first-deployment.mikroorm.native.json) | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) | [FAIL](cases/MG-02.first-deployment.typeorm.native.json) |
| `MG-02.session-loss` | B (server-side termination) | [PASS](cases/MG-02.session-loss.lucid.native.json) | — | [FAIL](cases/MG-02.session-loss.mikroorm.native.json) | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) | [FAIL](cases/MG-02.session-loss.typeorm.native.json) |
| `MG-02.idle-session-timeout` | none | [INCONCLUSIVE](cases/MG-02.idle-session-timeout.lucid.native.json) | — | [FAIL](cases/MG-02.idle-session-timeout.mikroorm.native.json) | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) | [FAIL](cases/MG-02.idle-session-timeout.typeorm.native.json) |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.lucid.native.json) | — | [PASS](cases/MG-03.valid-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) | [PASS](cases/MG-03.valid-reversal.typeorm.native.json) |
| `MG-03.no-reversal` | none | [FAIL](cases/MG-03.no-reversal.lucid.native.json) | — | [PASS](cases/MG-03.no-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) | [PASS](cases/MG-03.no-reversal.typeorm.native.json) |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.lucid.native.json) | — | [PASS](cases/MG-03.failing-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) | [PASS](cases/MG-03.failing-reversal.typeorm.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- lucid (native): held
- lucid (pre-commit-probe): held
- mikroorm (native): held
- mikroorm (clear-forks): held
- pg-control (correct): held
- pg-control (unsafe): held
- typeorm (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01A.caught-error-then-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.conn-lost-before-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-01B.commit-reply-discarded`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
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
- `MG-02.held`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.first-deployment`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.session-loss`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.idle-session-timeout`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.valid-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.no-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.failing-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.independent-inner`: no control adapter states an expectation for this case

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2040 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.lucid.native.json](cases/TX-01A.caught-error-then-commit.lucid.native.json)

### `TX-01B.conn-lost-before-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 2064 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** Known not committed: the session ended before the framework tried to commit, so the driver refused to send COMMIT ("Client has encountered a connection error and is not queryable"). A report of rollback is justified; a report of success is not.
4. **Contract:** TX-01B.1 violated: When the connection or PostgreSQL's reply was lost around COMMIT, so that the client never received an acknowledgement of COMMIT, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.conn-lost-before-commit`
- **Evidence:** [cases/TX-01B.conn-lost-before-commit.lucid.native.json](cases/TX-01B.conn-lost-before-commit.lucid.native.json)

### `TX-01B.commit-reply-discarded` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 2076 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 2076). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.1 violated: When the connection or PostgreSQL's reply was lost around COMMIT, so that the client never received an acknowledgement of COMMIT, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.lucid.native.json](cases/TX-01B.commit-reply-discarded.lucid.native.json)

### `TX-02.savepoint-rollback-not-sent` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2088 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2088), `inner` yes (inserted by xid 2089). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.lucid.native.json](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json)

### `TX-02.savepoint-rollback-rejected` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2103 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.lucid.native.json](cases/TX-02.savepoint-rollback-rejected.lucid.native.json)

### `TX-02.conn-lost-before-savepoint-rollback` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2118 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework sees its connection fail during the savepoint rollback.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.conn-lost-before-savepoint-rollback`
- **Evidence:** [cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json)

### `TX-03.rollback-not-sent` on lucid (native)

1. **What the API reported:** rolled_back: db.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 57 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2133 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 2133 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 2133), `next` yes (inserted by xid 2133). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.lucid.native.json](cases/TX-03.rollback-not-sent.lucid.native.json)

### `TX-03.statement-error-rollback-not-sent` on lucid (native)

1. **What the API reported:** rolled_back: db.transaction(callback) rejected with the error the callback threw. The next unit of work: rolled_back, after 2 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2145 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.lucid.native.json](cases/TX-03.statement-error-rollback-not-sent.lucid.native.json)

### `TX-05.explicit-serializable` on lucid (native)

1. **What the API reported:** committed: trx.commit() resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 2215 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 2215). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: In @adonisjs/lucid 22.4.2, db.transaction() takes { isolationLevel?: IsolationLevels } in both its forms, with IsolationLevels 'read uncommitted' | 'read committed' | 'snapshot' | 'repeatable read' | 'serializable' (TransactionFn, build/src/types/database.d.ts). The explicit form returns a transaction client, which trx.commit() commits.

- **Fault:** none
- **Form:** db.transaction({ isolationLevel }) on the default connection, then trx.commit(). db.connection(name).transaction() and Model.transaction() reach the same QueryClient.transaction().
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-05.explicit-serializable`
- **Evidence:** [cases/TX-05.explicit-serializable.lucid.native.json](cases/TX-05.explicit-serializable.lucid.native.json)

### `MG-03.no-reversal` on lucid (native)

1. **What the API reported:** reverted: MigrationRunner status completed for direction down.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT, COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: In @adonisjs/lucid 22.4.2, MigrationRunner.run() executes pending migrations (direction up) or reverts a batch (direction down). status is completed when files ran, skipped when none did, and error when a migration threw (build/src/migration/runner.js).

- **Fault:** none
- **Form:** MigrationRunner.run() on a standalone Database. The migration file is generated for the case.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.lucid.native.json](cases/MG-03.no-reversal.lucid.native.json)

### `TX-01A.caught-error-then-commit` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2503 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Reused experiment T4f: the outer scope flushes its write; the duplicate insert runs in an inner em.transactional() with propagation REQUIRED, which joins the outer transaction; the outer scope catches the error and returns with nothing pending. Other forms (for example T4g) are not covered by this result.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.mikroorm.native.json](cases/TX-01A.caught-error-then-commit.mikroorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2540 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2540), `inner` yes (inserted by xid 2541). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** The nested em.transactional() is called with { clear: true }, as in reused experiments R1a, T7c and R1e. The outer scope flushes its write before the nested scope starts, and the clear fork keeps the nested scope's flush to its own entity, so the case isolates the savepoint rollback from the pending-write hazard that TX-04 targets.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json)

### `TX-02.savepoint-rollback-rejected` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2555 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** The nested em.transactional() is called with { clear: true }, as in reused experiments R1a, T7c and R1e. The outer scope flushes its write before the nested scope starts, and the clear fork keeps the nested scope's flush to its own entity, so the case isolates the savepoint rollback from the pending-write hazard that TX-04 targets.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json)

### `TX-03.rollback-not-sent` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2585 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.mikroorm.native.json](cases/TX-03.rollback-not-sent.mikroorm.native.json)

### `TX-03.statement-error-rollback-not-sent` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2597 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json](cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json)

### `TX-03.conn-lost-in-transaction` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2609 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.mikroorm.native.json](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json)

### `TX-04.nested-failure-contained` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) with a nested em.transactional(callback), default propagation NESTED resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 2621 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: MikroORM 7.2.5 documents NESTED as "Create a nested savepoint within the current transaction, or a new transaction if none exists" (enums.d.ts, TransactionPropagation), and a nested em.transactional() as creating a savepoint by default (EntityManager.transactional).

- **Fault:** none
- **Form:** The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the nested scope flushes its own write.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.mikroorm.native.json](cases/TX-04.nested-failure-contained.mikroorm.native.json)

### `TX-04.independent-inner` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) with an inner em.transactional(callback, { propagation: REQUIRES_NEW }) rejected with the error the callback threw.
2. **What PostgreSQL did:** transaction `inner` (its ID read inside it at `inner-after-write`): xid 2684 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2684), `inner` yes (inserted by xid 2684). Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the inner transaction committed and the outer one rolled back. From the API alone, it cannot see which transaction carried a write the framework still had pending. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.3 violated: An inner transaction started through an API that promises an independent transaction commits only its own writes: the outer scope's writes, whether already sent or still pending in the framework, are committed only by the outer transaction. Framework contract: MikroORM 7.2.5 documents REQUIRES_NEW as "Always create a new transaction, suspending the current one if it exists" (enums.d.ts, TransactionPropagation).

- **Fault:** none
- **Form:** The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the inner transaction's write is flushed when it commits.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":2}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.independent-inner`
- **Evidence:** [cases/TX-04.independent-inner.mikroorm.native.json](cases/TX-04.independent-inner.mikroorm.native.json)

### `MG-02.held` on mikroorm (native)

1. **What the API reported:** applied: migrator.up() applied Migration20200101000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** none
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.mikroorm.native.json](cases/MG-02.held.mikroorm.native.json)

### `MG-02.first-deployment` on mikroorm (native)

1. **What the API reported:** applied: migrator.up() applied Migration20200101000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see, before it starts, that the other is about to apply the same migration. The database starts with no history row that could tell it so. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** none
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.mikroorm.native.json](cases/MG-02.first-deployment.mikroorm.native.json)

### `MG-02.session-loss` on mikroorm (native)

1. **What the API reported:** failed: migrator.up() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.mikroorm.native.json](cases/MG-02.session-loss.mikroorm.native.json)

### `MG-02.idle-session-timeout` on mikroorm (native)

1. **What the API reported:** applied: migrator.up() applied Migration20200101000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** none
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.mikroorm.native.json](cases/MG-02.idle-session-timeout.mikroorm.native.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 3003 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 3052 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 3052). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 3076 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 3076). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 3103 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 3103), `inner` yes (inserted by xid 3104). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 3133 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 53 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 3193 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 3193 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 3193), `next` yes (inserted by xid 3193). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 3220 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 3247 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 3275 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 3332 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 3332). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 3356 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 3356). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
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

### `TX-01A.caught-error-then-commit` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 3702 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.typeorm.native.json](cases/TX-01A.caught-error-then-commit.typeorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 3738 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json)

### `TX-02.savepoint-rollback-rejected` on typeorm (native)

1. **What the API reported:** failed: ds.transaction(callback) rejected with an error the callback did not throw.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 3753 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.typeorm.native.json](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json)

### `TX-03.rollback-not-sent` on typeorm (native)

1. **What the API reported:** rolled_back: ds.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 58 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 3783 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 3783 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 3783), `next` yes (inserted by xid 3783). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.typeorm.native.json](cases/TX-03.rollback-not-sent.typeorm.native.json)

### `TX-03.statement-error-rollback-not-sent` on typeorm (native)

1. **What the API reported:** rolled_back: ds.transaction(callback) rejected with the error the callback threw. The next unit of work: failed, after 2 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 3795 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json](cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json)

### `MG-02.held` on typeorm (native)

1. **What the API reported:** applied: runMigrations() executed Ppcsm11700000000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** none
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.typeorm.native.json](cases/MG-02.held.typeorm.native.json)

### `MG-02.first-deployment` on typeorm (native)

1. **What the API reported:** applied: runMigrations() executed Ppcsm11700000000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see, before it starts, that the other is about to apply the same migration. The database starts with no history row that could tell it so. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** none
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.typeorm.native.json](cases/MG-02.first-deployment.typeorm.native.json)

### `MG-02.session-loss` on typeorm (native)

1. **What the API reported:** failed: runMigrations() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.typeorm.native.json](cases/MG-02.session-loss.typeorm.native.json)

### `MG-02.idle-session-timeout` on typeorm (native)

1. **What the API reported:** applied: runMigrations() executed Ppcsm11700000000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** none
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.typeorm.native.json](cases/MG-02.idle-session-timeout.typeorm.native.json)

## Qualified passes

- `TX-01A.caught-error-then-commit` on lucid (pre-commit-probe): **PASS (mechanism not exercised)**. after the API returned, the session was "idle", and its last statement was "ROLLBACK"
- `TX-01B.commit-reply-discarded` on mikroorm (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-discarded` on typeorm (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Inconclusive, unsupported and not run

- `TX-01B.commit-reply-unseen` on lucid (native): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on lucid (native): **UNSUPPORTED (not applicable by design)**. Lucid has no propagation modes and no deferred writes: a nested trx.transaction() is always a savepoint, and every write is sent when it is made. An independent transaction is an unrelated db.transaction() on another connection, which shares no pending writes with the outer one, so the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.
- `MG-02.idle-session-timeout` on lucid (native): **INCONCLUSIVE**. an invariant could not be evaluated: MG-02.4 (no session of runner A ended, so the fault did not happen)
- `TX-01B.commit-reply-unseen` on mikroorm (native): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on pg-control (correct): **UNSUPPORTED (not applicable by design)**. The control has no propagation modes, so it has no API that promises an independent inner transaction, and the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.
- `TX-01B.commit-reply-unseen` on typeorm (native): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on typeorm (native): **UNSUPPORTED (not applicable by design)**. TypeORM has no propagation modes and no deferred writes in the repository API this adapter uses: a nested manager.transaction() is always a savepoint, and every insert is sent when it is made. An independent transaction is an unrelated ds.transaction() on another connection, which shares no pending writes with the outer one, so the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| lucid (native) | native | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `fae3c8c56d97…` |
| lucid (pre-commit-probe) | hardened | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `fae3c8c56d97…` |
| mikroorm (native) | native | @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8805029c4e73…` |
| mikroorm (clear-forks) | configured | @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8805029c4e73…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| typeorm (native) | native | typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `e5cec7da0662…` |

