# PPCS cases and SQLite

The catalog was read from `specifications/transactions.v1.json` and `specifications/migrations.v1.json` at the worktree base `a6b718d`. It was not modified.

Classifications:

| Classification | Meaning |
| --- | --- |
| Directly portable | Same invariant and comparable observable behavior |
| Semantically adaptable | Same correctness question, different SQLite expectations |
| Requires new injection | The existing fault mechanism cannot be reused |
| Not applicable | Depends on PostgreSQL-specific behavior |
| Unresolved | More evidence required |

"Same invariant" includes the sentence in the catalog. Sentences that name `pg_xact_status`, command tags, SQLSTATE, or `pg_stat_activity` are not the same invariant on SQLite even when a related question is worth asking. Those cases get a database-specific identifier. None of the existing identifiers should be reused until the catalog text is neutral, and that edit is out of scope.

Observer changes, throughout: drop `pg_current_xact_id`, `pg_xact_status`, `pg_stat_activity`, `pg_locks`, and command-tag checks. Replace them with `Connection.in_transaction` reported by the adapter and a second connection's reads of the marker table and `sqlite_schema`. There is no transaction id to bind.

## CTL-01

| | `CTL-01.commit` | `CTL-01.rollback` |
| --- | --- | --- |
| Classification | Semantically adaptable | Semantically adaptable |
| PostgreSQL preconditions | Fresh database, marker table empty, pool of one | Same, plus an application error inside the transaction |
| Fault | none | none |
| Expected outcome | `pg_xact_status` committed, second connection sees the marker | `pg_xact_status` aborted, second connection does not see the marker |
| SQLite, observed | SQL `COMMIT` with `in_transaction` false; second connection sees the marker (SQLITE-06) | SQL `ROLLBACK`, or `close()` with a pending transaction; second connection does not see the marker (SQLITE-03, SQLITE-04) |
| Proposed equivalent | A control that commits and checks the second connection | A control that rolls back and checks the second connection |
| Observer | Second connection only. No xid, no `pg_xact_status` | Same |
| Identifier | New, for example `SQLITE-CTL.commit` | New, for example `SQLITE-CTL.rollback` |

The question (can a separate connection confirm a commit and the absence of a rollback) is the same. The invariant text is not. These controls are still required before any other SQLite result counts.

## TX-01A `caught-error-then-commit`

| | |
| --- | --- |
| Classification | Semantically adaptable |
| PostgreSQL preconditions | Fixture row `'taken'` in `uniq`. After the caught `23505`, the session is `idle in transaction (aborted)` and `pg_xact_status` is already aborted. The callback sends nothing else. |
| Fault | Category A. Unique violation raised by PostgreSQL. |
| Expected outcome | `COMMIT` is answered with command tag `ROLLBACK` and commits nothing. The API must not report success. The application can know that from the command tag. |
| SQLite, observed | `IntegrityError` `SQLITE_CONSTRAINT_UNIQUE` 2067. `in_transaction` stays true. The earlier marker stays pending. SQL `COMMIT` succeeds and the second connection sees the marker (SQLITE-01 default). `OR ROLLBACK` is the conflict clause that does end the transaction; it is not the default. |
| Proposed equivalent | Caught unique violation, then `COMMIT`. The SQLite expectation is the opposite of PostgreSQL's: the commit is real, and it persists the earlier write. The interesting failure is an API that reports rollback, or a migration runner that assumes the transaction is dead and then commits. |
| Observer | Second connection must see the pre-error marker after a successful `COMMIT`, and must not see the conflicting row. `in_transaction` is true at the checkpoint after the error. |
| Identifier | New. Do not score this against TX-01A.1. |

## TX-01B `conn-lost-before-commit`

| | |
| --- | --- |
| Classification | Not applicable |
| PostgreSQL preconditions | Adapter reports `pg_backend_pid`. The runner terminates that backend and waits until it is gone. |
| Fault | Category B, `pg_terminate_backend`. |
| Expected outcome | Backend exits, transaction rolls back. The driver refuses to send `COMMIT`. A reported rollback is justified. A reported commit is not. |
| SQLite | There is no backend to terminate. SQLITE-06 killed a child after the insert and before `COMMIT`. The next process did not see the marker, and a journal file was still present. The child did not return an API result. |
| Proposed equivalent | A process-death durability check, not a client-report check. New identifier. |
| Observer | A later process opens the file. The dead process has no `reported` outcome. |
| Identifier | New, if the durability question is kept. Not TX-01B. |

## TX-01B `commit-reply-discarded`

| | |
| --- | --- |
| Classification | Not applicable |
| PostgreSQL preconditions | Statements pass through instrumented node-postgres. `COMMIT` completes, then the client discards the reply. |
| Fault | Category D, `pg.Client.prototype.query`. |
| Expected outcome | Server committed. The API must not report success (TX-01B.1) and must not report a confirmed rollback (TX-01B.2). |
| SQLite | The engine is in-process. SQLITE-06's trace-callback kill happened before `COMMIT` returned and the next open did not see the marker. That is an interrupted commit that recovered as not committed. A surviving caller with neither success nor error, while the database might have committed, was not observed. An I/O error during commit was not injected. |
| Proposed equivalent | None until such a surviving-caller case is actually produced. |
| Observer | Would have to be a later open, and only after a case that can leave the outcome unsettled. This run did not leave it unsettled. |
| Identifier | Do not reuse TX-01B. |

## TX-02

Shared PostgreSQL shape: outer write, savepoint write confirmed by a subtransaction lock, savepoint rollback fails, outer scope catches and ends normally. Invariants TX-02.1 and TX-02.2: if the API says the outer transaction committed, PostgreSQL committed the outer writes and not the inner ones, and the connection is not still inside a transaction when the API returns.

| Case | Classification | Fault today | SQLite evidence | Proposed equivalent | Identifier |
| --- | --- | --- | --- | --- | --- |
| `savepoint-rollback-not-sent` | Requires new injection | Category C. Driver fails `ROLLBACK TO` without sending it. Session stays `idle in transaction` holding the subtransaction lock. | Not injected. If the rollback is never sent, SQLITE-03 says the inner row is still pending and a later `COMMIT` persists it. There is no subtransaction lock to read. | A sqlite3 trace or statement wrapper that withholds `ROLLBACK TO` once. Expectation: inner row remains unless the adapter then rolls the outer transaction back. | New |
| `savepoint-rollback-rejected` | Semantically adaptable | Category C rewrite to a missing savepoint. PostgreSQL `3B001` aborts the transaction block. `COMMIT` without recovery is answered `ROLLBACK`. | Observed without a rewrite. `ROLLBACK TO` a missing name is `SQLITE_ERROR` 1, `no such savepoint`. `in_transaction` stays true. Later `COMMIT` persists the earlier rows, including a row whose savepoint was already released (SQLITE-03). | Issue `ROLLBACK TO` a name that is not active. Expectation: error, transaction still usable, `COMMIT` keeps earlier writes. Do not expect an aborted block or a `ROLLBACK` command tag. | New |
| `conn-lost-before-savepoint-rollback` | Not applicable | Category B inside the nested scope. | No backend. A top-level process kill before `COMMIT` left the marker absent. A kill inside an open savepoint was not run. | Not this case. | Do not reuse |

TX-02.2's underlying question (the connection must not stay in a transaction after the API returns) is testable with `in_transaction`. The PostgreSQL session-state wording is not.

## TX-03

| Case | Classification | PostgreSQL fault and expectation | SQLite | Identifier |
| --- | --- | --- | --- | --- |
| `rollback-not-sent` | Semantically adaptable, and the client-reject fault requires new injection | Category C withholds `ROLLBACK`. Session stays `idle in transaction` on the same xid. The next unit must not join or commit that transaction. | Observed without injection. Handing out a connection with `in_transaction` true: the next `BEGIN` fails with `cannot start a transaction within a transaction`, and an insert plus `COMMIT` persists both units (SQLITE-04). | New. The reuse question is the same. The signature is `in_transaction`, not `backend_xid`. |
| `statement-error-rollback-not-sent` | Semantically adaptable | `23505` aborts the transaction. Withheld `ROLLBACK` leaves `idle in transaction (aborted)`. Later statements fail with `25P02` until `ROLLBACK`. | A unique violation does not abort the transaction and does not poison the connection (SQLITE-01, SQLITE-04). Reuse without an ending statement joins the open transaction and can commit the pre-error write. There is no `25P02` analogue in this run. | New. Do not expect an aborted block. |
| `conn-lost-in-transaction` | Not applicable | `pg_terminate_backend` before `ROLLBACK`. The pool holds a closed connection. | `close()` with a pending transaction discards the marker and makes the connection unusable (`ProgrammingError`). That is disposal, not a terminated backend left in a pool. | Do not reuse |

TX-03.2 (the next unit finishes and commits within a bound) can be asked on SQLite only after the adapter's reuse rule is defined. On one connection it is immediate. It does not need `pg_stat_activity`.

## TX-04

| Case | Classification | PostgreSQL expectation | SQLite, observed | Identifier |
| --- | --- | --- | --- | --- |
| `nested-failure-contained` | Directly portable as a database outcome | Savepoint fails, caller commits, outer writes remain, inner writes do not | `ROLLBACK TO` removes the inner row, outer `COMMIT` keeps the outer row and a later row (SQLITE-03) | Database-specific id until the invariant stops saying "PostgreSQL". The outcome matches. |
| `nested-released-outer-rollback` | Directly portable as a database outcome | Released savepoint still belongs to the outer transaction and disappears if the outer transaction rolls back | `RELEASE` left `in_transaction` true. The second connection saw nothing until a commit. Outer `ROLLBACK` left nothing (SQLITE-03 and SQLITE-05 DDL) | Same as above |
| `independent-inner` | Unresolved | A second connection commits the inner transaction; the outer rollback does not remove it. Pool of two. | Not run as this script. SQLITE-02 shows a second connection does not see uncommitted rows, and sees a commit that was its own. A framework that promises independence has to open another connection; one SQLite connection cannot hold two top-level transactions (SQLITE-04, `cannot start a transaction within a transaction`). | New, only if an adapter claims a second connection. Not applicable to a single connection. |

Pending writes that a unit of work has not sent are a framework question. SQLite will not defer them on its own. Phase 0 did not run an ORM.

## TX-05

| Case | Classification | Why |
| --- | --- | --- |
| `managed-serializable` | Not applicable | The invariant is PostgreSQL's isolation order, `current_setting('transaction_isolation')`, and `SIReadLock`. SQLite has no such catalog and no predicate locks in this suite. |
| `explicit-serializable` | Not applicable | Same. |

Source, not a runtime result: Knex 3.3.0's SQLite transaction warns and sends `BEGIN;` when an isolation level is requested (`sqlite-transaction.js`). SQLAlchemy 2.1.5's SQLite dialect maps only `READ UNCOMMITTED` and `SERIALIZABLE` through `PRAGMA read_uncommitted` (`dialects/sqlite/base.py`). A SQLite isolation case would be that pragma, and it was not run. It should not be TX-05.

## MG-02

PostgreSQL preconditions, all four cases: several OS processes, `application_name` `ppcs-A` / `ppcs-B` / `ppcs-C`, an advisory lock held by the runner, the migration inserting a marker and waiting on `pg_advisory_xact_lock`. History is a table the adapter names. `pool_max` is per role.

| Case | Classification | Fault | SQLite | Identifier |
| --- | --- | --- | --- | --- |
| `held` | Requires new injection | none, advisory lock gate | No advisory locks, no `application_name`. SQLITE-02 shows a reader can make `COMMIT` return `SQLITE_BUSY` and leave the transaction open. That is a different gate. | New fixtures |
| `first-deployment` | Requires new injection | none, empty history | Two processes creating the same schema will contend on the file lock. Not run. Transactional DDL changes the recovery shape: a rolled-back creator leaves no tables (SQLITE-05). | New fixtures |
| `session-loss` | Not applicable | `pg_terminate_backend` of one session of runner A | No sessions to list. Process kill before `COMMIT` left the marker absent (SQLITE-06). A multi-process migration with one process killed was not run. | New, if built |
| `idle-session-timeout` | Not applicable | `idle_session_timeout=1s` | SQLite has no such setting. The PostgreSQL result is specifically that a busy transaction is not idle. | Do not reuse |

The question "does the migration commit once" can be asked. The coordination mechanism cannot be copied. SQLite-specific fixtures would use file locks or `BEGIN IMMEDIATE` and `SQLITE_BUSY`, plus `sqlite_schema` and a history table, not `pg_locks`.

## MG-03

| Case | Classification | PostgreSQL expectation | SQLite evidence | Identifier |
| --- | --- | --- | --- | --- |
| `valid-reversal` | Semantically adaptable | Reversal deletes the marker. History and the row are gone. The next apply runs again. | Not run as a runner. A transaction that deletes a row and commits is visible to a second connection; a transaction that rolls back is not (SQLITE-06, SQLITE-03). | New fixtures. The database can express it. |
| `no-reversal` | Semantically adaptable | A revert must not report success while the marker remains, unless a documented irreversible contract keeps history and the database consistent. | This is a runner contract, not an engine behavior. SQLite does not invent a reversal. | New, at the runner. The engine does not decide it. |
| `failing-reversal` | Semantically adaptable | The reversal deletes the marker and then raises, inside a transaction. Failure is reported. History remains. The marker remains because the migration is transactional. | Observed on a migration-shaped transaction: a failing statement does not abort the transaction. `ROLLBACK` removes the DDL and the rows. `COMMIT` after the caught error keeps them (SQLITE-05). A runner that catches the error and commits will persist a partial reversal. A runner that rolls back will not. | New. The PostgreSQL assumption that the transaction is already aborted is the part that does not transfer. |

Do not port the migration catalog in Phase 0. The useful comparison is already in SQLITE-05: schema changes and data changes share one transaction, and a caught statement error does not force that transaction to end.

## What transfers unchanged

These outcomes matched the PostgreSQL cases' intended database result, using explicit SQL rather than the PostgreSQL observer:

- A committed marker is visible to a second connection. A rolled-back marker is not. (CTL-01's question.)
- `ROLLBACK TO` a live savepoint removes that savepoint's writes and leaves the outer transaction usable. A later `COMMIT` keeps the outer writes. (TX-04.1's outcome.)
- `RELEASE` does not durably commit. An outer `ROLLBACK` removes the released work, including DDL. (TX-04.2's outcome.)
- A connection left inside a transaction will attach later work to that transaction, and one `COMMIT` can persist both. (TX-03.1's hazard, without the PostgreSQL aborted-block half.)

## What needs SQLite-specific expectations

- A caught unique violation leaves the transaction open. `COMMIT` persists earlier work.
- `ROLLBACK TO` an unknown savepoint is an error and does not abort the transaction.
- `OR FAIL` can keep earlier rows of the same statement. `OR ROLLBACK` ends the whole transaction. `OR REPLACE` writes a replacement.
- `COMMIT` can fail with `SQLITE_BUSY` in rollback-journal mode and leave the transaction active. WAL did not fail that way.
- `autocommit=True` makes `Connection.commit()`, `Connection.rollback()`, and the context manager unable to finish a SQL `BEGIN`.
- `autocommit=False` opens a transaction at connect. Legacy mode opens one before DML only.
- DDL participates in an explicit transaction. `PRAGMA journal_mode` and `PRAGMA foreign_keys` do not behave like `PRAGMA user_version`.
- There is no command tag, no SQLSTATE, no `xid`, and no aborted-session state corresponding to `25P02`.
