# Findings

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max).

Run directories are under `output/`. Every variant ran three times and every recorded run agreed on every variant. `output/RESULTS.md` has one generated table per experiment; the case files under each run's `cases/` are the raw record. Version and method details are in `methodology.md`.

## Answer

SQLite ends a transaction on its own for documented reasons. In this study that happened with `RAISE(ROLLBACK)` in a trigger, with `UNIQUE … ON CONFLICT ROLLBACK`, and with three realistic failures: `SQLITE_FULL` (a page limit, and a real `ENOSPC`) on a single-row `INSERT` or `UPDATE`, `SQLITE_INTERRUPT` on a write statement, and `SQLITE_IOERR_WRITE` from a real `EFBIG`. The exception does not say whether the transaction survived: `RAISE(ABORT)` and `RAISE(ROLLBACK)` both raise `IntegrityError` with `SQLITE_CONSTRAINT_TRIGGER` (1811). Only `Connection.in_transaction` tells them apart.

SQLAlchemy 2.1.6 (and 2.0.55) does not notice. Its `Connection`, `Transaction` and `Session` stay active after SQLite has ended the transaction. Later statements run in a new implicit transaction, in SQLite's autocommit mode, or, inside SQLAlchemy's own savepoint loop, as one-record transactions that each `RELEASE` commits. In the default and recipe configurations the final commit returns normally. With the SAVEPOINT loop from SQLAlchemy's ORM guide and the `BEGIN` recipe from its SQLite dialect documentation, a real disk-full during a 30-record import left `session.commit()` returning normally: the application reported 29 records committed, and 6 were (SQLITE-05c).

Under `autocommit=False`, the sqlite3 setting both CPython and SQLAlchemy recommend, the final commit raises instead, but the records after the failure are already committed. Three further problems appear in that mode: SQLAlchemy reports the driver's `cannot rollback - no transaction is active` in place of the error that ended the transaction; `Session.close()` keeps the pooled connection checked out until the garbage collector runs; and with the explicit `Connection` API the pool hands the connection to later work outside any transaction. Their common driver cause is that CPython's `sqlite3` does not keep the documented promise that, with `autocommit=False`, "a transaction is always open".

Django 6.1.2 recognizes the loss in its supported patterns: the failed savepoint rollback marks the connection for rollback, later queries are refused, `on_commit()` does not run, and the original error reaches the application.

## Classification

As defined in the assignment: **A** confirmed production-reachable correctness defect; **B** conditional correctness hazard; **C** expected behavior; **D** unsupported application behavior; **E** synthetic-only; **F** inconclusive. A classification describes the observed behavior under recorded conditions. Whether it is a defect is for the maintainers to decide.

## Summary table

| ID | Framework and version | SQLite | Python | Trigger | SQLite transaction state | Framework transaction state | Persisted outcome | Subsequent writes | Completion result | Repetitions | Class | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **F1** | SQLAlchemy 2.1.6, 2.0.55 ORM `Session`, `begin-recipe` | 3.54.1, 3.46.1 | 3.13.11, 3.14.2, 3.13.17 | the documented `begin_nested()` loop with a bare `except`; one record hits `SQLITE_FULL` (real `ENOSPC`, or `max_page_count`), `ON CONFLICT ROLLBACK`, or `RAISE(ROLLBACK)` | ended at the failing record; no transaction afterwards | `Session.in_transaction()` True throughout; the failed savepoint's `no such savepoint` error is swallowed by the loop | every record before the failure absent; every record after it committed | each later record's `SAVEPOINT … RELEASE` began and committed its own SQLite transaction | `session.commit()` returned normally and sent no SQL | 3 per variant, 4 environments | **A** | `sqlite05c-enospc/…-9e213e` `begin-recipe`; `sqlite05b-batch/…-4b67f2` `begin-recipe.*.{full,raise-rollback}`; `minimal-matrix/…-556213` `sa_savepoint_batch-*` |
| F1′ | same, `autocommit-false` | same | 3.13.11, 3.13.17 | same | same | same | records after the failure committed | same | `session.commit()` raised `cannot commit - no transaction is active` | 3 | **B** | `sqlite05c-enospc` `autocommit-false`; `sqlite05b-batch` `autocommit-false.docs-merge-bare-except.*` |
| **F2** | SQLAlchemy 2.1.6 Core and ORM (`session.execute()`), `default` and `begin-recipe` | 3.54.1, 3.46.1 | 3.13.11, 3.14.2, 3.13.17 | caught `IntegrityError` from `RAISE(ROLLBACK)` or `ON CONFLICT ROLLBACK`, then the block continues | ended | `Connection.in_transaction()` and `Transaction.is_active` True; `Session.is_active` True | earlier writes absent; a later write committed alone | `default`: new implicit transaction (`BEGIN `); recipe: SQLite autocommit, visible before completion | `tx.commit()`, `conn.commit()`, `engine.begin()` exit and `session.commit()` returned normally; `after_commit` fired | 3 | **B** | `sqlite02-core/…-ca780e` `{default,begin-recipe}.*.rollback.{write-b,no-write}`; `sqlite03-session/…-85d1f6` `*.execute.rollback.*-continue`; `minimal-matrix` `sa_core_false_commit` |
| **F3** | SQLAlchemy 2.1.6, 2.0.55 ORM, `autocommit-false` | 3.54.1, 3.46.1 | 3.13.11, 3.14.2, 3.13.17 | an error that ended the transaction leaves `with Session(engine)` from a `session.execute()` | none | `Session.close()` raised; the Core connection was never closed | – | – | the pooled connection stayed checked out; later checkouts timed out until `gc.collect()` | 3 | **B** | `sqlite03-session` `autocommit-false.execute.rollback.commit-escape`; `minimal-matrix` `sa_session_close_leak` |
| **F4** | CPython `sqlite3`, `autocommit=False` | 3.54.1, 3.46.1 | 3.13.11, 3.14.2, 3.13.17 | any error that ends the transaction (`RAISE(ROLLBACK)`, `ON CONFLICT ROLLBACK`) | none, and it stays so | `autocommit` False; `commit()` and `rollback()` raise | the next unit's write committed although it then called `rollback()` | SQLite autocommit | `commit()`: `cannot commit - no transaction is active`; `rollback()`: `cannot rollback …`; neither opens a transaction | 3 | **A** | `sqlite01-raw/…-737440` `pep249.rollback.*`; `minimal-matrix` `sqlite3_autocommit_false` |
| F5 | SQLAlchemy 2.1.6 Core and ORM, `autocommit-false` | 3.54.1 | 3.13.11 | as F2, or the error leaves the block | ended | as F2 | as F1′ | SQLite autocommit | the error that reaches the application is `cannot rollback - no transaction is active`; the original is only in `__context__` | 3 | **B** | `sqlite02-core` `autocommit-false.*.rollback.escape`; `sqlite03-session` `autocommit-false.flush.rollback.*`; `sqlite04-savepoint` `autocommit-false.*.catch-specific` |
| F6 | SQLAlchemy 2.1.6 Core and ORM, `autocommit-false`, `conn.begin()`/`tx.commit()`, commit-as-you-go, `session.commit()` | 3.54.1 | 3.13.11 | as F2 | none | the failed commit leaves the connection to be returned without a pool reset | N1 committed although its commit raised; N2 committed although it rolled back | SQLite autocommit, on the same pooled connection | later units' `commit()` and `rollback()` raise; ends when a pool reset fails and invalidates the connection | 3 | **B** | `sqlite02-core` `autocommit-false.{explicit,commit-as-you-go}.rollback.{write-b,no-write}`; `sqlite03-session` `autocommit-false.execute.rollback.commit-continue` |
| F7 | SQLite (via `sqlite3`) | 3.54.1, 3.46.1 | 3.13.11, 3.13.17 | realistic failures, explicit transaction | ended for single-row `INSERT`/`UPDATE` + `SQLITE_FULL`, write + `SQLITE_INTERRUPT`, write + `SQLITE_IOERR_WRITE`; statement only for `INSERT … SELECT` + `SQLITE_FULL` and a read + `SQLITE_INTERRUPT` | – | when ended: earlier writes absent | autocommit | SQL `COMMIT`: `cannot commit - no transaction is active` | 3 | C (documented); the trigger reachability for F1–F6 | `sqlite05-realistic/…-001c2c`; `sqlite05c-enospc` `raw` |

Negative and other results:

| ID | What | Class | Evidence |
| --- | --- | --- | --- |
| N1 | `RAISE(ABORT)`: the transaction survives in every `sqlite3` mode and every SQLAlchemy and Django configuration; the earlier and later writes commit; the documented savepoint patterns skip only the failing record | C | `RAISE(ABORT)` rows in every run |
| N2 | SQLAlchemy flush path: the flush rolls the `Session` back itself and `session.commit()` raises `PendingRollbackError`; nothing is committed | C | `sqlite03-session` `*.flush.rollback.commit-continue` |
| N3 | `with session.begin()` exits without raising after a caught flush error, and nothing is committed. PPCS's PostgreSQL run records the same (`adapters/sqlalchemy/FINDINGS.md`, TX-01A); not SQLite-specific | C | `sqlite03-session` `*.flush.rollback.begin-continue` |
| N4 | The documented savepoint pattern that catches `IntegrityError` only: the nested scope's `ROLLBACK TO` fails with `no such savepoint`, that error escapes the outer block, which rolls back; nothing is committed. The original error is masked (SQLAlchemy ticket #2696 describes the same masking on MySQL) | C, masking noted | `sqlite04-savepoint` `*.rollback.catch-specific`; `sqlite05b-batch` `*.docs-add-integrityerror.*` |
| N5 | `default` configuration with the documented savepoint loop: each savepoint is its own transaction, so the loop was never atomic. This is SQLAlchemy's documented legacy-mode SAVEPOINT caveat; the `IntegrityError` loop raised while records 1–4 were committed, and with a real `ENOSPC` records 1–15 were committed and the final commit raised | C | `sqlite05b-batch` `default.*`; `sqlite05c-enospc` `default` |
| N6 | Django 6.1.2, the documented nested `atomic()` pattern with `RAISE(ROLLBACK)`: the failed savepoint rollback sets `needs_rollback`; the original `IntegrityError` reaches the application; the next query raises `TransactionManagementError`; `on_commit` does not run; nothing is committed | C | `sqlite06-django/…-b4103f` `rollback.*.nested-catch` |
| N7 | Django, the same pattern with no query after the handled error: `atomic()` exits without raising and rolls back; `on_commit` does not run. Django documents a rollback at the end of the block after a database error | C | `sqlite06-django` `rollback.*.nested-catch-no-b` |
| N8 | Django, a raw-cursor error caught inside `atomic()` without a nested block: `on_commit` ran and only the later write committed. Django's documentation calls this path "unspecified and database-dependent"; PPCS recorded the same shape on PostgreSQL | D | `sqlite06-django` `rollback.raw.plain-catch` |
| N9 | sqlite3 `legacy` and `legacy-none`: `commit()` with no open transaction returns without SQL, as documented. The later write's placement (new implicit transaction, or autocommit) is documented behavior of those modes | C | `sqlite01-raw` `{legacy,legacy-none}.rollback.*` |
| X1 | SQLITE-07, aiosqlite and async cancellation: not run. Source reading (aiosqlite 0.22.1, `core.py` 150–160 and 258–260): cancelling an awaiting coroutine does not call `sqlite3_interrupt()`, so cancellation has no SQLite-specific path to the automatic rollback; what remains is the async-cancellation question another agent owns | not run (stop rule) | – |
| S1 | Side observation, source reading: SQLAlchemy dispatches `after_commit` on every savepoint `RELEASE` as well as on the outer commit (`orm/session.py` 1332–1340); its docstring does not say so. Not SQLite-specific | – | `sqlite05b-batch` sink rows |

## F1: the documented SAVEPOINT loop loses every record before a transaction-ending error, and the commit reports success

**Setup.** SQLAlchemy's ORM guide, "Using SAVEPOINT" (`doc/build/orm/session_transaction.rst` at `rel_2_1_6`, lines 157–168), recommends `begin_nested()` "where specific per-instance errors may be caught … without rolling back the whole transaction", with this loop:

```python
for record in records:
    try:
        with session.begin_nested():
            session.merge(record)
    except:
        print("Skipped record %s" % record)
session.commit()
```

The engine uses the recipe from SQLAlchemy's SQLite dialect documentation, which exists so that savepoints and transactional DDL work: a `connect` hook sets `isolation_level = None` and a `begin` hook emits `BEGIN`.

**Observed, real disk full (SQLITE-05c, Linux container, Python 3.13.17, SQLite 3.46.1, SQLAlchemy 2.1.6).** A tmpfs left 3 MiB free; 30 records of 200 KiB. Record 24's `INSERT` failed with `SQLITE_FULL`. (The 23 records before it, 4.6 MB, are more than SQLite's 2000 KiB page cache holds, so pages were being written to the full disk during the transaction; which write failed was not traced.) The loop printed one skipped record. `session.commit()` returned normally. The application's view: records 1–23 and 25–30 committed. An independent connection: 25–30 only. Three of three. (`output/sqlite05c-enospc/2026-10-25T17-22-54Z-9e213e/cases/begin-recipe.rep{1,2,3}.json`)

**Observed, host (SQLITE-05b, SQLite 3.54.1).** Ten records, record 5 too large. With `max_page_count` (a genuine `SQLITE_FULL`) and with `RAISE(ROLLBACK)`: `session.commit()` returned, the application reports 1–4 and 6–10, the database holds 6–10. The Core form of the loop (`engine.begin()`, `conn.begin_nested()`, `except Exception`) gives the same result. With `RAISE(ABORT)` the loop works as documented: only record 5 is missing.

**Layer A and B, per record** (`begin-recipe.docs-merge-bare-except.raise-rollback.rep1.json`, `per_record`): records 1–4 end with SQLite inside the transaction and `Session.in_transaction()` True. Record 5 ends with the handled error `no such savepoint: sa_savepoint_5`, SQLite outside any transaction, and `Session.in_transaction()` still True. Records 6–10 each end with SQLite outside any transaction. The trace after record 5 is `ROLLBACK TO SAVEPOINT sa_savepoint_5` (failed), `SAVEPOINT sa_savepoint_6`, the `INSERT`, `RELEASE SAVEPOINT sa_savepoint_6`, with no `BEGIN`; the trace ends with `RELEASE SAVEPOINT sa_savepoint_10` and `session.commit()` sends nothing. The no-fault control ends with `COMMIT`.

**Minimal reproduction** (`repro/minimal/sa_savepoint_batch.py`, about 60 lines, no harness). Same output in all four environments, three runs each (`output/minimal-matrix/2026-10-25T18-21-01Z-556213/`):

```
Skipped record b
session.commit() returned
committed: ['d', 'e']
```

for `on-conflict` (a duplicate under `sqlite_on_conflict_unique="ROLLBACK"`), and the same with `Skipped record big` for `page-limit` (`SQLITE_FULL`). Records a, b and c were never committed.

**Classification: A.** The application code is SQLAlchemy's documented example; the configuration is SQLAlchemy's documented one; the trigger is a full disk on an ordinary single-row insert; the consequence is externally observable (rows the application reports as committed are absent) and contradicts both the documented purpose of the loop and the meaning of a returned `commit()`. Under `autocommit=False` (F1′) the commit raises, so the application is told something failed, but the records after the failure are already committed, and a retry of the whole batch could write them twice; that is classified B.

### Root cause

1. **Smallest program:** `repro/minimal/sa_savepoint_batch.py`.
2. **Framework versions:** SQLAlchemy 2.1.6 and 2.0.55. On `main` at `10f4d1e2d` (2026-10-23), `engine/base.py` and the SQLite dialect have no commits since the 2.1.6 release, and `SessionTransaction.close()` is unchanged; the two later commits to `orm/session.py` concern `merge_all()` and the replaced-identity check (titles; not otherwise read).
3. **SQLite versions:** 3.54.1 (host) and 3.46.1 (container).
4. **The SQLite error:** `SQLITE_FULL` (13) "database or disk is full" on a single-row `INSERT`, or a constraint error under the `ROLLBACK` resolution. SQLite documents both as ending the transaction ([lang_transaction.html](https://www.sqlite.org/lang_transaction.html), [lang_conflict.html](https://www.sqlite.org/lang_conflict.html)); SQLITE-05 shows which statement shapes end it.
5. **The DBAPI exceptions:** `sqlite3.OperationalError` or `sqlite3.IntegrityError` from the `INSERT`; then `sqlite3.OperationalError: no such savepoint: sa_savepoint_N` from the nested scope's `ROLLBACK TO SAVEPOINT`.
6. **Framework transitions (source reading, 2.1.6):** the statement error takes the non-disconnect branch of `Connection._handle_dbapi_exception` (`engine/base.py` 2329–2340), which closes the cursor and rolls back only when no SQLAlchemy transaction is in progress (2340). The nested scope's exit calls `NestedTransaction._do_rollback` (2843) → `_close_impl` (2820) → `_rollback_to_savepoint_impl` (1184), which raises; the nested transaction is deactivated, and the `RootTransaction` (2645) remains active. The ORM's `SessionTransaction.rollback()` captures and re-raises that error (`orm/session.py` 1377, 1412) and leaves the root `SessionTransaction` active. The next `begin_nested()` emits `SAVEPOINT`; with no transaction open, SQLite treats an outermost savepoint as `BEGIN DEFERRED TRANSACTION` and its `RELEASE` as `COMMIT` ([lang_savepoint.html](https://www.sqlite.org/lang_savepoint.html)). `session.commit()` reaches `DefaultDialect.do_commit` (`engine/default.py` 953), which calls `sqlite3.Connection.commit()`; in legacy transaction control that is a documented no-op when no transaction is open.
7. **Where state diverges:** at the failing statement. SQLite reports no transaction (`sqlite3_get_autocommit()` true, Python's `in_transaction` False); SQLAlchemy's root transaction stays active and nothing consults the driver again.
8. **Which layer:** SQLAlchemy. SQLite and CPython's legacy transaction control behave as documented. SQLAlchemy can see what happened: in the recipe and `autocommit=False` configurations a transaction is open from the start of every SQLAlchemy transaction, so `in_transaction` False inside one means it was ended underneath SQLAlchemy; in the default configuration a check would have to compare the state before and after the failing statement. SQLAlchemy reads neither and keeps its transaction active. The documented example's bare `except` turns the resulting `no such savepoint` into a skipped record.
9. **Smallest plausible correction (proposal, not implemented):** when a DBAPI error occurs inside a SQLAlchemy transaction on the SQLite dialects, read `dbapi_connection.in_transaction`; if SQLite reports no transaction while SQLAlchemy's root transaction is active and has begun one, put the root transaction into the existing "invalid transaction" state, as a disconnect does, so that later statements, savepoints and `commit()` raise until the application rolls back. A narrower variant applies the same check only when `ROLLBACK TO SAVEPOINT` fails. Documentation changes could accompany either: say in the SQLite dialect documentation which SQLite errors end a transaction and that `sqlite_on_conflict="ROLLBACK"` does so, and catch a specific exception in the SAVEPOINT example.
10. **Regression tests (proposed):** (a) the documented loop under the recipe and under `autocommit=False` with an `ON CONFLICT ROLLBACK` table: after the failing record, `commit()` (or the next `begin_nested()`) raises and no record is committed; (b) Core: an `IntegrityError` that ended the transaction, caught, then `conn.commit()` raises; (c) the `ON CONFLICT ABORT` control: the loop skips only the failing record and commits the rest.

## F2: a caught error that ended the transaction, then a reported commit (no savepoint)

`repro/minimal/sa_core_false_commit.py` (default engine): the block debits an account, skips a duplicate reference that violates `UNIQUE … ON CONFLICT ROLLBACK`, writes an audit row, and exits. It prints:

```
duplicate transfer reference skipped
SQLAlchemy in_transaction(): True | sqlite3 in_transaction: False
engine.begin() block committed without error
balance: 100
audit: ['debited 30']
```

The debit is gone; the audit row saying it happened is committed. In SQLITE-02 (81 variants) the same holds for `conn.begin()`/`tx.commit()`, commit-as-you-go and `engine.begin()`, in the `default` and `begin-recipe` configurations. In SQLITE-03 the ORM `session.execute()` path behaves the same, `after_commit` fires, and the identity map keeps the discarded state: account 1 has `balance == 70` in memory and the database has 100, and ledger row A is "persistent" with no row. SQLite then reused rowid 1 for ledger row B, and the flush warned `Identity map already had an identity for (Ledger, (1,), None), replacing it with newly flushed object`.

**Classification: B.** It needs an application that catches a database error inside the transaction and continues. SQLAlchemy Core does not forbid that, and on SQLite it is how statement-level errors are normally handled; the error the application catches is the same one an `ABORT` produces. The root cause is F1's (items 6–9), without the savepoint step.

## F3: `Session.close()` keeps the pooled connection when the rollback inside it raises

`repro/minimal/sa_session_close_leak.py` (`autocommit=False`, a pool of one): an `INSERT` through `session.execute()` violates `ON CONFLICT ROLLBACK` inside `with Session(engine)`, and the error leaves the block. Same output in all four environments, three runs each:

```
left the block: OperationalError - (sqlite3.OperationalError) cannot rollback - no transaction is active
exception chain: sqlalchemy.OperationalError <- sqlite3.OperationalError <- sqlalchemy.IntegrityError <- sqlite3.IntegrityError
checked out after the block: 1
next checkout: TimeoutError
pool logged: Exception during reset or similar (OperationalError: cannot rollback - no transaction is active)
checked out after gc.collect(): 0
next checkout after gc.collect(): 1
```

In SQLITE-03 (`autocommit-false.execute.rollback.commit-escape`) the next three checkouts each failed with `QueuePool limit of size 1 overflow 0 reached`; `pool.checkedout()` was 1 at the end, and `gc.collect()` produced `reset (transaction_was_reset=False)`, `invalidate`, `checkin`. The flush path does not leak: the flush deactivates the Core transaction first, so `close()` reaches `connection.close()`.

**Classification: B.** It needs a rollback that raises an error SQLAlchemy does not classify as a disconnect. `autocommit=False` after a transaction-ending SQLite error produces one deterministically (F4).

### Root cause

1. **Smallest program:** `repro/minimal/sa_session_close_leak.py`.
2. **Versions:** SQLAlchemy 2.1.6 and 2.0.55; `SessionTransaction.close()` on `main` `10f4d1e2d` is unchanged.
3–5. SQLite 3.54.1 and 3.46.1; `SQLITE_CONSTRAINT_UNIQUE` under the `ROLLBACK` resolution ends the transaction; `sqlite3.OperationalError: cannot rollback - no transaction is active` from the close's rollback.
6. **Transitions (source reading, 2.1.6):** `SessionTransaction.close()` (`orm/session.py` 1422–1438) sets `session._transaction` to the parent, then for each connection calls `transaction.close()` and only afterwards `connection.close()`. `transaction.close()` rolls back the still-active Core transaction and raises. `connection.close()` is never reached, so the Core `Connection` and its pooled DBAPI connection stay checked out, `_state` is not set to `CLOSED`, and `after_transaction_end` is not dispatched.
7. **Divergence:** the Session has detached its transaction, while the Core connection is still open and checked out.
8. **Layer:** SQLAlchemy ORM. Core's `Connection.close()` was fixed for exactly this case in #13657 (commit `d29277af`, 2026-10-06: "an exception raised by the rollback performed within Connection.close(), which was not otherwise classified as a disconnect, would leave … its pooled DBAPI connection checked out"). That fix changed `engine/base.py` and the asyncpg dialect only. In the ORM path the rollback runs in `transaction.close()`, before `Connection.close()` is called, so the fix does not apply.
9. **Smallest plausible correction (proposal):** close the connection in a `finally` around `transaction.close()` in `SessionTransaction.close()`, so that `Connection.close()` and its #13657 handling (return the connection, let the pool reset it, invalidate it if that fails) always run, and keep the first exception.
10. **Regression test (proposed):** in the style of #13657's `test/engine/test_reconnect.py` test, at the ORM level: a `Session` whose Core rollback raises a non-disconnect error during `close()`; assert `pool.checkedout() == 0` afterwards.

## F4: `sqlite3` with `autocommit=False` does not keep a transaction open after SQLite ends one

CPython's documentation for 3.13 (`Doc/library/sqlite3.rst` at `v3.13.11`): `autocommit=False` means "`sqlite3` ensures a transaction is always open" (lines 1371–1373, 2678–2681), and `commit()` and `rollback()`: "If `autocommit` is `True`, or there is no open transaction, this method does nothing" (670–684).

`repro/minimal/sqlite3_autocommit_false.py` prints, in all four environments:

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

Row 2, written after the failed calls, was committed by itself, and the `rollback()` that followed it raised and undid nothing. SQLITE-01 shows the same with `RAISE(ROLLBACK)`: the next unit of work's write N persisted after its `rollback()` raised. Re-assigning `autocommit = False` or executing `BEGIN` restores a transaction; `rollback()` does not (`pep249.rollback.no-write.recover-*`).

**Source (CPython `Modules/_sqlite/connection.c`, `v3.13.11` 711–764, `main` `efbd1653` 752–805, identical):** with `AUTOCOMMIT_DISABLED`, `commit()` and `rollback()` execute `COMMIT` or `ROLLBACK` unconditionally and return the error before the `BEGIN` that follows. With legacy control they first check `sqlite3_get_autocommit()`.

**Classification: A** at the driver layer: a documented guarantee is violated, the trigger is production-reachable (F7), and the consequence, a later write committed despite the application's `rollback()`, is externally observable. It is also the mechanism behind F3, F5 and F6.

### Root cause

1. **Smallest program:** `repro/minimal/sqlite3_autocommit_false.py` (sqlite3 only).
2. **Version:** CPython 3.13.11, 3.13.17, 3.14.2; `main` unchanged.
3–5. SQLite 3.54.1 and 3.46.1; any error that ends the transaction; `OperationalError` from `commit()` and `rollback()`.
6–7. The module's PEP 249 bookkeeping assumes only its own `COMMIT`/`ROLLBACK` end a transaction. After SQLite ends one, no transaction is open, statements run in SQLite's autocommit mode, and the next `commit()`/`rollback()` fails before it can begin a new one.
8. **Layer:** CPython's `sqlite3`. The implicit `BEGIN` after a commit or rollback is the module's own documented responsibility.
9. **Corrections to consider (the maintainers' choice):** make `rollback()` a no-op that still opens a new transaction when none is open, as documented; keep `commit()` raising, since reporting success for work SQLite discarded would be wrong, but open a new transaction before raising; or document the behavior. A maintainer's comment on gh-112441 (2023, closed as not planned) restates the invariant: "`autocommit=False` implies PEP-249 compliant behaviour, meaning a transaction **is always open**." That issue concerned SQL issued by the user; this one is SQLite's own rollback.
10. **Regression tests (proposed):** in `Lib/test/test_sqlite3/test_transactions.py`, with `autocommit=False` and an `ON CONFLICT ROLLBACK` constraint: after the violation, `rollback()` succeeds and `in_transaction` is True; a later insert is not visible to a second connection before `commit()`.

## F5 and F6: two further consequences under `autocommit=False`

- **F5, a masked error.** Whenever SQLAlchemy rolls back in response to the error (a flush failure, a context manager's exit, `Connection.close()`, `Session.close()`), the driver's `cannot rollback - no transaction is active` becomes the exception the application sees. An application that catches `IntegrityError` to handle the business case does not see it. SQLAlchemy ticket #2696 (2013) describes the same masking when MySQL had "already automatically rolled back by itself, and so destroyed savepoints"; its resolution relied on Python 3's exception chaining.
- **F6, unsafe reuse.** With `conn.begin()`/`tx.commit()` or commit-as-you-go, the failed commit leaves the inactive `RootTransaction` on the connection (`engine/base.py` 2724–2742: "only remove as the connection's current transaction if commit succeeded"). `Connection.close()` then closes it without a rollback and tells the pool the transaction was reset (1270–1283), so the pool does not reset the connection. The next checkout gets it with SQLite outside any transaction while `sqlite3` still believes PEP 249 control is in force: N1's write committed although its `commit()` raised, and N2's write committed although it rolled back. A pool reset that failed then invalidated the connection, and N3 got a new one. `engine.begin()` rolls back after the failed commit, the pool's reset fails, and the connection is invalidated at once, so later units are safe. This is the mechanism PPCS recorded as P5a (`research/python-upstream-contribution-tracker.md`, PY-7) on PostgreSQL, where it commits the doomed writes on the next checkout. On SQLite with `autocommit=False` it hands out a connection with no transaction control at all.

Both are classified **B**. Their driver cause is F4; F6's pool behavior is SQLAlchemy's (PY-7).

## F7: which realistic SQLite failures end the transaction

SQLITE-05 (`output/sqlite05-realistic/2026-10-25T17-22-41Z-001c2c/`), both journal modes, three of three:

| Failure | Statement | SQLite after the error |
| --- | --- | --- |
| `SQLITE_FULL` from `max_page_count` | single-row `INSERT` (with or without a `UNIQUE` index), single-row `UPDATE` | transaction ended |
| `SQLITE_FULL` from `max_page_count` | `INSERT … SELECT` of 64 rows (with or without a `UNIQUE` index) | statement only |
| `SQLITE_INTERRUPT`, from a progress handler and from `Connection.interrupt()` on a timer thread | `INSERT … SELECT` | transaction ended |
| `SQLITE_INTERRUPT`, from a progress handler | a `SELECT` | statement only |
| `SQLITE_IOERR_WRITE` (778) from a real `EFBIG` | single-row `INSERT`, and an `UPDATE` of 24 rows | transaction ended |

SQLITE-05c adds a real `ENOSPC` on Linux: `SQLITE_FULL` at record 24 of a single-row `INSERT` loop, transaction ended, none of the 23 earlier records committed.

This matches SQLite's documentation: the errors that "can cause an automatic rollback" are `SQLITE_FULL`, `SQLITE_IOERR`, `SQLITE_INTERRUPT` and `SQLITE_NOMEM`; "depending on the statement being evaluated and the point at which the error occurs, it might be necessary for SQLite to rollback and cancel the entire transaction"; and for `sqlite3_interrupt()`, "if the interrupted SQL operation is an INSERT, UPDATE, or DELETE that is inside an explicit transaction, then the entire transaction will be rolled back automatically". The statement-shape split matches a source reading of `sqlite3VdbeHalt` (a statement journal only for multi-row writes that may abort), which was then tested.

## Production reachability

| Trigger | Assessment |
| --- | --- |
| A full disk during a write transaction, on a single-row statement (the shape ORMs flush) | production-reachable. Reproduced with a real `ENOSPC` (SQLITE-05c) |
| `PRAGMA max_page_count` | a real SQLite limit that applications set to cap database size; realistic but uncommon |
| `SQLITE_IOERR` during a write | realistic but uncommon; reproduced only through `EFBIG` under a file-size limit |
| `SQLITE_INTERRUPT` of a write | realistic but uncommon: statement time limits built on a progress handler, or `interrupt()` from another thread |
| `RAISE(ROLLBACK)` in a trigger, and `ON CONFLICT ROLLBACK` (which SQLAlchemy can emit with `sqlite_on_conflict="ROLLBACK"`) | production-valid schema features; deterministic; uncommon |

F1 needs one of these during a batch that uses the documented loop with a broad `except`. F2 needs an application that continues after catching a database error. F3, F5 and F6 need `autocommit=False`, which SQLAlchemy's documentation presents as the most straightforward non-legacy mode, and CPython's documentation recommends.

## Adversarial checks

| Question | Answer and evidence |
| --- | --- |
| Did SQLite actually end the transaction? | Yes: `in_transaction` False right after the error; the writer's own read no longer shows its earlier rows (SQLITE-01); an independent connection never sees them. |
| Statement-level or transaction-level? | Transaction-level for the triggers above; the `ABORT` control and the statement-level shapes in F7 keep the transaction, and every framework then behaves correctly (N1). |
| Was the application using the API correctly? | F1 uses SQLAlchemy's documented loop and documented configuration verbatim. F2 continues after a caught error, which Core permits and SQLite's statement-level errors normally allow; classified B for that reason. N8 is documented as unspecified and classified D. |
| Is the behavior documented? | No SQLAlchemy documentation found mentions SQLite ending a transaction (`doc/` and the SQLite dialect at `rel_2_1_6`, searched for `RAISE(ROLLBACK`, `ON CONFLICT ROLLBACK`, `SQLITE_FULL`, `disk is full`, `rolled back automatically`, `no such savepoint`, `in_transaction`). The legacy-mode SAVEPOINT caveat is documented and explains N5, not F1. |
| Was a new transaction started intentionally? | No. In F1 SQLite began one per `SAVEPOINT`; in F2 the driver's legacy implicit `BEGIN` or SQLite's autocommit placed the later write. |
| Did `sqlite3`'s transaction-control mode matter? | Yes, and every mode was run: legacy and `isolation_level=None` report success; `autocommit=False` raises but leaks later writes and connections. |
| Did SQLAlchemy's autobegin explain the later write? | No. SQLAlchemy emitted no `BEGIN` after the failure in any configuration (traces). |
| Did the ORM merely keep an object in memory? | The identity-map state (F2) is consistent with SQLAlchemy's false commit and is not counted separately. The failures are in the database (Layer C) and in reported outcomes. |
| Was the connection actually reused? | F6: the trace and pool events show the same DBAPI connection serial; F3: the next checkout timed out. |
| Committed or uncommitted data? | The observer is a separate connection with `query_only`; it reads only committed rows. B in F2's recipe rows was visible to it before the completion call, which shows it had committed. |
| Could a correct framework do better? | Django 6.1.2 did, in its supported patterns (N6). |
| Private monkeypatching? | None. The harness adds trace callbacks, event listeners and a log handler; the minimal reproductions use public APIs only. |
| Three repetitions, and without the harness? | Every variant three of three; the five minimal reproductions byte-identical across three runs in each of four environments (Python 3.13.11, 3.14.2, 3.13.17; SQLite 3.54.1, 3.46.1; SQLAlchemy 2.1.6, 2.0.55). |

## Prior reports

Searched on 2026-10-25; the queries and results are in `upstream/duplicate-search.md`. Nothing reports F1, F3 or F4. Related: SQLAlchemy #2696 (2013, MySQL lost savepoint masks the error), #5968 (2021, `ON CONFLICT IGNORE` breaks the ORM's assumption that an INSERT either succeeds or raises), #13657 (2026, the Core form of F3, fixed in `d29277af`), and CPython gh-112441 (2023, the "transaction is always open" invariant).

## Upstream status

Nothing has been filed, posted or pushed. `upstream/` holds:

- `sqlalchemy-facts.md`: facts, scripts and outputs for F1, F2 and F3. SQLAlchemy's code of conduct and contributing guide ask that issue and discussion text be the reporter's own words, so this is not a draft to paste.
- `cpython-sqlite3-autocommit-false-draft.md`: a draft issue for F4, for review. CPython's devguide asks that the person filing be able to explain the report in their own words; disclosure of AI assistance is appreciated.
