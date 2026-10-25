# Stage 4 review: Laravel afterCommit after a COMMIT answered with ROLLBACK

Reviewed 2026-10-25 UTC. Written by: Claude Opus 5.5 (max).

The runs in [`laravel/`](laravel/README.md) recorded the observation: PostgreSQL answered `COMMIT` with the command tag `ROLLBACK`, `PDO::commit()` returned `true`, and Laravel ran `afterCommit`. This review asks whether that is an upstream defect, which layer owns it, and whether production code reaches it. It does not re-record the observation. Nothing was filed or posted.

Verdicts use four labels: confirmed defect, plausible defect, expected behavior, unresolved. A verdict is this study's reading of a contract. Whether something is a defect is the maintainers' decision.

## Findings

1. **The false success is pdo_pgsql's.** For a `COMMIT` that PostgreSQL answered with `ROLLBACK`, `PDO::commit()` returns `true`, the value it returns for a real commit. PDO gives the application no other way to tell the two apart. PostgreSQL's own source calls that reply an unsuccessful commit. **Confirmed defect** against the documented return value, by this reading. The smallest correction is in `pgsql_handle_commit`.
2. **No independently actionable Laravel defect has been established for the false-success path.** Laravel runs `afterCommit` because `PDO::commit()` did not throw, and it cannot see the tag through PDO. Its documentation neither supports nor forbids catching a database error inside the closure. Whether its after-commit guarantees still make it responsible is for its maintainers to decide.
3. **A `COMMIT` that fails with an error is a different path.** For a deferred foreign key, PostgreSQL rejects `COMMIT` with `23503`, and PDO raises. Laravel's `DB::transaction()` then keeps the failed transaction's callbacks, and the next commit on the connection runs its `afterCommit`. That callback-retention defect is confirmed here on PostgreSQL, and already reported as [laravel/framework#61964](https://github.com/laravel/framework/issues/61964).
4. **The two defects interact, so a driver fix alone moves the wrong side effect without removing it.** I patched pdo_pgsql locally to report the `ROLLBACK` tag as a failure (check 9). With that driver, Laravel's `DB::transaction()` raises and runs no callback at once, but it keeps the failed transaction's record. The next commit on the connection then runs the aborted transaction's `afterCommit`. Correct callbacks need both the driver fix and #61964's fix.
5. **No silent trigger without an application catch on current builds.** None in Laravel 13.38.0's own code. None in pdo_pgsql built against libpq 17 or later. Built against libpq 16 or earlier, pdo_pgsql's own `DEALLOCATE` can abort the transaction ([php-src GH-21869](https://github.com/php/php-src/issues/21869), open). Behind PgBouncer that is plausible: its documentation predicts it, and a php-src user's server log shows the abort ([GH-12940](https://github.com/php/php-src/issues/12940)). It was not run here.
6. **The native pgsql extension reports the tag, and leaves it to the caller.** Expected behavior.
7. **The instrumentation does not explain the result.** Both minimal reproductions show it without the recorder, without added statements, and without observer reads during the transaction.

## Checks

### 1. Does `PDO::commit()` returning `true` violate its contract?

**Contract.** The PHP manual says `PDO::commit()` "Commits a transaction" and "Returns true on success or false on failure" ([`pdo/commit.xml`](https://github.com/php/doc-en/blob/master/reference/pdo/pdo/commit.xml)). The transactions page says work "is guaranteed to be applied to the database safely ... when it is committed." Neither page defines success more narrowly, or mentions a rollback by the server.

**PostgreSQL's definition.** PostgreSQL 18 marks this reply as a failed commit in two places:

- In `src/backend/tcop/utility.c:633-639`, when `EndTransactionBlock()` returns false, the code will "report unsuccessful commit" by setting the completion tag to `ROLLBACK`.
- The header of `EndTransactionBlock()` (`src/backend/access/transam/xact.c:4048-4052`) says: "Since COMMIT may actually do a ROLLBACK, the result indicates what happened: true for COMMIT, false for ROLLBACK."

**Evidence.**

- **Runtime.** In `pdo.caught-error` (three runs of three repetitions) and in [`repro/pdo-commit-rollback.php`](repro/pdo-commit-rollback.php) (three runs), `commit()` returned `true` and another connection could not see the row. The instrumented runs also show `pg_xact_status()` `aborted` and the wire tag `ROLLBACK`. The healthy transaction's `commit()` returned the same `true`.
- **php-src source** (`ext/pdo_pgsql/pgsql_driver.c`):
  - `pgsql_handle_commit()` calls `pdo_pgsql_transaction_cmd("COMMIT")`, which fails only when `PQresultStatus()` is not `PGRES_COMMAND_OK`. It never reads `PQcmdStatus()`.
  - The code is identical on `PHP-8.5` and on `master` at `296e8eac57` (2026-10-22).
  - PDO core's `PDO::commit()` returns `true` whenever the driver's method does (`ext/pdo/pdo_dbh.c`).
- **No other PDO signal**, at runtime, from [`pgsql-extension/commit-tag.php`](pgsql-extension/commit-tag.php):
  - `inTransaction()` was `true` before both commits;
  - `PDO::ATTR_CONNECTION_STATUS` was the same string for both;
  - none of `Pdo\Pgsql`'s 27 methods reports a tag or a transaction status.

  `errorInfo()` after `commit()` holds the earlier statement's error, when that statement ran on the connection handle. It is not a report about `COMMIT` (see [`laravel/README.md`](laravel/README.md)).
- **pdo_pgsql does report a `COMMIT` that fails with an error.** In `pdo.deferred-fk`, `commit()` raised `PDOException` `23503`. The gap is only the `ROLLBACK` tag.
- **Elsewhere:**
  - pgx returns an error for the tag `ROLLBACK`, as the PPCS GORM recording shows.
  - MikroORM 7.2.6-dev rejects with `25P02`.
  - The tracker records that a pgjdbc maintainer said `commit()` should report it (pgjdbc#4494).
  - psycopg#1453 and asyncpg#1400 report the same gap for those drivers. The tracker records both as submitted and waiting for a reply.

**Strongest counterargument.**

- "Success" may mean that the `COMMIT` command completed without an error response. libpq calls the reply `PGRES_COMMAND_OK`, and PDO never promised to interpret command tags.
- In the observed case, the application had already received an exception for the statement that aborted the transaction.
- Several other drivers behave the same way.
- Raising here would change what `commit()` does for code that today commits after a caught error.

**Verdict: confirmed defect,** by this reading of the contract. The server classifies the outcome as an unsuccessful commit, `commit()` returns the value documented for success, and PDO offers no other way to find out. The "application already knew" argument fails for the triggers in check 2, where no exception reaches PHP. Whether this is a bug fix or a behavior change, and for which branches, is for the maintainers.

### 2. What reaches it without an application catch?

**Question.** Can production code reach the false success with no application code catching a PostgreSQL error?

**Evidence.**

- **The application-catch trigger** needs no fault injection. Ordinary code catches `UniqueConstraintViolationException` inside `DB::transaction()`.
- **Laravel 13.38.0's own catches of query exceptions.** This is source reading of `src/Illuminate` at `c42f9abd4a`; none of the catches leaves a transaction silently aborted:
  - `Eloquent\Builder::createOrFirst()` and the `BelongsToMany`, `HasOneOrMany` and `HasOneOrManyThrough` helpers catch a unique violation inside `withSavepointIfNeeded()`, which is a savepoint when a transaction is open.
  - `Cache\DatabaseLock::acquire()` and `Session\DatabaseSessionHandler::performInsert()` follow a caught insert failure with an `UPDATE`. In an aborted transaction that `UPDATE` raises `25P02`, so the failure is loud. For the lock, laravel/framework PR [#62114](https://github.com/laravel/framework/pull/62114) describes exactly that: dispatching an already-locked `ShouldBeUnique` job inside `DB::transaction()` fails with `25P02`. It was merged into 13.x on 2026-10-20 at 21:51 UTC, after the v13.38.0 tag, and replaces the insert with `insertOrIgnore()`.
  - `Cache\DatabaseStore::add()` catches only on SQL Server. On PostgreSQL it uses `insertOrIgnore()`.
  - `Connection::run()` rethrows inside a transaction.
- **pdo_pgsql's own statements:**
  - **libpq 17 or later.** Statement and cursor cleanup use protocol-level close messages (`PQclosePrepared()`, `PQclosePortal()`). The recorded wire shows `Close` answered by `CloseComplete`, even inside a failed transaction.
  - **libpq 16 or earlier.** The statement destructor sends SQL `DEALLOCATE` through a bare `PQexec()` (`PHP-8.5`, `ext/pdo_pgsql/pgsql_statement.c:169-177`). If the server rejects it, the transaction aborts, and no exception reaches PHP. [GH-21869](https://github.com/php/php-src/issues/21869) reports this with a wire trace against Aurora DSQL, which rejects `DEALLOCATE <name>`. Its fix, PR [#21870](https://github.com/php/php-src/pull/21870), is open.
  - **PgBouncer, by its documentation** for `max_prepared_statements`. PgBouncer renames protocol-level prepared statements to `PGBOUNCER_<id>` on the server, and forwards SQL-level `DEALLOCATE` "straight to Postgres". So a libpq 16 build behind such a pooler would send `DEALLOCATE` for a name the server does not have, and abort the transaction.
    - **Seen by a third party.** In [php-src GH-12940](https://github.com/php/php-src/issues/12940), a user running PgBouncer in transaction mode with PHP 8.4 posted the server log: `prepared statement "pdo_stmt_00000001" does not exist` for `DEALLOCATE pdo_stmt_00000001`, then `current transaction is aborted`. A maintainer suggested that the PHP package had been built against an older libpq.
    - **Not run here.**
    - **When it would be silent.** Only after the transaction's last statement. After an earlier one, the next statement fails with `25P02`, as in that log.
  - **Laravel's pooled PostgreSQL mode** turns on emulated prepares (`Connectors/Concerns/ConfiguresPooledConnections.php:57-114` in 13.38.0). It creates no server-side statements, so it sends no `DEALLOCATE`.
  - **Scrollable cursors.** The destructor's `CLOSE` for a scrollable cursor was another such path. Commit `c1a7ab07ec` (2026-09-06) fixed it on 8.4 and 8.5, and PHP 8.5.12 contains that commit.
- **A deferred constraint** fails at `COMMIT` with an error, which PDO reports. See check 6.

**Strongest counterargument.** The main trigger is application code that catches a database error inside a transaction without a savepoint. Active Record's documentation warns against that pattern (`transactions.rb:106`), and Laravel's own helpers avoid it. The driver-internal trigger needs both a libpq older than 17 and a server or pooler that rejects or renames prepared statements.

**Verdict.**

- **Application-catch trigger:** confirmed reachable in ordinary code.
- **Driver-internal `DEALLOCATE` behind PgBouncer:** plausible. GH-12940 records a third-party observation of the abort, but it was not reproduced here.
- **Laravel-internal trigger:** none found.

### 3. Is the caught-error scenario supported usage in Laravel?

**Contract.** From the 13.x documentation and source:

- **`database.md`:** "If an exception is thrown within the transaction closure, the transaction will automatically be rolled back and the exception is re-thrown. If the closure executes successfully, the transaction will automatically be committed."
- **`queues.md`:** with `after_commit`, "Laravel will wait until the open parent database transactions have been committed before actually dispatching the job." It also says: "If a transaction is rolled back due to an exception that occurs during the transaction, the jobs that were dispatched during that transaction will be discarded."
- **`events.md` and `eloquent.md`:** after-commit events, listeners and observer handlers run after the transaction "has committed" or "is committed".
- **The `afterCommit()` docblock:** "Execute the callback after a transaction commits."

  The guide does not document `DB::afterCommit()` itself. A 2025 pull request to add it to the docs, laravel/docs [#10845](https://github.com/laravel/docs/pull/10845), was closed unmerged. Taylor Otwell's comment: "I think these are mainly helpful for the framework itself." So the documented contracts are those of the queue, event, listener and observer features, which reach the same manager method (source reading).

**Evidence.**

- None of those pages says whether a closure may catch a database exception and continue, or that PostgreSQL will then refuse to commit.
- Laravel has repeatedly fixed its own code where it aborted a PostgreSQL transaction:
  - #33934, fixed by #49025 (merged 2023-11-16): `DatabaseStore::add()`;
  - #48143: `createOrFirst()`, inside a savepoint in 13.38.0;
  - #48968 (merged 2023-11-13): the cache store's `put()`;
  - #36280, fixed by #62114 (merged 2026-10-20): `DatabaseLock::acquire()`.

  No issue, pull request or discussion addresses application code that catches inside the closure (see the duplicate assessment).
- Laravel raises a dedicated `UniqueConstraintViolationException`. Its own helpers catch it inside a savepoint (check 2).
- `Connection::transaction()` treats a `PDO::commit()` that does not throw as a commit, then runs the manager's callbacks (`Concerns/ManagesTransactions.php:52-72`). It cannot read the tag through PDO (check 1).

**Strongest counterargument, each way.**

- **Supported.** The documentation defines success as the closure executing successfully. Its discard promise covers a transaction "rolled back due to an exception that occurs during the transaction", and PostgreSQL rolled this one back because of exactly such an exception.
- **Misuse.** After a statement error, the PostgreSQL transaction is unusable. Laravel's helpers use savepoints for that reason. Code that catches without one relies on database behavior that Laravel never promised to handle.

The documentation supports neither reading. The savepoints in Laravel's helpers do not make other exception-handling patterns unsupported.

**Verdict: unresolved.** No independently actionable Laravel defect has been established for the false-success path. Laravel's behavior follows from what the driver reported, and its documentation does not settle whether the closure may catch. That does not show Laravel bears no responsibility under its after-commit guarantees; that judgment belongs to its maintainers. The separate callback-retention defect is confirmed and already reported (check 6), and it interacts with this path (check 9).

### 4. Standalone reproductions

- **[`repro/pdo-commit-rollback.php`](repro/pdo-commit-rollback.php)** needs pdo_pgsql only. Its output was identical in three runs ([`repro/output/`](repro/output/)):
  - healthy: `commit()` returned `true`, and the row was visible;
  - aborted: `23505` caught, `commit()` returned `true`, and the row was not visible.
- **[`repro/laravel-aftercommit/`](repro/laravel-aftercommit/)** needs `illuminate/database` 13.38.0 and the 24 packages it pulls in (`composer.lock`). Its output was identical in three runs:
  - healthy: `afterCommit` ran, and the row was visible;
  - aborted: `23505` caught, `afterCommit` ran, `DB::transaction()` returned, and the row was not visible.

Both connect directly, without the recorder, and neither adds a statement to the transaction under test. Connection settings come from libpq's `PG*` environment variables.

**Verdict:** both reproduce.

### 5. Is it already reported?

See [Duplicate assessment](#duplicate-assessment).

### 6. A deferred foreign key violated at COMMIT

**Invariant.** When `COMMIT` fails with an error, PDO reports the failure. Laravel neither runs that transaction's `afterCommit` callbacks nor keeps them for a later transaction.

**Evidence.** Run [`2026-10-25T06-05-06Z-ac32a1`](laravel/output/2026-10-25T06-05-06Z-ac32a1/summary.md); every repetition of the three agreed.

- **`pdo.deferred-fk`.** `COMMIT` was sent in a healthy transaction (status `T`) and answered by error `23503`. `commit()` raised `PDOException` `23503`, and `inTransaction()` was `false` afterwards. The transaction aborted, and the marker was absent.
- **`laravel.deferred-fk`.**
  - `DB::transaction()` raised the driver's `PDOException` `23503`, not a `QueryException`.
  - No callback ran, but the manager kept one pending record.
  - The next transaction on the connection committed. Then both its own `afterCommit` and the failed transaction's `afterCommit` ran.
  - In repetition 1, the server log shows xid 853's `COMMIT` failing at 06:05:08.706. Xid 854's `COMMIT` follows at .715, and the sink inserts the failed transaction's `afterCommit` row at .716.
- **`laravel.explicit-deferred-fk`.** `DB::commit()` raised. The catch block's `DB::rollBack()` took the level from 1 to 0 and ran `afterRollBack`. The manager was then empty, and the next transaction ran only its own callback.

**How it differs from the confirmed case.**

| | Aborted before COMMIT | Deferred FK at COMMIT |
| --- | --- | --- |
| Status before `COMMIT` | `E` | `T` |
| Server's reply | `CommandComplete ROLLBACK` | `ErrorResponse 23503` |
| `PDO::commit()` | returns `true` | raises |
| Laravel `afterCommit` through `DB::transaction()` | runs at once | runs at the next commit on the connection |
| Owner | pdo_pgsql | Laravel's `handleCommitTransactionException()`, [laravel/framework#61964](https://github.com/laravel/framework/issues/61964) |

`handleCommitTransactionException()` takes the same path whatever the exception. So a driver that raised for the `ROLLBACK` tag should make the caught-error case end like `laravel.deferred-fk`. Check 9 tests that.

**Strongest counterargument.** The leak needs a later transaction on the same connection in the same process: a queue worker, an Octane server, a long-running command, or a second transaction in the same request. And #61964 already reports it.

**Verdict.**

- **PDO:** expected behavior.
- **Laravel:** confirmed defect, already reported as #61964, here reproduced on PostgreSQL 18.6. Not a new finding.

### 7. Do the native pgsql functions report the tag?

**Evidence.** From [`pgsql-extension/commit-tag.php`](pgsql-extension/commit-tag.php), three identical runs in [`pgsql-extension/output/`](pgsql-extension/output/):

- **Transaction status.** `pg_transaction_status()` was `INERROR` before the aborted transaction's `COMMIT`, and `INTRANS` before the healthy one's.
- **Tag.** `pg_result_status($result, PGSQL_STATUS_STRING)` returned `ROLLBACK` and `COMMIT` respectively, while both results were `PGSQL_COMMAND_OK`.
- **`pg_query()`.** `pg_query('COMMIT')` on the aborted transaction returned a `PgSql\Result`, not `false`.

**Strongest counterargument.** An application that ends a transaction with `pg_query('COMMIT')` and checks only for `false` is misled the same way.

**Verdict: expected behavior.** The extension is a thin libpq binding with no commit method of its own, and it passes the tag through. So the information does reach PHP from libpq, and it is PDO's `commit()` that discards it.

### 8. Could the instrumentation explain the result?

**Evidence.**

- **`laravel/check-run.mjs` on run `ac32a1`:** 30 repetitions, 246 checks, none failed. In every repetition:
  - the subject's `pg_backend_pid()` is the pid in the recorder's `BackendKeyData`;
  - the observer's `pg_stat_activity` rows for that pid carry the subject's `application_name`;
  - the observer and the sink are two other backends;
  - each captured transaction ID appears as `%x` on that backend's later log lines, including its ending `COMMIT` or `ROLLBACK`;
  - every visible marker's `xmin` equals the transaction ID captured inside its transaction;
  - the PHP process's callbacks are exactly the rows in `callback_log`;
  - no callback ran before its transaction ended, apart from the savepoint's inner `afterRollBack`.

  The two earlier runs pass every check whose fields they recorded.
- **The minimal reproductions** show the same outcomes without the recorder, without `pg_current_xact_id()` or `pg_backend_pid()` in the session, and without reads during the transaction.
- **`tools/recorder-check.mjs`** matches the recorder's tags to node-postgres's own `Result.command`.

**Strongest counterargument.**

- Laravel is wired by hand: Capsule plus the `db.transactions` binding, not a booted application.
- The recorder is this study's own code.
- `pg_stat_activity.backend_xid` is empty after the abort, so the transaction ID comes from inside the transaction.

**Verdict: the instrumentation does not explain the result.** The Capsule wiring is the one remaining difference from an application. Source reading of `DatabaseServiceProvider` and `DatabaseManager::configure()` in 13.38.0 shows the same manager wiring.

### 9. What changes if pdo_pgsql reports the failure?

**Invariant.** Once the driver reports a `COMMIT` answered with `ROLLBACK` as a failure, no `afterCommit` callback of that transaction runs, then or later.

**Evidence** ([`patched-driver/`](patched-driver/README.md)):

- **Setup.** PHP 8.5.12 was built from the php.net tarball, with pdo_pgsql built twice from it as a shared module: unchanged, and with a 15-line patch to `pgsql_handle_commit()`. The patch reports the tag `ROLLBACK` as an error, using pdo_pgsql's convention for failures without a server SQLSTATE (`HY000`, code 7). The unchanged scenario matrix then ran under each build, three repetitions per scenario.
- **The control.** With the stock build, every row equals the Homebrew run `ac32a1`.
- **The patched build.** Exactly the three scenarios that reach the tag changed:
  - `pdo.caught-error`: `commit()` raised `HY000`.
  - `laravel.caught-error`: `DB::transaction()` raised, and no callback ran. The manager kept one pending record. The next transaction committed, and then the aborted transaction's `afterCommit` ran. In the server log, xid 962's `COMMIT` comes at .154 and xid 963's at .165. The sink inserted xid 962's `afterCommit` row at .166, and xid 962 stayed `aborted`.
  - `laravel.explicit-caught-error`: `DB::commit()` raised, no callback ran, and a pending record remained.
- **No regression in the other scenarios.** Healthy commits, the escaped exception, savepoint recovery and both deferred-FK paths are unchanged. `check-run.mjs` passed all 246 checks on both runs.

**Strongest counterargument.**

- The leak needs another commit on the same connection in the same process. A process that ends after the failed transaction drops the record unrun.
- The patch is this study's, not php-src's. A different fix, such as rolling back inside `commit()` or raising another SQLSTATE, might reach Laravel differently. But Laravel's rethrow path is the same for `HY000`, `25P02` and `40000` (source reading of its detectors). Only `40001` would differ: Laravel retries the closure for it.

**Verdict: confirmed.** In a long-running process, a correct driver fix alone moves the wrong side effect to the next commit on the connection, instead of removing it. That holds until laravel/framework#61964 is fixed. These are two distinct defects, in different projects, and each one alone produces an `afterCommit` for a transaction PostgreSQL rolled back.

## Correcting the driver: design questions

These are the questions a php-src fix has to answer. The experiment's patch is one possible answer, not a recommendation.

- **Which SQLSTATE, when PostgreSQL sends none?**
  - **`HY000`.** pdo_pgsql already reports failures without a server SQLSTATE this way. `_pdo_pgsql_error()` writes `HY000` when given none, and about 15 call sites pass `PGRES_FATAL_ERROR, NULL`.
  - **`25P02`** (`in_failed_sql_transaction`) names the state the transaction was in. MikroORM's fix (#8499, merged 2026-10-22) uses it, with the message "current transaction is aborted, COMMIT was answered with ROLLBACK".
  - **`40000`** (class 40, transaction rollback) names the outcome.
  - **Elsewhere.** pgx returns a dedicated error with no SQLSTATE, `ErrTxCommitRollback` ("commit unexpectedly resulted in rollback"). A pgjdbc maintainer agreed that `commit()` should report it ("There is no error in the actual commit command hence no error message", pgjdbc#4494) but chose no code.
  - **Not `40001`** (`serialization_failure`). Frameworks retry it. Laravel's `DB::transaction($callback, attempts: n)` would run the closure again.

  This review does not choose. The issue should leave the choice to the maintainers.
- **Is there a PDO convention for a command that completes at the protocol level but failed?** None found. Every failure path in pdo_pgsql starts from a libpq result other than `PGRES_COMMAND_OK`, or from a client-side error. The nearest case is a `COMMIT` that fails with an error, such as a deferred constraint (bug #67462). The patch reuses that path: report, return `false`, and recompute `in_txn` from the server's status.
- **Is the transaction state right after the failure?** At runtime, yes ([`patched-driver/state-after-failure.php`](patched-driver/state-after-failure.php)). After the patched failure, PDO is in exactly the state a deferred-constraint failure leaves it in: `inTransaction()` is `false`, `rollBack()` raises "There is no active transaction", and the next transaction commits.
- **Does it change nested-transaction abstractions?**
  - PDO has no nesting.
  - Laravel calls `PDO::commit()` only at the outermost level (`Concerns/ManagesTransactions.php:52-54` and `:205-207`), and ends inner levels with savepoint statements through `exec()`. Those are not affected.
  - Savepoint recovery still returns `true` under the patch, in both the matrix and the script.
  - A `COMMIT` that an application sends itself through `exec()` is not affected.
  - Other abstractions, such as Doctrine DBAL, were not checked.
- **Behavior change.**
  - Code that today commits after a caught statement error would get an exception. If its catch block then calls `rollBack()`, that raises "There is no active transaction", as it already does after a deferred-constraint failure at `COMMIT`.
  - The message should not resemble a connection-loss message. Frameworks classify errors by message text; Laravel's `LostConnectionDetector` matches about 30 phrases.
- **Large-object streams.** `pdo_pgsql_close_lob_streams()` runs only after a successful `COMMIT`, today and with the patch. The transaction is over either way, so whether to close them after a failure as well is a question for the maintainers.

## Upstream ownership

- **php-src, `ext/pdo_pgsql`, owns the false success.** The correction suggested for the maintainers' judgment:
  - **The change.** `pgsql_handle_commit()` keeps the `COMMIT` result and treats the command tag `ROLLBACK` as a failure. It records an error and returns `false`, so PDO raises in exception mode.
  - **Transaction state.** `dbh->in_txn` is already recomputed from the server's status on the failure path. Check 9's state script confirms the resulting state matches a deferred-constraint failure.
  - **A regression test,** as a phpt: begin, then a caught statement error; `commit()` must fail, `inTransaction()` must be `false`, and the row must be absent. Its controls are a healthy commit and a savepoint recovery, which must still return `true`.
  - **An error code.** See the design questions above. The issue should not prescribe one.
- **Laravel: no new issue for the false-success path.** Check 9 makes #61964 matter more than before: once the driver raises, #61964 is what makes the aborted transaction's `afterCommit` run anyway. The patched-driver evidence and the PostgreSQL deferred-FK reproduction are what would be worth adding to that issue.
- **PostgreSQL: nothing to change.** It reports the outcome.

## Duplicate assessment

The search scope, the queries and their limits are in [`duplicate-search/`](duplicate-search/README.md). It covered php-src issues and pull requests, the historical bugs.php.net tracker, laravel/framework issues, pull requests and discussions, and laravel/docs.

**php-src: is the commit check already reported? No.** No report asks for `pgsql_handle_commit()` to check the command tag, or names `PQcmdStatus` in connection with a commit. Related items:

| Item | State | Relation |
| --- | --- | --- |
| [GH-21869](https://github.com/php/php-src/issues/21869) | open | **Same symptom, different cause and fix.** The `COMMIT` is "silently returned as ROLLBACK", with `errorInfo()` `00000`, after pdo_pgsql's own `DEALLOCATE` fails. Its reproduction ends with `$pdo->exec("COMMIT")`. Its fix, PR #21870, changes when `DEALLOCATE` runs, and leaves the commit check alone. The maintainer said surfacing destructor failures "might be worth doing, but as a separate PR". |
| [GH-12940](https://github.com/php/php-src/issues/12940) | closed 2024 | PgBouncer and `DEALLOCATE`. A comment shows the abort in a server log (check 2). |
| PR [#23490](https://github.com/php/php-src/pull/23490), commit `c1a7ab07ec` | closed 2026-09-06 | The scrollable-cursor `CLOSE` in the destructor. Fixed. |
| bugs.php.net [#37870](https://bugs.php.net/bug.php?id=37870) | closed 2006 | A `DEALLOCATE` of a statement that was never prepared aborted the transaction. A 2018 comment: PDO "does not capture either the deallocation error nor the transaction commit error so it causes a silent fail". Never taken up as a request to check the commit. |
| bugs.php.net [#36681](https://bugs.php.net/bug.php?id=36681), [#67462](https://bugs.php.net/bug.php?id=67462) | closed 2006, 2014 | #36681 made a `COMMIT` that returns an error raise. #67462 recomputes `in_txn` after one. Both concern a `COMMIT` that errors, not one that succeeds with `ROLLBACK`. |
| php-src [#8698](https://github.com/php/php-src/issues/8698); bugs.php.net #66528, #66529 | closed | Adjacent, on MySQL: `commit()` looked successful after a server-side rollback or a lost connection. |

**Laravel: are after-commit callbacks after a `COMMIT` answered with `ROLLBACK` already reported? No.** No issue, pull request or discussion reports it. Related items:

- **#61964** (open): a `COMMIT` that raises leaves the manager stale (check 6). A different path.
- **Fixes to Laravel's own code**, where it aborted a PostgreSQL transaction (check 3): #33934 and #49025, #48143, #48968, #36280 and #62114.
- **Callback bookkeeping**, nested or on rollback: #48859, #48853, #55420, #47765, #47761, #45488. All are closed. By their titles, which are all that was read, each concerns Laravel's own bookkeeping, not a rollback by the database.
- **#51917** (closed): a `25P02` in an after-commit listener. A maintainer closed it, pointing the reporter to the support channels, with no diagnosis.
- **#38172** (closed): on PostgreSQL the original error is hidden behind the `25P02` errors that follow it. A maintainer replied "We'd definitely welcome PR's for this." Nothing about `COMMIT`.

**Assessment.**

- **php-src.** An issue about `pgsql_handle_commit()` would not duplicate an existing report. It should link GH-21869 for the same symptom with a different cause, and it may cite #37870's 2018 comment.
- **Laravel.** A Laravel issue would not duplicate one either, but check 3 does not support filing one.

## Recommendations

- **Option B, a real Laravel application: NO-GO for now.**
  - php-src owns the defect, and its issue needs only the PDO reproduction.
  - Laravel's queue and event paths reach the same `addCallback()` (source reading).
  - No Laravel-facing report is planned.

  Revisit if a comment on #61964 or a Laravel documentation change is planned, and needs the end-to-end consequence shown. In that case, demonstrate a documented feature, such as a queued job with `after_commit`, not `DB::afterCommit()`, which the maintainer called mainly for the framework.
- **A php-src issue: drafted, not filed.** It is in [`upstream-drafts/php-src-pdo-pgsql-commit-rollback.md`](upstream-drafts/php-src-pdo-pgsql-commit-rollback.md). Before anything is posted:
  - the exact text is approved;
  - the duplicate search is repeated on the day;
  - the issue is new and links GH-21869, rather than a comment there, because it proposes a different fix in a different function;
  - any LLM-written paragraphs are disclosed as markdown quotes, as php-src's `CONTRIBUTING.md` asks ("LLM usage in GitHub comments").
- **A php-src pull request: not yet.** The maintainers should first choose the error code, and accept the behavior change.
- **laravel/framework#61964: optional, after the php-src issue.** The patched-driver result is new evidence for that issue. A comment there would be written in the user's own words, given the project's stance on AI-generated contributions, and could link the php-src issue.

## Not done

- **No PgBouncer run.** The application-catch trigger is enough for the driver issue, and the PgBouncer path stays labeled plausible.
- **No Laravel application** (Option B).
- **No other error raised at `COMMIT`.** A serialization failure, `40001`, under `SERIALIZABLE` would take the deferred-FK path, and Laravel would retry it when `attempts` is more than 1.
- **No other abstraction's handling of a `commit()` that raises,** such as Doctrine DBAL or Symfony.
