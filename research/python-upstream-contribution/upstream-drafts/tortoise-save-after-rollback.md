# Draft: Tortoise ORM, new issue in tortoise/tortoise-orm

**Filed 2026-10-25, 03:20 UTC,** as `KevinBlakeLopez`: https://github.com/tortoise/tortoise-orm/issues/2383 The filed title and body match the text below; they were compared through the API.

**Checked just before filing, about 03:20 UTC:**
- No tortoise-orm issue or PR had been created or updated after 01:30 UTC. The API searches `rollback save`, `saved_in_db` and `save after rollback` returned the same counts as before (7, 0, 3).
- `develop` was still `ad0d6ce2b`, so the linked lines held.
- PyPI `latest` was 1.1.9.
- #2293 was open and unmerged; #1212 had no comments.

Prepared 2026-10-24 (PDT), from CHK-5 and checks run 2026-10-25 between about 01:05 and 01:35 UTC. Written by: Claude Opus 5.5 (max).

**Revised 2026-10-25 (UTC),** after an outside adversarial review. The review reproduced all six runs and found no defect in them. The changes:

- **The source bullet** separates what comes from the source from what the runs showed.
- **The setup paragraph** gives one install line, `tortoise-orm[asyncpg,psycopg]==1.1.9`. The review found that neither backend extra alone runs both commands. The line was then checked in a fresh virtualenv (see "Evidence").
- **The environment bullet** says that `develop` was compared, not run.
- **The comparison bullet** says that SQLAlchemy's retry adds the object, made transient by the rollback, to a session again.
- **Option 1** calls #2293 an open PR that proposes its tracking. **Option 2** dates #1212.
- **Internal notes:** the test claims are narrowed and labelled, the `force_update` tests are described exactly, #2293's timeline is corrected, and a MySQL lead is recorded under "Deliberately left out".

This is tracker item PY-3 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It would be a new issue at https://github.com/tortoise/tortoise-orm/issues/new, using the "Bug report" template.

**Proposed title:** `Model.save() returns normally and writes nothing after the instance's INSERT was rolled back`

Everything between the two rules below is the proposed issue body. The rest of this file is internal.

**Before filing:**

1. Get approval of the exact title, body and destination (`AGENTS.md` rule 9).
2. Search again for a duplicate: issues and pull requests created after 2026-10-25 01:30 UTC. Use the search API with the words unquoted, `gh api -X GET search/issues -f q='repo:tortoise/tortoise-orm <words>'`. `gh search issues -- "<words>"` sends several words as one quoted phrase: on 2026-10-25 it returned 0 results for `rollback save`, where the API returned 7. If a duplicate exists, comment there instead.
3. Re-check `develop`. Three things should still hold:
   - `Model.save()` is at `tortoise/models.py` 1135–1199, with the linked lines (1180–1183, 1186–1192, 1198) as quoted under "Source facts";
   - `BaseExecutor.execute_update()` returns early at `tortoise/backends/base/executor.py` 489–490;
   - PR #2293 is still open.

   If a line moved, update its link. If `save()` changed, run the program again before filing. If #2293 was merged or closed, rewrite the clause that cites it.
4. Check PyPI. If a release after 1.1.9 exists, run the program on it, three times per backend, before filing. That is CHK-5's rule: run the exact program that is posted.
5. Check #1212 for any reply.
6. After filing, record the issue in `docs/upstream-submissions.md`, and in the tracker. Check that file for another session's uncommitted edits first.

**Checks done 2026-10-25, between about 01:05 and 01:35 UTC.** All read-only: `gh`, `curl` to PyPI, and a blob-less clone of `develop`.

- **PyPI.** tortoise-orm 1.1.9 (uploaded 2026-10-14) is the latest release. asyncpg 0.32.0, psycopg 3.3.6 and psycopg-pool 3.3.3 are also the latest.
- **`develop`** is `ad0d6ce2b878f6d5188374eabb61d80484aedfa4` (2026-10-24 17:49 UTC, a setuptools bump). It is 20 commits after tag `1.1.9` (`ac3892300`), and its parent is the roadmap's `536fc3abd`.
  - `tortoise/models.py` changed since 1.1.9, but `Model.save()` is identical, compared as the function's source. It is at 1135–1199 instead of 1131–1195.
  - `backends/base/executor.py`, `backends/base/client.py`, `transactions.py` and both PostgreSQL clients are byte-identical to 1.1.9.
- **Duplicate search.** No report of this mechanism.
  - 28 queries over issues and pull requests, through the search API with the words unquoted:
    - the roadmap's eight: `saved_in_db`, `rollback save`, `rollback instance`, `retry save`, `IntegrityError commit`, `commit exception`, `force_update`, `not saved`;
    - twenty more: `save after rollback`, `saved rollback`, `save rollback transaction`, `in_transaction rollback save`, `save not persisted`, `save silently`, `save does nothing`, `update 0 rows`, `zero rows update`, `rows affected save`, `execute_update`, `savepoint save`, `nested transaction save`, `lost write`, `object not saved`, `saved transaction rollback`, `save rollback pk`, `rollback primary key`, `save update instead of insert`, `save no row`.
  - 209 distinct items, screened by title. Read in full: #1501, #2018, #731, #540, #242, #681, #417, and PRs #1357 and #2293.
  - A first pass with `gh search issues` had quoted the multi-word queries as phrases. The API pass above replaces it.
- **Nearest items, all different:**
  - **#1094** (open, `help wanted`, last updated 2023-10-01): asyncpg's "Resetting connection with an active transaction". It shares only a symptom. Not cited.
  - **#1212** (open since 2022-08-03, no comments): `save(force_update=True)` raises "Can't update object that doesn't exist" on MySQL for a row that was just fetched. Cited as the caution on option 2.
  - **#242** (closed 2019): a `save()` that inserted nothing, for an instance given a value for a generated primary key. A collaborator suggested there that `save()` "could raise an error (or log a warning) if no rows where affected". It was resolved in 0.15.0 by rejecting values for generated fields, and the mechanism was never established. Not cited (see "Deliberately left out").
  - **PR #2293** (open since 2026-10-03, by an outside contributor). It adds `on_commit()` with a stack of callback frames, one per transaction and savepoint level. A frame is dropped on rollback and merged into its parent on release (`tortoise/backends/base/client.py` in the PR's diff). `waketzheng` commented on 2026-10-05 with questions before merging (an issue comment, not a GitHub review); the author answered the same day and asked for another look on 2026-10-07. Cited in option 1, for that scope tracking.
  - **#417** (closed 2020): users set `_saved_in_db = False` by hand to copy an instance. `clone()` now does that.
  - **21 issues and PRs created on 2026-10-24** between 12:44 and 17:46 UTC (#2362–#2382). Their subjects are validators, URL parsing, hashing, prefetching and `clone()`. None concerns `save()` after a rollback.
- **The template.** `.github/ISSUE_TEMPLATE/bug_report.md` asks for: Describe the bug; To Reproduce ("preferably a small code snippet"); Expected behavior; Additional context. The body follows it.
- **Policy.** `docs/CONTRIBUTING.rst` says "If you want to contribute, check out the issues, or just create a PR", and asks to look for an existing issue or pull request first. Neither it, `docs/CODE_OF_CONDUCT.rst` nor `.github/PULL_REQUEST_TEMPLATE.md` states an AI policy.
- **Activity.** `waketzheng` merged outside contributors' PRs on 2026-10-24 (#2320, #2358, #2342), and released 1.1.9 (#2302).
- **Tests on `develop`** (source reading). A read-only AST scan of `tests/`: 1,969 test functions, with nothing imported or run. The outside review repeated the scan independently, and also read the helpers, transaction decorators and fixture teardown that it points to.
  - **I found no test that calls `save()`, `delete()` or `refresh_from_db()` on the same inserted instance after its transaction or savepoint rolled back.** Of the exception-catching blocks, 22 open a transaction, counting `pytest.raises`, `assertRaises`, `assertRaisesRegex`, `suppress` and `try`/`except`; none of them does it. Neither do the four explicit `rollback()` calls (`tests/test_manual_sql.py` 47, `tests/test_transactions.py` 49 and 271–272). Some tests read a retained ID after a rollback, as below.
  - **No test saves an instance again after `delete()`.**
  - **`test_force_update_raise` and `test_noid_force_update_raise`** (`tests/test_model_methods.py`, 539–542 and 851–854) set a primary key for which no row exists (`id=tournament_model.id + 100`, `id=noid_model.id + 100`), and expect `IntegrityError` from `save(force_update=True)`.
  - **`test_nested_tx_do_not_commit`** (`tests/test_transactions.py`, 99–110) reads `tournament.id` after its INSERT was rolled back. It does not save it again.

  None of these is cited in the issue.

**Re-checked 2026-10-25, about 03:00 UTC,** read-only with `gh`: `develop` is still `ad0d6ce2b`; the latest release is still 1.1.9 (published 2026-10-14); #2293 is open and unmerged; #1212 has no comments.

**Evidence.**

- **CHK-5:** [`../chk-5-tortoise/`](../chk-5-tortoise/README.md).
  - The program below is `tortoise_save_after_rollback.py`, SHA-256 `632ef90d3671d0c4ada653c9ee8c06795058cf5d81907db25836d967e9a154a3`.
  - The output below is `output/asyncpg.rep1.out`, unchanged. The six runs, three per backend, differ only in the version line and the transaction IDs.
  - The log excerpt is `output/server-log-extract.txt`, lines 16–25 and 39–50, unchanged: the `retry` arm's two transactions in that run.
  - The witness, `psql` and the server's statement log agree for all 144 transactions.
- **The count `save()` receives.** In the wrapped runs (`chk5_update_count.py`), `execute_update()` returned 0 to `save()` in all 30 calls.
- **Controls.** Django 6.1.2 and SQLAlchemy 2.1.5 persisted all four retry variants, three runs each. SQLAlchemy's rollback makes the object transient, and its retry adds the object to a session again.
- **The install line,** checked 2026-10-25 at 03:01 UTC, after the review. In a fresh virtualenv with only `tortoise-orm[asyncpg,psycopg]==1.1.9`, run from a directory holding only the program, both commands exited 0. Their outputs equal the recorded ones apart from the transaction IDs: [`../chk-5-tortoise/output/install-check/`](../chk-5-tortoise/output/install-check/).

**Source facts** (`develop` `ad0d6ce2b`; the functions are identical in 1.1.9, where `save()` is 4 lines higher):

- **The default path** (`tortoise/models.py`, 1186–1192): `if self._saved_in_db or update_fields:`, and with `pk` set, `await executor.execute_update(self, update_fields)`, whose result is not kept.
- **`force_update`** (1180–1183): `rows = await executor.execute_update(self, update_fields)`, then `if rows == 0: raise IntegrityError(f"Can't update object that doesn't exist. PK: {self.pk}")`.
- **The flag** (1198): `self._saved_in_db = True`, after either path.
- **The early return** (`tortoise/backends/base/executor.py`, 489–490): `if not effective_fields: return 0`.

**Deliberately left out:**

- **PY-8** (COMMIT-time exception translation) and **PY-19.**
- **#1094.** It shares only a symptom.
- **#242. Optional; the maintainer may add it.** Its 2019 suggestion supports option 2, but its mechanism was never established, and quoting it adds a line. A possible line: "Raising when no row was affected was suggested once before, in #242 (2019)."
- **The server-side transaction-ID signal,** and `pg_xact_status()` beyond the program's output.
- **An exception class, or a patch.** The roadmap's corrections (§7) wait for the maintainers.
- **Framing the two retries as two remedies.** Both sent an UPDATE that matched no row, so the issue says only that changing a field makes no difference.
- **Snapshotting all instance state on rollback.** That would be a redesign.
- **A MySQL lead for option 2. Source reading only; not run on MySQL.** Django's MySQL backend sets `CLIENT.FOUND_ROWS`, with the comment "We need the number of potentially affected rows after an "UPDATE", not the number of changed rows" (`django/db/backends/mysql/base.py`, 232–234, Django 6.1.2). Nothing in `tortoise/` sets a client flag. #1212's script changes the value before saving, so this would explain #1212 only if the row already held the new value, for example on a second run. Check it on MySQL before any PR for option 2.

**Length.** Outside `<details>`: 28 non-empty source lines, including the table and the two-line command block: 642 words, about 61 lines at 100 characters per line (link targets not counted). Before the revision it was 601 words, about 58 lines. The program, the 41-line output and the 22-line log excerpt are in 3 `<details>` blocks.

---

**Describe the bug**

When `save()` inserts a new instance inside `in_transaction()` and the block then raises, the transaction rolls back, but the instance keeps its `pk` and `_saved_in_db = True`. If the application saves the same instance again, for example on a retry, Tortoise sends an UPDATE for the old `pk` (`UPDATE "item" SET "arm"=$1,"value"=$2 WHERE "id"=$3` in the script below). That matches no row, `save()` returns normally, the transaction commits, and nothing is written. Changing a field before the retry makes no difference.

The same happens with a savepoint: a nested `in_transaction()` saves the instance and raises, and the outer block catches the error, saves the instance again and commits without the row.

**To Reproduce**

The script below runs these arms, each with a new instance, and reads the outcome from a separate connection:

| Arm | Second call | Transaction | Rows |
| --- | --- | --- | --- |
| `retry` (the first case above) | returned normally | committed | 0 |
| `retry-changed` (a field changed before the retry) | returned normally | committed | 0 |
| `savepoint` (the second case above) | returned normally | committed | 0 |
| `savepoint-changed` (a field changed before the retry) | returned normally | committed | 0 |
| `control` (a new instance, saved once) | returned normally | committed | 1 |
| `force_update` (as `retry`, with `save(force_update=True)`) | raised `IntegrityError` | rolled back | 0 |

Run it against a disposable server. `DATABASE_URL` must be able to create databases: the program first drops any database named `tortoise_save_after_rollback`, creates it, and drops it at the end. Install `tortoise-orm[asyncpg,psycopg]==1.1.9`: both commands also use asyncpg, for the setup and witness connections.

```
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python tortoise_save_after_rollback.py asyncpg
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python tortoise_save_after_rollback.py psycopg
```

<details>
<summary>tortoise_save_after_rollback.py</summary>

```python
"""Tortoise ORM: save() after a rolled-back transaction returns normally and writes nothing.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python tortoise_save_after_rollback.py [asyncpg|psycopg]

DATABASE_URL must be able to create a database. The program first drops any database
named tortoise_save_after_rollback, creates it, and drops it at the end. Tortoise uses
the backend named on the command line. A separate asyncpg connection, in autocommit,
reads what PostgreSQL did.

In each arm, save() runs inside in_transaction(), or inside a nested in_transaction()
(a savepoint), and the block then raises, so the INSERT is rolled back. The same
instance is then saved again. The witness reads pg_xact_status() of the transaction IDs
captured inside the transactions, and counts the arm's rows.
"""

import asyncio
import os
import platform
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import tortoise
from tortoise import Tortoise, fields
from tortoise.exceptions import IntegrityError
from tortoise.models import Model
from tortoise.transactions import in_transaction

URL = os.environ["DATABASE_URL"]
NAME = "tortoise_save_after_rollback"


class Item(Model):
    id = fields.IntField(primary_key=True)
    arm = fields.TextField()
    value = fields.IntField()

    class Meta:
        table = "item"


class AppError(Exception):
    pass


async def current_xid(conn):
    rows = await conn.execute_query_dict("select pg_current_xact_id()::text as xid")
    return rows[0]["xid"]


async def fate(witness, xid):
    status = await witness.fetchval("select pg_xact_status($1::text::xid8)", xid)
    return f"pg_xact_status({xid}) {status}"


async def rows(witness, arm):
    count = await witness.fetchval("select count(*) from item where arm = $1", arm)
    return f"rows with arm={arm!r}: {count}"


async def failed_attempt(witness, obj):
    try:
        async with in_transaction() as conn:
            await obj.save()
            xid = await current_xid(conn)
            raise AppError("the application fails after save()")
    except AppError:
        pass
    print(f"  first save() returned, pk={obj.pk}; the block raised AppError")
    print(f"  first transaction: {await fate(witness, xid)}")
    print(f"  after the rollback: pk={obj.pk}, _saved_in_db={obj._saved_in_db}, {await rows(witness, obj.arm)}")


async def retry(witness, change=False):
    arm = "retry-changed" if change else "retry"
    print(f"{arm}: save() in in_transaction(), the block raises; then"
          + (" value = 2 and" if change else "") + " save() again in a new in_transaction()")
    obj = Item(arm=arm, value=1)
    await failed_attempt(witness, obj)
    if change:
        obj.value = 2
    async with in_transaction() as conn:
        await obj.save()
        xid = await current_xid(conn)
    print("  second save() returned normally")
    print(f"  second transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, arm)}")


async def savepoint(witness, change=False):
    arm = "savepoint-changed" if change else "savepoint"
    print(f"{arm}: in an outer in_transaction(), save() in a nested in_transaction() that raises;"
          " the error is caught; then" + (" value = 2 and" if change else "") + " save() again in the outer block")
    obj = Item(arm=arm, value=1)
    async with in_transaction() as conn:
        try:
            async with in_transaction():
                await obj.save()
                raise AppError("the application fails after save()")
        except AppError:
            pass
        print(f"  first save() returned, pk={obj.pk}; the nested block raised AppError")
        print(f"  after the savepoint rollback: pk={obj.pk}, _saved_in_db={obj._saved_in_db}")
        if change:
            obj.value = 2
        await obj.save()
        xid = await current_xid(conn)
        print("  second save() returned normally")
    print("  the outer block exited normally")
    print(f"  outer transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, arm)}")


async def control(witness):
    print("control: save() of a new instance in in_transaction()")
    obj = Item(arm="control", value=1)
    async with in_transaction() as conn:
        await obj.save()
        xid = await current_xid(conn)
    print(f"  save() returned, pk={obj.pk}")
    print(f"  transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, 'control')}")


async def force_update(witness):
    print("force_update: as retry, but the second call is save(force_update=True)")
    obj = Item(arm="force_update", value=1)
    await failed_attempt(witness, obj)
    try:
        async with in_transaction() as conn:
            xid = await current_xid(conn)
            await obj.save(force_update=True)
        print("  second save(force_update=True) returned normally")
    except IntegrityError as exc:
        print(f"  second save(force_update=True) raised IntegrityError: {exc}")
    print(f"  second transaction: {await fate(witness, xid)}")
    print(f"  {await rows(witness, 'force_update')}")


async def run(backend):
    if backend == "psycopg":
        import psycopg
        import psycopg_pool

        driver = f"psycopg {psycopg.__version__}, psycopg_pool {psycopg_pool.__version__}"
    else:
        driver = f"asyncpg {asyncpg.__version__}"
    print(
        f"python {platform.python_version()}, tortoise-orm {tortoise.__version__},"
        f" backend {backend} ({driver}), {platform.system()} {platform.machine()}"
    )
    admin = await asyncpg.connect(URL, server_settings={"application_name": "repro-admin"})
    print(f"server_version {await admin.fetchval('show server_version')}")
    await admin.execute(f"drop database if exists {NAME} with (force)")
    await admin.execute(f"create database {NAME}")

    url = urlsplit(URL)
    scheme = "postgres" if backend == "asyncpg" else "psycopg"
    db_url = urlunsplit((scheme, url.netloc, f"/{NAME}", "application_name=repro-tortoise", ""))
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})
    await Tortoise.generate_schemas()

    witness = await asyncpg.connect(
        URL, database=NAME, server_settings={"application_name": "repro-witness"}
    )
    await retry(witness)
    await retry(witness, change=True)
    await savepoint(witness)
    await savepoint(witness, change=True)
    await control(witness)
    await force_update(witness)
    await witness.close()

    await Tortoise.close_connections()
    await admin.execute(f"drop database {NAME} with (force)")
    await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg"):
        sys.exit("usage: tortoise_save_after_rollback.py [asyncpg|psycopg]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
```

</details>

<details>
<summary>Output with the asyncpg backend (the psycopg runs differ only in the version line and the transaction IDs)</summary>

```
python 3.13.11, tortoise-orm 1.1.9, backend asyncpg (asyncpg 0.32.0), Darwin arm64
server_version 18.6 (Debian 18.6-1.pgdg13+2)
retry: save() in in_transaction(), the block raises; then save() again in a new in_transaction()
  first save() returned, pk=1; the block raised AppError
  first transaction: pg_xact_status(755) aborted
  after the rollback: pk=1, _saved_in_db=True, rows with arm='retry': 0
  second save() returned normally
  second transaction: pg_xact_status(756) committed
  rows with arm='retry': 0
retry-changed: save() in in_transaction(), the block raises; then value = 2 and save() again in a new in_transaction()
  first save() returned, pk=2; the block raised AppError
  first transaction: pg_xact_status(757) aborted
  after the rollback: pk=2, _saved_in_db=True, rows with arm='retry-changed': 0
  second save() returned normally
  second transaction: pg_xact_status(758) committed
  rows with arm='retry-changed': 0
savepoint: in an outer in_transaction(), save() in a nested in_transaction() that raises; the error is caught; then save() again in the outer block
  first save() returned, pk=3; the nested block raised AppError
  after the savepoint rollback: pk=3, _saved_in_db=True
  second save() returned normally
  the outer block exited normally
  outer transaction: pg_xact_status(759) committed
  rows with arm='savepoint': 0
savepoint-changed: in an outer in_transaction(), save() in a nested in_transaction() that raises; the error is caught; then value = 2 and save() again in the outer block
  first save() returned, pk=4; the nested block raised AppError
  after the savepoint rollback: pk=4, _saved_in_db=True
  second save() returned normally
  the outer block exited normally
  outer transaction: pg_xact_status(761) committed
  rows with arm='savepoint-changed': 0
control: save() of a new instance in in_transaction()
  save() returned, pk=5
  transaction: pg_xact_status(763) committed
  rows with arm='control': 1
force_update: as retry, but the second call is save(force_update=True)
  first save() returned, pk=6; the block raised AppError
  first transaction: pg_xact_status(764) aborted
  after the rollback: pk=6, _saved_in_db=True, rows with arm='force_update': 0
  second save(force_update=True) raised IntegrityError: Can't update object that doesn't exist. PK: 6
  second transaction: pg_xact_status(765) aborted
  rows with arm='force_update': 0
```

</details>

<details>
<summary>Server log for the <code>retry</code> arm (<code>log_statement=all</code>, and <code>auto_explain</code> with <code>log_analyze</code>)</summary>

```
2026-10-25 01:20:48.245 UTC [107] app=repro-tortoise xid=0 LOG:  statement: BEGIN;
2026-10-25 01:20:48.247 UTC [107] app=repro-tortoise xid=0 LOG:  execute __asyncpg_stmt_2__: INSERT INTO "item" ("arm","value") VALUES ($1,$2) RETURNING "id"
2026-10-25 01:20:48.247 UTC [107] app=repro-tortoise xid=0 DETAIL:  Parameters: $1 = 'retry', $2 = '1'
2026-10-25 01:20:48.247 UTC [107] app=repro-tortoise xid=755 LOG:  duration: 0.100 ms  plan:
	Query Text: INSERT INTO "item" ("arm","value") VALUES ($1,$2) RETURNING "id"
	Query Parameters: $1 = 'retry', $2 = '1'
	Insert on item  (cost=0.00..0.01 rows=1 width=40) (actual rows=1.00 loops=1)
	  ->  Result  (cost=0.00..0.01 rows=1 width=40) (actual rows=1.00 loops=1)
2026-10-25 01:20:48.247 UTC [107] app=repro-tortoise xid=755 LOG:  execute __asyncpg_stmt_3__: select pg_current_xact_id()::text as xid
2026-10-25 01:20:48.248 UTC [107] app=repro-tortoise xid=755 LOG:  statement: ROLLBACK;
…
2026-10-25 01:20:48.250 UTC [107] app=repro-tortoise xid=0 LOG:  statement: BEGIN;
2026-10-25 01:20:48.251 UTC [107] app=repro-tortoise xid=0 LOG:  execute __asyncpg_stmt_6__: UPDATE "item" SET "arm"=$1,"value"=$2 WHERE "id"=$3
2026-10-25 01:20:48.251 UTC [107] app=repro-tortoise xid=0 DETAIL:  Parameters: $1 = 'retry', $2 = '1', $3 = '1'
2026-10-25 01:20:48.251 UTC [107] app=repro-tortoise xid=0 LOG:  duration: 0.003 ms  plan:
	Query Text: UPDATE "item" SET "arm"=$1,"value"=$2 WHERE "id"=$3
	Query Parameters: $1 = 'retry', $2 = '1', $3 = '1'
	Update on item  (cost=0.15..8.17 rows=0 width=0) (actual rows=0.00 loops=1)
	  ->  Index Scan using item_pkey on item  (cost=0.15..8.17 rows=1 width=42) (actual rows=0.00 loops=1)
	        Index Cond: (id = 1)
	        Index Searches: 1
2026-10-25 01:20:48.251 UTC [107] app=repro-tortoise xid=0 LOG:  execute __asyncpg_stmt_3__: select pg_current_xact_id()::text as xid
2026-10-25 01:20:48.251 UTC [107] app=repro-tortoise xid=756 LOG:  statement: COMMIT;
```

</details>

**Expected behavior**

The second `save()` should either write the row or raise. It should not return normally after writing nothing. `save(force_update=True)` already raises in this situation (the `force_update` arm).

**Additional context**

- Tortoise ORM 1.1.9 with asyncpg 0.32.0, and with psycopg 3.3.6 (psycopg_pool 3.3.3), on PostgreSQL 18.6; Python 3.13.11 on macOS arm64. Three runs per backend gave the same result. I ran only the two PostgreSQL backends. I didn't run `develop`, but `Model.save()` is unchanged there.
- From the source: `save()` takes the update path because `_saved_in_db` is set, calls `execute_update()`, and ignores the count it returns ([models.py#L1186-L1192](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1186-L1192)). It sets `_saved_in_db = True` after the statement ([models.py#L1198](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1198)), and I found nothing in Tortoise that resets it when the transaction or savepoint rolls back. With `force_update=True` the same count raises ([models.py#L1180-L1183](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1180-L1183)). In the runs, `_saved_in_db` was still `True` after every rollback; with `execute_update()` wrapped, it returned 0 for every retry, and `auto_explain` showed each retry's UPDATE matching 0 rows.
- Django 6.1.2 persisted all four retries on the same server. So did SQLAlchemy 2.1.5, where the rollback makes the object transient and the retry adds it to a session again.

Which direction would you prefer? Or is saving an instance again after a rollback not meant to be supported?

1. Reset `_saved_in_db` for the instances inserted in a transaction or savepoint when that scope rolls back. The savepoint arms show that this has to work per savepoint level, since the outer transaction still commits. Open PR #2293 proposes the same kind of per-scope tracking for `on_commit()` callbacks.
2. When the UPDATE in the default path matches no row, raise as `force_update=True` does, or fall back to an INSERT as Django does. Two cautions: `execute_update()` also returns 0 without sending anything when no field needs updating ([executor.py#L489-L490](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/backends/base/executor.py#L489-L490)), and #1212 (2022, on 0.18.1 and 0.19.2) reported a count of 0 on MySQL for a row that exists, so the count may not be reliable on every backend.

If one of these works for you, I'm happy to prepare a PR with regression tests for the plain and savepoint cases.

---
