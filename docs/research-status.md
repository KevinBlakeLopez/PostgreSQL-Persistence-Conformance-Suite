# Research status

Inspected 2026-10-23 on `main` at `36dd52f`. This is the inventory to update. The mission stays in [`research-master-plan.md`](research-master-plan.md). The order of work stays in [`research-roadmap.md`](research-roadmap.md).

The 2026-10-21 inspection was `0b611f5`. This pass compared the inventory with the committed tree and with [`upstream-submissions.md`](upstream-submissions.md). It did not re-query GitHub and did not re-run the suite. Filing status below is the tracker's record. A draft banner that still says "Not filed" is the content status of that file.

Completion means the milestone's acceptance criteria are met. A directory, an adapter, or a draft is not completion.

This file describes the repository as inspected. It does not authorize a commit.

## Milestone tracker

| Milestone | Status | Dependencies | Evidence | Acceptance criteria | Next action | Approval required |
| --- | --- | --- | --- | --- | --- | --- |
| PPCS suite on PostgreSQL 18.6 | Complete for the recorded adapters | Disposable server, pinned adapters | Root `README.md` matrix and `reports/examples/` | Classifications recorded with versions, repetitions, and controls | Maintain. Do not add an adapter without a question. | Yes for a new adapter family or a classification-rule change |
| Production-reachability closeout (M0) | Preserved on `36dd52f` | Existing PR-01 runs | `research/production-reachability/`, committed in `64e2f5b` | Roadmap M0 criteria | Do not rerun it. Do not file S1 or PI1 without approval. Do not refile the Knex draft. | Yes before S1, PI1, or any other new post |
| Upstream tracker | Active | Drafts and already-filed issues | `docs/upstream-submissions.md` | Status, link, and draft-versus-filed are accurate | Monitor already-filed items on their dates. Do not post. | Yes before any new post |
| Ownership-benchmark design (M1) | Active | M0 evidence left intact | `docs/ownership-benchmark/` | Maintainer accepts the requirements | Review the draft. Do not implement it. | Yes before pilot execution |
| Python pilot (M2) | Planned | M1 frozen and program approval | None | Methodology-plan exit criteria | Wait | Yes |
| Python V1–V7 benchmark (M3) | Planned | M2 | None | Roadmap M3 | Wait | Yes |
| JVM cohort, .NET cohort, Node ownership cohort | Deferred | M3 and a separate approval | PPCS and Spring/JDBC recordings are evidence only | A cohort specification that is not a wrapper over PPCS | Wait | Yes |
| Observatory | Deferred | Demonstrated need after M3 | None | Experiments need shared orchestration or interactive history | Wait | Yes |
| Repository mining | Deferred | M3 method, plus a bias protocol | None | Protocol accepted | Wait | Yes |
| MySQL or SQLite inside the PPCS harness | Deferred | Written justification | Companion investigations, outside the harness | Master-plan justification | Leave the companion runners where they are | Yes |
| Hibernate adapter | Recorded | A research question and a recorded run | `reports/examples/2026-10-21T15-45-57Z-c3c03b` and `adapters/hibernate/FINDINGS.md` | A gated example run | Do not extend it without a new question. | Yes |

## 1. Existing capabilities

Implemented and verified means a recorded run in `reports/examples/` or a companion evidence directory, with the controls that run required, and a written per-adapter or per-investigation report.

The CI workflow (`.github/workflows/ci.yml`) runs `node harness/run.mjs --adapter=lucid,mikroorm,typeorm,pg-control --expect=reports/examples/2026-10-22T01-26-51Z-fb52c8/run.json`. That file is a later Lucid, MikroORM, TypeORM, and `pg-control` recording. It includes `TX-01B.commit-reply-unseen` and the migration cases those adapters run. The 2026-10-18 file remains the PPCS 0.3.0 recording. `compareWith` in `harness/lib/suite.mjs` treats a result whose case, adapter, and mode are absent from the expected file as a difference. `incomparable` refuses the comparison before the suite starts when the harness digest or the catalog digest differs. `scripts/setup.sh` installs every JavaScript adapter that has a `package.json`. Other adapters are still loaded from `adapter.json` and attempted. This inspection did not re-run CI, so the job's current result on `main` is not established here. Later recorded adapters are real results. They are not rows in that expected file.

| Capability | State |
| --- | --- |
| Catalog families CTL-01, TX-01A, TX-01B, TX-02, TX-03, TX-04, TX-05, MG-02, MG-03 | Implemented. Coverage depends on the adapter. The root README states which cases each adapter runs. |
| Runner, observer, classification, three-repetition gate, CTL-01 gate, `pg-control` gate | Implemented and covered by `pnpm run test` and `pnpm run test:methodology` |
| Lucid 22.4.2, MikroORM 7.2.5, TypeORM 1.1.2, `pg-control` | Recorded in `reports/examples/2026-10-18T00-11-46Z-95887b`, PPCS 0.3.0. CI expects the 2026-10-22 file named above |
| Django 6.1.2, SQLAlchemy 2.1.5 ORM and Core, Tortoise 1.1.9, Spring JDBC 7.0.9, Spring transaction management 7.0.9, JDBC control 42.7.14, Drizzle 0.45.4 and 1.0.0-rc.4, Prisma Client 7.10.1 | Later recorded runs, linked from the root README. Not the CI `--expect` target. |
| Hibernate 7.4.13.Final, jOOQ 3.21.9, Laravel v13.38.0, Active Record 8.1.4, EF Core 10.0.13, GORM v1.31.2, SQLx 0.9.0, and the PDO, ruby-pg, Npgsql, pgx, and `database/sql` controls | Recorded runs, linked from the root README. Sections 11–14 name the task records. Not the CI `--expect` target. |
| `PR-01` production-reachability catalog | On `main` since `64e2f5b`. Recorded under `research/production-reachability/runs/`. Harness PASS does not mean the commit report was correct. |
| MySQL 8.4 companion runner | Investigated and recorded under `investigations/mysql-innodb-baseline/`. The PHP and CodeIgniter 4 companion is `investigations/mysql-innodb-baseline/php/`, evidence `php-mx01.json`, finished `2026-10-21T17:15:26.400Z`. Not a PPCS adapter. |
| SQLite phase 0, sqlite3 control, SQLAlchemy Core comparison | Investigated and recorded under `research/sqlite-phase0/`. Not a PPCS adapter. |
| Drizzle follow-up probe | `investigations/drizzle-followups/probe.mjs` only. No evidence directory. Not a recorded result. The category B suite re-run is section 14. |

`PR-01` case files do not have a `pg-control` expectation. The run summary says so. CTL-01 held for the adapters in the main run. The contract verdicts are the research report, not the harness classification.

## 2. Completed investigations

These are complete as investigations. They are not a license to port them into the PostgreSQL harness.

**PPCS transaction and migration matrix.** The root README is the matrix. Notable recorded shapes, each with its own fault category:

- Category A `TX-01A` is a caught unique violation and then the normal completion path. Several frameworks FAIL with the COMMIT-answered-ROLLBACK mechanism exercised (SQLAlchemy Core, Drizzle, Prisma, and others in the matrix). Django's `atomic()` PASS does not exercise that mechanism: Django rolls back, so `COMMIT` is not the statement that ends the transaction. SQLAlchemy ORM's TX-01A result is INCONCLUSIVE because flush rolls back before `before-end`.
- Category C and D results are injected or simulated. They are not production-reachability claims.
- MG-02 and MG-03 are recorded for Lucid and `pg-control`. Lucid's `MG-03.no-reversal` FAIL is the subject of lucid#1204, which the tracker records as submitted.

**Production-reachability, contract layer.** Authoritative run: `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174`. PostgreSQL 18.6, image digest recorded in that summary, Node v24.14.1, three repetitions, 87 harness PASS and 3 harness INCONCLUSIVE. Catalog sha256 prefix `405731e049f8`. Harness sha256 prefix `af929302a2da`. That digest is the classifier as it ran. The tree is on `main` since `64e2f5b`. `0d69b27` later changed `harness/lib/classify.mjs` for `TX-01B.commit-reply-unseen`, so a checkout of `36dd52f` will not reproduce `af929302a2da`. Do not rerun PR-01 to make the digest match.

Django manual `commit()` follow-up: `2026-10-19T20-58-26Z-508b7a`. An earlier follow-up, `2026-10-19T18-34-44Z-8139f2`, records the same explicit-commit outcome. The report cites the later one. Runs `2026-10-19T17-50-05Z-90b4ea` and `2026-10-19T17-50-45Z-a66571` did not hold their controls or were partial. Run `2026-10-19T18-11-24Z-a70895` is a one-repetition Knex/Kysely subset. Do not cite those three as the result.

**MySQL baseline.** Recorded run finished `2026-10-19T13:49:36.491Z`, plus later Knex, Lucid, and lost-OK-packet recordings in that directory. The report's conclusion for TX-01A is that the PostgreSQL case is the wrong expectation: a caught duplicate key left the transaction active, and `COMMIT` persisted the earlier marker.

**SQLite.** Phase 0 evidence `research/sqlite-phase0/evidence/2026-10-19T13-20-36Z-py313/`. The decision memo says SQLite is useful for a narrow set of questions and that the PostgreSQL harness cannot be pointed at a SQLite file. The phase 1 sqlite3 control and the SQLAlchemy Core comparison have their own evidence directories. Two Core cases failed for SQLite-specific reasons described in `research/sqlite-phase0/sqlalchemy-core/README.md`.

## 3. Working tree

On 2026-10-21 the production-reachability tree, the `PR-01` classifier, `docs/upstream-submissions.md`, and `adapters/hibernate/` were uncommitted. They are on `main` at `36dd52f`. The planning documents were recorded in `ece7df4`.

Inspected 2026-10-23, the only untracked paths were `.pnpm-store/`, `adapters/sqlalchemy/__pycache__/`, and `research/production-reachability/py/__pycache__/`. Do not commit those.

## 4. Production-reachability findings checked against case JSON

Source: `2026-10-19T18-15-49Z-b2c174` unless a follow-up is named. "Mismatch" here means the application-visible success signal and the database outcome disagree. Harness classification for these rows is PASS whenever the evidence preconditions held. That PASS is not the verdict.

Database outcome for the caught-then-complete rows below: `pg_xact_status()` aborted, marker `tx` absent, marker `reuse` present, reuse fate committed.

| Subject | API signal recorded in the case file | Reuse | Report verdict |
| --- | --- | --- | --- |
| pg 8.23.1, check-tag | `reported` rolled_back, `command_tag` `ROLLBACK` | same backend | PASS, driver exposes the tag |
| pg 8.23.1, ignore-tag | `reported` committed, tag still `ROLLBACK` | same backend | APPLICATION MISUSE |
| Knex 3.3.0 managed and explicit | `reported` committed. Last statement `COMMIT`. No command-tag trace in the Knex case file | same backend | FAIL |
| Kysely 0.29.6 managed | promise `reported` committed. `driver.isCommitted` is null | same backend | FAIL. The public flag is not this row |
| Kysely 0.29.6 explicit | `reported` committed, `isCommitted` true | same backend | FAIL |
| Lucid 22.4.2 managed and explicit | `reported` committed, commit hook 1, rollback hook 0. Driver trace: command tag `ROLLBACK` for `COMMIT` | same backend | FAIL |
| MikroORM 7.2.5 managed and explicit | `reported` committed. No subscriber, so no hook. Driver trace: command tag `ROLLBACK` for `commit` | same backend | FAIL. The 7.2.6-dev.19 follow-up is a later run and does not replace this row |
| TypeORM 1.1.2 managed and explicit | `reported` committed, `after_commit` 1, `after_rollback` 0 | same backend | FAIL |
| SQLAlchemy Core 2.1.5 managed and explicit | `reported` committed, commit event 1. Trace includes `COMMIT (INERROR -> IDLE)` | same backend | FAIL |
| SQLAlchemy ORM 2.1.5 managed | `reported` committed. Basis: `Session.begin()` exited without an exception, so the adapter mapped it as committed. `after_commit` 0; `after_rollback` 1; mechanism not exercised; last statement `ROLLBACK` | same backend | DOCUMENTED / EXPECTED |
| SQLAlchemy ORM 2.1.5 explicit | `reported` failed, `after_rollback` 1 | same backend | PASS |
| Django 6.1.2 `atomic()` managed | `reported` rolled_back, `on_commit` 0, last statement `ROLLBACK`, mechanism not exercised | same backend | PASS |
| Django 6.1.2 manual `commit()` | Main run INCONCLUSIVE: `after-write` was not reached. Follow-ups `18-34-44` and `20-58-26`: `reported` committed, mechanism exercised, last statement `COMMIT`, marker absent, `on_commit` 0 | same backend on the follow-ups | FAIL for the manual API |
| Spring JDBC 7.0.9 and Spring TX programmatic, managed and explicit, native and pooled | `reported` committed, `after_commit` 1, `after_completion` committed | pooled: same backend. native: `same_backend` false, later transaction still committed | FAIL |
| Spring TX declarative managed catch | same hook result, `same_backend` false | later transaction committed | FAIL |
| Spring TX declarative explicit | harness INCONCLUSIVE, adapter status not implemented | — | UNSUPPORTED in the report |
| Spring TX declarative uncaught | `reported` rolled_back, and also `after_commit` 1 with `after_completion` committed, marker absent | `same_backend` false, reuse committed | FAIL in the report, because the hook fired |
| Spring TX declarative savepoint | harness INCONCLUSIVE. Recorded violation `25P02`, not `23505`. `reported` committed, `after_commit` 1, marker absent, fate aborted | `same_backend` false | Report says FAIL. That is an interpretation, not a harness FAIL |

Savepoint recovery PASS rows, including Knex, Kysely, Lucid, MikroORM, TypeORM, both SQLAlchemy adapters, Django, pg, Spring JDBC, and Spring TX programmatic: fate committed, marker `tx` visible. Kysely's savepoint row records `isCommitted` true together with a committed database outcome. That is the legitimate recovery the control exists to protect.

The Spring subject block records `java` 27. The Spring JDBC compiler release in `pom.xml` is 21. Which JDK launched the process is the recorded subject version. This inspection did not re-execute it.

Standalone scripts, with no saved console log beside them:

- `research/production-reachability/reproductions/node-commit-tag.mjs`
- `research/production-reachability/reproductions/sqlalchemy_catch_commit.py`
- `research/production-reachability/reproductions/PgjdbcCommit.java`

The report quotes their printed results. The preserved primary evidence is the harness case files. Do not invent a missing log.

Drizzle, Prisma, and Hibernate were out of scope for this catalog. Drizzle and Prisma do have suite `TX-01A` FAILs with the mechanism exercised, in `reports/examples/`. Those suite results are not PR-01 rows.

## 5. Upstream filing status

Source: `docs/upstream-submissions.md` as it exists on `36dd52f`. This inspection did not re-query GitHub. If the tracker and a draft disagree, the tracker is the filing log. A draft file's banner is the content status of that file. The Kysely, psycopg, TypeORM, and Drizzle drafts say filed. The Spring, Prisma, and Knex drafts still say not filed.

**Drafted, not submitted.** Do not describe these as filed.

| ID | Draft | Subject |
| --- | --- | --- |
| S1 | `research/production-reachability/upstream-drafts/spring-framework.md` | `afterCommit` runs, and `afterCompletion` is `STATUS_COMMITTED`, when PostgreSQL rolled back. Ready. Not approved. Waits on pgjdbc #4494 |
| PI1 | `research/production-reachability/upstream-drafts/prisma.md` | `$transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`. Ready. Not approved. Issue only |
| — | `research/production-reachability/upstream-drafts/knex.md` | Restates K1. The tracker says not to file it |
| — | `adapters/jooq/upstream-draft.md` | Not filed. pgjdbc #4494 stays the driver issue |
| — | `adapters/gorm/UPSTREAM.md` | Not filed |
| — | `adapters/sqlx/upstream-draft.md` | Not filed |

**Submitted, overlapping this study.** Waiting on maintainers unless the tracker says otherwise. M3 is the row the tracker records as closed. None of these is recorded as a merged pull request from this repository.

| ID | Recorded link | What it covers |
| --- | --- | --- |
| K1 | https://github.com/knex/knex/issues/6547 | `executionPromise` resolves when PostgreSQL rolls back at `COMMIT` |
| Y2 | https://github.com/kysely-org/kysely/issues/2157 | `commit()` sets `isCommitted` when the transaction did not commit. Filed 2026-10-21. Issue only |
| P1 | https://github.com/psycopg/psycopg/issues/1453 | `Connection.commit()` returns on command tag `ROLLBACK`. Filed 2026-10-21. Issue only |
| T3 | https://github.com/typeorm/typeorm/issues/12992 | `afterTransactionCommit` runs on that command tag. Filed 2026-10-21. Issue only |
| D1 | https://github.com/drizzle-team/drizzle-orm/issues/6572 | `db.transaction()` resolves on that command tag. Filed 2026-10-22. Issue only |
| M3 | https://github.com/mikro-orm/mikro-orm/issues/8476 | `em.transactional()` resolves on that `COMMIT`. Closed 2026-10-22 as completed via #8499. The 7.2.5 rows in section 4 stay. The follow-up is `research/production-reachability/runs/2026-10-22T12-18-31Z-928c75` |
| L2 | https://github.com/adonisjs/lucid/issues/1205 | Lucid reports success and runs commit hooks without a commit. Submitted 2026-10-21. Issue only |
| J1 | https://github.com/pgjdbc/pgjdbc/issues/4494 | Should `Connection.commit()` report the rollback tag? Use case answered 2026-10-21. Waiting on the maintainer |

**Nearby, and not the same finding.**

| ID | Recorded link | Difference |
| --- | --- | --- |
| K2 | https://github.com/knex/knex/issues/6546 | Connection returned to the pool with a transaction still open. Connection safety, not the command-tag report. |
| Y1 | https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924 | Rollback that never completed. Not `isCommitted`. |
| Knex 6141 | https://github.com/knex/knex/issues/6141 | A `COMMIT` that throws. This study's `COMMIT` does not throw. |
| Spring 28685 | https://github.com/spring-projects/spring-framework/issues/28685 | `afterCommit` itself throws. |

The tracker also records earlier Lucid, MikroORM, TypeORM, and Knex submissions (L1, L3, L5, M2, M4, T1, T2, K3). Their links and follow-up dates live in that file. The tracker records an L3 check on 2026-10-21. This 2026-10-23 inspection did not re-query GitHub and did not post. The execution queue in the tracker is empty.

The production-reachability report's original "No issues were filed" sentence is kept. A dated note under it points here. Both should be read together.

## 6. Unresolved

- The 2026-10-19 PR-01 harness digest `af929302a2da` does not match `36dd52f`, because `0d69b27` changed the classifier for category E. The runs and the `PR-01` family are on `main`. Reproducing that exact digest means the classifier as it ran, not a new execution.
- Spring declarative savepoint recovery is harness-INCONCLUSIVE. The report's FAIL is a contract interpretation.
- Spring native modes did not reuse the same backend. The false commit still occurred. The "same backend" sentence in the report's opening does not describe those modes.
- Knex's own case file does not contain a command-tag trace. The tag is recorded on the pg control and on Lucid's driver trace in the same run. Lucid uses Knex.
- Kysely's managed callback did not record the public `isCommitted` flag. The report's claim about an internal flag is part of the quoted contract text.
- SQLAlchemy ORM managed `api_outcome.reported` is `committed` even though `after_commit` did not run. Read the hooks before treating that field as a commit claim.
- Django's recorded `needs_rollback` value on the managed row is false after `Atomic.__exit__` has rolled back. The report's account of the flag being set is the framework's documented behavior during the error, not that JSON field at the end.
- The PR-01 run summary records Java 27 for Spring. Project docs and the compiler release say 21.
- Hibernate has a suite recording. It is not a PR-01 row. The study's report still excludes it from that catalog.
- Deadlock, serialization failure, and statement timeout were not executed in the production-reachability study. The report argues they are the same command-tag path. That argument is not a separate experiment.
- CI's `--expect` file is the 2026-10-22 Lucid, MikroORM, TypeORM, and `pg-control` run. It does not contain the other adapters or PR-01. Whether the workflow passes on `main` was not re-run here.
- GitHub issue state was not re-fetched on 2026-10-23.

## 7. Missing documentation before the planning commit

This section is the gap before `ece7df4`. Those documents are on `main` at `36dd52f`.

There was no `AGENTS.md`, no master plan, no roadmap, and no ownership-benchmark specification. The production-reachability report's upstream section did not mention filings made from other writeups. `docs/upstream-submissions.md` existed only as untracked work. The root README did not point at the research program.

## 8. Documentation the planning commit adds

Recorded in `ece7df4`. Case results were not changed by that commit.

| Path | Role |
| --- | --- |
| `docs/research-master-plan.md` | Mission, two programs, hypothesis, gates |
| `docs/research-roadmap.md` | Order, dependencies, concurrency |
| `docs/research-status.md` | This inventory |
| `docs/ownership-benchmark/research-questions.md` | What the benchmark asks |
| `docs/ownership-benchmark/methodology-plan.md` | Controls, pilot, transaction task, later cohorts |
| `docs/ownership-benchmark/application-evolution-spec.md` | V1–V7 requirements |
| `AGENTS.md` | Operating rules |
| Root `README.md` | Links only |
| `research/production-reachability/README.md` | Dated filing-status note. Case results unchanged. |

## 9. Next authorized task

Maintainer review of the ownership-benchmark design in `docs/ownership-benchmark/`.

M0's evidence is on `main`. Do not rerun PR-01. Do not implement the pilot, the V1–V7 harness, or a Node cohort. Filing S1 or PI1 is a separate approval of the exact text. The Knex draft that restates knex#6547 must not be filed again. Do not open a second pgjdbc issue.

PPCS maintenance may proceed beside that review: answer maintainers on issues that are already filed, on the dates in `docs/upstream-submissions.md`. The nearest dates there are one L1 follow-up around 2026-10-31 and one A1 follow-up around 2026-11-04. Do not post a new issue from this inventory update.

## 10. Still not started

Section 10 as written on 2026-10-21 predated the adapter tasks in sections 11–14. Those recordings exist. They are not permission to add another adapter.

Still not started at `36dd52f`:

- Ownership-benchmark application, harness, acceptance-test code, and pilot runs
- Another PR-01 execution
- Filing S1, PI1, the Knex restatement, the jOOQ draft, the GORM draft, or the SQLx draft
- Observatory, repository mining, and a MySQL or SQLite adapter inside `harness/`
- Commits of `.pnpm-store/`, `__pycache__/`, or `.ppcs-instance.json`

## 11. PHP adapters, recorded 2026-10-21

This section is the PHP adapter task. The suite inventory above includes the recording. Section 10, as first written, predated it.

`adapters/pdo-control` and `adapters/laravel` run through the existing harness. PHP 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, illuminate/database v13.38.0, PostgreSQL 18.6. The recording is `reports/examples/2026-10-21T16-24-17Z-231161`. Three repetitions agreed. No upstream issue was filed.

The scored Laravel path is Capsule. It does not register `DatabaseServiceProvider`, so `db.transactions` is not bound and `afterCommit` is not on that path. A separate probe, `adapters/php/probe.php`, sets `DatabaseTransactionsManager` and is not a PPCS case. Deadlock and serialization-failure retries were not executed. Laravel migration cases were NOT_RUN in that recording. They were recorded on 2026-10-23 in `reports/examples/2026-10-23T13-03-36Z-03a5b5`, on PHP 8.5.12. `TX-01B.commit-reply-discarded` is NOT_RUN because pdo_pgsql consumes the COMMIT reply inside `commit()`.

## 12. jOOQ adapter, recorded 2026-10-22

This section is the jOOQ adapter task. The suite inventory above includes the recording. Section 10, as first written, predated it.

`adapters/jooq` runs through the existing harness. jOOQ Open Source Edition 3.21.9, PostgreSQL JDBC 42.7.14, Java 27, compiler release 21, PostgreSQL 18.6. HikariCP 7.1.0 is only in the TX-03 modes. The recording is `reports/examples/2026-10-22T12-58-46Z-d4a7fc`. Three repetitions agreed. CTL-01 and `pg-control` held. No upstream issue was filed. `adapters/jooq/upstream-draft.md` is a draft. pgjdbc #4494 stays the driver issue. Do not open a second one.

`native` calls `DSLContext.transaction`. `jdbc` executes the same DSL and commits with `Connection.commit`. TX-01A fails in both: `commit()` returns while the driver state is `FAILED`, and the marker is absent. An exception that leaves the callback rolls back. That path is the probe in `adapters/jooq/src/main/java/org/ppcs/jooq/Probe.java`, not a catalog case. Pooled `TX-03.rollback-not-sent` fails because `DefaultTransactionProvider` calls `setAutoCommit(true)` after the withheld rollback and pgjdbc sends `COMMIT`. `jdbc-pooled` passes that case. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent. `TX-01B.commit-reply-discarded` is NOT_RUN.

## 13. Go adapters, recorded 2026-10-22

This section is the Go adapter task. The suite inventory above includes the recording. Section 10, as first written, predated it. The task assigned the adapters and the research question. No upstream issue was filed.

`adapters/go-pgx-control`, `adapters/go-database-sql-control`, and `adapters/gorm` run through the existing harness. One module, `adapters/go`, pins Go 1.27.3, pgx v5.11.0, GORM v1.31.2, and `gorm.io/driver/postgres` v1.6.3. The driver's own module requires pgx v5.10.0. This module selects v5.11.0. PostgreSQL 18.6. The recording is `reports/examples/2026-10-22T13-24-28Z-606909`. Three repetitions agreed. CTL-01 and `pg-control` held. The comparison is `docs/go-persistence.md`.

TX-01A passes on native pgx, `database/sql`, and both GORM modes. `Commit` returns `ErrTxCommitRollback`. The tracer recorded command tag `ROLLBACK`. The mechanism was exercised. `TX-02.savepoint-rollback-not-sent` fails on all four modes: the outer commit tag is `COMMIT` and both markers are visible. GORM `RollbackTo().Error` was nil. `adapters/gorm/UPSTREAM.md` is a draft. It was not filed. TX-03 passes. The next backend is not the failed unit's. `TX-01B.commit-reply-discarded` is unsupported on native pgx. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent.

## 14. Recorded after the 2026-10-21 inspection

These are on `main` at `36dd52f`. The root README is the matrix. This list does not restate classifications. Sections 11–13 are the PHP, jOOQ, and Go task records.

| Recording | Subject |
| --- | --- |
| `reports/examples/2026-10-21T15-45-57Z-c3c03b` | Hibernate ORM 7.4.13.Final. `adapters/hibernate/FINDINGS.md` |
| `reports/examples/2026-10-21T19-26-59Z-4ccef5` | Django and SQLAlchemy ORM TX-04 and TX-05 |
| `reports/examples/2026-10-21T19-39-32Z-b559f2` | Active Record 8.1.4 and the ruby-pg control |
| `reports/examples/2026-10-21T20-00-04Z-178fa4` | Django, Drizzle, and Prisma migration cases |
| `reports/examples/2026-10-21T20-00-07Z-cff349` | EF Core 10.0.13 and the Npgsql control |
| `reports/examples/2026-10-21T23-50-08Z-87af6a` | `TX-01B.commit-reply-unseen`, category E |
| `reports/examples/2026-10-22T01-10-06Z-0cb565` | TypeORM `runMigrations()` |
| `reports/examples/2026-10-22T01-23-00Z-38e672` | MikroORM `Migrator.up()` |
| `reports/examples/2026-10-22T01-26-51Z-fb52c8` | CI `--expect` target: Lucid, MikroORM, TypeORM, and `pg-control` |
| `research/production-reachability/runs/2026-10-22T12-18-31Z-928c75` | MikroORM 7.2.6-dev.19 PR-01 follow-up. Does not replace the 7.2.5 rows |
| `reports/examples/2026-10-22T18-40-05Z-7b77ec` | SQLx 0.9.0. `adapters/sqlx/upstream-draft.md` is not filed |
| `reports/examples/2026-10-23T12-49-21Z-094ceb` | EF Core `TX-01B.commit-reply-unseen` |
| `reports/examples/2026-10-23T13-03-36Z-03a5b5` | Laravel `Migrator::run()` and `Migrator::rollback()` |
| `reports/examples/2026-10-23T13-11-06Z-d7cd89` | Drizzle 0.45.4 category B, with an `'error'` listener on the checked-out client. The 2026-10-19 file is unchanged. The 1.0.0-rc.4 recording was not re-run |
| `investigations/mysql-innodb-baseline/evidence/php-mx01.json` | PHP and CodeIgniter 4 on the MySQL companion runner. Not a PPCS adapter |

Y2, P1, T3, and D1 are filed in the tracker. S1 and PI1 are not.
