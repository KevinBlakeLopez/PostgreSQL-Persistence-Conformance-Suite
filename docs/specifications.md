# Specifications

The machine-readable catalog is `specifications/transactions.v1.json`; this page describes it. Every case names its invariants, its fault, its preconditions and what the application could know. Cases are written without framework terms. Each adapter implements them with its framework's own APIs.

**Fixture.** Each case runs in a fresh database that contains:

- `item (id serial, name text, qty int)`, which holds the markers and starts empty;
- `uniq (id serial, code text unique)`, holding one row, `'taken'`.

**Markers.** A marker is a row in `item` whose name is unique to the run, for example `tx-8f6a3c`. Each case declares, in `marker_writes`, which transaction writes each marker, at which level (top level or inside a savepoint), and the checkpoint by which the write must have reached PostgreSQL. A write the framework may defer is declared `possibly-pending`. The runner confirms each declared write in `pg_locks` at its checkpoint (`docs/methodology.md`).

**Checkpoints.** Each case declares its checkpoints. Every case also has an implicit last checkpoint, `after-end`, reported as soon as the framework's API has returned: the runner records the state at report time there. A case with a client-side fault (category C) also declares `after-fault`, which the adapter's driver layer reports as the fault takes effect, before the framework sees the error.

**Common settings.** Unless a case says otherwise, the pool holds one connection (`pool_max: 1`). Cases are versioned individually, and families and the catalog as a whole are versioned too. Every case is at version 1.1, which added `after-end` and `marker_writes`, except `TX-03.statement-error-rollback-not-sent`, which PPCS 0.2 added at 1.0, and the TX-05 cases, which PPCS 0.3 added at 1.0.

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

The cases differ in what the client can know:

- **`conn-lost-before-commit`** is a known outcome. The session ended before the framework tried to commit, and the driver refused to send `COMMIT`. A report of rollback is justified, so the case declares only TX-01B.1.
- **`commit-reply-discarded`** is unknown to the client. The driver has already parsed the reply. TX-01B.2 is exercised only for adapters that observe a channel through which the framework could claim a rollback (`rollback_claim_channels`); otherwise it is recorded as not exercised.
- **`commit-reply-unseen`** is the same unknown outcome, produced on the wire before the driver reads the reply. It does not replace `commit-reply-discarded`. TX-01B.2 is exercised on the same rule.

A framework that verified the outcome, for example with `pg_xact_status()`, and reported it would still fail TX-01B.2: PPCS does not yet evaluate such evidence.

| Case | Steps | PostgreSQL's outcome |
| --- | --- | --- |
| `TX-01B.conn-lost-before-commit` (B) | The transaction writes `tx`. At the checkpoint, the runner terminates its backend. The adapter waits 100 ms, then ends the transaction normally. | Rolled back; known to the client |
| `TX-01B.commit-reply-discarded` (D, client-side simulation) | The transaction writes `tx`. The adapter arms a fault in its driver: `COMMIT` is sent and completes, then the client closes its connection and discards the reply. The transaction ends normally. The driver has already parsed the reply, so the case says nothing about logic that reads the driver's state. | Committed; unknown to the client |
| `TX-01B.commit-reply-unseen` (E, network) | The transaction writes `tx` and ends normally. The runner's protocol proxy forwards `COMMIT`, then discards PostgreSQL's reply through `ReadyForQuery` and closes the client socket before the driver reads it. | Committed; unknown to the client |

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

1. Unit 1 writes `doomed`, then fails: with an application error, or, in `TX-03.statement-error-rollback-not-sent`, with an uncaught unique violation.
2. Its `ROLLBACK` fails, as each case below describes.
3. At `after-unit1`, when unit 1's API has returned, the runner records unit 1's fate at report time.
4. Unit 2, the next unit of work on the same pool of one connection, writes `next` and ends normally.

**How unsafe reuse is detected:** unit 2 reports its own `pg_current_xact_id()`. If that equals unit 1's, unit 2 ran inside the failed transaction, and `pg_xact_status()` then shows whether that transaction committed. The report says when unit 1's fate was decided by unit 2, not by unit 1's own API.

| Case | How the ROLLBACK fails | The fault's signature on the server |
| --- | --- | --- |
| `TX-03.rollback-not-sent` (C) | The driver fails the top-level `ROLLBACK` without sending it, so the connection keeps its open transaction. | At `after-fault`: `idle in transaction`, with `backend_xid` equal to unit 1's ID |
| `TX-03.statement-error-rollback-not-sent` (C) | Unit 1's insert of `'taken'` into `uniq` fails with `23505`, which aborts its transaction. The driver then fails the top-level `ROLLBACK` without sending it, so the connection stays in its aborted transaction block. | At `after-fault`: `idle in transaction (aborted)`, with no `backend_xid`, and `pg_xact_status()` already reporting unit 1 aborted |
| `TX-03.conn-lost-in-transaction` (B) | The runner terminates unit 1's backend before the `ROLLBACK`. | The backend has gone |

**An open block or an aborted one.** The two client-side cases leave different states behind (case signature `open-block` or `aborted-block`).

- **An open transaction.** The next unit of work on that connection *joins* it without an error: its `BEGIN` only draws a warning, and its `COMMIT` commits both units' writes.
- **An aborted block.** The transaction is already rolled back, and it holds no locks. But every statement on the connection fails with `25P02` until a `ROLLBACK`, so a unit of work handed the connection fails loudly.

A pool that validates connections with a query such as `SELECT 1` catches only the second: `SELECT 1` succeeds inside an open block.

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

## TX-05: Requested isolation level

Application code asks the framework's API to start a transaction at an isolation level that PostgreSQL supports. A framework that drops the request runs the transaction at the server's default, READ COMMITTED. Nothing tells the application: the transaction works, and the anomalies the requested level excludes, such as lost updates, can occur. A framework that refuses the request, in contrast, tells the application, which can decide what to do.

- **TX-05.1** On PostgreSQL, a transaction that the API started at a requested isolation level runs at that level or a stricter one, never at a weaker one.
- **TX-05.2** An API whose documentation accepts an isolation level that PostgreSQL supports does not reject a valid request for that level: it starts the transaction.

**The ordering is PostgreSQL's.** READ UNCOMMITTED and READ COMMITTED come first, and PostgreSQL implements them identically; then REPEATABLE READ; then SERIALIZABLE. Isolation levels do not form one ordering across database engines, so another engine would need its own, from its documented semantics.

**Every case requests SERIALIZABLE** (`settings.isolation_level`). It is the one level whose effect a separate connection can observe: a SERIALIZABLE transaction that has read a table holds SIRead locks on it.

**Two observations, which must agree:**

1. **PostgreSQL's report.** At `after-read`, the adapter reads `current_setting('transaction_isolation')` in the same statement as `pg_current_xact_id()` and `pg_backend_pid()`, through the transaction's own connection, and reports all three.
2. **The runner's observation.** At `after-read`, while the transaction is idle, the runner reads that backend's locks. Under SERIALIZABLE, a read of `item`, confirmed by an `AccessShareLock`, leaves an `SIReadLock` on `item` or on an index of `item`. Under a weaker level it leaves none. Locks are attributed by their target, never by their number.

The work is bound to the transaction as in every case: the captured ID is the backend's `backend_xid`, the backend holds the write's and the read's locks on `item`, and the visible marker's `xmin` is the captured ID.

| Observations | Result |
| --- | --- |
| PostgreSQL reports SERIALIZABLE, and the backend holds an `SIReadLock` on `item` | TX-05.1 holds |
| PostgreSQL reports a weaker level, and the backend holds no `SIReadLock` | TX-05.1 is violated: FAIL |
| The report and the locks disagree, or the `SIReadLock`s are only on other relations | INCONCLUSIVE (`observation-conflict`) |
| An observation, the binding or the confirmed read is missing | INCONCLUSIVE (`evidence-missing`) |

**A rejected request.** If the API raises instead of starting the transaction, TX-05.1 is not exercised, and the adapter starts a plain transaction through the same form, with no isolation level, reported at `baseline`. TX-05.2 is violated (FAIL) only if:

- the error carries no PostgreSQL SQLSTATE and no operating-system error code;
- the plain transaction was bound at `baseline`.

An error with such a code, or a failed plain transaction, is INCONCLUSIVE (`environment`). A missing or unbound `baseline` is INCONCLUSIVE (`cause-not-established`).

`backend_xmin`, the backend's snapshot horizon, is recorded as a diagnostic. It decides nothing.

**Shared steps:**

1. Start a transaction requesting SERIALIZABLE, through the API each case names. The server's default is READ COMMITTED.
2. Write the marker `tx`, and make sure the write was sent.
3. Read the marker back inside the transaction, with a query that reaches PostgreSQL, not a lookup in the framework's identity map.
4. Checkpoint `after-read`: report the transaction's ID, its backend PID and `current_setting('transaction_isolation')`, all read in one statement.
5. End the transaction normally.
6. Only if step 1 raised: start a plain transaction through the same form, report it at `baseline`, end it, and report `failed` with the first error. If the plain transaction fails too, report its error in `steps.baseline`.

| Case | The API |
| --- | --- |
| `TX-05.managed-serializable` (none) | The managed transaction API: the framework runs a callback inside the transaction, and commits when it returns |
| `TX-05.explicit-serializable` (none) | The explicit transaction API: a call returns a transaction handle, and the application commits it with an explicit call |

**UNSUPPORTED.** An adapter declares a case UNSUPPORTED (`capability-absent`) in its manifest, citing the framework's documentation, when the framework has no such API form, or documents that it does not support the requested level. That is not a failure.

The negative control's `unsafe` mode sends a plain `BEGIN`, ignoring the requested level, and reports the level PostgreSQL applied. Both cases must FAIL for it.

**What the application could know:** a successful start says nothing about the level PostgreSQL applied. Only `current_setting('transaction_isolation')`, read inside the transaction, does. A rejected request reaches the application as an error.

## MG-02: Concurrent runner coordination

Several processes apply one migration to one database. Each process is a runner, named A, B or C, and sets `application_name` to `ppcs-A`, `ppcs-B` or `ppcs-C`. The migration inserts one marker row per execution. The count of that marker is the number of times the migration committed. History is the framework's own record that the migration was applied; the adapter names the table, and the runner reads it.

The runner holds an advisory lock on its own session. The migration waits on that lock after inserting its marker, so a runner that is executing the migration is visible to another connection. The harness's own session is excluded from the case's sessions only when its backend PID is one of the runner's connections and its name is `ppcs-observer`. `settings.pool_max` is the ceiling for each role.

- **MG-02.1** After every runner has finished, the migration's marker count is 1 and history holds one entry for it.
- **MG-02.2** A runner that did not apply the migration either waited and then found it applied, or reported failure (non-zero exit status).
- **MG-02.4** If any single session of runner A ends while A is inside the migration, either A's execution of it does not commit, or no other runner executes it before A finishes: its marker count is 1. Judged only when the session actually ended; otherwise the case is INCONCLUSIVE.
- **MG-02.5** No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation.

| Case | What it does |
| --- | --- |
| `MG-02.held` (none) | A is inside the migration, held at the gate. B starts. Then C, after both have finished. |
| `MG-02.first-deployment` (none) | Neither the framework's history table nor `ppcs_history` exists. The runner creates a table with the adapter's history-table name in its own transaction and holds it uncommitted, so both A and B find no history storage. Each waits on the creation or on the framework's coordination, or is refused by that coordination and reports failure. The runner then rolls back, and the creations of the runners that were waiting collide. A second runner that starts after the table exists is `MG-02.held`. Case version 1.1; version 1.0 started both runners at once and depended on their timing. |
| `MG-02.session-loss` (B) | While A is inside the migration, one of A's sessions, chosen by `application_name`, is terminated. Then B, then C. |
| `MG-02.idle-session-timeout` (none) | A's connections set `idle_session_timeout = 1s`. A session busy inside the migration's transaction is not idle, so the setting does not end it. |

On Lucid 22.4.2, `MG-02.held`, `MG-02.first-deployment` and `MG-02.session-loss` pass. `MG-02.idle-session-timeout` is inconclusive on MG-02.4: the session inside the migration is not idle, so the timeout does not end it, and the marker count stays 1.

## MG-03: Rollback and history consistency

One runner applies a migration, reverts it, and the runner reads the marker count and the history count after the revert returns, before any later apply.

- **MG-03.1** If a revert reports a migration as reverted, its history entry is absent and its marker is absent.
- **MG-03.2** If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent.
- **MG-03.3** If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains.

| Case | What it does |
| --- | --- |
| `MG-03.valid-reversal` (none) | The reversal deletes the marker. The runner then applies the migration again. |
| `MG-03.no-reversal` (none) | The migration provides no reversal. |
| `MG-03.failing-reversal` (none) | The reversal deletes the marker and then raises. The migration is transactional. |

On Lucid 22.4.2, `MG-03.valid-reversal` and `MG-03.failing-reversal` pass. `MG-03.no-reversal` fails: the revert reports the migration reverted, the history entry is gone, and the marker remains.

## Planned, not yet included

- **The explicit (manual) transaction forms** of each framework, for example `trx.commit()` and `queryRunner.commitTransaction()`, in the families other than TX-05, which covers them.
- **After-commit callbacks.**
- **The other migration families.** MG-01, MG-04, MG-05 and MG-06 are specified in the migration research and are not in this catalog yet.
