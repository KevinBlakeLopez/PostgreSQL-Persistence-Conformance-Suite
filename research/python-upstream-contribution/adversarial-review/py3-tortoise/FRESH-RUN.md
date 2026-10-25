# Fresh independent PY-3 runs

Review date: 2026-10-24. Written by: GPT-6 (effort not exposed).

All runtime statements below are **observed** unless marked judgment or source reading. The local date is America/Los_Angeles; UTC execution was on 2026-10-25. The six required runs were at about 02:33 UTC; the extras-only install check preceded them, and the repaired minimal psycopg check followed them.

## Isolation and versions

- Container: `ppcs-py3-adversarial-czkemg`, port `127.0.0.1:55439`, tmpfs `/var/lib/postgresql`.
- Image: `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`; `image-digests.json` records the matching RepoDigest.
- Server: PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), aarch64 Linux, gcc 14.2.0.
- Host: macOS 26.6.2 (25G83), arm64; Python 3.13.11 (Homebrew); colima 0.9.1; Docker server 28.4.0; gh 2.69.0.
- Psycopg: binary implementation, psycopg-binary 3.3.6, libpq 180006 (18.6).
- Virtualenvs, source archives, scripts and GitHub responses: `/private/tmp/py3-adversarial.CZKeMg/`.

Before creating the container, `DOCKER_CONTEXT=colima docker ps` showed `ppcs-postgres` on 55435 and the existing ci4 containers. `nc -z 127.0.0.1 55439` exited 1, and the container script independently checked that port before binding. No existing container or colima lifecycle/configuration was changed.

Server settings: `max_connections=100`, `log_lock_waits=on`, `deadlock_timeout=1s`, `log_statement=all`, `log_line_prefix='%m [%p] app=%a xid=%x '`, `shared_preload_libraries=auto_explain`, `auto_explain.log_min_duration=0`, `auto_explain.log_analyze=on`, `auto_explain.log_timing=off`. Read-back in `settings.txt`: synchronous_commit on, read committed, statement_timeout 0, idle_in_transaction_session_timeout 0.

Complete final execution environment (`pip freeze --all`):

```text
aiosqlite==0.22.1
anyio==4.15.1
asgiref==3.13.0
asyncpg==0.32.0
Django==6.1.2
idna==3.20
iso8601==2.1.0
pip==25.3
psycopg==3.3.6
psycopg-binary==3.3.6
psycopg-pool==3.3.3
pypika-tortoise==0.6.5
SQLAlchemy==2.1.5
sqlparse==0.6.0
tortoise-orm==1.1.9
typing_extensions==4.16.0
```

The two original extras-only environments are separately frozen in `freeze-asyncpg-initial.txt` and `freeze-psycopg-initial.txt`. `freeze-psycopg-plus-witness.txt` records the repaired psycopg-only environment. Those are distinct from the final full environment above.

## Commands

Run from my temporary directory unless shown otherwise. All Docker subprocesses used `DOCKER_CONTEXT=colima`; the Python orchestration sets that explicitly in the subprocess environment. Passwords and the random identity token are omitted here. Exact executable actions, including container options and the sensitivity-program changes, are preserved in `evidence/container.py`, `run.py`, `capture.py`, `integrity.py`, `recorded_check.py` and `github.py`.

```sh
/opt/homebrew/bin/python3.13 -m venv /private/tmp/py3-adversarial.CZKeMg/venv-asyncpg
/opt/homebrew/bin/python3.13 -m venv /private/tmp/py3-adversarial.CZKeMg/venv-psycopg
<scratch>/venv-asyncpg/bin/pip install --only-binary=:all: 'tortoise-orm[asyncpg]==1.1.9'
<scratch>/venv-psycopg/bin/pip install --only-binary=:all: 'tortoise-orm[psycopg]==1.1.9'
/opt/homebrew/bin/python3.13 <scratch>/container.py
/opt/homebrew/bin/python3.13 <scratch>/run.py install-check
<scratch>/venv-asyncpg/bin/pip install --only-binary=:all: 'tortoise-orm[psycopg]==1.1.9' 'Django==6.1.2' 'SQLAlchemy==2.1.5'
<scratch>/venv-psycopg/bin/pip install --only-binary=:all: 'asyncpg==0.32.0'
/opt/homebrew/bin/python3.13 <scratch>/run.py reproduce
/opt/homebrew/bin/python3.13 <scratch>/run.py witness-check
/opt/homebrew/bin/python3.13 <scratch>/capture.py
/opt/homebrew/bin/python3.13 <scratch>/integrity.py
/opt/homebrew/bin/python3.13 <scratch>/recorded_check.py
```

`<scratch>` means `/private/tmp/py3-adversarial.CZKeMg`. `run.py` supplies the isolated database URL through the environment, runs each program in a separate process with `-I`, and captures stdout and stderr. The program source path is PPCS's original `research/python-upstream-contribution/chk-5-tortoise/`; no copy or edit of the subject program was used for the required reproductions. All package installs used binary wheels only. The first sandboxed pip attempt failed to reach the index; the successful installs used the authorized network access and their logs are retained.

The six required command expansions were:

```sh
DATABASE_URL=<isolated-url> <scratch>/venv-asyncpg/bin/python -I <CHK-5>/tortoise_save_after_rollback.py asyncpg
# repeated three times, each in a separate process
DATABASE_URL=<isolated-url> <scratch>/venv-asyncpg/bin/python -I <CHK-5>/tortoise_save_after_rollback.py psycopg
# repeated three times, each in a separate process
```

## Required results

All six unchanged runs exited 0 and each comparison reported:

```text
MATCH recorded after masking IDs: True
```

Only `pg_xact_status(<digits>)` was normalized. The script hash before and after was `632ef90d3671d0c4ada653c9ee8c06795058cf5d81907db25836d967e9a154a3`.

One full fresh output (`outputs/asyncpg.rep1.out`):

```text
python 3.13.11, tortoise-orm 1.1.9, backend asyncpg (asyncpg 0.32.0), Darwin arm64
server_version 18.6 (Debian 18.6-1.pgdg13+2)
retry: save() in in_transaction(), the block raises; then save() again in a new in_transaction()
  first save() returned, pk=1; the block raised AppError
  first transaction: pg_xact_status(780) aborted
  after the rollback: pk=1, _saved_in_db=True, rows with arm='retry': 0
  second save() returned normally
  second transaction: pg_xact_status(781) committed
  rows with arm='retry': 0
retry-changed: save() in in_transaction(), the block raises; then value = 2 and save() again in a new in_transaction()
  first save() returned, pk=2; the block raised AppError
  first transaction: pg_xact_status(782) aborted
  after the rollback: pk=2, _saved_in_db=True, rows with arm='retry-changed': 0
  second save() returned normally
  second transaction: pg_xact_status(783) committed
  rows with arm='retry-changed': 0
savepoint: in an outer in_transaction(), save() in a nested in_transaction() that raises; the error is caught; then save() again in the outer block
  first save() returned, pk=3; the nested block raised AppError
  after the savepoint rollback: pk=3, _saved_in_db=True
  second save() returned normally
  the outer block exited normally
  outer transaction: pg_xact_status(784) committed
  rows with arm='savepoint': 0
savepoint-changed: in an outer in_transaction(), save() in a nested in_transaction() that raises; the error is caught; then value = 2 and save() again in the outer block
  first save() returned, pk=4; the nested block raised AppError
  after the savepoint rollback: pk=4, _saved_in_db=True
  second save() returned normally
  the outer block exited normally
  outer transaction: pg_xact_status(786) committed
  rows with arm='savepoint-changed': 0
control: save() of a new instance in in_transaction()
  save() returned, pk=5
  transaction: pg_xact_status(788) committed
  rows with arm='control': 1
force_update: as retry, but the second call is save(force_update=True)
  first save() returned, pk=6; the block raised AppError
  first transaction: pg_xact_status(789) aborted
  after the rollback: pk=6, _saved_in_db=True, rows with arm='force_update': 0
  second save(force_update=True) raised IntegrityError: Can't update object that doesn't exist. PK: 6
  second transaction: pg_xact_status(790) aborted
  rows with arm='force_update': 0
```

All other outputs are preserved, byte for byte, under `evidence/outputs/`. Their hashes are:

| Output | SHA-256 |
| --- | --- |
| `outputs/asyncpg.rep1.out` | `9e49c0165605f877ed23bb9d053689849c8b6d8240793ac0b30bd9138ce6c81f` |
| `outputs/asyncpg.rep2.out` | `821c50b07919ffeb5e1293f03ae6c5b5025b2c103b0c7c2fb9b828a793816303` |
| `outputs/asyncpg.rep3.out` | `157d6a2ca3b94ae1dbccb60d58edf9893dbb1241769411a294548602fecc06fc` |
| `outputs/controls.out` | `846aa734eb8ed22c7e117fedb80c88bc3de384c2456fc1060882f25a538c09aa` |
| `outputs/install-asyncpg-run-asyncpg.out` | `4bd3a9f0d9a500c34b1aac586578df9ff9fbce8654fce4c1d98347719dc498f2` |
| `outputs/install-asyncpg-run-psycopg.out` | `0e7c73c190dd765b060cdac9f2a41d528afa8e8bf5b153299ff97a5315de946e` |
| `outputs/install-psycopg-run-asyncpg.out` | `3abe7be866956883e2db9d2a911d41df0624f1a6402a9b492211a00a7329d48f` |
| `outputs/install-psycopg-run-psycopg.out` | `3abe7be866956883e2db9d2a911d41df0624f1a6402a9b492211a00a7329d48f` |
| `outputs/no-xid-asyncpg.out` | `e8e5ca27b0b45673e243a4d5066f767119d29b035daa6e9a9a7170e39b151d5c` |
| `outputs/no-xid-psycopg.out` | `79143d6c746e6947234f0ad49e534062eb451faf14299209288ecfd139034185` |
| `outputs/pool-one-no-xid-asyncpg.out` | `e8e5ca27b0b45673e243a4d5066f767119d29b035daa6e9a9a7170e39b151d5c` |
| `outputs/psycopg-extra-plus-witness.out` | `3c5dfcea5f0fb97682a2634a2e6abf8431e03fd08d88c8a8167461d4cfbed29d` |
| `outputs/psycopg.rep1.out` | `bf0c90c86cc04be89012f2e36b7ddbd934f024ef6066827f4689835b3d0c6412` |
| `outputs/psycopg.rep2.out` | `8185f4846858a11c6a1b007f160ecf72d37e11877a0e936fed3eca12ee9eac2c` |
| `outputs/psycopg.rep3.out` | `3753e7d70b5ca15e3eb9fbef8c3a64b61a8dcfedb2dcb05e986715e974d6a9dc` |
| `outputs/wrapped-asyncpg.out` | `ec8107f52019b3b9f53bd0a60634342125c0dad95f3ec07e903ada65307f6ec9` |
| `outputs/wrapped-psycopg.out` | `909aab89211bf8075a0d86c6e4a164bc8c70c082501eb5cc9c5023092a2579df` |

The extras-only matrix is recorded in `install-check.txt`: asyncpg-extra/asyncpg succeeds, asyncpg-extra/psycopg fails importing psycopg, and both commands from the psycopg-extra environment fail importing asyncpg. Adding asyncpg alone to the psycopg extra makes its psycopg run succeed. This corroborates the need to include asyncpg for the witness even when testing psycopg.

## Independent server verification

I read the full server log and grouped statements independently of the author's checker. `independent-log-review.txt` records statements, child scan counts and the psql fate next to each captured transaction. SQL parameters remain in `server.full.log`. `capture.py` queried every unique printed transaction ID from all successful XID-instrumented runs through `psql` inside my container:

```text
PSQL 102 transaction IDs; mismatches []
```

There were 54 IDs in the six required runs, plus 18 in the wrappers, 12 in the comparison controls, 9 in the initial successful extras-only run and 9 in the repaired minimal psycopg run. All agreed with the observer's statuses. The query and raw psql rows are in `psql-xact-status.txt`.

Each retry UPDATE's child scan reports zero rows with one loop. First top-level attempts roll back; default retries and outer savepoint transactions commit with zero rows; the fresh-instance control inserts and commits one row; force_update raises and rolls back. Server SQL/plan evidence, independently queried fate and observer visibility agree.

I reran `chk5_update_count.py` once per backend, and `controls_django_sqlalchemy.py` once. The former reports five zero counts per backend. The latter persists all four variants per framework; SQLAlchemy explicitly re-adds the transient object. I did not rerun `server_log_check.py`.

I also ran each backend once with `current_xid()` and `fate()` replaced by functions returning `not-collected`, leaving row observation in place. The outcomes stayed unchanged. A further no-XID asyncpg run added `minsize=1&maxsize=1`; its stdout equals the default-pool no-XID run. These are exploratory instrumentation/pool sensitivity checks, not part of the six unchanged reproductions. The two modified programs are retained.

## Removal and created paths

```sh
DOCKER_CONTEXT=colima docker rm -f ppcs-py3-adversarial-czkemg
# output: ppcs-py3-adversarial-czkemg
DOCKER_CONTEXT=colima docker ps -a --filter name=ppcs-py3-adversarial-czkemg --format '{{.Names}}'
# output: empty
```

**Confirmed: the review's container is removed.** `container-removed.txt` contains only its removal name and no subsequent match. `containers-after.txt` records the pre-existing containers still running, including `ppcs-postgres` on 55435. No tracked files were modified, staged or committed, and no GitHub writes were performed.

The two intentional artifact roots are the review directory containing this report, and `/private/tmp/py3-adversarial.CZKeMg/`. Pip also created two per-virtualenv files in its default shared cache and refreshed existing cache metadata; see `CACHE-SIDE-EFFECTS.md` for this execution-constraint deviation and its exact paths. The latter contains two virtualenvs, downloaded source archives and extracted source trees, scripts, raw read-only GitHub responses, outputs and a mode-0600 connection file for the now-removed server. Delete the whole temporary root when finished. `CREATED-PATHS.txt` enumerates every created file/directory/symlink recursively, including virtualenv contents. `evidence/SHA256SUMS.txt` inventories the delivered evidence hashes.

The created-path inventory also includes the two definitely owned pip self-check files. Shared HTTP metadata touched during install windows is listed separately in `CACHE-SIDE-EFFECTS.md`, because other sessions prevent exclusive attribution.
