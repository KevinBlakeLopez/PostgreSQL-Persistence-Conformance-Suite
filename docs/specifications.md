# Specifications

The machine-readable catalog is `specifications/transactions.v1.json`; this page describes it. Every case names its invariants, its fault, its preconditions and what the application could know. Cases are written without framework terms. Each adapter implements them with its framework's own APIs.

**Fixture.** Each case runs in a fresh database that contains:

- `item (id serial, name text, qty int)`, which holds the markers;
- `uniq (id serial, code text unique)`, holding one row, `'taken'`.

**Markers.** A marker is a row in `item` whose name is unique to the run, for example `tx-8f6a3c`.

**Common settings.** Unless a case says otherwise, the pool holds one connection (`pool_max: 1`). Cases are versioned individually, and families and the catalog as a whole are versioned too.

The case ID is followed by the fault category (`docs/methodology.md`).

## CTL-01: Observation controls

Can the runner see, through its own connections, a transaction the framework committed, and the absence of one the framework rolled back? If not, the adapter's other results are not credible.

- **CTL-01.1** A transaction that the API reports as committed is committed: `pg_xact_status()` reports it committed, and an independent connection sees its marker.
- **CTL-01.2** A transaction that the API reports as rolled back is not committed: `pg_xact_status()` reports it aborted, and an independent connection does not see its marker.

| Case | Steps |
| --- | --- |
| `CTL-01.commit` (none) | The transaction writes `tx` and ends normally. |
| `CTL-01.rollback` (none) | The transaction writes `tx` and raises an application error. |

## TX-01A: Commit of an aborted transaction

A statement fails inside a transaction, and the application catches the error. PostgreSQL has aborted the transaction, and answers the later `COMMIT` with `ROLLBACK`. Does the framework report a successful commit?

- **TX-01A.1** When PostgreSQL has aborted the transaction before it ends, so that its COMMIT is answered with ROLLBACK, the API does not report a successful commit.

**`TX-01A.caught-error-then-commit`** (category A):

1. The transaction writes `tx`.
2. It inserts the duplicate `'taken'` and catches the unique violation (23505).
3. It ends normally.

The runner confirms, server-side, that the session was `idle in transaction (aborted)` before the transaction ended. **What the application could know:** PostgreSQL's reply to `COMMIT` carries the command tag `ROLLBACK`, so the outcome reaches the client.

## TX-01B: Commit outcome unknown to the client

The connection, or PostgreSQL's reply, is lost around `COMMIT`, so the client never receives a reply to `COMMIT`. Does the framework still assert an outcome?

- **TX-01B.1** When the client has received no reply to COMMIT, because the connection or the reply was lost, the API does not report a successful commit.
- **TX-01B.2** When the client has received no reply to COMMIT, the API does not report a confirmed rollback.

A framework may hold other evidence of the outcome, for example that its driver never sent `COMMIT`. PPCS 0.1 does not evaluate such evidence: without a reply to `COMMIT`, a definite report of either outcome violates the family.

| Case | Steps | PostgreSQL's outcome |
| --- | --- | --- |
| `TX-01B.conn-lost-before-commit` (B) | The transaction writes `tx`. At the checkpoint, the runner terminates its backend. The adapter waits 100 ms, then ends the transaction normally. | Rolled back |
| `TX-01B.commit-reply-discarded` (D, client-side simulation) | The transaction writes `tx`. The adapter arms a fault in its driver: `COMMIT` is sent and completes, then the client closes its connection and discards the reply. The transaction ends normally. | Committed |

## TX-02: Failed savepoint rollback

A nested scope fails, and its `ROLLBACK TO SAVEPOINT` fails too. Does the outer transaction silently continue under an incorrect nesting state? That would mean committing the failed scope's writes, reporting success for a transaction PostgreSQL did not commit, or leaving its transaction open after its API returned.

- **TX-02.1** If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes.
- **TX-02.2** When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction.

**Shared steps:**

1. The outer scope writes `outer`.
2. A nested scope, opened with the framework's savepoint API, writes `inner` and raises an application error. The savepoint rollback then fails, as each case below describes.
3. The outer scope catches the error and ends normally.
4. At checkpoint `after-outer`, the runner records whether the connection is still inside a transaction.

| Case | How the savepoint rollback fails |
| --- | --- |
| `TX-02.savepoint-rollback-not-sent` (C) | The driver fails `ROLLBACK TO SAVEPOINT` without sending it. |
| `TX-02.savepoint-rollback-rejected` (C) | The driver rewrites `ROLLBACK TO SAVEPOINT` to name a savepoint that does not exist, so PostgreSQL rejects it (3B001) and aborts the transaction. The error is PostgreSQL's; the trigger is artificial. |
| `TX-02.conn-lost-before-savepoint-rollback` (B) | Inside the nested scope, the runner terminates the backend; the rollback then fails on the closed connection. |

## TX-03: Connection recovery and unsafe pool reuse

A transaction fails on a pooled connection, and its `ROLLBACK` fails too. Does the pool give that connection to unrelated work while it still holds the failed transaction? Does the pool recover its capacity?

- **TX-03.1** Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own.
- **TX-03.2** After the failure, the next unit of work on the same pool completes within the bound (5 s) and commits.

**Shared steps:**

1. Unit 1 writes `doomed` and raises an application error.
2. Its `ROLLBACK` fails, as each case below describes.
3. Unit 2, the next unit of work on the same pool of one connection, writes `next` and ends normally.

**How unsafe reuse is detected:** unit 2 reports its own `pg_current_xact_id()`. If that equals unit 1's, unit 2 ran inside the failed transaction, and `pg_xact_status()` then shows whether that transaction committed.

| Case | How the ROLLBACK fails |
| --- | --- |
| `TX-03.rollback-not-sent` (C) | The driver fails the top-level `ROLLBACK` without sending it, so the connection keeps its open transaction. |
| `TX-03.conn-lost-in-transaction` (B) | The runner terminates unit 1's backend before the `ROLLBACK`. |

## TX-04: Nested transaction propagation

When application code nests transactional work through an API that promises a propagation behaviour, does the work land in the transaction boundary the API promises? Frameworks do not share propagation modes. An adapter whose framework does not expose a case's behaviour through its supported API reports it UNSUPPORTED, which is not a failure.

- **TX-04.1** When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes.
- **TX-04.2** A nested scope (a savepoint) that completed belongs to the outer transaction: when the outer transaction rolls back, the nested scope's writes are rolled back too.
- **TX-04.3** An inner transaction started through an API that promises an independent transaction commits only its own writes. The outer scope's writes, whether already sent or still pending in the framework, are committed only by the outer transaction.

In every TX-04 case, the outer scope writes `outer` through the framework's ordinary write API. The framework decides when that write is sent: a framework with a unit of work may keep it pending.

| Case | Steps |
| --- | --- |
| `TX-04.nested-failure-contained` (none) | A nested scope writes `inner` and fails. The outer scope handles the failure and commits. |
| `TX-04.nested-released-outer-rollback` (none) | A nested scope writes `inner` and completes. The outer scope then fails. |
| `TX-04.independent-inner` (none) | An inner transaction, through an API that promises independence (for example `REQUIRES_NEW`), writes `inner` and commits. The outer scope then fails. Pool of two connections. |

## Planned, not in 0.1

- **TX-01B through a network-level fault.** The PostgreSQL protocol proxy described in `docs/methodology.md`.
- **The explicit (manual) transaction forms** of each framework, for example `trx.commit()` and `queryRunner.commitTransaction()`.
- **After-commit callbacks.**
- **Migration safety.** The reused experiments cover it (`docs/provenance.md`), but PPCS 0.1 does not.
