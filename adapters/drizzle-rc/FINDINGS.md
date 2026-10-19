# Drizzle 1.0.0-rc.4 compared with 0.45.4

Drizzle ORM 1.0.0-rc.4, `drizzle-orm/node-postgres`, pg 8.23.1, pg-pool 3.14.0, Node.js v24.14.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Recording [`reports/examples/2026-10-19T14-34-08Z-26b178`](../../reports/examples/2026-10-19T14-34-08Z-26b178/summary.md). Three repetitions agreed. CTL-01 and pg-control held their gates.

The 0.45.4 recording is [`reports/examples/2026-10-19T13-38-47Z-39ea07`](../../reports/examples/2026-10-19T13-38-47Z-39ea07/summary.md). Same server image, same Node.js, same pg, same catalog, same case settings. The native adapter adds no command-tag check and no connection discard.

`drizzle()` in 1.0.0-rc.4 no longer takes a positional pool. This adapter calls `drizzle({ client: pool })`. The 0.45.4 adapter calls `drizzle(pool, { schema })`. Both hand the case's `pg.Pool` to `NodePgSession`. `trace_sees_framework_pg` is true in both runs.

## Classifications

Every Drizzle case classification is the same in both versions.

| Case | 0.45.4 | 1.0.0-rc.4 | What the traces share |
| --- | --- | --- | --- |
| `CTL-01.commit` | PASS | PASS | `commit` answered `COMMIT` |
| `CTL-01.rollback` | PASS | PASS | `rollback` answered `ROLLBACK` |
| `TX-01A.caught-error-then-commit` | FAIL, mechanism exercised | FAIL, mechanism exercised | `db.transaction` resolved. Reply to `commit` was command tag `ROLLBACK`. Session idle afterwards, last statement `commit` |
| `TX-01B.conn-lost-before-commit` | INCONCLUSIVE | INCONCLUSIVE | Process exit 1. Unhandled `'error'` on the checked-out `Client`, SQLSTATE `57P01` |
| `TX-01B.commit-reply-discarded` | PASS, TX-01B.2 not exercised | PASS, TX-01B.2 not exercised | Reported failed. Surfaced error `Failed query: rollback`. PostgreSQL committed |
| `TX-02.savepoint-rollback-not-sent` | FAIL | FAIL | Outer callback caught `Failed query: rollback to savepoint sp1`. `commit` answered `COMMIT`. Both markers visible. Session idle |
| `TX-02.savepoint-rollback-rejected` | FAIL | FAIL | Outer callback caught `3B001`. `commit` answered `ROLLBACK`. Neither marker visible. Session idle, last statement `commit` |
| `TX-02.conn-lost-before-savepoint-rollback` | INCONCLUSIVE | INCONCLUSIVE | Same unhandled `57P01` |
| `TX-03.rollback-not-sent` | FAIL | FAIL | Unit 1 failed with `Failed query: rollback`. Unit 2 committed the same xid on the same backend. Both markers visible. Unit 2 took 46 ms on 0.45.4 and 43 ms on 1.0.0-rc.4 |
| `TX-03.statement-error-rollback-not-sent` | FAIL | FAIL | Unit 1 aborted. Next `begin` got `25P02`. Unit 2 failed with `Failed query: begin`. `pool.end()` did not return within 5 s |
| `TX-03.conn-lost-in-transaction` | INCONCLUSIVE | INCONCLUSIVE | Same unhandled `57P01`, before unit 2 |
| `TX-04.nested-failure-contained` | PASS | PASS | `savepoint sp1`, `rollback to savepoint sp1` answered `ROLLBACK`, then `commit` answered `COMMIT`. Inner row absent |
| `TX-04.nested-released-outer-rollback` | PASS | PASS | `release savepoint sp1` answered `RELEASE`, then `rollback` answered `ROLLBACK`. Neither row visible |
| `TX-05.managed-serializable` | PASS | PASS | SQL `begin isolation level serializable`. Server reported `serializable` and held an `SIReadLock` on `item` |

Statement text, after stripping backend pids, matches between the two recordings for every executed case. Savepoint names stay `sp1`. Isolation SQL stays `begin isolation level serializable`.

The 1.0.0-rc.4 repetition stored in the case files uses these ids: TX-01A xid 7177, command tag `ROLLBACK` on `commit`; TX-02 withheld-savepoint xid 7217 committed both markers (inner xmin 7218); TX-02 rejected-savepoint xid 7232 aborted; TX-03 reuse xid 7262 for both markers on one backend.

## Where the implementation lives

The two packages do not import one shared transaction module. Each publishes its own `node-postgres/session.js`. The control flow was carried forward.

0.45.4 `NodePgSession.transaction` is lines 180–194. 1.0.0-rc.4 `NodePgSession.transaction` is lines 50–65. Both do this, in this order:

1. Detect a pool by `instanceof Pool` or a constructor name containing `Pool`.
2. `client.connect()` when it is a pool.
3. `BEGIN`, with `getTransactionConfigSQL(config)` appended when a config object is passed. That helper still emits `isolation level …`, the access mode, and `deferrable` or `not deferrable` (0.45.4 `pg-core/session.js` lines 148–159; 1.0.0-rc.4 `pg-core/async/session.js` lines 125–130).
4. Run the callback.
5. `COMMIT` and return the callback value. The `pg` `Result`, including `command`, is not read.
6. On any throw, `ROLLBACK`, then rethrow that error. A throw from `ROLLBACK` replaces the original error.
7. `finally`: `session.client.release()` with no argument. `BEGIN` is before the `try`, so a `BEGIN` that throws does not reach `release()`.

Nested transactions are the same SQL. 0.45.4 lines 205–221 and 1.0.0-rc.4 lines 69–81 both use `SAVEPOINT spN`, `RELEASE SAVEPOINT spN`, and `ROLLBACK TO SAVEPOINT spN`, and both await the rollback before rethrowing the callback error. The RC constructor passes `relations` and a `parseRqbJson` flag. The savepoint name is still `sp${nestedIndex + 1}`.

1.0.0-rc.4 sends queries through an executor in `NodePgSession.prepareQuery` (lines 38–47). `session.execute` asks for mode `"raw"`, and that mode returns the full `pg` result (`mode === "raw" ? r : r.rows`). `transaction()` still ignores that result. The TX-01A trace is the observation: the driver received command tag `ROLLBACK`, and `db.transaction()` resolved.

pg-pool 3.14.0 is the same package in both adapters. It still removes the client `'error'` listener while the client is checked out. Neither Drizzle version adds a listener. The category B crash is that combination, unchanged.

No case passed in one version and failed in the other, so there is no source change to isolate as the cause of a classification difference.

`PgDialect.migrate` did change. 1.0.0-rc.4 `pg-core/async/session.js` `migrate` (lines 136–171) adds an upgrade step and selects migrations with `getMigrationsToRun`. Those cases were not run. The transaction adapter does not call `migrate()`.

## What did not change

PostgreSQL answering `COMMIT` with `ROLLBACK` is still reported as success. A failed `ROLLBACK TO SAVEPOINT` is still caught by the outer callback, and the outer `COMMIT` still runs. A withheld top-level `ROLLBACK` still returns the connection, and the next `db.transaction()` still commits the open transaction. Nested savepoints still use `sp1`. `isolationLevel: 'serializable'` still produces `begin isolation level serializable`, and the server still reports `serializable`.

The `query_timeout` probe in `investigations/drizzle-followups/probe.mjs` was run against 0.45.4 only. The RC `transaction()` still ends in the same `release()` with no error, which is the call that returned the connection in that probe. This run did not repeat the probe.
