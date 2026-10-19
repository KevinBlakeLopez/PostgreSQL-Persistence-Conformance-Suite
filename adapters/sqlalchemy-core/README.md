# SQLAlchemy Core adapter

SQLAlchemy 2.1 Core `Connection.begin()` and `Connection.begin_nested()` against the suite's disposable PostgreSQL, through psycopg 3. The adapter is a separate Python program. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit, and it does not use the ORM `Session`.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, `TX-01A.caught-error-then-commit`, `TX-01B.conn-lost-before-commit`, `TX-02.savepoint-rollback-not-sent`, `TX-02.savepoint-rollback-rejected`, `TX-02.conn-lost-before-savepoint-rollback`, `TX-03.rollback-not-sent`, `TX-03.statement-error-rollback-not-sent`, `TX-03.conn-lost-in-transaction`, `TX-04.nested-failure-contained`, `TX-04.nested-released-outer-rollback`, `TX-05.managed-serializable`, and `TX-05.explicit-serializable`. All of them run in the native mode. `TX-03`'s next unit of work is a second `Engine.connect()` and `Connection.begin()` on the same engine (`pool_size` 1, `max_overflow` 0). The engine is not disposed between the units, and `pool_pre_ping` is off.

`TX-05` requests `SERIALIZABLE` with `Connection.execution_options(isolation_level=...)` before `begin()`, which is the PostgreSQL dialect's documented per-connection isolation API. The managed case is the `Connection.begin()` context manager. The explicit case keeps the `RootTransaction` and calls `Transaction.commit()`. The marker is inserted with `insert()` and read back with `select()`.

`TX-04.nested-failure-contained` and `TX-04.nested-released-outer-rollback` use `Connection.begin_nested()`, which Core documents as a `SAVEPOINT`. `begin_nested()` is not an independent transaction. `TX-04.independent-inner` is UNSUPPORTED, not applicable by design: Core has no propagation mode that promises an independent transaction, and `execute()` does not defer writes. MG-02 and MG-03 are UNSUPPORTED, capability absent. Core has no migration runner. Alembic is a separate adapter, and this one does not substitute it.

Category C faults are injected in this process, once. `ROLLBACK TO SAVEPOINT` is withheld or rewritten in `before_cursor_execute`, before psycopg sends it. A withheld statement raises `RuntimeError` with no SQLSTATE. A rewritten `ROLLBACK TO SAVEPOINT` is sent under the name `ppcs_no_such_savepoint`, and `after-fault` is reported from `handle_error` after PostgreSQL answers, before `Connection.begin_nested()` sees the error. A top-level `ROLLBACK` does not reach the cursor event. On SQLAlchemy 2.1.5, `DefaultDialect.do_rollback` calls `dbapi_connection.rollback()` (`sqlalchemy/engine/default.py`). That call is withheld once on `psycopg.Connection.rollback`, before send. The cursor hook does not also match it. `psycopg.Connection.commit` is traced and not altered.

`TX-01B.commit-reply-discarded` is not implemented. psycopg 3.3.6 `Connection._commit_gen` calls `_exec_command(b"COMMIT")` and does not return until that command finishes (`psycopg/_connection_base.py`). `Connection.begin()` commits through `DefaultDialect.do_commit`, which calls that method. A probe on PostgreSQL 18.6 observed `transaction_status` `INTRANS` before `commit()` returned and `IDLE` when it returned. The caller never sees a lost COMMIT reply while the driver still reports a transaction in progress. Closing the socket after `commit()` returns is not that loss. The node-postgres reply-lost simulation closes the socket after the driver has already parsed the reply, so it is not this probe. The case stays NOT_RUN.

## Setup

`pnpm run setup` skips this directory because it has no `package.json`.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The manifest command is `./.venv/bin/python main.py`, run with this directory as the working directory.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=sqlalchemy-core --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by a full adapter run and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-19T12-35-51Z-64c5c5`](../../reports/examples/2026-10-19T12-35-51Z-64c5c5/summary.md) is the recording. `adapters/sqlalchemy-core/FINDINGS.md` is the per-case report.
