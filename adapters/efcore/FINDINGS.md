# EF Core results

Run [`reports/examples/2026-10-21T20-00-07Z-cff349`](../../reports/examples/2026-10-21T20-00-07Z-cff349/summary.md). PostgreSQL 18.6, the same image digest as the Npgsql control. EF Core 10.0.13, Npgsql EF Core provider 10.0.3, Npgsql 10.0.3, runtime 10.0.13. Three repetitions agreed. CTL-01 held for `native`, `execute-sql`, and `pooled`. `pg-control` held its expectations.

A FAIL is a counterexample to the PPCS invariant. It is not, by itself, a claim that EF Core has a defect.

| Case | native | execute-sql | pooled |
| --- | --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | INCONCLUSIVE | FAIL | |
| `TX-01B.conn-lost-before-commit` | PASS | | |
| `TX-01B.commit-reply-discarded` | NOT_RUN | | |
| `TX-02.savepoint-rollback-not-sent` | FAIL | | |
| `TX-02.savepoint-rollback-rejected` | FAIL | | |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | | |
| `TX-03.rollback-not-sent` | | | PASS |
| `TX-03.statement-error-rollback-not-sent` | | | PASS |
| `TX-03.conn-lost-in-transaction` | | | PASS |
| `TX-04.nested-failure-contained` | PASS | | |
| `TX-04.nested-released-outer-rollback` | PASS | | |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | | |
| `TX-05.managed-serializable` | UNSUPPORTED, capability absent | | |
| `TX-05.explicit-serializable` | PASS | | |
| `MG-02.held`, `MG-02.session-loss`, `MG-02.idle-session-timeout` | PASS | | |
| `MG-02.first-deployment` | PASS | | |
| `MG-03.valid-reversal`, `MG-03.no-reversal`, `MG-03.failing-reversal` | PASS | | |

## TX-01A

`native` catches `SaveChangesAsync` of a duplicate `Uniq` (`DbUpdateException`, SQLSTATE `23505`) and then calls `CommitAsync`. At `before-end` the session was `idle in transaction`, and `pg_xact_status()` was `in progress`. After commit the captured transaction was `committed` and the marker was visible. `CommitAsync` returned. The transaction-committed interceptor ran once. The rolled-back interceptor did not. The case precondition, an aborted transaction before the end, did not hold, so the result is INCONCLUSIVE. The COMMIT-answered-ROLLBACK path did not run.

`execute-sql` sends the duplicate with `Database.ExecuteSqlAsync`. The session is then in a failed transaction block. `CommitAsync` returns, the interceptor records a commit, and the harness sees the transaction aborted and the marker absent. The API reported `committed`. That is the FAIL. At `after-end` the backend had already gone, so the runner's mechanism flag is null. It does not say the last statement was `COMMIT`. The Npgsql control, which keeps the connection, records last statement `COMMIT` for the same driver call.

The separate probe, not a PPCS case, counted EF's savepoint callbacks. On the `SaveChanges` path: 3 created, 2 rolled back to a savepoint. The command log did not contain the text `SAVEPOINT`. After the failed `SaveChanges` the session still accepted a query, the earlier marker committed, and the failed entity was still `Added`. A later `SaveChanges` failed again with `23505` and its new row did not commit. On the `ExecuteSql` path the violation left the session at `25P02`, `CommitAsync` returned, and the earlier marker was absent. The provider's public options builder had no method whose name contained `Savepoint` or `Transaction`.

## TX-02

Both category C cases FAIL. The application catches the nested error and calls `CommitAsync`, which is the case's "end normally" step. EF does not roll the outer transaction back when `RollbackToSavepointAsync` throws.

`savepoint-rollback-not-sent`: the withheld rollback never reached PostgreSQL. `CommitAsync` returned. The outer and the inner markers are both visible. The failed scope's write committed.

`savepoint-rollback-rejected`: PostgreSQL rejected the rewritten `ROLLBACK TO SAVEPOINT`. `CommitAsync` returned and was reported as `committed`. The transaction fate is aborted and neither marker is visible.

The connection-loss case PASS: `CommitAsync` threw, reported `failed`.

## Pool and nesting

Pooled TX-03 PASS, including the statement-error case. That case uses `ExecuteSql` for the violation so the top-level transaction aborts. `SaveChanges` would have rolled the violation back to its own savepoint and left the transaction open, which is not the aborted block the case checks. On `rollback-not-sent` the two units shared a backend PID and used different transaction ids. The doomed marker stayed invisible.

TX-04 PASS. A failed `CreateSavepoint` scope does not keep its writes. A released savepoint's writes disappear when the outer transaction rolls back. `BeginTransactionAsync` is not an independent nested transaction. That case is unsupported.

`TX-05.explicit-serializable` PASS. PostgreSQL reported `serializable`, and the runner saw an `SIReadLock` on `item`. There is no managed callback API that takes an isolation level. That case is unsupported.

## Migrations

`Database.MigrateAsync` on one compiled migration. The adapter reports `applied` only when EF logs `Applying migration`. `MG-02.held` PASS: one runner applied, the others reported `nothing_to_do`, marker count 1, history count 1. `MG-02.first-deployment` PASS on the same counts, in version 1.0 and in version 1.1 ([`reports/examples/2026-10-24T14-38-34Z-142777`](../../reports/examples/2026-10-24T14-38-34Z-142777/summary.md)), where both runners were waiting on a lock when the runner released its creation of the history table. `MG-02.session-loss` and `MG-02.idle-session-timeout` PASS. The idle-timeout case opens one extra idle connection, because the migration connection is inside a transaction and `idle_session_timeout` does not end it. `MG-03` PASS: a valid reversal removes the marker and the history row, a missing reversal is reported `refused` and leaves both, and a reversal that raises after the delete reports `failed` and leaves both.

An earlier draft of this adapter treated a history-count increase as "applied". Two runners could both report `applied` when only one had logged the migration. That measurement was wrong. The run above uses the log line.
