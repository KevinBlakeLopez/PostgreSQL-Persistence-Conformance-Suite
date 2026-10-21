# Hibernate ORM

Native Hibernate ORM 7.4.13.Final on PostgreSQL JDBC 42.7.14. The adapter opens a `Session`, calls `beginTransaction`, and calls `Transaction.commit`. There is no Spring, no `EntityManagerFactory` bootstrap, and no migration tool.

The recording is [`reports/examples/2026-10-21T15-45-57Z-c3c03b`](../../reports/examples/2026-10-21T15-45-57Z-c3c03b/summary.md). [`FINDINGS.md`](FINDINGS.md) is the per-case report.

## Versions

| Component | Version |
| --- | --- |
| Java | 21.0.12.1 |
| Hibernate ORM | 7.4.13.Final (`hibernate-core`) |
| Jakarta Persistence | 3.2.0 |
| PostgreSQL JDBC | 42.7.14 |
| HikariCP | 7.1.0, pooled mode only |
| PostgreSQL | 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`) |
| Maven | compiler plugin 3.14.0, dependency plugin 3.8.1 |

`hibernate-core` also brings `jboss-logging` 3.6.1.Final, `hibernate-models` 1.1.2, `byte-buddy` 1.18.14, `antlr4-runtime` 4.13.2, and the JAXB runtime. HikariCP brings `slf4j-api` 2.0.17. No SLF4J provider is installed. stderr prints the SLF4J no-provider warning and Hibernate's version line. Neither is an outcome.

The SessionFactory is built with `MetadataSources` and `StandardServiceRegistryBuilder`. `hibernate.dialect` is not set. Hibernate selected `org.hibernate.dialect.PostgreSQLDialect` from the connection and reported database version 18.6. The hello message reads that class back from the factory.

## Configuration read back from the SessionFactory

| Setting | Value |
| --- | --- |
| Flush mode | `AUTO` |
| `hibernate.hbm2ddl.auto` | `none` |
| `jakarta.persistence.schema-generation.database.action` | `none` |
| Transaction coordinator | `jdbc` |
| Connection handling | `DELAYED_ACQUISITION_AND_RELEASE_AFTER_TRANSACTION` |
| `hibernate.jpa.compliance` | false |
| `hibernate.jpa.compliance.transaction` | false, read back false |
| JPA bootstrap | false |
| `connectionProviderDisablesAutoCommit` | false |

Hibernate calls `Connection.setAutoCommit(false)` at begin. On a completion that reaches `afterCompletion`, it calls `Connection.setAutoCommit(true)` when autocommit was on at begin, then releases the connection. A `Connection.rollback` that throws sets the status to `FAILED_ROLLBACK` and does not call `afterCompletion`.

Entities are `Item` and `Uniq`, mapped onto the runner's tables. `GenerationType.IDENTITY` makes PostgreSQL execute the insert during `persist`, so a unique violation on `uniq` is raised from `persist`, not from a later `flush`. The valid marker is still flushed before the checkpoint that must observe it. An unflushed persist is not treated as a sent statement. Schema generation stays off, so Hibernate does not emit DDL inside the transaction under test.

## Setup

JDK 21 or newer. From this directory:

```sh
mvn -B package
chmod +x run
```

`mvn package` copies the pinned jars into `target/dependency/`. `./run` executes `java` on that classpath. `pnpm run setup` does not build this adapter.

From the repository root, with the disposable PostgreSQL up:

```sh
node harness/run.mjs --adapter=hibernate --repeat=3
```

A separate probe, not a PPCS case, prints the lifecycle observations in [`FINDINGS.md`](FINDINGS.md). It checks `cluster_name` against `.ppcs-instance.json`, creates `ppcs_hibernate_probe`, and drops that database:

```sh
java -cp "target/classes:target/dependency/*" org.ppcs.hibernate.Probe ../../.ppcs-instance.json
```

## Modes

| Mode | Kind | What it changes |
| --- | --- | --- |
| `native` | native | `DriverManager` DataSource, no pool. Each checkout is a new physical connection. `session.close` closes it. |
| `pooled` | configured | HikariCP 7.1.0, `maximumPoolSize` 1. No other pool setting is changed. TX-03 only. |

`TX-03` is not run on the `DriverManager` DataSource. The probe's two sessions used backends `1228751` and `1228752`. A later unit cannot be handed the connection that still holds a transaction.

## Transaction path

```java
Session session = sessionFactory.openSession();
Transaction tx = session.beginTransaction();
try {
    // work, then tx.commit()
} catch (Exception e) {
    if (rollbackOnException && tx.isActive()) tx.rollback();
    throw e;
} finally {
    session.close();
}
```

`rollbackOnException` is set for `CTL-01.rollback` and TX-03, which is the rollback `Session.inTransaction` performs through `TransactionManagement` when the action throws. TX-01A catches `23505` inside the transaction and then calls `commit`. It does not call `rollback` first. TX-01B calls `commit` after the runner has terminated the backend.

A returning `commit()` is reported `committed`. A returning `rollback()`, with the application error then leaving, is reported `rolled_back`. Any other exception is reported `failed`. That third report is not a claim that PostgreSQL rolled back.

## Faults

Category A is the fixture's unique violation. Category B is the runner's `pg_terminate_backend`. Category C is a client-side injection in this process, fired once, before pgjdbc sends. `Connection.commit` and `Connection.setAutoCommit` are not intercepted.

The withhold is on the connection Hibernate holds. A second wrapper, under HikariCP, records `commit`, `rollback`, and `setAutoCommit` with pgjdbc's transaction state and the caller. That wrapper does not change the call.

Category D is not implemented. The probe:

```text
commit_state_after=IDLE
commit_returned_while_in_progress=false
```

`commit()` did not return while the driver still reported a transaction in progress. `TX-01B.commit-reply-discarded` is NOT_RUN.

## What the recording covers

One framework FAIL: `TX-01A.caught-error-then-commit`. `commit()` returned after Hibernate had sent `ROLLBACK` and had not sent `COMMIT`. The runner's mechanism check is null because the connection was released inside that completion and the backend was gone at `after-end`. TX-01B connection loss passes: `commit()` threw `57P01` and the adapter reported `failed`. Pooled TX-03 passes. The `ROLLBACK` that reached PostgreSQL after the withheld call was HikariCP's `ProxyConnection.close`, not Hibernate's `afterCompletion`. TX-02, TX-04, TX-05, and the migration cases are unsupported. Three repetitions agreed. CTL-01 and `pg-control` held their gates.
