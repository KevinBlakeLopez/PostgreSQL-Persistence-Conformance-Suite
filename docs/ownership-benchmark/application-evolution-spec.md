# Application evolution specification

Status: requirements draft, revised after the 2026-10-23 design review. Not frozen. Items marked **Open before freeze** are listed in [`research-questions.md`](research-questions.md). The acceptance tests read tables and columns that this document fixes, and call a Python service interface that it defines. Neither is written yet. Beyond them, this document does not contain a schema, an API, or an implementation. Do not build the application from it until the benchmark program is approved and the pilot scope below is the assigned task.

The representative application is a small GRC-style audit evidence workflow. GRC here means governance, risk, and compliance: an organization collects evidence that a control was met, and reviewers decide whether that evidence is sufficient.

Every entity exists because a later measurement needs it. Do not add entities to make the domain look larger.

## Evolution rule

V1 is implemented. V2 is a change to that V1. Each later version is a change to the previous version's code. A stage that throws the repository away and generates a new application is not a valid stage.

The pilot uses only the V1 to V2 transition. V3 through V7 are specified so the pilot does not paint the design into a corner. They are not pilot scope.

## Shared concepts

| Concept | Introduced | Why it is required |
| --- | --- | --- |
| Organization | V1 | Every durable record belongs to one organization, so V4 can test isolation on data that already exists |
| User | V1 | Evidence has an author. V3 adds reviewers from the same population |
| Control | V1 | The statement that evidence is meant to support. V5 counts controls with current evidence, so the population of controls has to exist before the report |
| Evidence | V1 | The artifact under review. This is the record the other stages revise, approve, isolate, report, and retain |
| Audit event | V1, one event type | An append-only record that evidence was created. V5 reports over it and V6 retains it. Starting with one event type keeps V1 small and gives later stages a log to evolve |
| Evidence revision | V2 | Immutable history. The pilot's only feature transition |
| Review assignment | V3 | More than one required reviewer |
| Review decision | V3 | An approval rule, a uniqueness constraint, and a conflicting-update case |
| Retention policy | V6 | A rule that decides what is archived. Archival then has a requirement to implement, not an arbitrary batch job |

No other tables are required by this specification. A report in V5 is a query over these records unless an accepted revision of this spec adds a stored report and says why.

An earlier draft had an Audit entity that grouped controls for one engagement. It was dropped on 2026-10-23, because its only later use was as the grouping key of the V5 report and no measurement needed it. Controls belong directly to an organization.

## V1 — Basic audit evidence

**Requirement.** A user in an organization adds controls to that organization and attaches one current evidence item to a control. Another user in the same organization can read that evidence. The evidence records its author and the time it was created. Creating evidence appends one audit event, which records the time it was appended. V5 reports the latest event time and V6 archives by age, so the time has to exist from V1.

**Measure.**

- initial implementation effort
- persistence-code complexity, not scored until an observation is defined
- basic correctness against the V1 acceptance tests
- how the first schema is created

Testability is not a V1 measure. The acceptance-test rules already fix it: the tests use a black-box application interface plus SQL. It is a constraint on the tests, not a result that can differ by architecture.

Schema design is not a V1 measure either. This spec fixes the tables and columns the tests read.

**Invariants the tests check.**

- An evidence item is readable after a successful create.
- An evidence item is absent after a failed create.
- A control belongs to one organization.
- The creation event refers to an evidence item that exists.

**Open before freeze: what "successful" and "failed" mean.** The invariants do not say whether they mean the application's response or the independent database read. The methodology counts a green functional suite with a wrong database outcome as a correctness failure, so those two observations can disagree.

**Open before freeze: V1 product rules.** Whether a user belongs to one organization. How many evidence items a control has. Whether a migration tool is part of each arm. psycopg has no migration framework, and Alembic is a separate project from SQLAlchemy Core and the ORM. The choice changes V1's schema cost and V7's migration measurement.

## V2 — Evidence revision history

**Requirement.** Evidence content is no longer updated in place. A change adds an immutable revision. Each revision records the time it was created, because V6 archives revisions by age. Previous revisions remain readable. The evidence item points at one current revision. Creating a revision is atomic with the pointer change and with an audit event for that revision. Two concurrent revision attempts must not leave two different revisions both marked current.

**Measure.**

- schema evolution from the V1 schema
- transactional consistency of the pointer and the new revision
- relationship changes
- preservation of V1 behavior for records that have only their original revision

**Open before freeze: V2 invariants.** V2 has no invariant list. V3 requires the stored decision to match the application's response. V2 does not say the same of the current-revision pointer.

**Open before freeze: the pilot's uniqueness rule.** The pilot runs the PPCS-derived transaction task, so V1 or V2 gains one uniqueness rule that this spec fixes as a constraint and the authoritative tests violate. Which rule, and on which stage, is chosen with the product rules.

This is the pilot transition. The pilot stops here.

## V3 — Multiple reviewers and approval rules

**Requirement.** An evidence item can be assigned to more than one reviewer. Each reviewer records at most one decision for a given revision. The revision becomes approved only when every assigned reviewer has approved it. A rejection is recorded and does not delete the revision. Two decisions from the same reviewer for the same revision cannot both persist. Conflicting decisions submitted concurrently must leave one stored decision and a database state that matches the application's response.

**Measure.**

- relationship management between assignments, decisions, users, and revisions
- concurrency control
- the business invariant on approval
- where the transaction boundary sits
- correctness when two operations conflict

The unique constraint on a review decision is a product rule. It is also a natural place for the PPCS-derived transaction task to catch a unique violation. The task first runs in the pilot, on the uniqueness rule added to V1 or V2. The task's primary scenario still follows the methodology plan: catch the violation, finish the transaction normally, and do not add a savepoint in that primary scenario. The product's happy path may use a savepoint or a retry. The scored primary scenario does not.

**Open before freeze: zero reviewers.** What approval means for a revision with no assigned reviewer.

## V4 — Organization-level isolation

**Requirement.** A user authenticated for organization A cannot read or write controls, evidence, revisions, assignments, decisions, or events that belong to organization B. The rule holds for list endpoints, detail reads, and writes. From V5 it also holds for the report. A query that filters in application memory after fetching another organization's rows is a failure if those rows crossed the persistence boundary.

**Open before freeze: how the tests observe that failure.** The acceptance tests observe the application and PostgreSQL. A correct response can hide an unscoped fetch. V5 mentions a query log; V4 does not say its tests use one.

**Measure.**

- query discipline
- authorization boundaries
- cross-tenant leakage
- whether the persistence abstraction makes an unscoped query easy to ship
- regression risk for the V1–V3 behavior inside a single organization

This stage adds no entity. It strengthens access to entities that have had an organization since V1.

## V5 — Reporting and aggregation

**Requirement.** Produce a report for one organization: counts of controls with current evidence, counts by approval state, and the latest event time for each evidence item. The report matches a fixture whose expected totals are computed independently of the application. The implementation may use the framework's query API. If it cannot express the report there, an escape hatch is allowed and is recorded.

**Measure.**

- query composition
- whether the SQL is visible to the implementer and to the reviewer, not scored until an observation is defined
- aggregation correctness
- query performance against a documented fixture size, as a correctness-and-cost observation rather than a throughput contest
- whether an escape hatch was required

The fixture size is part of the frozen spec. It has to be large enough that an N+1 load is visible in the query log, and small enough for the pilot's successor to run repeatedly.

**Open before freeze: the V5 fixture.** The row counts, what makes an N+1 load visible, and whether there is a performance bound. Until those are set, V5 has no explicit performance requirement.

## V6 — Retention and archival

**Requirement.** An organization has a retention policy: revisions and events older than a stated age, and not currently under review, are archived. Archival keeps referential integrity. Archived revisions remain readable through an explicit archive read and disappear from the ordinary current-evidence read. The operation is safe to rerun. It does not delete the current revision or an open review.

**Measure.**

- bulk operations
- lifecycle complexity
- referential integrity
- migration and data-management work, including how existing V1–V5 rows gain an archival state

The age threshold is set when the fixtures are frozen.

**Open before freeze: what counts as under review.** Which revisions and events are currently under review, and so are not archived.

## V7 — Persistence dependency upgrade

**Requirement.** Upgrade the persistence stack to a newer supported version chosen before the trajectories start. The application must meet the V1–V6 acceptance tests on the new version. The version gap is selected so the comparison is honest about release cadence: a library that ships many small releases is not graded as if it had stood still, and a library that ships a breaking major version is not graded as if the change were cosmetic. The frozen spec names the from-version and the to-version for each architecture and states why those two versions are comparable events.

**Measure.**

- required code changes
- breaking API changes
- configuration changes
- migration compatibility
- regression risk
- agent corrective work
- human intervention

Frameworks do not have to move the same number of version numbers. They have to move across a change of similar significance, and the spec has to say what "similar" means before the runs start.

SQLAlchemy Core and the ORM ship as one project. In the Python cohort they take one shared SQLAlchemy version move, not two independent upgrade samples.

**Open before freeze: V7 comparability.** The from-version and to-version for each arm. What "similar significance" means. Whether the upgraded persistence stack includes the database driver, and whether that driver is the psycopg arm's library.

## Acceptance-test rules

- Tests are architecture-neutral. They call the application through a fixed Python service interface: named functions with defined result types, called in the test process. They query PostgreSQL through the tables and columns this spec fixes. They do not read tables or columns an implementation added.
- They do not import the application's persistence objects unless a test double would hide the behavior under study. The default is a black-box application interface plus SQL.
- Agents cannot edit the authoritative tests.
- Each stage's tests include the previous stages' tests. A V4 implementation that breaks V2 history fails.
- The suite asserts nothing in the transaction task's scripted scenarios. The task's three scores are recorded whether the functional tests pass or fail.

**Open before freeze: the service interface and the assertions.** The interface's functions and result types, and the architecture-neutral assertions. Capability wording in the requirements is not that interface.

**Open before freeze: the fixed tables and columns.** The tables and columns the tests read at each stage, V1 and V2 first. They depend on the pilot's uniqueness rule and the product rules above.

## Out of scope for the application

- A general GRC product: risk registers, policy libraries, asset inventories, or workflow designers.
- Multi-region deployment, authentication providers, and a production user interface. A minimal interface the tests can call is enough.
- Throughput benchmarking as a goal.
- Extra entities whose only role is to make one architecture's relationship features look necessary.
