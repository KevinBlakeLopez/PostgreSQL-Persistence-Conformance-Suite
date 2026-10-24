# Test contract: V1 and V2

Status: V1 and V2 written and reviewed on 2026-10-24. Not frozen. Later stages are not written yet.

This document is the contract between the application and its acceptance tests. Anyone implementing the application reads it, so it states requirements only. The requirements it makes exact are in [`application-evolution-spec.md`](application-evolution-spec.md).

## Ground rules

- The application is a Python package with a synchronous service interface. The tests call that interface in their own process and read PostgreSQL over their own connection.
- The tables and columns below are fixed. An implementation may add tables, columns, indexes, and constraints. The tests never read what it adds.
- The schema is created and changed with Alembic. The tests run `alembic upgrade head` from the repository root.
- Identifiers are `bigint` columns generated as identity.
- Timestamps are `timestamptz` columns set by PostgreSQL through a default of `now()`. The application never writes them.
- The user table is named `app_user`, because `user` is reserved in PostgreSQL.
- Every table carries `organization_id`. Composite foreign keys keep it equal to the organization of the row's parent and author.
- Isolation between organizations is the application's job. PostgreSQL row-level security is not used.

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

Events are append-only. The application never updates or deletes one.

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

## Service interface

The application provides the module `claims_app.service`. The result types come from a small package the benchmark provides, `claims_contract`, pinned like any other dependency.

```python
from claims_contract import EvidenceView, Failure, Ok, ProbeReport, RevisionView

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

### Transaction probes

These are recorded, not asserted. No result here fails the suite.

The test first attaches `duplicate_ref` to the claim. It then calls each probe on a service opened with `pool_max_size` 1, and follows each probe with `probe_follow_up`. For each probe it records:

- the `ProbeReport`;
- whether the evidence row for `first_ref` exists, read on the test's own connection;
- `pg_xact_status()` of the reported `transaction_id`;
- for the follow-up, whether its row exists, and whether its `backend_pid` matches the probe's.
