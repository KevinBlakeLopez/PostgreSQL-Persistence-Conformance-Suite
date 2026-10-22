# PostgreSQL Transaction Outcome Propagation: Driver and Framework Capability Matrix

TX-01A slice for node-postgres 8.23.1 and TypeORM 1.1.2. Run `2026-10-22T13-21-12Z-af4ba2`.

## Executive summary

Each subject used a fresh database. A second connection read `pg_xact_status()` and marker visibility. The boundary is computed from those observations. `client_knowledge` UNKNOWN means the client did not receive the acknowledgment; the observer may still know the database outcome.

- **tx01a-php-pdo** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag NOT_EXPOSED. Application REPORTED_SUCCESS. Boundary **DRIVER** (MEDIUM).
- **tx01a-ruby-pg** (TX-01A.caught-error-then-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (public_return_value). Application REPORTED_ROLLBACK. Boundary **NONE** (HIGH).
- **tx01b-unseen-pg** (TX-01B.commit-reply-unseen). Verified outcome COMMITTED, client UNKNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **NONE** (HIGH).
- **tx01b-unseen-typeorm** (TX-01B.commit-reply-unseen). Verified outcome COMMITTED, client UNKNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **NONE** (HIGH).
- **tx01b-conn-lost-pg** (TX-01B.conn-lost-before-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **NONE** (HIGH).
- **tx01b-conn-lost-typeorm** (TX-01B.conn-lost-before-commit). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **NONE** (HIGH).
- **tx02-rejected-pg** (TX-02.savepoint-rollback-rejected). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag ROLLBACK (public_return_value). Application REPORTED_ROLLBACK. Boundary **NONE** (HIGH).
- **tx02-rejected-typeorm** (TX-02.savepoint-rollback-rejected). Verified outcome UNKNOWN, client KNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **UNDETERMINED** (LOW).
- **tx03-rollback-not-sent-pg** (TX-03.rollback-not-sent). Verified outcome ROLLED_BACK, client KNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **NONE** (HIGH).
- **tx03-rollback-not-sent-typeorm** (TX-03.rollback-not-sent). Verified outcome COMMITTED, client KNOWN. Driver command tag NOT_OBSERVED. Application REPORTED_FAILURE. Boundary **FRAMEWORK** (HIGH).

Defect claim: not made. A boundary names the layer where the recorded result stopped matching the verified database outcome.

## Driver capability matrix

Scope: Per-scenario capabilities are on each record. This file is only an index.

| Capability | Verdict | Note |
| --- | --- | --- |
| command_tag | UNKNOWN | This scenario did not establish this capability. |
| affected_row_count | UNKNOWN | This scenario did not establish this capability. |
| sqlstate | UNKNOWN | This scenario did not establish this capability. |
| transaction_status | UNKNOWN | This scenario did not establish this capability. |
| connection_failure | UNKNOWN | This scenario did not establish this capability. |
| commit_acknowledgment | UNKNOWN | This scenario did not establish this capability. |
| unknown_commit_outcome | UNKNOWN | This scenario did not establish this capability. |
| rollback_acknowledgment | UNKNOWN | This scenario did not establish this capability. |
| connection_invalidation | UNKNOWN | This scenario did not establish this capability. |
| pool_reset | UNKNOWN | This scenario did not establish this capability. |
| savepoint_failure | UNKNOWN | This scenario did not establish this capability. |
| nested_transactions | UNKNOWN | This scenario did not establish this capability. |

Evidence subject: `records/`. Driver mixed see records, git not recorded.

## Framework propagation matrix

| Subject | Driver | Server outcome | Driver observation | Framework result | Application result | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
| tx01a-php-pdo | pdo_pgsql 8.5.12 | ROLLED_BACK; command tag none (NOT_OBSERVED) | NOT_EXPOSED | NOT_APPLICABLE | REPORTED_SUCCESS | DRIVER |
| tx01a-ruby-pg | pg 1.7.0 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (public_return_value) | NOT_APPLICABLE | REPORTED_ROLLBACK | NONE |
| tx01b-unseen-pg | pg 8.23.1 | COMMITTED; command tag none (NOT_OBSERVED) | NOT_OBSERVED | NOT_APPLICABLE | REPORTED_FAILURE | NONE |
| tx01b-unseen-typeorm | pg 8.23.1 | COMMITTED; command tag none (NOT_OBSERVED) | NOT_OBSERVED | REPORTED_FAILURE | REPORTED_FAILURE | NONE |
| tx01b-conn-lost-pg | pg 8.23.1 | ROLLED_BACK; command tag none (NOT_OBSERVED) | NOT_OBSERVED | NOT_APPLICABLE | REPORTED_FAILURE | NONE |
| tx01b-conn-lost-typeorm | pg 8.23.1 | ROLLED_BACK; command tag none (NOT_OBSERVED) | NOT_OBSERVED | REPORTED_FAILURE | REPORTED_FAILURE | NONE |
| tx02-rejected-pg | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (public_return_value) | NOT_APPLICABLE | REPORTED_ROLLBACK | NONE |
| tx02-rejected-typeorm | pg 8.23.1 | UNKNOWN; command tag none (NOT_OBSERVED) | NOT_OBSERVED | REPORTED_FAILURE | REPORTED_FAILURE | UNDETERMINED |
| tx03-rollback-not-sent-pg | pg 8.23.1 | ROLLED_BACK; command tag none (NOT_OBSERVED) | NOT_OBSERVED | NOT_APPLICABLE | REPORTED_FAILURE | NONE |
| tx03-rollback-not-sent-typeorm | pg 8.23.1 | COMMITTED; command tag none (NOT_OBSERVED) | NOT_OBSERVED | REPORTED_FAILURE | REPORTED_FAILURE | FRAMEWORK |

## Confirmed false-success cases

### tx01a-php-pdo

pdo_pgsql does not expose PQcmdStatus. A true return is the only success signal this call gives. This run does not capture the protocol message libpq parsed.

Boundary: DRIVER. The independent check found a rollback and the application reported success. The examined driver API does not expose the command tag. This input does not show the protocol message itself.

Verified: pg_xact_status() aborted, marker visible false, xid 35464.

## Correctly handled cases

- **tx01a-ruby-pg.** PG::Result#cmd_status was ROLLBACK. transaction_status was 0.
- **tx01b-unseen-pg.** The ending call rejected after the proxy dropped the COMMIT reply: Connection terminated unexpectedly
- **tx01b-unseen-typeorm.** The ending call rejected after the proxy dropped the COMMIT reply: Connection terminated unexpectedly
- **tx01b-conn-lost-pg.** Client.query('COMMIT') rejected: Client has encountered a connection error and is not queryable
- **tx01b-conn-lost-typeorm.** DataSource.transaction threw: Query runner already released. Cannot run queries anymore.
- **tx02-rejected-pg.** The subject reads Result.command after the rejected savepoint rollback. Inner marker visible false.
- **tx03-rollback-not-sent-pg.** ROLLBACK was rejected before send. Before the client closed, session state was idle in transaction and fate was in progress.

## Unknown-outcome cases

- **tx02-rejected-typeorm.** Verified outcome UNKNOWN. Application REPORTED_FAILURE.

## Architectural observations

The three subjects share one driver and one PostgreSQL version. The direct client preserves the rollback when the application reads `Result.command`. The same resolved query is reported as success when that field is ignored. TypeORM’s transaction call is a third path: the diagnostic wrapper saw the driver result, and the framework call’s reported result is recorded above.

That is one stack, not a comparison of abstraction styles. Pool reset, savepoints, and connection loss were not measured here.

## Recommendations for framework maintainers

No framework false-success row is in this run, so this report does not recommend a TypeORM code change from these records.

For application code that calls node-postgres directly, read `Result.command` after `COMMIT`. A resolved promise means the client received ReadyForQuery. The command tag is the completion PostgreSQL sent.

## Source evidence

### tx01a-php-pdo

- runtime: pg_xact_status() aborted, marker visible false, session absent, xid 35464.

### tx01a-ruby-pg

- runtime: pg_xact_status() aborted, marker visible false, session absent, xid 35468.

### tx01b-unseen-pg

- runtime: pg_xact_status() committed, marker visible true, session absent, xid 35438.

### tx01b-unseen-typeorm

- runtime: pg_xact_status() committed, marker visible true, session absent, xid 35442.

### tx01b-conn-lost-pg

- runtime: pg_xact_status() aborted, marker visible false, session absent, xid 35430.

### tx01b-conn-lost-typeorm

- runtime: pg_xact_status() aborted, marker visible false, session absent, xid 35434.

### tx02-rejected-pg

- runtime: pg_xact_status() aborted, marker visible false, session idle, xid 35446.

### tx02-rejected-typeorm

- runtime: pg_xact_status() in progress, marker visible false, session idle in transaction, xid 35451.

### tx03-rollback-not-sent-pg

- runtime: pg_xact_status() aborted, marker visible false, session idle in transaction, xid 35456.

### tx03-rollback-not-sent-typeorm

- runtime: pg_xact_status() committed, marker visible true, session idle, xid 35460.

## Limitations

- Java and .NET are not installed in this environment, so pgjdbc and Npgsql were not executed.
- The system Python has no psycopg module, so psycopg was not executed.
- No packet capture. A server command tag is inferred only when a driver command tag was observed.
- TX-02's missing savepoint name and TX-03's withheld ROLLBACK are client-side injections.
- TX-01B.commit-reply-unseen uses harness/lib/pg-wire-proxy.mjs unchanged.

## Reproduction

```
node research/transaction-outcome-propagation/experiments/followups.mjs
```

Server: 18.6 (Debian 18.6-1.pgdg13+2). Image: postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336. Runtime: node v24.14.1.

Regenerate this file from the JSON:

```
node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/2026-10-22T13-21-12Z-af4ba2
```

