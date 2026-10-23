# PHP and CodeIgniter 4 on the MySQL companion runner

This directory is a subject for `../src/run-php-mx01.mjs`. It is not a PPCS adapter. It does not run `harness/run.mjs`, and it does not change PostgreSQL cases. The runner writes `../evidence/php-mx01.json`. That file does not replace `../evidence/suite.json` or the earlier mysql2 recordings.

CodeIgniter 4.7.5 has MySQLi, PostgreSQL, SQLite3, SQL Server, and OCI8 drivers. It has no PDO driver. PDO MySQL in this directory is an independent control.

## Reproduce

From `investigations/mysql-innodb-baseline`, with Docker, Node.js 24, PHP 8.5.6, and Composer:

```sh
pnpm install --frozen-lockfile --ignore-scripts
sh scripts/mysql-up.sh
cd php && composer install --no-interaction --no-scripts && cd ..
node src/run-php-mx01.mjs
```

`composer.json` pins `codeigniter4/framework` 4.7.5. `composer.lock` records reference `a1f129d56df3278702a8d1048af955d0ebf68c03`.

The Node script creates a schema, runs one PHP process per scenario, then reads `marker` and `uniq_row` from a connection opened after that process exits. The PHP process does not score itself. A password is passed in the environment and is not written to the evidence file.

## Recorded run

Finished `2026-10-21T17:15:26.400Z`. Evidence: `../evidence/php-mx01.json`. Three repetitions of each scenario. Every repetition matched its pre-stated expectation. `mismatched` is `[]`.

| Piece | Recorded value |
| --- | --- |
| Server | MySQL 8.4.11, image `mysql:8.4.11@sha256:24989179f58856db763f418010c1169fecc944e3ec1ea7e921572d83eb070f70` |
| `innodb_rollback_on_timeout` | `0` on the default server used here |
| Isolation / autocommit | `REPEATABLE-READ` / `1` |
| `innodb_lock_wait_timeout` | `50` |
| PHP | 8.5.6 |
| mysqli and pdo_mysql client | mysqlnd 8.5.6 |
| CodeIgniter | 4.7.5, `a1f129d56df3278702a8d1048af955d0ebf68c03` |
| Node | v24.14.1, mysql2 3.24.6 for the observer |

The duplicate-key setup is the same shape as `MX-01.duplicate-key-then-commit`: InnoDB `marker` and `uniq_row`, with `uniq_row.code = 'taken'` already present. The subject's failing statement is `INSERT INTO uniq_row (code) VALUES ('taken')`, errno `1062`, SQLSTATE `23000`.

`matched_expectation` means the run matched the sentence stored on that row as `expectation_basis`. It does not by itself classify a framework defect.

## What the run showed

**mysqli and PDO MySQL.** `MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT`, and PDO `ERRMODE_EXCEPTION`. The duplicate insert threw `1062` / `23000`. The following insert of `after-error` succeeded. `commit()` returned true. A later connection saw `before-error` and `after-error`, and still one `taken` row. That is the MX-01 server outcome: the statement failed and the transaction stayed usable.

**CodeIgniter managed default.** `DBDebug` true, `transStrict` true, `transException` false. `query()` returned false for the duplicate and did not throw. `error()` was `1062` and the duplicate message, without a SQLSTATE field. `transStatus()` was already false, and the following insert still returned true at transaction depth 1. `transComplete()` returned false. Neither marker remained. The user guide says the queries in a `transStart()` / `transComplete()` group are committed or rolled back together, and that a query error does not throw during a transaction by default. The false return and the absent rows agree with that group rollback. They are a different outcome from the mysqli control, which committed both markers.

**`transException(true)`.** The duplicate threw `CodeIgniter\Database\Exceptions\DatabaseException` with code `1062`. The previous `mysqli_sql_exception` carried SQLSTATE `23000`. Depth was 0 after the throw, and the caller did not reach its own `transComplete()`. The marker was absent. The guide says this setting rolls the group back and throws.

**Strict mode, the next group.** After the failed group, `transStatus()` stayed false. A new `transStart()`, a successful insert, and `transComplete()` returned false. No marker remained. `resetTransStatus()` made the next group commit: only `second-group` remained. `transStrict(false)` cleared the status inside the failed `transComplete()`, and the next group committed the same way. The guide describes both of those.

**Manual example.** `transBegin()`, then `transRollback()` because `transStatus()` was false. `transRollback()` returned true and the marker was absent. The same branch ran with `DBDebug` false. In both settings the duplicate `query()` returned false inside the transaction. `DBDebug` false still produced one error log line for the duplicate; the MySQLi `execute()` logs before it consults `DBDebug`. After the rollback, `transStatus()` was still false. A later managed group on that connection, without `resetTransStatus()`, rolled back. Its insert had returned true.

**`transCommit()` without the status check.** The guide's manual example checks `transStatus()` before it commits. This scenario skipped that check. `transStatus()` was false, `transCommit()` returned true, and `before-error` was visible afterward. `transStatus()` was still false. The next managed group rolled back, so `second-group` was absent. The commit return matches the row that remained. The status flag matches the later rollback. The flag does not mean the earlier `transCommit()` was rejected.

## Not in this run

Deadlock, lock-wait timeout, connection loss, commit-reply loss, savepoints, connection reuse after a failed transaction, DDL, Models, migrations, and `updateBatch()` are not in `php-mx01.json`. mysql2 evidence for several of those cases already exists beside this file. CodeIgniter's nested `transBegin()` is a depth counter in the 4.7.5 source and in the user guide; this run did not execute that path. The MySQLi `updateBatch()` SQL in 4.7.5 is an `UPDATE ... INNER JOIN` and the method does not append `QBWhere`; that is source reading, not a recorded execution.

No upstream issue is drafted from this run. The CodeIgniter outcomes above are the behaviors the user guide describes. The unchecked `transCommit()` result is what that method does when the caller does not follow the guide's status check.

## Deadlock and lock wait

`node src/run-php-concurrency.mjs` writes `../evidence/php-concurrency.json`. Node holds the other session. PHP is the subject. The subject is made the lighter deadlock victim the same way the mysql2 case is: the other session inserts eight ballast rows, locks row 1, waits on row 2, and the subject then updates row 1.

Recorded run finished `2026-10-21T17:44:17.623Z`. Thirteen scenario groups, three repetitions each, 39 runs, `mismatched` empty. Same PHP 8.5.6, mysqlnd 8.5.6, and CodeIgniter 4.7.5 as the duplicate-key run. Default server `innodb_rollback_on_timeout` 0. The second server is 1. Lock waits used `SET SESSION innodb_lock_wait_timeout = 2` and returned in 2002–2005 ms.

**Deadlock, errno 1213, SQLSTATE 40001 on the drivers.** The performance schema state after the error was `ROLLED BACK`. The victim marker was absent. An insert on that same connection was visible to another connection before the end call, so that insert autocommitted. mysqli `commit()` returned true and did not bring the victim marker back. `PDO::commit()` threw `There is no active transaction`. A first execution of this harness let that PDO exception escape and dropped the surrounding steps. The recorded file catches it and keeps the steps. The exception text was the same on the earlier three repetitions.

**CodeIgniter deadlock.** `query()` returned false, error code 1213, message `Deadlock found when trying to get lock; try restarting transaction`, and no SQLSTATE. `transStatus()` was false and `transDepth` stayed 1. The server transaction was already `ROLLED BACK`. The following insert autocommitted. `transComplete()` returned false. The documented manual branch called `transRollback()`, which returned true. `transCommit()` without the status check returned true, and `transStatus()` stayed false. In all three, the final rows were only the autocommitted insert. `transCommit()`'s true return is the same true mysqli returns when no transaction remains. It is not a commit of the victim transaction. The guide's status check takes the rollback branch instead.

**Lock wait, errno 1205, SQLSTATE HY000, message `Lock wait timeout exceeded; try restarting transaction`.** That message is the same whether or not the server aborts the transaction.

On the default server the transaction stayed `ACTIVE`. mysqli and PDO commit kept both markers. CodeIgniter still had depth 1 and `transStatus()` false. `transComplete()`, and the documented manual rollback, removed both markers. The driver commit on this server kept them. CodeIgniter's group rollback is the user-guide behavior. It discards a transaction InnoDB had left open.

On the server started with `innodb_rollback_on_timeout` ON, the state was `ROLLED BACK`. The marker written before the wait was absent. The insert after the error autocommitted. mysqli `commit()` returned true. `PDO::commit()` threw `There is no active transaction`. CodeIgniter's error report was the same 1205, false return, depth 1, and false status as on the default server. `error()` does not say which rollback scope applied. The later insert remained. The earlier marker did not.

The false return from `transComplete()` means the CodeIgniter group did not commit. A statement issued after InnoDB has already ended the transaction, and before that call, can autocommit anyway. The false return does not undo that statement.

## updateBatch() after where()

`node src/run-php-update-batch.mjs` writes `../evidence/php-update-batch.json`. Recorded run finished `2026-10-21T18:59:38.769Z`. Three repetitions, `mismatched` empty. Same server and CodeIgniter 4.7.5 as the other PHP runs.

The 4.7.4 changelog says `updateBatch()` after Query Builder `where()` conditions throws `DatabaseException`. The framework test is `testUpdateBatchThrowsExceptionWithWhere`. This run is that behavior on MySQL. The earlier source note that the MySQLi batch SQL omits `QBWhere` is still true of `_updateBatch()`. In 4.7.5, `updateBatch()` throws before it builds or sends that SQL when `where()` has already been called.

On a synthetic `item` table with two `scope_id` values and a shared `code`, `where('scope_id', 1)->updateBatch(..., 'code')` threw:

`updateBatch() cannot be safely combined with existing Query Builder WHERE conditions. Use updateBatch($data, $constraints), onConstraint(), or include all required constraint fields in the batch data.`

That happened with `DBDebug` true and false. `getLastQuery()` stayed unset, so no update was sent. A second connection still saw `alpha`, `beta`, and `gamma`. Calling `updateBatch()` again on the same builder, without a new `where()`, threw the same exception. The `where()` remains on the builder because the throw happens before `resetWrite()`.

Without `where()`, `updateBatch([['code' => 'a', 'label' => 'changed']], 'code')` returned 2. The SQL was an `UPDATE ... INNER JOIN` matching only `code`. Both scopes' `a` rows changed. `updateBatch()` with the constraint `['scope_id', 'code']`, and `scope_id` included in the row, returned 1 and changed only that scope.

CodeIgniter 4.7.0's `updateBatch()` does not contain this throw. It starts at `onConstraint()`. That version was not executed here. The 4.7.4 change is the closed fix: the call errors instead of updating every row that matches the constraint alone.

## Connection loss

`node src/run-php-connection.mjs` writes `../evidence/php-connection.json`. Recorded run finished `2026-10-21T19:27:50.163Z`. Nine groups, three repetitions, 27 runs, `mismatched` empty. This is not the lost `COMMIT` OK-packet case. The server's default `wait_timeout` is 28800. The idle cases set the session value to 1 and slept 3 seconds. `mysqli.reconnect` was off.

**Killed before commit.** Root ran `KILL` on the subject thread and waited until that thread was gone. Then the subject called commit. mysqli, PDO, and both CodeIgniter completion calls threw errno `2006`, SQLSTATE `HY000`, `MySQL server has gone away`. None returned success. The marker was absent. PDO's `inTransaction()` was still true after that exception. CodeIgniter's `transStatus()` was still true and `transDepth` stayed 1, because the exception left `transCommit()` before it decremented the depth.

**Idle `wait_timeout`.** The next statement on the same handle failed with errno `4031`, `The client was disconnected by the server because of inactivity.` The marker was absent and the old server thread was gone. mysqli and PDO threw. CodeIgniter `query()` returned false and did not throw. That is the in-transaction path with `transException` left false: `transStatus()` became false and `transDepth` stayed 1.

**`reconnect()` after the idle timeout.** `ping()` returned false. `reconnect()` did not throw. The new connection id was different, and the old thread was gone. `transDepth` was still 1 and `transStatus()` was still true, because `ping()` uses `simpleQuery()` and does not update that bookkeeping. An insert on the new connection was visible before the completion call. `transComplete()` and `transCommit()` both returned true. The timed-out marker was absent. The only remaining row was the insert made after reconnect. That true return is a commit on the new connection. It is not a commit of the transaction that was open when the server closed the session.

## Nested transactions

`node src/run-php-nested.mjs` writes `../evidence/php-nested.json`. Recorded run finished `2026-10-21T19:39:28.598Z`. Five scenarios, three repetitions, 15 runs, `mismatched` empty. This is not scored as MySQL `MX-04`. The user guide says only the outermost transaction commands are executed.

mysqli sent `SAVEPOINT sp1` and `ROLLBACK TO SAVEPOINT sp1`. After that rollback the same connection saw only `outer`. The outer `COMMIT` kept `outer` and `after`. `inside` was gone. Another connection saw no markers before that commit.

CodeIgniter sent no `SAVEPOINT`. An inner `transStart()` / `transComplete()` left `transDepth` at 1. The server history shows one `START TRANSACTION` and one `COMMIT`. The outer commit kept `outer`, `inside`, and `after`.

An inner `transRollback()` returned true and sent no `ROLLBACK`. The same connection still saw `inside`. The outer `transCommit()` kept both markers.

An inner `transCommit()` returned true and sent no `COMMIT`. Another connection saw nothing until the outer `transCommit()`, which kept both markers.

A duplicate key inside the inner managed pair returned false with errno `1062` and set `transStatus()` false. The inner `transComplete()` returned false and only decremented the depth. The same connection still saw `outer` and `inside`. The outer `transComplete()` then sent `ROLLBACK` and removed both. That is not a savepoint rollback of the inner write alone.

## DDL

`node src/run-php-ddl.mjs` writes `../evidence/php-ddl.json`. Recorded run finished `2026-10-21T20:04:32.993Z`. Two scenarios, three repetitions, 6 runs, `mismatched` empty. This is not scored as PostgreSQL `MG-03`.

mysqli started a transaction, inserted `ddl-marker`, and created `ddl_side`. Another connection could not see the marker before `CREATE TABLE`. After `CREATE TABLE` it could see the marker and the new table. A duplicate insert then failed with errno `1062`. `ROLLBACK` returned true. The marker and `ddl_side` both remained. The statement history contains `CREATE TABLE ddl_side` and `ROLLBACK`.

`MigrationRunner::force()` does not wrap `up()` in a transaction. It records a history row only when `up()` returns. The migration called `transStart()`, inserted the marker, ran the same `CREATE TABLE`, then the duplicate insert. After the create, `transDepth` was still 1 and `transStatus()` was still true, and the other connection already saw the marker and the table. The duplicate set `transStatus()` false. `transComplete()` returned false and sent `ROLLBACK`. The marker and the table remained. `up()` then threw `migration failed after schema change`. The runner did not write a `migrations` row for that class. The `migrations` table itself is the runner's own bookkeeping table, created before `up()`.

## Models

`node src/run-php-model.mjs` writes `../evidence/php-model.json`. Recorded run finished `2026-10-21T20:17:38.862Z`. Four scenarios, three repetitions, 12 runs, `mismatched` empty. The model allows `label` only. Validation is skipped. Timestamps and callbacks are off.

`update(1, ['label' => 'beta', 'secret' => 'changed'])` returned true. The SQL was `UPDATE item SET label = 'beta' WHERE item.id IN (1)`. Another connection saw `label` `beta` and `secret` still `keep`. `save()` with an `id` did the same.

`update(1, ['secret' => 'changed'])` threw `CodeIgniter\Database\Exceptions\DataException`, `There is no data to update.` No `UPDATE` was sent. The row stayed `alpha` / `keep`.

Inside `transStart()`, the same mixed `update()` returned true. Another connection still saw `alpha` / `keep` before `transComplete()`. A duplicate insert failed with errno `1062`. `transComplete()` returned false. The row was still `alpha` / `keep`. The Model return is not the transaction result.

