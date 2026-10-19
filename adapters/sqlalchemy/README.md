# SQLAlchemy adapter

SQLAlchemy 2.1 `Session.begin()` and `Session.begin_nested()` against the suite's disposable PostgreSQL, through psycopg 3. The adapter is a separate Python program. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, `TX-01A.caught-error-then-commit`, `TX-01B.conn-lost-before-commit`, `TX-02.savepoint-rollback-not-sent`, `TX-02.savepoint-rollback-rejected`, `TX-02.conn-lost-before-savepoint-rollback`, `TX-03.rollback-not-sent`, `TX-03.statement-error-rollback-not-sent`, and `TX-03.conn-lost-in-transaction`. All of them run in the native mode. `TX-03`'s next unit of work is a second `Session` on the same engine (`pool_size` 1, `max_overflow` 0). The engine is not disposed between the units, and `pool_pre_ping` is off.

Category C faults are injected in this process, once. `ROLLBACK TO SAVEPOINT` is withheld or rewritten in `before_cursor_execute`, before psycopg sends it. A withheld statement raises `RuntimeError` with no SQLSTATE. A rewritten `ROLLBACK TO SAVEPOINT` is sent under the name `ppcs_no_such_savepoint`, and `after-fault` is reported from `handle_error` after PostgreSQL answers, before `Session.begin_nested()` sees the error. A top-level `ROLLBACK` does not reach the cursor event. On SQLAlchemy 2.1.5, `DefaultDialect.do_rollback` calls `dbapi_connection.rollback()` (`sqlalchemy/engine/default.py`). That call is withheld once on `psycopg.Connection.rollback`, before send. The cursor hook does not also match it.

`TX-01B.commit-reply-discarded` is not implemented. psycopg 3.3.6 `Connection.commit` waits on `_commit_gen`, which calls `_exec_command(b"COMMIT")` and does not return until that command finishes (`psycopg/_connection_base.py`). `Session.begin()` commits through `DefaultDialect.do_commit`, which calls that method. A probe on PostgreSQL 18.6 observed `transaction_status` `INTRANS` before `commit()` returned and `IDLE` when it returned. The same transition is the successful `COMMIT (INTRANS -> IDLE)` in [`reports/examples/2026-10-19T00-49-25Z-3673a3`](../../reports/examples/2026-10-19T00-49-25Z-3673a3/summary.md). The caller never sees a lost COMMIT reply while the driver still reports a transaction in progress. Closing the socket after `commit()` returns is not that loss. The node-postgres reply-lost simulation closes the socket after the driver has already parsed the reply, so it is not this probe. The case stays NOT_RUN.

`TX-02.savepoint-rollback-not-sent` withholds the next `ROLLBACK TO SAVEPOINT` inside this process, before psycopg sends it, then reports `after-fault` and raises. That is the same client-side fault the Node adapters inject in `pg.Client.query`. At `after-fault` the session is `idle in transaction` and still holds both transaction ids.

The SQLAlchemy FAIL on that case is the same ending as Lucid, MikroORM, and `pg-control` unsafe, and the same ending as Django's run `2026-10-18T13-08-22Z-6d8443`. The outer API reports a commit, PostgreSQL commits, and both the outer and inner rows are visible. The session is idle afterward, so TX-02.2 holds. Recorded in `results/2026-10-17T23-08-15Z-6704a7`: three repetitions agreed, xid 5788 committed, markers `outer` and `inner` both visible. The same ending in [`reports/examples/2026-10-19T00-49-25Z-3673a3`](../../reports/examples/2026-10-19T00-49-25Z-3673a3/summary.md) is xid 1408.

TypeORM's FAIL on this case is a different ending. After the same withheld rollback it sends `RELEASE SAVEPOINT`, reports a commit, and leaves the session `idle in transaction`. Teardown then aborts the transaction, so neither row remains. TX-02.1 and TX-02.2 both fail. In the PPCS 0.3.0 recording that transaction is xid 2279. Do not describe TypeORM as having committed the inner write.

`TX-02.savepoint-rollback-rejected` in the 2026-10-19 run is also a different ending from that withheld-savepoint result. `Session.begin()` reports a commit, the session is idle, the last statement is `COMMIT`, and neither marker remains, because PostgreSQL aborted the transaction. `adapters/sqlalchemy/FINDINGS.md` is the per-case report.

`pg-control` correct sends `ROLLBACK` after the same withheld statement and passes.

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
node harness/run.mjs --adapter=sqlalchemy --case=CTL-01,TX-01A,TX-01B,TX-02,TX-03 --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by the `TX-01B` prefix and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-19T00-49-25Z-3673a3`](../../reports/examples/2026-10-19T00-49-25Z-3673a3/summary.md) is the recording. `adapters/sqlalchemy/FINDINGS.md` is the per-case report.
