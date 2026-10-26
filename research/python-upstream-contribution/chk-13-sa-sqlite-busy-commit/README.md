# CHK-13: a real `SQLITE_BUSY` at `COMMIT` reaches SQLAlchemy's P5a path

Written by: Claude Opus 5.5 (max). Run 2026-10-26 (UTC). Nothing posted. For PY-7.

**ID.** It was run under the working name CHK-9. The tracker records it as CHK-13, because CHK-9 to CHK-12 were assigned to other checks in the meantime. The script and output names keep the working name. The scripts are byte-identical to the ones that ran.

**Question.** PY-7 (P5a) was confirmed only with an injected `commit()` failure on PostgreSQL. Does an ordinary production event reach the same path without injection?

**Candidate trigger.** In SQLite's default rollback-journal mode, `COMMIT` fails with `SQLITE_BUSY` ("database is locked") while another connection holds a read transaction. SQLite documents that the transaction then stays active.

**Answer (observed, 3 of 3 in every case, SQLAlchemy 2.1.6 and 2.0.55).** Yes, when the code closes after the failed commit without calling `rollback()`. This holds in two configurations:
- the default pysqlite configuration;
- `autocommit=False`.

It holds in both flows tested:
- Core commit-as-you-go (`with engine.connect()`, `conn.commit()`);
- the ORM (`with Session(engine)`, `session.commit()`).

In each such case:
1. `commit()` raises `database is locked`, and the DBAPI connection stays in its transaction.
2. `close()` sends no rollback. The pool's `reset` event gets `transaction_was_reset=True` while `in_transaction` is true.
3. The pooled connection keeps its SQLite lock. Even after the reader finished, an independent connection could neither read nor write (`database is locked`).
4. The next checkout gets the same connection, still inside that transaction. Its `commit()` stores the failed unit's row along with its own.

## Setup

**Environment:** Python 3.13.11 (Homebrew), SQLite 3.54.1, SQLAlchemy 2.1.6 and 2.0.55, macOS arm64.

**Trigger.** Each case uses a fresh file database in `journal_mode=delete`.
1. The writer inserts a row.
2. `scripts/reader.py`, in a separate process, runs `BEGIN` and `SELECT count(*)`, and holds that read transaction.
3. The writer's commit hits the busy timeout. That timeout is 0.2 s, or `sqlite3`'s default of 5 s in one case.

Nothing is injected.

**Configurations:**
- `default`: pysqlite as SQLAlchemy configures it;
- `begin-recipe`: the SQLite dialect documentation's recipe (`isolation_level = None` plus `BEGIN` on the `begin` event);
- `autocommit-false`: `connect_args={"autocommit": False}`.

**Flows:**
- `core`: `with engine.connect() as conn`, an insert, `conn.commit()`;
- `session`: `with Session(engine) as session`, an insert, `session.commit()`;
- `engine.begin`: `with engine.begin() as conn`, an insert.

The rollback set adds `conn.rollback()` or `session.rollback()` in the `except` before the block closes.

**Next unit.** Each case is followed by `with engine.connect()`, an insert of row 2, and a commit. It runs on the default pool, which reuses the one connection.

**Ground truth:**
- **Rows:** a fresh `sqlite3` connection reads which rows committed, after `engine.dispose()`.
- **Locks:** probes from an independent connection, each with a 0.1 s timeout. The write probe runs `BEGIN IMMEDIATE`; the read probe runs `BEGIN` plus a `SELECT`.

**Instrumentation.** It changes no behaviour:
- a `PoolEvents.reset` listener records `reset_state`;
- `dialect.do_rollback` is wrapped to record each call, and then calls through.

## Main set

The records in `cases.jsonl` are byte-identical on 2.1.6 and 2.0.55.

| Configuration | Flow | `commit()` | Doomed row 1 | Next unit | Locks while pooled |
| --- | --- | --- | --- | --- | --- |
| default | core | raises `database is locked` | **committed by the next unit** | same connection, still in the transaction; commit resolves | reads and writes blocked |
| default | session | raises | **committed by the next unit** | same | blocked |
| default | engine.begin | raises | rolled back | clean | free |
| begin-recipe | core | raises | rolled back by the next unit's error handling | **fails: `cannot start a transaction within a transaction`** | blocked |
| begin-recipe | session | raises | same | **fails, same error** | blocked |
| begin-recipe | engine.begin | raises | rolled back | clean | free |
| autocommit-false | core | raises | **committed by the next unit** | same connection, still in the transaction | blocked |
| autocommit-false | session | raises | **committed by the next unit** | same | blocked |
| autocommit-false | engine.begin | raises | rolled back | clean | free |
| default, 5 s default timeout | core | raises after 5 s | **committed by the next unit** | same | blocked |
| control: no reader | core | resolves | committed (intended) | resolves | free |
| control: WAL | core | resolves; WAL readers do not block `COMMIT` | committed (intended) | resolves | free |

## Rollback set (`rollback()` in the `except`, then close)

The records are byte-identical on both versions.

| Configuration | Flow | Doomed row | Next unit |
| --- | --- | --- | --- |
| default | core+rollback | rolled back | clean, commits only row 2 |
| default | session+rollback | rolled back | clean |
| autocommit-false | core+rollback | rolled back | clean |
| autocommit-false | session+rollback | rolled back | clean |

**Why the explicit rollback helps (observed).**
- **Core:** `conn.rollback()` returns without sending a DBAPI rollback, so the connection is still `in_transaction` afterwards. That matches the PostgreSQL note in PY-7's review. It does clear the leftover transaction marker. `close()` then takes the normal path (`transaction_was_reset=False`), and the pool's reset-on-return sends the `ROLLBACK`.
- **ORM:** `session.rollback()` returns the connection through that same reset.

## What this changes for PY-7

PY-7 no longer depends on an injected failure. On SQLite, the trigger is a common production error, "database is locked" at `COMMIT` in the default journal mode, with another process reading. It is reached through the commit-as-you-go and `with Session(...)` patterns when the failure ends the block and nothing calls `rollback()`.

Two consequences follow:
- **Silent and wrong.** The next unit of work commits the failed unit's writes.
- **Operational.** Until that connection is used again, no other connection can read or write the database.

The PostgreSQL side of PY-7 is unchanged. It is still reproduced only with an injected `commit()` failure.

## Not established

- Linux, and Python versions other than 3.13.11.
- A pool with several connections, where the stranded connection may sit idle while other connections fail. Only the one-connection sequence was run.
- `with Session(engine) as session, session.begin():`.
- Framework integrations, for example a session closed in a request teardown. They have the same shape as the `session` flow, but were not run.
- Writer-writer contention in WAL mode.

## Reproduce

```sh
python3.13 -I -m venv venv && venv/bin/python -I -m pip install --only-binary=:all: sqlalchemy==2.1.6
venv/bin/python -I scripts/chk9.py out/run-main 3 main
venv/bin/python -I scripts/chk9.py out/run-rollback 3 rollback
```

## Files

| File | sha256 (first 16) |
| --- | --- |
| `scripts/chk9.py` | `addb9b9fad5fa015` |
| `scripts/reader.py` | `2bedd7227db2b066` |
| `out/sa-{2.1.6,2.0.55}/main/2026-10-26T05-20-11Z/cases.jsonl` (identical) | `316bac3076467c05` |
| `out/sa-{2.1.6,2.0.55}/rollback/2026-10-26T05-20-11Z/cases.jsonl` (identical) | `4824afceca265af9` |
| `out/sa-2.1.6/main/…/summary.json` | `65cd191e479f5619` |
| `out/sa-2.0.55/main/…/summary.json` | `e479f2932b657704` |
| `out/sa-2.1.6/rollback/…/summary.json` | `64e2d3ae6a598556` |
| `out/sa-2.0.55/rollback/…/summary.json` | `0647476b14d4b37d` |

`out/pilot/` holds the first run, made with the script before the rollback set was added. Its main-set verdicts match the final run.
