# Methodology

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max).

## Question and invariant

When SQLite ends a transaction that the application did not ask it to end, does the framework that manages the transaction notice, keep later work out of the boundary it no longer has, and avoid reporting success?

The invariant used throughout: a framework must report confirmed transaction outcomes accurately, and must not let operations escape the transaction boundary it claims to manage. SQLite's own behavior is not judged against PostgreSQL's. A difference between SQLite's transaction state and a framework's transaction object is recorded, but it counts as a failure only where it has an observable consequence: a reported commit of work that was not committed, a later write that commits outside the boundary, a lost or masked error, or a connection handed to later work in an unsafe state.

## Relation to earlier PPCS work

- `research/sqlite-phase0/` measured `sqlite3` alone. It observed that `INSERT OR ROLLBACK` ends the transaction and that a later statement can commit by itself under `autocommit=True`. It did not test triggers with `RAISE(ROLLBACK)`, other transaction-control modes after such a rollback, any framework after such a rollback, or realistic causes. This study starts there.
- PPCS's PostgreSQL cases TX-01A (caught error, then commit), TX-02 (failed savepoint rollback), TX-03 (connection reuse) and TX-04 (nested scopes) supplied the shapes. Their PostgreSQL expectations were not carried over: SQLite aborts a statement for most errors, and only some errors end the transaction.
- `research/python-upstream-contribution-tracker.md` PY-20 (Tortoise ORM after a failed `COMMIT`) is a different mechanism and was not repeated.
- The MySQL, transaction-hook, pool-state and Python cancellation investigations belong to other agents. Nothing here runs MySQL, and the async question was stopped by source reading (`findings.md`, SQLITE-07).

## Environment

| Item | Host | Container (SQLITE-05c and the minimal matrix) |
| --- | --- | --- |
| OS | macOS 26.6.2, arm64 | Debian (glibc 2.41), aarch64, in colima 0.9.1, Docker 28.4.0 |
| Python | CPython 3.13.11 (Homebrew); 3.14.2 for one cross-check | CPython 3.13.17 |
| SQLite library | 3.54.1, source id `2026-10-16 14:45:20 555e07ef…`, `THREADSAFE=1`, `DEFAULT_SYNCHRONOUS=2`, `DEFAULT_CACHE_SIZE=-2000`, page size 4096 | 3.46.1 |
| SQLAlchemy | 2.1.6; 2.0.55 for one cross-check | 2.1.6, installed offline from the two wheels pinned by SHA-256 in `repro/sqlite05c_enospc.py` |
| Django | 6.1.2 | not used |
| Image | – | `python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962`, `--network none` |

`output/*/<run>/environment.json` records the interpreter, the library, its compile options and the package versions for every host run. The phase 0 run of 2026-10-19 recorded SQLite 3.53.1 for the same interpreter; Homebrew has upgraded the library since.

Database files are file-backed, one fresh directory per variant and repetition. Journal mode is `DELETE` unless a variant says `wal`. The connections under test that the study opens itself, and the observer, use `timeout=0.0` (`busy_timeout` 0); some setup connections use the module default; SQLAlchemy and Django connections use their own defaults. No recorded step waited on a lock.

## Transaction-control configurations

Python's `sqlite3` offers legacy transaction control (with `isolation_level=""` or `None`), PEP 249 control (`autocommit=False`) and SQLite's own autocommit mode (`autocommit=True`). The four configurations below behave differently after SQLite ends a transaction:

| Name here | How the connection is opened | Who sends `BEGIN` | What `commit()` does with no open transaction |
| --- | --- | --- | --- |
| `explicit` | `autocommit=True` | the application, as SQL | the application sends SQL `COMMIT`, which fails |
| `legacy` | defaults: `autocommit=LEGACY_TRANSACTION_CONTROL`, `isolation_level=""` | the driver, before DML only (trace: `BEGIN `) | returns `None`, sends nothing (documented) |
| `legacy-none` | `isolation_level=None` | the application, as SQL | returns `None`, sends nothing (documented) |
| `pep249` | `autocommit=False` | the driver, at connect and after `commit()`/`rollback()` | raises `OperationalError` (contrary to the documentation, `findings.md` SQLITE-01) |

`Connection.autocommit` (the PEP 249 setting) and `Connection.in_transaction` (SQLite's own state, `!sqlite3_get_autocommit()`) are different things, and the record keeps both.

SQLAlchemy 2.1's SQLite documentation (`dialects/sqlite/base.py`, "Transactions with SQLite and the sqlite3 driver") offers three setups, and every SQLAlchemy experiment runs all three:

| Name here | Setup | `sqlite3` model underneath |
| --- | --- | --- |
| `default` | `create_engine("sqlite:///file")` | `legacy` |
| `autocommit-false` | `connect_args={"autocommit": False}`, "the most straightforward approach" | `pep249` |
| `begin-recipe` | a `connect` hook sets `isolation_level = None`; a `begin` hook emits `BEGIN` | `legacy-none` |

Django 6.1.2's SQLite backend starts `atomic()` blocks with an explicit `BEGIN` while `isolation_level` is `None` (`django/db/backends/sqlite3/base.py`, `_start_transaction_under_autocommit`), which is the `legacy-none` model.

SQLAlchemy engines use a pool of one connection (`pool_size=1`, `max_overflow=0`, as PPCS uses `pool_max: 1`) so that the next unit of work gets the same DBAPI connection if the pool still holds it. `pool_timeout` is 2 s instead of SQLAlchemy's 30 s; it only shortens how long a starved checkout waits before `TimeoutError`.

## What ends the transaction

| Mechanism | Kind | Used in |
| --- | --- | --- |
| `BEFORE UPDATE` trigger with `RAISE(ROLLBACK, 'negative balance')` | deterministic control | SQLITE-01 to -04, -06 |
| The same trigger with `RAISE(ABORT, …)` | statement-level control | same |
| No fault (a debit that does not fire the trigger) | success control | same |
| `UNIQUE … ON CONFLICT ROLLBACK`, declared through SQLAlchemy's `sqlite_on_conflict_unique="ROLLBACK"` | deterministic, a documented SQLAlchemy DDL option | minimal reproductions |
| `PRAGMA max_page_count` a few pages above the current size: a genuine `SQLITE_FULL` | SQLite's own size limit | SQLITE-05, -05b, minimal |
| A tmpfs filled to 3 MiB free: a real `ENOSPC`, which SQLite reports as `SQLITE_FULL` | real resource exhaustion | SQLITE-05c |
| A progress handler that returns non-zero (a statement time limit), and `Connection.interrupt()` from a timer thread: `SQLITE_INTERRUPT` | realistic application mechanisms | SQLITE-05 |
| A child process under `RLIMIT_FSIZE` with `SIGXFSZ` ignored, and `cache_size = 4` so pages reach the file during the statement: `write()` fails with `EFBIG` | a real OS write failure | SQLITE-05 |

No fault is injected into a framework, a driver or SQLite. The trigger and conflict clause are ordinary schema; the size limit, the progress handler and `interrupt()` are documented SQLite and Python APIs; the tmpfs and the file-size limit make the operating system refuse a write. The classification in `findings.md` keeps the deterministic controls apart from the realistic causes.

## Evidence layers

Each layer is recorded separately in every case file.

- **A, SQLite's state.** `Connection.in_transaction` on the connection under test, read at named checkpoints (before the fault, after it, after a later write, after completion). The SQL SQLite actually started, from `Connection.set_trace_callback`, including statements the driver issued on its own (`BEGIN ` in legacy mode, `BEGIN` after a PEP 249 commit). For SQLAlchemy and Django, the DBAPI connection is read directly, never through a framework call that could begin a transaction. A savepoint's existence is not queryable in SQLite; it is inferred from `in_transaction` (no transaction, no savepoint) and from SQLite's answer to `ROLLBACK TO` (`no such savepoint`).
- **B, framework state.** Public APIs: `Connection.in_transaction()`, `Transaction.is_active`, `Session.in_transaction()`, `Session.is_active`, `inspect(obj)` for identity-map state, Django's `needs_rollback`, `in_atomic_block` and `get_autocommit()`. One private attribute, `SessionTransaction._state`, is recorded under a key named `private_session_tx_state`. SQLAlchemy pool and connection events (`checkout`, `checkin`, `reset` with `transaction_was_reset`, `invalidate`) and the pool's own log records are kept.
- **C, persisted state.** A separate `sqlite3` connection, `autocommit=True` and `PRAGMA query_only=ON`, reads the file after each step and at the end. It sees committed rows only. Every row a repetition writes carries that repetition's random token, so no row can be mistaken for another run's.
- **D, external effects.** Callbacks (`after_commit`, `after_rollback`, `after_soft_rollback`, Django's `on_commit`) and the application's own "confirmed" record write to a second database file through a connection of their own, opened per write with `autocommit=True`. A callback can therefore never join the transaction under study.

## Repetitions and agreement

Every variant runs three times on fresh files. The fingerprint of a repetition is its `observed` section and its SQL trace, with that repetition's token replaced by `<token>`. Repetitions agree when the fingerprints are equal, and each run's `summary.json` records the result. Every recorded run agreed on every variant.

## Instrumentation caveats

- **Repeated trace lines.** CPython's trace callback reports a statement again when SQLite starts a trigger subprogram. `repro/trace_check.py` (run `trace-check/2026-10-25T17-21-27Z-d37fff`) shows one execution and one changed row with two trace lines when a trigger's `WHEN` is false, and three when it fires. A repeated `UPDATE` in a trace is not a re-execution.
- **Pool log attribution.** SQLAlchemy logs pool problems through module loggers. Each engine sets `pool_logging_name` to the repetition's token, and a single handler routes each record to the scenario whose pool logged it; anything else goes to `stray-pool-log.json`. A first development run used one global handler and credited one repetition with records from earlier repetitions' connections that the garbage collector finalized later. It was discarded (see `README.md`).
- **Leaked connections.** At the end of each SQLAlchemy scenario the harness records `pool.checkedout()`, runs `gc.collect()`, records it again, and disposes the engine. A connection that was never returned is therefore counted inside its own scenario, and the pool events that the collection triggers are recorded with it.
- **Django isolation.** Each Django repetition runs in a fresh subprocess, so settings and connection state cannot carry over.
- **Errors propagate.** Steps are recorded, then their exceptions are allowed to propagate as they would in an application, except where the variant itself catches them. A development version of the Django experiment swallowed write errors; it was fixed before the recorded run.
- **Exception chains.** A recorded error includes its `__cause__`/`__context__` chain, which is how a masked original error is shown.

## Source reading and runtime claims

Runtime claims come from recorded runs. Statements about third-party code paths are marked as source reading, with the version and file. Where a source-reading expectation was tested, `findings.md` says so; one was wrong in detail (SQLAlchemy's savepoints in the default configuration are not inside the outer transaction at all, which the batch experiment showed).

## Limits

- One host and one container image. macOS's and Linux's SQLite builds agree on every mechanism tested, but other builds were not run.
- `SQLITE_NOMEM` was not produced. `SQLITE_IOERR` was produced only through `EFBIG`; an `EIO` from a failing device was not.
- The real-`ENOSPC` run used tmpfs. Other filesystems were not tested.
- SQLite's list of errors that can cause an automatic rollback ([Response To Errors Within A Transaction](https://www.sqlite.org/lang_transaction.html), retrieved 2026-10-25) is `SQLITE_FULL`, `SQLITE_IOERR`, `SQLITE_INTERRUPT` and `SQLITE_NOMEM`. `SQLITE_BUSY` is not on it; it was not tested here, and phase 0's `COMMIT`/`SQLITE_BUSY` case left the transaction open.
- aiosqlite and SQLAlchemy's asyncio extension were not run (`findings.md`, SQLITE-07).
- Django was run only far enough to compare its handling with SQLAlchemy's, under the same trigger.
