# PPCS run 2026-10-21T23-50-08Z-87af6a

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `specifications`, sha256 `46420e946083…`
- **Runner:** PPCS 0.3.0, harness sha256 `ece507a7bb9f…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-21T23:50:08.507Z; duration 91 s
- **Counts:** PASS 59, FAIL 3

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures. Category E is the runner protocol proxy dropping a COMMIT reply before the client reads it (docs/methodology.md).

Columns of kind `control` are the suite's own positive and negative controls: the negative control is expected to FAIL where its manifest says so, which shows that the runner detects a known-bad implementation.

## Results

| Case | Fault | django (native) | django (persistent) | hibernate (native) | hibernate (pooled) | jdbc-control (correct) | jdbc-control (unsafe) | laravel (managed) | laravel (explicit) | laravel (persistent) | pdo-control (correct) | pdo-control (unsafe) | pdo-control (persistent) | pg-control (correct) | pg-control (unsafe) | spring-jdbc (native) | spring-jdbc (pooled) | spring-tx (native) | spring-tx (declarative) | spring-tx (pooled) | spring-tx (declarative-pooled) | sqlalchemy (native) | sqlalchemy-core (native) | tortoise (native) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.django.native.json) | [PASS](cases/CTL-01.commit.django.persistent.json) | [PASS](cases/CTL-01.commit.hibernate.native.json) | [PASS](cases/CTL-01.commit.hibernate.pooled.json) | [PASS](cases/CTL-01.commit.jdbc-control.correct.json) | [PASS](cases/CTL-01.commit.jdbc-control.unsafe.json) | [PASS](cases/CTL-01.commit.laravel.managed.json) | [PASS](cases/CTL-01.commit.laravel.explicit.json) | [PASS](cases/CTL-01.commit.laravel.persistent.json) | [PASS](cases/CTL-01.commit.pdo-control.correct.json) | [PASS](cases/CTL-01.commit.pdo-control.unsafe.json) | [PASS](cases/CTL-01.commit.pdo-control.persistent.json) | [PASS](cases/CTL-01.commit.pg-control.correct.json) | [PASS](cases/CTL-01.commit.pg-control.unsafe.json) | [PASS](cases/CTL-01.commit.spring-jdbc.native.json) | [PASS](cases/CTL-01.commit.spring-jdbc.pooled.json) | [PASS](cases/CTL-01.commit.spring-tx.native.json) | [PASS](cases/CTL-01.commit.spring-tx.declarative.json) | [PASS](cases/CTL-01.commit.spring-tx.pooled.json) | [PASS](cases/CTL-01.commit.spring-tx.declarative-pooled.json) | [PASS](cases/CTL-01.commit.sqlalchemy.native.json) | [PASS](cases/CTL-01.commit.sqlalchemy-core.native.json) | [PASS](cases/CTL-01.commit.tortoise.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.django.native.json) | [PASS](cases/CTL-01.rollback.django.persistent.json) | [PASS](cases/CTL-01.rollback.hibernate.native.json) | [PASS](cases/CTL-01.rollback.hibernate.pooled.json) | [PASS](cases/CTL-01.rollback.jdbc-control.correct.json) | [PASS](cases/CTL-01.rollback.jdbc-control.unsafe.json) | [PASS](cases/CTL-01.rollback.laravel.managed.json) | [PASS](cases/CTL-01.rollback.laravel.explicit.json) | [PASS](cases/CTL-01.rollback.laravel.persistent.json) | [PASS](cases/CTL-01.rollback.pdo-control.correct.json) | [PASS](cases/CTL-01.rollback.pdo-control.unsafe.json) | [PASS](cases/CTL-01.rollback.pdo-control.persistent.json) | [PASS](cases/CTL-01.rollback.pg-control.correct.json) | [PASS](cases/CTL-01.rollback.pg-control.unsafe.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.native.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.pooled.json) | [PASS](cases/CTL-01.rollback.spring-tx.native.json) | [PASS](cases/CTL-01.rollback.spring-tx.declarative.json) | [PASS](cases/CTL-01.rollback.spring-tx.pooled.json) | [PASS](cases/CTL-01.rollback.spring-tx.declarative-pooled.json) | [PASS](cases/CTL-01.rollback.sqlalchemy.native.json) | [PASS](cases/CTL-01.rollback.sqlalchemy-core.native.json) | [PASS](cases/CTL-01.rollback.tortoise.native.json) |
| `TX-01B.commit-reply-unseen` | E | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.django.native.json) | — | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.hibernate.native.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.jdbc-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.jdbc-control.unsafe.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.laravel.managed.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.laravel.explicit.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.pdo-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json) | — | [PASS](cases/TX-01B.commit-reply-unseen.pg-control.correct.json) | [FAIL](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.spring-jdbc.native.json) | — | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.spring-tx.native.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.spring-tx.declarative.json) | — | — | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.sqlalchemy.native.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.sqlalchemy-core.native.json) | [PASS (TX-01B.2 not exercised)](cases/TX-01B.commit-reply-unseen.tortoise.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- django (native): held
- hibernate (native): held
- jdbc-control (correct): held
- jdbc-control (unsafe): held
- laravel (managed): held
- laravel (explicit): held
- pdo-control (correct): held
- pdo-control (unsafe): held
- pg-control (correct): held
- pg-control (unsafe): held
- spring-jdbc (native): held
- spring-tx (native): held
- spring-tx (declarative): held
- sqlalchemy (native): held
- sqlalchemy-core (native): held
- tortoise (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `TX-01B.commit-reply-unseen`: held (pg-control (correct) expected PASS, got PASS, pg-control (unsafe) expected FAIL, got FAIL)

## Findings (FAIL)

### `TX-01B.commit-reply-unseen` on jdbc-control (unsafe)

1. **What the API reported:** rolled_back: Connection.commit() threw, which the unsafe policy reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 28952 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 28952). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe jdbc-control policy reports committed whenever Connection.commit() returns, whatever PgConnection.getTransactionState() was before the call. It reports rolled_back when Connection.commit() throws. It calls Connection.commit() after Connection.rollback(Savepoint) has thrown. When Connection.rollback() throws, it calls Connection.setAutoCommit(true) and keeps the connection. Java 21 Connection.setAutoCommit says: "If this method is called during a transaction and the auto-commit mode is changed, the transaction is committed." pgjdbc 42.7.14 PgConnection.setAutoCommit(true) calls commit() when auto-commit is off. It does not call Connection.setTransactionIsolation. A write made before a nested savepoint is executed inside that savepoint.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Form:** Connection.setAutoCommit(false), the work, then Connection.commit() or Connection.rollback(). Writes use PreparedStatement.
- **Conditions:** jdbc-control 0.1.0, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=jdbc-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.jdbc-control.unsafe.json](cases/TX-01B.commit-reply-unseen.jdbc-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pdo-control (unsafe)

1. **What the API reported:** rolled_back: PDO::commit() threw, which the unsafe policy reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 29144 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 29144). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. When PDO::commit() throws, the policy reports rolled_back. When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. There is no Connection.setAutoCommit. This is not the JDBC unsafe policy's setAutoCommit(true) call.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Form:** PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.
- **Conditions:** pdo_pgsql 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.3, php 8.5.6; mode `unsafe` (configured); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pdo-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pdo-control.unsafe.json)

### `TX-01B.commit-reply-unseen` on pg-control (unsafe)

1. **What the API reported:** rolled_back: COMMIT raised an error, which the unsafe control reports as a rollback.
2. **What PostgreSQL did:** transaction `tx` (its ID read inside it at `before-end`): xid 29217 committed at report time (`after-end`); markers visible to a separate connection after the adapter exited: `tx` yes (inserted by xid 29217). Session state (pg_stat_activity, supplementary): at `before-end` "idle in transaction".
3. **What the application could know:** None at the API level: the reply to COMMIT was not delivered. Only a later read can establish that the transaction committed.
4. **Contract:** TX-01B.2 violated: When COMMIT may have reached PostgreSQL and no reply arrived, the API does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. Framework contract: The unsafe control reports committed whenever COMMIT does not raise, whatever the command tag, and reports a rollback whenever COMMIT raises. It ignores failed savepoint rollbacks, and defers a write made before a nested scope into that scope's savepoint. It starts every transaction with a plain BEGIN, whatever isolation level is requested of it.

- **Fault:** category E. The runner's protocol proxy forwards COMMIT to PostgreSQL, then discards the reply through ReadyForQuery and closes the client socket. The client does not parse the reply. This is not the category D simulation, which closes the socket after node-postgres has already parsed the reply.
- **Conditions:** pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1; mode `unsafe` (control); settings `{"pool_max":1}`
- **Repetitions:** 3 of 3 FAILed
- **Reproduce:** `node harness/run.mjs --adapter=pg-control --mode=unsafe --case=TX-01B.commit-reply-unseen`
- **Evidence:** [cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json](cases/TX-01B.commit-reply-unseen.pg-control.unsafe.json)

## Qualified passes

- `TX-01B.commit-reply-unseen` on django (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on hibernate (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on laravel (managed): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on laravel (explicit): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on spring-jdbc (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on spring-tx (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on spring-tx (declarative): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on sqlalchemy (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on sqlalchemy-core (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised
- `TX-01B.commit-reply-unseen` on tortoise (native): **PASS (TX-01B.2 not exercised)**. TX-01B.2: the adapter observes no channel through which the framework could report a confirmed rollback here (a result, an error type, or a rollback hook or event), so the invariant was not exercised

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| django (native) | native | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `b7d8877f12b9…` |
| django (persistent) | configured | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `b7d8877f12b9…` |
| hibernate (native) | native | hibernate-orm 7.4.13.Final, hibernate-core 7.4.13.Final, jakarta.persistence-api 3.2.0, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `0f1e852efe8b…` |
| hibernate (pooled) | configured | hibernate-orm 7.4.13.Final, hibernate-core 7.4.13.Final, jakarta.persistence-api 3.2.0, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `0f1e852efe8b…` |
| jdbc-control (correct) | native | jdbc-control 0.1.0, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `626a9461c450…` |
| jdbc-control (unsafe) | configured | jdbc-control 0.1.0, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `626a9461c450…` |
| laravel (managed) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.6, php 8.5.6 | `a5aefae3548b…` |
| laravel (explicit) | native | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.6, php 8.5.6 | `a5aefae3548b…` |
| laravel (persistent) | configured | illuminate/database v13.38.0, illuminate/database v13.38.0, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), pdo_pgsql 8.5.6, php 8.5.6 | `a5aefae3548b…` |
| pdo-control (correct) | native | pdo_pgsql 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.3, php 8.5.6 | `201671b27ffb…` |
| pdo-control (unsafe) | configured | pdo_pgsql 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.3, php 8.5.6 | `201671b27ffb…` |
| pdo-control (persistent) | configured | pdo_pgsql 8.5.6, pdo_pgsql 8.5.6, libpq 18.3, postgresql 18.6 (Debian 18.6-1.pgdg13+2), libpq 18.3, php 8.5.6 | `201671b27ffb…` |
| pg-control (correct) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| pg-control (unsafe) | control | pg-control 0.1.0, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `7afb3b256f25…` |
| spring-jdbc (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `18715f69cd1d…` |
| spring-jdbc (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `18715f69cd1d…` |
| spring-tx (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `e68c59126086…` |
| spring-tx (declarative) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 21.0.12.1 | `e68c59126086…` |
| spring-tx (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `e68c59126086…` |
| spring-tx (declarative-pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 21.0.12.1 | `e68c59126086…` |
| sqlalchemy (native) | native | sqlalchemy 2.1.5, psycopg 3.3.6, python 3.13.11 | `0b9ee3acbd1d…` |
| sqlalchemy-core (native) | native | sqlalchemy 2.1.5, psycopg 3.3.6, python 3.13.11 | `f2d7472150af…` |
| tortoise (native) | native | tortoise-orm 1.1.9, pypika-tortoise 0.6.5, aiosqlite 0.22.1, iso8601 2.1.0, asyncpg 0.32.0, python 3.13.11 | `04d4a5bc38e1…` |

