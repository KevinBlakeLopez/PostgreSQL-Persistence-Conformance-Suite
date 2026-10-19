# SQLite Phase 0 baseline

Recorded run: `research/sqlite-phase0/evidence/2026-10-19T13-20-36Z-py313/`.

Fifty-seven variants, three repetitions, fresh file per repetition. `summary.json` records `agreement: true`. Nothing in that run was retried to hide a disagreement.

This report separates four kinds of statement:

- **Observed:** what this run's JSON files record.
- **Source:** what installed framework or driver source says. Those packages were not executed against SQLite here.
- **Documentation:** SQLite or Python documents, used only to name a mechanism the run did not itself display.
- **Hypothesis:** not observed.

## Environment

Observed from `environment.json` and `sqlite3` on `/opt/homebrew/bin/python3.13`:

| Item | Value |
| --- | --- |
| Python | 3.13.11, `/opt/homebrew/opt/python@3.13/bin/python3.13` |
| `sqlite3` module version | 2.6.0 (`sqlite3.version`, the DB-API module version) |
| SQLite library | 3.53.1 |
| `sqlite_source_id()` | `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9` |
| OS | Darwin 25.6.0, arm64 |
| DB-API | `apilevel` 2.0, `paramstyle` qmark, `threadsafety` 1 |
| `LEGACY_TRANSACTION_CONTROL` | `-1` |
| Default `Connection.autocommit` | `-1` (legacy) |
| Default `isolation_level` | `""` |
| Fresh-file `journal_mode` | `delete` |
| Fresh-file `synchronous` | `2` (FULL; compile option `DEFAULT_SYNCHRONOUS=2`) |
| Fresh-file `foreign_keys` | `0` (off until a connection sets it) |
| Fresh-file `locking_mode` | `normal` |
| Fresh-file `read_uncommitted` | `0` |
| Fresh-file `fullfsync` | `0` |
| Default `connect()` busy timeout | `PRAGMA busy_timeout` = 5000 ms |
| `PRAGMA lock_status` on an idle autocommit connection | empty row list, no error |
| Constraint probe | `IntegrityError`, `SQLITE_CONSTRAINT_UNIQUE` (2067, primary code 19) |

Compile options also include `THREADSAFE=1` and `ENABLE_UNLOCK_NOTIFY`. There is no `DEFAULT_FOREIGN_KEYS` option in the list, which matches the fresh-file pragma.

The experiments pass `timeout=0.0`, so `PRAGMA busy_timeout` is 0 unless a variant says otherwise. They set `PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=DELETE` on the baseline connection, except the WAL variant.

## Method

Every variant uses a file-backed database. `:memory:` is not used. A second connection, opened with `autocommit=True` and `PRAGMA query_only=ON`, reads after the operation under test. A row that connection can see is durable committed state. A row only the writer can see is still pending. The writer's `Connection.in_transaction` is the transaction-state checkpoint.

`Connection.set_trace_callback` records SQL the driver actually executed, including a `BEGIN` the experiment did not issue.

Three transaction-control modes are named explicitly:

| Mode | How the connection is opened | What the driver did in this run |
| --- | --- | --- |
| explicit | `autocommit=True` | No implicit `BEGIN`. SQL `BEGIN` / `COMMIT` / `ROLLBACK` are the experiment's. |
| legacy | `autocommit=-1`, `isolation_level=""` | Before `INSERT`, the trace contains `BEGIN ` (trailing space). `CREATE TABLE` and `SELECT` do not. |
| pep249 | `autocommit=False` | The connection opens already in a transaction, before any SQL. See SQLITE-04. |
| legacy-none | `isolation_level=None` | `autocommit` stays `-1`. No deprecation warning was captured. An explicit `BEGIN` works. This is not `autocommit=True`. |

The connection context manager was measured rather than assumed. On `autocommit=True` it does not begin a transaction. See SQLITE-04.

## SQLITE-01 — constraint conflict inside an explicit transaction

Setup, committed before `BEGIN`: `item(id INTEGER PRIMARY KEY, name TEXT UNIQUE)` and row `(1, 'taken')`. The writer then runs `BEGIN` and `INSERT` of `(2, 'marker')`, then the conflict statement. A follow-up `INSERT` of `(8, 'after')` records whether the connection still accepts SQL. Then the writer issues `COMMIT`.

`in_transaction` was false after setup and true before the conflict, in every variant. `implicit_begin_count` was 0.

### Single-row conflict

Statement shape: `INSERT [OR ...] INTO item(id, name) VALUES (3, 'taken')`, except `OR REPLACE`, which inserts `(6, 'taken')`.

| Variant | Driver | `in_transaction` after | Writer's rows after | Second connection before `COMMIT` | `COMMIT` | Second connection after |
| --- | --- | --- | --- | --- | --- | --- |
| default and `OR ABORT` | `IntegrityError` `SQLITE_CONSTRAINT_UNIQUE` 2067, `UNIQUE constraint failed: item.name` | true | `taken`, `marker` | `taken` | succeeds, `rowcount` -1, no description | `taken`, `marker`, `after` |
| `OR FAIL` | same error as ABORT | true | `taken`, `marker` | `taken` | succeeds | `taken`, `marker`, `after` |
| `OR IGNORE` | no exception, `rowcount` 0 | true | `taken`, `marker` | `taken` | succeeds | `taken`, `marker`, `after` |
| `OR ROLLBACK` | `IntegrityError` 2067 | **false** | `taken` only | `taken` | `OperationalError` `SQLITE_ERROR`, `cannot commit - no transaction is active` | `taken`, `after` |
| `OR REPLACE` | no exception, `rowcount` 1, `changes()` = 1 | true | `(2, marker)`, `(6, taken)` | `taken` | succeeds | `(2, marker)`, `(6, taken)`, `(8, after)` |

`OR REPLACE` deleted the original `(1, 'taken')` and inserted `(6, 'taken')`. That is a successful write, not an ignored conflict and not a rollback.

`OR ROLLBACK` ended the transaction. The follow-up `INSERT` of `'after'` then ran with `autocommit=True` and no `BEGIN`, so it committed by itself. The second connection saw `taken` and `after` before the failed `COMMIT`. The marker did not survive.

On a one-row insert, default `ABORT` and `OR FAIL` were not distinguishable.

### Multi-row conflict

```sql
INSERT OR <mode> INTO item(id, name)
SELECT 4, 'from-statement' UNION ALL SELECT 5, 'taken'
```

| Mode | Error | `'from-statement'` on the writer after the statement | Transaction | After a later successful `COMMIT` |
| --- | --- | --- | --- | --- |
| `ABORT` | `IntegrityError` 2067 | absent | still open | `taken`, `marker`, `after` |
| `FAIL` | `IntegrityError` 2067 | **present**, `changes()` = 1 | still open | `taken`, `marker`, `from-statement`, `after` |
| `IGNORE` | none, `rowcount` 1 | present | still open | same as `FAIL` |
| `ROLLBACK` | `IntegrityError` 2067 | absent, and `marker` is gone | closed | `taken`, `after` (the follow-up autocommitted) |

Observed difference between `ABORT` and `FAIL`: `ABORT` undoes the whole statement, including the earlier row of that statement. `FAIL` keeps that earlier row and stops. Earlier statements from before the failing statement (`marker`) stay pending for both, and a later `COMMIT` makes them durable. The second connection does not see them until that `COMMIT`.

## SQLITE-02 — `COMMIT` and `SQLITE_BUSY`

Journal mode `DELETE` unless noted. Two connections, each created on its own thread. The reader waits on an `Event` until the writer has inserted, then `BEGIN DEFERRED` and `SELECT`. The writer waits until the reader has read, then `COMMIT`. `timeout=0`. No sleep is the synchronization.

`PRAGMA lock_status` returned no rows on the writer after the insert, on the reader while it held its read, and on the writer after the failed `COMMIT`. This build did not expose lock mode through that pragma. The sequence below is the operation order and the errors. Mapping it onto SQLite's SHARED / RESERVED / PENDING / EXCLUSIVE names is an interpretation of the locking documentation, not a row this run read.

### `delete-journal-no-reader`

`BEGIN DEFERRED`, insert `(2, 'marker')`, `COMMIT` succeeds, `in_transaction` becomes false. A second connection sees `seed` and `marker` immediately. A second `COMMIT` is not issued.

### `delete-journal-reader-holds-shared`

Observed, all three repetitions:

1. Writer `BEGIN DEFERRED`, insert `marker`, `in_transaction` true.
2. Reader `BEGIN DEFERRED`, `SELECT` succeeds, and the reader sees only `seed`.
3. Writer `COMMIT` raises `OperationalError`, message `database is locked`, `SQLITE_BUSY` code 5 (not an extended code). `in_transaction` stays true. The writer still sees `marker`.
4. A third connection, opened while the reader is still inside its transaction, also gets `SQLITE_BUSY` on `SELECT`. An independent read was not available in that window.
5. Reader `ROLLBACK`. Writer `COMMIT` succeeds. `in_transaction` becomes false.
6. The third connection then sees `seed` and `marker`.

The failed `COMMIT` did not roll the writer back, and the retry after the reader released did commit. The marker was not visible to a connection that could read during the failure, because that connection could not read at all.

### `wal-reader-holds-snapshot`

Same choreography after `PRAGMA journal_mode=WAL`, which the setup connection reported as `wal`.

The reader's `SELECT` saw only `seed`. The writer's first `COMMIT` succeeded while that reader was still open. No `SQLITE_BUSY`. A new connection, opened before the reader ended, saw `seed` and `marker`. The reader's earlier read did not. WAL does not reproduce the rollback-journal `COMMIT` failure. It is a separate result.

## SQLITE-03 — savepoints

Explicit `BEGIN`. `RELEASE` is not a durable commit.

### Release, then outer `ROLLBACK`

`SAVEPOINT sp1`, insert `'released'`, `RELEASE SAVEPOINT sp1`. `in_transaction` stays true. The writer still sees the row. The second connection sees nothing. `ROLLBACK` succeeds, `in_transaction` becomes false, and the second connection still sees nothing.

### `ROLLBACK TO`, then continue, then `COMMIT`

Insert `'outer'`, `SAVEPOINT sp1`, insert `'inner'`, `ROLLBACK TO SAVEPOINT sp1` succeeds. The writer then sees only `'outer'`. `RELEASE SAVEPOINT sp1` succeeds, so the savepoint still existed after `ROLLBACK TO`. Insert `'after'`, `COMMIT`. The second connection sees `outer` and `after`, not `inner`. It saw nothing before the `COMMIT`.

### `ROLLBACK TO` a name that does not exist

`BEGIN`, insert `'kept'`, `ROLLBACK TO SAVEPOINT does_not_exist`.

`OperationalError`, `SQLITE_ERROR` code 1, `no such savepoint: does_not_exist`. `in_transaction` stays true. The writer still sees `kept`. A later insert of `'after'` succeeds. `COMMIT` succeeds. The second connection sees `kept` and `after`.

### `ROLLBACK TO` a savepoint that was already released

`SAVEPOINT sp1`, insert `'nested'`, `RELEASE`, then `ROLLBACK TO SAVEPOINT sp1`. Same error, `no such savepoint: sp1`. `in_transaction` stays true. The writer still sees `kept` and `nested`. `COMMIT` persists `kept`, `nested`, and the follow-up `'after'`.

The error does not close the transaction and does not discard earlier writes.

## SQLITE-04 — close, context managers, and reuse

Schema is committed by a separate `autocommit=True` connection before these probes, so a later rollback is not also undoing setup.

### Close with pending work

| Variant | `in_transaction` before `close()` | Second connection after `close()` |
| --- | --- | --- |
| explicit `BEGIN`, insert, close | true | no marker |
| explicit `BEGIN`, savepoint, insert, close | true | no marker |
| legacy, `INSERT` only (trace: `BEGIN `, `INSERT`, `SELECT`) | true | no marker; the table remains |
| pep249, `INSERT` only (trace has no `BEGIN`; close traces `ROLLBACK`) | true | no marker |
| explicit insert with no `BEGIN` | false | marker is present |
| `isolation_level=None`, explicit `BEGIN`, insert, close | true | no marker |

`close()` returns `None`. After close, reading `in_transaction` or executing SQL raises `ProgrammingError`, `Cannot operate on a closed database.`, with no SQLite error code.

A savepoint did not change the close result: the marker was not durable.

pep249 and legacy both discard a pending insert on close. They do it differently in the trace. Legacy's close did not add a `ROLLBACK` statement to the trace. pep249's close did. The second connection's empty read is the shared observation.

### Which statements start a transaction

One fresh connection per statement. For pep249, the connection opens with `in_transaction` true; the probe issues `ROLLBACK` before the statement so the statement is not merely joining that opening transaction.

| Mode | Opens in a transaction | `CREATE TABLE` | `INSERT` | `SELECT` | `PRAGMA user_version=3` |
| --- | --- | --- | --- | --- | --- |
| explicit | no | commits immediately, no `BEGIN` | commits immediately | no transaction | version 3 is visible to a new connection |
| legacy | no | commits immediately, no `BEGIN` | trace `BEGIN `, `in_transaction` true, close discards the row | no transaction | version 3 is visible |
| pep249 | **yes, before any SQL** | after the prelude `ROLLBACK`, the `CREATE` commits and is still there after close | after the prelude `ROLLBACK`, the `INSERT` commits | no transaction left open | version 3 is visible |

The pep249 prelude matters. `ddl-without-begin-pep249` does **not** roll back the opening transaction. There, `CREATE TABLE` and `INSERT` both leave `in_transaction` true, the trace has no `BEGIN`, and a later SQL `ROLLBACK` removes the table and the row. The second connection then cannot see the table.

So `autocommit=False` starts a transaction at connect. Statements join it until it is ended. After that SQL `ROLLBACK`, the next `CREATE` or `INSERT` in this run committed on its own.

### Context manager

On `autocommit=True`:

- An empty `with connection:` leaves `in_transaction` false. The trace is empty. The context manager does not begin a transaction.
- `with connection:` around SQL `BEGIN` and `INSERT` leaves `in_transaction` true on the way out. The trace is `BEGIN`, `INSERT`, and no `COMMIT`. The second connection does not see the marker. Exit did not commit.
- The same block, with `RuntimeError` raised inside, also leaves `in_transaction` true. The trace has no `ROLLBACK`. Exit did not roll back.

On legacy transaction control, `with connection:` around an `INSERT` traces `BEGIN `, `INSERT`, `COMMIT`. `in_transaction` is false afterward. The second connection sees the marker.

### `Connection.commit()` and `Connection.rollback()`

Under `autocommit=True`, after SQL `BEGIN` and `INSERT`:

- `commit()` returns `None`, does not raise, does not add `COMMIT` to the trace, and leaves `in_transaction` true. The second connection does not see the marker.
- `rollback()` behaves the same way: no `ROLLBACK` in the trace, transaction still open, marker not visible.
- `commit()` with no transaction returns `None` and leaves `in_transaction` false.

Under `isolation_level=None` (`autocommit` still `-1`), after SQL `BEGIN` and `INSERT`, `commit()` adds `COMMIT` to the trace, sets `in_transaction` false, and the second connection sees the marker. No connect-time warning was recorded.

`executescript("INSERT ... 'scripted'")` during an explicit transaction, with `autocommit=True`, returns successfully, does not add `COMMIT` to the trace, leaves `in_transaction` true, and the second connection sees neither the pending row nor the scripted row.

### Reuse of an open connection

No pool was implemented. A second unit of work used the same connection object.

- Open transaction, second `BEGIN`: `OperationalError` `SQLITE_ERROR`, `cannot start a transaction within a transaction`. `in_transaction` stays true. An `INSERT` of `'next'` and `COMMIT` then succeed. The second connection sees both `'doomed'` and `'next'`.
- `ROLLBACK` first: `in_transaction` becomes false. A new `BEGIN`, insert, and `COMMIT` leave only `'next'`.
- Caught unique violation, no rollback: `in_transaction` stays true, the doomed row is still pending, a second `BEGIN` fails with the same "within a transaction" error, and `COMMIT` persists `taken`, `doomed`, and `next`.

A constraint error did not make the connection refuse later statements, and it did not roll back the earlier insert.

What a future adapter has to check before it reuses a connection, from these observations:

1. The connection is open. A closed one raises `ProgrammingError` and has no SQLite code.
2. `in_transaction` is false. If it is true, the next unit joins the old transaction, and one `COMMIT` can persist both units.
3. The check has to match the transaction-control mode. With `autocommit=True`, `commit()`, `rollback()`, and the context manager do not end a SQL `BEGIN`. The adapter has to execute SQL `COMMIT` or `ROLLBACK` and read `in_transaction` again.
4. With `isolation_level=None` and `autocommit` still legacy, `commit()` does emit `COMMIT`. Treating that as the same knob as `autocommit=True` would be wrong on this interpreter.
5. A unique violation is not an aborted-transaction state. The connection stays usable, and the earlier writes stay pending until something ends the transaction.
6. `OR ROLLBACK` ends the transaction and returns the connection to autocommit. The next statement can commit by itself.
7. `PRAGMA foreign_keys` is per connection and defaults off. A reused connection does not inherit another connection's setting.
8. There is no command tag and no SQLSTATE on any of these outcomes.

## SQLITE-05 — transactional DDL

Explicit transactions use `autocommit=True` and SQL `BEGIN`.

| Variant | Writer while the transaction is open | Second connection before end | After `ROLLBACK` or `COMMIT` |
| --- | --- | --- | --- |
| `CREATE TABLE` + insert, then `ROLLBACK` | schema contains `item`, row `marker` is visible to the writer | schema query sees no `item`; selecting `item` errors | schema is empty |
| `ALTER TABLE item ADD COLUMN extra`, `DROP COLUMN extra`, add it again, `UPDATE`, `ROLLBACK` | writer schema SQL includes `extra TEXT` | second connection's schema SQL has no `extra` | table is the original `item(id, name)`; row `(1, marker)` remains from the committed setup |
| `CREATE TABLE kept`, savepoint, `CREATE TABLE discarded`, `ROLLBACK TO` | both names visible to the writer before `ROLLBACK TO`; only `kept` after | | `COMMIT` leaves only `kept` |
| savepoint, `CREATE TABLE released_ddl`, `RELEASE`, `ROLLBACK` | writer sees `released_ddl` after `RELEASE` | second connection does not | schema is empty |
| migration sequence, duplicate email, then `ROLLBACK` | both tables, migration id `001_account`, one account row | second connection sees no tables | schema is empty; account and migration queries error |
| same sequence, then `COMMIT` | transaction still open after the `IntegrityError` 2067 | second connection sees no tables | both tables exist, one account row, migration id `001_account` |

The duplicate insert did not end the transaction. `COMMIT` after catching it made the earlier DDL and the first account row durable. `ROLLBACK` removed all of it, including both `CREATE TABLE`s.

DDL with no explicit `BEGIN`:

| Mode | After `CREATE` | After `INSERT` | SQL `ROLLBACK` | Second connection |
| --- | --- | --- | --- | --- |
| explicit | `in_transaction` false | false | `cannot rollback - no transaction is active` | table and `marker` both present |
| legacy | false, no `BEGIN` in the trace | true, trace contains `BEGIN ` | succeeds | table present, marker absent |
| pep249, opening transaction left in place | true | true | succeeds | no table |

`PRAGMA user_version=7` inside an explicit transaction: the same connection reads 7, the second connection reads 0, and after `ROLLBACK` both read 0. This pragma followed the transaction.

`PRAGMA journal_mode=WAL` inside an explicit transaction: `OperationalError`, `cannot change into wal mode from within a transaction`. `in_transaction` stays true. `ROLLBACK` succeeds. Both connections then report `delete`.

`PRAGMA foreign_keys=OFF` inside a transaction that had set `foreign_keys=ON`: the statement returns without error, and the same connection still reads `1`. After `ROLLBACK` it still reads `1`. A new connection reads `0`, which is the default for a connection that has not set the pragma, not evidence that rollback changed a database-level flag. The in-transaction assignment did not change this connection's flag.

Not every `PRAGMA` is reversible. `user_version` was. `journal_mode` was refused. `foreign_keys` did not change.

## SQLITE-06 — what the driver reports

There is no command tag and no SQLSTATE on any success or failure in this run. `COMMIT` and `ROLLBACK`, when they succeed as SQL, return a cursor with `rowcount` -1 and `description` null. `Connection.in_transaction` is the state bit the driver exposes on an open connection.

| Situation | What sqlite3 reported | `in_transaction` after | Second connection |
| --- | --- | --- | --- |
| SQL `COMMIT` | success, `rowcount` -1 | false | marker present |
| SQL `ROLLBACK` | success, `rowcount` -1 | false | marker absent |
| SQL `COMMIT` while the reader holds a rollback-journal read | `OperationalError` `SQLITE_BUSY` 5 | true | could not read (`SQLITE_BUSY`) until the retry |
| `ROLLBACK TO` a missing savepoint | `OperationalError` `SQLITE_ERROR` 1 | true | sees the committed rows only after the later `COMMIT` |
| Unique violation, default abort | `IntegrityError` `SQLITE_CONSTRAINT_UNIQUE` 2067 | true | sees the marker only after `COMMIT` |
| `close()` with a pending insert | returns `None`; later use raises `ProgrammingError` | unreadable | marker absent |
| `commit()` / `rollback()` with `autocommit=True` and a SQL `BEGIN` | return `None`, no `COMMIT` or `ROLLBACK` in the trace | true | marker absent |
| `commit()` with `isolation_level=None` and a SQL `BEGIN` | trace contains `COMMIT` | false | marker present |

Confirmed completion, in this driver, is a successful SQL `COMMIT` together with `in_transaction` false, or the equivalent `commit()` only when that method actually traces `COMMIT`. Confirmed rollback is a successful SQL `ROLLBACK` or `OR ROLLBACK`, with `in_transaction` false, and the second connection missing the pending rows. A failed `COMMIT` (`SQLITE_BUSY`) is not confirmation and not rollback: the transaction is still open. A failed `ROLLBACK TO` is not a failed transaction: the transaction is still open and still usable. Failed cleanup is `close()` or a no-op `commit()`/`rollback()` that leaves `in_transaction` true, or a closed connection handed out afterward.

### Process termination

These are child processes. The parent reads the child's stdout and then opens the file. `PRAGMA synchronous` on that open was `2`. The child calls `os.kill(pid, SIGKILL)`. Return code `-9` in all three repetitions of each variant.

| Child | Stdout | Marker on the next open | Sidecars |
| --- | --- | --- | --- |
| insert, then kill, no `COMMIT` | `ready-to-kill` | absent | database and journal |
| `COMMIT` returns, then kill | `commit-returned` | present | database only |
| trace callback sees `COMMIT` and kills before `execute` returns | `trace-commit` only | absent | database and journal |

The trace-callback kill is an observed interruption at the start of `COMMIT`, before the call returned. The next connection did not see the marker. That is not a surviving caller holding an ambiguous reply, and it is not a case in which the commit had become durable. A protocol-level lost reply was not attempted. An I/O error during commit was not injected. Whether a kill after the journal is synced and before `sqlite3_step` returns can leave the database committed was not observed.

A second connection seeing a row after a returned `COMMIT` shows that the returned commit was visible to a later process, with `synchronous=2`, after the child had already received that return and had then been killed. It is not a power-loss test.

## Reproducibility

Command:

```sh
/opt/homebrew/bin/python3.13 research/sqlite-phase0/controls/run_all.py
```

The published run is `evidence/2026-10-19T13-20-36Z-py313/`. Three repetitions, one fingerprint each, `agreement: true`.

## Limitations

- One machine, one Python, one SQLite library build. No shared-cache mode, no `BEGIN IMMEDIATE` as the busy setup, no `SQLITE_BUSY_SNAPSHOT`.
- `PRAGMA lock_status` did not report lock holders, so the rollback-journal lock names are not a direct observation.
- The independent read during `SQLITE_BUSY` failed, so that window has the writer's view and the error, not a second connection's rows.
- Frameworks were not executed. Source notes are in the adapter proposal.
- `better-sqlite3` is not installed in this worktree or the main checkout.

## Open questions

- A commit interrupted after SQLite has synced the journal and before the caller resumes was not produced. The trace-callback kill recovered to "marker absent."
- How SQLAlchemy 2.1.5 and Django 6.1.2 behave at runtime on this Python, given they set `isolation_level` rather than `autocommit`, was not run. The `isolation_level=None` measurement is the relevant driver fact for that source.
- A two-connection "independent inner transaction" script in the shape of TX-04.3 was not run. Separate connections in SQLITE-02 do show that one connection's commit is visible to a new connection without becoming part of another connection's uncommitted transaction.
