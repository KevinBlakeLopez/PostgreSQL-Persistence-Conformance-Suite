# Draft: psycopg, follow-up comment on psycopg/psycopg#1453

**Posted 2026-10-24** as `KevinBlakeLopez`: https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348 The posted body matches the comment below; it was compared through the API. Prepared 2026-10-24. Written by: Claude Opus 5.5 (max).

**Issue closed 2026-10-27** by `dvarrazzo`: https://github.com/psycopg/psycopg/issues/1453#issuecomment-6443758485 His comment does not mention `transaction()` or `Transaction.status`. A thank-you that does not mention this API is drafted and not posted: [psycopg-1453-thanks.md](psycopg-1453-thanks.md).

**Checked just before posting, about 21:53 UTC.** #1453 was open, with no comment and no timeline event. `master` was still `99356800e`, and no commit had touched the linked files. PyPI `latest` was 3.3.6.

**Revised later on 2026-10-24,** after an outside adversarial review. Four changes:

- **The compatibility paragraph.** The first version said that no test catches a database error inside `transaction()`. That was false: see `test_outer_transaction_error` under "Source facts". The paragraph now names that test, and says that a `status`-only fix conflicts with neither test.
- **The savepoint control.** It now says where the error is caught.
- **"Not run"** is narrowed to a `COMMIT` sent while a pipeline is still open.
- **The program note.** One sentence in `<details>` now discloses the initial forced `DROP DATABASE`.

After the reviewer's recheck, "When I ran its body" became "When I ran the same steps outside pytest". The script replaces `pytest.raises` with `try`/`except`, and the pytest test itself was not run.

This is tracker item PY-1b in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It is a regular comment on https://github.com/psycopg/psycopg/issues/1453, which `KevinBlakeLopez` filed on 2026-10-21 (PY-1a). It is not a new issue.

Everything between the two rules below is the proposed comment. The rest of this file is internal.

**Before posting:**

1. Get approval of the exact text and of the destination (`AGENTS.md` rule 9).
2. Re-check #1453 for its state and any new comment. Stop in three cases:
   - it was closed as intended behaviour: record that, and do not argue;
   - a fix covering `Transaction` landed: verify it and record it;
   - a maintainer has already raised `transaction()`.
3. Re-check `master`. If any of these files changed after `99356800e`, re-check the linked line ranges:
   - `psycopg/psycopg/transaction.py`;
   - `docs/basic/transactions.rst`;
   - `tests/test_connection_async.py`;
   - `tests/test_pipeline.py`.
4. Check PyPI for a release after 3.3.6, and read its changelog for a related fix.
5. After posting, record the comment in `docs/upstream-submissions.md`, and in the tracker. Check that file for another session's uncommitted edits first.

**Checks done 2026-10-24, between about 16:15 and 16:25 UTC.** All read-only, with `gh` and a shallow clone of `master`.

- **#1453:** open. 0 comments, no labels, no assignee, no timeline events, no reactions. Last updated when it was created (2026-10-22T00:52:41Z).
- **`master`:** head `99356800e` (2026-10-12), the same as in the roadmap. No commit since 2026-10-01 touches `transaction.py`, `_connection_base.py` or `transactions.rst`.
- **PyPI:** the latest release is 3.3.6 (2026-09-18).

**Evidence.**

- **The program and its output** are [`../../python-ecosystem-contribution-audit/psycopg_transaction_block.py`](../../python-ecosystem-contribution-audit/psycopg_transaction_block.py) and [`.txt`](../../python-ecosystem-contribution-audit/psycopg_transaction_block.txt).
  - SHA-256 `951bcb4917cd777486591391f7be3f075d913f0070946d83c1e11de5cb39148b` and `079ce18aacc8e1a07a6b26c708b66dbeb21532a80a88895442c270299579c296`, re-verified on 2026-10-24.
  - Both are pasted below unchanged. The program's docstring still says "Diagnostic, not a PPCS case" and names the throwaway port. It is left as it ran, so the pasted program is the one that produced the output.
- **The run:** 2026-10-24T14:10:49Z. PostgreSQL 18.6 (PPCS's pinned digest), psycopg 3.3.6 (binary, libpq 18.6; `psycopg.pq.version()` prints `180006`), Python 3.13.11. Three repetitions, plus a normal-block control and a savepoint control. See [`../../python-ecosystem-contribution-audit/README.md`](../../python-ecosystem-contribution-audit/README.md).
- **The pipeline test's pattern:** [`../psycopg-pipeline-test-check/`](../psycopg-pipeline-test-check/README.md).
  - It is the basis for "When I ran the same steps outside pytest …".
  - Its arms are the test's body, and the body plus a marker, three repetitions each.
  - The driver was `INERROR` at block exit, the block did not raise, `status` was `committed`, and the transaction was `aborted`.

**Source facts behind the comment's third and fourth paragraphs.** All read at `99356800e`; the code is identical to 3.3.6.

- **`BaseTransaction._commit_gen`** (`transaction.py`, 133–140).
  - Line 135 sets `status = COMMITTED`.
  - Line 140 then sends the commands from `_get_commit_commands()` through `self._conn._exec_command`. For the outer transaction that is `b"COMMIT"` (180–190). The result is not kept.
  - `AsyncTransaction` inherits this method.
- **`BaseConnection._commit_gen`** (`_connection_base.py`, 577–595).
  - It raises `ProgrammingError` while `_num_transactions` is non-zero (579–584). That stops a user's `commit()` inside a block.
  - It is not why the block bypasses it. `_pop_savepoint()` (line 134) has already brought the counter to 0 when the block's `COMMIT` is sent; line 189 asserts that. The block simply does not call it.
  - Line 592 sends `COMMIT` through `_exec_command`. The result is not kept.
  - Both paths reach `_exec_command`. A check placed there, or in a helper both call, would cover both. That is a design observation, not part of the comment.
- **`_exec_command`** (443–493) raises only for a status other than `COMMAND_OK` or `TUPLES_OK`. In pipeline mode it queues the command and returns `None` (459–468).
- **`test_auto_transaction_fail`.** `tests/test_connection_async.py`, 401–421, with `await aconn.commit()` at 418. The sync copy is `tests/test_connection.py`, 405–425, with `conn.commit()` at 422.
- **A test exits a `transaction()` block normally after a caught database error.**
  - **Where:** `test_outer_transaction_error`, in `tests/test_pipeline.py` (506–511) and `tests/test_pipeline_async.py` (507–512).
  - **How it catches.** It uses `pytest.raises` around a pipeline inside `conn.transaction()`. The first scan looked only for try/except, found just two `ZeroDivisionError` handlers, and missed it.
  - **Not a conflict:** `test_errors_raised_on_nested_transaction_exit` (`test_pipeline.py`, 260–273) catches outside an inner savepoint block. Its outer transaction is not aborted.
- **Docs,** `docs/basic/transactions.rst`:
  - the block contract, 158–162;
  - `status`, 347–350;
  - an example asserting `COMMITTED` after a successful block, 322–325.

**Deliberately left out:**

- **CHK-1 was not run.** It is optional, and the task said not to delay the comment for it. So the comment says nothing about a `COMMIT` that itself raises (the roadmap's H-a), except to list it as not run.
- **The `57014`, `40P01` and `40001` results (PY-12).** They were observed through SQLAlchemy Core, which calls `Connection.commit()`, not `transaction()`. On 2026-10-24 the maintainer decided to keep them out, so that the comment stays narrow.
- **A fix design.** The roadmap's narrowest fix (§7) stays internal until the maintainer answers.
- **SQLAlchemy and Django.** The issue body already covers them as callers.

**Length.** Outside `<details>`: 13 paragraphs and bullets, 375 words. That is about 32 lines at 100 characters per line, within the roadmap's 30–40.

---

A second public API has the same problem, and the report above does not cover it: `Connection.transaction()`.

I caught a `UniqueViolation` inside `with conn.transaction() as tx:` and let the block end normally. psycopg 3.3.6, PostgreSQL 18.6, three repetitions, all the same:

- the block exited without raising, and `tx.status` was `committed`;
- from a separate connection, `pg_xact_status()` of the transaction's ID was `aborted`, the row inserted before the error was gone, and the session was `idle` with last statement `COMMIT`;
- the control, where the failing insert runs inside an inner `conn.transaction()` (a savepoint) and the error is caught just outside it, committed, and its row was visible.

The documentation says:

- "when leaving the context the transaction is committed, or it is rolled back if an exception is raised inside the block" ([transactions.rst](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/docs/basic/transactions.rst?plain=1#L158-L162))
- "allowing you to check the final outcome of the transaction even after the `with` block has exited. This is particularly useful when you need to log transaction outcomes or implement retry logic based on the transaction status" ([transactions.rst](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/docs/basic/transactions.rst?plain=1#L347-L350))

I would expect the block to raise here, or at least `tx.status` not to be `committed`.

A fix in `Connection.commit()` alone would not reach this path. `BaseTransaction._commit_gen` ([transaction.py#L133-L140](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/psycopg/psycopg/transaction.py#L133-L140)) does not call `Connection._commit_gen`. It sends `COMMIT` through `_exec_command` itself and does not keep the result. It also sets `status = COMMITTED` before sending the command.

A qualification to my report above: `test_auto_transaction_fail` ([test_connection_async.py#L401-L421](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/tests/test_connection_async.py#L401-L421), and its sync copy) calls `commit()` after a failed statement and expects it to return, leaving the connection `IDLE` and the row gone. Making `commit()` raise, as I asked, would fail that test, so the current behaviour may be intended. The block has a similar test: `test_outer_transaction_error` ([test_pipeline.py#L506-L511](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/tests/test_pipeline.py#L506-L511), and its async copy) catches a database error inside `transaction()` and expects the block to exit normally. When I ran the same steps outside pytest, the transaction was aborted and `tx.status` was `committed`, as above. Correcting `status` alone would not conflict with either test.

Not run: `AsyncConnection.transaction()` (it shares `BaseTransaction._commit_gen`), a `COMMIT` sent while a pipeline is still open, and a `COMMIT` that itself raises.

If it helps, I'm happy to write tests for the `transaction()` path, or a PR, once you have decided what the block should do in this case.

<details>
<summary>Program and complete output</summary>

Run it against a disposable server: it first drops any database named `audit_psycopg_tx`, then creates it, and drops it at the end.

```python
"""psycopg Connection.transaction() after a caught 23505. Diagnostic, not a PPCS case.

    DATABASE_URL=postgresql://postgres:...@127.0.0.1:55479/postgres python psycopg_transaction_block.py

Creates database audit_psycopg_tx, drops it at the end. Prints what the transaction
block reported (exception, Transaction.status, driver status) and what PostgreSQL did
(pg_xact_status of the xid captured inside the block, marker visibility, and the
backend's state and last statement), read from a separate connection.
"""

import os
import sys

import psycopg
from psycopg import errors
from psycopg.pq import TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "audit_psycopg_tx"
REPS = 3


def connect(dbname, autocommit=True):
    return psycopg.connect(URL, dbname=dbname, autocommit=autocommit)


def tstatus(conn):
    return TransactionStatus(conn.info.transaction_status).name


def observe(xid, pid, marker):
    with connect(NAME) as probe:
        fate = probe.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0]
        seen = probe.execute("select count(*) from item where name = %s", (marker,)).fetchone()[0]
        row = probe.execute(
            "select state, query from pg_stat_activity where pid = %s", (pid,)
        ).fetchone()
    return fate, seen, row


def subject(marker, recover_with_savepoint):
    conn = connect(NAME)
    pid = conn.info.backend_pid
    raised = None
    caught = None
    status_before_exit = None
    try:
        with conn.transaction() as tx:
            conn.execute("insert into item (name) values (%s)", (marker,))
            xid = conn.execute("select pg_current_xact_id()::text").fetchone()[0]
            if recover_with_savepoint:
                try:
                    with conn.transaction():
                        conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            else:
                try:
                    conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            status_before_exit = tstatus(conn)
    except Exception as exc:  # what the block raised on exit, if anything
        raised = f"{type(exc).__name__}: {exc}"
    status_after_exit = tstatus(conn)
    fate, seen, row = observe(xid, pid, marker)
    conn.close()
    return {
        "caught": caught,
        "driver status before block exit": status_before_exit,
        "block raised on exit": raised,
        "Transaction.status": tx.status.value,
        "driver status after block exit": status_after_exit,
        "pg_xact_status": fate,
        "marker visible": bool(seen),
        "backend state, last statement": row,
    }


def main():
    admin = connect("postgres")
    print(f"python {sys.version.split()[0]}")
    print(f"psycopg {psycopg.__version__}, impl {psycopg.pq.__impl__}, libpq {psycopg.pq.version()}")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    admin.close()
    with connect(NAME) as setup:
        setup.execute("create table item (id serial primary key, name text not null)")
        setup.execute("create table uniq (id serial primary key, code text not null unique)")
        setup.execute("insert into uniq (code) values ('taken')")

    # Control: a normal transaction block.
    conn = connect(NAME)
    with conn.transaction() as tx:
        conn.execute("insert into item (name) values ('control')")
    print("control: normal block")
    print(f"  Transaction.status {tx.status.value}")
    conn.close()
    with connect(NAME) as probe:
        n = probe.execute("select count(*) from item where name = 'control'").fetchone()[0]
    print(f"  marker visible {bool(n)}")

    for rep in range(1, REPS + 1):
        print(f"repetition {rep}: caught 23505 inside conn.transaction(), block exits normally")
        for key, value in subject(f"caught-{rep}", recover_with_savepoint=False).items():
            print(f"  {key}: {value}")
        print(f"repetition {rep}: savepoint recovery, inner conn.transaction() catches 23505")
        for key, value in subject(f"recovered-{rep}", recover_with_savepoint=True).items():
            print(f"  {key}: {value}")

    admin = connect("postgres")
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
```

Output, complete:

```
python 3.13.11
psycopg 3.3.6, impl binary, libpq 180006
server_version 18.6 (Debian 18.6-1.pgdg13+2)
control: normal block
  Transaction.status committed
  marker visible True
repetition 1: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 1: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
repetition 2: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 2: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
repetition 3: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 3: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
```

</details>

---
