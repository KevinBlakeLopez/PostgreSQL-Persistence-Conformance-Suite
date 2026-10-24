# Application evolution specification

Status: requirements draft, revised after the 2026-10-23 design review. Not frozen. Items marked **Open before freeze** are listed in [`research-questions.md`](research-questions.md). The acceptance tests read tables and columns that this document fixes, and call a Python service interface that it defines. Neither is written yet. Beyond them, this document does not contain a schema, an API, or an implementation. Do not build the application from it until the benchmark program is approved and the pilot scope below is the assigned task.

The representative application is a small claims-and-evidence review workflow. An organization records claims, collects evidence for them, and reviewers decide whether that evidence is sufficient. It has the same shape as evidence collection in governance, risk, and compliance (GRC) work, where the claims are controls.

Every entity exists because a later measurement needs it. Do not add entities to make the domain look larger.

## Evolution rule

V1 is implemented. V2 is a change to that V1. Each later version is a change to the previous version's code. A stage that throws the repository away and generates a new application is not a valid stage.

The pilot uses only the V1 to V2 transition. V3 through V7 are specified so the pilot does not paint the design into a corner. They are not pilot scope.

## Shared concepts

| Concept | Introduced | Why it is required |
| --- | --- | --- |
| Organization | V1 | Separate teams share the application but not their data. Every durable record belongs to one organization, so V4 can test isolation on data that already exists |
| User | V1 | Evidence has an author. V3 adds reviewers from the same population |
| Claim | V1 | A statement that evidence is meant to support. V5 counts claims with current evidence, so the population of claims has to exist before the report |
| Evidence | V1 | The artifact under review. This is the record the other stages revise, approve, isolate, report, and retain |
| Event | V1, one event type | An append-only record that evidence was created. V5 reports over it and V6 retains it. Starting with one event type keeps V1 small and gives later stages a log to evolve |
| Evidence revision | V2 | Immutable history. The pilot's only feature transition |
| Review assignment | V3 | More than one required reviewer |
| Review decision | V3 | An approval rule, a uniqueness constraint, and a conflicting-update case |
| Retention policy | V6 | A rule that decides what is archived. Archival then has a requirement to implement, not an arbitrary batch job |

No other tables are required by this specification. A report in V5 is a query over these records unless an accepted revision of this spec adds a stored report and says why.

Earlier drafts framed the application as a GRC audit-evidence workflow. Claims were called controls, events were called audit events, and an Audit entity grouped controls for one engagement. Audit was dropped on 2026-10-23, because its only later use was as the grouping key of the V5 report and no measurement needed it. Claims belong directly to an organization.

## V1 — Basic claims and evidence

**Requirement.** Each user belongs to one organization. A user in an organization adds claims to that organization and attaches evidence items to a claim. A claim can have several evidence items. Each evidence item carries an external reference, such as a document identifier, that is unique within its claim. Attaching a reference the claim already has fails, and the application reports the duplicate. Another user in the same organization can read that evidence. The evidence records its author and the time it was created. Creating evidence appends one event, which records the time it was appended. V5 reports the latest event time and V6 archives by age, so the time has to exist from V1.

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
- A claim belongs to one organization, and so does a user.
- The creation event refers to an evidence item that exists.
- No claim has two evidence items with the same external reference.

**Transaction task.** The PPCS-derived transaction task uses the external-reference rule as its unique constraint, so the pilot can run it.

**"Successful" and "failed".** A call succeeds when it returns `Ok`, and fails when it returns a `Failure` or raises. Each check also reads PostgreSQL on its own connection, and a disagreement between the response and the database fails the check. The checks are in [`test-contract.md`](test-contract.md).

**Migrations.** Every arm creates and changes its schema with Alembic. The methodology plan's Python cohort section says how each arm uses it.

## V2 — Evidence revision history

**Requirement.** Evidence content is no longer updated in place. A change adds an immutable revision: its content, author, and creation time never change. Each revision records the time it was created, because V6 archives revisions by age. Previous revisions remain readable. The evidence item points at one current revision. Creating a revision is atomic with the pointer change and with an event for that revision. Two concurrent revision attempts must not leave two different revisions both marked current.

**Measure.**

- schema evolution from the V1 schema
- transactional consistency of the pointer and the new revision
- relationship changes
- preservation of V1 behavior for records that have only their original revision

**Invariants.** V2's checks are V2-1 to V2-7 in [`test-contract.md`](test-contract.md). They include a stale-base conflict and a concurrency check whose stored pointer must match the application's responses.

This is the pilot transition. The pilot stops here.

## V3 — Multiple reviewers and approval rules

**Requirement.** An evidence item can be assigned to more than one reviewer. Each reviewer records at most one decision for a given revision. A revision is in one of three approval states. It is approved when it has at least one assigned reviewer and every assigned reviewer has approved it. It is rejected when any assigned reviewer has rejected it. Otherwise it is pending, including when no reviewer is assigned. A rejection is recorded and does not delete the revision. Recording a decision appends a `decision_recorded` event for the decided revision. Any user of the organization may assign reviewers, and an item's author may review it. A decision may be recorded on any revision of the item. Two decisions from the same reviewer for the same revision cannot both persist. Conflicting decisions submitted concurrently must leave one stored decision and a database state that matches the application's response.

**Measure.**

- relationship management between assignments, decisions, users, and revisions
- concurrency control
- the business invariant on approval
- where the transaction boundary sits
- correctness when two operations conflict

The unique constraint on a review decision is a product rule. The PPCS-derived transaction task does not use it. The task runs on V1's external-reference rule, and because each stage's tests include the earlier stages' tests, it runs again at V3 and at every later stage, including after V7's upgrade. The product's own handling of a duplicate decision is tested like any other feature, and it may use a savepoint or a retry.

## V4 — Organization-level isolation

**Requirement.** A user authenticated for organization A cannot read or write claims, evidence, revisions, assignments, decisions, or events that belong to organization B. The rule holds for list endpoints, detail reads, and writes. From V5 it also holds for the report. The application enforces the rule. PostgreSQL row-level security is not used. A record of another organization is reported as not found. A query that filters in application memory after fetching another organization's rows is a failure if those rows crossed the persistence boundary.

**How the tests observe it.** A correct response can hide an unscoped fetch, so the V4 tests also watch the wire. They run through a proxy between the application and PostgreSQL that records the rows each query returns. Organization B's fixture rows carry known identifiers. A test fails if any of them reaches the application, whatever the response says.

**Measure.**

- query discipline
- authorization boundaries
- cross-tenant leakage
- whether the persistence abstraction makes an unscoped query easy to ship
- regression risk for the V1–V3 behavior inside a single organization

This stage adds no entity. It strengthens access to entities that have had an organization since V1.

## V5 — Reporting and aggregation

**Requirement.** Produce a report for one organization: counts of claims with current evidence, counts of evidence items by the approval state of their current revision, and the latest event time for each evidence item. A claim has current evidence when at least one of its evidence items has a current revision. The report matches a fixture whose expected totals are computed independently of the application. The implementation may use the framework's query API. If it cannot express the report there, an escape hatch is allowed and is recorded. The number of statements a report call sends to PostgreSQL must not grow with the number of evidence items.

**Measure.**

- query composition
- whether the SQL is visible to the implementer and to the reviewer, not scored until an observation is defined
- aggregation correctness
- the number of statements a report call sends, at both fixture sizes
- whether an escape hatch was required

**Fixtures.** The report runs against two fixtures: 30 and 300 evidence items in the reporting organization, with as many in a second organization. Both include a revision with no assigned reviewer, which the report must count as pending. The V4 proxy counts the statements each report call sends. A count that differs between the two fixtures is an N+1 load and fails the test. There is no time limit. This statement-count rule is V5's explicit performance requirement, and it is not a throughput contest.

## V6 — Retention and archival

**Requirement.** An organization has a retention policy: revisions and events older than a stated age, and not currently under review, are archived. A revision is under review while at least one assigned reviewer has not recorded a decision on it, and an event about such a revision is under review too. The current revision of an evidence item is never archived. An event is archived only together with its revision. Archival marks rows with the time they were archived; it does not move or delete them. Archival keeps referential integrity. Archived revisions remain readable through an explicit archive read and disappear from the ordinary current-evidence read. The V5 report leaves archived rows out. The operation is safe to rerun.

**Measure.**

- bulk operations
- lifecycle complexity
- referential integrity
- migration and data-management work, including how existing V1–V5 rows gain an archival state

The age threshold is set when the fixtures are frozen.

## V7 — Persistence dependency upgrade

**Requirement.** Upgrade the persistence stack to a newer supported version chosen before the trajectories start. The application must meet the V1–V6 acceptance tests on the new version. The version gap is selected so the comparison is honest about release cadence: a library that ships many small releases is not graded as if it had stood still, and a library that ships a breaking major version is not graded as if the change were cosmetic. The frozen spec names the from-version and the to-version for each architecture and states why those two versions are comparable events.

**What moves, and over what window.** The persistence stack is every persistence dependency an arm installs: psycopg, its connection pool, SQLAlchemy, and Alembic, wherever each is installed. They all move together. One calendar window sets the versions for every arm. It is fixed before the pilot: it ends on the date it is fixed and starts 24 months earlier. V1–V6 pin the versions that were current at the start of the window. V7 moves to the versions current at its end.

**Measure.**

- required code changes
- breaking API changes
- configuration changes
- migration compatibility
- regression risk
- agent corrective work
- human intervention

Frameworks do not have to move the same number of version numbers. They move across the same calendar window, and that is what "similar significance" means here. A library that released a lot in those 24 months carries that churn into V7. One that barely changed does not.

SQLAlchemy Core and the ORM ship as one project. In the Python cohort they take one shared SQLAlchemy version move, not two independent upgrade samples.

**Versions.** The exact versions follow from the window's dates. They are looked up and recorded when the window is fixed.

## Acceptance-test rules

- Tests are architecture-neutral. They call the application through a fixed, synchronous Python service interface: named functions with defined result types, called in the test process. They query PostgreSQL through the tables and columns this spec fixes. They do not read tables or columns an implementation added. From V4 on, they also record the rows each query returns, through a proxy between the application and PostgreSQL, so the application connects without TLS in the test environment.
- They do not import the application's persistence objects unless a test double would hide the behavior under study. The default is a black-box application interface plus SQL.
- Agents cannot edit the authoritative tests.
- Each stage's tests include the previous stages' tests. A V4 implementation that breaks V2 history fails.
- The suite asserts nothing in the transaction task's scripted scenarios. The task's three scores are recorded whether the functional tests pass or fail.

**Open before freeze: the service interface and the assertions.** The interface's functions and result types, and the architecture-neutral assertions. Capability wording in the requirements is not that interface. V1 to V3 are written in [`test-contract.md`](test-contract.md). V4–V7 are not.

**Open before freeze: the fixed tables and columns.** The tables and columns the tests read at each stage. V1 to V3 are written in [`test-contract.md`](test-contract.md). V4–V7 are not.

## Out of scope for the application

- A general claims-management or compliance product: risk registers, policy libraries, asset inventories, or workflow designers.
- Multi-region deployment, authentication providers, and a production user interface. A minimal interface the tests can call is enough.
- Throughput benchmarking as a goal.
- Extra entities whose only role is to make one architecture's relationship features look necessary.
