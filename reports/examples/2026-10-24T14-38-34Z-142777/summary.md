# PPCS run 2026-10-24T14-38-34Z-142777

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `2d44447a84ed…`
- **Runner:** PPCS 0.3.0, harness sha256 `ca9a464603c5…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-24T14:38:34.317Z; duration 637 s
- **Counts:** PASS 94, FAIL 33, UNSUPPORTED 6, INCONCLUSIVE 4

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | activerecord (native) | django (native) | django (persistent) | drizzle (native) | drizzle (client-error-listener) | efcore (native) | efcore (execute-sql) | efcore (pooled) | laravel (managed) | laravel (explicit) | laravel (persistent) | lucid (native) | lucid (pre-commit-probe) | mikroorm (native) | mikroorm (clear-forks) | pg-control (correct) | pg-control (unsafe) | prisma (native) | ruby-pg-control (correct) | ruby-pg-control (unsafe) | typeorm (native) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.activerecord.native.json) | [PASS](cases/CTL-01.commit.django.native.json) | [PASS](cases/CTL-01.commit.django.persistent.json) | [PASS](cases/CTL-01.commit.drizzle.native.json) | [PASS](cases/CTL-01.commit.drizzle.client-error-listener.json) | [PASS](cases/CTL-01.commit.efcore.native.json) | [PASS](cases/CTL-01.commit.efcore.execute-sql.json) | [PASS](cases/CTL-01.commit.efcore.pooled.json) | [PASS](cases/CTL-01.commit.laravel.managed.json) | [PASS](cases/CTL-01.commit.laravel.explicit.json) | [PASS](cases/CTL-01.commit.laravel.persistent.json) | [PASS](cases/CTL-01.commit.lucid.native.json) | [PASS](cases/CTL-01.commit.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.commit.mikroorm.native.json) | [PASS](cases/CTL-01.commit.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.prisma.native.json) | [PASS](cases/CTL-01.commit.ruby-pg-control.correct.json) | [PASS](cases/CTL-01.commit.ruby-pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.typeorm.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.activerecord.native.json) | [PASS](cases/CTL-01.rollback.django.native.json) | [PASS](cases/CTL-01.rollback.django.persistent.json) | [PASS](cases/CTL-01.rollback.drizzle.native.json) | [PASS](cases/CTL-01.rollback.drizzle.client-error-listener.json) | [PASS](cases/CTL-01.rollback.efcore.native.json) | [PASS](cases/CTL-01.rollback.efcore.execute-sql.json) | [PASS](cases/CTL-01.rollback.efcore.pooled.json) | [PASS](cases/CTL-01.rollback.laravel.managed.json) | [PASS](cases/CTL-01.rollback.laravel.explicit.json) | [PASS](cases/CTL-01.rollback.laravel.persistent.json) | [PASS](cases/CTL-01.rollback.lucid.native.json) | [PASS](cases/CTL-01.rollback.lucid.pre-commit-probe.json) | [PASS](cases/CTL-01.rollback.mikroorm.native.json) | [PASS](cases/CTL-01.rollback.mikroorm.clear-forks.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.prisma.native.json) | [PASS](cases/CTL-01.rollback.ruby-pg-control.correct.json) | [PASS](cases/CTL-01.rollback.ruby-pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.typeorm.native.json) |
| `MG-02.held` | none | [PASS](cases/MG-02.held.activerecord.native.json) | [FAIL](cases/MG-02.held.django.native.json) | — | [FAIL](cases/MG-02.held.drizzle.native.json) | [FAIL](cases/MG-02.held.drizzle.client-error-listener.json) | [PASS](cases/MG-02.held.efcore.native.json) | — | — | [FAIL](cases/MG-02.held.laravel.managed.json) | — | — | [PASS](cases/MG-02.held.lucid.native.json) | — | [FAIL](cases/MG-02.held.mikroorm.native.json) | — | [PASS](cases/MG-02.held.pg-control.correct.json) | [FAIL](cases/MG-02.held.pg-control.unsafe.json) | [PASS](cases/MG-02.held.prisma.native.json) | [PASS](cases/MG-02.held.ruby-pg-control.correct.json) | [FAIL](cases/MG-02.held.ruby-pg-control.unsafe.json) | [FAIL](cases/MG-02.held.typeorm.native.json) |
| `MG-02.first-deployment` | none | [PASS](cases/MG-02.first-deployment.activerecord.native.json) | [PASS](cases/MG-02.first-deployment.django.native.json) | — | [PASS](cases/MG-02.first-deployment.drizzle.native.json) | [PASS](cases/MG-02.first-deployment.drizzle.client-error-listener.json) | [PASS](cases/MG-02.first-deployment.efcore.native.json) | — | — | [PASS](cases/MG-02.first-deployment.laravel.managed.json) | — | — | [PASS](cases/MG-02.first-deployment.lucid.native.json) | — | [PASS](cases/MG-02.first-deployment.mikroorm.native.json) | — | [PASS](cases/MG-02.first-deployment.pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.pg-control.unsafe.json) | [PASS](cases/MG-02.first-deployment.prisma.native.json) | [PASS](cases/MG-02.first-deployment.ruby-pg-control.correct.json) | [FAIL](cases/MG-02.first-deployment.ruby-pg-control.unsafe.json) | [PASS](cases/MG-02.first-deployment.typeorm.native.json) |
| `MG-02.session-loss` | B (server-side termination) | [PASS](cases/MG-02.session-loss.activerecord.native.json) | [FAIL](cases/MG-02.session-loss.django.native.json) | — | [INCONCLUSIVE](cases/MG-02.session-loss.drizzle.native.json) | [FAIL](cases/MG-02.session-loss.drizzle.client-error-listener.json) | [PASS](cases/MG-02.session-loss.efcore.native.json) | — | — | [FAIL](cases/MG-02.session-loss.laravel.managed.json) | — | — | [PASS](cases/MG-02.session-loss.lucid.native.json) | — | [FAIL](cases/MG-02.session-loss.mikroorm.native.json) | — | [PASS](cases/MG-02.session-loss.pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.pg-control.unsafe.json) | [PASS](cases/MG-02.session-loss.prisma.native.json) | [PASS](cases/MG-02.session-loss.ruby-pg-control.correct.json) | [FAIL](cases/MG-02.session-loss.ruby-pg-control.unsafe.json) | [FAIL](cases/MG-02.session-loss.typeorm.native.json) |
| `MG-02.idle-session-timeout` | none | [INCONCLUSIVE](cases/MG-02.idle-session-timeout.activerecord.native.json) | [FAIL](cases/MG-02.idle-session-timeout.django.native.json) | — | [FAIL](cases/MG-02.idle-session-timeout.drizzle.native.json) | [FAIL](cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json) | [PASS](cases/MG-02.idle-session-timeout.efcore.native.json) | — | — | [FAIL](cases/MG-02.idle-session-timeout.laravel.managed.json) | — | — | [INCONCLUSIVE](cases/MG-02.idle-session-timeout.lucid.native.json) | — | [FAIL](cases/MG-02.idle-session-timeout.mikroorm.native.json) | — | [PASS](cases/MG-02.idle-session-timeout.pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.pg-control.unsafe.json) | [INCONCLUSIVE](cases/MG-02.idle-session-timeout.prisma.native.json) | [PASS](cases/MG-02.idle-session-timeout.ruby-pg-control.correct.json) | [FAIL](cases/MG-02.idle-session-timeout.ruby-pg-control.unsafe.json) | [FAIL](cases/MG-02.idle-session-timeout.typeorm.native.json) |
| `MG-03.valid-reversal` | none | [PASS](cases/MG-03.valid-reversal.activerecord.native.json) | [PASS](cases/MG-03.valid-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.valid-reversal.drizzle.native.json) | — | [PASS](cases/MG-03.valid-reversal.efcore.native.json) | — | — | [PASS](cases/MG-03.valid-reversal.laravel.managed.json) | — | — | [PASS](cases/MG-03.valid-reversal.lucid.native.json) | — | [PASS](cases/MG-03.valid-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.valid-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.valid-reversal.prisma.native.json) | [PASS](cases/MG-03.valid-reversal.ruby-pg-control.correct.json) | [FAIL](cases/MG-03.valid-reversal.ruby-pg-control.unsafe.json) | [PASS](cases/MG-03.valid-reversal.typeorm.native.json) |
| `MG-03.no-reversal` | none | [PASS](cases/MG-03.no-reversal.activerecord.native.json) | [PASS](cases/MG-03.no-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.no-reversal.drizzle.native.json) | — | [PASS](cases/MG-03.no-reversal.efcore.native.json) | — | — | [FAIL](cases/MG-03.no-reversal.laravel.managed.json) | — | — | [FAIL](cases/MG-03.no-reversal.lucid.native.json) | — | [PASS](cases/MG-03.no-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.no-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.no-reversal.prisma.native.json) | [PASS](cases/MG-03.no-reversal.ruby-pg-control.correct.json) | [FAIL](cases/MG-03.no-reversal.ruby-pg-control.unsafe.json) | [PASS](cases/MG-03.no-reversal.typeorm.native.json) |
| `MG-03.failing-reversal` | none | [PASS](cases/MG-03.failing-reversal.activerecord.native.json) | [PASS](cases/MG-03.failing-reversal.django.native.json) | — | [UNSUPPORTED](cases/MG-03.failing-reversal.drizzle.native.json) | — | [PASS](cases/MG-03.failing-reversal.efcore.native.json) | — | — | [PASS](cases/MG-03.failing-reversal.laravel.managed.json) | — | — | [PASS](cases/MG-03.failing-reversal.lucid.native.json) | — | [PASS](cases/MG-03.failing-reversal.mikroorm.native.json) | — | [PASS](cases/MG-03.failing-reversal.pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.pg-control.unsafe.json) | [UNSUPPORTED](cases/MG-03.failing-reversal.prisma.native.json) | [PASS](cases/MG-03.failing-reversal.ruby-pg-control.correct.json) | [FAIL](cases/MG-03.failing-reversal.ruby-pg-control.unsafe.json) | [PASS](cases/MG-03.failing-reversal.typeorm.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- activerecord (native): held
- django (native): held
- drizzle (native): held
- drizzle (client-error-listener): held
- efcore (native): held
- laravel (managed): held
- lucid (native): held
- mikroorm (native): held
- pg-control (correct): held
- pg-control (unsafe): held
- prisma (native): held
- ruby-pg-control (correct): held
- ruby-pg-control (unsafe): held
- typeorm (native): held

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
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable is not reversible: unapply raises IrreversibleError and does not record the migration as unapplied.

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
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable is not reversible: unapply raises IrreversibleError and does not record the migration as unapplied.

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
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Django 6.1 MigrationExecutor.migrate applies or unapplies the plan. On PostgreSQL the migration runs inside schema_editor(atomic=True) (django/db/migrations/executor.py). record_applied runs in that transaction when the migration has no deferred SQL. record_unapplied runs after the backwards transaction commits. The executor takes no advisory lock. RunPython without a reverse callable is not reversible: unapply raises IrreversibleError and does not record the migration as unapplied.

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

### `MG-02.held` on drizzle (client-error-listener)

1. **What the API reported:** applied: migrate() inserted a history row.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: drizzle-orm PgDialect.migrate (pg-core/dialect.js) creates the history table, reads the latest created_at, then runs every pending migration's statements and the history insert inside one session.transaction. There is no advisory lock. The migrator has no reversal.

- **Fault:** none
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
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
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
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
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
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
- **Form:** migrate() from drizzle-orm/node-postgres/migrator, migrationsSchema public and migrationsTable drizzle_migrations, so the runner can count that identifier. The generated SQL inserts the marker and waits on pg_advisory_xact_lock inside the migrator transaction.
- **Conditions:** drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `client-error-listener` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=drizzle --mode=client-error-listener --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json](cases/MG-02.idle-session-timeout.drizzle.client-error-listener.json)

### `MG-02.held` on laravel (managed)

1. **What the API reported:** applied: Migrator::run() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.laravel.managed.json](cases/MG-02.held.laravel.managed.json)

### `MG-02.session-loss` on laravel (managed)

1. **What the API reported:** failed: Migrator::run() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.laravel.managed.json](cases/MG-02.session-loss.laravel.managed.json)

### `MG-02.idle-session-timeout` on laravel (managed)

1. **What the API reported:** applied: Migrator::run() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.laravel.managed.json](cases/MG-02.idle-session-timeout.laravel.managed.json)

### `MG-03.no-reversal` on laravel (managed)

1. **What the API reported:** reverted: Migrator::rollback() returned a migration.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.

- **Fault:** none
- **Form:** Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.
- **Conditions:** illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12; mode `managed` (native); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=laravel --mode=managed --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.laravel.managed.json](cases/MG-03.no-reversal.laravel.managed.json)

### `MG-03.no-reversal` on lucid (native)

1. **What the API reported:** reverted: MigrationRunner status completed for direction down.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT, COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: In @adonisjs/lucid 22.4.2, MigrationRunner.run() executes pending migrations (direction up) or reverts a batch (direction down). status is completed when files ran, skipped when none did, and error when a migration threw (build/src/migration/runner.js).

- **Fault:** none
- **Form:** MigrationRunner.run() on a standalone Database. The migration file is generated for the case.
- **Conditions:** @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=lucid --mode=native --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.lucid.native.json](cases/MG-03.no-reversal.lucid.native.json)

### `MG-02.held` on mikroorm (native)

1. **What the API reported:** applied: migrator.up() applied Migration20200101000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** none
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.mikroorm.native.json](cases/MG-02.held.mikroorm.native.json)

### `MG-02.session-loss` on mikroorm (native)

1. **What the API reported:** failed: migrator.up() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.mikroorm.native.json](cases/MG-02.session-loss.mikroorm.native.json)

### `MG-02.idle-session-timeout` on mikroorm (native)

1. **What the API reported:** applied: migrator.up() applied Migration20200101000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: MikroORM 7.2.5 Migrator.up() and Migrator.down() run pending migrations and revert the last one (AbstractMigrator). Migration.down() throws "This migration cannot be reverted" unless a migration overrides it. Each migration runs in a transaction by default (migrations.transactional and allOrNothing), and the history insert or delete is inside that transaction (MigrationRunner and MigrationStorage). There is no advisory lock.

- **Fault:** none
- **Form:** orm.migrator.up() and orm.migrator.down(), table mikro_orm_migrations, migrationsList of one in-memory Migration. snapshot and snapshotOnMigrate are false.
- **Conditions:** @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=mikroorm --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.mikroorm.native.json](cases/MG-02.idle-session-timeout.mikroorm.native.json)

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

### `MG-03.valid-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported revert says the migration's effects are gone. The next apply is what shows that history and the database agree: the migration runs again. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"valid"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.valid-reversal`
- **Evidence:** [cases/MG-03.valid-reversal.pg-control.unsafe.json](cases/MG-03.valid-reversal.pg-control.unsafe.json)

### `MG-03.no-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.pg-control.unsafe.json](cases/MG-03.no-reversal.pg-control.unsafe.json)

### `MG-03.failing-reversal` on pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported failure says the revert did not complete. For a transactional migration, the caller can treat the migration as still applied. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.3 violated: If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"partial-then-error"},"transactional":true}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=MG-03.failing-reversal`
- **Evidence:** [cases/MG-03.failing-reversal.pg-control.unsafe.json](cases/MG-03.failing-reversal.pg-control.unsafe.json)

### `MG-02.held` on ruby-pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.ruby-pg-control.unsafe.json](cases/MG-02.held.ruby-pg-control.unsafe.json)

### `MG-02.first-deployment` on ruby-pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** Neither runner can see the other's uncommitted creation of the history table, so both conclude the database is new. Only one creation can commit, and the other fails with a unique violation. What the second runner does with that error decides the case. If it reports failure, or waits on the framework's own coordination, the migration runs once. If it treats the error as "the table already exists" and continues, it finds no history row and executes the migration while the first runner is inside it. A second runner that starts after the history table exists is MG-02.held. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A","B"],"pool_max":10,"gate":"sql","bound_ms":3000,"database":"uninitialized","hold":"history-table","hold_ms":10000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-02.first-deployment`
- **Evidence:** [cases/MG-02.first-deployment.ruby-pg-control.unsafe.json](cases/MG-02.first-deployment.ruby-pg-control.unsafe.json)

### `MG-02.session-loss` on ruby-pg-control (unsafe)

1. **What the API reported:** failed: the migration raised.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.ruby-pg-control.unsafe.json](cases/MG-02.session-loss.ruby-pg-control.unsafe.json)

### `MG-02.idle-session-timeout` on ruby-pg-control (unsafe)

1. **What the API reported:** applied: the control committed the marker and a history entry.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.ruby-pg-control.unsafe.json](cases/MG-02.idle-session-timeout.ruby-pg-control.unsafe.json)

### `MG-03.valid-reversal` on ruby-pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported revert says the migration's effects are gone. The next apply is what shows that history and the database agree: the migration runs again. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"valid"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-03.valid-reversal`
- **Evidence:** [cases/MG-03.valid-reversal.ruby-pg-control.unsafe.json](cases/MG-03.valid-reversal.ruby-pg-control.unsafe.json)

### `MG-03.no-reversal` on ruby-pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The caller of revert learns only what the operation reports. If that report says the migration was reverted, the caller treats its effects as gone. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.1 violated: If a revert reports a migration as reverted, its history entry is absent and its marker is absent. MG-03.2 violated: If a migration provides no reversal, a revert does not report it as reverted while its marker remains: it refuses before changing history, or follows a documented irreversible-migration contract that keeps history and database consistent. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"none"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-03.no-reversal`
- **Evidence:** [cases/MG-03.no-reversal.ruby-pg-control.unsafe.json](cases/MG-03.no-reversal.ruby-pg-control.unsafe.json)

### `MG-03.failing-reversal` on ruby-pg-control (unsafe)

1. **What the API reported:** reverted: the unsafe control deleted the history entry and reported a revert.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A reported failure says the revert did not complete. For a transactional migration, the caller can treat the migration as still applied. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-03.3 violated: If a migration's reversal fails, the operation reports failure and the migration's history entry remains; for a transactional migration, its marker also remains. Framework contract: The unsafe control takes no coordination lock. It creates its history table outside the migration and, when a concurrent creation fails with a unique violation, carries on as if the table had existed. It reports a revert as reverted after deleting the history entry, and it does not delete the marker.

- **Fault:** none
- **Conditions:** ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7; mode `unsafe` (configured); settings `{"runners":["A"],"pool_max":10,"reversal":{"m1":"partial-then-error"},"transactional":true}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=ruby-pg-control --mode=unsafe --case=MG-03.failing-reversal`
- **Evidence:** [cases/MG-03.failing-reversal.ruby-pg-control.unsafe.json](cases/MG-03.failing-reversal.ruby-pg-control.unsafe.json)

### `MG-02.held` on typeorm (native)

1. **What the API reported:** applied: runMigrations() executed Ppcsm11700000000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** A runner that waits learns that another run is in progress. It does not learn, from a successful return alone, that its own execution was the one that committed. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** none
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.held`
- **Evidence:** [cases/MG-02.held.typeorm.native.json](cases/MG-02.held.typeorm.native.json)

### `MG-02.session-loss` on typeorm (native)

1. **What the API reported:** failed: runMigrations() threw.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** The runner whose session ended can see the connection error. Another runner cannot see, from the database alone, that the ended session was the one holding coordination.
4. **Contract:** MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** category B (server-side termination). pg_terminate_backend() of one session of runner A, chosen by application_name ppcs-A, without knowing which session coordinates.
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"enumerate":"sessions-of-A"}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.session-loss`
- **Evidence:** [cases/MG-02.session-loss.typeorm.native.json](cases/MG-02.session-loss.typeorm.native.json)

### `MG-02.idle-session-timeout` on typeorm (native)

1. **What the API reported:** applied: runMigrations() executed Ppcsm11700000000000.
2. **What PostgreSQL did:** markers visible to a separate connection after the adapter exited: `m1` yes (inserted by xid unknown).
3. **What the application could know:** idle_session_timeout ends a session that is idle outside a transaction. A session busy inside the migration's transaction is not idle, so the setting does not end that session. The adapter's driver trace (diagnostic) records the reply to COMMIT as the command tag COMMIT.
4. **Contract:** MG-02.1 violated: After every runner has finished, the migration's marker count is 1 and history holds one entry for it. MG-02.5 violated: No runner starts executing the migration while another runner's execution of it is still live (its session still inside the migration): two live sessions inside it at once is a violation. Framework contract: TypeORM 1.1.2 DataSource.runMigrations() executes pending migrations and undoLastMigration() reverts the last one (data-source/DataSource.js). MigrationExecutor defaults to transaction mode "all": one transaction wraps every pending migration, and the history insert is inside it (migration/MigrationExecutor.js). There is no advisory lock.

- **Fault:** none
- **Form:** DataSource.runMigrations() and DataSource.undoLastMigration(), migrationsTableName migrations. The migration object is built for the case. Its name ends in a 13-digit timestamp, which MigrationExecutor.getMigrations() requires.
- **Conditions:** typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `native` (native); settings `{"runners":["A","B","C"],"pool_max":10,"gate":"sql","bound_ms":3000,"connection_options":{"A":"-c idle_session_timeout=1000"}}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=typeorm --mode=native --case=MG-02.idle-session-timeout`
- **Evidence:** [cases/MG-02.idle-session-timeout.typeorm.native.json](cases/MG-02.idle-session-timeout.typeorm.native.json)

## Inconclusive, unsupported and not run

- `MG-02.idle-session-timeout` on activerecord (native): **INCONCLUSIVE**. an invariant could not be evaluated: MG-02.4 (no session of runner A ended, so the fault did not happen)
- `MG-02.session-loss` on drizzle (native): **INCONCLUSIVE**. the adapter reported an error: no detail
- `MG-03.valid-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-03.no-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-03.failing-reversal` on drizzle (native): **UNSUPPORTED**. drizzle-orm PgDialect.migrate (pg-core/dialect.js) runs pending up SQL and inserts a history row. The node-postgres migrator reads that up SQL from the journal. There is no down migration and no reversal call. This adapter does not add one.
- `MG-02.idle-session-timeout` on lucid (native): **INCONCLUSIVE**. an invariant could not be evaluated: MG-02.4 (no session of runner A ended, so the fault did not happen)
- `MG-02.idle-session-timeout` on prisma (native): **INCONCLUSIVE**. an invariant could not be evaluated: MG-02.4 (no session of runner A ended, so the fault did not happen)
- `MG-03.valid-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.
- `MG-03.no-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.
- `MG-03.failing-reversal` on prisma (native): **UNSUPPORTED**. Prisma Migrate 7.10.1 reads migration.sql and migration_lock.toml. migrate deploy applies that forward SQL and records _prisma_migrations. A migration directory has no down file, and deploy does not run a reversal. This adapter does not add one.

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| activerecord (native) | native | activerecord 8.1.4, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], activerecord 8.1.4, pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7 | `53f8737f66cd…` |
| django (native) | native | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `11e60e3e2f9a…` |
| django (persistent) | configured | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `11e60e3e2f9a…` |
| drizzle (native) | native | drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `515d761b9503…` |
| drizzle (client-error-listener) | configured | drizzle-orm 0.45.4, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `515d761b9503…` |
| efcore (native) | native | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| efcore (execute-sql) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| efcore (pooled) | configured | Microsoft.EntityFrameworkCore 10.0.13, Microsoft.EntityFrameworkCore 10.0.13, Npgsql.EntityFrameworkCore.PostgreSQL 10.0.3, Npgsql 10.0.3, runtime 10.0.13, Npgsql 10.0.3, dotnet 10.0.13 | `538bb4f950bf…` |
| laravel (managed) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| laravel (explicit) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| laravel (persistent) | configured | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.12, libpq 18.6, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.12, php 8.5.12 | `048157c18c0b…` |
| lucid (native) | native | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `fae3c8c56d97…` |
| lucid (pre-commit-probe) | hardened | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `fae3c8c56d97…` |
| mikroorm (native) | native | @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8805029c4e73…` |
| mikroorm (clear-forks) | configured | @mikro-orm/core 7.2.5, @mikro-orm/migrations 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `8805029c4e73…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `1e833df8af22…` |
| prisma (native) | native | @prisma/client 7.10.1, @prisma/adapter-pg 7.10.1, prisma 7.10.1, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `bad3f2a7258a…` |
| ruby-pg-control (correct) | native | ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7 | `d1e4e418d13f…` |
| ruby-pg-control (unsafe) | configured | ruby-pg-control 0.1.0, ruby ruby 4.0.7 (2026-09-15 revision 229531a6cf) +PRISM [arm64-darwin25], pg 1.7.0, libpq 180006, pg 1.7.0, ruby 4.0.7 | `d1e4e418d13f…` |
| typeorm (native) | native | typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `e5cec7da0662…` |

