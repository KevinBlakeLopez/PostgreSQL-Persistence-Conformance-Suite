# Draft: CPython issue for F4

Status: **AWAITING_APPROVAL**. Not filed. Written 2026-10-25 by Claude Opus 5.5 (max) for review.

Before filing:

- CPython's [Guidelines for using AI tools](https://devguide.python.org/getting-started/ai-tools/): the person filing is responsible for the content and should be able to explain it in their own words; disclosing AI assistance is appreciated, not required. Rewrite or edit as you see fit.
- Re-run `repro/minimal/sqlite3_autocommit_false.py` on the latest 3.13 and 3.14 releases, and re-read `Modules/_sqlite/connection.c` on `main` (checked at `efbd165392e2`, 2026-10-25).
- Search the tracker again (`upstream/duplicate-search.md` has the 2026-10-25 queries).

Evidence: `findings.md` F4; `output/minimal-matrix/2026-10-25T18-21-01Z-556213/*/sqlite3_autocommit_false.rep*.out`; `output/sqlite01-raw/2026-10-25T17-21-27Z-737440/cases/pep249.rollback.*`.

---

**Title:** sqlite3: with `autocommit=False`, a transaction that SQLite rolls back by itself leaves the connection outside transaction control

# Bug report

### Bug description:

With `autocommit=False`, the docs say that `sqlite3` "ensures a transaction is always open", and that `commit()` and `rollback()` do nothing "if there is no open transaction".

SQLite sometimes ends a transaction by itself: a constraint declared `ON CONFLICT ROLLBACK`, `RAISE(ROLLBACK, ...)` in a trigger, and, per <https://www.sqlite.org/lang_transaction.html>, some `SQLITE_FULL`, `SQLITE_IOERR`, `SQLITE_INTERRUPT` or `SQLITE_NOMEM` errors. After that:

- `in_transaction` is `False`, and later statements run in SQLite's autocommit mode;
- `commit()` raises `OperationalError: cannot commit - no transaction is active`;
- `rollback()` raises `OperationalError: cannot rollback - no transaction is active`;
- neither opens a new transaction, so the connection stays this way.

```python
import os
import sqlite3
import tempfile

path = os.path.join(tempfile.mkdtemp(), "demo.db")
con = sqlite3.connect(path, autocommit=False)
con.execute("CREATE TABLE t (x INTEGER UNIQUE ON CONFLICT ROLLBACK)")
con.commit()

con.execute("INSERT INTO t VALUES (1)")
try:
    con.execute("INSERT INTO t VALUES (1)")
except sqlite3.IntegrityError as exc:
    print("IntegrityError:", exc)
print("in_transaction:", con.in_transaction)

for name in ("commit", "rollback"):
    try:
        getattr(con, name)()
        print(f"{name}(): returned")
    except sqlite3.OperationalError as exc:
        print(f"{name}(): OperationalError:", exc)
    print("in_transaction:", con.in_transaction)

con.execute("INSERT INTO t VALUES (2)")  # the next unit of work
try:
    con.rollback()
    print("rollback(): returned")
except sqlite3.OperationalError as exc:
    print("rollback(): OperationalError:", exc)

other = sqlite3.connect(path)
print("committed rows:", [row[0] for row in other.execute("SELECT x FROM t ORDER BY x")])
other.close()
con.close()
```

Output, identical on 3.13.11 and 3.14.2 (macOS, SQLite 3.54.1) and 3.13.17 (Linux, SQLite 3.46.1):

```
IntegrityError: UNIQUE constraint failed: t.x
in_transaction: False
commit(): OperationalError: cannot commit - no transaction is active
in_transaction: False
rollback(): OperationalError: cannot rollback - no transaction is active
in_transaction: False
rollback(): OperationalError: cannot rollback - no transaction is active
committed rows: [2]
```

Row 2 was inserted after the failed calls and then rolled back, and it is committed. Setting `con.autocommit = False` again, or executing `BEGIN`, puts the connection back in a transaction; `rollback()` does not.

In `Modules/_sqlite/connection.c`, with `AUTOCOMMIT_DISABLED`, `pysqlite_connection_commit_impl()` and `pysqlite_connection_rollback_impl()` execute `COMMIT` or `ROLLBACK` unconditionally and return the error before the `BEGIN` that follows. The legacy branch checks `sqlite3_get_autocommit()` first.

Would it make sense for `rollback()` to do nothing and open a new transaction when none is open, as documented, and for `commit()` to open a new transaction even when it raises? If raising and staying outside a transaction is intended, the docs for `autocommit=False`, `commit()` and `rollback()` could say so.

gh-112441 was about transaction control issued by the user; here SQLite ends the transaction itself.

### CPython versions tested on:

3.13, 3.14

### Operating systems tested on:

macOS, Linux
