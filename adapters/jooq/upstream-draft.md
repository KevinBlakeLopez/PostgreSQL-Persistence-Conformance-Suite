# Draft: jOOQ `DSLContext.transaction` returns after PostgreSQL has aborted the transaction

**Not filed. Not approved to file. Do not post this. Do not open a second pgjdbc issue.**

pgjdbc#4494 already asks whether `Connection.commit()` should report that PostgreSQL answered `COMMIT` with `ROLLBACK`. The use case on that issue was answered on 2026-10-21. This draft records the jOOQ 3.21.9 measurement. It does not replace that issue.

A second observation, further down, is category C: after a withheld `Connection.rollback()`, jOOQ restores autocommit and pgjdbc's `setAutoCommit(true)` commits the still-open transaction. That one is not the command-tag question.

## Versions

| Piece | Version |
| --- | --- |
| jOOQ | Open Source Edition 3.21.9, `org.jooq:jooq` from Maven Central. Not a commercial edition |
| PostgreSQL JDBC | 42.7.14 |
| JDK | 27 (Homebrew OpenJDK, build 27). The adapter compiles with `--release 21` |
| PostgreSQL | 18.6, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` |
| Pool | none for this case |

Harness evidence: `reports/examples/2026-10-22T12-58-46Z-d4a7fc`, case `TX-01A.caught-error-then-commit`, modes `native` and `jdbc`. Three repetitions agreed. xid 33422 (`native`) and xid 33435 (`jdbc`) were `aborted`. The marker was absent.

## What the application does

```java
DSLContext dsl = DSL.using(dataSource, SQLDialect.POSTGRES);
dsl.transaction(configuration -> {
    configuration.dsl().execute("insert into item (name, qty) values (?, ?)", marker, 0);
    try {
        configuration.dsl().execute("insert into uniq (code) values (?)", "taken");
    } catch (DataAccessException ex) {
        // SQLSTATE 23505. The callback returns.
    }
});
```

`uniq.code` already contains `taken`. The second insert fails. The callback catches it and returns.

## Expected and actual

Expected, if a normal return means the transaction committed: the row is visible, and `pg_xact_status` of the captured id is `committed`.

Actual:

- The callback sees `IntegrityConstraintViolationException`, SQLSTATE `23505`.
- Before `commit`, pgjdbc's `PgConnection.getTransactionState()` is `FAILED`. The session is `idle in transaction (aborted)`.
- `Connection.commit()` returns. No `SQLException`. No `SQLWarning`. The driver state is then `IDLE`.
- `DSLContext.transaction` returns. Transaction listeners observed on this run: `beginStart`, `commitStart`, `commitEnd`. No rollback listener.
- An independent connection sees `pg_xact_status` `aborted` and does not see the first insert.

The same `commit()` return and the same aborted fate happen when the application never calls `DSLContext.transaction` and calls `Connection.commit()` itself after the same DSL inserts. In that mode the runner saw the session idle with last statement `COMMIT`.

If the `23505` is not caught, `transaction()` throws `IntegrityConstraintViolationException`, calls `Connection.rollback()` once, does not call `Connection.commit()`, and the row is absent. The probe on 2026-10-22 printed `escape_commit_calls=0`, `escape_rollback_calls=1`, `escape_fate=aborted`.

## JDBC observations

`java.sql.Connection.commit()` is void. pgjdbc 42.7.14 `PgConnection.commit` calls `executeTransactionCommand(commitQuery)` when the executor's transaction state is not `IDLE`. The completion tag is consumed inside that execute. `Statement.execute("COMMIT")` on an aborted transaction, in the same probe, returned update count 0 and no warning. The tag is not on the statement.

`DefaultConnectionProvider.commit` (jOOQ 3.21.9) is:

```java
connection.commit();
```

and on `SQLException` throws `DataAccessException("Cannot commit transaction", cause)`. It does not read `PgConnection.getTransactionState()`.

`DefaultDSLContext.transactionResult0` calls `provider.commit(ctx)`, sets a local `committed` flag when that call returns, and returns the callback result. `commitEnd` is in a `finally`, so it also runs when `commit()` throws. On the lost-reply case in this suite, `commit()` threw `08006`, `commitEnd` ran, and `transaction()` still threw. On TX-01A, `commit()` returned.

`DefaultTransactionProvider.commit` calls `connection.commit()` when the savepoint stack is empty. The manual (3.21, Transaction management) describes a callback return as the implicit commit.

Sources, tag `version-3.21.9`:

- `jOOQ/src/main/java/org/jooq/impl/DefaultDSLContext.java`, `transactionResult0`
- `jOOQ/src/main/java/org/jooq/impl/DefaultTransactionProvider.java`, `commit` and `brace`
- `jOOQ/src/main/java/org/jooq/impl/DefaultConnectionProvider.java`, `commit`
- Manual: https://www.jooq.org/doc/3.21/manual/sql-execution/transaction-management/

pgjdbc tag `REL42.7.14`, `pgjdbc/src/main/java/org/postgresql/jdbc/PgConnection.java`, `commit` and `setAutoCommit`.

## Where this sits

| Layer | What it did on TX-01A |
| --- | --- |
| PostgreSQL | Aborted the transaction on `23505`. The first insert is not committed |
| pgjdbc | `Connection.commit()` returned. The command tag was not a return value. Driver state went from `FAILED` to `IDLE` |
| jOOQ `DefaultTransactionProvider` / `DefaultConnectionProvider` | Called `connection.commit()` and got a normal return |
| jOOQ `DSLContext.transaction` | Returned normally. `commitEnd` ran |
| Application | Caught `23505` and let the callback return. It was not shown a command tag |

jOOQ did not drop a tag it had been given. A report that says jOOQ should throw would be asking it to notice a condition the JDBC call does not fail on, for example by reading a driver-specific transaction state before `commit()`. That is a design question for jOOQ. It is also the question already filed for pgjdbc. This draft does not choose a patch.

## Separate observation: autocommit restore after a withheld rollback

Category C. The client withholds `Connection.rollback()` once, so the statement is not sent. The transaction stays open. This is not a production error rate.

In `pooled` mode, `DefaultTransactionProvider.rollback` still runs `brace` in a `finally`. `brace` calls `setAutoCommit(true)` when the connection started in autocommit. pgjdbc's `setAutoCommit(true)`, while autocommit is currently false, calls `commit()` before flipping the flag. The harness trace was `setAutoCommit(true)` from `OPEN` to `IDLE`, and the session's last statement at `after-unit1` was `COMMIT`. xid 33585 was committed. The doomed row was visible. `transaction()` had rethrown the callback's exception, so the application-facing result was a rollback, and `rollbackEnd` had run.

`jdbc-pooled` does not call `setAutoCommit(true)` after the thrown `rollback()`. It closes the connection. HikariCP 7.1.0 then sent `ROLLBACK`. xid 33601 was aborted. That case passed.

The statement-error variant of the same withhold passes under jOOQ's provider too: the transaction is already aborted, `setAutoCommit(true)` still leads to last statement `COMMIT`, and the row stays absent.

This cleanup interaction is Spring's pooled TX-03 ending as well (`DataSourceTransactionManager` restores autocommit after `rollback()` throws). It is not the TX-01A command-tag question. It is not filed.
