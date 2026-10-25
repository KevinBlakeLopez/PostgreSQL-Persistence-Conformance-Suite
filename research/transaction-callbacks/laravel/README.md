# Laravel after-commit callbacks when PostgreSQL answers COMMIT with ROLLBACK

Recorded 2026-10-25 UTC. Written by: Claude Opus 5.5 (max).

Does Laravel run a callback that is documented to run after a commit, when PostgreSQL rolled the transaction back? This reproduction calls `afterCommit()` and `afterRollBack()` directly. Laravel's other after-commit features register their work through the same manager method, `DatabaseTransactionsManager::addCallback`. This is source reading of laravel/framework v13.38.0, not this run:

- **Queued jobs:** `Queue::enqueueUsing` does it for a job that dispatches after commit (`Queue/Queue.php:371-377`). That covers the `after_commit` option, `->afterCommit()`, and `ShouldQueueAfterCommit`.
- **Events and handlers:** the event dispatcher does it for `ShouldDispatchAfterCommit` events (`Events/Dispatcher.php:299-301`), and for listeners and observers that handle events after commit (`:608-625`).

The queue documentation says the `after_commit` option also covers queued listeners, mailables, notifications, and broadcast events.

This is not a PPCS case, and it does not change the catalog or the harness. Nothing was filed. The Stage 4 review of this result is [`../stage-4-review.md`](../stage-4-review.md): which layer owns it, what reaches it, and whether it is already reported.

## Setup

| Piece | Version |
| --- | --- |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg13+2), `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, this study's own container |
| PHP, pdo_pgsql, libpq | 8.5.12, 8.5.12, 18.6 |
| illuminate/database | v13.38.0, loaded from `adapters/php/vendor` (`composer.lock` sha256 `d492f988…ad800`) |
| Runner | Node.js v24.14.1, pg 8.23.1 (the runner's own connections only) |

Each repetition of each scenario runs in a fresh database and a fresh PHP process. [`scenario.php`](scenario.php) opens three connections:

- **The subject:** Laravel's connection, or plain PDO for `pdo.*`. It connects through [`../tools/pg-tag-recorder.mjs`](../tools/pg-tag-recorder.mjs). That recorder forwards every byte unchanged, and reports what the client sent and the server's `CommandComplete` tags, errors and `ReadyForQuery` status.
- **The observer,** straight to PostgreSQL. It reads `pg_xact_status()` of the transaction ID captured inside the transaction, the marker's visibility, and the subject's row in `pg_stat_activity`.
- **The sink,** straight to PostgreSQL. It is the callbacks' only side effect: each callback inserts a row into `callback_log` in autocommit. That row stays committed whatever happens to the subject's transaction, as a sent email or a queued job would.

Laravel is wired the way an application wires it. `DatabaseServiceProvider` binds `db.transactions` (`DatabaseServiceProvider.php:79-81`), and `DatabaseManager::configure` gives each connection that manager (`DatabaseManager.php:251-253`). Capsule does not register the provider, so `scenario.php` makes the binding on Capsule's container. No fault is injected. The error is a real unique violation (`23505`) on `uniq.code`.

## Scenarios

| Scenario | What the code does |
| --- | --- |
| `laravel.commit` | `DB::transaction()`: register both callbacks, insert the marker, return |
| `laravel.error-escapes` | The same, then insert the duplicate and let the exception leave the closure |
| `laravel.caught-error` | The same, then insert the duplicate, catch `UniqueConstraintViolationException`, and return. Then a second `DB::transaction()` on the same connection, with its own callback (the reuse control) |
| `laravel.explicit-caught-error` | `DB::beginTransaction()`, register both callbacks, insert the marker, insert the duplicate and catch the exception, `DB::commit()` |
| `laravel.savepoint-recovery` | `DB::transaction()`: register the callbacks, insert the marker. Then insert the duplicate inside a nested `DB::transaction()` (a savepoint) that registers its own callbacks, catch the exception outside it, and return |
| `laravel.deferred-fk` | `DB::transaction()`: register both callbacks and insert the marker. Then insert a `child` row whose `parent` does not exist, under a `DEFERRABLE INITIALLY DEFERRED` foreign key, and return. `COMMIT` fails. Then a second `DB::transaction()` runs on the same connection (the reuse control) |
| `laravel.explicit-deferred-fk` | The same with `DB::beginTransaction()` and `DB::commit()`. When `commit()` raises, the catch block calls `DB::rollBack()`. Then the reuse transaction |
| `pdo.commit` | Plain PDO: `beginTransaction()`, insert the marker, `commit()` |
| `pdo.caught-error` | Plain PDO: the same, with the duplicate inserted and the `PDOException` caught before `commit()` |
| `pdo.deferred-fk` | Plain PDO: the marker and the `child` row, then `commit()` |

## Result

Three full runs, each running every scenario three times, with every repetition agreeing:

- [`output/2026-10-25T05-26-34Z-c955f6`](output/2026-10-25T05-26-34Z-c955f6/summary.md) and [`output/2026-10-25T05-28-04Z-7b1e8d`](output/2026-10-25T05-28-04Z-7b1e8d/summary.md) ran the first seven scenarios with the first version of `scenario.php` (sha256 `014993…e46b`, recorded in each run's `versions.json`).
- [`output/2026-10-25T06-05-06Z-ac32a1`](output/2026-10-25T06-05-06Z-ac32a1/summary.md) ran all ten with the current version. That version adds the deferred-FK scenarios, and records more identity fields: the `application_name` of each observed session, each visible marker's `xmin`, the observer's and the sink's backend pids, and the manager's records just after the end. `run.mjs` gained the `CB_PHP` options after this run. With them unset, it runs the same command as before.

The seven rows that all three runs share have the same values. Two more runs used PHP 8.5.12 built from source, with pdo_pgsql loaded as a module; [`../patched-driver/`](../patched-driver/README.md) describes them:

- [`output/2026-10-25T14-05-31Z-046a1a`](output/2026-10-25T14-05-31Z-046a1a/summary.md) used the stock module, and equals `ac32a1` row for row.
- [`output/2026-10-25T14-05-44Z-b6ce5c`](output/2026-10-25T14-05-44Z-b6ce5c/summary.md) used a module patched to report the `ROLLBACK` tag as a failure.

The table below is the stock driver. In the table:

- **Wire:** each `COMMIT` or `ROLLBACK` the subject sent, the `ReadyForQuery` status before it, and the reply's tag or error.
- **Fate:** `pg_xact_status()`.
- **Callback log:** what the observer read from `callback_log` after the call returned.

| Scenario | API | Wire | Fate | Marker | Callback log |
| --- | --- | --- | --- | --- | --- |
| `laravel.commit` | returned | `COMMIT [T] -> COMMIT` | committed | 1 | afterCommit |
| `laravel.error-escapes` | raised `UniqueConstraintViolationException` 23505 | `ROLLBACK [E] -> ROLLBACK` | aborted | 0 | afterRollBack |
| `laravel.caught-error` | returned | `COMMIT [E] -> ROLLBACK` | aborted | 0 | **afterCommit** |
| `laravel.explicit-caught-error` | returned | `COMMIT [E] -> ROLLBACK` | aborted | 0 | **afterCommit** |
| `laravel.savepoint-recovery` | returned | `ROLLBACK TO SAVEPOINT trans2 [E] -> ROLLBACK`, then `COMMIT [T] -> COMMIT` | committed | 1 | afterRollBack:inner, afterCommit |
| `laravel.deferred-fk` | raised `PDOException` 23503 | `COMMIT [T] -> error 23503`, then reuse `COMMIT [T] -> COMMIT` | aborted | 0 | none. After the reuse transaction: **afterCommit**, afterCommit:reuse |
| `laravel.explicit-deferred-fk` | raised `PDOException` 23503 | `COMMIT [T] -> error 23503`, then reuse `COMMIT [T] -> COMMIT` | aborted | 0 | afterRollBack. After the reuse transaction: afterRollBack, afterCommit:reuse |
| `pdo.commit` | `commit()` returned `true` | `COMMIT [T] -> COMMIT` | committed | 1 | (no callbacks) |
| `pdo.caught-error` | `commit()` returned `true` | `COMMIT [E] -> ROLLBACK` | aborted | 0 | (no callbacks) |
| `pdo.deferred-fk` | `commit()` raised `PDOException` 23503 | `COMMIT [T] -> error 23503` | aborted | 0 | (no callbacks) |

**Observed in `laravel.caught-error` and `laravel.explicit-caught-error`, in every repetition:**

1. The duplicate insert raised `UniqueConstraintViolationException` with SQLSTATE `23505`, and the application caught it.
2. Before the transaction ended, the observer saw the subject session `idle in transaction (aborted)`, and `pg_xact_status()` already `aborted`.
3. Laravel sent `COMMIT`. The server had last reported status `E`, a failed transaction, and it answered `COMMIT` with the command tag `ROLLBACK`.
4. `DB::transaction()` returned the closure's value, and `DB::commit()` returned.
5. The `afterCommit` callback ran once, and its row in `callback_log` was committed. `afterRollBack` did not run. `callback_log` was empty when the observer read it just before the transaction ended.
6. After the call, `pg_xact_status()` was still `aborted`, and the marker was absent on the observer's connection.
7. The server's statement log shows the order on two backends. In `laravel.caught-error` repetition 1 of the first run, the subject sent `COMMIT` for xid 907 at 05:26:34.876 UTC. The sink inserted the `afterCommit` row at 05:26:34.877.

**Controls:**

- **Commit.** `laravel.commit` committed and ran `afterCommit` once.
- **Escaped exception.** In `laravel.error-escapes` the exception left the closure, Laravel sent `ROLLBACK`, and only `afterRollBack` ran. This is the path Laravel documents.
- **Savepoint recovery.** `laravel.savepoint-recovery` committed the marker. The nested scope's `afterRollBack` ran at the savepoint rollback, its `afterCommit` was discarded, and the outer `afterCommit` ran once.
- **Reuse.** After `laravel.caught-error`, the same connection and manager ran a second transaction. It committed, its marker was visible, and its callback ran once. The first transaction's callback did not run again. The manager held no pending or committed records after either scenario. That differs from the deferred-FK case below, where a `COMMIT` that raises leaves a record behind.
- **Driver.** In `pdo.commit` and `pdo.caught-error`, `PDO::commit()` returned `true`. `inTransaction()` was `true` before the call and `false` after.

**A `COMMIT` that fails with an error** is a different path, and not the one above. The deferred foreign key keeps the transaction healthy until `COMMIT` (status `T`), and PostgreSQL then answers `COMMIT` with error `23503`.

- **PDO.** `pdo.deferred-fk` shows PDO reporting the failure: `commit()` raised.
- **`DB::transaction()`.** In `laravel.deferred-fk` it raised the driver's `PDOException`, and no callback ran. But the manager kept the failed transaction's record, and the next commit on the connection ran that transaction's `afterCommit`. In repetition 1 the server log shows xid 853's `COMMIT` failing at 06:05:08.706, the reuse transaction's `COMMIT` at .715, and the sink's insert of xid 853's `afterCommit` at .716.

  That is [laravel/framework#61964](https://github.com/laravel/framework/issues/61964), already reported, here reproduced on PostgreSQL.
- **`DB::commit()`.** In `laravel.explicit-deferred-fk`, the catch block's `DB::rollBack()` cleared the manager and ran `afterRollBack`, so nothing leaked.

The review compares the two paths in [check 6](../stage-4-review.md#6-a-deferred-foreign-key-violated-at-commit).

## Which layer did what

| Layer | What happened | Basis |
| --- | --- | --- |
| PostgreSQL | Answered `COMMIT` in a failed transaction with the command tag `ROLLBACK`, and rolled back | Wire, `pg_xact_status()`, marker |
| pdo_pgsql | `PDO::commit()` returned `true` for that reply, the same value as for a real commit | Runtime, `pdo.*` |
| pdo_pgsql | `pdo_pgsql_transaction_cmd` checks only that `PQresultStatus` is `PGRES_COMMAND_OK`, and never reads `PQcmdStatus` (php-src `PHP-8.5`, `ext/pdo_pgsql/pgsql_driver.c`, commit `197bdc0`). PDO has no method that exposes the tag | Source reading |
| Laravel | Treats a `PDO::commit()` that does not throw as a commit, then runs the manager's callbacks before `transaction()` returns (`Concerns/ManagesTransactions.php:52-72` and `:203-219`, `DatabaseTransactionsManager.php:67-97`) | Source reading; the run shows the result |

One misleading value. In `pdo.caught-error`, `errorInfo()` after `commit()` is `23505`, with the caught `INSERT`'s own message and `DETAIL: Key (code)=(taken) already exists.` That is the earlier statement's error, still on the connection handle. A failed `COMMIT` would carry its own message. In `pdo.commit`, where no statement failed, it is `00000`. Laravel runs statements through prepared statements, and pdo_pgsql records a prepared statement's error on the statement, not the connection (source reading, `pgsql_driver.c:77`). There, the connection's `errorInfo()` after the commit was `00000`, as [`adapters/laravel/FINDINGS.md`](../../../adapters/laravel/FINDINGS.md) records.

## What this does not show

- **A Laravel application.** This is Capsule plus the `db.transactions` binding. No queue, mailer or event dispatcher is installed. The queue and event paths above are source reading. A job pushed to a real queue after a false commit was not run.
- **A trigger without an application catch.** Here the application catches the violation inside the closure. Laravel's transaction documentation does not warn against that. Laravel's own `createOrFirst` wraps its catch in a savepoint when a transaction is open (`Eloquent/Builder.php:771-777`). The review's [check 2](../stage-4-review.md#2-what-reaches-it-without-an-application-catch) looks for triggers without an application catch. [Check 3](../stage-4-review.md#3-is-the-caught-error-scenario-supported-usage-in-laravel) finds the documentation silent on whether catching inside the closure is supported.
- **Eloquent.** These scenarios use the query builder. [`adapters/laravel/FINDINGS.md`](../../../adapters/laravel/FINDINGS.md) records the same TX-01A outcome for Eloquent.
- **A subject transaction without extra statements.** The transaction contains one statement added for evidence, `select pg_current_xact_id()`, after the first write. The connection also runs `select pg_backend_pid()` before `BEGIN`.
- **`backend_xid` after the abort.** `pg_stat_activity.backend_xid` was null once the error had aborted the transaction. So the oracle is the transaction ID captured inside the transaction. In every repetition that ended in a commit, the two agreed.

Line numbers are illuminate/database v13.38.0.

## Run it

From the repository root, with PHP 8.5.12, `composer install` done in `adapters/php`, and colima running:

```sh
sh research/transaction-callbacks/tools/container.sh up
node research/transaction-callbacks/tools/recorder-check.mjs
node research/transaction-callbacks/laravel/run.mjs --repeat=3
sh research/transaction-callbacks/tools/container.sh down
```

`run.mjs` refuses any server other than the study container, whose random `cluster_name` it checks. `--scenario=a,b` runs a subset. `CB_PHP` and `CB_PHP_ARGS` select another PHP and its arguments, such as a build that loads a patched pdo_pgsql. `CB_DRIVER_LABEL` names that build in `versions.json`, together with each loaded module's sha256. Each run writes `output/<run id>/`:

- `results.jsonl`: one object per repetition, with its checkpoints, callbacks and wire events;
- `wire.ndjson`: every recorded event;
- `server.log`: the server's statement log for the run's databases;
- `versions.json` and `summary.md`.

`recorder-check.mjs` compares the recorder's tags with node-postgres's own `Result.command`.

To cross-check a recorded run's identities and correlations, repetition by repetition:

```sh
node research/transaction-callbacks/laravel/check-run.mjs research/transaction-callbacks/laravel/output/<run id>
```

It needs only the run directory. It checks that:

- the subject is the backend the recorder and the observer saw;
- the observer and the sink are other backends;
- each captured transaction ID matches the server log and the visible markers' `xmin`;
- the callbacks the PHP process saw are the rows in `callback_log`.

Run `ac32a1`: 30 repetitions, 246 checks, none failed. The two earlier runs pass every check whose fields they recorded.

## Discarded first run

The first run on 2026-10-25 used a recorder that parsed the server's stream as if it began untyped, so it recorded no server messages. Its database observations matched the runs above. Its output was deleted before anything cited it. The recorder was then fixed and checked with `recorder-check.mjs` before the two runs above.
