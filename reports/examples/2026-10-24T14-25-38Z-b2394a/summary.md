# PPCS run 2026-10-24T14-25-38Z-b2394a

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `2d44447a84ed…`
- **Runner:** PPCS 0.3.0, harness sha256 `ca9a464603c5…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-24T14:25:38.456Z; duration 159 s
- **Counts:** PASS 63, FAIL 44, UNSUPPORTED 16 (2 not applicable by design, outside coverage), NOT_RUN 2

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | laravel (managed) | laravel (explicit) | laravel (persistent) | pdo-control (correct) | pdo-control (unsafe) | pdo-control (persistent) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.laravel.managed.json) | [PASS](cases/CTL-01.commit.laravel.explicit.json) | [PASS](cases/CTL-01.commit.laravel.persistent.json) | [PASS](cases/CTL-01.commit.pdo-control.correct.json) | [PASS](cases/CTL-01.commit.pdo-control.unsafe.json) | [PASS](cases/CTL-01.commit.pdo-control.persistent.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.laravel.managed.json) | [PASS](cases/CTL-01.rollback.laravel.explicit.json) | [PASS](cases/CTL-01.rollback.laravel.persistent.json) | [PASS](cases/CTL-01.rollback.pdo-control.correct.json) | [PASS](cases/CTL-01.rollback.pdo-control.unsafe.json) | [PASS](cases/CTL-01.rollback.pdo-control.persistent.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [FAIL](cases/TX-01A.caught-error-then-commit.laravel.managed.json) | [FAIL](cases/TX-01A.caught-error-then-commit.laravel.explicit.json) | — | [PASS (mechanism not exercised)](cases/TX-01A.caught-error-then-commit.pdo-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pdo-control.unsafe.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.laravel.managed.json) | [PASS](cases/TX-01B.conn-lost-before-commit.laravel.explicit.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.pdo-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pdo-control.unsafe.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [NOT_RUN](cases/TX-01B.commit-reply-discarded.laravel.managed.json) | — | — | [NOT_RUN](cases/TX-01B.commit-reply-discarded.pdo-control.correct.json) | — | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.laravel.managed.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.laravel.explicit.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.pdo-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.laravel.managed.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-02.savepoint-rollback-not-sent.pdo-control.correct.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-rejected.laravel.managed.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-02.savepoint-rollback-rejected.pdo-control.correct.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [FAIL](cases/TX-02.conn-lost-before-savepoint-rollback.laravel.managed.json) | [FAIL](cases/TX-02.conn-lost-before-savepoint-rollback.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-02.conn-lost-before-savepoint-rollback.pdo-control.correct.json) | — | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.rollback-not-sent.laravel.managed.json) | [FAIL](cases/TX-03.rollback-not-sent.laravel.explicit.json) | [FAIL](cases/TX-03.rollback-not-sent.laravel.persistent.json) | [PASS](cases/TX-03.rollback-not-sent.pdo-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pdo-control.unsafe.json) | [PASS](cases/TX-03.rollback-not-sent.pdo-control.persistent.json) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.laravel.managed.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.laravel.explicit.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.laravel.persistent.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pdo-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pdo-control.unsafe.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pdo-control.persistent.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [FAIL](cases/TX-03.conn-lost-in-transaction.laravel.managed.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.laravel.explicit.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.laravel.persistent.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pdo-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pdo-control.unsafe.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pdo-control.persistent.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.laravel.managed.json) | [PASS](cases/TX-04.nested-failure-contained.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-04.nested-failure-contained.pdo-control.correct.json) | — | — | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.laravel.managed.json) | [PASS](cases/TX-04.nested-released-outer-rollback.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-04.nested-released-outer-rollback.pdo-control.correct.json) | — | — | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.laravel.managed.json) | — | — | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.pdo-control.correct.json) | — | — | — | — |
| `TX-05.managed-serializable` | none | [PASS](cases/TX-05.managed-serializable.laravel.managed.json) | — | — | [UNSUPPORTED](cases/TX-05.managed-serializable.pdo-control.correct.json) | — | — | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) |
| `TX-05.explicit-serializable` | none | — | [PASS](cases/TX-05.explicit-serializable.laravel.explicit.json) | — | [UNSUPPORTED](cases/TX-05.explicit-serializable.pdo-control.correct.json) | — | — | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) |
| `MG-02.held` | none | [FAIL](cases/MG-02.held.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-02.held.pdo-control.correct.json) | — | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-02.first-deployment.pdo-control.correct.json) | — | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) |
| `MG-02.session-loss` | B (server-side termination) | [FAIL](cases/MG-02.session-loss.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-02.session-loss.pdo-control.correct.json) | — | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) |
| `MG-02.idle-session-timeout` | none | [FAIL](cases/MG-02.idle-session-timeout.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-02.idle-session-timeout.pdo-control.correct.json) | — | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-03.valid-reversal.pdo-control.correct.json) | — | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) |
| `MG-03.no-reversal` | none | [FAIL](cases/MG-03.no-reversal.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-03.no-reversal.pdo-control.correct.json) | — | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.laravel.managed.json) | — | — | [UNSUPPORTED](cases/MG-03.failing-reversal.pdo-control.correct.json) | — | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- laravel (managed): held
- laravel (explicit): held
- laravel (persistent): held
- pdo-control (correct): held
- pdo-control (unsafe): held
- pdo-control (persistent): held
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
- `MG-02.held`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.first-deployment`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.session-loss`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.idle-session-timeout`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.valid-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.no-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.failing-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on laravel (managed)

1. **What the API reported:** committed: Connection::transaction() returned. When the callback returns, Laravel calls PDO::commit() if the transaction level is 1. The return value of PDO::commit() is not inspected..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 4645 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.laravel.managed.json](cases/TX-01A.caught-error-then-commit.laravel.managed.json)

### `TX-01A.caught-error-then-commit` on laravel (explicit)

1. **What the API reported:** committed: Connection::commit() returned. At level 1 that calls PDO::commit() and does not inspect its return value or a command tag..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 4657 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.laravel.explicit.json](cases/TX-01A.caught-error-then-commit.laravel.explicit.json)

### `TX-02.savepoint-rollback-not-sent` on laravel (managed)

1. **What the API reported:** committed: Connection::transaction() returned. When the callback returns, Laravel calls PDO::commit() if the transaction level is 1. The return value of PDO::commit() is not inspected..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 4717 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.laravel.managed.json](cases/TX-02.savepoint-rollback-not-sent.laravel.managed.json)

### `TX-02.savepoint-rollback-not-sent` on laravel (explicit)

1. **What the API reported:** committed: Connection::commit() returned. At level 1 that calls PDO::commit() and does not inspect its return value or a command tag..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 4732 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle in transaction".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.laravel.explicit.json](cases/TX-02.savepoint-rollback-not-sent.laravel.explicit.json)

### `TX-02.savepoint-rollback-rejected` on laravel (managed)

1. **What the API reported:** committed: Connection::transaction() returned. When the callback returns, Laravel calls PDO::commit() if the transaction level is 1. The return value of PDO::commit() is not inspected..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 4747 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle in transaction (aborted)".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.laravel.managed.json](cases/TX-02.savepoint-rollback-rejected.laravel.managed.json)

### `TX-02.savepoint-rollback-rejected` on laravel (explicit)

1. **What the API reported:** committed: Connection::commit() returned. At level 1 that calls PDO::commit() and does not inspect its return value or a command tag..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): open at report time (`after-outer`: xid 4762 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle in transaction (aborted)".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. TX-02.2 violated: When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.laravel.explicit.json](cases/TX-02.savepoint-rollback-rejected.laravel.explicit.json)

### `TX-02.conn-lost-before-savepoint-rollback` on laravel (managed)

1. **What the API reported:** committed: Connection::transaction() returned. When the callback returns, Laravel calls PDO::commit() if the transaction level is 1. The return value of PDO::commit() is not inspected..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 4777 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework sees its connection fail during the savepoint rollback.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-02.conn-lost-before-savepoint-rollback`
- **Evidence:** [cases/TX-02.conn-lost-before-savepoint-rollback.laravel.managed.json](cases/TX-02.conn-lost-before-savepoint-rollback.laravel.managed.json)

### `TX-02.conn-lost-before-savepoint-rollback` on laravel (explicit)

1. **What the API reported:** committed: Connection::commit() returned. At level 1 that calls PDO::commit() and does not inspect its return value or a command tag..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 4792 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework sees its connection fail during the savepoint rollback.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-02.conn-lost-before-savepoint-rollback`
- **Evidence:** [cases/TX-02.conn-lost-before-savepoint-rollback.laravel.explicit.json](cases/TX-02.conn-lost-before-savepoint-rollback.laravel.explicit.json)

### `TX-03.rollback-not-sent` on laravel (managed)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: committed, after 28 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 4807 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): open at report time (`after-end`: xid 4807 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.laravel.managed.json](cases/TX-03.rollback-not-sent.laravel.managed.json)

### `TX-03.rollback-not-sent` on laravel (explicit)

1. **What the API reported:** failed: the explicit transaction failed and Connection::rollBack() threw. The next unit of work: committed, after 28 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 4822 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): open at report time (`after-end`: xid 4822 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.laravel.explicit.json](cases/TX-03.rollback-not-sent.laravel.explicit.json)

### `TX-03.rollback-not-sent` on laravel (persistent)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: committed, after 27 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 4838 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): open at report time (`after-end`: xid 4838 in progress); rolled back at teardown, so decided after the API returned, not by the reported operation; markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `persistent` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=persistent --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.laravel.persistent.json](cases/TX-03.rollback-not-sent.laravel.persistent.json)

### `TX-03.statement-error-rollback-not-sent` on laravel (managed)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4853 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.laravel.managed.json](cases/TX-03.statement-error-rollback-not-sent.laravel.managed.json)

### `TX-03.statement-error-rollback-not-sent` on laravel (explicit)

1. **What the API reported:** failed: the explicit transaction failed and Connection::rollBack() threw. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4865 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.laravel.explicit.json](cases/TX-03.statement-error-rollback-not-sent.laravel.explicit.json)

### `TX-03.statement-error-rollback-not-sent` on laravel (persistent)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4877 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `persistent` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=persistent --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.laravel.persistent.json](cases/TX-03.statement-error-rollback-not-sent.laravel.persistent.json)

### `TX-03.conn-lost-in-transaction` on laravel (managed)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4889 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.laravel.managed.json](cases/TX-03.conn-lost-in-transaction.laravel.managed.json)

### `TX-03.conn-lost-in-transaction` on laravel (explicit)

1. **What the API reported:** failed: the explicit transaction failed and Connection::rollBack() threw. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4901 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `explicit` (native); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=explicit --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.laravel.explicit.json](cases/TX-03.conn-lost-in-transaction.laravel.explicit.json)

### `TX-03.conn-lost-in-transaction` on laravel (persistent)

1. **What the API reported:** failed: Connection::transaction() threw. The exception is not the callback's own error, so this is not reported as a confirmed rollback.. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 4913 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: Laravel 13.38.0 Illuminate\Database\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config['isolation_level']}" when the connection is opened, if that config key is set. This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `persistent` (configured); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=persistent --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.laravel.persistent.json](cases/TX-03.conn-lost-in-transaction.laravel.persistent.json)

### `MG-02.held` on laravel (managed)

1. **What the API reported:** applied: Migrator::run() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.laravel.managed.json](cases/MG-02.held.laravel.managed.json)

### `MG-02.session-loss` on laravel (managed)

1. **What the API reported:** failed: Migrator::run() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.laravel.managed.json](cases/MG-02.session-loss.laravel.managed.json)

### `MG-02.idle-session-timeout` on laravel (managed)

1. **What the API reported:** applied: Migrator::run() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.laravel.managed.json](cases/MG-02.idle-session-timeout.laravel.managed.json)

### `MG-03.no-reversal` on laravel (managed)

1. **What the API reported:** reverted: Migrator::rollback() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.laravel.managed.json](cases/MG-03.no-reversal.laravel.managed.json)

### `TX-01A.caught-error-then-commit` on pdo-control (unsafe)

1. **What the API reported:** committed: PDO::commit() returned true after a caught statement error. The return value is not a command tag. The unsafe policy reports committed..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 5304 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pdo-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pdo-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pdo-control (unsafe)

1. **What the API reported:** rolled_back: PDO::commit() threw, which the unsafe policy reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 5352 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 5352). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json)

### `TX-03.rollback-not-sent` on pdo-control (unsafe)

1. **What the API reported:** failed: the body threw and PDO::rollBack() threw. The handle was kept.. The next unit of work: committed, after 77 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 5379 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 5379 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 5379), `next` yes (inserted by xid 5379). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12; mode `unsafe` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pdo-control.unsafe.json](cases/TX-03.rollback-not-sent.pdo-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pdo-control (unsafe)

1. **What the API reported:** failed: the body threw and PDO::rollBack() threw. The handle was kept.. The next unit of work: rolled_back, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 5421 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12; mode `unsafe` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pdo-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pdo-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pdo-control (unsafe)

1. **What the API reported:** failed: the body threw and PDO::rollBack() threw. The handle was kept.. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 5463 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12; mode `unsafe` (configured); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pdo-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pdo-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 5550 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 5599 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 5599). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 5623 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 5623). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 5650 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 5650), `inner` yes (inserted by xid 5651). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 5680 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 39 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 5740 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 5740 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 5740), `next` yes (inserted by xid 5740). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 5767 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 5794 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 5821 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 5878 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 5878). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 5902 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 5902). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
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

- `TX-01B.commit-reply-unseen` on laravel (managed): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on laravel (explicit): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01A.caught-error-then-commit` on pdo-control (correct): **PASS (mechanism not exercised)**. after the API returned, the session was "idle", and its last statement was "ROLLBACK"

## Inconclusive, unsupported and not run

- `TX-01B.commit-reply-discarded` on laravel (managed): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on laravel (managed): **UNSUPPORTED (not applicable by design)**. Laravel has no propagation mode that commits an inner transaction while an outer transaction stays open. A nested Connection::transaction() or beginTransaction() is a SAVEPOINT on the same PDO and the same transaction. Eloquent create sends the insert when it is called, so there are no deferred outer writes for an inner transaction to commit. The hazard TX-04.3 targets cannot arise.
- `TX-01B.commit-reply-discarded` on pdo-control (correct): **NOT_RUN**. the adapter does not implement this case
- `TX-02.savepoint-rollback-not-sent` on pdo-control (correct): **UNSUPPORTED**. PDO has no savepoint or nested-transaction API. PDO::beginTransaction, commit, and rollBack are the transaction API. Issuing SAVEPOINT SQL from this control would be application SQL, not a PDO nested transaction.
- `TX-02.savepoint-rollback-rejected` on pdo-control (correct): **UNSUPPORTED**. PDO has no savepoint or nested-transaction API. PDO::beginTransaction, commit, and rollBack are the transaction API. Issuing SAVEPOINT SQL from this control would be application SQL, not a PDO nested transaction.
- `TX-02.conn-lost-before-savepoint-rollback` on pdo-control (correct): **UNSUPPORTED**. PDO has no savepoint or nested-transaction API. PDO::beginTransaction, commit, and rollBack are the transaction API. Issuing SAVEPOINT SQL from this control would be application SQL, not a PDO nested transaction.
- `TX-04.nested-failure-contained` on pdo-control (correct): **UNSUPPORTED**. PDO has no nested-transaction or savepoint API. A nested scope cannot be started through PDO.
- `TX-04.nested-released-outer-rollback` on pdo-control (correct): **UNSUPPORTED**. PDO has no nested-transaction or savepoint API. A nested scope cannot be started through PDO.
- `TX-04.independent-inner` on pdo-control (correct): **UNSUPPORTED (not applicable by design)**. PDO has no propagation mode and no API that commits an inner transaction while an outer transaction stays open. There are no deferred writes. The hazard TX-04.3 targets cannot arise through PDO's transaction API.
- `TX-05.managed-serializable` on pdo-control (correct): **UNSUPPORTED**. PDO::beginTransaction() takes no isolation level. The Pdo\Pgsql::TRANSACTION_* constants are deprecated in PHP 8.5 and have no effect. There is no PDO method that requests SERIALIZABLE. Sending SET TRANSACTION from this control would be PostgreSQL SQL, not a PDO API.
- `TX-05.explicit-serializable` on pdo-control (correct): **UNSUPPORTED**. PDO has no transaction handle distinct from the PDO object, and PDO::beginTransaction() takes no isolation level. The same absence as the managed case.
- `MG-02.held` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.first-deployment` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.session-loss` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.idle-session-timeout` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-03.valid-reversal` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.no-reversal` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.failing-reversal` on pdo-control (correct): **UNSUPPORTED**. PDO has no migration runner or reversible migration history. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| laravel (managed) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| laravel (explicit) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| laravel (persistent) | configured | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| pdo-control (correct) | native | pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12 | `aa269b57d3ed…` |
| pdo-control (unsafe) | configured | pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12 | `aa269b57d3ed…` |
| pdo-control (persistent) | configured | pdo_pgsql 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.6, php 8.5.12 | `aa269b57d3ed…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |

