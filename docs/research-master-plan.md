# PPCS master research plan

Inspected 2026-10-21. This is the mission and the boundary for the PostgreSQL Persistence Conformance Suite (PPCS) and for the separate longitudinal persistence ownership benchmark.

Read this plan before starting work. Current facts, including what is recorded and what is only drafted, are in [`research-status.md`](research-status.md). Order of work is in [`research-roadmap.md`](research-roadmap.md). Agent rules are in [`../AGENTS.md`](../AGENTS.md).

Writing this plan does not approve the future work it describes.

## Questions a new agent should be able to answer

| Question | Where it is answered |
| --- | --- |
| What is PPCS for? | Program A, below, and the root `README.md` |
| What has already been established? | [`research-status.md`](research-status.md) |
| Which findings are production-reachable? | [`../research/production-reachability/README.md`](../research/production-reachability/README.md) and the status inventory |
| Which upstream reports have been filed? | [`upstream-submissions.md`](upstream-submissions.md). Drafts are not filings. |
| What is the next research milestone? | Finish PPCS closeout preservation, then design review of the Python benchmark. See the roadmap. |
| Why is the ownership benchmark separate? | Program B, below |
| What should the benchmark measure? | [`ownership-benchmark/research-questions.md`](ownership-benchmark/research-questions.md) |
| Why does it begin with Python? | [`ownership-benchmark/methodology-plan.md`](ownership-benchmark/methodology-plan.md) |
| How would JVM and .NET enter later? | The same methodology document |
| What must be finished before implementation? | Pilot exit criteria in the methodology plan. Implementation also needs maintainer approval. |
| Which tasks may run together? | [`research-roadmap.md`](research-roadmap.md) |
| Which actions need maintainer approval? | Approval gates, below |
| What should an agent do next, and what should it avoid? | [`../AGENTS.md`](../AGENTS.md) and the status document's next action |

## Mission

PPCS is a reproducible laboratory for persistence correctness against a real PostgreSQL server. It drives a framework through that framework's own APIs, injects controlled failures where a case calls for them, and checks the framework's report against PostgreSQL.

The wider research program has two parts. They share an interest in persistence correctness. They do not share a scope, a score, or a schedule.

## Program A — Persistence correctness

This is PPCS's existing mission.

**Research question.** Do persistence drivers, query builders, ORMs, and transaction managers correctly communicate database transaction outcomes and preserve connection safety under ordinary and abnormal conditions?

PPCS investigates:

- transaction outcome correctness
- commit and rollback semantics
- savepoint behavior
- transaction state recovery
- connection reuse
- transaction isolation
- migration correctness
- realistic database failures
- relevant driver and framework behavior

The suite that implements this question is the catalog in `specifications/`, the runner in `harness/`, and the adapters in `adapters/`. Method is `docs/methodology.md`. A FAIL is a counterexample to a stated invariant under recorded versions and a fault category. It is not, by itself, a defect report. The root README states that PPCS is not a ranking, a benchmark, an ORM, or a replacement for a framework's own tests. That statement stays in force for the suite.

### Dimensions that stay separate

A single pass/fail score is not a result. These are independent:

1. **Actual database outcome.** What PostgreSQL did, read by an independent connection: `pg_xact_status()`, marker visibility, and the session state the runner observed.
2. **Application-visible transaction outcome.** What the framework API returned or raised, and any public committed-state flag.
3. **Transaction lifecycle callbacks.** `afterCommit`, `on_commit`, `afterTransactionCommit`, and the equivalents the adapter actually registered.
4. **Connection and pool safety.** Whether a later transaction on that pool can commit its own work, and whether it reused the same backend.
5. **Application misuse.** A caller that ignores evidence the driver already exposed. The node-postgres mode that treats a resolved `COMMIT` as success while `Result.command` is `ROLLBACK` is this category in the production-reachability study.
6. **Framework contract violations.** A supported API whose documented meaning disagrees with the database outcome. The contract text is part of the evidence. Maintainers judge whether the disagreement is a defect.
7. **Production reachability.** Whether the scenario uses an ordinary API and a real PostgreSQL error, or a client-side injection or simulation. Category C and D faults show a recovery path. They do not show how often that path occurs.

Safe connection reuse does not prove that an earlier transaction committed. A reported commit does not prove that PostgreSQL committed. A harness classification does not replace the contract assessment when the case says so. For family `PR-01`, a harness PASS means the independent evidence is complete and marker visibility agrees with `pg_xact_status()`. The classifier states that this PASS does not judge the commit report. The contract verdicts are in the production-reachability report.

## Program B — Persistence ownership economics

This is the planned longitudinal benchmark. It is not PPCS, and it is not implemented.

**Research question.** Under LLM-assisted test-driven development (LLMTDD), which persistence architecture minimizes the combined cost of implementation, verification, debugging, maintenance, upgrades, and correctness risk over an evolving application's lifetime?

The architectures of interest are:

- explicit SQL with minimal driver support
- SQL query builders and typed query abstractions
- Active Record ORMs
- Data Mapper / Unit of Work ORMs
- integrated persistence platforms

The benchmark asks whether additional abstraction returns enough benefit to justify its complexity and its long-term ownership cost. Sophisticated ORMs may do better when relationships, state, and lifecycle rules dominate. Thin SQL may do better when hidden persistence behavior dominates. The design has to be able to observe either result.

Program B may share fixtures, evidence formats, and findings with PPCS. It must not change PPCS's catalog, classification rules, or recorded results in order to serve the benchmark. The PPCS-derived transaction task is one scored scenario inside the benchmark. It must not dominate the benchmark's overall score.

Design documents:

- [`ownership-benchmark/research-questions.md`](ownership-benchmark/research-questions.md)
- [`ownership-benchmark/methodology-plan.md`](ownership-benchmark/methodology-plan.md)
- [`ownership-benchmark/application-evolution-spec.md`](ownership-benchmark/application-evolution-spec.md)

## Architectural hypothesis

**UNVALIDATED RESEARCH HYPOTHESIS — NOT AN EMPIRICAL RESULT.**

Provisional ten-year ownership ranking for PostgreSQL-backed business applications, as a hypothesis to be tested:

| Rank | Architecture | Initial hypothesis |
| --- | --- | --- |
| 1 | SQL + node-postgres | Minimal dependency and abstraction exposure |
| 2 | Kysely | Typed SQL composition without ORM lifecycle complexity |
| 3 | Knex | Established SQL foundation and broad capabilities |
| 4 | Lucid within Adonis | Conventional ORM with strong framework integration |
| 5 | MikroORM | Sophisticated Unit of Work and persistence semantics |
| 6 | TypeORM | Established but broader persistence model |
| 7 | Drizzle | SQL-oriented, with potentially greater tooling and API evolution |
| 8 | Prisma | Potentially greater architectural and upgrade exposure |

Limitations, all of which the benchmark must be able to overturn:

- The ranking is primarily a Node.js comparison.
- It is not a universal ranking of persistence libraries.
- It does not establish actual ten-year maintenance costs.
- It may overweight dependency stability.
- It may undervalue ORM productivity benefits.
- It does not account sufficiently for application complexity.
- It does not establish how coding agents perform with each architecture.
- It does not establish whether the findings generalize to Python, JVM, or .NET.

Do not use this table as a scoring rubric. Do not treat a higher rank as the expected winner. A result that reverses the table is a successful experiment if the method is sound.

The benchmark's first cohort is Python (psycopg, SQLAlchemy Core, SQLAlchemy ORM), not this Node list. The Node list remains a source of correctness evidence and a possible later cohort.

## What production-reachability already showed

The study is [`../research/production-reachability/README.md`](../research/production-reachability/README.md). The authoritative harness run is `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` (three agreeing repetitions). Per-framework evidence and the places where the report and the case files differ are in [`research-status.md`](research-status.md). Do not edit those case files to match a verdict.

The pattern:

1. Begin a transaction through a supported framework API.
2. Perform a write that should remain if the transaction commits.
3. Trigger a genuine PostgreSQL unique constraint violation (`23505`).
4. Catch the exception inside the transaction.
5. Allow the normal transaction API to complete.
6. Independently inspect the database.
7. Compare the application's success signals with the actual database outcome.

PostgreSQL accepts `COMMIT` on an aborted transaction and returns command tag `ROLLBACK` without raising a new error. That behavior was observed on node-postgres: `Result.command` was `ROLLBACK`, and `Client.query('COMMIT')` resolved. psycopg and pgjdbc do not expose that tag. For those drivers the recorded evidence is session state plus `pg_xact_status()`.

### Commit reporting

A transaction API may resolve, set a public committed-state flag, run an after-commit callback, or otherwise tell the application that the transaction committed, while `pg_xact_status()` is `aborted` and the marker is absent. That is an outcome-reporting result.

The production-reachability contract assessment records that shape for Knex, Kysely, Lucid, MikroORM, TypeORM, SQLAlchemy Core, Spring JDBC, and Spring `DataSourceTransactionManager`, on the APIs named in the report. Django's `atomic()` path and SQLAlchemy ORM's explicit `commit()` did not. Direct node-postgres code that reads `Result.command` reports a rollback. The case files confirm the database outcome and the signals each adapter actually recorded. Some adapters did not record every signal the prose mentions. The status document lists those limits.

### Connection reuse

When PostgreSQL processes `COMMIT` on an aborted transaction, the transaction ends. A later transaction can commit. In the pooled and driver-managed cases, that later transaction often ran on the same backend. A test that only checks the next transaction can miss the false commit.

Non-pooled Spring modes in the same run closed the session. `same_backend` is false there, and the later transaction still committed on a new connection. Reuse of a specific backend and success of a later transaction are both recorded. They are still separate from the commit report.

### Savepoint recovery

The control is a legitimate recovery:

1. Begin a transaction.
2. Perform a valid write.
3. Establish a savepoint.
4. Trigger a unique constraint violation.
5. Roll back to the savepoint.
6. Commit the outer transaction.
7. Verify that the earlier write persisted.

Where the framework's savepoint API ran and the harness reached PASS, the outer marker was visible and `pg_xact_status()` was `committed`. Spring's declarative nested case did not meet the `23505` precondition. The harness classified it INCONCLUSIVE. The research report's contract verdict of FAIL for that row is an interpretation of the recorded hooks and the aborted transaction, not a harness FAIL.

### Upstream

Drafts in `research/production-reachability/upstream-drafts/` are drafts. The filing log is [`upstream-submissions.md`](upstream-submissions.md). Do not describe a draft as filed, or a submitted patch as merged, unless that document says so.

## How the benchmark uses PPCS

The benchmark includes one explicitly scored transaction task taken from this pattern. Methodology is in [`ownership-benchmark/methodology-plan.md`](ownership-benchmark/methodology-plan.md). Score transaction-outcome reporting, connection reuse, and savepoint recovery separately.

A framework-level conformance failure is evidence about the framework. It is not automatic evidence that coding agents perform worse with that architecture. Agent-generated application behavior, the documented framework contract, the database outcome, and connection safety stay separate.

## Language and framework direction

The ownership benchmark starts in Python so that the first comparison shares a language, a PostgreSQL backend, and an application structure:

| Architecture | Initial technology |
| --- | --- |
| Explicit SQL | psycopg |
| Query abstraction | SQLAlchemy Core |
| Full ORM | SQLAlchemy ORM |

Django ORM is a possible later cohort. If it is added, the comparison has to account for the rest of the Django framework.

A later JVM cohort is JDBC, Spring JDBC and/or jOOQ, and Hibernate/JPA, using Spring Boot where the application needs it. The point of that cohort is Java or Kotlin application development, not a thin wrapper around existing PPCS tests.

A later .NET cohort is Npgsql, Dapper, and Entity Framework Core. It waits until the Python method has been validated.

Existing Node PPCS results stay available as correctness evidence. A Node ownership cohort may eventually include node-postgres, Kysely, Knex, Lucid, MikroORM, TypeORM, Drizzle, and Prisma. That cohort is not the first benchmark, and it is not justified merely by a wish to complete the eight-row hypothesis.

## Database expansion

PPCS is a PostgreSQL suite. MySQL and SQLite investigations already exist beside it. They use their own runners and their own evidence. They are not PPCS adapters, and their outcomes do not transfer into PostgreSQL classifications.

Before any new database is added, a written justification has to answer:

1. Which database-specific correctness question is being investigated.
2. Why the existing PostgreSQL evidence cannot answer it.
3. Which scenarios are portable.
4. Which scenarios require database-specific semantics.
5. How an independent connection will verify the outcome.
6. How the new work changes maintenance cost.

The MySQL report already shows that a caught duplicate key does not abort an InnoDB transaction the way `23505` aborts a PostgreSQL transaction, and that a later `COMMIT` can persist the earlier write. The SQLite phase 0 memo shows the same kind of difference. Do not assume the PostgreSQL `COMMIT`-answered-`ROLLBACK` result generalizes.

Do not rewrite the PostgreSQL harness into a multi-database framework without an explicit architectural decision. Companion harnesses stay companion harnesses.

## Later programs

These are named so they are not started by accident.

**Persistence Architecture Observatory.** A possible future application for scheduling runs, storing artifacts, ingesting PPCS and benchmark results, and publishing reports. It is not the next implementation milestone. A CLI that writes reproducible artifacts can be enough until shared orchestration is actually needed. Python/Django and Java/Kotlin/Spring are both plausible implementation choices. The choice follows the application's requirements and the maintainer's priorities. Do not commit to microservices, a distributed worker platform, or a complex frontend in advance.

**Repository mining.** A possible observational study of dependency churn, upgrade disruption, escape hatches, migrations, and architecture changes in public repositories. It has to account for selection bias, survivorship bias, project complexity, team size, repository age, adoption differences, missing private work, and the fact that commits are not engineering hours. It complements controlled experiments. It does not replace them, and it does not start during the first benchmark.

## Evidence rules

- Recorded results stay as recorded. Do not edit case JSON, summaries, or companion evidence to match an expected verdict.
- When a document and an executable result disagree, record the disagreement. The status document is the place for that.
- Versions, commands, server identity, and harness and catalog digests stay with the run that produced them.
- Database outcomes come from an independent connection, or from the runner's observer. A framework return value is a claim.
- Exploratory results and confirmatory results are labeled differently. Small samples get descriptive statistics and an uncertainty statement, not a claim of significance.
- New adapters, new databases, and new scenarios need a research question. A directory or a draft adapter is not a completed result.

## Approval gates

Maintainer approval is required before:

1. Filing an upstream issue.
2. Submitting an upstream pull request.
3. Publishing research findings outside this repository.
4. Beginning a new major research program, including implementation of the ownership benchmark.
5. Expanding PPCS to another database.
6. Introducing a substantial new framework or adapter family.
7. Changing the core experimental evidence model, including the classification rules or the result schema.
8. Building the Observatory application.
9. Committing to a cross-language benchmark expansion beyond the approved cohort.
10. Making destructive repository changes: force-push, history rewrite, discarding uncommitted work, or deleting recorded evidence.

Ordinary documentation updates and maintenance of existing tests may proceed when a task explicitly assigns them. Approval of a documentation task is not approval of the work the documents describe.

Upstream drafts that are ready to file still need approval of the exact text. As of the tracker copied into this repository, that includes Kysely `isCommitted`, Spring `afterCommit`, psycopg `commit()`, and TypeORM `afterTransactionCommit`. The Knex draft that restates knex#6547 must not be filed again.

## Maintenance after closeout

When the production-reachability closeout criteria in the roadmap are met, PPCS enters maintenance while the ownership benchmark is the next major research priority.

Maintenance includes replies to upstream maintainers, reproduction of reported regressions, tests of proposed fixes, compatibility updates, and upkeep of existing tests and docs. It does not include new adapters, new fault families, or a new database, unless a separate approved question requires them.

Deadlock (`40P01`), serialization failure (`40001`), and statement timeout (`57014`) were not run in the production-reachability study. The study's report treats them as the same `COMMIT` command-tag path unless a framework branches on the SQLSTATE. Another scenario needs its own question or a demonstrated gap. Do not add one only to lengthen the matrix.
