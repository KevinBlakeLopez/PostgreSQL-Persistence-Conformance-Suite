# Spring JDBC adapter

Spring Framework 7.0.9 `TransactionTemplate` on `DataSourceTransactionManager`, against the suite's disposable PostgreSQL. Writes use `JdbcTemplate` against the runner's `item` and `uniq` tables. The adapter is a separate Java process. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit, Spring Boot, Hibernate, or JPA.

The outer template keeps the default `PROPAGATION_REQUIRED`. A nested scope is a second `TransactionTemplate` with `PROPAGATION_NESTED`. No custom rollback rule is installed. A normal return from `TransactionTemplate.execute` commits. A `RuntimeException` or `Error` thrown inside the callback is rolled back and rethrown.

Native mode is `DriverManagerDataSource`: a connection is opened for the transaction and closed when Spring releases it. There is no pool. Category C faults are a client-side injection in this process, fired once, before pgjdbc 42.7.14 sends. A top-level `Connection.rollback()` never becomes a `Statement` (`PgConnection.rollback` calls `executeTransactionCommand`), so that call is withheld on the connection method. `ROLLBACK TO SAVEPOINT` is withheld or rewritten on `Connection.rollback(Savepoint)`, before `execSQLUpdate` sends it. A withheld statement raises `SQLException` with no SQLSTATE. A rewritten statement is `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint`, and PostgreSQL answers it.

`TX-03` is not run in native mode. The release probe below is why: this `DataSource` cannot hand a transactionally active connection to later work (`not-applicable-by-design`). The pooled mode is HikariCP 7.1.0 with `maximumPoolSize` 1 and no other pool setting changed. `TX-03` runs only there. Between the units the connection is released through Spring's normal path.

`TX-01B.commit-reply-discarded` is not implemented. See the commit probe below.

## Setup

JDK 21 or newer. The program refuses to start on an older JDK. From this directory:

```sh
mvn -B package
chmod +x run
```

`mvn package` copies the pinned jars into `target/dependency/`. `./run` executes `java` on that classpath. `pnpm run setup` does not build this adapter.

From the repository root, start the suite's disposable PostgreSQL if it is not already up:

```sh
pnpm run pg:up
```

## Run

From the repository root, with `java` on `PATH` pointing at JDK 21 or newer:

```sh
node harness/run.mjs --adapter=spring-jdbc --case=CTL-01,TX-01A,TX-01B,TX-02,TX-03 --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by the `TX-01B` prefix and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-18T16-08-25Z-9b025d`](../../reports/examples/2026-10-18T16-08-25Z-9b025d/summary.md) is the recording. `adapters/spring-jdbc/FINDINGS.md` is the per-case report.

## Commit probe

`TX-01B.commit-reply-discarded` is NOT_RUN. pgjdbc 42.7.14 `PgConnection.commit` calls `executeTransactionCommand(commitQuery)`. That call does not return until `QueryExecutor.execute` returns. The driver sets its transaction state to `IDLE` from the server's `ReadyForQuery`, inside that execute. Closing the socket after `commit()` returns is not this case.

A probe on this server, against the disposable PostgreSQL, called `Connection.commit()` on pgjdbc 42.7.14:

```text
transaction_state_before=OPEN
transaction_state_after=IDLE
commit_returned_while_in_progress=false
```

`commit()` did not return while the driver still reported a transaction in progress. The COMMIT reply had already been applied to the driver's transaction state.

## Release probe

Native `TX-03` is not executed. A probe on this server used `DriverManagerDataSource` and `DataSourceUtils.releaseConnection`. One connection had autocommit turned off and a statement in flight, so a transaction was open. `releaseConnection` closed it. The backend was gone. Two `TransactionTemplate` calls then used different backends, and the first backend was gone when the first call returned:

```text
open_pid=965
open_connection_closed=true
open_pid_present_after_release=false
template1_pid=966
template1_present_after_return=false
template2_pid=967
template_same_backend=false
```

An earlier run of the same probe agreed: the open backend was closed, and the two templates used different backends. `DataSourceTransactionManager.doCleanupAfterCompletion` unbinds the connection holder and then calls `DataSourceUtils.releaseConnection`. After the unbind, `doReleaseConnection` does not see a thread-bound holder, so `doCloseConnection` calls `Connection.close()`. `DriverManagerDataSource.getConnection` opens a new physical connection and does not retain one. A later unit of work cannot be handed the connection that still holds a transaction. That is `not-applicable-by-design` for the native mode. The pooled mode is the configuration that can check the same connection out again.
