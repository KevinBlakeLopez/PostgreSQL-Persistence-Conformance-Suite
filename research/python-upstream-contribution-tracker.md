# Python upstream contribution tracker

Started: 2026-10-24. Written by: Claude Opus 5.5 (max).

This is the working tracker for [`python-upstream-contribution-roadmap.md`](python-upstream-contribution-roadmap.md). The roadmap holds the reasoning, the fixes, and the test designs. This file holds only the status and the next step for each item.

- **Nothing here is filed unless its row links a filing.** Only PY-1a is filed: psycopg#1453, verified on GitHub on 2026-10-24.
- **The filing log is still [`docs/upstream-submissions.md`](../docs/upstream-submissions.md).** PY-1a is its P1. When an item is posted, record it there, and update the row here.
- **Every post needs approval** of its exact text and destination (`AGENTS.md` rule 9).
- **SQLAlchemy text must be written by its author,** in their own words. No agent posts there.

## Status key

| Status | Meaning |
| --- | --- |
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
| PY-1b | psycopg | `transaction()` exits normally, and `Transaction.status` is `committed`, after an abort | CONFIRMED | 1 (A1, B1) | READY_FOR_HUMAN_REVIEW | Draft the #1453 comment from the roadmap §10.1 outline |
| PY-2 | asyncpg | `Transaction.commit()` and `async with` report success after `COMMIT` is answered `ROLLBACK` | CONFIRMED | 2 (A2, B5) | READY_FOR_HUMAN_REVIEW | Run CHK-2, then draft the issue |
| PY-3 | Tortoise ORM | A retried `save()` after a rollback writes nothing and returns normally | CONFIRMED | 3 (A3, B4) | READY_FOR_HUMAN_REVIEW | Run CHK-5 (a, b), then draft the issue |
| PY-5 | SQLAlchemy (docs) | The documented PostgreSQL reset recipe resets nothing on psycopg 3 | CONFIRMED on psycopg 3 | 4 (A5, B3) | NEEDS_VERIFICATION | Run CHK-3, then hand the evidence package to the author |
| PY-6 | asyncpg | `SET ROLE` survives `Connection.reset()` | CONFIRMED | 5 (A4, B7) | READY_FOR_HUMAN_REVIEW | Write and run the standalone script; draft the issue |
| PY-8 | Tortoise ORM | COMMIT-time integrity errors are not translated | CONFIRMED | 6 (A8, B2) | READY_FOR_HUMAN_REVIEW | Prepare the PR and its test; run the touched backends locally |
| PY-7 | SQLAlchemy | P5a: after a failed `commit()`, `close()` returns the connection with its transaction open | CONFIRMED | 7 (A6, B6) | READY_FOR_HUMAN_REVIEW | Run CHK-7. The author then writes and posts |
| PY-4 | SQLAlchemy | `after_rollback` fires after a cancelled `COMMIT` that PostgreSQL then commits | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | 8 (A7, B8) | NEEDS_VERIFICATION | Run CHK-4, or PP-3 |
| PY-9 | SQLAlchemy | ORM `after_commit` fires on an aborted transaction (Draft C) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | — | DEFERRED | Revisit after PY-1 and PY-2 |
| PY-10 | Django | `atomic()` and `on_commit` | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-11 | psycopg_pool, SQLAlchemy pools, Django | Session state carries over by default | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-12 | Several | `57014`, `40P01`, `40001` on the caught-then-commit path | CONFIRMED; no new defect | — | CLOSED_NO_ACTION | Cite in the PY-1b and PY-2 texts |
| PY-13 | psycopg | `AsyncConnectionPool`: a level-cancelled `COMMIT` completes after the API returned | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-14 | Django | A documentation note that the native pool does not reset session state | Optional | — | DOCUMENTATION_ONLY | Not scheduled. Check Django's contribution policy first |
| PY-15 | SQLAlchemy | Draft A (SA-03): a failed `rollback()`, then reuse | Ext | — | DEFERRED | After P5a's reception |
| PY-16 | SQLAlchemy | Draft B (SA-02): a failed savepoint rollback is caught, then committed | Ext; no trigger | — | CLOSED_NO_ACTION | — |
| PY-17 | Django | Migration locking (MG-02) | PPCS | — | DOCUMENTATION_ONLY | Optional forum note. Not scheduled |
| PY-18 | Django | TX-02 not-sent | PPCS; no trigger | — | CLOSED_NO_ACTION | Keep in PPCS |
| PY-19 | Tortoise ORM | Rollback skipped after a class-25 error in a nested block | Src only | — | DEFERRED | Mention only if the PY-8 discussion invites it |

## Scheduled items

### PY-1a: psycopg `Connection.commit()`

- **Project:** psycopg 3.3.6. `master` `99356800e` is unchanged.
- **Finding:** `commit()` returns `None` when PostgreSQL completes `COMMIT` with tag `ROLLBACK`.
- **Evidence:**
  - `research/production-reachability/reproductions/psycopg_commit_tag.{py,txt}`;
  - `reports/examples/2026-10-19T12-35-51Z-64c5c5`;
  - `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` and `…20-58-26Z-508b7a`;
  - A2 P6.
- **Upstream:** [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21. Open, no comments, no labels (2026-10-24).
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
  - psycopg's docs tell callers to roll back after an error.
  - `tests/test_connection_async.py:401` asserts that `commit()` returns.
- **Priority:** severity rank 1. The action now is PY-1b.
- **Proposed action:** none beyond PY-1b. No new issue, and no reports to SQLAlchemy or Django.
- **Prerequisites:** —
- **Status:** UPSTREAM_ALREADY_TRACKED
- **Next concrete step:** let PY-1b's comment carry the compatibility note. Then follow the follow-up rule (roadmap §14).

### PY-1b: psycopg `Connection.transaction()` and `Transaction.status`

- **Project:** psycopg 3.3.6. `master` `99356800e` is unchanged.
- **Finding:** the block exits normally, and `tx.status` is `committed`, while PostgreSQL aborted. This contradicts the documented block contract and the `status` docs ("final outcome", "retry logic").
- **Evidence:**
  - `research/python-ecosystem-contribution-audit/psycopg_transaction_block.{py,txt}`: three repetitions, with a savepoint control;
  - Src: `transaction.py:133-140`;
  - Doc: `docs/basic/transactions.rst`, lines 159–162 and 347–350.
- **Upstream:** not in #1453. #967 has the maintainer's statement that a normal exit means a commit. #969 and PR #1184 added `status`.
- **Confidence:** CONFIRMED.
- **Priority:** 1.
- **Proposed action:** a follow-up comment on #1453 (roadmap §10.1). Offer tests or a PR, conditionally.
- **Prerequisites:** re-check #1453 and `master` on the day. CHK-1 is optional.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** draft about 30–40 visible lines, with Appendix A in `<details>`, and get the exact text approved.

### PY-2: asyncpg `Transaction.commit()` and `async with conn.transaction()`

- **Project:** asyncpg 0.32.0. `master` `13b01910d` is unchanged.
- **Finding:** both return normally, with internal state `committed`, after PostgreSQL answers `COMMIT` with `ROLLBACK`. Raw `execute('COMMIT')` returns `'ROLLBACK'`. Tortoise and SQLAlchemy's asyncpg dialect inherit this.
- **Evidence:**
  - `research/python-production-failure-gap-analysis/output/p1.out` (arms A–D);
  - `output/p6.jsonl` and `output/p6.server-log-endings.txt`;
  - `reports/examples/2026-10-19T12-45-38Z-c45624` (Tortoise TX-01A; trace `COMMIT; -> ROLLBACK`);
  - Src: `asyncpg/transaction.py:175-192`.
- **Upstream:** none found (2026-10-24). Related: #1130, #1386.
- **Confidence:** CONFIRMED.
- **Priority:** 2.
- **Proposed action:** a new issue in the shape of #1453, with a conditional PR offer (roadmap §10.2).
- **Prerequisites:**
  - CHK-2: the exact standalone script, run three times, on asyncio and on uvloop;
  - a fresh duplicate search;
  - the fields of asyncpg's issue template.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** extract P1's asyncpg arms into a standalone script, and run CHK-2.

### PY-3: Tortoise `Model.save()` after a rolled-back transaction

- **Project:** Tortoise ORM 1.1.9. `develop` `536fc3abd` is unchanged.
- **Finding:** after a rolled-back `save()`, `_saved_in_db` stays True. The retried `save()` returns normally, and 0 rows persist.
- **Evidence:**
  - `research/python-production-failure-gap-analysis/output/p45.rep{1,2,3}.out` (`p4_tortoise`; Django and SQLAlchemy as controls);
  - Src: `tortoise/models.py:1176-1194`.
- **Upstream:** none. #1094 shares only the symptom. #1212 bears on the fix (`force_update` sees 0 rows on MySQL).
- **Confidence:** CONFIRMED. The mechanism is Src.
- **Priority:** 3.
- **Proposed action:** an issue that asks for the fix direction: restoring state on rollback, or handling zero-row updates. Then a PR (roadmap §7 and §10.3).
- **Prerequisites:** CHK-5 (a) and (b). Recommended before the issue; required before a PR.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** run CHK-5, then draft the issue with a standalone script.

### PY-5: SQLAlchemy PostgreSQL reset-on-return recipe

- **Project:** SQLAlchemy documentation. 2.1.5 `dialects/postgresql/base.py:277-336`, unchanged on `main` `10f4d1e2d`.
- **Finding:** on psycopg 3 the recipe resets nothing. Role, GUC, `search_path`, `statement_timeout` and temp tables all carry over. Its URL is psycopg2's, but its calls are psycopg 3's.
- **Evidence:**
  - `research/python-production-failure-gap-analysis/p7_sa_reset_recipe.py` and `output/p7.rep{1,2,3}.out`;
  - the psql checks in that directory's README;
  - Src: `pool/base.py:1043-1053` and `1451-1467`;
  - the page's own search-path note (`base.py:340-372`).
- **Upstream:** none found (issues and discussions, 2026-10-24).
- **Confidence:** CONFIRMED on psycopg 3. psycopg2 is a HYPOTHESIS (H-d).
- **Priority:** 4.
- **Proposed action:** a corrected example: roll back, then `DISCARD ALL` in autocommit, restoring autocommit afterwards, with notes on scope (roadmap §7). The author writes the discussion or docs PR.
- **Prerequisites:** CHK-3. The author writes every word of the prose.
- **Status:** NEEDS_VERIFICATION
- **Next concrete step:** run CHK-3: the statement log, psycopg2, and the corrected example on both drivers.

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

- **Project:** Tortoise ORM 1.1.9. `develop` `536fc3abd`.
- **Finding:** `commit()` and `rollback()` lack `translate_exceptions`; `begin()` has it. A deferred-FK violation at `COMMIT` therefore arrives as a raw `asyncpg.exceptions.ForeignKeyViolationError`.
- **Evidence:**
  - `research/python-production-failure-gap-analysis/output/p45.rep{1,2,3}.out` (`p5_tortoise`);
  - Src: `tortoise/backends/asyncpg/client.py:189-208`, and the same pattern in the psycopg, MySQL, SQLite and ODBC clients.
- **Upstream:** none found.
- **Confidence:** CONFIRMED.
- **Priority:** 6. It is independent of PY-3 and can be done at any time.
- **Proposed action:** a PR that adds translation to `commit()` and `rollback()` in each backend, with a deferred-FK test. The description asks whether the omission was deliberate.
- **Prerequisites:** run Tortoise's test suite locally for the touched backends.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** a branch from `develop`, the change, the test, and the local runs.

### PY-7: SQLAlchemy P5a (failed `commit()`, then `close()`)

- **Project:** SQLAlchemy Core, 1.4.0 to 2.1.5. `RootTransaction` on `main` `10f4d1e2d` is unchanged. 2.1.6 has not been run.
- **Finding:** `close()` sends no ROLLBACK, and `transaction_was_reset` is True while the transaction is open. The next checkout commits the doomed writes.
- **Evidence:** `../python-orm-transactions/docs/sqlalchemy-p5a-close-review.md` and `check/p5a_close_v2.{py,out}` (Ext; commit `cca9b98`, on that repository's `origin/main`).
- **Upstream:** none found (2026-10-18). Precedent: #13381, fixed.
- **Confidence:** CONFIRMED. Reachability is limited to a commit listener that raises, or to mixing APIs.
- **Priority:** 7. It is ready, and can move earlier if the author prefers. Leave time after PY-5.
- **Proposed action:** a Usage Questions discussion, written by the author in their own words. The venue was decided on 2026-10-18.
- **Prerequisites:** CHK-7, and a fresh duplicate search.
- **Status:** READY_FOR_HUMAN_REVIEW
- **Next concrete step:** run CHK-7 on 2.1.6.

### PY-4: SQLAlchemy `after_rollback` during a cancelled `COMMIT`

- **Project:** SQLAlchemy 2.1.5 and 2.1.6 ORM. `main` `10f4d1e2d` is unchanged.
- **Finding:** under anyio level-triggered cancellation, `after_rollback` fires. PostgreSQL then commits.
- **Evidence:**
  - `research/python-production-failure-gap-analysis/p3_cancellation.py` and `output/p3.jsonl`, `p3b.jsonl`, `p3c-sa216.jsonl`;
  - Src: `orm/session.py:1377-1380` and `engine/base.py:2697-2742`. This code path is shared with PY-7.
- **Upstream:** none found. Precedent: #12728.
- **Confidence:** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.
- **Priority:** 8.
- **Proposed action:** a documentation clarification; a change to event delivery is optional (roadmap §7). The author writes a discussion.
- **Prerequisites:**
  - CHK-4, or PP-3: does a lost `COMMIT` reply give the same claim?
  - P5a's reception.
- **Status:** NEEDS_VERIFICATION
- **Next concrete step:** run CHK-4.

## Unscheduled items

| ID | Evidence location | Existing issue or PR | Proposed action | Prerequisites | Status | Next concrete step |
| --- | --- | --- | --- | --- | --- | --- |
| PY-9 | `output/p1.out` (F, G); Ext `run-2.txt` | — | None while PY-1 and PY-2 are open | The outcome of PY-1 and PY-2 | DEFERRED | Revisit if both drivers decline |
| PY-10 | PPCS `6d8443`, `b2c174`; A2 P5, P6; Ext arm 4b | — | None | — | CLOSED_NO_ACTION | — |
| PY-11 | `output/p2.rep*.out` | psycopg Discussion #893 | None | — | CLOSED_NO_ACTION | — |
| PY-12 | `output/p6.jsonl`, `output/p6.server-log-endings.txt` | — | Cite as further triggers in PY-1b and PY-2 | — | CLOSED_NO_ACTION | — |
| PY-13 | `output/p3.jsonl` (psycopg rows); psycopg `docs/advanced/async.rst:200-204` | — | None | — | CLOSED_NO_ACTION | — |
| PY-14 | `output/p2.rep*.out` (Django native pool) | — | Optional documentation note | Django's contribution policy | DOCUMENTATION_ONLY | Not scheduled |
| PY-15 | Ext `lifecycle-close-reuse.md`, `run-2.txt` | — | Author-written, after P5a | PY-7's reception | DEFERRED | — |
| PY-16 | PPCS `3673a3`, `64c5c5`; Ext `run-2.txt` | — | None without a production trigger | — | CLOSED_NO_ACTION | — |
| PY-17 | PPCS `reports/examples/2026-10-21T20-00-04Z-178fa4` | Django #30490, #34610 | Optional forum note | — | DOCUMENTATION_ONLY | Not scheduled |
| PY-18 | PPCS `6d8443` | — | None | — | CLOSED_NO_ACTION | Keep in PPCS |
| PY-19 | Src: `tortoise/backends/asyncpg/client.py:96-97`, `backends/base/client.py` (exits) | — | None | A run that shows a consequence | DEFERRED | — |

All `output/` paths are under `research/python-production-failure-gap-analysis/`.

## Verification checks

The designs are in the roadmap §11. Each check needs its own throwaway container. Never use `ppcs-postgres` or `pnpm run pg:up`.

| ID | Unblocks | Required? | Status |
| --- | --- | --- | --- |
| CHK-1 | PY-1b | Optional | NOT_STARTED |
| CHK-2 | PY-2 | Required before posting | NOT_STARTED |
| CHK-3 | PY-5 | Required | NOT_STARTED |
| CHK-4 | PY-4 | Required (or PP-3) | NOT_STARTED |
| CHK-5 | PY-3 | Recommended before the issue; required before a PR | NOT_STARTED |
| CHK-6 | PY-6 | Optional | NOT_STARTED |
| CHK-7 | PY-7 | Required | NOT_STARTED |

## Change log

- **2026-10-24.** Tracker created from the roadmap. Upstream re-checked the same day: only psycopg#1453 is filed, and nothing else in this tracker is posted.
