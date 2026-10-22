# SQLx 0.9.0 on PostgreSQL 18.6

Recording: [`reports/examples/2026-10-22T18-40-05Z-7b77ec`](../../reports/examples/2026-10-22T18-40-05Z-7b77ec/summary.md). Three repetitions agreed. `pg-control` held its expectations. No SQLx result was inconclusive. `direct-drop` failed `CTL-01.rollback`, so that mode has no scenario results to gate. The other modes passed both controls.

Rust's ownership rules decide when a `Transaction` value is dropped. They do not decide what PostgreSQL does. On this run, `Transaction::commit` returned `Ok` when PostgreSQL answered `COMMIT` with command tag `ROLLBACK`. Dropping a transaction queued `ROLLBACK` and did not wait. A pool flushed that queue before the next checkout. A bare `PgConnection` did not.

## Configuration

| | |
| --- | --- |
| rustc | 1.99.1 (58cf8f9c3 2026-10-13) |
| cargo | 1.99.1 (5f94df478 2026-08-27) |
| sqlx / sqlx-postgres / sqlx-core | 0.9.0 |
| Tokio | 1.54.1 |
| Features | `runtime-tokio`, `postgres`. No TLS feature. No `macros` feature. |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg13+2) |
| Pool | `PgPool`, `max_connections` = `pool_max`, `min_connections` 0, `test_before_acquire` false. No `after_release` hook. |
| Direct | one `PgConnection` |

`sqlx::query` is the ordinary runtime API. Compile-time checking is not what `commit` does, and it was not enabled.

Modes:

- `explicit`: `Pool::begin`, `Transaction::commit`, `Transaction::rollback`.
- `managed`: `Connection::transaction`. `Ok` commits. `Err` calls `rollback().await`.
- `direct`: the explicit calls on one `PgConnection`.
- `drop`: commit calls `commit`. Rollback paths drop the `Transaction`.
- `direct-drop`: the same drop, with no pool. Only the controls run.
- `sql`: `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` as the first statement. `begin` takes no isolation argument.

A nested `Transaction::begin` is `SAVEPOINT _sqlx_savepoint_N`. Category C faults are a cleartext proxy in this process. It withholds or rewrites one statement before PostgreSQL sees it, and it records `CommandComplete` tags.

## Matrix

The column is the classification. `—` means that mode does not run the case.

| Case | explicit | managed | direct | drop | direct-drop | sql |
| --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | PASS | PASS | PASS | PASS | PASS | PASS |
| `CTL-01.rollback` | PASS | PASS | PASS | PASS | FAIL | PASS |
| `TX-01A.caught-error-then-commit` | FAIL | FAIL | FAIL | — | — | — |
| `TX-01B.conn-lost-before-commit` | PASS | PASS | PASS | — | — | — |
| `TX-01B.commit-reply-discarded` | UNSUPPORTED | — | — | — | — | — |
| `TX-01B.commit-reply-unseen` | PASS | PASS | PASS | — | — | — |
| `TX-02.savepoint-rollback-not-sent` | PASS | PASS | PASS | PASS | — | — |
| `TX-02.savepoint-rollback-rejected` | PASS | PASS | PASS | PASS | — | — |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | PASS | PASS | PASS | — | — |
| `TX-03.rollback-not-sent` | PASS | PASS | — | PASS | — | — |
| `TX-03.statement-error-rollback-not-sent` | PASS | PASS | — | PASS | — | — |
| `TX-03.conn-lost-in-transaction` | PASS | PASS | — | PASS | — | — |
| `TX-04.nested-failure-contained` | PASS | PASS | PASS | PASS | — | — |
| `TX-04.nested-released-outer-rollback` | PASS | PASS | PASS | PASS | — | — |
| `TX-04.independent-inner` | UNSUPPORTED | — | — | — | — | — |
| `TX-05.managed-serializable` | — | — | — | — | — | PASS |
| `TX-05.explicit-serializable` | — | — | — | — | — | PASS |
| MG-02, MG-03 | UNSUPPORTED | — | — | — | — | — |

`TX-01A` is mechanism exercised on all three modes that run it. `TX-01B.commit-reply-unseen` is PASS with TX-01B.2 not exercised. `TX-04.independent-inner` is not applicable by design. The migration cases are capability-absent. The `sql` TX-05 passes are `SET TRANSACTION`, not an argument of `begin`.

## Commit outcome

`PgTransactionManager::commit` (`sqlx-postgres` 0.9.0 `src/transaction.rs` lines 40–48) executes `COMMIT` and returns `Ok` when `execute` returns `Ok`. `Transaction::commit` (`sqlx-core` `src/transaction.rs` lines 120–125) returns that `Ok` and clears the open flag.

`PgConnection::run` (`src/connection/executor.rs` lines 314–322) decodes `CommandComplete` and keeps `rows_affected()` only. `CommandComplete::rows_affected` (`src/message/command_complete.rs` lines 26–31) parses a trailing integer. The tag `ROLLBACK` has none, so the stored value is 0. The tag string is not given to `commit`.

On `TX-01A`, explicit, managed, and direct: the caught error was SQLSTATE `23505`, the session at `before-end` was `idle in transaction (aborted)`, `commit` returned `Ok`, the proxy logged `COMMIT -> ROLLBACK`, the last statement was `COMMIT`, and the marker was absent. The pool was not required. `direct` did the same thing.

`TX-01B.conn-lost-before-commit` reported `failed`. The connection was gone before `COMMIT`. `TX-01B.commit-reply-unseen` also reported `failed`. The runner's proxy dropped the reply. The transaction had committed. TX-01B.2 was not exercised: this adapter lists no channel that would report a confirmed rollback. `commit`'s error is a connection error, not a rollback type.

`TX-01B.commit-reply-discarded` is unsupported. `run` consumes the reply before `commit` returns. There is no supported hook after that parse and before the `Result`.

## Explicit rollback and Drop

`Transaction::rollback` waits for `ROLLBACK` or `ROLLBACK TO SAVEPOINT`. If that call returns an error, `open` stays true, so `Drop` still runs. `Drop` (`sqlx-core` `src/transaction.rs` lines 269–278) calls `start_rollback`. That function (`sqlx-postgres` `src/transaction.rs` lines 62–71) queues a simple query and decrements the depth. It does not wait, and it cannot return an error to the caller.

The documentation says rollback is called on drop. The implementation starts it.

`Floating::return_to_pool` (`sqlx-core` `src/pool/connection.rs` lines 307–314) calls `ping` before a pooled connection can be checked out again. The comment there says the ping flushes queued rollbacks. `PgConnection::ping` (`sqlx-postgres` `src/connection/mod.rs` lines 180–187) writes `Sync` and waits until ready. It is not `SELECT 1`.

On a pool, `CTL-01.rollback` in `drop` passed: by `after-end` the transaction was aborted. The caller still had no `Result` from the queued statement. The pool's return path had flushed it before the runner's snapshot.

On one `PgConnection`, `direct-drop` `CTL-01.rollback` failed. The proxy recorded `BEGIN` and no `ROLLBACK`. At `after-end` the session was `idle in transaction` and `pg_xact_status` was `in progress`. After the process closed the connection, the transaction was aborted. Drop had queued the statement. Nothing flushed it. Disconnect aborted the transaction. That is not a completed `ROLLBACK`.

## Connection reuse

Category C withholds one `ROLLBACK` and reports `after-fault` before SQLx sees the error.

`TX-03.rollback-not-sent`, explicit and managed: the fault fired once. The trace then contains a second `ROLLBACK`, which was sent. `Transaction::rollback` returned an error (`reported` `failed`). `Drop` queued the second statement because `open` was still true. Unit 2 committed on a new transaction id. `same_backend` was true. The failed transaction was not the one unit 2 committed.

`TX-03.rollback-not-sent`, drop: the only `ROLLBACK` was the queued one, and it was withheld. `same_backend` was false. Unit 2 committed on a new backend. `ping` saw the injected error and the pool did not check that connection out again.

`TX-03.statement-error-rollback-not-sent` and `TX-03.conn-lost-in-transaction` passed on explicit, managed, and drop. The statement-error case caught `23505` before the withheld `ROLLBACK`. The connection-loss case is the runner's `pg_terminate_backend`, not the proxy.

A withheld rollback did not leave the next unit inside the failed transaction. On the explicit path the same backend was reused only after a second `ROLLBACK` was sent. On the drop path the withheld statement was the only one, and the next unit got a new backend. The direct connection, with no pool `ping`, did not send `ROLLBACK` at all.

## Savepoints, nesting, isolation

Both client-side savepoint cases passed on explicit, managed, direct, and drop. The outer commit was not a commit of the inner marker. The connection-loss savepoint case passed. A nested `Transaction::begin` is a savepoint. `TX-04.independent-inner` is unsupported: SQLx has no propagation mode that commits a second connection while the outer transaction stays open, and it does not defer writes.

`TX-04.nested-failure-contained` and `TX-04.nested-released-outer-rollback` passed. The released savepoint's writes disappeared with the outer rollback.

`TX-05` in mode `sql`: `current_setting('transaction_isolation')` was `serializable`, and the runner saw an `SIReadLock` on `item`. The statement was `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE`, sent after `BEGIN`. `Pool::begin` and `Connection::transaction` take no level. This is not a native isolation argument.

## Capability

SQLx parses the PostgreSQL protocol and manages the transaction in the same crate. There is no separate driver boundary.

| Capability | What the run and the 0.9.0 source show |
| --- | --- |
| Command-tag visibility | The proxy saw `ROLLBACK` for `COMMIT`. `CommandComplete` keeps `rows_affected` only. `commit` does not receive the tag. |
| SQLSTATE | `23505` was on the caught `sqlx::Error`. |
| Transaction-state visibility | Not a public commit result. `ping` and `ReadyForQuery` update the connection's status inside the driver. |
| Commit outcome | `Ok` means `execute` returned `Ok`. It does not mean the tag was `COMMIT`. |
| Unknown outcome | A lost reply or a dead connection makes `commit` return `Err`. That error is not a confirmed rollback. |
| Explicit rollback failure | `rollback` returns the error. `Drop` then queues another rollback. |
| Implicit rollback completion | Not returned to the caller. A pool flushes it in `ping`. A bare connection does not, until something else uses it. |
| Connection invalidation | A `ping` error on return closes the connection. The drop-mode TX-03 case got a new backend. |
| Pool reset | No adapter `after_release`. The built-in return path is `ping`. |
| Savepoint failure | `rollback` of a savepoint returns the error. The outer `commit` is a separate call. Both TX-02 injections passed. |

## Other adapters

Same catalog and PostgreSQL 18.6. The comparison is the commit tag and the rollback path, not a pass count.

pgx v5.11.0, `database/sql`, and both GORM modes pass `TX-01A` with the mechanism exercised. `Tx.Commit` returns `ErrTxCommitRollback` when the tag is `ROLLBACK`, and the callers return that error. Recording: `reports/examples/2026-10-22T13-24-28Z-606909`. SQLx is the opposite result on the same server behavior: the tag was `ROLLBACK` and `commit` returned `Ok`. pgx reads the tag. SQLx stores `rows_affected`.

`pg-control` `correct` passes `TX-01A` by reading the tag. `unsafe` fails by ignoring it. SQLx matches `unsafe` on this case and matches `correct` on the TX-03 reuse cases.

SQLAlchemy Core, Drizzle, Prisma, jOOQ, and Active Record fail `TX-01A` with the mechanism exercised, in their own recordings. Several of those also fail a withheld savepoint rollback by committing both markers. SQLx passed both TX-02 cases. That difference is the savepoint cleanup, not the commit tag. SQLx's `commit` still ignores the tag when the outer transaction is already aborted, which is what `TX-01A` measured.

## Limitations

- `TX-01B.commit-reply-discarded` was not run. The category E case was.
- `TX-05` was not run through a `begin` option. The `sql` mode is manual SQL.
- `direct-drop` did not run scenarios. Its rollback control failed.
- The proxy is this adapter's injection point. It is not part of SQLx. The tags it records are what it forwarded, or withheld, before SQLx parsed them.
- Whether `commit` returning `Ok` on tag `ROLLBACK` is a defect is for SQLx's maintainers. The draft in `upstream-draft.md` is not filed.

## Reproduce

```sh
cargo build --locked --release --manifest-path adapters/sqlx/Cargo.toml
node harness/run.mjs --adapter=sqlx --repeat=3
```

Rust 1.99.1. The disposable server is `pnpm run pg:up`. Do not point this at another database.
