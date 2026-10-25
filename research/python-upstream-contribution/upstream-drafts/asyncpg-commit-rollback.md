# Draft: asyncpg, new issue in MagicStack/asyncpg

**Filed 2026-10-24** as `KevinBlakeLopez`: https://github.com/MagicStack/asyncpg/issues/1400 The filed title and body match the text below; they were compared through the API. Prepared 2026-10-24. Written by: Claude Opus 5.5 (max).

**Checked just before filing, about 21:53 UTC:**
- No asyncpg issue or PR had been created or updated that day.
- The duplicate queries returned the same results as before, and there was no new Discussion.
- `master` was still `13b01910d`, and no commit had touched the linked files.
- PyPI `latest` was 0.32.0.
- psycopg#1453 had no maintainer reply.

GitHub cross-referenced #1400 on #1453.

**Revised later on 2026-10-24,** after an outside adversarial review:

- **The compatibility note.** The first version said that no asyncpg test exits a transaction block normally after a caught error. That was false: see `test_timeout_06` under "Source facts". The note now cites that test and asks the maintainers which behaviour they want. "Expected" and the closing PR offer follow from that.
- **The `57014`/`40P01`/`40001` bullet** is dropped.
- **The downstream bullet** names the versions and entry points that were measured.
- **The setup paragraph** discloses the initial forced `DROP DATABASE`.
- **The command** is two pasteable lines.
- **The output** is folded.
- **Two sentences are tightened:** the opening, and the `raw` arm sentence.

This is tracker item PY-2 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It would be a new issue at https://github.com/MagicStack/asyncpg/issues/new.

**Proposed title:** `Transaction.commit() returns normally when PostgreSQL answers COMMIT with ROLLBACK`

Everything between the two rules below is the proposed issue body. The rest of this file is internal.

**Before filing:**

1. Get approval of the exact title, body and destination (`AGENTS.md` rule 9).
2. Search again for a duplicate: issues and pull requests created after 2026-10-24, and GitHub Discussions. If one exists, comment there instead.
3. Re-check `master`. Two things should still hold:
   - `asyncpg/transaction.py` is unchanged since 2023-05-30 (SHA-256 `b8026893a4a1c7bf8a76de65e0d5fe189b4bc552523d74ce254af219d6c8546f`);
   - the `execute()` docstring is still at `asyncpg/connection.py` line 348;
   - `test_timeout_06`'s last arm is still at `tests/test_timeout.py` lines 104–113.

   If any changed, re-check the three links.
4. Check PyPI. If a release after 0.32.0 exists, run the program on it, three times on asyncio and three on uvloop, before filing. That is CHK-2's rule: run the exact program that is posted.
5. Check psycopg#1453. If its maintainer has answered, for example on the exception class, consider whether one line should say so. Do not wait for that answer.
6. After filing, record the issue in `docs/upstream-submissions.md`, and in the tracker. Check that file for another session's uncommitted edits first.

**Checks done 2026-10-24, between about 16:20 and 16:35 UTC.** All read-only, with `gh` and a shallow clone of `master`.

- **Duplicate search.** No report of this mechanism. The queries were:
  - 19 phrasings over issues and pull requests: `commit ROLLBACK`, `commit rollback status`, `transaction commit aborted`, `commit status ROLLBACK`, `InFailedSQLTransactionError commit`, `commit returns rollback`, `transaction committed state`, `commit silently`, `silently rolled back`, `COMMIT command tag`, `aborted transaction commit`, `current transaction is aborted`, `commit does not raise`, `commit no exception`, `UniqueViolationError transaction commit`, `exception inside transaction commit`, `transaction state committed`, `rollback instead of commit`, `commit status string`;
  - five broader title and term queries;
  - seven queries over Discussions.
- **Nearest items, all different:**
  - #1130 (open, no comments) asks to make the transaction state public;
  - #1386 (open) reports a failed `BEGIN` that leaves `_top_xact` set. PRs #1387 (open, reviewed by the maintainer on 2026-10-07) and #1399 (open since 2026-10-22, new since the roadmap's search) change `start()` and its tests, not `__commit`;
  - #508 (closed 2019) is a deferred constraint raising at `COMMIT`;
  - Discussion #881 used the wrong connection;
  - #956 and #1215 are other paths.
- **The template.** `.github/ISSUE_TEMPLATE.md` at `13b01910d`. Its bullet questions are copied below as they stand.
  - It asks for "a test case that reproduces the problem … with clear instructions on how to run it".
  - The repository has no CONTRIBUTING, SECURITY or code-of-conduct file, and states no AI policy. MagicStack has no organisation `.github` repository.
- **`master`** is `13b01910d` (2026-10-08). The latest release is v0.32.0 (2026-10-06), which is also PyPI's latest.
- **The maintainer is active.** Elvis Pranskevichus (`elprans`) merged his own PRs through 2026-10-06, and reviewed #1387 on 2026-10-07. In #1355 (2026-09-21) he wrote that asyncpg "did not receive enough love in 2026", citing an "overwhelmed inbox", and that "Help is always welcome!". Expect a slow reply.

**Evidence.**

- **CHK-2:** [`../chk-2-asyncpg/`](../chk-2-asyncpg/README.md).
  - The program below is `asyncpg_commit_rollback.py`, SHA-256 `891ffa6a9efc9332f5d3991f904fec5379bd760dc0fc4fe36baca06cd0b0c104`.
  - The output below is `output/asyncio.rep1.out`, unchanged. The six runs (three on asyncio, three on uvloop) differ only in the event-loop line and the transaction IDs.
  - `psql` and the server's statement log agree for all 24 transactions.
- **Other SQLSTATEs,** no longer cited in the issue (see "Deliberately left out"): the gap analysis's P6 ([`../../python-production-failure-gap-analysis/output/p6.jsonl`](../../python-production-failure-gap-analysis/output/p6.jsonl) and [`p6.server-log-endings.txt`](../../python-production-failure-gap-analysis/output/p6.server-log-endings.txt)).
  - `async with c.transaction()` returned normally after a caught `57014`, `40P01`, or `40001` (the last at REPEATABLE READ). Three runs each.
  - Every transaction was `aborted`, and each session's last statement in the server log was `COMMIT`.
- **Downstream:**
  - **Tortoise 1.1.9.** PPCS `reports/examples/2026-10-19T12-45-38Z-c45624`, TX-01A: FAIL in 3 of 3 runs, with driver trace `COMMIT; -> ROLLBACK`. `TransactionWrapper.commit()` calls `await self.transaction.commit()` (`tortoise/backends/asyncpg/client.py`, 197–203).
  - **SQLAlchemy 2.1.5.** The gap analysis's P1, arm E: `postgresql+asyncpg` `engine.begin()` exited normally, and the transaction was `aborted`, in 3 of 3 runs. The adapter's `commit()` calls the asyncpg `Transaction.commit` and passes any exception to `_handle_exception` (`dialects/postgresql/asyncpg.py`, 902–908 and 919–926).

**Source facts** (`master` `13b01910d`, identical to 0.32.0):

- **`Transaction.__commit`** (`asyncpg/transaction.py`, 175–192). Line 187 is `await self._connection.execute(query)`, and its return value is not kept. Line 192 sets `TransactionState.COMMITTED`.
- **`__check_state_base`** (154–157) produces "cannot rollback; the transaction is already committed".
- **`Connection.execute()`** documents ":return str: Status of the last SQL command" (`asyncpg/connection.py`, 348).
- **asyncpg's own tests exit a transaction block normally after a caught error that aborted it.** A raising fix would change these tests.
  - **`test_timeout_06`** (`tests/test_timeout.py`, 77–113). In its last arm (104–113), a cursor fetch times out inside `async with self.con.transaction():`. The arm then asserts `InFailedSQLTransactionError`, and the block exits with no expected exception.
  - **`test_timeout_04`** (60–66) and `test_timeout_06`'s earlier arms catch a timeout inside the block in the same way.
  - **Why the first scan missed them.** It looked only for try/except. These tests catch with `self.assertRaises`. The only explicit `.commit()` call in `tests/` is in `test_transaction_interface_errors` (`tests/test_transaction.py:141`).

**Deliberately left out:**

- `repr()` and `TransactionState` (#1130). The public signal is the normal return and the `rollback()` message.
- An exception class or a fix. The roadmap's correction (§7) waits for the maintainer.
- Tortoise's exception translation (PY-8), and SQLAlchemy's ORM `after_commit` (PY-9).
- The roadmap's judgment that `RELEASE SAVEPOINT` already raises `25P02` in an aborted transaction. It was not run.
- Separate downstream reports. Tortoise and SQLAlchemy are named only as callers.
- **The `57014`, `40P01` and `40001` results.** They were dropped after the outside review, for two reasons:
  - their program is not in the issue;
  - `test_timeout_06` already shows the timeout case, with asyncpg's own test.

  They stay in P6, for a follow-up if one is asked for.

**Length.** Outside `<details>`:

- 25 non-empty source lines of template fields, prose and bullets: 496 words, about 47 lines at 100 characters per line;
- a two-line command block.

The program and the 19-line output are both in `<details>`.

---

* **asyncpg version**: 0.32.0 (`asyncpg/transaction.py` is unchanged on `master`)
* **PostgreSQL version**: 18.6 (the `postgres:18.6` Docker image)
* **Do you use a PostgreSQL SaaS?  If so, which?  Can you reproduce
  the issue with a local PostgreSQL install?**: No, a local Docker container
* **Python version**: 3.13.11
* **Platform**: macOS 26.6.2, arm64
* **Do you use pgbouncer?**: No
* **Did you install asyncpg with pip?**: Yes, the wheel
* **If you built asyncpg locally, which version of Cython did you use?**: n/a
* **Can the issue be reproduced under both asyncio and
  [uvloop](https://github.com/magicstack/uvloop)?**: Yes. Three runs each, on asyncio and on uvloop 0.23.0, with the same result

When a statement fails inside a transaction and the application catches the error without rolling back to a savepoint, PostgreSQL answers the later `COMMIT` with the command tag `ROLLBACK`. In that case `Transaction.commit()` returns `None`, and `async with con.transaction():` exits normally. asyncpg then treats the transaction as committed: a following `rollback()` raises `cannot rollback; the transaction is already committed`. The row inserted before the error is gone. On the same server, `con.execute('COMMIT')` returns `'ROLLBACK'`.

### Reproduction

Run it against a disposable server. `DATABASE_URL` must be able to create databases: the program first drops any database named `asyncpg_commit_rollback`, creates it, and drops it at the end. Each arm uses its own connection. A separate connection then reads `pg_xact_status()` of the arm's transaction ID, whether the arm's row is visible, and the session's last statement.

```
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python asyncpg_commit_rollback.py asyncio
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python asyncpg_commit_rollback.py uvloop
```

<details>
<summary>asyncpg_commit_rollback.py</summary>

```python
"""asyncpg: the transaction API returns normally after PostgreSQL answers COMMIT with ROLLBACK.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python asyncpg_commit_rollback.py [asyncio|uvloop]

DATABASE_URL must be able to create a database. The program connects to it, creates
database asyncpg_commit_rollback, and drops that database at the end.

Each arm runs on its own connection. It inserts a marker row, then inserts a duplicate
key and catches UniqueViolationError, then finishes the transaction the arm's way.
A separate connection then reads what PostgreSQL did: pg_xact_status() of the
transaction ID captured inside the transaction, whether the marker row is visible, and
the session's state and last statement in pg_stat_activity.
"""

import asyncio
import os
import platform
import sys

import asyncpg

URL = os.environ["DATABASE_URL"]
NAME = "asyncpg_commit_rollback"


async def connect(app, database=NAME):
    return await asyncpg.connect(
        URL, database=database, server_settings={"application_name": app}
    )


async def insert_marker(con, marker):
    await con.execute("insert into item (name) values ($1)", marker)
    return await con.fetchval("select pg_current_xact_id()::text")


async def insert_duplicate(con):
    try:
        await con.execute("insert into uniq (code) values ('taken')")
    except asyncpg.UniqueViolationError as exc:
        return f"caught {type(exc).__name__} ({exc.sqlstate})"
    return "no error"


async def insert_duplicate_in_savepoint(con):
    try:
        async with con.transaction():
            await con.execute("insert into uniq (code) values ('taken')")
    except asyncpg.UniqueViolationError as exc:
        return f"caught {type(exc).__name__} ({exc.sqlstate}) outside the savepoint block"
    return "no error"


async def report(probe, con, xid, marker):
    fate = await probe.fetchval("select pg_xact_status($1::text::xid8)", xid)
    seen = await probe.fetchval("select count(*) from item where name = $1", marker)
    row = await probe.fetchrow(
        "select state, query from pg_stat_activity where pid = $1", con.get_server_pid()
    )
    print(
        f"  PostgreSQL: pg_xact_status({xid}) {fate}, marker visible {bool(seen)},"
        f" session {row['state']}, last statement {row['query']!r}"
    )


async def managed(probe):
    print("managed: async with con.transaction(), error caught inside the block")
    con = await connect("repro-managed")
    try:
        async with con.transaction():
            xid = await insert_marker(con, "managed")
            print(f"  {await insert_duplicate(con)}")
        print("  the block exited normally")
    except Exception as exc:
        print(f"  the block raised {type(exc).__name__}: {exc}")
    await report(probe, con, xid, "managed")
    await con.close()


async def explicit(probe):
    print("explicit: tr.start(), error caught, tr.commit()")
    con = await connect("repro-explicit")
    tr = con.transaction()
    await tr.start()
    xid = await insert_marker(con, "explicit")
    print(f"  {await insert_duplicate(con)}")
    try:
        print(f"  commit() returned {await tr.commit()!r}")
    except Exception as exc:
        print(f"  commit() raised {type(exc).__name__}: {exc}")
    try:
        await tr.rollback()
        print("  rollback() afterwards returned")
    except asyncpg.InterfaceError as exc:
        print(f"  rollback() afterwards raised InterfaceError: {exc}")
    await report(probe, con, xid, "explicit")
    await con.close()


async def raw(probe):
    print("raw: execute('BEGIN'), error caught, execute('COMMIT')")
    con = await connect("repro-raw")
    await con.execute("BEGIN")
    xid = await insert_marker(con, "raw")
    print(f"  {await insert_duplicate(con)}")
    print(f"  execute('COMMIT') returned {await con.execute('COMMIT')!r}")
    await report(probe, con, xid, "raw")
    await con.close()


async def control(probe):
    print("control: async with con.transaction(), error caught around a nested con.transaction() (savepoint)")
    con = await connect("repro-control")
    try:
        async with con.transaction():
            xid = await insert_marker(con, "control")
            print(f"  {await insert_duplicate_in_savepoint(con)}")
        print("  the block exited normally")
    except Exception as exc:
        print(f"  the block raised {type(exc).__name__}: {exc}")
    await report(probe, con, xid, "control")
    await con.close()


async def run():
    loop = asyncio.get_running_loop()
    uvloop = sys.modules.get("uvloop")
    print(
        f"python {platform.python_version()}, asyncpg {asyncpg.__version__},"
        f" event loop {type(loop).__module__}.{type(loop).__qualname__}"
        + (f" (uvloop {uvloop.__version__})" if uvloop else "")
        + f", {platform.system()} {platform.machine()}"
    )
    admin = await connect("repro-admin", database=None)
    print(f"server_version {await admin.fetchval('show server_version')}")
    await admin.execute(f"drop database if exists {NAME} with (force)")
    await admin.execute(f"create database {NAME}")

    setup = await connect("repro-setup")
    await setup.execute("create table item (id serial primary key, name text not null)")
    await setup.execute("create table uniq (id serial primary key, code text not null unique)")
    await setup.execute("insert into uniq (code) values ('taken')")
    await setup.close()

    probe = await connect("repro-witness")
    for arm in (managed, explicit, raw, control):
        await arm(probe)
    await probe.close()

    await admin.execute(f"drop database {NAME} with (force)")
    await admin.close()


def main():
    loop = sys.argv[1] if len(sys.argv) > 1 else "asyncio"
    if loop == "asyncio":
        asyncio.run(run())
    elif loop == "uvloop":
        import uvloop

        uvloop.run(run())
    else:
        sys.exit("usage: asyncpg_commit_rollback.py [asyncio|uvloop]")


if __name__ == "__main__":
    main()
```

</details>

<details>
<summary>Output on asyncio (the uvloop runs differ only in the event-loop line and the transaction IDs)</summary>

```
python 3.13.11, asyncpg 0.32.0, event loop asyncio.unix_events._UnixSelectorEventLoop, Darwin arm64
server_version 18.6 (Debian 18.6-1.pgdg13+2)
managed: async with con.transaction(), error caught inside the block
  caught UniqueViolationError (23505)
  the block exited normally
  PostgreSQL: pg_xact_status(757) aborted, marker visible False, session idle, last statement 'COMMIT;'
explicit: tr.start(), error caught, tr.commit()
  caught UniqueViolationError (23505)
  commit() returned None
  rollback() afterwards raised InterfaceError: cannot rollback; the transaction is already committed
  PostgreSQL: pg_xact_status(758) aborted, marker visible False, session idle, last statement 'COMMIT;'
raw: execute('BEGIN'), error caught, execute('COMMIT')
  caught UniqueViolationError (23505)
  execute('COMMIT') returned 'ROLLBACK'
  PostgreSQL: pg_xact_status(759) aborted, marker visible False, session idle, last statement 'COMMIT'
control: async with con.transaction(), error caught around a nested con.transaction() (savepoint)
  caught UniqueViolationError (23505) outside the savepoint block
  the block exited normally
  PostgreSQL: pg_xact_status(760) committed, marker visible True, session idle, last statement 'COMMIT;'
```

</details>

### Expected

When the server completes `COMMIT` with `ROLLBACK`, the transaction should not be treated as committed, and callers should be able to tell. Raising from `Transaction.commit()` and from the exit of `async with con.transaction()` would do that; see the compatibility note below.

### Actual

Both return normally (`managed` and `explicit` above), and a later `rollback()` reports the transaction as committed. PostgreSQL aborted it: `pg_xact_status()` is `aborted`, and the row is not visible. The savepoint control commits as expected.

### Where the status is dropped

`Transaction.__commit` awaits `self._connection.execute(query)` without keeping its return value, then sets `TransactionState.COMMITTED` ([transaction.py#L186-L192](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/asyncpg/transaction.py#L186-L192)). That return value is the command status ("Status of the last SQL command", [connection.py#L348](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/asyncpg/connection.py#L348)). In this situation it is `'ROLLBACK'`, which the `raw` arm's `execute('COMMIT')` returns in the same state.

### Notes

- Tortoise ORM 1.1.9's `in_transaction()` and SQLAlchemy Core 2.1.5's `engine.begin()`, both on asyncpg 0.32.0, also exit normally after a caught `23505`; both commit through `Transaction.commit()`. I'm reporting it here because this is where the status is dropped.
- psycopg 3 does the same in `Connection.commit()`: psycopg/psycopg#1453.
- Raising here would change behaviour your tests rely on: `test_timeout_06` ([test_timeout.py#L104-L113](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/tests/test_timeout.py#L104-L113)) asserts `InFailedSQLTransactionError` inside `async with self.con.transaction():`, then expects the block to exit normally. Would you rather the transaction API raise when `COMMIT` returns `ROLLBACK`, or keep the current completion but stop recording the transaction as committed (#1130 asks for that state to be public)?

Once you have decided which behaviour you want, I'm happy to prepare a PR with tests for the managed and explicit forms and a savepoint control.

---
