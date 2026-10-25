# PostgreSQL Transaction Outcome Propagation: Driver and Framework Capability Matrix

TX-01A.caught-error-then-commit for pg 8.23.1. Frameworks: knex,kysely,drizzle-orm,@prisma/client 3.3.0, 0.29.6, 0.45.4, 7.10.1. Run `2026-10-22T13-39-52Z-a7324c`.

## Executive summary

Each subject used a fresh database. A second connection read `pg_xact_status()` and marker visibility. The boundary is computed from those observations. `client_knowledge` UNKNOWN means the client did not receive the acknowledgment; the observer may still know the database outcome.

- **tx01a-drizzle** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (diagnostic_wrapper). Application REPORTED_SUCCESS. Boundary **FRAMEWORK** (HIGH).
- **tx01a-knex** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (diagnostic_wrapper). Application REPORTED_SUCCESS. Boundary **FRAMEWORK** (HIGH).
- **tx01a-kysely** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (diagnostic_wrapper). Application REPORTED_SUCCESS. Boundary **FRAMEWORK** (HIGH).
- **tx01a-prisma** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (diagnostic_wrapper). Application REPORTED_SUCCESS. Boundary **FRAMEWORK** (HIGH).

Defect claim: not made. A boundary names the layer where the recorded result stopped matching the verified database outcome.

## Driver capability matrix

Scope: Command-tag exposure is on each framework record. This file is the shared pg driver.

| Capability | Verdict | Note |
| --- | --- | --- |
| command_tag | EXPOSED | pg Result.command, observed through the wrapper on each framework's pg module when COMMIT completed. |
| affected_row_count | UNKNOWN | This scenario did not establish this capability. |
| sqlstate | UNKNOWN | This scenario did not establish this capability. |
| transaction_status | UNKNOWN | This scenario did not establish this capability. |
| connection_failure | UNKNOWN | This scenario did not establish this capability. |
| commit_acknowledgment | EXPOSED | The same Result.command field. |
| unknown_commit_outcome | UNKNOWN | This scenario did not establish this capability. |
| rollback_acknowledgment | UNKNOWN | This scenario did not establish this capability. |
| connection_invalidation | UNKNOWN | This scenario did not establish this capability. |
| pool_reset | UNKNOWN | This scenario did not establish this capability. |
| savepoint_failure | UNKNOWN | This scenario did not establish this capability. |
| nested_transactions | UNKNOWN | This scenario did not establish this capability. |

Evidence subject: `records/tx01a-knex.json`. Driver pg 8.23.1, git 0980cefebe0ae461da8883703be049fe13ca96cf.

## Framework propagation matrix

| Subject | Driver | Server outcome | Driver observation | Framework result | Application result | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
| tx01a-drizzle | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (diagnostic_wrapper) | REPORTED_SUCCESS | REPORTED_SUCCESS | FRAMEWORK |
| tx01a-knex | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (diagnostic_wrapper) | REPORTED_SUCCESS | REPORTED_SUCCESS | FRAMEWORK |
| tx01a-kysely | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (diagnostic_wrapper) | REPORTED_SUCCESS | REPORTED_SUCCESS | FRAMEWORK |
| tx01a-prisma | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (diagnostic_wrapper) | REPORTED_SUCCESS | REPORTED_SUCCESS | FRAMEWORK |

## Confirmed false-success cases

### tx01a-drizzle

drizzle-orm 0.45.4 calls db.transaction(callback). The pg result of COMMIT is recorded by the wrapper, not by the framework return value. Defect claim: not made.

Boundary: FRAMEWORK. The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.

Verified: pg_xact_status() aborted, marker visible false, xid 37339.

### tx01a-knex

knex 3.3.0 calls knex.transaction(callback). The pg result of COMMIT is recorded by the wrapper, not by the framework return value. Defect claim: not made.

Boundary: FRAMEWORK. The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.

Verified: pg_xact_status() aborted, marker visible false, xid 37331.

### tx01a-kysely

kysely 0.29.6 calls db.transaction().execute(callback). The pg result of COMMIT is recorded by the wrapper, not by the framework return value. Defect claim: not made.

Boundary: FRAMEWORK. The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.

Verified: pg_xact_status() aborted, marker visible false, xid 37335.

### tx01a-prisma

@prisma/client 7.10.1 calls prisma.$transaction(callback). The pg result of COMMIT is recorded by the wrapper, not by the framework return value. @prisma/adapter-pg 7.10.1 executes COMMIT. PgQueryable.executeRaw returns rowCount. Defect claim: not made.

Boundary: FRAMEWORK. The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.

Verified: pg_xact_status() aborted, marker visible false, xid 37343.

## Correctly handled cases

No subject preserved the verified outcome.

## Unknown-outcome cases

This run has no UNKNOWN database outcome. TX-01B, the lost-commit-acknowledgment scenario, was not executed.

## Architectural observations

The three subjects share one driver and one PostgreSQL version. The direct client preserves the rollback when the application reads `Result.command`. The same resolved query is reported as success when that field is ignored. TypeORM’s transaction call is a third path: the diagnostic wrapper saw the driver result, and the framework call’s reported result is recorded above.

That is one stack, not a comparison of abstraction styles. Pool reset, savepoints, and connection loss were not measured here.

## Recommendations for framework maintainers

No framework false-success row is in this run, so this report does not recommend a TypeORM code change from these records.

For application code that calls node-postgres directly, read `Result.command` after `COMMIT`. A resolved promise means the client received ReadyForQuery. The command tag is the completion PostgreSQL sent.

## Source evidence

### tx01a-drizzle

- diagnostic_instrumentation (pg 8.23.1): pg_xact_status() aborted, marker visible false, session idle. begin [resolved BEGIN]; commit [resolved ROLLBACK]

### tx01a-knex

- diagnostic_instrumentation (pg 8.23.1): pg_xact_status() aborted, marker visible false, session idle. BEGIN; [resolved BEGIN]; COMMIT; [resolved ROLLBACK]

### tx01a-kysely

- diagnostic_instrumentation (pg 8.23.1): pg_xact_status() aborted, marker visible false, session idle. begin [resolved BEGIN]; commit [resolved ROLLBACK]

### tx01a-prisma

- diagnostic_instrumentation (pg 8.23.1): pg_xact_status() aborted, marker visible false, session idle. BEGIN [resolved BEGIN]; COMMIT [resolved ROLLBACK]

## Limitations

- Drizzle 1.0.0-rc.4 was not repeated. The suite already recorded the same TX-01A shape for 0.45.4 and the release candidate.
- Lucid and MikroORM are not separate rows. Knex and Kysely are the libraries those adapters place on pg.
- No packet capture. The server command tag is inferred from Result.command.
- psycopg, asyncpg, pgjdbc, and Npgsql were not run.

## Reproduction

```
node research/transaction-outcome-propagation/experiments/pg-frameworks.mjs
```

Server: 18.6 (Debian 18.6-1.pgdg13+2). Image: postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336. Runtime: node v24.14.1.

Regenerate this file from the JSON:

```
node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/2026-10-22T13-39-52Z-a7324c
```

