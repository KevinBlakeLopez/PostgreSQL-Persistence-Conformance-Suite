Written by: GPT-6 / Codex (effort setting not exposed)
Date: 2026-10-24 (America/Los_Angeles)

# Recheck of the revised drafts

| Text | Current verdict | Basis |
| --- | --- | --- |
| PY-1b | **READY** — INFERRED judgment | The coverage claim, savepoint description, database-drop disclosure, and pipeline scope have been corrected. New retained evidence supports the added pipeline-pattern observation. |
| PY-2 | **READY** — INFERRED judgment | The compatibility question now acknowledges the existing timeout test. Commands, downstream bounds, folded output, and setup disclosure address the earlier findings. |

**VERIFIED — scope.** This recheck concerns the revised working-tree files, not the original versions reviewed in REVIEW.md. HEAD remains `905e797e610335c4dd3fd513dfb34181231f9a43`, but the drafts now differ from that commit. The original review remains historical. No draft or existing evidence was edited by this recheck; no issue/comment was posted, database contacted, experiment executed, or upstream test run.

**VERIFIED — reviewed file identities.** Full-file SHA-256 values, including internal notes:

| Draft | SHA-256 |
| --- | --- |
| psycopg-1453-comment.md | `75511ea0f60fbbf12fb01f00cc6a9c31b9a4b13caef11e12357ec74378995b18` |
| asyncpg-commit-rollback.md | `5eecbf8ffacafc8eef47ca529746338b6de037e0f18e8e6424be55a76dc9dbd6` |

# Resolution of the previous findings

| Finding | Recheck |
| --- | --- |
| Incorrect no-tests claims | VERIFIED resolved. PY-1b line 98 names `test_outer_transaction_error`; PY-2 line 340 names `test_timeout_06` and explicitly asks maintainers to decide completion semantics. Both source references match the pinned upstream tests. |
| Initial database drop understated | VERIFIED resolved. PY-1b line 107 and PY-2 line 114 disclose the initial drop of any existing same-named database and direct readers to a disposable server. |
| Non-pasteable asyncpg command | VERIFIED resolved. PY-2 lines 117–118 give separate literal `asyncio` and `uvloop` arguments; the `|` usage notation remains only inside the preserved historical docstring. |
| Savepoint catch scope | VERIFIED resolved. PY-1b line 87 places the failing insert inside the inner block and the catch just outside it. |
| Downstream generalization | VERIFIED resolved. PY-2 line 338 identifies Tortoise 1.1.9 `in_transaction()` and SQLAlchemy Core 2.1.5 `engine.begin()`, on asyncpg 0.32.0, for caught 23505. Those are the recorded paths and versions. |
| Expanded long asyncpg output | VERIFIED resolved. The output is now inside a second balanced `<details>` block. Both drafts communicate their result before the folded code/output. |

**VERIFIED — artifact preservation.** The posted program/output pairs still match the original evidence bytes exactly: psycopg 4,571/2,189 bytes; asyncpg 5,987/1,233 bytes. Their hashes are unchanged from REVIEW.md. The extra-SQLSTATE bullet is absent from the posted asyncpg region. Both PR offers remain conditional, and the untested async, open-pipeline COMMIT, and COMMIT-raises cases are not represented as tested.

# New and changed claim checks

| Claim | Status and evidence |
| --- | --- |
| Psycopg's pipeline-pattern run starts from a non-autocommit connection like the test fixture | VERIFIED source comparison. `psycopg-pipeline-test-check/psycopg_pipeline_outer_error.py:35–51`; upstream `tests/fix_db.py:199–206` uses `conn_cls.connect(...)` without enabling autocommit. Upstream test body is `tests/test_pipeline.py:506–511`. |
| The pipeline error is caught inside the outer transaction, before its COMMIT | VERIFIED source comparison. The standalone program's pipeline is inside `try/except`, nested in `with conn.transaction()`. The pipeline has exited before the outer context sends COMMIT. |
| New run has INERROR, normal exit and committed status | VERIFIED against retained output: six arms, three unmarked and three witnessed. `output/psycopg_pipeline_outer_error.out:3–50` reports INERROR, no exit exception, committed status and IDLE afterward in every arm. |
| PostgreSQL aborted and discarded the marker | VERIFIED against recorded witness values in the three witnessed arms, output lines 24–50. The subject stays open until after the separate autocommit witness queries, program lines 61–67. The unmarked arms do not capture a transaction ID or marker outcome. |
| New server log supports that sequence | VERIFIED six distinct subject sessions. Every session has one `column "error" does not exist` error followed by COMMIT; no `create table voila` execution is logged. Witnessed-session IDs 755,756,757 occur in the retained log. The log is a subject-session excerpt, not the complete original server log or a CommandComplete trace. |
| A status-only change would not conflict with either cited psycopg test | VERIFIED as a narrow source observation: neither `test_auto_transaction_fail` nor `test_outer_transaction_error` asserts `Transaction.status`. NOT CHECKED against an implemented candidate fix or the full upstream suite. This does not promise compatibility with all applications or all tests. |
| Psycopg's new “Not run” wording is accurate | VERIFIED against program scope. The new run uses a pipeline, but sends COMMIT after leaving it; it does not test COMMIT queued while a pipeline remains open. No async transaction run is supplied. |
| Asyncpg's timeout test expects normal outer exit | VERIFIED pinned source `tests/test_timeout.py:104–113`: catches TimeoutError, then InFailedSQLTransactionError inside the block, and checks SELECT 1 afterward. No newly executed asyncpg test is claimed. |
| Asyncpg #1130 asks to expose transaction state | VERIFIED fresh public issue body requests a public started/committed/aborted state interface. It is open with zero comments. The new local shorthand link points to that issue. |
| New evidence hashes match README | VERIFIED all three recomputed: program `ddfdcc36e25235c8a269ee23d651c649ed3d08549df7dd77b5f8c51b81dc2540`; output `4a44bf998bdca14f5162b98773d7d60bfaed08bf77bd5ff92ae3e390bd68999e`; log excerpt `8e4395a7d449d01b35e137b1fab3e7715f98b5ead88681e7c0a5ce6753fb963a`. |

**INFERRED — one optional precision edit, not a blocker.** PY-1b line 98 says “When I ran its body”. The standalone script replaces `pytest.raises` with `try/except` and adds observation code; the upstream pytest test itself was not run. “When I reproduced its pattern” describes that provenance more precisely. The actual error-handling/transaction sequence is preserved, and the new run supports the stated observation.

# Refreshed upstream checks and limits

**VERIFIED — fresh unauthenticated public REST checks.** Psycopg `master` remains `99356800e90aa0e7b604f652d714ef0f33422b47`; asyncpg `master` remains `13b01910da3fe01b8241c31cc86eccb1301a2d39`. Therefore the independently downloaded source trees still represent the current heads, and the newly cited pinned test ranges were checked in those trees. Psycopg#1453 remains open, zero comments, updated 2026-10-22T00:52:41Z. Its current body still lacks the new transaction-context/status example.

**VERIFIED — repeated duplicate queries.** `repo:psycopg/psycopg commit rollback` returned 40 results; `repo:MagicStack/asyncpg commit rollback` returned 16. Both used `/search/issues?per_page=100&q=...`, all states, and returned `incomplete_results:false`; their result-number sets are unchanged from the first review. INFERRED: no new duplicate was found by these repeated queries.

**NOT CHECKED — unchanged limits.** This focused recheck did not repeat the full ten-query search, Discussions sweep, PyPI query, or policy inventory from the earlier review. It did not reconstruct original wheel/image/OS provenance, rerun the new pipeline experiment, run either upstream test suite, or test any proposed fix. The new pipeline run's versions are recorded Python 3.13.11, psycopg 3.3.6 binary/libpq 180006, PostgreSQL 18.6; they are historical recording values, not versions of a new reviewer execution. No existing recording was overwritten.

**INFERRED — conclusion.** The revised posts address the verified objections from the first review and do not require further substantive changes before the author's normal approval/posting decision. READY is a review verdict, not permission to publish or a prediction that maintainers will accept a behavior change.
