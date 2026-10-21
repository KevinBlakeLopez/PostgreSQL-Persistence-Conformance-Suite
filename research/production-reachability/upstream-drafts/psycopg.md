# Draft: psycopg

**Not filed.**

Suggested title: `Connection.commit()` returns when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [psycopg/psycopg](https://github.com/psycopg/psycopg/issues/new)

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. `COMMIT` is then accepted, the command tag is `ROLLBACK`, and no error result is sent. The effect is a rollback.

psycopg 3.3.6 `Connection.commit()` returns in that case. `_commit_gen` sends `COMMIT` through `_exec_command` and discards the returned result (`psycopg/_connection_base.py`). `_exec_command` raises unless the result status is `COMMAND_OK` or `TUPLES_OK`. A `ROLLBACK` command tag is still `COMMAND_OK`, so `commit()` returns.

Callers then report a successful commit.

### Versions

- psycopg 3.3.6
- PostgreSQL 18.6

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6. In an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### What callers did

**SQLAlchemy Core 2.1.5.** Inside `with conn.begin()`, the application caught `IntegrityError` (`23505`) from a duplicate insert and let the block end. `DefaultDialect.do_commit` calls `dbapi_connection.commit()`. The context manager returned without an exception. SQLAlchemy's connection `commit` event ran. The trace was `COMMIT (INERROR -> IDLE)`. `pg_xact_status()` was `aborted`, and another connection did not see the earlier insert. Three repetitions agreed. An explicit `Transaction.commit()` did the same thing.

**Django 6.1.2 manual commit.** Outside `atomic()`:

```python
transaction.set_autocommit(False)
try:
    Item.objects.create(name="kept", qty=0)
    try:
        Uniq.objects.create(code="taken")
    except IntegrityError:
        pass
    transaction.commit()
finally:
    transaction.set_autocommit(True)
```

`transaction.commit()` returned. Django's `DatabaseWrapper.commit` then sets `errors_occurred = False`. The last statement on the session was `COMMIT`. `pg_xact_status()` was `aborted`, and the `kept` row was not visible. `needs_rollback` stayed false because that flag is for an `atomic` block. Three repetitions agreed.

`transaction.atomic()` does not hit this path. A caught database error sets `needs_rollback`, and `Atomic.__exit__` calls `rollback()` instead of `commit()`. That path left the marker absent and did not report a commit.

**SQLAlchemy ORM is a different ending.** `Session._flush` rolls the transaction back when the flush raises, and `after_commit` does not run. `TransactionalContext.__exit__` commits only while the transaction is still active. That case is not this report.

### Expected

`Connection.commit()` should raise when the result of `COMMIT` has command tag `ROLLBACK`, so a caller cannot treat the return as a committed transaction.

### Actual

`commit()` returns. SQLAlchemy Core fires its commit event and returns from `Connection.begin()`. Django's manual `commit()` returns and clears `errors_occurred`.

### Why it matters

Both callers above are using a documented transaction API. The application caught a unique violation and then completed the transaction. The API reported success, and the row was not stored. The connection is usable afterward, so the next request can commit and hide the lost write.
