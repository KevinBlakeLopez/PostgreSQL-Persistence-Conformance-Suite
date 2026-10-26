# CHK-10: the false commit through SQLAlchemy's asyncio engine on asyncpg

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Question.** PY-2 in [the tracker](../../python-upstream-contribution-tracker.md) ([asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400)) is asyncpg's `Transaction.commit()` and `async with conn.transaction()` reporting success when PostgreSQL answers `COMMIT` with `ROLLBACK`. Its reach into SQLAlchemy's asyncio engine rested on source reading only ([the roadmap](../../python-upstream-contribution-roadmap.md), §3.2 B: the adapter calls `Transaction.commit()` and never sees the status). Does the false commit reach SQLAlchemy's async Core and ORM on asyncpg, on the latest releases?

**Answer (observed, 3 of 3 runs, every arm identical across runs).** Yes. `AsyncConnection.commit()` and `async with engine.begin()` return normally, and `AsyncSession.commit()` and `async_sessionmaker.begin()` return normally and run `after_commit`. In every case the server log shows `COMMIT` sent, the witness finds the row absent, and `psql` reads the transaction `aborted`. A failed ORM flush raises `PendingRollbackError` and sends `ROLLBACK`. The same holds for SQLAlchemy's async engine on psycopg 3.

## Each arm

The same arms as [CHK-9](../chk-9-psycopg2-false-commit/README.md): in one transaction, write row X; run an insert that fails with a duplicate key (23505), which the code catches and ignores; commit through the API under test.

| Arm | API result | Driver status before commit | Events | Row X | `pg_xact_status` (witness and psql) |
| --- | --- | --- | --- | --- | --- |
| `ap-raw-transaction-block` (asyncpg, positive control) | `async with conn.transaction()` exited normally | `is_in_transaction()` True | — | absent | aborted |
| `ap-raw-start-commit` (positive control) | `Transaction.commit()` returned normally | `is_in_transaction()` True | — | absent | aborted |
| `ap-raw-sql-commit` | `conn.execute("COMMIT")` returned status `ROLLBACK` | `is_in_transaction()` True | — | absent | aborted |
| `ap-core-connect-commit` | `AsyncConnection.commit()` returned normally; `in_transaction()` True before | `is_in_transaction()` True | `ConnectionEvents.commit` | absent | aborted |
| `ap-core-engine-begin` | `async with engine.begin()` exited normally | `is_in_transaction()` True | `ConnectionEvents.commit` | absent | aborted |
| `ap-orm-execute-commit` | `AsyncSession.commit()` returned normally (failing statement via `session.execute()`) | `is_in_transaction()` True | `commit`, `after_commit` | absent | aborted |
| `ap-orm-sessionmaker-begin` | `async with async_sessionmaker.begin()` exited normally | `is_in_transaction()` True | `commit`, `after_commit` | absent | aborted |
| `ap-orm-flush-control` | `AsyncSession.commit()` raised `PendingRollbackError`; `ROLLBACK` sent | — | `rollback`, `after_rollback`, `after_soft_rollback` | absent | aborted |
| `ap-core-no-error-control` | returned normally | `is_in_transaction()` True | `ConnectionEvents.commit` | present | committed |
| `pa-core-connect-commit`, `pa-orm-execute-commit` (SQLAlchemy async on psycopg 3) | as the asyncpg arms | `INERROR` | as above | absent | aborted |

asyncpg exposes no public "in error" transaction status: `is_in_transaction()` is True both inside a healthy and an aborted transaction, and its protocol's `xact_status` is not readable from Python. The server-side sequence for every false-commit arm is `BEGIN | insert | select xid | insert | ERROR 23505 | COMMIT` (`output/summary.txt`). `psql` read 30 transactions `aborted` and the 3 control transactions `committed` (`output/psql-xact-status.txt`).

## Environment

| Item | Value |
| --- | --- |
| Packages | SQLAlchemy 2.1.6, asyncpg 0.32.0, greenlet 3.5.6, psycopg 3.3.6 with psycopg-binary 3.3.6 (libpq 18.0.6): the latest releases on PyPI on 2026-10-26, installed with `pip install --only-binary=:all:` into a fresh virtualenv (`versions-pip.txt`) |
| Python | 3.13.11 (Homebrew), macOS arm64; `asyncio` event loop |
| Server | PostgreSQL 18.6, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, a throwaway container on `127.0.0.1:55463` with a random password and `cluster_name`, removed after the runs; `log_statement=all`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '` (`output/server-settings.txt`) |

## Files

- `false_commit_async.py`: the arms; one JSON document per run. `run.py`: three runs, one process each, and the server-log extract (lines whose `application_name` starts with `fc-`). `analyze.py`: one block per arm, compared across runs.
- `output/rep{1,2,3}.json`, `.stderr` (empty), `.exit` (0); `output/server-log-extract.txt`; `output/psql-xact-status.txt`; `output/summary.txt`.

## Limits

- Not run: uvloop, older driver or SQLAlchemy versions, FastAPI itself (the arms use SQLAlchemy directly, as a FastAPI dependency would).
- The arms catch the error and run nothing else before committing. Any later statement would fail loudly with 25P02, "current transaction is aborted".
