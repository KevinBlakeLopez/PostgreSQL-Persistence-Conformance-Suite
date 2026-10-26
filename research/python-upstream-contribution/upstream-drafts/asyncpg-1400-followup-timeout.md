# Draft: asyncpg, follow-up on MagicStack/asyncpg#1400 (client-side timeouts)

**Not posted.** Prepared 2026-10-26. Written by: Claude Opus 5.5 (max).

**RETIRED 2026-10-26, at the maintainer's decision. Do not send.**
- **Why:** its trigger, a timeout caught inside an all-or-nothing transaction followed by a commit, is not reasonable application code. A maintainer could fairly dismiss it as misuse.
- **What it leaves:** the evidence still stands as a mechanism check, in CHK-11 and [CHK-15](../chk-15-asyncpg-timeout-order/README.md).
- **Around 2026-11-07,** if #1400 is still silent, the choice is between a plain nudge with no new content and nothing at all. #1400 already shows the caught `23505`.
- **The text below** is kept as it was drafted.

This is the planned follow-up for tracker item PY-2 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). `KevinBlakeLopez` filed #1400 on 2026-10-24, from [its draft](asyncpg-commit-rollback.md). The follow-up reports CHK-11's result: a caught client-side timeout gives the same false commit as the caught `23505` in the issue.

Everything between the two rules below is the proposed comment. The rest of this file is internal.

**When.** The tracker sets one polite follow-up around 2026-11-07, two weeks after filing, and only if #1400 is still silent. This replaces a plain reminder.

**Before posting:**

1. Get approval of the exact text and of the destination (`AGENTS.md` rule 9).
2. Re-check #1400. If a maintainer has replied, adapt this or drop it. If the issue was closed as intended behaviour, record that, and do not argue.
3. Re-check that asyncpg 0.32.0 is still the latest release. If it isn't, re-run CHK-11 on the new one first.
4. Check that the evidence link resolves on `main`.
5. Run the content guard on the final text.

**Checks done 2026-10-26 (UTC).**

- **#1400:** open, no comments, no labels, no timeline events.
- **asyncpg's tracker,** searched for `timeout transaction commit rollback`, `InFailedSQLTransactionError timeout` and `wait_for transaction aborted commit`. No report of this. The only match on the second query is #1400 itself. The first query's other results are unrelated: #1399, #442, #1126, #1074, #295, #289 and #272.
- **asyncpg** has no `CONTRIBUTING`, code-of-conduct or AI-policy file, at the root or in `.github/`.

**Evidence.** [CHK-11](../chk-11-asyncpg-client-timeout/README.md), all eight arms. The comment links that folder, and embeds no program.

**Deliberately left out:**

- **CHK-10** (SQLAlchemy's asyncio engine). #1400 already lists the downstream callers, with SQLAlchemy's asyncpg dialect among them.
- **The 2020 pgjdbc history** (#1697, PR 1729 and its revert), and pgx's `ErrTxCommitRollback`. They are context for the maintainers' choice, not new asyncpg facts.
- **Pools and `asyncio.timeout()`.** CHK-11 did not run them.

**Length.** 8 lines, 136 words, link included.

---

One more trigger, in case it bears on the decision: a client-side timeout caught inside the block.

asyncpg 0.32.0, PostgreSQL 18.6, asyncio and uvloop 0.23.0, three runs each, all the same. Inside `async with con.transaction()`, after an insert, the code caught the `TimeoutError` from each of these:

- `fetch("select pg_sleep(10)", timeout=0.2)`;
- the same `fetch()` on a connection with `command_timeout=0.2`;
- `asyncio.wait_for(con.fetch(...), 0.2)`.

In all three, the server cancelled the statement ("canceling statement due to user request"), and the block exited normally. A later `tr.rollback()` raised "the transaction is already committed". From a separate connection, `pg_xact_status()` was `aborted`, and the inserted row was gone.

With `tr.start()` … `tr.commit()`, `commit()` returned `None`. A raw `execute('COMMIT')` returned `'ROLLBACK'`. With the timed-out query inside a nested `con.transaction()`, the outer block committed the row.

Program, outputs and server log: https://github.com/KevinBlakeLopez/PostgreSQL-Persistence-Conformance-Suite/tree/main/research/python-upstream-contribution/chk-11-asyncpg-client-timeout

---
