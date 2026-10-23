# MySQL 8.4 / InnoDB transaction baseline

Standalone experiments for a possible MySQL Persistence Conformance suite. They drive `mysql2` directly and read the server from a second connection.

This directory is not a PPCS adapter. It does not run `harness/run.mjs`, and it does not change PostgreSQL cases, adapters, or containers. A passing run here does not mean MySQL PCS is implemented. The investigation is in [REPORT.md](REPORT.md). The measured expectations are in [catalog/README.md](catalog/README.md). That catalog is not loaded by the PostgreSQL runner.

## Reproduce

From this directory, with Docker and Node.js 24:

```sh
pnpm install --frozen-lockfile --ignore-scripts
sh scripts/mysql-up.sh
node src/run-all.mjs
sh scripts/mysql-down.sh
```

`mysql-up.sh` starts two disposable servers and writes `.mpcs-instance.json` (gitignored, mode `0600`). `run-all.mjs` refuses a server that does not contain the token in that file. `mysql-down.sh` removes the containers and the instance file.

The recorded run that this report quotes finished at `2026-10-19T13:49:36.491Z`. Evidence is in `evidence/`.

## What the servers are

| | Default | `innodb_rollback_on_timeout` |
| --- | --- | --- |
| Image | `mysql:8.4.11@sha256:24989179f58856db763f418010c1169fecc944e3ec1ea7e921572d83eb070f70` | same image |
| Container | `mpcs-baseline-mysql` | `mpcs-baseline-mysql-rb-timeout` |
| Port | `127.0.0.1:13306` | `127.0.0.1:13307` |
| Extra server argument | none | `--innodb-rollback-on-timeout=ON` |
| Data directory | tmpfs `/var/lib/mysql` (1g) | same |

Compose project name: `mpcs-baseline`. File: `compose.yaml` in this directory, not the repository root `compose.yaml`.

Initialization is the official image entrypoint on an empty tmpfs: `MYSQL_DATABASE=mpcs`, user `mpcs`, random passwords, `MYSQL_ROOT_HOST=%` so the observer on the host can connect. After the entrypoint, `mysql-up.sh` stores a random token in `mpcs_meta.instance`. The runner then enables `events_transactions_history_long` if it is off. That consumer is off in the image; `events_transactions_current` and `events_transactions_history` are already on. Enabling the long consumer does not change InnoDB rollback behavior. The image defaults are in `evidence/server-config.json` under `transaction_consumers_before`.

## Experiments

| File | What it runs |
| --- | --- |
| `src/mpcs-01.mjs` | Duplicate key, then `COMMIT`, with and without another insert |
| `src/mpcs-02.mjs` | Two-connection deadlock, three repetitions |
| `src/mpcs-03.mjs` | Lock-wait timeout at 50s and at 2s, and the same wait with rollback-on-timeout |
| `src/mpcs-04.mjs` | Savepoint rollback, release, and a missing savepoint |
| `src/mpcs-05.mjs` | `COMMIT` / `ROLLBACK` result shape, `KILL`, and a local socket close |
| `src/probes.mjs` | Implicit commit, DDL, isolation, `GET_LOCK`, outer rollback |
| `src/run-knex.mjs` | Knex 3.3.0 beside a careful and a careless mysql2 control |
| `src/run-lucid.mjs` | Lucid 22.4.2 `db.transaction(callback)` on the same three cases |
| `src/run-lost-commit.mjs` | Drops the server's COMMIT OK packet after the server has sent it |
| `src/run-php-mx01.mjs` | mysqli, PDO MySQL, and CodeIgniter 4 MySQLi on the duplicate-key case. Writes `evidence/php-mx01.json`. Does not replace `evidence/suite.json`. |
| `src/run-php-concurrency.mjs` | The same three clients on deadlock and lock-wait timeout. Node holds the other session. Writes `evidence/php-concurrency.json`. |
| `src/run-php-update-batch.mjs` | CodeIgniter 4.7.5 `updateBatch()` after `where()`, on a synthetic table. Writes `evidence/php-update-batch.json`. |
| `src/run-php-connection.mjs` | mysqli, PDO, and CodeIgniter after a killed connection and after `wait_timeout`. Writes `evidence/php-connection.json`. |
| `src/run-php-nested.mjs` | CodeIgniter nested transaction depth beside a mysqli `SAVEPOINT`. Writes `evidence/php-nested.json`. |
| `src/run-php-ddl.mjs` | mysqli and a CodeIgniter migration that applies DDL and then fails. Writes `evidence/php-ddl.json`. |
| `src/run-php-model.mjs` | CodeIgniter Model `allowedFields`, and a Model update inside a failed transaction. Writes `evidence/php-model.json`. |

The PHP subject is [`php/README.md`](php/README.md). Install it with `composer install --no-interaction --no-scripts` from that directory, then `node src/run-php-mx01.mjs` or `node src/run-php-concurrency.mjs`. The servers still come from `scripts/mysql-up.sh`. The duplicate-key run finished `2026-10-21T17:15:26.400Z`. The deadlock and lock-wait run finished `2026-10-21T17:44:17.623Z`. The connection-loss run finished `2026-10-21T19:27:50.163Z`. The nested-transaction run finished `2026-10-21T19:39:28.598Z`. The DDL run finished `2026-10-21T20:04:32.993Z`. The Model run finished `2026-10-21T20:17:38.862Z`. A score is whether a pre-stated expectation held. It is not a defect verdict, and these files do not replace the mysql2 evidence already in `evidence/`.

`node src/run-knex.mjs` writes `evidence/knex.json`. `node src/run-lucid.mjs` writes `evidence/lucid.json` and compares it with the Knex file. `node src/run-suite.mjs` executes the case list and writes `evidence/suite.json`. None of these is the PostgreSQL harness. They need `mysql-up.sh` first.

Each step stores the SQL that was sent, the `mysql2` result or error, and a snapshot from a different connection. The snapshot is not treated as something the client knew when `mysql2` returned.
