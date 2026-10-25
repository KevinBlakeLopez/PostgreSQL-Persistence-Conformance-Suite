# PY-8: Tortoise ORM does not translate errors raised by COMMIT

Run on 2026-10-25, 03:40–04:07 UTC (2026-10-24, 20:40–21:07 PDT). Written by: Claude Opus 5.5 (max).

This is the evidence for tracker item PY-8 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It covers two steps of preparing its pull request.

- **Step 1: verify before a design is chosen.** It reproduces the gap analysis's observation P5 on the three backends that can fail at COMMIT and that run here, runs the two checks the assignment set, and measures four candidate changes against the reproduction, the checks and Tortoise's own test suite. The candidates are applied at run time; the Tortoise checkout was not changed.
- **Step 2: the branch** that implements the chosen approach, C3 on asyncpg and psycopg. See "Step 2: the branch".
- **A review package** for an independent correctness review of the branch, in [`review/`](review/README.md): verbatim materials, three more checks, and an assessment.

It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies. The independent checks are listed under "Independent verification".

## Question

Probe P5 (`../../python-production-failure-gap-analysis/p45_commit_error_and_retry.py`, `output/p45.rep{1,2,3}.out`, key `p5_tortoise`) observed, on Tortoise 1.1.9 with asyncpg, three of three: a deferred foreign-key violation inside `in_transaction()` arrived at block exit as `asyncpg.exceptions.ForeignKeyViolationError` (SQLSTATE 23503), not `tortoise.exceptions.IntegrityError`. psycopg and SQLite were not run, and nothing recorded the cause, the context or the database outcome. This directory asks:

- **(a)** Which exception reaches the application when the COMMIT that `in_transaction()` sends fails on a deferred foreign key, on asyncpg, psycopg and SQLite? What are its `__cause__` and `__context__`, and what does the database hold?
- **(b) Check 1.** A nested block catches a statement error and exits normally on an aborted transaction, so its `RELEASE SAVEPOINT` fails with a class-25 error. What reaches the application, does `ROLLBACK` reach the server, what does the pool log, and what does the database hold, before and after each candidate?
- **(c) Check 2.** What do the next `in_transaction()` and the next plain query see on SQLite after a failed COMMIT?
- **(d)** What does each candidate change: the reproduction, `get_or_create()`, a failing `rollback()`, and Tortoise's test suite?

## Answers

All observed, three of three, unless marked otherwise.

- **(a) Reproduced on all three backends,** on PyPI's 1.1.9 and on `develop` `ad0d6ce2b878`:
  - asyncpg raised `asyncpg.exceptions.ForeignKeyViolationError` (23503); psycopg `psycopg.errors.ForeignKeyViolation` (23503); SQLite `sqlite3.IntegrityError` (`SQLITE_CONSTRAINT_FOREIGNKEY`). None is a `tortoise.exceptions.IntegrityError`. `__cause__` and `__context__` are `None`. Each was raised through the context's `__aexit__`, then the wrapper's `commit()`, then the driver.
  - The same INSERT against a foreign key that is not deferred fails at the INSERT, and arrives translated on all three backends.
  - On PostgreSQL the transaction aborted, by the witness, `psql` and the server log; 0 rows. On SQLite, 0 committed rows.
  - `get_or_create()` with a deferred foreign key lets the same driver exception escape. Its fallback `get()` is not attempted: the server log shows no SELECT after the failed COMMIT.
- **(b) Check 1.** On `develop`, the driver's class-25 error (`InFailedSQLTransactionError`, `InFailedSqlTransaction`, 25P02) reaches the application, the outer block's `rollback()` sends `ROLLBACK`, and the pool reuses the connection without logging anything.
  - **C1** (decorate `commit()`) changes this. The nested block's `RELEASE` failure becomes `TransactionManagementError`, and the outer block skips its `rollback()`, as `__aexit__` does for that class.
    - **asyncpg:** the pool's reset sends `ROLLBACK` and logs `ERROR asyncio: Resetting connection with an active transaction`.
    - **psycopg:** psycopg_pool's reset fails ("Explicit rollback() forbidden within a Transaction context"), and the pool discards the connection. No `ROLLBACK` reaches the server; the session ends. The follow-up transaction runs on a new backend.
    - The outer transaction aborted either way.
  - **C2** (decorate `commit()`, but not the nested release) and **C3** (translate only integrity errors at commit) behave exactly as `develop`.
  - The two driver versions behaved the same: six of six per backend and candidate.
- **(c) Check 2, SQLite.** `develop` and C1 differ only in the first exception's class. After the failed COMMIT, the shared connection stays inside the transaction. Then:
  - a plain `create()` returns normally, and is not committed;
  - the next `in_transaction()` raises a raw `sqlite3.IntegrityError` from `begin()`, which calls `commit()` first. It also leaves `connections.get('default')` set to the transaction wrapper;
  - the `in_transaction()` after that is a savepoint inside the leftover transaction (`NestedTransactionContext`). It returns normally, and nothing is committed;
  - `close_connections()` closes the connection, then raises `AttributeError: 'SqliteTransactionWrapper' object has no attribute 'filename'`.

  Nothing written after the failed COMMIT was committed, although three of the four writes returned normally. This is a separate defect: see "A separate candidate" below.
- **(d) After the change.**
  - **Exception class.** All four candidates turn the COMMIT-time error into `tortoise.exceptions.IntegrityError` on asyncpg and psycopg, also when the violating row was inserted in a nested block. There `RELEASE SAVEPOINT` succeeded and the outer COMMIT failed.
  - **`get_or_create()` on PostgreSQL.** With any candidate it catches the COMMIT-time error, and runs its fallback `get()`: the log shows one SELECT after the failed COMMIT.
    - With a deferred foreign key, it then re-raises `tortoise.exceptions.IntegrityError`.
    - Racing a competitor on a deferred UNIQUE constraint, `develop` raises the driver's `UniqueViolationError` (23505). The candidates return the competitor's row (`id=100`, `created=False`).
  - **`get_or_create()` on SQLite, with C1, C3 and R: a phantom row, nine of nine.** With a deferred foreign key, it returns `created=False` for a row that was never committed (the witness counts 0). The fallback `get()` runs on the shared connection, inside the transaction that the failed COMMIT left open, and reads its own uncommitted INSERT. On `develop` it raises the raw `sqlite3.IntegrityError` instead.
  - **`rollback()` after the backend was terminated.** asyncpg raised `InterfaceError` or `InternalClientError`, depending on timing, under `develop` and R alike; the translator maps neither. psycopg's `rollback()` raised nothing: psycopg logs "error ignored in rollback" and suppresses the error, so the application's own `AppError` arrived. R changed nothing in these runs.
  - **Tortoise's suite, full, under each candidate: no failure that a candidate caused,** on any backend (see "Tortoise's test suite").
  - **No test in the suite makes `commit()` raise a driver error.** The full suite, traced on all three backends, saw exactly one exception from `commit()`: `TransactionManagementError("Transaction already finalised")`, from `commit()`'s own guard, in `test_transaction_exception_2`. No candidate touches it.

## Candidates

`candidates.py` applies each one by wrapping methods of the backend's transaction wrapper class at run time, exactly as a decorator in the source would.

| Candidate | asyncpg and psycopg | SQLite |
| --- | --- | --- |
| `develop` | no change | no change |
| C1 | the backend's `translate_exceptions` on `commit()`. `release_savepoint()` calls `self.commit()`, so a nested block's `RELEASE SAVEPOINT` is translated too | a copy of the module's mapping, with the signature `(self, *args)`, on `commit()` |
| C2 | as C1, but `release_savepoint()` calls the undecorated `commit()` | same as C1, since SQLite's `release_savepoint()` does not call `commit()`; not run separately |
| C3 | `commit()` maps only the driver's integrity error to `IntegrityError`, as the backend's translator does (asyncpg chains it with `from exc`; psycopg does not); everything else passes through | the same, for `sqlite3.IntegrityError` |
| R | C1, plus the backend's `translate_exceptions` on `rollback()`, which `savepoint_rollback()` calls | C1, plus the same mapping on `rollback()` |

SQLite's own decorator cannot wrap `commit()`: its signature is `(self, query, *args)`. `chk_sqlite_decorator_signature.py` wraps it anyway, and the block raises `TypeError: SqliteTransactionWrapper.commit() missing 1 required positional argument: 'query'`, three of three.

## Files

`SHA256SUMS` lists every file here but this README; `shasum -a 256 -c SHA256SUMS` passes. The programs were byte-identical before and after the 114 recorded runs.

| File | Contents | SHA-256 |
| --- | --- | --- |
| `tortoise_commit_translation.py` | The reproduction: four arms, each on a new `Tortoise.init()`: `create()` inside `in_transaction()` and `get_or_create()`, against a deferred and an immediate foreign key | `cb45958847400a453f458cf0663acd83c2fa433dfdb3fd9327ce61714925f8fa` |
| `candidates.py` | CHK-only. The candidates above | `44b79206a2aebe2e9ad5e889149f7a58e57168619eed5c6995934b8c341b08e5` |
| `chk_nested_release.py` | CHK-only. Check 1 | `09f6bd47e65103c89d3fe31f82a3b6faa654c0e3867b97acc5d31ba466c36871` |
| `chk_sqlite_failed_commit.py` | CHK-only. Check 2 | `a4999e1c84d9c95a347d754422c05c4cfba615b1ac7fad3c4d1a8d688a44c23d` |
| `chk_after_change.py` | CHK-only. The reproduction under a candidate (part 1), a deferred violation inside a nested block (part 2), and on PostgreSQL the `get_or_create()` race (part 3) and `rollback()` after `pg_terminate_backend()` (part 4) | `dd1e86910bbef54f7cd41bebb036995bb74fed27f588304702c3f62f2d5d80b5` |
| `chk_sqlite_decorator_signature.py` | CHK-only. SQLite's decorator on `commit()` | `8a886fa706c17ab5e26b6a34f3d4c4ecbe02b68bffa77be80183d292407b4a87` |
| `server_log_check.py` | CHK-only. Extracts the subject sessions from the server log, prints the `psql` query, builds per-run transcripts and cross-checks fates | `af41ab4e81b0ed81b34e88a2066443b716d52b73e3e004b4b2bf834ce7a0f17e` (see "Changes between attempts") |
| `tools/py8_candidate_plugin.py`, `tools/py8_commit_trace_plugin.py` | CHK-only pytest plugins: apply a candidate in every pytest process, or record what `commit()` raises | in `SHA256SUMS` |
| `tools/ppcs_py8_netguard.py`, `.pth` | The network guard installed into the Tortoise virtualenv for its suite | in `SHA256SUMS` |
| `output/repro/{release,develop}-{asyncpg,psycopg,sqlite}.rep{1,2,3}.out` | The reproduction: PyPI 1.1.9 and `develop` | |
| `output/nested/{release,develop}-{asyncpg,psycopg}-{develop,C1,C2,C3}.rep{1,2,3}.out` | Check 1, in both environments | |
| `output/sqlite-failed-commit/{develop,C1}.rep{1,2,3}.out` | Check 2 | |
| `output/after-change/{asyncpg,psycopg}-{develop,C1,C2,C3,R}.rep{1,2,3}.out`, `output/after-change/sqlite-{develop,C1,C3,R}.rep{1,2,3}.out` | `chk_after_change.py` | |
| `output/sqlite-decorator-signature.rep{1,2,3}.out` | `chk_sqlite_decorator_signature.py` | |
| `output/psql-xact-status.txt` | `pg_xact_status()` of all 180 printed transaction IDs, read with `psql` inside the container after the runs, with its query | `edfbfd00f661d3842461a65dcf3bb361ea038a53d5256fdc03ec9697b702b494` |
| `output/server-log-extract.txt` | Every server-log entry of the subject sessions: 4,527 entries | `ee9db2c55088913d5326666458bff5480e876f4b3f636ae869f164ccb2210926` |
| `output/server-log-check.txt` | `server_log_check.py check` | `25f6ccadb9bc5080c53f2ce07779a8302e24eafc202b471511e0242f72070bcc` |
| `output/server-log-transcripts.txt` | `server_log_check.py transcripts` | `2a639b859821b411a53a2afe9578ae36b6c5d2313914c7409330d44ea421aaaf` |
| `output/suite/*.txt` | Tortoise's suite and `make check` steps: baselines on `develop`, the runs under each candidate, the sequential and traced runs, the build. The checkout path is replaced by `<tortoise-checkout>`, and Homebrew's Python prefix by `<python>` | in `SHA256SUMS` |
| `branch/` | Step 2: the patch, the step-1 programs' outputs on the branch, its server-log files, and its test and check outputs, masked the same way | in `SHA256SUMS` |
| `chk_update_or_create.py`, `chk_connection_reuse.py`, `chk_explicit_commit.py` | CHK-only, for the review package: `update_or_create()` with deferred constraints; the same pooled connection after a failed COMMIT; an explicit `commit()` inside the block that fails. Each runs against a checkout named by `PY8_TORTOISE_SRC` | in `SHA256SUMS` |
| `review/` | The review package: `README.md`, `materials.md` (generated by `make_materials.py`), `assessment.md`, and the outputs of the three programs above | in `SHA256SUMS` |

Every output holds the program's complete stdout and stderr. Python's warnings go to stderr unbuffered, so in a file they can sit above the stdout lines printed before them; psycopg's "error ignored in rollback" lines in `after-change/psycopg-*` are such lines.

**Repetitions.** The three repetitions of each run are identical once the transaction IDs and memory addresses are masked, with one exception: part 4 on asyncpg, whose exception class varies with timing. `develop` gave two `InterfaceError` and one `InternalClientError`; R one `InterfaceError` and two `InternalClientError`; C1 and C2 three `InterfaceError`; C3 three `InternalClientError`. The server-log transcripts of all three repetitions are identical for every run, part 4 included.

**The full server log is not kept.** It was 9,769 lines (SHA-256 `cc13468cee17e01f5f752c7de801293f140f6f2485fde1f845f6cd0c219081f2`), captured with `docker logs` right after the runs. None of the passwords or `cluster_name` tokens occurs in it or in any file here. The rest of it is server start-up and the admin, witness and competitor sessions.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest), arm64. A throwaway container, `ppcs-py8-tortoise-pg`, on `127.0.0.1:55497`, with a tmpfs data directory, a random password and a random `cluster_name` token. Not `ppcs-postgres` |
| Server settings | `max_connections=100`, `log_connections=on`, `log_disconnections=on`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '`, and `log_statement=all` through `ALTER SYSTEM`. Read back before the runs, with the token: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout`, `idle_in_transaction_session_timeout` and `lock_timeout` 0 |
| Host | macOS 26.6.2 (25G83) arm64, colima 0.9.1 (4 CPU, 8 GiB), Docker server 28.4.0 |
| Python | 3.13.11 (Homebrew) |
| `release` environment | A fresh virtualenv with `tortoise-orm[asyncpg,psycopg]==1.1.9` from PyPI wheels (`--only-binary=:all:`): asyncpg 0.32.0, psycopg 3.3.6 (binary, libpq 18.6), psycopg-pool 3.3.3, aiosqlite 0.22.1, pypika-tortoise 0.6.5. The installed transaction code, `models.py` and `exceptions.py` are byte-identical to tag `1.1.9` (`ac3892300`); the hashes equal CHK-5's |
| `develop` environment | A local clone of `tortoise/tortoise-orm` (`<tortoise-checkout>` in the masked outputs), `develop` `ad0d6ce2b878f6d5188374eabb61d80484aedfa4`, unchanged in step 1. `uv sync --frozen --all-groups` with the extras `make deps` names (asyncpg, accel, psycopg, asyncodbc, aiomysql): asyncpg 0.31.0, psycopg 3.3.3 (libpq 18.0), psycopg-pool 3.3.0, aiosqlite 0.22.1 (SQLite 3.54.1), pyodbc 5.3.0 (it imports; unixODBC is installed through Homebrew), pytest 9.0.3, pytest-xdist 3.8.0, pytest-asyncio 1.4.0, ruff 0.15.4, mypy 1.19.1, bandit 1.9.4. uv 0.13.5 ran from a throwaway virtualenv, with its cache in a scratch directory |
| Tortoise source | `develop` is 20 commits after `1.1.9`. `backends/base/client.py`, `base_postgres/client.py`, the asyncpg, psycopg, SQLite, MySQL and ODBC clients, `transactions.py`, `exceptions.py` and `tests/test_transactions.py` are byte-identical to `1.1.9`. In `models.py`, `_create_or_get()` differs only in `raise exc` becoming `raise` |

## Commands

The password is replaced by `<password>`, and the token by `<token>`. `<release>` and `<develop>` are the two environments' interpreters. Every `docker` command ran with `DOCKER_CONTEXT=colima`.

```sh
docker run -d --name ppcs-py8-tortoise-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55497:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_connections=on \
  -c log_disconnections=on -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '
docker exec ppcs-py8-tortoise-pg psql -U postgres -c "ALTER SYSTEM SET log_statement = 'all'" -c "SELECT pg_reload_conf()"
# Then `show cluster_name` through 127.0.0.1:55497 returned <token>.

# From this directory, each run a separate process, one after another, in this order.
# A Python driver ran them with only PATH, HOME, DATABASE_URL and the variable named per run.
export DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55497/postgres"
for env in release develop; do for b in asyncpg psycopg sqlite; do for rep in 1 2 3; do
  PY8_APP=py8-repro-$env-$b-r$rep <$env> -I -B tortoise_commit_translation.py $b > output/repro/$env-$b.rep$rep.out 2>&1
done; done; done
for env in develop release; do for b in asyncpg psycopg; do for c in develop C1 C2 C3; do for rep in 1 2 3; do
  PY8_REP=${env:0:3}$rep <$env> -I -B chk_nested_release.py $b $c > output/nested/$env-$b-$c.rep$rep.out 2>&1
done; done; done; done
for c in develop C1; do for rep in 1 2 3; do
  <develop> -I -B chk_sqlite_failed_commit.py $c > output/sqlite-failed-commit/$c.rep$rep.out 2>&1
done; done
for b in asyncpg psycopg; do for c in develop C1 C2 C3 R; do for rep in 1 2 3; do
  PY8_REP=dev$rep <develop> -I -B chk_after_change.py $b $c > output/after-change/$b-$c.rep$rep.out 2>&1
done; done; done
for c in develop C1 C3 R; do for rep in 1 2 3; do
  PY8_REP=dev$rep <develop> -I -B chk_after_change.py sqlite $c > output/after-change/sqlite-$c.rep$rep.out 2>&1
done; done

# After the runs:
docker logs ppcs-py8-tortoise-pg > <scratch>/server.full.log 2>&1
python3 -I -B server_log_check.py extract <scratch>/server.full.log output/server-log-extract.txt
python3 -I -B server_log_check.py query . > <scratch>/psql-query.sql
docker exec -i ppcs-py8-tortoise-pg psql -U postgres -d postgres < <scratch>/psql-query.sql > <scratch>/psql-out.txt
# output/psql-xact-status.txt holds the query, then that output.
python3 -I -B server_log_check.py check . output/psql-xact-status.txt output/server-log-extract.txt > output/server-log-check.txt
python3 -I -B server_log_check.py transcripts output/server-log-extract.txt > output/server-log-transcripts.txt

# Later, the one-off decorator check, three times:
<develop> -I -B chk_sqlite_decorator_signature.py > output/sqlite-decorator-signature.rep$rep.out 2>&1
```

All 114 recorded runs exited 0, between 03:40:53 and 03:42:21 UTC. `server_log_check.py check` exited 0.

## Results

### The reproduction

Each row held in all six runs per backend (three per environment). The two environments differ only in the version line and in frame line numbers.

| Arm | asyncpg | psycopg | SQLite | Database |
| --- | --- | --- | --- | --- |
| `DeferredChild.create()` in `in_transaction()` | `asyncpg.exceptions.ForeignKeyViolationError` 23503, raised by `commit()` | `psycopg.errors.ForeignKeyViolation` 23503, raised by `commit()` | `sqlite3.IntegrityError` `SQLITE_CONSTRAINT_FOREIGNKEY`, raised by `commit()` | PostgreSQL: `aborted`; 0 rows. SQLite: 0 rows |
| `ImmediateChild.create()` in `in_transaction()` | `tortoise.exceptions.IntegrityError`, raised by the INSERT; cause and context the driver's error | the same; context the driver's error, no cause | the same; context the driver's error, no cause | `aborted`; 0 rows |
| `DeferredChild.get_or_create()` | the driver's error, from `commit()` | the driver's error; context `DoesNotExist` | the driver's error; context `DoesNotExist` | 0 rows |
| `ImmediateChild.get_or_create()` | `tortoise.exceptions.IntegrityError` | the same | the same | 0 rows |

The log shows the deferred arm's `COMMIT` answered with ERROR 23503 in each PostgreSQL run. In the deferred `get_or_create()` arm it shows a SELECT, then `BEGIN`, the INSERT and the failed `COMMIT`, and nothing after. In the immediate arm the INSERT fails, `ROLLBACK` follows, and then a second SELECT: `_create_or_get()`'s fallback.

### Check 1: a nested block exits normally on an aborted transaction

Each row held in all six runs, three per environment. The statements are from the server log.

| Backend, candidate | Reaches the application | After `RELEASE` fails with 25P02 | Python log records | Outer transaction | Follow-up |
| --- | --- | --- | --- | --- | --- |
| asyncpg, `develop`, C2, C3 | `asyncpg.exceptions.InFailedSQLTransactionError` | `ROLLBACK;` (asyncpg's `Transaction.rollback()`, called by the outer block) | none | `aborted`, 0 rows | same backend; `committed` |
| asyncpg, C1 | `tortoise.exceptions.TransactionManagementError`, cause and context the driver's error | `ROLLBACK` (asyncpg's `Connection.reset()`, when the pool takes the connection back), then the reset query | `ERROR asyncio: Resetting connection with an active transaction <asyncpg.connection.Connection object at 0x…>` | `aborted`, 0 rows | same backend; `committed` |
| psycopg, `develop`, C2, C3 | `psycopg.errors.InFailedSqlTransaction` | `ROLLBACK` (psycopg's transaction exit, called by the outer block) | none | `aborted`, 0 rows | same backend; `committed` |
| psycopg, C1 | `tortoise.exceptions.TransactionManagementError`, context the driver's error | nothing; the session disconnects | three `WARNING psycopg.pool`: rolling back returned connection; rollback failed: `ProgrammingError: Explicit rollback() forbidden within a Transaction context…` Discarding connection; discarding closed connection | `aborted`, 0 rows | a new backend; `committed` |

asyncpg's two sources are told apart by the text: `Transaction` sends `'ROLLBACK;'` (`asyncpg/transaction.py`, 203), and `Connection.reset()` sends `"ROLLBACK"` after reporting "Resetting connection with an active transaction" (`asyncpg/connection.py`, 1537–1542, asyncpg 0.31.0). Both are Src.

### Check 2: SQLite after a failed COMMIT

Both candidates, three of three; they differ only in step 1's exception class.

| Step | Result | Shared connection in a transaction | `connections.get('default')` | Committed, by a separate connection |
| --- | --- | --- | --- | --- |
| 1. `in_transaction()`, deferred violation | `develop`: raw `sqlite3.IntegrityError`; C1: `tortoise.exceptions.IntegrityError` | True | `SqliteClient` | nothing |
| 2. plain `Note.create(id=1)` | returned normally | True | `SqliteClient` | nothing |
| 3. `in_transaction()` writes note 2 | raw `sqlite3.IntegrityError`, raised by `begin()` → `aiosqlite` `commit()` | True | `SqliteTransactionWrapper` | nothing |
| 4. `in_transaction()` writes note 3 | returned normally; `in_transaction()` had returned a `NestedTransactionContext` | True | `SqliteTransactionWrapper` | nothing |
| 5. plain `Note.create(id=4)` | returned normally | True | `SqliteTransactionWrapper` | nothing |
| 6. `Tortoise.close_connections()` | `AttributeError: 'SqliteTransactionWrapper' object has no attribute 'filename'`; the connection was closed | — | — | nothing |

### After the change

Each row held in three of three, on asyncpg and psycopg unless marked.

| Case | `develop` | C1, C2, C3, R |
| --- | --- | --- |
| Deferred violation, `in_transaction()` | the driver's error | `tortoise.exceptions.IntegrityError`; `aborted` |
| Deferred violation inserted in a nested block | the nested block exits normally; the driver's error from the outer `commit()` | the nested block exits normally; `tortoise.exceptions.IntegrityError` |
| `get_or_create()`, deferred foreign key | the driver's error; no SELECT after the failed COMMIT | one SELECT after the failed COMMIT, then `tortoise.exceptions.IntegrityError` |
| `get_or_create()` racing a deferred UNIQUE | waits on the competitor at `COMMIT`, then the driver's `UniqueViolation` 23505; one row, the competitor's | waits at `COMMIT`; one SELECT after the failed COMMIT; returns `id=100, created=False` |
| `rollback()` after `pg_terminate_backend()` | asyncpg: `InterfaceError` or `InternalClientError`; psycopg: the application's `AppError` | the same |
| SQLite, `get_or_create()`, deferred foreign key (C1, C3, R) | raw `sqlite3.IntegrityError`; 0 rows | returns `created=False`; 0 rows |

### Tortoise's test suite

The Makefile's options, `-n auto --cov=tortoise --cov-append --cov-branch --tb=native -q -m "not benchmark" --cov-report=`, with `PYTHONDEVMODE=1`. `-n auto` started 18 workers. `TORTOISE_TEST_DB` was `sqlite://:memory:`, `asyncpg://postgres:<password>@127.0.0.1:55497/test_{}`, or the same with `psycopg://`. The PostgreSQL runs used a second throwaway container (see "Changes between attempts"). The network guard in `tools/` allowed Python sockets to reach only 127.0.0.1:55497; libpq and ODBC connect from C, past it.

| Run | SQLite | asyncpg | psycopg |
| --- | --- | --- | --- |
| `develop`, local time zone (PDT) | 2 failed, 2117 passed, 149 skipped, 2 xfailed (twice) | 5 failed, 2191 passed, 73 skipped, 1 xfailed | 2 failed, 2195 passed, 72 skipped, 1 xfailed |
| `develop`, `TZ=UTC` | 2 failed, 2117 passed (twice) | 2196 passed, 73 skipped, 1 xfailed | 2197 passed, 72 skipped, 1 xfailed |
| C1, `TZ=UTC` | 2119 passed | 2 failed, 2194 passed | 2197 passed |
| C2, `TZ=UTC` | — | 2 failed, 2194 passed | 2 failed, 2195 passed |
| C3, `TZ=UTC` | 2119 passed | 2196 passed | 2 failed, 2195 passed |
| `develop` through the plugin, `TZ=UTC` | 2 failed, 2117 passed | — | — |
| sequential (`-p no:xdist`), `TZ=UTC` | `develop` and C1: 2119 passed | — | — |

- **The "2 failed"** are always `tests/test_datetime_field_bug.py::test_datetimefield_auto_value_stays_naive_without_use_tz[auto_now]` and `[auto_now_add]`. They pass when their file runs alone, and in the sequential runs, with and without C1. The test sets `USE_TZ=False` with `monkeypatch.setenv`, while `tortoise.timezone.get_use_tz()` is `functools.cache`d (Src), so the result depends on which test ran earlier in the same worker. They come and go between runs, with and without a candidate.
- **The three other asyncpg failures** under the local time zone are in `tests/fields/test_time.py`. They pass under `TZ=UTC`, and the stored value is shifted by the Pacific offset.
- **Every pytest process applied the candidate.** All 19 per run, the controller and 18 workers, wrote a marker showing `commit()` wrapped.
- **Static checks on `develop`:** `ruff format --check` (452 files already formatted), `ruff check` (all checks passed), `mypy` (no issues in 452 source files), `bandit` (exit 0), `uv build` and `twine check` (passed).
- **Leftover databases.** Each PostgreSQL suite run left about 290 `test_*` databases behind, about 3 GB. They were dropped between runs.

## Independent verification

Four sources agree for all 180 printed transaction IDs (`output/server-log-check.txt`: 0 problems).

1. **The programs' witness connections:** psycopg in autocommit, separate from the Tortoise pool; for SQLite, a separate `sqlite3` connection on the same file.
2. **`psql` inside the container,** after all runs, with no Python driver involved: 132 `aborted`, 48 `committed`.
3. **The server's statement log.** `server_log_check.py` grouped each subject session's statements into transactions, matched each printed ID to the transaction that carried it, and checked how it ended:
   - 42 `COMMIT` answered with ERROR 23503;
   - 42 `ROLLBACK` after an immediate violation;
   - 42 `ROLLBACK` after 23503 and 25P02;
   - 6 sessions that ended without either: check 1, psycopg, C1;
   - 48 `COMMIT`s that succeeded: the follow-ups.
4. **Per-run transcripts** (`output/server-log-transcripts.txt`): masked, and identical across the repetitions of every run.

**A log-reading note.** After an error aborts a top-level transaction, PostgreSQL 18.6 logged the statements up to and including `ROLLBACK` with a vxid of `<backend>/0`, not the transaction's vxid. The checker attaches those entries to the session's current transaction. Inside a savepoint, the vxid did not change.

## Source reading

Labelled Src. Lines are `develop` `ad0d6ce2b878`'s, and identical in 1.1.9 for these files.

| Backend | `begin()` | `commit()` | `rollback()` | Translator |
| --- | --- | --- | --- | --- |
| asyncpg `client.py` | decorated, 189–192 | not, 197–203 | not, 208–214 | 89–97: classes 42 and 22 → `OperationalError`, 23 → `IntegrityError`, 25 → `TransactionManagementError`, each `from exc` |
| psycopg `client.py` | decorated, 249–252 | not, 257–264 | not, 269–276 | 203–218: the same classes, plus `UndefinedTable`; no `from exc`, so the driver's error is only the context |
| MySQL `client.py` | decorated, 259–262 | not, 264–268 | not, 276–280 | 46–62, signature `(self, *args)`: `OperationalError`, `ProgrammingError`, `DataError`, `InternalError`, `NotSupportedError` → `OperationalError`; `IntegrityError` → `IntegrityError` |
| SQLite `client.py` | inline `try/except`, `sqlite3.OperationalError` → `TransactionManagementError` only, 236–241 | not, 249–253 | not, 243–247 | 38–48, signature `(self, query, *args)`: `OperationalError` → `OperationalError`, `IntegrityError` → `IntegrityError` |
| ODBC `client.py` | not, 192–194 | not, 196–201 | not, 203–208 | 35–52, signature `(self, *args)`: five classes → `OperationalError`; `IntegrityError` and the catch-all `pyodbc.Error` → `IntegrityError` |

- **Contexts.** `TransactionContextPooled.__aexit__` (`backends/base/client.py` 373–386) calls `commit()` on a clean exit, and skips `rollback()` when `exc_type is TransactionManagementError`. `NestedTransactionContext.__aexit__` (399–406) calls `release_savepoint()`, which is `commit()` on asyncpg and psycopg, with the same skip. `SqliteTransactionContext.__aexit__` (`sqlite/client.py` 200–211) has the same shape. None of them rolls back when `commit()` raises.
- **SQLite's `begin()`** commits first (238). When the previous COMMIT failed and left the transaction open, that COMMIT fails again, and `begin()` lets the `IntegrityError` through. `SqliteTransactionContext.__aenter__` (193–198) has then already set the context variable to the wrapper, and `__aexit__` never runs.
- **`in_transaction()`** returns `connections.get(name)._in_transaction()` (`transactions.py` 33–44). On a transaction wrapper that is a `NestedTransactionContext`.
- **`Model._create_or_get()`** (`models.py` 1300–1316) catches `IntegrityError` around `in_transaction()` and `create()`, then tries `get()` before re-raising.
- **History.** No backend's `commit()` or `rollback()` has carried `translate_exceptions`; I checked the decorator lines of every commit to each client file. `begin()`'s decorator descends from `retry_connection`, a reconnect-and-retry wrapper that `77cb7e7` (2019-05-26, "Added automatic PostgreSQL connection retry") put on asyncpg's `start()` only. `223ab91` (2019-11-21) renamed it `translate_exceptions` and removed the reconnect. Whether leaving `commit()` out was deliberate is not recorded.
- **Correction to the tracker and roadmap.** They say every backend decorates `begin()`. SQLite and ODBC do not.

## Upstream

Checked 2026-10-25, 03:14–03:20 UTC.

- **`develop`** is still `ad0d6ce2b878` (2026-10-24 17:49 UTC). PyPI's latest is 1.1.9 (uploaded 2026-10-14).
- **PR #2293** (`feat(transactions): add on_commit()`) is open, head `b6f7dfcb`, last activity 2026-10-07. In every backend it adds `self._committed = True` after `self._finalized = True` in `commit()`. A decorator line above `async def commit` would sit just outside its hunks' context lines. Src; no merge was tried.
- **Duplicates.** 34 queries through the search API with the words unquoted gave 190 distinct issues and pull requests, screened by title. I opened #1796, #2007, #1861, #1816, #792, #1404, #2169, #2276, #2060, #1094, #1757 and #2293. None reports this.
- **Nearest:**
  - **#1796** (merged 2024-12-03) restores the connection context when `commit()` or `rollback()` raises. It added `test_commit_raising_exception` and `test_rollback_raising_exception`, which replace `commit` and `rollback` on the instance with a `Mock`, so a class-level decorator does not reach them. It does not translate anything.
  - **#2007:** a raw `psycopg.OperationalError` ("the connection is closed") from `in_transaction()`. The translator maps neither that class nor any candidate.
  - **#1757:** SQLite, "cannot start a transaction within a transaction" in `bulk_create`. The reporter suspected cancellation. It shares a symptom with the SQLite candidate below; nothing links them.

## What this establishes, and what it does not

- **Established**, on Tortoise 1.1.9 and `develop` `ad0d6ce2b878`, with PostgreSQL 18.6 and SQLite 3.54.1:
  - a deferred violation that COMMIT reports reaches the application as the driver's exception on asyncpg, psycopg and SQLite, and `get_or_create()` then skips its fallback;
  - decorating `commit()` alone (C1) changes nested blocks: a `RELEASE` that fails on an aborted transaction becomes `TransactionManagementError`, and the outer block no longer rolls back itself. asyncpg's pool then rolls back and logs an error; psycopg's pool discards the connection;
  - C2 and C3 translate the COMMIT-time error and leave nested blocks as they are;
  - on SQLite, any candidate makes `get_or_create()` return an uncommitted row after a failed COMMIT;
  - no test in Tortoise's suite fails because of a candidate, and none makes `commit()` raise a driver error.
- **Source reading only:**
  - the history of the decorators;
  - which errors each translator maps;
  - MySQL's and ODBC's behaviour.
- **Not run here:**
  - MySQL, MSSQL and Oracle. MySQL would need a second container, and port 3306 belongs to another project;
  - other PostgreSQL versions; Linux;
  - a failing COMMIT for any reason but a deferred constraint (serialization failure, a lost connection, a deferred constraint trigger);
  - `atomic()`, which uses the same contexts (Src);
  - `update_or_create()`, which also calls `_create_or_get()` (Src);
  - code that catches the driver's exception today. The PR changes what it receives.

## A separate candidate: SQLite after a failed COMMIT

Check 2 shows, on `develop`, three of three, that after a COMMIT fails on Tortoise's SQLite backend the shared connection stays inside the transaction. Every later write on that connection then returns normally and is lost, `in_transaction()` either raises from `begin()` or becomes a savepoint, and `close_connections()` raises `AttributeError`. This is independent of PY-8: C1 changes only the first exception's class.

- **Observed trigger:** a deferred foreign key. SQLite's documentation, read 2026-10-25:
  - [`foreignkeys.html`](https://www.sqlite.org/foreignkeys.html): "COMMIT will fail as long as foreign key constraints remain in violation". Its example inserts the missing parent row after the failed COMMIT and commits again;
  - [`lang_transaction.html`](https://www.sqlite.org/lang_transaction.html): a COMMIT can also fail with `SQLITE_BUSY` while another connection reads, and "When COMMIT fails in this way, the transaction remains active". That trigger was not run here.
- **Interaction with PY-8.** Translating SQLite's `commit()` lets `get_or_create()` reach its fallback inside that leftover transaction, where it returns the uncommitted row (observed, nine of nine). Translation on SQLite should wait until the leftover transaction is handled, or come with that change.
- **Status:** recorded as a candidate for the tracker. No upstream search has been made for it yet, beyond the PY-8 queries above.

## Step 2: the branch

Run on 2026-10-25, 04:21–04:31 UTC. The user chose approach A that morning (UTC): translate only integrity errors in `commit()`, on asyncpg and psycopg. That is candidate C3, written into the source.

- **Branch:** `fix/commit-integrity-error` in the clone, from `origin/develop` `ad0d6ce2b878`, with no upstream set. Nothing is committed.
- **`branch/fix.patch`** is the whole diff: 4 files, 44 lines added and 4 removed. SHA-256 `ac1bad08bc41016ca597885db9170cbe6065eb9d6dcbc66dfce24b60356a1540`. `branch/src.patch` is its `tortoise/` part, used to reverse and re-apply the source change.
  - **`tortoise/backends/asyncpg/client.py`:** `commit()` catches `asyncpg.IntegrityConstraintViolationError` around `self.transaction.commit()`, and raises `IntegrityError(exc) from exc`, as the module's translator does.
  - **`tortoise/backends/psycopg/client.py`:** `commit()` catches `psycopg.errors.IntegrityError` around `self._transaction.__aexit__(None, None, None)`, and raises `exceptions.IntegrityError(exc)` without `from`, as that module's translator does.
  - Both carry the same two-line comment: why COMMIT is translated at all, and why only integrity errors.
  - **`tests/test_transactions.py`:** two tests, run on PostgreSQL only (`requireCapability(dialect="postgres")`), in a fresh database (`db_isolated`). A helper adds `intfields.intnum REFERENCES intfields (id) DEFERRABLE INITIALLY DEFERRED`.
    - `test_commit_raising_integrity_error`: `IntFields.create(intnum=999)` inside `in_transaction()` raises `IntegrityError`, and no row remains.
    - `test_get_or_create_commit_raising_integrity_error`: `IntFields.get_or_create(intnum=999)` raises `IntegrityError`.
  - **`CHANGELOG.rst`:** one entry under 1.1 → Unreleased → Fixed. It ends with `(#XXXX)`, to be replaced by the PR number after the PR is opened.
- **Reworded after the review package (06:03 UTC), at the user's request.** The changelog entry now names `update_or_create()` alongside `get_or_create()`.
  - `branch/fix-v2.patch` (SHA-256 `8f2244c160004a266908ebb260f8ee080c61cf895402636befb843f6b3bdcfd8`) is the current diff. It differs from `branch/fix.patch` only in that line, and its `tortoise/` part is byte-identical to `branch/src.patch`.
  - All runs in this section used `fix.patch`. Nothing was rerun for a changelog-only change.

### Commands

The container was a new `ppcs-py8-tortoise-pg`: same image and port, a new password and token, and a disk-backed anonymous volume, as for step 1's suite runs. It was removed with its volume at 04:31 UTC. `<develop>` is the clone's virtualenv, which imports the checkout, so it ran the branch.

```sh
docker run -d --name ppcs-py8-tortoise-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55497:5432 -v /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_connections=on \
  -c log_disconnections=on -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '
docker exec ppcs-py8-tortoise-pg psql -U postgres -c "ALTER SYSTEM SET log_statement = 'all'" -c "SELECT pg_reload_conf()"

# The step-1 programs, unchanged (their hashes still match SHA256SUMS), with no runtime patch:
# "candidate develop" in these outputs means that, and the printed source digest is the branch's.
export DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55497/postgres"
for b in asyncpg psycopg sqlite; do for rep in 1 2 3; do
  PY8_APP=py8-repro-branch-$b-r$rep <develop> -I -B tortoise_commit_translation.py $b > branch/output/repro/$b.rep$rep.out 2>&1
done; done
for b in asyncpg psycopg; do for rep in 1 2 3; do
  PY8_REP=$rep <develop> -I -B chk_nested_release.py $b develop > branch/output/nested/$b.rep$rep.out 2>&1
done; done
for b in asyncpg psycopg sqlite; do for rep in 1 2 3; do
  PY8_REP=$rep <develop> -I -B chk_after_change.py $b develop > branch/output/after-change/$b.rep$rep.out 2>&1
done; done
# Then the log, extract, psql query, check and transcripts as in step 1, with "branch" as the directory.

docker exec ppcs-py8-tortoise-pg psql -U postgres -c "ALTER SYSTEM RESET log_statement" -c "SELECT pg_reload_conf()"

# In the checkout: the new tests on develop's source, then on the branch, 3 times per PostgreSQL backend.
git apply -R <src.patch>
PYTHONDEVMODE=1 TORTOISE_TEST_DB=<url> .venv/bin/pytest -q -rA --tb=line tests/test_transactions.py -k commit_raising_integrity_error
git apply <src.patch>   # git diff then hashed the same as branch/fix.patch
PYTHONDEVMODE=1 TORTOISE_TEST_DB=<url> .venv/bin/pytest -q -rA --tb=line tests/test_transactions.py -k commit_raising_integrity_error

# The full suite, with the Makefile's options, under TZ=UTC and under the local time zone:
PYTHONDEVMODE=1 TORTOISE_TEST_DB=<url> .venv/bin/pytest -n auto --cov=tortoise --cov-append --cov-branch --tb=native -q -m "not benchmark" --cov-report=
# The make check steps: ruff format --check, ruff check, mypy, bandit -c pyproject.toml -r, on
# tortoise/ examples/ tests/ conftest.py; then uv build and twine check dist/*.
```

`<url>` was `sqlite://:memory:`, `asyncpg://postgres:<password>@127.0.0.1:55497/test_{}`, or the same with `psycopg://`. Leftover `test_*` databases were dropped after each PostgreSQL suite run. The versions are step 1's `develop` environment: Python 3.13.11, asyncpg 0.31.0, psycopg 3.3.3, aiosqlite 0.22.1, the same image digest.

### Results

All 24 program runs exited 0. Their repetitions are identical once the transaction IDs and addresses are masked, except part 4 on asyncpg, as in step 1.

| Case | asyncpg and psycopg on the branch | SQLite on the branch |
| --- | --- | --- |
| Deferred violation, `in_transaction()` | `tortoise.exceptions.IntegrityError`; `aborted`, 0 rows | the raw `sqlite3.IntegrityError`, unchanged |
| Deferred violation, `get_or_create()` | `tortoise.exceptions.IntegrityError`, after one fallback SELECT in the log | unchanged |
| Immediate violation, both arms | `tortoise.exceptions.IntegrityError`, as before | as before |
| Check 1: nested block on an aborted transaction | the driver's class-25 error, as on `develop`; the outer block sends `ROLLBACK;` (asyncpg) or `ROLLBACK` (psycopg); no log records; the same backend serves the follow-up | — |
| Deferred violation inserted in a nested block | `tortoise.exceptions.IntegrityError` from the outer `commit()` | unchanged |
| `get_or_create()` racing a deferred UNIQUE | returns `id=100, created=False` | — |
| `rollback()` after `pg_terminate_backend()` | as on `develop` | — |

**Independent verification.** All 36 printed transaction IDs agree across the witness, `psql` (30 `aborted`, 6 `committed`) and the server log (`branch/output/server-log-check.txt`: 0 problems). The transcripts of every run's three repetitions are identical. The full server log was 2,216 lines, SHA-256 `5ebd21f49e6f4662873badaf7a79c93c1e74b923f242b1c8e7e8cdb8a7360810`, and is not kept.

**The new tests.** On `develop`'s source, both failed on asyncpg and on psycopg, three of three, with the driver's `ForeignKeyViolationError` or `ForeignKeyViolation`. On the branch both passed, three of three. On SQLite both were skipped ("Capability dialect != postgres").

**Tortoise's suite.** No failure is new.

| Run | `develop` (step 1) | Branch |
| --- | --- | --- |
| SQLite, `TZ=UTC` | 2 failed, 2117 passed, 149 skipped, 2 xfailed | 2 failed, 2117 passed, 151 skipped, 2 xfailed |
| asyncpg, `TZ=UTC` | 2196 passed, 73 skipped, 1 xfailed | 2198 passed, 73 skipped, 1 xfailed |
| psycopg, `TZ=UTC` | 2197 passed, 72 skipped, 1 xfailed | 2199 passed, 72 skipped, 1 xfailed |
| SQLite, local time zone | 2 failed, 2117 passed, 149 skipped, 2 xfailed | 2 failed, 2117 passed, 151 skipped, 2 xfailed |
| asyncpg, local time zone | 5 failed, 2191 passed | 3 failed, 2195 passed |
| psycopg, local time zone | 2 failed, 2195 passed | 2199 passed |

- The SQLite failures are the order-dependent `test_datetime_field_bug.py` pair. The three asyncpg failures under the local time zone are the `tests/fields/test_time.py` failures that pass under UTC. Both are described under "Tortoise's test suite".
- The two extra passes on PostgreSQL, and the two extra skips on SQLite, are the new tests.
- **Watched tests,** run by name on all three backends under `TZ=UTC`: `test_commit_raising_exception`, `test_rollback_raising_exception`, the nested-transaction tests (seven in `test_transactions.py`, one in `test_concurrency.py`), `test_get_or_create_transaction_using_db`, and the `get_or_create` tests in `test_concurrency.py` and `test_model_methods.py`. They passed (`watched-tests-*.txt`: 41 passed on asyncpg and psycopg; 39 passed and 2 skipped on SQLite).
- In the two mocked tests, asyncpg's pool logs "Resetting connection with an active transaction", because the mock leaves the real transaction open. It does so on `develop` too (`mocked-tests-develop-asyncpg.txt`).
- **Static checks on the branch:** `ruff format --check` (452 files already formatted), `ruff check` (all checks passed), `mypy` (no issues in 452 source files), `bandit` (exit 0), `uv build` and `twine check` (passed).

**Compatibility.** On asyncpg and psycopg, code that catches the driver's exception when `in_transaction()` exits now receives `tortoise.exceptions.IntegrityError`. The same applies to `atomic()`, which uses `in_transaction()` (Src).
- The driver's exception is still `args[0]`. On asyncpg it is also `__cause__` and `__context__`; on psycopg only `__context__`.
- `get_or_create()` now treats such an error like one from the INSERT: it tries the fallback `get()`, then returns the existing row or re-raises `IntegrityError` (observed). `update_or_create()` calls the same `_create_or_get()` (Src; not run).
- Unchanged by construction (Src), and unchanged where these runs covered them: other errors at COMMIT, `rollback()`, the other backends, and nested blocks.

## Changes between attempts

- **Development runs on a separate container.** Before the recorded runs, every program ran on a container with the same image and port but a different password and token. Its log prefix lacked `sqlstate=%e`, and statement logging was switched on part-way. It was removed before the recorded runs, and none of its output is kept. The trials changed the programs; the recorded runs used the final versions, whose hashes are above:
  - the frame paths' masking, which first kept only the last package name;
  - frames from every program in this directory, not only the reproduction's, are left out;
  - the driver's error code is read through any Tortoise exception that wraps it;
  - `PY8_APP` and `PY8_REP` name the sessions for the log, and the application name is no longer printed;
  - candidate C3 was added;
  - check 2 gained the context class, a guarded close, and step 7, which closes the connection directly.
- **Bytecode.** The trials wrote a `__pycache__` into this directory. It was removed, and the recorded runs used `-B`.
- **`server_log_check.py`** was revised after the recorded runs: entries with a vxid of `<backend>/0` are attached to the current transaction, and a SELECT's column list is sorted before transcripts are compared, since Tortoise orders it differently in each process. `extract` did not change; the extract was made before the revision.
  - For the review package it also extracts `py8-uoc-` and `py8-reuse-` sessions. With that change, the step-1 and step-2 checks and transcripts reproduce byte-identically.
- **The first suite attempt filled the evidence container.** It was the asyncpg baseline, on the tmpfs (3.9 GB, the colima default of half the VM's memory). About 290 leftover `test_*` databases and 1 GB of WAL filled it, and the run ended in `DiskFullError`. That container was removed at about 03:49 UTC, after its log and the `psql` check had been saved. Its output is not kept: the next run overwrote it.
  - The suite then ran on a second throwaway container, with the same image and port, a new password and token, default settings, and a disk-backed anonymous volume. It was removed with its volume at 04:07 UTC.
  - Two other sessions' containers, running at the start, had gone by then. Docker's event buffer does not reach back far enough to say when, and the VM's kernel log shows no OOM kill.
- **`chk_sqlite_decorator_signature.py`.** Its first three runs printed a Tortoise `RuntimeWarning` carrying a local path. The program now filters that warning, and the kept outputs are the three runs after the change.
