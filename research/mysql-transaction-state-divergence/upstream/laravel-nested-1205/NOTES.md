# Facts for an upstream report

Not issue text. Nothing has been filed. These are the checked facts that an issue on laravel/framework would rest on, with where each one comes from. The wording of any issue is to be written separately.

## Versions

- `illuminate/database` v13.38.0, the latest 13.x release on 2026-10-25. The `13.x` branch had not changed the involved files since.
- **Source:** v12.70.1 and v11.57.0 contain the same nested branch and the same detector message. They were not run.
- MySQL 8.4.11, default `innodb_rollback_on_timeout=OFF`; PHP 8.5.12, `pdo_mysql` with mysqlnd 8.5.12.

## Behavior

**Observed.** With `innodb_rollback_on_timeout=OFF`, a nested `DB::transaction()` whose statement fails with errno 1205:

- throws `Illuminate\Database\DeadlockException`;
- runs that level's `afterRollBack` callbacks;
- never runs its `afterCommit` callbacks;
- is not rolled back to its savepoint.

If the surrounding code catches the exception and the outer transaction commits, the nested unit's writes commit. The outer `DB::transaction()` returns normally.

With a duplicate key in the same place, Laravel sends `ROLLBACK TO SAVEPOINT` and the nested writes do not commit. The standalone reproduction is `repro.php` in this directory, with recorded output. The study's evidence, with an independent observer and callback sink, is `../../output/2026-10-25T17-03-57Z-e28e5b/`, scenario `laravel.nested-1205-caught`.

## Where in the code

v13.38.0:

- `ConcurrencyErrorDetector.php:34` matches `Lock wait timeout exceeded; try restarting transaction`.
- `Concerns/ManagesTransactions.php:93–102`: for any concurrency error at a nesting level above 1, the level is lowered, the manager's `rollback()` runs (which executes the inner `afterRollBack` callbacks and drops the inner `afterCommit` callbacks), and `DeadlockException` is thrown. `rollBack()` and `ROLLBACK TO SAVEPOINT` are not reached.
- The comment on that branch gives its premise: "On a deadlock, MySQL rolls back the entire transaction".

## MySQL manual (8.4, InnoDB Error Handling)

- "A transaction deadlock causes InnoDB to roll back the entire transaction."
- "A lock wait timeout causes InnoDB to roll back the current statement (the statement that was waiting for the lock and encountered the timeout). To have the entire transaction roll back, start the server with --innodb-rollback-on-timeout enabled."

## History

All of these are public:

- **#15932** (merged 2016-10-26) added the nested branch for deadlocks: "Deadlock in the inner transaction() function means the DBMS has rolled back the outer transaction as well."
- **#16140** (2016-10-27) noted that a lock wait timeout does not roll back the entire transaction by default.
- **#19749** (merged 2017-06-25) added the lock-wait-timeout message to the same detector, for servers with deadlock detection off.

## Related reports

None of these reports this case:

- **#61829** (open): SQL Server rolls back the whole transaction, Laravel's savepoint rollback then fails, and the level stays stuck. Its fix PRs #61830 and #62170 were closed unmerged. With `innodb_rollback_on_timeout=ON`, MySQL reaches the same state through the explicit nested API (study O1). A fix for this report has to avoid sending MySQL there.
- **#61964** (open): a failed `COMMIT` leaves the transactions manager pending. Its fix PRs #61968, #62082, #62109 and #62169 were closed unmerged.
- **#32543** (closed 2020): caught deadlock exceptions and the transaction level.
- **#16140** (closed 2016): general discussion of deadlocks and retries.

GitHub searches on 2026-10-25 found no report of the nested 1205 case. They used `gh api search/issues` on laravel/framework, with these terms:

- "lock wait timeout nested transaction";
- "savepoint lock wait timeout";
- "DeadlockException lock wait";
- "nested transaction 1205";
- "innodb_rollback_on_timeout";
- "nested transaction not rolled back savepoint deadlock";
- "handleTransactionException savepoint".

A further query, "lock wait timeout savepoint rollback", returned only #32543. A GitHub Discussions search of laravel/framework found nothing for these terms:

- "lock wait timeout nested transaction";
- "savepoint lock wait timeout";
- "DeadlockException".

The Laravel forums and other sites were not searched.

## What a fix has to respect

These are constraints, not a proposal:

- **The ON setting.** With `innodb_rollback_on_timeout=ON` the savepoint no longer exists after a 1205, so `ROLLBACK TO SAVEPOINT` fails with 1305.
- **The status bit.** `PDO::inTransaction()` immediately after the error still reported a transaction that InnoDB had already rolled back (study O3). It became accurate after the next successful statement.
- **Top-level retries.** These depend on the same detector (#19749's purpose).

## Checked again 2026-10-27

Through the GitHub API. Nothing was re-run. The filing checklist is [`FILING.md`](FILING.md), queued as LA1.

- `v13.39.0` was published that day. Its diff from v13.38.0 adds four lines to `handleCommitTransactionException()` (#62206). The nested branch cited above is not in that diff.
- `taylorotwell` closed #61964 that day, state reason `completed`, via #62206. The "open" label on #61964 in the history section above is the 2026-10-25 record.
- #61829 was still open. A search for `lock wait timeout nested` and for `DeadlockException savepoint` returned no issues.
