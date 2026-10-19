# MySQL / InnoDB transaction baseline

Phase 0 investigation for a possible MySQL Persistence Conformance suite, written against the PostgreSQL Persistence Conformance Suite (PPCS) as it stands in this repository. The experiments are direct `mysql2` scripts. They are not a MySQL adapter, and a completed run is not an implementation of MySQL PCS.

Recorded run: `2026-10-19T13:49:36.491Z`, evidence in `evidence/`, failures `[]`. Reproduce with the commands in [README.md](README.md).

Labels used below:

- **Observed.** A value read from `evidence/` for that run.
- **Source.** A reading of PPCS or of the installed `mysql2` 3.24.6 sources. Not a runtime result unless a sentence also says observed.
- **Manual.** A claim in the MySQL 8.4 Reference Manual. Cited so it can be compared with the run.
- **Hypothesis.** Not run, or not established by the run.

## 1. What PPCS assumes

PPCS keeps four things apart: what the framework API reported, what PostgreSQL did, what the client could have known, and whether an invariant failed. The runner decides the last of those. The adapter does not. That split is in `docs/methodology.md` and is the part worth keeping for MySQL. The mechanisms under it are PostgreSQL-specific.

**Transaction identity and fate.** The adapter reads `pg_current_xact_id()` and `pg_backend_pid()` inside the transaction. The runner checks `pg_stat_activity.backend_xid` and later calls `pg_xact_status()` (`harness/lib/observer.mjs`). Those functions exist from PostgreSQL 13. There is no equivalent lookup in this MySQL run that still worked after the session had closed. See MPCS-05.

**Aborted transactions.** A statement error aborts the PostgreSQL transaction. `pg_current_xact_id()` then fails with `25P02`. An `idle in transaction (aborted)` session has a null `backend_xid`. Classification treats `23505` as the unique violation that produces that state, and `25P02` as the failure of every later statement until `ROLLBACK` (`docs/methodology.md`, `harness/lib/classify.mjs`). TX-01A's catalog text says PostgreSQL answers the later `COMMIT` with the command tag `ROLLBACK`, without an error (`specifications/transactions.v1.json`).

**Command tags.** node-postgres exposes `result.command`. `adapters/node-kit/pg-instrument.mjs` records it for `BEGIN`, `COMMIT`, `ROLLBACK`, and savepoint statements. `adapters/pg-control/main.mjs` reports committed only when that tag is `COMMIT`. The positive control's contract is that rule. MySQL's OK packet, as `mysql2` exposes it, has no such tag. See MPCS-05.

**Savepoints.** A PostgreSQL savepoint allocates a subtransaction id. The runner treats a second `transactionid` lock in `pg_locks` as evidence of a write inside the savepoint. TX-02's rejected rollback is SQLSTATE `3B001`. The catalog says that error aborts the subtransaction, leaves the session `idle in transaction (aborted)`, and makes a later `COMMIT` return the tag `ROLLBACK`. Category C faults are implemented by patching `pg.Client.prototype.query` (`adapters/node-kit/pg-instrument.mjs`).

**Pool reuse.** TX-03 distinguishes an open transaction block from an aborted one. On PostgreSQL, the next `BEGIN` on an open block joins it, and a statement on an aborted block fails with `25P02`. That is server behavior the catalog states, not a framework behavior.

**Isolation.** TX-05's ordering is PostgreSQL's, including the fact that PostgreSQL treats `READ UNCOMMITTED` and `READ COMMITTED` as the same. The second observation is an `SIReadLock`. The catalog says another engine needs its own ordering. The default PPCS server profile requires `default_transaction_isolation = read committed` (`harness/lib/instance.mjs`).

**Migrations.** MG-02 holds `pg_advisory_xact_lock` and ends a session with `pg_terminate_backend`. MG-02's idle case sets `idle_session_timeout`. MG-03's failing reversal assumes a transactional migration: the reversal's delete and its later error share a transaction, which is true of PostgreSQL DDL as well as DML. The safety gate is `cluster_name` on the disposable PostgreSQL container (`compose.yaml`, `scripts/pg-up.sh`).

**What is not PostgreSQL-specific.** The questions are. A reported commit should match a commit the server actually made. A client that never received an acknowledgement of `COMMIT` should not report success. A nested savepoint failure should not commit the nested writes. A connection that still holds a failed transaction should not be handed to unrelated work. Those questions can be asked of MySQL. The expected server behavior, the fault tool, and the observer queries cannot be copied.

None of the files named in this section were modified.

## 2. Environment

**Observed** from `evidence/server-config.json` and `evidence/run.json`.

| Item | Value |
| --- | --- |
| Server | MySQL Community Server 8.4.11, GPL, Linux aarch64 |
| Image | `mysql:8.4.11@sha256:24989179f58856db763f418010c1169fecc944e3ec1ea7e921572d83eb070f70` |
| Client | Node.js v24.14.1, `mysql2` 3.24.6 |
| `transaction_isolation` | `REPEATABLE-READ` |
| `autocommit` | `ON` |
| `transaction_read_only` | `OFF` |
| `innodb_lock_wait_timeout` | `50` |
| `innodb_rollback_on_timeout` | `OFF` on the default server, `ON` on the second |
| `innodb_deadlock_detect` | `ON` |
| `innodb_flush_log_at_trx_commit` | `1` |
| `innodb_doublewrite` | `ON` |
| `sync_binlog` | `1` |
| `log_bin` | `ON` |
| `binlog_format` | `ROW` |
| `gtid_mode` | `OFF` |
| `enforce_gtid_consistency` | `OFF` |
| `default_storage_engine` | `InnoDB` |
| `sql_mode` | `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION` |
| `character_set_server` / collation | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| `wait_timeout` / `interactive_timeout` | `28800` / `28800` |
| `lock_wait_timeout` (metadata locks) | `31536000` |
| `max_execution_time` | `0` |

The second server is the same image with `--innodb-rollback-on-timeout=ON`. **Observed:** `SET GLOBAL innodb_rollback_on_timeout = ON` on the default server failed with errno `1238`, `ER_INCORRECT_GLOBAL_LOCAL_VAR`, SQLSTATE `HY000`, message `Variable 'innodb_rollback_on_timeout' is a read only variable`. The value remained `0`. **Manual:** the variable is global, dynamic `No`, default `OFF` ([`innodb_rollback_on_timeout`](https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html#sysvar_innodb_rollback_on_timeout)).

Accounts created by the image entrypoint, **observed:** `mpcs@%`, `root@%`, `root@localhost`, all `caching_sha2_password`. `MYSQL_ROOT_HOST=%` is a container choice so the host can open the observer connection. The port is bound to `127.0.0.1`. Passwords are random per start and are not in `evidence/`.

Tables created by the experiments reported `ENGINE=InnoDB`. The data directory is a tmpfs. This run says nothing about crash recovery after a power loss.

An unrelated container already used the name `mpcs-mysql`. These containers are `mpcs-baseline-mysql` and `mpcs-baseline-mysql-rb-timeout`. The PostgreSQL container was not started or stopped by these scripts.

`mysql2` connection options, recorded without the password: host `127.0.0.1`, `connectTimeout` 10000, `supportBigNumbers`, `bigNumberStrings`, `dateStrings`, charset `utf8mb4`, `multipleStatements: false`.

## 3. How a step is recorded

Every experiment step has:

1. **Requested.** The SQL text and parameters.
2. **Driver.** `resolved` with the `mysql2` value, or `rejected` with `errno`, `code`, `sqlState`, `sqlMessage`, and `fatal` when those properties exist.
3. **Independent observation.** A different connection, after the driver call returned: `information_schema.innodb_trx` filtered by the subject's connection id, `performance_schema.events_transactions_current`, recent `events_transactions_history`, and `data_locks`. Marker visibility is a query on that other connection, or on a connection opened only after the call returned.

A visible row is a later fact. It is not recorded as proof that the client knew the commit when `mysql2` returned.

## 4. Experiments

### MPCS-01. Duplicate key, then COMMIT

**Observed** (`evidence/mpcs-01.json`).

`START TRANSACTION`, insert a marker, insert the duplicate code `'taken'`, catch the error, `COMMIT`. A second variant inserts another marker before `COMMIT`. No `ROLLBACK` is sent.

The duplicate insert rejected:

- errno `1062`
- code `ER_DUP_ENTRY`
- SQLSTATE `23000`
- message `Duplicate entry 'taken' for key 'uniq_row.uniq_code'`
- no `fatal` property on the error object

After that error, and before another statement, `events_transactions_current.STATE` was `ACTIVE`. A following insert resolved. Its OK packet had `serverStatus` `3`. `COMMIT` resolved with `serverStatus` `16386`, and `events_transactions_current.STATE` became `COMMITTED`.

A connection opened after `COMMIT` saw the original marker. In the second variant it saw both the original marker and the marker inserted after the error. It did not see a second `'taken'` row; the duplicate insert did not land.

`data_locks` after the error still showed the same `ENGINE_TRANSACTION_ID` holding an `IX` table lock on `marker`, an `IX` on `uniq_row`, an `S` record lock on `uniq_code` for `'taken'`, and an `X` lock on the primary index supremum. **Manual:** a duplicate-key error rolls back the statement, not the transaction, and locks taken by the statement are not released ([InnoDB error handling](https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html), [COMMIT](https://dev.mysql.com/doc/refman/8.4/en/commit.html)). The run matches that: the transaction stayed usable, and those locks were still granted.

`innodb_trx` filtered by connection id returned no row during this transaction, while `data_locks` and `events_transactions_current` showed it. The same filtered `innodb_trx` query did return a row in MPCS-03. **Observed limitation:** an empty `innodb_trx` result for that connection id is not evidence that no transaction exists.

**What the client knew at return.** On the duplicate insert, `mysql2` rejected with `1062` / `23000`. On `COMMIT`, `mysql2` resolved with an OK packet. The client did not receive a rollback tag. The later read shows the marker persisted. That read is not what the `COMMIT` call returned.

This is not PostgreSQL's TX-01A. There the caught unique violation aborts the transaction, and `COMMIT` completes with the command tag `ROLLBACK`. Here the caught duplicate key does not abort the transaction, and `COMMIT` acknowledges a commit of the earlier marker.

### MPCS-02. Deadlock

**Observed** (`evidence/mpcs-02.json`), three repetitions, same shape each time.

Two connections. T1 updates primary key `1`. T2 updates primary key `2`. T1 then updates key `2` and enters a lock wait. `performance_schema.data_lock_waits` showed that wait before T2 sent its conflicting update, at 1 ms, 53 ms, and 1 ms across the three repetitions. T2 then updates key `1`.

T2's statement rejected:

- errno `1213`
- code `ER_LOCK_DEADLOCK`
- SQLSTATE `40001`
- message `Deadlock found when trying to get lock; try restarting transaction`
- no `fatal` property

T1's waiting update then resolved. `SHOW ENGINE INNODB STATUS` reported `WE ROLL BACK TRANSACTION (2)`. In the status text, transaction `(1)` is T1's thread and transaction `(2)` is T2's thread. After the error, and before T2 sent another statement, T2's `events_transactions_current.STATE` was `ROLLED BACK` and T2 had no `innodb_trx` row. T1's state was `ACTIVE` / `RUNNING`. An independent read of `dl` still showed `(1, 0)` and `(2, 0)`: T1 had not committed.

T2 then ran `SELECT @@autocommit` successfully. The value was `1`. T2 inserted a marker in another table. That insert's `serverStatus` was `16386`, and the marker was visible to the other connection **before** T2's explicit `COMMIT`. That `COMMIT` resolved with `serverStatus` `2`. T1's later `COMMIT` resolved, and `dl` became `(1, 1)` and `(2, 1)`. Those values are T1's two updates. T2's updates are not in them.

**Manual:** a deadlock rolls back the whole victim transaction ([InnoDB error handling](https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html); error `1213` is SQLSTATE `40001`). The run matches that. The victim in this lock order was the transaction that completed the cycle, three times. **Hypothesis:** a different statement cost or lock order can choose the other transaction. This run does not establish that InnoDB always chooses the second waiter.

**What the client knew.** The victim's driver call rejected with `1213` / `40001`. A later statement ran and autocommitted. The explicit `COMMIT` after that was an OK packet for a session that was not in the deadlocked transaction. The client was not told, inside the `1213` error object, a transaction id or a rollback flag beyond the error text. The `ROLLED BACK` state was read by the other connection.

### MPCS-03. Lock wait timeout

**Observed** (`evidence/mpcs-03.json`).

One session holds an `UPDATE` lock. Another session, inside a transaction that has already inserted a marker, updates the same row. The holder later rolls back. The waited-for update does not change the row in any variant (`lk` stays `(1, 0)` after the holder rolls back).

The waited statement rejected in all three variants with the same driver error:

- errno `1205`
- code `ER_LOCK_WAIT_TIMEOUT`
- SQLSTATE `HY000`
- message `Lock wait timeout exceeded; try restarting transaction`
- no `fatal` property

| Variant | Server | Wait used | Elapsed | State after the error, before the next subject statement | Insert after the error | Rows visible after the waiter's `COMMIT` |
| --- | --- | --- | --- | --- | --- | --- |
| `default-timeout-rollback-off` | `innodb_rollback_on_timeout=OFF`, global wait `50` | that default | 50045 ms | `ACTIVE`, `innodb_trx` `RUNNING` | `serverStatus` `3` (still in the transaction); marker not yet visible | both the pre-timeout marker and the later marker |
| `session-timeout-2s-rollback-off` | same server | `SET SESSION innodb_lock_wait_timeout = 2` before `START TRANSACTION` | 2004 ms | same `ACTIVE` | same `serverStatus` `3` | both markers |
| `session-timeout-2s-rollback-on` | the other server, flag `ON` | session wait `2` | 2006 ms | `ROLLED BACK`, no `innodb_trx` row | `serverStatus` `16386`; the new marker was visible before `COMMIT` | only the marker inserted after the timeout |

The default 50 second wait and the 2 second session wait produced the same rollback scope on the default server. The session setting changed the wait, not the scope. **Manual:** default behavior rolls back only the statement; `--innodb-rollback-on-timeout` rolls back the transaction. The two server settings match that manual, and they produced the **same** `mysql2` error. The phrase `try restarting transaction` was the message in the default case, where the transaction was still active and a later statement in it committed.

**What the client knew.** The driver error does not say whether the transaction survived. That difference was visible to the other connection, and in whether the next insert's `serverStatus` still had the in-transaction bit.

### MPCS-04. Savepoints

**Observed** (`evidence/mpcs-04.json`). One `ENGINE_TRANSACTION_ID` was attached to the locks during an open savepoint. `events_transactions_current.NUMBER_OF_SAVEPOINTS` went to `1` after `SAVEPOINT`. There was no second transaction id.

**Rollback to a savepoint.** After `ROLLBACK TO SAVEPOINT sp1`, the same connection saw only the outer marker. The other connection saw nothing until `COMMIT`. After `COMMIT` it saw the outer marker and a marker inserted after the rollback. It did not see the marker inserted inside the savepoint. `NUMBER_OF_ROLLBACK_TO_SAVEPOINT` was `1`.

**Release.** `RELEASE SAVEPOINT` left the inner insert in the transaction. After `COMMIT`, both the outer and the inner marker were visible. Release did not commit by itself: the other connection did not see the new rows until `COMMIT`.

**Missing savepoint.** `ROLLBACK TO SAVEPOINT does_not_exist` and `RELEASE SAVEPOINT does_not_exist` each rejected with:

- errno `1305`
- code `ER_SP_DOES_NOT_EXIST`
- SQLSTATE `42000`
- message `SAVEPOINT does_not_exist does not exist`

The transaction stayed `ACTIVE`. The next insert resolved with `serverStatus` `3`. After the missing `ROLLBACK TO`, `ROLLBACK TO SAVEPOINT sp_real` still worked: the commit kept the outer marker and not the markers written after `sp_real`. After the missing `RELEASE`, `COMMIT` kept both the outer marker and the marker written after the error.

**Manual:** a missing savepoint is `ERROR 1305 (42000): SAVEPOINT identifier does not exist`, and `ROLLBACK TO SAVEPOINT` does not end the transaction ([SAVEPOINT](https://dev.mysql.com/doc/refman/8.4/en/savepoint.html)). The run matches that. It does not match PostgreSQL's `3B001` path, which leaves the session aborted so that a later `COMMIT` returns the tag `ROLLBACK`.

Autoincrement values skipped across a rolled-back insert (the committed ids were not contiguous). That is a side observation from the same tables, not a transaction-outcome result.

### MPCS-05. COMMIT, ROLLBACK, and connection failure

**Observed** (`evidence/mpcs-05.json`). A lost `COMMIT` response was not attempted.

**Source, `mysql2` 3.24.6.** `lib/packets/resultset_header.js` parses the MySQL OK packet into `fieldCount`, `affectedRows`, `insertId`, `info`, `serverStatus`, `warningStatus`, `changedRows`, and `stateChanges` when the session-state flag is set. The file comment says the packet is an OK packet, not a command completion. `lib/promise/make_done_cb.js` resolves `[rows, fields]`. `lib/constants/server_status.js` names the status bits and says they were extracted from `mysql_com.h`. The bits used here are `SERVER_STATUS_IN_TRANS = 1`, `SERVER_STATUS_AUTOCOMMIT = 2`, and `SERVER_SESSION_STATE_CHANGED = 16384`. `lib/promise/connection.js` also has `beginTransaction`, `commit`, and `rollback` methods. Those methods were not called. The experiments sent SQL.

**Observed OK packets.** `query()` resolved to a `ResultSetHeader`. Enumerable keys on a transaction-ending `COMMIT` were `fieldCount`, `affectedRows`, `insertId`, `info`, `serverStatus`, `warningStatus`, `stateChanges`, `changedRows`. There is no `command` property. `affectedRows` was `0`, `info` was `""`, `warningStatus` was `0`, and `SHOW WARNINGS` on the next statement returned no rows. `stateChanges` was `{ systemVariables: {}, schema: null, gtids: [], trackStateChange: null }`.

| Statement | `serverStatus` | Bits, using the `mysql2` constants above |
| --- | --- | --- |
| `START TRANSACTION` | `16387` | `16384 + 2 + 1` |
| insert inside that transaction | `3` | `2 + 1` |
| `COMMIT` of that transaction | `16386` | `16384 + 2` |
| `ROLLBACK` of an open transaction that had inserted a row | `16386` | `16384 + 2` |
| `COMMIT` or `ROLLBACK` with no explicit transaction | `2` | `2` |

`COMMIT` and `ROLLBACK` that end a transaction produced the same header shape. The packet does not say which statement ran. The client knows which statement it sent, and that the server acknowledged it. `events_transactions_current.STATE` after a successful `COMMIT` was `COMMITTED`. After a successful `ROLLBACK` it was `ROLLED BACK`. The marker inserted before `ROLLBACK` was absent for a new connection. The marker inserted before `COMMIT` was present for a new connection. That presence was read after the driver returned. It is not a field of the OK packet.

`@@autocommit` stayed `1` through `START TRANSACTION`. The in-transaction bit, not the autocommit bit, is what changed. `events_transactions_current.AUTOCOMMIT` was `NO` for the explicit transaction even though the session variable was `1`.

**Connection failure, KILL.** The observer ran `KILL <connection id>`. The observer's `KILL` resolved with an OK packet (`serverStatus` `2`). The subject's thread was gone from `performance_schema.threads` before the subject sent `COMMIT` (the wait returned in the same poll). `COMMIT` then rejected with `fatal: true` and message `Can't add new command when connection is in closed state`. The error object had no `errno` and no `sqlState`. The connection also emitted `PROTOCOL_CONNECTION_LOST`, `fatal: true`, message `Connection lost: The server closed the connection.` A new connection did not see the uncommitted marker.

**Connection failure, local close.** `connection.destroy()` delegates to `Connection.close()`, which ends the socket and rejects later commands (**source**). The following `COMMIT` rejected with the same closed-state message, `fatal: true`. No `PROTOCOL_CONNECTION_LOST` event was recorded on that connection. The server thread was gone within 53 ms. The uncommitted marker was absent afterward.

**What those two failures are, and are not.** In both, `mysql2` did not return an OK packet for `COMMIT`, and the closed-state error means the driver did not send the statement. That is client-side knowledge that `COMMIT` was not acknowledged. The missing marker is a later observation that the open transaction did not become visible. Neither experiment discards a `COMMIT` reply after the server has executed `COMMIT`. That lost-response case was not run. **Hypothesis:** a proxy that drops the OK packet would be a different result, and this phase does not say what `mysql2` would surface then.

**After disconnect.** `events_transactions_history` for the subject's `THREAD_ID`, read after `connection.end()`, returned no rows. The thread row was gone. `gtid_mode` is `OFF`; the history GTID observed while the session existed was `ANONYMOUS` on commit and `AUTOMATIC` while active. The binary log is on. This run did not read it. **Hypothesis:** the binlog might retain a commit record after the session is gone. That was not checked. A later marker read still works, and it is still a later read.

## 5. Probes

**Observed** (`evidence/probes.json`). These are not catalog cases.

**Second `START TRANSACTION`.** Insert `implicit-doomed`, then `START TRANSACTION` again, then insert `implicit-next`, then `ROLLBACK`. The other connection saw `implicit-doomed` at the second `START TRANSACTION`, before the rollback. After `ROLLBACK`, a new connection still saw `implicit-doomed` and did not see `implicit-next`. **Manual:** `START TRANSACTION` implicitly commits the current transaction, and transactions cannot be nested ([statements that cause an implicit commit](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html)). The run matches that. On PostgreSQL the analogous hazard in TX-03 is different: a second `BEGIN` on an open transaction joins it. Here the second `START TRANSACTION` commits the first transaction, and the later `ROLLBACK` does not undo that commit.

**DDL.** `CREATE TABLE` inside a transaction that had inserted `ddl-marker` returned `serverStatus` `16386`, and the other connection could already see `ddl-marker`. The following `ROLLBACK` returned `serverStatus` `2`. The marker and the new InnoDB table were both still there. **Manual:** `CREATE TABLE` is in the implicit-commit list, and a user `ROLLBACK` does not undo `CREATE TABLE`. The run shows the preceding insert was committed as well.

**Isolation.** `SET TRANSACTION ISOLATION LEVEL <level>` and then `START TRANSACTION`, for `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, and `SERIALIZABLE`. While the transaction was `ACTIVE`:

- `performance_schema.events_transactions_current.ISOLATION_LEVEL` was the requested level. The spelling there is `REPEATABLE READ` with a space.
- `SELECT @@transaction_isolation` on that same connection returned `REPEATABLE-READ` for every requested level, including `SERIALIZABLE` and `READ UNCOMMITTED`. The spelling of the session variable uses a hyphen.

So the PostgreSQL-shaped check `current_setting('transaction_isolation')` does not carry over to `@@transaction_isolation` when the level was set with `SET TRANSACTION` rather than `SET SESSION`.

`SET SESSION transaction_isolation = 'SERIALIZABLE'` did make `@@transaction_isolation` return `SERIALIZABLE` inside the later transaction, and performance schema also said `SERIALIZABLE`. After the insert, `data_locks` showed only a table `IX` lock. After the following plain `SELECT` of the inserted row, a record lock `X,REC_NOT_GAP` on that unique key was also present. The three weaker `SET TRANSACTION` runs had only the table `IX` lock after the same insert-then-select sequence. The `SERIALIZABLE` `SET TRANSACTION` run had the table lock and the record lock. **Manual:** InnoDB `SERIALIZABLE` is repeatable read plus locking on plain reads. The lock that appeared between the insert snapshot and the select snapshot, in the `SET SESSION` run, is the observation behind that reading. There is no `SIReadLock` in these snapshots.

`SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` while a transaction was already open rejected with errno `1568`, `ER_CANT_CHANGE_TX_CHARACTERISTICS`, SQLSTATE `25001`, message `Transaction characteristics can't be changed while a transaction is in progress`. The following `SELECT @@transaction_isolation` still returned `REPEATABLE-READ`.

`READ UNCOMMITTED` and `READ COMMITTED` were distinct in performance schema. PostgreSQL's TX-05 note that those two levels are the same does not describe this server.

**`GET_LOCK`.** `GET_LOCK('mpcs_probe_lock', 2)` returned `1` on the holder. Another connection's `GET_LOCK(..., 1)` returned `0` while the holder was inside a transaction, and again after the holder ran `ROLLBACK`. The holder's marker was gone after that rollback. After `RELEASE_LOCK`, the other connection's `GET_LOCK` returned `1`. A named lock is not released by rolling back the transaction that was open when it was taken. It is not `pg_advisory_xact_lock`.

**Released savepoint, then outer `ROLLBACK`.** `SAVEPOINT`, insert, `RELEASE SAVEPOINT`, `ROLLBACK`. A new connection saw no markers. Performance schema state after the rollback was `ROLLED BACK`. Releasing the savepoint did not commit the inner row.

## 6. Client knowledge

| Situation | What `mysql2` returned | What another connection could see afterward | Did the client know the commit outcome from the call itself? |
| --- | --- | --- | --- |
| `COMMIT` of an open transaction | OK packet, `serverStatus` `16386` | `STATE=COMMITTED`, marker visible | It knew the server acknowledged the `COMMIT` statement it sent. The packet does not name the command. |
| `ROLLBACK` of an open transaction | OK packet, `serverStatus` `16386` | `STATE=ROLLED BACK`, marker absent | It knew the server acknowledged the `ROLLBACK` it sent. The header matches `COMMIT`. |
| Duplicate key, then `COMMIT` | statement error `1062`, then a `COMMIT` OK packet | marker from before the error is visible | It knew the insert failed and that `COMMIT` was acknowledged. It was not told that the transaction had been aborted, because it had not. |
| Deadlock victim | error `1213` / `40001` | `STATE=ROLLED BACK` before the next statement | It knew that statement failed with `1213`. The full rollback was observed on the server. A following statement autocommitted. |
| Lock wait, default | error `1205` / `HY000` | transaction still `ACTIVE` | It knew the waited statement failed. The error text does not say the transaction survived. It did survive. |
| Lock wait, rollback-on-timeout | the same `1205` / `HY000` | `STATE=ROLLED BACK` | The driver error matches the default case. The transaction did not survive. The client cannot tell these apart from the error object alone. |
| `KILL`, then `COMMIT` | fatal closed-state error, no SQLSTATE | thread already gone; marker absent | It knew `COMMIT` was not sent. It did not receive an OK packet. |
| `destroy()`, then `COMMIT` | the same closed-state error | marker absent | Same client knowledge. No `PROTOCOL_CONNECTION_LOST` event on this path. |
| Lost OK packet after a completed `COMMIT` | not run | not run | Not established. |

## 7. PPCS case matrix

The PPCS case ids and their expected outcomes are unchanged. This table says whether that case can be asked of MySQL, not whether a framework passes it. No framework was run.

| PPCS case | Class | Why |
| --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | Portable with MySQL-specific expectations | The question, reported outcome versus server outcome, is the same. `pg_xact_status()` is not. While the session still exists, `events_transactions_current.STATE` was `COMMITTED` or `ROLLED BACK` after a successful `COMMIT` or `ROLLBACK`, and a new connection's marker read agreed. After `connection.end()`, the history row for that thread was gone. A later marker read remains available and is still a later read. |
| `TX-01A.caught-error-then-commit` | PostgreSQL-specific and not applicable | The case requires a transaction that PostgreSQL has already aborted, so that `COMMIT` is answered with the tag `ROLLBACK`. **Observed:** a caught duplicate key left the transaction `ACTIVE`, and `COMMIT` acknowledged persistence of the marker. Applying TX-01A.1 unchanged would call a correct MySQL commit a failure. A MySQL case for this statement is a different case: the error rolls back the statement, and a later `COMMIT` commits the earlier work. Deadlock and lock-wait-with-`innodb_rollback_on_timeout` do roll back the whole transaction, but the error is on the failed statement, and a later `COMMIT` is not answered with a rollback tag. |
| `TX-01B.conn-lost-before-commit` | Requires a different fault-injection mechanism | The question, do not report success without an acknowledgement of `COMMIT`, is portable. PPCS uses `pg_terminate_backend`. **Observed** with `KILL`: the thread was gone, `COMMIT` was not sent, and `mysql2` returned a fatal error with no SQLSTATE. The marker was absent afterward. |
| `TX-01B.commit-reply-discarded` | Unresolved pending further investigation | The question is portable. The PPCS fault patches `pg.Client.prototype.query` after the server has completed `COMMIT`. That was not done for `mysql2`. The OK packet is not a command tag, so the PostgreSQL rule "tag is `COMMIT`" has nothing to read. Do not treat an OK packet, or a later marker, as a substitute answer for a reply that never arrived. |
| `TX-02.savepoint-rollback-not-sent` | Requires a different fault-injection mechanism | Withholding `ROLLBACK TO SAVEPOINT` is a `pg` client patch. It was not ported. **Observed** when rollback-to does run: the inner marker is absent after commit and the outer marker is present. The PostgreSQL signature, a second subtransaction id and `idle in transaction`, was not present; one InnoDB transaction id was. If the statement is simply never sent, a later `COMMIT` would commit the inner row. That injection was not run. |
| `TX-02.savepoint-rollback-rejected` | PostgreSQL-specific and not applicable | The case depends on `3B001` aborting the transaction so that `COMMIT` returns the tag `ROLLBACK`. **Observed:** a missing savepoint is `1305` / `42000`, the transaction stays `ACTIVE`, later statements run, and the real savepoint still rolls back. A MySQL expectation for that statement is the opposite of the PostgreSQL one and has to be a different case. |
| `TX-02.conn-lost-before-savepoint-rollback` | Requires a different fault-injection mechanism | Same class of fault as `TX-01B.conn-lost-before-commit`, at the savepoint statement. `KILL` of an open transaction was observed in MPCS-05: the uncommitted marker did not become visible. The savepoint statement itself was not the statement in flight during that `KILL`. |
| `TX-03.rollback-not-sent` | Portable with MySQL-specific expectations | The question, a failed unit's transaction must not commit, and the next unit must be its own transaction, still applies. The PostgreSQL mechanism, the next `BEGIN` joins the open transaction, does not. **Observed:** a second `START TRANSACTION` committed the first transaction. The doomed marker was visible before the second transaction's `ROLLBACK`, and that `ROLLBACK` did not remove it. Staging "ROLLBACK was not sent" for a framework still needs a `mysql2` injection rather than `pg.Client.prototype.query`. |
| `TX-03.statement-error-rollback-not-sent` | PostgreSQL-specific and not applicable | The case requires an aborted block and `25P02` until `ROLLBACK`. **Observed:** duplicate key `1062` does not do that. The next statement ran. The MySQL hazard if `ROLLBACK` is then skipped is the implicit commit in the previous row, not an aborted block that fails loudly. |
| `TX-03.conn-lost-in-transaction` | Requires a different fault-injection mechanism | `KILL` instead of `pg_terminate_backend`. The open transaction's marker was not visible after the session was gone. |
| `TX-04.nested-failure-contained` | Portable with MySQL-specific expectations | **Observed** with SQL savepoints, not a framework: rollback-to, then commit, kept the outer marker and dropped the inner one. Confirm with marker visibility. Do not require a second transaction id. |
| `TX-04.nested-released-outer-rollback` | Portable with MySQL-specific expectations | **Observed:** `RELEASE SAVEPOINT` then outer `ROLLBACK` left no markers. Release did not commit the inner write. |
| `TX-04.independent-inner` | Unresolved pending further investigation | This is a second connection and a framework propagation promise. InnoDB savepoints are not that. The implicit-commit probe shows a second `START TRANSACTION` on the **same** connection commits the outer work, so it is not an independent inner transaction. A real independent transaction needs another connection. No framework API was called. |
| `TX-05.managed-serializable`, `TX-05.explicit-serializable` | Portable with MySQL-specific expectations | The question, did the requested level take effect or was it refused, can be asked. The PostgreSQL ordering and `SIReadLock` check cannot. **Observed:** `SET TRANSACTION` made performance schema report the requested level, including distinct `READ UNCOMMITTED` and `READ COMMITTED`, while `@@transaction_isolation` stayed `REPEATABLE-READ`. `SET SESSION` made `@@transaction_isolation` agree. `SERIALIZABLE` added a record lock that the weaker levels did not show on this insert-then-select workload. Setting the level inside an open transaction failed with `1568` / `25001`. The default isolation on this server is `REPEATABLE-READ`, not read committed. |
| `MG-02.held`, `MG-02.first-deployment`, `MG-02.session-loss` | Unresolved pending further investigation | The marker-count question is not MySQL-specific. The PPCS mechanism is `pg_advisory_xact_lock` and `pg_terminate_backend`. **Observed:** `GET_LOCK` survived `ROLLBACK`. **Hypothesis:** a migration lock built on `GET_LOCK` will not follow the transaction, so the PPCS hold point cannot be copied. Not run inside a migration runner. Session loss would use `KILL`, which was observed only for a single open transaction. |
| `MG-02.idle-session-timeout` | PostgreSQL-specific and not applicable | The case sets PostgreSQL `idle_session_timeout`. This server has `wait_timeout` and `interactive_timeout` at `28800`. No MySQL session was ended by an idle timeout in this run. |
| `MG-03.valid-reversal`, `MG-03.no-reversal` | Unresolved pending further investigation | History versus marker is a framework question. No migration tool was run. DML-only reversal is a normal transaction. That was not run as a migration. |
| `MG-03.failing-reversal` | Portable with MySQL-specific expectations | The PPCS case says a transactional reversal's failed delete leaves the marker in place. **Observed:** DML in an explicit transaction rolls back with `ROLLBACK`. **Observed:** `CREATE TABLE` inside a transaction committed the preceding insert, and `ROLLBACK` did not undo either. A reversal that runs DDL does not have the atomicity this case assumes. A DML-only reversal can. The case text can stay; a MySQL adapter would have to say which kind of migration it ran. |

## 8. Architecture

MySQL-specific controls and expectations can be added without a database abstraction in the PPCS harness. The way to do that is a sibling tree, not a `Database` interface behind `harness/lib`.

Three options were considered.

**Parameterize the current harness.** One observer, one classifier, one protocol, with a driver argument. This rejects itself. `harness/lib/observer.mjs` calls `pg_xact_status` and reads `pg_locks`. `harness/lib/classify.mjs` requires `23505`, `25P02`, `3B001`, and `idle in transaction (aborted)`. `harness/lib/instance.mjs` refuses a server whose `cluster_name` is wrong and whose default isolation is not read committed. `schema/result.v1.schema.json` requires `xid` and `fate` from those PostgreSQL reads. A change under `harness/lib` or `harness/run.mjs` changes the harness digest, so existing `--expect` comparisons stop working. MySQL's duplicate-key and missing-savepoint results would also pressure someone to edit TX-01A and TX-02 so that the current adapters still pass. Those invariants should not move.

**Keep the PPCS protocol and special-case MySQL inside the classifier.** Same problem, smaller surface. The catalog sentence for TX-01A is the PostgreSQL mechanism. A MySQL result that commits after a caught duplicate key is a different fact, not a qualifier on that sentence.

**Add a separate MySQL runner and catalog, and do not import `harness/lib`.** This is the recommendation. The scripts in this directory are the control experiments. A later runner can live beside them, write its own evidence, and start its own containers from this `compose.yaml`. Copying the idea of newline-delimited messages is fine. Importing `harness/lib/adapter-process.mjs` is not: that module is the PPCS protocol (`ppcs: 1`, `PG*` stripped from the environment). A change to it changes the PPCS harness digest.

Suggested order, none of it done here:

1. Leave this baseline as the measured oracle. Do not register it as an adapter.
2. After approval, add a new catalog file that states MySQL expectations. Do not edit `specifications/transactions.v1.json`. The first cases worth writing are the ones this run actually measured: observation control, duplicate-key-then-commit, deadlock, lock-wait under both `innodb_rollback_on_timeout` values, savepoint success and missing savepoint, commit acknowledgement versus connection loss, and implicit commit on a second `START TRANSACTION`. Leave the lost-response case out until a fault exists that drops the reply without the client parsing it.
3. A small runner next to that catalog. Its observer reads another connection, as these scripts do. It does not call `pg_xact_status`. It records the OK packet or the driver error as what the client had, and the other connection as what the server did.
4. A `mysql2` control program with two modes, analogous in role to `pg-control` but not an edit of it. The careful mode reports committed only after the `COMMIT` it sent is acknowledged, and reports a driver failure when `COMMIT` cannot be sent. The careless mode reports committed when `COMMIT` does not throw, including after a deadlock it caught and ignored, and reports a rollback when the connection died even though it did not see a server rollback. Those two modes are the gate for later framework runs. They are not written yet.
5. **Knex**, `mysql2` dialect, native `knex.transaction`, pinned. Lucid sends SQL through Knex. A Lucid/MySQL result will not be interpretable until the same case has been run on Knex itself. Do not infer Knex's MySQL behavior from Lucid's PostgreSQL PPCS column.
6. **Kysely**, `MysqlDialect`, same `mysql2` version, native transaction API. Kysely does not sit on Knex. Run it after the `mysql2` control exists. It can be built in parallel with Knex once that control and the runner exist; the sequence puts Knex first only because Lucid depends on it.
7. **Lucid** last, on Knex and `mysql2`, native mode only. Its PostgreSQL TX-01A failure is a `ROLLBACK` command tag that MySQL does not return for a duplicate key. A MySQL run has to be measured. It must not be scored with the PostgreSQL expected outcome.

Drizzle, TypeORM, MikroORM, and Prisma are out of this phase. Prisma in particular needs its own transaction and migration notes; nothing here measured it.

## 9. Shared changes that would need approval

No shared file was changed. No adapter was added. No commit was made.

Do not do the following without a separate decision. Each one moves PostgreSQL results or the harness digest.

| Change | Why it is not part of this phase |
| --- | --- |
| Edit `specifications/transactions.v1.json` or `docs/specifications.md` so TX-01A, TX-02, or TX-03 accept the MySQL outcomes | Those sentences are the PostgreSQL mechanisms. MySQL needs new sentences. |
| Edit `harness/lib/observer.mjs`, `classify.mjs`, `instance.mjs`, or `run-case.mjs` to accept MySQL | They are the PostgreSQL observer, classifier, and safety gate. |
| Edit `harness/lib/adapter-process.mjs` so a MySQL adapter can speak it | Couples the protocols and changes the harness digest. |
| Edit `schema/result.v1.schema.json` or `schema/run.v1.schema.json` | The result schema requires `xid` and `pg_xact_status` fate. MySQL evidence should stay in its own files until a schema is approved. |
| Edit `adapters/node-kit/pg-instrument.mjs` or `adapters/pg-control/` | Category C and D faults and the command-tag control are node-postgres. |
| Edit root `compose.yaml`, `scripts/pg-up.sh`, or `scripts/pg-down.sh` | The disposable PostgreSQL 18.6 server. MySQL uses `investigations/mysql-innodb-baseline/compose.yaml`. |
| Add Knex, Lucid, Kysely, or another ORM under `adapters/` | Knex was measured only as `investigations/mysql-innodb-baseline/src/run-knex.mjs`. It is not a PPCS adapter. |

## 10. Knex 3.3.0

**Observed** (`evidence/knex.json`, `2026-10-19T15:51:36.053Z`). Knex 3.3.0 is the version `@adonisjs/lucid` 22.4.2 depends on. The client is still mysql2 3.24.6, on the same default MySQL 8.4.11 server. This is not a PPCS run and not an ORM result. Lucid was not called.

**Source.** Knex's mysql2 transaction sends `BEGIN;`, commits when the callback resolves, and sends `ROLLBACK` when the callback rejects (`node_modules/knex/lib/execution/transaction.js`). The mysql2 dialect swallows `ER_SP_DOES_NOT_EXIST` on those transaction statements. These three cases do not hit that path.

`mysql2-correct` reports a commit when the `COMMIT` it sent is acknowledged, and it sends `ROLLBACK` after an application error. `mysql2-unsafe` reports a commit when `COMMIT` does not throw, including after a deadlock, and it starts the next transaction without sending `ROLLBACK`.

| Case | mysql2-correct | mysql2-unsafe | Knex native |
| --- | --- | --- | --- |
| Caught duplicate key, callback returns | Claims committed. OK packet `serverStatus` `16386`. Marker visible. Error was `1062` / `23000`. | Claims committed because `COMMIT` did not throw. Same packet and the marker is visible. | `knex.transaction` resolved. Query log: `BEGIN;`, both inserts, `COMMIT;`. The duplicate insert was `1062` / `ER_DUP_ENTRY` / `23000`. Marker visible. |
| Deadlock, subject is the victim | Claims failed. Subject got `1213` / `40001`. `COMMIT` was not sent. Victim marker absent. | Claims committed. Subject got `1213`, then `COMMIT` resolved with `serverStatus` `16386`. Victim marker absent. | `knex.transaction` rejected with `1213` / `ER_LOCK_DEADLOCK` / `40001`. Query log ends in `ROLLBACK`. Victim marker absent. |
| Next transaction without a `ROLLBACK` of the first | Claims rolled back. First `ROLLBACK` was sent. Neither marker remains. | Claims rolled back because the second `ROLLBACK` was acknowledged. The first marker was already visible at the second `START TRANSACTION`, and it remains. | `knex.transaction` rejected with the callback's error, `second unit fails`, which has no errno. The first marker remains. |

The deadlock subject is the victim only when it is the lighter transaction. A first run, where the subject had inserted a marker and the fixture had not, killed the fixture instead (`1213` on the fixture, and the subject's update resolved). The recorded run gives the fixture eight extra inserts so the subject is the one rolled back. The surviving fixture's later commit leaves `dl` at `(1, 1)`.

Knex agrees with the careful control on the two cases that go through `knex.transaction(callback)`. A caught duplicate key is a commit. A deadlock that escapes the callback is a rejection carrying `1213`, and the victim's marker is absent. The careless control's post-deadlock `COMMIT` is the one that claims a commit the marker does not support. Its OK packet is the same `16386` as a commit of work that was still open.

The third case is the implicit commit, reached by holding a Knex pool connection in `BEGIN` and then calling `knex.transaction` on that connection. Knex sends its own `BEGIN;` for the second unit. The first marker is visible afterward, and the rejection describes only the second unit. The careful control, which sends `ROLLBACK` before the next transaction, leaves neither marker.

## 11. Lucid 22.4.2

**Observed** (`evidence/lucid.json`, `2026-10-19T16:17:24.357Z`). Lucid 22.4.2, Knex 3.3.0, mysql2 3.24.6, MySQL 8.4.11. The call is `db.transaction(callback)`. This is not a PPCS adapter.

**Source.** Lucid awaits `knex.transaction()` without handing Knex the callback, runs the callback itself, calls `commit()` when the callback returns, and calls `rollback()` then rethrows when the callback throws (`@adonisjs/lucid` 22.4.2, `build/src/query_client/index.js`).

| Case | Lucid | Knex 3.3.0, from `evidence/knex.json` |
| --- | --- | --- |
| Caught duplicate key, callback returns | Resolved. Query log: `BEGIN;`, both inserts, `COMMIT;`. Duplicate insert `1062` / `ER_DUP_ENTRY` / `23000`. Marker visible. | Same claim, one marker visible. |
| Deadlock, subject is the victim | Rejected with `1213` / `ER_LOCK_DEADLOCK` / `40001`. Query log ends in `ROLLBACK`. Victim marker absent. `dl` is `(1, 1)` after the heavier fixture commits. | Same claim, same error, marker absent. |
| Next transaction without a `ROLLBACK` of the first | Rejected with `second unit fails` and no errno. The first marker remains. | Same claim, one marker remains. |

The comparison recorded in `evidence/lucid.json` matches Lucid to Knex on the claim and the marker count for all three cases. Lucid does not add a different commit or rollback outcome on top of the Knex behavior already recorded.

## 12. Lost COMMIT reply

**Observed** (`evidence/lost-commit.json`, `2026-10-19T17:00:15.446Z`). A local proxy forwarded the MySQL protocol. It forwarded the `COMMIT` query. It read the server's reply packet and did not write that packet to the client, then closed the client socket. This is not a driver hook that parses the OK packet and then discards it.

The dropped packet started with `0x00` and contained status bytes `0x4002` (`serverStatus` `16386`), the same OK packet recorded for an ordinary `COMMIT`. A connection that did not go through the proxy saw the marker. A control `COMMIT` through the same proxy, with the drop disarmed, resolved with `serverStatus` `16386` and its marker was visible.

| Client | What the call returned | Marker afterward |
| --- | --- | --- |
| mysql2 `query('COMMIT')` | Rejected. `PROTOCOL_CONNECTION_LOST`, `fatal: true`, no SQLSTATE. | Visible |
| Knex 3.3.0 `knex.transaction` | Rejected. Same `PROTOCOL_CONNECTION_LOST`. The log shows `COMMIT;` was sent. | Visible |
| Lucid 22.4.2 `db.transaction` | Resolved. The log shows `COMMIT;` was sent. | Visible |

**Source.** Lucid awaits `knexClient.commit()` (`@adonisjs/lucid` 22.4.2, `build/src/query_client/index.js`). Knex's mysql2 `Transaction.query` catches a failed transaction statement and still resolves the promise returned to `commit()`, while rejecting the separate promise that `knex.transaction(callback)` waits on (`node_modules/knex/lib/dialects/mysql2/transaction.js`). The recorded calls match that split: Knex's managed transaction rejected, and Lucid's managed transaction resolved.

The client that received `PROTOCOL_CONNECTION_LOST` knew the connection failed. It did not receive the OK packet. The visible marker was read afterward. Lucid's resolved promise tells its caller the transaction committed. That caller did not receive the OK packet either.

## 13. Limits

- One full run, plus three deadlock repetitions inside it. The duplicate-key, lock-wait, and savepoint results were each a single execution. The 50 second lock wait and the 2 second lock wait agreed on scope. That is not a statistical claim.
- Knex 3.3.0 and Lucid 22.4.2 were each run once on the three cases (`evidence/knex.json`, `evidence/lucid.json`). Kysely was not run. The first Knex deadlock attempt was discarded because InnoDB killed the fixture instead of the subject. The Lucid deadlock used the heavier fixture from the start.
- The lost COMMIT reply was run once through a local proxy (`evidence/lost-commit.json`). mysql2 and Knex rejected. Lucid resolved.
- The binary log was not read. `gtid_mode` is off, so there is no GTID to look up after the session ends.
- `innodb_trx` by connection id was sometimes empty while performance schema and `data_locks` showed the transaction. Do not use that view alone.
- The host is aarch64. The image pin is the multi-platform index digest of `mysql:8.4.11`.
- tmpfs: no durability claim across a crash of the container.
