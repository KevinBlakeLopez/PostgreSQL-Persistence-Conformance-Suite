# ruby-pg control findings

Recording: [`reports/examples/2026-10-21T19-39-32Z-b559f2`](../../reports/examples/2026-10-21T19-39-32Z-b559f2/summary.md). Ruby 4.0.7, pg 1.7.0, `PG.library_version` 180006, PostgreSQL 18.6. Three repetitions agreed on every row. CTL-01 passed in both modes. `pg-control` held its gate in the same run. Every classification matches the expectations in `adapter.json`. Those expectations are not a suite gate: the mode kinds are `native` and `configured`, the same split as `jdbc-control` and `pdo-control`, so this adapter is not auto-run beside other adapters and does not change their `case_controls` result.

`correct` passes every case it executes. `unsafe` fails the cases it is built to fail, including TX-01A, the reply-discarded commit, the two client-side savepoint rollbacks, the three TX-03 cases, the deferred-write nested failure, both TX-05 cases, and every migration case.

## What the pg gem makes observable

On an aborted transaction, `COMMIT` returns a `PG::Result`. In the TX-01A `correct` trace the result is command tag `ROLLBACK`, `PG::Result.res_status` is `PGRES_COMMAND_OK`, and `PG::Connection#transaction_status` is `PQTRANS_IDLE`. The same idle status follows a command tag of `COMMIT`. Idle-versus-in-error does not distinguish the two outcomes after the statement has completed. `PG::Result#cmd_status` does.

`correct` reports committed only for the tag `COMMIT`, rolled back only for the tag `ROLLBACK`, and failed for any other tag or a raised error. `unsafe` reports committed whenever `COMMIT` does not raise. TX-01A then fails with the mechanism exercised: the session is idle and its last statement is `COMMIT`, and the marker is absent.

A lost reply is a client-side simulation. The statement is sent, the result is discarded, and the connection is closed. `correct` reports `failed`. `unsafe` reports `rolled_back`. TX-01B.2 fails only for `unsafe`, because this adapter lists `result` as a rollback-claim channel.

## Savepoints, pool, isolation, migrations

`correct` ends a transaction with `ROLLBACK` after a failed `ROLLBACK TO SAVEPOINT`. `unsafe` continues to `COMMIT`. A withheld top-level `ROLLBACK` is discarded by closing the connection in `correct` and kept in `unsafe`. `correct` sends `BEGIN ISOLATION LEVEL SERIALIZABLE`. `unsafe` sends `BEGIN`. Both report `current_setting('transaction_isolation')` from the same statement as the transaction id.

Migrations in `correct` take `pg_advisory_xact_lock` before reading `ppcs_history`. `unsafe` takes no lock, deletes the history row on revert, and leaves the marker. Those are the control's deliberate shapes, not a claim about typical Ruby applications.
