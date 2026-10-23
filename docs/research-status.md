# Research status

Inspected 2026-10-21 on `main` at `0b611f5`. This is the inventory to update. The mission stays in [`research-master-plan.md`](research-master-plan.md). The order of work stays in [`research-roadmap.md`](research-roadmap.md).

Completion means the milestone's acceptance criteria are met. A directory, an adapter, or a draft is not completion.

This file describes the working tree as inspected. It does not authorize a commit.

## Milestone tracker

| Milestone | Status | Dependencies | Evidence | Acceptance criteria | Next action | Approval required |
| --- | --- | --- | --- | --- | --- | --- |
| PPCS suite through Prisma, on PostgreSQL 18.6 | Complete for the recorded adapters | Disposable server, pinned adapters | Root `README.md` matrix and `reports/examples/` | Classifications recorded with versions, repetitions, and controls | Maintain. Do not add an adapter without a question. | Yes for a new adapter family or a classification-rule change |
| Production-reachability closeout (M0) | Active | Existing PR-01 runs | `research/production-reachability/` | Roadmap M0 criteria | Preserve the uncommitted tree when the maintainer asks. Do not rerun it. | Yes to commit, and yes to file remaining drafts |
| Upstream tracker | Active | Drafts and already-filed issues | `docs/upstream-submissions.md` | Status, link, and draft-versus-filed are accurate | Monitor already-filed items on their dates. Do not post. | Yes before any new post |
| Ownership-benchmark design (M1) | Active | M0 evidence left intact | `docs/ownership-benchmark/` | Maintainer accepts the requirements | Review the draft. Do not implement it. | Yes before pilot execution |
| Python pilot (M2) | Planned | M1 frozen and program approval | None | Methodology-plan exit criteria | Wait | Yes |
| Python V1–V7 benchmark (M3) | Planned | M2 | None | Roadmap M3 | Wait | Yes |
| JVM cohort, .NET cohort, Node ownership cohort | Deferred | M3 and a separate approval | PPCS and Spring/JDBC recordings are evidence only | A cohort specification that is not a wrapper over PPCS | Wait | Yes |
| Observatory | Deferred | Demonstrated need after M3 | None | Experiments need shared orchestration or interactive history | Wait | Yes |
| Repository mining | Deferred | M3 method, plus a bias protocol | None | Protocol accepted | Wait | Yes |
| MySQL or SQLite inside the PPCS harness | Deferred | Written justification | Companion investigations, outside the harness | Master-plan justification | Leave the companion runners where they are | Yes |
| Hibernate adapter | Deferred | A research question and a recorded run | Untracked `adapters/hibernate/` only | A gated example run | Do not extend it as part of planning | Yes |

## 1. Existing capabilities

Implemented and verified means a recorded run in `reports/examples/` or a companion evidence directory, with the controls that run required, and a written per-adapter or per-investigation report.

The CI workflow (`.github/workflows/ci.yml`) runs `node harness/run.mjs --expect=reports/examples/2026-10-18T00-11-46Z-95887b/run.json` with no adapter filter. That file is the Lucid, MikroORM, TypeORM, and `pg-control` recording. `compareWith` in `harness/lib/suite.mjs` treats a result whose case, adapter, and mode are absent from the expected file as a difference. `incomparable` refuses the comparison before the suite starts when the harness digest or the catalog digest differs. `scripts/setup.sh` installs every JavaScript adapter that has a `package.json`. Other adapters are still loaded from `adapter.json` and attempted. This inspection did not re-run CI, so the job's current result on `main` is not established here. Later recorded adapters are real results. They are not rows in that expected file.

| Capability | State |
| --- | --- |
| Catalog families CTL-01, TX-01A, TX-01B, TX-02, TX-03, TX-04, TX-05, MG-02, MG-03 | Implemented. Coverage depends on the adapter. The root README states which cases each adapter runs. |
| Runner, observer, classification, three-repetition gate, CTL-01 gate, `pg-control` gate | Implemented and covered by `pnpm run test` and `pnpm run test:methodology` |
| Lucid 22.4.2, MikroORM 7.2.5, TypeORM 1.1.2, `pg-control` | Recorded in the CI example run, PPCS 0.3.0 |
| Django 6.1.2, SQLAlchemy 2.1.5 ORM and Core, Tortoise 1.1.9, Spring JDBC 7.0.9, Spring transaction management 7.0.9, JDBC control 42.7.14, Drizzle 0.45.4 and 1.0.0-rc.4, Prisma Client 7.10.1 | Later recorded runs, linked from the root README. Not the CI `--expect` target. |
| `PR-01` production-reachability catalog | Implemented in the working tree and recorded under `research/production-reachability/runs/`. Not on `0b611f5`. Harness PASS does not mean the commit report was correct. |
| Hibernate adapter | Source and `adapter.json` exist, untracked. No `FINDINGS.md` and no example run. Not verified. |
| MySQL 8.4 companion runner | Investigated and recorded under `investigations/mysql-innodb-baseline/`. Merged to `main` through the repository's MySQL pull requests. Not a PPCS adapter. |
| SQLite phase 0, sqlite3 control, SQLAlchemy Core comparison | Investigated and recorded under `research/sqlite-phase0/`. Not a PPCS adapter. |
| Drizzle follow-up probe | `investigations/drizzle-followups/probe.mjs` only. No evidence directory. Not a recorded result. |

`PR-01` case files do not have a `pg-control` expectation. The run summary says so. CTL-01 held for the adapters in the main run. The contract verdicts are the research report, not the harness classification.

## 2. Completed investigations

These are complete as investigations. They are not a license to port them into the PostgreSQL harness.

**PPCS transaction and migration matrix.** The root README is the matrix. Notable recorded shapes, each with its own fault category:

- Category A `TX-01A` is a caught unique violation and then the normal completion path. Several frameworks FAIL with the COMMIT-answered-ROLLBACK mechanism exercised (SQLAlchemy Core, Drizzle, Prisma, and others in the matrix). Django's `atomic()` PASS does not exercise that mechanism: Django rolls back, so `COMMIT` is not the statement that ends the transaction. SQLAlchemy ORM's TX-01A result is INCONCLUSIVE because flush rolls back before `before-end`.
- Category C and D results are injected or simulated. They are not production-reachability claims.
- MG-02 and MG-03 are recorded for Lucid and `pg-control`. Lucid's `MG-03.no-reversal` FAIL is the subject of lucid#1204, which the tracker records as submitted.

**Production-reachability, contract layer.** Authoritative run: `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174`. PostgreSQL 18.6, image digest recorded in that summary, Node v24.14.1, three repetitions, 87 harness PASS and 3 harness INCONCLUSIVE. Catalog sha256 prefix `405731e049f8`. Harness sha256 prefix `af929302a2da`. That harness digest includes the uncommitted `PR-01` classifier. It will not match a checkout of `0b611f5` until that classifier is preserved with the runs.

Django manual `commit()` follow-up: `2026-10-19T20-58-26Z-508b7a`. An earlier follow-up, `2026-10-19T18-34-44Z-8139f2`, records the same explicit-commit outcome. The report cites the later one. Runs `2026-10-19T17-50-05Z-90b4ea` and `2026-10-19T17-50-45Z-a66571` did not hold their controls or were partial. Run `2026-10-19T18-11-24Z-a70895` is a one-repetition Knex/Kysely subset. Do not cite those three as the result.

**MySQL baseline.** Recorded run finished `2026-10-19T13:49:36.491Z`, plus later Knex, Lucid, and lost-OK-packet recordings in that directory. The report's conclusion for TX-01A is that the PostgreSQL case is the wrong expectation: a caught duplicate key left the transaction active, and `COMMIT` persisted the earlier marker.

**SQLite.** Phase 0 evidence `research/sqlite-phase0/evidence/2026-10-19T13-20-36Z-py313/`. The decision memo says SQLite is useful for a narrow set of questions and that the PostgreSQL harness cannot be pointed at a SQLite file. The phase 1 sqlite3 control and the SQLAlchemy Core comparison have their own evidence directories. Two Core cases failed for SQLite-specific reasons described in `research/sqlite-phase0/sqlalchemy-core/README.md`.

## 3. Active work

Uncommitted on 2026-10-21, and not part of this planning task's edits except where a file is named below:

- `research/production-reachability/` including runs, reproductions, and upstream drafts
- `harness/lib/classify.mjs` and `harness/test/unit/classify-pr.test.mjs` (the `PR-01` family)
- PR-01 entry points: `adapters/lucid/pr01.mjs`, `adapters/mikroorm/pr01.mjs`, `adapters/typeorm/pr01.mjs`, plus modifications to the Django, Lucid, MikroORM, TypeORM, SQLAlchemy, SQLAlchemy Core, Spring JDBC, and Spring transaction adapters
- `docs/upstream-submissions.md`
- `adapters/hibernate/`
- small `FINDINGS.md` / `README.md` edits under the SQLAlchemy adapters, and a `CHANGELOG.md` edit

Also present and not research: `.pnpm-store/` and `adapters/sqlalchemy/__pycache__/`. Do not commit those.

This planning change adds the research documents, `AGENTS.md`, README links, and a filing-status note on the production-reachability report. It does not change case results.

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
| MikroORM 7.2.5 managed and explicit | `reported` committed. No subscriber, so no hook. Driver trace: command tag `ROLLBACK` for `commit` | same backend | FAIL |
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

Source: `docs/upstream-submissions.md` as it existed in the working tree on 2026-10-21. This inspection did not re-query GitHub. If the tracker and a draft disagree, the tracker is the filing log and the draft file's "Not filed" banner is the content status.

**Drafted, not submitted.** Do not describe these as filed.

| ID | Draft | Subject |
| --- | --- | --- |
| Y2 | `research/production-reachability/upstream-drafts/kysely.md` | `commit()` sets `isCommitted` when PostgreSQL answers `COMMIT` with `ROLLBACK` |
| S1 | `research/production-reachability/upstream-drafts/spring-framework.md` | `afterCommit` runs, and `afterCompletion` is `STATUS_COMMITTED`, when PostgreSQL rolled back |
| P1 | `research/production-reachability/upstream-drafts/psycopg.md` | `Connection.commit()` returns on command tag `ROLLBACK` |
| T3 | `research/production-reachability/upstream-drafts/typeorm.md` | `afterTransactionCommit` runs on that command tag |
| — | `research/production-reachability/upstream-drafts/knex.md` | Restates K1. The tracker says not to file it |

**Submitted, overlapping this study.** Waiting on maintainers unless the tracker says otherwise. None of these is recorded as merged.

| ID | Recorded link | What it covers |
| --- | --- | --- |
| K1 | https://github.com/knex/knex/issues/6547 | `executionPromise` resolves when PostgreSQL rolls back at `COMMIT` |
| M3 | https://github.com/mikro-orm/mikro-orm/issues/8476 | `em.transactional()` resolves on that `COMMIT` |
| L2 | https://github.com/adonisjs/lucid/issues/1205 | Lucid reports success and runs commit hooks without a commit. Submitted 2026-10-21. Issue only. |
| J1 | https://github.com/pgjdbc/pgjdbc/issues/4494 | Should `Connection.commit()` report the rollback tag? Use case answered 2026-10-21. Waiting on the maintainer. |

**Nearby, and not the same finding.**

| ID | Recorded link | Difference |
| --- | --- | --- |
| K2 | https://github.com/knex/knex/issues/6546 | Connection returned to the pool with a transaction still open. Connection safety, not the command-tag report. |
| Y1 | https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924 | Rollback that never completed. Not `isCommitted`. |
| Knex 6141 | https://github.com/knex/knex/issues/6141 | A `COMMIT` that throws. This study's `COMMIT` does not throw. |
| Spring 28685 | https://github.com/spring-projects/spring-framework/issues/28685 | `afterCommit` itself throws. |

The tracker also records earlier Lucid, MikroORM, TypeORM, and Knex submissions (L1, L3, L5, M2, M4, T1, T2, K3). Their links live in that file. L3 had a monitor window of 2026-10-21 to 2026-10-22. This planning pass did not perform that check and did not post.

The production-reachability report's original "No issues were filed" sentence is kept. A dated note under it points here. Both should be read together.

## 6. Unresolved

- M0 is not on a git revision. Reproducing PR-01 from `origin/main` alone is not possible until the working tree is preserved.
- Spring declarative savepoint recovery is harness-INCONCLUSIVE. The report's FAIL is a contract interpretation.
- Spring native modes did not reuse the same backend. The false commit still occurred. The "same backend" sentence in the report's opening does not describe those modes.
- Knex's own case file does not contain a command-tag trace. The tag is recorded on the pg control and on Lucid's driver trace in the same run. Lucid uses Knex.
- Kysely's managed callback did not record the public `isCommitted` flag. The report's claim about an internal flag is part of the quoted contract text.
- SQLAlchemy ORM managed `api_outcome.reported` is `committed` even though `after_commit` did not run. Read the hooks before treating that field as a commit claim.
- Django's recorded `needs_rollback` value on the managed row is false after `Atomic.__exit__` has rolled back. The report's account of the flag being set is the framework's documented behavior during the error, not that JSON field at the end.
- The PR-01 run summary records Java 27 for Spring. Project docs and the compiler release say 21.
- Hibernate has no recorded run.
- Deadlock, serialization failure, and statement timeout were not executed. The report argues they are the same command-tag path. That argument is not a separate experiment.
- CI's `--expect` file does not contain the post-0.3.0 adapters or PR-01. Whether the unmodified workflow still passes on `main` was not re-run here. A dirty `harness/lib/classify.mjs` changes the harness digest and makes `--expect` refuse the comparison.
- GitHub issue state was not re-fetched during this inspection.

## 7. Missing documentation before this change

There was no `AGENTS.md`, no master plan, no roadmap, and no ownership-benchmark specification. The production-reachability report's upstream section did not mention filings made from other writeups. `docs/upstream-submissions.md` existed only as untracked work. The root README did not point at the research program.

## 8. Documentation this change adds

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

Maintainer review of the planning documents.

The next research action after that review, still without implementing the benchmark, is whatever M0 preservation the maintainer requests: committing the existing production-reachability tree, or leaving it uncommitted and saying so. Filing Y2, S1, P1, or T3 is a separate approval.

The next major research activity after closeout is design review and, only with approval, the Python pilot. It is not the full V1–V7 run, not a Node cohort, and not the Observatory.

## 10. Deliberately not started

- Ownership-benchmark application, harness, acceptance-test code, and pilot runs
- New PPCS adapters, including further Hibernate work
- New experiments, including another PR-01 execution
- Upstream issues or pull requests
- Observatory, repository mining, and database expansion
- Commits, pushes, and cleanup of unrelated working-tree files

## 11. PHP adapters, recorded 2026-10-21

This section is the PHP adapter task. It does not change the planning inventory above. Section 10 was written before that task.

`adapters/pdo-control` and `adapters/laravel` run through the existing harness. PHP 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, illuminate/database v13.38.0, PostgreSQL 18.6. The recording is `reports/examples/2026-10-21T16-24-17Z-231161`. Three repetitions agreed. No upstream issue was filed.

The scored Laravel path is Capsule. It does not register `DatabaseServiceProvider`, so `db.transactions` is not bound and `afterCommit` is not on that path. A separate probe, `adapters/php/probe.php`, sets `DatabaseTransactionsManager` and is not a PPCS case. Deadlock and serialization-failure retries were not executed. Laravel migration cases are NOT_RUN. `TX-01B.commit-reply-discarded` is NOT_RUN because pdo_pgsql consumes the COMMIT reply inside `commit()`.

## 12. jOOQ adapter, recorded 2026-10-22

This section is the jOOQ adapter task. It does not change the planning inventory above. Section 10 was written before that task.

`adapters/jooq` runs through the existing harness. jOOQ Open Source Edition 3.21.9, PostgreSQL JDBC 42.7.14, Java 27, compiler release 21, PostgreSQL 18.6. HikariCP 7.1.0 is only in the TX-03 modes. The recording is `reports/examples/2026-10-22T12-58-46Z-d4a7fc`. Three repetitions agreed. CTL-01 and `pg-control` held. No upstream issue was filed. `adapters/jooq/upstream-draft.md` is a draft. pgjdbc #4494 stays the driver issue. Do not open a second one.

`native` calls `DSLContext.transaction`. `jdbc` executes the same DSL and commits with `Connection.commit`. TX-01A fails in both: `commit()` returns while the driver state is `FAILED`, and the marker is absent. An exception that leaves the callback rolls back. That path is the probe in `adapters/jooq/src/main/java/org/ppcs/jooq/Probe.java`, not a catalog case. Pooled `TX-03.rollback-not-sent` fails because `DefaultTransactionProvider` calls `setAutoCommit(true)` after the withheld rollback and pgjdbc sends `COMMIT`. `jdbc-pooled` passes that case. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent. `TX-01B.commit-reply-discarded` is NOT_RUN.

## 13. Go adapters, recorded 2026-10-22

This section is the Go adapter task. It does not change the planning inventory above. Section 10 was written before that task. The task assigned the adapters and the research question. No upstream issue was filed.

`adapters/go-pgx-control`, `adapters/go-database-sql-control`, and `adapters/gorm` run through the existing harness. One module, `adapters/go`, pins Go 1.27.3, pgx v5.11.0, GORM v1.31.2, and `gorm.io/driver/postgres` v1.6.3. The driver's own module requires pgx v5.10.0. This module selects v5.11.0. PostgreSQL 18.6. The recording is `reports/examples/2026-10-22T13-24-28Z-606909`. Three repetitions agreed. CTL-01 and `pg-control` held. The comparison is `docs/go-persistence.md`.

TX-01A passes on native pgx, `database/sql`, and both GORM modes. `Commit` returns `ErrTxCommitRollback`. The tracer recorded command tag `ROLLBACK`. The mechanism was exercised. `TX-02.savepoint-rollback-not-sent` fails on all four modes: the outer commit tag is `COMMIT` and both markers are visible. GORM `RollbackTo().Error` was nil. `adapters/gorm/UPSTREAM.md` is a draft. It was not filed. TX-03 passes. The next backend is not the failed unit's. `TX-01B.commit-reply-discarded` is unsupported on native pgx. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent.
