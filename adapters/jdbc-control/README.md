# Plain JDBC control

A small application-owned transaction policy on PostgreSQL JDBC 42.7.14. Java 21. No Spring, Hibernate, JPA, jOOQ, HikariCP, or other pool. The adapter speaks PPCS adapter protocol version 1 on stdin and stdout. Writes use `PreparedStatement` against the runner's `item` and `uniq` tables.

`correct` is the positive control. `unsafe` is the negative control. The two completion paths are separate classes. The manifest kinds are `native` and `configured`, not `control`: an adapter whose every mode is `control` is scheduled beside every other adapter and, if it states `expectations`, becomes a case-control gate. This adapter does not replace `pg-control`.

## Setup

JDK 21 or newer. The program refuses to start on an older JDK. From this directory:

```sh
mvn -B package
chmod +x run
```

`mvn package` copies `postgresql-42.7.14.jar` into `target/dependency/`. `./run` executes `java` on that classpath. `pnpm run setup` does not build this adapter. `java` on `PATH` must be JDK 21 or newer.

From the repository root, start the suite's disposable PostgreSQL if it is not already up:

```sh
pnpm run pg:up
```

## Run

From the repository root:

```sh
node harness/run.mjs --adapter=jdbc-control --case=CTL-01,TX-01,TX-02,TX-03,TX-04,TX-05,MG-02,MG-03 --repeat=3
```

`pg-control` runs beside the scenario cases, because it is the suite's case control. `TX-01B.commit-reply-discarded` is selected by the `TX-01` prefix and recorded as NOT_RUN.

The run [`reports/examples/2026-10-19T12-51-00Z-0a0698`](../../reports/examples/2026-10-19T12-51-00Z-0a0698/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) is the per-case report.

A separate probe, not a PPCS case, prints what `Connection.commit()` and `Connection.setAutoCommit(true)` do on this server. It checks `cluster_name` against `.ppcs-instance.json`, creates `ppcs_jdbc_probe`, and drops that database:

```sh
java -cp "target/classes:target/dependency/*" org.ppcs.jdbccontrol.Probe ../../.ppcs-instance.json
```

## Modes

| | `correct` | `unsafe` |
| --- | --- | --- |
| `Connection.commit()` returns and the driver state was `OPEN` | `committed` | `committed` |
| driver state was `FAILED` before `commit()` | `rolled_back` after `commit()` returns | `committed` |
| `commit()` throws | `failed`, connection closed | `rolled_back` |
| `rollback(Savepoint)` throws | outer `Connection.rollback()`, not `commit()` | `commit()` anyway |
| `rollback()` throws | connection closed; `setAutoCommit` is not called | `setAutoCommit(true)`, connection kept |
| requested isolation | `setTransactionIsolation` before `setAutoCommit(false)` | not called |
| write before a savepoint | sent before `setSavepoint` | sent inside the savepoint |

`FAILED` is `PgConnection.getTransactionState()`. pgjdbc 42.7.14 sets it from PostgreSQL's `ReadyForQuery` status `E`. `Connection.commit()` is void and does not return a command tag.

## Cases

| Case | `correct` | `unsafe` |
| --- | --- | --- |
| `CTL-01.commit`, `CTL-01.rollback` | PASS | PASS |
| `TX-01A.caught-error-then-commit` | PASS, mechanism exercised | FAIL |
| `TX-01B.conn-lost-before-commit` | PASS | PASS |
| `TX-01B.commit-reply-discarded` | NOT_RUN | |
| `TX-02.savepoint-rollback-not-sent` | PASS | FAIL |
| `TX-02.savepoint-rollback-rejected` | PASS | FAIL |
| `TX-02.conn-lost-before-savepoint-rollback` | PASS | PASS |
| `TX-03.rollback-not-sent` | PASS | FAIL |
| `TX-03.statement-error-rollback-not-sent` | PASS | PASS |
| `TX-03.conn-lost-in-transaction` | PASS | FAIL |
| `TX-04.nested-failure-contained` | PASS | FAIL |
| `TX-04.nested-released-outer-rollback` | PASS | PASS |
| `TX-04.independent-inner` | UNSUPPORTED, not applicable by design | |
| `TX-05.managed-serializable`, `TX-05.explicit-serializable` | PASS | FAIL |
| `MG-02.*`, `MG-03.*` | UNSUPPORTED, capability absent | |

Both TX-05 cases use the same calls. JDBC has no second transaction-handle type.

## Fault injection

Category B is the runner's `pg_terminate_backend`. Category A is the fixture's unique violation.

Category C is a client-side injection in this process, fired once, before pgjdbc sends. A JDK proxy implements `java.sql.Connection`. It does not wrap statements and does not intercept `commit()` or `setAutoCommit`.

- Top-level `ROLLBACK` is withheld on `Connection.rollback()`. `PgConnection.rollback` calls `executeTransactionCommand`, not `Statement.execute`, so a statement hook would not see it.
- `ROLLBACK TO SAVEPOINT` is withheld or rewritten on `Connection.rollback(Savepoint)`, before `execSQLUpdate`. The rewrite is `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint`, executed on the raw connection. PostgreSQL's reply is recorded. In this run the reply code was `3B001`.
- `after-fault` is sent from the proxy after the withhold, or after the rewritten statement's reply, and before the policy sees the exception.

No private pgjdbc field is read or written. `PgConnection.getTransactionState()` is a public method on the driver class. The correct policy calls it. The unsafe policy does not.

Category D is not implemented. See the commit probe in `FINDINGS.md`.

These injections show what the policy does if the failure happens. They do not show how often it happens.

## Connection lifecycle

`DriverManager.getConnection` once. There is no pool. The holder keeps that connection until `correct` closes it or the process exits.

`correct` closes the connection when `Connection.rollback()` throws or `Connection.commit()` throws. The next unit calls `getConnection` again. That is disposal. It is not evidence that a pool would recover the same physical connection.

`unsafe` calls `Connection.setAutoCommit(true)` after a thrown `rollback()` and returns the same connection. On this driver, `PgConnection.setAutoCommit(true)` calls `commit()` when auto-commit is off. Java 21's `Connection.setAutoCommit` says that changing auto-commit during a transaction commits that transaction.

A successful `commit()` does not restore auto-commit. Restoring it would call `commit()` again when the driver state is not `IDLE`. The connection stays open until `after-end`, then the process closes it.

## Known limitations

- `Connection.commit()` does not expose PostgreSQL's command tag. `TransactionCommandHandler` does not implement `handleCommandStatus`. A `COMMIT` that PostgreSQL answers with `ROLLBACK` does not throw. After the call, `getTransactionState()` is `IDLE` for both a commit and that rollback.
- `Statement.execute("COMMIT")` stores an update count of 0 and no warning. It does not expose the tag either. The policy does not use it.
- `TX-01B.commit-reply-discarded` is NOT_RUN. `commit()` does not return until `ReadyForQuery` has set the driver to `IDLE`.
- TX-03 on this adapter exercises one held connection. It does not exercise pool validation, eviction, or HikariCP.
- JDBC has no `REQUIRES_NEW` and no migration runner. Those cases are declared in the manifest, not skipped at run time.
