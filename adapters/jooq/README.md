# jOOQ adapter

jOOQ Open Source Edition 3.21.9 on the suite's disposable PostgreSQL. The question is whether jOOQ's SQL DSL changes PostgreSQL transaction outcomes relative to JDBC, Spring, and Hibernate. The adapter drives `DSLContext.transaction` in `native`, and the same DSL statements under application-owned `Connection.commit` in `jdbc`. It does not answer that question in advance. The recorded run is [`reports/examples/2026-10-22T12-58-46Z-d4a7fc`](../../reports/examples/2026-10-22T12-58-46Z-d4a7fc/summary.md). The per-case report is [`FINDINGS.md`](FINDINGS.md). The comparison with the other JVM adapters is [`JVM-COMPARISON.md`](JVM-COMPARISON.md).

The dependency is `org.jooq:jooq:3.21.9` from Maven Central. That is the Open Source Edition. jOOQ 3.21's open-source line is Java 21, and its open-source PostgreSQL dialect minimum is PostgreSQL 18. This suite's server is PostgreSQL 18.6. The PostgreSQL JDBC driver is 42.7.14, the same pin as the other JVM adapters. HikariCP 7.1.0 is used only for TX-03. There is no commercial jOOQ artifact, no license key, and no generated catalog. Tables are the runner's `item` and `uniq` fixture, addressed with `DSL.table` and `DSL.field`.

`DefaultTransactionProvider` is the provider `Configuration.transactionProvider()` installs when none was set. Nested transactions are JDBC savepoints (`nested()` is true). `DSLContext.transaction` commits when the callback returns and rolls back when the callback throws. The JDBC-owned mode does not call `transaction()`.

## Modes

| Mode | Kind | What it does |
| --- | --- | --- |
| `native` | native | `DSL.using(DataSource, SQLDialect.POSTGRES)` and `DSLContext.transaction`. `DriverManager` connections. No pool. |
| `jdbc` | native | The same DataSource and the same DSL writes. `Connection.setAutoCommit(false)`, then `Connection.commit` or `Connection.rollback`. Nested work is `Connection.setSavepoint`. |
| `pooled` | configured | `native` on HikariCP 7.1.0, `maximumPoolSize` 1. TX-03 only, plus the CTL-01 gate. |
| `jdbc-pooled` | configured | `jdbc` on that same pool. TX-03 only, plus the CTL-01 gate. |

`TX-05.explicit-serializable` runs in `jdbc` only. `transaction()` does not return a handle. `TX-04.independent-inner` is unsupported, not applicable by design. MG-02 and MG-03 are unsupported, capability absent. `org.jooq.Migrations` is in the 3.21.9 jar and is not driven here. `TX-01B.commit-reply-discarded` is NOT_RUN.

Category C faults are a client-side injection in this process, fired once, before pgjdbc 42.7.14 sends. `PgConnection.rollback()` and `PgConnection.commit()` do not become statements. The top-level withhold is on `Connection.rollback()`. `ROLLBACK TO SAVEPOINT` is withheld or rewritten on `Connection.rollback(Savepoint)`.

## Setup

JDK 21 or newer. jOOQ 3.21.9's open-source build is Java 21. The program refuses to start on an older JDK. The recorded run used Java 27, which can run that bytecode. From this directory:

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
node harness/run.mjs --adapter=jooq --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by the `TX-01B` prefix and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

One case:

```sh
node harness/run.mjs --adapter=jooq --mode=native --case=TX-01A.caught-error-then-commit
```

The evidence is `results/<run id>/`. The checked-in recording is [`reports/examples/2026-10-22T12-58-46Z-d4a7fc`](../../reports/examples/2026-10-22T12-58-46Z-d4a7fc/summary.md).

## Probe

`org.ppcs.jooq.Probe` is not a catalog case. It refuses a server whose `cluster_name` is not the instance token, creates `ppcs_jooq_probe`, and drops it. From this directory, after `mvn -B package`:

```sh
java -Dorg.jooq.no-logo=true -cp "target/classes:target/dependency/*" org.ppcs.jooq.Probe ../../.ppcs-instance.json
```

It prints the caught-callback path, the escaping-callback path, `Statement.execute("COMMIT")` on an aborted transaction, isolation set before `setAutoCommit(false)`, and isolation set after a statement has opened the transaction. The output quoted in `FINDINGS.md` is from that command on 2026-10-22, against the same disposable PostgreSQL 18.6, jOOQ 3.21.9, pgjdbc 42.7.14, and Java 27.

## Draft

[`upstream-draft.md`](upstream-draft.md) is not filed. It is not approved to file. pgjdbc#4494 is already open. Do not open a second pgjdbc issue.
