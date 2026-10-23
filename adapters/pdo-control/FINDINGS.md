# PDO control findings

Recording: [`reports/examples/2026-10-21T16-24-17Z-231161`](../../reports/examples/2026-10-21T16-24-17Z-231161/summary.md). Re-run on PHP 8.5.12, pdo_pgsql 8.5.12, and libpq 18.6: [`reports/examples/2026-10-23T14-18-35Z-5a6ff7`](../../reports/examples/2026-10-23T14-18-35Z-5a6ff7/summary.md), where every classification matched; the per-case notes below are from the first recording. PHP 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, PostgreSQL 18.6. Three repetitions agreed. CTL-01 passed in each mode. `pg-control` held its gate. No executed row is INCONCLUSIVE.

This adapter is a policy on PDO, not a claim that PDO is an oracle. `correct` passes the cases it executes. `unsafe` fails the cases it is built to fail. Neither policy can read a PostgreSQL command tag.

## Results

| Case | Fault | correct | unsafe | persistent |
| --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | PASS | PASS | PASS |
| `CTL-01.rollback` | none | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | A | PASS, mechanism not exercised | FAIL, mechanism exercised | |
| `TX-01B.conn-lost-before-commit` | B | PASS | PASS | |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | | |
| `TX-02.*` | | UNSUPPORTED, capability absent | | |
| `TX-03.rollback-not-sent` | C | PASS | FAIL | PASS |
| `TX-03.statement-error-rollback-not-sent` | C | PASS | FAIL | PASS |
| `TX-03.conn-lost-in-transaction` | B | PASS | FAIL | PASS |
| `TX-04.*` | | UNSUPPORTED | | |
| `TX-05.*` | | UNSUPPORTED, capability absent | | |
| `MG-02.*`, `MG-03.*` | | UNSUPPORTED, capability absent | | |

`TX-04.independent-inner` is not applicable by design. The other TX-04 cases, and all of TX-02, are capability-absent: PDO has no savepoint API. TX-05 is capability-absent: `PDO::beginTransaction()` takes no isolation level, and the `Pdo\Pgsql::TRANSACTION_*` constants are deprecated in PHP 8.5 and have no effect.

## What PDO::commit() returned

`unsafe` TX-01A, three times. A unique violation was caught (`23505`). `PDO::commit()` then returned true. `errorInfo()` SQLSTATE was `00000`. `inTransaction()` was true before the call and false after. The session was idle and its last statement was `COMMIT`. The transaction was aborted. The marker was absent. The mechanism was exercised. The policy reported committed because that is what a true return means in this mode. The return value is not a command tag.

`correct` TX-01A did not call `commit()`. It called `rollBack()` after the caught statement error. The last statement was `ROLLBACK`. The mechanism was not exercised. PASS means the policy reported a rollback and PostgreSQL aborted the transaction. It does not mean PDO surfaced a `ROLLBACK` tag.

`adapters/php/probe.php` is a separate observation, not a case. On `PDO::exec` of the duplicate, `commit()` returned true and `errorInfo()` was still `23505`. On `prepare`/`execute` of the duplicate, `commit()` returned true and `errorInfo()` was `00000`. The marker was absent on both. `get_class_methods(Pdo\Pgsql::class)` had no method whose name contains `cmd`, `tag`, or `status`. `errorInfo()` after `commit()` is not a stable outcome signal: it depended on whether the failed statement was `exec` or a prepared statement. Confidence: high for that one probe run.

## TX-01B

`correct` reported `failed` when `commit()` threw (`HY000`) after the runner terminated the backend. `unsafe` reported `rolled_back` for that throw. Neither reported committed. PASS.

The reply-discarded case was not run. `commit()` does not return until `pdo_pgsql` has consumed the reply. There is no PHP hook between the reply and the return value.

## TX-03

Category C withholds `PDO::rollBack()` once, in this process, before `pdo_pgsql` sends it.

`correct` drops the handle when `rollBack()` throws and opens another for the next unit. The next unit committed on a new transaction. PASS. With `ATTR_PERSISTENT` false, the next unit's backend pid differed. With `ATTR_PERSISTENT` true, the next unit reused the backend pid, the session at `after-unit1` was idle, and its last statement was `ROLLBACK`. The withheld `rollBack()` was followed by a `ROLLBACK` visible to the runner before the next unit committed. The next xid was not the failed xid. PASS. Persistent reuse of the backend was not reuse of the failed transaction.

`unsafe` keeps the handle. On the withheld rollback of an open transaction, the next unit continued after `beginTransaction()` reported an active transaction, and `commit()` committed that transaction. The doomed marker was visible. TX-03.1 fails. On the statement-error case, the next insert failed with `25P02` and the unit reported `rolled_back`. TX-03.2 fails. The failed transaction was not committed. On connection loss, the next unit did not commit on the dead connection. TX-03.2 fails.

## Limits

PDO is not a nested-transaction API. Savepoint SQL from this control would be application SQL. It is not implemented, and the TX-02 and TX-04 rows are unsupported for that reason.

No libpq control was added. `pg_transaction_status` exists on the `pgsql` extension and takes a `PgSql\Connection`, not a PDO handle. Using it would be a different driver. It is not a substitute for the PDO result.
