# Draft, not filed

GORM v1.31.2 and `gorm.io/driver/postgres` v1.6.3. pgx v5.11.0. Go 1.27.3. PostgreSQL 18.6.

Do not file this as part of ordinary repository work. No issue tracker search was done. If it is filed, search first, and do not also file pgx: `Tx.Commit` already returns `ErrTxCommitRollback` when the command tag is `ROLLBACK`.

## What the dialector returns

`Dialector.RollbackTo` and `Dialector.SavePoint` call `tx.Exec` and return nil. `DB.RollbackTo` then calls `AddError` with that nil. `AddError(nil)` does not change `DB.Error`.

`DB.Exec` returns `getInstance()`, which copies the DB when `clone > 0`. The statement error is on that copy. The dialector ignores the copy.

A program that does not use the harness, `adapters/go/cmd/gorm-rollback-repro`, printed this on the disposable server on 2026-10-22. It checked `cluster_name`, created `ppcs_gorm_rollback_repro`, and dropped that database. The log is [`repro-output.txt`](repro-output.txt).

```text
RollbackTo().Error == nil: true
Commit().Error: commit unexpectedly resulted in rollback
errors.Is(Commit().Error, pgx.ErrTxCommitRollback): true
rows visible after Commit: 0
```

`RollbackTo("no_such_savepoint")` did not report the failure. `Commit` did, because pgx reads the command tag. The row was not visible.

The catalog case `TX-02.savepoint-rollback-rejected` in `reports/examples/2026-10-22T13-24-28Z-606909` is the same split with a rewritten savepoint name. The tracer recorded SQLSTATE `3B001`. `RollbackTo().Error` was not set. `Commit().Error` was `ErrTxCommitRollback`.

## What managed Transaction returns

`DB.Transaction`, when it is already inside a transaction, calls `RollbackTo` from a defer and does not use that call's `*gorm.DB`. It returns the callback's error. An outer callback that catches the inner error and returns nil is committed.

`TX-02.savepoint-rollback-not-sent` is that ending. `ROLLBACK TO SAVEPOINT` was not sent. The tracer recorded `context canceled`. The outer `DB.Transaction` returned nil. Both markers were committed, and the commit tag was `COMMIT`. pgx and `database/sql` returned an error from that same withheld statement. Their outer `Commit` was still called, and it also returned nil. The GORM-specific observation is that `RollbackTo().Error` stayed nil.

Whether either observation is a defect is for the maintainers.
