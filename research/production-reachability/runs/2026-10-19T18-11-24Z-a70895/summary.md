# PPCS run 2026-10-19T18-11-24Z-a70895

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `research/production-reachability/catalog.json`, sha256 `405731e049f8…`
- **Runner:** PPCS 0.3.0, harness sha256 `af929302a2da…`, Node v24.14.1
- **Repetitions:** every executed case ran once, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-19T18:11:24.256Z; duration 4 s
- **Counts:** PASS 12

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

## Results

| Case | Fault | knex (native) | kysely (native) |
| --- | --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.knex.native.json) | [PASS](cases/CTL-01.commit.kysely.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.knex.native.json) | [PASS](cases/CTL-01.rollback.kysely.native.json) |
| `PR-01.managed-catch-commit` | A (PostgreSQL error) | [PASS](cases/PR-01.managed-catch-commit.knex.native.json) | [PASS](cases/PR-01.managed-catch-commit.kysely.native.json) |
| `PR-01.explicit-catch-commit` | A (PostgreSQL error) | [PASS](cases/PR-01.explicit-catch-commit.knex.native.json) | [PASS](cases/PR-01.explicit-catch-commit.kysely.native.json) |
| `PR-01.uncaught-control` | A (PostgreSQL error) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.knex.native.json) | [PASS (mechanism not exercised)](cases/PR-01.uncaught-control.kysely.native.json) |
| `PR-01.savepoint-recovery` | A (PostgreSQL error) | [PASS](cases/PR-01.savepoint-recovery.knex.native.json) | [PASS](cases/PR-01.savepoint-recovery.kysely.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- knex (native): held
- kysely (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `PR-01.managed-catch-commit`: no control adapter states an expectation for this case
- `PR-01.explicit-catch-commit`: no control adapter states an expectation for this case
- `PR-01.uncaught-control`: no control adapter states an expectation for this case
- `PR-01.savepoint-recovery`: no control adapter states an expectation for this case

## Qualified passes

- `PR-01.uncaught-control` on knex (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "ROLLBACK"
- `PR-01.uncaught-control` on kysely (native): **PASS (mechanism not exercised)**. before-end was not recorded; at after-api the session was "idle" and its last statement was "rollback"

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| knex (native) | native | knex 3.3.0, knex 3.3.0, pg 8.23.1, node v24.14.1 | `9ba000b3a6ef…` |
| kysely (native) | native | kysely 0.29.6, kysely 0.29.6, pg 8.23.1, node v24.14.1 | `0d0b0a55070c…` |

