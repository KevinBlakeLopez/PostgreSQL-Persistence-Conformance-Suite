# CHK-4: SQLAlchemy's `after_rollback` when a `COMMIT` reply is lost and PostgreSQL commits

Run on 2026-10-25 (US Pacific); the server log is in UTC, 15:32–15:35. Written by: Claude Opus 5.5 (max).

This is check CHK-4 from [`../../python-upstream-contribution-roadmap.md`](../../python-upstream-contribution-roadmap.md) (§11, line 918), for PY-4.

It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies. It uses one harness module unchanged: the category-E proxy, [`harness/lib/pg-wire-proxy.mjs`](../../../harness/lib/pg-wire-proxy.mjs). The independent checks are under "Independent verification".

The facts for the author are in [`FACTS.md`](FACTS.md). SQLAlchemy's rules forbid AI-written prose in its discussions, issues and PRs, so nothing here is text to post, and nothing was posted.

## Question

The roadmap's CHK-4 row asks: "Without cancellation, does `after_rollback` fire when the `COMMIT` reply is lost and PostgreSQL commits? Check a sync `Session` on psycopg, and `AsyncSession`."

- **What it tests.** Hypothesis H-b (roadmap line 138), which rested on source reading.
- **What turns on it.** The roadmap's §D (line 311): if a lost reply gives the same claim, PY-4 concerns unknown outcomes in general, not anyio.

## Answer

**Yes.** This holds on SQLAlchemy 2.1.6 and 2.1.5, with `Session` on psycopg and with `AsyncSession` on asyncpg and on psycopg, 3 of 3 each:

- **PostgreSQL committed.** By the time the block raised, `pg_xact_status()` already read `committed`. The row was visible, with `xmin` equal to the transaction's xid.
- **The application.** The block raised a disconnect error, and the connection was invalidated.
- **The events.** The ORM fired `after_rollback` and `after_soft_rollback`.
- **No rollback.** No DBAPI rollback was attempted, and none reached the server.

The event sequence is P3's level-triggered sequence, with a lost reply in place of the cancellation.

A rejected `COMMIT`, added as a comparison, fires the same events. There, PostgreSQL did roll back.

## Results

There are 18 cells (2 versions × 3 stacks × 3 arms), each run 3 times: 54 runs, all valid.

- **Within each cell,** the three outputs are byte-identical.
- **Across versions,** every cell's output is the same on 2.1.5 and 2.1.6, apart from the version field.

| Arm (unit 1) | Fate when the block raised or returned | Marker row | ORM events | DBAPI rollback after `COMMIT` | Unit 1's backend in the server log after `COMMIT` |
| --- | --- | --- | --- | --- | --- |
| `lost-reply`: the proxy drops the reply to `COMMIT` | `committed` | visible, `xmin` = unit 1's xid | `after_rollback`, `after_soft_rollback` | none: `do_rollback` was not called | only its disconnection |
| `rejected` (added): a deferred foreign key fails at `COMMIT` | `aborted` | absent | `after_rollback`, `after_soft_rollback` | the pool's reset calls `do_rollback` after `after_rollback`, but no `ROLLBACK` reaches the server | `ERROR` `23503`, then unit 2's `BEGIN` |
| `no-fault` (the control) | `committed` | visible, `xmin` = unit 1's xid | `after_commit` | — | unit 2's `BEGIN` |

What the application saw from unit 1:

| Stack | `lost-reply` | `rejected` |
| --- | --- | --- |
| `sync-psycopg`: `Session.begin()` | `sqlalchemy.exc.OperationalError`: "(psycopg.OperationalError) consuming input failed: server closed the connection unexpectedly"; `connection_invalidated` true | `sqlalchemy.exc.IntegrityError` (`psycopg.errors.ForeignKeyViolation`); `connection_invalidated` false |
| `async-asyncpg`: `AsyncSession.begin()` | `sqlalchemy.exc.DBAPIError`: "(sqlalchemy.dialects.postgresql.asyncpg.Error) connection was closed in the middle of operation"; `connection_invalidated` true | `sqlalchemy.exc.IntegrityError` (`AsyncAdapt_asyncpg_dbapi.ForeignKeyViolationError`); `connection_invalidated` false |
| `async-psycopg`: `AsyncSession.begin()` | the same as `sync-psycopg` | the same as `sync-psycopg` |

Unit 2, a plain write on the same engine, committed normally in all 54 runs. After a lost reply it ran on a new backend. Otherwise it reused unit 1's backend, in a new transaction.

### Event sequences

These are verbatim from `output/sa-2.1.6/*.rep1.out`, between the program's `--unit 1--` and `--unit 1 ended--` markers, shown with the psycopg exception classes. The three stacks differ only in the exception class.

```text
lost-reply  connect 1: through the proxy → pool.first_connect → dialect.do_rollback → core.commit
            → dialect.do_commit → dialect.do_commit raised psycopg.OperationalError
            → pool.invalidate → pool.close → pool.checkin → orm.after_rollback → orm.after_soft_rollback
rejected    connect 1: direct → pool.first_connect → dialect.do_rollback → core.commit
            → dialect.do_commit → dialect.do_commit raised psycopg.errors.ForeignKeyViolation
            → orm.after_rollback → pool.reset → dialect.do_rollback → pool.checkin → orm.after_soft_rollback
no-fault    connect 1: direct → pool.first_connect → dialect.do_rollback → core.commit
            → dialect.do_commit → orm.after_commit → pool.reset → dialect.do_rollback → pool.checkin
```

The `dialect.do_rollback` right after `pool.first_connect` is SQLAlchemy's own. It ends dialect initialization on a new connection, before unit 1's transaction begins.

For comparison, P3's level-triggered rows (roadmap §D): `core.commit`, the cancellation, `pool.invalidate`, `pool.close`, `pool.checkin`, `orm.after_rollback`, `orm.after_soft_rollback`.

## Added beyond the brief

Each item is labelled "added" where it appears.

- **The `rejected` arm.** The roadmap's §D says, by source reading, that the same event follows server-rejected COMMITs. This arm shows it at runtime, and gives the contrast: there, PostgreSQL did roll back.
- **SQLAlchemy 2.1.5 next to 2.1.6.** P3 ran both, and 2.1.5 is the PPCS adapter's pin.
- **Unit 2,** kept from P3. It asks whether the next unit of work on the pool gets a clean transaction.
- **Instrumentation P3 did not have:**
  - a wrapper around the dialect's `do_commit` and `do_rollback`, which records whether a DBAPI rollback was attempted;
  - a `pool.first_connect` marker.

## The program

[`chk4_after_rollback.py`](chk4_after_rollback.py) runs one process per run, with arguments `<stack> <arm> <raw.json>`.

- **Engine.** `create_engine` or `create_async_engine`, with `pool_size=1` and `max_overflow=0`, as in P3. psycopg uses `sslmode=disable` and `gssencmode=disable`; asyncpg uses `ssl=False`. The login is `chk4_app`, which is not a superuser.
- **Unit 1.** `with Session(engine) as s: with s.begin():` (or the `AsyncSession` equivalent).
  - It inserts a marker row, then reads `pg_backend_pid()` and `pg_current_xact_id()`.
  - In `rejected`, it also inserts a child row whose foreign key (`DEFERRABLE INITIALLY DEFERRED`) has no parent.
  - The block's own exit commits.
- **The proxy.** In `lost-reply`, the program starts [`commit_reply_proxy.mjs`](commit_reply_proxy.mjs), which runs the harness's `startCommitReplyProxy`.
  - The proxy drops the reply to the first committing `COMMIT` on every connection it carries. So SQLAlchemy's `do_connect` event sends only the engine's first connection through it; every later one goes straight to PostgreSQL.
  - The proxy reports how many replies it dropped.
- **Listeners.**
  - **P3's:** Core `commit` and `rollback`; pool `checkin`, `invalidate`, `close`, `reset` and `soft_invalidate`; ORM `after_commit`, `after_rollback` and `after_soft_rollback`, on the `Session` class.
  - **Added:** the dialect wrapper and `pool.first_connect`.
  - **Also recorded:** warnings; log records at WARNING or above from `sqlalchemy`, `asyncpg` and `psycopg`; asyncio loop errors. There were none in any run.
- **Observer.** A separate psycopg connection, straight to PostgreSQL, in autocommit. It refuses a server whose `cluster_name` is not the instance's token.
  - After unit 1, it reads `pg_xact_status()` and the marker's `xmin`.
  - After unit 2, it reads unit 2's fate and row.
  - At the end, it reads unit 1's fate again.
- **Validity.**
  - `lost-reply` needs exactly one dropped reply, a raise, and `committed` at report time.
  - `rejected` needs a raise and `aborted`.
  - `no-fault` needs a normal return and `committed`.
  - All three need unit 2 to return normally and commit.
- **Output.** stdout has no PIDs, xids, tags or times, so repetitions compare byte for byte. Those details go to `output/sa-<version>/raw/<run>.json`.

## Independent verification

- **Repetitions.**
  - [`output/comparison.txt`](output/comparison.txt): of 18 cells, none has differing repetitions.
  - [`output/versions-compare.txt`](output/versions-compare.txt): no cell differs between 2.1.5 and 2.1.6, apart from the version field.
- **Server log.** [`server_log_extract.py`](server_log_extract.py) keeps each run's sessions in `output/sa-<version>/server-log/`, and checks them from the log alone:
  - **in every arm,** unit 1's backend logged `COMMIT` with unit 1's xid, and unit 2's backend logged `COMMIT` with unit 2's xid;
  - **in `lost-reply`,** unit 1's backend logged nothing after `COMMIT` except its disconnection;
  - **in `rejected`,** `COMMIT` was followed by `ERROR` `23503`;
  - **in `no-fault`,** there was no error.

  Result: [`output/server-log-checks.txt`](output/server-log-checks.txt). 54 runs, none with a problem.
- **psql.** [`psql_check.py`](psql_check.py) read all 108 xids with `pg_xact_status()` in `psql` inside the container, and every `chk4_item` row with its `xmin`. Result: [`output/psql-check.txt`](output/psql-check.txt). In no run did psql and the program disagree.
- **Passwords.** [`output/secret-scan.txt`](output/secret-scan.txt): neither password appears in the full server log, or in the files present at the time of the scan.

## Apparatus incidents

Before the recorded matrix, 28 smoke runs ran between 15:32:45 and 15:34:20 UTC. Their outputs stayed in the session scratchpad and are not kept. They found two problems, both fixed before the matrix:

- **`rejected` first went through the proxy.**
  - **The intent** was to show that the proxy forwards an error reply unchanged.
  - **What happened:** unit 2 reused connection 1, so the proxy dropped unit 2's `COMMIT` reply.
  - **Why only one check caught it:** the validity check of the time required only that PostgreSQL commit unit 2. So only "the proxy dropped a reply" flagged it.
  - **The fix:** `rejected` now connects directly, and every arm requires unit 2 to return normally.
- **The `pool.first_connect` marker was added** after the first smoke run, to explain that run's `do_rollback`.

**Incidental, not recorded.** In that first pass, the dropped reply on a reused connection gave the same events: `after_rollback`, and PostgreSQL committed. This was on 2.1.6, for all three stacks, once each. It is mentioned because it was seen. It is not evidence.

The program's SHA-256 was recorded before the matrix started (15:34:41 UTC). The scripts it ran are unchanged since.

## Limits

- **How the reply was lost.** A proxy on the wire (PPCS category E) dropped it. This is not a measurement of network failures, or of how often replies are lost.
- **Which connection.** In the recorded runs, unit 1 always ran on the pool's first connection, on which dialect initialization had just run. A reused connection appears only in the incidental smoke observation above.
- **The forms.** Only the context-manager forms ran. An explicit `session.commit()` followed by the application's own `rollback()` did not.
- **The setup.** One server, PostgreSQL 18.6, with `synchronous_commit` on and `client_connection_check_interval` 0. A pool of one with default settings (`pool_pre_ping` off).
- **Not run:** psycopg2, pg8000, other drivers, and other databases.
- **`main`.** SQLAlchemy's `main` was read, not run (FACTS.md, fact 10).
- **The contract.** Whether the event's behavior matches its contract is the maintainers' judgment (AGENTS.md, "PPCS evidence conventions").

## Files

| File | What it is |
| --- | --- |
| `chk4_after_rollback.py` | The program (see "The program"). `--versions` prints the versions and server settings |
| `commit_reply_proxy.mjs` | Runs the harness's `startCommitReplyProxy` unchanged. It refuses any port but 55494 |
| `chk4_setup.py` | Writes the instance file (random passwords and `cluster_name`, 0600). Creates the role, database and tables, setting the role's password with `log_statement` off |
| `run_matrix.py` | Runs the 54 runs, repetition-major, and records exit codes and UTC times |
| `server_log_extract.py` | The server-log extracts and checks |
| `compare_outputs.py` | The repetition and version comparisons |
| `psql_check.py` | The psql check, as run. It needs the container, which is gone |
| `secret_scan.py` | The password scan, as run. It needs the instance file, which was deleted |
| `output/sa-<version>/<stack>.<arm>.rep<n>.out` | Each run's stdout. No run wrote to stderr |
| `output/sa-<version>/raw/<run>.json` | Each run's PIDs, xids, tags, times and proxy port |
| `output/sa-<version>/server-log/<run>.txt` | Every server-log line of that run's sessions |
| `output/sa-<version>/versions.json` | Versions and server settings, read through each virtualenv |
| `output/pip-freeze.sa-<version>.txt` | Each virtualenv's packages |
| `output/runs.txt` | Exit codes, and UTC start and end times |
| `output/comparison.txt`, `output/versions-compare.txt` | The comparisons |
| `output/server-log-checks.txt` | The server-log checks, and what unit 1's backend logged after its `COMMIT` |
| `output/psql-xact-status.txt`, `output/psql-item-rows.txt`, `output/psql-check.txt` | The psql reads, and their comparison with the program |
| `output/secret-scan.txt` | The password scan's result and scope |

**The full server log is not kept.** It has 4,048 lines, from 15:32:19 to 15:34:53 UTC, including the smoke runs. Its SHA-256 is `4e26c367471ee5148559d6dfc99c084cf95018e4a47d60eeed4c49bee87d3fb8`. As in CHK-3, it stays outside the repository, and only the per-run extracts are kept.

## Environment

| | |
| --- | --- |
| Client | macOS (arm64), Python 3.13.11 (Homebrew), Node v24.14.1. Two virtualenvs, one with SQLAlchemy 2.1.6 and one with 2.1.5. Each also has psycopg 3.3.6 and psycopg-binary 3.3.6 (libpq 18.6), asyncpg 0.32.0 and greenlet 3.5.6 |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64. Image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, PPCS's pinned digest. Container `ppcs-chk4-pg` on `127.0.0.1:55494`, with a 256 MB tmpfs data directory, a random password and a random `cluster_name`. Removed after the checks. Not `ppcs-postgres` |
| Server settings | `max_connections=100`, `log_statement=all`, `log_connections=on`, `log_disconnections=on`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '`. Read back: `synchronous_commit` on, `client_connection_check_interval` 0, `default_transaction_isolation` read committed, `statement_timeout` 0, `idle_in_transaction_session_timeout` 0 |
| Login | `chk4_app`: `rolsuper` false, owner of the database `chk4` |

## Running it

In zsh, from this directory:

```zsh
SP=<a private directory>
python3.13 -I chk4_setup.py new-instance "$SP"     # prints the cluster_name token
DOCKER_CONTEXT=colima docker run -d --name ppcs-chk4-pg --env-file "$SP/pg.env" \
  -p 127.0.0.1:55494:5432 --tmpfs /var/lib/postgresql:rw,size=256m \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_statement=all \
  -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x sqlstate=%e ' \
  -c log_connections=on -c log_disconnections=on
DOCKER_CONTEXT=colima python3.13 -I chk4_setup.py init-db "$SP/instance.json"
python3.13 -m venv "$SP/venv-sa216" && "$SP/venv-sa216/bin/python" -m pip install \
  "sqlalchemy[asyncio]==2.1.6" "psycopg[binary]==3.3.6" asyncpg==0.32.0
python3.13 -m venv "$SP/venv-sa215" && "$SP/venv-sa215/bin/python" -m pip install \
  "sqlalchemy[asyncio]==2.1.5" "psycopg[binary]==3.3.6" asyncpg==0.32.0
CHK4_INSTANCE="$SP/instance.json" CHK4_VENV_216="$SP/venv-sa216" CHK4_VENV_215="$SP/venv-sa215" \
  python3.13 -I run_matrix.py 1 2 3
DOCKER_CONTEXT=colima docker logs ppcs-chk4-pg > "$SP/server-log.full.txt" 2>&1
CHK4_INSTANCE="$SP/instance.json" python3.13 -I server_log_extract.py "$SP/server-log.full.txt" output
(cd output && DOCKER_CONTEXT=colima python3.13 -I ../psql_check.py && python3.13 -I ../compare_outputs.py)
python3.13 -I secret_scan.py "$SP/instance.json" . "$SP/server-log.full.txt"
DOCKER_CONTEXT=colima docker rm -f -v ppcs-chk4-pg
```

## SHA-256

Every file under output/ is listed, with its SHA-256, in output/SHA256SUMS.

```text
000959c144e979930a2d93382effa1924ab00adbede85f4f5a2dbd3d99f8d9fd  chk4_after_rollback.py
7178c95342ddbfcbe053af1ea693fd24eba818b28735d0a55426522edeb96aa4  chk4_setup.py
3a0e37367bf17c1e81e7b1dbf71de94436a7fe71069886df51e4b3200581713a  commit_reply_proxy.mjs
4b6adf1bde2b20c9fe70949ecdee6847772bf2ad362cb412151a96838cd74bd6  compare_outputs.py
1c738b2385015d60a4a19d3f6ebd2ff1930f1cfbf409f4a117fb793860cffbac  psql_check.py
3461934e17a1f2f336d32eba3581994637657bc14088a4fef28ba432dd5f37a4  run_matrix.py
578c748e95b326bab8a6bb06a373552652727bf54576acd5d706a9c050188131  secret_scan.py
6740bcec385492d2b27b1c5290d757f3f69983a04f69a35510591b9790d5bbb0  server_log_extract.py
45185f901fab4dd7d18327540d721074a2ea4d6dfa1eb84dcc713266b8d7000e  FACTS.md
0ec0367287ef2b7b68339919aa5c7676ed658a369c9e8169c0fa9905279fdc22  ../../../harness/lib/pg-wire-proxy.mjs
1d4915701350c004116b1ac34051a6b66a13ad9c274647ecd964a7ecb97b484c  output/comparison.txt
bb93d7aeb02107d3125d9512a062e2c3670601264b517ec97d8f9c9fb4c67aee  output/versions-compare.txt
08bcd32edfe55eddbc3e6c4c3cad2dfb422d121f8ecaacd43e90fde33b82725b  output/runs.txt
db90641d48f9c9494d84c3e618aefa9c0145ed66fe11e61321a6c580570a89d0  output/server-log-checks.txt
57e6c85216078d1b81592446de362a755e348e82ec3a1eb51fc0d8fe38cef0e5  output/psql-check.txt
5bdbd4fa2ca721ce54c12f22944c9da627ef685c7f74ebcd2ee61a34b0d36eda  output/psql-xact-status.txt
8febb887128fefbb5c89bb55f1b23c5bd92525cf20c2135c95fe6c78c402712c  output/psql-item-rows.txt
17ca06b41fe41057e4bd9b1cd38957bfbde1dc838e6db8a1f85b1b9da456b46c  output/secret-scan.txt
40d8a8279ad0aed42b6bf608e6c7fffb3d4611f1ae6513d12d9e7f7956970db8  output/SHA256SUMS
```
