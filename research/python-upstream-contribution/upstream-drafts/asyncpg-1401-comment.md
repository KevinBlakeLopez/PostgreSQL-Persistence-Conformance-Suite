# Draft: comment on MagicStack/asyncpg#1401

**Not posted.** Prepared 2026-10-27. Written by: Cursor Grok 4.7.

This is a comment on the outside pull request that says it fixes #1400. It is not a new issue. Do not post it without approval of the exact text (`AGENTS.md` rule 9).

**Proposed destination:** https://github.com/MagicStack/asyncpg/pull/1401

Everything between the two rules below is the proposed comment. The rest of this file is internal.

**Before posting:**

1. Get approval of the exact text and destination.
2. Re-read #1401. If the head is no longer `9a33f253f49a3fb0229f2027210379aa726b0b41`, or the tests have been updated, do not post this text.
3. If a maintainer has already said which behaviour they want, adapt the question or drop the comment.

**Run, 2026-10-27.** Two throwaway containers, one after the other, both `postgres:18.6` digest `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, each removed afterwards. Not `ppcs-postgres`. Python 3.13.11.

- **The pull request.** `asyncpg` 0.33.0.dev0 from `soujasK/asyncpg` `9a33f253`, installed from that git commit. Head confirmed `9a33f253f49a3fb0229f2027210379aa726b0b41`.
- **#1400's program,** once, asyncio: [`../chk-2-asyncpg/asyncpg_commit_rollback.py`](../chk-2-asyncpg/asyncpg_commit_rollback.py). Output [`../py-2-asyncpg-1401-check/output/pr.chk2.asyncio.out`](../py-2-asyncpg-1401-check/output/pr.chk2.asyncio.out). Exit 0. The program prints what happened; it does not assert.
  - `async with`: the block raised `InFailedSQLTransactionError: the transaction was rolled back by the server instead of being committed`. `pg_xact_status` aborted, marker absent, last statement `COMMIT`.
  - explicit `commit()`: the same raise. A following `rollback()` raised `InterfaceError: cannot rollback; the transaction is already rolled back`.
  - `execute('COMMIT')`: still returned `'ROLLBACK'`.
  - savepoint control: the block exited normally, the transaction committed, and the marker was visible.
- **`test_timeout_04` and `test_timeout_06` on that install.** Output [`../py-2-asyncpg-1401-check/output/pr.timeout.out`](../py-2-asyncpg-1401-check/output/pr.timeout.out). Exit 1.
  - `test_timeout_04` failed at `tests/test_timeout.py:61`, leaving the block after a caught `TimeoutError`. `__aexit__` called `__commit`, which raised `InFailedSQLTransactionError`.
  - `test_timeout_06` failed the same way at line 78, its first block. Later arms were not reached.
- **The same two tests on asyncpg 0.32.0,** the installed wheel, using the `v0.32.0` tests. Output [`../py-2-asyncpg-1401-check/output/v032.timeout.out`](../py-2-asyncpg-1401-check/output/v032.timeout.out). Exit 0. Both ok.
- **The pull request's new test,** `test_transaction_commit_rolled_back_by_server`. Output [`../py-2-asyncpg-1401-check/output/pr.newtest.out`](../py-2-asyncpg-1401-check/output/pr.newtest.out). Exit 0.
- **Not run:** the rest of asyncpg's suite, uvloop, and any check that the new `25P02` is the right exception class for callers that already handle that SQLSTATE.

The first attempt to run the timeout tests imported the unbuilt checkout and failed before connecting. Those outputs were replaced by the run above. The #1400 program was not part of that failed attempt.

---

The raise does what #1400 asked for on `Transaction.commit()` and on `async with con.transaction()`. I ran `9a33f253` against the caught `23505` case from that issue: both of those paths now raise `InFailedSQLTransactionError`, the transaction is aborted, and the earlier row is absent. `connection.execute('COMMIT')` still returns `'ROLLBACK'`. A nested `transaction()` around the error still commits the outer block.

`test_timeout_04` and `test_timeout_06` fail on this branch. They catch `TimeoutError` inside the block, so the block commits on the way out, and that commit now raises. On 0.32.0, on the same PostgreSQL 18.6, both tests pass. The new `test_transaction_commit_rolled_back_by_server` passes.

#1400 asked whether a `ROLLBACK` command status should raise, or whether the block should still exit normally and stop recording the transaction as committed. These two tests are the suite's current answer: they expect the normal exit. Do you want them updated to expect the raise?

---
