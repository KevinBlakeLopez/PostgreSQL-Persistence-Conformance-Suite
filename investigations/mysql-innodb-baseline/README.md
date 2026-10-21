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

`node src/run-knex.mjs` writes `evidence/knex.json`. `node src/run-lucid.mjs` writes `evidence/lucid.json` and compares it with the Knex file. `node src/run-suite.mjs` executes the case list and writes `evidence/suite.json`. None of these is the PostgreSQL harness. They need `mysql-up.sh` first.

Each step stores the SQL that was sent, the `mysql2` result or error, and a snapshot from a different connection. The snapshot is not treated as something the client knew when `mysql2` returned.
