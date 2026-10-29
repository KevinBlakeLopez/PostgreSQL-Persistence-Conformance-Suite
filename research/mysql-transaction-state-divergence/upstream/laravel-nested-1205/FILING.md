# LA1. Filing package for the nested lock-wait finding

Queued 2026-10-27 in [`docs/upstream-submissions.md`](../../../../docs/upstream-submissions.md) as LA1. Not approved to post. This file is not the issue text. Laravel's maintainers have closed fix pull requests on the neighboring transaction bugs, and the study asks that a person write the report ([`findings.md`](../../findings.md) §8). The facts are in [`NOTES.md`](NOTES.md). The wording of the issue is still to be written.

## Destination

A new issue on `laravel/framework`. No pull request. The fix has choices the study did not run (§3.7 of the findings), and it sits next to code that #61829 is about.

`laravel.caught-1213-return` and O3 stay out. The study left those as a separate decision.

## What changed after the study

Checked through the GitHub API on 2026-10-27. Nothing here was re-run.

- `v13.39.0` was published 2026-10-27T14:06:19Z. `v12.70.2` was published the same day. The study ran `illuminate/database` v13.38.0 only.
- The compare `v13.38.0...v13.39.0` changes `ManagesTransactions.php` by the four lines in #62206: `handleCommitTransactionException()` now tells `DatabaseTransactionsManager` to roll back. That is the #61964 path. The nested branch the study cites at lines 93–102 is not in that diff. `ConcurrencyErrorDetector.php` is not in the compare's file list.
- `taylorotwell` closed #61964 at 2026-10-27T13:26:06Z, state reason `completed`, when #62206 merged (`377f5ce`). #61829 is still open, last updated 2026-10-02, with no comments.
- A search that evening for `lock wait timeout nested` and for `DeadlockException savepoint` in `laravel/framework` returned no issues. The queries recorded in `NOTES.md` are the 2026-10-25 search. Search again on the day of posting.

## Before posting

1. Approval of the exact title, body, and destination.
2. Run `repro.php` on v13.39.0, three times, against a MySQL 8.4 server with the default `innodb_rollback_on_timeout=OFF`. The recorded 13.38.0 output is `output/off-r1.txt` (and `off-r2.txt`, `off-r3.txt`), SHA-256 `191715f6cf008eb2a995c66db6ce0230201ec6a175df11d69318b693d79f70ff`. If 13.39.0 differs, the issue describes the run, not the 13.38.0 output.
3. Re-read the nested branch on the tag that was run. The 13.38.0 lines in `NOTES.md` are for that release.
4. Repeat the duplicate search, including issues opened after 2026-10-27.
5. Leave #61829 and #61964 as neighbors. Do not restate them as this bug. Say that a fix which always sends `ROLLBACK TO SAVEPOINT` after errno 1205 meets errno 1305 when `innodb_rollback_on_timeout=ON` (study O1, the explicit nested API).
6. Do not claim that v12 or v11 were run. `NOTES.md` records a source reading of v12.70.1 and v11.57.0. v12.70.2 was not read.

## What the report can rest on

These are the checked claims. Rewrite them.

- With the server default OFF, a nested `DB::transaction()` whose statement fails with errno 1205 throws `Illuminate\Database\DeadlockException`, runs that level's `afterRollBack` callbacks, and does not send `ROLLBACK TO SAVEPOINT`.
- If the outer closure catches that exception and the outer transaction commits, the nested unit's earlier writes commit. The outer call returns normally. There is no inner `afterCommit`.
- The same nested code with a duplicate key (1062) does send `ROLLBACK TO SAVEPOINT`, and those inner writes do not commit.
- The study's instrumented row is `laravel.nested-1205-caught`, OFF, 3 of 3, in `output/2026-10-25T17-03-57Z-e28e5b`. The server's transaction was still `ACTIVE`, with one savepoint and zero `ROLLBACK TO SAVEPOINT`, at the checkpoint just after the throw.
- The nested shortcut was added for deadlocks in #15932, on the premise that MySQL has rolled the whole transaction back. #19749 added the lock-wait message to the same detector. The MySQL 8.4 manual distinguishes the two: a deadlock rolls the transaction back; a lock wait timeout rolls the statement back unless `innodb_rollback_on_timeout` is on.
- The standalone script is `repro.php` in this directory. It uses two PDO connections and `illuminate/database` 13.38.0. Its three OFF runs are byte-identical.

## Leave out

- A patch, a suggested diff, or a pull request.
- O1, O2, and O3, except the one sentence that an unconditional `ROLLBACK TO SAVEPOINT` is unsafe on the ON setting.
- The first run's deadlock rows, including `laravel.caught-1213-return`.
- Any name of this research repository.
- A claim that v13.39.0 was run, until the re-run above exists.
