# Production relevance of the filed false-commit items: Node.js and Java

Assessed 2026-10-26. Written by: Claude Opus 5.5 (max).

This page rates the production relevance of eight filed items under PPCS's `docs/production-relevance.md`: L2, K1, M3, Y2 with Y3, T3, D1, PI1 and J1. It is a desk assessment. Nothing was run, posted or contacted. The searches are in `searches/`.

**The shared mechanism.** A statement fails inside a PostgreSQL transaction, and the application catches the error and lets the transaction complete. PostgreSQL answers the `COMMIT` with command tag `ROLLBACK` and no error. The library reports success. Every write in the transaction is lost. A later statement in the same transaction would fail loudly with `25P02`, so the silent case needs the caught error to be the last statement, or every later error to be caught too.

## Tiers (judgment, 2026-10-26)

The tiers weigh likelihood, the strength and source of the evidence, and whether the failure is silent. All eight findings are silent. They change no severity rank and no status.

- **Higher:** none. No production report of the silent form names any of these libraries; the production reports found on Prisma and Drizzle are the loud form.
- **Middle:**
  - **L2 (Lucid):** case 2 needs no special code, only a `COMMIT` that fails; one user says they hit it in an app.
  - **Y2 (Kysely):** a project's own report describes the loss through Kysely's managed transaction (warden#148), on a very large install base.
  - **T3 (TypeORM):** a widely used framework, Vendure, releases its events on `afterTransactionCommit`. It is at the lower edge: no code with the shape was found.
  - **J1 (pgjdbc):** real Java code had the shape in 2020 (a framework's Oracle port, #1697; ShedLock, #1739), and pgjdbc's maintainers accept it as a defect.
- **Lower:**
  - **K1 (knex):** no report, 0 of 12 inspected hits. Its own reach is direct knex use, and MikroORM 6 by source reading.
  - **D1 (Drizzle):** the Drizzle reports found are the loud form; 0 of 10 inspected hits.
  - **PI1 (Prisma):** the host issue is a 2023 reproduction made for a library feature, not production; 0 of 10 silent.
  - **M3 (MikroORM 7):** fixed on the default branch on 2026-10-22, not yet in a stable release; 0 of 9.
- **No production trigger:** L2 case 3, a failed `ROLLBACK TO SAVEPOINT`, which our runs produced only by client-side injection.
- **Not defects, or folded into other items:** Y3 is our validation of Kysely's fix for Y2, and is rated with Y2. L2 case 1 has K1's trigger; for Lucid applications it is counted under L2 only (see K1).

| ID | Filed as | Trigger, and how our runs produced it | Strongest real-world evidence | Real code run | Consequence | Likelihood (judgment) |
| --- | --- | --- | --- | --- | --- | --- |
| L2 | [adonisjs/lucid#1205](https://github.com/adonisjs/lucid/issues/1205) (issue, open) | 1: a caught error, then `COMMIT`; a real `23505`. 2: `COMMIT` fails; a real backend termination before `COMMIT`; a lost reply, simulated. 3: a failed savepoint rollback; injected. 4: an outer failure after a nested release; no fault | Case 2: a user's comment on #1205 says they hit it in an app through a deferred constraint trigger (not checked). Harmful consumers of `after('commit')`: `@jrmc/adonis-attachment` deletes replaced files there | No | `db.transaction()` and `trx.commit()` resolve, and `after('commit')` hooks run, for writes PostgreSQL did not commit | Case 1 low; case 2 low to moderate; case 3 low; case 4 low |
| K1 | [knex/knex#6547](https://github.com/knex/knex/issues/6547) (issue, open); outside PR #6549 open | A caught error, then `COMMIT`; a real `23505` | None. One latent hit: alga-psa swallows a `23505` inside the caller's knex transaction | No | `executionPromise` and the handler form resolve; `commit()` resolves with tag `ROLLBACK`, which knex documents | Low |
| M3 | [mikro-orm/mikro-orm#8476](https://github.com/mikro-orm/mikro-orm/issues/8476) (closed; fixed by #8499) | A caught error, then `COMMIT`; a real `23505` | None | No | `em.transactional()` and `em.commit()` resolve; source reading: `afterTransactionCommit` is dispatched | Low; fixed on the default branch, unreleased |
| Y2 | [kysely-org/kysely#2157](https://github.com/kysely-org/kysely/issues/2157) (issue, open); Y3: [validation comment](https://github.com/kysely-org/kysely/pull/2161#issuecomment-6403967170) on #2161 | A caught error, then `COMMIT`; a real `23505` | Audit: [warden#148](https://github.com/laclemen92/warden/pull/148) (0 stars): actions "returned 200, ran `afterCommit` and reported success, but nothing was saved", through `db.transaction().execute()` | No | `commit().execute()` resolves with `isCommitted` true; `transaction().execute()` resolves | Low to moderate |
| T3 | [typeorm/typeorm#12992](https://github.com/typeorm/typeorm/issues/12992) (issue, open); outside PR #12993 open | A caught error, then `COMMIT`; a real `23505` | Harmful consumer: Vendure's EventBus publishes a transaction's events when `afterTransactionCommit` fires | No | `dataSource.transaction()` resolves and `afterTransactionCommit` runs | Low |
| D1 | [drizzle-team/drizzle-orm#6572](https://github.com/drizzle-team/drizzle-orm/issues/6572) (issue, open); outside PR #6574 open | A caught error, then `COMMIT`; a real `23505` | Only the loud form: a production `25P02` on Drizzle over postgres.js ([LanternOps/breeze#5907](https://github.com/LanternOps/breeze/pull/5907)) | No | `db.transaction()` resolves with the callback's value | Low |
| PI1 | [comment on prisma/orm#20496](https://github.com/prisma/orm/issues/20496) | A caught error, then `COMMIT`; a real `23505` | The host issue: a 2023 reproduction made while emulating `createMany` with `skipDuplicates`; two upvotes | No | `$transaction()` resolves | Low |
| J1 | [pgjdbc/pgjdbc#4494](https://github.com/pgjdbc/pgjdbc/issues/4494) (question, open); maintainer PR #4499 open | A caught `SQLException`, then `commit()`; a real `23505`, also through Spring | 2020: a framework's Oracle-to-PostgreSQL port (#1697); ShedLock's insert-catch-commit lock (#1739), where nothing was lost | No | `Connection.commit()` returns; Spring then runs `afterCommit` | Low |

## Per-finding blocks

### L2: Lucid reports success, and runs `after('commit')`, without a commit

- **Filed:** adonisjs/lucid#1205, 2026-10-21, an issue with four cases and a proposed change. No maintainer reply. A user, jals1212 (NONE), commented the same day; the filer replied. Lucid 22.4.2 is the latest release. `TransactionClient.commit()` on the default branch `f715bb4ecc` still awaits only knex's `commit()` before running the hooks (`src/transaction_client/index.ts`, lines 315–329).
- **Production relevance (2026-10-26):**
  - **Consequence:** the transaction resolves and `after('commit')` hooks run for writes that were not committed. Lucid's guide presents these hooks for side effects "that should only happen when the transaction is durable", such as job enqueueing. Silent.
  - **Trigger, case 1, a caught error and then `COMMIT`:** in production, yes as an event (unique violations, deadlocks, serialization failures); in our runs, a real `23505` through `db.transaction()` and `trx.commit()` (LT1a, LT1b, LH1c, PPCS `TX-01A`, the #1205 script). Code shape: a catch inside the callback with no later statement. Redrawn, a competent developer rethrows to roll the unit back, or wraps the statement in a nested transaction (a savepoint), or uses `ON CONFLICT`. The silent shape is reasonable only when the caught write is a once-only last step, or in code written for MySQL. Evidence: 0 of 7 inspected hits; no report.
  - **Trigger, case 2, a `COMMIT` that fails:** in production, yes. Deferred constraints from a real schema fail at `COMMIT` for knex users ([knex#6141](https://github.com/knex/knex/issues/6141), NONE, 2024), and a serialization failure at `COMMIT` was reported from a test scenario ([knex#3370](https://github.com/knex/knex/issues/3370), 2019). Connection loss before `COMMIT` (a failover, `idle_in_transaction_session_timeout`) is the other event; its frequency is not established. In our runs: a real backend termination by `pg_terminate_backend()` from a second connection (PPCS category B), and a lost reply simulated on the client (category D). Code shape: none needed; every Lucid transaction, including Lucid's own `managedTransaction()` helpers (`src/utils/index.ts`, lines 206–227 at `f715bb4ecc`; not run). Evidence: the [jals1212 comment](https://github.com/adonisjs/lucid/issues/1205#issuecomment-6324526300) (unverified, no logs).
  - **Trigger, case 3, a failed `ROLLBACK TO SAVEPOINT`:** in production, unknown; in our runs, a client-side injection only. Code shape: a nested transaction whose caller catches its error. Evidence: none.
  - **Trigger, case 4, an outer failure after a nested release:** in production, yes: any error after a nested `trx.transaction()` completed; in our runs, no fault (LH1f). Code shape: `after('commit')` registered on a nested client; consumers such as `@jrmc/adonis-attachment` register on whatever `$trx` a row carries. Evidence: harmful consumers only.
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26, GitHub code and issues. `c2-lucid`: 94 files, 0 of 7 inspected hits have the shape. `c2-lucid-hook`: 17 files, 6 inspected, all consumers. `b1-lucid-aborted`, `b1-lucid-notsaved`, `b1-adonis-cta` and `i4-lucid-silent`: no Lucid report beyond #1205's thread.
  - **Likelihood (judgment):** case 1 low: the shape was not in the sample. Case 2 low to moderate: no shape is needed and the triggers occur in real deployments, but each is rare per transaction. Case 3 low. Case 4 low: it needs nested transactions with hooks on the nested client.
  - **Not established:** any production report; how often Lucid applications nest transactions; whether jals1212's application lost data.

### K1: knex `executionPromise` resolves on the `ROLLBACK` tag

- **Filed:** knex/knex#6547, 2026-10-17. No comments. An outside PR, [#6549](https://github.com/knex/knex/pull/6549) (pintu544, NONE, 2026-10-18), is open with no review. knex 3.3.0 is the latest release, and `master` has been `e25d54bc` since 2026-06-26. The filed quotation checks out: knex's guide says `executionPromise` is "rejected if it gets rolled back by DB itself" (knex/documentation `src/guide/transactions.md` @ `9b49f59e34`, line 190).
- **Production relevance (2026-10-26):**
  - **Consequence:** `trx.executionPromise` resolves, and the handler form `knex.transaction(async trx => …)` resolves with the handler's value. `commit()` resolves with the reply, whose `response.command` is `ROLLBACK`; that is knex's documented contract (#3847). Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505`, in the manual and handler forms (knex root-cause review K1-2 and K1-3; PPCS run `b2c174`). Code shape: as L2 case 1. Evidence: none; one latent hit (alga-psa, below).
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-knex-ts` and `c2-knex-js`: 201 and 189 files; 0 of 12 inspected hits have the silent shape, 1 is latent and 1 is loud. `b1-knex-cta`, `b1-knex-silent`, `b1-knex-cta-global`, `i3-knex-catch` and `i4-knex-silent`: no report of the silent form.
  - **Likelihood (judgment):** low: the shape was rare in the sample, and nothing reports it.
  - **Not established:** a report; how many knex users read `executionPromise`.
- **Shared root cause with L2, and exposure.** L2 case 1 and K1 have the same trigger and the same PostgreSQL reply. They are separate defects in two layers:
  - knex hands Lucid the tag in `commit()`'s value, and Lucid drops it (root-cause review K1-6).
  - With knex patched so that `executionPromise` rejects, Lucid's managed form still resolved and ran `after('commit')` (K1-7f). A K1 fix alone does not fix L2.
  - L2's proposed change reads the tag itself and does not depend on K1.
  - Count AdonisJS applications under L2 only. K1's own exposure is code that uses knex's handler form or reads `executionPromise`. Lucid's npm downloads (about 0.63 million from 2026-09-23 to 2026-10-22) are part of knex's (about 20.6 million in the same period), so they are not additive.
  - MikroORM 6.6.17 awaits knex's `executionPromise` in `commit()` (`packages/knex/src/AbstractSqlConnection.ts` at tag `v6.6.17`, lines 128–145). So MikroORM 6 would resolve on this trigger and benefit from a K1 fix. That is source reading, not run.
  - L2 case 2 is Lucid's alone: knex already rejects `executionPromise` when `COMMIT` fails, and Lucid does not read it.

### M3: MikroORM `em.transactional()` resolves on the `ROLLBACK` tag

- **Filed:** mikro-orm/mikro-orm#8476, 2026-10-18. Closed 2026-10-22 as completed by [#8499](https://github.com/mikro-orm/mikro-orm/pull/8499) (B4nan, MEMBER), merged 2026-10-22 as `743fafd702`.
- **Fix status:**
  - No stable release contains it on 2026-10-26. The last GitHub release and tag is `v7.2.5` (2026-10-09), 25 commits behind `743fafd702`. npm `latest` is 7.2.5.
  - npm `next` builds 7.2.6-dev.19 (2026-10-22, 04:32 UTC) to dev.27 follow the merge. PPCS ran dev.19: both calls rejected with `25P02` (`research/production-reachability/runs/2026-10-22T12-18-31Z-928c75`).
  - The 6.x branch has no backport; MikroORM 6 runs on knex (see K1).
  - Relevance applies to MikroORM 7 up to 7.2.5.
- **Production relevance (2026-10-26):**
  - **Consequence:** `em.transactional()` and `em.commit()` resolve. Source reading: `afterTransactionCommit` is dispatched after the commit resolves. Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505` (T4f, PPCS `TX-01A`, the #8476 script). Code shape: as L2 case 1. By default a nested `em.transactional()` is a savepoint, which gives a safe way to recover. Evidence: none.
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-mikro`: 225 files; 0 of 9 inspected hits, 1 loud. `b1-mikro-cta`, `b1-mikro-cta-global`, `i3-mikro-catch` and `i4-mikro-silent`: no report.
  - **Likelihood (judgment):** low, and lower once a release ships the fix.
  - **Not established:** a report; MikroORM 6's behaviour at runtime.

### Y2 (and Y3): Kysely `commit()` sets `isCommitted` on the `ROLLBACK` tag

- **Filed:** kysely-org/kysely#2157, 2026-10-21. The maintainer igalklebanov (MEMBER) opened fix PR [#2161](https://github.com/kysely-org/kysely/pull/2161) the same day, and labelled the issue on 2026-10-22. Y3 is our validation comment on #2161 (2026-10-25).
- **#2161 on 2026-10-26:** open, not merged, no reviews, head `ef60ffe` (last commit 2026-10-22), GitHub state "behind". Our comment is the only human comment.
- **Fix status:** no release contains a fix. The latest are 0.29.7 (2026-10-17) and 0.28.18. 0.29.6 and 0.29.7 were run.
- **Y3, what changes for users when #2161 ships:** code written to the 0.29.7 `commit()` docs example, which calls `trx.rollback()` in the `catch`, will see "Transaction is already rolled back" instead of `AbortedTransactionError`. This is recorded in PPCS `research/production-reachability/kysely-pr-2161-validation/`.
- **Production relevance (2026-10-26):**
  - **Consequence:** `commit().execute()` resolves with `isCommitted` true, and `transaction().execute()` resolves. Code that runs after-commit work on resolution runs it for lost writes, as warden did. Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505` (PPCS run `b2c174`, three repetitions; the #2161 validation). Code shape: a catch inside the callback, often in code a framework runs inside its own transaction. Evidence:
    - audit, [laclemen92/warden#148](https://github.com/laclemen92/warden/pull/148) (OWNER, 0 stars, 2026-10-21). At its merge commit, `apps/server/src/routes/actions.ts` opens the action's transaction with `db.transaction().execute()` (line 341);
    - same stack, the project's own wrapper rather than Kysely's API: [scottkelly36/Wagonwise#58](https://github.com/scottkelly36/Wagonwise/pull/58) (OWNER, 0 stars), "the request reported success with nothing saved".
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-kysely`: 458 files; 0 of 10 inspected hits. warden#148 and Wagonwise#58 came from `i3-reported-success-nothing-saved` and `b1-silently-rolled-back`; `b1-kysely-cta`, `b1-kysely-cta-global` and `i3-kysely-catch` found only the loud form.
  - **Likelihood (judgment):** low to moderate: a project's own report shows the shape on Kysely's managed path, and Kysely had about 75 million npm downloads from 2026-09-26 to 2026-10-25, much of it through other libraries.
  - **Not established:** a production report; whether larger Kysely users have the shape. better-auth's catch-inside shape is the loud form ([better-auth#11947](https://github.com/better-auth/better-auth/issues/11947)).

### T3: TypeORM runs `afterTransactionCommit` on the `ROLLBACK` tag

- **Filed:** typeorm/typeorm#12992, 2026-10-22. No comments.
- **Fix status:** an outside PR, [#12993](https://github.com/typeorm/typeorm/pull/12993) (lazerg, CONTRIBUTOR), makes `query()` throw on a `ROLLBACK` reply to `COMMIT`. It is open, with no maintainer review. TypeORM 1.1.2 is the latest release.
- **Production relevance (2026-10-26):**
  - **Consequence:** `dataSource.transaction()` and `QueryRunner.commitTransaction()` resolve, and `afterTransactionCommit` runs while `afterTransactionRollback` does not. Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505` (TT1a, TT1b, TH1c; PPCS run `b2c174`; run `2026-10-22T12-49-59Z-dbcc52`). Code shape: as L2 case 1. Evidence:
    - harmful consumer, vendurehq/vendure (8,544 stars): `packages/core/src/connection/transaction-subscriber.ts` @ `4f7b7955b9`, lines 43–64, and `packages/core/src/event-bus/event-bus.ts`, lines 320–343. The EventBus holds a transaction's events until `afterTransactionCommit`, and drops them on rollback. A false commit event would release them;
    - snapetech-org/seerrng sends deferred notifications from `afterTransactionCommit` (not inspected beyond the search fragment).
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-typeorm-tx`: 238 files; 0 of 8 inspected hits, 1 loud when called inside a caller's transaction. Vendure came from `c4-typeorm-aftercommit`, whose count is not used. `b1-typeorm-*`, `i3-typeorm-notsaved`, `i4-typeorm-silent` and `i4-typeorm-aftercommit-rb`: no silent report.
  - **Likelihood (judgment):** low: the shape was not found, though the consumer that would turn it into damage is widely used.
  - **Not established:** whether Vendure's own code or common Vendure plugins catch database errors inside the request transaction.

### D1: Drizzle `db.transaction()` resolves on the `ROLLBACK` tag

- **Filed:** drizzle-team/drizzle-orm#6572, 2026-10-22. No comments.
- **Fix status:** an outside PR, [#6574](https://github.com/drizzle-team/drizzle-orm/pull/6574) (princejain756, NONE), covers the node-postgres, Neon, Vercel and CockroachDB sessions and leaves postgres-js untouched. It is open, with no review. Latest: 0.45.4 and 1.0.0-rc.5.
- **Production relevance (2026-10-26):**
  - **Consequence:** `db.transaction()` resolves with the callback's value. Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505` on 0.45.4 (run `2026-10-22T13-39-52Z-a7324c`) and 1.0.0-rc.5 (PPCS `reports/examples/2026-10-22T13-28-31Z-671f3e`); the draft `research/production-reachability/upstream-drafts/drizzle.md` records three runs per version. Code shape: as L2 case 1. Evidence, the loud form only:
    - [LanternOps/breeze#5907](https://github.com/LanternOps/breeze/pull/5907) (COLLABORATOR): "US prod, 2026-09-15", repeated 500s from a caught `23505` followed by a re-select, on Drizzle over postgres.js;
    - [marjanneboniii/personal-wealth-operating-system#48](https://github.com/marjanneboniii/personal-wealth-operating-system/pull/48): a `23505` swallowed with `continue` in a loop;
    - [payloadcms/payload#14576](https://github.com/payloadcms/payload/issues/14576): a `25P02` whose first error is not shown.
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-drizzle`: 6,584 files, a loose count; 0 of 10 inspected hits. `b1-drizzle-cta`, `b1-drizzle-cta-global`, `i3-drizzle-catch` and `i4-drizzle-silent`: only the loud form.
  - **Likelihood (judgment):** low: real Drizzle code with the shape usually runs another statement, and so fails loudly.
  - **Not established:** a silent report.

### PI1: Prisma `$transaction()` resolves on the `ROLLBACK` tag (comment on #20496)

- **Filed:** our comment on prisma/orm#20496 (2026-10-23), on Prisma 7.10.1 with `@prisma/adapter-pg`. A bot answered that the request is being considered. No maintainer reply.
- **The host report** (ymc9, NONE, 2023-08-02, label `bug/1-unconfirmed`, two upvotes):
  - **What it is:** a CLI reproduction script with query logging, not production. The reporter's follow-up gives the use case: emulating `createMany` with `skipDuplicates` inside a transaction, to run a post-write check. No production data or logs.
  - **Who answered:** two CONTRIBUTOR accounts. One said "this is not something `Prisma` controls" and suggested `upsert`, or moving the write out of the transaction. The other said that any rolled-back transaction throws, which the reporter corrected.
  - **Code that cites the issue:** two small copies (8 and 7 stars) of a Prisma access-policy layer's `createMany` handler: `sullivanpj/open-system` `tools/storm/runtime/src/enhancements/policy/handler.ts` @ `387fc58f94`, lines 549–557, and a copy in `storm-software/stormstack`. It emulates `skipDuplicates` by checking unique constraints before each create, because "we can't rely on try/catch/ignore constraint violation error".
- **Production relevance (2026-10-26):**
  - **Consequence:** `$transaction()` resolves and the earlier writes are lost. Silent.
  - **Trigger, a caught error and then `COMMIT`:** in production, yes as an event; in our runs, a real `23505` (P2010) on 7.10.1, three runs (run `a7324c`). Code shape: as L2 case 1. Evidence: the host report (a reproduction); the loud form in production at [misospace/dispatch#853](https://github.com/misospace/dispatch/pull/853), where a recovery `updateMany` in the catch hit `25P02` (the post quotes production logs; not checked).
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c3-prisma-itx`: 24,896 files, a loose count; 0 of 10 inspected hits are silent, and 2 are loud. Both loud projects use `provider = "postgresql"`. `c2-prisma-20496` and `c3-zenstack-20496` found the code that cites the issue. `b1-prisma-*`, `i3-prisma-catch` and `i4-prisma-silent`: no other silent report.
  - **Likelihood (judgment):** low: the inspected Prisma code mostly catches outside, or runs another statement and fails loudly.
  - **Not established:** a production loss on Prisma.

### J1: pgjdbc `Connection.commit()` returns when PostgreSQL answers `ROLLBACK`

- **Filed:** pgjdbc/pgjdbc#4494, 2026-10-19, as a question. davecramer (MEMBER) answered "commit() should report it" and asked for the use case. The filer replied on 2026-10-21 with the Spring measurement.
- **Fix status:** vlsi's (MEMBER) PR [#4499](https://github.com/pgjdbc/pgjdbc/pull/4499) adds `raiseExceptionOnSilentRollback`. It is open, default `false`, and was revised after davecramer's review on 2026-10-22. The latest release is 42.7.14 (2026-10-07). In pgjdbc's changelog, 42.2.11 (2020-03-07) raised on silent rollbacks by default (#1729), and 42.2.12 (2020-03-31) reverted it "as this is a breaking change" (#1746).
- **History:**
  - **#1697** (tl-sfo, NONE, 2020-02-05): the report is a test-style snippet (`assertTrue`).
    - A second account (haumacher, NONE) explained the background as "our request". They were adding PostgreSQL support, at a large customer's request, to the database layer of their application framework.
    - They wrote that framework users "possibly could" catch an `SQLException` without a savepoint. That is a porting risk, not an observed loss.
    - Maintainer bokken (MEMBER) runs "a solution which supports both oracle and postgresql" with `autosave=always`.
  - **#1739** (lukas-krecan, NONE, 2020-03-20): ShedLock's JdbcTemplate provider inserted a lock row, caught `DuplicateKeyException`, and let Spring commit; 42.2.11 made that commit throw.
    - vlsi called it "a true ShedLock bug that was previously hidden". ShedLock's transaction held no earlier write, so the silent rollback lost nothing.
    - ShedLock (4,233 stars) now catches outside the `TransactionTemplate` and uses `ON CONFLICT` on PostgreSQL (`JdbcTemplateStorageAccessor.java` @ `5843c5a1b2`, lines 65–72 and 118–119).
  - **#1968** (IvyDev0, CONTRIBUTOR, 2020): a statement cancelled by a client query timeout, caught, then `commit()` returned. Its trigger is not reasonable code.
- **Production relevance (2026-10-26):**
  - **Consequence:** `commit()` returns, `getTransactionState()` is `IDLE`, and Spring runs `afterCommit` and `afterCompletion(STATUS_COMMITTED)` for lost writes. Silent.
  - **Trigger, a caught `SQLException` and then `commit()`:** in production, yes as an event; in our runs, a real `23505` on 42.7.14, directly and through Spring 7.0.9's `DataSourceTransactionManager` and `TransactionTemplate`, with `DriverManagerDataSource` and HikariCP (#4494; PPCS run `b2c174`). Code shape: a catch inside `@Transactional` or a JDBC transaction; found in code written for Oracle (#1697), MySQL (two inspected hits) and H2-tested code (below). Evidence: #1697 and #1739 above;
    - [diegoalegil/AnimeShowdown#712](https://github.com/diegoalegil/AnimeShowdown/pull/712) is the loud form: "H2 (tests) doesn't poison the tx, that's why it passed green";
    - JPA paths are different: Hibernate marks the transaction rollback-only (not checked here).
  - **Reproduced on real code:** no.
  - **Searches:** 2026-10-26. `c2-spring-dup`: 5,824 files; 0 of 10 inspected hits are silent on PostgreSQL, and 2 swallow duplicates in a loop in code whose default database is MySQL, or MySQL and Oracle. `c4-jdbc`: 1,024 files; 0 of 8. `b1-pgjdbc-*`, `b1-spring-*`, `i3-spring-commit-aborted`, `i3-pgjdbc-autosave` and `i4-spring-silent`: the 2020 threads and the loud form.
  - **Likelihood (judgment):** low: the inspected Java code mostly rethrows or rolls back, and ported code that swallows errors usually targets other databases. The 2020 revert shows that the shape exists in real libraries.
  - **Not established:** a production loss on PostgreSQL in Java.

## Details

### What our runs used

- **PPCS `research/production-reachability/`, run `2026-10-19T18-15-49Z-b2c174`.** A real unique violation through each library's ordinary API, three repetitions on PostgreSQL 18.6. It covered knex 3.3.0, Kysely 0.29.6, Lucid 22.4.2, MikroORM 7.2.5, TypeORM 1.1.2 and Spring 7.0.9 on pgjdbc 42.7.14. Deadlock, serialization failure and statement timeout were not run.
- **PPCS `research/transaction-outcome-propagation/`.** Drizzle 0.45.4, Prisma 7.10.1, knex and Kysely in run `2026-10-22T13-39-52Z-a7324c`, and TypeORM in run `dbcc52`. A diagnostic wrapper read the driver's command tag; it is not a library API. Drizzle 1.0.0-rc.5 ran in `reports/examples/2026-10-22T13-28-31Z-671f3e`.
- **`nest-adonis-spike`, branch `docs/lucid-isolation-level-fix`:**
  - `docs/transaction-failure-reporting.md` §2.5 classes `pg_terminate_backend` as natural (PPCS category B), and a discarded `COMMIT` reply as an injected simulation (category D);
  - `docs/knex-root-cause-review/recorded/k1-commit-rollback.txt` holds K1-2, K1-3, K1-4 and K1-6 to K1-7f;
  - `docs/lucid-transaction-outcome-issue-draft.md` holds #1205's script.
- **Experiment IDs** such as LT1a, LH1f, T4f, TT1a and TH1c are `nest-adonis-spike` harness experiments, indexed in `docs/transaction-failure-reporting.md` §8.1.

### Provenance of the main reports

| Report | Kind | Who, when | Size | What I checked |
| --- | --- | --- | --- | --- |
| [#1205 comment](https://github.com/adonisjs/lucid/issues/1205#issuecomment-6324526300) by jals1212 | Incident (claimed) | NONE, 2026-10-21 | Lucid 1,229 stars | Read the comment only. Not checked: their application, the trigger, the SQL Server claim |
| [warden#148](https://github.com/laclemen92/warden/pull/148) | Audit | OWNER, 2026-10-21 | 0 stars | That the route uses `db.transaction().execute()` (line 341 at the merge commit) |
| [Wagonwise#58](https://github.com/scottkelly36/Wagonwise/pull/58) | Audit (own wrapper) | OWNER, 2026-09-29 | 0 stars | `apps/core/src/platform/postgres-data-scopes.ts` at the merge commit checks `command === 'ROLLBACK'` (lines 73–76) |
| [Medplum#10952](https://github.com/medplum/medplum/issues/10952) | Acknowledged | MEMBER, 2026-10-15 | 2,765 stars | Read the issue. It says "not reproduced end to end"; node-postgres directly |
| [Windmill#11938](https://github.com/windmill-labs/windmill/pull/11938), [#7680](https://github.com/windmill-labs/windmill/issues/7680) | Incident, other ecosystem (Rust, sqlx) | The fix by rubenfiszel (CONTRIBUTOR), merged 2026-10-22; #7680 by users (NONE) on self-hosted Docker Compose and Helm deployments | 18,274 stars | Read both. The users reported the loud form (`25P02`). The fix PR describes the silent form: "Saving a schedule, flow or script could return 200 while nothing was saved." sqlx's behaviour was not checked |
| [awcms#1099](https://github.com/ahliweb/awcms/issues/1099), [awcms-one#417](https://github.com/ahliweb/awcms-one/pull/417) | Audit, Bun SQL | OWNER, 2026-10-16 | 13 and 0 stars | Read both. awcms counts "about 45 sites" that catch a `23505` inside a transaction callback and map it to 409, 404 or "already exists". Their code was not inspected |
| [misospace/dispatch#853](https://github.com/misospace/dispatch/pull/853) | Production (loud form), Prisma | CONTRIBUTOR, 2026-08-24 | — | Read the PR. Its production logs were not checked |
| [LanternOps/breeze#5907](https://github.com/LanternOps/breeze/pull/5907) | Production (loud form), Drizzle | COLLABORATOR, 2026-09-15 | — | Read the PR. Its logs were not checked |
| [better-auth#11947](https://github.com/better-auth/better-auth/issues/11947) | Incident (loud form), exposed code | NONE, 2026-10-20 | 30,469 stars | Read the issue. "We hit it under load through the deadlock path." Not checked |
| [pgjdbc#1697](https://github.com/pgjdbc/pgjdbc/issues/1697), [#1739](https://github.com/pgjdbc/pgjdbc/issues/1739), [#1968](https://github.com/pgjdbc/pgjdbc/issues/1968) | Acknowledged and exposed code (2020) | NONE, NONE and CONTRIBUTOR | pgjdbc 1,744 stars; ShedLock 4,233 | Read the threads and pgjdbc's changelog, and ShedLock's current code |

### Harmful consumers of after-commit hooks

- **Lucid `after('commit')`:** 17 files match `"trx.after" "commit"` (TypeScript); 6 were inspected.
  - batosai/adonis-attachment, published as `@jrmc/adonis-attachment`: `src/services/attachment/attachment_transaction_service.ts` @ `40b91a4cd0`, lines 20–24 and 41–53, removes the replaced files on `after('commit')`. 41 stars, 15,004 npm downloads from 2026-09-23 to 2026-10-22.
  - EliasGcf/watch-wise (0 stars): `app/listeners/delete_radarr_movie_file.ts` @ `f5722fe74d`, lines 10–14 and 19–33, deletes media files through Radarr on `after('commit')`; the Sonarr listener does the same.
  - The others dispatch events after commit: exosky12/ateliermerienne, starksinclair/sportykore-api, and the Melchyore/adonis-lucid-observer library (2022).
- **TypeORM `afterTransactionCommit`:** Vendure's EventBus, above.

### Inspected samples

The queries target explicit unique-violation handling. That selects code whose authors know the error, and several of them comment on where the catch must go:
- alga-psa `shared/models/tagModel.ts`, lines 242–249: catching a `23505` "would not work: a failed insert aborts the enclosing Postgres transaction";
- kun-touchgal `app/api/edit/update.ts`, lines 129–135: never move the fallback return into the callback, where it would be "treated as a normal end and committed" (translated from Chinese);
- javascript.cm `app/controllers/reports_controller.ts`, line 103: a savepoint "keeps an outer transaction usable".

Generic catch-all code inside transactions is not reachable with code search. The self-reports suggest it is where the silent form occurs: a framework running plugin or user code inside its own transaction (warden, Medplum, Windmill), or handlers mapping a duplicate to 409 (awcms).

"Silent" means the silent failing shape. "Loud" means caught inside the transaction, then another statement, which raises `25P02`.

| Library (query id) | Files | Inspected | Silent | Loud | Correct or not applicable |
| --- | --- | --- | --- | --- | --- |
| knex (`c2-knex-ts`, `c2-knex-js`) | 201 + 189 | 12 | 0 (1 latent) | 1 | 10 |
| Lucid (`c2-lucid`) | 94 | 7 | 0 | 0 | 7 |
| MikroORM (`c2-mikro`) | 225 | 9 | 0 | 1 | 8 |
| Kysely (`c2-kysely`) | 458 | 10 | 0 | 0 | 10 |
| TypeORM (`c2-typeorm-tx`) | 238 | 8 | 0 | 1 | 7 |
| Drizzle (`c2-drizzle`) | 6,584 | 10 | 0 | 0 | 10 |
| Prisma (`c3-prisma-itx`) | 24,896 | 10 | 0 | 2 | 8 |
| Spring (`c2-spring-dup`) | 5,824 | 10 | 0 (2 latent, MySQL-targeted) | 0 | 8 |
| Plain JDBC (`c4-jdbc`) | 1,024 | 8 | 0 | 0 | 8 |

In all, 0 of 84 inspected hits have the established silent shape. 5 are loud. 3 are latent: the shape is there, but whether it is silent depends on the callers or on running on PostgreSQL.

**The hits,** owner/repo path @ commit (lines):

- **knex:**
  - Latent:
    - Nine-Minds/alga-psa `shared/services/assets/assetTicketAssociation.ts` @ `058d45c388` (6–32) returns on `23505` inside the caller's transaction.
    - Its two in-transaction callers run another statement afterwards: `shared/rmm/alerts/ticketCreator.ts` (141–145) and `shared/services/tickets/createTicketWithSideEffects.ts` (283–291). The third gives it its own transaction: `shared/services/email/processInboundEmailInApp.ts` (2118–2127).
  - Loud: alga-psa `packages/tags/src/models/tagDefinition.ts` (132–167) re-reads after a `23505` when given a transaction.
  - Correct:
    - catch outside the transaction: bahnzumberg/zuugle-suchseite `apps/backend/src/routes/lists.js` @ `33bfd3c39f`; webiny/webiny-js `packages/api-core-sql/src/keyValueStore/index.ts` @ `01a42e0e86`; lightdash/lightdash `packages/backend/src/models/SavedChartModel.ts` @ `a4a88b90bc` (641–775); alga-psa `packages/users/src/lib/roleActions.ts` and `packages/billing/src/actions/categoryActions.ts`;
    - `ON CONFLICT`: alga-psa `shared/models/tagModel.ts` (242–249);
    - explicit rollback: navapbc/arpa-reporter `packages/server/src/lib/grantsCollaboration/followers.js` @ `a09b332907` (1–13);
    - no transaction at the catch: voxpelli/node-fetch-politely `lib/pglookup.js` @ `b9be0f030c`; jamcalli/Pulsarr `src/services/database/methods/session.ts` @ `7af0905a57` (it uses `ON CONFLICT` on PostgreSQL);
    - no catch: PicPeak/picpeak `backend/src/services/externalRelpathFold.js` @ `cbdb9e37ee` (309–312).
- **Lucid:**
  - catch outside: Joao-r-Am/hotep-api `app/services/public-scheduling-service.ts` @ `d2abc690ed`; kanwas-ai/kanwas `backend/app/services/document_share_service.ts` and `task_lifecycle_service.ts` @ `7c2292aec9`; MaloLebrin/boat-management `app/services/boat_hull_service.ts` @ `79586d149c`; javascriptcm/javascript.cm `app/controllers/reports_controller.ts` @ `ae78cf1199`;
  - rethrow: kanwas `organization_invite_service.ts` (248–262); Solvro/backend-topwr `app/controllers/v1/users.ts` @ `66042c4bd2` (111–162).
- **MikroORM:**
  - Loud: open-mercato/open-mercato `packages/core/src/modules/wms/commands/inventory-actions.ts` @ `c3cfc9211c` (1066–1069) reads again in the same transaction.
  - Correct:
    - catch outside: open-mercato `packages/core/src/modules/configs/services/upgradeActionsService.ts` (77–120); bym-refitted/backyard-monsters-refitted `server/src/scripts/monthly-shiny.ts`, `server/src/services/user/renameUser.ts` and `server/src/controllers/alliance/createAlliance.ts` @ `870498fff2`;
    - rethrow: liketrek/TREK `server/src/db/repositories/Users.repository.ts` @ `d4da05bbc9` (269–279); PKUHPC/OpenSCOW `apps/mis-server/src/services/tenant.ts` @ `8de039b22c` (115–124); open-mercato `packages/core/src/modules/catalog/commands/productUnitConversions.ts` (301–305);
    - not in an explicit transaction: OpenSCOW `apps/mis-server/src/services/account.ts` (238–246). It swallows non-unique flush errors, and the flush rolls back its own transaction.
- **Kysely:**
  - catch outside: johanohly/AirTrail `src/lib/server/utils/oauth-link-token.ts` @ `ed100a90cd`; crbnos/carbon `packages/database/src/quality.ts` and `apps/erp/app/modules/items/items.service.ts` @ `835b19a5cb`; logtide-dev/logtide `packages/backend/src/modules/invitations/service.ts` @ `40618910fa`; Globulation2/glob2 `platform/packages/play/src/play/intake.ts` @ `e154bda4ce`; boringnode/queue `src/drivers/kysely_adapter.ts` @ `f60954e1cb` (585–600);
  - not applicable: carbon `settings.service.ts` (no database transaction) and `resources.service.ts` (Supabase client); flojoy-ai/cloud `apps/server/src/lib/db-utils.ts` (a helper that rethrows); HamedMP/matrix-os `packages/gateway/src/bots/repositories/shared.ts` (a helper).
- **TypeORM:**
  - Loud when nested: worldalliance/alliance `server/src/share-urls/share-url-rows.ts` @ `283227fb49` (105–124) reads again after a caught `23505` if called inside a caller's transaction.
  - Correct:
    - rethrow: boostcampwm2025/web25-ittda `backend/src/modules/post/post-draft.service.ts` @ `948ddeca84` (105–117); openlinker-project/openlinker `libs/oms/src/routing/oms-routing-rule.repository.ts` @ `02f9827811`;
    - catch outside: ar-webcetera/nervion `apps/backend/src/projects/projects.service.ts` @ `a32671e735`; alkem-io/server `src/domain/community/user/user.service.ts` @ `f155cae222`; galarzafrancisco/ai-monorepo `apps/backend/src/agents/agents.service.ts` @ `693baf5aa0`;
    - a savepoint per item: leggedrobotics/kleinkram `backend/src/services/file-lifecycle.service.ts` @ `93f31da8e9` (502–568);
    - a non-database error swallowed: mnfst/llm-gateway `packages/backend/src/routing/custom-provider/custom-provider.service.ts` @ `cd2feb2d49` (500–520).
- **Drizzle:**
  - catch outside: claudiumio/geronticare `lib/bootstrap.ts` @ `c524826365`; hicyoucom/hicyou `lib/bookmark-batch-import.ts` @ `592dffaeda` (one transaction per item); xynehq/xyne `server/server.ts` @ `0fc3313f2c`; superloglabs/superlog `packages/db/src/agent-chat.ts` @ `2fdc51da33`; fancyboi999/open-tag `src/server/replyCoordination.ts` @ `35d8eee6c4`;
  - a savepoint: superlog `apps/api/src/orgs.ts` (63–78);
  - rethrow: getpact/pact `apps/issuer/src/workspace.ts` @ `fed96d0a9d` (36–43);
  - no transaction at the catch: nainglinnkhant/shadcn-view-table `src/app/_lib/actions.ts` @ `f60b450da0`; zmeyer44/Locker `apps/web/server/ai/tools/tags.ts` @ `0ade074650`; riffado/riffado `src/db/queries/billing.ts` @ `b518379bde`.
- **Prisma:**
  - Loud: lovedevpanda/Rhex `src/db/block-queries.ts` @ `4b6ffb0d47` (181–194); ifalfahri/keluhkesah `src/lib/storage.ts` @ `1376e8ced1` (120–135).
  - Correct:
    - catch outside: KunMoe/kun-touchgal-next `app/api/edit/update.ts` @ `a3e50efa08` (its comment warns against moving the return into the callback); actionow-ai/x2t `src/lib/react-action.ts` @ `f90487430f`; pedromello/manifoldpowered.com `models/review.ts` @ `e2bdc4e692`;
    - no transaction: Ammaar-Alam/minebench `lib/gallery/service.ts` @ `cc9eee3072`;
    - rethrow: SIMARSINGHRAYAT/GitHubCrazy.com `api/followers.ts` and `api/stars.ts` @ `3f54ec67aa`; CNVioletTech/image2-ai `src/lib/checkin.ts` @ `8aae122000` (95–105).
  - Not applicable: Rhex `src/lib/messages.ts` (a read path).
- **Spring:**
  - Latent: apache/rocketmq-dashboard `server/src/main/java/org/apache/rocketmq/studio/auth/AuthService.java` @ `0228dad5b9` (449–475, a private bootstrap loop; default datasource MySQL); hzwy23/batch-scheduler `.../GroupTaskDaoImpl.java` @ `ce42d9ebba` (155–175; MySQL and Oracle SQL).
  - Correct:
    - rethrow: sohutv/mqcloud `UserProducerService.java` and `TopicService.java` @ `ab25e28176`; MaJesTySA/miaosha_Shop `UserServiceImpl.java` @ `e676eb98e0`; madvirus/ddd-start `SpringLockManager.java` @ `8970372f30`;
    - `setRollbackOnly()`: mqcloud `AuditService.java` (225–244).
  - Not applicable: FlowCI/flow-core-x, three files on MongoDB.
- **Plain JDBC:** rollback or no explicit transaction in apache/polaris `DatasourceOperations.java` @ `421062c85b` (293–322); mit-cml/appinventor-sources `PostgreSQLStorageIo.java` @ `3a4af6e4bb`; diudiu-tech/delivery-harness `PlatformStore.java` @ `3fb2d17354` (110–128); agentscope-ai/agentscope-java `JdbcAgentSkillRepository.java` @ `16cb024ae6` (1001–1012); nuxeo/nuxeo `VCSLockManager.java` @ `aaf54d4b42`; apache/hop `DatabaseMaskingStore.java` @ `e3d1b597cc`; ucshadow/SEP2 `DBHandler.java` @ `ef10e3ee16` (64–86); BenCodez/VotingPlugin `SharedPointTransferJournal.java` @ `2a1e4e19ce` (160–191).

### User reports of the consequence, by library

In 51 issue queries on 2026-10-26 (`searches.txt`), I found:

- **Lucid:** only #1205's own thread.
- **knex:** no report of the silent form. #6141, #3370 and #3847 concern a `COMMIT` that raises.
- **MikroORM:** none.
- **Kysely:** warden#148, and Wagonwise#58 on its own wrapper. The loud form: bichu-app/bichu-app#35 (measured in staging) and wilanis/wilanis-js#800.
- **TypeORM:** no silent report. #8661 (subscribers fire before commit) is a different mechanism.
- **Drizzle:** only the loud form.
- **Prisma:** #20496 itself; the loud form in misospace/dispatch#853 and pedroalvs/properfy#1056.
- **Java:** #1697, #1739 and #1968 from 2020; AnimeShowdown#712 (loud).

### Evidence against

- **Documentation that puts the duty on the caller:**
  - MikroORM `docs/docs/transactions.md` @ `9688b6ae30`, line 480: "when catching Exception you should generally re-throw the exception. If you intend to recover from some exceptions, catch them explicitly … (but do not forget to rollback the transaction)". Line 90: a nested `em.transactional()` creates a savepoint by default.
  - Spring `framework-docs/.../declarative/rolling-back.adoc` @ `393e5c4b14`: rollback by default only for unchecked exceptions (line 18), and `setRollbackOnly()` in a `catch` (lines 168–184).
  - pgjdbc `docs/content/documentation/use.md` @ `8747452584`, lines 232–235: `autosave=always` sets a savepoint before each query and rolls back to it on failure. It is opt-in; the default is `never`.
  - Lucid's guide (adonisjs/lucid.adonisjs.com `content/docs/guides/transactions.md` @ `798060f49a`), line 19: managed transactions "commit when the callback returns, and rollback when it throws". Line 174: a nested transaction is a savepoint.
  - Prisma's transactions page (prisma/docs `apps/docs/content/docs/orm/v7/prisma-client/queries/transactions.mdx` @ `8ac389a9cf`), line 916: the callback must throw for the transaction to roll back.
  - Kysely's controlled-transaction example (`site/docs/examples/transactions/0011-controlled-transaction.js` @ `b506b6390a`) rolls back in the `catch`.
  - Drizzle's PostgreSQL page (drizzle-team/drizzle-orm-docs `src/content/docs/pg/transactions.mdx` @ `75cad5e1d7`, lines 18 and 33–42) documents savepoints through nested transactions and `tx.rollback()`.
  - TypeORM's guide (`docs/docs/transactions.mdx` @ `5bdc67882d`, lines 283–285) shows `rollbackTransaction()` in the `catch` of the QueryRunner form.
  - Of these pages, only MikroORM's and Spring's discuss catching a database error inside the transaction.
- **The inspected code:** 0 of 84 hits have the silent shape; most catch outside the transaction, rethrow, or use a savepoint or `ON CONFLICT` (above).
- **Maintainers:** vlsi (pgjdbc, 2020): PostgreSQL "forbids patterns like" catching a duplicate and continuing; "you need to configure `autosave=always`". Prisma's 2023 reply put the fix on the caller. knex's #3847 keeps `commit()` from throwing.
- **Libraries that already guard:**
  - pgx returns `ErrTxCommitRollback` (verified on PPCS's `research/python-upstream-contribution/real-world-evidence/README.md`);
  - Bun's SQL client since 1.4.3 (below);
  - MikroORM's `next` builds;
  - in the inspected code, savepoints per item (kleinkram, superlog), `ON CONFLICT` (alga-psa, Pulsarr), and rollback-only marking (mqcloud).
- **The raise has a cost.** pgjdbc reverted it in 42.2.12 because it broke code whose silent rollback was harmless (ShedLock). awcms says Bun 1.4.3 turned about 45 of its catch sites into 500s. Kysely's #2161 changes what code written to its old docs example sees.

### Cross-ecosystem fixes

- **From the Python page** (verified there): pgx `ErrTxCommitRollback`; [rust-postgres#1342](https://github.com/rust-postgres/rust-postgres/pull/1342) (open); [postgres.js#1217](https://github.com/porsager/postgres/issues/1217) (open, no comments on 2026-10-26); pgjdbc#4499.
- **New, verified here:** Bun's built-in SQL client. [oven-sh/bun#35119](https://github.com/oven-sh/bun/pull/35119), "sql: reject sql.begin() when COMMIT is answered with the ROLLBACK tag", merged 2026-09-30 as `5a183c1ebc`.
  - Tag `bun-v1.4.3` (2026-10-10) contains it, and `bun-v1.4.2` does not (compare API).
  - At tag `bun-v1.4.3`, `src/js/bun/sql.ts` lines 892–896 throw `ERR_POSTGRES_COMMIT_ROLLED_BACK` when `commit_result?.command === "ROLLBACK"`.
- **Application-level fixes for the same mechanism:**
  - Windmill#11938: an audit write that fails on a transaction's executor now returns its error;
  - Wagonwise#58 and michaelcarletta-cmd/ChecksOps#1082 check the `COMMIT` reply;
  - warden#148 tracks the first error.

## Method

Read-only GitHub searches on 2026-10-26, from 15:42 to 16:05 UTC, through the shared paced helper (`paced_search.py`). The queries are in `searches/q-batch1.json` to `q-batch4.json`. `searches/searches.txt` lists each query with its total and the hits it showed; `searches/raw/` holds the responses.

- **Totals:** 74 queries, 51 over issues and pull requests and 23 over code. Two code queries for plain JDBC (`c2-jdbc` and `c3-jdbc`, two phrasings) each failed with GitHub's "too many shards failed" (HTTP 503) and have no result; `c4-jdbc` replaced them.
- **Counts not used:** some code counts are not cited, because their hits were not inspected or were mostly vendored copies: `c2-prisma`, `c2-typeorm-hook`, `c2-ported-mysql`, `c3-drizzle-txinsert`, `c4-typeorm-aftercommit` and `c4-mikro-aftercommit`.
- **Inspection:** 84 hits for the shape, plus 7 hook consumers. Each file was read at the commit its hit points to, through the contents API. Lines are cited from those files.
- **Other reads:** issues, pull requests, comments, timelines, releases, tags and commit comparisons through `gh api`; documentation files at their default-branch commits; npm registry metadata and the npm downloads API.
- **Nothing was run.**
- **Excerpts:** the fetched files are kept beside the search logs (`inspected/`). They are third-party code and not for publication.
