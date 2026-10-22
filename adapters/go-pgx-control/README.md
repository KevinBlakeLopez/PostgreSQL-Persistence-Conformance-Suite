# Native pgx control

pgx v5.11.0. Go 1.27.3. No `database/sql` and no GORM. PostgreSQL 18.6.

`native` is one `*pgx.Conn`. `pooled` is `pgxpool.Pool` with `MaxConns` 1 and `MinConns` 0, for TX-03. Nested `Tx.Begin` is a savepoint. `Tx.Commit` returning nil is `committed`. `pgx.ErrTxCommitRollback` is `rolled_back`. Any other error is `failed`.

```sh
node harness/run.mjs --adapter=go-pgx-control --repeat=3
```

The module README is [`../go/README.md`](../go/README.md). The comparison is [`docs/go-persistence.md`](../../docs/go-persistence.md).

## Recording

[`reports/examples/2026-10-22T13-24-28Z-606909`](../../reports/examples/2026-10-22T13-24-28Z-606909/summary.md). Three repetitions agreed. CTL-01 and `pg-control` held.

| Case | native | pooled |
| --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised. `Commit` returned `ErrTxCommitRollback`. Tracer tag `ROLLBACK`. | |
| `TX-01B.conn-lost-before-commit` | PASS, `failed` (`57P01`) | |
| `TX-01B.commit-reply-discarded` | UNSUPPORTED. `Tx.Commit` is the API under test, and the tracer cannot replace its return after the tag is parsed. | |
| `TX-01B.commit-reply-unseen` | PASS, `failed` (`conn closed`). TX-01B.2 held. | |
| `TX-02.savepoint-rollback-not-sent` | FAIL. Nested `Rollback` returned an error. The outer `Commit` returned nil, tag `COMMIT`, and both markers are visible. | |
| `TX-02.savepoint-rollback-rejected` | PASS. Nested `Rollback` returned `3B001`. Outer `Commit` returned `ErrTxCommitRollback`. | |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | |
| `TX-03` all three | PASS. After a failed `Rollback`, pgx closed the connection and the next unit dialed a new backend. | PASS. `same_backend` false. |
| `TX-04` both savepoint cases | PASS | |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | |
| `TX-05.managed-serializable` | UNSUPPORTED, capability absent | |
| `TX-05.explicit-serializable` | PASS. `begin isolation level serializable`. | |
| MG-02, MG-03 | UNSUPPORTED, capability absent | |

`dbTx.Commit` (`tx.go`) returns `ErrTxCommitRollback` when `commandTag.String()` is `ROLLBACK`. `dbTx.Rollback` calls `Conn.die` on any error. A nested rollback does not.
