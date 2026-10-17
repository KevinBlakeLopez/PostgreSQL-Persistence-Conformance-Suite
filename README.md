# PostgreSQL Persistence Conformance Suite (PPCS)

PPCS is a reproducible laboratory for transaction correctness in persistence frameworks, run against a real PostgreSQL server. It drives a framework through its own APIs and injects controlled failures. It then checks, through PostgreSQL itself, whether what the framework reported matches what the server did.

It answers questions like these:

- When a framework reports that a transaction committed, did PostgreSQL commit it?
- When the commit outcome is unknowable to the client, does the framework still assert one?
- After a nested scope's savepoint rollback fails, can its abandoned writes be committed anyway?
- After a rollback fails, can the pool hand the connection, still holding the failed transaction, to unrelated work?
- Does nested transactional work land in the boundary the framework's propagation API promises?

## Why

A framework's report of a transaction outcome is a claim. A framework's own test suite usually checks that claim with the framework's own reads, often against mocks. PPCS checks it independently:

- **Transaction identity:** each transaction's ID is read inside it, with `pg_current_xact_id()`, and checked against that session in `pg_stat_activity`.
- **Fate:** a separate connection asks PostgreSQL for that transaction's fate, with `pg_xact_status()`, when the API returns and again after the framework is gone. It also asks which writes are visible, and which transaction inserted each one.
- **Fault labels:** every fault is labelled by what it is: an error PostgreSQL generated, a server-side termination, or a client-side injection. Its effect is confirmed on the server.
- **Controls:** a result counts only if, in the same run, the framework's own observation controls passed, the suite's positive and negative controls behaved as expected, and three repetitions agreed.

## What PPCS does not claim

- **A FAIL is not a defect report.** It is a reproducible counterexample to a stated PPCS invariant, under recorded versions, settings and fault category. Each FAIL quotes the framework's contract for the API it called, so that readers can judge it against the framework's own promises.
- **Injected faults show recovery paths, not frequency.** Category C and D faults are injected in the client. They show what a framework does *if* that failure happens, not how often it happens in production.
- **PPCS is not a ranking, a benchmark, an ORM, or a replacement for a framework's own tests.**

## Quick start

Requirements: Docker (with Compose), Node.js 24, pnpm 12.

```sh
pnpm run setup     # frozen-lockfile install of the harness and every adapter
pnpm run pg:up     # disposable PostgreSQL 18.6 on 127.0.0.1:55435 (pinned image digest, tmpfs, random password)
pnpm run ppcs      # every case on every adapter; writes results/<run id>/summary.md and JSON evidence
pnpm run pg:down   # removes the container
```

- **Filters:** `node harness/run.mjs --adapter=lucid --case=TX-01A --mode=native`. The controls each result depends on always run with it.
- **Repetitions:** every case runs three times by default (`--repeat=<n>`).
- **Regression check:** `--expect=<earlier run.json>` exits 1 if any classification changed. It refuses (exit 2) an earlier run made with a different harness or catalog.
- **Self-tests:** `pnpm run test` for the classification rules, with no database; `pnpm run test:methodology` for the controls through the real runner.

A full run takes about three minutes. The runner refuses any server that is not the disposable instance, or whose settings differ from the profile the cases assume. It never touches another database (`docs/methodology.md`).

## What is implemented

**Specifications** (`specifications/transactions.v1.json`, described in `docs/specifications.md`): 6 families, 14 cases.

| Family | Question | Cases |
| --- | --- | --- |
| CTL-01 | Can the observer see a committed transaction, and the absence of a rolled-back one? | 2 |
| TX-01A | Is a COMMIT that PostgreSQL answered with ROLLBACK reported as a success? | 1 |
| TX-01B | After the connection or the reply is lost around COMMIT, does the framework report only what it has evidence for? | 2 |
| TX-02 | After a failed savepoint rollback, does the transaction continue under an incorrect nesting state? | 3 |
| TX-03 | After a failed rollback, is the connection reused unsafely, and does the pool recover? | 3 |
| TX-04 | Does nested work land in the boundary the propagation API promises? | 3 |

**Adapters:**

| Adapter | Framework stack | Modes |
| --- | --- | --- |
| `lucid` | `@adonisjs/lucid` 22.4.2 (standalone), knex 3.3.0, pg 8.23.1 | `native`; `pre-commit-probe` (hardened) |
| `mikroorm` | `@mikro-orm/postgresql` 7.2.5, kysely 0.29.6, pg 8.23.1 | `native`; `clear-forks` (configured) |
| `typeorm` | `typeorm` 1.1.2, pg 8.23.1 | `native` |
| `pg-control` | node-postgres 8.23.1, no framework | `correct` (positive control); `unsafe` (negative control) |

These are the stacks and versions of the experiments PPCS was extracted from (`docs/provenance.md`).

## Results of the recorded run

The recorded run is [`reports/examples/2026-10-17T01-51-34Z-c1a29f/`](reports/examples/2026-10-17T01-51-34Z-c1a29f/summary.md), PPCS 0.2.0 on PostgreSQL 18.6. It produced 77 results: 45 PASS, 29 FAIL, 3 UNSUPPORTED (all three not applicable by design), 0 INCONCLUSIVE. Each executed case ran three times, and every repetition agreed. A second full run on the same machine reproduced all 77 classifications.

| Case | Fault | Lucid | MikroORM | TypeORM |
| --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | PASS | PASS | PASS |
| `CTL-01.rollback` | none | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | A | FAIL (hardened `pre-commit-probe`: PASS, mechanism not exercised) | FAIL | FAIL |
| `TX-01B.conn-lost-before-commit` | B | FAIL | PASS | PASS |
| `TX-01B.commit-reply-discarded` | D | FAIL (TX-01B.2 not exercised) | PASS (TX-01B.2 not exercised) | PASS (TX-01B.2 not exercised) |
| `TX-02.savepoint-rollback-not-sent` | C | FAIL | FAIL | FAIL |
| `TX-02.savepoint-rollback-rejected` | C | FAIL | FAIL | FAIL |
| `TX-02.conn-lost-before-savepoint-rollback` | B | FAIL | PASS | PASS |
| `TX-03.rollback-not-sent` | C | FAIL | FAIL | FAIL |
| `TX-03.statement-error-rollback-not-sent` | C | FAIL | FAIL | FAIL |
| `TX-03.conn-lost-in-transaction` | B | PASS | FAIL | PASS |
| `TX-04.nested-failure-contained` | none | PASS | FAIL (configured `clear-forks`: PASS) | PASS |
| `TX-04.nested-released-outer-rollback` | none | PASS | PASS | PASS |
| `TX-04.independent-inner` | none | UNSUPPORTED (not applicable by design) | FAIL (configured `clear-forks`: PASS) | UNSUPPORTED (not applicable by design) |

**How to read the matrix:**

- **Fault categories:** A is an error PostgreSQL generated, B a backend terminated by the runner, C an error injected in the client, D a client-side simulation (`docs/methodology.md`).
- **The 21 framework FAILs:** 8 need no client-side injection, and 13 depend on one.
- **Qualifiers:**
  - **"Mechanism not exercised":** Lucid's `pre-commit-probe` passes TX-01A by failing before COMMIT. That makes it a valid mitigation, not evidence that Lucid reads the reply to COMMIT.
  - **"TX-01B.2 not exercised":** the framework adapters observe no channel through which a framework could claim a rollback, so TX-01B.2 was not tested for them.
- **Report time:** where a transaction was still open when the API returned, each FAIL says so, and says whether teardown or later work decided its fate. In TypeORM's TX-02 cases, for example, the transaction was open at report time and rolled back at teardown.
- **Controls:** the positive control passes every case it implements. The negative control fails the 7 cases it is built to fail, so the runner detects a known-bad implementation. That includes unsafe connection reuse, which the observer sees server-side: the next unit of work runs inside the failed transaction's own ID. It also includes a write lost with a failed nested scope. Every control expectation held in this run, so no result was gated.
- **Detail:** each FAIL in `reports/examples/*/summary.md` gives what the API reported, what PostgreSQL did at report time and at the end, what the application could know, the violated invariant, the framework's contract, and a reproduction command.

## Classifications

| Classification | Meaning |
| --- | --- |
| PASS | Every exercised invariant of the case held, with complete and consistent observations. A qualifier marks an invariant or a mechanism that was not exercised. |
| FAIL | An invariant was violated. The result names it, with the observations, the conditions and the contract basis. |
| UNSUPPORTED | The adapter's manifest declares that the framework's supported API does not expose what the case tests, or that the hazard cannot arise by design. Never a failure. |
| INCONCLUSIVE | The run did not establish a conclusion. Causes include a timeout, a protocol error, a missing or unconfirmed observation, a precondition that did not hold, observations that contradict each other, disagreeing repetitions, or controls that did not hold in the run. Never a PASS. |
| NOT_RUN | The case was not executed: not implemented by the adapter, or filtered out. |

## Layout

| Path | Contents |
| --- | --- |
| `specifications/` | The case catalog |
| `harness/` | The runner (`run.mjs`), observer, adapter process handling, classification, reports and tests |
| `adapters/` | One project per adapter, each with its own lockfile. `node-kit/` is shared by the JavaScript adapters only. |
| `schema/` | JSON Schemas for a case result and for a run manifest |
| `docs/` | Methodology, specifications, the adapter protocol and provenance |
| `reports/examples/` | A complete recorded run: `summary.md`, `run.json` and one JSON file per case |
| `compose.yaml`, `scripts/` | The disposable server; setup |

## Documentation

- `docs/methodology.md`: independent observation, fault categories, commit outcome ambiguity, classification, gates, modes, controls, reproducibility, limitations.
- `docs/specifications.md`: the families and cases.
- `docs/protocol.md`: how an adapter, in any language, talks to the runner.
- `docs/provenance.md`: the experiments PPCS reuses, with versions and how their results compare.
- `CONTRIBUTING.md`: adding an adapter without compromising framework-native semantics.

## License

MIT (`LICENSE`). The frameworks under test are installed from npm, are not vendored, and keep their own licenses.
