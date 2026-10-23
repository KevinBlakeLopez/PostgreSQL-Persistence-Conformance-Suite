# Application evolution specification

Status: requirements draft for maintainer review. This document does not contain a schema, an API, or an implementation. Do not build the application from it until the benchmark program is approved and the pilot scope below is the assigned task.

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
| Audit | V1 | Groups the controls under assessment for one engagement |
| Control | V1 | The statement that evidence is meant to support |
| Evidence | V1 | The artifact under review. This is the record the other stages revise, approve, isolate, report, and retain |
| Audit event | V1, one event type | An append-only record that evidence was created. V5 reports over it and V6 retains it. Starting with one event type keeps V1 small and gives later stages a log to evolve |
| Evidence revision | V2 | Immutable history. The pilot's only feature transition |
| Review assignment | V3 | More than one required reviewer |
| Review decision | V3 | An approval rule, a uniqueness constraint, and a conflicting-update case |
| Retention policy | V6 | A rule that decides what is archived. Archival then has a requirement to implement, not an arbitrary batch job |

No other tables are required by this specification. A report in V5 is a query over these records unless an accepted revision of this spec adds a stored report and says why.

## V1 — Basic audit evidence

**Requirement.** A user in an organization creates an audit, adds controls to that audit, and attaches one current evidence item to a control. Another user in the same organization can read that evidence. The evidence records its author and the time it was created. Creating evidence appends one audit event.

**Measure.**

- initial implementation effort
- persistence-code complexity
- basic correctness against the V1 acceptance tests
- schema and migration design, including how the first schema is created
- testability, meaning whether the acceptance tests can run without reading the framework's private state

**Invariants the tests check.**

- An evidence item is readable after a successful create.
- An evidence item is absent after a failed create.
- A control belongs to one audit, and an audit belongs to one organization.
- The creation event refers to an evidence item that exists.

## V2 — Evidence revision history

**Requirement.** Evidence content is no longer updated in place. A change adds an immutable revision. Previous revisions remain readable. The evidence item points at one current revision. Creating a revision is atomic with the pointer change and with an audit event for that revision. Two concurrent revision attempts must not leave two different revisions both marked current.

**Measure.**

- schema evolution from the V1 schema
- transactional consistency of the pointer and the new revision
- relationship changes
- preservation of V1 behavior for records that have only their original revision

This is the pilot transition. The pilot stops here.

## V3 — Multiple reviewers and approval rules

**Requirement.** An evidence item can be assigned to more than one reviewer. Each reviewer records at most one decision for a given revision. The revision becomes approved only when every assigned reviewer has approved it. A rejection is recorded and does not delete the revision. Two decisions from the same reviewer for the same revision cannot both persist. Conflicting decisions submitted concurrently must leave one stored decision and a database state that matches the application's response.

**Measure.**

- relationship management between assignments, decisions, users, and revisions
- concurrency control
- the business invariant on approval
- where the transaction boundary sits
- correctness when two operations conflict

The unique constraint on a review decision is a product rule. It is also the natural place for the PPCS-derived transaction task to catch a unique violation. The task's primary scenario still follows the methodology plan: catch the violation, finish the transaction normally, and do not add a savepoint in that primary scenario. The product's happy path may use a savepoint or a retry. The scored primary scenario does not.

## V4 — Organization-level isolation

**Requirement.** A user authenticated for organization A cannot read or write audits, controls, evidence, revisions, assignments, decisions, or events that belong to organization B. The rule holds for list endpoints, detail reads, reports, and writes. A query that filters in application memory after fetching another organization's rows is a failure if those rows crossed the persistence boundary.

**Measure.**

- query discipline
- authorization boundaries
- cross-tenant leakage
- whether the persistence abstraction makes an unscoped query easy to ship
- regression risk for the V1–V3 behavior inside a single organization

This stage adds no entity. It strengthens access to entities that have had an organization since V1.

## V5 — Reporting and aggregation

**Requirement.** Produce a report for one organization and one audit: counts of controls with current evidence, counts by approval state, and the latest event time for each evidence item. The report matches a fixture whose expected totals are computed independently of the application. The implementation may use the framework's query API. If it cannot express the report there, an escape hatch is allowed and is recorded.

**Measure.**

- query composition
- whether the SQL is visible to the implementer and to the reviewer
- aggregation correctness
- query performance against a documented fixture size, as a correctness-and-cost observation rather than a throughput contest
- whether an escape hatch was required

The fixture size is part of the frozen spec. It is large enough that an N+1 load is visible in the query log, and small enough for the pilot's successor to run repeatedly.

## V6 — Retention and archival

**Requirement.** An organization has a retention policy: revisions and events older than a stated age, and not currently under review, are archived. Archival keeps referential integrity. Archived revisions remain readable through an explicit archive read and disappear from the ordinary current-evidence read. The operation is safe to rerun. It does not delete the current revision or an open review.

**Measure.**

- bulk operations
- lifecycle complexity
- referential integrity
- migration and data-management work, including how existing V1–V5 rows gain an archival state

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

## Acceptance-test rules

- Tests are architecture-neutral. They call the application and they query PostgreSQL.
- They do not import the application's persistence objects unless a test double would hide the behavior under study. The default is a black-box application interface plus SQL.
- Agents cannot edit the authoritative tests.
- Each stage's tests include the previous stages' tests. A V4 implementation that breaks V2 history fails.
- The transaction task's three scores are recorded even when the functional tests pass.

## Out of scope for the application

- A general GRC product: risk registers, policy libraries, asset inventories, or workflow designers.
- Multi-region deployment, authentication providers, and a production user interface. A minimal interface the tests can call is enough.
- Throughput benchmarking as a goal.
- Extra entities whose only role is to make one architecture's relationship features look necessary.
