# Python upstream contribution tracker

Started: 2026-10-24. Updated the same day, after CHK-2 and the PY-1b and PY-2 drafts. Written by: Claude Opus 5.5 (max).

This is the working tracker for [`python-upstream-contribution-roadmap.md`](python-upstream-contribution-roadmap.md). The roadmap holds the reasoning, the fixes, and the test designs. This file holds only the status and the next step for each item.

- **Nothing here is filed unless its row links a filing.** Filed so far:
  - PY-1a: [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), 2026-10-21;
  - PY-1b: [a comment on #1453](https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348), 2026-10-24;
  - PY-2: [asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400), 2026-10-24;
  - PY-3: [tortoise/tortoise-orm#2383](https://github.com/tortoise/tortoise-orm/issues/2383), 2026-10-25.
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
| PY-2 | asyncpg | `Transaction.commit()` and `async with` report success after `COMMIT` is answered `ROLLBACK` | CONFIRMED; CHK-2 reproduced it on asyncio and uvloop | 2 (A2, B5) | SUBMITTED | Filed 2026-10-24 as [#1400](https://github.com/MagicStack/asyncpg/issues/1400). One follow-up around 2026-11-07 if silent; decide around 2026-11-21 |
| PY-3 | Tortoise ORM | A retried `save()` after a rollback writes nothing and returns normally | CONFIRMED; CHK-5 reproduced it on the asyncpg and psycopg backends, the savepoint variant included | 3 (A3, B4) | SUBMITTED | Filed 2026-10-25 as [#2383](https://github.com/tortoise/tortoise-orm/issues/2383). One follow-up around 2026-11-08 if silent; decide around 2026-11-22 |
| PY-5 | SQLAlchemy (docs) | On a transactional psycopg 3 engine, the documented PostgreSQL reset recipe leaves the role, a custom GUC, `search_path`, `statement_timeout` and temp tables in place. On psycopg2, the driver in its URL, it raised on each tested return, and the pool discarded the connection | CONFIRMED on both drivers; CHK-3 | 4 (A5, B3) | READY_FOR_HUMAN_REVIEW | The author writes the discussion or docs PR from CHK-3's [`FACTS.md`](python-upstream-contribution/chk-3-sa-reset-recipe/FACTS.md) |
| PY-6 | asyncpg | `SET ROLE` survives `Connection.reset()` | CONFIRMED | 5 (A4, B7) | READY_FOR_HUMAN_REVIEW | Write and run the standalone script; draft the issue |
| PY-8 | Tortoise ORM | COMMIT-time integrity errors are not translated | CONFIRMED on asyncpg, psycopg and SQLite; the fix runs on a local branch | 6 (A8, B2) | READY_FOR_HUMAN_REVIEW | Draft the PR text and commit message for approval; the user forks, pushes and opens the PR |
| PY-7 | SQLAlchemy | P5a: after a failed `commit()`, `close()` returns the connection with its transaction open | CONFIRMED; CHK-7 reproduced it on 2.1.6 | 7 (A6, B6) | READY_FOR_HUMAN_REVIEW | CHK-7 is done. The author writes and posts, using CHK-7's `FACTS.md` (see PY-7) |
| PY-4 | SQLAlchemy | `after_rollback` fires after a root `COMMIT` that raised, also when PostgreSQL committed: a cancelled `COMMIT` (P3, P8) or a lost reply (CHK-4) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN; CHK-4 reproduced it with no cancellation | 8 (A7, B8) | READY_FOR_HUMAN_REVIEW | After P5a's reception, the author writes the discussion from CHK-4's [`FACTS.md`](python-upstream-contribution/chk-4-sa-lost-commit-reply/FACTS.md) |
| PY-9 | SQLAlchemy | ORM `after_commit` fires on an aborted transaction (Draft C) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | — | DEFERRED | Revisit after PY-1 and PY-2 |
| PY-10 | Django | `atomic()` and `on_commit` | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
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

## Scheduled items

### PY-1a: psycopg `Connection.commit()`

- **Project:** psycopg 3.3.6. `master` `99356800e` is unchanged.
- **Finding:** `commit()` returns `None` when PostgreSQL completes `COMMIT` with tag `ROLLBACK`.
- **Evidence:**
  - `research/production-reachability/reproductions/psycopg_commit_tag.{py,txt}`;
  - `reports/examples/2026-10-19T12-35-51Z-64c5c5`;
  - `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` and `…20-58-26Z-508b7a`;
  - A2 P6.
- **Upstream:** [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21. Open, no comments, no labels. Re-checked 2026-10-24 at about 16:20 UTC: also no timeline events and no reactions.
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
  - psycopg's docs tell callers to roll back after an error.
  - `tests/test_connection_async.py:401` asserts that `commit()` returns.
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
- **Next concrete step:** wait for a reply. If #1453 is still silent around 2026-11-07, send one polite follow-up. Decide around 2026-11-21 (roadmap §14).

### PY-2: asyncpg `Transaction.commit()` and `async with conn.transaction()`

- **Project:** asyncpg 0.32.0, still the latest release. `master` `13b01910d` is unchanged (re-checked 2026-10-24). Its `asyncpg/transaction.py` is byte-identical to 0.32.0's, and unchanged since 2023-05-30.
- **Finding:** both return normally, with internal state `committed`, after PostgreSQL answers `COMMIT` with `ROLLBACK`. Raw `execute('COMMIT')` returns `'ROLLBACK'`. Tortoise and SQLAlchemy's asyncpg dialect inherit this.
- **Evidence:**
  - **CHK-2,** [`python-upstream-contribution/chk-2-asyncpg/`](python-upstream-contribution/chk-2-asyncpg/README.md). This is the standalone program to post, run three times on asyncio and three on uvloop; all six agreed. `psql` and the server's statement log agree for all 24 transactions. After `commit()` has returned, asyncpg's own `rollback()` raises "the transaction is already committed", a public-API signal;
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
- **Next concrete step:** wait for a reply. If #1400 is still silent around 2026-11-07, send one polite follow-up. Decide around 2026-11-21 (roadmap §14). Expect a slow reply (see "Receptiveness").

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
  - Src: `asyncpg/connection.py:1567-1594` and `1763-1790`; `asyncpg/pool.py:1320-1340`.
- **Upstream:** none for the role (2026-10-24). Temp tables are #1293, and PR #1392 (open, unreviewed) uses a capability-gated reset statement. #270 rejects `DISCARD ALL`.
- **Confidence:** CONFIRMED.
- **Priority:** 5.
- **Proposed action:** an issue proposing `RESET ROLE` behind a capability, or a corrected docstring. Include the compatibility note on `init`-time roles (roadmap §10.5).
- **Prerequisites:** run the script to be posted three times, on a non-superuser login. CHK-6 is optional.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** write the standalone script (pool of one: `SET ROLE`, release, acquire, `current_user`).

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
- **Upstream:** none found.
  - Re-checked 2026-10-25 for 2026-10-18 onward, with the review's twelve issue queries and five replacement discussion queries; no matching item was found.
  - #13699 (fixed in 2.1.6) touches `Connection.close()`, but it is a cancellation during the reset, not P5a.
  - Precedent: #13381, fixed.
- **Confidence:** CONFIRMED for a `commit()` that fails before sending, on a healthy connection. The demonstrated triggers that replace no DBAPI method are a raising commit listener, and mixing psycopg's and SQLAlchemy's transaction APIs. Reachability through ordinary driver or OS failures, and production frequency, are not established.
- **Priority:** 7. It is ready, and can move earlier if the author prefers. Leave time after PY-5.
- **Proposed action:** a Usage Questions discussion, written by the author in their own words. The venue was decided on 2026-10-18.
- **Prerequisites:** CHK-7 and a fresh duplicate search, both done 2026-10-25 (UTC).
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
- **Upstream:** none found. Precedent: #12728. Not re-checked for CHK-4.
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
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

All `output/` paths are under `research/python-production-failure-gap-analysis/`, except PY-20's.

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
