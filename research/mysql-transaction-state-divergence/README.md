# MySQL lock-wait timeouts and Laravel nested transactions

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max).

**Question.** When MySQL ends a statement with errno 1205 (lock wait timeout) inside a nested `DB::transaction()`, does Laravel 13.38.0 roll the nested unit back? Or does it treat the statement-level rollback as a whole-transaction rollback, drop its savepoint bookkeeping, and let the outer transaction commit the inner writes? The study covers both `innodb_rollback_on_timeout` settings, savepoints, callbacks, and the outer transaction's completion.

**Answer, observed in 3 of 3 repetitions in each of two runs.** With the server default `innodb_rollback_on_timeout=OFF`, Laravel 13.38.0 does not roll a nested `DB::transaction()` back to its savepoint when the failure is errno 1205. It throws `DeadlockException` and runs the inner `afterRollBack` callbacks. If the code around the inner call catches that exception and the outer transaction commits, the inner rows commit too. The same code with a duplicate-key failure is rolled back to the savepoint. Details, controls, mechanism and classification are in [findings.md](findings.md).

This directory is not a PPCS adapter. It does not run `harness/run.mjs` and changes no PostgreSQL case, catalog, schema or recorded result. It does not modify [`investigations/mysql-innodb-baseline/`](../../investigations/mysql-innodb-baseline/README.md). That baseline already recorded the raw InnoDB behavior, and the CodeIgniter 4, mysqli, PDO, Knex and Lucid results; this study reuses the baseline's server image and method, but none of its files.

## Layout

| Path | What it is |
| --- | --- |
| [methodology.md](methodology.md) | Versions, configuration, roles, triggers, observations, controls, repetitions, and what the recorded runs do not show |
| [findings.md](findings.md) | Result matrix, the finding, its mechanism and history, classification, adversarial review, related observations |
| [`repro/`](repro/) | The study: `compose.yaml` and `scripts/` for two disposable MySQL 8.4.11 servers, `run.mjs` (orchestrator and observer, Node), `php/subject.php` (the Laravel and PDO subject), `lib.mjs`, `summarize.mjs` |
| [`output/`](output/) | Recorded runs. `runs.json` is the raw record of every run. `summary.json` comes from `run.mjs`; `matrix.json` and `matrix.md` come from `summarize.mjs` |
| [`upstream/laravel-nested-1205/`](upstream/laravel-nested-1205/) | A minimal standalone reproduction with its recorded output, and notes for an upstream report. Nothing has been filed |

## Recorded runs

| Run | Command | Scenarios | Runs | Matched the stated expectation |
| --- | --- | --- | --- | --- |
| [`2026-10-25T17-03-57Z-e28e5b`](output/2026-10-25T17-03-57Z-e28e5b/matrix.md) | `node run.mjs --scope refined` | the 21 scenario-and-server groups of the refined question | 63 | 63 |
| [`2026-10-25T16-15-42Z-5bd1e8`](output/2026-10-25T16-15-42Z-5bd1e8/matrix.md) | `node run.mjs` | 22 groups: the refined question as it stood then, plus deadlock (1213) scenarios outside it | 66 | 66 |

The second run is the primary record. It was made after the question was narrowed. It adds the outer-rollback control and the `innodb_rollback_on_timeout=ON` variants of three nested controls. The first run was made by an earlier revision of `run.mjs` and `php/subject.php`. That revision lacked those scenarios and the `--scope` option; the scenarios both runs contain have the same code and the same expectations. Its results for those scenarios are the same as the second run's. Its deadlock results are reported separately in findings.md §7 and were not analyzed further.

## Reproduce

From `repro/`, with Docker, Node.js 24, pnpm, PHP 8.5 with `pdo_mysql`, and Composer:

```sh
pnpm install --frozen-lockfile --ignore-scripts
(cd php && composer install --no-interaction --no-scripts)
sh scripts/mysql-up.sh
node run.mjs --scope refined          # about 5 minutes; three repetitions per scenario
node summarize.mjs ../output/<run id>
sh scripts/mysql-down.sh
```

`mysql-up.sh` starts two disposable servers: `mysd-mysql` on `127.0.0.1:13316` with the default `innodb_rollback_on_timeout=OFF`, and `mysd-mysql-rb-timeout` on `127.0.0.1:13317` with it ON. It writes `.mysd-instance.json`, which is gitignored and mode 0600. `run.mjs` refuses a server without the token stored in that file, and every connection, Node and PHP, refuses any port but those two. `node run.mjs --only <id>[,<id>] --reps 1 --out <dir>` runs a subset into another directory.

The standalone reproduction needs only PHP, Composer and a MySQL server; see [`upstream/laravel-nested-1205/README.md`](upstream/laravel-nested-1205/README.md).

## Paths in the record

Recorded files name this directory as `$STUDY`. They contain no absolute local paths, passwords or tokens. `run.mjs` refuses to write a file containing the password or token.
