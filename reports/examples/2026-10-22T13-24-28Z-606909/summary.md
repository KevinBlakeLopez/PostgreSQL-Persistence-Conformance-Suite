# PPCS run 2026-10-22T13-24-28Z-606909

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `46420e946083…`
- **Runner:** PPCS 0.3.0, harness sha256 `ece507a7bb9f…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-22T13:24:28.632Z; duration 171 s
- **Counts:** PASS 88, FAIL 22, UNSUPPORTED 27 (3 not applicable by design, outside coverage)

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | go-database-sql-control (native) | go-pgx-control (native) | go-pgx-control (pooled) | gorm (managed) | gorm (explicit) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.go-database-sql-control.native.json) | [PASS](cases/CTL-01.commit.go-pgx-control.native.json) | [PASS](cases/CTL-01.commit.go-pgx-control.pooled.json) | [PASS](cases/CTL-01.commit.gorm.managed.json) | [PASS](cases/CTL-01.commit.gorm.explicit.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.go-database-sql-control.native.json) | [PASS](cases/CTL-01.rollback.go-pgx-control.native.json) | [PASS](cases/CTL-01.rollback.go-pgx-control.pooled.json) | [PASS](cases/CTL-01.rollback.gorm.managed.json) | [PASS](cases/CTL-01.rollback.gorm.explicit.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [PASS](cases/TX-01A.caught-error-then-commit.go-database-sql-control.native.json) | [PASS](cases/TX-01A.caught-error-then-commit.go-pgx-control.native.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.gorm.managed.json) | [PASS](cases/TX-01A.caught-error-then-commit.gorm.explicit.json) | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.go-database-sql-control.native.json) | [PASS](cases/TX-01B.conn-lost-before-commit.go-pgx-control.native.json) | — | [PASS](cases/TX-01B.conn-lost-before-commit.gorm.managed.json) | [PASS](cases/TX-01B.conn-lost-before-commit.gorm.explicit.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [PASS](cases/TX-01B.commit-reply-discarded.go-database-sql-control.native.json) | [UNSUPPORTED](cases/TX-01B.commit-reply-discarded.go-pgx-control.native.json) | — | [PASS](cases/TX-01B.commit-reply-discarded.gorm.managed.json) | [PASS](cases/TX-01B.commit-reply-discarded.gorm.explicit.json) | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS](cases/TX-01B.commit-reply-unseen.go-database-sql-control.native.json) | [PASS](cases/TX-01B.commit-reply-unseen.go-pgx-control.native.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.gorm.managed.json) | [PASS](cases/TX-01B.commit-reply-unseen.gorm.explicit.json) | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.go-database-sql-control.native.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.go-pgx-control.native.json) | — | [FAIL](cases/TX-02.savepoint-rollback-not-sent.gorm.managed.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.gorm.explicit.json) | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [PASS](cases/TX-02.savepoint-rollback-rejected.go-database-sql-control.native.json) | [PASS](cases/TX-02.savepoint-rollback-rejected.go-pgx-control.native.json) | — | [PASS](cases/TX-02.savepoint-rollback-rejected.gorm.managed.json) | [PASS](cases/TX-02.savepoint-rollback-rejected.gorm.explicit.json) | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.go-database-sql-control.native.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.go-pgx-control.native.json) | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.gorm.managed.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.gorm.explicit.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.rollback-not-sent.go-database-sql-control.native.json) | [PASS](cases/TX-03.rollback-not-sent.go-pgx-control.native.json) | [PASS](cases/TX-03.rollback-not-sent.go-pgx-control.pooled.json) | [PASS](cases/TX-03.rollback-not-sent.gorm.managed.json) | [PASS](cases/TX-03.rollback-not-sent.gorm.explicit.json) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | [PASS](cases/TX-03.statement-error-rollback-not-sent.go-database-sql-control.native.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.go-pgx-control.native.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.go-pgx-control.pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.gorm.managed.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.gorm.explicit.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | [PASS](cases/TX-03.conn-lost-in-transaction.go-database-sql-control.native.json) | [PASS](cases/TX-03.conn-lost-in-transaction.go-pgx-control.native.json) | [PASS](cases/TX-03.conn-lost-in-transaction.go-pgx-control.pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.gorm.managed.json) | [PASS](cases/TX-03.conn-lost-in-transaction.gorm.explicit.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.go-database-sql-control.native.json) | [PASS](cases/TX-04.nested-failure-contained.go-pgx-control.native.json) | — | [PASS](cases/TX-04.nested-failure-contained.gorm.managed.json) | [PASS](cases/TX-04.nested-failure-contained.gorm.explicit.json) | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.go-database-sql-control.native.json) | [PASS](cases/TX-04.nested-released-outer-rollback.go-pgx-control.native.json) | — | [PASS](cases/TX-04.nested-released-outer-rollback.gorm.managed.json) | [PASS](cases/TX-04.nested-released-outer-rollback.gorm.explicit.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.go-database-sql-control.native.json) | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.go-pgx-control.native.json) | — | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.gorm.managed.json) | — | — | — |
| `TX-05.managed-serializable` | none | [UNSUPPORTED](cases/TX-05.managed-serializable.go-database-sql-control.native.json) | [UNSUPPORTED](cases/TX-05.managed-serializable.go-pgx-control.native.json) | — | [PASS](cases/TX-05.managed-serializable.gorm.managed.json) | — | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) |
| `TX-05.explicit-serializable` | none | [PASS](cases/TX-05.explicit-serializable.go-database-sql-control.native.json) | [PASS](cases/TX-05.explicit-serializable.go-pgx-control.native.json) | — | — | [PASS](cases/TX-05.explicit-serializable.gorm.explicit.json) | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) |
| `MG-02.held` | none | [UNSUPPORTED](cases/MG-02.held.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-02.held.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-02.held.gorm.managed.json) | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) |
| `MG-02.first-deployment` | none | [UNSUPPORTED](cases/MG-02.first-deployment.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-02.first-deployment.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-02.first-deployment.gorm.managed.json) | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) |
| `MG-02.session-loss` | B (server-side termination) | [UNSUPPORTED](cases/MG-02.session-loss.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-02.session-loss.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-02.session-loss.gorm.managed.json) | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) |
| `MG-02.idle-session-timeout` | none | [UNSUPPORTED](cases/MG-02.idle-session-timeout.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-02.idle-session-timeout.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-02.idle-session-timeout.gorm.managed.json) | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) |
| `MG-03.valid-reversal` | none | [UNSUPPORTED](cases/MG-03.valid-reversal.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-03.valid-reversal.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-03.valid-reversal.gorm.managed.json) | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) |
| `MG-03.no-reversal` | none | [UNSUPPORTED](cases/MG-03.no-reversal.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-03.no-reversal.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-03.no-reversal.gorm.managed.json) | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) |
| `MG-03.failing-reversal` | none | [UNSUPPORTED](cases/MG-03.failing-reversal.go-database-sql-control.native.json) | [UNSUPPORTED](cases/MG-03.failing-reversal.go-pgx-control.native.json) | — | [UNSUPPORTED](cases/MG-03.failing-reversal.gorm.managed.json) | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- go-database-sql-control (native): held
- go-pgx-control (native): held
- go-pgx-control (pooled): held
- gorm (managed): held
- gorm (explicit): held
- pg-control (correct): held
- pg-control (unsafe): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01A.caught-error-then-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.conn-lost-before-commit`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-01B.commit-reply-discarded`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-01B.commit-reply-unseen`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.savepoint-rollback-rejected`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-02.conn-lost-before-savepoint-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-03.rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.statement-error-rollback-not-sent`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-03.conn-lost-in-transaction`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-failure-contained`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-04.nested-released-outer-rollback`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected PASS, got PASS)
- `TX-05.explicit-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-05.managed-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-02.savepoint-rollback-not-sent` on go-database-sql-control (native)

1. **What the API reported:** committed: sql.Tx.Commit returned nil.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 35634 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 35634), `inner` yes (inserted by xid 35635). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: Go database/sql Tx.Commit returns the error from driver.Tx.Commit and does not add a command tag (database/sql/sql.go). pgx stdlib v5.11.0 wrapTx.Commit calls pgx.Tx.Commit and returns that error (stdlib/sql.go). A nil error is database/sql's report that the transaction committed. pgx.ErrTxCommitRollback therefore reaches the caller as a non-nil error. stdlib Conn.ResetSession returns driver.ErrBadConn when pgx's transaction status is not idle, so the pool discards that connection before the next checkout. database/sql has no savepoint type. This control sends SAVEPOINT, ROLLBACK TO SAVEPOINT, and RELEASE SAVEPOINT as SQL.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** [object Object]
- **Conditions:** database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, github.com/jackc/pgx/v5/stdlib v5.11.0, go go1.27.3; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=go-database-sql-control --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.go-database-sql-control.native.json](cases/TX-02.savepoint-rollback-not-sent.go-database-sql-control.native.json)

### `TX-02.savepoint-rollback-not-sent` on go-pgx-control (native)

1. **What the API reported:** committed: pgx.Tx.Commit returned nil.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 35851 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 35851), `inner` yes (inserted by xid 35852). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: pgx v5.11.0 Tx.Commit (tx.go, dbTx.Commit) executes COMMIT and returns ErrTxCommitRollback when the command tag is ROLLBACK. The Tx interface documents that a commit which fails with a rollback status returns an error where errors.Is(ErrTxCommitRollback) is true. ErrTxCommitRollback's comment says PostgreSQL accepts COMMIT on an aborted transaction and treats it as ROLLBACK. A nil error is pgx's report that the transaction committed. dbTx.Rollback executes ROLLBACK and, on any error, calls Conn.die, which closes the connection. A nested Tx.Begin is a savepoint. Nested Rollback executes ROLLBACK TO SAVEPOINT and does not close the connection.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** [object Object]
- **Conditions:** github.com/jackc/pgx/v5 v5.11.0, github.com/jackc/pgx/v5 v5.11.0, go go1.27.3; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=go-pgx-control --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.go-pgx-control.native.json](cases/TX-02.savepoint-rollback-not-sent.go-pgx-control.native.json)

### `TX-02.savepoint-rollback-not-sent` on gorm (managed)

1. **What the API reported:** committed: db.Transaction returned nil.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 36173 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 36173), `inner` yes (inserted by xid 36174). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: GORM v1.31.2 DB.Transaction (finisher_api.go) commits when the callback returns nil and returns tx.Commit().Error. Its comment says: return error will rollback, otherwise to commit. A nil return is GORM's report that the transaction committed. A non-nil return is not a successful commit. gorm.io/driver/postgres v1.6.3 opens the pool with pgx stdlib (postgres.go Initialize) unless Config.Conn is set. This adapter passes a *sql.DB opened on pgx stdlib, which is the supported Config.Conn path, so the pool limits and the tracer sit under GORM. A nested DB.Transaction is a savepoint when DisableNestedTransaction is false, which is the default. The postgres dialector's SavePoint and RollbackTo call Exec and return nil, ignoring the *gorm.DB that Exec returns.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** [object Object]
- **Conditions:** gorm.io/gorm v1.31.2, database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, gorm.io/driver/postgres v1.6.3, go go1.27.3; mode `managed` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=gorm --mode=managed --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.gorm.managed.json](cases/TX-02.savepoint-rollback-not-sent.gorm.managed.json)

### `TX-02.savepoint-rollback-not-sent` on gorm (explicit)

1. **What the API reported:** committed: gorm.DB.Commit returned nil.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 36188 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 36188), `inner` yes (inserted by xid 36189). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: GORM v1.31.2 DB.Begin starts a transaction and DB.Commit calls the underlying Tx.Commit and stores its error (finisher_api.go). A nil DB.Error after Commit is GORM's report that the transaction committed. gorm.io/driver/postgres v1.6.3 uses pgx stdlib. This adapter passes *sql.DB through Config.Conn. SavePoint and RollbackTo are the explicit savepoint API. The postgres dialector executes the SQL and returns nil from SavePoint and RollbackTo.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** [object Object]
- **Conditions:** gorm.io/gorm v1.31.2, database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, gorm.io/driver/postgres v1.6.3, go go1.27.3; mode `explicit` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=gorm --mode=explicit --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.gorm.explicit.json](cases/TX-02.savepoint-rollback-not-sent.gorm.explicit.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 36499 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 36547 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 36547). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 36571 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 36571). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 36598 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 36598), `inner` yes (inserted by xid 36599). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 36628 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 40 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 36689 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 36689 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 36689), `next` yes (inserted by xid 36689). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 36716 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 36743 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 36770 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 36827 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 36827). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 36851 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 36851). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
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

## Inconclusive, unsupported and not run

- `TX-04.independent-inner` on go-database-sql-control (native): **UNSUPPORTED (not applicable by design)**. database/sql has no propagation mode and no API that commits an inner transaction while an outer transaction stays open. A SAVEPOINT stays on the same connection and the same transaction. This adapter does not open a second connection and call it an independent transaction.
- `TX-05.managed-serializable` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no managed callback API that commits when a callback returns. BeginTx and Commit are explicit. sql.TxOptions.Isolation is passed to BeginTx in the explicit case.
- `MG-02.held` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.first-deployment` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.session-loss` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.idle-session-timeout` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-03.valid-reversal` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.no-reversal` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.failing-reversal` on go-database-sql-control (native): **UNSUPPORTED**. database/sql has no migration runner or reversible migration history. This adapter does not add one.
- `TX-01B.commit-reply-discarded` on go-pgx-control (native): **UNSUPPORTED**. The API under test is pgx.Tx.Commit. pgx v5.11.0 parses the command tag inside dbTx.Commit and returns ErrTxCommitRollback when the tag is ROLLBACK. QueryTracer.TraceQueryEnd runs inside Conn.Exec, before Commit chooses its return value, and cannot replace that return value. There is no supported hook between the parsed tag and Tx.Commit's return. The category E case, TX-01B.commit-reply-unseen, is the wire loss this adapter can run. This is not a claim that pgx reports the tag correctly.
- `TX-04.independent-inner` on go-pgx-control (native): **UNSUPPORTED (not applicable by design)**. pgx has no propagation mode and no API that commits an inner transaction while an outer transaction stays open. Tx.Begin on an open transaction is a savepoint. This adapter does not open a second connection and call it an independent transaction.
- `TX-05.managed-serializable` on go-pgx-control (native): **UNSUPPORTED**. pgx has no managed callback API that commits when a callback returns. BeginTx and Commit are explicit. TxOptions.IsoLevel is passed to BeginTx in the explicit case.
- `MG-02.held` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.first-deployment` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.session-loss` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.idle-session-timeout` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-03.valid-reversal` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.no-reversal` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.failing-reversal` on go-pgx-control (native): **UNSUPPORTED**. pgx has no migration runner or reversible migration history. This adapter does not add one.
- `TX-04.independent-inner` on gorm (managed): **UNSUPPORTED (not applicable by design)**. GORM has no propagation mode that commits an inner transaction while an outer transaction stays open. A nested DB.Transaction or SavePoint is a SAVEPOINT on the same connection. DisableNestedTransaction false is the default and still uses a savepoint. This adapter does not open a second *sql.DB and call it an independent transaction.
- `MG-02.held` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate or a migration history. GORM has no multi-process advisory-lock migration protocol in the transaction API under test. This adapter does not add one.
- `MG-02.first-deployment` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate or a migration history. GORM has no multi-process advisory-lock migration protocol in the transaction API under test. This adapter does not add one.
- `MG-02.session-loss` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate or a migration history. GORM has no multi-process advisory-lock migration protocol in the transaction API under test. This adapter does not add one.
- `MG-02.idle-session-timeout` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate or a migration history. GORM has no multi-process advisory-lock migration protocol in the transaction API under test. This adapter does not add one.
- `MG-03.valid-reversal` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate. There is no reversible migration history under test. This adapter does not add one.
- `MG-03.no-reversal` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate. There is no reversible migration history under test. This adapter does not add one.
- `MG-03.failing-reversal` on gorm (managed): **UNSUPPORTED**. This adapter does not use GORM's AutoMigrate. There is no reversible migration history under test. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| go-database-sql-control (native) | native | database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, github.com/jackc/pgx/v5/stdlib v5.11.0, go go1.27.3 | `03a2ce8aa41c…` |
| go-pgx-control (native) | native | github.com/jackc/pgx/v5 v5.11.0, github.com/jackc/pgx/v5 v5.11.0, go go1.27.3 | `eeaedf188fe2…` |
| go-pgx-control (pooled) | configured | github.com/jackc/pgx/v5 v5.11.0, github.com/jackc/pgx/v5 v5.11.0, go go1.27.3 | `eeaedf188fe2…` |
| gorm (managed) | native | gorm.io/gorm v1.31.2, database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, gorm.io/driver/postgres v1.6.3, go go1.27.3 | `39051de8a3ec…` |
| gorm (explicit) | native | gorm.io/gorm v1.31.2, database/sql go1.27.3, github.com/jackc/pgx/v5 v5.11.0, gorm.io/driver/postgres v1.6.3, go go1.27.3 | `39051de8a3ec…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |

