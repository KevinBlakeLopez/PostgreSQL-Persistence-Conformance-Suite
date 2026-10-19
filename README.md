# PostgreSQL Persistence Conformance Suite (PPCS)

PPCS is a reproducible laboratory for transaction correctness in persistence frameworks, run against a real PostgreSQL server. It drives a framework through its own APIs and injects controlled failures. It then checks, through PostgreSQL itself, whether what the framework reported matches what the server did.

It answers questions like these:

- When a framework reports that a transaction committed, did PostgreSQL commit it?
- When the commit outcome is unknowable to the client, does the framework still assert one?
- After a nested scope's savepoint rollback fails, can its abandoned writes be committed anyway?
- After a rollback fails, can the pool hand the connection, still holding the failed transaction, to unrelated work?
- Does nested transactional work land in the boundary the framework's propagation API promises?
- When application code asks for an isolation level, does the transaction run at that level?

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

Requirements: Docker (with Compose), Node.js 24, pnpm 12. JDK 21 for the Spring JDBC adapter.

```sh
pnpm run setup     # frozen-lockfile install of the harness and the JavaScript adapters
pnpm run pg:up     # disposable PostgreSQL 18.6 on 127.0.0.1:55435 (pinned image digest, tmpfs, random password)
pnpm run ppcs      # every case on every adapter; writes results/<run id>/summary.md and JSON evidence
pnpm run pg:down   # removes the container
```

- **Filters:** `node harness/run.mjs --adapter=lucid --case=TX-01A --mode=native`. The controls each result depends on always run with it.
- **Repetitions:** every case runs three times by default (`--repeat=<n>`).
- **Regression check:** `--expect=<earlier run.json>` exits 1 if any classification changed. It refuses (exit 2) an earlier run made with a different harness or catalog.
- **Self-tests:** `pnpm run test` for the classification rules, with no database; `pnpm run test:methodology` for the controls through the real runner.

A full run of the JavaScript adapters takes about six minutes. Django, SQLAlchemy, and Tortoise each need the virtualenv in their adapter README. Spring JDBC and the plain JDBC control need JDK 21 and `mvn -B package` in `adapters/spring-jdbc` and `adapters/jdbc-control`. `pnpm run setup` does not install those. The runner refuses any server that is not the disposable instance, or whose settings differ from the profile the cases assume. It never touches another database (`docs/methodology.md`).

## What is implemented

**Specifications** (`specifications/`, described in `docs/specifications.md`): 9 families, 23 cases. Lucid and `pg-control` execute MG-02 and MG-03. Django, the SQLAlchemy ORM adapter, and Spring JDBC do not implement the migration cases, TX-04, or TX-05. SQLAlchemy Core implements TX-04 and TX-05 and declares the migration cases unsupported. Tortoise implements the two TX-04 savepoint cases. It declares `TX-04.independent-inner` and both TX-05 cases unsupported, and it does not implement the migration cases. Drizzle implements the transaction cases through `db.transaction()`, including the savepoint TX-04 cases and managed TX-05. It declares `TX-04.independent-inner` not applicable by design and `TX-05.explicit-serializable` capability-absent, and it does not implement the migration cases. The plain JDBC control implements the savepoint TX-04 cases and TX-05, and declares `TX-04.independent-inner` and the migration cases unsupported.

| Family | Question | Cases |
| --- | --- | --- |
| CTL-01 | Can the observer see a committed transaction, and the absence of a rolled-back one? | 2 |
| TX-01A | Is a COMMIT that PostgreSQL answered with ROLLBACK reported as a success? | 1 |
| TX-01B | After the connection or the reply is lost around COMMIT, does the framework report only what it has evidence for? | 2 |
| TX-02 | After a failed savepoint rollback, does the transaction continue under an incorrect nesting state? | 3 |
| TX-03 | After a failed rollback, is the connection reused unsafely, and does the pool recover? | 3 |
| TX-04 | Does nested work land in the boundary the propagation API promises? | 3 |
| TX-05 | When a framework is asked for an isolation level, does the transaction run at that level? | 2 |
| MG-02 | With several runner processes, is each migration committed once, and does that survive the loss of one session? | 4 |
| MG-03 | After a revert, does history describe the database? | 3 |

**Adapters:**

| Adapter | Framework stack | Modes |
| --- | --- | --- |
| `lucid` | `@adonisjs/lucid` 22.4.2 (standalone), knex 3.3.0, pg 8.23.1 | `native`; `pre-commit-probe` (hardened) |
| `mikroorm` | `@mikro-orm/postgresql` 7.2.5, kysely 0.29.6, pg 8.23.1 | `native`; `clear-forks` (configured) |
| `typeorm` | `typeorm` 1.1.2, pg 8.23.1 | `native` |
| `pg-control` | node-postgres 8.23.1, no framework | `correct` (positive control); `unsafe` (negative control) |
| `django` | Django 6.1.2, psycopg 3.3.6 | `native` (`CONN_MAX_AGE` 0); `persistent` (`CONN_MAX_AGE` null, TX-03 only) |
| `sqlalchemy` | SQLAlchemy 2.1.5 ORM `Session`, psycopg 3.3.6 | `native` |
| `sqlalchemy-core` | SQLAlchemy 2.1.5 Core `Connection`, psycopg 3.3.6 | `native` |
| `tortoise` | Tortoise ORM 1.1.9, asyncpg 0.32.0 | `native` |
| `spring-jdbc` | Spring Framework 7.0.9 `TransactionTemplate` and `JdbcTemplate`, PostgreSQL JDBC 42.7.14, HikariCP 7.1.0 | `native` (`DriverManagerDataSource`); `pooled` (HikariCP, `maximumPoolSize` 1, TX-03 only) |
| `jdbc-control` | PostgreSQL JDBC 42.7.14, Java 21, no framework and no pool | `correct` (positive control); `unsafe` (negative control) |
| `drizzle` | `drizzle-orm` 0.45.4, `drizzle-orm/node-postgres`, pg 8.23.1, pg-pool 3.14.0 | `native` (`pg.Pool`, `db.transaction(callback)`) |
| `drizzle-rc` | `drizzle-orm` 1.0.0-rc.4, `drizzle-orm/node-postgres`, pg 8.23.1, pg-pool 3.14.0 | `native` (`drizzle({ client: pg.Pool })`, `db.transaction(callback)`) |

The first four rows are the stacks and versions of the experiments PPCS was extracted from (`docs/provenance.md`). Django, SQLAlchemy, SQLAlchemy Core, Tortoise, Spring JDBC, the plain JDBC control, and Drizzle are later adapters, written as separate programs. They are not part of that extraction. Django and the SQLAlchemy ORM adapter are not general ORM runners. The Core adapter does not use `Session`. Tortoise drives `in_transaction()` on asyncpg, not every Tortoise API. Spring JDBC is not a Spring Boot, Hibernate, or JPA application. The plain JDBC control is not a transaction library. An adapter does not have to be written in JavaScript. Their install and runner commands are in [`adapters/django`](adapters/django/README.md), [`adapters/sqlalchemy`](adapters/sqlalchemy/README.md), [`adapters/sqlalchemy-core`](adapters/sqlalchemy-core/README.md), [`adapters/tortoise`](adapters/tortoise/README.md), [`adapters/spring-jdbc`](adapters/spring-jdbc/README.md), [`adapters/jdbc-control`](adapters/jdbc-control/README.md), [`adapters/drizzle`](adapters/drizzle/README.md), and [`adapters/drizzle-rc`](adapters/drizzle-rc/README.md).

## Results

The matrix below is the Node, Django, SQLAlchemy, SQLAlchemy Core, Tortoise, Spring JDBC, and Drizzle recordings, all on PostgreSQL 18.6 and the same catalog. They are not one execution. The Lucid, MikroORM, and TypeORM columns are the Node run. The Django, SQLAlchemy, SQLAlchemy Core, Tortoise, Spring JDBC, and Drizzle columns are later runs. The plain JDBC control is a separate run and is not a column in the matrix.

The Node run is [`reports/examples/2026-10-18T00-11-46Z-95887b/`](reports/examples/2026-10-18T00-11-46Z-95887b/summary.md), PPCS 0.3.0. It produced 122 results: 64 PASS, 40 FAIL, 3 UNSUPPORTED (all three not applicable by design), 1 INCONCLUSIVE, 14 NOT_RUN. Each executed case ran three times, and every repetition agreed. The 87 classifications from the previous recording are unchanged. The 35 new results are MG-02 and MG-03: Lucid and both `pg-control` modes, plus NOT_RUN for MikroORM and TypeORM, which do not implement those cases. A second full run on the same machine reproduced all 122 classifications.

Django 6.1.2 is [`reports/examples/2026-10-18T13-08-22Z-6d8443/`](reports/examples/2026-10-18T13-08-22Z-6d8443/summary.md). The per-case report is [`adapters/django/FINDINGS.md`](adapters/django/FINDINGS.md). SQLAlchemy 2.1.5 `Session` is [`reports/examples/2026-10-19T00-49-25Z-3673a3/`](reports/examples/2026-10-19T00-49-25Z-3673a3/summary.md). The per-case report is [`adapters/sqlalchemy/FINDINGS.md`](adapters/sqlalchemy/FINDINGS.md). SQLAlchemy 2.1.5 Core is [`reports/examples/2026-10-19T12-35-51Z-64c5c5/`](reports/examples/2026-10-19T12-35-51Z-64c5c5/summary.md). The per-case report is [`adapters/sqlalchemy-core/FINDINGS.md`](adapters/sqlalchemy-core/FINDINGS.md). Tortoise ORM 1.1.9 is [`reports/examples/2026-10-19T12-45-38Z-c45624/`](reports/examples/2026-10-19T12-45-38Z-c45624/summary.md). The per-case report is [`adapters/tortoise/FINDINGS.md`](adapters/tortoise/FINDINGS.md). Spring JDBC is [`reports/examples/2026-10-18T16-08-25Z-9b025d/`](reports/examples/2026-10-18T16-08-25Z-9b025d/summary.md). The per-case report is [`adapters/spring-jdbc/FINDINGS.md`](adapters/spring-jdbc/FINDINGS.md). In each of these, three repetitions agreed, and CTL-01 and `pg-control` held their gates.

Plain JDBC is [`reports/examples/2026-10-19T12-51-00Z-0a0698/`](reports/examples/2026-10-19T12-51-00Z-0a0698/summary.md). The per-case report is [`adapters/jdbc-control/FINDINGS.md`](adapters/jdbc-control/FINDINGS.md). Three repetitions agreed, and CTL-01 and `pg-control` held their gates. `correct` passes every case it executes. `unsafe` fails the eight cases it is built to fail.

Drizzle ORM 0.45.4 is [`reports/examples/2026-10-19T13-38-47Z-39ea07/`](reports/examples/2026-10-19T13-38-47Z-39ea07/summary.md). The per-case report is [`adapters/drizzle/FINDINGS.md`](adapters/drizzle/FINDINGS.md). Three repetitions agreed. CTL-01 and `pg-control` held their gates. Five framework FAILs: `TX-01A.caught-error-then-commit`, with the COMMIT-answered-ROLLBACK mechanism exercised, both savepoint-rollback cases, and both client-side TX-03 cases. The three category B cases are INCONCLUSIVE: the process exits on an unhandled `Client` error event before `db.transaction()` returns.

Drizzle ORM 1.0.0-rc.4 is [`reports/examples/2026-10-19T14-34-08Z-26b178/`](reports/examples/2026-10-19T14-34-08Z-26b178/summary.md), on the same PostgreSQL 18.6, Node.js v24.14.1, and pg 8.23.1. The per-case report is [`adapters/drizzle-rc/FINDINGS.md`](adapters/drizzle-rc/FINDINGS.md). Every classification matches 0.45.4, including the command tag on `COMMIT`, the savepoint SQL, and the reused backend after a withheld `ROLLBACK`. The release candidate is not a separate column in the matrix.

| Case | Fault | Lucid | MikroORM | TypeORM | Django | SQLAlchemy | SQLAlchemy Core | Tortoise | Spring JDBC | Drizzle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `CTL-01.rollback` | none | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| `TX-01A.caught-error-then-commit` | A | FAIL (hardened `pre-commit-probe`: PASS, mechanism not exercised) | FAIL | FAIL | PASS (mechanism not exercised) | INCONCLUSIVE | FAIL (mechanism exercised) | FAIL | FAIL | FAIL (mechanism exercised) |
| `TX-01B.conn-lost-before-commit` | B | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | INCONCLUSIVE |
| `TX-01B.commit-reply-discarded` | D | FAIL (TX-01B.2 not exercised) | PASS (TX-01B.2 not exercised) | PASS (TX-01B.2 not exercised) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | PASS (TX-01B.2 not exercised) |
| `TX-02.savepoint-rollback-not-sent` | C | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| `TX-02.savepoint-rollback-rejected` | C | FAIL | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| `TX-02.conn-lost-before-savepoint-rollback` | B | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | INCONCLUSIVE |
| `TX-03.rollback-not-sent` | C | FAIL | FAIL | FAIL | PASS (persistent) | PASS | PASS | PASS | FAIL (pooled) | FAIL |
| `TX-03.statement-error-rollback-not-sent` | C | FAIL | FAIL | FAIL | PASS (persistent) | PASS | PASS | PASS | PASS (pooled) | FAIL |
| `TX-03.conn-lost-in-transaction` | B | PASS | FAIL | PASS | PASS (persistent) | PASS | PASS | PASS | PASS (pooled) | INCONCLUSIVE |
| `TX-04.nested-failure-contained` | none | PASS | FAIL (configured `clear-forks`: PASS) | PASS | NOT_RUN | NOT_RUN | PASS | PASS | NOT_RUN | PASS |
| `TX-04.nested-released-outer-rollback` | none | PASS | PASS | PASS | NOT_RUN | NOT_RUN | PASS | PASS | NOT_RUN | PASS |
| `TX-04.independent-inner` | none | UNSUPPORTED (not applicable by design) | FAIL (configured `clear-forks`: PASS) | UNSUPPORTED (not applicable by design) | NOT_RUN | NOT_RUN | UNSUPPORTED (not applicable by design) | UNSUPPORTED (not applicable by design) | NOT_RUN | UNSUPPORTED (not applicable by design) |
| `TX-05.managed-serializable` | none | PASS | PASS | PASS | NOT_RUN | NOT_RUN | PASS | UNSUPPORTED | NOT_RUN | PASS |
| `TX-05.explicit-serializable` | none | FAIL | PASS | PASS | NOT_RUN | NOT_RUN | PASS | UNSUPPORTED | NOT_RUN | UNSUPPORTED (capability absent) |
| `MG-02.held` | none | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-02.first-deployment` | none | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-02.session-loss` | B | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-02.idle-session-timeout` | none | INCONCLUSIVE | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-03.valid-reversal` | none | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-03.no-reversal` | none | FAIL | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |
| `MG-03.failing-reversal` | none | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | UNSUPPORTED (capability absent) | NOT_RUN | NOT_RUN | NOT_RUN |

**How to read the matrix:**

- **Fault categories:** A is an error PostgreSQL generated, B a backend terminated by the runner, C an error injected in the client, D a client-side simulation (`docs/methodology.md`).
- **The Node columns.** Those 23 framework FAILs are 10 that need no client-side injection, and 13 that depend on one. The one added in the 0.3.0 recording is Lucid's `MG-03.no-reversal`.
- **Django.** One framework FAIL: `TX-02.savepoint-rollback-not-sent`. A plain exception withheld before send, and Django commits both markers. PostgreSQL's `3B001` on the same statement is a PASS. TX-01A passes with the mechanism not exercised: Django rolls back, so COMMIT is never answered with ROLLBACK. Native TX-03 is not run. `CONN_MAX_AGE` 0 closes the connection at the end of each request. The persistent rows are `CONN_MAX_AGE` null, and they pass.
- **SQLAlchemy.** Two framework FAILs, both TX-02. The withheld savepoint rollback is the same ending as Lucid, MikroORM, Django, and `pg-control` unsafe: the API reports a commit, PostgreSQL commits, and both markers are visible. The rejected savepoint rollback is a different ending: the API reports a commit, the session is idle, the last statement is `COMMIT`, and PostgreSQL aborted the transaction, so neither marker remains. TX-02.2 holds. TX-01A is INCONCLUSIVE: `Session._flush` rolls the transaction back before `before-end`, so the session is already idle there. `TX-01B.commit-reply-discarded` is NOT_RUN for Django, both SQLAlchemy adapters, Tortoise, and Spring JDBC. psycopg does not return from `commit()` until the command finishes. asyncpg's `Transaction.commit` awaits `Connection.execute` until the command finishes. pgjdbc does not return from `commit()` until `ReadyForQuery` has set the driver to `IDLE`.
- **Tortoise.** Three framework FAILs: `TX-01A.caught-error-then-commit` and both savepoint-rollback cases. The withheld savepoint rollback commits both markers, the same ending as Django and SQLAlchemy. The rejected savepoint rollback reports a commit of a transaction PostgreSQL aborted, the same ending as SQLAlchemy, and the session is idle afterward. TX-01A reports a commit after PostgreSQL had aborted the transaction. The runner records `mechanism_exercised` false, because `in_transaction()` releases the connection and the last statement at `after-end` is the pool reset query. TX-03 passes. On the two client-side cases the next unit reuses the backend under a new transaction id, after the pool reset sends `ROLLBACK`. Both implemented TX-04 cases pass. `TX-04.independent-inner` is not applicable by design. Both TX-05 cases are unsupported because `in_transaction()` accepts no isolation level. `TX-01B.commit-reply-discarded` is NOT_RUN.
- **SQLAlchemy Core.** Three framework FAILs. TX-01A fails with the COMMIT-answered-ROLLBACK mechanism exercised: `Connection.begin()` calls `commit()` after the application catches `23505`, `commit()` returns while the connection is `INERROR`, and PostgreSQL has aborted the transaction. The ORM run did not reach that `commit()`. Both TX-02 failures match the ORM endings: a withheld savepoint rollback commits both markers, and a rejected savepoint rollback reports a commit of a transaction PostgreSQL aborted. TX-01B connection loss and all three TX-03 cases pass, with the same pool reuse as the ORM adapter. `begin_nested()` passes both savepoint propagation cases, and both TX-05 forms run at `serializable`. `TX-04.independent-inner` is not applicable by design. MG-02 and MG-03 are capability-absent.
- **Spring JDBC.** Four framework FAILs. `TX-02.savepoint-rollback-not-sent` commits both markers, the same ending as Django and SQLAlchemy. The session was closed afterward. `TX-02.savepoint-rollback-rejected` reports a commit of a transaction PostgreSQL aborted, so neither marker remains and the session was closed. That is the same shape as SQLAlchemy's rejected-savepoint FAIL, and it is not TypeORM's ending: the session was not left idle in transaction. `TX-01A.caught-error-then-commit` reports a commit after PostgreSQL had aborted the transaction. Django rolled that transaction back, and SQLAlchemy's flush rolled it back before `before-end`. `TX-03.rollback-not-sent` fails TX-03.1: the withheld `ROLLBACK` was followed by pgjdbc's `COMMIT` when Spring restored autocommit, the doomed marker is visible, and the pool reused the backend. The statement-error case stays aborted and passes, on that same backend. Native TX-03 is not run. `DriverManagerDataSource` closes the connection when Spring releases it.
- **Qualifiers:**
  - **"Mechanism not exercised":** Lucid's `pre-commit-probe` passes TX-01A by failing before COMMIT. Django's native TX-01A passes the same way in substance: it rolls back inside the block, and COMMIT is not the statement that ends the transaction. Neither is evidence that the framework reads a ROLLBACK command tag on COMMIT.
  - **"TX-01B.2 not exercised":** the framework adapters observe no channel through which a framework could claim a rollback, so TX-01B.2 was not tested for them.
- **Report time:** where a transaction was still open when the API returned, each FAIL says so, and says whether teardown or later work decided its fate. In TypeORM's TX-02 cases, for example, the transaction was open at report time and rolled back at teardown. SQLAlchemy's rejected-savepoint FAIL is not that ending. The session was idle when the API returned.
- **Controls:** the positive control passes every case it implements. The negative control fails the 17 cases it is built to fail, so the runner detects a known-bad implementation. That includes unsafe connection reuse, which the observer sees server-side: the next unit of work runs inside the failed transaction's own ID. It also includes a write lost with a failed nested scope, a requested isolation level dropped by a plain `BEGIN`, a migration applied twice, and a reversal that leaves history and the database disagreeing. Every control expectation held in each of these runs, so no result was gated.
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
| `adapters/` | One project per adapter. The JavaScript adapters have lockfiles. `node-kit/` is shared by them only. |
| `schema/` | JSON Schemas for a case result and for a run manifest |
| `docs/` | Methodology, specifications, the adapter protocol and provenance |
| `reports/examples/` | Recorded runs: `summary.md`, `run.json` and one JSON file per case |
| `compose.yaml`, `scripts/` | The disposable server; setup |

## Documentation

- `docs/methodology.md`: independent observation, fault categories, commit outcome ambiguity, classification, gates, modes, controls, reproducibility, limitations.
- `docs/specifications.md`: the families and cases.
- `docs/protocol.md`: how an adapter, in any language, talks to the runner.
- `docs/provenance.md`: the experiments PPCS reuses, with versions and how their results compare.
- `CONTRIBUTING.md`: adding an adapter without compromising framework-native semantics.

## License

MIT (`LICENSE`). The frameworks under test are installed from npm, are not vendored, and keep their own licenses.
