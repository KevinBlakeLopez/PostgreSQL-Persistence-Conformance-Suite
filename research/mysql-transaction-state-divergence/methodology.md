# Methodology

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max).

Labels used here and in findings.md:

- **Observed**: read from a recorded file in `output/`.
- **Source**: a reading of Laravel, PHP or MySQL code or documentation. Not a runtime result unless a sentence also says observed.
- **Manual**: quoted from the MySQL 8.4 Reference Manual or the PHP manual.

## 1. Scope

The study began from a broad assignment: MySQL/InnoDB transaction-state divergence across CodeIgniter 4, Laravel and SQLAlchemy. A read-only reconnaissance found that most of it was already recorded in `investigations/mysql-innodb-baseline/`:

- raw InnoDB deadlock and lock-wait behavior under both `innodb_rollback_on_timeout` settings;
- CodeIgniter 4.7.5, mysqli and PDO on deadlock and lock wait;
- Knex 3.3.0 and Lucid 22.4.2.

None of that was repeated except the raw PDO controls this question needs.

The question was then narrowed to Laravel 13.38.0 and the interaction between:

- errno 1205;
- `innodb_rollback_on_timeout` OFF and ON;
- nested `DB::transaction()`;
- savepoint preservation;
- Laravel's concurrency-error classification;
- callback execution;
- the outer transaction's completion.

That narrowing arrived after the first recorded run. The first run therefore also contains deadlock (errno 1213) scenarios, which are reported but not analyzed (findings.md §7). SQLAlchemy was not studied.

## 2. Environment

**Observed** from `output/<run id>/versions.json` and `server-config.json`.

| Item | Value |
| --- | --- |
| Server | MySQL Community Server 8.4.11, image `mysql:8.4.11@sha256:24989179f58856db763f418010c1169fecc944e3ec1ea7e921572d83eb070f70`, the digest the baseline used |
| Containers | `mysd-mysql` on `127.0.0.1:13316`, image defaults; `mysd-mysql-rb-timeout` on `127.0.0.1:13317`, started with `--innodb-rollback-on-timeout=ON` |
| Data directory | tmpfs (1 GiB), so nothing outlives the container |
| `innodb_rollback_on_timeout` | `0` on 13316, `1` on 13317. The variable is not dynamic (baseline REPORT.md §2), which is why there are two servers |
| `innodb_lock_wait_timeout` | `50` globally. The subject sets `SET SESSION innodb_lock_wait_timeout = 2` except in `laravel.nested-1205-caught.server-timeout`, which keeps 50 |
| `innodb_deadlock_detect` | `1` |
| `transaction_isolation`, `autocommit` | `REPEATABLE-READ`, `1` |
| `binlog_format`, `log_bin` | `ROW`, `1` |
| `performance_schema` | `1`. The runner enables the `events_transactions_*` and `events_statements_*` consumers, including `events_statements_history_long` (size 10000). The recorded runs' `consumers_before` already show them enabled, because unrecorded development runs had enabled them on the same server instances. The image defaults were not recorded by this study |
| PHP | 8.5.12 (CLI, NTS), `pdo_mysql` client `mysqlnd 8.5.12` |
| Laravel | `illuminate/database` v13.38.0, reference `add3b4602c77c38edbee26be9ab55e7eec621182`, through Composer (`repro/php/composer.lock`) |
| Laravel sources hashed in `versions.json` | `Concerns/ManagesTransactions.php`, `ConcurrencyErrorDetector.php`, `DatabaseTransactionsManager.php` |
| Node and driver | Node v24.14.1, `mysql2` 3.24.6 (`repro/pnpm-lock.yaml`) |
| Host | macOS 26.6.2 on arm64, colima 0.9.1, Docker Engine 28.4.0 |

Laravel 13.38.0 was the latest 13.x release on 2026-10-25. The `13.x` branch had no change to `ManagesTransactions.php`, `ConcurrencyErrorDetector.php`, `DatabaseTransactionsManager.php`, `Connection.php` or `MySqlConnection.php` since that tag (GitHub compare `v13.38.0...13.x`, 40 commits ahead).

## 3. Roles

Every run uses its own schema, `mysd_<scenario>_<server>_r<repetition>`. Each schema is created by root just before the run. The same marker names therefore never meet across runs.

| Role | Process and connection | What it does |
| --- | --- | --- |
| Subject | PHP, `repro/php/subject.php` | One process per run. Laravel's MySQL connection is built through Capsule, with `db.transactions` bound to a `DatabaseTransactionsManager` before the connection is created. `DatabaseServiceProvider` does the same in an application, and the PostgreSQL study `research/transaction-callbacks/` did the same. The `pdo.*` scenarios use plain PDO instead |
| Sink | PHP, a second PDO connection in the subject process, in autocommit mode | Callbacks write only here, one row per callback into `callback_sink`. A sink row stays committed whatever happens to the subject's transaction |
| Other session | Node, `mysql2`, the application user | A lock holder for 1205: `START TRANSACTION; UPDATE lk ... WHERE id = 1`, held until the subject exits, then `ROLLBACK`. A deadlock fixture for 1213 (§4) |
| Observer | Node, `mysql2`, root, autocommit | Reads the server at every checkpoint, never inside a transaction |
| Fresh reader | Node, a connection opened after the subject exited | The final read of the markers and sink rows |

The subject and Node talk over stdin and stdout, one JSON object per line:

- at a checkpoint the subject prints its own state and waits for `resume`;
- before a statement that should block, it prints a `blocking` notice, and Node polls `performance_schema.data_lock_waits` while the subject waits.

No step relies on a sleep.

## 4. Triggers

Nothing is injected. Each failure is a real server error.

- **errno 1205.** The subject updates the `lk` row the holder has locked, and waits until its lock-wait timeout.
  - Every run recorded the wait in `data_lock_waits` while the subject was blocked, within 0 to 29 ms of the `blocking` notice.
  - The subject's own clock measured 2002–2064 ms per wait at the 2 s session setting, and 50061–50320 ms at the server's 50 s.
- **errno 1213.** Same arrangement as the baseline (REPORT.md §10):
  1. the fixture inserts eight `ballast` rows and locks `dl` row 1;
  2. the subject locks row 2 and reaches the `holding-row-2` checkpoint;
  3. the fixture requests row 2;
  4. Node waits until that wait is visible in `data_lock_waits`, then resumes the subject;
  5. the subject's request for row 1 closes the cycle.

  The subject is the lighter transaction. In all 30 deadlock runs, across both recorded runs, InnoDB's `LATEST DETECTED DEADLOCK` named the subject's thread in `WE ROLL BACK TRANSACTION (2)`, and the fixture's statement completed (`deadlock` and `fixture_cross` in `runs.json`).
- **errno 1062.** The inner unit inserts `uniq_row.code = 'taken'`, which already exists.

## 5. Transaction boundaries

`DB::transaction()` below is `Connection::transaction()` on the Capsule connection; the `DB` facade calls the same method. Marker names are `outer`, `inner`, `after` (written after the failure), `next` (a later transaction on the same connection), `tx` (single-level) and `attempt-N`.

| Scenario | Shape |
| --- | --- |
| `pdo.savepoint-1205.rollback-to` | `beginTransaction`, insert `outer`, `SAVEPOINT trans2`, insert `inner`, the 1205 statement (caught), `ROLLBACK TO SAVEPOINT trans2`, insert `after`, `commit()`. These are the statements Laravel's MySQL grammar uses for a level-2 transaction |
| `pdo.savepoint-1205.skip` | The same without `ROLLBACK TO SAVEPOINT` |
| `pdo.savepoint-1213` | The same as `rollback-to`, with the deadlock as the failure |
| `pdo.caught-1205.commit` | `beginTransaction`, insert `tx`, the 1205 statement (caught), `commit()` with no statement in between |
| `laravel.commit` | `DB::transaction()` inserting `tx`. The control |
| `laravel.nested-1205-caught` | `DB::transaction(outer: insert outer; try { DB::transaction(inner: insert inner; the 1205 statement) } catch (Throwable) {}; insert after)` |
| `laravel.nested-1205-caught.server-timeout` | The same, with the server's 50 s timeout |
| `laravel.nested-1205-caught.outer-rollback` | `DB::beginTransaction(); insert outer; try { DB::transaction(inner: insert inner; the 1205 statement) } catch {}; DB::rollBack()` |
| `laravel.nested-1205-escapes` | As `nested-1205-caught`, but nothing catches, so the exception leaves both closures |
| `laravel.nested-explicit-1205` | `DB::transaction(outer: insert outer; DB::beginTransaction(); insert inner; try { the 1205 statement } catch { DB::rollBack() }; insert after)` |
| `laravel.nested-duplicate-caught` | As `nested-1205-caught`, with a duplicate key as the inner failure |
| `laravel.nested-1213-caught` | As `nested-1205-caught`, with the deadlock as the inner failure |
| `laravel.caught-1205-return` | `DB::transaction(insert tx; try { the 1205 statement } catch {}; return)` |

Every `laravel.*` closure registers `afterCommit` and `afterRollBack` callbacks for its own level (`:outer`, `:inner`, `:tx`). Every `laravel.*` scenario ends with one more `DB::transaction()` on the same connection and manager, which inserts `next` and registers `afterCommit:next`. That transaction shows any callback or level left over from the scenario.

## 6. Observations

Read at each checkpoint (`after-error`, `after-continue`, `after-end`, `final`) and after the subject exits:

- **The server's view of the subject's transaction (layer A).**
  - From `performance_schema.events_transactions_current` for the subject thread: `STATE`, `NUMBER_OF_SAVEPOINTS`, `NUMBER_OF_ROLLBACK_TO_SAVEPOINT`, `AUTOCOMMIT`.
  - Also `performance_schema.data_locks` for that thread.
  - At `final`, while the subject is still connected: `events_transactions_history_long` and `events_statements_history_long` for that thread. These give the transactions the server recorded and every statement it received, with its errno.
- **The subject's view (layers A and B).**
  - `Connection::transactionLevel()`, and the pending and committed levels of `DatabaseTransactionsManager`.
  - `PDO::inTransaction()`, which sends nothing to the server and is recorded as what PDO believed, not as the server's state.
  - For every call: returned or raised, with the exception class, SQLSTATE, errno and the cause chain.
- **Persisted state (layer C).** The markers visible to the observer at each checkpoint (committed rows only), and the fresh reader's markers after the subject exited.
- **Callbacks (layer D).** The sink rows at each checkpoint and at the end. A callback counts as executed only if its sink row exists. The subject's own list of callbacks is kept as a cross-check.

**Limits of these observations:**

- `information_schema.innodb_trx` is recorded but not used for any conclusion. In these runs it sometimes still showed a `RUNNING` row for the subject after the commit. **Manual** (17.15.2.3, Persistence and Consistency of InnoDB Transaction and Locking Information): "Data might not be consistent between the INNODB_TRX, data_locks, and data_lock_waits tables."
- Laravel's statements are server-side prepared statements. They appear in the statement history as `statement/com/Execute` with an errno and no SQL text. Transaction-control statements (`START TRANSACTION`, `SAVEPOINT`, `ROLLBACK TO SAVEPOINT`, `ROLLBACK`, `COMMIT`) go over the text protocol and appear with their text, so the presence or absence of `ROLLBACK TO SAVEPOINT` is observable.
- The observer's reads happen after the subject's call returned and the subject printed its checkpoint. They are not what the subject knew at the time.

## 7. Expectations and scoring

Every scenario states its expected observations in `repro/run.mjs` (`expect`), with the reasoning (`basis`). These were written from source reading, the MySQL manual and the baseline's records before the run that scores them. `matched_expectation` says whether a run agreed with that prediction. It is not a defect verdict.

Development runs, written to a scratch directory and not recorded:

- **4 runs**, all matched.
- **21 runs**, 20 matched. One prediction named the escaped scenario's callbacks `:tx`, while the subject names them by attempt (`:attempt-1`). The label was corrected before the first recorded run. The predicted behavior, `afterRollBack` once and no `afterCommit`, was unchanged.
- **8 runs** of the scenarios added for the second recorded run, all matched.

No other expectation was changed after a run.

## 8. Repetitions and agreement

Each scenario-and-server group ran 3 times in each recorded run.

- `summary.json` lists, per group, any observed field that differed between repetitions. Every list is empty in both runs.
- `matrix.json` agrees: no value is marked `differs_between_repetitions`.
- The 16 groups the two runs share have identical matrix rows.

## 9. Controls

- **Positive:** `laravel.commit`.
- **Raw driver:** the four `pdo.*` scenarios, which establish what the server does with the savepoint after 1205 and 1213 under each setting, without Laravel.
- **Framework, same code with another error:** `laravel.nested-duplicate-caught`.
- **Framework, the documented explicit API:** `laravel.nested-explicit-1205`.
- **The exception not caught:** `laravel.nested-1205-escapes`.
- **The outer transaction rolled back explicitly after catching:** `laravel.nested-1205-caught.outer-rollback`.
- **The case where Laravel's premise holds:** `laravel.nested-1213-caught`, where InnoDB did roll back the whole transaction.
- **Server timeout:** `laravel.nested-1205-caught.server-timeout`, at the server's 50 s.

## 10. Host

The host was on AC power for both recorded runs. During the second run, `pmset -g log` shows five maintenance-sleep periods between 10:04 and 10:14 local time. They stretched the wall time to 10 minutes 19 seconds. Every lock wait still measured 2002–2064 ms (50128–50320 ms at the server timeout), and outcomes do not depend on wall time.

## 11. Safety

- **Ports.** Every connection, from Node and from PHP, refuses any host but `127.0.0.1` and any port but 13316 and 13317. Another project's MySQL listens on 3306 on this machine.
- **Token.** `run.mjs` refuses a server without the token from `.mysd-instance.json`.
- **Containers.** The scripts start and remove only the `mysd` compose project. No other container was started, stopped or contacted.
