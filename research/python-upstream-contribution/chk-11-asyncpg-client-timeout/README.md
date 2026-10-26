# CHK-11: a caught client-side timeout, then asyncpg's transaction API

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Question.** PY-2 in [the tracker](../../python-upstream-contribution-tracker.md) ([asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400)) was filed with a caught `23505`. Does a caught client-side timeout take the same path? There are three ways to set one: asyncpg's `timeout=` argument, the connection's `command_timeout`, and `asyncio.wait_for()`.

- asyncpg's own `test_timeout_06` suggests it does, from source reading.
- The gap analysis's P6 ran only a server-side `statement_timeout`, where `57014` reaches the code as a database error.

**Answer (observed, 6 of 6 runs per arm: three on asyncio, three on uvloop).** Yes.

- In all three ways, the code gets `TimeoutError`, the server cancels the statement (`57014`, "canceling statement due to user request"), and the transaction is aborted.
- If the code catches the `TimeoutError`:
  - `async with con.transaction()` exits normally;
  - `Transaction.commit()` returns `None`;
  - a raw `execute('COMMIT')` returns `'ROLLBACK'`;
  - asyncpg records the transaction as committed.
- The row written before the timeout is gone.

## Each arm

Each arm inserts a marker row in a transaction, then runs `select pg_sleep(10)` under a 0.2 s client-side timeout, then finishes the transaction the arm's way. Each arm uses its own connection.

| Arm | What asyncpg reported | PostgreSQL |
| --- | --- | --- |
| `managed`: `async with con.transaction()`, `fetch(timeout=0.2)` caught inside | `TimeoutError` caught; the block exited normally; a later `rollback()` raised "the transaction is already committed" | `57014`, then `COMMIT;`; `aborted`; marker absent |
| `explicit`: `tr.start()`, the same, `tr.commit()` | `commit()` returned `None`; a later `rollback()` raised "already committed" | The same |
| `raw`: `execute('BEGIN')`, the same, `execute('COMMIT')` | Returned `'ROLLBACK'` | The same |
| `command_timeout`: `connect(command_timeout=0.2)`, `fetch()` with no argument | As `managed` | The same |
| `wait_for`: `asyncio.wait_for(con.fetch(...), 0.2)` | As `managed` | The same |
| Control `control_savepoint`: the timed-out `fetch()` inside a nested `con.transaction()`, caught outside it | The block exited normally; "already committed" | `SAVEPOINT`, `57014`, `ROLLBACK TO`, `COMMIT;`; `committed`; marker visible |
| Control `control_fast`: `fetch(timeout=5)` of `select pg_sleep(0.01)` | No error; "already committed" | `committed`; marker visible |
| Control `control_uncaught`: the `TimeoutError` not caught | The block raised `TimeoutError`; a later `rollback()` raised "already rolled back" | `57014`, then `ROLLBACK;`; `aborted`; marker absent |

## Agreement

- **Three sources agree for all 48 transactions** (`output/log-check.txt`). They are the program's witness connection, `psql` inside the container (36 `aborted`, 12 `committed`, `output/psql-xact-status.txt`), and the server's statement log.
- **The server log, per subject session.** It shows the cancelled statement's `57014` and then `COMMIT;`, both carrying the transaction ID the program printed.
  - The `COMMIT;` line's virtual transaction ID has local part 0, for example `5/0` after `5/2`. PostgreSQL resets it when it aborts the transaction, so the server had already aborted when `COMMIT` arrived.
  - The committed controls keep their virtual transaction ID.
- **The SQLSTATE is inferred.** "57014" here, and "57014x1" in `log-check.txt`, mean the logged message "canceling statement due to user request". PostgreSQL raises that message with `ERRCODE_QUERY_CANCELED` (57014), but the log prefix had no `%e`, so the code itself was not logged. asyncpg's `TimeoutError` does not carry it.
- **The outputs.** With the transaction IDs and the first line masked, all six outputs are identical. The first line names the event loop.
- **The files.** The program, the runner and its helper have the same SHA-256 before and after the runs.

## Apparatus incident

The first cross-check, `log_check.v1.py` (output `output/log-check.v1.txt`), required one virtual transaction ID per transaction. It therefore flagged all 36 aborted sessions as disagreeing.

The log shows why. The `COMMIT;` of an aborted transaction carries the same `%x` transaction ID, but its `%v` local part is 0. The corrected `log_check.py` changes two things:

- it requires the backend part of the virtual transaction ID to stay constant;
- it requires the final statement's local part to be 0 exactly when the transaction aborted.

The data did not change. Both versions and both outputs are kept.

## Environment

| Item | Value |
| --- | --- |
| Packages | asyncpg 0.32.0 and uvloop 0.23.0, the latest releases on PyPI on 2026-10-26, installed with `pip install --only-binary=:all:` into a fresh virtualenv (`versions-pip.txt`) |
| Python | 3.13.11 (Homebrew), macOS 26.6.2 arm64 |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. A throwaway container on `127.0.0.1:55498`, with tmpfs, a random password and a random `cluster_name` token. The token was checked through the host port before the runs, and the container was removed after them. Not `ppcs-postgres`. Settings: CHK-2's (`max_connections=100`, `log_lock_waits=on`, `deadlock_timeout=1s`, `log_statement=all`), with `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '` (`output/server-settings.txt`) |
| Docker | colima 0.9.1, Docker server 28.4.0 (`output/env.txt`) |

## Commands

```sh
bash run.sh <venv>/bin/python      # container, token check, three runs per event loop, psql fates, server log, removal
python -I log_check.py output      # cross-check
```

`run.sh` refuses to start if its container name or port is already in use, and it removes the container on exit.

## Files

- `asyncpg_client_timeout.py`: the arms. Run as `python asyncpg_client_timeout.py [asyncio|uvloop]` with `DATABASE_URL` set. It creates database `asyncpg_client_timeout` and drops it at the end.
- `run.sh` and `wait_for_server.py`: the runner, and its readiness and token check.
- `log_check.py` (and `log_check.v1.py`, superseded): the cross-check.
- `output/{asyncio,uvloop}.rep{1,2,3}.out`: complete stdout and stderr of the six runs. Every run exited 0 (`output/exit-codes.txt`).
- `output/server.log`: the server's complete log (`docker logs`), from initialisation to the `psql` check.
- `output/psql-xact-status.txt`, `output/server-settings.txt`, `output/env.txt`, `output/log-check.txt`, `output/log-check.v1.txt`.
- `SHA256SUMS`: every file except this README and itself.

## Limits

- **Not run:**
  - `asyncio.timeout()`;
  - a pool (`create_pool`): the arms use `asyncpg.connect()`;
  - SQLAlchemy or Tortoise on top. CHK-10 covers SQLAlchemy's asyncio engine, for a caught `23505`;
  - older releases.
- **Nothing runs after the catch.** The arms catch the timeout and send nothing else before committing. A later statement would fail loudly with `InFailedSQLTransactionError` (25P02).
- **The cancel always lands mid-statement.** The timeout fires 0.2 s into a 10 s sleep. A statement that finishes just as the timeout fires was not tested.
