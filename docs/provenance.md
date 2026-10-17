# Provenance

PPCS 0.1 was extracted on 2026-10-16 from the PostgreSQL experiments of the Adonis' Nest persistence research repository (`nest-adonis-spike`). It was not published at the time of extraction.

- **What the experiments were for.** Three experiment projects measured Lucid, MikroORM and TypeORM against an internal persistence standard, on the same PostgreSQL server image.
- **Why files are identified by hash.** At extraction, the projects were uncommitted files on top of commit `015cc82`. So this page identifies each source file by its path under `docs/experiments/` and the first 16 hex digits of its SHA-256.
- **Where the files are now.** They have since been committed unchanged, and every digest on this page matches the committed file: the Lucid project in `3781772`, MikroORM in `7497dd0`, TypeORM in `06f93bb`. (The repository's history was rewritten after the extraction; `015cc82` was `0b98556` before.)
- **Independence.** PPCS does not need the source repository to run. Its specifications are stated independently, and its results come from its own runs.

## Files reused

| PPCS file | Source (`docs/experiments/…`) | SHA-256 prefix | How |
| --- | --- | --- | --- |
| `adapters/lucid/pnpm-lock.yaml` | `lucid-postgres/pnpm-lock.yaml` | `a798cda819011e2e` | Copied unchanged |
| `adapters/mikroorm/pnpm-lock.yaml` | `mikroorm-postgres/pnpm-lock.yaml` | `610b86f1910ff76d` | Copied, then pruned of `@mikro-orm/decorators`, `@mikro-orm/migrations` and `reflect-metadata`. No other resolution changed. |
| `adapters/typeorm/pnpm-lock.yaml` | `typeorm-postgres/pnpm-lock.yaml` | `ed21805169fbbf85` | Copied, then pruned of the NestJS, rxjs, TypeScript and type packages (32 entries). No other resolution changed. |
| `harness/lib/instance.mjs` | `lucid-postgres/lib/harness.mjs`: safety gate, owned databases, scoped termination | `e7eb661b240f4168` | Adapted |
| `adapters/node-kit/pg-instrument.mjs` | `lucid-postgres/lib/harness.mjs`: statement trace; `client-reject`, `rewrite` and `reply-lost` faults. The same mechanism is in `typeorm-postgres/lib/harness.mjs` (`b3b0ff3864e6a362`). | `e7eb661b240f4168` | Adapted: one instance per adapter process, and the reply tag of every transaction-control statement is recorded |
| `adapters/lucid/lucid.mjs` | `lucid-postgres/lib/harness.mjs` (standalone `Database`), `lucid-postgres/lib/models.mjs` (`Item`, `Uniq`) | `e7eb661b240f4168`, `292a2ea9c6cf22b6` | Adapted |
| `adapters/mikroorm/orm.mjs` | `mikroorm-postgres/lib/harness.mjs` (`initOrm`, `inRequest`), `mikroorm-postgres/lib/entities.mjs` | `09d1134bc61fc5e0`, `dd17cf4d20658560` | Adapted |
| `adapters/typeorm/orm.mjs` | `typeorm-postgres/lib/harness.mjs` (`makeDataSource`), `typeorm-postgres/lib/entities.mjs` | `b3b0ff3864e6a362`, `cfc846486b9b4537` | Adapted |
| `scripts/pg-up.sh` | `lucid-postgres/scripts/pg-up.sh`: cluster_name token, host-port wait | `e9971bb5980fe623` | Adapted to Docker Compose, with a random password per start |
| Catalog fixture | The `item` and `uniq` tables of `lucid-postgres/lib/harness.mjs` | `e7eb661b240f4168` | Subset |

The case implementations in `adapters/*/main.mjs` are adaptations of the experiments listed below. Each names its source experiment in a comment. The experiment files they come from:

| Suite | Experiment files |
| --- | --- |
| Lucid | `lucid-postgres/experiments/lt-transactions.mjs` (`a16939d267ded55d`), `lr-tx6.mjs` (`b98f71e2311e1084`), `lg-gates.mjs` (`4301efcdd847d9b5`) |
| MikroORM | `mikroorm-postgres/experiments/e1-core.mjs` (`9cabb440eff63fd0`), `e1-more.mjs` (`bc51a9279b315c31`), `e3-tx6.mjs` (`ef7c77f30cd647bc`), `e4-pool.mjs` (`81e4733ec3f86f46`) |
| TypeORM | `typeorm-postgres/experiments/tt-transactions.mjs` (`ade55d508114f61e`), `tr-tx6.mjs` (`c3ab6547268c06e9`) |

**The adaptations, the same in every case:**

- markers carry a per-run value;
- checkpoints report `pg_current_xact_id()` and `pg_backend_pid()` from inside the transaction;
- the final state is read by the runner's observer, not by the experiment;
- category B terminations are made by the runner instead of inside the experiment;
- pools hold one connection (two in `TX-04.independent-inner`). Some original experiments used the harness default of four; pool size does not affect a single-transaction case.

## Experiments reused, and how the results compare

**Original verdicts.** They come from the latest baselines: `lucid-22.4.2.rev4.json` (`02fed8e928eb9b38`), `mikro-orm-7.2.5.rev3.json` (`69e0ec8058ecb137`) and `typeorm-1.1.2.rev2.json` (`cac51ec8344d8b1f`). They were judged against the internal standard's pass conditions, not against PPCS's invariants, so agreement means the same scenario failed or passed in the same direction.

**PPCS results.** They come from the run in `reports/examples/`, on the same package versions. Hardening the methodology changed no framework classification in this table: only the controls' own expected results changed.

| PPCS case | Lucid 22.4.2 | MikroORM 7.2.5 | TypeORM 1.1.2 |
| --- | --- | --- | --- |
| `TX-01A.caught-error-then-commit` | LT1a FAIL → FAIL; LT1c PASS → `pre-commit-probe` PASS | T4f FAIL → FAIL | TT1a FAIL → FAIL |
| `TX-01B.conn-lost-before-commit` | LR1d FAIL → FAIL | R1f PASS → PASS | TR1e PASS → PASS |
| `TX-01B.commit-reply-discarded` | LH1e's fault (that experiment tested after-commit hooks; it recorded the commit reported as success) → FAIL | New: the suite had no reply-lost experiment → PASS | TR1e3 PASS → PASS |
| `TX-02.savepoint-rollback-not-sent` | LR1a FAIL → FAIL | R1a FAIL → FAIL | TR1c FAIL → FAIL |
| `TX-02.savepoint-rollback-rejected` | LT5b FAIL → FAIL | T7c FAIL → FAIL | TR1b FAIL → FAIL (TX-02.2). TR1b also ran the next unit of work; PPCS stops when the outer API returns. |
| `TX-02.conn-lost-before-savepoint-rollback` | LR1b FAIL → FAIL | R1e PASS → PASS | TR1c2 PASS → PASS |
| `TX-03.rollback-not-sent` | LT5c FAIL → FAIL | P1a FAIL → FAIL | TR1d FAIL → FAIL |
| `TX-03.conn-lost-in-transaction` | LR1c PASS → PASS | P1c FAIL → FAIL | TR1d2 PASS → PASS |
| `TX-04.nested-failure-contained` | LT2b PASS → PASS | T2a FAIL → FAIL; T2b PASS → `clear-forks` PASS | TT2b PASS → PASS |
| `TX-04.nested-released-outer-rollback` | New → PASS | New → PASS | New → PASS |
| `TX-04.independent-inner` | No propagation API → UNSUPPORTED | T1a FAIL → FAIL; T1b PASS → `clear-forks` PASS | No propagation API → UNSUPPORTED |
| `CTL-01.*` | New → PASS | New → PASS | New → PASS |

**New in PPCS:**

- the `pg-control` controls;
- the misbehaving fixture;
- the case runner, observer, classification and reports;
- `xmin` attribution of markers;
- observation at report time, write evidence in `pg_locks`, and the server-side signature of each fault;
- the run-level gates: controls in the same run, and three agreeing repetitions.

## Versions reproduced

| Component | Version |
| --- | --- |
| PostgreSQL | 18.6, `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. This is the same multi-platform image index the original runs resolved `postgres:18` to. |
| Node.js | 24.14.1 |
| pnpm | 12.8.1 |
| Lucid | `@adonisjs/lucid` 22.4.2, `@adonisjs/core` 7.6.0, knex 3.3.0, tarn 3.1.2, luxon 3.7.2 |
| MikroORM | `@mikro-orm/core`, `@mikro-orm/postgresql` and `@mikro-orm/sql` 7.2.5, kysely 0.29.6 |
| TypeORM | typeorm 1.1.2, reflect-metadata 0.2.2 (a peer dependency) |
| Driver, every project | pg 8.23.1, pg-pool 3.14.0, pg-protocol 1.16.1 |

Upgrading any of these is a separate, recorded change: a new lockfile, and a run compared with `--expect` against the earlier one.

## Not reused

- **`lucid-postgres/lib/patches.mjs`:** runtime simulations of proposed upstream fixes. It contains copies of MIT-licensed `@adonisjs/lucid` and `knex` source.
- **Mitigation prototypes:** `lib/mitigations.mjs`, `lib/tx6.mjs`, `lib/tx9.mjs`, `lib/kit.mjs` and `lib/tx6-guard.mjs`. The one mitigation PPCS runs, LT1c's pre-commit probe, is re-implemented in a few lines as a hardened mode.
- **Out of scope for 0.1:** the migration experiments (LM, M, TM), concurrency (LC, T8, T9, TC), operations (LO, TO), after-commit hooks (LH, TH), NestJS integration (TN) and type-checking (TD).
- **Records:** the original baselines and recorded runs. They remain in the source repository; PPCS records its own runs.

## Licensing

The reused code was written for the source repository, whose packages were private, unpublished and marked `UNLICENSED`. It has one author, who is also PPCS's copyright holder. PPCS is licensed under the MIT License (`LICENSE`).

The only third-party code in the source experiments, `patches.mjs`, was not copied. The frameworks under test are installed from npm at the versions above, and are not vendored. Each keeps its own license: MIT for Lucid, knex, MikroORM, kysely, TypeORM and node-postgres.
