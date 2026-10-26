# CHK-16: Procrastinate's queueing lock inside the caller's transaction

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Question.** [Procrastinate](https://github.com/procrastinate-org/procrastinate) is a PostgreSQL job queue: 1,433 GitHub stars, and about 1.9 million PyPI downloads in the month to 2026-10-26. That count includes CI.

It supports inserting a job inside the caller's transaction. Its Django integration does so by default, because its connector runs on Django's connection. Its external-connection API does so through `configure(connection=conn)`.

A queueing lock keeps at most one job with a given lock waiting. Deferring another raises `AlreadyEnqueued`, an exception "which you can choose to ignore" (`docs/howto/advanced/queueing_locks.md`, line 18, at 3.10.0).

What happens to the caller's transaction when the code ignores it there?

**The application.** An order and its follow-up job commit together: the job recomputes the customer's stats. A per-customer queueing lock keeps at most one such job waiting.

That job belongs in the order's transaction: it should exist only if the order commits. That is the point of enqueueing inside the transaction. On a repeat order, while the first job still waits, the code ignores `AlreadyEnqueued`:

```python
def place_order(customer_id):
    with transaction.atomic():
        order = Order.objects.create(customer_id=customer_id)
        transaction.on_commit(...)  # instrumentation: records that the callback ran
        try:
            recompute_customer_stats.configure(queueing_lock=f"stats-{customer_id}").defer(
                customer_id=customer_id
            )
        except exceptions.AlreadyEnqueued:
            pass  # one is already queued; the docs say this can be ignored
    return order.id
```

The psycopg arms do the same through the external-connection API, as in that page's example: an `INSERT`, then `configure(connection=conn, queueing_lock=...).defer(...)` with the same `except`, then `conn.commit()`.

**Answer (observed, 3 of 3 runs per arm).** On a repeat order, the order is lost without an error.

- **Django.** `place_order()` returns the new order's ID, and Django runs the `on_commit` callback. Procrastinate's insert had failed with `23505` on `procrastinate_jobs_queueing_lock_idx_v1`, so PostgreSQL had aborted the transaction. Django sent `COMMIT` anyway, and psycopg 3's `commit()` returned normally (PY-1a). This is CHK-12's raw-SQL path: Procrastinate's Django connector uses a cursor, not the ORM, so Django does not mark the transaction for rollback.
- **External-connection API (psycopg).** `conn.commit()` returns normally. The transaction was aborted, and the order is gone.
- **With the `defer` in a savepoint** (a nested `atomic()`, or `conn.transaction()`), the duplicate rolls back only the savepoint. The order commits, and the waiting job is unchanged.

## Each arm

| Arm | What the code saw | PostgreSQL |
| --- | --- | --- |
| `django.first`, `psycopg.first` | returned the order (`on_commit` ran, Django) | `COMMIT`; `committed`; order visible; one job waiting |
| `django.repeat` | returned the order; **`on_commit` ran** | `23505`, then `COMMIT` after the abort; `aborted`; **order absent**; the earlier job still waiting |
| `psycopg.repeat` | `commit()` returned normally | the same |
| `django.repeat_savepoint`, `psycopg.repeat_savepoint` | returned the order | `SAVEPOINT`, `23505`, `ROLLBACK TO SAVEPOINT`, then `COMMIT`; `committed`; order visible; one job waiting |

In each repeat arm, the customer's earlier order and its job are committed first, on a separate connection.

## Agreement

- **Three fates agree for all 18 transactions** (`output/log-check.txt`): the witness connection, `psql` inside the container (`output/psql-xact-status.txt`), and the server log, read as in CHK-12.
  - In the repeat arms, the `COMMIT` carries a virtual transaction ID with local part 0, so the abort came first.
  - In the first run of `django.repeat`, for example, the `23505` comes at `vxid=11/3`, and the `COMMIT` at `vxid=11/0`.
- **The SQLSTATEs are logged** with `%e`: twelve `23505` errors on `procrastinate_jobs_queueing_lock_idx_v1`, from the four repeat arms in three runs.
- **The hypothesis.** It was written before the runs, in `log_check.py`, and it held for every arm, 3 of 3. `output/hashes-before.txt` and `output/hashes-after.txt` are identical.
- **The outputs.** With the transaction IDs and the order numbers masked, the three outputs are identical. Each begins with Procrastinate's warning that the app is defined in the main module, which is harmless here.

## What Procrastinate documents

- **The queueing-lock page** says the exception is one "which you can choose to ignore". It does not mention transactions.
- **The external-connection page** (`docs/howto/production/external_connection.md`, line 110, at 3.10.0, added with PR [#1508](https://github.com/procrastinate-org/procrastinate/pull/1508)) says that errors from the job insert "(e.g. queueing lock violations) … may abort your transaction. Use savepoints if you need to isolate the defer".
- **The Django pages** do not say that `defer()` runs inside the current `atomic()` block, and say nothing about transactions outside testing.
- **The library does not swallow the error.** It translates the unique violation into `AlreadyEnqueued` (`procrastinate/manager.py`, `_raise_already_enqueued`). Its Python API has no ON CONFLICT or ignore mode for queueing locks. Only the command line has `--ignore-already-enqueued`, and the CLI defers on its own connection.
- **Related, upstream:**
  - [#1446](https://github.com/procrastinate-org/procrastinate/issues/1446) (open): a queueing-lock violation in `retry_stalled_jobs`; a commenter's SQL workaround avoids aborting the caller's transaction.
  - [#1512](https://github.com/procrastinate-org/procrastinate/pull/1512) (an open PR, blocked from merging): the Django admin's retry action ignores `AlreadyEnqueued` the safe way, `with suppress(AlreadyEnqueued), transaction.atomic():`.

## Real-world signal

A GitHub code search on 2026-10-26 for code that catches `AlreadyEnqueued` found 91 files outside forks and Procrastinate itself, with 104 catch sites. Three caveats: it covered only the first page of each of three queries; the context check was a heuristic, looking only at the enclosing function; and it did not trace callers or `ATOMIC_REQUESTS`.

- **No unprotected catch inside a caller's transaction was found.**
- **At least six projects wrap the `defer` in a savepoint.** Three explain why:
  - [JJMxr04/MDProject](https://github.com/JJMxr04/MDProject/blob/ca5ac8c6e06bb9d160adc9230b3377541c731aef/core/mail/debounce.py#L22-L24): "without the savepoint it would poison a caller's open transaction";
  - [xca-sh/xcash](https://github.com/xca-sh/xcash/blob/f4327a2310303fa55b7cab4fb54bcd798f6eb755/xcash/common/jobs.py#L58-L60), translated from Chinese: the conflict "marks the outer transaction aborted … so it must be wrapped in a savepoint";
  - [dimagi-rad/scout](https://github.com/dimagi-rad/scout/blob/93b8778125d1f479d6fd89c7dd4708faf58d275e/apps/workspaces/task_dispatch.py#L143): "the queueing-lock violation must not abort the caller's transaction".
- **The rest defer on Procrastinate's own connection,** outside any caller transaction.

All three describe the loud form: later statements fail. None mentions this check's silent form, where the `defer` is the last statement and the commit reports success.

## Environment

| Item | Value |
| --- | --- |
| Packages | Procrastinate 3.10.0, Django 6.1.2, psycopg 3.3.6 and psycopg-pool 3.3.3: the latest releases on PyPI on 2026-10-26, installed with `pip install --only-binary=:all:` into a fresh virtualenv (`versions-pip.txt`) |
| Python | 3.13.11 (Homebrew), macOS 26.6.2 arm64 |
| Server | PostgreSQL 18.6, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` |
| Docker | colima 0.9.1, Docker server 28.4.0 (`output/env.txt`) |

**The container.**
- A throwaway container on `127.0.0.1:55489`, not `ppcs-postgres`.
- tmpfs storage, a random password and a random `cluster_name` token. The token was checked through the host port before the runs, and the container was removed after them.
- Settings: CHK-12's (`output/server-settings.txt`).

## Commands

```sh
bash run.sh <venv>/bin/python      # container, token check, three runs, psql fates, server log, cross-check, removal
python -I log_check.py output      # the cross-check alone
```

## Files

- `procrastinate_queueing_lock.py`: the application and the arms. Run it with `DATABASE_URL` set. It creates database `procrastinate_queueing_lock` (Procrastinate's schema comes from its Django migrations) and drops it at the end.
- `run.sh` and `wait_for_server.py`: the runner, and its readiness and token check.
- `log_check.py`: the cross-check and the hypothesis.
- `output/run.rep{1,2,3}.out`: the complete stdout and stderr of the three runs. Every run exited 0 (`output/exit-codes.txt`).
- `output/server.log`: the server's complete log.
- `output/psql-xact-status.txt`, `output/server-settings.txt`, `output/env.txt`, `output/log-check.txt`, `output/hashes-before.txt`, `output/hashes-after.txt`.
- `versions-pip.txt`.
- `SHA256SUMS`: every file except this README and itself.

## Limits

- **Not run:**
  - `defer_async()`;
  - Procrastinate's SQLAlchemy connector;
  - psycopg2 and asyncpg;
  - a web server around the Django code: the arms call `place_order()` directly;
  - older Procrastinate releases.
- **Nothing runs after the ignored exception.** A later statement in the same transaction would fail with `25P02`, the loud form.
- **The real-world search** is a sample, not a census. It found guarded code, not an incident.
