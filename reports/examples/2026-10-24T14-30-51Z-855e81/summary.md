# PPCS run 2026-10-24T14-30-51Z-855e81

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `2d44447a84ed…`
- **Runner:** PPCS 0.3.0, harness sha256 `ca9a464603c5…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-24T14:30:51.307Z; duration 210 s
- **Counts:** PASS 82, FAIL 29, UNSUPPORTED 10 (2 not applicable by design, outside coverage), INCONCLUSIVE 1, NOT_RUN 2

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | efcore (native) | efcore (execute-sql) | efcore (pooled) | npgsql-control (correct) | npgsql-control (unsafe) | npgsql-control (pooled) | npgsql-control (pooled-no-reset) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.efcore.native.json) | [PASS](cases/CTL-01.commit.efcore.execute-sql.json) | [PASS](cases/CTL-01.commit.efcore.pooled.json) | [PASS](cases/CTL-01.commit.npgsql-control.correct.json) | [PASS](cases/CTL-01.commit.npgsql-control.unsafe.json) | [PASS](cases/CTL-01.commit.npgsql-control.pooled.json) | [PASS](cases/CTL-01.commit.npgsql-control.pooled-no-reset.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.efcore.native.json) | [PASS](cases/CTL-01.rollback.efcore.execute-sql.json) | [PASS](cases/CTL-01.rollback.efcore.pooled.json) | [PASS](cases/CTL-01.rollback.npgsql-control.correct.json) | [PASS](cases/CTL-01.rollback.npgsql-control.unsafe.json) | [PASS](cases/CTL-01.rollback.npgsql-control.pooled.json) | [PASS](cases/CTL-01.rollback.npgsql-control.pooled-no-reset.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `TX-01A.caught-error-then-commit` | A (PostgreSQL error) | [INCONCLUSIVE](cases/TX-01A.caught-error-then-commit.efcore.native.json) | [FAIL](cases/TX-01A.caught-error-then-commit.efcore.execute-sql.json) | — | [PASS](cases/TX-01A.caught-error-then-commit.npgsql-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-01A.caught-error-then-commit.pg-control.correct.json) | [FAIL](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json) |
| `TX-01B.conn-lost-before-commit` | B (server-side termination) | [PASS](cases/TX-01B.conn-lost-before-commit.efcore.native.json) | — | — | [PASS](cases/TX-01B.conn-lost-before-commit.npgsql-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.correct.json) | [PASS](cases/TX-01B.conn-lost-before-commit.pg-control.unsafe.json) |
| `TX-01B.commit-reply-discarded` | D (client-side simulation) | [NOT_RUN](cases/TX-01B.commit-reply-discarded.efcore.native.json) | — | — | [NOT_RUN](cases/TX-01B.commit-reply-discarded.npgsql-control.correct.json) | — | — | — | [PASS](cases/TX-01B.commit-reply-discarded.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.efcore.native.json) | — | — | [PASS](cases/TX-01B.commit-reply-unseen.npgsql-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-not-sent` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.efcore.native.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.npgsql-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json) |
| `TX-02.savepoint-rollback-rejected` | C (client-side injection) | [FAIL](cases/TX-02.savepoint-rollback-rejected.efcore.native.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-rejected.npgsql-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-02.savepoint-rollback-rejected.pg-control.correct.json) | [FAIL](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json) |
| `TX-02.conn-lost-before-savepoint-rollback` | B (server-side termination) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.efcore.native.json) | — | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.npgsql-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.correct.json) | [PASS](cases/TX-02.conn-lost-before-savepoint-rollback.pg-control.unsafe.json) |
| `TX-03.rollback-not-sent` | C (client-side injection) | — | — | [PASS](cases/TX-03.rollback-not-sent.efcore.pooled.json) | [PASS](cases/TX-03.rollback-not-sent.npgsql-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.npgsql-control.unsafe.json) | [PASS](cases/TX-03.rollback-not-sent.npgsql-control.pooled.json) | [PASS](cases/TX-03.rollback-not-sent.npgsql-control.pooled-no-reset.json) | [PASS](cases/TX-03.rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.statement-error-rollback-not-sent` | C (client-side injection) | — | — | [PASS](cases/TX-03.statement-error-rollback-not-sent.efcore.pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.npgsql-control.correct.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.npgsql-control.unsafe.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.npgsql-control.pooled.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.npgsql-control.pooled-no-reset.json) | [PASS](cases/TX-03.statement-error-rollback-not-sent.pg-control.correct.json) | [FAIL](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json) |
| `TX-03.conn-lost-in-transaction` | B (server-side termination) | — | — | [PASS](cases/TX-03.conn-lost-in-transaction.efcore.pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.npgsql-control.correct.json) | [PASS](cases/TX-03.conn-lost-in-transaction.npgsql-control.unsafe.json) | [PASS](cases/TX-03.conn-lost-in-transaction.npgsql-control.pooled.json) | [PASS](cases/TX-03.conn-lost-in-transaction.npgsql-control.pooled-no-reset.json) | [PASS](cases/TX-03.conn-lost-in-transaction.pg-control.correct.json) | [FAIL](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json) |
| `TX-04.nested-failure-contained` | none | [PASS](cases/TX-04.nested-failure-contained.efcore.native.json) | — | — | [PASS](cases/TX-04.nested-failure-contained.npgsql-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-04.nested-failure-contained.pg-control.correct.json) | [FAIL](cases/TX-04.nested-failure-contained.pg-control.unsafe.json) |
| `TX-04.nested-released-outer-rollback` | none | [PASS](cases/TX-04.nested-released-outer-rollback.efcore.native.json) | — | — | [PASS](cases/TX-04.nested-released-outer-rollback.npgsql-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.correct.json) | [PASS](cases/TX-04.nested-released-outer-rollback.pg-control.unsafe.json) |
| `TX-04.independent-inner` | none | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.efcore.native.json) | — | — | [UNSUPPORTED (not applicable by design)](cases/TX-04.independent-inner.npgsql-control.correct.json) | — | — | — | — | — |
| `TX-05.managed-serializable` | none | [UNSUPPORTED](cases/TX-05.managed-serializable.efcore.native.json) | — | — | [PASS](cases/TX-05.managed-serializable.npgsql-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-05.managed-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.managed-serializable.pg-control.unsafe.json) |
| `TX-05.explicit-serializable` | none | [PASS](cases/TX-05.explicit-serializable.efcore.native.json) | — | — | [PASS](cases/TX-05.explicit-serializable.npgsql-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-05.explicit-serializable.pg-control.correct.json) | [FAIL](cases/TX-05.explicit-serializable.pg-control.unsafe.json) |
| `MG-02.held` | none | [PASS](cases/MG-02.held.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-02.held.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-02.first-deployment.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) |
| `MG-02.session-loss` | B (server-side termination) | [PASS](cases/MG-02.session-loss.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-02.session-loss.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) |
| `MG-02.idle-session-timeout` | none | [PASS](cases/MG-02.idle-session-timeout.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-02.idle-session-timeout.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-03.valid-reversal.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) |
| `MG-03.no-reversal` | none | [PASS](cases/MG-03.no-reversal.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-03.no-reversal.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.efcore.native.json) | — | — | [UNSUPPORTED](cases/MG-03.failing-reversal.npgsql-control.correct.json) | — | — | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- efcore (native): held
- efcore (execute-sql): held
- efcore (pooled): held
- npgsql-control (correct): held
- npgsql-control (unsafe): held
- npgsql-control (pooled): held
- npgsql-control (pooled-no-reset): held
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
- `TX-05.explicit-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.held`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.first-deployment`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.session-loss`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.idle-session-timeout`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.valid-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.no-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.failing-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `TX-05.managed-serializable`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01A.caught-error-then-commit` on efcore (execute-sql)

1. **What the API reported:** committed: IDbContextTransaction.CommitAsync returned.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 7504 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: EF Core 10 IDbContextTransaction.CommitAsync commits the transaction begun by Database.BeginTransactionAsync. The EF Core transaction API does not return a PostgreSQL command tag. A return from CommitAsync is reported as committed. A throw from CommitAsync is reported as failed. A throw from the body followed by RollbackAsync returning is reported as rolled_back. A throw from RollbackAsync is reported as failed. Marker inserts use Database.ExecuteSqlAsync. SaveChangesAsync inside an explicit transaction inserts the row under a savepoint and releases it; the row xmin is then that subtransaction, while pg_current_xact_id() is the top-level id, and the harness does not attribute that xmin to a top-level write. The native TX-01A violation is still SaveChangesAsync of a Uniq entity. The execute-sql mode uses ExecuteSqlAsync for that violation. A nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. EF Core creates its own savepoint around SaveChangesAsync when a user transaction is already active and the transaction reports SupportsSavepoints. This adapter does not disable that savepoint and does not read Npgsql protocol messages.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** The marker is SaveChangesAsync. The unique violation is Database.ExecuteSqlAsync inside the same BeginTransactionAsync. CommitAsync is unchanged.
- **Conditions:** Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `execute-sql` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=efcore --mode=execute-sql --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.efcore.execute-sql.json](cases/TX-01A.caught-error-then-commit.efcore.execute-sql.json)

### `TX-02.savepoint-rollback-not-sent` on efcore (native)

1. **What the API reported:** committed: IDbContextTransaction.CommitAsync returned.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 7540 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 7540), `inner` yes (inserted by xid 7541). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` no such session.
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: EF Core 10 IDbContextTransaction.CommitAsync commits the transaction begun by Database.BeginTransactionAsync. The EF Core transaction API does not return a PostgreSQL command tag. A return from CommitAsync is reported as committed. A throw from CommitAsync is reported as failed. A throw from the body followed by RollbackAsync returning is reported as rolled_back. A throw from RollbackAsync is reported as failed. Marker inserts use Database.ExecuteSqlAsync. SaveChangesAsync inside an explicit transaction inserts the row under a savepoint and releases it; the row xmin is then that subtransaction, while pg_current_xact_id() is the top-level id, and the harness does not attribute that xmin to a top-level write. The native TX-01A violation is still SaveChangesAsync of a Uniq entity. The execute-sql mode uses ExecuteSqlAsync for that violation. A nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. EF Core creates its own savepoint around SaveChangesAsync when a user transaction is already active and the transaction reports SupportsSavepoints. This adapter does not disable that savepoint and does not read Npgsql protocol messages.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** The outer transaction is BeginTransactionAsync. The nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. A second BeginTransactionAsync is not used.
- **Conditions:** Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=efcore --mode=native --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.efcore.native.json](cases/TX-02.savepoint-rollback-not-sent.efcore.native.json)

### `TX-02.savepoint-rollback-rejected` on efcore (native)

1. **What the API reported:** committed: IDbContextTransaction.CommitAsync returned.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 7555 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` no such session.
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: EF Core 10 IDbContextTransaction.CommitAsync commits the transaction begun by Database.BeginTransactionAsync. The EF Core transaction API does not return a PostgreSQL command tag. A return from CommitAsync is reported as committed. A throw from CommitAsync is reported as failed. A throw from the body followed by RollbackAsync returning is reported as rolled_back. A throw from RollbackAsync is reported as failed. Marker inserts use Database.ExecuteSqlAsync. SaveChangesAsync inside an explicit transaction inserts the row under a savepoint and releases it; the row xmin is then that subtransaction, while pg_current_xact_id() is the top-level id, and the harness does not attribute that xmin to a top-level write. The native TX-01A violation is still SaveChangesAsync of a Uniq entity. The execute-sql mode uses ExecuteSqlAsync for that violation. A nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. EF Core creates its own savepoint around SaveChangesAsync when a user transaction is already active and the transaction reports SupportsSavepoints. This adapter does not disable that savepoint and does not read Npgsql protocol messages.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** The outer transaction is BeginTransactionAsync. The nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. A second BeginTransactionAsync is not used.
- **Conditions:** Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `native` (native); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=efcore --mode=native --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.efcore.native.json](cases/TX-02.savepoint-rollback-rejected.efcore.native.json)

### `TX-01A.caught-error-then-commit` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 7968 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Form:** NpgsqlConnection.BeginTransactionAsync, parameterized commands, then CommitAsync or RollbackAsync. One connection is held until the case's after-end checkpoint, unless the policy disposed it.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.npgsql-control.unsafe.json](cases/TX-01A.caught-error-then-commit.npgsql-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on npgsql-control (unsafe)

1. **What the API reported:** rolled_back: CommitAsync threw, which the unsafe policy reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 8016 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8016). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Form:** NpgsqlConnection.BeginTransactionAsync, parameterized commands, then CommitAsync or RollbackAsync. One connection is held until the case's after-end checkpoint, unless the policy disposed it.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json](cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. A savepoint rollback had failed and was ignored. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8043 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 8043), `inner` yes (inserted by xid 8044). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Form:** The outer transaction is BeginTransactionAsync. The nested scope is SaveAsync, RollbackAsync(name), and ReleaseAsync on that NpgsqlTransaction. There is no second connection.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.npgsql-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.npgsql-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. A savepoint rollback had failed and was ignored. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8073 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Form:** The outer transaction is BeginTransactionAsync. The nested scope is SaveAsync, RollbackAsync(name), and ReleaseAsync on that NpgsqlTransaction. There is no second connection.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.npgsql-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.npgsql-control.unsafe.json)

### `TX-03.rollback-not-sent` on npgsql-control (unsafe)

1. **What the API reported:** failed: the body threw and RollbackAsync threw. CommitAsync then returned and the connection was kept.. The next unit of work: committed, after 34 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 8134 committed at report time (`after-unit1`); transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 8135 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 8134), `next` yes (inserted by xid 8135). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Form:** The next unit receives the same connection when the policy kept it, or a new checkout when the policy disposed it. pooled uses NpgsqlDataSource with MaxPoolSize 1. It is not a framework pool.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.npgsql-control.unsafe.json](cases/TX-03.rollback-not-sent.npgsql-control.unsafe.json)

### `TX-04.nested-failure-contained` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 8314 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** none
- **Form:** The outer transaction is BeginTransactionAsync. The nested scope is SaveAsync, RollbackAsync(name), and ReleaseAsync on that NpgsqlTransaction. There is no second connection.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.npgsql-control.unsafe.json](cases/TX-04.nested-failure-contained.npgsql-control.unsafe.json)

### `TX-05.managed-serializable` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8371 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8371). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** none
- **Form:** The policy runs the work and calls CommitAsync when the work returns. Npgsql has no managed-transaction type separate from NpgsqlTransaction.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.npgsql-control.unsafe.json](cases/TX-05.managed-serializable.npgsql-control.unsafe.json)

### `TX-05.explicit-serializable` on npgsql-control (unsafe)

1. **What the API reported:** committed: CommitAsync returned. The unsafe policy does not read a command tag and does not probe the session..
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8395 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8395). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** none
- **Form:** The same BeginTransactionAsync(IsolationLevel) and CommitAsync calls as the managed case. The handle is the NpgsqlTransaction the begin call returns.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-05.explicit-serializable`
- **Evidence:** [cases/TX-05.explicit-serializable.npgsql-control.unsafe.json](cases/TX-05.explicit-serializable.npgsql-control.unsafe.json)

### `TX-01A.caught-error-then-commit` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-write`): xid 8468 rolled back at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` no. Session state (pg_stat_activity, supplementary): at `after-write` "idle in transaction", at `before-end` "idle in transaction (aborted)".
3. **What the application could know:** The outcome reaches the client: PostgreSQL's reply to COMMIT carries the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-01A.1 violated: When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category A (PostgreSQL error). A unique_violation raised by PostgreSQL inside the transaction, and caught by the application.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01A.caught-error-then-commit`
- **Evidence:** [cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json](cases/TX-01A.caught-error-then-commit.pg-control.unsafe.json)

### `TX-01B.commit-reply-discarded` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 8516 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8516). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was discarded before the framework saw it. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category D (client-side simulation). A client-side simulation inside the adapter's driver layer (node-postgres, pg.Client.prototype.query): COMMIT is sent and completes on the server; the client then closes its own connection, and the caller receives a connection error instead of the reply. It is not a network failure. Artifact: the driver has already parsed PostgreSQL's reply (its transaction status reads idle) before the simulated loss, where a real loss leaves it reading in-transaction. The case therefore establishes only whether the API claims an outcome after its COMMIT call fails, not behaviour that depends on the driver's state, such as pool recovery.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-discarded`
- **Evidence:** [cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json](cases/TX-01B.commit-reply-discarded.pg-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 8540 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8540). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8567 committed at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` yes (inserted by xid 8567), `inner` yes (inserted by xid 8568). Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-outer` "idle".
3. **What the application could know:** The framework knows that its savepoint rollback failed, so it knows that the nested scope's writes may still be in the transaction. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): ROLLBACK TO SAVEPOINT fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-not-sent`
- **Evidence:** [cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-not-sent.pg-control.unsafe.json)

### `TX-02.savepoint-rollback-rejected` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag ROLLBACK).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `outer-after-write`): xid 8597 rolled back at report time (`after-outer`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `outer-after-write` "idle in transaction", at `inner-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-outer` "idle".
3. **What the application could know:** The framework receives PostgreSQL's error (3B001) for the savepoint rollback. If it then sends COMMIT without recovering, it receives the command tag ROLLBACK. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag ROLLBACK.
4. **Contract:** TX-02.1 violated: If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer: ROLLBACK TO SAVEPOINT is rewritten before it is sent, to name a savepoint that does not exist. PostgreSQL rejects it with 3B001, which aborts the current subtransaction (the savepoint's). The error is PostgreSQL's; the trigger is artificial.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-02.savepoint-rollback-rejected`
- **Evidence:** [cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json](cases/TX-02.savepoint-rollback-rejected.pg-control.unsafe.json)

### `TX-03.rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: committed, after 30 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): open at report time (`after-unit1`: xid 8657 in progress); committed by later work in the case, before teardown, so decided after the API returned, not by the reported operation; transaction `unit2` (its ID read inside it at `unit2-after-write`): xid 8657 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `doomed` yes (inserted by xid 8657), `next` yes (inserted by xid 8657). Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction", at `after-unit1` "idle in transaction", at `unit2-after-write` "idle in transaction".
3. **What the application could know:** The framework knows that its ROLLBACK failed, so it knows that the connection's transaction state is unknown. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-03.1 violated: Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.rollback-not-sent`
- **Evidence:** [cases/TX-03.rollback-not-sent.pg-control.unsafe.json](cases/TX-03.rollback-not-sent.pg-control.unsafe.json)

### `TX-03.statement-error-rollback-not-sent` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 1 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 8684 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-fault` "idle in transaction (aborted)", at `after-unit1` "idle in transaction (aborted)".
3. **What the application could know:** The framework received PostgreSQL's error for the failed statement, and knows that its ROLLBACK failed, so it knows that the connection is still inside a transaction block.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category C (client-side injection). A unique_violation raised by PostgreSQL inside unit 1, which aborts its transaction, then a client-side injection in the adapter's driver layer (node-postgres, pg.Client.prototype.query): the top-level ROLLBACK fails without being sent, as a failed send would.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.statement-error-rollback-not-sent`
- **Evidence:** [cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json](cases/TX-03.statement-error-rollback-not-sent.pg-control.unsafe.json)

### `TX-03.conn-lost-in-transaction` on pg-control (unsafe)

1. **What the API reported:** rolled_back: the body threw; ROLLBACK failed, and the connection was kept. The next unit of work: failed, after 0 ms.
2. **What PostgreSQL did:** transaction `unit1` (its ID read inside it at `unit1-after-write`): xid 8711 rolled back at report time (`after-unit1`); markers visible to a separate connection after the adapter exited: `doomed` no, `next` no. Session state (pg_stat_activity, supplementary): at `unit1-after-write` "idle in transaction", at `after-unit1` no such session.
3. **What the application could know:** The framework knows that its connection failed.
4. **Contract:** TX-03.2 violated: After the failure, the next unit of work on the same pool completes within the bound (settings.bound_ms) and commits. Framework contract: The unsafe control returns a connection whose ROLLBACK failed to its pool as it is, and reports a unit whose body threw as rolled back.

- **Fault:** category B (server-side termination). pg_terminate_backend(pid), run by the runner from its own connection.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"bound_ms":5000,"settle_ms":100}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-03.conn-lost-in-transaction`
- **Evidence:** [cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json](cases/TX-03.conn-lost-in-transaction.pg-control.unsafe.json)

### `TX-04.nested-failure-contained` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `inner-after-write`): xid 8738 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `outer` no, `inner` no. Session state (pg_stat_activity, supplementary): at `inner-after-write` "idle in transaction".
3. **What the application could know:** The caller knows that the nested scope failed: its error reached the caller. PostgreSQL answers the final COMMIT with COMMIT. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-04.1 violated: When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-04.nested-failure-contained`
- **Evidence:** [cases/TX-04.nested-failure-contained.pg-control.unsafe.json](cases/TX-04.nested-failure-contained.pg-control.unsafe.json)

### `TX-05.managed-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8795 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8795). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
3. **What the application could know:** A successful start does not tell the application which level PostgreSQL applied; only current_setting('transaction_isolation'), read inside the transaction, does. An application that requested SERIALIZABLE and got no error relies on its guarantee: concurrent transactions behave as if they had run one at a time. A rejected request reaches the application as an error, so it can decide what to do instead. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** TX-05.1 violated: On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1,"isolation_level":"serializable"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-05.managed-serializable`
- **Evidence:** [cases/TX-05.managed-serializable.pg-control.unsafe.json](cases/TX-05.managed-serializable.pg-control.unsafe.json)

### `TX-05.explicit-serializable` on pg-control (unsafe)

1. **What the API reported:** committed: COMMIT did not raise (command tag COMMIT).
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `after-read`): xid 8819 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 8819). Session state (pg_stat_activity, supplementary): at `after-read` "idle in transaction".
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

- `TX-01B.commit-reply-unseen` on efcore (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Inconclusive, unsupported and not run

- `TX-01A.caught-error-then-commit` on efcore (native): **INCONCLUSIVE**. precondition not established: the top-level transaction was aborted before it ended: at `before-end` the session was "idle in transaction (aborted)" and pg_xact_status() already reported it aborted (state: "idle in transaction"; pg_xact_status: in progress); PostgreSQL did not commit the transaction (pg_xact_status: committed; marker visible: true)
- `TX-01B.commit-reply-discarded` on efcore (native): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on efcore (native): **UNSUPPORTED (not applicable by design)**. EF Core has no propagation mode that promises an independent transaction while an outer transaction stays open. BeginTransactionAsync throws if a transaction is already in progress. A second DbContext is a second physical transaction coordinated by application code, not a framework propagation mode. This adapter does not manufacture that mode.
- `TX-05.managed-serializable` on efcore (native): **UNSUPPORTED**. EF Core has no managed transaction API that runs a callback and commits when the callback returns, and that accepts an isolation level. ExecutionStrategy.ExecuteAsync is a retry policy. AutoTransactionBehavior starts an implicit transaction around SaveChanges and does not take an isolation level. BeginTransactionAsync is the explicit API and is the other case.
- `TX-01B.commit-reply-discarded` on npgsql-control (correct): **NOT_RUN**. the adapter does not implement this case
- `TX-04.independent-inner` on npgsql-control (correct): **UNSUPPORTED (not applicable by design)**. Npgsql has no propagation mode and no API that commits an inner transaction while an outer transaction stays open. SaveAsync stays in the same transaction, so an inner transaction cannot commit writes the outer transaction has not committed.
- `MG-02.held` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.first-deployment` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.session-loss` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-02.idle-session-timeout` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner, migration history, or multi-process advisory-lock protocol. This adapter does not add one.
- `MG-03.valid-reversal` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.no-reversal` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner or reversible migration history. This adapter does not add one.
- `MG-03.failing-reversal` on npgsql-control (correct): **UNSUPPORTED**. Plain Npgsql has no migration runner or reversible migration history. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| efcore (native) | native | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| efcore (execute-sql) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| efcore (pooled) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| npgsql-control (correct) | native | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `0f9d99213019…` |
| npgsql-control (unsafe) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `0f9d99213019…` |
| npgsql-control (pooled) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `0f9d99213019…` |
| npgsql-control (pooled-no-reset) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `0f9d99213019…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |

