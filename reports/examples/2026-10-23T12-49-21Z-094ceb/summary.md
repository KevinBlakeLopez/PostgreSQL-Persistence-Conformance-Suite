# PPCS run 2026-10-23T12-49-21Z-094ceb

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `46420e946083…`
- **Runner:** PPCS 0.3.0, harness sha256 `ece507a7bb9f…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-23T12:49:21.392Z; duration 25 s
- **Counts:** PASS 21, FAIL 2

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | efcore (native) | efcore (execute-sql) | efcore (pooled) | npgsql-control (correct) | npgsql-control (unsafe) | npgsql-control (pooled) | npgsql-control (pooled-no-reset) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.efcore.native.json) | [PASS](cases/CTL-01.commit.efcore.execute-sql.json) | [PASS](cases/CTL-01.commit.efcore.pooled.json) | [PASS](cases/CTL-01.commit.npgsql-control.correct.json) | [PASS](cases/CTL-01.commit.npgsql-control.unsafe.json) | [PASS](cases/CTL-01.commit.npgsql-control.pooled.json) | [PASS](cases/CTL-01.commit.npgsql-control.pooled-no-reset.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.efcore.native.json) | [PASS](cases/CTL-01.rollback.efcore.execute-sql.json) | [PASS](cases/CTL-01.rollback.efcore.pooled.json) | [PASS](cases/CTL-01.rollback.npgsql-control.correct.json) | [PASS](cases/CTL-01.rollback.npgsql-control.unsafe.json) | [PASS](cases/CTL-01.rollback.npgsql-control.pooled.json) | [PASS](cases/CTL-01.rollback.npgsql-control.pooled-no-reset.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.efcore.native.json) | — | — | [PASS](cases/TX-01B.commit-reply-unseen.npgsql-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json) | — | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- efcore (native): held
- npgsql-control (correct): held
- npgsql-control (unsafe): held
- pg-control (correct): held
- pg-control (unsafe): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01B.commit-reply-unseen`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01B.commit-reply-unseen` on npgsql-control (unsafe)

1. **What the API reported:** rolled_back: CommitAsync threw, which the unsafe policy reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 39294 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 39294). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Form:** NpgsqlConnection.BeginTransactionAsync, parameterized commands, then CommitAsync or RollbackAsync. One connection is held until the case's after-end checkpoint, unless the policy disposed it.
- **Conditions:** npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=npgsql-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json](cases/TX-01B.commit-reply-unseen.npgsql-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 39366 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 39366). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

## Qualified passes

- `TX-01B.commit-reply-unseen` on efcore (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| efcore (native) | native | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `24118f79469e…` |
| efcore (execute-sql) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `24118f79469e…` |
| efcore (pooled) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `24118f79469e…` |
| npgsql-control (correct) | native | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `59cb491c7af1…` |
| npgsql-control (unsafe) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `59cb491c7af1…` |
| npgsql-control (pooled) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `59cb491c7af1…` |
| npgsql-control (pooled-no-reset) | configured | npgsql-control 0.1.0, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `59cb491c7af1…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |

