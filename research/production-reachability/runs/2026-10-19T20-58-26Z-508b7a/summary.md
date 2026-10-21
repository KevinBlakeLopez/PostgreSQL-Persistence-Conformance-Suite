# PPCS run 2026-10-19T20-58-26Z-508b7a

- **PostgreSQL:** 18.6 (Debian 18.6-1.pgdg13+2) (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`)
- **Catalog:** `research/production-reachability/catalog.json`, sha256 `405731e049f8…`
- **Runner:** PPCS 0.3.0, harness sha256 `af929302a2da…`, Node v24.14.1
- **Repetitions:** every executed case ran 3 times, each time on a fresh database; a result counts only if its repetitions agree
- **Started:** 2026-10-19T20:58:26.886Z; duration 4 s
- **Counts:** PASS 3

Each cell links to that case's evidence. A FAIL is a reproducible counterexample to the stated PPCS invariant under the recorded conditions. By itself it is not a claim that the framework has a defect (docs/methodology.md).

A qualifier in parentheses changes what a classification means: "mechanism not exercised" (the case's mechanism did not run, so the PASS says less), "not exercised" (an invariant the adapter cannot exercise), "not applicable by design", "gated" (the run's controls did not hold, so the result does not count). Faults of category C and D are client-side injections and simulations, not network failures (docs/methodology.md).

## Results

| Case | Fault | django (native) |
| --- | --- | --- |
| `CTL-01.commit` | none | [PASS](cases/CTL-01.commit.django.native.json) |
| `CTL-01.rollback` | none | [PASS](cases/CTL-01.rollback.django.native.json) |
| `PR-01.explicit-catch-commit` | A (PostgreSQL error) | [PASS](cases/PR-01.explicit-catch-commit.django.native.json) |

## Controls in this run

Observation controls (CTL-01). A scenario result counts only if both CTL-01 cases PASSed for the same adapter and mode in this run:

- django (native): held

Case controls. A framework's result for a case counts only if the control adapters' expectations for that case held in this run:

- `PR-01.explicit-catch-commit`: no control adapter states an expectation for this case

## Subjects

| Adapter (mode) | Kind | Versions | Adapter source sha256 |
| --- | --- | --- | --- |
| django (native) | native | django 6.1.2, psycopg 3.3.6, python 3.13.11 | `de213cddef82…` |

