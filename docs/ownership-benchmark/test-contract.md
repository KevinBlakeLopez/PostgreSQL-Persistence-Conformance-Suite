# Test contract

Status: V1 to V7 written and reviewed on 2026-10-24. Not frozen.

This document is the contract between the application and its acceptance tests. Anyone implementing the application reads it, so it states requirements only. The requirements it makes exact are in [`application-evolution-spec.md`](application-evolution-spec.md).

## Ground rules

- The application is a Python package with a synchronous service interface. The tests call that interface in their own process and read PostgreSQL over their own connection.
- The tables and columns below are fixed. An implementation may add tables, columns, indexes, and constraints. The tests never read what it adds.
- The schema is created and changed with Alembic. The tests run `alembic upgrade head` from the repository root.
- Dependencies are declared in `pyproject.toml` with exact versions and locked with `uv`. Python stays at one version from V1 to V7, chosen to support the persistence stack at both ends of V7's window.
- Identifiers are `bigint` columns generated as identity.
- Timestamps are `timestamptz` columns set by PostgreSQL through a default of `now()`. The application never writes them.
- The user table is named `app_user`, because `user` is reserved in PostgreSQL.
- Every table carries `organization_id`. Composite foreign keys keep it equal to the organization of the row's parent and author.
- Isolation between organizations is the application's job. PostgreSQL row-level security is not used.
- From V4, the DSN passed to `open_service` points at a proxy the tests run. The application must not require TLS.

## Tables after V1

### `organization`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `name` | `text` | Not null |

### `app_user`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null, references `organization` |
| `name` | `text` | Not null |

Unique: (`id`, `organization_id`).

### `claim`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null, references `organization` |
| `statement` | `text` | Not null |

Unique: (`id`, `organization_id`).

### `evidence`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null |
| `claim_id` | `bigint` | Not null |
| `external_ref` | `text` | Not null |
| `content` | `text` | Not null |
| `created_by` | `bigint` | Not null |
| `created_at` | `timestamptz` | Not null, default `now()` |

Foreign keys: (`claim_id`, `organization_id`) references `claim` (`id`, `organization_id`), and (`created_by`, `organization_id`) references `app_user` (`id`, `organization_id`).

Unique: (`claim_id`, `external_ref`), and (`id`, `organization_id`).

### `event`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null |
| `evidence_id` | `bigint` | Not null |
| `kind` | `text` | Not null. In V1 always `evidence_created` |
| `occurred_at` | `timestamptz` | Not null, default `now()` |

Foreign key: (`evidence_id`, `organization_id`) references `evidence` (`id`, `organization_id`).

Events are append-only. The application never deletes one, and never updates one except to mark it archived in V6.

## Tables after V2

V2's migration does five things, in one Alembic revision:

1. creates `evidence_revision`;
2. gives every existing evidence item one revision holding its organization, content, author, and creation time;
3. adds `evidence.current_revision_id` and points it at that revision;
4. adds `event.revision_id` and fills it, for every existing event, with the first revision of its evidence item;
5. drops `evidence.content`.

### `evidence_revision`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null |
| `evidence_id` | `bigint` | Not null |
| `content` | `text` | Not null |
| `created_by` | `bigint` | Not null |
| `created_at` | `timestamptz` | Not null, default `now()` |

Foreign keys: (`evidence_id`, `organization_id`) references `evidence` (`id`, `organization_id`), and (`created_by`, `organization_id`) references `app_user` (`id`, `organization_id`).

Unique: (`id`, `organization_id`), and (`evidence_id`, `id`).

A revision's content, author, and creation time never change. From V6, archival can mark a revision archived.

### `evidence`, changed

| Column | Type | Rule |
| --- | --- | --- |
| `current_revision_id` | `bigint` | Nullable, because a not-null rule cannot be deferred. Set for every evidence item after every successful call |

Foreign key: (`id`, `current_revision_id`) references `evidence_revision` (`evidence_id`, `id`), deferrable initially deferred. The pointer can only name one of the item's own revisions.

`content` no longer exists.

The current revision is a pointer on the evidence item, not a flag on the revision.

### `event`, changed

| Column | Type | Rule |
| --- | --- | --- |
| `revision_id` | `bigint` | Set on every event after V2's migration. (`revision_id`, `organization_id`) references `evidence_revision` (`id`, `organization_id`) |
| `kind` | `text` | `evidence_created` or `revision_created` |

## Tables after V3

V3's migration creates two tables. Existing revisions have no reviewers, so they are pending.

### `review_assignment`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null |
| `evidence_id` | `bigint` | Not null |
| `reviewer_id` | `bigint` | Not null |
| `assigned_at` | `timestamptz` | Not null, default `now()` |

Foreign keys: (`evidence_id`, `organization_id`) references `evidence` (`id`, `organization_id`), and (`reviewer_id`, `organization_id`) references `app_user` (`id`, `organization_id`).

Unique: (`evidence_id`, `reviewer_id`).

An assignment belongs to the evidence item, so it applies to every revision of that item.

### `review_decision`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | `bigint` | Primary key, generated always as identity |
| `organization_id` | `bigint` | Not null |
| `evidence_id` | `bigint` | Not null |
| `revision_id` | `bigint` | Not null |
| `reviewer_id` | `bigint` | Not null |
| `outcome` | `text` | Not null, `approved` or `rejected` |
| `decided_at` | `timestamptz` | Not null, default `now()` |

Foreign keys: (`evidence_id`, `revision_id`) references `evidence_revision` (`evidence_id`, `id`); (`evidence_id`, `reviewer_id`) references `review_assignment` (`evidence_id`, `reviewer_id`); (`evidence_id`, `organization_id`) references `evidence` (`id`, `organization_id`).

Unique: (`revision_id`, `reviewer_id`).

A decision is never updated or deleted.

### `event`, changed

| Column | Type | Rule |
| --- | --- | --- |
| `kind` | `text` | `evidence_created`, `revision_created`, or `decision_recorded` |

A `decision_recorded` event's `revision_id` names the decided revision.

### Approval state

A revision's approval state is derived from assignments and decisions. It is not stored.

- **Approved:** the item has at least one assigned reviewer, and every assigned reviewer has approved this revision.
- **Rejected:** at least one assigned reviewer has rejected this revision.
- **Pending:** otherwise, including when the item has no assigned reviewer.

## Tables after V6

V4 and V5 add no tables. V6's migration creates `retention_policy` and adds `archived_at` to `evidence_revision` and `event`. Every existing row starts with `archived_at` null.

### `retention_policy`

| Column | Type | Rule |
| --- | --- | --- |
| `organization_id` | `bigint` | Primary key, references `organization` |
| `max_age` | `interval` | Not null, greater than zero |

An organization has at most one policy.

### `evidence_revision` and `event`, changed

| Column | Type | Rule |
| --- | --- | --- |
| `archived_at` | `timestamptz` | Null until the row is archived. The archiving statement sets it to `now()`, once. It is the only column archival changes |

### Archival rules

A revision is archived by `run_archival` when all of these hold:

1. it is not archived yet;
2. its `created_at` is older than `now()` minus the organization's `max_age`;
3. it is not its evidence item's current revision;
4. it is not under review.

A revision is under review while a reviewer counted for it has not recorded a decision on it. For the current revision, every assigned reviewer counts. For a revision that has been replaced, only reviewers assigned before the next revision of the item was created count.

When a revision is archived, all of its events are archived in the same statement or transaction, whatever their own age. An event is never archived on its own.

## The V7 upgrade

V7 adds no tables and no service calls. It changes versions.

1. The harness replaces the pinned versions of psycopg, `psycopg_pool`, SQLAlchemy, and Alembic, wherever each is installed, with the versions current at the end of V7's window, and updates the lock. It changes nothing else.
2. Before the agent changes anything, the harness runs the full suite on the new versions and records which checks fail.
3. The agent then makes every earlier check pass on the new versions.

Pinning a package back to an older version, or copying old library code into the application, is a departure.

## Service interface

The application provides the module `claims_app.service`. The result types come from a small package the benchmark provides, `claims_contract`, pinned like any other dependency.

```python
from claims_contract import ApprovalState, ArchivalSummary, ClaimView, EvidenceView, Failure, Ok, ProbeReport, Report, RevisionView

def open_service(dsn: str, pool_max_size: int) -> "Service": ...

class Service:
    def close(self) -> None: ...

    # Setup
    def create_organization(self, name: str) -> Ok[int] | Failure: ...
    def create_user(self, organization_id: int, name: str) -> Ok[int] | Failure: ...

    # V1
    def add_claim(self, actor: int, statement: str) -> Ok[int] | Failure: ...
    def attach_evidence(self, actor: int, claim_id: int, external_ref: str, content: str) -> Ok[int] | Failure: ...
    def get_evidence(self, actor: int, evidence_id: int) -> Ok[EvidenceView] | Failure: ...
    def list_evidence(self, actor: int, claim_id: int) -> Ok[list[EvidenceView]] | Failure: ...

    # V2
    def revise_evidence(self, actor: int, evidence_id: int, based_on_revision_id: int, content: str) -> Ok[int] | Failure: ...
    def list_revisions(self, actor: int, evidence_id: int) -> Ok[list[RevisionView]] | Failure: ...

    # V3
    def assign_reviewer(self, actor: int, evidence_id: int, reviewer_id: int) -> Ok[int] | Failure: ...
    def record_decision(self, actor: int, revision_id: int, outcome: str) -> Ok[int] | Failure: ...
    def approval_state(self, actor: int, revision_id: int) -> Ok[ApprovalState] | Failure: ...

    # V4
    def list_claims(self, actor: int) -> Ok[list[ClaimView]] | Failure: ...

    # V5
    def report(self, actor: int) -> Ok[Report] | Failure: ...

    # V6
    def set_retention_policy(self, actor: int, max_age_days: int) -> Ok[None] | Failure: ...
    def run_archival(self, actor: int) -> Ok[ArchivalSummary] | Failure: ...
    def list_archived_revisions(self, actor: int, evidence_id: int) -> Ok[list[RevisionView]] | Failure: ...

    # Transaction probes, from V1
    def probe_caught_violation(self, actor: int, claim_id: int, first_ref: str, duplicate_ref: str) -> ProbeReport: ...
    def probe_savepoint_recovery(self, actor: int, claim_id: int, first_ref: str, duplicate_ref: str) -> ProbeReport: ...
    def probe_follow_up(self, actor: int, claim_id: int, ref: str) -> ProbeReport: ...
```

- `actor` is the ID of the user making the call. There is no authentication: the service trusts it. A write acts in the actor's organization.
- An expected failure is returned as `Failure(kind)`, where `kind` is `NOT_FOUND`, `DUPLICATE_REFERENCE`, or `CONFLICT`. An exception that escapes the service is an unexpected failure.
- `EvidenceView` has `id`, `claim_id`, `external_ref`, `content`, `created_by`, and `created_at`. From V2 it also has `current_revision_id`, and `content` is the current revision's content.
- `RevisionView` has `id`, `evidence_id`, `content`, `created_by`, and `created_at`.
- In V2, `attach_evidence` also creates the item's first revision, points `current_revision_id` at it, and appends one `evidence_created` event that refers to both.
- `revise_evidence` succeeds only when `based_on_revision_id` is the item's current revision. Otherwise it fails with `CONFLICT`.
- `assign_reviewer` assigns a user of the actor's organization to an evidence item. Any user of the organization may assign, and an item's author may be its reviewer. Assigning a reviewer who is already assigned fails with `CONFLICT`. An item or a reviewer that is not found, including one in another organization, fails with `NOT_FOUND`.
- `record_decision` records the actor's decision, `approved` or `rejected`, on a revision. The actor must be assigned to the revision's evidence item; otherwise the call fails with `NOT_FOUND`. A decision may be recorded on any revision of the item, not only the current one. A second decision by the same reviewer on the same revision fails with `CONFLICT`. Recording a decision and appending its `decision_recorded` event happen in one transaction.
- `approval_state` returns `approved`, `rejected`, or `pending` for a revision, as defined above. `ApprovalState` is that set of three strings.
- From V4, every call that takes an `actor` is scoped to the actor's organization. A record of another organization is reported as `NOT_FOUND`, exactly like a record that does not exist. The setup calls take no actor and are not scoped.
- `list_claims` returns the claims of the actor's organization. `ClaimView` has `id` and `statement`.
- `report` describes the actor's organization. `Report` has three fields:
  - `claims_with_current_evidence`: the number of claims with at least one evidence item that has a current revision;
  - `evidence_by_state`: a mapping from `approved`, `rejected`, and `pending` to the number of evidence items whose current revision is in that state. All three keys are always present;
  - `latest_event_at`: a mapping from each evidence item's identifier to the latest `occurred_at` among its events.

  `report` is an organization-wide read. The number of statements it sends must not grow with the number of evidence items.
- `set_retention_policy` creates or replaces the actor's organization's policy. Any user of the organization may set it.
- `run_archival` applies the archival rules to the actor's organization in one transaction, so a failure archives nothing. It returns an `ArchivalSummary` with the numbers of `revisions` and `events` it archived. Without a policy, it archives nothing. It is an organization-wide read.
- From V6, ordinary reads leave archived revisions out. `list_revisions` does not list them, and `record_decision` and `approval_state` on an archived revision fail with `NOT_FOUND`. `list_archived_revisions` lists an item's archived revisions. `RevisionView` gains `archived_at`, which ordinary reads always report as `None`.
- The V5 report leaves archived events out of `latest_event_at`.

### Connection pool

`pool_max_size` caps the connections the service holds. The service opens them as needed and reuses them. With `psycopg_pool`, that is `min_size=1` and `max_size=pool_max_size`. With SQLAlchemy, it is `pool_size=pool_max_size` and `max_overflow=0`. The tests use 4, and 1 for the transaction probes.

### Transaction probes

Each probe runs one transaction through the assigned library's ordinary transaction API.

`probe_caught_violation`:

1. Begin a transaction.
2. Read `pg_current_xact_id()` and `pg_backend_pid()`.
3. Attach an evidence item to `claim_id` with `first_ref`. This write must reach PostgreSQL before step 4 starts.
4. Attach an evidence item to `claim_id` with `duplicate_ref`. That reference is already attached to the claim, so PostgreSQL rejects the write with a unique-constraint violation.
5. Catch that error inside the transaction and continue. Do not use a savepoint, and do not roll back.
6. Let the transaction API finish normally.
7. Return a `ProbeReport`.

`probe_savepoint_recovery` is the same, except that step 4 runs inside a savepoint, and step 5 rolls back to that savepoint before continuing.

`probe_follow_up` runs one ordinary transaction. It reads `pg_backend_pid()`, attaches an evidence item with `ref`, and returns a `ProbeReport`.

The reads of `pg_current_xact_id()` and `pg_backend_pid()` may use textual SQL with any library. If the transaction API raises when it finishes, the probe catches that exception after the transaction and reports it. The probes do nothing else.

`ProbeReport` fields:

| Field | Meaning |
| --- | --- |
| `transaction_id` | The value read in step 2, as text. `None` for `probe_follow_up` |
| `backend_pid` | The value read in step 2, or by `probe_follow_up` |
| `outcome` | `returned` or `raised`: whether the transaction API returned or raised when it finished |
| `exception_type` | The qualified name of the exception the transaction API raised, or `None` |
| `committed_flag` | The value of the API's committed-state flag after it finished, or `None` if the API has no such flag |
| `commit_hook_ran` | Whether a commit hook registered through the API ran, or `None` if the API offers no commit hook |
| `reported_committed` | Whether the probe concluded that the transaction committed |

## Checks

A call *succeeds* when it returns `Ok` and *fails* when it returns a `Failure` or raises. After every call, the check also reads PostgreSQL on the test's own connection. When the response and the database disagree, the check fails.

### Schema

- **S1.** On an empty database, `alembic upgrade head` creates every V1 table and column above, with these types, nullability, keys, references, and the unique constraint.
- **S2.** On a V1 database that holds data, `alembic upgrade head` produces the V2 tables and columns. `evidence.content` no longer exists.
- **S3.** On a V2 database that holds data, `alembic upgrade head` produces the V3 tables, columns, keys, and unique constraints. Existing revisions have no decisions.
- **S4.** On a V3 database that holds data, `alembic upgrade head` succeeds and leaves every fixed table and column as V3 defined it. V4 may add indexes.
- **S5.** The same holds for V5's migration on a V4 database.
- **S6.** On a V5 database that holds data, `alembic upgrade head` creates `retention_policy` and adds `archived_at` to `evidence_revision` and `event`, null on every existing row.
- **S7.** On the new versions, `alembic upgrade head` builds the V6 schema from an empty database, and runs on a V6 database that holds data without changing any fixed table, column, or row.

### V1

- **V1-1.** `add_claim` succeeds. A claim row exists in the actor's organization with the statement.
- **V1-2.** `attach_evidence` succeeds. One evidence row exists with the claim, the reference, the content, and the actor as `created_by`, and `created_at` is set. Exactly one `evidence_created` event refers to it, and `occurred_at` is set.
- **V1-3.** Attaching a reference the claim already has fails with `DUPLICATE_REFERENCE`. No evidence row and no event are added.
- **V1-4.** The same reference attached to a different claim succeeds.
- **V1-5.** Attaching to a claim that does not exist fails with `NOT_FOUND`. No evidence row and no event are added.
- **V1-6.** A second user in the same organization reads the evidence through `get_evidence` and `list_evidence` and sees the stored values.
- **V1-7.** After every V1 check, the database holds:
  - every claim and every user in an organization;
  - every event referring to an existing evidence item;
  - no claim with two evidence items that share a reference;
  - every evidence item's author in its claim's organization.

### V2

- **V2-1.** The migration preserves V1 data. Each V1 evidence item has exactly one revision with its content, author, and creation time. `current_revision_id` names that revision, and the item's events refer to it.
- **V2-2.** `attach_evidence` succeeds and creates the first revision. `current_revision_id` names it, and one `evidence_created` event refers to both.
- **V2-3.** `revise_evidence` with the current revision as `based_on_revision_id` succeeds. A new revision row exists, `current_revision_id` names it, and one `revision_created` event refers to it. Earlier revisions are unchanged and still listed by `list_revisions`.
- **V2-4.** `revise_evidence` with a `based_on_revision_id` that is no longer current fails with `CONFLICT`. No revision, no pointer change, and no event are added.
- **V2-5.** Atomicity. The test arms a trigger on `event` that rejects the next `revision_created` insert. `revise_evidence` fails. No revision row was added, the pointer is unchanged, and no event was added.
- **V2-6.** Concurrency. Two threads call `revise_evidence` on the same item with the same `based_on_revision_id`, released together, for 20 rounds. In each round exactly one call succeeds and the other fails with `CONFLICT`. The pointer names the successful call's revision. The failed call left no revision and no event.
- **V2-7.** After every V2 check, every evidence item's `current_revision_id` names one of its own revisions, and every event refers to an existing revision of its evidence item.
- Every V1 check still passes. V1-2 now also expects the first revision.

### V3

- **V3-1.** `assign_reviewer` succeeds. One assignment row exists with the organization, the item, and the reviewer.
- **V3-2.** Assigning the same reviewer to the same item again fails with `CONFLICT`. No row is added.
- **V3-3.** Assigning to an item that does not exist, or assigning a user of another organization, fails with `NOT_FOUND`. No row is added.
- **V3-4.** An assigned reviewer's `record_decision` on a revision succeeds. One decision row exists with the revision, the reviewer, and the outcome. Exactly one `decision_recorded` event refers to the revision.
- **V3-5.** Approval states, read through `approval_state` and recomputed by the test from the decision rows:
  - an item with no assigned reviewer: pending;
  - two assigned reviewers, one approval: pending;
  - two assigned reviewers, two approvals: approved;
  - two assigned reviewers, one approval and one rejection: rejected.
- **V3-6.** A second decision by the same reviewer on the same revision fails with `CONFLICT`. No decision and no event are added, and the first decision is unchanged.
- **V3-7.** A decision by a user who is not assigned to the item fails with `NOT_FOUND`. No decision and no event are added.
- **V3-8.** After `revise_evidence`, the new revision is pending, even when the previous revision was approved. Assignments carry over; decisions do not.
- **V3-9.** Concurrency. The same reviewer submits `approved` and `rejected` on the same revision from two threads, released together, for 20 rounds. In each round exactly one call succeeds and the other fails with `CONFLICT`. The stored outcome is the successful call's outcome, and there is one `decision_recorded` event for it.
- **V3-10.** Atomicity. The test arms a trigger on `event` that rejects the next `decision_recorded` insert. `record_decision` fails, and no decision row was added.
- **V3-11.** After every V3 check, the database holds:
  - every decision's reviewer assigned to the decision's evidence item;
  - every decision's revision belonging to that evidence item;
  - at most one decision per reviewer per revision;
  - as many `decision_recorded` events on each revision as decisions on it.
- Every V1 and V2 check still passes.

### V4

**Fixture.** Each V4 check starts with two organizations. Organization A has two users, claims, evidence with several revisions, assignments, and decisions, created through the service. The test then restarts every identity column at 9,000,000,000 and creates the same shape for organization B, so every identifier of B is at least that value. Every text value of B, including the organization's and users' names, contains a token the test generates for the run. The test then restarts the identity columns below 9,000,000,000 again.

**The proxy.** The application's DSN points at a proxy between the application and PostgreSQL. The proxy records every row PostgreSQL returns to the application, decoding text and binary formats. A *value of B* is an integer of at least 9,000,000,000, or a text containing B's token.

- In an organization-wide read, any value of B fails the check, whatever the response says. A query that fetches B's rows and drops them in application code therefore fails, even when the response is correct. `list_claims` is such a read, and from V5 so is the report.
- In a call that names a record by identifier, values of B may cross: fetching the named record to find that it belongs to B is an accepted way to answer `NOT_FOUND`. The check records the values of B that crossed, and passes when the response is right and nothing was written.

Each check runs as a user of organization A against identifiers of organization B, in one direction only.

- **V4-1.** Detail reads. `get_evidence`, `list_revisions`, and `approval_state` on identifiers of B fail with `NOT_FOUND`.
- **V4-2.** Lists. `list_evidence` on a claim of B fails with `NOT_FOUND`. `list_claims` returns exactly A's claims.
- **V4-3.** Writes. Each of these fails with `NOT_FOUND`, and no row of A or B is added or changed:
  - `attach_evidence` to a claim of B;
  - `revise_evidence` on an evidence item of B, based on its current revision;
  - `assign_reviewer` of a user of B to an item of A, and of a user of A to an item of B;
  - `record_decision` on a revision of B.
- **V4-4.** For `list_claims`, the proxy saw no value of B. For each call in V4-1 to V4-3, the values of B that crossed are recorded. They do not fail the check.
- **V4-5.** An identifier that exists in no organization fails with `NOT_FOUND`, the same failure as an identifier of B.
- The transaction probes run with A's claim and are not part of V4's checks.
- Every V1 to V3 check still passes inside one organization.

**Proxy controls.** Before V4's checks are trusted, the harness runs them against two reference implementations the benchmark keeps. In the first, `list_claims` fetches every organization's claims and filters them in application code, and named-record calls fetch by identifier and check the organization in code. It must fail V4-4, and its V4-1 to V4-3 calls must show recorded values of B. The second scopes every query. It must pass V4-4 and record no value of B.

### V5

**Fixtures.** Each fixture is a fresh database built through the service.

- The reporting organization has 30 evidence items in the small fixture and 300 in the large one: 10 or 100 claims with three items each, plus 5 claims with no evidence.
- Items have one to three revisions. Their current revisions cover all three approval states, and at least one current revision belongs to an item with no assigned reviewer, so it is pending.
- A second organization has the same shape, marked as in V4.

Expected counts come from the fixture's plan. Expected latest event times come from the test's own query over `event`. Both are independent of the application.

**Counting statements.** The proxy counts every statement the application sends during one `report` call, as simple-query and extended-protocol execute messages, including transaction control. The service is opened with `pool_max_size` 1, and the first `report` call after opening is not counted, so connection setup does not enter the count.

- **V5-1.** On the small fixture, `report` returns exactly the expected `claims_with_current_evidence`, `evidence_by_state`, and `latest_event_at`.
- **V5-2.** The same on the large fixture.
- **V5-3.** The statement count is the same on both fixtures. A difference is an N+1 load and fails. There is no time limit.
- **V5-4.** The item with no assigned reviewer is counted as pending.
- **V5-5.** After `revise_evidence` on an item whose current revision was approved, the report counts that item as pending, and its latest event time is the new revision's event.
- **V5-6.** `report` is an organization-wide read: the proxy saw no value of the second organization.
- Every V1 to V4 check still passes.

### V6

**Making rows old.** The tests age rows by updating their `created_at`, `occurred_at`, and `assigned_at` directly. Each check sets a 30-day policy and ages the rows it needs by 60 days.

- **V6-1.** An aged revision that is not current and not under review is archived by `run_archival`. Its `archived_at` is set, all of its events are archived, and the summary's counts match the rows that changed.
- **V6-2.** The current revision is never archived, however old, and its events stay.
- **V6-3.** An aged, replaced revision with a reviewer, assigned before it was replaced, who has not decided on it, is not archived. After that reviewer records a decision on it, the next run archives it.
- **V6-4.** A reviewer assigned after a revision was replaced does not keep it under review.
- **V6-5.** After archival, `list_revisions` leaves the archived revision out, `record_decision` and `approval_state` on it fail with `NOT_FOUND`, and `list_archived_revisions` lists it with its `archived_at`. The report leaves its events out of `latest_event_at`.
- **V6-6.** A second run archives nothing, and every `archived_at` set by the first run is unchanged.
- **V6-7.** Without a policy, `run_archival` archives nothing.
- **V6-8.** Atomicity. The test arms a trigger that rejects the next update setting `event.archived_at`. `run_archival` fails, and no revision or event is archived.
- **V6-9.** Isolation. `run_archival` archives only the actor's organization's rows, and, as an organization-wide read, lets no value of the second organization cross.
- **V6-10.** After every V6 check, the database holds:
  - every event archived exactly when its revision is archived;
  - no archived current revision;
  - every reference still resolving.
- Every V1 to V5 check still passes.

### V7

- **V7-1.** Every V1 to V6 check passes on the new versions.
- **V7-2.** The lock holds the window-end version of every persistence package the application installs.

Recorded, not checked:

- which checks failed right after the version change, before the agent changed anything;
- the deprecation warnings the persistence libraries emit during a full suite run, before and after the agent's work;
- the transaction-probe records on the new versions, beside the V6 records.

### Transaction probes

These are recorded, not asserted. No result here fails the suite.

The test first attaches `duplicate_ref` to the claim. It then calls each probe on a service opened with `pool_max_size` 1, and follows each probe with `probe_follow_up`. For each probe it records:

- the `ProbeReport`;
- whether the evidence row for `first_ref` exists, read on the test's own connection;
- `pg_xact_status()` of the reported `transaction_id`;
- for the follow-up, whether its row exists, and whether its `backend_pid` matches the probe's.
