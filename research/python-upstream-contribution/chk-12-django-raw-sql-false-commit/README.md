# CHK-12: a raw-SQL error caught inside Django's `atomic()`, then Django's commit

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Question.** PY-10 in [the tracker](../../python-upstream-contribution-tracker.md) closed Django's `atomic()` and `on_commit` as not a defect: when an ORM write fails inside `atomic()`, Django rolls the transaction back by itself. Django's `atomic()` ends in psycopg 3's `Connection.commit()`. That call returns normally when PostgreSQL answers `COMMIT` with `ROLLBACK` (PY-1a, [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453)).

So what happens when the caught error comes from raw SQL (`connection.cursor()`) instead? Does Django commit, and does it run its `on_commit` callbacks? And what changes when `ATOMIC_REQUESTS` makes the request the transaction?

Django's documentation leaves this case open: "If you catch exceptions raised by raw SQL queries, Django's behavior is unspecified and database-dependent" (`docs/topics/db/transactions.txt` on `stable/6.1.x`, lines 187–188, under "Avoid catching exceptions inside `atomic`!").

**Answer (observed, 3 of 3 runs per arm).** In two of the three setups, Django reports the commit.

- **`atomic()` in the view, or `ATOMIC_REQUESTS` alone.** After a caught raw-SQL error:
  - Django sends `COMMIT`;
  - psycopg 3's `commit()` returns normally;
  - the `on_commit` callback runs;
  - the view returns 200.

  PostgreSQL had already aborted the transaction, and the order is gone.
- **`atomic()` in the view under `ATOMIC_REQUESTS`.** There, `atomic()` is a savepoint. Django's `RELEASE SAVEPOINT` gets `25P02`, and the request returns 500.
- **The ORM helper.** In all three setups, Django sends `ROLLBACK` by itself and does not run `on_commit`. The view still returns 200, and the order is gone.

**Why the helpers differ** (from reading Django 6.1.2's source):
- `Model.save_base()` (`django/db/models/base.py:987`) runs the write inside `transaction.mark_for_rollback_on_error()` (`django/db/transaction.py:112`).
- That context manager sets `connection.needs_rollback` when the write raises inside an atomic block.
- A raw cursor does not go through it, so `atomic()` commits.

## The view

Each arm sends one request through Django's request handling. The view does four things:

1. creates an order (`Order.objects.create()`);
2. reads `pg_current_xact_id()`;
3. registers an `on_commit` callback;
4. records an analytics event through a best-effort helper, which catches `DatabaseError` and logs it.

The helper uses the ORM (`Event.objects.create()`) or raw SQL:

```python
def record_event_sql(name, **props):
    """The same helper, in raw SQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into shop_event (name, props) values (%s, %s::jsonb)",
                [name, json.dumps(props)],
            )
    except DatabaseError as e:
        log.warning("could not record event %s: %s", name, e)
```

The event name either fits `shop_event.name` (`varchar(32)`), or it is 35 characters long and fails with `22001`. Nothing is sent between the caught error and the end of the transaction.

## Each arm

| Arm | Setup | Helper | Event name | Django | `on_commit` | PostgreSQL |
| --- | --- | --- | --- | --- | --- | --- |
| `atomic.orm.ok` | `ATOMIC_REQUESTS` off, `atomic()` in the view | ORM | fits | 200 | ran | `COMMIT`; `committed`; order visible |
| `atomic.orm.long` | The same | ORM | too long | 200 | did not run | `22001`, then `ROLLBACK`; `aborted`; order absent |
| `atomic.sql.ok` | The same | raw SQL | fits | 200 | ran | `COMMIT`; `committed`; order visible |
| `atomic.sql.long` | The same | raw SQL | too long | 200 | **ran** | `22001`, then `COMMIT`; `aborted`; order absent |
| `nested.orm.ok` | `ATOMIC_REQUESTS` on, `atomic()` in the view (a savepoint) | ORM | fits | 200 | ran | `committed`; order visible |
| `nested.orm.long` | The same | ORM | too long | 200 | did not run | `22001`, `ROLLBACK TO SAVEPOINT`, then `COMMIT`; `committed`; order absent |
| `nested.sql.ok` | The same | raw SQL | fits | 200 | ran | `committed`; order visible |
| `nested.sql.long` | The same | raw SQL | too long | 500, `InternalError: current transaction is aborted…` | did not run | `22001`; `RELEASE SAVEPOINT` fails with `25P02`; `ROLLBACK TO SAVEPOINT`, then `ROLLBACK`; `aborted`; order absent |
| `request.orm.ok` | `ATOMIC_REQUESTS` on, no `atomic()` in the view | ORM | fits | 200 | ran | `committed`; order visible |
| `request.orm.long` | The same | ORM | too long | 200 | did not run | `22001`, then `ROLLBACK`; `aborted`; order absent |
| `request.sql.ok` | The same | raw SQL | fits | 200 | ran | `committed`; order visible |
| `request.sql.long` | The same | raw SQL | too long | 200 | **ran** | `22001`, then `COMMIT`; `aborted`; order absent |

In `nested.orm.long`, a `committed` transaction with no order is expected. The order was written inside the savepoint that Django rolled back, and then the request's transaction committed.

## Agreement

- **Three fates agree for all 36 transactions** (`output/log-check.txt`):
  - the program's witness connection;
  - `psql` inside the container: 15 `aborted`, 21 `committed` (`output/psql-xact-status.txt`);
  - the server's statement log.
- **The server log's fate.** When PostgreSQL aborts a transaction, the local part of its virtual transaction ID becomes 0 (CHK-11's log check established this).
  - A final `COMMIT` or `ROLLBACK` with local part 0 therefore arrived after the abort. In the first run of `atomic.sql.long`, the `22001` is logged at `vxid=13/3 xid=758`, and the `COMMIT` at `vxid=13/0 xid=758`.
  - Otherwise, a final `COMMIT` means committed, and a final `ROLLBACK` means aborted.
  - In the `nested` arms the error happens inside a savepoint. Only the subtransaction aborts, so the final statement keeps its virtual transaction ID.
- **The SQLSTATEs are logged,** with `%e` in the log prefix: `22001` and `25P02`.
- **The hypothesis was fixed before the runs.**
  - It is in `log_check.py`, and it held for every arm, 3 of 3.
  - `output/hashes-before.txt` has the SHA-256 of `log_check.py`, the program, the runner and its helper from before the runs, and `output/hashes-after.txt` is identical.
- **The outputs.** With the transaction IDs masked, the three outputs of each mode are identical.

## What this does not change

- **PY-10 stays closed.** Django documents a caught raw-SQL error inside `atomic()` as unspecified. The false report comes from psycopg 3's `Connection.commit()`, which Django calls (PY-1a).
- **No report to Django.** PY-1a's proposed action stands: nothing beyond PY-1b.

## Environment

| Item | Value |
| --- | --- |
| Packages | Django 6.1.2 and psycopg 3.3.6, with `psycopg-binary`. These were the latest releases on PyPI on 2026-10-26, installed with `pip install --only-binary=:all:` into a fresh virtualenv (`versions-pip.txt`). Django used its psycopg 3 backend |
| Python | 3.13.11 (Homebrew), macOS 26.6.2 arm64 |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. A throwaway container on `127.0.0.1:55499`, not `ppcs-postgres` (details below) |
| Docker | colima 0.9.1, Docker server 28.4.0 (`output/env.txt`) |

**The container:**
- tmpfs storage, a random password and a random `cluster_name` token;
- the token was checked through the host port before the runs;
- the container was removed after the runs;
- settings: CHK-11's, with `sqlstate=%e` added to `log_line_prefix` (`output/server-settings.txt`).

## Commands

```sh
bash run.sh <venv>/bin/python      # container, token check, three runs per mode, psql fates, server log, cross-check, removal
python -I log_check.py output      # the cross-check alone
```

`run.sh` refuses to start if its container name or port is already in use, and it removes the container on exit.

## Files

- `django_raw_sql.py`: the view, the helpers and the arms. Run it as `python django_raw_sql.py off|on` (the `ATOMIC_REQUESTS` setting), with `DATABASE_URL` set. It creates database `django_raw_sql` and drops it at the end.
- `run.sh` and `wait_for_server.py`: the runner, and its readiness and token check.
- `log_check.py`: the cross-check and the hypothesis.
- `output/{off,on}.rep{1,2,3}.out`: the complete stdout and stderr of the six runs. Every run exited 0 (`output/exit-codes.txt`).
- `output/server.log`: the server's complete log (`docker logs`), from initialisation to the `psql` check.
- `output/psql-xact-status.txt`, `output/server-settings.txt`, `output/env.txt`, `output/log-check.txt`, `output/hashes-before.txt`, `output/hashes-after.txt`.
- `versions-pip.txt`.
- `SHA256SUMS`: every file except this README and itself.

## Limits

- **Django's request handling, not a web server.** Requests go through `django.test.Client`. It runs Django's handler and `ATOMIC_REQUESTS`, but no WSGI or ASGI server is involved.
- **Connections close after each request.** The test client does not close the connection at the end of a request, so the program closes it after each one.
- **Not run:**
  - Django on psycopg2;
  - async views;
  - Django's connection pool (`OPTIONS["pool"]`) and persistent connections (`CONN_MAX_AGE`);
  - `server_side_binding`;
  - `on_commit(robust=True)`;
  - older Django releases.
- **One error type.** Only `22001` was raised here.
- **Nothing runs after the caught error.** A later statement in the same transaction would fail with `25P02`, and Django would raise.
