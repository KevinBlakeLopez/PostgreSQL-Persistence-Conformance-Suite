# Specifications

The machine-readable catalog is `specifications/transactions.v1.json`; this page describes it. Every case names its invariants, its fault, its preconditions and what the application could know. Cases are written without framework terms. Each adapter implements them with its framework's own APIs.

**Fixture.** Each case runs in a fresh database that contains:

- `item (id serial, name text, qty int)`, which holds the markers and starts empty;
- `uniq (id serial, code text unique)`, holding one row, `'taken'`.

**Markers.** A marker is a row in `item` whose name is unique to the run, for example `tx-8f6a3c`. Each case declares, in `marker_writes`, which transaction writes each marker, at which level (top level or inside a savepoint), and the checkpoint by which the write must have reached PostgreSQL. A write the framework may defer is declared `possibly-pending`. The runner confirms each declared write in `pg_locks` at its checkpoint (`docs/methodology.md`).

**Checkpoints.** Each case declares its checkpoints. Every case also has an implicit last checkpoint, `after-end`, reported as soon as the framework's API has returned: the runner records the state at report time there. A case with a client-side fault (category C) also declares `after-fault`, which the adapter's driver layer reports as the fault takes effect, before the framework sees the error.

**Common settings.** Unless a case says otherwise, the pool holds one connection (`pool_max: 1`). Cases are versioned individually, and families and the catalog as a whole are versioned too. Every case is at version 1.1, which added `after-end` and `marker_writes`.

The case ID is followed by the fault category (`docs/methodology.md`).

## CTL-01: Observation controls

Can the runner see, through its own connections, a transaction the framework committed, and the absence of one the framework rolled back? If not, the adapter's other results are not credible. Every adapter and mode runs both cases in every run, and its scenario results count only if both PASS.

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
2. It inserts the duplicate `'taken'` and catches the unique violation (23505). After catching the error, it sends nothing else.
3. It ends normally.

The runner confirms, server-side, that the session was `idle in transaction (aborted)`, and that `pg_xact_status()` already reported the transaction aborted, before the transaction ended. It also records whether the case's mechanism ran: whether, after the API returned, the backend was idle and its last statement was `COMMIT`. A PASS without that is "PASS (mechanism not exercised)". **What the application could know:** PostgreSQL's reply to `COMMIT` carries the command tag `ROLLBACK`, so the outcome reaches the client.

## TX-01B: Commit outcome after a connection or reply failure

The connection, or PostgreSQL's reply, is lost around `COMMIT`. Does the framework report only what it has evidence for?

- **TX-01B.1** When the connection or PostgreSQL's reply was lost around COMMIT, so that the client never received an acknowledgement of COMMIT, the API does not report a successful commit.
- **TX-01B.2** When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events.

The two cases differ in what the client can know:

- **`conn-lost-before-commit`** is a known outcome. The session ended before the framework tried to commit, and the driver refused to send `COMMIT`. A report of rollback is justified, so the case declares only TX-01B.1.
- **`commit-reply-discarded`** is unknown to the client. TX-01B.2 is exercised only for adapters that observe a channel through which the framework could claim a rollback (`rollback_claim_channels`); otherwise it is recorded as not exercised.

A framework that verified the outcome, for example with `pg_xact_status()`, and reported it would still fail TX-01B.2: PPCS 0.1 does not evaluate such evidence.

| Case | Steps | PostgreSQL's outcome |
| --- | --- | --- |
| `TX-01B.conn-lost-before-commit` (B) | The transaction writes `tx`. At the checkpoint, the runner terminates its backend. The adapter waits 100 ms, then ends the transaction normally. | Rolled back; known to the client |
| `TX-01B.commit-reply-discarded` (D, client-side simulation) | The transaction writes `tx`. The adapter arms a fault in its driver: `COMMIT` is sent and completes, then the client closes its connection and discards the reply. The transaction ends normally. The driver has already parsed the reply, so the case says nothing about logic that reads the driver's state. | Committed; unknown to the client |

## TX-02: Failed savepoint rollback

A nested scope fails, and its `ROLLBACK TO SAVEPOINT` fails too. Does the outer transaction silently continue under an incorrect nesting state? That would mean committing the failed scope's writes, reporting success for a transaction PostgreSQL did not commit, or leaving its transaction open after its API returned.

- **TX-02.1** If the API reports that the outer transaction committed, PostgreSQL committed it, with the outer scope's writes and none of the failed nested scope's writes.
- **TX-02.2** When the outer transaction's API has returned, the connection that ran it is no longer inside a transaction.

**Shared steps:**

1. The outer scope writes `outer`.
2. A nested scope, opened with the framework's savepoint API, writes `inner`. At `inner-after-write`, the runner sees the savepoint's subtransaction lock.
3. The nested scope raises an application error. The savepoint rollback then fails, as each case below describes.
4. The outer scope catches the error and ends normally.
5. At checkpoint `after-outer`, the runner records the transaction's fate at report time, and whether the connection is still inside a transaction.

| Case | How the savepoint rollback fails | The fault's signature on the server |
| --- | --- | --- |
| `TX-02.savepoint-rollback-not-sent` (C) | The driver fails `ROLLBACK TO SAVEPOINT` without sending it. | At `after-fault`: `idle in transaction`, still holding the savepoint's subtransaction lock |
| `TX-02.savepoint-rollback-rejected` (C) | The driver rewrites `ROLLBACK TO SAVEPOINT` to name a savepoint that does not exist, so PostgreSQL rejects it (3B001). That aborts the current subtransaction, the savepoint's, not the whole transaction. `ROLLBACK TO` the existing savepoint recovers it; a `COMMIT` without recovery is answered with `ROLLBACK`. The error is PostgreSQL's; the trigger is artificial. | The reply 3B001; at `after-fault`, `idle in transaction (aborted)` with the top-level transaction in progress |
| `TX-02.conn-lost-before-savepoint-rollback` (B) | Inside the nested scope, the runner terminates the backend; the rollback then fails on the closed connection. | The backend has gone |

## TX-03: Connection recovery and unsafe pool reuse

A transaction fails on a pooled connection, and its `ROLLBACK` fails too. Does the pool give that connection to unrelated work while it still holds the failed transaction? Does the pool recover its capacity?

- **TX-03.1** Unrelated work never runs inside, or commits, a transaction whose rollback failed: that transaction is never committed, and the next unit of work runs in a transaction of its own.
- **TX-03.2** After the failure, the next unit of work on the same pool completes within the bound (5 s) and commits.

**Shared steps:**

1. Unit 1 writes `doomed` and raises an application error.
2. Its `ROLLBACK` fails, as each case below describes.
3. At `after-unit1`, when unit 1's API has returned, the runner records unit 1's fate at report time.
4. Unit 2, the next unit of work on the same pool of one connection, writes `next` and ends normally.

**How unsafe reuse is detected:** unit 2 reports its own `pg_current_xact_id()`. If that equals unit 1's, unit 2 ran inside the failed transaction, and `pg_xact_status()` then shows whether that transaction committed. The report says when unit 1's fate was decided by unit 2, not by unit 1's own API.

| Case | How the ROLLBACK fails | The fault's signature on the server |
| --- | --- | --- |
| `TX-03.rollback-not-sent` (C) | The driver fails the top-level `ROLLBACK` without sending it, so the connection keeps its open transaction. | At `after-fault`: `idle in transaction`, with `backend_xid` equal to unit 1's ID |
| `TX-03.conn-lost-in-transaction` (B) | The runner terminates unit 1's backend before the `ROLLBACK`. | The backend has gone |

## TX-04: Nested transaction propagation

When application code nests transactional work through an API that promises a propagation behaviour, does the work land in the transaction boundary the API promises? Frameworks do not share propagation modes. An adapter whose framework does not expose a case's behaviour declares the case UNSUPPORTED in its manifest, which is not a failure. Where the hazard cannot arise by design, for example with no propagation modes and no deferred writes, the class is `not-applicable-by-design`, and the case is outside coverage.

- **TX-04.1** When a nested scope (a savepoint) fails, and the caller handles the failure and commits, PostgreSQL commits all of the caller's writes and none of the nested scope's writes.
- **TX-04.2** A nested scope (a savepoint) that completed belongs to the outer transaction: when the outer transaction rolls back, the nested scope's writes are rolled back too.
- **TX-04.3** An inner transaction started through an API that promises an independent transaction commits only its own writes. The outer scope's writes, whether already sent or still pending in the framework, are committed only by the outer transaction.

In every TX-04 case, the outer scope writes `outer` through the framework's ordinary write API. The framework decides when that write is sent: a framework with a unit of work may keep it pending. The nested scope's write is confirmed by its subtransaction lock at `inner-after-write`.

| Case | Steps |
| --- | --- |
| `TX-04.nested-failure-contained` (none) | A nested scope writes `inner` and fails. The outer scope handles the failure and commits. |
| `TX-04.nested-released-outer-rollback` (none) | A nested scope writes `inner` and completes. The outer scope then fails. |
| `TX-04.independent-inner` (none) | An inner transaction, through an API that promises independence (for example `REQUIRES_NEW`), writes `inner` and commits. The outer scope then fails. Pool of two connections. |

The negative control's `unsafe` mode defers the outer write into the nested scope's savepoint, so `TX-04.nested-failure-contained` must FAIL for it.

## Planned, not in 0.1

- **TX-01B through a network-level fault.** The PostgreSQL protocol proxy described in `docs/methodology.md`.
- **The aborted-leak variant of TX-03:** a statement error, then an unsent `ROLLBACK`, then the next unit of work.
- **The explicit (manual) transaction forms** of each framework, for example `trx.commit()` and `queryRunner.commitTransaction()`.
- **After-commit callbacks.**
- **Migration safety.** The reused experiments cover it (`docs/provenance.md`), but PPCS 0.1 does not.
