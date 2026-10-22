# SQLx adapter

SQLx 0.9.0's PostgreSQL driver against the suite's disposable PostgreSQL. The adapter is a Rust program. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit, and it does not use another Rust PostgreSQL driver.

`explicit` calls `Pool::begin`, `Transaction::commit`, and `Transaction::rollback`. `managed` calls `Connection::transaction`, which commits when the callback returns `Ok` and calls `rollback().await` when it returns `Err`. `direct` uses one `PgConnection` and the explicit calls. `drop` and `direct-drop` drop an open `Transaction` instead of calling `rollback()`. Drop queues `ROLLBACK` and does not wait. `sql` sends `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` because `begin` takes no isolation argument. That mode is application SQL, not a transaction-API option.

A nested `Transaction::begin` is `SAVEPOINT _sqlx_savepoint_N`. Compile-time query macros are not enabled. Features are `runtime-tokio` and `postgres`, with TLS off.

Category C faults are withheld or rewritten in this process, once, on a cleartext proxy in front of SQLx, before PostgreSQL receives the statement. The proxy also records `CommandComplete` tags. `TX-01B.commit-reply-discarded` is unsupported: `PgConnection::run` reads the reply before `commit` returns, and there is no hook between that parse and the `Result`.

The per-case report is [`FINDINGS.md`](FINDINGS.md). The recording is [`reports/examples/2026-10-22T18-40-05Z-7b77ec`](../../reports/examples/2026-10-22T18-40-05Z-7b77ec/summary.md). The draft in [`upstream-draft.md`](upstream-draft.md) is not filed.

## Setup

`pnpm run setup` builds this adapter only when `cargo` is already on `PATH`. Otherwise:

```sh
cargo build --locked --release
```

Rust 1.99.1. The lockfile pins SQLx 0.9.0, sqlx-postgres 0.9.0, sqlx-core 0.9.0, and Tokio 1.54.1.

The manifest command is `./run`, which executes `target/release/ppcs-sqlx` when that binary exists, and `target/debug/ppcs-sqlx` otherwise.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=sqlx --repeat=3
```

`TX-01B.commit-reply-discarded`, `TX-04.independent-inner`, and the migration cases are selected by a full adapter run and recorded as UNSUPPORTED. The controls that gate these cases, including `pg-control`, run in the same command.
