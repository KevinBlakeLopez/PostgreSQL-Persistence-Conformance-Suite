# Production relevance of findings that had no section

Assessed 2026-10-26. Searches ran 2026-10-27 02:17–02:35 UTC. Written by: Grok 4.7.

This page is the search record for the findings [`docs/production-relevance.md`](../../docs/production-relevance.md) listed as unsearched on 2026-10-26: unfiled drafts, the studies' findings, and suite FAILs that were never filed. A suite FAIL stays a counterexample to an invariant. Here each unfiled FAIL is rated as a finding, and rows that share a trigger share one section.

The Python tracker and the [filed-items page](../filed-items-production-relevance/README.md) are not re-rated. Knex's unfiled draft restates knex#6547 (K1). Uvicorn discussion #3232 is the lifecycle study's F1 (U1). Procrastinate's draft is PY-25. The psycopg2 and asyncpg follow-up drafts are PY-1b and PY-2; the asyncpg follow-up was retired on 2026-10-26.

This is a desk assessment. Nothing was run, posted, or sent. Third-party behavior described below is either a recorded PPCS or study run, or source reading already in those records. Issue bodies were opened only where this page says they were opened. A title sample is a title sample.

Raw query output is in `queries.json`, `queries-2.json`, `queries-3.json`, and `searches/`.

## Tiers (judgment, 2026-10-26)

The tiers follow the filed-items page. They weigh likelihood and whether the outcome is silent. They change no severity and no status.

- **Higher:** none. No production report names one of these silent outcomes on the library that has it.
- **Middle, lower edge:** SQLite F1; MySQL `laravel.caught-1213-return`; Dramatiq F2. Hypercorn's F3 is moderate for a timeout that does not bound shutdown, and the harm is a slow shutdown.
- **Lower:** the unfiled false-commit rows, the other SQLite and MySQL findings, HikariCP F-H2, the PHP `PDO::commit` draft, Dramatiq F1, F3, and F4, the unfiled migration rows, and MikroORM's two TX-04 rows.
- **No production trigger:** the category C savepoint and pool rows. Our runs produced them by withholding a statement or rewriting a savepoint name.

## Already rated, so not searched again

| Finding | Where it is rated |
| --- | --- |
| Lucid TX-01A, TX-01B connection loss, TX-01B lost reply, the injected savepoint row | L2 on the filed-items page. Case 3 is the injected savepoint |
| Lucid TX-05 | L1 |
| Lucid `MG-03.no-reversal` | L5 |
| TypeORM TX-01A | T3 |
| TypeORM pool release after a failed rollback | T2 |
| TypeORM concurrent nested transactions | T1 |
| MikroORM TX-01A | M3 |
| MikroORM failed savepoint rollback | M2 |
| MikroORM migration slot | M4 |
| Drizzle and Prisma TX-01A | D1 and PI1. Both filings leave the failed-rollback pool release out, so those TX-03 rows are rated below |
| GORM and pgx TX-01A | The matrix PASS. `Commit` returns `ErrTxCommitRollback` |
| SQLAlchemy ORM TX-01A | INCONCLUSIVE. The flush rolls back before the commit |

## S1. Spring `afterCommit`

Draft: [`spring-framework.md`](../production-reachability/upstream-drafts/spring-framework.md). Not filed. Spring JDBC and Spring transaction management both FAIL `TX-01A.caught-error-then-commit`.

**Consequence.** `Connection.commit()` returns, `afterCommit` runs, and `afterCompletion` is `STATUS_COMMITTED`, while the transaction is aborted and the marker is absent. The caller is not given an exception from `commit()`. Hook counts are the first repetition. Three repetitions agree on the return, the aborted fate, and the absent marker. Same-backend reuse is the pooled rows only. The draft does not claim a command tag.

**Triggers.**

- Caught `23505`, then the transaction API returns. In production, unique violations occur; whether an application catches one inside `TransactionTemplate` or `@Transactional` and treats the return as success is unknown from this search. In our runs, a real PostgreSQL error through the ordinary API (category A). Code shape: catch the statement error inside the transaction and continue to the commit. A reasonable transaction would let that error leave the transaction. Real-world evidence: none with this split. The driver half is J1 (pgjdbc#4494), already rated low.
- `TransactionTemplate` with `PROPAGATION_NESTED`: the four recorded rows committed the outer row. That is the contained savepoint outcome. The declarative nested row is INCONCLUSIVE (`25P02`, not `23505`).

**Reproduced on real code.** No.

**Searches.** 2026-10-27 02:17 UTC. `repo:spring-projects/spring-framework afterCommit rollback`: 8 issues, all 8 titles read, 0 are this split. `org:spring-projects afterCommit caught DataAccessException`: 1 issue, spring-framework#7582 (2006, closed), an `EntityManager` commit exception swallowed by Spring. Title only. The body was not opened.

**Likelihood (judgment, 2026-10-26).** Low. The trigger is a real constraint error. The catch-and-continue shape was not found in this search, and J1's earlier code sample on the filed-items page found the silent shape in 0 of the inspected Java hits.

**Not established.** How often applications catch inside the transaction. Whether `PgConnection.getTransactionState()` was `FAILED`: the run did not log it. A command tag. Frequency.

## Unfiled false commit after a caught PostgreSQL error

These are category A. The application catches `23505` and the commit API reports success. The marker is absent. They were not filed. S1 is the Spring row of the same family.

### SQLx `Transaction::commit` returns `Ok`

Draft: [`adapters/sqlx/upstream-draft.md`](../../adapters/sqlx/upstream-draft.md). SQLx 0.9.0. `explicit`, `managed`, and `direct` all FAIL `TX-01A` with the mechanism exercised. The proxy logged `COMMIT -> ROLLBACK`. `PgTransactionManager::commit` returns `Ok` when `execute` returns `Ok` and does not read the tag (draft, source reading of 0.9.0).

**Consequence.** The call returns `Ok`. The row is absent. `pg_xact_status` was `aborted`.

**Triggers.** Caught `23505`, then `commit`. In production, unknown for this tag. In our runs, a real PostgreSQL error through the ordinary API. Code shape: catch the unique violation inside the transaction and commit. A reasonable design lets the error leave the transaction. Real-world evidence: none in the title sample.

**Reproduced on real code.** No.

**Searches.** `repo:launchbadge/sqlx` is not searchable (HTTP 422 on 2026-10-27). `repo:transact-rs/sqlx commit ROLLBACK transaction`: 37 issues. The first 6 titles were read. 0 of 6 are a Postgres `commit` that returns `Ok` on the tag `ROLLBACK`. Nearby titles, not opened: #4445 (a failed nested `begin()` rolls back the enclosing transaction), #4434 and #4473 (SQLite `SQLITE_FULL` or an automatic rollback leaves a stale transaction depth), #3875 (a started transaction that may not commit or roll back).

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** An application that catches inside a SQLx transaction and checks only `Ok`. The other 31 issues in that search.

### SQLx `direct-drop` fails `CTL-01.rollback`

Not in the commit draft. Dropping the `Transaction` queued `ROLLBACK`. The proxy did not see it sent. At `after-end` the transaction was still in progress. Pooled `drop` passed. Run `2026-10-22T18-40-05Z-7b77ec`.

**Consequence.** A direct connection can still be inside a transaction after the guard is dropped. The caller is not told that a rollback completed.

**Triggers.** Dropping the transaction value. In production, unknown. In our runs, the ordinary drop path, no injected fault. Code shape: the transaction goes out of scope on a connection that is not pooled. That is ordinary Rust. Real-world evidence: #3875's title is adjacent and was not opened.

**Reproduced on real code.** No.

**Searches.** The transact-rs search above. It was not a query for `Drop`.

**Likelihood (judgment, 2026-10-26).** Low. Pooled drop passed, and a pool is the usual production setup.

**Not established.** Whether the queued rollback arrives later, after the harness's `after-end` point.

### jOOQ `DSLContext.transaction`

Draft: [`adapters/jooq/upstream-draft.md`](../../adapters/jooq/upstream-draft.md). Not filed. Do not open a second pgjdbc issue. Both `native` and `jdbc` FAIL `TX-01A`. `Connection.commit()` returned. The marker was absent. Listeners saw `commitEnd` and no rollback listener.

**Consequence.** The callback returns and jOOQ reports the commit. The first insert is gone. The driver half is J1.

**Triggers.** Caught `DataAccessException` (`23505`) inside the callback. In production, unknown for this return. In our runs, category A. Code shape: catch inside `transaction()` and return. A reasonable design lets the exception leave the callback, which is the path the draft's probe recorded as a rollback. Real-world evidence: jOOQ#20138 (open, 2026-08-17, user report) is a dead connection whose nested rollback throws and poisons `ThreadLocalTransactionProvider`. The next transaction fails. Body opened. It is a loud leftover, and it is a different trigger.

**Reproduced on real code.** No.

**Searches.** `repo:jOOQ/jOOQ transaction catch commit unique`: 3 titles, 0 this split. `repo:jOOQ/jOOQ setAutoCommit rollback commit`: 6 titles. #20138 was opened. 0 of those titles are the silent `commit()` return.

**Likelihood (judgment, 2026-10-26).** Low, the same judgment as J1.

**Not established.** A jOOQ application that catches inside the callback.

### Hibernate `commit()` after Hibernate sent `ROLLBACK`

Hibernate ORM 7.4.13.Final. The only framework FAIL is `TX-01A`. `commit()` returned after Hibernate had sent `ROLLBACK` and had not sent `COMMIT`. The mechanism check is null because the backend was gone at `after-end`. Run `2026-10-21T15-45-57Z-c3c03b`. No draft.

**Consequence.** The commit API returns after a rollback was sent. The row is absent. The caller is not shown a commit error from that return. This is a different path from a `COMMIT` tag of `ROLLBACK`.

**Triggers.** Caught error, then `commit()`, with the session marked so Hibernate rolls back. In production, unknown. In our runs, category A. Code shape: catch the persistence exception and still call `commit()`. A reasonable design lets the exception mark the transaction and then treats `commit()` as the failure. Real-world evidence: none in this search. hibernate-orm#12298 and #12173 (titles) are `afterTransactionCompletion` when a commit fails. That is the loud path.

**Reproduced on real code.** No.

**Searches.** `repo:hibernate/hibernate-orm catch commit rollback-only`: 3 pull requests, titles read. `repo:hibernate/hibernate-orm rollback-only commit returned`: 0.

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** The command tag, which the run could not log. How often callers invoke `commit()` after catching.

### Active Record `transaction` and `after_commit`

Active Record 8.1.4 FAIL `TX-01A`, mechanism exercised. Run `2026-10-23T21-46-47Z-b3b7bd`. The transaction-callbacks study records that a model `after_commit` ran, and that the Rails guide warns against rescuing `StatementInvalid` inside the block. No draft.

**Consequence.** The transaction API reports a commit, the earlier write is absent, and `after_commit` can run for that ending.

**Triggers.** Rescuing the statement error inside the transaction block, then committing. In production, unknown for the silent ending. In our runs, category A. Code shape: `rescue` inside the open transaction. The guide tells the reader to keep that rescue outside. Real-world evidence from the code sample is the outside rescue.

**Reproduced on real code.** No.

**Searches.** `repo:rails/rails rescue RecordNotUnique transaction commit`: 9 issues, 5 titles read, 0 are a commit reported after an aborted transaction. `repo:rails/rails "current transaction is aborted"`: 19. rails#58288 was opened: a deadlock in `before_commit` leaves the connection aborted. That is a leftover aborted session, and the report is the deadlock. Code: `rescue ActiveRecord::RecordNotUnique language:Ruby`, 12192 hits. 8 snippets inspected. 2 files opened, and both catch outside the transaction. `fjordllc/bootcamp` `app/models/report.rb` at `d1a86a3127`, lines 149–156: `rescue` is outside `transaction do`. `instructure/canvas-lms` `app/models/user.rb` at `1c9f0bb801`, lines 911–914: `rescue` is outside `transaction(requires_new: true)`. The other 6 snippets do not show a transaction block around the rescue. They were not opened. 0 of 2 opened files are the silent shape.

**Likelihood (judgment, 2026-10-26).** Low. The inspected applications catch outside the block, which is the shape the guide describes.

**Not established.** A count of rescues that are inside the block. The other 4 issue titles in the first query, and the other 13 in the second.

### Laravel on PostgreSQL, `TX-01A`

Laravel FAIL `TX-01A`, mechanism exercised. This is the PostgreSQL suite row. The MySQL study is a different finding, below. No draft for this row.

**Consequence.** `DB::transaction()` reports success. The marker inserted before the caught error is absent.

**Triggers.** Catching the query exception inside the closure and returning. In production, the loud form is reported: laravel/framework#48143 (closed, 2023, user) describes `createOrFirst()` leaving `25P02` for later statements in the same PostgreSQL transaction. Body opened through the first paragraphs. Later statements fail. That is the opposite of a commit that returns success. In our runs, category A, and the commit path reported success. Code shape: catch inside the closure. Laravel's own `createOrFirst()` catches a duplicate key. Real-world evidence of the silent commit: none in this search.

**Reproduced on real code.** No. #48143 was not re-run.

**Searches.** `repo:laravel/framework transaction catch commit unique`: 7 titles, including #61964 and #61829, which the MySQL study already cites for other mechanisms. `repo:laravel/framework "current transaction is aborted"`: 8. #48143 opened. 0 of those titles are a commit reported as success after `23505`.

**Likelihood (judgment, 2026-10-26).** Low for the silent commit. The continue-after-error shape exists in Laravel's own code and shows up as `25P02`.

**Not established.** Whether any of the 8 aborted-transaction issues ends in a successful `commit()` that the reporter treated as a commit.

### EF Core `execute-sql`

EF Core 10.0.13. Native `TX-01A` is INCONCLUSIVE: `SaveChangesAsync` keeps the transaction open after a caught unique violation, and the earlier marker commits. `execute-sql` FAILs: `CommitAsync` returns and PostgreSQL aborted the transaction. Run `2026-10-21T20-00-07Z-cff349`. No draft.

**Consequence.** For `ExecuteSql`, the commit API returns and the write is gone. For `SaveChangesAsync`, the transaction stays open and the earlier write can still commit. Those are different outcomes. The silent one is `execute-sql`.

**Triggers.** Caught unique violation, then `CommitAsync`, on the execute-sql path. In production, unknown. In our runs, category A. Code shape: raw SQL inside a transaction, catch, commit. Real-world evidence: none in the title sample. dotnet/efcore#36470 (closed, title only) is a change-tracker state after a successful insert in a failed batch. The body was not opened.

**Reproduced on real code.** No.

**Searches.** `repo:dotnet/efcore ExecuteSql Commit unique violation`: 1 issue, #26480, a SQLite lock, unrelated. `repo:dotnet/efcore ExecuteSqlRaw transaction commit`: 11 issues, 5 titles read, 0 are this return.

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** How often applications commit after catching around `ExecuteSql`. The native path's open transaction, which is a different finding and was not searched on its own.

### Tortoise suite `TX-01A`

Tortoise FAIL `TX-01A`. The runner records `mechanism_exercised` false, because `in_transaction()` releases the connection and the last statement at `after-end` is the pool reset. The API still reports a commit after PostgreSQL had aborted the transaction. This is not PY-3. PY-3 is a later `save()` that writes nothing, and it is already rated.

**Consequence.** The transaction API reports a commit. The marker is absent. The connection is released back through the pool reset.

**Triggers.** Caught error, then the transaction helper returns. In production, unknown for this suite row. In our runs, category A. Code shape: catch inside `in_transaction()` and return normally. Real-world evidence: not searched separately from the Python tracker's PY-3 search. This pass did not repeat that search.

**Reproduced on real code.** No.

**Searches.** Not a new query. PY-3's search is the nearest record and it is a different finding.

**Likelihood (judgment, 2026-10-26).** Low, carried from the same catch-and-continue shape. The absence of a new search is part of the judgment's limit.

**Not established.** A Tortoise application that returns normally from `in_transaction()` after catching a database error. The command tag, which this row did not log.

### SQLAlchemy Core `TX-01A`

SQLAlchemy Core FAIL `TX-01A`, mechanism exercised. The 2026-10-19 reachability run logged psycopg's status moving `INERROR` to `IDLE` on `COMMIT`. That caller is named in psycopg#1453 (PY-1a), which is rated in the Python tracker. There is no separate SQLAlchemy issue.

**Consequence.** `commit()` returns. The transaction is aborted. The marker is absent. The driver is the filed finding.

**Triggers.** Caught `IntegrityError`, then `commit()`. In production, the Python tracker's rating of PY-1a. In our runs, category A. Code shape: catch and commit on a Core connection. Real-world evidence: the tracker, not a new sample.

**Reproduced on real code.** No new run.

**Searches.** `repo:sqlalchemy/sqlalchemy IntegrityError commit postgresql transaction`: 10 issues, 6 titles, 0 this split. `repo:sqlalchemy/sqlalchemy "current transaction is aborted" commit`: 0. The SQLite study's searches are a different database.

**Likelihood (judgment, 2026-10-26).** Low, the same judgment as PY-1a. This row does not get a second tier.

**Not established.** Anything the Python tracker marks not established for PY-1a.

## Category C savepoint rows

`TX-02.savepoint-rollback-not-sent` and `TX-02.savepoint-rollback-rejected` are client-side injections. The first withholds `ROLLBACK TO SAVEPOINT`. The second rewrites the savepoint name so the statement fails. They show a path. They are not a frequency.

Lucid's injected savepoint case is L2 case 3, already rated, with no production trigger. MikroORM's failed-savepoint filing is M2, already rated. The rows below were not filed.

**Not-sent FAILs** (the outer API reports a commit, PostgreSQL commits, both markers are visible): Lucid (already rated), MikroORM, TypeORM, Django, SQLAlchemy, SQLAlchemy Core, Tortoise, Spring JDBC, Spring TX, Drizzle, Prisma, Laravel, Active Record, EF Core, jOOQ, and all four Go modes in the 2026-10-22 recording (pgx, `database/sql`, GORM managed, GORM explicit). SQLx PASSes. Hibernate does not run the case.

**Rejected FAILs** (the API reports a commit of a transaction PostgreSQL aborted): the same list, except Django PASSes, GORM PASSes because `Commit` returns `ErrTxCommitRollback`, SQLx PASSes, and Hibernate does not run it. MikroORM's rejected row is M2.

**Consequence.** Not-sent: both the outer and the nested writes remain, and the API reports a commit. Rejected: the API reports a commit and neither marker remains. GORM's extra observation, in [`adapters/gorm/UPSTREAM.md`](../../adapters/gorm/UPSTREAM.md): `RollbackTo().Error` is nil when the savepoint statement failed. On the rejected catalog row, `Commit` still returns `ErrTxCommitRollback`, so the caller is told at commit. On the not-sent row, the outer `Transaction` returns nil and both markers commit.

**Triggers.** One trigger: the runner does not send the savepoint rollback, or it changes the name. In production, unknown. Nothing in this search is that injection happening on its own. In our runs, category C. Code shape: a nested transaction whose caller catches the inner error and commits the outer one. That shape is ordinary. The failure of the savepoint statement is the part our runs manufactured. Real-world evidence: mnemosyne-oss/mnemosyne#888 (open, 2026-08-30) quotes production logs, 26 traceback chains in 7 days, `no such savepoint: degrade_row` on SQLite, after which the run continues. Body opened through the summary. The cause is not established, and it is SQLite, so it is recorded under F1's searches. It is not a PostgreSQL category C incident. jOOQ#20138, opened above, is a dead connection during a nested rollback. The next transaction fails loudly.

**Reproduced on real code.** No.

**Searches.** `"rollback to savepoint" catch commit` returned 2997 issues. The first page is dominated by this repository's own filings. That total is not an exposure count. `"no such savepoint" commit`: 254. The first 6 titles were read. One, mnemosyne#888, was opened. `repo:go-gorm/gorm RollbackTo savepoint`: 5 titles, 0 are `Error == nil` after a failed savepoint. `repo:go-gorm/gorm savepoint rollback commit`: 2 titles, neither is that.

**Likelihood (judgment, 2026-10-26).** No production trigger for the injected statement. Low for the ordinary nested-catch shape producing this ending on its own.

**Not established.** A production report of a PostgreSQL `ROLLBACK TO SAVEPOINT` that failed, or was skipped, and an outer commit that then persisted both units.

## Category C pool rows

`TX-03.rollback-not-sent` and `TX-03.statement-error-rollback-not-sent` withhold `ROLLBACK`. On the pooled FAILs, a later unit can commit work that belonged to the failed unit, or the pool's cleanup commits it.

TypeORM's filed form is T2. Kysely's is Y1. Knex's is K2. Those stay on the filed-items page.

**Unfiled FAILs of `TX-03.rollback-not-sent`:** Lucid, MikroORM, Spring JDBC pooled, Spring TX pooled, Drizzle, Prisma, Laravel, jOOQ pooled. Django's persistent mode PASSes. SQLAlchemy, Core, Tortoise, Active Record, EF Core pooled, GORM, SQLx, and Hibernate pooled PASS.

**Unfiled FAILs of `TX-03.statement-error-rollback-not-sent`:** Lucid, MikroORM, Drizzle, Prisma, Laravel. Spring's pooled rows PASS this variant. jOOQ's statement-error variant keeps the row absent. The jOOQ draft records the mechanism for the withheld rollback: `setAutoCommit(true)` runs from `brace`, and pgjdbc's `setAutoCommit(true)` issues `COMMIT` while autocommit is off. xid 33585 committed and the doomed row was visible. `transaction()` had rethrown, so the application-facing result was a rollback. `jdbc-pooled` closes instead, HikariCP sent `ROLLBACK`, and that case passed. The same cleanup is Spring's pooled TX-03 ending.

Drizzle's and Prisma's filed issues say this pool release is not part of those issues.

**Consequence.** A connection goes back to the pool, or has autocommit restored, while the transaction is still open, and PostgreSQL then commits it. The application saw a rollback error or a thrown callback. The durable outcome can still be a commit.

**Triggers.** The runner does not send `ROLLBACK`. In production, unknown. In our runs, category C. Code shape: the framework's cleanup after a rollback that threw. The throw is injected. Real-world evidence: none of a withheld rollback. jOOQ#20138 is the loud cousin, a rollback that did throw because the connection died.

**Reproduced on real code.** No.

**Searches.** The jOOQ `setAutoCommit` search above. No separate code search for `setAutoCommit(true)` after a failed rollback. The broad savepoint search is not reused as a count.

**Likelihood (judgment, 2026-10-26).** No production trigger for the withheld statement. Low for the cleanup path once a rollback has thrown for a real reason. That real reason was not produced in these rows.

**Not established.** A production pool that committed an open transaction because `rollback()` threw.

## MikroORM TX-04, native

MikroORM 7.2.5. Fault: none. `clear-forks` PASSes both rows. Run recorded in `reports/examples/2026-10-24T14-19-00Z-4f477e`. Not filed. M3 and M4 are other findings.

**Consequence.**

- `TX-04.nested-failure-contained`: `em.transactional` with a nested `em.transactional` resolves. xid 3147 committed. The outer marker and the inner marker are both absent. The outer write was still pending in the unit of work. The caller handled the nested error and was told the outer transaction committed, without the outer write.
- `TX-04.independent-inner`: the outer API rejects with the callback's error. The inner `REQUIRES_NEW` transaction committed, and the outer marker was inserted by that inner transaction (xid 3210). The caller is told the outer transaction rolled back. The pending outer write went with the inner one.

**Triggers.** Ordinary nested `em.transactional`, with the outer write left pending, which the case summary describes as ordinary MikroORM code. In production, unknown. In our runs, no injected fault. Code shape: nest `em.transactional` around work that has not been flushed. A developer following the default propagation would write this. Real-world evidence: mikro-orm#2668 (2022, closed, title only) says transaction scope differs from the docs. The body was not opened. #8476 is our own filing of the caught-commit bug, a different finding.

**Reproduced on real code.** No.

**Searches.** `repo:mikro-orm/mikro-orm nested transactional flush savepoint`: 2 issues. Titles read. 0 of 2 are the pending-write loss.

**Likelihood (judgment, 2026-10-26).** Low. The code shape is ordinary nested use. No report of this loss was in the two-issue sample.

**Not established.** How often applications nest `em.transactional` with an unflushed outer entity. The body of #2668.

## Migration rows that were not filed

### `MG-02` without an advisory lock

FAIL on Django, TypeORM, Drizzle, and Laravel for `MG-02.held`, `MG-02.session-loss`, and `MG-02.idle-session-timeout`. Two runners are inside the migration at once. On the held and idle cases the marker count and the history count are 2. MikroORM's migration finding is M4, already rated. Lucid's unreleased regression is L3, already rated. Version 1.1 of `MG-02.first-deployment` PASSes these frameworks: one runner applies, the other fails on the history table's unique violation.

**Consequence.** Two overlapping `migrate` processes can both apply a migration. Session loss: the second runner enters while the first is still inside.

**Triggers.** Two migrators at once, and a migrator that takes no advisory lock. In production, concurrent deploys happen; this search did not find a report of a double apply on these four. In our runs, no injected fault. The runners are started together. Code shape: the framework's migrate command as the suite calls it. Laravel's `MigrateCommand` implements `Isolatable`. The suite calls `Migrator::run()` the way `php artisan migrate` does without `--isolated`. Real-world evidence: none in the title sample. L3's filed note says AdonisJS's deployment guide documents concurrent runners. That is a different project.

**Reproduced on real code.** No.

**Searches.** `repo:django/django migrate advisory lock concurrent` and `repo:django/django "advisory lock" migrations`: 1 issue each, django#18408, an async-connections pull request. Title only. 0 of 1 are a double migrate.

**Likelihood (judgment, 2026-10-26).** Low. A single migrator is the usual deploy. `--isolated` exists on Laravel and was not the measured command.

**Not established.** How often two processes run these migrators together. A Django ticket that uses different words.

### Laravel `MG-03.no-reversal`

`rollback()` reports reverted, the history row is deleted, and the marker remains. `runMigration()` skips a missing `down()`, and `runDown()` still calls `repository->delete()`. Lucid's same ending is L5, already rated. The filed page cites laravel/framework#57429 as a Laravel contributor describing that behavior.

**Consequence.** The history says the migration was reverted. The schema change is still there.

**Triggers.** A migration with no `down()`, then `migrate:rollback`. In production, migrations without `down()` exist. In our runs, no injected fault. Code shape: omit `down()`. Laravel allows that. Real-world evidence: the contributor comment already cited for L5. This pass did not re-open #57429.

**Reproduced on real code.** No.

**Searches.** `repo:laravel/framework migration rollback missing down method`: 6 issues, 5 titles. laravel#37246 (closed pull request, 2021) proposes throwing when a migration method is missing. 0 of 5 titles are a rollback that deletes history while leaving the schema.

**Likelihood (judgment, 2026-10-26).** Low, the same judgment as L5.

**Not established.** Whether #57429's comment is this `down()` skip. It was not re-read.

## TypeORM findings with no draft

The tracker rows in `docs/upstream-submissions.md` section 3.6. The experiment write-up is in a private repository. This page uses the tracker's one-line description and does not restate measurements that are not in PPCS.

### A rollback error vanishes in `catch (rollbackError) {}`

**Consequence.** The documented manual pattern loses the original error. The tracker names experiments TR1d, TR1d3, and TR4a. T2, the pool release, was filed separately as typeorm#12978.

**Triggers.** A rollback that throws, and an empty `catch`. In production, unknown. In our runs, not re-read from PPCS case files this pass. Code shape: the empty catch the tracker calls the documented manual pattern. The pattern text was not opened here. Real-world evidence: none.

**Reproduced on real code.** No.

**Searches.** `repo:typeorm/typeorm rollbackError swallowed`: 1 pull request, #12335, Spanner isolation. Unrelated.

**Likelihood (judgment, 2026-10-26).** Low, with a narrow search.

**Not established.** The manual pattern's exact code. Whether the original error is reachable by another path. Application copies of the empty catch.

### `@VersionColumn` writes a stale version back

**Consequence.** The tracker says an update is lost silently. Experiment TC1a.

**Triggers.** A version column and a stale write. In production, unknown. Code shape: not re-read. Real-world evidence: typeorm#3608 (2019, closed) was opened. It is a question about how optimistic concurrency is implemented, with a two-user invoice example. It does not report a stale version written back.

**Reproduced on real code.** No.

**Searches.** `repo:typeorm/typeorm VersionColumn stale`: 18 issues, 5 titles, 0 this loss. `repo:typeorm/typeorm VersionColumn optimistic lock lost update`: 1, #3608, opened.

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** The TC1a procedure, which is not in this repository. A code search of applications.

### A subscriber without `@EventSubscriber()` is dropped

**Consequence.** The subscriber is dropped without a warning. Experiment TT5a. Hooks that the author expected do not run.

**Triggers.** Forgetting the decorator. In production, unknown. Code shape: a subscriber class that is not decorated and not registered another way. A reader of the decorator docs would add it. Real-world evidence: none.

**Reproduced on real code.** No.

**Searches.** `repo:typeorm/typeorm EventSubscriber not registered`: 3 titles, 0 are a missing decorator with no warning.

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** Other ways TypeORM registers subscribers. A code search.

## SQLite study

Findings: [`../sqlite-transaction-state-divergence/findings.md`](../sqlite-transaction-state-divergence/findings.md). Nothing filed. The 2026-10-25 duplicate search is [`../sqlite-transaction-state-divergence/upstream/duplicate-search.md`](../sqlite-transaction-state-divergence/upstream/duplicate-search.md). It found no report of F1, F3, or F4. This pass adds the samples below and does not repeat that query list.

F7 is the study's list of which SQLite errors end a transaction. It is classified C there. It is the trigger list for F1–F6, not a separate framework finding. N1–N9 are the cases that held. They are not rated.

### F1. Documented savepoint loop, commit returns, earlier rows absent

**Consequence.** With SQLAlchemy's documented `begin_nested()` loop and the documented SQLite `BEGIN` recipe, `session.commit()` returns. The application counts the records after the failing one as committed. An independent connection sees only those later records. The records before the failure are absent. Under `autocommit=False` (F1′) the commit raises `cannot commit - no transaction is active`, and the records after the failure are already committed, so a retry of the batch can write them twice.

**Triggers.**

- A full disk, a page cap, `ON CONFLICT ROLLBACK`, or `RAISE(ROLLBACK)`, during the loop. In production, a full disk is a real `ENOSPC` (the study reproduced it). It is uncommon. `ON CONFLICT ROLLBACK` is a schema choice. In our runs, those real SQLite endings, through the ordinary API. Code shape: the loop in SQLAlchemy's ORM guide, including the bare `except`. A developer who copies the guide writes it. Real-world evidence: the 2026-10-25 search found none of this commit. mnemosyne#888, opened this pass, is a production count of `no such savepoint` (26 chains in 7 days) after which the job continues and tier state is not tracked. The summary does not say `commit()` returned success, and it does not name SQLAlchemy.
- sqlx issues #4434 and #4473 (titles only) report SQLite `SQLITE_FULL` or an automatic rollback leaving a stale transaction depth. Another library, same family of "SQLite ended the transaction and the client did not notice." Bodies not opened.

**Reproduced on real code.** The study ran SQLAlchemy's documented loop. It did not run mnemosyne.

**Searches.** The 2026-10-25 log. This pass: `sqlalchemy savepoint "database or disk is full" commit`: 0. `begin_nested language:Python except`: 94080. The first 8 hits are libraries defining `begin_nested`, not an application loop. 0 of 8 are the guide's loop. That total counts the two words. It is not a count of copies of the guide.

**Likelihood (judgment, 2026-10-26).** Low to moderate. The code shape is the documented example. The trigger is uncommon, and no report of the false commit was found.

**Not established.** How many applications copy the loop. Whether mnemosyne's 26 incidents lost committed rows. Frequency of `ENOSPC` on SQLite deployments.

### F2. Caught transaction-ending error, then a reported commit

**Consequence.** After a caught `IntegrityError` from `RAISE(ROLLBACK)` or `ON CONFLICT ROLLBACK`, a later write commits on its own, and `commit()` returns. `after_commit` fired. The earlier writes are absent.

**Triggers.** Catch the error and keep writing. In production, unknown. In our runs, a real SQLite rollback-class error. Code shape: catch and continue, which the study says Core permits for statement-level errors. The error here ended the transaction, and the exception does not say so. Real-world evidence: sqlalchemy#5968 is `ON CONFLICT IGNORE`, a different resolution. The maintainer said the ORM expects an insert to succeed or raise. Cited from the 2026-10-25 search.

**Reproduced on real code.** No application. The minimal reproduction is the study's.

**Searches.** The 2026-10-25 log. No new F2-only query.

**Likelihood (judgment, 2026-10-26).** Low. Continuing after a caught database error is plausible. The rollback-class conflict is the uncommon part.

**Not established.** An application that uses `ON CONFLICT ROLLBACK` and catches the `IntegrityError`.

### F3. `Session.close()` keeps the pooled connection

**Consequence.** After an error that ended the transaction, `Session.close()` raises and the pooled connection stays checked out until garbage collection. Later checkouts time out.

**Triggers.** `autocommit=False`, which the study says CPython and SQLAlchemy recommend, plus an error that ends the transaction. In production, unknown. In our runs, that mode and a real ending error. Code shape: `with Session(engine)` around a statement that hits the error. Ordinary. Real-world evidence: sqlalchemy#13657 is the same leak after a failed `BEGIN` on asyncpg, fixed in `d29277af`. The SQLite path was not that issue. Cited from the 2026-10-25 search.

**Reproduced on real code.** No.

**Searches.** The 2026-10-25 log.

**Likelihood (judgment, 2026-10-26).** Low. The mode is recommended. The trigger is uncommon. The symptom is a timeout, which is loud.

**Not established.** A production pool timeout blamed on this close path.

### F4, F5, F6. `autocommit=False` after SQLite ends the transaction

**Consequence.** F4: `sqlite3` does not keep a transaction open. `commit()` and `rollback()` raise `no transaction is active`, and the next unit's write commits even if the caller then rolls back. F5: the error that reaches the application is `cannot rollback - no transaction is active`. The original error is on `__context__`. F6: the pooled connection is handed out with that state. Later `commit()` and `rollback()` raise until a pool reset fails.

**Triggers.** Any error that ends the transaction, under `autocommit=False`. In production, the mode is the recommended one. The ending errors are the F7 list. In our runs, `RAISE(ROLLBACK)` and `ON CONFLICT ROLLBACK`. Code shape: use the recommended autocommit mode. Real-world evidence: CPython gh-112441 (2023, closed as not planned). A maintainer said `autocommit=False` means a transaction is always open. That issue was user-issued `BEGIN`/`COMMIT`, which the 2026-10-25 note distinguishes from SQLite's own rollback. sqlalchemy#12585 (open, title only, this pass) is "support SQLite `.autocommit=False`".

**Reproduced on real code.** No.

**Searches.** The 2026-10-25 CPython and SQLAlchemy logs. This pass did not add a CPython query.

**Likelihood (judgment, 2026-10-26).** Low to moderate for F4's broken invariant once an ending error happens. Low for how often that error happens. F5 and F6 follow F4.

**Not established.** A production report of `cannot rollback - no transaction is active` after `SQLITE_FULL` or a rollback-class constraint.

### Side observation. `after_commit` on savepoint `RELEASE`

The study's source reading: SQLAlchemy dispatches `after_commit` on every savepoint `RELEASE` as well as on the outer commit (`orm/session.py` 1332–1340 at the version the study read). The docstring does not say so.

**Consequence.** A hook the caller treats as "the transaction committed" can run when a savepoint is released.

**Triggers.** A savepoint release. In production, unknown. In the study, observed in the batch sink. Code shape: use `begin_nested()` and `after_commit`.

**Reproduced on real code.** No.

**Searches.** Not assessed. No query this pass.

**Likelihood (judgment, 2026-10-26).** Not assessed. The observation is source reading plus the study's sink.

**Not established.** Whether applications bind durable work to `after_commit` inside a savepoint loop.

## MySQL study

Findings: [`../mysql-transaction-state-divergence/findings.md`](../mysql-transaction-state-divergence/findings.md). Laravel 13.38.0, MySQL 8.4.11. Nothing filed. F1 is the study's classification A. O1–O3 need `innodb_rollback_on_timeout=ON` except where a deadlock is named. Section 7 is the first run, kept as recorded and not analyzed further. This page does not analyze it further. It rates the recorded rows.

### F1. Nested `DB::transaction()` and errno 1205, server default OFF

**Consequence.** The inner call throws `DeadlockException`. `afterRollBack` runs for the inner unit. `ROLLBACK TO SAVEPOINT` is not sent. The savepoint and the inner rows are still in the open transaction. If the outer closure catches and commits, the inner rows commit, `DB::transaction()` returns normally, and `afterCommit:outer` runs. There is no `afterCommit:inner`.

**Triggers.** Lock wait timeout inside a nested `DB::transaction()`, caught by the outer closure. In production, lock waits occur (laravel#40574 and #14733 are reports of 1205). #14733 was opened: a 504 during `exec()` left a transaction open, and later requests hit 1205. The user had a `try` with `DB::rollback()`. The process died in the middle. That is a lock held by a live transaction, which is a different sequence from F1. In our runs, a real 1205 against a lock the observer held. Code shape: catch a nested `DB::transaction()`. The study says Laravel's `createOrFirst()` catches inside a nested transaction. That is source reading in the study, not re-read this pass. A duplicate key in the same place is rolled back to the savepoint (the study's control). Real-world evidence of the inner rows surviving: none in this search.

**Reproduced on real code.** The study's minimal reproduction. No application.

**Searches.** `repo:laravel/framework lock wait timeout nested transaction`: 0. `repo:laravel/framework "Lock wait timeout exceeded"`: 8, 6 titles read, #14733 opened. 0 of 6 are a nested savepoint that was not rolled back. `innodb_rollback_on_timeout language:PHP`: 603. The first 6 are configuration and documentation files. 0 of 6 are an application nested transaction.

**Likelihood (judgment, 2026-10-26).** Low to moderate. Lock waits are a known production error. The nested catch is a shape Laravel itself uses for duplicate keys. No report of the surviving inner rows was found.

**Not established.** An application log that shows inner rows committed after a nested 1205. MariaDB, MySQL 8.0, and 9.x, which the study did not run.

### O1. Explicit nested API, `innodb_rollback_on_timeout=ON`

**Consequence.** `DB::rollBack()` sends `ROLLBACK TO SAVEPOINT`, which fails with errno 1305 because InnoDB ended the whole transaction. The 1205 disappears from the error the caller sees. The level stays at 2. The next `DB::transaction()` can autocommit a single statement and run no `afterCommit`.

**Triggers.** The non-default server setting, plus the explicit nested API, plus a 1205. In production, the setting is off by default. In our runs, ON. Code shape: `DB::beginTransaction()` / `DB::rollBack()` around a nested unit. The study identifies laravel#61829 (open) as this state on SQL Server. This pass did not re-open it.

**Reproduced on real code.** No.

**Searches.** The 1205 searches above. They were not filtered to the ON setting.

**Likelihood (judgment, 2026-10-26).** Low, because the server setting is off by default.

**Not established.** How many deployments set `innodb_rollback_on_timeout=ON`.

### O2. Stale `afterCommit` after InnoDB rolls the outer transaction back

**Consequence.** The outer commit throws. The outer `afterCommit` runs at the next transaction's commit, for a transaction InnoDB rolled back.

**Triggers.** The managed nested form with ON, and also `laravel.nested-1213-caught` with the server default (a deadlock). In production, deadlocks occur. In our runs, a real 1205 or 1213. Code shape: nested `DB::transaction()`. The study identifies laravel#61964 (open) as this mechanism. This pass did not re-open the body. The title was in the Laravel search results.

**Reproduced on real code.** No.

**Searches.** The Laravel transaction search that listed #61964. No new query.

**Likelihood (judgment, 2026-10-26).** Low to moderate on the deadlock path, because that path uses the server default. Low on the 1205 path, because that path needs ON.

**Not established.** A production report that quotes an `afterCommit` side effect for the rolled-back transaction. The study did not claim one.

### O3. Single-level catch of 1205, setting ON

**Consequence.** The closure catches 1205 and returns. `DB::transaction()` returns normally. `afterCommit:tx` runs. The marker is absent. `PDO::commit()` returned true. The server had already rolled the transaction back.

**Triggers.** ON, plus catch inside a single `DB::transaction()`. In production, the setting is non-default. In our runs, ON. Code shape: catch and return, which is the same shape as the PostgreSQL false commit. Real-world evidence: none for this MySQL setting.

**Reproduced on real code.** No.

**Searches.** The 1205 searches. 0 of the opened titles are a successful `commit()` after InnoDB's full rollback.

**Likelihood (judgment, 2026-10-26).** Low.

**Not established.** Deployments with the setting ON whose closures catch 1205.

### First run, deadlock, server default

Recorded 3 of 3. Not analyzed further in the study. Rated from the table only.

| Row | What the table records |
| --- | --- |
| `pdo.caught-1213.commit` | `PDO::commit()` returned true after the session was the deadlock victim. The server recorded only the rolled-back transaction |
| `laravel.caught-1213-return` | `DB::transaction()` returned normally and `afterCommit:tx` ran. The marker is absent |
| `laravel.caught-1213` | An insert after the deadlock autocommitted. The commit threw. `afterCommit:tx` ran at the next commit (#61964) |
| `laravel.explicit-caught-1213` | `commit()` threw, `rollBack()` ran `afterRollBack`, and the insert after the deadlock had autocommitted |
| `laravel.escaped-1213` and the retry | Rollback and rethrow. The retry's second attempt committed |

**Consequence.** `laravel.caught-1213-return` is a success callback for a transaction the server rolled back, with the default deadlock behavior. The caller is not given an error from `DB::transaction()`. `pdo.caught-1213.commit` is the driver half of that return.

**Triggers.** A deadlock (errno 1213), caught inside the closure, then a normal return. In production, deadlocks are a known MySQL error. laravel#7046 (2015, title in the 1205 search) is a PDO deadlock with the database queue driver. Body not opened. In our runs, a real deadlock on the first run only. Code shape: catch inside `DB::transaction()` and return. The study says Laravel's documentation leaves that catch unspecified. Real-world evidence of the callback firing: none opened this pass.

**Reproduced on real code.** No.

**Searches.** No query named 1213. The deadlock titles that appeared inside the 1205 query were not a sample of deadlock reports. This field is thin on purpose.

**Likelihood (judgment, 2026-10-26).** Low to moderate. The server setting is the default, and a deadlock is a production error. The catch-and-return shape is the part this search did not find in an application. The study itself says the row was not pursued.

**Not established.** A second run. An application that catches 1213 and treats the return as a commit. The body of any deadlock issue.

## HikariCP F-H2

Study: [`../connection-pool-session-state/README.md`](../connection-pool-session-state/README.md) sections 8 and 10. Draft: [`hikaricp-failed-reset-recycled.md`](../connection-pool-session-state/upstream-drafts/hikaricp-failed-reset-recycled.md). Not filed. The pgjdbc `getSchema()` comment draft is the same study's note on #3005, which is already open. Do not file a second pgjdbc issue.

**Consequence.** A connection whose rollback or state reset failed is returned to the pool. The study's impact note: reads can come from an old snapshot; later transactions can run `SERIALIZABLE` on a pool configured for `READ COMMITTED`; a read-only leftover fails later writes while validation passes; a leftover schema sends unqualified writes to the previous borrower's schema. The study says F-H2 produced no false write success.

**Triggers.** A driver-begun transaction after the last commit, plus a dirty isolation, read-only, or schema setting, so cleanup throws. `getSchema()` and `setSchema()` begin a transaction in non-autocommit mode (pgjdbc#3005, open). In production, unknown. The study says frequency is not established. In the study's runs, a real pgjdbc session state and HikariCP's `close()`. Code shape: HikariCP's default pool, a connection that has had its isolation or read-only flag changed, and a driver call that opens a transaction the pool does not count. Real-world evidence: the 2026-10-24 duplicate search in the study's section 15 found related schema and reset issues (#2081, #2144, #2142, #2200, and others). None of them report a reset failure followed by reuse. This pass: `repo:brettwooldridge/HikariCP reset exception returned pool`, 21 issues, 6 titles, 0 are that reuse.

**Reproduced on real code.** The study ran HikariCP. It did not run a Spring or Hibernate application on that pool. Framework reachability there is source reading, as the study says.

**Searches.** The study's section 15 (2026-10-24) and the query above (2026-10-27).

**Likelihood (judgment, 2026-10-26).** Low. The consequence is serious when the trigger lines up. The study did not establish how often the trigger lines up, and neither search found a reuse report.

**Not established.** Frequency. A production incident. Behavior under PgBouncer, which the study did not run.

## PHP `PDO::commit()` returns true

Draft: [`php-src-pdo-pgsql-commit-rollback.md`](../transaction-callbacks/upstream-drafts/php-src-pdo-pgsql-commit-rollback.md). Not filed. The transaction-callbacks duplicate search (2026-10-24 and 2026-10-25) is the search record for the question "is this already reported?" Its conclusion, in `stage-4-review.md`: no php-src report asks `pgsql_handle_commit()` to check the command tag.

**Consequence.** `PDO::commit()` returns true when PostgreSQL answers `COMMIT` with `ROLLBACK`. The caller is not given an exception. Laravel's callback behavior on top of that return was measured with a patched driver and is Laravel's issue if it is filed at all. The draft keeps it out of the php-src report.

**Triggers.** A statement error that aborts the transaction, then `commit()`, with the error caught so PHP reaches `commit()`. In production, unknown for this tag. In the study's runs, a real PostgreSQL error. Code shape: catch and commit. Real-world evidence from that search, related and different: php-src#21869 (open), `DEALLOCATE` in a destructor aborts the transaction and a later `COMMIT` comes back as `ROLLBACK`. The maintainer said surfacing destructor failures might be a separate change. bugs.php.net #37870, a 2018 comment, says PDO does not capture the commit error so the fail is silent. bugs.php.net #8698 is MySQL: `commit()` looked successful after a server-side rollback. This pass's `repo:php/php-src pdo_pgsql PDO commit ROLLBACK` returned 7 issues. 6 titles were read. #21869 is the one related item, already in the study's table. 0 of 6 are the command-tag check.

**Reproduced on real code.** The study's `pdo-commit-rollback.php`. No application.

**Searches.** The 2026-10-24/25 duplicate-search directory, plus the 6 titles this pass.

**Likelihood (judgment, 2026-10-26).** Low, the same family as J1 and S1. The historical comments show the symptom class. They do not show this PostgreSQL tag in a deployed application.

**Not established.** An application that treats a true return from `PDO::commit()` as proof the row is durable, after catching `23505`.

## Dramatiq

Findings: [`../python-dramatiq-lifecycle/findings.md`](../python-dramatiq-lifecycle/findings.md). Nothing filed. Dramatiq 2.2.1 and `master` `08d711a`. The faults are real Redis events on a private server.

### F1. A retry that never reaches Redis is acknowledged

**Consequence.** The original message is deleted. There is no retry and no dead letter. Dramatiq logs that it is retrying, then the worker exits 0. 21 of 21 fault runs.

**Triggers.** The actor fails while Redis is down, so the retry enqueue never reaches Redis, and the worker then acknowledges the original. In production, Redis outages happen. Whether the ack lands after a failed enqueue was not found in an issue. In the study, a real Redis shutdown. Code shape: the default `Retries` middleware. Ordinary. Real-world evidence: the study says the behavior appears in two comments on pull request #545 (closed, unmerged), and that no issue exists. This pass: `repo:Bogdanp/dramatiq retry message acknowledged redis` returned #213 (2019, closed), a SIGKILL during the actor. Title only. It is a different loss.

**Reproduced on real code.** No application. The study's actor.

**Searches.** The query above, 1 hit. The study's reading of #545.

**Likelihood (judgment, 2026-10-26).** Low to moderate. A Redis blip during the retry write is a narrow window. The outcome is a silent drop.

**Not established.** A production log of a retry line followed by a missing message. RabbitMQ, which the study did not run.

### F2. Delayed messages stranded in a live worker

**Consequence.** Delayed messages sit in the worker's ack set until the worker exits. A second default-timeout worker did not recover them. 14 of 14 fault runs.

**Triggers.** Redis restarts while a live worker holds not-yet-due delayed messages, and the worker keeps heartbeating. In production, dramatiq#527 (closed, 2023-02-18, user `odigity`) reports this symptom: enqueue with a delay, kill Redis, restart Redis, the job never runs. Ubuntu 20.04, Dramatiq 1.14.0, Redis 6.2. Body opened through test 3. The issue was closed with a heartbeat-timeout explanation. The study says its runs contradict that explanation: the messages stayed stranded with a fresh heartbeat. In the study, a real Redis restart. Code shape: `send_with_options(delay=...)` and a Redis broker. Ordinary delayed jobs.

**Reproduced on real code.** #527's steps were the study's scenario. #527's process was not re-run as that user's project. There is no application repository in the report.

**Searches.** `repo:Bogdanp/dramatiq delayed messages heartbeat`: 3 issues. #527 was opened. #461 is RabbitMQ duplication. #321 is missed AMQP heartbeats at boot.

**Likelihood (judgment, 2026-10-26).** Moderate, conditional on a Redis restart while a worker holds delayed messages and stays alive. One user report, on 1.14.0. The study reproduced the symptom on 2.2.1.

**Not established.** How often workers hold a delay queue across a Redis restart. Whether the 2023 close was right for 1.14.0 and wrong later. The study's runs are 2.2.1 and current `master`.

### F3. The delay-queue consumer thread dies

**Consequence.** The worker keeps running ordinary jobs and never fetches delayed ones again. 10 of 10 runs with a 15 s write pause. A 7 s pause did not kill it.

**Triggers.** An unmapped `redis.TimeoutError` while the delay consumer holds messages. The study also used a network blackhole, 3 of 3. In production, a stalled Redis or a black hole is a real operations event. It is uncommon. Code shape: the default delay consumer. Real-world evidence: the study says #894 and pull request #895 do not report the thread death. This pass did not open them.

**Reproduced on real code.** No.

**Searches.** Not a separate query for the thread death. The #527 search did not surface #894.

**Likelihood (judgment, 2026-10-26).** Low. The pause has to outlast the socket timeout. The worker stays up, so the failure is quiet.

**Not established.** A production report of a worker that runs new jobs and never runs delayed ones.

### F4. `Worker.stop()` raises if Redis is down at shutdown

**Consequence.** Exit 1, and `after_worker_shutdown` is skipped. With the AsyncIO middleware the process does not exit. The message is recovered later by maintenance. 11 of 11 without AsyncIO, 4 of 4 hangs with it.

**Triggers.** Redis unavailable during the shutdown requeue. In production, unknown. In the study, a real Redis outage at shutdown. Code shape: a graceful stop while the broker is down. Real-world evidence: the study calls it a second path to #899's hang. This pass did not open #899.

**Reproduced on real code.** No.

**Searches.** Not a separate query. The finding's upstream note is the study's.

**Likelihood (judgment, 2026-10-26).** Low. The outcome is a loud exit, or a hang when AsyncIO is installed. The message is not lost.

**Not established.** How often shutdown coincides with a Redis outage. A hang report that names this requeue.

## Python lifecycle study

Findings: [`../python-lifecycle-correctness/findings.md`](../python-lifecycle-correctness/findings.md).

### F1. Uvicorn graceful-shutdown overlap

This is U1, uvicorn discussion #3232, rated on the filed-items page. Likelihood there is moderate. This pass does not re-rate it.

### F2. Signal during lifespan startup, before 0.41.0

**Consequence.** On 0.40.0, a signal during lifespan startup skipped lifespan shutdown, 0 of 10. On 0.54.0, shutdown was sent 10 of 10.

**Triggers.** A signal during startup. In production, historical. The study says pull request #2812, released in 0.41.0 (2026-02-16), fixed it. In the study, a real signal against those two versions.

**Reproduced on real code.** The study's harness, not an application.

**Searches.** The study's identification of #2812. No new query. Current releases are outside the bug.

**Likelihood (judgment, 2026-10-26).** None on 0.41.0 and later. The finding is kept so the historical row has a section.

**Not established.** Whether any supported branch before 0.41.0 is still deployed. That was not searched.

### F3. Hypercorn `graceful_timeout` is not enforced on Python 3.12+

**Consequence.** Shutdown waits for in-flight requests. With an 8 s request and a 2 s timeout, Hypercorn 0.18.0 exited after 8.6 s and did not cancel the request, 10 of 10. The study classifies it as a duplicate of pgjones/hypercorn#308 (open, 2025-06-23). Pull request #388 is open.

**Triggers.** SIGTERM or Ctrl-C with `graceful_timeout` set, on Python 3.12+, while a request is in flight. In production, the open issue is a user report of the timeout. This pass did not open the body. In the study, a real signal and a real in-flight request. Code shape: set `graceful_timeout` and expect it to bound shutdown. The configuration text the study quotes describes that wait. Real-world evidence: #308, title and the study's classification.

**Reproduced on real code.** The study's application, not the reporter's.

**Searches.** `repo:pgjones/hypercorn graceful_timeout wait_closed`: 3 hits. #308, #388, and a closed pull request #374. Titles match the finding. 0 additional reports in that set of 3.

**Likelihood (judgment, 2026-10-26).** Moderate for the timeout failing to bound shutdown on Python 3.12+. The harm in the study is a shutdown that lasts as long as the request, not a lost row.

**Not established.** How many deployments set a short `graceful_timeout` on 3.12+. The body of #308 beyond the study's summary.
