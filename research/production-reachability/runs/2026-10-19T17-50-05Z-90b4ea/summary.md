# PPCS run 2026-10-19T17-50-05Z-90b4ea

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `research/production-reachability/catalog.json`, sha256 `405731e049f8…`
- **Runner:** PPCS 0.3.0, harness sha256 `af929302a2da…`, Node v24.14.1
- **Repetitions:** every executed case ran once, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-19T17:50:05.953Z; duration 3 s
- **Counts:** INCONCLUSIVE 24

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

## Results

| Case | Fault | knex (native) | kysely (native) | pg (check-tag) | pg (ignore-tag) |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | [INCONCLUSIVE](cases/CTL-01.commit.knex.native.json) | [INCONCLUSIVE](cases/CTL-01.commit.kysely.native.json) | [INCONCLUSIVE](cases/CTL-01.commit.pg.check-tag.json) | [INCONCLUSIVE](cases/CTL-01.commit.pg.ignore-tag.json) |
| `CTL-01.rollback` | none | [INCONCLUSIVE](cases/CTL-01.rollback.knex.native.json) | [INCONCLUSIVE](cases/CTL-01.rollback.kysely.native.json) | [INCONCLUSIVE](cases/CTL-01.rollback.pg.check-tag.json) | [INCONCLUSIVE](cases/CTL-01.rollback.pg.ignore-tag.json) |
| `PR-01.managed-catch-commit` | A (PostgreSQL error) | [INCONCLUSIVE](cases/PR-01.managed-catch-commit.knex.native.json) | [INCONCLUSIVE](cases/PR-01.managed-catch-commit.kysely.native.json) | [INCONCLUSIVE](cases/PR-01.managed-catch-commit.pg.check-tag.json) | [INCONCLUSIVE](cases/PR-01.managed-catch-commit.pg.ignore-tag.json) |
| `PR-01.explicit-catch-commit` | A (PostgreSQL error) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.knex.native.json) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.kysely.native.json) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.pg.check-tag.json) | [INCONCLUSIVE](cases/PR-01.explicit-catch-commit.pg.ignore-tag.json) |
| `PR-01.uncaught-control` | A (PostgreSQL error) | [INCONCLUSIVE](cases/PR-01.uncaught-control.knex.native.json) | [INCONCLUSIVE](cases/PR-01.uncaught-control.kysely.native.json) | [INCONCLUSIVE](cases/PR-01.uncaught-control.pg.check-tag.json) | [INCONCLUSIVE](cases/PR-01.uncaught-control.pg.ignore-tag.json) |
| `PR-01.savepoint-recovery` | A (PostgreSQL error) | [INCONCLUSIVE](cases/PR-01.savepoint-recovery.knex.native.json) | [INCONCLUSIVE](cases/PR-01.savepoint-recovery.kysely.native.json) | [INCONCLUSIVE](cases/PR-01.savepoint-recovery.pg.check-tag.json) | [INCONCLUSIVE](cases/PR-01.savepoint-recovery.pg.ignore-tag.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- knex (native): **did not hold**: CTL-01.commit INCONCLUSIVE, CTL-01.rollback INCONCLUSIVE
- kysely (native): **did not hold**: CTL-01.commit INCONCLUSIVE, CTL-01.rollback INCONCLUSIVE
- pg (check-tag): **did not hold**: CTL-01.commit INCONCLUSIVE, CTL-01.rollback INCONCLUSIVE
- pg (ignore-tag): **did not hold**: CTL-01.commit INCONCLUSIVE, CTL-01.rollback INCONCLUSIVE

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `PR-01.managed-catch-commit`: no control adapter states an expectation for this case
- `PR-01.explicit-catch-commit`: no control adapter states an expectation for this case
- `PR-01.uncaught-control`: no control adapter states an expectation for this case
- `PR-01.savepoint-recovery`: no control adapter states an expectation for this case

## Inconclusive, unsupported and not run

- `CTL-01.commit` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.rollback` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.managed-catch-commit` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.explicit-catch-commit` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.uncaught-control` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.savepoint-recovery` on knex (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.commit` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.rollback` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.managed-catch-commit` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.explicit-catch-commit` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.uncaught-control` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.savepoint-recovery` on kysely (native): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.commit` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.commit` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.rollback` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `CTL-01.rollback` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.managed-catch-commit` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.managed-catch-commit` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.explicit-catch-commit` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.explicit-catch-commit` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.uncaught-control` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.uncaught-control` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.savepoint-recovery` on pg (check-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)
- `PR-01.savepoint-recovery` on pg (ignore-tag): **INCONCLUSIVE**. the adapter sent no hello message; the adapter exited without a result (exit code 1, signal none)

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |

