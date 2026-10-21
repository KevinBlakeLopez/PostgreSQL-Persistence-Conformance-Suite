# PPCS run 2026-10-19T18-15-49Z-b2c174

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `research/production-reachability/catalog.json`, sha256 `405731e049f8…`
- **Runner:** PPCS 0.3.0, harness sha256 `af929302a2da…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-19T18:15:49.147Z; duration 108 s
- **Counts:** PASS 87, INCONCLUSIVE 3

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

## Results

| Case | Fault | knex (native) | kysely (native) | pg (check-tag) | pg (ignore-tag) | django (native) | lucid (native) | mikroorm (native) | spring-jdbc (native) | spring-jdbc (pooled) | spring-tx (native) | spring-tx (declarative) | spring-tx (pooled) | sqlalchemy (native) | sqlalchemy-core (native) | typeorm (native) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.knex.native.json) | [PASS](cases/CTL-01.commit.kysely.native.json) | [PASS](cases/CTL-01.commit.pg.check-tag.json) | [PASS](cases/CTL-01.commit.pg.ignore-tag.json) | [PASS](cases/CTL-01.commit.django.native.json) | [PASS](cases/CTL-01.commit.lucid.native.json) | [PASS](cases/CTL-01.commit.mikroorm.native.json) | [PASS](cases/CTL-01.commit.spring-jdbc.native.json) | [PASS](cases/CTL-01.commit.spring-jdbc.pooled.json) | [PASS](cases/CTL-01.commit.spring-tx.native.json) | [PASS](cases/CTL-01.commit.spring-tx.declarative.json) | [PASS](cases/CTL-01.commit.spring-tx.pooled.json) | [PASS](cases/CTL-01.commit.sqlalchemy.native.json) | [PASS](cases/CTL-01.commit.sqlalchemy-core.native.json) | [PASS](cases/CTL-01.commit.typeorm.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.knex.native.json) | [PASS](cases/CTL-01.rollback.kysely.native.json) | [PASS](cases/CTL-01.rollback.pg.check-tag.json) | [PASS](cases/CTL-01.rollback.pg.ignore-tag.json) | [PASS](cases/CTL-01.rollback.django.native.json) | [PASS](cases/CTL-01.rollback.lucid.native.json) | [PASS](cases/CTL-01.rollback.mikroorm.native.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.native.json) | [PASS](cases/CTL-01.rollback.spring-jdbc.pooled.json) | [PASS](cases/CTL-01.rollback.spring-tx.native.json) | [PASS](cases/CTL-01.rollback.spring-tx.declarative.json) | [PASS](cases/CTL-01.rollback.spring-tx.pooled.json) | [PASS](cases/CTL-01.rollback.sqlalchemy.native.json) | [PASS](cases/CTL-01.rollback.sqlalchemy-core.native.json) | [PASS](cases/CTL-01.rollback.typeorm.native.json) |
| `PR-01.managed-catch-commit` | A (PostgreSQL error) | [PASS](cases/PR-01.managed-catch-commit.knex.native.json) | [PASS](cases/PR-01.managed-catch-commit.kysely.native.json) | [PASS](cases/PR-01.managed-catch-commit.pg.check-tag.json) | [PASS](cases/PR-01.managed-catch-commit.pg.ignore-tag.json) | [PASS (mechanism not exercised)](cases/PR-01.managed-catch-commit.django.native.json) | [PASS](cases/PR-01.managed-catch-commit.lucid.native.json) | [PASS](cases/PR-01.managed-catch-commit.mikroorm.native.json) | [PASS](cases/PR-01.managed-catch-commit.spring-jdbc.native.json) | [PASS](cases/PR-01.managed-catch-commit.spring-jdbc.pooled.json) | [PASS](cases/PR-01.managed-catch-commit.spring-tx.native.json) | [PASS](cases/PR-01.managed-catch-commit.spring-tx.declarative.json) | [PASS](cases/PR-01.managed-catch-commit.spring-tx.pooled.json) | [PASS (mechanism not exercised)](cases/PR-01.managed-catch-commit.sqlalchemy.native.json) | [PASS](cases/PR-01.managed-catch-commit.sqlalchemy-core.native.json) | [PASS](cases/PR-01.managed-catch-commit.typeorm.native.json) |
| `PR-01.explicit-catch-commit` | A (PostgreSQL error) | [PASS](cases/PR-01.explicit-catch-commit.knex.native.json) | [PASS](cases/PR-01.explicit-catch-commit.kysely.native.json) | [PASS](cases/PR-01.explicit-catch-commit.pg.check-tag.json) | [PASS](cases/PR-01.explicit-catch-commit.pg.ignore-tag.json) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.django.native.json) | [PASS](cases/PR-01.explicit-catch-commit.lucid.native.json) | [PASS](cases/PR-01.explicit-catch-commit.mikroorm.native.json) | [PASS](cases/PR-01.explicit-catch-commit.spring-jdbc.native.json) | [PASS](cases/PR-01.explicit-catch-commit.spring-jdbc.pooled.json) | [PASS](cases/PR-01.explicit-catch-commit.spring-tx.native.json) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.spring-tx.declarative.json) | [PASS](cases/PR-01.explicit-catch-commit.spring-tx.pooled.json) | [PASS (mechanism not exercised)](cases/PR-01.explicit-catch-commit.sqlalchemy.native.json) | [PASS](cases/PR-01.explicit-catch-commit.sqlalchemy-core.native.json) | [PASS](cases/PR-01.explicit-catch-commit.typeorm.native.json) |
| `PR-01.uncaught-control` | A (PostgreSQL error) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.knex.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.kysely.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.pg.check-tag.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.pg.ignore-tag.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.django.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.lucid.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.mikroorm.native.json) | [PASS](cases/PR-01.uncaught-control.spring-jdbc.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.spring-jdbc.pooled.json) | [PASS](cases/PR-01.uncaught-control.spring-tx.native.json) | [PASS](cases/PR-01.uncaught-control.spring-tx.declarative.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.spring-tx.pooled.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.sqlalchemy.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.sqlalchemy-core.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.typeorm.native.json) |
| `PR-01.savepoint-recovery` | A (PostgreSQL error) | [PASS](cases/PR-01.savepoint-recovery.knex.native.json) | [PASS](cases/PR-01.savepoint-recovery.kysely.native.json) | [PASS](cases/PR-01.savepoint-recovery.pg.check-tag.json) | [PASS](cases/PR-01.savepoint-recovery.pg.ignore-tag.json) | [PASS](cases/PR-01.savepoint-recovery.django.native.json) | [PASS](cases/PR-01.savepoint-recovery.lucid.native.json) | [PASS](cases/PR-01.savepoint-recovery.mikroorm.native.json) | [PASS](cases/PR-01.savepoint-recovery.spring-jdbc.native.json) | [PASS](cases/PR-01.savepoint-recovery.spring-jdbc.pooled.json) | [PASS](cases/PR-01.savepoint-recovery.spring-tx.native.json) | [INCONCLUSIVE](cases/PR-01.savepoint-recovery.spring-tx.declarative.json) | [PASS](cases/PR-01.savepoint-recovery.spring-tx.pooled.json) | [PASS](cases/PR-01.savepoint-recovery.sqlalchemy.native.json) | [PASS](cases/PR-01.savepoint-recovery.sqlalchemy-core.native.json) | [PASS](cases/PR-01.savepoint-recovery.typeorm.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- knex (native): held
- kysely (native): held
- pg (check-tag): held
- pg (ignore-tag): held
- django (native): held
- lucid (native): held
- mikroorm (native): held
- spring-jdbc (native): held
- spring-jdbc (pooled): held
- spring-tx (native): held
- spring-tx (declarative): held
- spring-tx (pooled): held
- sqlalchemy (native): held
- sqlalchemy-core (native): held
- typeorm (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `PR-01.managed-catch-commit`: no control adapter states an expectation for this case
- `PR-01.explicit-catch-commit`: no control adapter states an expectation for this case
- `PR-01.uncaught-control`: no control adapter states an expectation for this case
- `PR-01.savepoint-recovery`: no control adapter states an expectation for this case

## Qualified passes

- `PR-01.uncaught-control` on knex (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on kysely (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "rollback"
- `PR-01.uncaught-control` on pg (check-tag): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on pg (ignore-tag): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.managed-catch-commit` on django (native): **PASS (mechanism not exercised)**. at before-end the session was "idle in transaction (aborted)"; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on django (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on lucid (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on mikroorm (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "rollback"
- `PR-01.uncaught-control` on spring-jdbc (pooled): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on spring-tx (pooled): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.managed-catch-commit` on sqlalchemy (native): **PASS (mechanism not exercised)**. at before-end the session was "idle"; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.explicit-catch-commit` on sqlalchemy (native): **PASS (mechanism not exercised)**. at before-end the session was "idle"; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on sqlalchemy (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on sqlalchemy-core (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on typeorm (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"

## Inconclusive, unsupported and not run

- `PR-01.explicit-catch-commit` on django (native): **INCONCLUSIVE**. checkpoint "after-write" was not reached; checkpoint "before-end" was not reached
- `PR-01.explicit-catch-commit` on spring-tx (declarative): **INCONCLUSIVE**. the adapter returned status "not_implemented": @Transactional does not return a TransactionStatus. Declarative mode has no explicit commit handle.
- `PR-01.savepoint-recovery` on spring-tx (declarative): **INCONCLUSIVE**. precondition not established: a unique_violation (23505) was observed on the failing statement (violation: 25P02; api_error: none)

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| knex (native) | native | knex 3.3.0, knex 3.3.0, pg 8.23.1, node v24.14.1 | `9ba000b3a6ef…` |
| kysely (native) | native | kysely 0.29.6, kysely 0.29.6, pg 8.23.1, node v24.14.1 | `0d0b0a55070c…` |
| pg (check-tag) | native | pg 8.23.1, pg 8.23.1, node v24.14.1 | `c2d7e3ebb8dd…` |
| pg (ignore-tag) | configured | pg 8.23.1, pg 8.23.1, node v24.14.1 | `c2d7e3ebb8dd…` |
| django (native) | native | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `7a09a9af3b03…` |
| lucid (native) | native | @adonisjs/lucid 22.4.2, knex 3.3.0, tarn 3.1.2, pg-pool 3.14.0, @adonisjs/core 7.6.0, luxon 3.7.2, pg 8.23.1, node v24.14.1 | `fae3c8c56d97…` |
| mikroorm (native) | native | @mikro-orm/core 7.2.5, @mikro-orm/postgresql 7.2.5, @mikro-orm/sql 7.2.5, kysely 0.29.6, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `c906035934ba…` |
| spring-jdbc (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 27 | `31ae4a32672e…` |
| spring-jdbc (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 27 | `31ae4a32672e…` |
| spring-tx (native) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 27 | `6f5f7e6cb60b…` |
| spring-tx (declarative) | native | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, postgresql 42.7.14, java 27 | `6f5f7e6cb60b…` |
| spring-tx (pooled) | configured | spring-framework 7.0.9, spring-tx 7.0.9, spring-jdbc 7.0.9, spring-aop 7.0.9, spring-context 7.0.9, postgresql 42.7.14, HikariCP 7.1.0, postgresql 42.7.14, java 27 | `6f5f7e6cb60b…` |
| sqlalchemy (native) | native | sqlalchemy 2.1.5, psycopg 3.3.6, python 3.13.11 | `a93ca31bde41…` |
| sqlalchemy-core (native) | native | sqlalchemy 2.1.5, psycopg 3.3.6, python 3.13.11 | `f207e592897b…` |
| typeorm (native) | native | typeorm 1.1.2, pg-pool 3.14.0, pg 8.23.1, node v24.14.1 | `4099adf5effb…` |

