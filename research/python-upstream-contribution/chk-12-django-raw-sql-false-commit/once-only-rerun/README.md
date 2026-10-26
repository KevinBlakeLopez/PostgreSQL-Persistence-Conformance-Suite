# CHK-12 re-run: a once-only first-order bonus as the trigger

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Why a re-run.** [CHK-12](../README.md) triggered the error with a best-effort analytics write inside the order's transaction. Optional work does not belong in an all-or-nothing transaction, so that trigger is not reasonable application code. This re-run uses a write that does belong there: the customer's first-order bonus. It is the order's last step. Its primary key on `customer_id` makes it once-only, and the view treats `IntegrityError` as "already awarded". The only mistake left in the code is the missing savepoint, a nested `atomic()`, which Django's documentation asks for when an exception is caught inside `atomic()`.

**Answer (observed, 3 of 3 runs per arm).** The same as CHK-12, with `23505` in place of `22001`. When the customer already has a bonus:

- **Raw SQL, with `atomic()` in the view or with `ATOMIC_REQUESTS` alone.** Django sends `COMMIT`, psycopg 3's `commit()` returns, the `on_commit` callback runs, and the view returns 200. PostgreSQL had already aborted the transaction, and the new order is gone.
- **Raw SQL, with `atomic()` nested inside `ATOMIC_REQUESTS`.** Django's `RELEASE SAVEPOINT` fails with `25P02`, and the request returns 500.
- **The ORM.** Django rolls back by itself in all three setups and does not run `on_commit`. The view still returns 200, and the new order is gone.

First orders commit, with the order visible and `on_commit` run, in all six setups.

## The view

```python
def award_bonus_sql(customer_id, order_id):
    """The same, in raw SQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into shop_firstorderbonus (customer_id, order_id) values (%s, %s)",
                [customer_id, order_id],
            )
    except IntegrityError:
        log.info("customer %s already had the first-order bonus", customer_id)


def place_order(marker, customer_id, award):
    order = Order.objects.create(marker=marker, customer_id=customer_id)
    ...  # reads pg_current_xact_id() and registers the on_commit callback
    award(customer_id, order.id)  # the last step
    return order.id
```

The ORM version calls `FirstOrderBonus.objects.create()` instead. For a `dup` arm, the program first stores an earlier order and its bonus for that customer, on a separate connection.

## Each arm

The arms and setups are CHK-12's. `ok` is a first order, and `dup` is a repeat customer.

| Arm | Django | `on_commit` | PostgreSQL |
| --- | --- | --- | --- |
| `{atomic,nested,request}.{orm,sql}.ok` | 200 | ran | `COMMIT`; `committed`; order visible |
| `atomic.orm.dup`, `request.orm.dup` | 200 | did not run | `23505`, then `ROLLBACK`; `aborted`; order absent |
| `atomic.sql.dup`, `request.sql.dup` | 200 | **ran** | `23505`, then `COMMIT`; `aborted`; order absent |
| `nested.orm.dup` | 200 | did not run | `23505`, `ROLLBACK TO SAVEPOINT`, then `COMMIT`; `committed`; order absent |
| `nested.sql.dup` | 500, `InternalError: current transaction is aborted…` | did not run | `23505`; `RELEASE SAVEPOINT` fails with `25P02`; `ROLLBACK TO SAVEPOINT`, then `ROLLBACK`; `aborted`; order absent |

## Agreement

- **Three fates agree for all 36 transactions** (`output/log-check.txt`): the witness connection, `psql` (15 `aborted`, 21 `committed`), and the server log, read as in CHK-12. For example, `atomic.sql.dup`'s first run logs the `23505` at `vxid=15/3 xid=762` and the `COMMIT` at `vxid=15/0`.
- **The hypothesis** was written before the runs: CHK-12's, with `23505` in place of `22001`. It is in `log_check.py`, and it held for every arm, 3 of 3. `output/hashes-before.txt` and `output/hashes-after.txt` are identical.
- **The outputs.** With the transaction IDs masked, the three outputs of each mode are identical.

## Environment, commands, files and limits

These are CHK-12's:
- Django 6.1.2, psycopg 3.3.6 (`versions-pip.txt`) and Python 3.13.11;
- PostgreSQL 18.6, from the same image digest;
- a throwaway container `ppcs-django-once-only-pg` on `127.0.0.1:55499`, removed after the runs (`output/env.txt`, `output/server-settings.txt`).

Run `bash run.sh <venv>/bin/python`, or `python -I log_check.py output` for the cross-check alone. `django_once_only.py off|on` creates database `django_once_only` and drops it at the end.

`SHA256SUMS` covers every file except this README and itself. CHK-12's limits apply too: Django's test client, not a server; no psycopg2, async views, pools or older releases.
