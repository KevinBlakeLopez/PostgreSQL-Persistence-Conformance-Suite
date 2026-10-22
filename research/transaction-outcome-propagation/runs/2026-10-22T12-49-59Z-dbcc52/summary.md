# PostgreSQL Transaction Outcome Propagation: Driver and Framework Capability Matrix

TX-01A slice for node-postgres 8.23.1 and TypeORM 1.1.2. Run `2026-10-22T12-49-59Z-dbcc52`.

## Executive summary

This run asks where a caught unique violation, followed by COMMIT, stops matching PostgreSQL. Each subject used a fresh database. A second connection read `pg_xact_status()` and marker visibility. The boundary is computed from those observations.

- **pg-read-tag.** Verified outcome ROLLED_BACK. Driver command tag ROLLBACK (public_return_value). Application REPORTED_ROLLBACK. Boundary **NONE** (HIGH).
- **pg-ignore-tag.** Verified outcome ROLLED_BACK. Driver command tag ROLLBACK (public_return_value). Application REPORTED_SUCCESS. Boundary **APPLICATION** (HIGH).
- **typeorm-transaction.** Verified outcome ROLLED_BACK. Driver command tag ROLLBACK (diagnostic_wrapper). Application REPORTED_SUCCESS. Boundary **FRAMEWORK** (HIGH).

Defect claim: not made. A boundary names the layer where the recorded result stopped matching the verified database outcome.

## Driver capability matrix

Scope: pg.Client public API, taken from the pg-read-tag subject in this run and copied onto the other subjects. Untested capabilities stay UNKNOWN.

| Capability | Verdict | Note |
| --- | --- | --- |
| command_tag | EXPOSED | Client.query('COMMIT') resolved with Result.command "ROLLBACK". The application can read that field on the public result. |
| affected_row_count | EXPOSED | Result.rowCount is a separate field from Result.command. On this COMMIT result it was null. |
| sqlstate | EXPOSED | The error caught from the duplicate insert has code 23505. |
| transaction_status | EXPOSED | Client.getTransactionStatus() returned "E" after the statement error once Client.readyForQuery was true, and "I" after COMMIT. The method returns the ReadyForQuery status byte Client stored. The query promise can reject on ErrorResponse before that byte is updated. |
| connection_failure | UNKNOWN | TX-01A does not drop the connection. Distinguishing connection loss from a server-reported transaction failure was not tested. |
| commit_acknowledgment | EXPOSED | The acknowledgment recorded here is Result.command on the resolved COMMIT query. |
| unknown_commit_outcome | UNKNOWN | TX-01B was not run. Whether this driver can represent an unknown commit without asserting success or failure is UNKNOWN in this inventory. |
| rollback_acknowledgment | UNKNOWN | This scenario sends COMMIT after the statement error. A ROLLBACK command tag was not requested, so rollback acknowledgment was not tested. |
| connection_invalidation | UNKNOWN | Removing an unsafe connection from a pool was not tested. |
| pool_reset | NOT_APPLICABLE | This inventory is pg.Client. Pool reset is not a Client operation. The TypeORM subject uses pg-pool beside the driver, and this scenario does not record a reset statement. |
| savepoint_failure | UNKNOWN | TX-02 was not run. |
| nested_transactions | NOT_APPLICABLE | pg.Client executes the SQL it is given. It has no nested-transaction API of its own, so a nesting guarantee is not a Client capability. |

Evidence subject: `records/pg-read-tag.json`. Driver pg 8.23.1, git 0980cefebe0ae461da8883703be049fe13ca96cf.

## Framework propagation matrix

| Subject | Driver | Server outcome | Driver observation | Framework result | Application result | Boundary |
| --- | --- | --- | --- | --- | --- | --- |
| pg-read-tag | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (public_return_value) | NOT_APPLICABLE | REPORTED_ROLLBACK | NONE |
| pg-ignore-tag | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (public_return_value) | NOT_APPLICABLE | REPORTED_SUCCESS | APPLICATION |
| typeorm-transaction | pg 8.23.1 | ROLLED_BACK; command tag ROLLBACK (INFERRED) | ROLLBACK (diagnostic_wrapper) | REPORTED_SUCCESS | REPORTED_SUCCESS | FRAMEWORK |

## Confirmed false-success cases

### pg-ignore-tag

The application reports success from promise resolution and leaves the exposed Result.command unread. That is application misuse of the driver result. Defect claim: not made.

Boundary: APPLICATION. The driver exposed command tag ROLLBACK on the public query result, and the application reported success.

Verified: pg_xact_status() aborted, marker visible false, xid 33225.

### typeorm-transaction

DataSource.transaction resolved to the callback sentinel. afterTransactionCommit count 1. afterTransactionRollback count 0. The diagnostic wrapper saw command tag ROLLBACK on the pg Result for COMMIT. Installed TypeORM 1.1.2 PostgresQueryRunner.commitTransaction awaits query("COMMIT") and does not inspect Result.command. Defect claim: not made.

Boundary: FRAMEWORK. The independent check found a rollback. The driver exposed command tag ROLLBACK on the query result. The framework reported success, and the application received that success.

Verified: pg_xact_status() aborted, marker visible false, xid 33229.

## Correctly handled cases

- **pg-read-tag.** The subject reads Result.command after Client.query('COMMIT'). The query resolved with command tag ROLLBACK.

## Unknown-outcome cases

This run has no UNKNOWN database outcome. TX-01B, the lost-commit-acknowledgment scenario, was not executed.

## Architectural observations

The three subjects share one driver and one PostgreSQL version. The direct client preserves the rollback when the application reads `Result.command`. The same resolved query is reported as success when that field is ignored. TypeORM’s transaction call is a third path: the diagnostic wrapper saw the driver result, and the framework call’s reported result is recorded above.

That is one stack, not a comparison of abstraction styles. Pool reset, savepoints, and connection loss were not measured here.

## Recommendations for framework maintainers

For TypeORM 1.1.2 on this evidence, `PostgresQueryRunner.commitTransaction` awaits `query("COMMIT")` and continues to `AfterTransactionCommit`. The pg result that call receives has a public `command` field. Two remediations fit this path:

1. After `COMMIT`, inspect `Result.command`. When it is `ROLLBACK`, skip the after-commit signal and surface a rollback to the caller.
2. Return an explicit transaction outcome from the transaction API, using the command tag as the input.

Invalidating the connection is a different remedy. On this path the session was idle after the `ROLLBACK` completion, so the connection was usable again. That does not make the earlier transaction committed.

For application code that calls node-postgres directly, read `Result.command` after `COMMIT`. A resolved promise means the client received ReadyForQuery. The command tag is the completion PostgreSQL sent.

## Source evidence

### pg-read-tag

- runtime: A second connection read pg_xact_status() aborted for xid 33221 and marker visibility false. Session state idle.
- runtime (pg 8.23.1): COMMIT resolved with Result.command ROLLBACK, read by public_return_value.
- source_inspection (pg 8.23.1 lib/result.js Result.addCommandComplete line 38): Result.command is the first token of the command-completion text. Result.rowCount is parsed from the same message into a separate field.
- source_inspection (pg 8.23.1 lib/client.js Client.getTransactionStatus line 795): getTransactionStatus() returns the status byte stored from ReadyForQuery in _handleReadyForQuery.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.commitTransaction line 154): commitTransaction awaits query("COMMIT"), clears the transaction flag, and broadcasts AfterTransactionCommit. The query result is not inspected.
- source_inspection (typeorm 1.1.2 entity-manager/EntityManager.js EntityManager.transaction line 84): transaction() awaits commitTransaction() and returns the callback result when the callback returns.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.query line 213): query() reads raw.command for UPDATE and DELETE row counts. The default path returns raw.rows. commitTransaction ignores that return value.
- runtime (pg-pool 3.14.0): The TypeORM subject sets poolSize 1, which uses pg-pool. Reset behavior was not recorded.

### pg-ignore-tag

- runtime: A second connection read pg_xact_status() aborted for xid 33225 and marker visibility false. Session state idle.
- runtime (pg 8.23.1): COMMIT resolved with Result.command ROLLBACK, read by public_return_value.
- source_inspection (pg 8.23.1 lib/result.js Result.addCommandComplete line 38): Result.command is the first token of the command-completion text. Result.rowCount is parsed from the same message into a separate field.
- source_inspection (pg 8.23.1 lib/client.js Client.getTransactionStatus line 795): getTransactionStatus() returns the status byte stored from ReadyForQuery in _handleReadyForQuery.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.commitTransaction line 154): commitTransaction awaits query("COMMIT"), clears the transaction flag, and broadcasts AfterTransactionCommit. The query result is not inspected.
- source_inspection (typeorm 1.1.2 entity-manager/EntityManager.js EntityManager.transaction line 84): transaction() awaits commitTransaction() and returns the callback result when the callback returns.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.query line 213): query() reads raw.command for UPDATE and DELETE row counts. The default path returns raw.rows. commitTransaction ignores that return value.
- runtime (pg-pool 3.14.0): The TypeORM subject sets poolSize 1, which uses pg-pool. Reset behavior was not recorded.

### typeorm-transaction

- runtime: A second connection read pg_xact_status() aborted for xid 33229 and marker visibility false. Session state idle.
- diagnostic_instrumentation (pg 8.23.1): COMMIT resolved with Result.command ROLLBACK, read by diagnostic_wrapper.
- source_inspection (pg 8.23.1 lib/result.js Result.addCommandComplete line 38): Result.command is the first token of the command-completion text. Result.rowCount is parsed from the same message into a separate field.
- source_inspection (pg 8.23.1 lib/client.js Client.getTransactionStatus line 795): getTransactionStatus() returns the status byte stored from ReadyForQuery in _handleReadyForQuery.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.commitTransaction line 154): commitTransaction awaits query("COMMIT"), clears the transaction flag, and broadcasts AfterTransactionCommit. The query result is not inspected.
- source_inspection (typeorm 1.1.2 entity-manager/EntityManager.js EntityManager.transaction line 84): transaction() awaits commitTransaction() and returns the callback result when the callback returns.
- source_inspection (typeorm 1.1.2 driver/postgres/PostgresQueryRunner.js PostgresQueryRunner.query line 213): query() reads raw.command for UPDATE and DELETE row counts. The default path returns raw.rows. commitTransaction ignores that return value.
- runtime (pg-pool 3.14.0): The TypeORM subject sets poolSize 1, which uses pg-pool. Reset behavior was not recorded.

## Limitations

- No packet capture. The server command tag is inferred from pg Result.command. Result.addCommandComplete stores the first token of the command-completion text.
- TX-01B, TX-02, and TX-03 were not run.
- Connection failure, unknown commit outcome, rollback acknowledgment, connection invalidation, and savepoint failure were not tested.
- The TypeORM command tag is read by a diagnostic wrapper around pg.Client.prototype.query. That wrapper is not a TypeORM API.
- Client.getTransactionStatus() returns the ReadyForQuery status byte the client stored. This run does not capture the ReadyForQuery packet.

## Reproduction

```
node research/transaction-outcome-propagation/experiments/tx01a-pg-typeorm.mjs
```

Server: 18.6 (Debian 18.6-1.pgdg13+2). Image: postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336. Runtime: node v24.14.1.

Regenerate this file from the JSON:

```
node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/2026-10-22T12-49-59Z-dbcc52
```

