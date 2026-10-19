# Spring transaction management

Spring Framework 7.0.9 transaction management on `DataSourceTransactionManager` and PostgreSQL JDBC 42.7.14. Writes are `PreparedStatement` calls on the connection from `DataSourceUtils.getConnection`. `JdbcTemplate` is not used. There is no Spring Boot, Hibernate, or JPA.

The adapter is `adapters/spring-tx`. It speaks PPCS adapter protocol version 1. `native` and `pooled` call `TransactionTemplate`. `declarative` and `declarative-pooled` call a JDK proxy advised by `TransactionInterceptor`. The proxy is the only object the case code calls.

## Versions

| Component | Version |
| --- | --- |
| Java | 21.0.12.1 |
| Spring Framework | 7.0.9 (`spring-tx`, `spring-jdbc`, `spring-aop`, `spring-context`, `spring-beans`, `spring-core`, `spring-expression`) |
| PostgreSQL JDBC | 42.7.14 |
| HikariCP | 7.1.0, pooled modes only |
| PostgreSQL | 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`) |
| Maven | 3.10.0, compiler plugin 3.14.0, dependency plugin 3.8.1 |

Resolved with the Spring Framework 7.0.9 BOM. Other runtime jars: `commons-logging` 1.3.5, `jspecify` 1.0.0, `micrometer-observation` 1.16.7, `micrometer-commons` 1.16.7, `checker-qual` 3.55.1, `slf4j-api` 2.0.17. No SLF4J provider is installed. stderr prints the SLF4J warning. It is not an outcome.

The repository already runs Spring JDBC at 7.0.9 on Java 21. This adapter uses that pin. `spring-context` is on the classpath because `TransactionInterceptor` references `ApplicationEventPublisherAware`. No `ApplicationContext` is created.

The manager is constructed with `new DataSourceTransactionManager(dataSource)` and no setters. The hello message records the values that constructor leaves: `nestedTransactionAllowed` true, `rollbackOnCommitFailure` false, `globalRollbackOnParticipationFailure` true, `failEarlyOnGlobalRollbackOnly` false, `transactionSynchronization` `SYNCHRONIZATION_ALWAYS`.

## Setup

JDK 21 or newer. From this directory:

```sh
mvn -B package
chmod +x run
```

`mvn package` copies the pinned jars into `target/dependency/`. `./run` executes `java` on that classpath. `pnpm run setup` does not build this adapter. `java` on `PATH` must be JDK 21 or newer.

From the repository root, with the disposable PostgreSQL up:

```sh
node harness/run.mjs --adapter=spring-tx --repeat=3
```

The run [`reports/examples/2026-10-19T15-02-38Z-8a2f4d`](../../reports/examples/2026-10-19T15-02-38Z-8a2f4d/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) is the per-case report.

A separate probe, not a PPCS case, prints the lifecycle observations below. It checks `cluster_name` against `.ppcs-instance.json`, creates `ppcs_springtx_probe`, and drops that database:

```sh
java -cp "target/classes:target/dependency/*" org.ppcs.springtx.Probe ../../.ppcs-instance.json
```

## Transaction paths

Programmatic:

`TransactionTemplate.execute` calls `PlatformTransactionManager.getTransaction`, runs the callback, and calls `commit` only when the callback returns. On a `RuntimeException` or `Error` it rolls back and rethrows that throwable. If rollback throws `TransactionSystemException`, that exception replaces the callback throwable and `initApplicationException` stores the original (`TransactionTemplate.rollbackOnException`, 7.0.9).

`DataSourceTransactionManager.doBegin` calls `DataSourceUtils.prepareConnectionForTransaction` and then, if autocommit is on, `Connection.setAutoCommit(false)`. `doCommit` calls `Connection.commit`. `doRollback` calls `Connection.rollback`. A nested transaction rolls back through `AbstractTransactionStatus.rollbackToHeldSavepoint`, which calls `Connection.rollback(Savepoint)`. `doCleanupAfterCompletion` unbinds the holder, and if it had turned autocommit off, calls `Connection.setAutoCommit(true)`, then `DataSourceUtils.releaseConnection`.

Declarative:

A JDK proxy invokes `TransactionInterceptor`. `TransactionAspectSupport.completeTransactionAfterThrowing` calls `rollback` when `rollbackOn` is true, and `commit` when it is false. With no `rollbackFor` rules, that is true for `RuntimeException` and `Error` only. The 7.0.9 reference, Rolling Back a Declarative Transaction, states that default. After completion, the interceptor rethrows the original throwable unless rollback or commit threw `TransactionSystemException`, which replaces it.

`PROPAGATION_NESTED` is a JDBC savepoint on this manager. `PROPAGATION_REQUIRES_NEW` suspends the outer connection and opens another. The adapter does not substitute one for the other.

`Connection.commit()` is void. pgjdbc 42.7.14 `TransactionCommandHandler` does not implement `handleCommandStatus`. A `COMMIT` that PostgreSQL answers with the command tag `ROLLBACK` does not throw. The probe read `PgConnection.getTransactionState()` `FAILED` before a normal `TransactionTemplate` return, and `execute` threw nothing. PostgreSQL's fate, read on another connection, was `aborted`.

## Modes

| Mode | Kind | What it changes |
| --- | --- | --- |
| `native` | native | `TransactionTemplate`, `DriverManagerDataSource`, no pool |
| `declarative` | native | `@Transactional` through `TransactionInterceptor`, same `DataSource` |
| `pooled` | configured | `TransactionTemplate`, HikariCP 7.1.0, `maximumPoolSize` 1. TX-03 only |
| `declarative-pooled` | configured | `@Transactional`, same pool. TX-03 only. The statement-error case uses `rollbackFor = Exception.class` |

`TX-05.explicit-serializable` runs only in `native`. It calls `PlatformTransactionManager.getTransaction` and `commit`. `@Transactional` does not return a handle.

`TX-03` is not run on `DriverManagerDataSource`. The release probe closed an open connection and the next two templates used different backends (`238509` and `238510`). A later unit cannot be handed the connection that still holds a transaction.

## Faults

Category A is the fixture's unique violation. Category B is the runner's `pg_terminate_backend`. Category C is a client-side injection in this process, fired once, before pgjdbc sends. `Connection.commit` and `Connection.setAutoCommit` are not intercepted.

- A withhold on `Connection.rollback()` or `Connection.rollback(Savepoint)` throws before the command reaches PostgreSQL. That is not a rollback PostgreSQL executed.
- A rewrite sends `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint` on the raw connection and records PostgreSQL's reply. In this run the reply was `3B001`. That is not a command that never left the client.

`after-fault` is sent from that layer, after the withhold or after the reply, before Spring sees the exception. Each recorded category C case fired once, and the runner's server-side signature held.

Category D is not implemented. The commit probe:

```text
commit_state_before=OPEN
commit_state_after=IDLE
commit_returned_while_in_progress=false
```

`commit()` did not return while the driver still reported a transaction in progress. `TX-01B.commit-reply-discarded` is NOT_RUN. Closing the socket after `commit()` returns is not that case.

## What the recording covers

[`FINDINGS.md`](FINDINGS.md) is the case table, the comparison with plain JDBC and Spring JDBC, and the probes that are not catalog cases. Four catalog invariants fail, in both invocation modes: `TX-01A.caught-error-then-commit`, both client-side TX-02 cases, and pooled `TX-03.rollback-not-sent`. Declarative matched programmatic on every case both modes ran. `TX-04` and `TX-05` pass, including `PROPAGATION_REQUIRES_NEW`. `TX-01B.commit-reply-discarded` is NOT_RUN. MG-02 and MG-03 are capability-absent.

A normal return from the boundary is the report `committed`. It is not, by itself, evidence that PostgreSQL committed. The suite reads `pg_xact_status()` and marker visibility on another connection.
