# What changes if pdo_pgsql rejects the ROLLBACK tag

Recorded 2026-10-25 UTC. Written by: Claude Opus 5.5 (max).

The Stage 4 review predicted an interaction, from Laravel's code path. If pdo_pgsql reported a `COMMIT` answered with `ROLLBACK` as a failure, Laravel's `DB::transaction()` would keep the failed transaction's callbacks, the defect reported as laravel/framework#61964. The next commit on the connection would then run them. This experiment tests that with a locally patched driver. It is not a proposed php-src change.

## Design

- **One PHP binary, two driver builds.**
  - PHP 8.5.12 is built from the php.net release tarball, checksum verified, with only the extensions the scenarios need.
  - pdo_pgsql is built twice from that tarball's `ext/pdo_pgsql`, as a shared module, with `phpize`, against that PHP and Homebrew's libpq 18.6. One build is unchanged (`stock.so`). The other has [`pdo_pgsql-reject-rollback-tag.patch`](pdo_pgsql-reject-rollback-tag.patch) applied (`patched.so`).
  - [`build.sh`](build.sh) reproduces all of it.
- **The patch** changes only `pgsql_handle_commit()`. When `COMMIT` succeeds at the protocol level (`PGRES_COMMAND_OK`) but its command tag is `ROLLBACK`, the patched driver records an error and returns `false`. It follows pdo_pgsql's existing convention for a failure without a server SQLSTATE: SQLSTATE `HY000`, error code 7 (`PGRES_FATAL_ERROR`), and an explicit message, "COMMIT was answered with ROLLBACK: the transaction was rolled back". The code after it is unchanged: it recomputes `in_txn` from the server's status on failure, and closes large-object streams on success.
- **The scenarios are the unchanged matrix** in [`../laravel/`](../laravel/README.md). [`run.mjs`](../laravel/run.mjs) takes another PHP through `CB_PHP` and `CB_PHP_ARGS`, and records the build's label and the module's sha256 in `versions.json`.
- **The control.** `stock.so` on this PHP must reproduce the run made with Homebrew's PHP, `2026-10-25T06-05-06Z-ac32a1`, row for row.

## Result

| Run | Driver build | Rows equal to `ac32a1` | `check-run.mjs` |
| --- | --- | --- | --- |
| [`2026-10-25T14-05-31Z-046a1a`](../laravel/output/2026-10-25T14-05-31Z-046a1a/summary.md) | stock | all 10 | 246 checks, none failed |
| [`2026-10-25T14-05-44Z-b6ce5c`](../laravel/output/2026-10-25T14-05-44Z-b6ce5c/summary.md) | patched | 7 of 10 | 246 checks, none failed |

Every scenario ran three times in both runs, and every repetition agreed. Exactly the three scenarios that reach the `ROLLBACK` tag changed:

| Scenario | Stock driver | Patched driver |
| --- | --- | --- |
| `pdo.caught-error` | `commit()` returned `true` | `commit()` raised `PDOException` `HY000` |
| `laravel.caught-error` | `DB::transaction()` returned. `afterCommit` ran at once. Manager empty | `DB::transaction()` raised the driver's `PDOException` `HY000`. No callback ran. The manager kept **1 pending record**. The next transaction committed, and then **the aborted transaction's `afterCommit` ran**, followed by the new transaction's own |
| `laravel.explicit-caught-error` | `DB::commit()` returned. `afterCommit` ran at once | `DB::commit()` raised. No callback ran. The manager still held 1 pending record when the process ended (this scenario runs no later transaction) |

In `laravel.caught-error` repetition 1 of the patched run, the server log shows the order:

- **14:05:45.149:** xid 962 hits the unique violation.
- **.154:** its `COMMIT` is answered with `ROLLBACK`, and the patched driver raises.
- **.165:** an unrelated transaction, xid 963, commits on the same connection.
- **.166:** the sink inserts xid 962's `afterCommit` row.

`pg_xact_status()` for xid 962 stayed `aborted`.

These scenarios are unchanged: the healthy commit, the escaped exception, savepoint recovery, both deferred-FK scenarios, `pdo.commit` and `pdo.deferred-fk`.

**So fixing the driver alone does not remove the wrong side effect.** In a process that commits again on the same connection, it moves it from the failed transaction's end to the next commit. Two fixes are needed for correct callbacks: the driver must report the rollback, and Laravel must discard the failed transaction's callbacks when `COMMIT` raises (#61964). Laravel's branch does not depend on the SQLSTATE the driver chooses. `ConcurrencyErrorDetector` in 13.38.0 treats only `40001`, or deadlock and lock-timeout messages, as retryable, and the patch's message contains none of `LostConnectionDetector`'s phrases. So `HY000`, `25P02` and `40000` all take the same rethrow path (source reading).

## Connection state after the failed commit

[`state-after-failure.php`](state-after-failure.php) records what PDO reports after `commit()`, for four endings, under each build. Its output was identical in three runs per build ([`output/`](output/)). The two builds differ in one place only:

| Ending | Stock `commit()` | Patched `commit()` | Afterwards, both builds |
| --- | --- | --- | --- |
| healthy | `true` | `true` | `inTransaction()` false; `rollBack()` raises "There is no active transaction"; the next transaction commits |
| savepoint recovery | `true`, row committed | `true`, row committed | same |
| `ROLLBACK` tag | `true`, row absent; `errorInfo()` holds the caught statement's `23505` | raises `HY000`; `errorInfo()` `[HY000, 7, "COMMIT was answered with ROLLBACK: ..."]` | same |
| deferred FK | raises `23503` | raises `23503` | same |

With the patch, a `COMMIT` answered with `ROLLBACK` leaves PDO in exactly the state that a `COMMIT` failing with an error already leaves it in. The connection is out of its transaction, it can begin a new one, and `rollBack()` reports that there is nothing to roll back.

## Run it

```sh
sh research/transaction-callbacks/patched-driver/build.sh /tmp/pdo-pgsql-build
sh research/transaction-callbacks/tools/container.sh up
CB_PHP=/tmp/pdo-pgsql-build/php/bin/php CB_PHP_ARGS="-n -dextension=/tmp/pdo-pgsql-build/patched.so" \
  CB_DRIVER_LABEL=patched node research/transaction-callbacks/laravel/run.mjs --repeat=3
```

Replace `patched.so` with `stock.so` for the control. `state-after-failure.php` reads libpq's `PG*` environment variables, like the reproductions in [`../repro/`](../repro/):

```sh
/tmp/pdo-pgsql-build/php/bin/php -n -dextension=/tmp/pdo-pgsql-build/patched.so research/transaction-callbacks/patched-driver/state-after-failure.php
```

The recorded runs used builds made by hand with the same configure options and the same patch. Their `versions.json` gives each module's path in this study's scratch area, and its sha256. `build.sh`, run from scratch on 2026-10-25, produced a patched `pgsql_driver.c` byte-identical to the one those builds used. Its two modules produced the same `state-after-failure.php` output as the recorded runs. Their sha256 values differ from the recorded ones, because the build directory is compiled into a module.
