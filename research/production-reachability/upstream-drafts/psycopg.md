# psycopg — `commit()` returns after PostgreSQL rolls the transaction back

**Filed 2026-10-21** as https://github.com/psycopg/psycopg/issues/1453 Posted as `KevinBlakeLopez`. No pull request.

Search the same day, before filing: `ROLLBACK commit` and `commit() ROLLBACK` did not return a report of `commit()` returning when the command tag is `ROLLBACK`. Open #1451 is cancellation of `AsyncConnection.transaction().__aenter__()`, which leaves a stale transaction stack. Closed #969 and #967 ask whether a transaction context records commit versus rollback. Closed #296 is pipeline mode. PyPI `latest` was 3.3.6, uploaded 2026-09-18. The 2026-10-19 case files record that same driver version.

## Notes (not part of the issue)

`Connection.commit()` calls `_exec_command(b"COMMIT")` and does not return the result. `_exec_command` returns when the status is `COMMAND_OK`. A `ROLLBACK` tag is still `COMMAND_OK`.

The body program is `reproductions/psycopg_commit_tag.py`. It creates and drops database `ppcs_repro_psycopg_tag`. The output block is that program's full stdout from one run on 2026-10-21. Nothing is omitted.

`pgresult.status` and `pgresult.command_status` come from `cursor.execute("COMMIT")` on a second connection. They were not read from `commit()`. On this Mac, `pgconn.trace()` raises `NotSupportedError: currently only supported on Linux`. This program does not call it.

Line numbers below are psycopg 3.3.6.

`Connection.commit()` is at `psycopg/connection.py`, lines 306–309. The annotation is `-> None`. It calls `self.wait(self._commit_gen())`. `_commit_gen` starts at `psycopg/_connection_base.py`, line 577. Line 592 is `yield from self._exec_command(b"COMMIT")`, and that result is not bound. `_exec_command` starts at line 443. Lines 485–492 raise unless the status is `COMMAND_OK` or `TUPLES_OK`. Line 493 returns the result.

`cursor.execute("COMMIT")` with no parameters uses `send_query` (`psycopg/_cursor_base.py`, line 459). `_exec_command` uses `send_query` for `COMMIT` (`psycopg/_connection_base.py`, line 474).

SQLAlchemy and Django are not separate reports. SQLAlchemy Core on the 2026-10-19 run logged `COMMIT (INERROR -> IDLE)`. The later transaction was a new `Engine.connect()` checkout from the pool, and it committed on the same PostgreSQL backend (`same_backend: true`, the same pid). Django's manual `commit()` observation is the follow-up `2026-10-19T20-58-26Z-508b7a`: the server session moved from `idle in transaction (aborted)` to `idle`, the last statement was `COMMIT`, and a later transaction on that connection committed. It did not log a psycopg status. The same day's earlier Django explicit case reported `rolled_back` because the adapter raised `TransactionManagementError`: `on_commit() cannot be used in manual transaction management`. The basis is that the body threw and `transaction.rollback()` was called. That case is not a measurement of `commit()`. Its adapter source hash is `7a09a9af3b0330d2cc70efb5954145cbd07d53531daa86d7409eb00e09d2784c`. The follow-up hash is `de213cddef82bde0259da5c10b50c38ada8e32ea261789d4a8d28ae10b688e89`. The direct program closes the connection after `commit()` and does not show reuse.

## Body

`Connection.commit()` returns `None` after PostgreSQL has aborted the transaction. The command tag on a separate `cursor.execute("COMMIT")`, using the same kind of simple-query call, is `ROLLBACK`. The row inserted before the error is gone.

### Direct check

`DATABASE_URL` must be able to create a database. The program connects to the `postgres` database, creates `ppcs_repro_psycopg_tag`, and drops that database at the end. It does not drop tables in an existing database.

```python
"""Direct psycopg check. Uses DATABASE_URL and a throwaway database.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python psycopg_commit_tag.py

Does not print the password. Does not trace libpq. The command tag is read from
cursor.execute("COMMIT") on a second connection, not from Connection.commit().
"""

import os

import psycopg
from psycopg.pq import ExecStatus, TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "ppcs_repro_psycopg_tag"


def connect(dbname, autocommit):
    return psycopg.connect(URL, dbname=dbname, autocommit=autocommit)


def status_name(conn):
    return TransactionStatus(conn.info.transaction_status).name


def names(rows):
    return [row[0] for row in rows]


def setup(conn):
    conn.execute("create table item (id serial primary key, name text not null)")
    conn.execute("create table uniq (id serial primary key, code text not null unique)")
    conn.execute("insert into uniq (code) values ('taken')")


def abort_with_unique(conn):
    conn.execute("insert into item (name) values ('kept')")
    try:
        conn.execute("insert into uniq (code) values ('taken')")
    except psycopg.errors.UniqueViolation as exc:
        return exc.sqlstate
    return None


def main():
    admin = connect("postgres", True)
    print(f"psycopg {psycopg.__version__}")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    admin.close()

    with connect(NAME, True) as setup_conn:
        setup(setup_conn)

    control = connect(NAME, False)
    control.execute("insert into item (name) values ('seen')")
    print("normal commit() control")
    print(f"  commit() returned {control.commit()!r}")
    control.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")
        probe.execute("delete from item")

    subject = connect(NAME, False)
    caught = abort_with_unique(subject)
    print("commit() after caught 23505")
    print(f"  caught {caught}")
    print(f"  transaction_status before commit() {status_name(subject)}")
    print(f"  commit() returned {subject.commit()!r}")
    print(f"  transaction_status after commit() {status_name(subject)}")
    subject.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")
        probe.execute("delete from item")

    other = connect(NAME, False)
    caught = abort_with_unique(other)
    print("cursor.execute('COMMIT') on a second connection, not commit()")
    print(f"  caught {caught}")
    print(f"  transaction_status before execute {status_name(other)}")
    cur = other.cursor()
    cur.execute("COMMIT")
    result = cur.pgresult
    print(f"  statusmessage {cur.statusmessage!r}")
    print(f"  pgresult.status {ExecStatus(result.status).name}")
    print(f"  pgresult.command_status {result.command_status.decode()!r}")
    other.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")

    admin = connect("postgres", True)
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
```

Output of that program, complete:

```
psycopg 3.3.6
server_version 18.6 (Debian 18.6-1.pgdg13+2)
normal commit() control
  commit() returned None
  visible from another connection ['seen']
commit() after caught 23505
  caught 23505
  transaction_status before commit() INERROR
  commit() returned None
  transaction_status after commit() IDLE
  visible from another connection []
cursor.execute('COMMIT') on a second connection, not commit()
  caught 23505
  transaction_status before execute INERROR
  statusmessage 'ROLLBACK'
  pgresult.status COMMAND_OK
  pgresult.command_status 'ROLLBACK'
  visible from another connection []
```

`statusmessage`, `pgresult.status`, and `pgresult.command_status` are printed from `cursor.execute("COMMIT")`. `commit()` only prints its return value, `None`.

### What happened

1. Insert a row.
2. Catch a unique violation (`23505`). That aborts the transaction.
3. Call `commit()`. It returns `None`.
4. The row is gone.

### Versions

- psycopg 3.3.6
- PostgreSQL 18.6

### What the caller sees

`commit()` returns `None` and does not raise. The program above closes that connection after `commit()` and does not use it again.

SQLAlchemy Core 2.1.5, on psycopg 3.3.6, logged `COMMIT (INERROR -> IDLE)` after a caught unique violation. The insert was gone. A later `Engine.connect()` from that pool committed on the same PostgreSQL backend.

Django 6.1.2 called `transaction.commit()` after catching the same error. The server session moved from `idle in transaction (aborted)` to `idle`, and the last statement was `COMMIT`. The insert was gone. A later transaction on that same connection committed. That run did not record a psycopg status.

Those callers continued after the call returned. This report is for psycopg.

### Expected

When the server completes `COMMIT` with the command tag `ROLLBACK`, `commit()` should raise. The driver already requires `COMMAND_OK` for that command. The tag is a separate field on the same result.

### Actual

`commit()` returns `None`. On the separate `cursor.execute("COMMIT")` above, `statusmessage` is `'ROLLBACK'`, `pgresult.status` is `COMMAND_OK`, and `pgresult.command_status` is `'ROLLBACK'`. The row is gone. A normal `commit()` in the same program is visible from another connection as `['seen']`.
