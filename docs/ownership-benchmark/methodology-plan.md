# Ownership benchmark methodology plan

Status: draft for maintainer review. Do not implement the harness, the applications, or the pilot from this document alone. Implementation requires maintainer approval to begin the program, after the design is frozen.

Questions: [`research-questions.md`](research-questions.md). Workload: [`application-evolution-spec.md`](application-evolution-spec.md). Sequencing: [`../research-roadmap.md`](../research-roadmap.md).

## Design before implementation

The pilot is the first execution, and only after this plan is accepted. The full V1–V7 study waits until the pilot's exit criteria are met. Results from an informal run, a changed prompt, or a hand-repaired repository are not benchmark results.

## Identical requirements

Each architecture in a cohort receives the same functional requirements for each stage. The requirements are the application-evolution spec plus the acceptance tests. Wording may name a capability ("persist an evidence revision atomically"). It does not name an architecture's API ("use `session.flush`" or "hand-write this `INSERT`").

If a requirement can only be met through an escape hatch, the escape hatch is a measurement. The requirement is not rewritten to avoid it, and it is not rewritten to force it.

## Independent acceptance tests

Acceptance tests are specified and stored apart from agent-generated implementations. Agents may read the tests. Agents may not modify them, skip them, or replace them with tests they wrote. A trajectory that changes the authoritative suite is invalid.

Tests include functional checks, database invariant checks, concurrency checks where the stage requires them, migration checks, and the PPCS-derived transaction task. The tests observe the database from a connection the application does not own.

## Equivalent starting conditions

Longitudinal scoring starts only after each architecture has a V1 implementation that satisfies the same functional contract. The cost of building that V1 is preserved. It is not discarded and replaced with a fresh generation at V2.

Each later stage is a change to the previous stage's code. Regenerating the application from scratch at each stage measures initial implementation again. It does not measure maintenance.

## Controlled agent configuration

Every trajectory records:

- model identity and version
- agent implementation
- the prompt and any system instructions
- tool permissions
- context configuration, including which documents were available
- execution limits
- dependency versions and lockfiles
- environment configuration, including PostgreSQL version and image digest

Changing any of these starts a different experiment. Runs that differ in model or prompt are not pooled into one confirmatory sample.

The hypothesis table, if it is present in the repository the agent can read, is labeled as an unvalidated hypothesis. Agents are not told which architecture is expected to win.

## Repeated trajectories

A complete evolution is repeated with a fresh context and an isolated environment. The number of repetitions is chosen before the confirmatory run and is written into the frozen spec. The pilot's job is to show that repetition is affordable and that the runs are not identical copies of one cached solution.

Do not draw a ranking from one run.

## Randomization and time

Where practical, randomize the order of architectures inside a repetition. Record the calendar time of each trajectory so that a model change during the study can be seen. If the provider changes the model mid-study, stop and record the break. Do not treat the before and after as one sample.

## Human intervention

Record human assistance separately:

- review time
- the instruction given
- repair time
- which files the human changed

A human may stop a run for safety or for a protocol breach. A human does not silently repair one architecture and leave another failed. Any repair is applied under a rule written in advance, or the affected trajectories are reported as human-repaired and kept out of the confirmatory comparison.

## Cost accounting

Record, for each stage and each trajectory:

- agent execution time
- token consumption
- API cost, where the platform provides it
- number of corrective iterations
- count of failing acceptance-test cycles
- human review time
- human repair time

Missing cost data is reported as missing. It is not imputed in order to complete a table.

## Correctness

Use:

- functional acceptance tests
- database invariant tests checked from an independent connection
- concurrency tests at the stages that specify them
- migration tests, including a check that history and schema agree after each stage
- the PPCS-derived transaction task below

A green functional test suite with a wrong database outcome is a correctness failure.

## PPCS-derived transaction task

This task is required. It is derived from [`../../research/production-reachability/README.md`](../../research/production-reachability/README.md). It is scored in three parts. No part substitutes for another. The task does not dominate the benchmark's overall score; the frozen spec will say how it combines with the other correctness results, and that combination is part of maintainer review.

Primary scenario, with no savepoint:

1. Begin a transaction through the framework's normal API.
2. Write a row that should persist if the transaction commits.
3. Trigger a real PostgreSQL unique constraint violation.
4. Catch the exception inside the transaction.
5. Allow the transaction API to finish normally.
6. Read the database from another connection.
7. Compare that read with the API's return value and with any lifecycle signals the application uses.

### A. Transaction outcome reporting

Record each of:

- whether the transaction API resolves or raises
- whether a committed-state flag becomes true
- whether commit callbacks run
- whether the application is told that the transaction committed
- whether the expected row exists

A reported successful commit while PostgreSQL rolled the transaction back is an outcome mismatch. Record the mismatch. Do not convert it into a single blended pass.

### B. Connection reuse

Run a subsequent transaction through the same pool or connection source. Record whether it commits, and whether it used the same backend. Safe reuse is a connection-safety result. It is not evidence that the earlier transaction committed.

### C. Savepoint recovery control

Repeat the workload with a valid savepoint recovery: write, savepoint, unique violation, roll back to the savepoint, commit the outer transaction. Verify that the earlier write persisted. This is the legitimate success the primary scenario must not be confused with.

### Attribution

For each part, record:

- what the framework did when used through its ordinary API
- what the agent-generated application did
- what the framework's documentation says that API means
- what PostgreSQL did
- whether the connection remained usable

A framework-level mismatch that matches PPCS is reported as framework behavior. It becomes an agent-performance result only when the agent's code departed from the specified use of the API, or when the agent failed to detect the mismatch with the tests it was given. The authoritative tests are what detect it. The agent is not graded for failing to invent that detection if the tests already contain it.

## Evidence preservation

Each experiment preserves enough to reproduce and to re-score:

- the specification version and test version
- full source of every stage, as a patch series from the previous stage
- dependency locks and tool versions
- the agent configuration list above
- transcripts or their durable equivalent, including tool calls that changed files
- acceptance-test output
- independent database observations for the transaction task
- cost records
- human-intervention records
- a short run manifest that points at these artifacts

Recorded artifacts are not edited to match the expected outcome. A scoring bug is fixed by re-scoring from the artifacts, or by an explicitly labeled rerun. It is not fixed by changing the old transcript.

## Statistical interpretation

Use descriptive statistics and an uncertainty estimate that matches the sample size. State how many trajectories were run. Do not claim statistical significance from a sample too small to support it. Label pilot output as exploratory. Label the pre-registered confirmatory run separately from any analysis added after seeing the data.

Pre-register, in the frozen spec, the primary comparisons and the rule for missing runs. Analyses invented after the results are exploratory even if they use the confirmatory data.

## Pilot

The pilot compares:

1. psycopg
2. SQLAlchemy Core
3. SQLAlchemy ORM

One feature transition: V1 to V2, adding evidence revision history, as specified in the application-evolution document.

The pilot establishes whether:

- the workload specification is precise enough that two implementers would build the same product
- the acceptance tests are architecture-neutral
- agent execution can be repeated
- the scoring distinguishes something meaningful
- the cost is small enough to repeat
- an architecture receives an advantage from the spec, the tests, or the prompt
- the artifacts support an analysis

Pilot results are not a definitive ranking and are not evidence for or against the Node hypothesis.

### Pilot exit criteria

Proceed to the full benchmark only when:

- all implementations have equivalent starting behavior
- experiment isolation works
- evidence capture is reliable
- scoring rules are unambiguous
- agent configuration is recorded
- the results can be independently verified

If a criterion fails, revise the method and record the revision. Do not widen the pilot into V3–V7 to compensate.

## Full benchmark, after the pilot

1. Freeze the specification at the accepted revision.
2. Implement the experiment harness.
3. Establish independently verified V1 implementations and keep their construction costs.
4. Run repeated V1–V7 trajectories.
5. Preserve patches and execution artifacts.
6. Analyze correctness and maintenance cost.
7. Publish the methodology.
8. Publish the results and the limitations.
9. List findings that require replication before they are treated as stable.

Cross-language expansion waits until this method is stable. The goal is a credible result from a small cohort, not the largest matrix that can be built.

## Initial cohort and later cohorts

### Python, first

| Architecture | Technology |
| --- | --- |
| Explicit SQL | psycopg |
| Query abstraction | SQLAlchemy Core |
| Full ORM | SQLAlchemy ORM |

Reasons to start here: one language, one PostgreSQL server, a comparable application shape, less confounding from unrelated frameworks, and direct relevance to Python development. SQLAlchemy Core and the ORM share a project and a driver, which makes the abstraction difference easier to see. It also means a Core-versus-ORM difference cannot be blamed on an unrelated ecosystem. The psycopg arm is what shows whether leaving SQLAlchemy entirely changes the cost.

Versions are pinned at the start of the pilot and recorded. The upgrade stage, V7, is the planned version move. An unplanned upgrade during V1–V6 invalidates those stages.

### Django, later

Django ORM may be a later cohort. The comparison has to treat Django's migrations, admin, settings, and request cycle as part of the architecture under test. Productivity that comes from the surrounding framework is attributed to that framework, not to "ORMs" as a class.

### JVM, later

| Architecture | Technology |
| --- | --- |
| Explicit SQL | JDBC |
| SQL abstraction | Spring JDBC and/or jOOQ |
| Full ORM | Hibernate/JPA |

Use Spring Boot where the application needs an application framework. The cohort has to exercise Spring transaction management and the Hibernate persistence context as they are used in an application. A thin adapter that only replays PPCS cases does not satisfy this cohort. Existing PPCS Spring and JDBC recordings remain correctness evidence. They are not this benchmark.

The choice between Spring JDBC alone, jOOQ alone, or both is part of the cohort specification when this phase is approved. It is not decided here.

### .NET, later

| Architecture | Technology |
| --- | --- |
| Explicit SQL | Npgsql |
| Lightweight mapper | Dapper |
| Full ORM | Entity Framework Core |

This cohort waits until the Python method has been validated.

### Node, not first

PPCS already holds Node correctness evidence for node-postgres, Kysely, Knex, Lucid, MikroORM, TypeORM, Drizzle, and Prisma. A Node ownership cohort may use those stacks. It is not opened in order to complete the eight-row hypothesis. If it is opened, it uses the same longitudinal rules as the Python cohort, including fresh application trajectories rather than a rescoring of PPCS.

## Explicitly out of the first implementation

- The Observatory application
- GitHub repository mining
- A second database
- Additional Python ORMs beside the three named above
- Hand-tuning one implementation after seeing another's score
