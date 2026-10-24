# Python upstream contribution tracker

Started: 2026-10-24. Updated the same day, after CHK-2 and the PY-1b and PY-2 drafts. Written by: Claude Opus 5.5 (max).

This is the working tracker for [`python-upstream-contribution-roadmap.md`](python-upstream-contribution-roadmap.md). The roadmap holds the reasoning, the fixes, and the test designs. This file holds only the status and the next step for each item.

- **Nothing here is filed unless its row links a filing.** Only PY-1a is filed: psycopg#1453, verified on GitHub on 2026-10-24.
- **The filing log is still [`docs/upstream-submissions.md`](../docs/upstream-submissions.md).** PY-1a is its P1. When an item is posted, record it there, and update the row here.
- **Every post needs approval** of its exact text and destination (`AGENTS.md` rule 9).
- **SQLAlchemy text must be written by its author,** in their own words. No agent posts there.

## Status key

| Status | Meaning |
| --- | --- |
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
| PY-1b | psycopg | `transaction()` exits normally, and `Transaction.status` is `committed`, after an abort | CONFIRMED | 1 (A1, B1) | AWAITING_APPROVAL | Approve the comment in `upstream-drafts/psycopg-1453-comment.md`. Then run its pre-post checks and post |
| PY-2 | asyncpg | `Transaction.commit()` and `async with` report success after `COMMIT` is answered `ROLLBACK` | CONFIRMED; CHK-2 reproduced it on asyncio and uvloop | 2 (A2, B5) | AWAITING_APPROVAL | Approve the issue in `upstream-drafts/asyncpg-commit-rollback.md`. Then run its pre-file checks and file |
| PY-3 | Tortoise ORM | A retried `save()` after a rollback writes nothing and returns normally | CONFIRMED | 3 (A3, B4) | READY_FOR_HUMAN_REVIEW | Run CHK-5 (a, b), then draft the issue |
| PY-5 | SQLAlchemy (docs) | The documented PostgreSQL reset recipe resets nothing on psycopg 3 | CONFIRMED on psycopg 3 | 4 (A5, B3) | NEEDS_VERIFICATION | Run CHK-3, then hand the evidence package to the author |
| PY-6 | asyncpg | `SET ROLE` survives `Connection.reset()` | CONFIRMED | 5 (A4, B7) | READY_FOR_HUMAN_REVIEW | Write and run the standalone script; draft the issue |
| PY-8 | Tortoise ORM | COMMIT-time integrity errors are not translated | CONFIRMED | 6 (A8, B2) | READY_FOR_HUMAN_REVIEW | Prepare the PR and its test; run the touched backends locally |
| PY-7 | SQLAlchemy | P5a: after a failed `commit()`, `close()` returns the connection with its transaction open | CONFIRMED | 7 (A6, B6) | READY_FOR_HUMAN_REVIEW | Run CHK-7. The author then writes and posts |
| PY-4 | SQLAlchemy | `after_rollback` fires after a cancelled `COMMIT` that PostgreSQL then commits | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | 8 (A7, B8) | NEEDS_VERIFICATION | Run CHK-4, or PP-3 |
| PY-9 | SQLAlchemy | ORM `after_commit` fires on an aborted transaction (Draft C) | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | — | DEFERRED | Revisit after PY-1 and PY-2 |
| PY-10 | Django | `atomic()` and `on_commit` | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-11 | psycopg_pool, SQLAlchemy pools, Django | Session state carries over by default | NOT A DEFECT | — | CLOSED_NO_ACTION | — |
| PY-12 | Several | `57014`, `40P01`, `40001` on the caught-then-commit path | CONFIRMED; no new defect | — | CLOSED_NO_ACTION | Cited in the PY-2 draft. Left out of PY-1b (see its row below) |
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
  - Doc: `docs/basic/transactions.rst`, lines 158–162 and 347–350.
- **Upstream:** not in #1453. #967 has the maintainer's statement that a normal exit means a commit. #969 and PR #1184 added `status`.
- **Confidence:** CONFIRMED.
- **Priority:** 1.
- **Proposed action:** a follow-up comment on #1453 (roadmap §10.1). Offer tests or a PR, conditionally.
- **Draft:** [`python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md`](python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md). Not posted. About 29 visible lines, with the program and its output in `<details>`; both are byte-identical to the audit's evidence files. It covers:
  - the second surface;
  - the documented block contract and `status` ("final outcome", "retry logic");
  - why a fix in `Connection.commit()` alone does not reach the block: `BaseTransaction._commit_gen` calls `_exec_command` itself and sets `COMMITTED` before sending `COMMIT`;
  - the `test_auto_transaction_fail` qualification;
  - what was not run;
  - a conditional offer of tests or a PR.
- **Left out of the draft:** PY-12's SQLSTATEs. Their evidence goes through SQLAlchemy Core, that is `Connection.commit()`, not `transaction()`. This departs from PY-12's earlier "cite in the PY-1b and PY-2 texts". One line can add them if wanted.
- **Prerequisites:** #1453 and `master` were re-checked on 2026-10-24. CHK-1 was not run; it is optional. Repeat the draft's pre-post checks on the day of posting.
- **Status:** AWAITING_APPROVAL
- **Next concrete step:**
  1. Approval of the exact text and destination.
  2. The draft's pre-post checks.
  3. The post.
  4. Record it in `docs/upstream-submissions.md`.

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
- **Draft:** [`python-upstream-contribution/upstream-drafts/asyncpg-commit-rollback.md`](python-upstream-contribution/upstream-drafts/asyncpg-commit-rollback.md). Not filed. It contains:
  - the template's fields;
  - the program, in `<details>`, and its asyncio output, byte-identical to the CHK-2 files;
  - the expected and actual behaviour;
  - the line where the status is dropped (`asyncpg/transaction.py` 186–192 at `13b01910d`);
  - one line each on the other SQLSTATEs (PY-12), the downstream callers, #1453, and compatibility;
  - a conditional PR offer.
- **Prerequisites:** done on 2026-10-24: CHK-2, the duplicate search, and the template. Repeat the draft's pre-file checks on the day of filing. A new asyncpg release means re-running the program first.
- **Status:** AWAITING_APPROVAL
- **Next concrete step:**
  1. Approval of the exact title, body and destination.
  2. The draft's pre-file checks.
  3. Filing.
  4. Record it in `docs/upstream-submissions.md`.

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
| PY-12 | `output/p6.jsonl`, `output/p6.server-log-endings.txt` | — | Cited as further triggers in the PY-2 draft. Left out of PY-1b: the evidence went through `Connection.commit()`, not `transaction()` | — | CLOSED_NO_ACTION | — |
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
| CHK-1 | PY-1b | Optional | NOT_STARTED. Not run for the PY-1b draft |
| CHK-2 | PY-2 | Required before posting | DONE 2026-10-24. Reproduced, with no discrepancy from P1: [`python-upstream-contribution/chk-2-asyncpg/`](python-upstream-contribution/chk-2-asyncpg/README.md) |
| CHK-3 | PY-5 | Required | NOT_STARTED |
| CHK-4 | PY-4 | Required (or PP-3) | NOT_STARTED |
| CHK-5 | PY-3 | Recommended before the issue; required before a PR | NOT_STARTED |
| CHK-6 | PY-6 | Optional | NOT_STARTED |
| CHK-7 | PY-7 | Required | NOT_STARTED |

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

## Evidence preservation (PP-1)

**Status on 2026-10-24: prepared, not committed.**

- Committing needs the maintainer's approval (`AGENTS.md` rule 13, and the roadmap's PP-1 gate).
- Nothing is staged, because the main checkout's index is shared with other sessions.

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
- **A departure from this tracker.** PY-12 is cited in the PY-2 draft only.
- **Blockers.**
  - Approval of the exact PY-1b comment, the PY-2 issue, and their destinations.
  - Approval to commit (PP-1).

## Change log

- **2026-10-24.** Tracker created from the roadmap. Upstream re-checked the same day: only psycopg#1453 is filed, and nothing else in this tracker is posted.
- **2026-10-24, later.**
  - Ran CHK-2, which reproduced the result.
  - Drafted the PY-1b comment and the PY-2 issue; neither is posted or filed.
  - Re-checked upstream: #1453 unchanged; no asyncpg duplicate; both default branches unchanged.
  - Prepared the PP-1 commits, not made.
  - PY-1b and PY-2 moved to AWAITING_APPROVAL.
