# SQLAlchemy: facts for a report written in your own words

Status: **NOT FILED**. Nothing posted. Prepared 2026-10-25 by Claude Opus 5.5 (max).

This is not a draft to paste. SQLAlchemy's code of conduct asks participants not to use LLMs as their primary means of communicating and to use GitHub "as a human, in a non-automated fashion", and its contributing guide asks for "your own words"; LLM help is acceptable for code that demonstrates an issue (as checked on 2026-10-18 at `rel_2_1_5`; re-check before posting). So the scripts and their outputs below can be posted as they are, and the text around them has to be yours. SQLAlchemy's bug form asks for a discussion first when unsure; discussion #13656 becoming issue #13657 is a recent example.

Evidence references are to this study (`findings.md`, `output/`).

## SA-1. After SQLite ends the transaction, SQLAlchemy keeps it active and reports the commit

### Facts

1. SQLite ends the whole transaction by itself for some errors: a constraint declared `ON CONFLICT ROLLBACK` (which SQLAlchemy emits for `sqlite_on_conflict="ROLLBACK"` and `sqlite_on_conflict_unique="ROLLBACK"`), `RAISE(ROLLBACK, …)` in a trigger, and, per SQLite's documentation, some `SQLITE_FULL`, `SQLITE_IOERR`, `SQLITE_INTERRUPT` and `SQLITE_NOMEM` errors. This study observed it for `SQLITE_FULL` on a single-row `INSERT` or `UPDATE` (a page limit, and a real `ENOSPC`), for `SQLITE_INTERRUPT` on a write, and for `SQLITE_IOERR_WRITE` from a real `EFBIG` (`findings.md` F7).
2. The application cannot tell this from the exception. `RAISE(ABORT, …)`, which only aborts the statement, and `RAISE(ROLLBACK, …)` raise the same `IntegrityError` with the same `sqlite_errorcode` (1811, `SQLITE_CONSTRAINT_TRIGGER`). Only `sqlite3.Connection.in_transaction` differs: True after `ABORT`, False after `ROLLBACK`.
3. Afterwards `sqlite3`'s `in_transaction` is False, and SQLAlchemy's `Connection.in_transaction()`, `Transaction.is_active` and `Session.in_transaction()` are True. SQLAlchemy emits no SQL and changes no state in response.
4. **The SAVEPOINT loop from the ORM guide** ("Using SAVEPOINT", `doc/build/orm/session_transaction.rst` lines 157–168 at `rel_2_1_6`, the loop with `except:`), on an engine set up with the `BEGIN` recipe from the SQLite dialect documentation ("Enabling Non-Legacy SQLite Transactional Modes"): when one record ends the transaction, the loop prints that record as skipped, `session.commit()` returns normally and sends no SQL, every record before the failing one is absent, and every record after it is committed.
5. The records after it are committed one at a time. The next `SAVEPOINT` is issued with no transaction open, which SQLite treats as `BEGIN DEFERRED TRANSACTION`, and its `RELEASE` as `COMMIT` (<https://www.sqlite.org/lang_savepoint.html>). The trace has no `BEGIN` after the failure.
6. With a real disk full (a tmpfs with 3 MiB free, 30 records of 200 KiB, Linux, SQLite 3.46.1), `session.commit()` returned normally; the loop's own record says 29 records were committed; 6 were (`findings.md` F1, `output/sqlite05c-enospc/2026-10-25T17-22-54Z-9e213e/`).
7. With `connect_args={"autocommit": False}`, the commit raises `cannot commit - no transaction is active`, but the records after the failing one are already committed.
8. With the default engine (legacy `sqlite3` transaction control) the documented loop is not atomic in the first place, because `SAVEPOINT` does not begin a transaction there. That is the documented legacy-mode caveat, and not part of this item.
9. Without savepoints (`repro/minimal/sa_core_false_commit.py`, default engine): an `engine.begin()` block that catches the error and continues exits normally; the write before the error is gone, and a write after it is committed by itself, in a new implicit transaction. The same holds for `conn.begin()`/`tx.commit()`, commit-as-you-go and the ORM through `session.execute()`, where `after_commit` also fires (`findings.md` F2).
10. The ORM-guide example that catches `exc.IntegrityError` instead (lines 177–188) fails loudly: the nested scope's `ROLLBACK TO SAVEPOINT` raises `no such savepoint`, which escapes and replaces the `IntegrityError`; nothing is committed.
11. Versions: SQLAlchemy 2.1.6 and 2.0.55; Python 3.13.11, 3.14.2 (macOS) and 3.13.17 (Linux); SQLite 3.54.1 and 3.46.1. `lib/sqlalchemy/engine/base.py` and `lib/sqlalchemy/dialects/sqlite/` have no commits on `main` since 2.1.6 (checked at `10f4d1e2d706`, 2026-10-23).
12. For comparison, Django 6.1.2 under the same trigger, with its documented nested `atomic()` pattern: the failed savepoint rollback marks the connection for rollback, the original `IntegrityError` reaches the application, the next query raises `TransactionManagementError`, `on_commit` does not run, and nothing is committed (`findings.md` N6).

### Scripts and their output

`repro/minimal/sa_savepoint_batch.py` (SHA-256 `2b5fa19c506e8698c775aa1638eff208de7dcc7b9f887d6ce3140c185770fdfc`), the recipe plus the guide's loop; record "b" appears twice under `UNIQUE … ON CONFLICT ROLLBACK`, or record "big" exceeds `max_page_count`:

```
$ python sa_savepoint_batch.py on-conflict
Skipped record b
session.commit() returned
committed: ['d', 'e']
$ python sa_savepoint_batch.py page-limit
Skipped record big
session.commit() returned
committed: ['d', 'e']
```

`repro/minimal/sa_core_false_commit.py` (SHA-256 `a39e5f00ae7944a9fb59a89511ccecc58e05b6c526baef2d7b8b2782f569dbf5`), default engine:

```
duplicate transfer reference skipped
SQLAlchemy in_transaction(): True | sqlite3 in_transaction: False
engine.begin() block committed without error
balance: 100
audit: ['debited 30']
```

Each output was byte-identical over three runs in each of four environments: macOS with Python 3.13.11 and SQLAlchemy 2.1.6; with Python 3.14.2; with SQLAlchemy 2.0.55; and Linux (`python:3.13-slim`, Python 3.13.17, SQLite 3.46.1, SQLAlchemy 2.1.6). Run `output/minimal-matrix/2026-10-25T18-21-01Z-556213/`.

### Code path (source reading, 2.1.6)

- `engine/base.py` 2329–2340: a non-disconnect DBAPI error closes the cursor and rolls back only when no transaction is in progress.
- `engine/base.py` 2843 → 2820 → 1184: the nested transaction's rollback emits `ROLLBACK TO SAVEPOINT`, which raises; the nested transaction is deactivated and the `RootTransaction` stays active.
- `orm/session.py` 1377, 1412: the ORM's nested rollback re-raises that error; the root `SessionTransaction` stays active.
- `engine/default.py` 953: `do_commit()` calls `sqlite3.Connection.commit()`, which in legacy transaction control does nothing when no transaction is open, as `sqlite3` documents.

### Questions a maintainer may ask

- *"The example catches everything; isn't that the user's choice?"* The bare `except` is the guide's own example, and its stated purpose is to skip a record "without rolling back the whole transaction". With the specific-exception example the failure is loud, but the original error is replaced by `no such savepoint`.
- *"Which real errors do this?"* Fact 1, and `findings.md` F7: single-row statements with `SQLITE_FULL`; writes with `SQLITE_INTERRUPT`; writes with `SQLITE_IOERR`. A multi-row `INSERT … SELECT` with `SQLITE_FULL`, and an interrupted `SELECT`, only abort the statement.
- *"Is there prior history?"* Ticket #2696 (2013): MySQL "had already automatically rolled back by itself, and so destroyed savepoints", and the missing savepoint hid the original error; the maintainer then wrote that "it's probably reasonable to be ready for the SAVEPOINT to be missing". #5968 (2021): `sqlite_on_conflict="IGNORE"` broke the ORM's assumption that an INSERT either succeeds or raises.
- *"What could SQLAlchemy do?"* Not tested; options for discussion: after a DBAPI error inside a transaction on the SQLite dialects, read `in_transaction` and, if SQLite has no transaction while SQLAlchemy's is active, put the root transaction into the existing invalid state used after a disconnect, so later statements, savepoints and `commit()` raise until the application rolls back; or apply that check only when `ROLLBACK TO SAVEPOINT` fails; and in the documentation, say which SQLite errors end a transaction (including `sqlite_on_conflict="ROLLBACK"`), and catch a specific exception in the SAVEPOINT example.

## SA-2. `Session.close()` keeps the pooled connection when the rollback inside it raises

### Facts

1. `SessionTransaction.close()` (`orm/session.py` 1422–1438 at 2.1.6, unchanged on `main`) calls `transaction.close()` for each connection and only then `connection.close()`. If `transaction.close()` raises, `connection.close()` is not reached: the Core `Connection` and its pooled DBAPI connection stay checked out, `_state` is not set to `CLOSED`, and `after_transaction_end` is not dispatched (source reading).
2. #13657 (fixed by `d29277af2b80`, 2026-10-06) fixed the same symptom in Core's `Connection.close()`: "an exception raised by the rollback performed within Connection.close(), which was not otherwise classified as a disconnect, would leave the Connection open and its pooled DBAPI connection checked out". That commit changed `engine/base.py`, the asyncpg dialect and tests only. In the ORM path the rollback happens inside `transaction.close()`, before `Connection.close()` is called.
3. With `connect_args={"autocommit": False}`, a transaction that SQLite ended makes this rollback raise deterministically: `sqlite3` raises `cannot rollback - no transaction is active` (see `upstream/cpython-sqlite3-autocommit-false-draft.md`; it is not a disconnect).
4. It happens when the error comes from `session.execute()` and leaves `with Session(engine)`. Through `session.flush()` the flush rolls back first, and `close()` returns the connection.
5. The connection is released only when the cyclic garbage collector frees the Session. In the study's harness, with a pool of one, three later checkouts each timed out (`findings.md` F3).

### Script and its output

`repro/minimal/sa_session_close_leak.py` (SHA-256 `a420747052166e5142b3015b2d015448dd406899ea16367432e44c824efc08f6`), a pool of one, `pool_timeout=1`:

```
left the block: OperationalError - (sqlite3.OperationalError) cannot rollback - no transaction is active
exception chain: sqlalchemy.OperationalError <- sqlite3.OperationalError <- sqlalchemy.IntegrityError <- sqlite3.IntegrityError
checked out after the block: 1
next checkout: TimeoutError
pool logged: Exception during reset or similar (OperationalError: cannot rollback - no transaction is active)
checked out after gc.collect(): 0
next checkout after gc.collect(): 1
```

Byte-identical over three runs in each of the four environments above, including SQLAlchemy 2.0.55.

### Possible change and test (not tested)

Close the connection in a `finally` around `transaction.close()` in `SessionTransaction.close()`, so that `Connection.close()` and its #13657 handling always run. A test in the style of #13657's `test/engine/test_reconnect.py` addition, at the ORM level: a `Session` whose Core rollback raises a non-disconnect error during `close()`; afterwards `pool.checkedout() == 0`.

## SA-3. P5a on SQLite (evidence for PY-7, not a new report)

With `autocommit=False` and the explicit `Connection` API, the failed commit leaves the inactive `RootTransaction` on the connection, `Connection.close()` then skips the pool's reset (`engine/base.py` 1270–1283), and the next checkout gets the connection with SQLite outside any transaction: its writes commit by themselves, its `commit()` raises although its write persisted, and its `rollback()` raises without undoing it (`findings.md` F6). This is the mechanism of P5a (`research/python-upstream-contribution-tracker.md`, PY-7) with a different consequence than on PostgreSQL. It belongs with PY-7 when that is written.

## Before posting

- Re-run the scripts on the latest SQLAlchemy release and on `main`.
- Check `main` again for changes to `SessionTransaction.close()`, `NestedTransaction`, `RootTransaction` and the SQLite dialect.
- Repeat the searches in `upstream/duplicate-search.md`.
- Quote the documentation from the released version you test.
