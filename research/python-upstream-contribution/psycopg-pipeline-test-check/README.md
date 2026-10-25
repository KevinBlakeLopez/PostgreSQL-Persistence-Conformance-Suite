# psycopg's `test_outer_transaction_error` pattern: what the `transaction()` block reports

Run on 2026-10-24. Written by: Claude Opus 5.5 (max).

An outside review of the PY-1b draft found psycopg's `tests/test_pipeline.py::test_outer_transaction_error`, at `master` `99356800e`, lines 506–511, and its async copy in `tests/test_pipeline_async.py`, lines 507–512. The test catches a database error inside `conn.transaction()` and expects the block to exit normally. The draft had said that no such test exists.

This check answers one question. In that test's pattern, is the transaction already aborted when the block exits? If so, the block's `COMMIT` is answered with `ROLLBACK`, and a change that makes the block raise on that tag would fail the test.

It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies.

## Files

| File | Contents | SHA-256 |
| --- | --- | --- |
| `psycopg_pipeline_outer_error.py` | The program, byte-identical to the one that ran | `ddfdcc36e25235c8a269ee23d651c649ed3d08549df7dd77b5f8c51b81dc2540` |
| `output/psycopg_pipeline_outer_error.out` | Its complete stdout and stderr | `4a44bf998bdca14f5162b98773d7d60bfaed08bf77bd5ff92ae3e390bd68999e` |
| `output/server-log.subject-sessions.txt` | The server log's lines for the six subject sessions (`application_name` `chk-pipe-*`). The rest of the log was not kept | `8e4395a7d449d01b35e137b1fab3e7715f98b5ead88681e7c0a5ce6753fb963a` |

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. A throwaway container, `ppcs-review-check-pg`, on `127.0.0.1:55492`, with a tmpfs data directory, a random password, and a random `cluster_name`. The `cluster_name` was checked through the host port before the run. The container was removed afterwards. Not `ppcs-postgres` |
| Server settings | `log_statement=all` and `log_line_prefix='%m [%p] app=%a xid=%x '`. Otherwise image defaults: PPCS's `max_connections`, `log_lock_waits` and `deadlock_timeout` settings were not passed |
| Client | `adapters/sqlalchemy-core/.venv/bin/python -I`: Python 3.13.11, psycopg 3.3.6 (binary implementation, libpq 18.6; `psycopg.pq.version()` prints `180006`) |
| Command | `DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55492/postgres" <venv>/bin/python -I psycopg_pipeline_outer_error.py` |
| Run time | 2026-10-24, 18:35:22.215 to 18:35:22.273 UTC (the subject sessions, by the server log) |

## The program

The program opens a non-autocommit connection, as the test's `conn` fixture does (`conn_cls.connect(dsn, connect_timeout=10)`, in `tests/fix_db.py`). It has two arms, three repetitions each, in one process:

- **`exact`** runs the test's body. `pytest.raises((e.UndefinedColumn, e.OperationalError))` is replaced by `try`/`except` on the same tuple.
- **`witnessed`** adds a marker insert and `pg_current_xact_id()` before the pipeline. A separate autocommit connection then reads `pg_xact_status()` and the marker's visibility.

Each arm reports:

- the exception caught inside the block;
- the driver's transaction status just before the block exits;
- whether the block raised;
- `Transaction.status`;
- the session's state and last statement.

## Result

All six repetitions agreed.

| Arm | Caught inside the block | Driver status before exit | Block raised | `Transaction.status` | `pg_xact_status` | Marker visible | Session after exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `exact` | `UndefinedColumn` | `INERROR` | no | `committed` | — | — | `idle`, last statement `COMMIT` |
| `witnessed` | `UndefinedColumn` | `INERROR` | no | `committed` | `aborted` | no | `idle`, last statement `COMMIT` |

**The server log.** For each subject session it shows:

- `BEGIN`;
- for `witnessed` only, the marker insert and `select pg_current_xact_id()`;
- `select error` failing with `column "error" does not exist`;
- then `COMMIT`.

`create table voila ()` was never executed.

## What this establishes, and what it does not

- **Established.** In `test_outer_transaction_error`'s pattern, the transaction is aborted (`INERROR`) when the outer `transaction()` block exits. The block exits normally, `Transaction.status` reads `committed`, and PostgreSQL rolled the transaction back.
- **The consequence.**
  - A change that makes the block raise when its `COMMIT` is answered `ROLLBACK` would fail that test.
  - A change that corrects `status` alone would not, because the test does not check `status`.
- **Not read here: the command tag of that `COMMIT`.** For a `COMMIT` sent in the `INERROR` state, psycopg receives tag `ROLLBACK` with status `COMMAND_OK`, as [`../../production-reachability/reproductions/psycopg_commit_tag.txt`](../../production-reachability/reproductions/psycopg_commit_tag.txt) records.
- **Not run:**
  - the async copy of the test (by source reading, it is the same pattern);
  - psycopg's own test runner;
  - other psycopg or PostgreSQL versions.
- **Scope of the pipeline.** The block's `COMMIT` is sent after the pipeline block has exited. A `COMMIT` queued while a pipeline is still open was not exercised.
