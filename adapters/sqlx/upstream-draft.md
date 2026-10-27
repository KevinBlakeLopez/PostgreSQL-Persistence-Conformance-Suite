# Not filed

SQLx 0.9.0 `Transaction::commit` returns `Ok` when PostgreSQL answers `COMMIT` with command tag `ROLLBACK`.

This file is a draft. It has not been posted. Production relevance (2026-10-26): [`unfiled findings`](../../research/unfiled-findings-production-relevance/README.md), sections "SQLx `Transaction::commit` returns `Ok`" and "SQLx `direct-drop`". Likelihood: low for both.

## Versions

- rustc 1.99.1 (58cf8f9c3 2026-10-13)
- cargo 1.99.1 (5f94df478 2026-08-27)
- sqlx 0.9.0, sqlx-postgres 0.9.0, sqlx-core 0.9.0
- Tokio 1.54.1
- Features: `runtime-tokio`, `postgres`. TLS features off. Query macros off.
- PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`

## What happened

A transaction inserted a row, then an insert of a duplicate unique key failed with SQLSTATE `23505`. The application caught that error and called `Transaction::commit`. PostgreSQL had already aborted the transaction. Its reply to `COMMIT` was command tag `ROLLBACK`, with no new error. The row was absent. `commit` returned `Ok`.

The same result was recorded for `Pool::begin` / `commit`, for `Connection::transaction` when the callback returns `Ok` after catching `23505`, and for one `PgConnection` with no pool. Three repetitions agreed on each. The runner's mechanism check was true: after the call returned, the session was idle and its last statement was `COMMIT`.

The adapter's proxy, which sits in front of SQLx and forwards the reply, logged `COMMIT -> ROLLBACK`. The tag reached the process. `Transaction::commit` still returned `Ok`.

## Expected

`commit` should not report success when PostgreSQL completed `COMMIT` with command tag `ROLLBACK`.

pgx v5.11.0, recorded in this repository on the same PostgreSQL 18.6, returns `ErrTxCommitRollback` for that tag. `database/sql` and GORM return that error. That comparison is `reports/examples/2026-10-22T13-24-28Z-606909`. It is a different driver. It shows that the tag is something a PostgreSQL client can observe.

## Actual

`Transaction::commit` returned `Ok`. `pg_xact_status` was `aborted`. The marker was not visible.

## Where SQLx handles it

`PgTransactionManager::commit` in sqlx-postgres 0.9.0 `src/transaction.rs` lines 40–48 executes `COMMIT` and returns `Ok` when `execute` returns `Ok`. It does not read the command tag.

`Transaction::commit` in sqlx-core 0.9.0 `src/transaction.rs` lines 120–125 returns `Ok` when that method returns `Ok`, and then clears the open flag.

`PgConnection::run` in sqlx-postgres 0.9.0 `src/connection/executor.rs` lines 314–322 decodes `CommandComplete` and keeps `rows_affected()` only. `CommandComplete::rows_affected` in `src/message/command_complete.rs` lines 26–31 parses a trailing integer. The tag `ROLLBACK` has none, so the value is 0. The tag string is not returned to `commit`.

This is one library. Protocol parsing and the transaction API are both SQLx. There is no separate driver whose public API hides the tag from a transaction wrapper.

## Minimal program

`examples/tx01a.rs` is that program. It uses the same dependency versions as the adapter. Point it at a disposable database only.

```sh
export DATABASE_URL='postgres://USER:PASSWORD@127.0.0.1:PORT/DATABASE?sslmode=disable'
cargo run --example tx01a --manifest-path adapters/sqlx/Cargo.toml
```

The fixture it expects is `create table uniq (id serial primary key, code text not null unique); insert into uniq (code) values ('taken');`.

The harness reproduction, which creates that fixture and checks PostgreSQL from another connection, is:

```sh
node harness/run.mjs --adapter=sqlx --mode=explicit --case=TX-01A.caught-error-then-commit --repeat=3
```

Evidence: `reports/examples/2026-10-22T18-40-05Z-7b77ec/cases/TX-01A.caught-error-then-commit.sqlx.explicit.json`. The managed and direct case files in that directory show the same `Ok` result.

## A separate observation, not this report

Dropping an open `Transaction` queues `ROLLBACK` and does not wait (`Transaction`'s `Drop`, sqlx-core `src/transaction.rs` lines 269–278; `PgTransactionManager::start_rollback`, sqlx-postgres `src/transaction.rs` lines 62–71). On a `PgPool`, `Floating::return_to_pool` calls `ping` before the connection can be checked out again (sqlx-core `src/pool/connection.rs` lines 307–314). `PgConnection::ping` writes `Sync` and waits until ready (sqlx-postgres `src/connection/mod.rs` lines 180–187), which flushes the queued statement.

On one `PgConnection`, with no pool, that flush does not run. In `direct-drop` `CTL-01.rollback`, the proxy recorded `BEGIN` and no `ROLLBACK`. At `after-end` the session was `idle in transaction` and `pg_xact_status` was `in progress`. After the connection closed, the transaction was aborted. That case failed CTL-01.2. It is recorded in the same run. It is not the commit-tag report above.
