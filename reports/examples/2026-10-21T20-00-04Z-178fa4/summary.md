# PPCS run 2026-10-21T20-00-04Z-178fa4

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `b504ba4a1b60…`
- **Runner:** PPCS 0.3.0, harness sha256 `af929302a2da…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-21T20:00:04.208Z; duration 213 s
- **Counts:** PASS 26, FAIL 13, UNSUPPORTED 6, INCONCLUSIVE 2

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | django (native) | django (persistent) | drizzle (native) | pg-control (correct) | pg-control (unsafe) | prisma (native) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.django.native.json) | [PASS](cases/CTL-01.commit.django.persistent.json) | [PASS](cases/CTL-01.commit.drizzle.native.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.prisma.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.django.native.json) | [PASS](cases/CTL-01.rollback.django.persistent.json) | [PASS](cases/CTL-01.rollback.drizzle.native.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.prisma.native.json) |
| `MG-02.held` | none | [FAIL](cases/MG-02.held.django.native.json) | — | [FAIL](cases/MG-02.held.drizzle.native.json) | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) | [PASS](cases/MG-02.held.prisma.native.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.django.native.json) | — | [INCONCLUSIVE (repetitions disagree)](cases/MG-02.first-deployment.drizzle.native.json) | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) | [PASS](cases/MG-02.first-deployment.prisma.native.json) |
| `MG-02.session-loss` | B (server-side termination) | [FAIL](cases/MG-02.session-loss.django.native.json) | — | [FAIL](cases/MG-02.session-loss.drizzle.native.json) | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) | [PASS](cases/MG-02.session-loss.prisma.native.json) |
| `MG-02.idle-session-timeout` | none | [FAIL](cases/MG-02.idle-session-timeout.django.native.json) | — | [FAIL](cases/MG-02.idle-session-timeout.drizzle.native.json) | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) | [INCONCLUSIVE](cases/MG-02.idle-session-timeout.prisma.native.json) |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.valid-reversal.drizzle.native.json) | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.valid-reversal.prisma.native.json) |
| `MG-03.no-reversal` | none | [PASS](cases/MG-03.no-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.no-reversal.drizzle.native.json) | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.no-reversal.prisma.native.json) |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.failing-reversal.drizzle.native.json) | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.failing-reversal.prisma.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- django (native): held
- drizzle (native): held
- pg-control (correct): held
- pg-control (unsafe): held
- prisma (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `MG-02.held`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.first-deployment`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.session-loss`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-02.idle-session-timeout`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.valid-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.no-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)
- `MG-03.failing-reversal`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `MG-02.held` on django (native)

1. **What the API reported:** applied: MigrationExecutor.migrate returned.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable raises NotImplementedError from database_backwards and does not record the migration as unapplied.

- **Fault:** none
- **Form:** MigrationExecutor.migrate on a generated ppcs_mg.0001_m1 RunPython migration. forwards inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock in that transaction.
- **Conditions:** django 6.1.2, psycopg 3.3.6, python 3.13.11; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=django --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.django.native.json](cases/MG-02.held.django.native.json)

### `MG-02.session-loss` on django (native)

1. **What the API reported:** failed: MigrationExecutor.migrate raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable raises NotImplementedError from database_backwards and does not record the migration as unapplied.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** MigrationExecutor.migrate on a generated ppcs_mg.0001_m1 RunPython migration. forwards inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock in that transaction.
- **Conditions:** django 6.1.2, psycopg 3.3.6, python 3.13.11; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=django --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.django.native.json](cases/MG-02.session-loss.django.native.json)

### `MG-02.idle-session-timeout` on django (native)

1. **What the API reported:** applied: MigrationExecutor.migrate returned.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable raises NotImplementedError from database_backwards and does not record the migration as unapplied.

- **Fault:** none
- **Form:** MigrationExecutor.migrate on a generated ppcs_mg.0001_m1 RunPython migration. forwards inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock in that transaction.
- **Conditions:** django 6.1.2, psycopg 3.3.6, python 3.13.11; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=django --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.django.native.json](cases/MG-02.idle-session-timeout.django.native.json)

### `MG-02.held` on drizzle (native)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.drizzle.native.json](cases/MG-02.held.drizzle.native.json)

### `MG-02.session-loss` on drizzle (native)

1. **What the API reported:** failed: migrate() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.drizzle.native.json](cases/MG-02.session-loss.drizzle.native.json)

### `MG-02.idle-session-timeout` on drizzle (native)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.drizzle.native.json](cases/MG-02.idle-session-timeout.drizzle.native.json)

### `MG-02.held` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.pg-control.unsafe.json](cases/MG-02.held.pg-control.unsafe.json)

### `MG-02.first-deployment` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see, before it starts, that the other is about to apply the same migration. The database starts with no history row that could tell it so. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.pg-control.unsafe.json](cases/MG-02.first-deployment.pg-control.unsafe.json)

### `MG-02.session-loss` on pg-control (unsafe)

1. **What the API reported:** failed: the migration raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.pg-control.unsafe.json](cases/MG-02.session-loss.pg-control.unsafe.json)

### `MG-02.idle-session-timeout` on pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.pg-control.unsafe.json](cases/MG-02.idle-session-timeout.pg-control.unsafe.json)

### `MG-03.valid-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported revert says the migration's effects are gone. The next apply is what shows that history and the database agree: the migration runs again. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"valid"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.valid-reversal`
- **Evidence:** [cases/MG-03.valid-reversal.pg-control.unsafe.json](cases/MG-03.valid-reversal.pg-control.unsafe.json)

### `MG-03.no-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.pg-control.unsafe.json](cases/MG-03.no-reversal.pg-control.unsafe.json)

### `MG-03.failing-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported failure says the revert did not complete. For a transactional migration, the caller can treat the migration as still applied. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.3 violated: If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains. Framework contract: The unsafe control takes no coordination lock. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"partial-then-error"},"transactional":true}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.failing-reversal`
- **Evidence:** [cases/MG-03.failing-reversal.pg-control.unsafe.json](cases/MG-03.failing-reversal.pg-control.unsafe.json)

## Inconclusive, unsupported and not run

- `MG-02.first-deployment` on drizzle (native): **INCONCLUSIVE (repetitions disagree)**. the repetitions disagree: #1 PASS; #2 FAIL; #3 PASS
- `MG-03.valid-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-03.no-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-03.failing-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-02.idle-session-timeout` on prisma (native): **INCONCLUSIVE**. an invariant could not be evaluated: MG-02.4 (no session of runner A ended, so the fault did not happen)
- `MG-03.valid-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.
- `MG-03.no-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.
- `MG-03.failing-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| django (native) | native | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `5fa432a9b38b…` |
| django (persistent) | configured | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `5fa432a9b38b…` |
| drizzle (native) | native | drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaa4742d2ab7…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `aaec0b36482f…` |
| prisma (native) | native | @prisma/client 7.10.1, @prisma/adapter-pg 7.10.1, prisma 7.10.1, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `f21780ff7832…` |

