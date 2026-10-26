# Findings

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max). Labels (**Observed**, **Source**, **Manual**) as in [methodology.md](methodology.md).

Primary run: [`output/2026-10-25T17-03-57Z-e28e5b`](output/2026-10-25T17-03-57Z-e28e5b/matrix.md), 63 runs, 3 per group, all matching the stated expectations. The 16 groups it shares with the first run, [`output/2026-10-25T16-15-42Z-5bd1e8`](output/2026-10-25T16-15-42Z-5bd1e8/matrix.md), have identical matrix rows.

## 1. Summary

**F1 (observed in every repetition; classification A by this study's criteria, see §3.6).** On MySQL 8.4.11 with the default `innodb_rollback_on_timeout=OFF`, Laravel 13.38.0:

- does not roll a nested `DB::transaction()` back to its savepoint when its statement fails with errno 1205 (lock wait timeout);
- throws `Illuminate\Database\DeadlockException`, runs the inner `afterRollBack` callbacks, drops the inner `afterCommit` callbacks, and lowers its nesting level without sending `ROLLBACK TO SAVEPOINT`.

The server has rolled back only the timed-out statement, so the transaction and the savepoint are still open. When the code around the inner call catches the exception and the outer transaction commits, the inner unit's earlier writes commit with it. `DB::transaction()` returns normally.

The same code with a duplicate key as the inner failure is rolled back to the savepoint. The documented explicit API (`DB::beginTransaction()` / `DB::rollBack()`) also rolls the 1205 case back to the savepoint.

**Mechanism.** The nested shortcut in `handleTransactionException()` was added in 2016 (laravel/framework#15932) for deadlocks, on the stated premise that the server has already rolled back the whole transaction. In 2017 #19749 added "Lock wait timeout exceeded" to the same predicate, for top-level retries. That routed 1205 into the shortcut, although by default MySQL rolls back only the statement after a lock wait timeout.

**Related observations, with `innodb_rollback_on_timeout=ON`:**

- **O1, the explicit nested API.** It reaches the failure laravel/framework#61829 reports for SQL Server: the 1205 is replaced by a 1305 error and the nesting level stays at 2. Every later `DB::transaction()` on that connection then commits nothing as a unit and runs no callback.
- **O2, the managed form.** It ends in a loud outer failure, but the outer `afterCommit` runs at the next commit for a transaction InnoDB rolled back (the #61964 mechanism).
- **O3, a single-level `DB::transaction()` that catches the 1205 and returns.** It returns normally and runs `afterCommit`, although InnoDB rolled the transaction back. `PDO::commit()` returned true for a transaction that no longer existed.

**Recommendation.** F1 warrants an upstream Laravel issue, written by a person (§8). Nothing has been filed or posted.

## 2. Result matrix

From [`matrix.md`](output/2026-10-25T17-03-57Z-e28e5b/matrix.md) of the primary run.

- **Framework.** The PDO rows use no framework (PHP 8.5.12, `pdo_mysql`, mysqlnd 8.5.12). The `laravel.*` rows use `illuminate/database` v13.38.0 on that same PHP and driver.
- **Server column.** OFF is `innodb_rollback_on_timeout=OFF` and ON is `=ON`.
- **"Outer committed?"** comes from `performance_schema.events_transactions_history_long` for the subject thread.
- **"Inner writes"** comes from a connection opened after the subject exited.
- **Callbacks** come from the independent sink.
- **Evidence.** Each row's runs are the entries with that `scenario` and `server` in `runs.json`.

| Scenario | Server | Trigger | Database outcome | Outer call (what the framework reported) | Write after the failure | Callbacks | Laravel level: after failure / after outer call / at end | Reps | Class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `pdo.savepoint-1205.rollback-to` | OFF | 1205 | Statement rolled back; transaction and savepoint kept; `ROLLBACK TO` ok; inner rolled back; outer committed | `commit()` true | Inside the transaction | — | — | 3/3 | Control |
| `pdo.savepoint-1205.rollback-to` | ON | 1205 | Whole transaction rolled back; `ROLLBACK TO` errno 1305 | `commit()` threw "There is no active transaction" | Autocommitted | — | — | 3/3 | Control |
| `pdo.savepoint-1205.skip` | OFF | 1205 | Savepoint kept, never rolled back; **inner committed** | `commit()` true | Inside the transaction | — | — | 3/3 | Control: the server's consequence of skipping `ROLLBACK TO` |
| `pdo.savepoint-1205.skip` | ON | 1205 | Whole transaction rolled back | `commit()` threw | Autocommitted | — | — | 3/3 | Control |
| `pdo.savepoint-1213` | OFF | 1213 | Whole transaction rolled back; `ROLLBACK TO` errno 1305 | `commit()` threw | Autocommitted | — | — | 3/3 | Control |
| `pdo.caught-1205.commit` | OFF | 1205 | Transaction kept; marker committed | `commit()` true | none | — | — | 3/3 | Control |
| `pdo.caught-1205.commit` | ON | 1205 | Whole transaction rolled back; `COMMIT` acknowledged with no transaction | `commit()` **true** | none | — | — | 3/3 | B (O3, driver half) |
| `laravel.commit` | OFF | — | Committed | returned | — | `afterCommit` | — / 0 / 0 | 3/3 | Control |
| **`laravel.nested-1205-caught`** | **OFF** | **1205** | **No `ROLLBACK TO`; inner committed with the outer** | **returned** | Inside the transaction | **`afterRollBack:inner`** before the commit, then `afterCommit:outer`; no `afterCommit:inner` | 1 / 0 / 0 | 3/3 | **A (F1)** |
| `laravel.nested-1205-caught` | ON | 1205 | Whole transaction rolled back | threw `PDOException` (PDO did not send `COMMIT`) | Autocommitted | `afterRollBack:inner`; `afterCommit:outer` at the **next** transaction's commit | 1 / 0 / 0 | 3/3 | B (O2, #61964) |
| `laravel.nested-1205-caught.server-timeout` | OFF | 1205 after 50 s | Same as the OFF row of the candidate: inner committed | returned | Inside the transaction | Same as the OFF row of the candidate | 1 / 0 / 0 | 3/3 | A (F1) |
| `laravel.nested-1205-caught.outer-rollback` | OFF | 1205 | Outer rolled back explicitly; nothing committed | `DB::rollBack()` returned | — | `afterRollBack:inner`, `afterRollBack:outer` | 1 / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-1205-caught.outer-rollback` | ON | 1205 | Whole transaction rolled back | `DB::rollBack()` returned | — | `afterRollBack:inner`, `afterRollBack:outer` | 1 / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-1205-escapes` | OFF | 1205 | `ROLLBACK` sent; nothing committed | threw `DeadlockException` | — | `afterRollBack:inner`, `afterRollBack:outer` | — / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-1205-escapes` | ON | 1205 | Whole transaction rolled back; `ROLLBACK` sent | threw `DeadlockException` | — | `afterRollBack:inner`, `afterRollBack:outer` | — / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-explicit-1205` | OFF | 1205 | `ROLLBACK TO` ok; inner rolled back; outer committed | returned | Inside the transaction | `afterRollBack:inner`, `afterCommit:outer` | 1 / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-explicit-1205` | ON | 1205 | Whole transaction rolled back; `ROLLBACK TO` errno 1305, twice | threw `PDOException` 1305; the 1205 is not in its cause chain | The next transaction's insert autocommitted; no `COMMIT` sent | **none at all** | — / **2** / **2** | 3/3 | B (O1, #61829) |
| `laravel.nested-duplicate-caught` | OFF | 1062 | `ROLLBACK TO` ok; inner rolled back; outer committed | returned | Inside the transaction | `afterRollBack:inner`, `afterCommit:outer` | 1 / 0 / 0 | 3/3 | Control (holds) |
| `laravel.nested-1213-caught` | OFF | 1213 | Whole transaction rolled back (Laravel's premise holds) | threw `PDOException` | Autocommitted | `afterRollBack:inner`; `afterCommit:outer` at the next commit | 1 / 0 / 0 | 3/3 | B (#61964) |
| `laravel.caught-1205-return` | OFF | 1205 | Statement rolled back; `tx` committed | returned | none | `afterCommit:tx` | 1 / 0 / 0 | 3/3 | Control (holds) |
| `laravel.caught-1205-return` | ON | 1205 | Whole transaction rolled back; `COMMIT` acknowledged with no transaction | **returned** | none | **`afterCommit:tx`** | 1 / 0 / 0 | 3/3 | B (O3) |

## 3. F1: a nested `DB::transaction()` failing with 1205 is not rolled back to its savepoint

### 3.1 What was observed

**Observed**, `laravel.nested-1205-caught`, OFF, primary run, repetitions 1–3 identical.

1. The outer `DB::transaction()` inserted `outer`.
2. The inner `DB::transaction()`, a savepoint, inserted `inner`. Its next statement waited on the held row. The observer saw that wait in `performance_schema.data_lock_waits`. After 2 s the statement failed with `SQLSTATE[HY000]: General error: 1205 Lock wait timeout exceeded; try restarting transaction`.
3. The inner call threw `Illuminate\Database\DeadlockException`. Its cause chain was `QueryException` (1205), then `PDOException` (1205).
4. At the `after-error` checkpoint, immediately after that throw:
   - **Server:** the subject's transaction was `ACTIVE`, with `NUMBER_OF_SAVEPOINTS` 1 and `NUMBER_OF_ROLLBACK_TO_SAVEPOINT` 0. Its IX locks on `marker` and `lk` were still held, and no marker was visible to another connection.
   - **Laravel:** `transactionLevel()` was already 1, and the manager had one pending record, level 1.
   - **Sink:** it already held `afterRollBack:inner`.
5. The outer closure caught the exception, inserted `after` inside the still-open transaction, and returned.
6. The subject thread's statements, in order, were:
   - `START TRANSACTION`, an `Execute` (outer);
   - `SAVEPOINT trans2`, an `Execute` (inner), an `Execute` with errno 1205;
   - an `Execute` (after), `COMMIT`.

   There is no `ROLLBACK TO SAVEPOINT` anywhere. The server recorded one transaction, `COMMITTED`, with `NUMBER_OF_SAVEPOINTS` 1 and `NUMBER_OF_ROLLBACK_TO_SAVEPOINT` 0.
7. A connection opened after the subject exited saw `outer`, `inner`, `after` and `next`.
8. The sink held `afterRollBack:inner`, then `afterCommit:outer`, then `afterCommit:next`. No `afterCommit:inner` row exists.

Your six dimensions for this case:

1. The inner writes were not rolled back.
2. They persisted.
3. The inner `afterRollBack` ran, before the outer commit.
4. The inner `afterCommit` did not run.
5. The outer transaction committed, and `DB::transaction()` returned normally.
6. Laravel's level went 2 to 1 at the throw, then 0 after the commit. The manager kept no stale record.

The server-default variant ran the same steps with a 50 s wait (50128–50320 ms) and recorded the same outcome in all three repetitions. The minimal reproduction in [`upstream/laravel-nested-1205/`](upstream/laravel-nested-1205/README.md) shows the same thing without any of this study's instrumentation. On the OFF server, three runs produced byte-identical output.

### 3.2 Source-level mechanism

**Source**, `illuminate/database` v13.38.0:

- `ConcurrencyErrorDetector::causedByConcurrencyError()` (`ConcurrencyErrorDetector.php:18–38`) returns true for SQLSTATE 40001, or for any of a list of messages. Line 34 is `'Lock wait timeout exceeded; try restarting transaction'`. MySQL reports 1205 with SQLSTATE HY000, so the message is what matches.
- `ManagesTransactions::handleTransactionException()` (`Concerns/ManagesTransactions.php:88–115`) runs when an exception leaves a `transaction()` closure. Lines 90–102:

  ```php
  // On a deadlock, MySQL rolls back the entire transaction so we can't just
  // retry the query. We have to throw this exception all the way out and
  // let the developer handle it in another way. We will decrement too.
  if ($this->causedByConcurrencyError($e) &&
      $this->transactions > 1) {
      $this->transactions--;

      $this->transactionsManager?->rollback(
          $this->getName(), $this->transactions
      );

      throw new DeadlockException($e->getMessage(), is_int($e->getCode()) ? $e->getCode() : 0, $e);
  }
  ```

  This branch never calls `rollBack()`, so `performRollBack()` (lines 300–313), which would send `ROLLBACK TO SAVEPOINT trans2`, is not reached. Every other exception at a nested level goes through `$this->rollBack()` (line 107), which sends it. That is why the duplicate-key control is contained.
- `DatabaseTransactionsManager::rollback()` (`DatabaseTransactionsManager.php:128–151`), called with level 1:
  - drops the pending level-2 record, and with it the inner `afterCommit` callbacks (lines 133–136);
  - runs that record's `afterRollBack` callbacks (line 142).

  The manager is told the inner unit rolled back, and the database is not.
- `DeadlockException` extends `PDOException`, not `QueryException` (`DeadlockException.php:7`). A `catch (QueryException $e)` around the inner call does not catch it. A `catch (PDOException|Exception|Throwable)` does.

Where the two states diverge: at line 95, Laravel's level drops to 1, while the server is still at the savepoint inside the open transaction. Nothing later re-synchronizes them, so the outer `COMMIT` commits the inner writes.

**Manual** (MySQL 8.4, InnoDB Error Handling):

- "A transaction deadlock causes InnoDB to roll back the entire transaction."
- "A lock wait timeout causes InnoDB to roll back the current statement (the statement that was waiting for the lock and encountered the timeout). To have the entire transaction roll back, start the server with --innodb-rollback-on-timeout enabled."

The raw controls match the manual. With OFF, the savepoint survives the 1205 and `ROLLBACK TO SAVEPOINT` succeeds. Skipping it commits the inner row. With ON, the savepoint is gone, and `ROLLBACK TO SAVEPOINT` fails with `ERROR 1305 (42000)`.

### 3.3 History: the shortcut is for whole-transaction rollbacks

- **laravel/framework#15932** (merged 2016-10-26, "[5.3] dont rollback to savepoints on deadlock") added the branch. Its description: "Deadlock in the inner transaction() function means the DBMS has rolled back the outer transaction as well." It quotes the MySQL manual on deadlocks. The comment it added: "the outer most transaction is rolled back by the server so we shouldn't rollback to save points." At that time the predicate, `causedByDeadlock()`, matched deadlock messages only.
- **#16140** (2016-10-27, by the same author, closed 2016-10-31) noted: "MySQL may or may not rollback the entire transaction on lock wait timeout, which is different from deadlock. The default configurations says not to rollback the entire transaction on lock wait timeout."
- **#19749** (merged 2017-06-25, "[5.4] detect lock wait timeout as deadlock") added `'Lock wait timeout exceeded; try restarting transaction'` to `causedByDeadlock()`. It was a one-line change with no review discussion. Its stated reason was servers that disable deadlock detection and rely on the lock wait timeout. That reason concerns retrying the transaction at the top level. The change also routed 1205 into the nested shortcut.
- Later changes:
  - the predicate was renamed `causedByConcurrencyError()` (2019) and moved to `ConcurrencyErrorDetector` (#56493, 2025);
  - the branch had already started notifying the transactions manager before 2022, and #42129 (2022) replaced its `throw $e` with `throw new DeadlockException(...)`.

  None of these changed the 1205 classification or the branch's premise. **Source:** v12.70.1 and v11.57.0 contain the same branch and the same message. Only v13.38.0 was run.

**Answer to the refinement's question:** yes, the special handling is intentionally restricted to cases where the database has rolled back the entire transaction. Its author said so, quoted the manual for it, and the code comment says so. Classifying MySQL 1205 as a concurrency error is right for the top-level retry: there Laravel sends a full `ROLLBACK` before retrying, whatever the server did. It is wrong for the nested shortcut on a server with the default `innodb_rollback_on_timeout=OFF`.

This study's reading, an interpretation: the underlying defect is not the 1205 classification on its own. It is that one predicate decides two questions with different premises:

1. Should the whole transaction be retried?
2. Has the server already rolled back the whole transaction, so that the savepoint is gone?

### 3.4 What Laravel documents or reasonably guarantees

- **Documented.** The Laravel 13.x database guide (`database.md`, docs commit `9d2857adec`, 2026-10-20) says of `DB::transaction()`: "If an exception is thrown within the transaction closure, the transaction will automatically be rolled back and the exception is re-thrown." Its deadlock section covers only the `attempts` argument. It does not mention nested transactions, savepoints, `DeadlockException`, `afterRollBack` or `DB::afterCommit`. The guide therefore does not state nested semantics. It also gives no exception to the rollback sentence for a call that happens to be nested.
- **Reasonably guaranteed by the implementation:**
  - nested calls are savepoints (`createSavepoint()`);
  - every exception other than a concurrency error is rolled back to the savepoint before being rethrown (§3.2; control `laravel.nested-duplicate-caught`);
  - the explicit API's `rollBack()` to a nested level sends `ROLLBACK TO SAVEPOINT` (control `laravel.nested-explicit-1205`).
- **Relied on by Laravel itself.** `Eloquent\Builder::createOrFirst()` (`Eloquent/Builder.php:771–778`) runs its insert through `withSavepointIfNeeded()` (`2048–2053`). That method wraps the insert in a nested `DB::transaction()` when a transaction is open, and `createOrFirst()` catches `UniqueConstraintViolationException` outside it and continues the outer transaction. PR #48144 (merged 2023-08-23) added this as a "save point transaction". The pattern in F1 (a nested call whose exception the outer code catches) is therefore one the framework uses itself.
- **Signalled by Laravel in the failing case.** Laravel ran the inner `afterRollBack` callbacks, so the framework itself reported the inner unit as rolled back.
- **Tested upstream.** At v13.38.0, `tests/Database/DatabaseConnectionTest.php`, `tests/Database/DatabaseTransactionsTest.php` and `tests/Integration/Database/DatabaseTransactionsTest.php` contain no test of the nested concurrency branch. A GitHub code search of the default branch's `tests/` found no use of `DeadlockException`, and no transaction test mentioning a lock wait timeout. `testTransactionMethodRetriesOnDeadlock` is top-level, with a mocked PDO. `testNestedTransactionsAreRolledBack` lets the exception escape both levels and checks only the manager calls. The `createOrFirst` tests mock `transactionLevel()` as 0.

### 3.5 Adversarial review

| Challenge | Answer from the evidence |
| --- | --- |
| Did the database roll back the inner work? | No. The server kept the transaction `ACTIVE` with one savepoint, received no `ROLLBACK TO SAVEPOINT`, and committed one transaction containing `inner` |
| Did a later write autocommit? | No, not with OFF. `after` was not visible to another connection before the outer `COMMIT`, and the server recorded a single transaction |
| Did the framework start a new transaction? | No: one `START TRANSACTION`, one `COMMIT`, one recorded transaction |
| Is it documented? | No. Nesting is undocumented, and the general sentence promises rollback (§3.4) |
| Did the application misuse the API? | It caught an exception from a nested `DB::transaction()` and continued. Nothing in the documentation prohibits that, and Laravel's `createOrFirst()` does the same. Laravel contains the same code shape for a duplicate key (control) |
| Is it only internal bookkeeping? | No. The persisted rows and the sink rows are external effects |
| Could pooling or instrumentation explain it? | There is no pool: one PDO connection and one server thread throughout. The observer only reads, from other connections. The standalone reproduction has no instrumentation and gives the same rows |
| Does it depend on timing? | No. The lock is held deterministically, and the server's own 50 s timeout gives the same result as the 2 s session setting |
| Three repetitions? | 3 of 3 in each of two runs, and 3 of 3 byte-identical outputs of the standalone reproduction |
| Raw driver control? | `pdo.savepoint-1205.skip`, OFF: skipping `ROLLBACK TO SAVEPOINT` commits the inner row. `pdo.savepoint-1205.rollback-to`, OFF: sending it removes the row |
| Could a correct framework do this? | Only one that defined a nested unit's 1205 as "left to the outer transaction". Laravel defines no such thing. Its own `afterRollBack` signal and its explicit API say the opposite |

**Strongest counter-argument: intentional, but undocumented.**

- `DeadlockException` and the comment "We have to throw this exception all the way out" suggest Laravel intends the exception to reach the outermost level, where the full rollback or retry happens. Catching it in between would then be outside the design.
- For a real deadlock that is coherent, because the transaction is already gone. A caller who continues gets autocommitted writes and a loud failure at the outer commit (`laravel.nested-1213-caught`).

Three things weigh against it:

- **Applied to 1205 with OFF, the same intent produces a silent outcome.** The outer commit succeeds, and nothing reports that the inner unit's writes committed.
- **The 1205 routing was not a decision.** It came from a one-line change made for a different purpose (#19749). The shortcut's author had noted the difference a day after adding it (#16140).
- **The intent is not discoverable.** `DeadlockException` is undocumented, a generic `catch (Throwable)` catches it, and the inner `afterRollBack` callbacks tell listeners the opposite of what the database did.

This study does not find the behavior intentional. The judgment belongs to the maintainers.

### 3.6 Classification and production reachability

**Classification: A** under the definitions this study was given: "a documented or reasonably supported workflow produces an externally observable correctness violation."

- **Supported workflow:** a nested `DB::transaction()` whose exception the surrounding code catches (§3.4).
- **Configuration:** the server default.
- **Violation:** externally observable. The rows committed, the inner `afterRollBack` ran, and the inner `afterCommit` did not.

It is not classified C, because no documentation describes the behavior. It is not D, because nothing is injected and the API is used as written.

The condition is stated in full so that it can be weighed: the surrounding code must catch the exception. If the exception propagates to the outermost `DB::transaction()`, Laravel rolls everything back correctly (`laravel.nested-1205-escapes`).

**Reachability:**

- **Trigger.** Errno 1205 is an ordinary production error under lock contention: a transaction waiting longer than `innodb_lock_wait_timeout` (default 50 s) for a row lock. Laravel's detector has matched it since 2017 because applications meet it.
- **Configuration.** `innodb_rollback_on_timeout=OFF` is the MySQL default.
- **Application pattern.** A nested `DB::transaction()` inside an outer transaction, with the exception caught in between. Examples are per-item savepoints in a batch job, an optional step that "may fail", or a service method with its own `DB::transaction()` called from code that wraps a larger transaction and handles sub-step failures. Code that catches only `QueryException` does not catch `DeadlockException` (§3.2). Laravel's own `createOrFirst()` catches only `UniqueConstraintViolationException`, so it does not reach this path (**source**).
- **Consequence.**
  - The writes the inner unit made before the timed-out statement commit, without the statement that timed out. For example, an order line commits without its inventory decrement.
  - Listeners registered with `afterRollBack` for the inner unit run although its data committed, so compensations run for committed work.
  - The inner unit's `afterCommit` callbacks never run. **Source:** queued jobs, mail and events dispatched with `->afterCommit()` or the `after_commit` queue option register through the same `DatabaseTransactionsManager::addCallback()`, so they would be dropped although the data committed. This study measured `DB::afterCommit` through the sink, not a queue.

### 3.7 Root cause and minimal plausible corrections

The root cause is in Laravel. The driver reports 1205 correctly, and the server behaves as its manual says.

The corrections below are **source reasoning, not implemented or tested**. Each must also hold with `innodb_rollback_on_timeout=ON`, where the savepoint is gone and `ROLLBACK TO SAVEPOINT` fails with 1305 (O1). They must also not rely on `PDO::inTransaction()` immediately after the error. In this study it still returned true after InnoDB had rolled the transaction back, until the next successful statement refreshed it (O3).

1. **Restrict the nested shortcut to errors that end the whole transaction.** For MySQL errno 1205, decide by the server's setting, read once per connection with `SELECT @@innodb_rollback_on_timeout`.
   - When it is OFF, take the ordinary path: `rollBack()` to the savepoint, then rethrow.
   - Otherwise keep the shortcut.

   This is precise for MySQL and MariaDB, but it is driver-specific code in a generic trait.
2. **At a nested level, attempt `ROLLBACK TO SAVEPOINT` for a concurrency error.**
   - If it succeeds, the transaction survived, so rethrow as an ordinary failure of the nested unit.
   - If it fails because the savepoint does not exist (1305 on MySQL), fall back to the current shortcut.

   This needs `rollBack()`'s failure path changed, because today it rethrows the rollback error and leaves the level unchanged (O1, #61829).
3. **Probe before deciding:** send a trivial statement after the concurrency error, then read `PDO::inTransaction()`. **Observed:** after a later successful statement it was accurate in both settings. This adds a round trip on an error path.

Removing 1205 from `ConcurrencyErrorDetector` is not minimal. It would change top-level retries, which is what #19749 was for.

**Regression tests that would catch it:**

- A MySQL integration test with two connections: one holds a row lock, and the other runs an outer transaction whose nested `transaction()` inserts and then waits until a 1 s lock wait timeout. The outer code catches the exception and returns. The test asserts:
  - the inner row is absent after the commit;
  - the inner `afterRollBack` ran exactly once;
  - the inner `afterCommit` never ran.
- A mocked-PDO unit test in the style of `testTransactionMethodRetriesOnDeadlock`: a `QueryException` whose message is the 1205 text, thrown at level 2, must lead to `ROLLBACK TO SAVEPOINT trans2` when the transaction survived.
- With `innodb_rollback_on_timeout=ON`, the same integration test asserts that the nesting level returns to 0, and that the original 1205 stays in the exception chain.

## 4. Related observations with `innodb_rollback_on_timeout=ON`

These are not F1. They are recorded because they bound any fix and show what the ON setting does to the same code.

**O1: the explicit nested API reaches #61829's failure mode on MySQL (B).** This is `laravel.nested-explicit-1205`, ON, 3/3. The sequence:

1. The application caught the 1205 and called `DB::rollBack()`. Laravel sent `ROLLBACK TO SAVEPOINT trans2`, which failed with errno 1305 because the 1205 had ended the whole transaction.
2. `rollBack()` rethrew before lowering the level.
3. The exception left the outer closure. The outer handler sent the same statement again, and it failed the same way.
4. `DB::transaction()` threw `PDOException` 1305, with no cause chain. The 1205 is gone from what the caller sees.
5. The level stayed at 2, and the manager kept records for levels 1 and 2.
6. The next `DB::transaction()` sent `SAVEPOINT trans3`, which the server accepted although no transaction was open. Its insert autocommitted, no `COMMIT` was sent, and its `afterCommit` never ran: the record moved to the manager's committed list and stayed there.
7. The sink is empty for the whole run.

This is the state laravel/framework#61829 (open) reports for SQL Server. Two fix PRs for it, #61830 and #62170, were closed without merging. It needs a non-default server setting, so it is B. It matters to F1 because a fix that always sends `ROLLBACK TO SAVEPOINT` after 1205 would route the managed nested form on ON servers into this state.

**O2: a stale `afterCommit` for a rolled-back outer transaction (B, the known #61964 mechanism).** This is `laravel.nested-1205-caught`, ON, and `laravel.nested-1213-caught`, OFF.

1. InnoDB rolled back the whole transaction. The insert after the failure autocommitted, which refreshed PDO's status, so `PDO::commit()` threw "There is no active transaction" without sending `COMMIT`.
2. `handleCommitTransactionException()` does not tell the transactions manager, so the outer record stayed pending.
3. `afterCommit:outer` then ran at the next transaction's commit, for a transaction the server rolled back.

laravel/framework#61964 (open) reports this mechanism. Four fix PRs for it have been closed (#61968, #62082, #62109, #62169).

**O3: a single-level `DB::transaction()` reports success after InnoDB rolled it back (B).** This is `laravel.caught-1205-return`, ON, 3/3, with `pdo.caught-1205.commit`, ON, as its driver control. The closure caught the 1205 and returned.

- At the `after-error` checkpoint, the server's state was `ROLLED BACK`, and `PDO::inTransaction()` still returned true.
- `PDO::commit()` sent `COMMIT`, which the server acknowledged with errno 0, and returned true. The server recorded no transaction between the rolled-back one and the scenario's next `DB::transaction()`. In the PDO control, the rolled-back transaction is the only one the server recorded.
- `DB::transaction()` returned normally, `afterCommit:tx` ran, and the `tx` marker is absent.

**Manual** (PHP, `PDO::commit`): "Throws a PDOException if there is no active transaction." The driver half here is PHP's `pdo_mysql`. Laravel's own role matches the PostgreSQL study's conclusion: catching an error inside the closure is a case its documentation leaves unspecified. It needs the non-default ON setting and a catch inside the closure, so it is B. The same mechanism appears with a deadlock and the server default in the first run (§7). It was not pursued further: that would be a separate question for php-src.

## 5. Negative findings: guarantees that held

- **Raw InnoDB behaves as the manual says.** With OFF, the 1205 keeps the transaction and the savepoint, and `ROLLBACK TO SAVEPOINT` removes only the inner row. With ON, and on 1213, the transaction and its savepoints are gone (1305).
- **Laravel contains a caught nested failure** that is not a concurrency error (1062): it sends `ROLLBACK TO SAVEPOINT`, runs `afterRollBack:inner` only, and the outer commit keeps only the outer rows.
- **The explicit nested API contains a 1205 with OFF.**
- **When nothing catches,** a nested 1205 rolls everything back, with consistent callbacks, in both settings.
- **The refinement's control holds.** When the outer transaction rolls back explicitly after catching the inner timeout, nothing commits in either setting. The callbacks are `afterRollBack:inner`, then `afterRollBack:outer`, and no `afterCommit`. The inner writes are rolled back only because the outer transaction was rolled back.
- **A single-level caught 1205 with OFF** commits the earlier write, which is correct under statement-level rollback, and `afterCommit` matches.
- **Laravel's premise holds for 1213.** InnoDB rolled the whole transaction back, so nothing of the inner unit was left to undo.
- **The server's 50 s timeout behaves exactly like the 2 s session setting.**

## 6. Not established

- **Other versions:**
  - only Laravel 13.38.0 was run; the same code is in v12.70.1 and v11.57.0 (**source**);
  - only MySQL 8.4.11. MySQL 8.0 and 9.x, MariaDB and Galera (whose "WSREP detected deadlock/conflict" message is also in the detector) were not run.
- **`innodb_deadlock_detect=OFF`,** the configuration #19749 was written for, was not run.
- **Queued jobs and events with `afterCommit`** were not run. Their path through `DatabaseTransactionsManager::addCallback()` is **source** reading.
- **PostgreSQL.** The nested shortcut is also reached by PostgreSQL deadlocks (40P01) and serialization failures (40001), where an error inside a savepoint aborts only the subtransaction. That was not run, and it is outside this study.
- **Fix options.** None of the corrections in §3.7 was implemented or run.

## 7. Outside the refined question: deadlock (1213) scenarios, first run only

The first run, made before the question was narrowed, also contains these groups, each 3 of 3. They were not analyzed further; they are kept as recorded.

| Scenario | Observed |
| --- | --- |
| `pdo.caught-1213.commit` | `PDO::commit()` returned true after the subject was the deadlock victim, with no statement in between. The server recorded only the rolled-back transaction |
| `laravel.caught-1213-return` | `DB::transaction()` returned normally and `afterCommit:tx` ran. The victim's marker is absent. This is O3's mechanism, reached with the server default |
| `laravel.caught-1213` | An insert after the caught deadlock autocommitted. The commit threw, and `afterCommit:tx` ran at the next commit (#61964) |
| `laravel.explicit-caught-1213` | The documented manual pattern: `commit()` threw, `rollBack()` ran `afterRollBack:tx`, and the insert after the deadlock had autocommitted |
| `laravel.escaped-1213`, `laravel.escaped-1213-retry` | The documented deadlock handling worked: rollback and rethrow; with two attempts, the second attempt committed and only its `afterCommit` ran |

`laravel.caught-1213-return` is a confirmed-success callback after a transaction known not to have committed, reached with a common production error and the server's default configuration. Whether to pursue it, at the driver or at Laravel, is a separate decision.

## 8. Recommendation

- **F1: prepare an upstream Laravel issue,** with the standalone reproduction. Two cautions:
  - Laravel maintainers have closed contributions that appeared AI-generated (#62109, #62170), so the issue text should be written by a person;
  - [`upstream/laravel-nested-1205/NOTES.md`](upstream/laravel-nested-1205/NOTES.md) holds the facts it needs, not issue text.

  Do not open a pull request. The fix has design choices that need the maintainers (§3.7), and it touches the code #61829 is about.
- **O1 and O2** are already reported upstream (#61829 and #61964). The issue for F1 can mention O1 as a constraint on the fix.
- **O3 and the first run's `laravel.caught-1213-return`** need a separate decision before any work.
- **Do not expand to SQLAlchemy** on the strength of this study.

Nothing was committed, pushed, filed or posted.
