# Laravel findings

Recording: [`reports/examples/2026-10-21T16-24-17Z-231161`](../../reports/examples/2026-10-21T16-24-17Z-231161/summary.md). Re-run on PHP 8.5.12, pdo_pgsql 8.5.12, and libpq 18.6: [`reports/examples/2026-10-23T14-18-35Z-5a6ff7`](../../reports/examples/2026-10-23T14-18-35Z-5a6ff7/summary.md), where every classification matched; the per-case notes below are from the first recording. PHP 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, illuminate/database v13.38.0, PostgreSQL 18.6. Three repetitions agreed on every row. CTL-01 passed in each mode. `pg-control` held its gate. No row is INCONCLUSIVE.

`managed` and `explicit` produced the same classification on every case both modes ran. The tables below use `managed` for the shared rows. `explicit` matched it. `persistent` matched `managed` on the three TX-03 cases.

A FAIL here is a counterexample to a PPCS invariant under these versions and this fault category. It is not, by itself, a defect report, and it is not a security finding. Nothing was filed upstream.

## Results

| Case | Fault | managed | explicit | persistent |
| --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | PASS | PASS | PASS |
| `CTL-01.rollback` | none | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | A | FAIL, mechanism exercised | FAIL, mechanism exercised | |
| `TX-01B.conn-lost-before-commit` | B | PASS | PASS | |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | | |
| `TX-02.savepoint-rollback-not-sent` | C | FAIL | FAIL | |
| `TX-02.savepoint-rollback-rejected` | C | FAIL | FAIL | |
| `TX-02.conn-lost-before-savepoint-rollback` | B | FAIL | FAIL | |
| `TX-03.rollback-not-sent` | C | FAIL | FAIL | FAIL |
| `TX-03.statement-error-rollback-not-sent` | C | FAIL | FAIL | FAIL |
| `TX-03.conn-lost-in-transaction` | B | FAIL | FAIL | FAIL |
| `TX-04.nested-failure-contained` | none | PASS | PASS | |
| `TX-04.nested-released-outer-rollback` | none | PASS | PASS | |
| `TX-04.independent-inner` | none | UNSUPPORTED, not applicable by design | | |
| `TX-05.managed-serializable` | none | PASS | | |
| `TX-05.explicit-serializable` | none | | PASS | |
| `MG-02.*`, `MG-03.*` | | NOT_RUN in this recording. See [Migration cases](#migration-cases) | | |

## TX-01A

Observed, three times, both modes. The callback caught `UniqueConstraintViolationException` with SQLSTATE `23505`. `Connection::transaction()` and explicit `commit()` then returned. Diagnostics: `PDO::commit()` was called once, returned true, `errorInfo()` SQLSTATE was `00000`, `inTransaction()` was true before the call and false after. The runner's mechanism check is true: after the API returned, the same session was idle and its last statement was `COMMIT`. `pg_xact_status` was aborted. The marker was absent.

`pdo_pgsql` does not expose `PQcmdStatus`. This run does not claim Laravel or PDO read a `ROLLBACK` tag. The tag is the runner's inference from the session's last statement together with the aborted fate. What the application received is a normal return from `transaction()` or `commit()`, and a true return from `PDO::commit()`.

Confidence: high for that sequence. The same shape is on the PDO control's `unsafe` mode, which reports committed exactly when `PDO::commit()` returns true.

`DatabaseTransactionsManager` was not set on these rows. Capsule does not register `DatabaseServiceProvider`, and `DatabaseManager::configure` sets the manager only when `db.transactions` is bound. `afterCommit` is not part of the scored path.

A separate probe, `adapters/php/probe.php`, sets the manager and repeats the caught-unique-violation sequence. It is not a PPCS case. On that run, Eloquent and the query builder both returned from `transaction()`, ran the `afterCommit` callback once, ran the `afterRollback` callback zero times, and left the marker absent. Confidence: high for that probe execution. It is one database, not three harness repetitions.

## TX-01B

Connection loss before `COMMIT` (`pg_terminate_backend`). Both modes reported `failed`. `PDO::commit()` threw. Diagnostics recorded SQLSTATE `HY000`, not a successful return. The API did not report a commit. PASS for TX-01B.1.

`TX-01B.commit-reply-discarded` was not run. `pdo_pgsql` returns from `commit()` only after it has consumed the server reply. Discarding that reply inside the extension is not available from PHP. A TCP proxy that drops the reply is the deferred harness mechanism. It is not substituted here.

## TX-02

Category C is a client-side injection in `FaultingPdo`, once, before Laravel sees the error. It is not a production network failure.

**Rollback not sent.** Laravel reported committed. `PDO::commit()` was not called (`commit_calls` 0). At `after-outer` the session was `idle in transaction`. The transaction was still open. Teardown rolled it back. Neither marker remained. TX-02.1 fails because the API reported a commit of a transaction PostgreSQL had not committed. TX-02.2 fails because the session was still inside a transaction. This is not the ending where both markers are committed.

The counter explains the missing `COMMIT`, as source plus this trace. `rollBack()` threw from the withheld `ROLLBACK TO SAVEPOINT` before `$this->transactions` was assigned. The outer `transaction()` or `commit()` then saw a level other than 1, skipped `PDO::commit()`, decremented the counter, and returned. That reading fits `commit_calls` 0 and the still-open session. It is an interpretation of `ManagesTransactions` at v13.38.0 together with the trace, not a second experiment.

**Rollback rejected.** PostgreSQL answered the rewritten statement with `3B001`. Laravel reported committed. `PDO::commit()` was not called. At `after-outer` the session was `idle in transaction (aborted)`. Teardown rolled the transaction back. Neither marker remained. TX-02.1 and TX-02.2 both fail. The session was not idle outside a transaction.

**Connection lost inside the savepoint.** The runner terminated the backend. The nested rollback raised `PDOException` `HY000`. Laravel reported committed. `PDO::commit()` was not called. The session was gone at `after-outer`. The captured transaction was aborted. TX-02.1 fails. TX-02.2 holds: there was no session left inside a transaction.

## TX-03

One Capsule connection. It is not a pool. `ATTR_PERSISTENT` did not change the classification.

**Rollback not sent.** After the withheld `PDO::rollBack()`, `transactionLevel()` was 1 and the session was `idle in transaction` on the same backend. The next `transaction()` reported committed. Its xid was the failed transaction's xid. That transaction was aborted at teardown. The next marker was not visible. TX-03.1 fails because the next unit ran inside the failed transaction. TX-03.2 fails because that unit did not commit. The doomed marker was not left visible.

**Statement error, then rollback not sent.** The session stayed `idle in transaction (aborted)`. The next statement failed with `25P02`. The next unit reported failed and did not capture an xid. TX-03.2 fails. The failed transaction was not committed.

**Connection lost.** The backend was gone. `transactionLevel()` was 0. The next `beginTransaction()` threw `PDOException` "There is already an active transaction". That string is PDO's client-side flag. The next unit reported failed. TX-03.2 fails. The lost transaction was not committed, and the next unit did not join a live xid.

## TX-04 and TX-05

Both savepoint cases passed in both modes. A nested failure was rolled back to the savepoint and the outer commit kept the outer marker only. A released nested scope was removed when the outer transaction rolled back.

`TX-04.independent-inner` is not applicable by design. A nested call is a savepoint on the same PDO. Eloquent `create` sends the insert when it is called.

TX-05 passed. `current_setting('transaction_isolation')` was `serializable`, read in the same statement as the xid. The request is not an argument of `transaction()` or `beginTransaction()`. `PostgresConnector::configureIsolationLevel` runs `set session characteristics as transaction isolation level serializable` when the connection config key `isolation_level` is set. That is Laravel's documented connector setting. The transaction methods themselves take no level.

## Migration cases

Recording: [`reports/examples/2026-10-23T13-03-36Z-03a5b5`](../../reports/examples/2026-10-23T13-03-36Z-03a5b5/summary.md). PHP 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, illuminate/database v13.38.0, illuminate/filesystem v13.38.0, PostgreSQL 18.6. Managed mode only. Three repetitions agreed on every row. CTL-01 passed. `pg-control` held every case gate.

The adapter writes the case's migration file to a temporary directory, creates `migrations` when the table is missing, and calls `Migrator::run()` or `Migrator::rollback()`. That is what `php artisan migrate` does without `--isolated`, and what `migrate:rollback` does. On the MG-02 cases, `up()` inserts the marker and then waits on the runner's gate inside the migration's transaction.

| Case | Result | Observed |
| --- | --- | --- |
| `MG-02.held` | FAIL | A and B were inside the migration at once. Marker count 2, history count 2. C found nothing to do. |
| `MG-02.first-deployment` | PASS (history-table collision, no lock) | One runner failed creating `migrations` (`pg_class_relname_nsp_index`, on `migrations_id_seq`). The other applied. B failed in the first repetition, A in the other two. |
| `MG-02.session-loss` | FAIL, MG-02.5 | B entered while A was still inside. The terminated runner reported `SQLSTATE[HY000]` "no connection to the server", and B applied. Marker count 1. |
| `MG-02.idle-session-timeout` | FAIL | As `MG-02.held`. A had one session, inside the migration's transaction, and it did not end. |
| `MG-03.valid-reversal` | PASS | The revert deleted the marker and the history row. The reapply ran the migration again. |
| `MG-03.no-reversal` | FAIL | `rollback()` returned the migration. The history row was deleted and the marker remained. Lucid ends the same way. |
| `MG-03.failing-reversal` | PASS | `rollback()` threw. The marker and the history row remained. |

Source reading of `Migrations/Migrator.php` at v13.38.0: the migrator takes no advisory lock. `runUp()` calls `runMigration()`, which wraps `up()` in `Connection::transaction()`, and then calls `repository->log()`. `runDown()` calls `runMigration()`, which skips a missing `down()`, and then calls `repository->delete()`. The `CREATE TABLE` in the recorded first-deployment error has no unique constraint on `migration`, so two runners leave two history rows.

The first-deployment pass is not coordination. Both runners started at once against a database with no history table, and one `CREATE TABLE` collided. When B starts after the table exists and A is still inside the migration, both runners execute it, as `MG-02.held` shows.

`MigrateCommand`, in the same package, implements `Isolatable`. In the illuminate/console v13.38.0 source, `php artisan migrate --isolated` takes a lock in the application's cache store before the command runs. The lock expires after an hour by default. A run that cannot get it prints that the command is already running and exits 0, unless `--isolated` is given a status code. `migrate:rollback` is not `Isolatable`. This adapter does not run the console command, so `--isolated` is not measured.

## What was not run

Deadlock and serialization-failure retries. From `ConcurrencyErrorDetector` at v13.38.0, a `PDOException` whose code is `40001` is treated as a concurrency error, and `transaction()` retries while attempts remain. The default attempts value is 1. A `QueryException` is not a `PDOException`, so the `40001` check does not apply to it unless the message matches the detector's list. `could not serialize access` is not in that list. This is source reading. No deadlock was executed.

Query builder versus Eloquent, on the scored matrix, was not repeated case by case. The trace of Eloquent `create` is `Connection::insert` through a prepared statement. The probe's query-builder insert had the same TX-01A outcome as Eloquent: `transaction()` returned, `afterCommit` ran, the marker was absent. That is the probe, not the full matrix.

## Reproduction

```sh
node harness/run.mjs --adapter=laravel --case=TX-01A.caught-error-then-commit --mode=managed --repeat=3
```

The same sequence outside the harness is `php adapters/php/probe.php .ppcs-instance.json` on the disposable server. It prints `pdo_commit_return`, marker visibility, and the callback counts. It is the review reproduction. It has not been filed.
