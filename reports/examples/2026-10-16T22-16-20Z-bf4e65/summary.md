# PPCS run 2026-10-16T22-16-20Z-bf4e65

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications/transactions.v1.json`, sha256 `328dab252187…`
- **Runner:** PPCS 0.1.0, Node v24.14.1
- **Started:** 2026-10-16T22:16:20.887Z; duration 46 s
- **Counts:** PASS 40, FAIL 25, UNSUPPORTED 3

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL, which shows that the runner detects a known-bad implementation.

## Results

| Case | lucid (native) | lucid (pre-commit-probe) | mikroorm (native) | mikroorm (clear-forks) | pg-control (correct) | pg-control (unsafe) | typeorm (native) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | [PASS](cases/CTL-01.commit.lucid.native.json) | — | [PASS](cases/CTL-01.commit.mikroorm.native.json) | — | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.typeorm.native.json) |
| `CTL-01.rollback` | [PASS](cases/CTL-01.rollback.lucid.native.json) | — | [PASS](cases/CTL-01.rollback.mikroorm.native.json) | — | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.typeorm.native.json) |
| `TX-01A.caught-error-then-commit` | [FAIL](cases/TX-01A.caught-error-then-commit.lucid.native.json) | [PASS](cases/TX-01A.caught-error-then-commit.lucid.pre-commit-probe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.mikroorm.native.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) | [FAIL](cases/TX-01A.caught-error-then-commit.typeorm.native.json) |
| `TX-01B.conn-lost-before-commit` | [FAIL](cases/TX-01B.conn-lost-before-commit.lucid.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.mikroorm.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [FAIL](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) | [PASS](cases/TX-01B.conn-lost-before-commit.typeorm.native.json) |
| `TX-01B.commit-reply-discarded` | [FAIL](cases/TX-01B.commit-reply-discarded.lucid.native.json) | — | [PASS](cases/TX-01B.commit-reply-discarded.mikroorm.native.json) | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) | [PASS](cases/TX-01B.commit-reply-discarded.typeorm.native.json) |
| `TX-02.savepoint-rollback-not-sent` | [FAIL](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json) |
| `TX-02.savepoint-rollback-rejected` | [FAIL](cases/TX-02.savepoint-rollback-rejected.lucid.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | [FAIL](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.mikroorm.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.typeorm.native.json) |
| `TX-03.rollback-not-sent` | [FAIL](cases/TX-03.rollback-not-sent.lucid.native.json) | — | [FAIL](cases/TX-03.rollback-not-sent.mikroorm.native.json) | — | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) | [FAIL](cases/TX-03.rollback-not-sent.typeorm.native.json) |
| `TX-03.conn-lost-in-transaction` | [PASS](cases/TX-03.conn-lost-in-transaction.lucid.native.json) | — | [FAIL](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json) | — | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) | [PASS](cases/TX-03.conn-lost-in-transaction.typeorm.native.json) |
| `TX-04.nested-failure-contained` | [PASS](cases/TX-04.nested-failure-contained.lucid.native.json) | — | [FAIL](cases/TX-04.nested-failure-contained.mikroorm.native.json) | [PASS](cases/TX-04.nested-failure-contained.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [PASS](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-failure-contained.typeorm.native.json) |
| `TX-04.nested-released-outer-rollback` | [PASS](cases/TX-04.nested-released-outer-rollback.lucid.native.json) | — | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.mikroorm.clear-forks.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) | [PASS](cases/TX-04.nested-released-outer-rollback.typeorm.native.json) |
| `TX-04.independent-inner` | [UNSUPPORTED](cases/TX-04.independent-inner.lucid.native.json) | — | [FAIL](cases/TX-04.independent-inner.mikroorm.native.json) | [PASS](cases/TX-04.independent-inner.mikroorm.clear-forks.json) | [UNSUPPORTED](cases/TX-04.independent-inner.pg-control.correct.json) | — | [UNSUPPORTED](cases/TX-04.independent-inner.typeorm.native.json) |

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3413, read inside it at `after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category A. A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.lucid.native.json](cases/TX-01A.caught-error-then-commit.lucid.native.json)

### `TX-01B.conn-lost-before-commit` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3421, read inside it at `before-end`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** No reply to COMMIT can arrive: the session ended before the framework tried to commit. The driver could know that it never sent COMMIT, but the framework's API has no way to report that.
4. **Contract:** TX-01B.1 violated: When the client has received no reply to COMMIT, because the connection or the reply was lost, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B. pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.conn-lost-before-commit`
- **Evidence:** [cases/TX-01B.conn-lost-before-commit.lucid.native.json](cases/TX-01B.conn-lost-before-commit.lucid.native.json)

### `TX-01B.commit-reply-discarded` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3425, read inside it at `before-end`): pg_xact_status() **committed**; markers visible to a separate connection: `tx` yes (inserted by xid 3425). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.1 violated: When the client has received no reply to COMMIT, because the connection or the reply was lost, the API does not report a successful commit. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category D. A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.lucid.native.json](cases/TX-01B.commit-reply-discarded.lucid.native.json)

### `TX-02.savepoint-rollback-not-sent` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3429, read inside it at `outer-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `outer` yes (inserted by xid 3429), `inner` yes (inserted by xid 3430). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.lucid.native.json](cases/TX-02.savepoint-rollback-not-sent.lucid.native.json)

### `TX-02.savepoint-rollback-rejected` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3434, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error for the savepoint rollback, and later, if it sends COMMIT, the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, so that PostgreSQL rejects it with an error (3B001) that aborts the transaction. The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.lucid.native.json](cases/TX-02.savepoint-rollback-rejected.lucid.native.json)

### `TX-02.conn-lost-before-savepoint-rollback` on lucid (native)

1. **What the API reported:** committed: db.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3439, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework sees its connection fail during the savepoint rollback.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category B. pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-02.conn-lost-before-savepoint-rollback`
- **Evidence:** [cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json](cases/TX-02.conn-lost-before-savepoint-rollback.lucid.native.json)

### `TX-03.rollback-not-sent` on lucid (native)

1. **What the API reported:** rolled_back: db.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 7 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3444, read inside it at `unit1-after-write`): pg_xact_status() **committed**; transaction `unit2` (xid 3444, read inside it at `unit2-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `doomed` yes (inserted by xid 3444), `next` yes (inserted by xid 3444). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In @adonisjs/lucid 22.4.2, the managed form of transaction() awaits the callback, commits, and resolves with the callback's value; if the callback throws, it rolls back and rethrows (src/query_client/index.js, "Self managed transaction"). A resolved call is Lucid's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.lucid.native.json](cases/TX-03.rollback-not-sent.lucid.native.json)

### `TX-01A.caught-error-then-commit` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3471, read inside it at `after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category A. A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.mikroorm.native.json](cases/TX-01A.caught-error-then-commit.mikroorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3483, read inside it at `outer-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `outer` yes (inserted by xid 3483), `inner` yes (inserted by xid 3484). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json](cases/TX-02.savepoint-rollback-not-sent.mikroorm.native.json)

### `TX-02.savepoint-rollback-rejected` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3488, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error for the savepoint rollback, and later, if it sends COMMIT, the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, so that PostgreSQL rejects it with an error (3B001) that aborts the transaction. The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json](cases/TX-02.savepoint-rollback-rejected.mikroorm.native.json)

### `TX-03.rollback-not-sent` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3498, read inside it at `unit1-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.mikroorm.native.json](cases/TX-03.rollback-not-sent.mikroorm.native.json)

### `TX-03.conn-lost-in-transaction` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) rejected with the error the callback threw. The next unit of work: still pending after 5000 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3502, read inside it at `unit1-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: In MikroORM 7.2.5, em.transactional(callback) runs the callback, flushes, and commits (AbstractSqlConnection.transactional in @mikro-orm/sql: begin, callback, commit, return); if the callback or the flush throws, it rolls back and rethrows that error. A resolved call is MikroORM's report that the transaction committed.

- **Fault:** category B. pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.mikroorm.native.json](cases/TX-03.conn-lost-in-transaction.mikroorm.native.json)

### `TX-04.nested-failure-contained` on mikroorm (native)

1. **What the API reported:** committed: em.transactional(callback) with a nested em.transactional(callback), default propagation NESTED resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3506, read inside it at `inner-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: MikroORM 7.2.5 documents NESTED as "Create a nested savepoint within the current transaction, or a new transaction if none exists" (enums.d.ts, TransactionPropagation), and a nested em.transactional() as creating a savepoint by default (EntityManager.transactional).

- **Fault:** none
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.mikroorm.native.json](cases/TX-04.nested-failure-contained.mikroorm.native.json)

### `TX-04.independent-inner` on mikroorm (native)

1. **What the API reported:** rolled_back: em.transactional(callback) with an inner em.transactional(callback, { propagation: REQUIRES_NEW }) rejected with the error the callback threw.
2. **What PostgreSQL did:** transaction `inner` (xid 3527, read inside it at `inner-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `outer` yes (inserted by xid 3527), `inner` yes (inserted by xid 3527). Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the inner transaction committed and the outer one rolled back. From the API alone, it cannot see which transaction carried a write the framework still had pending. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.3 violated: An inner transaction started through an API that promises an independent transaction commits only its own writes: the outer scope's writes, whether already sent or still pending in the framework, are committed only by the outer transaction. Framework contract: MikroORM 7.2.5 documents REQUIRES_NEW as "Always create a new transaction, suspending the current one if it exists" (enums.d.ts, TransactionPropagation).

- **Fault:** none
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":2}`
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=TX-04.independent-inner`
- **Evidence:** [cases/TX-04.independent-inner.mikroorm.native.json](cases/TX-04.independent-inner.mikroorm.native.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (xid 3555, read inside it at `after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks.

- **Fault:** category A. A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.conn-lost-before-commit` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (xid 3563, read inside it at `before-end`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** No reply to COMMIT can arrive: the session ended before the framework tried to commit. The driver could know that it never sent COMMIT, but the framework's API has no way to report that.
4. **Contract:** TX-01B.2 violated: When the client has received no reply to COMMIT, the API does not report a confirmed rollback. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks.

- **Fault:** category B. pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"settle_ms":100}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.conn-lost-before-commit`
- **Evidence:** [cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (xid 3571, read inside it at `before-end`): pg_xact_status() **committed**; markers visible to a separate connection: `tx` yes (inserted by xid 3571). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When the client has received no reply to COMMIT, the API does not report a confirmed rollback. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks.

- **Fault:** category D. A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (xid 3580, read inside it at `outer-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `outer` yes (inserted by xid 3580), `inner` yes (inserted by xid 3581). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (xid 3590, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error for the savepoint rollback, and later, if it sends COMMIT, the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks.

- **Fault:** category C. A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, so that PostgreSQL rejects it with an error (3B001) that aborts the transaction. The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 7 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3610, read inside it at `unit1-after-write`): pg_xact_status() **committed**; transaction `unit2` (xid 3610, read inside it at `unit2-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `doomed` yes (inserted by xid 3610), `next` yes (inserted by xid 3610). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3619, read inside it at `unit1-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B. pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3651, read inside it at `after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category A. A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.typeorm.native.json](cases/TX-01A.caught-error-then-commit.typeorm.native.json)

### `TX-02.savepoint-rollback-not-sent` on typeorm (native)

1. **What the API reported:** committed: ds.transaction(callback) resolved.
2. **What PostgreSQL did:** transaction `tx` (xid 3663, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json](cases/TX-02.savepoint-rollback-not-sent.typeorm.native.json)

### `TX-02.savepoint-rollback-rejected` on typeorm (native)

1. **What the API reported:** failed: ds.transaction(callback) rejected with an error the callback did not throw.
2. **What PostgreSQL did:** transaction `tx` (xid 3668, read inside it at `outer-after-write`): pg_xact_status() **aborted**; markers visible to a separate connection: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework receives PostgreSQL's error for the savepoint rollback, and later, if it sends COMMIT, the command tag ROLLBACK.
4. **Contract:** TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, so that PostgreSQL rejects it with an error (3B001) that aborts the transaction. The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1}`
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.typeorm.native.json](cases/TX-02.savepoint-rollback-rejected.typeorm.native.json)

### `TX-03.rollback-not-sent` on typeorm (native)

1. **What the API reported:** rolled_back: ds.transaction(callback) rejected with the error the callback threw. The next unit of work: committed, after 6 ms.
2. **What PostgreSQL did:** transaction `unit1` (xid 3678, read inside it at `unit1-after-write`): pg_xact_status() **committed**; transaction `unit2` (xid 3678, read inside it at `unit2-after-write`): pg_xact_status() **committed**; markers visible to a separate connection: `doomed` yes (inserted by xid 3678), `next` yes (inserted by xid 3678). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: In TypeORM 1.1.2, ds.transaction(callback) (EntityManager.transaction) starts a transaction, runs the callback, calls commitTransaction() and returns the callback's result; if the callback throws, it calls rollbackTransaction(), ignores any rollback error, and rethrows (entity-manager/EntityManager.js). A resolved call is TypeORM's report that the transaction committed.

- **Fault:** category C. A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.typeorm.native.json](cases/TX-03.rollback-not-sent.typeorm.native.json)

## Inconclusive, unsupported and not run

- `TX-04.independent-inner` on lucid (native): **UNSUPPORTED**. Lucid has no propagation modes: a nested trx.transaction() is always a savepoint, and an independent transaction is an unrelated db.transaction() on another connection, which this case does not test.
- `TX-04.independent-inner` on pg-control (correct): **UNSUPPORTED**. The control implements no propagation modes, so it has no API that promises an independent inner transaction.
- `TX-04.independent-inner` on typeorm (native): **UNSUPPORTED**. TypeORM has no propagation modes: a nested manager.transaction() is always a savepoint, and an independent transaction is an unrelated ds.transaction() on another connection, which this case does not test.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| lucid (native) | native | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `f7d230e1ddd4…` |
| lucid (pre-commit-probe) | hardened | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `f7d230e1ddd4…` |
| mikroorm (native) | native | @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `2cb24d85f85c…` |
| mikroorm (clear-forks) | configured | @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `2cb24d85f85c…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `b80f2688b4b0…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `b80f2688b4b0…` |
| typeorm (native) | native | typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `b8dbf1b8003f…` |

