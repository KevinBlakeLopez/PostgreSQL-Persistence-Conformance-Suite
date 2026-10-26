# CHK-9: psycopg2's false commit, directly and through SQLAlchemy

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Question.** PY-1a in [the tracker](../../python-upstream-contribution-tracker.md) ([psycopg#1453](https://github.com/psycopg/psycopg/issues/1453)) is psycopg 3's `commit()` returning normally when PostgreSQL answers `COMMIT` with `ROLLBACK`. [The roadmap](../../python-upstream-contribution-roadmap.md) (§9) judged that psycopg2 behaves the same, without running it. Does it, directly and through SQLAlchemy Core and ORM, on the latest releases?

**Answer (observed, 3 of 3 runs, every arm identical across runs).** Yes. psycopg2's `commit()` and its `with conn:` block return normally, SQLAlchemy Core's `commit()` and `engine.begin()` return normally, and the ORM's `session.commit()` and `sessionmaker.begin()` return normally and run `after_commit`. In every case the server log shows `COMMIT` sent, the witness finds the row absent, and `psql` reads the transaction `aborted`. The ORM flush path is the exception: it raises `PendingRollbackError` and sends `ROLLBACK`.

## Each arm

In one transaction: write row X; run an insert that fails with a duplicate key (23505), which the code catches and ignores; commit through the API under test. PostgreSQL has aborted the transaction at the failed insert, so it keeps nothing.

| Arm | API result | Driver status before commit | Events | Row X | `pg_xact_status` (witness and psql) |
| --- | --- | --- | --- | --- | --- |
| `p2-raw-commit` | `conn.commit()` returned normally | `INERROR` | — | absent | aborted |
| `p2-raw-with` | `with conn:` exited normally | `INERROR` | — | absent | aborted |
| `p2-raw-sql-commit` | `cur.execute("COMMIT")`: status `ROLLBACK` | `INERROR` | — | absent | aborted |
| `p2-core-connect-commit` | `conn.commit()` returned normally; `in_transaction()` True before | `INERROR` | `ConnectionEvents.commit` | absent | aborted |
| `p2-core-engine-begin` | `with engine.begin()` exited normally | `INERROR` | `ConnectionEvents.commit` | absent | aborted |
| `p2-orm-execute-commit` | `session.commit()` returned normally (failing statement via `session.execute()`) | `INERROR` | `commit`, `after_commit` | absent | aborted |
| `p2-orm-sessionmaker-begin` | `with sessionmaker.begin()` exited normally | `INERROR` | `commit`, `after_commit` | absent | aborted |
| `p2-orm-flush-control` | `session.commit()` raised `PendingRollbackError`; `ROLLBACK` sent | — | `rollback`, `after_rollback`, `after_soft_rollback` | absent | aborted |
| `p2-core-no-error-control` | returned normally | `INTRANS` | `ConnectionEvents.commit` | present | committed |
| `p3-raw-commit`, `p3-raw-sql-commit`, `p3-core-connect-commit`, `p3-orm-execute-commit` (psycopg 3, positive controls) | as the psycopg2 arms; `COMMIT` status `ROLLBACK` | `INERROR` | as above | absent | aborted |

The server-side sequence for every false-commit arm is `BEGIN | insert | select xid | insert | ERROR 23505 | COMMIT` (`output/summary.txt`). `psql` read 36 transactions `aborted` and the 3 control transactions `committed` (`output/psql-xact-status.txt`).

## Environment

| Item | Value |
| --- | --- |
| Packages | SQLAlchemy 2.1.6, psycopg2-binary 2.9.13 (libpq 17.0.11), psycopg 3.3.6 with psycopg-binary 3.3.6 (libpq 18.0.6): the latest releases on PyPI on 2026-10-26, installed with `pip install --only-binary=:all:` into a fresh virtualenv (`versions-pip.txt`) |
| Python | 3.13.11 (Homebrew), macOS arm64 |
| Server | PostgreSQL 18.6, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, a throwaway container on `127.0.0.1:55463` with a random password and `cluster_name`, removed after the runs; `log_statement=all`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '` (`output/server-settings.txt`) |

## Files

- `false_commit.py`: the arms; one JSON document per run. `run.py`: three runs, one process each, and the server-log extract (lines whose `application_name` starts with `fc-`). `analyze.py`: one block per arm, compared across runs.
- `output/rep{1,2,3}.json`, `.stderr` (empty), `.exit` (0); `output/server-log-extract.txt`; `output/psql-xact-status.txt`; `output/summary.txt`.

## Limits

- Not run: Django on psycopg2 (its `atomic()` handles errors in the ORM paths, PY-10; manual commits and raw cursors were not run here), the asyncio engine, asyncpg through SQLAlchemy, older driver or SQLAlchemy versions.
- The arms catch the error and run nothing else before committing. Any later statement would fail loudly with 25P02, "current transaction is aborted".
