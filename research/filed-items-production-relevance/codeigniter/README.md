# CodeIgniter 4 on MySQL: production relevance of CI1 and CI2

Assessed 2026-10-26. Written by: Claude Opus 5.5 (max).

This page rates two findings filed upstream on 2026-10-22, under PPCS's standard (`docs/production-relevance.md`). It is a desk assessment: read-only GitHub searches, source reading at commits, and PPCS's recorded runs. Nothing was run, posted or sent.

- **CI1:** `reconnect()` replaces a dead MySQLi connection but keeps `transDepth` and `transStatus`, so `transComplete()` returns true for the lost transaction. Filed as [codeigniter4/CodeIgniter4#10648](https://github.com/codeigniter4/CodeIgniter4/issues/10648), with PR [#10650](https://github.com/codeigniter4/CodeIgniter4/pull/10650).
- **CI2:** after MySQL error 1213 (deadlock), `transDepth` stays at 1. Later writes on the connection autocommit, and `transCommit()` returns true while the earlier writes are gone. Filed as [#10649](https://github.com/codeigniter4/CodeIgniter4/issues/10649), with PR [#10651](https://github.com/codeigniter4/CodeIgniter4/pull/10651).

All four were open and unmerged on 2026-10-26. That day a maintainer (michalsn, MEMBER) reviewed both PRs. On #10650 he wrote "Looks good overall" and asked for documentation changes. On #10651 he asked for one extra check and two documentation changes. He did not call either shape misuse.

## Tiers (judgment, 2026-10-26)

The tiers follow the Python tracker. They weigh likelihood, the strength and source of the evidence, and whether the failure is silent. They change no severity rank.

- **Middle: CI2.**
  - For: a production log shows the trigger in OSPOS's sale code, with the group running on after the deadlock ([opensourcepos#4320](https://github.com/opensourcepos/opensourcepos/issues/4320)). OSPOS 3.4.2 and 3.4.3 now ship that code on an affected CodeIgniter version. The failing code is the user guide's own idiom.
  - Against: that report ran on CodeIgniter 3, where the later writes did not commit. No report shows the committed tail, and the documented calls return false.
- **Lower: CI1.** When it fires, the false success is silent. But no inspected code calls `reconnect()` inside a transaction, and no report was found.

| ID | Filed as | Trigger, and how our runs produced it | Strongest real-world evidence | Real code run | Consequence | Likelihood (judgment) |
| --- | --- | --- | --- | --- | --- | --- |
| CI1 | #10648 (issue) and #10650 (PR), open | The server ends the session inside a transaction (idle `wait_timeout`, kill, restart, failover), then the code calls `reconnect()`. Our runs: a real idle disconnect through the ordinary API (session `wait_timeout` of 1 s, a 3 s sleep), CodeIgniter 4.7.5, 6 of 6 | None with the filed shape. The real `reconnect()` calls found sit between units of work. A queue user's unfinished transaction (codeigniter4/queue#41) shows the precondition of a second path | No | The writes before the loss are gone, later writes autocommit, and `transComplete()` returns true | Low |
| CI2 | #10649 (issue) and #10651 (PR), open | Error 1213 on a write that is not the last of its group. Our runs: a real InnoDB deadlock with a second session, ordinary API, CodeIgniter 4.7.5, 9 of 9 | Production, for the trigger: opensourcepos#4320 quotes a deployment's logs (OSPOS 3.3.9 on CodeIgniter 3). A deadlock hit the sale-item insert, and the same sale's later inserts still ran. Exposed code: OSPOS (4,464 stars) ships that `save_value()` in 3.4.2 and 3.4.3 on 4.7.4; Castopod (877 stars) `addLike()` on 4.7.0 | No | Earlier writes are rolled back and later ones commit. `transComplete()` returns false but cannot undo them, and a retry repeats them. An unchecked `transCommit()` returns true | Moderate |

## CI1: `reconnect()` keeps a lost transaction

- **Production relevance (2026-10-26)** (standard: PPCS `docs/production-relevance.md`; details [below](#ci1-details)):
  - **Consequence:** the writes made before the connection was lost are gone, because the server rolled them back. Each write after `reconnect()` autocommits, and `transComplete()` or `transCommit()` returns true: a false success for a torn unit. The API reports nothing; CodeIgniter's error log records the disconnect.
  - **Trigger, the connection dies inside a transaction and the code calls `reconnect()` before continuing:** in production, the events happen (MySQL's default idle timeout is 28,800 s, one shared host is reported at 30 s, and kills, restarts and failovers also end sessions), but whether code calls `reconnect()` there is unknown; in our runs, a real idle disconnect through the ordinary API (PPCS `investigations/mysql-innodb-baseline/evidence/php-connection.json`, `MX-05.idle-then-reconnect`, 6 of 6, CodeIgniter 4.7.5). Code shape: `reconnect()` between `transStart()` and `transComplete()`. Not reasonable: redrawn, the slow work goes before the transaction, and a lost transaction is retried whole, not continued. The guide's reconnect advice does not mention transactions. On 4.6 and earlier, MySQLi's `reconnect()` always replaced the connection, so the same code lost the transaction with no timeout at all (source reading). Evidence: none; 0 of 3 real call sites are inside a transaction.
  - **Trigger, a transaction left open by an earlier unit in a long-running worker, then its routine `reconnect()` (source reading, not run):** in production, the leak happens (codeigniter4/queue#41, a user, 2024); in our runs, only the leftover depth after a killed `COMMIT` (`MX-05.connection-closed-before-commit`). Code shape: reconnecting before each unit is reasonable, and codeigniter4/queue does it; leaving a transaction open is misuse per the maintainers. Once the connection is replaced, later units' `transStart()` sends no `BEGIN`, so their writes autocommit and their `transComplete()` cannot undo them. Evidence: none for the combination.
  - **Reproduced on real code:** no. Our runs used a constructed subject.
  - **Searches:** 0 of 21 inspected application files that mention both `reconnect` and a transaction method call `reconnect()` inside a transaction. The 3 real call sites found are between units of work.
  - **Likelihood (judgment):** low. The filed shape was not found, and the connection has to die inside that window.
  - **Not established:** any real code with the shape; how often CodeIgniter deployments lose a connection inside a transaction; the second path, end to end.

## CI2: a deadlock leaves `transDepth` set

- **Production relevance (2026-10-26)** (standard: PPCS `docs/production-relevance.md`; details [below](#ci2-details)):
  - **Consequence:** InnoDB has rolled back the earlier writes, and every later write in the same group autocommits. `transComplete()` returns false but cannot undo them; in the guide's manual branch, `transRollback()` returns true. The caller believes nothing was written, so a retry applies the tail twice. `transCommit()` without the `transStatus()` check returns true: a false success. `transStatus()` is false, and the error log has the deadlock line.
  - **Trigger, error 1213 on a write that is not the last of its group:** in production, yes. [opensourcepos#4320](https://github.com/opensourcepos/opensourcepos/issues/4320) (2025, a user, several concurrent logins) quotes a deployment's logs: a deadlock on the sale-item insert in OSPOS's sale transaction, then the same sale's later inserts still ran and failed on foreign keys. It ran on CodeIgniter 3, where the later writes did not commit (source reading). MySQL's manual treats deadlocks as normal. In our runs, a real InnoDB deadlock with a second session, through the ordinary API (PPCS `investigations/mysql-innodb-baseline/evidence/php-concurrency.json`, `MX-02.deadlock-victim`: managed, the guide's manual branch, and an unchecked `transCommit()`, 9 of 9, CodeIgniter 4.7.5). Code shape: several writes between `transStart()` and `transComplete()` with no check between them, the guide's own example. Reasonable: since 4.3.0 an error inside a transaction does not throw unless `transException(true)` is set. Skipping the `transStatus()` check before `transCommit()` is contrary to the guide. Evidence:
    - production, for the trigger in this exact path: #4320 (the deployment was modified; its logs were not checked);
    - exposed code: OSPOS 3.4.2 and 3.4.3 ship the same `save_value()` on CodeIgniter 4.7.4, with `DBDebug` false in production;
    - exposed code: Castopod's `addLike()` on 4.7.0, where, in my judgment, two concurrent likes can deadlock before its last writes.
  - **Reproduced on real code:** no.
  - **Searches:** 9 of 15 inspected general hits have the shape. So do 8 of 12 projects whose code mentions deadlocks near a transaction; 3 of the 12 handle it correctly. Of 7 try/catch hits, 0 confirmed an unchecked `transCommit()`, and 4 are correct.
  - **Likelihood (judgment):** moderate. The shape is the default idiom, and OSPOS has hit the trigger in this path. The trigger needs concurrent writers and a deadlock before the group's last write, so most small applications will rarely see it. The autocommitted tail affects only releases since 2026-02-01 (4.6.5 and 4.7.0 on).
  - **Not established:** a report of the committed tail on an affected version; frequency; whether Castopod's deadlocks occur; 4.6.4 and earlier, and CodeIgniter 3, were not run.

## CI1 details

**Affected versions.** Neither fix is merged; PR #10650 adds a v4.7.6 changelog entry. By source reading:

- 4.7.0 to 4.7.5 and `develop` close and reopen the connection only when `ping()` fails:
  - `codeigniter4/CodeIgniter4 system/Database/BaseConnection.php @ 17d2d66671, lines 495–501` (v4.7.0);
  - the same file `@ 699fc2f86a, lines 630–636` (`develop`, 2026-10-26).
- The 4.8 branch has the same body: `@ 10ea628d0a, lines 669–675`.
- 4.6.5 and earlier: MySQLi's own `reconnect()` closes and reopens every time, as `system/Database/MySQLi/Connection.php @ f2907b94a2, lines 258–262` (v4.6.4) shows. The 4.6 guide says so: `user_guide_src/source/database/connecting.rst @ f2907b94a2, lines 101–102` ("the `reconnect()` method does not ping the server but it closes the connection then connects again"). In #9043, a maintainer (paulbalandan) noted the same in 2024. There, any `reconnect()` inside a transaction drops it. Not run.
- The issue says "4.7.0 (measured)". The recorded runs are on 4.7.5, and no 4.7.0 run is recorded in PPCS. 4.7.0 has the same `reconnect()` by source reading.

**Our runs.** PPCS `investigations/mysql-innodb-baseline/php/README.md`, section "Connection loss", and `evidence/php-connection.json` (finished 2026-10-21T19:27:50Z). MySQL 8.4.11 with `wait_timeout` at its default of 28800, PHP 8.5.6 with mysqlnd, CodeIgniter 4.7.5, `mysqli.reconnect` off.

- In `MX-05.idle-then-reconnect`, `ping()` returned false and `reconnect()` opened a new connection with a new id. `transDepth` stayed 1 and `transStatus()` stayed true. An insert on the new connection was visible to another session before the completion call. `transComplete()` (managed) and `transCommit()` (manual) returned true. Only the post-reconnect row remained.
- I checked all six repetitions in the JSON. Each records two error-log lines from `Connection.php` line 294.
- The neighboring case `MX-05.connection-closed-before-commit` (the thread killed before `COMMIT`): the completion calls threw errno 2006, and `transDepth` stayed 1 afterwards. That leftover depth is the precondition of the second path.

**How CodeIgniter's own long-running code calls `reconnect()`.** Source reading:

- **codeigniter4/queue** (76 stars) `src/Models/QueueJobModel.php @ 4b444640c3`:
  - lines 68–81 call `reconnect()` before every job claim, outside any transaction, which is correct;
  - lines 148–180 then run the claim in `transStart()`/`transComplete()` and ignore its result;
  - lines 50–61 turn strict mode off.
  - The worker uses the shared default connection (`src/Config/Queue.php`, lines 47–53). It does not reset transaction state between jobs (`src/Commands/QueueWork.php`, lines 172–189 and 315–369).
  - So a job that leaves a transaction open carries it into the next poll's `reconnect()`.
- **The FrankenPHP worker mode** (#9889, in 4.7.0) calls `reconnect()` on every connection at the start of each request: `system/Database/Config.php @ 699fc2f86a, lines 159–164`, from `system/Commands/Worker/Views/frankenphp-worker.php.tpl`, line 77. At the end of each request it rolls back any open transaction (`Config.php`, lines 177–191, template line 119). That keeps a stale depth out of the next `reconnect()`: evidence against CI1 reaching worker mode.

**Inspected application code.** Most hits for `reconnect` are vendored copies of CodeIgniter's own `system/` folder, or Laravel code.

- `reconnect transStart path:app` (23 files): 11 are vendored copies. Of the 12 application files, none calls the database's `reconnect()`; the token matched other words ("reconnecter", `reconnectUsingMpesaCode`, comments, a facade docblock). Files:
  - Andrianina-Mariah/reegime_alimentaire `Wallet.php`, `Activites.php` and `Regimes.php` @ a62cf8d69e;
  - peterdetruth/wifi_system `MpesaService.php` @ 1ae285f4dd;
  - mikhaelfelian/p54-kopmensa `Shift.php` @ 4c631a37a8;
  - tikusgot007/AuliaPos `ConversationModel.php` and `InboxGatewayApi.php` @ c8c9e187b0;
  - shohan-dev/isp-web `Customer.php` @ 73b2f78704;
  - MandresyMC/4051-4381-OperateurS4 `ClientOperationController.php` and `OperationController.php` @ 8a213b870a;
  - agungsugiarto/codeigniter4-realworld-api `DB.php` @ fbf40371b9;
  - benemmylex/phoenixbackups.org `index.php` @ 281271a3a3.
- `reconnect transBegin path:app` (84 files, all listed): 75 are vendored copies. Of the 9 application files:
  - nkarisa/gms `app/Controllers/Web/Grants/Budget.php @ e87cebdb47`, lines 372 and 491, calls `reconnect()` on a read connection, with no transaction in those methods;
  - geosh2000's two copies of a custom driver override `reconnect()` (`app/Libraries/Database/Connection.php @ 7ac4f5e6ad, lines 239–243`);
  - the other 6 do not call it.
- Long-running commands. romeroa14/tuasesorrm-rems `app/Commands/QueueProcess.php @ 9a8e9c95a4` is a `while (true)` worker. Before each message it calls `DatabaseReconnect::ensureLive()` (`app/Libraries/DatabaseReconnect.php`, lines 14–29), which runs `SELECT 1` and calls `reconnect()` if that throws. That is between messages, outside any transaction, which is correct.
- Faiqzakii/meetingku `app/Commands/WaWorker.php @ 08e5ef938e, lines 17–90` is a polling worker that uses `transStart()` and no `reconnect()`.

So 0 of 3 real `reconnect()` call sites are inside a transaction: the queue package, tuasesorrm-rems, and gms. Across both queries, 0 of 21 application files have the shape.

**Reports of the trigger.**

- CodeIgniter 4 tracker: in 15 issue queries, I found no user report of a lost connection or `reconnect()` inside a transaction. The connection-related items are ours, #9043 and its fix #9279 (a PostgreSQL `pg_ping()` TypeError, 2024), #462 (2017), and the worker-mode PR #9889.
- codeigniter4/queue: no report of "gone away" or of `reconnect()` (one PR, #47).
- CodeIgniter 3: [bcit-ci/CodeIgniter#4957](https://github.com/bcit-ci/CodeIgniter/issues/4957) (2016-12-22, NONE) reports "MySQL server has gone away" after "some heavy work before executing SQL statement" on "a huge project". It does not mention transactions. narfbg (CONTRIBUTOR) declined an automatic ping before every query.
- MySQL 8.4's manual gives `wait_timeout` a default of 28800 and a minimum of 1.
- Host values: one user states that Hostpapa's shared hosting fixes it at 30 s (forum.scriptcase.net, 2021-09-23). A cPanel community thread said to report 60 s returned HTTP 403 and was not read.

**Evidence against.**

- The `reconnect()` docblock and the guide describe keeping a connection alive between slow work and the next queries. Neither promises to resume a transaction.
- On #10650, michalsn wrote: "Please clarify that `reconnect()` does not resume the lost transaction and that failure handling must cover the entire operation, including nested transaction groups." His suggested guide text: "If the operation must remain atomic, stop executing its remaining queries."
- On queue#41 he told the user, whose job had left a transaction open, to "handle possible errors a bit better".

## CI2 details

**Affected versions.** By source reading:

- The tail autocommits only since PR [#9888](https://github.com/codeigniter4/CodeIgniter4/pull/9888) (first released in v4.6.5 and v4.7.0, both 2026-02-01). That PR stopped MySQLi from turning autocommit off for a transaction.
- Before it, `_transBegin()` called `autocommit(false)`, and commit and rollback turned it back on: `system/Database/MySQLi/Connection.php @ f2907b94a2, lines 626–659` (v4.6.4). Since v4.6.5 (`@ 7a3563d6c6, lines 611–630`) and on `develop` (`@ 699fc2f86a, lines 575–588`), only `begin_transaction()` remains.
- So on 4.6.4 and earlier, a write after the deadlock opened a new implicit transaction, which `transComplete()` and the guide's rollback undid. An unchecked `transCommit()` committed it and returned true on every version.
- None of this was run below 4.7.5. The fix PR (#10651) adds a v4.7.6 changelog entry and leaves prepared statements out of scope.
- The 4.8 branch (`@ 10ea628d0a`) has the same MySQLi methods (lines 638–651).

**Why the group keeps running.** On `develop`:

- `query()` marks the status failed and throws only if `DBDebug` is on and either no transaction is open or `transException` is set (`system/Database/BaseConnection.php @ 699fc2f86a, lines 826–840`).
- `transComplete()` rolls back when the status is false (lines 967–988).
- `transCommit()` does not read the status (lines 1035–1049).
- The 4.3.0 changelog records the change: "During transactions, exceptions are not thrown by default even if `DBDebug` is true" (`user_guide_src/source/changelogs/v4.3.0.rst @ f8e4ec57cb, lines 41–56`).
- `DBDebug` false turns off `transException(true)` too, because `query()` needs both flags to throw.

**Our runs.** PPCS `investigations/mysql-innodb-baseline/php/README.md`, section "Deadlock and lock wait", and `evidence/php-concurrency.json`: MySQL 8.4.11, PHP 8.5.6, CodeIgniter 4.7.5, `DBDebug` true, `transException` false. A Node session made the PHP session the deadlock victim. I checked all nine repetitions:

- error 1213, `transDepth` 1, and performance-schema state `ROLLED BACK`;
- the follow-up insert was visible to another session before the end call;
- the final rows held only that insert;
- `transComplete()` returned false, the documented manual `transRollback()` returned true, and the unchecked `transCommit()` returned true.

**A production report of the trigger, in OSPOS.** [opensourcepos/opensourcepos#4320](https://github.com/opensourcepos/opensourcepos/issues/4320), opened 2025-09-18 by fernando47924 (NONE) and closed 2025-11-21 with no stated fix.

- The report quotes error-log lines dated 2025-09-17 from a deployment (database `ospos_lcm1`, sale 59500):
  - `Query error: Deadlock found when trying to get lock; try restarting transaction - Invalid query: INSERT INTO ospos_sales_items ...` for line 2 of the sale;
  - two `Cannot add or update a child row: a foreign key constraint fails` errors on that sale's `ospos_sales_items_taxes` inserts.
- So the sale transaction kept running after InnoDB had rolled it back.
- The deployment was OSPOS 3.3.9 on MariaDB 10.7.3. The reporter confirmed that the schema was modified and that "I'm using the application from multiple browsers with different login". jekkos (MEMBER) and odiea (COLLABORATOR) replied.
- The log lines were not checked beyond the report.
- OSPOS 3.3.9 runs CodeIgniter 3 (`codeigniter/framework` `^3.1.11` at tag 3.3.9, `c00ff28d10`). The log format is CodeIgniter 3's (`system/database/DB_driver.php @ bcb17eb8ba`, line 672, tag 3.1.13).
- CodeIgniter 3 turns autocommit off for a transaction (`system/database/drivers/mysqli/mysqli_driver.php @ bcb17eb8ba, lines 347–384`), so writes after the deadlock joined a new implicit transaction that `trans_complete()` rolled back. The report shows the trigger and the continuation, not the committed tail.
- OSPOS releases and their CodeIgniter versions, from each tag's `composer.lock`:
  - 3.4.0 (2025-03-23), CodeIgniter 4.5.5;
  - 3.4.1 (2025-06-05), 4.6.0;
  - 3.4.2 (2026-10-02) and 3.4.3 (2026-10-22), 4.7.4, an affected version.
- `Sale::save_value()` at tag 3.4.3 (`35b68245a0`) is identical to the commit read below. OSPOS deployments that upgrade to 3.4.2 or later move this code onto CI2's version range.
- OSPOS maintainers have worked on concurrency in this path: [#4640](https://github.com/opensourcepos/opensourcepos/pull/4640) (objecttothis, MEMBER, merged 2026-08-19) made gift-card and reward-point decrements atomic and reports insufficient balances. Its description covers the steps that `save_value()` checks (gift cards, reward points, stock); I did not trace those lines to the PR.

**Exposed code in widely used applications.** Source reading; nothing was run.

- **OSPOS** (opensourcepos/opensourcepos, 4,464 stars) pins CodeIgniter 4.7.4 and sets `'DBDebug' => (ENVIRONMENT !== 'production')` (`app/Config/Database.php @ 9253cfe836`, line 36).
  - `app/Models/Sale.php @ 9253cfe836, lines 562–695` (`save_value()`) runs these inserts unchecked:
    - the sale, its payments and its sale items (lines 570, 611, 643);
    - the inventory rows (line 673).
  - It checks the gift-card and reward-point steps, and the stock upsert (lines 585–594 and 647–654). A failed stock upsert returns `INSUFFICIENT_STOCK`, a misleading message, but stops the save.
  - A deadlock on one of the unchecked inserts would let the stock changes and inventory rows from that point on autocommit, while the sale returns -1. Later sale-item and tax inserts would fail on foreign keys, as in #4320.
  - `app/Models/Receiving.php @ 9253cfe836, lines 124–189` says "we want to make sure we do all or nothing" and checks none of its writes.
  - `app/Models/Item_quantity.php`, lines 93–104, shows the stock upsert.
- **Castopod** (ad-aures/castopod, 877 stars) pins 4.7.0, with `DBDebug` true. `app/Models/LikeModel.php @ e439b31ac2, lines 50–89` (`addLike()`):
  - inserts into `likes`, whose foreign key points at the comment (`app/Database/Migrations/2021-08-12-160000_add_likes.php`, lines 34–36);
  - then increments that comment's `likes_count`;
  - then, for local likes, inserts and updates a queued `Like` activity;
  - ignores `transComplete()`.
  - MySQL documents that a foreign-key check "sets shared record-level locks on the records that it looks at". The increment then needs an exclusive lock on the same comment row.
  - My judgment: two concurrent likes of one comment can deadlock on the increment, and then the victim's activity rows autocommit for a like that was not saved.
  - `app/Models/EpisodeCommentModel.php`, lines 143–193, has the same unchecked shape.
  - Castopod's GitHub repository has issues turned off, and its own tracker was not searched.
- **esection** (VishalNanavare/esection, 0 stars, CodeIgniter 4.7.4), `app/Services/StudentVerificationService.php @ bbb483ef71, lines 118–200`, states its all-or-nothing contract most clearly. Its comment says the batch was moved into one transaction because "a failure part-way through (deadlock, dropped connection, lock timeout, an over-long value) left every earlier candidate committed". On failure it reports "No records were written". Under CI2, the inserts after a deadlocked one would be committed, so a resubmission would duplicate them.

**Sample 1: projects that mention deadlocks near a transaction.** Queries `transStart Deadlock`, `transBegin 1213` and `transStart 1213` returned 16, 8 and 6 files. After excluding the following, 12 CodeIgniter 4 projects remain:

- non-CodeIgniter code (the Tencent Cloud SDK, a ThinkPHP project, omegaup);
- test files;
- PPCS's own subject;
- a false positive (`1213` in a code map);
- an identical fork.

8 have the shape:

- jsnmrs/aggro `FeedIngestionService.php @ 43b47b26a2, lines 139–187` (4.7.5). It retries only when the last query's error code is 1213 or 1205, so a deadlock before the last write is not retried. Its `REPLACE` writes make a later re-fetch harmless.
- vosidiy/edutest-uz `PlayerStore.php @ ef54b901ea, lines 23–51` (4.7.4). Same last-error check. It locks the row first, which makes a later deadlock unlikely.
- Dikrifm/devdaily2 `BaseService.php` and `TransactionService.php @ d30c9d5f5e` (locked 4.6.4). The retry matches on an exception message or a `DatabaseException`, which CodeIgniter does not raise inside a transaction by default, so it never fires for a deadlock inside the transaction.
- sebastiananthonyacierto1-dotcom/Counselign-web `TransactionManager.php @ 54cea0c91f, lines 36–99` (locked 4.6.1). Same problem: the retry looks for "Deadlock" in a message its own wrapper never produces.
- rafael-fu2025/synapse_ci `GuidanceCaseService.php @ 73a2e4db42, lines 565–611` (4.7.5). Last-error check; it takes a tenant lock first and asks the user to retry.
- VishalNanavare/esection, above (4.7.4).
- ITZ-HURAIRAH18/CodeIgniter-AI-Driven-Development `StockTransferService.php @ bba4fa7c26, lines 105–185` (4.7.0). It also ignores `transComplete()` and returns the transfer as completed.
- luisbeltranh/nutsypos_v1_old `Dashboard.php @ f4e2ad3a5b, lines 273–366` (locked 4.6.0). It updates stock in a loop after a sales `insertBatch`, and its comment assumes a deadlock rolls everything back.

3 are correct:

- arumiforge/spensada `app/Services/Sistem/Transaction.php @ c1876f11dd, lines 55–96` sets `transException(true)`, rolls back, and retries the whole action once on 1205 or 1213.
- abdullahazwar/framework-codeigniter-parkirkendaraan `ParkirService.php @ 779ad07a49, lines 251–284` and `PenggunaParkirService.php`, lines 292–310, do the same.
- shohan-dev/isp-web `Customer.php @ 73b2f78704, lines 3580–3700` checks every write, throws, and rolls back.

1 does not apply: GabrielMarques1/Emissor-de-notas-fiscais `CaixaSessaoModel.php @ 56ceba2385` has one checked write per group.

Of the 8 with the shape, 5 lock an affected version. devdaily2, Counselign-web and nutsypos lock 4.6.x, where the tail is rolled back, but their `composer.json` allows an upgrade. All 12 repositories have 0 to 2 stars.

**Sample 2: ordinary transactions.**

- `transStart transComplete` returned 960 files under `path:app/Models` and 2,540 under `path:app/Controllers`. I inspected 15 files from 10 repositories among the top hits.
- 9 have a group with two or more writes, no check between them, and no `transException(true)`:
  - OSPOS `Sale.php` and `Receiving.php`;
  - Castopod `LikeModel.php` and `EpisodeCommentModel.php`;
  - ikhsan3adi/absensi-sekolah-qr-code (493 stars, 4.7.5) `app/Models/PerizinanModel.php @ 4261440c8b, lines 53–111`;
  - pmiidev/hibahweb (4.7.2) `PostModel.php @ 4504c21885, lines 29–36`, whose likely deadlock lands on the last write, so there is no tail;
  - gieart87/ci4-cicommerce `Products.php @ 9127970441, lines 159–185` (no lock file, last push 2021);
  - adimiuprix/diginine-topup-games `TripayController.php @ 5d2efc3928, lines 134–149` (4.4.6, before #9888);
  - purwostwn98/lazismu_keuangan `Mutasi.php @ ffc0e9d2bd, lines 121–162` (4.7.3).
- 6 do not:
  - OSPOS `Customer.php`, where the second write runs only if the first succeeded, and `Item.php`, with single writes;
  - llbbl/codeigniter-chat `ChannelModel.php` (single writes) and `ChatModel.php` (`transException(true)`, lines 357–360);
  - felixsinggih/inventory-ci4 `Barang.php` (single writes);
  - Marinay-ALTF4/SAD `Orders.php` (single writes).
- 7 of the 9 are in projects locked to an affected version.

**Sample 3: try/catch around `transBegin()`.**

- `transBegin transCommit catch path:app` returned 1,444 files. I inspected 7 from 5 repositories.
- 4 are correct:
  - OSPOS `app/Controllers/Items.php @ 9253cfe836, lines 829–907` chains `$success && ...`, so it stops at the first failed write;
  - imxz/LetsBBS `FollowService.php` and `TopicService.php @ 795a79f8bb` use `transException(true)`;
  - soerennb/extplorer `DatabaseStateBackend.php @ bce4755467` checks every write.
- 3 are not determined: collec-science/collec-science `Lot.php` and `Movement.php @ 13ed0cb81a` convert errors in a layer I did not read, and ronokcse/chatpionv2 wraps the connection.
- No inspected hit confirmed the unchecked `transCommit()` path.

**Sample 4: `DBDebug` settings.**

- `DBDebug filename:Database.php path:app/Config` returned 4,384 files. 6 of the top 10 turn it off in production, with `(ENVIRONMENT !== 'production')` or an equivalent; 4 set `true`.
- The query that adds `ENVIRONMENT production` returned 1,312 files; 10 of 10 inspected turn it off in production, including Opmantek/open-audit.
- That value was the default before 4.3.0 (`app/Config/Database.php @ 558db238d0`, line 42, v4.2.12). From 4.3.0 the default is `true` (line 36 on `develop`).

**The 4.8 retry helper (source reading of an unreleased branch, not run).**

- On the 4.8 branch, `transaction()` with `attempts` (PR #10197) retries after `transComplete()` returns false, if the failure was retryable and the depth is 0 (`system/Database/BaseConnection.php @ 10ea628d0a, lines 1094–1174`).
- With the default `transException(false)`, a deadlock does not stop the callback, so its later writes autocommit before the retry runs them again. The guide's retry example (`transactions/016.php`) does not set `transException`.
- PR #10651's fix would make those writes join a new server transaction that is rolled back, for `query()` and the query builder.

**Reports of the trigger.**

- CodeIgniter 4 tracker: in the deadlock, `1213` and lock-wait queries, the only deadlock items are ours and two 4.8 features (#10162, #10197). The codeigniter4/queue tracker has none.
- In the trackers of the applications I sampled:
  - OSPOS has #4320 (above), and #4763 and #4769 about migrations;
  - absensi-sekolah-qr-code has none;
  - Castopod's GitHub issues are turned off.
- MySQL 8.4's manual:
  - "A transaction deadlock causes InnoDB to roll back the entire transaction. Retry the entire transaction when this happens." (InnoDB error handling);
  - "You can get deadlocks even in the case of transactions that just insert or delete a single row";
  - a foreign-key check "sets shared record-level locks on the records that it looks at".
- michalsn on #10197 (2026-05-13): "Most retryable transaction failures, especially deadlocks, are often resolved naturally once the database aborts one of the competing transactions."
- Several sampled projects name deadlocks in comments as a failure they design against: esection, nutsypos, `StockTransferService.php`, and `CaixaSessaoModel.php`, which reads "without a transaction to avoid deadlocks". None reports one happening.

**Evidence against.**

- The guide offers the safe forms:
  - "Throwing Exceptions" with `transException(true)` ("all the queries will be rolled backed, and a `DatabaseException` will be thrown");
  - checking `transStatus()` in "Managing Errors";
  - the manual example, which checks `transStatus()` before `transCommit()` (`user_guide_src/source/database/transactions.rst @ 699fc2f86a, lines 84–112 and 137–146`).
- 3 of the 12 deadlock-aware projects, and 4 of the 7 try/catch hits, use those forms.
- The unchecked `transCommit()` path is contrary to the guide.
- Against that, the same guide page promises that the queries in a group "will all be committed or rolled back based on the success or failure of any given query" (lines 48–50). In our runs, the guide's own managed form and its manual branch both left the post-deadlock row.

## Neighbors listed in the issues

| Item | Who and when | Production or test | Relation to CI1 and CI2 |
| --- | --- | --- | --- |
| [#10162](https://github.com/codeigniter4/CodeIgniter4/pull/10162) | PR by memleakd (CONTRIBUTOR), 2026-05-06; merged to `4.8` on 2026-05-10; unreleased | A feature with unit tests; no failure report | Classifies 1213 as `RetryableTransactionException`. The same trigger, but it changes neither `transDepth` nor what follows the deadlock |
| [#10197](https://github.com/codeigniter4/CodeIgniter4/pull/10197) | PR by memleakd (CONTRIBUTOR), 2026-05-13; merged to `4.8` on 2026-05-15; unreleased | A feature with tests | Retries the closure helper only when the depth is 0. With the default `transException(false)` it would retry after CI2's tail has committed (source reading). Holds michalsn's statement on deadlocks |
| [#9888](https://github.com/codeigniter4/CodeIgniter4/pull/9888) | PR by kamil-tekiela (CONTRIBUTOR), 2026-01-16; merged to `develop` 2026-01-18; first in v4.6.5 and v4.7.0 | A refactor, approved as correct ("I had to read up on it, and it looks like you're right") | Part of CI2's mechanism: since it, the write after a deadlock autocommits. It marks where the torn tail starts |
| [#6909](https://github.com/codeigniter4/CodeIgniter4/issues/6909) | Issue by kenjis (MEMBER), 2022-11-25; open | A design to-do list after 4.3.0 | Covers exceptions in manual transactions (#6917), `resetTransStatus()` (#8767), and model validation inside a transaction. The status flag only; it shares neither mechanism |
| [#8767](https://github.com/codeigniter4/CodeIgniter4/pull/8767) | PR by kenjis (MEMBER), 2024-04-12; merged to `4.6` on 2024-06-30; in v4.6.0 and later | A feature | `resetTransStatus()` restarts groups after a strict-mode failure. It does not detect a server-side rollback. Code that resets the status and keeps writing (tikusgot007/AuliaPos `ConversationModel.php @ c8c9e187b0, lines 399–470`, after a duplicate key) is correct for 1062 on MySQL but not for 1213 |
| [#10236](https://github.com/codeigniter4/CodeIgniter4/pull/10236) | PR by michalsn (MEMBER), 2026-05-25; merged to `develop` 2026-05-27; first in v4.7.4 | A bug fix with a test | A different mechanism: `updateBatch()` after `where()`. It fixes #10234, which is not assessed here |

None of the six reports a production failure. Only #9888 is part of a mechanism (CI2's), and it is a refactor, not a report.

## The forum

On 2026-10-26, forum.codeigniter.com returned HTTP 403 to direct fetches of its search page and of a thread, and the web archive was not reachable from this environment. I could not search or read the forum.

A web search restricted to the forum returned thread titles only. They include "How to cope with deadlocks?" (thread-57044), "Problem with transactions try catch" (thread-89118) and "Mysql gone Away error pls HELP!" (thread-81504). These are leads, not evidence.

## Method

All searches ran on 2026-10-26 (UTC) through the shared paced helper, which serializes GitHub's search limits across agents. The queries are in `searches/q-batch1.json` to `q-batch5.json`. `searches/searches.txt` lists each query with its total and the hits it showed, and `searches/raw/` keeps the responses.

- There were 71 queries, and none failed:
  - 36 issue searches, over the trackers of codeigniter4/CodeIgniter4, codeigniter4/queue, bcit-ci/CodeIgniter, OSPOS, Castopod and absensi-sekolah-qr-code, and over GitHub at large;
  - 35 code searches.
- Code search is GitHub's legacy engine: totals count files where the tokens co-occur, including vendored copies of CodeIgniter's `system/` folder. That is why the samples use `path:app` and exclude those copies. The top hits are ranked, not random.
- I read 69 application files at their commits, 20 `app/Config/Database.php` files, and each sampled project's `composer.lock` for its CodeIgniter version.
- I read CodeIgniter 4's source and guide at v4.2.12, v4.3.0, v4.6.4, v4.6.5, v4.7.0, v4.7.5, `develop` (`699fc2f86a`) and `4.8` (`10ea628d0a`); CodeIgniter 3 at 3.1.13; codeigniter4/queue at `4b444640c3`; and OSPOS at its tags 3.3.9 to 3.4.3.
- I read MySQL 8.4's manual pages on deadlocks, InnoDB error handling, locks and `wait_timeout`.
- PPCS's evidence was read from `origin/main` at `292336f`.
