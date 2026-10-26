# Ownership benchmark methodology plan

Status: draft, revised after the 2026-10-23 design review. Not frozen. Do not implement the harness, the applications, or the pilot from this document alone. Implementation requires maintainer approval to begin the program, after the design is frozen. Items marked **Open before freeze** are listed in [`research-questions.md`](research-questions.md).

Questions: [`research-questions.md`](research-questions.md). Workload: [`application-evolution-spec.md`](application-evolution-spec.md). Sequencing: [`../research-roadmap.md`](../research-roadmap.md).

## Design before implementation

The pilot is the first execution, and only after this plan is accepted. The full V1–V7 study waits until the pilot's exit criteria are met. Results from an informal run, a changed prompt, or a hand-repaired repository are not benchmark results.

## Identical requirements

Each architecture in a cohort receives the same functional requirements for each stage. The requirements are the stage documents, one per stage, plus the acceptance tests. Wording may name a capability ("persist an evidence revision atomically"). It does not name an architecture's API ("use `session.flush`" or "hand-write this `INSERT`"). The spec also fixes the tables and columns the acceptance tests read. That is a data contract shared by every architecture, not an architecture's API.

If a requirement can only be met through an escape hatch, the escape hatch is a measurement. The requirement is not rewritten to avoid it, and it is not rewritten to force it.

## Independent acceptance tests

Acceptance tests are specified and stored apart from agent-generated implementations. Agents may read and run the tests of the current and earlier stages. Agents may not modify them, skip them, or replace them with tests they wrote. A trajectory that changes the authoritative suite is invalid.

Tests include functional checks, database invariant checks, concurrency checks where the stage requires them, migration checks, and the PPCS-derived transaction task. The tests observe the database from a connection the application does not own. Of the application's data, they read only the tables and columns the application-evolution spec fixes. From V4 on, a wire-protocol proxy between the application and PostgreSQL also records the rows each query returns, so a test can see another organization's rows cross the persistence boundary even when the response is correct. In V5 the same proxy counts the statements each report call sends. In an organization-wide read, another organization's rows crossing the boundary is a failure. In a call that names a record by identifier, it is recorded as a field per call, because fetching the named record and checking its organization in code is a legitimate way to refuse it. PPCS's cleartext proxy, `harness/lib/pg-wire-proxy.mjs`, is the starting point. The proxy has its own control: a deliberately unscoped implementation must be caught.

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
- execution limits: the caps that were actually set
- temperature or seed, when the agent exposes them
- dependency versions and lockfiles
- environment configuration, including PostgreSQL version and image digest
- the model's stated training cutoff, and the release date of each pinned persistence library

Changing any of these starts a different experiment. Runs that differ in model or prompt are not pooled into one confirmatory sample.

A run that stops on a cap is recorded as a capped run. When the agent does not expose temperature or seed, the record says so, the same way missing API cost is recorded as missing.

The default context for a stage is that stage's document and every earlier stage's, the acceptance tests for those stages, and ordinary documentation for the assigned library. The agent may read and run those tests. It never sees a later stage's document or tests. Nothing else from the research repository is in reach: not the research rationale in the application-evolution spec, this plan, the research questions, the master plan, or PPCS results, and no link to any of them. Each stage starts a fresh agent session on the repository as the previous stage left it, including its git history, and without earlier transcripts. The run record lists every supplied file with its hash. Putting the master plan's ranking or the PPCS contract verdicts in context starts a different experiment. In such an experiment the hypothesis table is labeled as an unvalidated hypothesis. Agents are not told which architecture is expected to win.

The prompt text and the numeric caps are part of pilot approval, not of the design freeze.

## Repeated trajectories

A complete evolution is repeated with a fresh context and an isolated environment. The number of repetitions is chosen before the confirmatory run and is written into the frozen spec. The pilot's job is to show that repetition is affordable and that the runs are not identical copies of one cached solution.

Do not draw a ranking from one run.

## Randomization and time

Within a repetition, all three architectures use the same model, prompt, tools, execution limits, document set, and PostgreSQL image. Only the assigned persistence technology changes, with its library documentation. The order of the three architectures inside a repetition is randomized, and the assigned order is recorded.

Record the calendar time of each trajectory so that a model change during the study can be seen. If the provider changes the model mid-study, stop and record the break. Do not treat the before and after as one sample.

## Models over time

Agent results are a snapshot of one model, one agent implementation, and one period. A better model can change every cost field and every agent-attributed correctness result. The design does not assume that a comparison holds for other or later models.

Measures differ in how much they depend on the model:

- Results that the transaction task attributes to the framework or to PostgreSQL, and V7's breakage before upgrade repair (the checks that fail on the new versions before the agent changes anything), are properties of the library version and the database, given the code that ran. Given the same code, they do not depend on the model. But the agent wrote that code and chose its APIs, so across trajectories these results are conditional on each agent's implementation, and how often each one occurs can change with the model. Reports give each result with the code and API that produced it.
- Cost fields, human review and repair time, and agent-attributed correctness results depend on the model directly.

The pre-registration in the frozen spec labels every measure as one kind or the other. Reports keep the two groups separate, and do not treat how often a library-level result occurs across trajectories as independent of the model.

Models usually know older library versions better than new ones. The configuration record includes the model's stated training cutoff and each pinned library's release date, so a recency effect can be seen.

Two decisions wait until the pilot has measured what a trajectory costs:

- whether the confirmatory run uses two models of clearly different capability, to show whether the differences between architectures grow or shrink as models improve;
- whether the frozen benchmark is re-run on later model generations. A re-run is a new experiment. It is compared with earlier runs, not pooled with them.

The frozen specification, the frozen tests, and the preserved artifacts are what make a re-run mechanical.

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

A failing acceptance-test cycle is one execution of the authoritative suite whose result is not a pass. A corrective iteration is one agent turn that edits implementation files after such a failure. The two counts stay separate. They are not added into a debugging total.

Missing cost data is reported as missing. It is not imputed in order to complete a table.

Cost fields have no weights. They are not converted into one another or into correctness results. See the weights section of [`research-questions.md`](research-questions.md).

## Correctness

Use:

- functional acceptance tests
- database invariant tests checked from an independent connection
- concurrency tests at the stages that specify them
- migration tests, including a check that history and schema agree after each stage
- the PPCS-derived transaction task below

A green functional test suite with a wrong database outcome is a correctness failure.

Each correctness result is its own record. There is no correctness grade and no overall score.

## PPCS-derived transaction task

This task is required. It is derived from [`../../research/production-reachability/README.md`](../../research/production-reachability/README.md). It is scored in three parts, and each part's score is a field list, not a grade. No part substitutes for another.

The task does not dominate the benchmark because nothing is combined. There is no overall score and no correctness grade. Outcome reporting, connection reuse, and savepoint recovery are three records beside the functional, invariant, concurrency, and migration results. Time, tokens, dollars, iterations, human time, and these correctness records are not converted into one another. The transaction records cannot rank a trajectory. This rule assigns no weight, and it does not use the master plan's Node table.

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

A reported successful commit while PostgreSQL rolled the transaction back is an outcome mismatch. Store each signal above. Do not reduce them to one mismatch bit. The same database outcome can arrive with different signals and with different documented meanings, and one bit would grade those shapes alike. Do not convert the signals into a single blended pass.

### B. Connection reuse

Run a subsequent transaction through the same pool or connection source. Record whether it commits, and whether it used the same backend. Safe reuse is a connection-safety result. It is not evidence that the earlier transaction committed.

### C. Savepoint recovery control

Repeat the workload with a valid savepoint recovery: write, savepoint, unique violation, roll back to the savepoint, commit the outer transaction. Verify that the earlier write persisted. Record the same classes of fields as part A: the API result, callbacks, row visibility, and the independent database outcome. This is the legitimate success the primary scenario must not be confused with.

### Attribution

For each part, record:

- what the framework did when used through its ordinary API
- what the agent-generated application did
- what the framework's documentation says that API means
- what PostgreSQL did
- whether the connection remained usable

A framework-level mismatch that matches PPCS is reported as framework behavior. It becomes an agent-performance result only when the agent's code departed from the specified use of the API. The suite does not assert the scripted scenarios, so failing to detect the mismatch there is not an agent result.

**What the suite asserts.** Nothing in the task's scripted scenarios. All of part A's signals are recorded, including what the operation told its caller, and so are parts B and C. The product's own handling of the same uniqueness rule is a separate path. It may use a savepoint or a retry, and the functional tests assert it like any other feature.

**Pilot host.** The pilot runs this task. The spec's natural constraint is on V3's review decision, outside the pilot, so the task uses a V1 rule instead: an evidence item's external reference is unique within its claim. The spec fixes that rule as a constraint the authoritative tests violate. A test that used whatever constraint an implementation happened to create would depend on that implementation. The pilot is not widened into V3–V7. The task is not repeated on V3's constraint. Each stage's tests include the earlier stages' tests, so the task runs again at every later stage, including after V7's upgrade.

## Evidence preservation

Each experiment preserves enough to reproduce and to re-score:

- the specification version and test version
- full source of every stage, as a patch series from the previous stage
- dependency locks and tool versions
- the agent configuration list above
- transcripts or their durable equivalent, including tool calls that changed files
- acceptance-test output
- each stage's recorded Alembic revision and database snapshot
- independent database observations for the transaction task
- cost records
- human-intervention records
- a short run manifest that points at these artifacts

Recorded artifacts are not edited to match the expected outcome. A scoring bug is fixed by re-scoring from the artifacts, or by an explicitly labeled rerun. It is not fixed by changing the old transcript.

## Statistical interpretation

Use descriptive statistics and an uncertainty estimate that matches the sample size. State how many trajectories were run. Do not claim statistical significance from a sample too small to support it. Label pilot output as exploratory. Label the pre-registered confirmatory run separately from any analysis added after seeing the data.

Pre-register, in the frozen spec, the primary comparisons and the rule for missing runs. A pre-registered comparison is a difference on a single field, read against the run-to-run spread. Analyses invented after the results are exploratory even if they use the confirmatory data.

## Pilot

The pilot compares:

1. psycopg
2. SQLAlchemy Core
3. SQLAlchemy ORM

One feature transition: V1 to V2, adding evidence revision history, as specified in the application-evolution document. The pilot also runs the PPCS-derived transaction task, on V1's external-reference rule.

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
- scoring rules are unambiguous, including the three transaction records
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

Reasons to start here: one language, one PostgreSQL server, a comparable application shape, less confounding from unrelated frameworks, and direct relevance to Python development. SQLAlchemy Core and the ORM share a project and a driver, which makes the abstraction difference easier to see. It also means a Core-versus-ORM difference cannot be blamed on an unrelated ecosystem. The psycopg arm is what shows whether leaving SQLAlchemy at runtime changes the cost.

**Adherence to the assigned API.** The cohort labels measure the assigned APIs only if a departure is defined before the first trajectory. Implementing the ORM assignment through psycopg, or the psycopg assignment through the ORM, is a departure, and it removes that trajectory from the confirmatory comparison. Ordinary writes and transaction completion use the assigned API. A lower layer used because the assigned query API cannot express a required report is the escape hatch V5 records. It is not a departure. The requirement is still not rewritten to avoid an escape hatch or to force one. Migration scripts are outside this rule: SQL inside a migration is not a departure in any arm.

**Migrations.** All three arms create and change the schema with Alembic, so the migration tool is not a difference between them. Core and the ORM may generate migrations from the tables they already declare (Alembic's autogenerate). The psycopg arm writes its migrations by hand as explicit SQL, and it does not declare SQLAlchemy tables in order to use autogenerate. Its application code never imports SQLAlchemy. SQLAlchemy is installed in that arm only because Alembic depends on it. The difference autogenerate makes belongs to the architecture: explicit SQL has no table declarations to generate from.

**Synchronous code.** All three arms and the service interface are synchronous. Concurrency tests use threads or processes. Async is a separate variable for a later study, not part of this comparison. PPCS's existing Python evidence is synchronous too.

**Connection pooling.** Each arm uses its usual pool: `psycopg_pool` in the psycopg arm, and the engine's built-in pool in the SQLAlchemy arms. The test contract gives every arm the same connection limit, expressed in each pool's own options, and a limit of one connection for the transaction probes, so that part B's connection is certainly reused. The limit is what the arms share. How each pool resets and checks a connection it hands out is library behavior, and part B of the transaction task records it as such.

**Test interface.** The Python cohort's acceptance tests call a fixed Python service interface in the test process, and read PostgreSQL on their own connection. A cohort in another language needs its own suite.

**Where the line sits.** In the ORM arm, the assigned API is the Session working on mapped classes: its unit of work (adding, changing, deleting, flushing, committing) and ORM-enabled select, insert, update, and delete statements run through the Session. A Core statement on a plain table, or textual SQL, run through the Session for an ordinary write is a recorded escape hatch. Each one is counted, and the trajectory stays in the comparison. A write or a transaction completion that bypasses the Session, through a driver cursor or a separate connection, is a departure. The Core arm follows the same line: its assigned API is Core statements run through a Connection, textual SQL for an ordinary write is a recorded escape hatch, and a write or completion that bypasses the Connection is a departure.

Versions are pinned at the start of the pilot and recorded. They are the versions current at the start of V7's calendar window (see the application-evolution spec), so the pilot runs on the same versions as V1–V6 of the full study, and its costs carry over. The upgrade stage, V7, is the planned version move. An unplanned upgrade during V1–V6 invalidates those stages.

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

## Reusing the application after the study

The workload is shaped so that one implementation, forked after the study, can become a claims-and-evidence tool for this research program. The reuse must not touch the experiment:

- Agents never see it. Stage requirements, prompts, fixtures, and sample data stay neutral and synthetic. The reuse plan appears only in planning documents outside the agents' context.
- The benchmark's own evidence never lives in agent-built code. The harness, the authoritative tests, and the recorded artifacts stay independent of every trajectory.
- The tool is a fork. A product need may decide only a product rule that no measurement depends on. Any other change waits for the fork, and the frozen spec changes only through the approval the roadmap already requires.
- No fork is taken before the pilot's results are recorded. Which implementation to fork is chosen only after its results are recorded, so expectations about the fork cannot shape the spec.
- A usable tool needs work the benchmark does not do: an interface beyond the Python service layer, and removal of the transaction task's deliberately unsafe operation. Building it is a separate approval.

## Explicitly out of the first implementation

- The Observatory application
- GitHub repository mining
- A second database
- Additional Python ORMs beside the three named above
- Hand-tuning one implementation after seeing another's score
