# Upstream submissions tracker

Started: 2026-10-17. Written by: Claude Opus 5.5.

This document lists every issue, pull request, comment and discussion we plan to send to an upstream project as a result of the persistence research. It is the single place to see what exists, what is ready, what is blocked, and what has been sent.

This copy is in the PostgreSQL Persistence Conformance Suite. The same tracker is on `docs/lucid-isolation-level-fix` in [nest-adonis-spike](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/upstream-submissions.md). Drafts from 2026-10-20 are in this repository under `research/production-reachability/upstream-drafts/`. Older draft files linked below are in that other repository.

- **M2, K3, K2, K1, L3, L1, and L5 were submitted on 2026-10-17.** Y1, M4, and M3 were submitted on 2026-10-18. T1 was submitted on 2026-10-17 as #12976, #12977, and #12979. T2 was submitted on 2026-10-18 as #12978. J1 was submitted on 2026-10-19 as pgjdbc #4494. L2 was submitted on 2026-10-21 as lucid #1205. A1 was submitted on 2026-10-21 as adonisjs discussion #5166. K2-PR was submitted on 2026-10-18 as knex PR #6548.
- **The current execution queue is in §2.** The priority table there is the decision from earlier the same day, kept for history. K2, L3, and L1 in that table are already submitted.
- **Every row is outward-facing.** Each needs explicit approval of its exact content and destination before it is posted.
- **The drafts stay the source of truth for content.** This tracker records status, order and dependencies, and links to each draft.
- **[`upstream-drafts-review.md`](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/upstream-drafts-review.md)** stays as it is: a dated review of the drafts that existed on 2026-10-14.

**How to update it.** When an item is submitted, set its status to Submitted, fill in the date and link, and set the follow-up date. Record replies in the item's notes. Add a line to the change log at the end.

## Status key

| Status | Meaning |
| --- | --- |
| **Ready** | Drafted and reviewed. Needs only the pre-posting checks and approval |
| **Decision** | Drafted, but a decision is needed before it can be sent |
| **In progress** | An agent is preparing it now |
| **Not drafted** | A measured finding with no draft yet |
| **Candidate** | Ranked in a plan, not drafted |
| **Submitted** | Sent; waiting for a reply |
| **Closed** | Merged, answered, or withdrawn |

## 1. All items

The upstream states below were last checked 2026-10-14 to 2026-10-17, as shown per item. Every Submitted and Closed row was rechecked on GitHub on 2026-10-25 (§4). Re-check before posting.

| ID | Upstream | Type | Subject | Status | Next action | Draft |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | adonisjs/lucid | Issue + PR (`22.x`) | Explicit transactions ignore the requested isolation level | **Submitted** | Monitor #1202 and #1203. One follow-up around 2026-10-31; decide around 2026-11-14 (§4). Offer the nested `TypeError` only if maintainers ask | [lucid-isolation-level-fix.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/lucid-isolation-level-fix.md) §7–§9 |
| L2 | adonisjs/lucid #1205 | Issue | Transactions report success when PostgreSQL did not commit; `after('commit')` hooks run without a commit | **Submitted** | Non-maintainer reply 2026-10-21. Do not treat their `executionPromise` patch as a fix for case 1. No pull request until maintainers agree. The 2026-11-04 follow-up is no longer a silence ping | [lucid-transaction-outcome-issue-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/lucid-transaction-outcome-issue-draft.md) |
| L3 | adonisjs/lucid PR #1168 | Comment | PostgreSQL evidence: the PR fixes #1153 but lets a second runner apply a migration when the lock's session dies | **Submitted** | Checked 2026-10-21. Still open at `28e65029`. No reply to the regression comment. No further comment | [ppcs-migration-research/docs/pr-1168-comment-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/ppcs-migration-research/docs/pr-1168-comment-draft.md) |
| A1 | adonisjs discussion #5166 | Discussion | Using Lucid outside AdonisJS: would small decoupling contributions be welcome? | **Submitted** | One follow-up around 2026-11-04. Decide around 2026-11-18 (§4). Posted in Ideas | [adonisjs-maintainer-discussion-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/adonisjs-maintainer-discussion-draft.md) |
| L4 | adonisjs/lucid | Issue | `--step` stays within the latest batch, unlike the docs | **Candidate** | Draft after replies to L1, L2 and A1 | [upstream-contribution-plan.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/ppcs-migration-research/docs/upstream-contribution-plan.md) §3.2 |
| L5 | adonisjs/lucid #1204 | Issue | Rolling back a migration with no `down()` reports success and deletes its history row | **Submitted** | Wait for a reply. §4 sets no follow-up date | [lucid-missing-down-issue-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/lucid-missing-down-issue-draft.md) |
| L6 | adonisjs/lucid | Issue | `migration:run` ignores applied migrations missing on disk, which rollback refuses | **Candidate** | Draft after replies to L1, L2 and A1 | [upstream-contribution-plan.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/ppcs-migration-research/docs/upstream-contribution-plan.md) §2 order 4 |
| L7 | adonisjs/lucid | Issue | `migration:status` creates the history table | **Candidate** | Same | same, §2 order 5 |
| L8 | Lucid documentation | Docs change | `MigrationRunner.close()` closes the whole `Database` | **Candidate** | Same | same, §2 order 6 |
| K2 | knex/knex #6546 | Issue | A connection goes back to the pool with its transaction open when `ROLLBACK` or `COMMIT` fails on the client; reproduced without injection | **Submitted** | Wait for a reply. §4 sets no follow-up date for knex | [knex-transaction-outcome-issue-drafts.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-transaction-outcome-issue-drafts.md), K2 |
| K2-PR | knex/knex PR #6548 | PR | Discard a connection when `COMMIT` or `ROLLBACK` fails uncertainly (fix for #6546) | **Submitted** | Opened 2026-10-18. Checked 2026-10-25: no comments or reviews; CI workflows wait for maintainer approval (`action_required`). The K1 and K3 fixes wait for feedback here | [knex-root-cause-review/fixes/6546-fix-report.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-root-cause-review/fixes/6546-fix-report.md) |
| K1 | knex/knex #6547 | Issue | `executionPromise` resolves when PostgreSQL rolls back at `COMMIT` | **Submitted** | Wait for a reply. §4 sets no follow-up date for knex. Outside PR #6549 (2026-10-18) says it closes #6547; no maintainer activity as of 2026-10-25 | [knex-transaction-outcome-issue-drafts.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-transaction-outcome-issue-drafts.md), K1 |
| K3 | knex/knex #4709 | Comment | The cause, a trigger without timeouts, and a fix shape for the failed-`BEGIN` behaviour that #4709 already reports | **Submitted** | Wait for a reply. §4 sets no follow-up date for knex | [knex-4709-comment-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-4709-comment-draft.md) |
| M1 | mikro-orm/mikro-orm | PR | Fix #8458: a failed `ROLLBACK TO SAVEPOINT` is swallowed, so inner writes commit with the outer transaction | **Closed** | Withdrawn 2026-10-17: PR #8462, by another contributor, already fixes #8458 (§3.3) | — |
| M2 | mikro-orm/mikro-orm PR #8462 | Comment | Independent results on PostgreSQL and MySQL, two suggested tests (a throwing `beforeTransactionRollback` subscriber; two rollbacks failing in a row), and a short compatibility note | **Closed** | #8462 approved and merged by B4nan on 2026-10-22, at head `d3d3b5da`, not the validated `272a1081`. No reply to the comment. The subscriber test was not added (§3.3) | [mikroorm-8458-comment-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/mikroorm-8458-comment-draft.md); evidence in [mikroorm-pr-8462-validation.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/mikroorm-pr-8462-validation.md) |
| M3 | mikro-orm/mikro-orm #8476 | Issue | `em.transactional()` resolves although PostgreSQL turned `COMMIT` into `ROLLBACK` (T4f) | **Closed** | Closed 2026-10-22 as completed via #8499. Retested on 7.2.6-dev.19: both calls reject. npm `latest` was still 7.2.5 | [mikroorm-commit-rollback-issue-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/mikroorm-commit-rollback-issue-draft.md) |
| M4 | mikro-orm/mikro-orm PR #8448 | Comment | The listener fix does not reach a `ROLLBACK` that fails on a live connection | **Submitted** | Wait for a reply. §4 sets no follow-up date. The PR was already merged | [kysely-connection-recovery-comment-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/kysely-connection-recovery-comment-draft.md), comment 2 |
| Y1 | kysely-org/kysely #1990 | Comment | 0.29.7 and 0.28.18 can return a connection whose `ROLLBACK` never completed; the next commit can include those writes | **Submitted** | Wait for a reply. §4 sets no follow-up date. A later PR waits on the four release checks | [kysely-connection-recovery-comment-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/kysely-connection-recovery-comment-draft.md), comment 1 |
| Y2 | kysely-org/kysely #2157 | Issue | `commit()` sets `isCommitted` when the transaction did not commit | **Submitted** | Filed 2026-10-21. No pull request from us. Duplicate search the same day did not find this case. The maintainer `igalklebanov` opened PR #2161 ("closes #2157") on 2026-10-21 and labeled the issue on 2026-10-22; #2161 was open on 2026-10-25. #1990 is the connection leak | [kysely.md](../research/production-reachability/upstream-drafts/kysely.md) |
| Y3 | kysely-org/kysely PR #2161 | Comment | Independent validation of the maintainer's fix for Y2: both #2157 paths reject with `AbortedTransactionError`; controls unchanged; a note on the 0.29.7 docs catch pattern | **Submitted** | Wait for a reply. §4 sets no follow-up date | [kysely-pr-2161-validation/comment.md](../research/production-reachability/kysely-pr-2161-validation/comment.md) |
| S1 | spring-projects/spring-framework | Issue | `afterCommit` runs, and `afterCompletion` is `STATUS_COMMITTED`, when PostgreSQL rolled the transaction back | **Ready** | A1 is posted as discussion #5166. Not approved to file. pgjdbc #4494 (J1) is the driver half and is already submitted | [spring-framework.md](../research/production-reachability/upstream-drafts/spring-framework.md) |
| P1 | psycopg/psycopg #1453 | Issue | `Connection.commit()` returns when `COMMIT` completes with command tag `ROLLBACK` | **Submitted** | Filed 2026-10-21. No pull request. Same-day search found no duplicate. PyPI `latest` was 3.3.6, uploaded 2026-09-18. Do not also file SQLAlchemy or Django | [psycopg.md](../research/production-reachability/upstream-drafts/psycopg.md) |
| J1 | pgjdbc/pgjdbc #4494 | Issue | Should `Connection.commit()` report that PostgreSQL answered `COMMIT` with `ROLLBACK`? | **Submitted** | Use case answered 2026-10-21. `vlsi` opened PR #4499 (opt-in `raiseExceptionOnSilentRollback`) and PR #4496 (XA) on 2026-10-22, both referencing #4494; both open on 2026-10-25. Do not open a second pgjdbc issue | — |
| T1 | typeorm/typeorm #12976, #12977, #12979 | Issue + PR | Nested `startTransaction()` failure rolls back the caller; a failed `ROLLBACK TO SAVEPOINT` leaves the connection in a transaction | **Submitted** | Monitor #12976, #12977, and #12979. Outside PRs #12983 ("Fixes #12976", 2026-10-20) and #12997 ("Fixes #12977", 2026-10-23) have no maintainer activity as of 2026-10-25. The per-depth unresolved-rollback patch was not what those posts contain | [typeorm-savepoint-depth-fix/HANDOFF.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-savepoint-depth-fix/HANDOFF.md); [design-review.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-savepoint-depth-fix/design-review.md) |
| T2 | typeorm/typeorm #12978 | Issue | `QueryRunner.release()` returns a connection that is still in a transaction | **Submitted** | Monitor #12978. `bunnysayzz` pointed at fix PR #12980 on 2026-10-18. The other §3.6 rows stay unfiled except T3 | [typeorm-objection-sequelize-assessment.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-objection-sequelize-assessment.md) |
| T3 | typeorm/typeorm #12992 | Issue | `afterTransactionCommit` runs when `COMMIT` completes with command tag `ROLLBACK` | **Submitted** | Filed 2026-10-21. No pull request from us. Same-day search found no duplicate. Outside PR #12993 ("Fixes #12992", 2026-10-22) has no maintainer activity as of 2026-10-25. npm `latest` was 1.1.2. Not #12976–#12979 | [typeorm.md](../research/production-reachability/upstream-drafts/typeorm.md) |
| D1 | drizzle-team/drizzle-orm #6572 | Issue | `db.transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK` | **Submitted** | Filed 2026-10-22. No pull request from us. Same-day search found no duplicate. Outside PR #6574 ("Fixes #6572", 2026-10-22) has no maintainer activity as of 2026-10-25. npm `latest` was 0.45.4. `rc` was 1.0.0-rc.5 | [drizzle.md](../research/production-reachability/upstream-drafts/drizzle.md) |
| PI1 | prisma/orm #20496 | Comment | The `ROLLBACK` command tag on `COMMIT` that #20496's caught-error report lacks, and where Prisma 7.10.1 leaves it unread | **Submitted** | Posted 2026-10-23 as a comment on #20496. No pull request. Only reply: the automated `prisma-asks[bot]` triage message the same day, not a maintainer. #20496 was still open, with no comment after 2023-08-07. Same-day search found no newer report. npm `latest` was 7.10.1. `prisma/prisma` redirects to `prisma/orm` | [prisma.md](../research/production-reachability/upstream-drafts/prisma.md) |
| PY-1b | psycopg/psycopg #1453 | Comment | `with conn.transaction() as tx:` exits normally, and `tx.status` is `committed`, after PostgreSQL aborted the transaction | **Submitted** | Posted 2026-10-24 as a comment on #1453 (P1). No pull request. #1453 was still open with no comments. One follow-up around 2026-11-07; decide around 2026-11-21 (§4) | [psycopg-1453-comment.md](../research/python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md) |
| PY-2 | MagicStack/asyncpg #1400 | Issue | `Transaction.commit()` and `async with conn.transaction()` return normally when PostgreSQL answers `COMMIT` with `ROLLBACK` | **Submitted** | Filed 2026-10-24. No pull request. Same-day search found no duplicate. PyPI `latest` was 0.32.0. One follow-up around 2026-11-07; decide around 2026-11-21 (§4) | [asyncpg-commit-rollback.md](../research/python-upstream-contribution/upstream-drafts/asyncpg-commit-rollback.md) |
| PY-3 | tortoise/tortoise-orm #2383 | Issue | `Model.save()` returns normally and writes nothing after the instance's INSERT was rolled back | **Submitted** | Filed 2026-10-25. No pull request; one is offered if the maintainers pick a direction. Same-day search found no duplicate. PyPI `latest` was 1.1.9. One follow-up around 2026-11-08; decide around 2026-11-22 (§4) | [tortoise-save-after-rollback.md](../research/python-upstream-contribution/upstream-drafts/tortoise-save-after-rollback.md) |

## 2. Order

### Current execution queue

This is the remaining work. L1 is submitted (#1202 and #1203). L2 is submitted (#1205). A1 is submitted (#5166). The decision brief's Lucid sequence is posted.

Do not resume a row from the historical priority table once its item is submitted.

No item is queued. D1 was filed 2026-10-22 as #6572. P1 was filed 2026-10-21 as #1453. T3 was filed 2026-10-21 as #12992. Y2 was filed 2026-10-21 as #2157. S1 stays unfiled until pgjdbc #4494 decides how `commit()` reports the rollback. PI1 was posted 2026-10-23 as a comment on prisma/orm #20496. PY-1b was posted 2026-10-24 as a comment on psycopg #1453, and PY-2 was filed the same day as asyncpg #1400. PY-3 was filed 2026-10-25 as tortoise/tortoise-orm #2383. The remaining Python items are sequenced in [`python-upstream-contribution-tracker.md`](../research/python-upstream-contribution-tracker.md). None of the unfiled items is approved to file.

Not in this queue: M2, M3, M4, K3, K2, K1, L3, L1, L2, L5, Y1, Y2, Y3, J1, T1, T2, T3, P1, D1, PI1, PY-1b, PY-2, PY-3, and A1 are submitted (§5). M1 is withdrawn. L4, L6, L7 and L8 wait on replies to L1, L2 and A1. SQLite controls stay useful and must not delay anything. The Knex draft written 2026-10-20 restates K1 (#6547) and must not be filed again.

### Priority (set 2026-10-17)

Historical. This is the order decided before the day's submissions. **K2, L3, and L1 are submitted.** Use the current execution queue above.

| Priority | Work | Why |
| --- | --- | --- |
| 1 | Adversarially validate L1 on PostgreSQL and MySQL | The first PR to Lucid should be exceptionally well tested |
| 2 | Submit L3, the evidence on PR #1168 | An existing, independently validated reproduction; most useful before the PR merges |
| 3 | Submit L1, the issue and the PR | A reviewed first contribution is the evidence the decision brief asks for |
| 4 | Validate and submit K2 | A serious connection-pool correctness issue |
| 5 | Submit L2 | Important but behaviour-changing; it benefits from maintainer discussion |
| 6 | Submit Y1 and M3 | Independent findings with focused reproductions |
| 7 | Continue T1 | A more complex fix that needs design review |
| 8 | Expand SQLite controls | Useful, but must not delay upstream work. Scope to be defined |

**What changed from the first version of this tracker** (the decision above; K2, L3, and L1 have since been submitted):

- **L3 went before L1.** It is a comment on an open PR, and its evidence was already independently validated. It did not wait for the conformance work.
- **L1 and K2 each had a validation step** before submission. Both steps are done. L1 is #1202 and #1203.

**The decision brief's constraint still holds:** L1, then L2, then A1. All three are submitted. L2 links knex#6546. A1 is discussion #5166.

**Unranked** (placement proposed, not yet confirmed):

- **A1**, the discussion: after L2, as the decision brief orders it.
- **K1:** posted 2026-10-17 as #6547, after K2. **M4:** after Y1, or skip.
- **K3:** posted 2026-10-17 on #4709. It sits with the knex transaction and pool work that #6241 tracks.
- **T2:** not drafted; decide later.
- **L4, L6, L7 and L8:** wait for replies to L1, L2 and A1. **L5** was filed 2026-10-17 as #1204, ahead of those replies.

### Validation steps

**L1 (priority 1). Done.** Posted 2026-10-17 as #1202 and #1203. A new issue links the stale-closed #1006; the PR targets `22.x`. The adversarial pass is recorded in [lucid-isolation-level-fix.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/lucid-isolation-level-fix.md) §9. It covered:

- every invocation form and isolation level, on PostgreSQL and MySQL, proven by effect (visibility or blocking) and not only by reported settings;
- the #1006 consequence scenario;
- nested transactions, and a level the database rejects;
- unchanged behaviour of the managed form;
- the review questions in §6 of the report.

**K2 (priority 4). Done.** Posted 2026-10-17 as #6546.

- The reproduction needs no fault injection ([knex-root-cause-review.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-root-cause-review.md)).
- At posting, knex `master` was still `e25d54bc`. A duplicate search found no matching issue.
- The script was not re-run in the minutes before filing. The posted output is the recorded run.

## 3. Item notes

### 3.1 Lucid and AdonisJS

**L1. Isolation-level fix. Submitted 2026-10-17** as https://github.com/adonisjs/lucid/issues/1202 and https://github.com/adonisjs/lucid/pull/1203 Posted as `KevinBlakeLopez`. A new issue links the stale-closed #1006. The pull request targets `22.x` and says `Resolves #1202`. Head `c8188dab8c2f85fe58b35aeb21028fc1539ffeef`, on [`KevinBlakeLopez/lucid`](https://github.com/KevinBlakeLopez/lucid/tree/fix/manual-transaction-isolation-level) `fix/manual-transaction-isolation-level`, based on `22.x` at `f715bb4`. Fork CI [run 39003708393](https://github.com/KevinBlakeLopez/lucid/actions/runs/39003708393) passed all 9 jobs.

- One follow-up around 2026-10-31. Decide around 2026-11-14 (§4).
- Offer the nested `TypeError` (§3 of the report) only if the maintainers want it. The pull request mentions it and does not pin it. K3 is already #4709.

**L2. Transaction outcome. Submitted 2026-10-21** as https://github.com/adonisjs/lucid/issues/1205 Posted as `KevinBlakeLopez`. Issue only. The body asks the maintainers to agree on the approach before a pull request, because a callback that catches an error and returns normally would start to reject. It links [knex#6546](https://github.com/knex/knex/issues/6546) and [knex#3847](https://github.com/knex/knex/issues/3847), and it does not mention the wider project.

- One follow-up around 2026-11-04 was for silence. A reply arrived 2026-10-21, so that date is no longer a silence ping. Decide around 2026-11-18 (§4) if no maintainer has answered.
- No pull request until the maintainers agree.
- **Reply 2026-10-21** from `jals1212` (Jeffrey León), association `NONE`, not a maintainer: https://github.com/adonisjs/lucid/issues/1205#issuecomment-6324526300 They report case 2 on Lucid 22.4.2 / knex 3.3.0 without connection loss: a `DEFERRABLE INITIALLY DEFERRED` constraint trigger that raises makes `COMMIT` fail, `trx.commit()` and `db.transaction()` still resolve, `after('commit')` runs, and no rows remain. On SQL Server, after `ROLLBACK TRANSACTION`, `COMMIT` fails with error 3902, knex rejects `executionPromise` and resolves `commit()`, and Lucid follows. Their `pnpm` patch awaits `executionPromise` after `commit()`. They say it covers case 2 and a failing `RELEASE SAVEPOINT`, and does not cover cases 1, 3, or 4. This repository has not rerun the deferred-trigger or SQL Server reports. Case 1 remains the command tag `ROLLBACK`, where `commit()` resolves and `executionPromise` does not reject. Awaiting `executionPromise` does not see it. Replied 2026-10-21: https://github.com/adonisjs/lucid/issues/1205#issuecomment-6325444504 The reply does not accept the deferred-trigger or SQL Server reports as measurements from this repository. No pull request.

**L3. PR #1168 comment. Submitted 2026-10-17** as https://github.com/adonisjs/lucid/pull/1168#issuecomment-6237944617 Posted as `KevinBlakeLopez`.

- The comment includes the script inline, because the research repository is private.
- It is evidence on the maintainers' own PR, not a competing PR.
- The comment names the regression in the opening, limits the pool claim to the tested configuration, and qualifies the suggested fix for nontransactional migrations. The script exits 2 when the lock session never ends.
- **Checked 2026-10-21.** https://github.com/adonisjs/lucid/pull/1168 is still open and not merged. Head is still `28e650290e36918217d5c59b830d5af1986d57a1`. Nothing was posted after the 2026-10-17 comment. `thetutlage` has not replied. `simoneNEMO`'s 2026-04-25 comment predates the regression report. No second comment: the existing one still matches this head. Further validation waits on a new head. MySQL and PgBouncer remain untested, which the comment already says.

**A1. Discussion. Submitted 2026-10-21** as https://github.com/orgs/adonisjs/discussions/5166 Posted as `KevinBlakeLopez`, in the Ideas category. Lucid has discussions disabled, so the organization discussion lives on `adonisjs/core`. The body links L1 ([#1202](https://github.com/adonisjs/lucid/issues/1202) and [#1203](https://github.com/adonisjs/lucid/pull/1203)) and mentions L2 ([#1205](https://github.com/adonisjs/lucid/issues/1205)) without the bug's detail. There is no public project link. Signed Kevin Blake Lopez.

- One follow-up around 2026-11-04. Decide around 2026-11-18 (§4).
- The project name contains "Adonis". Be ready to discuss it.

**L5. Missing `down()`. Submitted 2026-10-17** as https://github.com/adonisjs/lucid/issues/1204 Posted as `KevinBlakeLopez`. A new issue. The body is the proposal in [lucid-missing-down-issue-draft.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/lucid-missing-down-issue-draft.md): rollback reports success when `down()` is inherited as a no-op. The duplicate search the same day found no matching issue. §4 sets no follow-up date.

**L4, L6, L7 and L8. Migration candidates.** Ranked in [`upstream-contribution-plan.md`](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/ppcs-migration-research/docs/upstream-contribution-plan.md) (revision 2, 2026-10-17). Each affects AdonisJS applications as they are; none is about standalone use. They wait for replies to L1, L2 and A1.

### 3.2 knex

**K2. Submitted 2026-10-17** as https://github.com/knex/knex/issues/6546 Posted as `KevinBlakeLopez`. Duplicate search the same day found no report of a connection returned to the pool with its transaction open. Nearby and different: #4709 (already commented), #5959 (closed question about a max transaction time), and #4460 (`__knexTxId` left set). The posted text qualifies the stale-status claim and labels pool `validate` a partial mitigation. The change only knex can make. It changes no API.

- **Revision 2 (2026-10-17)** reproduces it without fault injection, through pg's `query_timeout`. It also covers a `COMMIT` that is never sent.
- **Stubbed notes.** Its MySQL and `connectionPool` notes come from a stubbed failure, and the text says so.
- **The suggested change** must reach the MySQL-family `query()` overrides. It must not dispose after `COMMIT` failures the server reports.
- **Evidence:** the [review](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-root-cause-review.md), §3 and its addendum.

**K2-PR. Fix for #6546. Submitted 2026-10-18** as https://github.com/knex/knex/pull/6548 Posted as `KevinBlakeLopez` from the fork `KevinBlakeLopez/knex`, head `32d6d0d`, base `master`. Report and limits: [6546-fix-report.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-root-cause-review/fixes/6546-fix-report.md). Failed `BEGIN` is out of its scope (K3). The local K1 and K3 fix branches conflict with it textually and wait for its feedback. **Checked 2026-10-25:** open, no comments or reviews. Only the `Assign PR to DRI` workflow ran; the CI, unit-test, lint, coverage and CodeQL runs are `action_required`, waiting for a maintainer to approve workflows for a first-time contributor.

**K1. Submitted 2026-10-17** as https://github.com/knex/knex/issues/6547 Posted as `KevinBlakeLopez`. knex `master` was still `e25d54bc`; `lib/execution/transaction.js` and `lib/dialects/postgres/execution/pg-transaction.js` matched knex 3.3.0. The duplicate search the same day found no report of `executionPromise` resolving when PostgreSQL answers `COMMIT` with `ROLLBACK`. The issue asks for that outcome and does not prescribe the settlement implementation. It follows the contract settled in #3847, and does not ask for `commit()` to reject. Detection is PostgreSQL-specific. A second writeup on 2026-10-20, [knex.md](../research/production-reachability/upstream-drafts/knex.md), restates this result from the production-reachability run. Do not file it. #6547 is the submission.

**K3. Failed `BEGIN`. Submitted 2026-10-17** as a regular comment on #4709: https://github.com/knex/knex/issues/4709#issuecomment-6236885052 Posted as `KevinBlakeLopez`. #4709 was still open, with no comment newer than 2025-10-18. knex `master` was still `e25d54bc`, and `lib/execution/transaction.js` matched knex 3.3.0. The reproduction was re-run and matched the posted output. This is not a new issue.

- **Already reported.** #4709 (open since 2021) reports it, and the meta issue #6241 tracks it. A maintainer called it "clearly buggy" on 2025-10-18.
- **The draft is a comment** that adds:
  - the cause: a microtask race in knex. The difference between PostgreSQL and MySQL is incidental; MySQL rejects only because knex sends it a two-statement begin;
  - a trigger with no timeout and no misuse: a nested `trx.transaction()` in an aborted PostgreSQL transaction;
  - the fact that the handler form runs the handler before rejecting;
  - a fix shape, simulated with an unchanged regression matrix.
- **No connection leaks.**
- **A candidate PPCS case.**
- **The L1 PR** (#1203) mentions the nested `TypeError` instead of pinning it in a test. It does not link #4709.

### 3.3 MikroORM

**M1. PR for #8458. Withdrawn 2026-10-17.** The agent's Phase 0 check found [PR #8462](https://github.com/mikro-orm/mikro-orm/pull/8462), opened by another contributor on 2026-10-15. It says "Fixes #8458" and implements the fix our draft sketched. On 2026-10-17 its head was `272a108`, CI was green, and it had no reviews. The agent stopped before cloning, so no branch or `mikroorm-8458-fix.md` exists.

**M2. Comment on PR #8462. Submitted 2026-10-17** as a regular comment, not a review: https://github.com/mikro-orm/mikro-orm/pull/8462#issuecomment-6236026353 Posted as `KevinBlakeLopez`. The head was still `272a1081`, with no reviews and only Codecov's comment. The draft was retargeted from #8458 to #8462 and cut to the two cases the PR does not test: a subscriber that throws in `beforeTransactionRollback` (a trigger with no driver failure, R2b), and two rollbacks failing in a row. The PR's tests mock `connection.rollback()`. **Validated 2026-10-17** ([report](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/mikroorm-pr-8462-validation.md)). On PostgreSQL 18.6 and MySQL 8.0.44, the scenarios fail at the PR's base `aafc511d` (12 failed, 4 passed). They pass at its head `272a1081` (16 passed), and also with its diff applied to current master. The posted comment compresses those scenarios, keeps the two test snippets as run, and does not suggest `TransactionStateError`.

**M2 closed 2026-10-22.** B4nan approved #8462 at 04:25 UTC and merged it at 04:43 UTC (merge commit `1610b600`). Before merging, the author added `895e134e` ("cover explicit commit after a failed savepoint rollback") and merged `master`, so the merged head is `d3d3b5da`, not the validated `272a1081`. No one replied to the M2 comment. The PR's diff does not contain `beforeTransactionRollback`, so the suggested subscriber test was not added. The merged head was not re-validated.

**Follow-up checks (2026-10-17).**

- **A, in-repo.** The two tests were added to MikroORM's `transaction-propagation` files (commit `ea9c86b1` on `../mikro-orm`, pushed to the fork as `next`). They pass with the PR on PostgreSQL, MySQL, MariaDB and SQLite (195/195), and exactly those tests fail at the base. On SQLite they must sit before the existing test that rejects every `rollback()`. That ordering note is in the validation report, not in the posted comment.
- **D, mutation testing.** Each test is the only one that catches one unsafe regression of the fix. The subscriber test also fails on one safe alternative. The posted comment distinguishes that alternative from the unsafe misses.
- **C, fork CI.** [Run 39044037619](https://github.com/KevinBlakeLopez/mikro-orm/actions/runs/39044037619) on `KevinBlakeLopez/mikro-orm` passed, including MSSQL (56/56 in `transaction-propagation.test.ts`). The posted comment links it. The Release job was skipped because it is limited to the upstream owner.

**M3. T4f. Closed 2026-10-22** as completed via https://github.com/mikro-orm/mikro-orm/pull/8499. Submitted 2026-10-18 as https://github.com/mikro-orm/mikro-orm/issues/8476 Posted as `KevinBlakeLopez`. Follow-up `research/production-reachability/runs/2026-10-22T12-18-31Z-928c75` on 7.2.6-dev.19: `em.transactional()` and `em.commit()` rejected `25P02`. The marker was absent. Savepoint recovery committed. npm `latest` was still 7.2.5. dev.19 does not contain the #8462 savepoint change. Revision 2 of the draft. Bare Kysely 0.29.6 and 0.29.7 resolve the same `COMMIT`, and `pg` records the command tag `ROLLBACK`. A single `em.transactional()`, with no nesting, does the same. `REQUIRED` adds no savepoint. A successful `NESTED` rollback still ends in command tag `COMMIT`. No separate Kysely issue was opened. The duplicate search the same day still finds only #8458, which is a different trigger. 7.2.5 was still the latest release.

**M4. PR #8448 comment. Submitted 2026-10-18** as https://github.com/mikro-orm/mikro-orm/pull/8448#issuecomment-6249891879 Posted as `KevinBlakeLopez`. The PR had already merged on 2026-10-15 (`ada68f83`). The only earlier comment was Codecov's. Published MikroORM was still 7.2.5, pinning `kysely@0.29.6`. The comment links the Y1 comment. It was not re-run against the later bare-Kysely results.

**Not ours:** the pool slot leak after a failed top-level `ROLLBACK` (#8447, PR #8448) is already reported and has a PR by someone else.

### 3.4 Kysely

**Y1. kysely#1990. Submitted 2026-10-18** as https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924 Posted as `KevinBlakeLopez`. Comment 1 of revision 4. Immediately before posting, the last comment was still the 2026-10-17 close, and npm `latest` was still 0.29.7. No new issue and no pull request. The posted text is on `docs/kysely-y1-review`. A `ROLLBACK` that never reaches PostgreSQL can return the open transaction to the pool, and the next `COMMIT` can include its writes. `query_timeout` reproduces it with no injection. The callback API already did this on 0.29.6. The comment does not prescribe how a discard crosses the connection provider. Checked 2026-10-20: no comment after this one. #1990 stays closed.

**Y2. `isCommitted` after a caught `23505`. Submitted 2026-10-21** as https://github.com/kysely-org/kysely/issues/2157. Not Y1. On run `2026-10-19T18-15-49Z-b2c174`, explicit `commit().execute()` resolved and `driver.isCommitted` was `true` while the row was absent. Managed `db.transaction().execute()` resolved and the row was absent. That case logs `driver.isCommitted` as `null`. Neither Kysely case logs `command_tag`. The `ROLLBACK` tag in the same run is the pg control. The managed internal flag is source in `TransactionBuilder.execute`, not a logged value. Savepoint recovery committed the kept row and logged `isCommitted` true. Duplicate search the same day: `isCommitted` returned only #1990. `ROLLBACK` with commit returned #1894. `23505` returned nothing. `command tag` returned #428. npm `latest` was 0.29.7, and its `commitTransaction` still discards the result before `isCommitted` is set. No pull request. M3 (#8476) already reports the MikroORM call that goes through this driver path. Y2 is the Kysely issue M3 deliberately did not open. **Checked 2026-10-25:** the maintainer `igalklebanov` opened https://github.com/kysely-org/kysely/pull/2161 ("fix(postgres): reject commits that roll back aborted transactions", body "closes #2157") on 2026-10-21 and labeled #2157 `postgres` and `built-in dialect` on 2026-10-22. #2161 was open. No comment on #2157.

**Y3. Validation comment on PR #2161. Submitted 2026-10-25** as https://github.com/kysely-org/kysely/pull/2161#issuecomment-6403967170 Posted as `KevinBlakeLopez`.

- **Setup:** PR head `ef60ffe` (the pkg.pr.new build) against npm 0.29.7, the PR's base (tag `v0.29.7`). pg 8.23.1, Node.js 24.14.1, PostgreSQL 18.6, three runs per build.
- **Result:** both #2157 paths reject with `AbortedTransactionError`. On both builds the server shows `aborted` and no row.
- **Controls:** plain commit, savepoint recovery, and a deferred FK failing at `COMMIT` are unchanged. The pooled connection is idle and reusable after every case.
- **Included:** a note that the 0.29.7 `commit()` docs pattern (`rollback()` in the catch) now surfaces `Transaction is already rolled back`.
- **Left out:** raw `` sql`commit` `` and `` sql`rollback` `` now return a `{ command }` row.
- **Before posting:** the head was unchanged, with no human comments or reviews.
- **After posting:** the body returned by the API matched the draft.
- **Evidence:** [`kysely-pr-2161-validation/`](../research/production-reachability/kysely-pr-2161-validation/README.md).

### 3.5 TypeORM

**T1. Nested start, then savepoint-rollback depth.**

The earlier description covered only the depth desync: after a failed `ROLLBACK TO SAVEPOINT`, `transactionDepth` stays one too high. Simply decrementing it would make the outer commit send a real `COMMIT`. When the savepoint rollback was never sent, that commits the inner writes. That finding still holds, and it is no longer the whole of T1.

Later experiments found a prerequisite. `EntityManager.transaction()` calls `rollbackTransaction()` whenever `startTransaction()` throws. A nested start that fails before it opens a level has not changed `transactionDepth`, so that rollback hits the caller's transaction. On PostgreSQL, a throw from `beforeTransactionStart` during a nested start also clears `isTransactionActive` while a transaction is already open, so no `ROLLBACK` is sent and the connection stays in the transaction. The no-injection lead case is FS3. Evidence: [HANDOFF.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-savepoint-depth-fix/HANDOFF.md) (T0) and [design-review.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-savepoint-depth-fix/design-review.md) §7.

Keep the two later distinctions:

- **Depth recovery** uses the per-depth unresolved list (`unresolvedSavepointRollbacks`). Both single-record forms fail scenario H2. Do not replace that list.
- **Connection disposal** after a failed cleanup is separate. The `asyncDispose` rollback is held in `patches/held-back-asyncdispose-rollback.diff`. Do not put it back, and do not fold a failed top-level `ROLLBACK` into the savepoint fix.

**Submitted 2026-10-17 and 2026-10-18**, after this section still said nothing was filed.

- **Nested start.** https://github.com/typeorm/typeorm/issues/12976 and https://github.com/typeorm/typeorm/pull/12979 Posted as `KevinBlakeLopez`. The pull request is "keep the caller transaction when a nested start fails." Checked 2026-10-20: #12976 has no comments. #12979 has an automated Qodo review and no human review.
- **Failed savepoint rollback.** https://github.com/typeorm/typeorm/issues/12977 Posted as `KevinBlakeLopez`. A failed `ROLLBACK TO SAVEPOINT` leaves the connection in a transaction. No comments as of 2026-10-20. This is the finding the handoff said not to ship ahead of the nested-start fix. It was filed the same minute as #12976. The per-depth unresolved-rollback patch is not what #12977's title describes.
- **Checked 2026-10-25.** Still no human comments on #12976 or #12977, and no human review on #12979. `Asadshah7950` opened PR #12983 ("Fixes #12976", 2026-10-20), which competes with #12979, and PR #12997 ("Fixes #12977", 2026-10-23). Neither has maintainer activity.

The local branches named in the old note may still hold uncommitted patch work. Do not open another nested-start issue or pull request. Do not combine that work with T3 unless a maintainer asks.

### 3.6 T2: other TypeORM findings

From [`typeorm-objection-sequelize-assessment.md`](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/typeorm-objection-sequelize-assessment.md), not drafted. Decide after T1's reception.

| Finding | Experiments | Status |
| --- | --- | --- |
| A failed top-level `ROLLBACK` returns the connection to the pool inside its transaction; the next unit of work commits the doomed write | TR1d, TR1d3, TR3a | **Submitted 2026-10-18** as https://github.com/typeorm/typeorm/issues/12978 The TypeORM counterpart of knex K2. `bunnysayzz` replied the same day and pointed at fix PR #12980 |
| A rollback error vanishes in `catch (rollbackError) {}`; the documented manual pattern loses the original error | TR1d, TR1d3, TR4a | Not drafted |
| `COMMIT` answered with `ROLLBACK` is reported as success, and `afterTransactionCommit` runs | TT1a, TT1b, TH1c, TH1f, TH1g | **Submitted 2026-10-21** as https://github.com/typeorm/typeorm/issues/12992 The PR-01 hook counts and the driver-trace tag are the first repetition. All three repetitions resolved with the row absent. Not covered by #12976–#12979 |
| `@VersionColumn` writes a stale version back, losing the update silently | TC1a | Not drafted |
| A subscriber without `@EventSubscriber()` is dropped without a warning | TT5a | Not drafted |
| `await using` commits when the scope exits by an exception | TT2c | Already reported as #12913; a comment at most |

### 3.7 Spring, psycopg, and pgjdbc

These come from the production-reachability runs on 2026-10-19. The main run is `2026-10-19T18-15-49Z-b2c174`. Django's manual `commit()` is the follow-up `2026-10-19T20-58-26Z-508b7a`. Each executed case was repeated three times. A caught `23505` left the transaction aborted and the row absent. The psycopg cases did not read a command tag. SQLAlchemy Core logged psycopg's status moving `INERROR` to `IDLE` on `COMMIT`. Django logged the server session moving from `idle in transaction (aborted)` to `idle`, with last statement `COMMIT`. pgjdbc `Connection.commit()` is void and did not log a tag either.

**S1. Spring `afterCommit`. Ready 2026-10-20. Not filed.** Spring Framework 7.0.9 `DataSourceTransactionManager` calls `Connection.commit()`. pgjdbc 42.7.14 returns. `afterCommit` runs and `afterCompletion` is `STATUS_COMMITTED`. Hook counts and the before-end session state are the first repetition. Three repetitions agree that the call returned, the transaction was aborted, and the marker was absent. That split was measured for `TransactionTemplate`, `@Transactional` when the `SQLException` is caught, and `getTransaction` / `commit`. Same-backend reuse is the pooled rows only. The run recorded Java 27. The pom compiler release is 21. The run did not log a command tag or `PgConnection.getTransactionState()`. The draft does not claim a `ROLLBACK` tag for these rows. The four `TransactionTemplate` `PROPAGATION_NESTED` rows committed the outer row. The declarative nested row did not commit the outer row. The harness records that row INCONCLUSIVE: the violation is `25P02`, not `23505`. Draft: [spring-framework.md](../research/production-reachability/upstream-drafts/spring-framework.md). Not Spring issue #28685, where `afterCommit` itself throws. J1 is the driver question and is already submitted. S1 is still the Spring report. Redo the duplicate search and the release check before posting.

**P1. psycopg `commit()`. Submitted 2026-10-21** as https://github.com/psycopg/psycopg/issues/1453 Posted as `KevinBlakeLopez`. No pull request. Same-day search: `ROLLBACK commit` did not return this case. Open #1451 is a cancelled `AsyncConnection.transaction()` entry, not this `commit()` return. PyPI `latest` was 3.3.6, uploaded 2026-09-18. The issue body is `reproductions/psycopg_commit_tag.py`, and the output block is that program's full stdout from one run the same day. The program reads `DATABASE_URL`, creates database `ppcs_repro_psycopg_tag`, and drops it. It does not drop tables in an existing database, and it does not reuse the connection after `commit()`. psycopg 3.3.6, server `18.6 (Debian 18.6-1.pgdg13+2)`. A normal `commit()` was visible as `['seen']`. After a caught `23505`, `commit()` returned `None`, status went `INERROR` to `IDLE`, and the other connection saw `[]`. `cursor.execute("COMMIT")` on a second connection logged `ROLLBACK` and `COMMAND_OK`. The program does not call `pgconn.trace()`. Installed 3.3.6 line numbers: `commit` is `connection.py` 306–309, `_commit_gen` starts at `_connection_base.py` 577 and yields at 592, `_exec_command` starts at 443. The 2026-10-19 case files already record driver 3.3.6. The body names SQLAlchemy Core and Django's manual `transaction.commit()` as callers. Core's later committed transaction was a new `Engine.connect()` checkout on the same PostgreSQL backend. Django's later transaction was on that connection. Django's manual observation is follow-up `2026-10-19T20-58-26Z-508b7a`. The earlier Django explicit case in `b2c174` reported `rolled_back` because the adapter raised `on_commit() cannot be used in manual transaction management`; the basis is that the body threw and `transaction.rollback()` was called. The adapter source hashes differ (`7a09a9af` and `de213cdd`). Django `atomic()` rolled back. SQLAlchemy ORM is not this item. Draft: [psycopg.md](../research/production-reachability/upstream-drafts/psycopg.md). One issue, to psycopg. Do not also open SQLAlchemy and Django issues.

**J1. pgjdbc. Submitted 2026-10-19** as https://github.com/pgjdbc/pgjdbc/issues/4494 Posted as `KevinBlakeLopez`. The question is whether `Connection.commit()` should report that PostgreSQL answered `COMMIT` with `ROLLBACK`. **Reply 2026-10-20** from Dave Cramer: `commit()` should report it, and he asked for the use case. **Answered 2026-10-21** at https://github.com/pgjdbc/pgjdbc/issues/4494#issuecomment-6316574491 The use case is a caller that caught the original error and then treats a normal `commit()` return as success. The measured caller is Spring Framework 7.0.9: `afterCommit` runs and `afterCompletion` is `STATUS_COMMITTED` while `pg_xact_status` is `aborted`. No second pgjdbc issue. **Maintainer PRs 2026-10-22:** `vlsi` opened https://github.com/pgjdbc/pgjdbc/pull/4499 ("add raiseExceptionOnSilentRollback to make commit() throw when the server rolls back a failed transaction", "See #4494") and https://github.com/pgjdbc/pgjdbc/pull/4496 (XA: report `XA_RBROLLBACK` when prepare or one-phase commit meets an aborted branch). Both were open on 2026-10-25, with no reviews. #4499 is opt-in, so S1's driver half is not fixed by default even if it merges.

**T3. TypeORM commit hook. Submitted 2026-10-21** as https://github.com/typeorm/typeorm/issues/12992 Posted as `KevinBlakeLopez`. No pull request. Duplicate search the same day found no report of `afterTransactionCommit` after a PostgreSQL `COMMIT` tag of `ROLLBACK`. npm `latest` and the GitHub release were still 1.1.2, published 2026-10-08. The body cites https://www.postgresql.org/docs/current/tutorial-transactions.html for the aborted transaction block. The PostgreSQL 18 `COMMIT` page does not state the command tag, and the body does not cite it for that. The issue body uses a repository-insert example and says that example is not the code that was executed. The stated differences are `qty: 0`, a subscriber that counted calls, `select pg_current_xact_id()::text as xid, pg_backend_pid() as pid` between the inserts, and `select 1 as ok` after `COMMIT`. The paragraph names the `Item` and `Uniq` columns. The evidence split is unchanged: on run `2026-10-19T18-15-49Z-b2c174`, all three repetitions resolved with the transaction aborted and the row absent. Hook counts and the driver-trace tag `ROLLBACK` are the first repetition only, and the run does not order the hook against the tag. `command_tag` on the case file is `null`. `query("COMMIT")` returns `raw.rows` and does not pass `raw.command` to `commitTransaction()`. Explicit `commitTransaction()` matches. The savepoint recovery committed the row on all three repetitions. Its subscriber counts are the first repetition, one subscriber with both methods. Expected does not require the call to reject. #12976, #12977, #12978, and #12979 do not report this. Draft: [typeorm.md](../research/production-reachability/upstream-drafts/typeorm.md). **Checked 2026-10-25:** no comments. `lazerg` opened PR #12993 ("Fixes #12992") on 2026-10-22; no maintainer activity.

**D1. Drizzle `db.transaction()`. Submitted 2026-10-22** as https://github.com/drizzle-team/drizzle-orm/issues/6572 Posted as `KevinBlakeLopez`. No pull request. Duplicate search on 2026-10-22 found no report of this `COMMIT` tag. npm `latest` was still 0.45.4. The `rc` tag was 1.0.0-rc.5, published 2026-10-21. Caught-commit was run on 1.0.0-rc.5 the same day: `reports/examples/2026-10-22T13-28-31Z-671f3e`. Three runs resolved with the transaction aborted and the row absent. The first run's tag was `ROLLBACK`. The 0.45.4 recording is `reports/examples/2026-10-19T13-38-47Z-39ea07`, with the same split. `NodePgSession.transaction` sends `COMMIT` and returns the callback value. It does not read `Result.command`. In 1.0.0-rc.5 that function is lines 52–86. A failed `BEGIN` releases the client. That is not this issue. Draft: [drizzle.md](../research/production-reachability/upstream-drafts/drizzle.md). The failed-rollback pool release, the `BEGIN` checkout leak, and the checked-out `'error'` process exit are not this issue. P1 is filed as #1453. T3 is filed as #12992. Issue only. **Checked 2026-10-25:** no comments. `princejain756` opened PR #6574 ("Fixes #6572") on 2026-10-22; no maintainer activity.

**PI1. Prisma `$transaction()`. Submitted 2026-10-23** as a regular comment on prisma/orm #20496: https://github.com/prisma/orm/issues/20496#issuecomment-6372520392 Posted as `KevinBlakeLopez`. The posted body matches the draft. Before posting: #20496 was still open, with no comment after 2023-08-07. The `v7` head was still the 7.10.1 tag commit `97ea359`, and npm `latest` was 7.10.1 for `@prisma/client` and `@prisma/adapter-pg`. A same-day search found no newer report. Prisma Client 7.10.1 and `@prisma/adapter-pg` 7.10.1 send `COMMIT` through `executeRaw`, which returns `rowCount` and does not read `result.command`. The transaction manager treats that resolved promise as a commit. The first repetition's tag was `ROLLBACK`. Three repetitions agreed that the call resolved and the row inserted before the error was absent. Evidence: run `2026-10-21T14-10-47Z-148b69` ([FINDINGS.md](../adapters/prisma/FINDINGS.md)), not the 2026-10-19 runs this section starts from. Draft: [prisma.md](../research/production-reachability/upstream-drafts/prisma.md). #20496 has been open since 2023-08-02 and reports the same loss after a caught unique violation on Prisma 5.1.0. The comment says the run used `$executeRaw`, not that issue's `tx.user.create()`. A failed `ROLLBACK` released with no error is not part of this comment. Comment only, with no pull request. **Checked 2026-10-25:** the only later comment is `prisma-asks[bot]`'s automated triage note (2026-10-23, "considering it now"). No maintainer reply.

### 3.8 Not planned

- **Objection.js and Sequelize.** Nothing planned; both stopped at the maintenance gate.
- **Making knex's `commit()` reject.** #3847 settled that contract.
- **A Lucid fork.** Excluded by the persistence standard (PS-IM-1).

### 3.9 Python: psycopg `transaction()`, asyncpg and Tortoise (PY-1b, PY-2, PY-3)

These come from [`python-upstream-contribution-roadmap.md`](../research/python-upstream-contribution-roadmap.md). Their status is kept in [`python-upstream-contribution-tracker.md`](../research/python-upstream-contribution-tracker.md).

**PY-1b. psycopg `transaction()`. Submitted 2026-10-24** as a comment on #1453 (P1): https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348 Posted as `KevinBlakeLopez`. The posted body matches the draft.

- **What it reports.** `with conn.transaction() as tx:` exits normally, and `tx.status` is `committed`, after PostgreSQL aborted the transaction. It explains why a fix to `commit()` alone would not reach the block.
- **The compatibility note.** `test_auto_transaction_fail` and `test_outer_transaction_error` expect normal returns. A fix that only corrects `status` conflicts with neither test.
- **Before posting:** #1453 was still open, with no comment. `master` `99356800e` and the linked files were unchanged. PyPI `latest` was 3.3.6.

**PY-2. asyncpg `Transaction.commit()`. Submitted 2026-10-24** as https://github.com/MagicStack/asyncpg/issues/1400 Posted as `KevinBlakeLopez`. The filed title and body match the draft.

- **What it contains:**
  - a standalone reproduction (CHK-2: three runs each on asyncio and on uvloop, independently re-run by an outside reviewer);
  - the line where `Transaction.__commit` drops the command status;
  - a question for the maintainers: raise, or stop recording the transaction as committed? `test_timeout_06` expects the current normal exit.
- **Before filing:** a same-day duplicate search found nothing, and PyPI `latest` was 0.32.0.
- **Downstream:** Tortoise and SQLAlchemy are named only as callers. Do not file them separately.

**PY-3. Tortoise `Model.save()` after a rollback. Submitted 2026-10-25** as https://github.com/tortoise/tortoise-orm/issues/2383 Posted as `KevinBlakeLopez`. The filed title and body match the draft, compared through the API.

- **What it contains:** a standalone reproduction (CHK-5: three runs per backend on asyncpg and psycopg, independently re-run by an outside reviewer); the default-path line that ignores `execute_update()`'s count; the savepoint case; and a question: reset `_saved_in_db` per rolled-back scope, or act on a 0-row UPDATE. A PR is offered for either.
- **Before filing:** no issue or PR created or updated after 01:30 UTC; `develop` still `ad0d6ce2b`; PyPI `latest` 1.1.9; #2293 open; #1212 without comments.
- **Not this issue:** PY-8 (COMMIT-time exception translation) is separate and not filed.

## 4. Waiting for replies

**For L1, L2 and A1** ([decision brief](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/persistence-decision-brief.md)):

- Allow about **two weeks** for a first reply, then send **one** polite follow-up.
- Decide at about **four weeks** after posting. Silence is not a "no", but it is not evidence either.
- Interest is not commitment. Continuing on the Lucid path needs evidence of agreed package boundaries, a reviewed first contribution (L1 counts), and a way to avoid duplicating AdonisJS infrastructure.

**For the other upstreams** no general rule has been set. These items do not decide the persistence choice. They do bear on how much integration code a MikroORM or TypeORM path would need permanently. Record dates here, so replies can be judged.

Knex (K1, K2, K2-PR, K3), MikroORM (M4), Kysely (Y1, Y2, Y3), and Prisma (PI1) have no follow-up date. M2 and M3 are closed.

**Recheck 2026-10-25.** Every Submitted row was rechecked on GitHub. Changes since the last per-item checks: M2 closed (#8462 merged 2026-10-22); maintainer fix PRs for Y2 (Kysely #2161) and J1 (pgjdbc #4499, #4496); outside-contributor PRs for K1 (#6549), T1 (#12983, #12997), T3 (#12993) and D1 (#6574), none with maintainer activity; a bot triage note on PI1; K2-PR still waits for CI approval. No new human reply on L1, L3, L5, A1, K1, K2, K3, M4, Y1, P1, PY-1b, PY-2 or PY-3. Y1 still has no reply after the 2026-10-18 comment.

**PY-1b, PY-2 and PY-3** follow the Python roadmap's rule (§14 of [`python-upstream-contribution-roadmap.md`](../research/python-upstream-contribution-roadmap.md)). Send one polite follow-up around 2026-11-07 if there is no reply, and decide around 2026-11-21; for PY-3, follow up around 2026-11-08 and decide around 2026-11-22. Expect asyncpg to be slow: its maintainer described an overwhelmed inbox in asyncpg #1355.

**J1 has a reply, and the use-case question is answered.** Dave Cramer, 2026-10-20, on https://github.com/pgjdbc/pgjdbc/issues/4494 said `commit()` should report the rollback and asked for the use case. The use case was posted 2026-10-21: https://github.com/pgjdbc/pgjdbc/issues/4494#issuecomment-6316574491 Wait for his next reply. No second pgjdbc issue. On 2026-10-22 `vlsi` opened PRs #4499 and #4496, which reference #4494 (§3.7).

**T2 has a non-maintainer reply.** `bunnysayzz`, 2026-10-18, on https://github.com/typeorm/typeorm/issues/12978 pointed at the `release()` path and at fix PR #12980. #12976 and #12977 have no comments. #12979 has an automated review only. Checked 2026-10-25: unchanged, apart from the outside PRs in §3.5.

**L2 has a non-maintainer reply.** `jals1212`, 2026-10-21, on https://github.com/adonisjs/lucid/issues/1205#issuecomment-6324526300 Their patch awaits `executionPromise` after `commit()`. That matches case 2, a `COMMIT` that fails. It does not match case 1, where PostgreSQL answers `COMMIT` with command tag `ROLLBACK` and the knex promise resolves. No maintainer has replied. Replied 2026-10-21 at https://github.com/adonisjs/lucid/issues/1205#issuecomment-6325444504 No pull request.

**L3 was checked 2026-10-21.** https://github.com/adonisjs/lucid/pull/1168 is still open and not merged. Head is still `28e650290e36918217d5c59b830d5af1986d57a1`. No maintainer has acknowledged the regression. Nothing was posted after the 2026-10-17 comment. The existing comment still matches this head, so no second comment was posted. Further validation waits on a new head.

**Dependency on PPCS.** L1 is submitted, so the TX-05 Lucid explicit-isolation FAIL is reported. MikroORM and TypeORM had no TX-05 FAIL ([TX-05 draft](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/ppcs-tx05-isolation-level/README.md)). L5 is submitted as #1204, so the MG-03 no-reversal FAIL is reported too. Publishing `migrations-mg02-mg03` is no longer held for an unfiled Lucid finding.

## 5. Submission log

| ID | Submitted | Link | Follow-up due | Reply | Outcome |
| --- | --- | --- | --- | --- | --- |
| M2 | 2026-10-17 | https://github.com/mikro-orm/mikro-orm/pull/8462#issuecomment-6236026353 | — | No reply. #8462 approved and merged by B4nan 2026-10-22 at `d3d3b5da` | closed |
| K3 | 2026-10-17 | https://github.com/knex/knex/issues/4709#issuecomment-6236885052 | — (§4 sets no date) | — | waiting |
| K2 | 2026-10-17 | https://github.com/knex/knex/issues/6546 | — (§4 sets no date) | — | waiting |
| K2-PR | 2026-10-18 | https://github.com/knex/knex/pull/6548 | — (§4 sets no date) | None as of 2026-10-25. CI workflows `action_required` | waiting |
| L3 | 2026-10-17 | https://github.com/adonisjs/lucid/pull/1168#issuecomment-6237944617 | checked 2026-10-21 | No reply after the 2026-10-17 comment. Head still `28e65029`. PR still open | waiting |
| K1 | 2026-10-17 | https://github.com/knex/knex/issues/6547 | — (§4 sets no date) | No comment. Outside PR #6549 | waiting |
| L1 | 2026-10-17 | https://github.com/adonisjs/lucid/issues/1202 and https://github.com/adonisjs/lucid/pull/1203 | 2026-10-31 (one follow-up); decide around 2026-11-14 (§4) | — | waiting |
| L5 | 2026-10-17 | https://github.com/adonisjs/lucid/issues/1204 | — (§4 sets no date) | — | waiting |
| Y1 | 2026-10-18 | https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924 | — (§4 sets no date) | — | waiting |
| Y2 | 2026-10-21 | https://github.com/kysely-org/kysely/issues/2157 | — (§4 sets no date) | Maintainer `igalklebanov` opened PR #2161 (closes #2157) 2026-10-21 and labeled the issue | fix PR open |
| Y3 | 2026-10-25 | https://github.com/kysely-org/kysely/pull/2161#issuecomment-6403967170 | — (§4 sets no date) | — | waiting |
| M4 | 2026-10-18 | https://github.com/mikro-orm/mikro-orm/pull/8448#issuecomment-6249891879 | — (§4 sets no date) | — | waiting |
| M3 | 2026-10-18 | https://github.com/mikro-orm/mikro-orm/issues/8476 | — | Closed 2026-10-22 as completed via #8499. Retested on 7.2.6-dev.19 | closed |
| J1 | 2026-10-19 | https://github.com/pgjdbc/pgjdbc/issues/4494 | — | Dave Cramer, 2026-10-20: `commit()` should report it; he asked for the use case. Use case answered 2026-10-21: https://github.com/pgjdbc/pgjdbc/issues/4494#issuecomment-6316574491 `vlsi` opened PRs #4499 and #4496 on 2026-10-22 | maintainer PRs open |
| T1 | 2026-10-17 | https://github.com/typeorm/typeorm/issues/12976 https://github.com/typeorm/typeorm/issues/12977 and https://github.com/typeorm/typeorm/pull/12979 | — | #12979 has an automated Qodo review only. Outside PRs #12983 and #12997 | waiting |
| T2 | 2026-10-18 | https://github.com/typeorm/typeorm/issues/12978 | — | `bunnysayzz`, 2026-10-18, pointed at PR #12980 | reply received |
| T3 | 2026-10-21 | https://github.com/typeorm/typeorm/issues/12992 | — (§4 sets no date) | No comment. Outside PR #12993 | waiting |
| P1 | 2026-10-21 | https://github.com/psycopg/psycopg/issues/1453 | — (§4 sets no date) | — | waiting |
| D1 | 2026-10-22 | https://github.com/drizzle-team/drizzle-orm/issues/6572 | — (§4 sets no date) | No comment. Outside PR #6574 | waiting |
| PI1 | 2026-10-23 | https://github.com/prisma/orm/issues/20496#issuecomment-6372520392 | — (§4 sets no date) | Automated `prisma-asks[bot]` triage note only | waiting |
| L2 | 2026-10-21 | https://github.com/adonisjs/lucid/issues/1205 | decide around 2026-11-18 if no maintainer replies (§4). The 2026-11-04 silence ping is cancelled | `jals1212`, 2026-10-21, not a maintainer. `executionPromise` patch covers their case 2, not case 1 | reply received |
| A1 | 2026-10-21 | https://github.com/orgs/adonisjs/discussions/5166 | 2026-11-04 (one follow-up); decide around 2026-11-18 (§4) | — | waiting |
| PY-1b | 2026-10-24 | https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348 | 2026-11-07 (one follow-up); decide around 2026-11-21 (§4) | — | waiting |
| PY-2 | 2026-10-24 | https://github.com/MagicStack/asyncpg/issues/1400 | 2026-11-07 (one follow-up); decide around 2026-11-21 (§4) | — | waiting |
| PY-3 | 2026-10-25 | https://github.com/tortoise/tortoise-orm/issues/2383 | 2026-11-08 (one follow-up); decide around 2026-11-22 (§4) | — | waiting |

## Change log

- **2026-10-17.** Tracker created. Nothing submitted. M1 and T1 in progress in separate agents.
- **2026-10-17.** M1 withdrawn: PR #8462 (another contributor) already fixes #8458. M2 retargeted to #8462 and cut to the two untested cases; validation of the PR branch in progress. Nothing submitted.
- **2026-10-17.** Re-prioritized: L1 adversarial validation first, then L3 (allowed before L1), L1, K2 (validated first), L2, Y1 and M3, T1, then SQLite controls. A1, M2, K1 and M4 unranked, with proposed placements. Nothing submitted.
- **2026-10-17.** M2 validated: #8462 passes every scenario on PostgreSQL and MySQL; 12 of 16 fail at its base. The comment was rewritten with the results; status Ready. Nothing submitted.
- **2026-10-17.** M2 format decided: a regular PR comment, tightened to about 40 visible lines. #8462 re-checked: head unchanged, no reviews. Awaiting approval of the exact text. Nothing submitted.
- **2026-10-17.** M2 follow-ups. A: the tests pass in MikroORM's own files on 4 drivers. D: each test uniquely catches one unsafe mutant. C: fork created, push blocked by auto mode. Comment updated. Nothing submitted upstream.
- **2026-10-17.** K2 revised (revision 2): reproduced without fault injection through pg's `query_timeout`, extended to a `COMMIT` that is never sent, and the suggested change corrected. K3 found to be #4709 and drafted as a comment there. Evidence: [knex-root-cause-review.md](https://github.com/KevinBlakeLopez/nest-adonis-spike/blob/docs/lucid-isolation-level-fix/docs/knex-root-cause-review.md) (committed as `5f48ab8`) and its addendum. Nothing submitted.
- **2026-10-17.** M2 submitted on PR #8462: https://github.com/mikro-orm/mikro-orm/pull/8462#issuecomment-6236026353 Head still `272a1081`. Fork CI [39044037619](https://github.com/KevinBlakeLopez/mikro-orm/actions/runs/39044037619) passed, including MSSQL. Status Submitted.
- **2026-10-17.** K3 submitted on #4709: https://github.com/knex/knex/issues/4709#issuecomment-6236885052 Issue still open; knex `master` still `e25d54bc`; the reproduction matched. Status Submitted.
- **2026-10-17.** K2 submitted as #6546: https://github.com/knex/knex/issues/6546 knex `master` still `e25d54bc`. Duplicate search found no matching issue. The posted text qualifies the stale-status claim and labels pool `validate` a partial mitigation. Status Submitted.
- **2026-10-17.** L3 submitted on PR #1168: https://github.com/adonisjs/lucid/pull/1168#issuecomment-6237944617 PR still open; head still `28e65029`. Status Submitted.
- **2026-10-17.** K1 submitted as #6547: https://github.com/knex/knex/issues/6547 knex `master` still `e25d54bc`; the two transaction files matched 3.3.0. Duplicate search found no matching issue. The issue asks for the outcome and does not prescribe the settlement path. Status Submitted.
- **2026-10-17.** Corrected the tracker after the five submissions. §2 keeps the original priority order as history and adds the current execution queue: L1, L2, Y1, M3, T1, A1. K2 and L3 are no longer outstanding priorities. T1 now records the nested-start prerequisite, the per-depth unresolved-rollback state, and the separate disposal question. L3 has a monitor-only check on 2026-10-21 to 2026-10-22.
- **2026-10-17.** L1 submitted as #1202 and #1203. A new issue links #1006; the pull request targets `22.x` at head `c8188dab`. Status Submitted. The execution queue now starts at L2.
- **2026-10-17.** L5 submitted as #1204. Posted as `KevinBlakeLopez`. Duplicate search found no matching issue. Status Submitted. L4, L6, L7 and L8 still wait on replies to L1, L2 and A1. The migration-results note in §4 no longer waits on an unfiled finding.
- **2026-10-17.** Y1 revised (revision 2). #1990 was closed the same day with `kysely@0.29.7`, whose `rollback()` releases in a `finally`. The comment is now a follow-up: destroy a still-usable connection instead of returning it inside its transaction. 0.29.7 was read from the published tarball and not run. Status Ready.
- **2026-10-18.** Y1 submitted on #1990: https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924 Comment 1 of revision 4. M4 submitted on merged PR #8448: https://github.com/mikro-orm/mikro-orm/pull/8448#issuecomment-6249891879 M3 submitted as #8476: https://github.com/mikro-orm/mikro-orm/issues/8476 Bare Kysely resolves the same `COMMIT`. No separate Kysely issue. The queue is now L2, T1, A1. L2 waits until 2026-10-21.
- **2026-10-20.** Copied this tracker into the PostgreSQL Persistence Conformance Suite at `docs/upstream-submissions.md`. Older draft links in that copy point at nest-adonis-spike. The 2026-10-20 drafts stay in that suite.
- **2026-10-20.** Recorded submissions that were missing from this file, and the drafts that are not duplicates. J1 is pgjdbc #4494, with Dave Cramer's reply. T1 is #12976, #12977, and #12979. T2 is #12978, with the `bunnysayzz` comment. Y2, S1, P1, and T3 are Ready and are not ahead of L2. The 2026-10-20 Knex draft restates K1 and is not a new item. Y1 still has no reply after the posted comment.
- **2026-10-21.** Answered Dave Cramer's use-case question on pgjdbc #4494: https://github.com/pgjdbc/pgjdbc/issues/4494#issuecomment-6316574491 The caller is application code that catches `23505` and a transaction manager that treats a normal `commit()` return as success. Measured with Spring Framework 7.0.9 `afterCommit`. No second pgjdbc issue.
- **2026-10-21.** L2 draft now links knex#6546 and keeps that failure out of scope. Duplicate search and versions rechecked the same day: no matching Lucid issue; Lucid 22.4.2 and knex 3.3.0 are still current. Not submitted. Issue only, no PR.
- **2026-10-21.** L2 submitted as https://github.com/adonisjs/lucid/issues/1205 Posted as `KevinBlakeLopez`. Issue only. The body asks for agreement before a pull request and links knex#6546. One follow-up around 2026-11-04. Decide around 2026-11-18. The queue is now A1.
- **2026-10-21.** A1 placeholders filled. The draft links lucid #1202, #1203, and #1205. No public project link, because `nest-adonis-spike` is private. Not posted.
- **2026-10-21.** L3 checked. https://github.com/adonisjs/lucid/pull/1168 is still open at `28e65029`. No reply to the regression comment. No second comment.
- **2026-10-21.** A1 submitted as https://github.com/orgs/adonisjs/discussions/5166 Posted as `KevinBlakeLopez` in Ideas. The Lucid sequence L1, L2, A1 is posted. One follow-up around 2026-11-04. Decide around 2026-11-18. Y2, S1, P1, and T3 stay Ready and are not approved to file.
- **2026-10-21.** L2 reply from `jals1212` on #1205: https://github.com/adonisjs/lucid/issues/1205#issuecomment-6324526300 Not a maintainer. Deferred constraint trigger and SQL Server error 3902 are further ways for `COMMIT` to fail while Lucid reports success. Their patch awaits `executionPromise` and does not cover case 1. Replied the same day: https://github.com/adonisjs/lucid/issues/1205#issuecomment-6325444504 The reply separates case 1 from their `executionPromise` patch and does not open a pull request.
- **2026-10-21.** Drafted D1 (Drizzle) and PI1 (Prisma). Both are the `COMMIT` command tag `ROLLBACK` reported as success. Not filed. They come after P1 and T3. Issue only. S1 still waits on pgjdbc #4494.
- **2026-10-21.** Y2 submitted as https://github.com/kysely-org/kysely/issues/2157. Same-day search: `isCommitted` returned only #1990. `ROLLBACK` with commit returned #1894. `23505` returned nothing. `command tag` returned #428. npm latest was 0.29.7 and still sets `isCommitted` after discarding `commit`. No pull request.
- **2026-10-21.** T3 submitted as https://github.com/typeorm/typeorm/issues/12992 Posted as `KevinBlakeLopez`. Same-day search found no duplicate. npm `latest` and the GitHub release were 1.1.2, published 2026-10-08. No pull request.
- **2026-10-21.** P1 submitted as https://github.com/psycopg/psycopg/issues/1453 Posted as `KevinBlakeLopez`. Same-day search found no duplicate. Open #1451 is a cancelled async transaction entry. PyPI `latest` was 3.3.6, uploaded 2026-09-18. No pull request. Do not also file SQLAlchemy or Django.
- **2026-10-22.** M3 closed as completed via #8499. Retested MikroORM 7.2.6-dev.19 in `research/production-reachability/runs/2026-10-22T12-18-31Z-928c75`. Both commit calls rejected. npm `latest` was still 7.2.5.
- **2026-10-22.** D1 submitted as https://github.com/drizzle-team/drizzle-orm/issues/6572 Posted as `KevinBlakeLopez`. Same-day search found no duplicate. npm `latest` was 0.45.4. `rc` was 1.0.0-rc.5, and the caught-commit case was run on that version. No pull request.
- **2026-10-23.** PI1 draft corrected against run `2026-10-21T14-10-47Z-148b69`. The reproduction snippet is labeled as not the executed code. The nested-savepoint paragraph is cut: the recorded nested case raised an application error, not the duplicate insert. The next-transaction claim is cut: the case runs no second transaction. The transaction manager is placed in `@prisma/client`. Not filed.
- **2026-10-23.** PI1 retargeted from a new issue to a comment on prisma/orm #20496. A duplicate search that day found #20496, open since 2023-08-02 with the same loss on Prisma 5.1.0. The 2026-10-21 search had looked for the command tag, which #20496 never mentions. 7.10.1 is the latest stable release, and its tag commit is the `v7` head; neither reads `result.command`. Not posted.
- **2026-10-23.** PI1 submitted as a comment on prisma/orm #20496: https://github.com/prisma/orm/issues/20496#issuecomment-6372520392 Posted as `KevinBlakeLopez`. #20496 was still open. `v7` was still at the 7.10.1 tag commit, and npm `latest` was 7.10.1. A same-day search found no newer report. No pull request. Status Submitted.
- **2026-10-24.** PY-1b and PY-2 submitted, both as `KevinBlakeLopez`, after approval of the exact texts. No pull request. Status Submitted. One follow-up around 2026-11-07; decide around 2026-11-21.
  - **PY-1b:** posted as a comment on psycopg #1453: https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348
  - **PY-2:** filed as https://github.com/MagicStack/asyncpg/issues/1400
  - **Before posting:** #1453 was open, with no comment. Both default branches and the linked files were unchanged. PyPI `latest` was psycopg 3.3.6 and asyncpg 0.32.0. There was no new asyncpg duplicate.
  - **After posting:** both posted texts match the drafts, compared through the API.
- **2026-10-25.** PY-3 submitted as https://github.com/tortoise/tortoise-orm/issues/2383 Posted as `KevinBlakeLopez` after approval of the exact text, which was revised after an outside adversarial review. No pull request. Status Submitted. One follow-up around 2026-11-08; decide around 2026-11-22.
  - **Before filing:** no tortoise-orm issue or PR had been created or updated after 01:30 UTC. `develop` was still `ad0d6ce2b`, so the linked lines held. PyPI `latest` was 1.1.9. #2293 was open; #1212 had no comments.
  - **After filing:** the posted title and body match the draft, compared through the API.
- **2026-10-25.** Rechecked every Submitted and Closed row on GitHub. M2 closed: #8462 merged 2026-10-22 at `d3d3b5da`, without the suggested subscriber test, and not re-validated. Recorded the maintainer fix PRs for Y2 (Kysely #2161) and J1 (pgjdbc #4499 and #4496), the outside-contributor PRs for K1, T1, T3 and D1, and the bot triage note on PI1. Added K2-PR (knex PR #6548, submitted 2026-10-18), which was missing; its CI waits for maintainer approval. Nothing posted.
- **2026-10-25.** Y3 submitted on Kysely PR #2161: https://github.com/kysely-org/kysely/pull/2161#issuecomment-6403967170 It validates the maintainer's fix for Y2 against 0.29.7. Before posting, the head was still `ef60ffe`, with no human comments or reviews. The posted body matches the draft, compared through the API. Evidence: `research/production-reachability/kysely-pr-2161-validation/`. Status Submitted.
