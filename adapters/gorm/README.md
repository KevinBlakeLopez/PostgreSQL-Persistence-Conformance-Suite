# GORM

GORM v1.31.2 on `gorm.io/driver/postgres` v1.6.3 and pgx v5.11.0 through `database/sql`. Go 1.27.3. PostgreSQL 18.6.

`managed` calls `DB.Transaction`. `explicit` calls `DB.Begin`, `DB.Commit`, and `DB.Rollback`. A nested `DB.Transaction` is a savepoint. Explicit nested scopes use `SavePoint` and `RollbackTo`. The pool is `database/sql` with `MaxOpenConns` 1, passed in `postgres.Config.Conn`. It is not pgxpool. `logger.Discard` keeps GORM off the protocol stdout. `DisableNestedTransaction` stays false.

Build and run from the repository root:

```sh
node harness/run.mjs --adapter=gorm --repeat=3
```

`./run` is `go run -mod=readonly ./cmd/gorm` in `adapters/go`. The module README is [`../go/README.md`](../go/README.md).

## Recording

[`reports/examples/2026-10-22T13-24-28Z-606909`](../../reports/examples/2026-10-22T13-24-28Z-606909/summary.md). Three repetitions agreed. CTL-01 and `pg-control` held. The comparison is [`docs/go-persistence.md`](../../docs/go-persistence.md).

| Case | managed | explicit |
| --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised, `rolled_back` | PASS, same |
| `TX-01B.conn-lost-before-commit` | PASS, `failed` | PASS, `failed` |
| `TX-01B.commit-reply-discarded` | PASS, `failed`, TX-01B.2 held | PASS, same |
| `TX-01B.commit-reply-unseen` | PASS, `failed`, TX-01B.2 held | PASS, same |
| `TX-02.savepoint-rollback-not-sent` | FAIL | FAIL |
| `TX-02.savepoint-rollback-rejected` | PASS, `ErrTxCommitRollback` | PASS, same |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | PASS |
| `TX-03` all three | PASS | PASS |
| `TX-04` both savepoint cases | PASS | PASS |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | |
| `TX-05.managed-serializable` | PASS, `serializable` | |
| `TX-05.explicit-serializable` | | PASS, `serializable` |
| MG-02, MG-03 | UNSUPPORTED, capability absent | |

On TX-01A the callback or the explicit code catches `23505` and still commits. `DB.Transaction` and `DB.Commit().Error` are `pgx.ErrTxCommitRollback`. The tracer under GORM recorded command tag `ROLLBACK` for `commit`. The session was idle and its last statement was `commit`. The marker was absent.

On `TX-02.savepoint-rollback-not-sent` the outer callback returns nil, or explicit `Commit` is called. Both markers commit. Explicit `RollbackTo().Error` was nil. `steps.nested.driver_rollback_error` is the pgx tracer's error for the withheld `ROLLBACK TO SAVEPOINT`. Managed nested `DB.Transaction` returned the application error, not a rollback error.

On `TX-02.savepoint-rollback-rejected` the tracer recorded SQLSTATE `3B001` and the following commit tag was `ROLLBACK`. GORM's `RollbackTo().Error` was still nil. `Commit` returned `ErrTxCommitRollback`, so the case passes. [`repro-output.txt`](repro-output.txt) is the same split outside the harness. [`UPSTREAM.md`](UPSTREAM.md) is a draft. It was not filed.

`TX-03.rollback-not-sent` managed reports `rolled_back` because the callback returned an error. Explicit reports `failed` because `Rollback().Error` is the driver error. Both pass on a new backend. pgx closed the connection when its `Rollback` failed.
