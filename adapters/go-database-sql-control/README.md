# database/sql control

Go 1.27.3 `database/sql` on pgx v5.11.0 `stdlib`. No GORM. PostgreSQL 18.6.

The pool is `database/sql` with `MaxOpenConns` 1. `sql.Tx.Commit` returns the error from `driver.Tx.Commit`. pgx `wrapTx.Commit` calls `pgx.Tx.Commit` (`stdlib/sql.go`). A nil error is `committed`. `pgx.ErrTxCommitRollback` is `rolled_back`. Any other error is `failed`. Nested transactions are `SAVEPOINT`, `ROLLBACK TO SAVEPOINT`, and `RELEASE SAVEPOINT`. `database/sql` has no savepoint type.

Category D discards the parsed commit inside a `driver.Tx` wrapper, after `pgx.Tx.Commit` returns and before `sql.Tx.Commit` returns.

```sh
node harness/run.mjs --adapter=go-database-sql-control --repeat=3
```

The module README is [`../go/README.md`](../go/README.md). The comparison is [`docs/go-persistence.md`](../../docs/go-persistence.md).

## Recording

[`reports/examples/2026-10-22T13-24-28Z-606909`](../../reports/examples/2026-10-22T13-24-28Z-606909/summary.md). Three repetitions agreed. CTL-01 and `pg-control` held.

| Case | native |
| --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised. `sql.Tx.Commit` returned `ErrTxCommitRollback`. Tracer tag `ROLLBACK`. |
| `TX-01B.conn-lost-before-commit` | PASS, `failed` |
| `TX-01B.commit-reply-discarded` | PASS, `failed`. Discarded result `nil`, tracer tag `COMMIT`. TX-01B.2 held. |
| `TX-01B.commit-reply-unseen` | PASS, `failed`. TX-01B.2 held. |
| `TX-02.savepoint-rollback-not-sent` | FAIL. `ROLLBACK TO` returned `driver: bad connection`. The outer `Commit` returned nil, tag `COMMIT`, and both markers are visible. |
| `TX-02.savepoint-rollback-rejected` | PASS. The rewritten statement returned `3B001`. `Commit` returned `ErrTxCommitRollback`. |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS |
| `TX-03` all three | PASS. The next unit's backend was not unit 1's. |
| `TX-04` both savepoint cases | PASS |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design |
| `TX-05.managed-serializable` | UNSUPPORTED, capability absent |
| `TX-05.explicit-serializable` | PASS, `serializable` |
| MG-02, MG-03 | UNSUPPORTED, capability absent |

The `driver: bad connection` text is `driver.ErrBadConn`. pgx reported the cancelled-context injection as safe to retry, and `database/sql` surfaces that as a bad connection. The tracer error for the withheld statement is `context canceled`. The statement was not sent.
