# Draft: Spring Framework

**Not filed.** Production relevance (2026-10-26): [`unfiled findings`, section S1](../../unfiled-findings-production-relevance/README.md). Likelihood: low.

Suggested title: `afterCommit` runs when PostgreSQL rolls back an aborted transaction on `COMMIT`

Suggested component: `spring-tx` / `spring-jdbc`

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If application code catches that error and the Spring transaction then completes normally, `Connection.commit()` returns. No `SQLException` is raised. The earlier write is gone.

Spring Framework 7.0.9 treats that as a successful commit. `DataSourceTransactionManager.doCommit` calls `Connection.commit()` and translates only a `SQLException`:

```java
try {
    con.commit();
} catch (SQLException ex) {
    throw translateException("JDBC commit", ex);
}
```

`Connection.commit()` returns. `AbstractPlatformTransactionManager.processCommit` then calls `triggerAfterCommit` and `triggerAfterCompletion(STATUS_COMMITTED)`.

PostgreSQL JDBC 42.7.14 `Connection.commit()` is void. It returned without a `SQLException`. An independent session sees the transaction aborted. This run recorded no command tag. The pooled rows logged `COMMIT` as the last statement. On the `DriverManagerDataSource` rows the session was already gone.

### Versions

- Spring Framework 7.0.9 (`spring-tx`, `spring-jdbc`)
- PostgreSQL JDBC 42.7.14
- Java 27, the runtime recorded in the run. The adapter compiler release is 21.
- PostgreSQL 18.6

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

This snippet has the same shape as the recorded `TransactionTemplate` form. It is not the code that was executed.

Schema: `item (id serial primary key, name text not null)`, `uniq (id serial primary key, code text not null unique)`, with one existing row `code = 'taken'`.

Three repetitions agreed, for both `DriverManagerDataSource` and HikariCP, that `TransactionTemplate.execute` returned, `pg_xact_status()` was `aborted`, and a second connection did not see the row inserted before the error. The recorded marker was `tx`, not `kept`. On the first repetition, for both of those DataSources:

- `afterCommit` ran once
- `afterCompletion` received `STATUS_COMMITTED` (`0`)
- before that completion, the session was `idle in transaction (aborted)`

The first repetition recorded those same hook counts for:

- `@Transactional` when the method caught `SQLException` and returned
- `PlatformTransactionManager.getTransaction` followed by `commit`, with the `SQLException` caught before `commit`

Three repetitions of those two forms agreed that the call returned, the transaction was aborted, and the row was absent.

The four `TransactionTemplate` rows that use `PROPAGATION_NESTED` committed the outer row. The duplicate insert was inside the nested callback, and the exception left that callback. The nested template rolled back. The declarative `PROPAGATION_NESTED` row did not commit the outer row. The run classifies that row INCONCLUSIVE because the recorded violation is `25P02`, not `23505`. The failure in this report is a commit of a transaction PostgreSQL has already aborted.

### Expected

`afterCommit` should not run, and `afterCompletion` should not be `STATUS_COMMITTED`, when PostgreSQL rolled the transaction back.

`TransactionSynchronization.afterCommit` says it is invoked after the main transaction has successfully committed, and gives confirmation messages or emails as the example.

`PlatformTransactionManager.commit` documents `UnexpectedRollbackException` for an unexpected rollback that the transaction coordinator initiated. This is that case: PostgreSQL rolled the transaction back, and `commit` returned without that exception.

### Actual

`afterCommit` runs, `afterCompletion` is `STATUS_COMMITTED`, `execute` returns, and the insert is not durable.

On the pooled rows, a later transaction reused the same PostgreSQL backend and committed its own row. With `DriverManagerDataSource` the connection was closed, and the later transaction ran on a new backend. An `afterCommit` listener that sends mail or enqueues work will act on a commit that did not happen.

### Related observation

If a checked `SQLException` leaves an `@Transactional` method, Spring's default rollback rule does not mark the transaction rollback-only, so the interceptor still commits. The caller sees the `SQLException`. On the first repetition, `afterCommit` still ran while PostgreSQL had aborted the transaction. The caught-and-return case above is the one where the application itself sees a normal return.

### What this is not

This is not Spring issue 28685. That issue is an exception thrown from `afterCommit`, after which `afterCompletion` is still `STATUS_COMMITTED`. Here `afterCommit` runs because `Connection.commit()` returned, and the database had already aborted the transaction.

pgjdbc is part of the mechanism, because `Connection.commit()` returned without a `SQLException` while an independent session saw the transaction aborted. Spring is where that return becomes `afterCommit`. This run did not log a command tag or `PgConnection.getTransactionState()`.
