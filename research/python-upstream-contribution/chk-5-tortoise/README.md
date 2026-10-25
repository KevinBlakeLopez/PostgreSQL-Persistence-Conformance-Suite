# CHK-5: Tortoise ORM `save()` after the instance's INSERT was rolled back

Run on 2026-10-25, 01:20 UTC (2026-10-24, 18:20 PDT); revised the same day after an outside review (see the last section). Written by: Claude Opus 5.5 (max).

This is check CHK-5 from [`../../python-upstream-contribution-roadmap.md`](../../python-upstream-contribution-roadmap.md) §11, for tracker item PY-3. It runs the standalone program proposed for the Tortoise issue three times on each PostgreSQL backend, and adds three CHK-only programs: a wrapper that shows the count `save()` receives, Django and SQLAlchemy controls, and a server-log cross-check.

It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies. The independent checks are listed under "Independent verification".

## Question

The gap analysis's probe P4 (`../../python-production-failure-gap-analysis/p45_commit_error_and_retry.py`, `output/p45.rep{1,2,3}.out`) observed, on Tortoise 1.1.9 with asyncpg, three of three: after a rolled-back `save()`, the instance kept `pk = 1` and `_saved_in_db = True`, and a retried `save()` in a new `in_transaction()` returned normally while the witness counted 0 rows. P4 logged neither the retry's statements nor its transaction ID. CHK-5 asks:

- **(a)** Does the retry really send an UPDATE that matches 0 rows? What is the retry's transaction, and its fate?
- **(b)** The savepoint variant: an outer `in_transaction()` contains a nested `in_transaction()` that saves, then raises; the error is caught; `save()` runs again in the outer block, which commits. Is the write lost?
- **(c)** Do the same arms behave the same on Tortoise's psycopg backend?
- **Controls:** a new instance saved once must persist; Django and SQLAlchemy on the same retries.
- **Optional:** `save(force_update=True)` on the retry, to confirm that it raises.
- **Added before the recorded runs, at the maintainer's request** after an outside review of this design: a retry that changes a non-primary-key field first, beside the retry with no change. The review asked whether the unchanged retry might skip SQL altogether, while a changed one sends an UPDATE.

## Answers

All observed, three of three on each backend, unless marked otherwise.

- **(a) Yes.** The retry sends `UPDATE "item" SET "arm"=$1,"value"=$2 WHERE "id"=$3`, with `$3` the rolled-back primary key. `auto_explain` shows it matching 0 rows. `execute_update()` returns 0 to `save()`, `save()` returns normally, and the transaction commits (`pg_xact_status` `committed`, read by the witness and by `psql`). No row exists.
- **Changing a field first makes no difference.** The changed retry sends the same UPDATE with the new value. It also matches 0 rows, and the transaction commits. Neither path skipped SQL.
- **(b) Yes, the write is lost.** After `ROLLBACK TO` the savepoint, the instance keeps `pk` and `_saved_in_db = True`. The second `save()` in the outer block sends the same UPDATE, which matches 0 rows, and the outer transaction commits without the row.
- **(c) Yes.** The psycopg backend gives the same outputs, apart from the version line and the transaction IDs. Its savepoints add a `RELEASE` after `ROLLBACK TO`.
- **Controls.** A new instance saved once persists (1 row, committed). Django 6.1.2 and SQLAlchemy 2.1.5 persisted all four retry variants (1 row each, committed). Django sends an UPDATE for the old primary key, which matches 0 rows, and then an INSERT with that key. SQLAlchemy makes the object transient and inserts it with that key.
- **Optional `force_update=True`.** It raises `IntegrityError: Can't update object that doesn't exist. PK: 6` for the same situation. Its UPDATE also matched 0 rows, and the transaction rolled back.

## Files

| File | Contents | SHA-256 |
| --- | --- | --- |
| `tortoise_save_after_rollback.py` | The program proposed for the issue. Byte-identical to the one that ran: same hash before and after the 12 runs that used it | `632ef90d3671d0c4ada653c9ee8c06795058cf5d81907db25836d967e9a154a3` |
| `chk5_update_count.py` | CHK-only. Runs the program above unchanged, with `BaseExecutor.execute_update` wrapped to print the value it returns to `save()` | `98e586d5e99553a0fbbcf9cc96cbe55e109d57bc88bbcc6e53d33d99c6194cf4` |
| `controls_django_sqlalchemy.py` | CHK-only. Django and SQLAlchemy on the four retry arms | `0d82f23ee3aee380c2f324a079ec7852f3965772c17336d436ed6afc2fd907b3` |
| `server_log_check.py` | CHK-only. Extracts the subject sessions from the server log, prints the `psql` query, and cross-checks the log, the outputs and the `psql` fates | `de665e4fc6624176780c602e8ba07c8cc0d1be04d7fd48916ff5305b4f1bee13` |
| `output/asyncpg.rep{1,2,3}.out`, `output/psycopg.rep{1,2,3}.out` | Complete stdout and stderr of the program, per backend | below |
| `output/wrapped-asyncpg.rep{1,2,3}.out`, `output/wrapped-psycopg.rep{1,2,3}.out` | Complete stdout and stderr of the wrapped runs | below |
| `output/controls.rep{1,2,3}.out` | Complete stdout and stderr of the controls | below |
| `output/psql-xact-status.txt` | `pg_xact_status()` of all 144 printed transaction IDs, read with `psql` inside the container after the runs, with its query | `18ff2f31868349dbea703c326ebde474d1d3bd23d6a896b58b607f0857eccc25` |
| `output/server-log-extract.txt` | Every server-log entry, with its continuation lines, of the subject sessions (`application_name` `repro-tortoise`, `repro-django`, `repro-sqlalchemy`): 1,470 entries | `4b47e88e20fd7de2ced9d606ca219966317dc28c99167ba2040107b6b842ab98` |
| `output/server-log-check.txt` | `server_log_check.py check output` | `a11a6fd4ca672779a77172872fe686df3bcd0a11b7bb5ef6008b704076cc349c` |
| `output/pip-freeze.txt` | The virtualenv's packages, the Python build, psycopg's libpq, and how the virtualenv was created | `4fde8d656f8815a52d8436228f1ed7de02a0c6a0d54fc82c55f836062439f1d2` |
| `output/install-check/asyncpg.out`, `output/install-check/psycopg.out` | The install check after the outside review: complete stdout and stderr of the program, from a fresh virtualenv with only `tortoise-orm[asyncpg,psycopg]==1.1.9` | in the last section |
| `output/install-check/pip-freeze.txt` | That virtualenv's packages (`pip freeze --all`) | `f5c277a909bff5bc2848726f1d9ba10719d0b791b670d2940e64773d421a5448` |

Full hashes of the 15 outputs:

```text
b1db438afadd1388a88acf8f3e39b9caebd62e00c717f5eae7cf9c2bddd93197  output/asyncpg.rep1.out
3ac9bb53848618d49f6d057ed07c873a4991f7ddde8fb4c5c3621e94ba91c55c  output/asyncpg.rep2.out
939d972c2a9b1286d3457ef3a76cfbcb17acf8f5a0672294558becf6518fe8a7  output/asyncpg.rep3.out
af388f4af35388f23b221721dc94de29aaea9cf7f1ba961299f8ccf5672aeecc  output/psycopg.rep1.out
3d5cd0d60150f25ffb13dcf9c724c23e1ccf884621455776c637d6618033eb68  output/psycopg.rep2.out
d02f34a019a5ac39444704a9e18af275f562e0bb74141533640ff69bf7561a8f  output/psycopg.rep3.out
93358e69e618e9aaacff1bcde6eeec384eb7dc2696d61ed0d42f6430feeeea63  output/wrapped-asyncpg.rep1.out
9a957e6023e77e5f01fa61a27b9ce82bc546fd36789835e9d343f474f9592626  output/wrapped-asyncpg.rep2.out
1602811f33742a1038416e1a71441e2a5f980fa455bb5655b7b8252a0f499fc2  output/wrapped-asyncpg.rep3.out
3f1d931bf8229ea3e52c644b53040605f928ddb9276f30a7a56994954add8cf3  output/wrapped-psycopg.rep1.out
6f78b07d132ce2c878a8ce6486572de4aa0b1e8c3e9302bc1ab117de05ef9aa2  output/wrapped-psycopg.rep2.out
115e303bfc8944cae40b062766bd979822bdc77f92b4c2d90d849020c9b1261d  output/wrapped-psycopg.rep3.out
b3ea3649b5d0755c446c80d880557f1058f35786c19c57bd52d09faf3c72b451  output/controls.rep1.out
b9decf3c91ee98e7a38f317216294b6c3de2342bdc4056952b4a26f0853e487a  output/controls.rep2.out
c72258bd699d5aaf402527b3b64ac199dd1b00d45335a396c8706828f93da042  output/controls.rep3.out
```

The three repetitions of each program are identical once the transaction IDs are masked. The wrapped outputs equal the plain outputs plus the wrapper's lines. The asyncpg and psycopg outputs differ only in the version line and the transaction IDs.

**The full server log is not kept.** It was 5,432 lines (SHA-256 `46913235811e94082dd6e0bc2ebdc701788bf624c615938a41fb65d00d696e65`), captured with `docker logs`. Neither the password nor the `cluster_name` token occurs in it, or in any file here. The rest of it is server start-up, the witness and admin sessions, and `auto_explain` plans for their queries.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest), arm64. A throwaway container, `ppcs-chk5-tortoise-pg`, published on `127.0.0.1:55495`, with a tmpfs data directory, a random password and a random `cluster_name` token. Removed at 01:22 UTC. Not `ppcs-postgres` |
| Server settings | PPCS's (`max_connections=100`, `log_lock_waits=on`, `deadlock_timeout=1s`), plus `log_statement=all`, `log_line_prefix='%m [%p] app=%a xid=%x '`, and `auto_explain` (`shared_preload_libraries=auto_explain`, `auto_explain.log_min_duration=0`, `auto_explain.log_analyze=on`, `auto_explain.log_timing=off`). Read back before the runs, with the token: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout` and `idle_in_transaction_session_timeout` 0 |
| Host | macOS 26.6.2 (25G83) arm64, colima 0.9.1, Docker server 28.4.0 |
| Python | 3.13.11 (Homebrew) |
| Packages | tortoise-orm 1.1.9 (pypika-tortoise 0.6.5), asyncpg 0.32.0, psycopg 3.3.6 (binary implementation, libpq `180006`, that is 18.6), psycopg-pool 3.3.3, Django 6.1.2, SQLAlchemy 2.1.5. Installed from PyPI wheels with `--only-binary=:all:` into a fresh virtualenv. All but SQLAlchemy were PyPI's latest that day. SQLAlchemy 2.1.5 is PPCS's pin and P4's version; 2.1.6 is the latest |
| Tortoise source | The installed files are byte-identical to tag `1.1.9` (`ac3892300`): `models.py` `a757e72803cce7b7593f57970420e638a40c445c99f23b67ea8f575b001ffcc7`, `backends/base/executor.py` `5cf030487a0d69cfd36cabac80db1ed5d51b2075588881dac20286fa2ac51aa2`, `backends/base/client.py` `c2313cbe4a453632c44622891ec290fd5a6a59d911a3e8e672f3dbcdf2004b18`, `backends/asyncpg/client.py` `5c2dbb3f66750dfd0dc58872420af7b1be07701e413833a8d98c925e1bf9170d`, `backends/psycopg/client.py` `ea9532388dada72554d7b22d6333274f57f1f3456b27d525c57e6917b11aaa98`. On `develop` `ad0d6ce2b` (2026-10-24 17:49 UTC), `Model.save()` and `BaseExecutor.execute_update()` are identical; `save()` sits 4 lines lower, at 1135–1199 |

## Commands

The password is replaced by `<password>`, and the token by `<token>`. `<venv>` is the virtualenv and `<scratch>` a directory outside the repository. Every `docker` command ran with `DOCKER_CONTEXT=colima`.

```sh
docker run -d --name ppcs-chk5-tortoise-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55495:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_lock_waits=on \
  -c deadlock_timeout=1s -c log_statement=all -c 'log_line_prefix=%m [%p] app=%a xid=%x ' \
  -c shared_preload_libraries=auto_explain -c auto_explain.log_min_duration=0 \
  -c auto_explain.log_analyze=on -c auto_explain.log_timing=off

# Before the runs: `show cluster_name` through 127.0.0.1:55495 returned <token>.

# From this directory, each run a separate process, one after another:
export DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55495/postgres"
for b in asyncpg psycopg; do for rep in 1 2 3; do
  <venv>/bin/python -I tortoise_save_after_rollback.py $b > output/$b.rep$rep.out 2>&1
done; done
for b in asyncpg psycopg; do for rep in 1 2 3; do
  <venv>/bin/python -I chk5_update_count.py $b > output/wrapped-$b.rep$rep.out 2>&1
done; done
for rep in 1 2 3; do
  <venv>/bin/python -I controls_django_sqlalchemy.py > output/controls.rep$rep.out 2>&1
done

# After the runs: the psql check (its query is recorded in output/psql-xact-status.txt),
# the log, the extract, and the cross-check.
docker exec ppcs-chk5-tortoise-pg psql -U postgres -d postgres \
  -c "$(<venv>/bin/python -I server_log_check.py query output)"
docker logs ppcs-chk5-tortoise-pg > <scratch>/server.full.log 2>&1
<venv>/bin/python -I server_log_check.py extract <scratch>/server.full.log output/server-log-extract.txt
<venv>/bin/python -I server_log_check.py check output > output/server-log-check.txt
docker rm -f ppcs-chk5-tortoise-pg
```

All 15 runs exited 0. By the server log, the first run's first statement was at 01:20:48.206 UTC, and the last run's `drop database` at 01:20:51.215 UTC. `server_log_check.py check` exited 0.

## The programs

**`tortoise_save_after_rollback.py`** creates database `tortoise_save_after_rollback`, and drops it at the end. Tortoise connects with `application_name=repro-tortoise` and its default pool settings, through `postgres://` (asyncpg) or `psycopg://`. The model is `Item(id IntField primary key, arm TextField, value IntField)`; Tortoise generates `id` as `SERIAL`. A separate asyncpg connection, `repro-witness`, in autocommit, reads `pg_xact_status()` of the IDs that each transaction captured with `pg_current_xact_id()`, and counts the arm's rows.

| Arm | What it does |
| --- | --- |
| `retry` | `save()` in `in_transaction()`; the block raises `AppError`, so it rolls back. Then `save()` of the same instance in a new `in_transaction()` |
| `retry-changed` | The same, with `value = 2` set before the second `save()` |
| `savepoint` | In an outer `in_transaction()`: `save()` in a nested `in_transaction()` (a savepoint) that raises; the error is caught in the outer block; `save()` again in the outer block, which then exits normally |
| `savepoint-changed` | The same, with `value = 2` set before the second `save()` |
| `control` | `save()` of a new instance in `in_transaction()` |
| `force_update` (optional) | As `retry`, but the second call is `save(force_update=True)`. This transaction captures its ID before `save()`, since `save()` raises |

**`controls_django_sqlalchemy.py`** runs the four retry arms on its own database, `chk5_controls`. The witness is a psycopg connection in autocommit.

- **Django** uses `atomic()`, with a nested `atomic()` for the savepoint arms.
- **SQLAlchemy ORM** uses a new `Session` per attempt, with the object added again, as P4 did. Its savepoint arms use `begin_nested()`, and the object is added again in the outer transaction.

## Result

### Tortoise, both backends

Each row held in all six runs, three per backend. The statements are from the server log, and the matched rows from `auto_explain`. On psycopg, the savepoint arms also send `RELEASE` after `ROLLBACK TO`.

| Arm | After the first attempt | Second call | Statements of the retry's transaction | UPDATE matched | Fate | Rows for the arm |
| --- | --- | --- | --- | --- | --- | --- |
| `retry` | `pk=1`, `_saved_in_db=True`; first transaction `aborted`; 0 rows | `save()` returned normally | `BEGIN`, `UPDATE … WHERE "id"=$3` (`$3 = '1'`), `COMMIT` | 0 rows | `committed` | 0 |
| `retry-changed` | `pk=2`, `_saved_in_db=True`; `aborted`; 0 rows | `save()` returned normally | the same, with `$2 = '2'` | 0 rows | `committed` | 0 |
| `savepoint` | `pk=3`, `_saved_in_db=True` after the savepoint rollback | `save()` returned normally; the outer block exited normally | `BEGIN`, `SAVEPOINT`, `INSERT` (1 row), `ROLLBACK TO`, `UPDATE … WHERE "id"=$3` (`$3 = '3'`), `COMMIT` | 0 rows | `committed` | 0 |
| `savepoint-changed` | `pk=4`, `_saved_in_db=True` | the same | the same, with `$2 = '2'` | 0 rows | `committed` | 0 |
| `control` | — | `save()` returned normally | `BEGIN`, `INSERT` (1 row), `COMMIT` | — | `committed` | 1 |
| `force_update` | `pk=6`, `_saved_in_db=True`; `aborted`; 0 rows | `save(force_update=True)` raised `IntegrityError: Can't update object that doesn't exist. PK: 6` | `BEGIN`, `UPDATE … WHERE "id"=$3`, `ROLLBACK` | 0 rows | `aborted` | 0 |

**The count `save()` receives.** In the 30 wrapped calls, 15 per backend (`retry`, `retry-changed`, both savepoint arms and `force_update`, three runs each), `execute_update()` returned `0` to `save()`. In the four default-path arms `save()` then returned normally. In `force_update` it raised.

### Controls: Django 6.1.2 and SQLAlchemy 2.1.5

Each row held in all three runs.

| Framework and arms | State after the rollback | Statements of the retry's transaction | Fate | Rows |
| --- | --- | --- | --- | --- |
| Django `retry`, `retry-changed` | `pk` kept, `_state.adding=False` | `BEGIN`, `UPDATE … WHERE "dj_item"."id" = <pk>` (0 rows), `INSERT` with that `id` (1 row), `COMMIT` | `committed` | 1 |
| Django `savepoint`, `savepoint-changed` | the same, after `ROLLBACK TO SAVEPOINT` | `… ROLLBACK TO SAVEPOINT`, `RELEASE SAVEPOINT`, `UPDATE` (0 rows), `INSERT` (1 row), `COMMIT` | `committed` | 1 |
| SQLAlchemy `retry`, `retry-changed` | transient, `pk` kept | `BEGIN`, `INSERT` with that `id` (1 row), `COMMIT` | `committed` | 1 |
| SQLAlchemy `savepoint`, `savepoint-changed` | transient after the savepoint rollback | `… ROLLBACK TO SAVEPOINT`, `INSERT` with that `id` (1 row), `COMMIT` | `committed` | 1 |

## Independent verification

Four sources agree for all 144 printed transactions (`output/server-log-check.txt`: 0 problems).

1. **The programs' witness connections,** described above: asyncpg for Tortoise, psycopg for the controls.
2. **`psql` inside the container,** after all runs, with no Python driver involved. Fates: 48 first attempts `aborted`; 36 retries and 36 outer transactions `committed`; 12 `control` arms `committed`; 12 `force_update` retries `aborted`.
3. **The server's statement log.** `server_log_check.py` grouped each subject session's statements into transactions. It matched each printed ID to exactly one transaction, by the ID on its `COMMIT` or `ROLLBACK` line, and checked that the ending statement agrees with the fate. The 9 unmatched transactions are the controls' setup: Django's and SQLAlchemy's `CREATE TABLE`, and SQLAlchemy's read-only first-connect check.
4. **`auto_explain`,** with `log_analyze`. For each INSERT and UPDATE it logs the rows of the node under the Insert or Update node. For these statements, which have no triggers, no `ON CONFLICT` and one loop each, those are the rows inserted, or the rows the UPDATE matched. Statements with triggers, `ON CONFLICT` or repeated loops would need a separate reading.

**One more server-side signal, for the plain retries.** `auto_explain` logs a plan after its statement has run: the INSERT's plan entry already carries the ID that the INSERT assigned, while its statement entry shows 0 (lines 16–25 of the extract). In all 24 `retry` and `retry-changed` transactions, the log prefix's `xid` was still 0 in the UPDATE's plan entry. An ID was assigned only by the program's `pg_current_xact_id()` call afterwards. Changing a row requires a transaction ID, since every new row version is stamped with it, so the UPDATE changed no row. The converse does not hold: an ID can be assigned without any row changing, for example by a sequence's allocation. In the savepoint arms the nested INSERT had already assigned the ID, and in `force_update` the program's own call had, so this signal does not apply there.

## Source reading

Labelled Src. Lines are 1.1.9's. `develop` `ad0d6ce2b` has identical functions, with `save()` 4 lines lower.

- **`Model.save()`** (`tortoise/models.py`, 1131–1195). With `_saved_in_db` true and a primary key set, the default path calls `executor.execute_update(self, update_fields)` and discards its result (1182–1188; on `develop` 1186–1192). `force_update=True` keeps the same result and raises `IntegrityError` when it is 0 (1176–1179; `develop` 1180–1183). `self._saved_in_db = True` follows either path (1194; `develop` 1198).
- **Nothing resets the flag on rollback.** `_saved_in_db` is set to False only in `Model.__init__`, `clone()`, `construct()` and `create()`. No client or transaction code refers to it.
- **`execute_update()`** (`tortoise/backends/base/executor.py`, 460–505) sends every non-primary-key, non-generated field that does not hold a `DatabaseDefault`. It has no dirty-field check. It returns 0 without sending anything only when no such field remains (489–490), which these arms never reached. Otherwise it returns the first element of `execute_query()`'s result.
- **That element is the command tag's count.** The asyncpg client parses `"UPDATE n"` (`backends/asyncpg/client.py`, 137–143). The psycopg client uses `cursor.rowcount` (`backends/psycopg/client.py`, 178).
- **A nested `in_transaction()` is a savepoint.** `NestedTransactionContext` calls `savepoint()`, then `savepoint_rollback()` on an exception and `release_savepoint()` otherwise (`backends/base/client.py`, 388–406). Both PostgreSQL backends implement them with the driver's nested transaction.

## Compared with the earlier evidence

CHK-5 reproduces P4's Tortoise result on asyncpg: the retry returned normally, the instance kept `pk = 1` and `_saved_in_db = True`, and 0 rows exist. There is no discrepancy. P4 used a pool of one connection; CHK-5 uses Tortoise's defaults. CHK-5 adds:

- the statement sent, and its 0 matched rows;
- the retry's transaction and its fate;
- the count that `save()` received;
- the psycopg backend;
- the savepoint and changed-field variants;
- the `force_update` contrast;
- Django and SQLAlchemy controls for all four variants. P4 ran them on the plain retry only.

## What this establishes, and what it does not

- **Established.** On Tortoise 1.1.9 with PostgreSQL 18.6, on both the asyncpg and the psycopg backends:
  - after the transaction or savepoint that inserted an instance rolls back, the instance keeps its `pk` and `_saved_in_db = True`;
  - a later `save()` sends an UPDATE for that `pk`, which matches 0 rows. `execute_update()` returns 0, `save()` returns normally, the transaction commits, and no row exists. The same holds whether or not a field was changed first, and when the outer transaction of a rolled-back savepoint commits;
  - `save(force_update=True)` raises `IntegrityError` in the same situation.

  On the same server, Django 6.1.2 persisted the same four retries, and so did SQLAlchemy 2.1.5, where the rollback makes the object transient and the retry adds it to a session again.
- **Source reading only.** Two claims rest on the code, not on these runs:
  - nothing resets `_saved_in_db` on rollback;
  - `execute_update()` returns 0 without sending a statement when no field needs updating.
- **Not run here:**
  - other PostgreSQL versions; Linux;
  - Tortoise's other backends. `Model.save()` is shared code, but #1212 (2022, on 0.18.1 and 0.19.2) suggests that MySQL's counts may differ;
  - `Model.create()` inside the rolled-back transaction. It goes through `save(force_create=True)`, which sets the same flag;
  - `update_fields`, `bulk_create`, `get_or_create` and `update_or_create`;
  - client-generated primary keys;
  - the `atomic()` decorator;
  - concurrent writers.

## Changes between attempts

- **Development runs on a separate container.** Before the recorded runs, every program was tried on a container with the same image, port and settings, but a different password and token. That container was removed before the recorded runs, and none of its output is kept. The issue program did not change between those trials and the recorded runs. The trials found three problems in the CHK-only programs, all fixed before the recorded runs:
  - **The SQLAlchemy retry arms.** They read `obj.id` after the second `Session` had committed and closed. `expire_on_commit` made that raise `DetachedInstanceError`. The primary key is now read inside the block.
  - **The pattern summary in `server_log_check.py`.** It counted patterns before replacing the primary-key values, so each run showed up separately. It now counts after replacing them, per program, arm and transaction. Two columns were widened.
  - **An unused parameter.** It was removed from the controls' `report()`.
- **The settings read-back before the recorded runs** first failed on a quoting error in an inline script, before it connected. It was rerun from a file.

## After the outside review (2026-10-25)

An outside adversarial review reproduced the six runs on its own container and found no defect in them. Two things changed here.

- **Wording.** Point 4 under "Independent verification" now says which statements its reading covers. The transaction-ID paragraph now gives the exact reason for its conclusion, and says that the converse does not hold.
- **An install check, for the issue's setup line.** The review found that neither backend extra alone runs both commands, because the program always imports asyncpg for its setup and witness connections. The issue now says to install `tortoise-orm[asyncpg,psycopg]==1.1.9`. That line was checked at 03:01 UTC in a fresh virtualenv that had nothing else, with Python 3.13.11 and `--only-binary=:all:`, on a throwaway container from the same image (`py3-install-check-pg`, `127.0.0.1:55497`, default settings, removed after the runs). The program was copied into an otherwise empty directory and run from there, once per backend, as the issue's two commands:

  ```sh
  python3.13 -m venv <venv>
  <venv>/bin/pip install --only-binary=:all: 'tortoise-orm[asyncpg,psycopg]==1.1.9'
  DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55497/postgres <venv>/bin/python tortoise_save_after_rollback.py asyncpg
  DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55497/postgres <venv>/bin/python tortoise_save_after_rollback.py psycopg
  ```

  Both exited 0. Once the transaction IDs are masked, the outputs equal `output/asyncpg.rep1.out` and `output/psycopg.rep1.out`; the asyncpg output is byte-identical even unmasked. The virtualenv resolved the same versions as the recorded runs: tortoise-orm 1.1.9, asyncpg 0.32.0, psycopg 3.3.6 (binary), psycopg-pool 3.3.3.

  ```text
  b1db438afadd1388a88acf8f3e39b9caebd62e00c717f5eae7cf9c2bddd93197  output/install-check/asyncpg.out
  9e6e6f5a17f230f91db04f99eb9d67a546565ca48fc4a793b0a024316caaf235  output/install-check/psycopg.out
  ```
