# Decision memo: SQLite as a PCS target

Evidence is the run `research/sqlite-phase0/evidence/2026-10-19T13-20-36Z-py313/` (Python 3.13.11, SQLite 3.53.1, three agreeing repetitions). Framework comments in the adapter proposal are source inspections, not SQLite runs. The PostgreSQL catalog was not changed.

## 1. Is SQLite a useful PCS target?

Yes, for a narrow set of questions the PostgreSQL suite cannot ask, and for a few questions it already asks whose answers come out differently.

It is useful because a second connection can see committed rows and cannot see pending ones, DDL can share a transaction with DML, and the driver's report is thin enough that "the API said commit" has to be checked against `in_transaction` and that second connection. Those are persistence-conformance questions.

It is a poor target for anything that needs a separate server process: lost commit replies, `pg_terminate_backend`, advisory locks, `idle_session_timeout`, command tags, or an aborted transaction that rejects every later statement. Those are not missing coverage. They are a different system.

## 2. Which new correctness questions does it introduce?

Observed in this run:

- A caught unique violation does not end the transaction. A later `COMMIT` persists the earlier write. `OR FAIL` can also keep an earlier row of the same statement. `OR ROLLBACK` ends the transaction and the next statement, under `autocommit=True`, can commit on its own.
- `COMMIT` in rollback-journal mode can raise `SQLITE_BUSY` and leave the transaction open. Retrying `COMMIT` after the reader finishes makes the marker visible. WAL, under the same choreography, committed while the reader still held a snapshot that did not include the marker.
- `ROLLBACK TO` an unknown savepoint errors with `SQLITE_ERROR` and leaves the transaction usable.
- `RELEASE` does not publish rows to another connection. Outer `ROLLBACK` removes them, including tables created inside the savepoint.
- With `autocommit=True`, `Connection.commit()`, `Connection.rollback()`, and the connection context manager do not finish a SQL `BEGIN`. With `isolation_level=None`, `commit()` does emit `COMMIT`. Closing a connection discards a pending transaction in every mode that still had one.
- `autocommit=False` opens a transaction before any SQL. Legacy mode opens one only before DML, and the trace shows `BEGIN `.
- `CREATE TABLE` and `ALTER TABLE` roll back with the transaction. `PRAGMA user_version` rolls back. `PRAGMA journal_mode=WAL` inside a transaction errors. `PRAGMA foreign_keys=OFF` inside a transaction returns success and leaves the flag unchanged.
- A process killed after `INSERT` and before `COMMIT` leaves the marker absent. A process killed after `COMMIT` has returned leaves the marker present (`synchronous=2`). A kill in the statement trace of `COMMIT`, before `execute` returns, also leaves the marker absent. A living caller with an unknown commit outcome was not observed.

## 3. Which existing PPCS invariants transfer unchanged?

As database outcomes, checked with a second connection and explicit SQL:

- A committed marker is visible afterward. A rolled-back marker is not. This is CTL-01's question, without `pg_xact_status`.
- Rolling back to a live savepoint drops that savepoint's writes and leaves the outer transaction able to commit the rest. This is the TX-04.1 outcome.
- Releasing a savepoint does not make its writes durable. Rolling back the outer transaction removes them, including DDL. This is the TX-04.2 outcome.
- Work done on a connection that is still inside a transaction is part of that transaction, and one `COMMIT` can persist it together with the earlier unit. This is the TX-03 open-transaction hazard, without PostgreSQL's aborted-block twin.

The catalog sentences that name PostgreSQL facilities do not transfer as text. The matrix gives those cases new identifiers.

## 4. Which require SQLite-specific expectations?

- TX-01A. PostgreSQL aborts the transaction and answers `COMMIT` with `ROLLBACK`. SQLite keeps the transaction open and a successful `COMMIT` persists the earlier marker.
- TX-02's rejected savepoint rollback. PostgreSQL `3B001` aborts the transaction block. SQLite's `no such savepoint` does not.
- TX-03's statement-error case. PostgreSQL leaves `25P02` until `ROLLBACK`. SQLite leaves a usable transaction and pending writes.
- TX-05. The isolation ladder, `current_setting`, and `SIReadLock` are PostgreSQL. SQLite's dialect source maps at most `PRAGMA read_uncommitted`.
- MG-02. Advisory locks, `application_name`, and `idle_session_timeout` do not exist. File-lock `SQLITE_BUSY` is the related, different mechanism.
- MG-03's failing reversal. On PostgreSQL the failed statement has already aborted the transaction. On SQLite the runner's explicit `ROLLBACK` is what removes the work. A caught error followed by `COMMIT` keeps the partial migration.
- Any check that reads a command tag, SQLSTATE, `xid`, or `pg_stat_activity`.

## 5. Can SQLite adapters be introduced additively?

Yes. A separate program, a separate evidence directory, and database-specific case ids. The PostgreSQL runner, catalogs, adapters, and result schema stay as they are.

They cannot be introduced by pointing the existing harness at a SQLite file. The observer, the protocol checkpoint, the fault injectors, and the result schema all require PostgreSQL. That limitation is precise, and the modification is not part of this phase.

## 6. What is the smallest useful Phase 1?

One `sqlite3` control, still outside `harness/run.mjs`, with these cases and new ids:

1. Commit visibility and rollback visibility.
2. Caught unique violation, then `COMMIT` (expect the marker to persist).
3. `ROLLBACK TO` a missing savepoint, then `COMMIT` (expect the transaction to stay usable and earlier writes to persist).
4. Savepoint release, then outer `ROLLBACK` (expect no rows and no tables created in that transaction).
5. Connection reused while `in_transaction` is true (expect both units to commit together).
6. The same connection after SQL `ROLLBACK` (expect only the second unit).
7. A multi-statement DDL transaction that hits a unique violation, once ended with `ROLLBACK` and once with `COMMIT`.

Optional, still in that control, because it is already measured: `COMMIT` returning `SQLITE_BUSY` in `journal_mode=DELETE`, with WAL recorded as a different expected result.

Do not add an ORM in that step. The next adapter after the control is SQLAlchemy Core, because its SQLite dialect already emits `BEGIN` and the PostgreSQL suite already has a Core adapter to compare against, without sharing code. Django's `atomic()` is the following one, for the same reason: the source shows explicit `BEGIN` and savepoints, and the foreign-key pragma behavior is already in both the Django source and SQLITE-05.

## 7. What should remain out of scope?

- Editing `specifications/`, `harness/`, `schema/`, or any PostgreSQL adapter.
- A common transaction interface over PostgreSQL, MySQL, and SQLite.
- Scoring SQLite with TX-01A.1, TX-01B, TX-05, or MG-02's current wording.
- A lost-reply or crash-during-fsync case, until one is actually produced. This run's process kills do not establish it.
- ORM adapters, `better-sqlite3`, Knex, Kysely, and Lucid, until the `sqlite3` control's cases are stable. Lucid 22.4.2 contains SQLite dialect names; that is not a reason to port the Lucid PostgreSQL adapter.
- Connection pools, migration runners, and concurrent migration processes. SQLITE-04 states what reuse must check. It does not implement a pool. SQLITE-05 states what a transactional migration can roll back. It does not implement a runner.
- Claims that SQLite is or is not reliable. The run says which guarantees can be observed, and which PostgreSQL guarantees are a different system.
