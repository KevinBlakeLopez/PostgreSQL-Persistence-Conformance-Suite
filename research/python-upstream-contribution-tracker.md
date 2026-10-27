# Python upstream contribution tracker

Started: 2026-10-24. Updated the same day, after CHK-2 and the PY-1b and PY-2 drafts. Written by: Claude Opus 5.5 (max).

This is the working tracker for [`python-upstream-contribution-roadmap.md`](python-upstream-contribution-roadmap.md). The roadmap holds the reasoning, the fixes, and the test designs. This file holds only the status and the next step for each item.

- **Nothing here is filed unless its row links a filing.** Filed so far:
  - PY-1a: [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), 2026-10-21;
  - PY-1b: [a comment on #1453](https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348), 2026-10-24;
  - PY-2: [asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400), 2026-10-24;
  - PY-3: [tortoise/tortoise-orm#2383](https://github.com/tortoise/tortoise-orm/issues/2383), 2026-10-25;
  - PY-6: [asyncpg#1402](https://github.com/MagicStack/asyncpg/issues/1402), 2026-10-27.
- **The filing log is still [`docs/upstream-submissions.md`](../docs/upstream-submissions.md).** PY-1a is its P1. When an item is posted, record it there, and update the row here.
- **Every post needs approval** of its exact text and destination (`AGENTS.md` rule 9).
- **SQLAlchemy text must be written by its author,** in their own words. No agent posts there.

## Status key

| Status | Meaning |
| --- | --- |
| SUBMITTED | Posted or filed; the row links it. Waiting on maintainers, under the follow-up rule in roadmap §14 |
| AWAITING_APPROVAL | The exact text is drafted, checked, and stored in [`python-upstream-contribution/upstream-drafts/`](python-upstream-contribution/upstream-drafts/). Nothing is posted. The next step is approval of the exact text and destination |
| READY_FOR_HUMAN_REVIEW | The evidence is complete. The next step is drafting the exact text, or the author writing it, for approval |
| NEEDS_VERIFICATION | One named check (CHK-n) comes before drafting |
| UPSTREAM_ALREADY_TRACKED | An upstream issue already exists. Wait, or add to it |
| DOCUMENTATION_ONLY | The right contribution is a documentation change. Optional and not scheduled |
| DEFERRED | Depends on another item's outcome |
| CLOSED_NO_ACTION | No upstream contribution is warranted |

## Summary

Order is the roadmap's execution order (§6.3). A and B are the severity and feasibility ranks.

| ID | Project | Finding | Confidence | Order (A, B) | Status | Next concrete step |
| --- | --- | --- | --- | --- | --- | --- |
| PY-1a | psycopg | `Connection.commit()` returns when `COMMIT` is answered `ROLLBACK` | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | — (A1) | UPSTREAM_ALREADY_TRACKED | Wait on #1453. PY-1b adds to it |
| PY-1b | psycopg | `transaction()` exits normally, and `Transaction.status` is `committed`, after an abort | CONFIRMED | 1 (A1, B1) | SUBMITTED | Posted 2026-10-24 ([comment](https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348)). One follow-up around 2026-11-07 if silent; decide around 2026-11-21 |
| PY-2 | asyncpg | `Transaction.commit()` and `async with` report success after `COMMIT` is answered `ROLLBACK` | CONFIRMED; CHK-2 reproduced it on asyncio and uvloop | 2 (A2, B5) | SUBMITTED | Filed 2026-10-24 as [#1400](https://github.com/MagicStack/asyncpg/issues/1400). `Claire-ovo` reproduced it on 2026-10-27. Outside PR [#1401](https://github.com/MagicStack/asyncpg/pull/1401) is open and unreviewed. The 2026-11-07 silence follow-up no longer applies; decide around 2026-11-21 |
| PY-3 | Tortoise ORM | A retried `save()` after a rollback writes nothing and returns normally | CONFIRMED; CHK-5 reproduced it on the asyncpg and psycopg backends, the savepoint variant included | 3 (A3, B4) | SUBMITTED | Filed 2026-10-25 as [#2383](https://github.com/tortoise/tortoise-orm/issues/2383). One follow-up around 2026-11-08 if silent; decide around 2026-11-22 |
| PY-5 | SQLAlchemy (docs) | On a transactional psycopg 3 engine, the documented PostgreSQL reset recipe leaves the role, a custom GUC, `search_path`, `statement_timeout` and temp tables in place. On psycopg2, the driver in its URL, it raised on each tested return, and the pool discarded the connection | CONFIRMED on both drivers; CHK-3 | 4 (A5, B3) | READY_FOR_HUMAN_REVIEW | The author writes the discussion or docs PR from CHK-3's [`FACTS.md`](python-upstream-contribution/chk-3-sa-reset-recipe/FACTS.md) |
| PY-6 | asyncpg | `SET ROLE` survives `Connection.reset()` | CONFIRMED | 5 (A4, B7) | SUBMITTED | Filed 2026-10-27 as [#1402](https://github.com/MagicStack/asyncpg/issues/1402). One follow-up around 2026-11-10 if silent; decide around 2026-11-24 |
| PY-8 | Tortoise ORM | COMMIT-time integrity errors are not translated | CONFIRMED on asyncpg, psycopg and SQLite; the fix runs on a local branch | 6 (A8, B2) | READY_FOR_HUMAN_REVIEW | Draft the PR text and commit message for approval; the user forks, pushes and opens the PR |
| PY-7 | SQLAlchemy | P5a: after a failed `commit()`, `close()` returns the connection with its transaction open | CONFIRMED; CHK-7 reproduced it on 2.1.6; a second consequence on SQLite (2026-10-25, see PY-7) | 7 (A6, B6) | READY_FOR_HUMAN_REVIEW | CHK-7 is done. The author writes and posts, using CHK-7's `FACTS.md` (see PY-7) |
| PY-4 | SQLAlchemy | `after_rollback` fires after a root `COMMIT` that raised, also when PostgreSQL committed: a cancelled `COMMIT` (P3, P8) or a lost reply (CHK-4) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN; CHK-4 reproduced it with no cancellation | 8 (A7, B8) | READY_FOR_HUMAN_REVIEW | After P5a's reception, the author writes the discussion from CHK-4's [`FACTS.md`](python-upstream-contribution/chk-4-sa-lost-commit-reply/FACTS.md) |
| PY-9 | SQLAlchemy | ORM `after_commit` fires on an aborted transaction (Draft C) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN; CHK-9 and CHK-10 observed it on 2.1.6 with psycopg2, psycopg 3 and asyncpg | — | DEFERRED | Revisit after PY-1 and PY-2 |
| PY-10 | Django | `atomic()` and `on_commit` | NOT A DEFECT for ORM errors. CHK-12: after a caught raw-SQL error, PY-1a's false commit reaches `on_commit`, a case Django documents as unspecified | — | CLOSED_NO_ACTION | — |
| PY-11 | psycopg_pool, SQLAlchemy pools, Django | Session state carries over by default | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-12 | Several | `57014`, `40P01`, `40001` on the caught-then-commit path | CONFIRMED; no new defect | — | CLOSED_NO_ACTION | Not cited in either draft. Kept out of PY-1b by the maintainer's decision; dropped from PY-2 after the outside review |
| PY-13 | psycopg | `AsyncConnectionPool`: a level-cancelled `COMMIT` completes after the API returned | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-14 | Django | A documentation note that the native pool does not reset session state | Optional | — | DOCUMENTATION_ONLY | Not scheduled. Check Django's contribution policy first |
| PY-15 | SQLAlchemy | Draft A (SA-03): a failed `rollback()`, then reuse | Ext | — | DEFERRED | After P5a's reception |
| PY-16 | SQLAlchemy | Draft B (SA-02): a failed savepoint rollback is caught, then committed | Ext; no trigger | — | CLOSED_NO_ACTION | — |
| PY-17 | Django | Migration locking (MG-02) | PPCS | — | DOCUMENTATION_ONLY | Optional forum note. Not scheduled |
| PY-18 | Django | TX-02 not-sent | PPCS; no trigger | — | CLOSED_NO_ACTION | Keep in PPCS |
| PY-19 | Tortoise ORM | Rollback skipped after a class-25 error in a nested block | Src only | — | DEFERRED | Mention only if the PY-8 discussion invites it |
| PY-20 | Tortoise ORM | SQLite: after a COMMIT fails, the shared connection stays in the transaction, and later writes return normally and are lost | CONFIRMED with a deferred foreign key | — | NEEDS_VERIFICATION | Run CHK-8 |
| PY-21 | SQLAlchemy | When SQLite ends the transaction by itself (a full disk, `ON CONFLICT ROLLBACK`, `RAISE(ROLLBACK)`), SQLAlchemy keeps its transaction active and reports the commit. With the ORM guide's SAVEPOINT loop and the SQLite dialect's `BEGIN` recipe, every record before the failure is lost while `session.commit()` returns | CONFIRMED on 2.1.6 and 2.0.55; on 2.1.6 also with a real disk full | — | READY_FOR_HUMAN_REVIEW | The author writes a discussion from the study's [`sqlalchemy-facts.md`](sqlite-transaction-state-divergence/upstream/sqlalchemy-facts.md), item SA-1 |
| PY-22 | SQLAlchemy | `Session.close()` keeps the pooled connection checked out when the rollback inside it raises an error that is not a disconnect, as on SQLite with `autocommit=False`. #13657 fixed the same in Core's `Connection.close()` only | CONFIRMED on 2.1.6 and 2.0.55 | — | READY_FOR_HUMAN_REVIEW | The author writes it from `sqlalchemy-facts.md`, item SA-2 |
| PY-23 | CPython `sqlite3` | With `autocommit=False`, after SQLite ends a transaction by itself, `commit()` and `rollback()` raise instead of doing nothing, no transaction is opened again, and later writes commit by themselves | CONFIRMED on 3.13.11, 3.13.17 and 3.14.2 | — | AWAITING_APPROVAL | Approval of the exact text of [the draft](sqlite-transaction-state-divergence/upstream/cpython-sqlite3-autocommit-false-draft.md), stored with its study |
| PY-24 | sqlalchemy-file | After a `COMMIT` that raised, also when PostgreSQL committed (a lost reply), its `after_soft_rollback` listener deletes the files uploaded in the unit of work, so a committed row references a deleted file. Also: a failed `commit()` without `rollback()` never cleans up, and `after_commit` at a savepoint `RELEASE` clears its tracking, so a later rejection orphans the file | CONFIRMED on 0.7.0 with SQLAlchemy 2.1.6 (CHK-14) | — | READY_FOR_HUMAN_REVIEW | A duplicate search in jowilf/sqlalchemy-file, then a draft issue for approval |
| PY-25 | Procrastinate (docs) | The queueing-lock page says `AlreadyEnqueued` can be ignored. Inside the caller's transaction (the Django integration by default, or `configure(connection=...)`), ignoring it loses the transaction: Django runs `on_commit`, `commit()` returns, and the order is gone. Only the external-connection page has the savepoint caveat | CONFIRMED; CHK-16 | — | AWAITING_APPROVAL | Approval of the exact text of [the draft](python-upstream-contribution/upstream-drafts/procrastinate-queueing-lock-transaction.md) |

## Scheduled items

### PY-1a: psycopg `Connection.commit()`

- **Project:** psycopg 3.3.6. `master` `99356800e` is unchanged.
- **Finding:** `commit()` returns `None` when PostgreSQL completes `COMMIT` with tag `ROLLBACK`.
- **Evidence:**
  - `research/production-reachability/reproductions/psycopg_commit_tag.{py,txt}`;
  - `reports/examples/2026-10-19T12-35-51Z-64c5c5`;
  - `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` and `…20-58-26Z-508b7a`;
  - A2 P6.
  - **CHK-9 (2026-10-26 UTC): psycopg2 does the same.** On psycopg2 2.9.13, `commit()` and `with conn:` return normally after `COMMIT` is answered `ROLLBACK`, directly and through SQLAlchemy 2.1.6 Core and ORM, 3 of 3: [`python-upstream-contribution/chk-9-psycopg2-false-commit/`](python-upstream-contribution/chk-9-psycopg2-false-commit/README.md).
  - **CHK-12 (2026-10-26 UTC): through Django.** Django 6.1.2's `atomic()` ends in this call. Consider a raw-SQL error (`connection.cursor()`) caught inside `atomic()`, or inside a request under `ATOMIC_REQUESTS`. Django then sends `COMMIT`, psycopg 3.3.6's `commit()` returns, Django runs the `on_commit` callback, and the view returns 200, 3 of 3: [`python-upstream-contribution/chk-12-django-raw-sql-false-commit/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/README.md).
    - An ORM error makes Django roll back by itself (PY-10).
    - With `atomic()` nested inside `ATOMIC_REQUESTS`, the raw-SQL error fails loudly with a 500.
    - **Re-run with a reasonable trigger (2026-10-26):** the same results with a once-only first-order bonus as the order's last step, the duplicate treated as "already awarded", 3 of 3: [`python-upstream-contribution/chk-12-django-raw-sql-false-commit/once-only-rerun/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/once-only-rerun/README.md). The original trigger, a best-effort analytics write inside the transaction, is not reasonable application code.
  - **CHK-16 (2026-10-26 UTC): through a library.** Procrastinate 3.10.0 inserts a job inside the caller's transaction, by default with its Django integration. If the code ignores the documented `AlreadyEnqueued` from a queueing-lock clash, Django runs `on_commit`, or `conn.commit()` returns on the external-connection API, and the transaction is lost, 3 of 3: [`python-upstream-contribution/chk-16-procrastinate-queueing-lock/`](python-upstream-contribution/chk-16-procrastinate-queueing-lock/README.md). Procrastinate's docs side is PY-25.
- **Upstream:** [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21. Open, no comments, no labels. Re-checked 2026-10-24 at about 16:20 UTC: also no timeline events and no reactions.
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
  - psycopg's docs tell callers to roll back after an error.
  - `tests/test_connection_async.py:401` asserts that `commit()` returns.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-1-and-py-2-and-py-9-the-false-commit)):
  - **Consequence:** the writes before a caught error are lost while `commit()` returns. Through Django (CHK-12), `on_commit` also runs. Silent unless a later statement fails.
  - **Trigger, a caught ordinary error** (`23505`, `57014`, `40P01`, `40001`): in production, yes; in our runs, real errors (the production-reachability runs, P6, CHK-9, CHK-12, CHK-16). Code shape: a per-row catch inside one transaction, common batch code that needs a savepoint on PostgreSQL; or a once-only last write with the duplicate treated as done, which is reasonable (CHK-12's re-run). Evidence: audit, news-scraping#36 (the owner's report, 0 stars); acknowledged, airflow#59120; other ecosystems.
  - **Reproduced on real code:** a real library, Procrastinate 3.10.0, used as its docs allow, in a constructed application (CHK-16). No real application ran.
  - **Searches:** the pattern counts have no inspected sample. CHK-16's sample of Procrastinate users found no unguarded catch in 104 sites, and at least six projects that guard with a savepoint.
  - **Likelihood (judgment):** moderate: the batch shape is common, and any caught error triggers it.
  - **Not established:** frequency; a production report on psycopg 3.
- **Priority:** severity rank 1. The action now is PY-1b.
- **Proposed action:** none beyond PY-1b. No new issue, and no reports to SQLAlchemy or Django.
- **Prerequisites:** —
- **Status:** UPSTREAM_ALREADY_TRACKED
- **Next concrete step:** PY-1b's drafted comment carries the compatibility note. Once it is posted, follow the follow-up rule (roadmap §14).

### PY-1b: psycopg `Connection.transaction()` and `Transaction.status`

- **Project:** psycopg 3.3.6, still the latest release. `master` `99356800e` is unchanged (re-checked 2026-10-24, about 16:20 UTC). No commit since 2026-10-01 touches `transaction.py`, `_connection_base.py` or `docs/basic/transactions.rst`.
- **Finding:** the block exits normally, and `tx.status` is `committed`, while PostgreSQL aborted. This contradicts the documented block contract and the `status` docs ("final outcome", "retry logic").
- **Evidence:**
  - `research/python-ecosystem-contribution-audit/psycopg_transaction_block.{py,txt}`: three repetitions, with a savepoint control;
  - Src: `transaction.py:133-140`;
  - Doc: `docs/basic/transactions.rst`, lines 158–162 and 347–350;
  - psycopg's own `test_outer_transaction_error` pattern, three repetitions per arm: [`python-upstream-contribution/psycopg-pipeline-test-check/`](python-upstream-contribution/psycopg-pipeline-test-check/README.md). The block exits normally, `status` is `committed`, and the transaction is aborted.
- **Upstream:** not in #1453. #967 has the maintainer's statement that a normal exit means a commit. #969 and PR #1184 added `status`.
- **Confidence:** CONFIRMED.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-1-and-py-2-and-py-9-the-false-commit)):
  - **Consequence:** the block exits normally and `tx.status` reads `committed`, the value its docs offer to retry logic, while PostgreSQL aborted. Silent.
  - **Trigger, an error caught inside `with conn.transaction()`:** in production, yes; in our runs, real errors (the audit's program, and psycopg's own `test_outer_transaction_error` pattern). Code shape: a catch inside the block, as psycopg's own test does. Evidence: none found with the shape.
  - **Reproduced on real code:** no.
  - **Searches:** of 2 inspected hits among 686 files, 0 have the shape: PostHog and Datadog catch outside the block.
  - **Likelihood (judgment):** low: no real code with the shape was found.
  - **Not established:** any real code with the shape.
- **Priority:** 1.
- **Proposed action:** a follow-up comment on #1453 (roadmap §10.1). Offer tests or a PR, conditionally.
- **Draft:** [`python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md`](python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md). Posted 2026-10-24 as https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348; the posted body matches the draft. It was revised before posting, after an outside review. About 32 visible lines, with the program and its output in `<details>`; both are byte-identical to the audit's evidence files. It covers:
  - the second surface;
  - the documented block contract and `status` ("final outcome", "retry logic");
  - why a fix in `Connection.commit()` alone does not reach the block: `BaseTransaction._commit_gen` calls `_exec_command` itself and sets `COMMITTED` before sending `COMMIT`;
  - the compatibility qualification:
    - `test_auto_transaction_fail` expects `commit()` to return;
    - `test_outer_transaction_error` expects the block to exit normally, and in its pattern `status` is also `committed`;
    - a `status`-only fix conflicts with neither test;
  - what was not run;
  - a conditional offer of tests or a PR.
- **Left out of the draft:** PY-12's SQLSTATEs. Their evidence goes through SQLAlchemy Core, that is `Connection.commit()`, not `transaction()`. The maintainer decided on 2026-10-24 to keep them out.
- **Prerequisites:** #1453 and `master` were re-checked on 2026-10-24. CHK-1 was not run; it is optional. Repeat the draft's pre-post checks on the day of posting.
- **Status:** SUBMITTED
- **Next concrete step:** wait for a reply. If #1453 is still silent around 2026-11-07, send one polite follow-up: [`python-upstream-contribution/upstream-drafts/psycopg-1453-followup-psycopg2.md`](python-upstream-contribution/upstream-drafts/psycopg-1453-followup-psycopg2.md), drafted 2026-10-26 with CHK-9's psycopg2 result and awaiting approval of its exact text. Decide around 2026-11-21 (roadmap §14).

### PY-2: asyncpg `Transaction.commit()` and `async with conn.transaction()`

- **Project:** asyncpg 0.32.0, still the latest release. `master` `13b01910d` is unchanged (re-checked 2026-10-24). Its `asyncpg/transaction.py` is byte-identical to 0.32.0's, and unchanged since 2023-05-30.
- **Finding:** both return normally, with internal state `committed`, after PostgreSQL answers `COMMIT` with `ROLLBACK`. Raw `execute('COMMIT')` returns `'ROLLBACK'`. Tortoise and SQLAlchemy's asyncpg dialect inherit this.
- **Evidence:**
  - **CHK-2,** [`python-upstream-contribution/chk-2-asyncpg/`](python-upstream-contribution/chk-2-asyncpg/README.md). This is the standalone program to post, run three times on asyncio and three on uvloop; all six agreed. `psql` and the server's statement log agree for all 24 transactions. After `commit()` has returned, asyncpg's own `rollback()` raises "the transaction is already committed", a public-API signal;
  - **CHK-10 (2026-10-26 UTC): through SQLAlchemy.** SQLAlchemy 2.1.6's asyncio engine on asyncpg 0.32.0 reports the same success: `AsyncConnection.commit()`, `engine.begin()`, `AsyncSession.commit()` and `async_sessionmaker.begin()` (with `after_commit`), 3 of 3: [`python-upstream-contribution/chk-10-sa-asyncpg-false-commit/`](python-upstream-contribution/chk-10-sa-asyncpg-false-commit/README.md). The roadmap's source-reading claim (§3.2 B) is now observed.
  - **CHK-11 (2026-10-26 UTC): a caught client-side timeout.** With asyncpg 0.32.0, a `TimeoutError` caught inside `async with con.transaction()` gives the same false commit. It held for `fetch(timeout=)`, `command_timeout` and `asyncio.wait_for()`, on asyncio and uvloop, 6 of 6 per arm: [`python-upstream-contribution/chk-11-asyncpg-client-timeout/`](python-upstream-contribution/chk-11-asyncpg-client-timeout/README.md).
    - What asyncpg reported: the block exits normally, `tr.commit()` returns `None`, and a raw `execute('COMMIT')` returns `'ROLLBACK'`.
    - What the server did: it cancelled the statement and aborted the transaction.
    - Before this, the timeout path rested on P6's server-side `statement_timeout` and on asyncpg's own `test_timeout_06` (source reading).
  - **CHK-15 (2026-10-26 UTC): which timeout fires first, and the race at the deadline.** asyncpg 0.32.0 on asyncio and uvloop, run under the working name CHK-13: [`python-upstream-contribution/chk-15-asyncpg-timeout-order/`](python-upstream-contribution/chk-15-asyncpg-timeout-order/README.md). It is a mechanism check; its trigger is not a recommended design.
    - A server `lock_timeout` or `statement_timeout` that fires before the client's deadline raises `LockNotAvailableError` or `QueryCanceledError`. Neither is a `TimeoutError`, so the block rolls back.
    - When the client fires first, the caught `TimeoutError` gives the false commit. That holds with a longer server timeout too, and with `asyncio.timeout()`, 6 of 6 per arm.
    - In 488 trials around a 0.2 s deadline, the same caught `TimeoutError` was followed by a real commit when the statement had finished before the cancel arrived (95), and by the false commit otherwise (196).
  - `research/python-production-failure-gap-analysis/output/p1.out` (arms A–D);
  - `output/p6.jsonl` and `output/p6.server-log-endings.txt`;
  - `reports/examples/2026-10-19T12-45-38Z-c45624` (Tortoise TX-01A; trace `COMMIT; -> ROLLBACK`);
  - Src: `asyncpg/transaction.py:175-192`.
- **Upstream:** none found.
  - **A fresh duplicate search on 2026-10-24:** 19 phrasings over issues and pull requests, five broader title queries, and seven queries over Discussions.
  - **Related:** #1130, and #1386 with PRs #1387 and #1399. #1399 is new, opened 2026-10-22. Both PRs change `start()`, not `__commit`.
- **Receptiveness, re-checked 2026-10-24.**
  - The maintainer reviewed #1387 on 2026-10-07.
  - In #1355 (2026-09-21) he wrote that asyncpg "did not receive enough love in 2026", citing an "overwhelmed inbox".
  - Expect a slow reply. A tested PR may move faster (roadmap §9).
- **Confidence:** CONFIRMED.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-1-and-py-2-and-py-9-the-false-commit)):
  - **Consequence:** the writes before a caught error are lost while `commit()` and `async with` report success, also through SQLAlchemy's asyncio engine (CHK-10). Silent unless a later statement fails.
  - **Trigger, a caught deadlock or unique violation:** in production, yes; in our runs, real errors (CHK-2, P6, CHK-10). Code shape: a per-item `except Exception: continue` inside one transaction, common batch code that needs a savepoint on PostgreSQL. Evidence: production, bainluck#8935 and #8129 (the owner's reports, on a one-star repository; their metrics were not checked); audit, ldvelh#24 (0 stars).
  - **Trigger, a caught client-side timeout:** in production, yes; in our runs, real timeouts (CHK-11, CHK-15). Code shape: not reasonable, so the #1400 follow-up was retired. Evidence: a pattern count only.
  - **Reproduced on real code:** no.
  - **Searches:** the pattern counts have no inspected sample.
  - **Likelihood (judgment):** moderate: the batch shape is common, and any caught error triggers it.
  - **Not established:** frequency; a report from a widely used project.
- **Priority:** 2.
- **Proposed action:** a new issue in the shape of #1453, with a conditional PR offer (roadmap §10.2).
- **Draft:** [`python-upstream-contribution/upstream-drafts/asyncpg-commit-rollback.md`](python-upstream-contribution/upstream-drafts/asyncpg-commit-rollback.md). Filed 2026-10-24 as [MagicStack/asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400); the filed title and body match the draft. It was revised before filing, after an outside review. It contains:
  - the template's fields;
  - the program and its asyncio output, both in `<details>` and byte-identical to the CHK-2 files;
  - two pasteable run commands, and a note that the program force-drops its database first;
  - the expected and actual behaviour;
  - the line where the status is dropped (`asyncpg/transaction.py` 186–192 at `13b01910d`);
  - the downstream callers, with the versions measured, and #1453;
  - the compatibility question. `test_timeout_06` (`tests/test_timeout.py`, 104–113) expects a block to exit normally after a caught error that aborted it, so the issue asks whether the maintainers want a raise or a corrected state;
  - a PR offer, conditional on that decision.

  The `57014`/`40P01`/`40001` line was dropped.
- **Prerequisites:** done on 2026-10-24: CHK-2, the duplicate search, and the template. Repeat the draft's pre-file checks on the day of filing. A new asyncpg release means re-running the program first.
- **Status:** SUBMITTED
- **Reply (2026-10-27):** [`Claire-ovo`](https://github.com/MagicStack/asyncpg/issues/1400#issuecomment-6435904826) reproduced #1400 on PostgreSQL 17.10, Python 3.12, asyncio. Outside PR [#1401](https://github.com/MagicStack/asyncpg/pull/1401) by `soujasK` changes `transaction.py` and adds tests (+51/−3). No reviews, and no checks have run. Not validated here.
- **Next concrete step:** #1400 is no longer silent, so do not send the 2026-11-07 nudge. Decide around 2026-11-21 whether to review #1401. The timeout follow-up draft stays retired.

### PY-3: Tortoise `Model.save()` after a rolled-back transaction

- **Project:** Tortoise ORM 1.1.9, still the latest release (re-checked 2026-10-25, about 01:10 UTC). `develop` is now `ad0d6ce2b` (2026-10-24, a setuptools bump), the child of the roadmap's `536fc3abd`. `Model.save()` and `BaseExecutor.execute_update()` are identical to 1.1.9. `save()` sits 4 lines lower, at 1135–1199.
- **Finding:** after the transaction or savepoint that inserted an instance rolls back, `_saved_in_db` stays True.
  - The retried `save()` sends an UPDATE for the old `pk`, which matches 0 rows. `execute_update()` returns 0, `save()` returns normally, the transaction commits, and 0 rows persist.
  - It makes no difference whether a field was changed first.
  - In the savepoint variant, the outer transaction commits without the row.
- **Evidence:**
  - **CHK-5,** [`python-upstream-contribution/chk-5-tortoise/`](python-upstream-contribution/chk-5-tortoise/README.md). It contains:
    - the program to post, three runs per backend (asyncpg and psycopg);
    - a wrapper showing the count `save()` receives;
    - Django and SQLAlchemy controls;
    - the server's statement log with `auto_explain`, and `psql`. Both agree with the witness for all 144 transactions;
  - `research/python-production-failure-gap-analysis/output/p45.rep{1,2,3}.out` (`p4_tortoise`; Django and SQLAlchemy as controls);
  - Src: `tortoise/models.py:1176-1194` (1.1.9; `develop` 1180–1198).
- **Upstream:** none found. The search ran on 2026-10-25: 28 queries through the search API, 209 items screened by title, 9 read in full.
  - #1094 shares only the symptom.
  - #1212 bears on option (b): `force_update` sees 0 rows on MySQL for a row that exists.
  - Also related, and not duplicates: #242 (2019), where a collaborator suggested that `save()` raise or warn when no rows were affected; and open PR #2293, whose per-savepoint `on_commit()` frames are the kind of bookkeeping option (a) needs.
- **Confidence:** CONFIRMED. Observed: the outcome, the statement sent, its 0 matched rows, and the count `save()` receives. Src: that nothing resets the flag on rollback.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-3-tortoise-save-after-a-rolled-back-transaction)):
  - **Consequence:** the retried `save()` writes nothing and returns normally, and the transaction commits without the row. Silent.
  - **Trigger, a retry that saves the same instance after a rollback:** in production, unknown; in our runs, an application error rolls the block back (CHK-5). Code shape: a retry loop that saves the same instance; whether that is supported is a question the filed issue asks. Evidence: none matching.
  - **Reproduced on real code:** no.
  - **Searches:** of 59 files, the five among the top ten that are outside Tortoise and PPCS were not inspected.
  - **Likelihood (judgment):** low: it needs that retry shape, and none was found.
  - **Not established:** whether any application retries with the same instance.
- **Priority:** 3.
- **Proposed action:** a new issue that asks for the fix direction, with a conditional PR offer (roadmap §7 and §10.3). The directions are (a), resetting `_saved_in_db` on rollback per transaction and savepoint level, and (b), handling zero-row updates. The issue also asks whether saving an instance again after a rollback is meant to be supported.
- **Draft:** [`python-upstream-contribution/upstream-drafts/tortoise-save-after-rollback.md`](python-upstream-contribution/upstream-drafts/tortoise-save-after-rollback.md). It uses Tortoise's bug-report template and has about 58 visible lines. The program, its output and a server-log excerpt are in `<details>`, all byte-identical to the CHK-5 files. It passed the content guard. It covers:
  - the mechanism: the stale `pk` and `_saved_in_db`, an UPDATE that matches no row, a normal return and a commit;
  - the savepoint case;
  - a table of the six arms;
  - the ignored count, `_saved_in_db`, and the `force_update` contrast, with links to `develop` `ad0d6ce2b`;
  - one sentence on Django and SQLAlchemy;
  - options (a) and (b), with the #1212 caution and the no-statement early return;
  - a conditional PR offer.
- **Left out of the draft:** PY-8, PY-19, #1094, and the transaction-ID signal. #242 is optional: the draft offers one line for the maintainer to add.
- **Prerequisites:** CHK-5, done 2026-10-25. Repeat the draft's pre-filing checks on the day of filing. A release after 1.1.9 means running the program again first.
- **Filed:** 2026-10-25, as [tortoise/tortoise-orm#2383](https://github.com/tortoise/tortoise-orm/issues/2383), posted as `KevinBlakeLopez` after approval of the exact text, which was revised after an outside adversarial review. The filed title and body match the draft. Recorded in [`docs/upstream-submissions.md`](../docs/upstream-submissions.md) (commit `38bf2a7`).
- **Status:** SUBMITTED
- **Next concrete step:** wait for the maintainers. One polite follow-up around 2026-11-08 if there is no reply; decide around 2026-11-22. A pull request is offered only if they pick a direction.

### PY-5: SQLAlchemy PostgreSQL reset-on-return recipe

- **Project:** SQLAlchemy documentation, `dialects/postgresql/base.py:275-336`. The file is byte-identical on 2.1.5, 2.1.6 and `main` `10f4d1e2d` (re-checked 2026-10-25).
- **Finding:** its URL is psycopg2's, but its calls are psycopg 3's.
  - **On psycopg 3, on a transactional (default) engine,** its statements run inside one transaction, which its own `rollback()` aborts. The role, a custom GUC, `search_path`, `statement_timeout` and temp tables all carry over.
    - Its `CLOSE ALL` still takes effect: WITH HOLD cursors are closed despite the rollback.
    - On an AUTOCOMMIT engine the recipe resets everything measured except the role.
  - **On psycopg2,** `dbapi_connection.execute()` raised `AttributeError` on each tested return. The pool logged "Exception during reset or similar" and invalidated the connection, so unit 2 got a new connection with none of the measured state.
- **Evidence:**
  - **CHK-3,** [`python-upstream-contribution/chk-3-sa-reset-recipe/`](python-upstream-contribution/chk-3-sa-reset-recipe/README.md), on SQLAlchemy 2.1.6: three runs per driver, the server's statement log, `psql`, a 64-line demo, and a supplement run after an outside review. [`FACTS.md`](python-upstream-contribution/chk-3-sa-reset-recipe/FACTS.md) there is the package for the author;
  - `research/python-production-failure-gap-analysis/p7_sa_reset_recipe.py` and `output/p7.rep{1,2,3}.out` (2.1.5);
  - the psql checks in that directory's README;
  - Src (2.1.6):
    - `pool/base.py:1465-1474`: the event is dispatched before the pool's own reset;
    - `1041-1060`: an exception from it is logged, and the record invalidated;
  - the page's own search-path note (`base.py:338-371`).
- **The corrected example (roadmap §7),** run in CHK-3:
  - it resets all five measured items on both drivers, and keeps the connection. That holds under the default `pool_reset_on_return` too, and when a connection is returned with its transaction open (supplement);
  - it keeps an AUTOCOMMIT engine in autocommit;
  - it discards a `search_path` set by the docs' connect-time recipe, while one from startup `options` survives;
  - added: REPEATABLE READ survives, and psycopg 3's prepared statements keep working.
- **Upstream:** the recorded queries found no matching report (issues, pull requests and discussions, 2026-10-25).
  - In discussion #12486 (2025-03), a maintainer pointed a user whose `SET ROLE` and `search_path` carried over to this recipe.
  - Discussion #6905 (2022-08) is a precedent: a hook's `DISCARD TEMPORARY` did not persist until the hook committed.
- **Confidence:** CONFIRMED on psycopg 3 and psycopg2. H-d held.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-5-the-documented-postgresql-reset-recipe)):
  - **Consequence:** on a transactional psycopg 3 engine, the next checkout inherits the role, a custom GUC, `search_path`, `statement_timeout` and temp tables. Silent. On psycopg2 the pool discards the connection instead.
  - **Trigger, adopting the recipe and setting session state:** in production, one adopter is known; in our runs, the ordinary API with no fault (CHK-3). Code shape: following SQLAlchemy's documentation, which is reasonable. Evidence: exposed code, csfrace-scrape (0 stars; not run, and whether it sets session state was not checked).
  - **Reproduced on real code:** no.
  - **Searches:** the counts are mostly vendored copies of SQLAlchemy and do not measure adoption.
  - **Likelihood (judgment):** low: deterministic for adopters, and one is known.
  - **Not established:** how many applications use the recipe on psycopg 3.
- **Priority:** 4.
- **Proposed action:** a corrected example: roll back, then `DISCARD ALL` in autocommit, restoring autocommit afterwards, with notes on scope (roadmap §7). The author writes the discussion or docs PR.
- **Prerequisites:** CHK-3, done 2026-10-25 (UTC). The author writes every word of the prose.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** the author reads CHK-3's `FACTS.md` and writes the discussion or docs PR in their own words. No agent drafts or posts the text.

### PY-6: asyncpg `Connection.reset()` and `SET ROLE`

- **Project:** asyncpg 0.32.0. `master` `13b01910d`.
- **Finding:** the default reset (`RESET ALL` and others) leaves `SET ROLE` in place. The next borrower runs as the previous borrower's role. The `reset()` docstring promises a state "resembling that of a newly obtained connection".
- **Evidence:**
  - `research/python-production-failure-gap-analysis/output/p2.rep{1,2,3}.out` (the asyncpg flavour);
  - the psql checks in that README;
  - Src: `asyncpg/connection.py:1567-1594` and `1763-1790`; `asyncpg/pool.py:1320-1340`;
  - the standalone script and `output/run.rep{1,2,3}.out`, run 2026-10-27: [`python-upstream-contribution/py-6-asyncpg-reset-role/`](python-upstream-contribution/py-6-asyncpg-reset-role/repro.py).
- **Upstream:** none for the role (re-checked 2026-10-27). Temp tables are #1293, and PR #1392 (open, not merged) uses a capability-gated reset statement. #270 rejects `DISCARD ALL`.
- **Confidence:** CONFIRMED.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-6-asyncpg-keeps-a-role-after-connectionreset)):
  - **Consequence:** the next borrower runs as the previous borrower's role. The saved stdout contains both checkout results; no stderr or asyncpg diagnostic-log capture is included.
  - **Trigger, a session-level `SET ROLE` on a pooled connection:** in production, yes; in our runs, the ordinary API with no fault (P2). Code shape: reasonable, since `reset()`'s docstring promises a state "resembling that of a newly obtained connection". Evidence: incident, Percolate's changelog (the project's own record; 60 stars).
  - **Reproduced on real code:** no.
  - **Searches:** hundreds of asyncpg files set or reset roles; no inspected sample.
  - **Likelihood (judgment):** moderate: deterministic once the code exists.
  - **Not established:** frequency.
- **Priority:** 5.
- **Proposed action:** an issue proposing `RESET ROLE` behind a capability, or a corrected docstring. Include the compatibility note on `init`-time roles (roadmap §10.5).
- **Draft:** [`python-upstream-contribution/upstream-drafts/asyncpg-reset-role.md`](python-upstream-contribution/upstream-drafts/asyncpg-reset-role.md). Filed 2026-10-27 as [#1402](https://github.com/MagicStack/asyncpg/issues/1402). Prepared the same day, then revised after an outside review ([`adversarial-review/py6-asyncpg-reset-role/REVIEW.md`](python-upstream-contribution/adversarial-review/py6-asyncpg-reset-role/REVIEW.md), verdict READY WITH CHANGES; the program was not rerun). The filed title and body match the draft.
- **Prerequisites:** the standalone script was run three times on 2026-10-27, as non-superuser `app_login`. CHK-6 is still optional and has not been run.
- **Filed:** 2026-10-27, as [MagicStack/asyncpg#1402](https://github.com/MagicStack/asyncpg/issues/1402), posted as `KevinBlakeLopez` after approval of the exact text. The filed title and body match the draft. Recorded in [`docs/upstream-submissions.md`](../docs/upstream-submissions.md).
- **Status:** SUBMITTED
- **Next concrete step:** wait for the maintainers. One polite follow-up around 2026-11-10 if there is no reply; decide around 2026-11-24. No pull request until they choose a direction.

### PY-8: Tortoise COMMIT-time exception translation

- **Project:** Tortoise ORM 1.1.9, the latest release when checked, and `develop` `ad0d6ce2b878` (re-checked 2026-10-25, 03:14–03:20 UTC). The transaction code is byte-identical in both.
- **Finding:** an integrity error raised by `COMMIT`, such as a deferred foreign key, reaches the application as the driver's exception, not as `tortoise.exceptions.IntegrityError`.
  - Observed on asyncpg, psycopg and SQLite, 3 of 3 each, on 1.1.9 and on `develop`.
  - `get_or_create()` and `update_or_create()` then skip their `IntegrityError` fallback.
- **Correction (2026-10-25).** This item and roadmap §3.2 H said that every backend decorates `begin()`. SQLite's `begin()` catches only `OperationalError`, inline, and ODBC's translates nothing (Src).
- **Evidence:** [`python-upstream-contribution/py-8-tortoise-commit-translation/`](python-upstream-contribution/py-8-tortoise-commit-translation/README.md), committed as `2757a35`:
  - step 1: the reproduction; check 1, a nested block's failed `RELEASE`; check 2, SQLite after a failed COMMIT; and four candidate changes, measured against them and against Tortoise's suite;
  - step 2: the branch, its tests and its suite runs;
  - [`review/`](python-upstream-contribution/py-8-tortoise-commit-translation/review/README.md): a package for an independent review, with verbatim materials, checks of `update_or_create()`, connection reuse and an explicit `commit()`, and an assessment. Its verdict was READY WITH MINOR CHANGES, and the change was applied;
  - P5's original runs: `research/python-production-failure-gap-analysis/output/p45.rep{1,2,3}.out` (`p5_tortoise`).
- **The chosen approach (the maintainer, 2026-10-25):** `commit()` translates only integrity errors, on asyncpg and psycopg.
  - Decorating `commit()` with the full translator made a failed nested `RELEASE` skip the outer rollback.
  - Translating on SQLite made `get_or_create()` return a row that was never committed (PY-20).
  - `rollback()` is left alone: no reachable case changed.
- **The branch:** `fix/commit-integrity-error` in a local clone, from `develop` `ad0d6ce2b878`, uncommitted. Its diff is the evidence's `branch/fix-v2.patch`.
  - Its two tests fail on `develop` and pass on the branch.
  - The full suites on SQLite, asyncpg and psycopg gain only those tests.
  - `ruff`, `mypy`, `bandit`, the build and `twine check` pass.
- **Upstream:** no duplicate found (34 queries, 2026-10-25). Open PR #2293 adds a line inside every `commit()`.
- **Confidence:** CONFIRMED.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#items-with-no-signal)):
  - **Consequence:** the driver's exception reaches the application instead of `IntegrityError`, so `get_or_create()` and `update_or_create()` skip their fallback. Loud.
  - **Trigger, an integrity error raised by `COMMIT`:** in production, unknown; in our runs, a deferred foreign key, a real error. Code shape: deferrable constraints with Tortoise, which is reasonable. Evidence: none found.
  - **Reproduced on real code:** no.
  - **Searches:** one project outside PPCS combines Tortoise and `DEFERRABLE`; it was not inspected.
  - **Likelihood (judgment):** low: deferrable constraints with Tortoise are rare.
  - **Not established:** any report.
- **Priority:** 6. It is independent of PY-3.
- **Proposed action:** one PR, as on the branch. Its description asks whether leaving `commit()` untranslated was deliberate, and states the compatibility change. MySQL and ODBC are neither changed nor run.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** draft the PR text and the commit message for approval. The user forks, pushes and opens the PR. After that, the changelog's `(#XXXX)` gets the PR number.

### PY-7: SQLAlchemy P5a (failed `commit()`, then `close()`)

- **Project:** SQLAlchemy Core. The runs covered 1.4.0, 1.4.54, 2.0.55 and 2.1.5 (2026-10-18), and 2.1.6 (CHK-7). `RootTransaction` on `main` `10f4d1e2d` is unchanged. 2.1.6 changed `Connection.close()` and `_finalize_fairy` (#13699), but the reproduced path behaves as before (Src, and the CHK-7 runs).
- **Finding:** `close()` sends no ROLLBACK, and `transaction_was_reset` is True while the transaction is open. The next checkout commits the doomed writes.
- **Evidence:**
  - `../python-orm-transactions/docs/sqlalchemy-p5a-close-review.md` and `check/p5a_close_v2.{py,out}` (Ext; commit `cca9b98`, on that repository's `origin/main`);
  - **CHK-7,** `../python-orm-transactions/docs/sqlalchemy-transaction-experiments/p5a-review/chk-7/` (Ext; commit `3c9758b`), whose `FACTS.md` is the package for the author.
    - On 2.1.6 with psycopg 3.3.6, the unchanged script's stdout was byte-identical to the recorded output, 3 of 3.
    - The server log and `psql` show the next checkout's `COMMIT` committing the transaction whose `commit()` raised.
    - **Supplement (2026-10-25 UTC):** the two triggers that replace no DBAPI method, a raising `commit` listener through three API paths and SQLAlchemy's `commit()` inside psycopg's `transaction()` block, reproduce on 2.1.6, 3 of 3 each (`chk-7/supplement/`, commit `70676d9` in that repository).
  - **Published copy (2026-10-26 UTC):** [`python-upstream-contribution/py-7-sa-p5a-close/`](python-upstream-contribution/py-7-sa-p5a-close/README.md), normalized from that repository's commit `90cfaf3`: the review, the scripts and outputs, the harness, and CHK-7 with its supplement. The issue draft is not included.
- **SQLite consequence (2026-10-25).** [`sqlite-transaction-state-divergence/`](sqlite-transaction-state-divergence/findings.md), finding F6; SQLAlchemy 2.1.6, SQLite 3.54.1, Python 3.13.11.
  - With `connect_args={"autocommit": False}`, after SQLite ends the transaction itself (`RAISE(ROLLBACK)` in these runs), `commit()` raises `cannot commit - no transaction is active`. The pool's reset then reports `transaction_was_reset=True` and does not run, 3 of 3. This is P5a's path.
  - The consequence differs from PostgreSQL's. SQLite has already rolled back, so the next checkout gets the same connection with no transaction open: its write committed although its `commit()` raised, and the following unit's write committed although its `rollback()` raised. A pool reset that failed then invalidated the connection.
  - Same through `conn.begin()`/`tx.commit()`, commit-as-you-go and `session.commit()`. `engine.begin()` is not affected: it rolls back, the pool's reset fails, and the connection is invalidated.
  - Runs: `sqlite-transaction-state-divergence/output/sqlite02-core/2026-10-25T17-21-27Z-ca780e/` (`autocommit-false.{explicit,commit-as-you-go}.rollback.*`) and `…/sqlite03-session/2026-10-25T17-21-29Z-85d1f6/` (`autocommit-false.execute.rollback.commit-continue`). The study's `upstream/sqlalchemy-facts.md`, item SA-3, states it for the author.
  - Evidence commit `4d54f1b`, pushed to `main` on 2026-10-25.
- **Upstream:** none found.
  - Re-checked 2026-10-25 for 2026-10-18 onward, with the review's twelve issue queries and five replacement discussion queries; no matching item was found.
  - #13699 (fixed in 2.1.6) touches `Connection.close()`, but it is a cancellation during the reset, not P5a.
  - Precedent: #13381, fixed.
- **Confidence:** CONFIRMED for a `commit()` that fails before sending, on a healthy connection. The demonstrated triggers that replace no DBAPI method are a raising commit listener, and mixing psycopg's and SQLAlchemy's transaction APIs. Reachability through ordinary driver or OS failures, and production frequency, are not established.
  - On SQLite there is a trigger that replaces no DBAPI method: SQLite ending the transaction itself, under `sqlite3`'s `autocommit=False` (see the SQLite consequence above). It was run with `RAISE(ROLLBACK)`. A real disk full ends the transaction the same way (that study's SQLITE-05c), but this path was not run end to end with one.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-7-a-commit-that-fails-before-it-is-applied-p5a)):
  - **Consequence:** `commit()` raises, and the write commits later anyway, in the next checkout's `COMMIT`. On SQLite under CHK-13's trigger, the pooled connection also keeps the lock.
  - **Trigger, on PostgreSQL, a `commit()` that fails before sending:** in production, not established; in our runs, injected, or a raising `commit` listener or mixed transaction APIs (CHK-7's supplement). Code shape: not ordinary application code. Evidence: none; neither of the 2 inspected `commit` listeners can raise.
  - **Trigger, on SQLite, `COMMIT` refused with `database is locked`:** in production, yes; in our runs, a real lock held by another process (CHK-13). Code shape: the ordinary `with Session(engine)` and `session.commit()`, closed without `rollback()`. Evidence: incident, lessons#378 (the owner's report, 0 stars). It says this happens although the caller rolls back, while CHK-13 found an explicit `rollback()` before close not affected; not reconciled.
  - **Reproduced on real code:** no.
  - **Searches:** 120 files register a `commit` listener, 2 of them inspected; no count for the SQLite shape.
  - **Likelihood (judgment):** on PostgreSQL, very low: no production trigger. On SQLite, low to moderate: it needs the default journal mode and a reader in another process, with the ordinary session pattern.
  - **Not established:** a PostgreSQL trigger without injection or unusual code; frequency on SQLite.
- **Production trigger (CHK-13, 2026-10-26).** No injection is needed on SQLite. In the default rollback-journal mode, a reader in another process makes `COMMIT` fail with `database is locked`, and SQLite keeps the transaction open.
  - **Configurations:** the default pysqlite configuration and `autocommit=False`.
  - **The path:** `with engine.connect()` / `conn.commit()` and `with Session(engine)` / `session.commit()` that close without `rollback()` reach P5a's path. Then:
    - no rollback;
    - the pooled connection keeps the lock, so independent reads and writes fail;
    - the next checkout commits the failed unit's row.
  - **Repetitions:** 3 of 3 on 2.1.6 and 2.0.55, with byte-identical case records.
  - **Not affected:** `engine.begin()`, an explicit `rollback()` before close, and WAL.
  - **The documented `BEGIN` recipe:** the next unit fails with `cannot start a transaction within a transaction` instead.
  - **Evidence:** [`python-upstream-contribution/chk-13-sa-sqlite-busy-commit/`](python-upstream-contribution/chk-13-sa-sqlite-busy-commit/README.md), with `FACTS.md` for the author.
  - **The PostgreSQL side** is still injection-only.
- **Priority:** 7. It is ready, and can move earlier if the author prefers. Leave time after PY-5.
- **Proposed action:** a Usage Questions discussion, written by the author in their own words. The venue was decided on 2026-10-18.
- **Prerequisites:** CHK-7 and a fresh duplicate search, both done 2026-10-25 (UTC). Re-checked 2026-10-25, 22:56–23:02 UTC: no duplicate, and `main` still `10f4d1e2d` ([`python-upstream-contribution/py-7-posting-day-checks/`](python-upstream-contribution/py-7-posting-day-checks/README.md)).
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** the author writes and posts, in their own words, in Usage Questions. The draft's script and Observed block are still valid on 2.1.6. Its line numbers are 2.1.5's; CHK-7's `FACTS.md` maps them to 2.1.6.

### PY-4: SQLAlchemy `after_rollback` during a cancelled `COMMIT`

- **Project:** SQLAlchemy 2.1.5 and 2.1.6 ORM. `main` `10f4d1e2d` is unchanged on this path: re-read 2026-10-25, it is three commits past `rel_2_1_6`, none touching rollback, commit or event dispatch.
- **Finding:** under anyio level-triggered cancellation, `after_rollback` fires. PostgreSQL then commits.
  - **CHK-4: the same without cancellation.** When the reply to `COMMIT` is lost and PostgreSQL commits, `after_rollback` and `after_soft_rollback` fire, and no DBAPI rollback is attempted.
  - **A rejected `COMMIT`** (`23503`, so PostgreSQL rolls back) fires the same events.
  - **So the event follows any root `COMMIT` that raised,** whatever PostgreSQL decided. It conflicts with the database when the outcome was unknown and PostgreSQL committed. In the roadmap's words (§D), "the finding concerns unknown outcomes in general, not anyio, and it should be reported that way."
- **Evidence:**
  - `research/python-production-failure-gap-analysis/p3_cancellation.py` and `output/p3.jsonl`, `p3b.jsonl`, `p3c-sa216.jsonl`;
  - added 2026-10-25: `research/python-production-failure-gap-analysis/p8-uvicorn-shutdown/` (P8). The same claim without anyio, from Uvicorn's graceful-shutdown timeout under SIGINT; it does not replace CHK-4;
  - **CHK-4,** [`python-upstream-contribution/chk-4-sa-lost-commit-reply/`](python-upstream-contribution/chk-4-sa-lost-commit-reply/README.md), on SQLAlchemy 2.1.6 and 2.1.5:
    - `Session` on psycopg, and `AsyncSession` on asyncpg and on psycopg, 3 of 3 per cell, with the server's statement log and `psql`;
    - [`FACTS.md`](python-upstream-contribution/chk-4-sa-lost-commit-reply/FACTS.md) there is the package for the author;
  - Src: `orm/session.py:1377-1380` and `engine/base.py:2697-2742`. These are 2.1.5's lines; CHK-4's `FACTS.md` gives 2.1.6's. This code path is shared with PY-7.
- **Consequence in a library (CHK-14, 2026-10-26).** sqlalchemy-file 0.7.0 deletes a unit of work's uploads in a `Session` `after_soft_rollback` listener. It has about 90k downloads a month and is integrated by starlette-admin.
  - **The runs:** through CHK-4's lost-reply proxy, `with session.begin()` and commit-then-`rollback()` both led to deletion. PostgreSQL committed the row, and sqlalchemy-file deleted its file (`delete_files`, `ctx=after_soft_rollback`), 3 of 3.
  - **README form:** sqlalchemy-file's README form (commit, no rollback) fires no rollback event.
  - **starlette-admin's call sequence:** it escapes, because `after_commit` fires at the savepoint `RELEASE`.
  - **Evidence:** [`python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/`](python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/README.md). The library's own gaps are PY-24.
- **Upstream:** none found. Precedent: #12728. Not re-checked for CHK-4.
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
- **Production relevance (2026-10-26)** ([standard](../docs/production-relevance.md); [evidence](python-upstream-contribution/real-world-evidence/README.md#py-4-and-py-24-rollback-hooks-after-a-commit-whose-outcome-is-unknown)):
  - **Consequence:** `commit()` raises and the rollback events fire while PostgreSQL committed, so a listener that undoes side effects deletes a committed row's file or discards its queued work.
  - **Trigger, a cancellation during `COMMIT`:** in production, yes (#12728, filed by SQLAlchemy's maintainer); in our runs, a real anyio cancellation (P3). Code shape: concurrent writes in tasks, which is reasonable.
  - **Trigger, a lost reply to `COMMIT`:** in production, yes in other ecosystems (block/buzz#3785, ducklake#1802); in our runs, simulated (CHK-4, category D). Code shape: any root `COMMIT`.
  - **Trigger, Uvicorn's graceful-shutdown timeout under `SIGINT`:** in production, unknown; in our runs, a real signal (P8). Code shape: the option set, with work that outlives it.
  - **Evidence for all three:** harmful consumers: sqlalchemy-file (117 stars, about 90k downloads a month; PY-24) and two small applications (0 and 1 stars) delete files, and two listeners discard queued work (source read). Other ecosystem: ducklake#1802, a user's report.
  - **Reproduced on real code:** yes, sqlalchemy-file 0.7.0 (CHK-14), 3 of 3. starlette-admin's call sequence ran, not starlette-admin, and it stays consistent after a lost reply.
  - **Searches:** about 414 files register `after_soft_rollback`; no inspected sample beyond the projects named.
  - **Likelihood (judgment):** low to moderate: such listeners are common enough, but the trigger needs a `COMMIT` whose outcome is unknown.
  - **Not established:** a Python report of the event on a committed transaction.
- **Priority:** 8.
- **Proposed action:** a documentation clarification; a change to event delivery is optional (roadmap §7). The author writes a discussion.
- **Prerequisites:**
  - CHK-4, done 2026-10-25 (UTC): a lost `COMMIT` reply gives the same claim;
  - P5a's reception.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** after P5a's reception, the author reads CHK-4's `FACTS.md` and writes the discussion in their own words. No agent drafts or posts the text.

## Unscheduled items

| ID | Evidence location | Existing issue or PR | Proposed action | Prerequisites | Status | Next concrete step |
| --- | --- | --- | --- | --- | --- | --- |
| PY-9 | `output/p1.out` (F, G); Ext `run-2.txt` | — | None while PY-1 and PY-2 are open | The outcome of PY-1 and PY-2 | DEFERRED | Revisit if both drivers decline |
| PY-10 | PPCS `6d8443`, `b2c174`; A2 P5, P6; Ext arm 4b | — | None | — | CLOSED_NO_ACTION | — |
| PY-11 | `output/p2.rep*.out` | psycopg Discussion #893 | None | — | CLOSED_NO_ACTION | — |
| PY-12 | `output/p6.jsonl`, `output/p6.server-log-endings.txt` | — | Not cited. Kept out of PY-1b by the maintainer's decision, since its evidence went through `Connection.commit()`. Dropped from PY-2 after the outside review: `test_timeout_06` covers the timeout case | — | CLOSED_NO_ACTION | — |
| PY-13 | `output/p3.jsonl` (psycopg rows); psycopg `docs/advanced/async.rst:200-204` | — | None | — | CLOSED_NO_ACTION | — |
| PY-14 | `output/p2.rep*.out` (Django native pool) | — | Optional documentation note | Django's contribution policy | DOCUMENTATION_ONLY | Not scheduled |
| PY-15 | Ext `lifecycle-close-reuse.md`, `run-2.txt` | — | Author-written, after P5a | PY-7's reception | DEFERRED | — |
| PY-16 | PPCS `3673a3`, `64c5c5`; Ext `run-2.txt` | — | None without a production trigger | — | CLOSED_NO_ACTION | — |
| PY-17 | PPCS `reports/examples/2026-10-21T20-00-04Z-178fa4` | Django #30490, #34610 | Optional forum note | — | DOCUMENTATION_ONLY | Not scheduled |
| PY-18 | PPCS `6d8443` | — | None | — | CLOSED_NO_ACTION | Keep in PPCS |
| PY-19 | Src: `tortoise/backends/asyncpg/client.py:96-97`, `backends/base/client.py` (exits) | — | None | A run that shows a consequence | DEFERRED | — |
| PY-20 | `python-upstream-contribution/py-8-tortoise-commit-translation/` (check 2; README "A separate candidate") | None found in PY-8's queries; not searched on its own | An issue, if CHK-8 holds | CHK-8 | NEEDS_VERIFICATION | Run CHK-8 |
| PY-21 | `sqlite-transaction-state-divergence/` findings F1 and F2; runs `sqlite-transaction-state-divergence/output/sqlite05c-enospc/2026-10-25T17-22-54Z-9e213e/`, `…/sqlite05b-batch/2026-10-25T17-22-43Z-4b67f2/`, `…/minimal-matrix/2026-10-25T18-21-01Z-556213/` | None found on 2026-10-25 (that study's `upstream/duplicate-search.md`). Related: #2696 (2013, MySQL lost its savepoints), #5968 (2021, `ON CONFLICT IGNORE`) | A Usage Questions discussion, written by the author in their own words | — | READY_FOR_HUMAN_REVIEW | The author writes it from `upstream/sqlalchemy-facts.md`, item SA-1, after its "Before posting" checks |
| PY-22 | `sqlite-transaction-state-divergence/` finding F3; `…/output/sqlite03-session/2026-10-25T17-21-29Z-85d1f6/` (`autocommit-false.execute.rollback.commit-escape`); `…/repro/minimal/sa_session_close_leak.py` | None found. #13657 (discussion #13656) fixed the same symptom in Core's `Connection.close()`, commit `d29277af` | A report written by the author in their own words; #13657 began as a discussion | — | READY_FOR_HUMAN_REVIEW | The author writes it from `upstream/sqlalchemy-facts.md`, item SA-2 |
| PY-23 | `sqlite-transaction-state-divergence/` finding F4; `…/output/sqlite01-raw/2026-10-25T17-21-27Z-737440/` (`pep249.rollback.*`); `…/repro/minimal/sqlite3_autocommit_false.py` | None found. Related: gh-112441 (2023, not planned; there the user's own SQL ended the transaction) | A CPython issue | Approval of the exact text | AWAITING_APPROVAL | Approve or edit `upstream/cpython-sqlite3-autocommit-false-draft.md`, then run its "Before filing" checks |
| PY-24 | [`python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/`](python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/README.md) | None found on 2026-10-26: no title among its 157 issues and pull requests reports it ([`python-upstream-contribution/real-world-evidence/`](python-upstream-contribution/real-world-evidence/README.md)) | An issue in jowilf/sqlalchemy-file: it treats `after_soft_rollback` as "nothing committed"; a failed `commit()` without `rollback()` leaves uploads; a savepoint `RELEASE` fires `after_commit` and clears its tracking. Not prescribed: a fix. Check its contribution rules first | A duplicate search | READY_FOR_HUMAN_REVIEW | Search the repository, then draft the issue for approval |
| PY-25 | [`python-upstream-contribution/chk-16-procrastinate-queueing-lock/`](python-upstream-contribution/chk-16-procrastinate-queueing-lock/README.md) | None found on 2026-10-26. Related: #1446 (open, the loud form in `retry_stalled_jobs`), #1508 (added the external-connection page's savepoint caveat), #1512 (an open PR that already uses the safe pattern) | An issue in procrastinate-org/procrastinate, offering a docs PR: the savepoint caveat on the queueing-lock and Django pages | Approval of the exact text; CHK-16 on `main` | AWAITING_APPROVAL | Approve or edit [the draft](python-upstream-contribution/upstream-drafts/procrastinate-queueing-lock-transaction.md) |

All `output/` paths are under `research/python-production-failure-gap-analysis/`, except PY-20's and those of PY-21 to PY-23. Theirs are under `research/sqlite-transaction-state-divergence/`, written `…/` after the first path in a row.

## Production relevance (2026-10-26)

Rated under [`docs/production-relevance.md`](../docs/production-relevance.md), from the evidence recorded by 2026-10-26: the [real-world evidence page](python-upstream-contribution/real-world-evidence/README.md), CHK-14, CHK-16 and each item's own checks. No new searches. The tiers weigh likelihood, the strength and source of the evidence, and whether the failure is silent. They are a judgment. They change no severity or feasibility rank (A, B) and no status.

- **Higher:** PY-2, PY-1a with PY-9, and PY-6. They are close: PY-6 has the best-sourced incident, and PY-1 and PY-2 the widest exposure.
- **Middle:** PY-4, PY-21, PY-25, PY-7 on SQLite, and PY-24.
- **Lower:** PY-1b, PY-5, PY-3, PY-20, PY-23, PY-22 and PY-8.
- **No production trigger:** PY-7 on PostgreSQL, PY-15, PY-16 and PY-18. PY-19 is unknown: source reading only.
- **Not defects, or folded into other items:** PY-10, PY-11, PY-12, PY-13, PY-14 and PY-17.

The scheduled items' own sections have the details. The other rated items:

| ID | Trigger, and how our runs produced it | Strongest real-world evidence | Real code run | Consequence | Likelihood (judgment) |
| --- | --- | --- | --- | --- | --- |
| PY-9 | A caught error from `Session.execute()`, then `commit()`; real errors (CHK-9, CHK-10) | PY-1's and PY-2's cases run through SQLAlchemy sessions (news-scraping#36, bainluck#8935); whether they register `after_commit` was not checked | No | `after_commit` runs for lost writes | Moderate, as PY-1a and PY-2 |
| PY-20 | A `COMMIT` that fails on SQLite; a deferred foreign key. CHK-13's locked `COMMIT` was not run | None | No | Later writes return normally and are lost | Low |
| PY-21 | SQLite ends the transaction; a real disk full, among others | The trigger occurs: Home Assistant #117263 and #112816, optuna #5011, google/fuzzbench #2070. No report of the mechanism | No | Every record before the failure is lost while `session.commit()` returns | Low to moderate |
| PY-22 | `ON CONFLICT ROLLBACK` under `autocommit=False` | None; the search was too broad | No | The pooled connection stays checked out | Low |
| PY-23 | `RAISE(ROLLBACK)` and `ON CONFLICT ROLLBACK` under `autocommit=False` | None; the count does not measure use | No | Later writes commit by themselves | Low |
| PY-24 | A rejected `COMMIT` in the README's form, from a deferred foreign key; a lost reply, simulated (CHK-14) | About 90k downloads a month, 117 stars; no incident among its 157 issues and pull requests | Yes (CHK-14) | Orphaned files; files deleted for committed rows | Orphaning moderate; deletion low |
| PY-25 | Ignoring `AlreadyEnqueued` inside the caller's transaction, as the docs allow; real errors (CHK-16) | CHK-16's sample: no unguarded catch in 104 sites; at least six projects guard with a savepoint | Yes (CHK-16) | The transaction is lost while `on_commit` runs or `commit()` returns | Low to moderate |

The others: PY-10, PY-11 and PY-13 are not defects. PY-12 adds triggers to PY-1 and PY-2. PY-14 and PY-17 are documentation only. PY-15's trigger is injected. PY-16 and PY-18 have no trigger. PY-19 is source reading only, and not assessed.

## Verification checks

The designs are in the roadmap §11. Each check needs its own throwaway container. Never use `ppcs-postgres` or `pnpm run pg:up`.

| ID | Unblocks | Required? | Status |
| --- | --- | --- | --- |
| CHK-1 | PY-1b | Optional | NOT_STARTED. Not run for the PY-1b draft |
| CHK-2 | PY-2 | Required before posting | DONE 2026-10-24. Reproduced, with no discrepancy from P1: [`python-upstream-contribution/chk-2-asyncpg/`](python-upstream-contribution/chk-2-asyncpg/README.md) |
| CHK-3 | PY-5 | Required | DONE 2026-10-25 (UTC). The measured arms reproduced on both drivers, and the corrected example reset all five measured items. A supplement after the outside review narrowed "resets nothing": [`python-upstream-contribution/chk-3-sa-reset-recipe/`](python-upstream-contribution/chk-3-sa-reset-recipe/README.md) |
| CHK-4 | PY-4 | Required (or PP-3) | DONE 2026-10-25 (UTC). H-b holds: with no cancellation, a lost `COMMIT` reply fires `after_rollback` while PostgreSQL commits, on 2.1.6 and 2.1.5 and all three stacks, 3 of 3: [`python-upstream-contribution/chk-4-sa-lost-commit-reply/`](python-upstream-contribution/chk-4-sa-lost-commit-reply/README.md) |
| CHK-5 | PY-3 | Recommended before the issue; required before a PR | DONE 2026-10-25 (UTC). Reproduced on both PostgreSQL backends, the savepoint variant included, with no discrepancy from P4: [`python-upstream-contribution/chk-5-tortoise/`](python-upstream-contribution/chk-5-tortoise/README.md) |
| CHK-6 | PY-6 | Optional | NOT_STARTED |
| CHK-7 | PY-7 | Required | DONE 2026-10-25 (UTC). Reproduced on SQLAlchemy 2.1.6, 3 of 3, with output byte-identical to the recorded run: `../python-orm-transactions/docs/sqlalchemy-transaction-experiments/p5a-review/chk-7/` (commit `3c9758b`) |
| CHK-8 | PY-20 | Required before an issue | NOT_STARTED. A duplicate search of its own, and the `SQLITE_BUSY` trigger (a reader holding the file during COMMIT), which SQLite documents and which has not been run |
| CHK-9 | PY-1a | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). psycopg2 2.9.13 has the same false commit, directly and through SQLAlchemy 2.1.6 Core and ORM, 3 of 3; the psycopg 3 positive controls reproduce: [`python-upstream-contribution/chk-9-psycopg2-false-commit/`](python-upstream-contribution/chk-9-psycopg2-false-commit/README.md) |
| CHK-10 | PY-2, PY-9 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). SQLAlchemy 2.1.6's asyncio engine on asyncpg 0.32.0 reports the false commit in Core and ORM, 3 of 3; raw asyncpg and the psycopg 3 asyncio controls reproduce: [`python-upstream-contribution/chk-10-sa-asyncpg-false-commit/`](python-upstream-contribution/chk-10-sa-asyncpg-false-commit/README.md) |
| CHK-11 | PY-2 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). A caught client-side timeout (`fetch(timeout=)`, `command_timeout`, `asyncio.wait_for()`) gives asyncpg 0.32.0's false commit, 6 of 6 per arm on asyncio and uvloop. The savepoint, no-timeout and uncaught controls behave as expected: [`python-upstream-contribution/chk-11-asyncpg-client-timeout/`](python-upstream-contribution/chk-11-asyncpg-client-timeout/README.md) |
| CHK-12 | PY-1a | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). Django 6.1.2 on psycopg 3.3.6, 3 of 3. After a raw-SQL error caught inside `atomic()`, or under `ATOMIC_REQUESTS` alone, Django sends `COMMIT`, `commit()` returns, `on_commit` runs, and the view returns 200, though the server had aborted. ORM errors roll back, and `atomic()` nested inside `ATOMIC_REQUESTS` fails loudly: [`python-upstream-contribution/chk-12-django-raw-sql-false-commit/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/README.md). Re-run 2026-10-26 with a once-only bonus as the trigger, the same results: [`once-only-rerun/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/once-only-rerun/README.md) |
| CHK-13 | PY-7 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). A real `SQLITE_BUSY` at `COMMIT`, with a reader in another process in rollback-journal mode, reaches P5a's path with no injection. The default and `autocommit=False` configurations, Core and Session closes without `rollback()`: the next checkout commits the failed unit's row, and the idle connection blocks all reads and writes until then. 3 of 3 on SQLAlchemy 2.1.6 and 2.0.55: [`python-upstream-contribution/chk-13-sa-sqlite-busy-commit/`](python-upstream-contribution/chk-13-sa-sqlite-busy-commit/README.md) |
| CHK-14 | PY-4, PY-24 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). sqlalchemy-file 0.7.0 through CHK-4's lost-reply proxy. With `with session.begin()` or commit-then-`rollback()`, PostgreSQL commits the row and the library deletes its file (`after_soft_rollback`), 3 of 3. The README form orphans files on a rejected `COMMIT`. starlette-admin's call sequence escapes the deletion, because `after_commit` fires at the savepoint `RELEASE`: [`python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/`](python-upstream-contribution/chk-14-sqlalchemy-file-lost-reply/README.md) |
| CHK-15 | PY-2 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC), under the working name CHK-13. asyncpg 0.32.0, asyncio and uvloop; a mechanism check, not a recommended design. A server timeout that fires before the client's deadline raises, and the block rolls back. A client deadline that fires first gives the false commit, also with `asyncio.timeout()` and longer server timeouts, 6 of 6 per arm. At the deadline, the same caught `TimeoutError` was followed by a real commit (95 of 488 trials) or the false commit (196): [`python-upstream-contribution/chk-15-asyncpg-timeout-order/`](python-upstream-contribution/chk-15-asyncpg-timeout-order/README.md) |
| CHK-16 | PY-1a, PY-25 | Added 2026-10-26; optional | DONE 2026-10-26 (UTC). Procrastinate 3.10.0 with Django 6.1.2 and psycopg 3.3.6. An order and its queueing-locked follow-up job in one transaction. On a repeat order, the ignored `AlreadyEnqueued` loses the transaction: Django runs `on_commit`, or `commit()` returns. A savepoint keeps the order. 3 of 3; 18 transactions agree: [`python-upstream-contribution/chk-16-procrastinate-queueing-lock/`](python-upstream-contribution/chk-16-procrastinate-queueing-lock/README.md) |

### CHK-2 result (2026-10-24)

**The setup:**

- container `ppcs-chk2-asyncpg-pg`, PPCS's pinned 18.6 digest, `127.0.0.1:55491`, with a tmpfs data directory and `log_statement=all`. Removed afterwards. `ppcs-postgres` was not touched;
- asyncpg 0.32.0, uvloop 0.23.0, Python 3.13.11.

**The arms,** each in 6 of 6 runs (asyncio and uvloop):

| Arm | asyncpg's report | PostgreSQL |
| --- | --- | --- |
| `async with con.transaction()`, error caught inside | Exits normally | `aborted` |
| `tr.start()` … `tr.commit()` | `commit()` returns `None`; a later `rollback()` raises "the transaction is already committed" | `aborted` |
| Raw `execute('COMMIT')` | Returns `'ROLLBACK'` | `aborted` |
| Savepoint control | Exits normally | `committed` |

**Agreement.** The program's witness connection, `psql` inside the container, and the server's statement log agree for all 24 transactions. The script's hash was the same before and after the runs.

**Independent re-run.** Later on 2026-10-24 an outside reviewer re-ran all three posted programs on its own fresh container, with the same versions and image. They were this program (three runs on asyncio and three on uvloop), the psycopg `transaction()` program, and the pipeline-pattern program.
- Every result matched: the asyncpg outputs once only the transaction IDs are masked, and the psycopg outputs byte for byte.
- `psql` agreed for all 24 asyncpg transactions.
- I re-checked those comparisons myself.
- The reviewer's records are kept locally, outside the repository.

### CHK-5 result (2026-10-25)

**The setup:**

- container `ppcs-chk5-tortoise-pg`, PPCS's pinned 18.6 digest, `127.0.0.1:55495`. It had a tmpfs data directory, `log_statement=all`, and `auto_explain` with `log_analyze`. Removed afterwards. `ppcs-postgres` was not touched;
- Tortoise ORM 1.1.9, asyncpg 0.32.0, psycopg 3.3.6, psycopg-pool 3.3.3, Django 6.1.2, SQLAlchemy 2.1.5, Python 3.13.11.

**The arms.** Each held in 6 of 6 runs, three on asyncpg and three on psycopg:

| Arm | Tortoise's report | PostgreSQL |
| --- | --- | --- |
| `retry`: `save()`, rollback, `save()` in a new `in_transaction()` | Returns normally | UPDATE for the old `pk` matches 0 rows; `committed`; 0 rows |
| `retry-changed`: a field changed before the retry | Returns normally | The same |
| `savepoint`: the INSERT in a rolled-back savepoint, then `save()` in the outer block | Returns normally; the outer block exits normally | The same UPDATE matches 0 rows; outer `committed`; 0 rows |
| `savepoint-changed` | Returns normally | The same |
| `control`: a new instance, saved once | Returns normally | INSERT; `committed`; 1 row |
| `force_update` (optional) | `IntegrityError: Can't update object that doesn't exist` | UPDATE matches 0 rows; `aborted`; 0 rows |

**The count `save()` receives.** In the wrapped runs, `execute_update()` returned 0 to `save()` in all 30 calls.

**The controls.** Django 6.1.2 and SQLAlchemy 2.1.5 persisted all four retry variants: 1 row each, three runs each. Django falls back from a 0-row UPDATE to an INSERT. SQLAlchemy makes the object transient and inserts it.

**Agreement.** The witness, `psql` inside the container, and the server's statement log with `auto_explain` agree for all 144 printed transactions; the cross-check found 0 problems. The program's hash was the same before and after its 12 runs.

**What it answers:**

- **(a)** The retry really sends an UPDATE that matches 0 rows, and its transaction commits.
- **(b)** The savepoint variant loses the write too.
- **(c)** The psycopg backend behaves the same.
- **The added changed-field arms.** Neither retry path skips SQL.

### CHK-3 result (2026-10-25)

**The setup:**

- containers `ppcs-chk3-sa-reset-pg` (the program and the psql checks) and then `ppcs-chk3-demo-pg` (the demo), PPCS's pinned 18.6 digest, both on `127.0.0.1:55492`, with tmpfs, `log_statement=all` and connection logging. Both removed. `ppcs-postgres` was not touched;
- SQLAlchemy 2.1.6, in one virtualenv with psycopg 3.3.6 and another with psycopg2-binary 2.9.13, Python 3.13.11;
- the login `app_login`, not a superuser, a member of `tenant_a`.

**The results,** each in 3 of 3 runs, with byte-identical output per driver:

| Question | psycopg 3 | psycopg2 |
| --- | --- | --- |
| (a), (b): the documented recipe | The hook ran on every return. It sent `BEGIN`, `CLOSE ALL`, `RESET ALL`, `DISCARD TEMP` and `ROLLBACK` in one transaction, which is `aborted`. All five state items carried over | The hook raised `AttributeError` (`execute`) on each tested return. The pool logged it and invalidated the connection. The next checkout was a new backend, with none of the five items |
| (c): the corrected example | All five reset; same connection | All five reset; same connection |
| (d): on an AUTOCOMMIT engine | Autocommit kept (P7's variant, as a control, loses it) | Autocommit kept |
| (e): connect-time `SET SESSION search_path` | Lost after the first return | Lost |
| (e): startup `options` | Survives | Survives |
| Added: REPEATABLE READ | Survives | Survives. psycopg2 adds `SET default_transaction_isolation TO DEFAULT` per return |
| Added: prepared statements | psycopg sends `DEALLOCATE ALL` and re-prepares, with no error | — |
| Supplement: `CLOSE ALL` and a WITH HOLD cursor (`psql`) | The recipe's rolled-back block still closes the cursor; an empty rolled-back block does not | — |
| Supplement: the documented recipe on an AUTOCOMMIT engine | Resets everything measured except the role | — (the hook raises first) |
| Supplement: the corrected example, default `pool_reset_on_return` | All five reset | All five reset |
| Supplement: a connection returned with its transaction open | `transaction_was_reset=True`; the uncommitted row never appears; all five reset (state carries over without a hook) | The same |

**Agreement.** The witness, the server's statement log, and `psql` (the reset transactions' fates, and all 48 rows) agree. The program's hash was the same before and after its six runs. A 64-line demo, run three times per driver, reproduced the documented and corrected results.

### CHK-7 result (2026-10-25)

- **The run.** `check/p5a_close_v2.py`, unchanged, on SQLAlchemy 2.1.6 with psycopg 3.3.6. It used its own container, `chk7-p5a-pg` on `127.0.0.1:55454` (the script's URL), with tmpfs and `log_statement=all`, since removed.
- **3 of 3 runs** exited 0, with stdout byte-identical to the recorded `.out`. After masking the paths, stderr differs from the saved 2026-10-18 run of the draft's script in two line numbers, each appearing twice:
  - `pool/base.py` 1485 → 1492, from SQLAlchemy 2.1.6;
  - the script's frame 31 → 38, from v2's added reset listener.

  The v2 script's own 2026-10-18 stderr was not saved.
- **Independent confirmation.** In the server log, the next checkout's insert and `COMMIT` share the `doomed` insert's virtual transaction, with no `ROLLBACK` between them. `psql` reads those transactions as `committed`.

### CHK-4 result (2026-10-25)

**The setup:**

- container `ppcs-chk4-pg`, PPCS's pinned 18.6 digest, `127.0.0.1:55494`, with tmpfs, `log_statement=all` and connection logging. Removed afterwards. `ppcs-postgres` was not touched;
- SQLAlchemy 2.1.6 and 2.1.5, each in a virtualenv with psycopg 3.3.6, asyncpg 0.32.0 and greenlet 3.5.6, on Python 3.13.11;
- the login `chk4_app`, not a superuser, and a pool of one, as in P3;
- the lost reply: PPCS's category-E proxy, `harness/lib/pg-wire-proxy.mjs`, run unchanged, on the engine's first connection only.

**The results.** Each cell ran 3 of 3, with byte-identical output per cell. Both versions gave the same output, apart from the version field.

| Arm | PostgreSQL | ORM events | DBAPI rollback after the failed `COMMIT` |
| --- | --- | --- | --- |
| Lost reply | `committed` when the block raised; the row visible, `xmin` = its xid | `after_rollback`, `after_soft_rollback` | None: not called, and the backend logged only its disconnection |
| Added: a rejected `COMMIT` (deferred foreign key, `23503`) | `aborted` | `after_rollback`, `after_soft_rollback` | No `ROLLBACK` reached the server |
| Control: no fault | `committed` | `after_commit` | — |

- **The sequence.** The lost-reply sequence is P3's level-triggered one, with the lost reply in place of the cancellation.
- **The error.** Every stack raised a disconnect error with `connection_invalidated` true: `OperationalError` on psycopg, `DBAPIError` on asyncpg.
- **The next unit.** The next unit of work committed normally in all 54 runs.

**Agreement.**
- The observer, the server's statement log and `psql` (all 108 xids, and every marker row) agree.
- The scripts' hashes were recorded before the matrix, and are unchanged.
- 28 smoke runs before the matrix found one apparatus error, fixed before recording (README, "Apparatus incidents").

## Evidence preservation (PP-1)

**Status: committed and pushed on 2026-10-24.**

- **Committed** at the maintainer's approval, as the six commits planned below: `ad2a1e0`, `0a72d66`, `5962a3b`, `e776374`, `6fc6d98` and `905e797`.
- **Pushed** to GitHub's `main` through the merge commit `e59a484`, a fast-forward with nothing forced.
- **Uncommitted since then.** The later revisions are local:
  - both drafts;
  - this tracker;
  - the roadmap's corrections;
  - the CHK-2 README's hash fix;
  - `python-upstream-contribution/psycopg-pipeline-test-check/`.
- **The outside review's own files** stay local, outside version control.

The rest of this section is the plan as it stood before the commits.

**Verified before preparing the commits:**

- **Hashes.** Both evidence directories match the SHA-256 lists in their READMEs: 22 files in the gap analysis, 2 in the audit.
- **No credentials.**
  - `.pgpass_token` is absent, and gitignored.
  - The only password in a script is P2's probe-only `app_login` password. Its README documents it, and the role existed only in a container that has since been removed.
  - CHK-2's server log contains no password.
- **No private paths.** There are no local, scratchpad, or personal paths in the files to be committed.
- **The three investigations are complete.**
  - Both agent status files end with "Done".
  - The roadmap and this tracker were unchanged since 09:11 PDT until this update.

**Planned commits.** Each is staged by explicit path.

| # | Contents | Paths |
| --- | --- | --- |
| 1 | The audit and its evidence (Agent 1) | `research/python-ecosystem-contribution-audit.md`, `research/python-ecosystem-contribution-audit/` |
| 2 | The gap analysis and its evidence (Agent 2) | `research/python-production-failure-gap-analysis.md`, `research/python-production-failure-gap-analysis/`, including its `.gitignore` |
| 3 | The roadmap, and this tracker as first written | `research/python-upstream-contribution-roadmap.md`, and the tracker's first version (SHA-256 `a6dfbf20a942ede639536eec44592868ee068ba634da844e0b678ba57ae02432`) |
| 4 | CHK-2 | `research/python-upstream-contribution/chk-2-asyncpg/` |
| 5 | The PY-1b and PY-2 drafts | `research/python-upstream-contribution/upstream-drafts/` |
| 6 | This update of the tracker | `research/python-upstream-contribution-tracker.md` |

**Left out on purpose:**

- **`research/AGENT-1-STATUS.md` and `research/AGENT-2-STATUS.md`.** Coordination files, marked "not for commit".
- **Another session's uncommitted edits of 2026-10-23,** unrelated to this research:
  - `AGENTS.md`;
  - `docs/research-master-plan.md`, `docs/research-roadmap.md` and `docs/research-status.md`;
  - `research/production-reachability/README.md`, and its `upstream-drafts/README.md`.
- **`research/python-lifecycle-investigation-prompt.md`.** It appeared at 09:39 PDT during this update: a research assignment for a separate investigation.
- **`.pnpm-store/` and the `__pycache__/` directories** (`AGENTS.md` rule 13).
- **`../sqla-tx02-repro/` and `../tortoise-tx-investigation/`,** the roadmap's other PP-1 items. They lie outside this repository, are not git repositories, and are not this research's work.

**A stale pointer, left unedited.** The audit's §8.2 (line 531) says that P1's program and output are in Agent 2's scratchpad. They are preserved at `research/python-production-failure-gap-analysis/p1_commit_tag.py` and `output/p1.out`. The audit is Agent 1's finished report, so it was not changed.

## Blockers and changed conclusions (2026-10-24)

- **No conclusion changed.** CHK-2 reproduced P1's asyncpg result in all six runs. psycopg#1453 and both default branches are unchanged.
- **Refinements:**
  - **The PY-2 draft uses a public signal.** asyncpg's `rollback()` message ("the transaction is already committed") shows the recorded state through the public API. The draft uses it instead of `repr()`.
  - **psycopg.** `Transaction` does not reach `Connection._commit_gen` simply because it calls `_exec_command` itself. The method's guard against use inside a block is not the reason: the block's counter is already 0 when its `COMMIT` is sent. The roadmap's §3.2 A wording stands.
  - **asyncpg.** One new related PR (#1399), and the maintainer's review and statement under PY-2.
- **A departure from this tracker.** PY-12 is now cited in neither draft (see PY-12).
- **A correction, later on 2026-10-24.** An outside adversarial review found two false claims that no upstream test exercises this pattern. Both drafts and the roadmap had them. The earlier search looked only for `try`/`except`.
  - **psycopg.** `test_outer_transaction_error`, and its async copy, catches a database error inside `transaction()` and expects normal exit.
    - When run, its pattern gave `INERROR` at exit, no raise, `status` `committed`, and an aborted transaction.
    - So a `transaction()` fix that raises conflicts with it, and a `status`-only fix does not.
    - Evidence: [`python-upstream-contribution/psycopg-pipeline-test-check/`](python-upstream-contribution/psycopg-pipeline-test-check/README.md).
  - **asyncpg.** `test_timeout_06`, and `test_timeout_04`, exit a transaction block normally after a caught error that aborted it, so a fix that raises conflicts with them. The PY-2 draft now asks the maintainers which behaviour they want.
  - **What did not change.** The findings themselves (PY-1b and PY-2 CONFIRMED). The change is to the compatibility framing.
- **Blockers.** None for PY-1b and PY-2: the comment was posted and the issue filed on 2026-10-24, after approval of the exact texts. Today's later edits are uncommitted and local (see PP-1).
- **CHK-5 (2026-10-25 UTC). No conclusion changed.** PY-3 stays CONFIRMED.
  - **Refinements:**
    - The retry's statement, its 0 matched rows, and the count `save()` receives are now observed. Before CHK-5 they were Src.
    - The roadmap's H-c holds: the savepoint variant loses the write.
  - **The effect on the fix question.**
    - Option (a) has to work per savepoint level. A reset only at the outermost rollback would miss the savepoint case, because the outer transaction commits.
    - Option (b) does not depend on nesting.
    - The recommendation stands: ask the maintainers. The draft presents both options without choosing.
  - **The added control** (a field changed before the retry, at the maintainer's request) changed nothing. Both retry paths send an UPDATE.
- **CHK-3 and CHK-7 (2026-10-25 UTC).** The five-item result on a transactional engine, and the P5a reproduction, remain CONFIRMED. One earlier wording was too broad.
  - **"The recipe resets nothing"** (roadmap §1 and §3.2 E, and this tracker before the check) holds only for the five measured items on a transactional psycopg 3 engine. The recipe's `CLOSE ALL` does close WITH HOLD cursors. On an AUTOCOMMIT engine the recipe resets everything measured except the role (the CHK-3 supplement, after an outside review).
  - **Refinements for PY-5:**
    - "The hook ran" was an inference from P7. It is now observed: a counter, and the statements in the server log.
    - H-d held for each tested return. On psycopg2 the effect is not leaked state but no connection reuse, because every tested return discarded the connection.
    - Two Judg or Src claims in roadmap §3.2 E.3 are now observed: startup `options` survive `DISCARD ALL`, and psycopg 3 recovers its prepared statements.
  - **Line numbers.** On 2.1.6 the code PY-5 and PY-7 cite sits lower: `RootTransaction` by 5 lines, and `_reset`, `_close_special` and `_checkin` by 7. The P5a draft, and PY-5's earlier Src lines, are 2.1.5's. Both `FACTS.md` files give the 2.1.6 lines.

- **PY-8 (2026-10-25 UTC). No conclusion changed.** PY-8 stays CONFIRMED, now on three backends.
  - **A correction.** Not every backend decorates `begin()` (see PY-8).
  - **A new item.** Check 2 found PY-20, which is independent of PY-8. It is the reason the PR leaves SQLite alone.
- **CHK-4 (2026-10-25 UTC). One framing changed.** PY-4 stays CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN, but it is not specific to cancellation.
  - **H-b holds** (roadmap §3.1). A lost `COMMIT` reply, with no cancellation, gives the same `after_rollback`, and PostgreSQL commits. In §D's words, "the finding concerns unknown outcomes in general, not anyio, and it should be reported that way."
  - **A Src claim is now observed.** The event also follows a server-rejected `COMMIT` (the added arm), with no `ROLLBACK` sent.
  - **Not covered:** an explicit `session.commit()`, and a reused connection in the recorded runs (CHK-4's README, "Limits").

## Change log

- **2026-10-24.** Tracker created from the roadmap. Upstream re-checked the same day: only psycopg#1453 is filed, and nothing else in this tracker is posted.
- **2026-10-24, later.**
  - Ran CHK-2, which reproduced the result.
  - Drafted the PY-1b comment and the PY-2 issue; neither is posted or filed.
  - Re-checked upstream: #1453 unchanged; no asyncpg duplicate; both default branches unchanged.
  - Prepared the PP-1 commits, not made.
  - PY-1b and PY-2 moved to AWAITING_APPROVAL.
- **2026-10-24, later still.**
  - Made the PP-1 commits (`ad2a1e0`..`905e797`) and pushed them through the merge commit `e59a484`.
  - An outside adversarial review rated both drafts READY WITH CHANGES.
  - I verified its findings, and ran psycopg's `test_outer_transaction_error` pattern.
  - I revised both drafts, corrected the roadmap's test claims, and fixed one abbreviated hash in the CHK-2 README.
  - These edits are uncommitted. PY-1b and PY-2 stay AWAITING_APPROVAL.
- **2026-10-24, about 21:53 UTC.** The maintainer approved the exact texts, and both were submitted after the pre-posting checks passed.
  - PY-1b posted as https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348.
  - PY-2 filed as https://github.com/MagicStack/asyncpg/issues/1400.
  - Both posted texts match the drafts (compared through the API).
  - Both items are SUBMITTED. A follow-up is due around 2026-11-07, and a decision around 2026-11-21.
  - Added the note on the outside reviewer's independent re-run.
- **2026-10-25, about 01:45 UTC (2026-10-24 PDT).**
  - Ran CHK-5, which reproduced P4 and answered (a), (b) and (c): [`python-upstream-contribution/chk-5-tortoise/`](python-upstream-contribution/chk-5-tortoise/README.md).
  - Re-checked upstream for PY-3: no duplicate; `develop` moved to `ad0d6ce2b`, with `save()` unchanged; PyPI's latest is still 1.1.9.
  - Drafted the PY-3 issue; it is not filed. PY-3 moved to AWAITING_APPROVAL.
  - Nothing committed.
- **2026-10-25, about 02:00 UTC (2026-10-24 PDT).**
  - **Ran CHK-7.** P5a reproduced on SQLAlchemy 2.1.6, 3 of 3, with output byte-identical to the recorded run. Its evidence and `FACTS.md` are in `../python-orm-transactions/docs/sqlalchemy-transaction-experiments/p5a-review/chk-7/`, uncommitted there.
  - **Ran CHK-3.** The measured arms reproduced on both drivers, and the corrected example reset all five measured items on psycopg 3 and psycopg2: [`python-upstream-contribution/chk-3-sa-reset-recipe/`](python-upstream-contribution/chk-3-sa-reset-recipe/README.md), with `FACTS.md`.
  - **Re-checked upstream** for PY-5 and PY-7:
    - no duplicate;
    - the recipe's text is unchanged on `main`;
    - #13699 is related code, not P5a;
    - 2.1.6 is still the latest release.
  - **Status.** PY-5 moved to READY_FOR_HUMAN_REVIEW. PY-7 stays READY_FOR_HUMAN_REVIEW. Both await their author's own text.
  - **Nothing committed, posted or filed.** `docs/upstream-submissions.md` was not edited.
- **2026-10-25, about 03:30 UTC (2026-10-24 PDT).**
  - **An outside adversarial review** rated CHK-3 and CHK-7 SOUND WITH CHANGES, this tracker ACCURATE WITH CHANGES, and the commit plan NOT READY. Every required run reproduced byte for byte.
  - **I verified its findings and accepted all of them:**
    - "resets nothing" was too broad;
    - CHK-3's fact 6 was wrong for psycopg2;
    - CHK-7 generalized its xid reasoning;
    - this tracker misattributed a stderr line shift;
    - the commit plan did not check committed blobs.
  - **The maintainer approved the CHK-3 supplement:** `CLOSE ALL` with a WITH HOLD cursor, the documented recipe on an AUTOCOMMIT engine, the corrected example under the default reset, and a connection returned with its transaction open. 3 of 3 runs each; results as in "CHK-3 result".
  - **Corrected:** both `FACTS.md` files, both READMEs, this tracker's PY-5, PY-7, CHK-3 and CHK-7 text, and the commit plan, which now builds commits outside the shared index.
  - **Nothing committed, posted or filed.** The review's own files stay local.
- **2026-10-25, about 14:46 UTC (2026-10-25 PDT).** Committed at the maintainer's approval:
  - the CHK-7 evidence as `3c9758b`, in `../python-orm-transactions`;
  - the CHK-3 evidence as `f9daa31`;
  - this tracker update, in the commit after `f9daa31`.
- **2026-10-25, 03:14–14:05 UTC.** PY-8 steps 1 and 2, and a review package.
  - Ran step 1's checks and candidates, implemented the chosen approach on a local Tortoise branch, and ran the review checks: [`python-upstream-contribution/py-8-tortoise-commit-translation/`](python-upstream-contribution/py-8-tortoise-commit-translation/README.md).
  - The changelog wording the review recommended was applied at the maintainer's request.
  - Committed and pushed at the maintainer's request: the evidence as `2757a35`, a correction of three times in its READMEs as `ed8e236`, and this tracker update in the commit after it. The Tortoise branch is not committed, and nothing is filed.
  - New: PY-20 and CHK-8.
  - **PY-3 recorded as SUBMITTED** ([#2383](https://github.com/tortoise/tortoise-orm/issues/2383), filed 2026-10-25 by another session and logged in `docs/upstream-submissions.md` in `38bf2a7`): the header list, the summary row and PY-3's status. This tracker had not been updated when it was filed.
- **2026-10-25, about 15:35 UTC.**
  - **Ran CHK-4.** H-b holds on SQLAlchemy 2.1.6 and 2.1.5: [`python-upstream-contribution/chk-4-sa-lost-commit-reply/`](python-upstream-contribution/chk-4-sa-lost-commit-reply/README.md), with `FACTS.md`.
  - **Status.** PY-4 moved to READY_FOR_HUMAN_REVIEW. Its post still waits on P5a's reception.
  - **Committed and pushed** at the maintainer's request: the evidence as `190173c`, and this tracker update in the commit after it.
  - **Nothing posted or filed.** The roadmap was not edited.
- **2026-10-25, about 22:00 UTC.**
  - **PY-7: added the SQLite consequence** from [`sqlite-transaction-state-divergence/`](sqlite-transaction-state-divergence/findings.md) (F6), at the maintainer's request, and a note on the SQLite trigger under Confidence. Status unchanged.
  - Committed on branch `research/sqlite-state-divergence` with that study. Not pushed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-25, about 22:10 UTC.**
  - **New: PY-21, PY-22 and PY-23** from the same study: F1 with F2, F3, and F4, at the maintainer's request. They are unranked, like PY-20; the roadmap was not edited.
  - PY-23's draft is stored with its study, in `sqlite-transaction-state-divergence/upstream/`, not in `python-upstream-contribution/upstream-drafts/`.
  - Committed on branch `research/sqlite-state-divergence`. Not pushed. Nothing posted or filed.
- **2026-10-25, about 22:20 UTC.** Pushed to `main` at the maintainer's request, as a fast-forward from `68fa4e0`: the SQLite study (`4d54f1b`, `2c48f68`, `b8d8e48`, `8e82653`), the PY-7 note (`378bdd5`), PY-21 to PY-23 (`8de2fbb`), and this entry in the commit after it. Nothing posted or filed.
- **2026-10-26, about 02:50 UTC.** At the maintainer's request:
  - **PY-7: published the P5a evidence** in [`python-upstream-contribution/py-7-sa-p5a-close/`](python-upstream-contribution/py-7-sa-p5a-close/README.md) (commit `c79ff1a`), normalized from `python-orm-transactions` at `90cfaf3`. Local paths are replaced by placeholders, and `SOURCE-HASHES.txt` gives each file's source and published SHA-256. The SQLAlchemy issue draft is not included.
  - **PY-7: recorded the CHK-7 supplement** (`70676d9` in that repository): both triggers that replace no DBAPI method reproduce on 2.1.6.
  - Status unchanged. Nothing posted or filed.
- **2026-10-26, about 03:35 UTC.** At the maintainer's request:
  - **CHK-9 (new): psycopg2 has the PY-1 false commit.** psycopg2 2.9.13, directly (`commit()`, `with conn:`) and through SQLAlchemy 2.1.6 Core (`commit()`, `engine.begin()`) and ORM (`session.commit()`, `sessionmaker.begin()`, both running `after_commit`), 3 of 3; a failed ORM flush raised `PendingRollbackError`. Evidence: [`python-upstream-contribution/chk-9-psycopg2-false-commit/`](python-upstream-contribution/chk-9-psycopg2-false-commit/README.md) (commit `9166ea1`). The roadmap's §9 judgment that psycopg2 behaves the same is now observed; the roadmap was not edited.
  - Nothing posted or filed.
- **2026-10-26, about 04:06 UTC.** At the maintainer's request:
  - **CHK-10 (new): SQLAlchemy's asyncio engine passes asyncpg's false commit through.** On SQLAlchemy 2.1.6 with asyncpg 0.32.0, `AsyncConnection.commit()`, `engine.begin()`, `AsyncSession.commit()` and `async_sessionmaker.begin()` (with `after_commit`) return normally after `COMMIT` is answered `ROLLBACK`, 3 of 3; a failed ORM flush raised `PendingRollbackError`. Evidence: [`python-upstream-contribution/chk-10-sa-asyncpg-false-commit/`](python-upstream-contribution/chk-10-sa-asyncpg-false-commit/README.md) (commit `664464b`).
  - **PY-7: posting-day checks** of 2026-10-25, 22:56–23:02 UTC, in [`python-upstream-contribution/py-7-posting-day-checks/`](python-upstream-contribution/py-7-posting-day-checks/README.md) (commit `bf0bf37`): no duplicate; nothing posted.
  - **New summary:** [`python-upstream-contribution/false-commit-across-drivers.md`](python-upstream-contribution/false-commit-across-drivers.md) (commit `ae1c695`), the false commit by driver and access path, linked to each piece of evidence.
  - **PY-1b: follow-up drafted** in [`python-upstream-contribution/upstream-drafts/psycopg-1453-followup-psycopg2.md`](python-upstream-contribution/upstream-drafts/psycopg-1453-followup-psycopg2.md) (commit `3ebe530`), reporting CHK-9's psycopg2 result. Planned as the one follow-up if #1453 is still silent in week 3; not posted.
  - **PY-9:** CHK-9 and CHK-10 observed `after_commit` on aborted transactions with psycopg2, psycopg 3 and asyncpg on 2.1.6. Still DEFERRED.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 04:25 UTC.** At the maintainer's request:
  - **CHK-11 (new): a caught client-side timeout gives asyncpg's false commit.** On asyncpg 0.32.0, a `TimeoutError` from `fetch(timeout=)`, `command_timeout` or `asyncio.wait_for()`, caught inside `async with con.transaction()`, gives the false commit, 6 of 6 per arm on asyncio and uvloop. Evidence: [`python-upstream-contribution/chk-11-asyncpg-client-timeout/`](python-upstream-contribution/chk-11-asyncpg-client-timeout/README.md) (commit `70be22f`).
    - What asyncpg reported: the block exits normally, `tr.commit()` returns `None`, and a raw `execute('COMMIT')` returns `'ROLLBACK'`.
    - What PostgreSQL did: it aborted the transaction.
  - **PY-2: follow-up drafted** in [`python-upstream-contribution/upstream-drafts/asyncpg-1400-followup-timeout.md`](python-upstream-contribution/upstream-drafts/asyncpg-1400-followup-timeout.md) (commit `f57e9f5`), reporting CHK-11's result. Planned as the one follow-up if #1400 is still silent around 2026-11-07; not posted.
  - **The false-commit summary** ([`python-upstream-contribution/false-commit-across-drivers.md`](python-upstream-contribution/false-commit-across-drivers.md)) gained a CHK-11 row.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 13:20 UTC.** At the maintainer's request:
  - **CHK-12 (new): Django commits after a caught raw-SQL error inside `atomic()`.** Evidence: [`python-upstream-contribution/chk-12-django-raw-sql-false-commit/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/README.md) (commit `3545572`).
    - On Django 6.1.2 with psycopg 3.3.6, with `atomic()` in the view or with `ATOMIC_REQUESTS` alone, Django sends `COMMIT` after a raw-SQL error caught inside the transaction.
    - psycopg's `commit()` returns, `on_commit` runs, and the view returns 200, 3 of 3.
    - An ORM error makes Django roll back by itself in all three setups, without `on_commit`.
    - With `atomic()` nested inside `ATOMIC_REQUESTS`, Django's `RELEASE SAVEPOINT` fails with `25P02`, and the request returns 500.
  - **PY-10:** its row now notes CHK-12. It stays CLOSED_NO_ACTION, because Django documents a caught raw-SQL error inside `atomic()` as unspecified.
  - **The false-commit summary** gained a Django row.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26.**
  - **New: CHK-13 (PY-7) and CHK-14 (PY-4, PY-24),** run under the working names CHK-9 and CHK-10 before those IDs were taken.
  - **PY-7** has a production trigger on SQLite (`SQLITE_BUSY` at `COMMIT`). The PostgreSQL side is unchanged.
  - **PY-4** has a library consequence confirmed at runtime (sqlalchemy-file deletes the file of a committed row), plus real-world signal notes.
  - **New: PY-24,** sqlalchemy-file's own gaps. It is unranked.
  - **PY-21:** the real-world search found disk-full errors in SQLAlchemy-on-SQLite projects: Home Assistant #117263 and #112816, optuna #5011, google/fuzzbench #2070. It found no report of PY-21's own mechanism.
  - **Priorities** are unchanged, pending the maintainer's ranking. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 13:48 UTC.** Pushed to `main` at the maintainer's request, as a fast-forward from `1f30616`: CHK-11 (`70be22f`, `f57e9f5`, `75d68dd`) and CHK-12 (`3545572`, `28c0566`). Nothing posted or filed.
- **2026-10-26, about 14:15 UTC.** At the maintainer's request:
  - **CHK-15 (new): which timeout fires first, and the race at the deadline.** Evidence: [`python-upstream-contribution/chk-15-asyncpg-timeout-order/`](python-upstream-contribution/chk-15-asyncpg-timeout-order/README.md) (commit `ecc0a8d`).
    - It ran under the working name CHK-13, which the SQLite record above took first.
    - On asyncpg 0.32.0, a server timeout that fires first raises, and the block rolls back. A client deadline that fires first gives the false commit, also with `asyncio.timeout()`.
    - Its README says the trigger is not a recommended design.
  - **PY-2: the timeout follow-up draft is retired** (commit `50b824f`). Its trigger is not reasonable application code. Around 2026-11-07, the choice is between a plain nudge and nothing.
  - **The false-commit summary** cites CHK-15.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 14:20 UTC.** At the maintainer's request:
  - **CHK-12 re-run with a reasonable trigger.** Evidence: [`python-upstream-contribution/chk-12-django-raw-sql-false-commit/once-only-rerun/`](python-upstream-contribution/chk-12-django-raw-sql-false-commit/once-only-rerun/README.md) (commit `9811a82`).
    - The trigger is a once-only first-order bonus as the order's last step, with the duplicate (`23505`) treated as "already awarded". It replaces CHK-12's best-effort analytics write, which does not belong in the transaction.
    - The results are the same, 3 of 3, and all 36 transactions agree.
    - CHK-12's README gains a scope note. Its original evidence is unchanged.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 14:21 UTC.** At the maintainer's request:
  - **Real-world evidence** for the Python items, from read-only GitHub searches: [`python-upstream-contribution/real-world-evidence/`](python-upstream-contribution/real-world-evidence/README.md) (commit `d631390`). Strongest: production loss on SQLAlchemy's asyncio engine with asyncpg (PY-2); an audit on SQLAlchemy with psycopg2 (PY-1); a SQLite P5a incident (PY-7); a role carried over, in a project's changelog (PY-6); file-deleting rollback hooks (PY-4). Nothing found for PY-8, PY-15 or PY-20 to PY-23.
  - Each scheduled item gains a "Real-world signal" bullet; PY-24's upstream check is recorded.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 15:00 UTC.** At the maintainer's request:
  - **A production-relevance standard:** [`docs/production-relevance.md`](../docs/production-relevance.md) (commit `99328b6`), with `AGENTS.md` rule 15 and a link from the master plan's dimension 7.
  - **Each scheduled item's "Real-world signal" bullet becomes a "Production relevance" section** in the standard's fields. PY-1b gains one, and PY-4's two bullets become one.
    - The content comes from the real-world evidence page and from each item's own evidence. Star counts and reporters were read from GitHub on 2026-10-26.
    - Likelihood is "not assessed" throughout.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 15:05 UTC.** At the maintainer's request:
  - **CHK-16 (new): Procrastinate's queueing lock inside the caller's transaction.** Evidence: [`python-upstream-contribution/chk-16-procrastinate-queueing-lock/`](python-upstream-contribution/chk-16-procrastinate-queueing-lock/README.md) (commit `70e8703`).
    - The application: an order and its follow-up job commit together, with a per-customer queueing lock, and the documented `AlreadyEnqueued` is ignored. The job belongs in the transaction.
    - On a repeat order, the transaction is lost while the code reports success, 3 of 3.
    - The README includes a code-search sample: no unprotected catch was found, and at least six projects guard with a savepoint.
  - **New: PY-25,** Procrastinate's docs: the savepoint caveat is only on the external-connection page. The issue draft ([`python-upstream-contribution/upstream-drafts/procrastinate-queueing-lock-transaction.md`](python-upstream-contribution/upstream-drafts/procrastinate-queueing-lock-transaction.md), commit `71e3740`) is not posted.
  - **The false-commit summary** gained a Procrastinate row.
  - No other status changed. Nothing posted or filed. The roadmap was not edited.
- **2026-10-26, about 15:50 UTC.** At the maintainer's request:
  - **Production relevance rated for every Python item,** from the evidence already recorded, with no new searches: the new section "Production relevance (2026-10-26)" gives the tiers and a row for each other rated item.
  - **Each scheduled item's section** is shortened to verdicts with links to the evidence, and gains a likelihood. PY-1a's adds CHK-16.
  - **The standard** now allows a link to the evidence instead of a copy, and its coverage note is updated.
  - No status changed. Nothing posted or filed. The roadmap was not edited.
