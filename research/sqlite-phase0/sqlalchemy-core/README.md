# SQLAlchemy Core on SQLite

Scores SQLAlchemy 2.1.5 `Connection.begin()` and `Connection.begin_nested()` against the same outcomes as `research/sqlite-phase0/control/run.py`. It is not registered with the PostgreSQL runner and it does not import `adapters/sqlalchemy-core`.

The engine is `create_engine("sqlite:///")`. On Python 3.13 that leaves the DB-API connection at legacy transaction control (`autocommit == -1`, `isolation_level == ""`). Core's `begin()` does not send `BEGIN` itself. The sqlite3 driver inserts `BEGIN ` before a DML statement.

```sh
/Users/kevinlopez/code/ppcs-sqlalchemy-core/adapters/sqlalchemy-core/.venv/bin/python \
  research/sqlite-phase0/sqlalchemy-core/run.py
```

`requirements.txt` pins `sqlalchemy==2.1.5`. Any environment with that version can run the file. The command above uses the virtualenv already installed for the PostgreSQL Core adapter.

A second `sqlite3` connection checks the file after the Core API returns. A case fails when that observation disagrees with the sqlite3 control.

Recorded run: `evidence/2026-10-19T13-42-59Z/`. Three repetitions agreed. Seven cases passed. Two failed.

`SQLITE-TX-04.release-then-outer-rollback` failed. The trace is `SAVEPOINT sa_savepoint_1`, `CREATE TABLE`, `INSERT`, `RELEASE SAVEPOINT sa_savepoint_1`, and no `BEGIN` or `ROLLBACK`. After `begin_nested()` returns, `in_transaction` is already false, and the second connection sees `item`. Releasing that savepoint committed the table. The outer block's exception did not remove it.

`SQLITE-DDL.statement-error-rollback` failed. The trace puts both `CREATE TABLE` statements before `BEGIN `, then the inserts, then `ROLLBACK`. The second connection still sees `account` and `schema_migrations`. Their rows are empty. The rollback removed the inserts and left the tables, because those `CREATE TABLE` statements had already committed.

`SQLITE-DDL.statement-error-commit` passed: the same sequence without the outer exception leaves the tables, the migration id, and the one account row.
