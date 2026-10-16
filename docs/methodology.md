# Methodology

PPCS asks one kind of question: when a persistence framework reports what happened to a transaction, does the report match what PostgreSQL did? Every case keeps four things apart:

1. **What the framework's API reported:** the adapter's observation of the call (it returned, or it raised), mapped to `committed`, `rolled_back` or `failed` by the framework's own contract.
2. **What PostgreSQL did:** read by the runner, through its own connections, after the adapter has exited.
3. **What the application could have known at the time:** stated by each case. For example, a `ROLLBACK` command tag in the reply to `COMMIT` reaches the client; a reply that never arrived does not.
4. **Whether a stated invariant was violated:** decided by the runner's classification rules, never by the adapter.

## Independent observation

An adapter runs inside the framework under test, so its reports are claims. The runner checks them against server-side facts:

- **Transaction identity.** At each checkpoint, the adapter reads `pg_current_xact_id()` and `pg_backend_pid()` through the transaction's own connection, using the framework's raw-query API, and reports them. The ID comes from inside the transaction, not from inspecting sessions.
- **Transaction fate.** After the adapter has exited and its sessions have closed, the runner calls `pg_xact_status()` for every captured ID, on its own connection: `committed`, `aborted`, `in progress`, or unknown.
- **Marker visibility.** Each case writes markers: rows with unique, per-run values. A new READ COMMITTED connection reads which markers are visible, and each visible row's `xmin`, the ID of the transaction that inserted it. `xmin` attributes a committed write to the transaction that committed it. For example, it shows when an outer scope's write was committed by an inner transaction.
- **Session state (supplementary).** At checkpoints, the runner reads `pg_stat_activity` for the reported PID. It uses this for preconditions, such as "the session is `idle in transaction (aborted)`", and to cross-check the reported ID against `backend_xid`. It never identifies a transaction from `pg_stat_activity` alone.

**Consistency.** One combination of observations is impossible: a visible row whose inserting transaction (`xmin`) `pg_xact_status()` reports as aborted. If it occurs, the observations are wrong, and the case is INCONCLUSIVE.

A committed transaction whose marker is missing is not an inconsistency. It is a lost write, and the invariants judge it. In TX-04, MikroORM's native nested call loses a pending outer write in exactly this way.

## Fault-injection categories

| Category | Meaning | Mechanisms in PPCS 0.1 | Depends on driver internals |
| --- | --- | --- | --- |
| **A** | An error PostgreSQL generates in ordinary operation | A unique violation caught inside the transaction (TX-01A) | No |
| **B** | Connection or network termination | `pg_terminate_backend(pid)`, run by the runner, only inside the case's own database | No |
| **C** | A client-side injected error | The adapter's driver layer fails a statement without sending it (`client-reject`), or rewrites it so that PostgreSQL rejects it (`rewrite`) | Yes: `pg.Client.prototype.query` |
| **D** | Driver or ORM internal-state manipulation | `reply-lost`: COMMIT is sent and completes, then the client closes its own connection and discards the reply | Yes: `pg.Client.prototype.query` |

These categories are not interchangeable. Categories C and D show what a framework does *if* such a failure happens. They do not show that the failure is reachable in ordinary production operation, or how often it occurs. Results record the category of every fault, and every client-side mechanism says so in its description.

**Category B, step by step:**

1. At the checkpoint, the runner terminates the reported backend, but only after confirming that it belongs to the case's database.
2. It waits until the backend has gone.
3. It records both facts as the fault's observed effect.
4. Only then does it resume the adapter.

If the termination did not happen, the case's precondition fails and the case is INCONCLUSIVE.

**Category C and D:** the adapter reports how many times its fault fired. A fault that never fired makes the case INCONCLUSIVE.

**Deferred: a network-level unknown-outcome fault.** A TCP proxy that understands the PostgreSQL protocol could discard the reply to `COMMIT` without touching the client. It would make an unknown-outcome case available to adapters in any language. PPCS 0.1 does not include it; its only case of that kind is the category D simulation in TX-01B.

## Commit outcome ambiguity

There are three possible situations after `COMMIT`:

- **Confirmed commit:** PostgreSQL answered `COMMIT` with the command tag `COMMIT`.
- **Confirmed rollback:** the client has evidence that the transaction did not commit, such as PostgreSQL answering `COMMIT` with `ROLLBACK` (TX-01A).
- **Unknown:** no reply to `COMMIT` reached the client (TX-01B). Only a later read can establish the outcome. A framework that reports success, or reports a rollback, is asserting what it cannot know. That holds even when the assertion turns out to match what PostgreSQL did.

PPCS never reads a later observation of committed state as proof that the client could have known the outcome. In `TX-01B.commit-reply-discarded`, PostgreSQL committed. A framework that reported success still fails TX-01B.1, because it had no reply to base the report on.

## Classification

The runner applies these checks in order (`harness/lib/classify.mjs`):

1. **UNSUPPORTED:** the adapter states that its framework's supported API lacks the capability the case tests. This is never a FAIL.
2. **INCONCLUSIVE:** the evidence is not trustworthy. This covers a timeout, a protocol error, a missing result or required checkpoint, a transaction ID that was not captured, a fate PostgreSQL could not report, or the consistency violation described above.
3. **INCONCLUSIVE:** a precondition of the case did not hold, for example the transaction was not aborted, or the fault did not take effect. The invariants then do not apply.
4. **FAIL:** an invariant was violated, with complete and consistent observations. The result names the invariant, the observations, the conditions, and the framework contract that gives the API outcome its meaning.
5. **PASS:** every invariant held.

**NOT_RUN** means the case was not executed: the adapter does not implement it, or the run's filters left it out.

**A FAIL is a reproducible counterexample to a PPCS invariant, not a defect claim.** It is a counterexample under the recorded conditions: versions, configuration and fault category. Whether it is a defect depends on the framework's own contract, which each FAIL quotes, and on whether the fault is reachable in practice, which the fault category bounds.

## Native, configured and hardened modes

An adapter runs each case in its `native` mode: the framework's defaults, through its ordinary APIs. It may also declare other modes, each a separate column in the report:

| Kind | Meaning | Example in 0.1 |
| --- | --- | --- |
| `recommended` | A configuration the framework's documentation recommends | none |
| `configured` | A documented, non-default option | MikroORM `clear-forks`: `{ clear: true }` on nested calls |
| `hardened` | An external mitigation in application code | Lucid `pre-commit-probe`: `select 1` before the transaction ends |
| `control` | The suite's own controls | `pg-control` `correct` and `unsafe` |

A passing configured or hardened mode never replaces the native result. Both are reported, side by side.

## Controls and methodology tests

A suite that cannot detect a known-bad implementation is not credible, so PPCS tests its own method:

- **`pg-control`:** transactions written directly against node-postgres. Its `correct` mode is the positive control: it should pass every case. Its `unsafe` mode is the negative control. It deliberately ignores the `ROLLBACK` tag of the reply to COMMIT, reports any COMMIT error as a rollback, commits after a failed savepoint rollback, and returns a connection whose ROLLBACK failed to its pool. The runner must classify these as FAIL. In TX-03, the observer detects the unsafe reuse directly: the next unit of work reports the failed transaction's own ID, and `pg_xact_status()` shows that transaction committed.
- **The misbehaving fixture** (`harness/test/fixtures/`): an adapter that hangs, crashes, skips a checkpoint, reports an ID that does not exist, loses its write, makes its markers unreadable, sends malformed protocol messages, or lies about the outcome. None of these may be classified PASS.
- **`pnpm run test`:** the classification rules on hand-built evidence. No database.
- **`pnpm run test:methodology`:** the controls and the fixture through the real runner, against the real server. It also validates every file the runs write against the JSON schemas, and checks that none contains the instance password. These tests fail, rather than skip, when the server is not running.

## Reproducibility

- **Server:** PostgreSQL 18.6, pinned by image digest. It runs in a disposable container with a tmpfs data directory and a random password, bound to 127.0.0.1.
- **Safety gate:** the runner refuses any server whose `cluster_name` is not that start's random token. It drops only the databases it created, and terminates sessions only inside them.
- **Dependencies:** each adapter is its own project, with its own lockfile, installed with `--frozen-lockfile`. The versions are those of the reused experiments (`docs/provenance.md`).
- **Isolation:** every case runs in a fresh database, in a fresh adapter process.
- **Results** record versions, settings, fault category, a SHA-256 of the specification catalog, and a SHA-256 of each adapter's source. `--expect=<run.json>` compares a run's classifications with an earlier run's, for regression checks. A second full run on the same machine reproduced all 68 classifications.

## Requirements and limitations

- **PostgreSQL 13 or later.** `pg_current_xact_id()`, `pg_xact_status()` and the `xid8` type were added in PostgreSQL 13. Older servers would need `txid_current()` and `txid_status()`, which PPCS does not implement.
- **`pg_current_xact_id()` assigns a transaction ID** if the transaction has none yet. That is harmless here: every capture happens after the transaction has written.
- **It cannot run in an aborted transaction.** It fails with 25P02, so cases capture the ID before the failing statement.
- **Aborted sessions hide their ID.** On PostgreSQL 18.6, an `idle in transaction (aborted)` session shows a null `backend_xid` and `xact_start` in `pg_stat_activity`. The ID is available only if it was captured inside the transaction before the failure.
- **`pg_xact_status()` returns null** for a transaction ID too old to be in the commit log. The case is then INCONCLUSIVE. In a fresh disposable server this does not happen.
- **`pg_xact_status()` reports the top-level transaction.** The outcome of a savepoint is established by marker visibility.
- **`xmin` is 32 bits.** The runner compares it with the low 32 bits of the captured `xid8`. In a server that has wrapped around, two IDs can share those bits; a fresh disposable server has not wrapped.
- **Category B has timing.** After the termination, the adapter waits `settle_ms` (100 ms), as the reused experiments did, so that the driver can observe the closed connection. A different wait can change which error the framework reports, but not whether the transaction committed.
- **TX-03's recovery bound** is `bound_ms` (5 s), measured by the adapter. A pool slot that never comes back fails it whatever the bound.
- **Single node, local container.** Results cover these PostgreSQL settings (recorded in each result) and this network path. Poolers such as PgBouncer, replicas and managed services are not covered.
- **Client-side faults depend on node-postgres.** Categories C and D patch `pg.Client.prototype.query` in the adapter's process. Adapters in other languages must implement their own injections, and say so.
