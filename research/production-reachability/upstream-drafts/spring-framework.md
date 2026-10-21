# Draft: Spring Framework

**Not filed.**

Suggested title: `afterCommit` runs when PostgreSQL rolls back an aborted transaction on `COMMIT`

Suggested component: `spring-tx` / `spring-jdbc`

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If application code catches that error and the Spring transaction then completes normally, PostgreSQL accepts `COMMIT` and reports command tag `ROLLBACK`. No `SQLException` is raised. The effect is a rollback.

Spring Framework 7.0.9 treats that as a successful commit. `DataSourceTransactionManager.doCommit` calls `Connection.commit()` and translates only a `SQLException`:

```java
try {
    con.commit();
} catch (SQLException ex) {
    throw translateException("JDBC commit", ex);
}
```

`Connection.commit()` returns. `AbstractPlatformTransactionManager.processCommit` then calls `triggerAfterCommit` and `triggerAfterCompletion(STATUS_COMMITTED)`.

PostgreSQL JDBC 42.7.14 does not surface the `ROLLBACK` command tag through `Connection.commit()`, which is void. The tag is still what PostgreSQL sent. An independent session sees the transaction aborted.

### Versions

- Spring Framework 7.0.9 (`spring-tx`, `spring-jdbc`)
- PostgreSQL JDBC 42.7.14
- Java 21
- PostgreSQL 18.6

The command-tag behavior is documented for current PostgreSQL and is not specific to 18.6: in an aborted transaction, `COMMIT` has the same effect as `ROLLBACK`, including the command tag, and no exception condition is raised. https://www.postgresql.org/docs/current/sql-commit.html

### Reproduction

`DataSourceTransactionManager` and `TransactionTemplate`. The duplicate insert is a real `23505`. The callback catches it and returns.

```java
DataSource dataSource = new DriverManagerDataSource(url, user, password);
JdbcTemplate jdbc = new JdbcTemplate(dataSource);
DataSourceTransactionManager manager = new DataSourceTransactionManager(dataSource);
TransactionTemplate tx = new TransactionTemplate(manager);

int[] afterCommit = {0};
int[] completion = {-1};

tx.execute(status -> {
    TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
        @Override
        public void afterCommit() {
            afterCommit[0]++;
        }
        @Override
        public void afterCompletion(int status) {
            completion[0] = status;
        }
    });
    jdbc.update("insert into item (name) values (?)", "kept");
    try {
        jdbc.update("insert into uniq (code) values (?)", "taken");
    } catch (DataAccessException ex) {
        // 23505. Caught inside the callback.
    }
    return null;
});
```

Schema: `item (id serial primary key, name text not null)`, `uniq (id serial primary key, code text not null unique)`, with one existing row `code = 'taken'`.

Observed on three repetitions, with both `DriverManagerDataSource` and HikariCP:

- `TransactionTemplate.execute` returned normally
- `afterCommit` ran once
- `afterCompletion` received `STATUS_COMMITTED` (`0`)
- before that completion, the session was `idle in transaction (aborted)`
- `pg_xact_status()` for the transaction was `aborted`
- a second connection did not see the `kept` row

The same hook result happened for:

- `@Transactional` when the method caught `SQLException` and returned
- `PlatformTransactionManager.getTransaction` followed by `commit`, with the `SQLException` caught before `commit`

A nested savepoint used through `PROPAGATION_NESTED`, with the duplicate insert inside the nested callback and the exception caught there, committed the outer row. That path is working. The failure is a commit of a transaction PostgreSQL has already aborted.

### Expected

`afterCommit` should not run, and `afterCompletion` should not be `STATUS_COMMITTED`, when PostgreSQL rolled the transaction back.

`TransactionSynchronization.afterCommit` says it is invoked after the main transaction has successfully committed, and gives confirmation messages or emails as the example.

`PlatformTransactionManager.commit` documents `UnexpectedRollbackException` for an unexpected rollback that the transaction coordinator initiated. This is that case: PostgreSQL rolled the transaction back, and `commit` returned without that exception.

### Actual

`afterCommit` runs, `afterCompletion` is `STATUS_COMMITTED`, `execute` returns, and the insert is not durable.

The connection is not left in an aborted block. `COMMIT` ends the transaction, so a later transaction on that connection can commit its own row. An application that only retries the next request will not notice. An `afterCommit` listener that sends mail or enqueues work will act on a commit that did not happen.

### Related observation

If a checked `SQLException` leaves an `@Transactional` method, Spring's default rollback rule does not mark the transaction rollback-only, so the interceptor still commits. The caller sees the `SQLException`, and `afterCommit` still runs while PostgreSQL has aborted the transaction. The caught-and-return case above is the one where the application itself sees a normal return.

### What this is not

This is not Spring issue 28685. That issue is an exception thrown from `afterCommit`, after which `afterCompletion` is still `STATUS_COMMITTED`. Here `afterCommit` runs because `Connection.commit()` returned, and the database had already aborted the transaction.

pgjdbc is part of the mechanism, because `Connection.commit()` does not report the `ROLLBACK` tag. Spring is where the false commit becomes `afterCommit`. `PgConnection.getTransactionState()` is `FAILED` before `commit()` returns in this situation, so the aborted state is visible to code that looks at the PostgreSQL JDBC connection before calling `commit()`.
