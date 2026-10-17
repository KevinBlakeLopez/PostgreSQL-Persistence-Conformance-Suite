# Methodology

PPCS asks one kind of question: when a persistence framework reports what happened to a transaction, does the report match what PostgreSQL did? Every case keeps four things apart:

1. **What the framework's API reported:** the adapter's observation of the call (it returned, or it raised), mapped to `committed`, `rolled_back` or `failed` by the framework's own contract.
2. **What PostgreSQL did:** read by the runner, through its own connections, at report time (as soon as the API returned), and again after the adapter has exited.
3. **What the application could have known at the time:** stated by each case. For example, a `ROLLBACK` command tag in the reply to `COMMIT` reaches the client; a reply that never arrived does not.
4. **Whether a stated invariant was violated:** decided by the runner's classification rules, never by the adapter.

Every PASS and FAIL must rest on evidence the runner collected itself. Where that evidence is missing, the result is INCONCLUSIVE, not a guess.

## Independent observation

An adapter runs inside the framework under test, so its reports are claims. The runner checks them against server-side facts:

- **Transaction identity and binding.** At a capture checkpoint, the adapter reads `pg_current_xact_id()` and `pg_backend_pid()` through the transaction's own connection, using the framework's raw-query API. The runner then confirms, in `pg_stat_activity`, that this backend is inside a transaction whose `backend_xid` is the reported ID. An ID read outside the transaction (in autocommit, `pg_current_xact_id()` returns an unrelated, committed ID) fails this check, and the case is INCONCLUSIVE.
- **Transaction fate, at two moments.** At every checkpoint, the runner calls `pg_xact_status()` for every transaction captured so far, on its own connection. The checkpoint `after-end`, which every adapter sends as soon as the framework's API has returned, gives the fate *at report time*. After the adapter has exited and its sessions have closed, the runner reads the fate again.
  - When the two differ, the fate was decided after the API returned: by later work in the case, or at teardown, when closing the framework ended a transaction that was still open. The report says which. It never presents a teardown outcome as what the reported operation did.
- **Write evidence.** Other sessions cannot see uncommitted rows, but they can see locks. At each checkpoint, the runner reads the backend's locks in `pg_locks`:
  - a `RowExclusiveLock` on `item` shows that a write to the marker table reached PostgreSQL in that transaction;
  - a second `transactionid` lock shows a write inside a savepoint (the savepoint's subtransaction ID).
  Each case declares, in `marker_writes`, the checkpoint at which each marker's write must have been sent, and at which level. A missing marker counts as a lost write only if its write was confirmed this way. Otherwise the case is INCONCLUSIVE. A write the framework may defer, such as a pending write in a unit of work, is declared `possibly-pending` and is not required.
- **Marker visibility and attribution.** Each case writes markers: rows with unique, per-run values. After the adapter has exited, a new READ COMMITTED connection reads which markers are visible, and each visible row's `xmin`, the ID of the transaction that inserted it.
  - A visible marker whose write was confirmed at a checkpoint must have been inserted by its declared transaction: by the top-level ID, or, for a savepoint write, by a subtransaction seen in its locks. Otherwise the observation is about some other transaction, and the case is INCONCLUSIVE.
  - A `possibly-pending` write is not attributed, because where it lands is what TX-04 observes. It can also land in a subtransaction created after the last checkpoint. For example, MikroORM flushed a pending outer write inside a savepoint that `ROLLBACK TO` had kept established.
  - The marker table starts empty. Any visible row that is not one of the case's markers makes the case INCONCLUSIVE, so a write with the wrong value cannot pass as a lost write.
- **Session state (supplementary).** `pg_stat_activity` supplies preconditions, such as "the session is `idle in transaction (aborted)`", and the last statement a backend ran. It also identifies a backend across checkpoints (`backend_start`). It never identifies a transaction alone.
- **The run itself.** At every checkpoint, the case's database may hold no more adapter sessions than the case's `pool_max`. No adapter session may remain once the adapter has exited. A fingerprint of the fixture's tables and constraints, taken before and after, must not change. Any of these failing makes the case INCONCLUSIVE.

**Consistency.** One combination of observations is impossible: a visible row whose inserting transaction (`xmin`) `pg_xact_status()` reports as aborted. If it occurs, the observations are wrong, and the case is INCONCLUSIVE.

A committed transaction whose confirmed write is missing is not an inconsistency. It is a lost write, and the invariants judge it. In TX-04, MikroORM's native nested call loses a pending outer write in exactly this way.

## Fault-injection categories

| Category | Meaning | Mechanisms in PPCS | Depends on driver internals |
| --- | --- | --- | --- |
| **A** | An error PostgreSQL generates in ordinary operation | A unique violation caught inside the transaction (TX-01A) | No |
| **B** | Server-side termination of the backend | `pg_terminate_backend(pid)`, run by the runner, only inside the case's own database | No |
| **C** | A client-side injected error | The adapter's driver layer fails a statement without sending it (`client-reject`), or rewrites it so that PostgreSQL rejects it (`rewrite`) | Yes: `pg.Client.prototype.query` |
| **D** | A client-side simulation in the driver | `reply-lost`: COMMIT is sent and completes, then the client closes its own connection and discards the reply | Yes: `pg.Client.prototype.query` |

These categories are not interchangeable. Categories C and D show what a framework does *if* such a failure happens. They do not show that the failure is reachable in ordinary production operation, or how often it occurs. Category B results generalize to a server-initiated termination, not to a silent network partition. Results record the category of every fault, and the summary prints it beside every case.

**Category B, step by step:**

1. At the checkpoint, the runner terminates the reported backend, but only after confirming that it belongs to the case's database.
2. It waits until the backend has gone.
3. It records both facts as the fault's observed effect.
4. Only then does it resume the adapter.

If the termination did not happen, the case's precondition fails and the case is INCONCLUSIVE.

**Category C:** the fault must have fired exactly once, and its effect must show on the server. The adapter's driver layer reports the checkpoint `after-fault` as the fault fires, before the framework sees the error, and the runner reads the fault's signature there:

| Fault | Signature at `after-fault` |
| --- | --- |
| `client-reject` on `ROLLBACK TO SAVEPOINT` | The session is `idle in transaction`, still holding the savepoint's subtransaction lock |
| `rewrite` of `ROLLBACK TO SAVEPOINT` | PostgreSQL answered `3B001`. The session is `idle in transaction (aborted)`, and the top-level transaction is still in progress |
| `client-reject` on `ROLLBACK` | The session is `idle in transaction`, and its `backend_xid` is the failed transaction's ID |
| `client-reject` on `ROLLBACK`, after a failed statement (`TX-03.statement-error-rollback-not-sent`) | The session is `idle in transaction (aborted)`, with no `backend_xid`, and `pg_xact_status()` already reports the failed transaction aborted |

The signature is read at the fault, not when the API returns. A framework that reacts correctly, by discarding the connection or by rolling the transaction back at once, would otherwise look like a fault that changed nothing.

**Category D:** the fault must have fired exactly once, and PostgreSQL's outcome must be the one the case produces (committed), both at report time and at the end. The simulation has one known artifact: node-postgres parses PostgreSQL's reply before the simulated loss, so the driver's own state is "idle". Results of `TX-01B.commit-reply-discarded` therefore say nothing about logic that reads driver state, or about pool recovery after a real loss.

**Deferred: a network-level unknown-outcome fault.** A TCP proxy that understands the PostgreSQL protocol could discard the reply to `COMMIT` without touching the client. It would make an unknown-outcome case available to adapters in any language. PPCS does not include it yet; its only case of that kind is the category D simulation in TX-01B.

## Commit outcome ambiguity

There are three possible situations after `COMMIT`:

- **Confirmed commit:** PostgreSQL answered `COMMIT` with the command tag `COMMIT`.
- **Confirmed rollback:** the client has evidence that the transaction did not commit, such as PostgreSQL answering `COMMIT` with `ROLLBACK` (TX-01A). The client also knows when COMMIT was never sent. After a server-side termination, node-postgres refuses to send it, so `TX-01B.conn-lost-before-commit` is a known outcome. A truthful report of a rollback passes it.
- **Unknown:** COMMIT may have reached PostgreSQL, and no reply reached the client (`TX-01B.commit-reply-discarded`). Only a later read can establish the outcome. A framework that reports success, or reports a rollback, is asserting what it cannot know. That holds even when the assertion turns out to match what PostgreSQL did.

PPCS never reads a later observation of committed state as proof that the client could have known the outcome. In `TX-01B.commit-reply-discarded`, PostgreSQL committed. A framework that reported success still fails TX-01B.1, because it had no reply to base the report on.

**TX-01B.2 needs a channel.** TX-01B.2 forbids a confirmed rollback after an unknown outcome. A framework can claim a rollback through its result, its error types, or its rollback hooks or events. Each adapter declares, in `rollback_claim_channels`, which of these it observes. A rollback reported through the result always violates TX-01B.2. Otherwise, TX-01B.2 holds only for an adapter that observes at least one channel. For the others it is recorded as *not exercised*, never as held. The current framework adapters observe no such channel. Their TX-01B.2 results are therefore "not exercised", and the summary says so.

## Classification

UNSUPPORTED and NOT_RUN come from the plan, before anything runs:

- **UNSUPPORTED:** the adapter's manifest declares the case unsupported, with a reason and a class. The class is `capability-absent` (the framework's supported API lacks what the case exercises) or `not-applicable-by-design` (the hazard the case targets cannot arise by the framework's design). Not-applicable cases are outside coverage, and the summary counts them separately. UNSUPPORTED is never a FAIL. An adapter cannot declare a case unsupported at run time: that is a protocol error.
- **NOT_RUN:** the case was not executed, because the adapter does not implement it, or the run's filters left it out.

For each executed case, the runner applies these checks in order (`harness/lib/classify.mjs`):

1. **INCONCLUSIVE:** the evidence is not trustworthy. The checks include:
   - the adapter timed out, broke the protocol (including a repeated checkpoint), or returned no result;
   - a required checkpoint, including `after-end`, is missing;
   - the outcome is unknown or `pending`, or a `failed` or `rolled_back` outcome came without the error the API raised;
   - a transaction ID is missing or not bound to its session, or a fate is unknown;
   - a marker is misattributed, the marker table holds rows that are not markers, or the observations are inconsistent;
   - too many sessions, leftover sessions, or a changed fixture.
2. **INCONCLUSIVE:** a precondition of the case did not hold, so its invariants do not apply. Preconditions come from the runner's own observations: write evidence, the fault's signature, session states and fates.
3. **INCONCLUSIVE:** the invariants evaluated are not exactly the ones the case declares, or none of them was exercised.
4. **FAIL:** an invariant was violated, with complete and consistent observations. The result names the invariant, the observations at report time and at the end, the conditions, and the framework contract that gives the API outcome its meaning.
5. **PASS:** every exercised invariant held.

**Qualified PASS results.** Two qualifiers change what a PASS means, and the summary prints them in the cell:

- **"not exercised":** an invariant the adapter cannot exercise, such as TX-01B.2 without a rollback-claim channel. It is never counted as held.
- **"mechanism not exercised":** the case's mechanism did not run. In TX-01A, the runner records whether COMMIT reached PostgreSQL: after the API returned, the same backend was idle, and its last statement was COMMIT. Lucid's `pre-commit-probe` passes TX-01A by failing *before* COMMIT, so its PASS is a valid mitigation, not evidence that Lucid reads the reply to COMMIT.

**A FAIL is a reproducible counterexample to a PPCS invariant, not a defect claim.** It is a counterexample under the recorded conditions: versions, configuration and fault category. Whether it is a defect depends on the framework's own contract, which each FAIL quotes, and on whether the fault is reachable in practice, which the fault category bounds.

## Gates

A classification counts only if the run around it was sound. After all cases have run, `harness/lib/suite.mjs` applies three gates:

- **Repetitions.** Every executed case runs three times (`--repeat`), each time on a fresh database. The repetitions must agree on the classification and its qualifiers. Otherwise the result is INCONCLUSIVE, and every repetition's record is kept.
- **Observation controls.** A scenario result counts only if CTL-01.commit and CTL-01.rollback PASSed for the same adapter and mode in the same run. The plan always runs them, even for a mode that lists only some cases.
- **Case controls.** A framework's result for a case counts only if the control adapter's expectations for that case held in the same run, on the same server. Those expectations are in `adapters/pg-control/adapter.json`, and the plan always runs `pg-control` beside the selected cases.

A result that fails a gate is INCONCLUSIVE. The classification it would have had is kept as `evaluation.ungated`, and the summary marks it "gated".

## Native, configured and hardened modes

An adapter runs each case in its `native` mode: the framework's defaults, through its ordinary APIs. It may also declare other modes, each a separate column in the report:

| Kind | Meaning | Example |
| --- | --- | --- |
| `recommended` | A configuration the framework's documentation recommends for the pattern. The mode must cite that documentation (`documentation`), or the manifest is refused | none |
| `configured` | A documented, non-default option | MikroORM `clear-forks`: `{ clear: true }` on nested calls |
| `hardened` | An external mitigation in application code | Lucid `pre-commit-probe`: `select 1` before the transaction ends |
| `control` | The suite's own controls | `pg-control` `correct` and `unsafe` |

A passing configured or hardened mode never replaces the native result. Both are reported, side by side.

**Forms.** Where a case leaves the framework a choice of native form, the result records the form the adapter used, and why (`execution.form`). Examples:

- MikroORM's TX-01A uses the form of reused experiment T4f, so the result does not cover other forms.
- MikroORM's TX-02 calls the nested scope with `{ clear: true }`, as the reused experiments did. The outer write is already flushed, and the option keeps the case on the savepoint rollback, not on the pending-write hazard that TX-04 targets.

## Controls and methodology tests

A suite that cannot detect a known-bad implementation is not credible, so PPCS tests its own method:

- **`pg-control`:** transactions written directly against node-postgres. Its manifest states the classification each mode must reach in each case.
  - The `correct` mode is the positive control: it should pass every case.
  - The `unsafe` mode is the negative control. It deliberately:
    - ignores the `ROLLBACK` tag of the reply to COMMIT;
    - reports any COMMIT error as a rollback;
    - commits after a failed savepoint rollback;
    - returns a connection whose ROLLBACK failed to its pool;
    - defers a write made before a nested scope into that scope's savepoint, so that a failing nested scope loses it.
  - In TX-03, the observer detects the unsafe reuse directly: the next unit of work reports the failed transaction's own ID, and `pg_xact_status()` shows that transaction committed.
- **The misbehaving fixture** (`harness/test/fixtures/`): an adapter that does one of the following. None of these may be classified PASS:
  - hangs, crashes, or skips a checkpoint;
  - reports an ID that does not exist, or an ID read outside its transaction;
  - reports its capture checkpoint twice;
  - commits without writing its marker;
  - makes its markers unreadable;
  - opens a connection beyond its pool;
  - sends malformed protocol messages;
  - lies about the outcome, always or on one repetition only.
- **`pnpm run test`:** the classification rules on hand-built evidence. This includes the harness counterexamples H1 to H9 of the independent methodology review, the gates, the repetitions and the server profile. No database.
- **`pnpm run test:methodology`:** the controls and the fixture through the real runner, against the real server. It also validates every file the runs write against the JSON schemas, and checks that none contains the instance password. These tests fail, rather than skip, when the server is not running.

## Reproducibility

- **Server:** PostgreSQL 18.6, pinned by image digest. It runs in a disposable container with a tmpfs data directory and a random password, bound to 127.0.0.1.
- **Server profile.** Before anything runs, the runner refuses a server whose settings differ from what the cases assume:
  - `synchronous_commit`, `fsync` and `track_activities` on;
  - READ COMMITTED, and not read-only, by default;
  - no `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout` or `transaction_timeout`;
  - no synchronous standbys.
- **Safety gate:** the runner refuses any server whose `cluster_name` is not that start's random token. It drops only the databases it created, and terminates sessions only inside them. Its own connections have connect and statement timeouts; the adapters' connections do not.
- **Dependencies:** each adapter is its own project, with its own lockfile, installed with `--frozen-lockfile`. The versions are those of the reused experiments (`docs/provenance.md`).
- **Isolation:** every case runs in a fresh database, in a fresh adapter process.
- **Results** record versions, settings, fault category, and three SHA-256 digests: of the specification catalog, of each adapter's source, and of the harness (`harness/lib` and `harness/run.mjs`). A change to the code that observes or classifies changes the harness digest. `--expect=<run.json>` compares a run's classifications with an earlier run's, for regression checks. It refuses, before running anything, an earlier run made with a different harness or catalog.

## Requirements and limitations

- **PostgreSQL 13 or later.** `pg_current_xact_id()`, `pg_xact_status()` and the `xid8` type were added in PostgreSQL 13. Older servers would need `txid_current()` and `txid_status()`, which PPCS does not implement.
- **`pg_current_xact_id()` assigns a transaction ID** if the transaction has none yet. That is harmless here: every capture happens after the transaction has written. Inside a savepoint, it returns the top-level ID.
- **It cannot run in an aborted transaction.** It fails with 25P02, so cases capture the ID before the failing statement.
- **Aborted sessions hide their ID.** On PostgreSQL 18.6, an `idle in transaction (aborted)` session shows a null `backend_xid` and `xact_start` in `pg_stat_activity`. The ID is available only if it was captured inside the transaction before the failure.
- **`pg_xact_status()` returns null** for a transaction ID too old to be in the commit log. The case is then INCONCLUSIVE. In a fresh disposable server this does not happen.
- **`pg_xact_status()` reports the top-level transaction.** The outcome of a savepoint is established by marker visibility.
- **`xmin` is 32 bits.** The runner compares it with the low 32 bits of the captured `xid8`. In a server that has wrapped around, two IDs can share those bits; a fresh disposable server has not wrapped.
- **Write evidence is per table, not per row.** A lock on `item` shows that a write to the marker table reached PostgreSQL in that transaction, not which row. The stray-row check excludes a committed write of the wrong value. A declared savepoint write is confirmed by a subtransaction lock. A framework that ran a nested scope as a separate transaction would make that case INCONCLUSIVE, not FAIL.
- **Category B has timing.** After the termination, the adapter waits `settle_ms` (100 ms), as the reused experiments did, so that the driver can observe the closed connection. A different wait can change which error the framework reports, but not whether the transaction committed. Three repetitions guard against a result that depends on the timing; they do not prove that none does.
- **TX-03's recovery bound** is `bound_ms` (5 s), measured by the adapter. A pool slot that never comes back fails it whatever the bound.
- **Single node, local container.** Results cover these PostgreSQL settings (recorded in each result) and this network path. Poolers such as PgBouncer, replicas and managed services are not covered.
- **Client-side faults depend on node-postgres.** Categories C and D patch `pg.Client.prototype.query` in the adapter's process, which also reports `after-fault`. Adapters in other languages must implement their own injections and that checkpoint, and say so.
