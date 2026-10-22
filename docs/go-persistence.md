# Go persistence comparison

Recording: [`reports/examples/2026-10-22T13-24-28Z-606909`](../reports/examples/2026-10-22T13-24-28Z-606909/summary.md). PostgreSQL 18.6, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. Runner Node v24.14.1, PPCS 0.3.0. Every executed case ran three times on a fresh database, and the repetitions agreed. CTL-01 passed for every Go mode. `pg-control` held its case gate, including the expected `unsafe` FAILs. No Go result was gated.

This report compares three Go surfaces on the existing PPCS catalog. It does not change that catalog. There is no driver-capability schema in the harness. The capability table below is this study's classification of the calls this run made.

No upstream issue was filed.

## Executive summary

On the caught unique violation, native pgx, `database/sql` through pgx's stdlib driver, and GORM all report that the transaction rolled back. PostgreSQL answered `COMMIT` with command tag `ROLLBACK`. The session was idle afterward, and its last statement was `commit`. The marker was absent. The mechanism was exercised on all four executed modes: pgx `native`, `database/sql` `native`, GORM `managed`, and GORM `explicit`.

The error starts in pgx. `dbTx.Commit` in pgx v5.11.0 returns `ErrTxCommitRollback` when the command tag is `ROLLBACK`. pgx's `database/sql` wrapper returns that error from `driver.Tx.Commit`. `sql.Tx.Commit` returns it unchanged. GORM's `DB.Transaction` returns `tx.Commit().Error`, and explicit `DB.Commit().Error` is the same error. The layers above pgx did not turn that error back into success.

That is not the ending recorded for node-postgres, Knex, Kysely, Lucid, MikroORM 7.2.5, TypeORM, Drizzle, Prisma, SQLAlchemy Core, Spring JDBC, jOOQ, Laravel, Active Record, or EF Core's `execute-sql` path. Those reports treat a completed `COMMIT` as success. pgjdbc's `Connection.commit()` is void and returns while the driver state is `FAILED`. psycopg's `commit()` returns on command tag `ROLLBACK`. pgx is the driver in this set that fails `Commit` on that tag, and the Go abstractions above it kept the failure.

Go does not remove the other failure. When `ROLLBACK TO SAVEPOINT` is withheld and the outer scope still commits, all four Go modes report `committed`, PostgreSQL commits, and both the outer and the inner markers are visible. `TX-02.savepoint-rollback-not-sent` fails. pgx and `database/sql` return an error from the withheld statement. The case commits anyway. GORM's `RollbackTo` does not surface that error: `RollbackTo().Error` was nil while the pgx tracer recorded the failure. The later `Commit` still returned nil, because the transaction was still open. A withheld savepoint rollback followed by a normal commit is the same shape as Django, SQLAlchemy, and Prisma on this case.

`TX-03` passes on a new backend. pgx closes the connection when `dbTx.Rollback` returns an error. The next unit cannot reuse that session. This run does not separate that close from pgxpool's idle-transaction check or from `database/sql`'s `ResetSession` check. Those checks are in the source. The recorded connections were already closed.

## Adapter configurations

| Piece | Version | Role |
| --- | --- | --- |
| Go | 1.27.3 | The runtime recorded in every hello |
| pgx | v5.11.0 | Native transactions, and the driver under the other two |
| `gorm.io/gorm` | v1.31.2 | Managed `DB.Transaction` and explicit `Begin` / `Commit` / `Rollback` |
| `gorm.io/driver/postgres` | v1.6.3 | GORM's PostgreSQL dialector. Its own `go.mod` requires pgx v5.10.0. This module selects v5.11.0 for all three adapters |
| PostgreSQL | 18.6 | The disposable server |

GORM's dialector uses `github.com/jackc/pgx/v5/stdlib` unless `Config.Conn` is already set (`postgres.go`, `Initialize`). This adapter passes a `*sql.DB` opened with that stdlib driver, so the pool limit and the tracer sit under GORM. The DSN path in the same function also calls `stdlib.OpenDB`. The call chain in this run is:

```text
PostgreSQL
    |
    v
pgx v5.11.0
    |
    v
database/sql  (Go 1.27.3)
    |
    v
GORM v1.31.2
    |
    v
application
```

Native pgx stops at `pgx.Tx`. The `database/sql` control stops at `sql.Tx`, whose driver commit is `wrapTx.Commit`, which calls `pgx.Tx.Commit` (`stdlib/sql.go`). GORM's managed and explicit commits call that `sql.Tx`. The statement trace on every GORM TX-01A row contains `commit` with command tag `ROLLBACK`, recorded by the pgx tracer under GORM, and `db.Transaction` or `DB.Commit` returned `ErrTxCommitRollback`.

`go-pgx-control` `native` is one `*pgx.Conn`. It dials a replacement only after that connection is closed. `pooled` is `pgxpool.Pool` with `MaxConns` 1 and `MinConns` 0, and only for TX-03. `go-database-sql-control` is a `database/sql` pool with `MaxOpenConns` 1. GORM uses that same kind of pool. It is not pgxpool.

## Conformance results

The column for a mode is the harness classification. Detail is in the case JSON.

| Case | pgx native | pgx pooled | database/sql | GORM managed | GORM explicit |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised, `rolled_back` | — | PASS, mechanism exercised, `rolled_back` | PASS, mechanism exercised, `rolled_back` | PASS, mechanism exercised, `rolled_back` |
| `TX-01B.conn-lost-before-commit` | PASS, `failed` | — | PASS, `failed` | PASS, `failed` | PASS, `failed` |
| `TX-01B.commit-reply-discarded` | UNSUPPORTED | — | PASS, `failed`, TX-01B.2 held | PASS, `failed`, TX-01B.2 held | PASS, `failed`, TX-01B.2 held |
| `TX-01B.commit-reply-unseen` | PASS, `failed`, TX-01B.2 held | — | PASS, `failed`, TX-01B.2 held | PASS, `failed`, TX-01B.2 held | PASS, `failed`, TX-01B.2 held |
| `TX-02.savepoint-rollback-not-sent` | FAIL | — | FAIL | FAIL | FAIL |
| `TX-02.savepoint-rollback-rejected` | PASS | — | PASS | PASS | PASS |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | — | PASS | PASS | PASS |
| `TX-03.rollback-not-sent` | PASS | PASS | PASS | PASS | PASS |
| `TX-03.statement-error-rollback-not-sent` | PASS | PASS | PASS | PASS | PASS |
| `TX-03.conn-lost-in-transaction` | PASS | PASS | PASS | PASS | PASS |
| `TX-04.nested-failure-contained` | PASS | — | PASS | PASS | PASS |
| `TX-04.nested-released-outer-rollback` | PASS | — | PASS | PASS | PASS |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | — | UNSUPPORTED, not applicable by design | UNSUPPORTED, not applicable by design | — |
| `TX-05.managed-serializable` | UNSUPPORTED, capability absent | — | UNSUPPORTED, capability absent | PASS, `serializable` | — |
| `TX-05.explicit-serializable` | PASS, `serializable` | — | PASS, `serializable` | — | PASS, `serializable` |
| MG-02, MG-03 | UNSUPPORTED, capability absent | — | UNSUPPORTED, capability absent | UNSUPPORTED, capability absent | — |

`reported` on TX-01A is `rolled_back` because the error is `pgx.ErrTxCommitRollback`, whose text is `commit unexpectedly resulted in rollback`. A nil commit is `committed`. Any other commit or rollback error is `failed`. These adapters declare `result` as a rollback-claim channel, so TX-01B.2 is exercised. Reporting `failed` holds it. Reporting `rolled_back` would not.

GORM managed and explicit agreed on every case both modes ran, except the report value on `TX-03.rollback-not-sent`: managed reports `rolled_back` because the callback returned an error, and explicit reports `failed` because `DB.Rollback().Error` is the driver error. Both pass. The next unit's backend was not unit 1's.

## Driver capability comparison

| Capability | Native pgx | database/sql | GORM |
| --- | --- | --- | --- |
| PostgreSQL command-tag visibility | Tested. `dbTx.Commit` reads the tag. The tracer recorded `ROLLBACK` for `commit`. The API returns `ErrTxCommitRollback`, not the tag string. | Tested. `sql.Tx.Commit` has no tag field. It returned `ErrTxCommitRollback`. The tracer under the driver recorded `ROLLBACK`. | Tested. `DB.Commit().Error` and `DB.Transaction`'s return were `ErrTxCommitRollback`. GORM has no tag field. The tracer under GORM recorded `ROLLBACK`. GORM did not drop a tag the driver had turned into an error. |
| SQLSTATE preservation | Tested. The caught insert is `*pgconn.PgError` `23505`. | Tested. The same `23505` is on the error `sql.Tx` returns from `Exec`. | Tested. The caught insert is still `*pgconn.PgError` `23505`. `RollbackTo().Error` was nil on a statement whose tracer error carried `3B001`. That loss is below. |
| Transaction-state visibility | `PgConn().TxStatus()` exists. This adapter does not read it to decide `reported`. Commit uses the command tag. | No transaction-state method on `sql.Tx`. `stdlib.Conn.ResetSession` returns `driver.ErrBadConn` when `TxStatus` is not idle. This run's failed rollbacks had already closed the connection in pgx. | No transaction-state method on `gorm.DB`. The pool underneath is the `database/sql` pool. |
| Commit outcome detection | Tested. Tag `ROLLBACK` becomes `ErrTxCommitRollback`. Tag `COMMIT` is a nil error. | Tested. The pgx error is the `sql.Tx.Commit` error. | Tested. The pgx error is `Commit().Error` and the `Transaction` return value when the callback returned nil. |
| Unknown-outcome representation | Tested for connection loss and for the category E proxy. `Commit` returned an error (`57P01`, or `conn closed`). `reported` is `failed`, not `committed` and not `rolled_back`. Category D is unsupported: nothing under `Tx.Commit` can replace its return after the tag is parsed. | Tested, including category D. The wrapper discards a parsed nil commit and returns `fault.LostCommit`. `reported` is `failed`. The discarded result in the case file is `nil`, and the tracer tag is `COMMIT`. | Tested the same way as `database/sql`. `DB.Transaction` returned `LostCommit` after the callback returned nil. `reported` is `failed`. |
| Failed rollback detection | Tested. `Tx.Rollback` returns the error, then `dbTx.Rollback` calls `Conn.die`. A nested `Rollback` returns the error and does not close the connection. | Tested. `sql.Tx.Rollback` returned `driver: bad connection` for the cancelled-context injection. The tracer error was `context canceled`. | Split. Explicit `DB.Rollback().Error` was the driver error on the top-level TX-03 rollback. Explicit `RollbackTo().Error` was nil. Managed `DB.Transaction` returned the callback error and not the rollback error. |
| Unsafe connection invalidation | Tested. After the rollback error, the `*pgx.Conn` was closed. The next transaction dialed a new backend (`reconnected` true, `same_backend` false). | Tested. The next transaction's backend pid differed. pgx had closed the connection before `database/sql` checked it out again. | Tested. Same new backend, through the `database/sql` pool under GORM. |
| Connection reuse safety | Tested on one `*pgx.Conn` and on `pgxpool`. TX-03 passes. Unit 2 committed its own transaction. | Tested. TX-03 passes. | Tested. TX-03 passes. |

The category C injection is a cancelled context returned from `QueryTracer.TraceQueryStart`. pgx calls that hook before it sends. For a statement with no parameters, `pgconn.Exec` sees the cancelled context and returns before `SendQuery`. The fault report's withheld SQL, `fired: 1`, and the runner's `after-fault` signature are the evidence the statement did not reach the server. The error text `timeout: context already done: context canceled` is pgconn's wording for that cancelled context. It is not `statement_timeout`. `database/sql` then surfaces `driver.ErrBadConn` when pgx reports the context error as safe to retry.

## Confirmed false-success cases

TX-01A is not one. The API did not report a successful commit.

`TX-02.savepoint-rollback-not-sent` is one, on all four modes. The nested application error was caught. `ROLLBACK TO SAVEPOINT` was not sent. The outer scope then ended with `Commit`. The tracer's next tag was `COMMIT`, not `ROLLBACK`. Both markers were visible. The API reported `committed`.

pgx's nested `Rollback` returned `context canceled`. `database/sql`'s `Exec` of `ROLLBACK TO SAVEPOINT` returned `driver: bad connection`. Those errors are in `steps.nested.rollback_error`. The outer `Commit` was still called, and it returned nil. The driver reported the failed savepoint statement and then reported a successful commit of the transaction that still contained the inner row.

GORM explicit left `RollbackTo().Error` nil. `steps.nested.driver_rollback_error` is the tracer's `context canceled` string. GORM managed's nested `DB.Transaction` returned the callback's application error, not a rollback error. The outer callback returned nil, and `DB.Transaction` returned nil. The dialector's `RollbackTo` calls `Exec` and returns nil (`postgres.go`). `DB.RollbackTo` therefore `AddError(nil)`. Managed `DB.Transaction` also ignores the `*gorm.DB` that `RollbackTo` returns (`finisher_api.go`). The case committed because the outer callback returned nil, which is the same completion the other three modes used. The extra GORM fact is that the explicit API did not show the failure those other modes showed.

`TX-02.savepoint-rollback-rejected` is not a false success. The rewritten statement produced SQLSTATE `3B001`. The following `Commit` returned `ErrTxCommitRollback`, including through GORM, and the tag was `ROLLBACK`. A standalone program printed the same split for a missing savepoint name, without the harness fault: `RollbackTo().Error` was nil, `Commit().Error` was `ErrTxCommitRollback`, and the row count was 0. The output is [`adapters/gorm/repro-output.txt`](../adapters/gorm/repro-output.txt). That program is not a catalog case.

## Correctly handled cases

- A normal commit returns nil, the tag is `COMMIT`, and CTL-01.commit passes.
- An application error followed by `Rollback` leaves the marker absent. CTL-01.rollback passes. GORM managed maps the callback error to `rolled_back`. pgx and `database/sql` map a nil `Rollback` to `rolled_back`.
- TX-01A, as above. The tag check is in pgx. The upper layers return the error.
- A backend terminated before `COMMIT` makes `Commit` return `57P01`. `reported` is `failed`. The case passes TX-01B.1. The API does not claim a confirmed rollback.
- The category E proxy closes the socket before the reply is read. pgx's error text is `conn closed`. `reported` is `failed`. TX-01B.2 holds.
- Category D, on `database/sql` and GORM, discards a parsed commit whose tracer tag is `COMMIT` and whose discarded result is `nil`. The API error does not wrap `ErrTxCommitRollback`. `reported` is `failed`. TX-01B.2 holds.
- A nested failure that is rolled back to a real savepoint, then an outer commit, leaves the inner marker absent and the outer marker present. TX-04.1 passes. pgx nested `Begin` is `SAVEPOINT sp_N`. `database/sql` sends `SAVEPOINT` / `ROLLBACK TO` / `RELEASE` because it has no savepoint type. GORM managed uses nested `DB.Transaction`. GORM explicit uses `SavePoint`.
- A released or completed nested scope, then an outer rollback, leaves both markers absent. TX-04.2 passes.
- Requested `serializable` is `begin isolation level serializable`. `current_setting('transaction_isolation')` was `serializable`, and the runner saw an `SIReadLock` on `item`. pgx and `database/sql` only have the explicit form. GORM has both.
- TX-03 passes, including both client-side rollbacks and the server-side disconnect. Unit 2 committed a different transaction on a different backend.

## Unknown outcomes

| Situation | What the client received | What PostgreSQL did | Report |
| --- | --- | --- | --- |
| Backend terminated before `COMMIT` | `57P01` from `Commit` | Aborted | `failed` |
| Category E: reply dropped before read | `conn closed` | Committed, marker visible | `failed` |
| Category D: parsed `COMMIT` discarded | `fault.LostCommit`, discarded result `nil` | Committed | `failed` |
| Native pgx, category D | Not run | — | UNSUPPORTED |

None of these rows report `committed` or `rolled_back`. A connection error is not treated as proof of rollback. `ErrTxCommitRollback` is reserved for the command tag.

## Architectural interpretation

The TX-01A difference tracks the driver, and then whether the layer above it returns that driver's error.

pgx v5.11.0 fails `Commit` when the tag is `ROLLBACK`. node-postgres 8.23.1 resolves the query and leaves `command` as `ROLLBACK` for the caller. pgjdbc 42.7.14's `commit()` is void. psycopg 3.3.6's `commit()` returns on that tag. pdo_pgsql's `commit()` returned true in the Laravel recording. Frameworks whose commit is "the driver call returned" then report success: Knex, Kysely, Lucid, MikroORM 7.2.5, TypeORM, Drizzle, Prisma, SQLAlchemy Core, Spring, jOOQ, Laravel, Active Record, and EF Core `execute-sql`. GORM's commit is also "the driver call returned." On this stack the driver call does not return success, so GORM does not report success. That is preservation of pgx's result, not a separate GORM check of the command tag.

The TX-02 rejected-savepoint difference has the same shape. SQLAlchemy reports a commit after `3B001` because psycopg's `commit()` returns. GORM reports `rolled_back` after `3B001` because pgx's `Commit` does not return nil, even though GORM's `RollbackTo` itself returned nil. The ORM did not read the tag. The driver did.

The withheld-savepoint case does not follow that line. The transaction stays open, so a later `COMMIT` has tag `COMMIT`. Every Go mode that commits after that reports success and keeps the inner row. Django, SQLAlchemy, Prisma, jOOQ, and Laravel fail the same case. Passing it, as `pg-control` `correct` does, means not committing after the savepoint rollback fails. These Go adapters commit, because that is the case's normal ending. The pgx and `database/sql` errors would let a caller choose not to.

TX-03 follows the pool and the driver's rollback failure, not the ORM. pgx closes the connection when a top-level `Rollback` fails. The next unit gets a new backend. Prisma and Drizzle fail the withheld-rollback case by reusing the connection. Spring and jOOQ fail it when `setAutoCommit(true)` sends `COMMIT`. This run's Go pools did not do that. The measurement is the new backend and the committed `next` marker. It is not a measurement that pgxpool's `TxStatus != 'I'` check, by itself, discarded a still-open connection. `dbTx.Rollback` had already closed it.

Nothing here says Go's explicit style prevents application code from committing the wrong transaction. The withheld-savepoint FAIL is that application ending, on the driver and on GORM.

## Limitations

- Migrations are capability-absent. GORM AutoMigrate was not run.
- `TX-04.independent-inner` is not applicable. None of the three surfaces has a propagation mode that commits an inner transaction while an outer one stays open. A second connection was not used as a substitute.
- pgx and `database/sql` have no managed callback API. Their TX-05 managed case is capability-absent. The explicit case sends the isolation level.
- Native pgx does not implement category D. The tracer cannot change `Tx.Commit`'s return value after the tag is parsed.
- The category C fault is a cancelled context in the tracer, plus a cleartext rewrite of `ROLLBACK TO SAVEPOINT`. It is not a patch to pgx. `sslmode=disable` is required for the rewrite and for the harness proxy.
- GORM was not run with `PreferSimpleProtocol`, `DisableNestedTransaction`, or `SkipDefaultTransaction` changed. Defaults were left in place except `logger.Discard`, so the logger cannot write on the protocol stdout, and `Config.Conn`, so the pool and the tracer are the ones under test.
- The GORM driver module requires pgx v5.10.0. The adapter module pins v5.11.0 for the native driver, the stdlib driver, and GORM together. A run on v5.10.0 was not done.
- pgxpool's non-idle destroy and `ResetSession`'s non-idle `ErrBadConn` were not isolated from `Conn.die`.
- Deadlock, serialization failure, and statement timeout were not separate cases.
- No search of GORM's issue tracker was done before writing the draft. The draft says that.

## Build and run

Go 1.27.3. From the repository root, with the disposable server up:

```sh
export PATH="$HOME/sdk/go1.27.3/bin:$PATH"   # if go is not already on PATH
(cd adapters/go && go test ./...)
node harness/run.mjs --adapter=go-pgx-control,go-database-sql-control,gorm --repeat=3
```

Each adapter command is `./run`, which executes `go run -mod=readonly` in `adapters/go`. `pnpm run setup` downloads the module when `go` is on `PATH` and does not require Go to install the JavaScript adapters.

The GORM savepoint repro, against the disposable server only:

```sh
(cd adapters/go && go run -mod=readonly ./cmd/gorm-rollback-repro ../../.ppcs-instance.json)
```
