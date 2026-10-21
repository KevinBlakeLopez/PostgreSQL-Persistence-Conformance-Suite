# Npgsql control results

Run [`reports/examples/2026-10-21T20-00-07Z-cff349`](../../reports/examples/2026-10-21T20-00-07Z-cff349/summary.md). PostgreSQL 18.6, image `postgres:18.6` digest `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. Npgsql 10.0.3, runtime 10.0.13, three repetitions, and they agreed. CTL-01 held for every mode. `pg-control` held its expectations. A FAIL is a counterexample to the PPCS invariant under those conditions. It is not, by itself, a defect claim.

The matrix below is this adapter and `pg-control`. The full grid, including EF Core, is in the run summary.

| Case | correct | unsafe | pooled | pooled-no-reset |
| --- | --- | --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised | FAIL, mechanism exercised | | |
| `TX-01B.conn-lost-before-commit` | PASS | PASS | | |
| `TX-01B.commit-reply-discarded` | NOT_RUN | | | |
| `TX-02.savepoint-rollback-not-sent` | PASS | FAIL | | |
| `TX-02.savepoint-rollback-rejected` | PASS | FAIL | | |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | PASS | | |
| `TX-03.rollback-not-sent` | PASS | FAIL | PASS | PASS |
| `TX-03.statement-error-rollback-not-sent` | PASS | PASS | PASS | PASS |
| `TX-03.conn-lost-in-transaction` | PASS | PASS | PASS | PASS |
| `TX-04.nested-failure-contained` | PASS | FAIL | | |
| `TX-04.nested-released-outer-rollback` | PASS | PASS | | |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | | | |
| `TX-05.managed-serializable`, `TX-05.explicit-serializable` | PASS | FAIL | | |
| `MG-02.*`, `MG-03.*` | UNSUPPORTED, capability absent | | | |

## TX-01A

Observation, from the case files and from `Probe` in this session. The probe is not a PPCS case.

After a caught `23505`, `SELECT 1` fails with `25P02`. `CommitAsync` then returns. It does not throw. An independent connection sees `pg_xact_status()` aborted and the marker absent. There is no public `TransactionStatus` property on `NpgsqlConnection` or `NpgsqlTransaction`. A direct `COMMIT` command also returns, with an update count of -1.

`correct` reports `rolled_back` because of the `25P02`, and says it did not read the command tag. The runner's mechanism check is true: after the API returned, the session was idle and its last statement was `COMMIT`. `unsafe` reports `committed` because `CommitAsync` returned. The marker is still absent. That is the FAIL.

## Pool

`pooled` and `pooled-no-reset` use the correct policy. On `TX-03.rollback-not-sent`, both PASS. For `pooled-no-reset` the case file records the same backend PID for both units and a new transaction id for the second unit. The doomed marker is absent. The adapter trace contains only the withheld `ROLLBACK`. The next unit did not run inside the failed transaction. `NoResetOnClose` did not, in this run, hand the open transaction to the next checkout.

## Not run

`TX-01B.commit-reply-discarded` is NOT_RUN. `CommitAsync` reads `CommandComplete` and `ReadyForQuery` before it returns. This adapter does not discard that reply.
