# PPCS run 2026-10-25T03-17-33Z-562776

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `2d44447a84ed…`
- **Runner:** PPCS 0.3.0, harness sha256 `ca9a464603c5…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-25T03:17:33.715Z; duration 133 s
- **Counts:** PASS 14, FAIL 9, INCONCLUSIVE 1

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | drizzle (native) | drizzle (client-error-listener) | pg-control (correct) | pg-control (unsafe) |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.drizzle.native.json) | [PASS](cases/CTL-01.commit.drizzle.client-error-listener.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.drizzle.native.json) | [PASS](cases/CTL-01.rollback.drizzle.client-error-listener.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) |
| `MG-02.held` | none | [FAIL](cases/MG-02.held.drizzle.native.json) | [FAIL](cases/MG-02.held.drizzle.client-error-listener.json) | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.drizzle.native.json) | [PASS](cases/MG-02.first-deployment.drizzle.client-error-listener.json) | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) |
| `MG-02.session-loss` | B (server-side termination) | [INCONCLUSIVE](cases/MG-02.session-loss.drizzle.native.json) | [FAIL](cases/MG-02.session-loss.drizzle.client-error-listener.json) | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) |
| `MG-02.idle-session-timeout` | none | [FAIL](cases/MG-02.idle-session-timeout.drizzle.native.json) | [FAIL](cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json) | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- drizzle (native): held
- drizzle (client-error-listener): held
- pg-control (correct): held
- pg-control (unsafe): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `MG-02.held`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.first-deployment`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.session-loss`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.idle-session-timeout`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `MG-02.held` on drizzle (native)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction. A DrizzleQueryError is recorded with its class, the SQLSTATE of its cause, and a message the adapter composes from the failed statement and the cause's message.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.drizzle.native.json](cases/MG-02.held.drizzle.native.json)

### `MG-02.held` on drizzle (client-error-listener)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction. A DrizzleQueryError is recorded with its class, the SQLSTATE of its cause, and a message the adapter composes from the failed statement and the cause's message.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `client-error-listener` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=client-error-listener --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.drizzle.client-error-listener.json](cases/MG-02.held.drizzle.client-error-listener.json)

### `MG-02.session-loss` on drizzle (client-error-listener)

1. **What the API reported:** failed: migrate() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction. A DrizzleQueryError is recorded with its class, the SQLSTATE of its cause, and a message the adapter composes from the failed statement and the cause's message.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `client-error-listener` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=client-error-listener --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.drizzle.client-error-listener.json](cases/MG-02.session-loss.drizzle.client-error-listener.json)

### `MG-02.idle-session-timeout` on drizzle (native)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction. A DrizzleQueryError is recorded with its class, the SQLSTATE of its cause, and a message the adapter composes from the failed statement and the cause's message.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.drizzle.native.json](cases/MG-02.idle-session-timeout.drizzle.native.json)

### `MG-02.idle-session-timeout` on drizzle (client-error-listener)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction. A DrizzleQueryError is recorded with its class, the SQLSTATE of its cause, and a message the adapter composes from the failed statement and the cause's message.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `client-error-listener` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=client-error-listener --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json](cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json)

### `MG-02.held` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.pg-control.unsafe.json](cases/MG-02.held.pg-control.unsafe.json)

### `MG-02.first-deployment` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see the other's uncommitted creation of the history table, so both conclude the database is new. Only one creation can commit, and the other fails with a unique violation. What the second runner does with that error decides the case. If it reports failure, or waits on the framework's own coordination, the migration runs once. If it treats the error as "the table already exists" and continues, it finds no history row and executes the migration while the first runner is inside it. A second runner that starts after the history table exists is MG-02.held. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized","hold":"history-table","hold_ms":10000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.pg-control.unsafe.json](cases/MG-02.first-deployment.pg-control.unsafe.json)

### `MG-02.session-loss` on pg-control (unsafe)

1. **What the API reported:** failed: the migration raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.pg-control.unsafe.json](cases/MG-02.session-loss.pg-control.unsafe.json)

### `MG-02.idle-session-timeout` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.pg-control.unsafe.json](cases/MG-02.idle-session-timeout.pg-control.unsafe.json)

## Inconclusive, unsupported and not run

- `MG-02.session-loss` on drizzle (native): **INCONCLUSIVE**. the adapter reported an error: no detail

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| drizzle (native) | native | drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8d4a81d9d5d3…` |
| drizzle (client-error-listener) | configured | drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8d4a81d9d5d3…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |

