# PPCS run 2026-10-17T01-51-34Z-c1a29f

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications/transactions.v1.json`, sha256 `2f6ad9f7bf99…`
- **Runner:** PPCS 0.2.0, harness sha256 `9be521e4e5b9…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-17T01:51:34.206Z; duration 192 s
- **Counts:** PASS 45, FAIL 29, UNSUPPORTED 3 (3 not applicable by design, outside coverage)

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | lucid (native) | lucid (pre-commit-probe) | mikroorm (native) | mikroorm (clear-forks) | pg-control (correct) | pg-control (unsafe) | typeorm (native) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.lucid.native.json) | [PASS](cases/CTL-01.commit.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.commit.mikroorm.native.json) | [PASS](cases/CTL-01.commit.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.typeorm.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.lucid.native.json) | [PASS](cases/CTL-01.rollback.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.rollback.mikroorm.native.json) | [PASS](cases/CTL-01.rollback.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.typeorm.native.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [FAIL](cases/TX-01A.caught-error-then-commit.lucid.native.json) | [PASS (mechanism not exercised)](cases/TX-01A.caught-error-then-commit.lucid.pre-commit-probe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.mikroorm.native.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.typeorm.native.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [FAIL](cases/TX-01B.conn-lost-before-commit.lucid.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.mikroorm.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) | [PASS](cases/TX-01B.conn-lost-before-commit.typeorm.native.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [FAIL (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.lucid.native.json) | — | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.mikroorm.native.json) | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-discarded.typeorm.native.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-rejected.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [FAIL](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.mikroorm.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.typeorm.native.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-03.rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-03.rollback-not-sent.typeorm.native.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [PASS](cases/TX-03.conn-lost-in-transaction.lucid.native.json) | — | [FAIL](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json) | — | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) | [PASS](cases/TX-03.conn-lost-in-transaction.typeorm.native.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.lucid.native.json) | — | [FAIL](cases/TX-04.nested-failure-contained.mikroorm.native.json) | [PASS](cases/TX-04.nested-failure-contained.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-failure-contained.typeorm.native.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.lucid.native.json) | — | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-released-outer-rollback.typeorm.native.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.lucid.native.json) | — | [FAIL](cases/TX-04.independent-inner.mikroorm.native.json) | [PASS](cases/TX-04.independent-inner.mikroorm.clear-forks.json) | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.pg-control.correct.json) | — | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.typeorm.native.json) |

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
- `TX-04.independent-inner`: no control adapter states an expectation for this case

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2106 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.lucid.native.json](cases/TX-01A.caught-error-then-commit.lucid.native.json)

### `TX-01B.conn-lost-before-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 2130 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** Known not committed: the session ended before the framework tried to commit, so the driver refused to send COMMIT ("Client has encountered a connection error and is not queryable"). A report of rollback is justified; a report of success is not.
4. **Contract:** TX-01B.1 violated: When the connection or PostgreSQL's reply was lost around COMMIT, so that the client never received an acknowledgement of COMMIT, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.conn-lost-before-commit`
- **Evidence:** [cases/TX-01B.conn-lost-before-commit.lucid.native.json](cases/TX-01B.conn-lost-before-commit.lucid.native.json)

### `TX-01B.commit-reply-discarded` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 2142 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 2142). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.1 violated: When the connection or PostgreSQL's reply was lost around COMMIT, so that the client never received an acknowledgement of COMMIT, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.lucid.native.json](cases/TX-01B.commit-reply-discarded.lucid.native.json)

### `TX-02.savepoint-rollback-not-sent` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2154 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2154), `inner` yes (inserted by xid 2155). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.lucid.native.json](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json)

### `TX-02.savepoint-rollback-rejected` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2169 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.lucid.native.json](cases/TX-02.savepoint-rollback-rejected.lucid.native.json)

### `TX-02.conn-lost-before-savepoint-rollback` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2185 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework sees its connection fail during the savepoint rollback.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.conn-lost-before-savepoint-rollback`
- **Evidence:** [cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json)

### `TX-03.rollback-not-sent` on lucid (native)

1. **What the API reported:** rolled_back: db.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 31 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2200 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 2200 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 2200), `next` yes (inserted by xid 2200). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.lucid.native.json](cases/TX-03.rollback-not-sent.lucid.native.json)

### `TX-03.statement-error-rollback-not-sent` on lucid (native)

1. **What the API reported:** rolled_back: db.transaction(callback) rejected with the error the callback threw. The next unit of work: rolled_back, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2212 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.lucid.native.json](cases/TX-03.statement-error-rollback-not-sent.lucid.native.json)

### `TX-01A.caught-error-then-commit` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2317 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Reused experiment T4f: the outer scope flushes its write; the duplicate insert runs in an inner em.transactional() with propagation REQUIRED, which joins the outer transaction; the outer scope catches the error and returns with nothing pending. Other forms (for example T4g) are not covered by this result.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.mikroorm.native.json](cases/TX-01A.caught-error-then-commit.mikroorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2354 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2354), `inner` yes (inserted by xid 2355). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** The nested em.transactional() is called with { clear: true }, as in reused experiments R1a, T7c and R1e. The outer scope flushes its write before the nested scope starts, and the clear fork keeps the nested scope's flush to its own entity, so the case isolates the savepoint rollback from the pending-write hazard that TX-04 targets.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json)

### `TX-02.savepoint-rollback-rejected` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2369 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** The nested em.transactional() is called with { clear: true }, as in reused experiments R1a, T7c and R1e. The outer scope flushes its write before the nested scope starts, and the clear fork keeps the nested scope's flush to its own entity, so the case isolates the savepoint rollback from the pending-write hazard that TX-04 targets.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json)

### `TX-03.rollback-not-sent` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2399 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.mikroorm.native.json](cases/TX-03.rollback-not-sent.mikroorm.native.json)

### `TX-03.statement-error-rollback-not-sent` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2411 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json](cases/TX-03.statement-error-rollback-not-sent.mikroorm.native.json)

### `TX-03.conn-lost-in-transaction` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2423 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.mikroorm.native.json](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json)

### `TX-04.nested-failure-contained` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) with a nested em.transactional(callback), default propagation NESTED resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 2435 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: MikroORM 7.2.5 documents NESTED as "Create a nested savepoint within the current transaction, or a new transaction if none exists" (enums.d.ts, TransactionPropagation), and a nested em.transactional() as creating a savepoint by default (EntityManager.transactional).

- **Fault:** none
- **Form:** The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the nested scope flushes its own write.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.mikroorm.native.json](cases/TX-04.nested-failure-contained.mikroorm.native.json)

### `TX-04.independent-inner` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) with an inner em.transactional(callback, { propagation: REQUIRES_NEW }) rejected with the error the callback threw.
2. **What PostgreSQL did:** transaction `inner` (its ID read inside it at `inner-after-write`): xid 2498 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2498), `inner` yes (inserted by xid 2498). Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the inner transaction committed and the outer one rolled back. From the API alone, it cannot see which transaction carried a write the framework still had pending. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.3 violated: An inner transaction started through an API that promises an independent transaction commits only its own writes: the outer scope's writes, whether already sent or still pending in the framework, are committed only by the outer transaction. Framework contract: MikroORM 7.2.5 documents REQUIRES_NEW as "Always create a new transaction, suspending the current one if it exists" (enums.d.ts, TransactionPropagation).

- **Fault:** none
- **Form:** The outer write is left pending in the unit of work, as ordinary MikroORM code leaves it; the inner transaction's write is flushed when it commits.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":2}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.independent-inner`
- **Evidence:** [cases/TX-04.independent-inner.mikroorm.native.json](cases/TX-04.independent-inner.mikroorm.native.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2583 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 2631 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 2631). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2658 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 2658), `inner` yes (inserted by xid 2659). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 2688 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 28 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2748 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 2748 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 2748), `next` yes (inserted by xid 2748). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2775 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2802 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 2829 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 2898 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.typeorm.native.json](cases/TX-01A.caught-error-then-commit.typeorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 2934 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json)

### `TX-02.savepoint-rollback-rejected` on typeorm (native)

1. **What the API reported:** failed: ds.transaction(callback) rejected with an error the callback did not throw.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 2949 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.typeorm.native.json](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json)

### `TX-03.rollback-not-sent` on typeorm (native)

1. **What the API reported:** rolled_back: ds.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 32 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 2980 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 2980 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 2980), `next` yes (inserted by xid 2980). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.typeorm.native.json](cases/TX-03.rollback-not-sent.typeorm.native.json)

### `TX-03.statement-error-rollback-not-sent` on typeorm (native)

1. **What the API reported:** rolled_back: ds.transaction(callback) rejected with the error the callback threw. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 2992 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json](cases/TX-03.statement-error-rollback-not-sent.typeorm.native.json)

## Qualified passes

- `TX-01A.caught-error-then-commit` on lucid (pre-commit-probe): **PASS (mechanism not exercised)**. after the API returned, the session was "idle", and its last statement was "ROLLBACK"
- `TX-01B.commit-reply-discarded` on mikroorm (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-discarded` on typeorm (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Inconclusive, unsupported and not run

- `TX-04.independent-inner` on lucid (native): **UNSUPPORTED (not applicable by design)**. Lucid has no propagation modes and no deferred writes: a nested trx.transaction() is always a savepoint, and every write is sent when it is made. An independent transaction is an unrelated db.transaction() on another connection, which shares no pending writes with the outer one, so the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.
- `TX-04.independent-inner` on pg-control (correct): **UNSUPPORTED (not applicable by design)**. The control has no propagation modes, so it has no API that promises an independent inner transaction, and the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.
- `TX-04.independent-inner` on typeorm (native): **UNSUPPORTED (not applicable by design)**. TypeORM has no propagation modes and no deferred writes in the repository API this adapter uses: a nested manager.transaction() is always a savepoint, and every insert is sent when it is made. An independent transaction is an unrelated ds.transaction() on another connection, which shares no pending writes with the outer one, so the hazard TX-04.3 targets (pending outer writes committed by the inner transaction) cannot arise.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| lucid (native) | native | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `af2c3ca109a0…` |
| lucid (pre-commit-probe) | hardened | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `af2c3ca109a0…` |
| mikroorm (native) | native | @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `93b8a1b69e7e…` |
| mikroorm (clear-forks) | configured | @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `93b8a1b69e7e…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `93437193c770…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `93437193c770…` |
| typeorm (native) | native | typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `de9087739f37…` |

