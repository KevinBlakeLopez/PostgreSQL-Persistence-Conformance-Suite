# Python upstream contribution roadmap

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

**Corrected later on 2026-10-24.** An outside adversarial review found two false claims about upstream tests. The passages are corrected in place, each marked "(corrected 2026-10-24)". The earlier search looked only for `try`/`except`. It missed tests that catch with `pytest.raises` or `assertRaises`.

- **psycopg.** `tests/test_pipeline.py::test_outer_transaction_error`, and its async copy, catches a database error inside `transaction()` and expects the block to exit normally. A run of its pattern found the transaction aborted and `status` reading `committed` ([`python-upstream-contribution/psycopg-pipeline-test-check/`](python-upstream-contribution/psycopg-pipeline-test-check/README.md)). So a `transaction()` fix that raises conflicts with that test, and a fix that only corrects `status` does not.
- **asyncpg.** `tests/test_timeout.py::test_timeout_06`, and `test_timeout_04`, exit a transaction block normally after a caught error that aborted it. A fix that raises conflicts with them.

This roadmap orders the upstream contributions that PPCS's Python research supports. It synthesizes two completed investigations:

- [`python-ecosystem-contribution-audit.md`](python-ecosystem-contribution-audit.md), "the audit";
- [`python-production-failure-gap-analysis.md`](python-production-failure-gap-analysis.md), "the gap analysis". Its premise probes P1–P7 are in [`python-production-failure-gap-analysis/`](python-production-failure-gap-analysis/README.md).

The working tracker is [`python-upstream-contribution-tracker.md`](python-upstream-contribution-tracker.md).

**What this document is, and is not:**

- **A plan.** It authorizes nothing it describes (`AGENTS.md` rules 2, 9 and 10). Every upstream post needs approval of its exact text and destination.
- **No new experiment.** Its new facts come from three sources, all on 2026-10-24:
  - the raw probe outputs, re-read;
  - source reading of the installed versions and of each project's default branch;
  - read-only checks of the upstream trackers with `gh`.
- **No other changes.** No adapter, harness file, specification, recorded result, shared document, or either report was edited. Nothing was filed or posted.

**Evidence labels.** These are the two reports' labels, plus two for this synthesis.

| Label | Meaning |
| --- | --- |
| **PPCS** | A recorded run in this repository: three repetitions, gated by CTL-01 and `pg-control` |
| **Audit** | The audit's diagnostic run (its Appendix A): three repetitions, outside the harness |
| **A2** | The gap analysis's premise probes P1–P7: three repetitions each, all agreeing, outside the harness, not gated. Outputs are in `python-production-failure-gap-analysis/output/` |
| **Ext** | Recorded outside this repository (the audit's §2.2) |
| **Src** | Source reading, with file and line. Lines are for the PPCS-pinned versions unless stated. Not a runtime observation |
| **Doc** | Documentation, quoted |
| **Upstream** | Tracker, release or branch state, checked 2026-10-24 between about 15:00 and 16:00 UTC |
| **Judg** | This synthesis's assessment |

**Upstream snapshot (2026-10-24):**

| Project | PPCS-pinned | Latest release (PyPI upload) | Default-branch head | The cited code on that head |
| --- | --- | --- | --- | --- |
| psycopg | 3.3.6 | 3.3.6 (2026-09-18) | `master` `99356800e` (2026-10-12) | Both `_commit_gen` implementations are identical to 3.3.6 |
| asyncpg | 0.32.0 | 0.32.0 (2026-10-06) | `master` `13b01910d` (2026-10-08) | `Transaction.__commit` is identical to 0.32.0 |
| Tortoise ORM | 1.1.9 | 1.1.9 (2026-10-14) | `develop` `536fc3abd` (2026-10-24) | `Model.save()` and the asyncpg `TransactionWrapper.commit()` are identical to 1.1.9 |
| SQLAlchemy | 2.1.5 (P3 also ran 2.1.6) | 2.1.6 (2026-10-21) | `main` `10f4d1e2d` (2026-10-23) | Identical to 2.1.5: `RootTransaction`, `Connection._commit_impl` and `_rollback_impl`, the `SessionTransaction.rollback` body, the `after_rollback` docstring, and the PostgreSQL reset recipe |

## 1. Executive summary

- **Two drivers report a commit that PostgreSQL turned into a rollback.** These are the most severe and most widely inherited Python findings.
  - **The sequence.** An application catches a PostgreSQL error inside a transaction, then lets the transaction finish. Every write is lost, and the API returns normally.
  - **Observed triggers:** `23505`, `57014`, `40P01` and `40001` (PPCS; A2 P1 and P6).
  - **psycopg (PY-1).**
    - `Connection.commit()` is filed as [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453): open, no reply, no labels.
    - Its second public surface is not in #1453. `with conn.transaction() as tx:` exits normally and sets `tx.status` to `committed` (Audit).
    - psycopg documents `status` as "the final outcome of the transaction", for "retry logic".
  - **asyncpg (PY-2).** `Transaction.commit()` and `async with conn.transaction()` discard the `ROLLBACK` status that asyncpg's own `execute()` returns (A2 P1; Src). There is no upstream report. Tortoise and SQLAlchemy's asyncpg dialect inherit it.
- **Tortoise loses a retried write silently (PY-3).**
  - **The behaviour.** After a rolled-back `save()`, the instance still claims to be saved. A retried `save()` returns normally and persists nothing (A2 P4). By source reading, it sends an UPDATE that matches no row.
  - **The fix needs a maintainer's choice.** Row counts mean different things on different backends (Tortoise #1212).
- **Two reset contracts do not hold.**
  - **asyncpg (PY-6).** `Connection.reset()` promises a state "resembling that of a newly obtained connection", but leaves `SET ROLE` in place.
  - **SQLAlchemy (PY-5).** The documented PostgreSQL reset recipe resets nothing on psycopg 3. The same page's next section explains why: a transaction's rollback reverts the `SET` statements run inside it.
  - **Both matter for security.** The previous user's role and tenant state reach the next borrower. Both fixes are small.
- **In SQLAlchemy, one code path lies behind two findings.**
  - **The path.** After a failed root `COMMIT`, `RootTransaction._do_commit` deactivates the transaction. The later rollback then sends nothing, because `_close_impl` gates on `is_active`. The ORM dispatches `after_rollback` anyway.
  - **P5a (PY-7)** is the pool consequence. It is ready for its author.
  - **PY-4** is the event consequence: `after_rollback` after a cancelled `COMMIT`. Its contract is uncertain. One check (CHK-4) decides whether it is specific to cancellation.
- **New in this synthesis.** Neither report has these:
  1. **psycopg's own suite asserts today's `commit()` behaviour** (`test_auto_transaction_fail`). A `commit()` that raises therefore has a known compatibility cost. The `transaction()` path has documented semantics. Its suite also exits a block normally after a caught error (`test_outer_transaction_error`), so a block that raises has a compatibility cost too. A corrected `status` alone conflicts with neither test (corrected 2026-10-24).
  2. **psycopg's docs define `Transaction.status` as the final outcome, for retry logic.** That settles "exit path or outcome?" against the current behaviour.
  3. **SQLAlchemy's `after_rollback` follows every failed root `COMMIT`** without a DBAPI rollback (Src). The cancellation result is one instance of this.
  4. **SQLAlchemy's recipe mixes two drivers.** It shows a `postgresql+psycopg2://` URL but calls `dbapi_connection.execute()`, a psycopg 3 method.
  5. **asyncpg PR #1392 (open) sets the pattern for a role fix:** a capability-gated statement in the reset query. asyncpg's maintainers rejected `DISCARD ALL` in 2018 (#270).
  6. **Tortoise #1212 shows `execute_update()` returning 0 for an existing row on MySQL.** A fix based on row counts carries that risk.
- **Recommended order:**
  1. PY-1b: a comment on #1453;
  2. PY-2: the asyncpg issue;
  3. PY-3: the Tortoise issue;
  4. PY-5: the SQLAlchemy documentation, written by its author;
  5. PY-6: the asyncpg role issue;
  6. then PY-8, PY-7 and PY-4 (§6.3).
- **Readiness.**
  - **Ready for human review:** PY-1b, PY-2, PY-3, PY-6, PY-7 (written by its author), and PY-8.
  - **One check first:** PY-5 (CHK-3) and PY-4 (CHK-4).
  - **Already tracked upstream:** PY-1a (#1453).
- **No new upstream issue for these** (§13):
  - the SQLAlchemy ORM `after_commit` result;
  - Django `atomic()` and `on_commit`;
  - session state in psycopg_pool and Django;
  - the extra SQLSTATEs;
  - psycopg's pool under cancellation.
- **Where this roadmap departs from the reports.**
  - **The gap analysis** recommends a two-to-three-day cancellation investigation next. Here CHK-4 replaces it: CHK-4 answers the one question an upstream post needs.
  - **The audit** put P5a third. It is seventh here, behind findings with wider reach. It stays ready for its author, and can run in parallel.

## 2. Consolidated findings matrix

| ID | Project and API | Finding | Failure class | Trigger | Nature | Evidence | Upstream | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PY-1a | psycopg 3.3.6 `Connection.commit()` | Returns `None` when PostgreSQL completes `COMMIT` with tag `ROLLBACK` | False transaction success | A: a caught `23505`. Through SQLAlchemy Core, also `57014`, `40P01` and `40001` | Driver; contested | PPCS `reproductions/psycopg_commit_tag.{py,txt}`, `64c5c5`; PR-01 `b2c174`, `508b7a`; A2 P6; Src | #1453: filed, open, no reply | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN |
| PY-1b | psycopg 3.3.6 `Connection.transaction()` | The block exits normally and `Transaction.status` is `committed`. PostgreSQL aborted the transaction | False transaction success, through a public status | A | Driver, against documented semantics | Audit Appendix A (3 of 3, savepoint control); Src; Doc | Not in #1453 | CONFIRMED |
| PY-2 | asyncpg 0.32.0 `Transaction.commit()`, `async with conn.transaction()` | Return normally; internal state `committed`. A raw `execute('COMMIT')` returns `'ROLLBACK'` | False transaction success | A: `23505`, `57014`, `40P01`, `40001` | Driver | A2 P1, P6; PPCS `c45624` (Tortoise; trace `COMMIT; -> ROLLBACK`); Src | None | CONFIRMED |
| PY-3 | Tortoise 1.1.9 `Model.save()` | A retry after a rolled-back `save()` returns normally; 0 rows persist | Silent data loss | An application error, then a retry with the same instance | ORM | A2 P4, with Django and SQLAlchemy as controls; Src | None; #1094 is unrelated | CONFIRMED |
| PY-4 | SQLAlchemy 2.1.5 and 2.1.6 ORM `after_rollback` | Fires after a cancelled `COMMIT` that PostgreSQL then commits | Incorrect rollback claim | anyio level-triggered cancellation while `COMMIT` waits; also Uvicorn's graceful-shutdown timeout under SIGINT (P8) | Documentation at least; possibly event semantics | A2 P3 and P8 (both drivers, both versions); Src | None | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN |
| PY-5 | SQLAlchemy docs: the PostgreSQL reset recipe | Resets nothing on psycopg 3 | Cross-tenant state; a mitigation that does nothing | Session state set by one checkout | Documentation | A2 P7; Src; psql | None | CONFIRMED on psycopg 3; psycopg2 is a HYPOTHESIS |
| PY-6 | asyncpg 0.32.0 `Connection.reset()` | `SET ROLE` survives release and reacquisition | Cross-tenant and privilege carryover | Session-level `SET ROLE` | Docstring versus default; PostgreSQL behaves as documented | A2 P2; psql; Src | None. #1293 and PR #1392 cover temp tables | CONFIRMED |
| PY-7 | SQLAlchemy Core 1.4.0–2.1.5, `Connection.close()` after a failed `commit()` | Returns the connection with its transaction open; the next checkout commits the doomed writes | Unsafe connection reuse | `commit()` raises before `COMMIT` is processed: a raising `commit` listener, or mixed APIs | Library; two documented guarantees | Ext adversarial review (2026-10-18); Src | None. Draft approved, not posted | CONFIRMED |
| PY-8 | Tortoise 1.1.9 `TransactionWrapper.commit()` | A COMMIT-time integrity error arrives as a raw `asyncpg.ForeignKeyViolationError` | Wrong exception type (loud) | A deferred FK checked at `COMMIT` | Library, minor | A2 P5; Src | None | CONFIRMED |
| PY-9 | SQLAlchemy ORM `after_commit` | Fires on an aborted transaction when `Session.execute()` raised | Commit hook without a commit | A | Downstream of PY-1 and PY-2 | A2 P1; Ext `run-2.txt` | None | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN |
| PY-10 | Django 6.1.2 `atomic()`, `on_commit` | The ORM path rolls back and drops `on_commit`. The raw-cursor path runs `on_commit` after tag `ROLLBACK` | — | A | Correct (ORM); documented as unspecified (raw) | PPCS `6d8443`, `b2c174`; A2 P5, P6; Ext arm 4b, one run | — | NOT A DEFECT |
| PY-11 | psycopg_pool, SQLAlchemy's pools, Django connections | Session state reaches the next borrower | Cross-tenant state | Session-level `SET` | Documented; the application's responsibility | A2 P2 | psycopg Discussion #893 (via A2) | NOT A DEFECT |
| PY-12 | SQLAlchemy Core, asyncpg, Tortoise, Django | `57014`, `40P01` and `40001` on the caught-then-commit path | Same as PY-1 and PY-2 | A | The same mechanism | A2 P6, with the endings from the server log | — | CONFIRMED; no new defect |
| PY-13 | psycopg `AsyncConnectionPool` | A level-cancelled `COMMIT` completes after the API returned | Unknown outcome; no claim | Cancellation | Documented | A2 P3; Doc | — | NOT A DEFECT |

## 3. Evidence and confidence classification

### 3.1 Summary

| ID | Classification | What holds it below the next level | What would change it |
| --- | --- | --- | --- |
| PY-1a | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | psycopg's docs tell callers to `rollback()` after a failed statement. Its suite asserts that `commit()` returns after one | A maintainer reply on #1453 |
| PY-1b | CONFIRMED | — | — |
| PY-2 | CONFIRMED | asyncpg documents only "commit changes". Maintainers may accept today's behaviour | A maintainer reply |
| PY-3 | CONFIRMED | The mechanism (an UPDATE matching 0 rows) is Src. P4 logged no statements | CHK-5 |
| PY-4 | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | The event follows every failed `COMMIT`, including those PostgreSQL rolled back. The unknown outcome is not SQLAlchemy's doing | CHK-4; a maintainer reply |
| PY-5 | CONFIRMED on psycopg 3 | "The hook ran" is Src: no invalidation was recorded. psycopg2 was not run | CHK-3 |
| PY-6 | CONFIRMED | The pool docs list the exact reset statements. Maintainers may prefer a docstring fix | The maintainers' choice |
| PY-7 | CONFIRMED | No ordinary driver or OS failure reproduced it (Ext) | Evidence of such a trigger |
| PY-8 | CONFIRMED | Severity only | — |
| PY-9 | CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN | The cause is the driver | The outcome of PY-1 and PY-2 |
| PY-10, PY-11, PY-13 | NOT A DEFECT | Documented behaviour | — |
| PY-12 | CONFIRMED; no new defect | — | — |

**Hypotheses** (not verified):

- **H-a.** psycopg's `Transaction.status` stays `committed` when `COMMIT` itself raises, as on a deferred constraint. This is the audit's H6. By Src, `status` is set at `transaction.py:135`, before the command at line 140. CHK-1.
- **H-b.** SQLAlchemy's `after_rollback` also fires when a `COMMIT` reply is lost and PostgreSQL commits. Src: P3's code path. CHK-4.
- **H-c.** Tortoise's savepoint variant loses the write the same way (the gap analysis, §7.3). CHK-5.
- **H-d.** On psycopg2, the driver in the URL the recipe shows, the recipe's `dbapi_connection.execute()` raises, and the pool discards every returned connection.
  - SQLAlchemy's handling is Src (`pool/base.py:1043-1053`).
  - psycopg2's connection API was not checked here.
  - CHK-3.
- **H-e.** A zero-row rule in Tortoise's `save()` would misfire on MySQL when values are unchanged, because MySQL reports changed rows.
  - The MySQL client sets no `FOUND_ROWS` flag by default (`backends/mysql/client.py:114-124`). Parameters a user supplies pass through at line 123.
  - #1212 shows a zero count for an existing row.
  - Not run.
- **H-f.** If the drivers raised, SQLAlchemy Core and Django `atomic()` would roll back and drop their hooks. This is the audit's H1.

### 3.2 Candidate determinations

#### A. psycopg: false transaction success (PY-1a, PY-1b)

**Observed.**

- **PPCS.** After a caught `23505`:
  - `Connection.commit()` returned `None`, and another connection saw no row.
  - In the same state, a cursor `COMMIT` returned `statusmessage 'ROLLBACK'` with `COMMAND_OK` (`research/production-reachability/reproductions/psycopg_commit_tag.txt`).
  - SQLAlchemy Core (`64c5c5`, `b2c174`) and Django's manual `commit()` (`508b7a`) reached the same `commit()`, 3 of 3.
- **Audit**, 3 of 3. `with conn.transaction() as tx:` exited without raising, and `tx.status` was `committed`. Yet `pg_xact_status` was `aborted`, the marker was absent, and the backend was `idle` with last statement `COMMIT`. The savepoint-recovery control committed.
- **A2 P6.** `57014`, `40P01` and `40001` take the same path through SQLAlchemy Core on psycopg.

**Src** (3.3.6, identical on `master`):

- **`Connection.commit()`.** `BaseConnection._commit_gen` (`_connection_base.py:577-595`) sends `COMMIT` through `_exec_command`, then drops the `PGresult`. `_exec_command` (443–493) raises only for a status other than `COMMAND_OK` or `TUPLES_OK`.
- **`transaction()`.** `BaseTransaction._commit_gen` (`transaction.py:133-140`) sets `status = COMMITTED` at line 135, before sending `COMMIT` at line 140, and drops the result.
- **Independent paths.** The second calls `_exec_command` directly, not `Connection._commit_gen`. A fix in one therefore does not reach the other, which confirms the audit's H2 by reading.
- **Pipeline mode.** `_exec_command` queues the command and returns `None` (459–468). No result is available at that point.

**Doc** (`docs/basic/transactions.rst` on `master`):

- **The block contract:** "when leaving the context the transaction is committed, or it is rolled back if an exception is raised inside the block" (159–162).
- **`status`:** "remains accessible after the transaction context has exited, allowing you to check the final outcome of the transaction … particularly useful when you need to log transaction outcomes or implement retry logic" (347–350).
- **After a failed operation:** "You need to call `rollback()` if you want to keep on using the same connection" (103–108).

**Upstream.**

- **#967 (2024-12-16).** The maintainer wrote: "you can understand if there was a rollback because an exception will be thrown as well". The `try`/`except`/`else` that followed reads "there was a commit" in its `else` branch.
- **`tests/test_connection_async.py:401`** (`test_auto_transaction_fail`; sync copy `tests/test_connection.py:405`). It runs a failing statement and asserts `INERROR`. It then calls `commit()`, and asserts `IDLE` and that the row is gone.
- **`test_transaction_status`** (`tests/test_transaction_async.py:533`). No case catches an error inside the block.
- **`test_outer_transaction_error`** (`tests/test_pipeline.py:506`; async copy `tests/test_pipeline_async.py:507`). It catches a database error inside `transaction()` with `pytest.raises`, and expects the block to exit normally. In its pattern the transaction is aborted at exit, and `status` reads `committed` (corrected 2026-10-24; `python-upstream-contribution/psycopg-pipeline-test-check/`).

**Answers to the brief:**

1. **Does #1453 cover both APIs?** No. Its body covers `Connection.commit()` and asks that it raise. It does not mention `transaction()` or `Transaction.status`.
2. **A follow-up comment, or a separate issue?** A comment on #1453. It is one driver behaviour, one maintainer and one fix area. A separate issue would split a single decision across two threads.
3. **The narrowest fix.** In `BaseTransaction._commit_gen`, keep the outer `COMMIT`'s result. Set `COMMITTED` only after it succeeds, and raise when its command status is `ROLLBACK`.
   - Raising breaks `test_outer_transaction_error`. Setting a non-committed `status` without raising breaks no test found (corrected 2026-10-24).
   - The same check in `BaseConnection._commit_gen` would cover `commit()`, and with it SQLAlchemy and Django. It changes `test_auto_transaction_fail`, though.
   - Details are in §7.
4. **Regression tests:** §8.
5. **Compatibility.** Yes (§9).
   - Code that ends a failed transaction with `commit()` would start to raise. psycopg's test encodes exactly that behaviour.
   - So would blocks that swallow an error and exit normally.
   - Pipeline mode needs its own path.
   - The exception class decides how Django and SQLAlchemy react.

**Adversarial review:**

- **Explained by documented behaviour?** For `commit()`, partly: the rollback hint, and the test. For `transaction()`, no. The docs promise the opposite.
- **An unsupported pattern?** Catching a database error inside a transaction without a savepoint is a mistake in PostgreSQL terms. It is still ordinary application code, and PR-01 rated it reachable without injection. A driver that receives `ROLLBACK` should not report success.
- **Synthetic?** No. PostgreSQL generated the errors (category A).
- **Independent evidence?** Yes: `pg_xact_status`, marker visibility, and `pg_stat_activity`, all from another connection.
- **A positive control?** Savepoint recovery committed in the same runs.
- **A misread of the attribute?** #969's request text asks "whether the block was exited with a commit or a rollback", which could mean the exit path. The shipped docs say "final outcome" and "retry logic", so the documented reading is the outcome.
- **Regression risk of the fix?**
  - A `commit()` that raises changes behaviour that an existing test encodes.
  - A fix in `transaction()` only avoids that only if it does not raise. A block that raises fails `test_outer_transaction_error` (corrected 2026-10-24). Either way it leaves SQLAlchemy and Django exposed: both call `Connection.commit()`.
- **Maintainer position?** None on #1453 yet. The last commit on `master` was 2026-10-12.

**Classification.** PY-1b is CONFIRMED. PY-1a is CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.

#### B. asyncpg: false transaction success (PY-2)

**Observed.**

- **A2 P1**, 3 of 3, asyncpg 0.32.0, no framework:
  - `async with conn.transaction()` exits normally, and `repr` shows `state:committed`.
  - `Transaction.start()`, then `commit()`, returns `None`.
  - A raw `execute('COMMIT')` returns `'ROLLBACK'`.
  - PostgreSQL aborted, the marker is absent, and the last statement is `COMMIT;`.
  - A nested-savepoint control committed.
- **PPCS `c45624`.** The same path through Tortoise: FAIL, 3 of 3, with driver trace `COMMIT; -> ROLLBACK`.
- **A2 P6.** `57014`, `40P01` and `40001` end the same way. The server log shows `COMMIT;`.

**Src** (0.32.0, identical on `master`):

- `Transaction.__commit` (`transaction.py:175-192`) awaits `self._connection.execute(query)`. It sets `COMMITTED` without reading the status that `execute()` returns (`connection.py:348`: ":return str: Status of the last SQL command").
- `Transaction.commit()` is documented as "Exit the transaction or savepoint block and commit changes" (`transaction.py:215`).
- `TransactionState` is not public (#1130).

**Answers to the brief:**

1. **Does an issue cover this exact mechanism?** None found.
   - **Searches, 2026-10-24.** The gap analysis's research subagent tried about 15 phrasings. This synthesis searched `commit ROLLBACK`, `transaction commit aborted`, `commit status ROLLBACK`, `transaction committed state failed`, `InFailedSQLTransactionError commit` and `commit returns rollback`.
   - **Nearest.** #1130 (make transaction state public; open, no comments) and #1386 (a failed `BEGIN` leaves `_top_xact` set; open; a different path).
2. **asyncpg, or its downstream consumers?** asyncpg.
   - **Where the status goes.** It reaches asyncpg, and asyncpg's own transaction object drops it.
   - **Why consumers cannot fix it.** Tortoise (`backends/asyncpg/client.py:197-203`) and SQLAlchemy's adapter (`dialects/postgresql/asyncpg.py:919-926`) call `Transaction.commit()` and never see the string. They could check it only by bypassing asyncpg's transaction API.
   - **How a fix would reach them.** SQLAlchemy's adapter passes an exception from that call through, since `_call_and_discard` only clears its reference in `finally` (902–908). A driver fix would reach SQLAlchemy users unchanged, and Tortoise users as a raw asyncpg exception (PY-8).
3. **The smallest change to transaction completion.** For the top-level `COMMIT;` only, keep the status `execute()` returns. If it is `ROLLBACK`, set the state to `ROLLEDBACK` (or `FAILED`) and raise. `RELEASE SAVEPOINT` in an aborted transaction already raises `25P02` (Judg, from PostgreSQL semantics; not run).
4. **Exception behaviour and compatibility.**
   - **The class** is the maintainers' choice. SQLAlchemy's `_handle_exception` must be able to map it to a DBAPI error. It must not imitate a SQLSTATE the server never sent.
   - **Compatibility.** Code that catches an error inside `async with conn.transaction()` and exits normally would raise, where today it rolls back silently.
   - **Existing tests.** `tests/test_timeout.py::test_timeout_06`, and `test_timeout_04`, exit a transaction block normally after a caught error that aborted it. `test_timeout_06` asserts `InFailedSQLTransactionError` first. A fix that raises changes them (corrected 2026-10-24).
5. **Regression tests:** §8.

**Downstream frameworks are secondary.** Tortoise's only independent defect here is exception translation (PY-8). SQLAlchemy's ORM `after_commit` (PY-9) goes away if the driver raises (H-f).

**Adversarial review:**

- **Internal state is not an API.** `state:committed` comes from `repr`. The public claim is the normal return, so do not present the internal state as the contract.
- **Gating.** The probe ran outside PPCS's gates, but with an independent witness and a savepoint control. PPCS `c45624` adds a gated observation of the same driver path, through Tortoise.
- **Pattern, trigger, evidence and control:** as for psycopg.
- **Maintainer position.** None. Responsiveness is the main risk (§9).

**Classification.** CONFIRMED.

#### C. Tortoise: silent lost write after rollback (PY-3)

**Observed** (A2 P4, 3 of 3):

- **Tortoise.** The application called `save()` inside an `in_transaction()`, then raised, so the transaction rolled back. The instance kept `pk = 1` and `_saved_in_db = True`. A retried `save()` in a new `in_transaction()` returned normally, and the witness counted 0 rows.
- **Controls.** Django 6.1.2 re-inserted: 1 row. SQLAlchemy 2.1.5 made the object transient and re-inserted it: 1 row.
- **Not recorded.** P4 logged neither the retry's statements nor its transaction ID.

**Src** (1.1.9, identical on `develop`):

- **The default path ignores the count.** When `_saved_in_db` is true, `Model.save()` (`models.py:1131-1195`) sends `execute_update()` and ignores the count it returns (1182–1188).
- **`force_update=True` does not.** It checks the same count and raises "Can't update object that doesn't exist" (1176–1179).
- **The flag is never reverted.** `_saved_in_db = True` is set after the statement (1194). Nothing resets it on rollback.
- **A zero count can mean "nothing sent".** `execute_update()` returns 0 without sending any statement when no field needs updating (`backends/base/executor.py:489-490`).

**Answers to the brief:**

1. **Does this violate Tortoise's documented save semantics?**
   - **The docstring.** "Creates/Updates the current model object" (`models.py:1139`). It raises `IntegrityError` "If the model can't be created or updated (specifically if force_create or force_update has been set)" (1150).
   - **What is undocumented.** Nothing describes instance state after a rollback. Nothing describes the observed result either: a normal return that neither created nor updated.
   - **The nearest documented rule,** `force_update`, treats a 0-row update as an error.
   - **Judg:** a defect. Whether reusing an instance after a rollback is supported is the maintainers' decision.
2. **Is #1094 related?** Only by symptom.
   - Its reports involve asyncpg's "Resetting connection with an active transaction" warning, `bulk_create`, and connection resets.
   - No cause was ever established, and nothing there points at `_saved_in_db` (read 2026-10-24).
   - Do not comment there.
3. **Restore state after rollback, detect zero-row updates, or both?** §7 describes both.
   - **Restoring `_saved_in_db`** for instances inserted in a rolled-back transaction or savepoint targets the cause, on every backend.
   - **Detecting zero rows** is the smaller diff. But what the count means depends on the backend (MySQL counts changed rows; #1212, H-e), and on whether a statement was sent at all.
   - **Recommendation.** Ask the maintainers. Propose restoration, with zero-row handling as an optional backstop on PostgreSQL and SQLite.
4. **Nested transactions and savepoints.** Not probed.
   - The gap analysis expects the same stale state after a savepoint rollback inside a committing outer transaction (H-c; CHK-5).
   - Restoration must then work per savepoint level.
   - Zero-row detection does not depend on nesting.
5. **Could the fix change legitimate UPDATE behaviour?** Zero-row detection could:
   - misfire on MySQL when values are unchanged;
   - misfire on updates that send no statement;
   - change rows deleted concurrently. Today such a save is a silent no-op. An INSERT fallback, as in Django, would resurrect the row; raising would make it loud.

   Restoration changes nothing for instances that never had a rolled-back INSERT.

**The immediate bug, kept apart from a redesign.** The bug: after a rollback, `save()` returns normally and writes nothing. Snapshotting all instance state, as SQLAlchemy does, would be a redesign, and is not proposed.

**Adversarial review:**

- **An application choice?** Reusing an instance across attempts is one. Django and SQLAlchemy handle it, though, and Tortoise documents no restriction.
- **Synthetic?** No injection. The trigger is an application exception.
- **Independent evidence?** The witness's row count is independent. The mechanism is Src.
- **A positive control?** Django and SQLAlchemy persisted the same retry, which makes a cross-framework control. There is no raw-driver control.

**Classification.** CONFIRMED. The outcome and its owner are observed; the mechanism is Src.

#### D. SQLAlchemy: rollback event during a cancelled COMMIT (PY-4)

**Observed** (A2 P3; 3 of 3 per cell; SQLAlchemy 2.1.5 and 2.1.6; asyncpg and psycopg):

- **The gate.** `COMMIT` waited at a server-side gate: a deferred constraint trigger, blocked on an advisory lock that the runner held.
- **Level-triggered cancellation** (`anyio.CancelScope.cancel()`):
  - the recorded events, in order, were `core.commit`, the cancellation, `pool.invalidate`, `pool.close`, `pool.checkin`, `orm.after_rollback` and `orm.after_soft_rollback`;
  - the fate at report time was `in progress`;
  - after the gate opened, the transaction committed and the marker was visible.
- **Edge-triggered cancellation** (`task.cancel()`): the same events, but the fate was already `aborted` at report time.
- **No-cancellation control:** committed, with `after_commit`.
- **Gate in the body instead.** `after_rollback` fired while the fate was still `in progress`, and the transaction ended `aborted`. `COMMIT` was never sent there, so the outcome was knowable.

**Added 2026-10-25: the same claim without anyio** (gap analysis P8, `research/python-production-failure-gap-analysis/p8-uvicorn-shutdown/`; 3 of 3 per cell; SQLAlchemy 2.1.5 and 2.1.6; asyncpg and psycopg). Uvicorn 0.54.0's `--timeout-graceful-shutdown` expired while an `AsyncSession` `COMMIT` waited at the same gate. Under SIGINT, `after_rollback` and `after_soft_rollback` fired before the process exited, and PostgreSQL then committed. Under SIGTERM, no ORM commit or rollback event fired, and PostgreSQL also committed. P8 does not answer CHK-4's question (a lost `COMMIT` reply without cancellation).

**Src** (2.1.5, identical on `main`):

- **Commit.** `RootTransaction._do_commit` deactivates the transaction in its `finally`, whether or not the commit succeeded (`engine/base.py:2719-2742`).
- **Rollback.** `_do_rollback` runs `_close_impl`, which calls the DBAPI rollback only `if self.is_active` (2697–2717).
- **The event.** `SessionTransaction.rollback` dispatches `after_rollback` as soon as `t[1].rollback()` returns (`orm/session.py:1377-1380`).
- **The consequence.** After any failed root `COMMIT`, the ORM emits `after_rollback` without a DBAPI rollback. That holds whether PostgreSQL rolled back (a rejected deferred constraint), committed later (P3, level-triggered), or has not yet decided.

**Answers to the brief:**

1. **Is the documented `after_rollback` contract violated?**
   - **The docstring:** "Execute after a real DBAPI rollback has occurred. Note that this event only fires when the *actual* rollback against the database occurs" (`orm/events.py:1882-1898`).
   - **The contradiction.** P3's level-triggered rows contradict it literally: there was no DBAPI rollback, and the database committed.
   - **The weakness.** By source reading, the same event follows server-rejected COMMITs, where no DBAPI rollback is sent either. The docstring is already loose in that common case.
2. **An attempted rollback, or a completed DBAPI rollback?** The docstring says completed. The code means "the Session's transaction ended without committing", whether or not anything was sent.
3. **SQLAlchemy, the driver, AnyIO, or a combination?** A combination.
   - **The unknown outcome comes from the runtime and the driver.** Under level-triggered cancellation, no cancel stopped the waiting `COMMIT`. This is Judg, from the fates.
   - **psycopg's pool shows the same fate without SQLAlchemy** (P3), and psycopg documents why: "cancelling the Python Task does not guarantee that the operation will not complete" (`docs/advanced/async.rst:200-204`).
   - **The rollback claim is SQLAlchemy's.**
   - **Precedent.** In #12728 (2025), a report that in-flight commits were not cancelled was judged "might not be our bug". zzzeek then reported asyncpg's cancellation handling to asyncpg as #1265.
4. **Can SQLAlchemy avoid a definitive rollback claim while `COMMIT` is in flight?** Src: yes, in principle.
   - **What it knows.** The failure passes through `_handle_dbapi_exception` from `_commit_impl` (1157–1172; 2211). There SQLAlchemy knows the error came from `do_commit`, and whether the connection was invalidated.
   - **What it could do.** The Session could then emit only `after_soft_rollback`.
   - **A documentation-only alternative** is in §7.
5. **Can the event be corrected without breaking applications?**
   - **A documentation fix,** yes.
   - **Suppressing the event** would change behaviour for applications that use it for cleanup.
   - **The ORM itself does not depend on the event.** Its snapshot restore (`orm/session.py:1385`) runs regardless.

**Adversarial review:**

- **Cancelled is not rolled back.** P3 measures exactly that difference.
- **Not every cancellation produces this.** Edge-triggered cancellation aborted in every subject.
- **The gate is synthetic.** Its realistic analogue is a deferred FK waiting on a row lock. psql showed that wait, but it was never combined with cancellation (G-FK not run).
- **An open question changes the framing.** Does a lost `COMMIT` reply produce the same claim (H-b; CHK-4)? If so, the finding concerns unknown outcomes in general, not anyio, and it should be reported that way.

**Classification.** CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN.

#### E. SQLAlchemy: PostgreSQL reset recipe with psycopg 3 (PY-5)

**Observed** (A2 P7, 3 of 3; SQLAlchemy 2.1.5, psycopg 3.3.6; a non-superuser login):

- **The documented recipe**, installed with `pool_reset_on_return=None`. The next checkout, on the same backend, still had all of these: the role, a custom GUC, `search_path`, `statement_timeout`, and a temp table. No invalidation was recorded.
- **The default reset** (a rollback only). Everything carried over.
- **"`rollback()`, then `DISCARD ALL` in autocommit".** Everything was reset.
- **psql.** `RESET ALL` leaves `SET ROLE` in place. `RESET ROLE` and `DISCARD ALL` reset it.

**Src and Doc:**

- **The recipe** (`dialects/postgresql/base.py:277-336`; identical on `main`). It runs `CLOSE ALL`, `RESET ALL` and `DISCARD TEMP` through `dbapi_connection.execute()`, then calls `dbapi_connection.rollback()`. Its example URL is `postgresql+psycopg2://` (line 311).
- **When the hook runs.** The pool dispatches `reset` on every return that has a listener, whatever `pool_reset_on_return` says (`pool/base.py:1451-1467`, called from `_finalize_fairy` at 1020).
- **When the hook fails.** An exception from it is logged as "Exception during reset or similar", and the record is invalidated (1043–1053). P7 recorded no invalidation, so the hook ran without raising.
- **The page's next section.** It saves and restores `.autocommit` so that "the SET SESSION search_path directive" is not "reverted when the DBAPI connection has a rollback" (340–372).

**Answers to the brief:**

1. **Does the documentation explicitly support psycopg 3?** No.
   - The section belongs to the PostgreSQL dialect, which covers every driver.
   - Its example URL is psycopg2's, yet it calls `dbapi_connection.execute()`, a psycopg 3 connection method.
   - On the URL as written, the hook may raise on every return (H-d; CHK-3).
2. **Is the recipe defective as published?** Yes.
   - **On psycopg 3** its effect was observed to be nothing. Judg on the mechanism: its statements run inside the implicit transaction that its own `rollback()` then reverts.
   - **On any driver,** `RESET ALL` would not reset the role.
3. **Is `DISCARD ALL` safe with prepared statements and driver caches?**
   - **psycopg 3.3.5 and later** discard their prepared statements on `DISCARD` (changelog, 3.3.5; Src `_preparing.py:82-99`).
   - **psycopg2** keeps no server-side prepared statements (Judg).
   - **asyncpg** keeps a statement cache that `DISCARD ALL` would invalidate. Its maintainers rejected `DISCARD ALL` for that reason (#270).
   - **Connect-time settings.** `DISCARD ALL` also discards settings made with `SET SESSION` in a `connect` handler, including the page's own search-path recipe. Startup `options` survive, because `RESET ALL` returns to session defaults (Judg, from the PostgreSQL docs).
   - **Transactions.** It "cannot be executed inside a transaction block" (PostgreSQL 18 docs).
4. **A documentation PR, a regression test, or an implementation change?** A documentation change. Docs recipes are not normally covered by regression tests. P7 is the demonstration program.
5. **The minimal corrected example:** §7.

**Classification.** CONFIRMED on psycopg 3. psycopg2 is H-d.

#### F. asyncpg: PostgreSQL role survives pool reset (PY-6)

**Observed** (A2 P2, 3 of 3; a non-superuser login; a pool of one):

- **Unit 1** ran `SET ROLE tenant_a`, then committed.
- **Unit 2**, after release and reacquisition of the same backend:
  - `current_user` was `tenant_a`;
  - its unqualified insert recorded `inserted_by` as `tenant_a`, through `DEFAULT current_user`.
- **What the reset did clear.** The GUC, `search_path` and `statement_timeout` were reset, and the advisory lock was released.
- **The temp table survived.** That part is already #1293.

**Src** (0.32.0):

- **The reset query:** `SELECT pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;`, gated by server capability (`connection.py:1763-1790`).
- **The `reset()` docstring:** "reset the connection session state to a state resembling that of a newly obtained connection. Namely, … all session configuration variables are reset to their default values" (1567–1594).
- **The pool docs.** `create_pool(reset=)` lists the four statements (`pool.py:1320-1340`).

**Answers to the brief:**

1. **Does the documented reset guarantee cover `SET ROLE`?**
   - **The summary sentence promises it.** A role different from a new connection's contradicts "resembling that of a newly obtained connection".
   - **A maintainer can reply** that the pool docs list the exact statements, and that PostgreSQL documents that `RESET ALL` skips the role.
   - **Judg:** a mismatch between docstring and behaviour, owned by asyncpg. PostgreSQL itself behaves as documented.
2. **Does an existing issue cover role leakage?** None found. Searches: `RESET ROLE`, `SET ROLE pool`, `reset role release`, `session authorization reset`, `reset query role`. Related:
   - **#1293:** temp tables survive (open, no comments).
   - **PR #1392:** adds `DISCARD TEMP` behind a new `sql_discard_temp` capability, updates the `reset()` docstring, and adds a pool test (open, no review).
3. **Should the default reset query include `RESET ROLE`?** Judg: yes, behind a capability flag as #1392 does. Three reasons:
   - it makes the docstring true;
   - any user may run it;
   - it returns to a connection-time role when one is set (startup options, `ALTER ROLE`, `ALTER DATABASE`; PostgreSQL 18, SET ROLE), so configured roles survive.
4. **Would the change break supported application patterns?** One:
   - **Who breaks.** Applications that run `SET ROLE` in the pool's `init` callback, which runs once per physical connection, keep that role on every acquisition today.
   - **What changes.** After the change, every acquisition after the first would run as the login role, which may be more privileged.
   - **Mitigation.** `init` is documented for type codecs (`pool.py:1312-1318`), and `RESET ALL` already discards other settings made in `init`; the role is the exception applications may rely on. Release-note the change, and point those applications to `setup` or `server_settings`.
5. **A security-sensitive regression test:** §8.

**Expected PostgreSQL behaviour, versus the pool's documented responsibility.** PostgreSQL behaves as documented. The issue is the pool's documented responsibility.

**Disclosure.** asyncpg and the MagicStack organization publish no security policy (checked 2026-10-24). Present it publicly, as a mismatch between the docstring and the default, not as an exploit.

**Classification.** CONFIRMED.

#### G. SQLAlchemy P5a: connection returned with an active transaction (PY-7)

**Evidence.** `../python-orm-transactions/docs/sqlalchemy-p5a-close-review.md` (2026-10-18: CONFIRMED DEFECT) and `check/p5a_close_v2.{py,out}`. Both are in that repository's commit `cca9b98`, which is on its `origin/main` (checked 2026-10-24).

- **What was observed.** After `commit()` raised before PostgreSQL processed `COMMIT`:
  - `close()` sent no ROLLBACK;
  - `PoolResetState.transaction_was_reset` was True while psycopg was `INTRANS`;
  - the next checkout's `COMMIT` committed the doomed writes (server log).
- **Versions.** 1.4.0, 1.4.54, 2.0.55 and 2.1.5 were affected. 1.3.24 was not.

**Answers to the brief:**

1. **Does the reproduction show a SQLAlchemy-owned invariant violation?** Yes. It contradicts two documented guarantees:
   - `Connection.close()` releases transactional state "unconditionally … via the DBAPI connection's rollback()";
   - `PoolResetState.transaction_was_reset`.
2. **Does it depend on a user event listener raising?** The path that replaces no DBAPI method does: a `ConnectionEvents.commit` listener that raises. The other demonstrated path mixes psycopg's own `transaction()` with SQLAlchemy's commit, where psycopg raises `ProgrammingError` before sending.
3. **Is it reachable through an ordinary driver or OS failure?** Not demonstrated. A server-rejected COMMIT, connection loss, `KeyboardInterrupt` and `CancelledError` all ended safely (Ext).
   - **The closest case.** An exception from a signal handler, raised after `COMMIT` was sent, reaches the same reset skip, but loudly: the next checkout fails with "another command is already in progress".
4. **Is a minimal fix feasible?** Yes, by source reading. A transaction that `_do_commit` deactivated after a failure must not count as reset. Either:
   - leave `transaction_was_reset` False, so that the pool's reset-on-return rolls back (smaller); or
   - send the DBAPI rollback while the connection is valid. This also covers the review's follow-up, where `rollback()` after a failed commit sends nothing.
5. **File now, or hold for stronger production evidence?** File now, in its author's own words.
   - The review has taken reachability as far as the evidence goes.
   - Two documented guarantees are contradicted, and the behaviour regressed from 1.3.
   - SQLAlchemy fixed #13657 the day after it was reported, and #13381 within ten days.

   Do not overstate reachability. Say "a commit listener that raises, or mixing psycopg's transaction API with SQLAlchemy's".

**Today's checks.** `RootTransaction` on `main` is byte-identical to 2.1.5. 2.1.6 was not run (CHK-7). The code path is shared with PY-4 (part D).

**Classification.** CONFIRMED.

#### H. Additional findings

- **SQLAlchemy ORM `after_commit` after an aborted transaction (PY-9).**
  - **Evidence.** A2 P1 shows it on psycopg and on asyncpg, when `Session.execute()` raised the caught error. Ext `run-2.txt` shows it once.
  - **Cause.** The driver discards the tag (PY-1, PY-2). If the driver raised, the ORM would not reach `after_commit` (H-f).
  - **Action.** No issue. Reconsider only if both drivers decline. This is the same item as Draft C.
- **Django `atomic()` and `on_commit()` (PY-10).**
  - **ORM writes.** The transaction rolls back and `on_commit` is dropped: PPCS `6d8443` and PR-01 `b2c174`; P6 for `57014`, `40P01` and `40001`.
  - **A deferred FK at `COMMIT`.** Raises `IntegrityError 23503` and drops `on_commit` (P5).
  - **The raw-cursor path** runs `on_commit` after tag `ROLLBACK` (Ext, one run). Django documents it as unspecified: "If you catch exceptions raised by raw SQL queries, Django's behavior is unspecified and database-dependent".
  - **Action.** None.
- **Tortoise COMMIT-time exception translation (PY-8).** Observed in P5.
  - **Src.** Every backend decorates `begin()` with `translate_exceptions`; none decorates `commit()` or `rollback()`. Locations: asyncpg `client.py:189-208`, psycopg 249–269, MySQL 259–276, SQLite 236–249, ODBC 192–203.
  - **Impact.** Loud, but with the wrong type.
  - **Action.** A small pull request.
- **Session-state carryover in psycopg_pool, SQLAlchemy's pools and Django (PY-11).** These carry state by design.
  - **psycopg_pool** documents no default reset, and a `reset` callback (the maintainer in Discussion #893, via A2).
  - **SQLAlchemy's** reset section starts from the fact that a rollback "does not cover a wider range of session-level state".
  - **Django** documents its persistent-connection caveat. Its native pool applies only `configure=` (Src, via A2).
  - **Action.** At most, a Django documentation note on the native pool. Low priority.
- **The SQLSTATE experiments `57014`, `40P01` and `40001` (PY-12).** The same mechanism: P6, 36 runs, with endings from the server log. No new issue. Cite them as further triggers in the PY-1 and PY-2 texts.
- **psycopg `AsyncConnectionPool` with a level-cancelled `COMMIT` (PY-13).** The anyio scope absorbed the `CancelledError`, so the API made no outcome claim. psycopg documents the unknown outcome (`docs/advanced/async.rst:200-204`). Not a defect.

**No new upstream issue is justified for** PY-9 through PY-13, nor for the items in §13.

## 4. Existing upstream issues and pull requests

Every row was checked on 2026-10-24 (Upstream). "Ours" means filed from this research.

| Project | Reference | State | Relevance |
| --- | --- | --- | --- |
| psycopg | [#1453](https://github.com/psycopg/psycopg/issues/1453) | Open. Created 2026-10-22T00:52Z (2026-10-21, US Pacific). No comments, no labels | Ours (tracker P1). Covers `Connection.commit()` only. The vehicle for PY-1b |
| psycopg | [#969](https://github.com/psycopg/psycopg/issues/969) and [PR #1184](https://github.com/psycopg/psycopg/pull/1184) | Closed. The PR merged 2025-11-22 | Added `Transaction.status` |
| psycopg | [#967](https://github.com/psycopg/psycopg/issues/967) | Closed | The maintainer: a normal exit means a commit |
| psycopg | [#1451](https://github.com/psycopg/psycopg/issues/1451) and [PR #1454](https://github.com/psycopg/psycopg/pull/1454) | Open. No reply, no review | A cancelled `AsyncConnection.transaction()` entry. Not ours, and not PY-1 |
| psycopg | #1408, and the 3.3.5 changelog | Released | Prepared statements are discarded on `DEALLOCATE ALL` and `DISCARD` (relevant to PY-5) |
| asyncpg | none | — | No report of PY-2 or PY-6 |
| asyncpg | [#1130](https://github.com/MagicStack/asyncpg/issues/1130) | Open since 2024-03-11. No comments | Asks to make transaction state public (PY-2) |
| asyncpg | [#1293](https://github.com/MagicStack/asyncpg/issues/1293) and [PR #1392](https://github.com/MagicStack/asyncpg/pull/1392) | Both open, no comments. The PR has been open since 2026-10-14, unreviewed | Temp tables survive the reset. The PR adds a capability-gated `DISCARD TEMP` (PY-6) |
| asyncpg | [#270](https://github.com/MagicStack/asyncpg/issues/270) | Closed, 2018 | The maintainers decline `DISCARD ALL`: prepared statements, old servers, forks |
| asyncpg | [#1386](https://github.com/MagicStack/asyncpg/issues/1386) | Open since 2026-10-07. One non-maintainer comment | A failed `BEGIN` leaves `_top_xact` set. A different path |
| asyncpg | [#1265](https://github.com/MagicStack/asyncpg/issues/1265) | Open since 2025-07-11. Filed by zzzeek with a patch. No maintainer reply | Cancellation handling. Evidence of slow responses |
| Tortoise | [#1094](https://github.com/tortoise/tortoise-orm/issues/1094) | Open since 2022. 20 comments | Shares only the symptom ("says saved but actually isn't"). Not PY-3 |
| Tortoise | [#1212](https://github.com/tortoise/tortoise-orm/issues/1212) | Open since 2022-08-03. No comments | `force_update` sees 0 rows for an existing row on MySQL and MariaDB. A risk for PY-3's fix |
| SQLAlchemy | none | — | No report of PY-4 or PY-5 in issues or discussions. P5a's duplicate search was on 2026-10-18 |
| SQLAlchemy | [#12728](https://github.com/sqlalchemy/sqlalchemy/issues/12728) | Closed, 2025-07 | In-flight commits not cancelled: "might not be our bug". A precedent for PY-4 |
| SQLAlchemy | [#13381](https://github.com/sqlalchemy/sqlalchemy/issues/13381) | Closed 2026-06-27. Labelled bug, engine, asyncio | An exception in a hook during cancellation returned an open transaction. Fixed. A precedent for PY-7 |
| SQLAlchemy | [#13657](https://github.com/sqlalchemy/sqlalchemy/issues/13657) and [#13699](https://github.com/sqlalchemy/sqlalchemy/issues/13699) | Closed 2026-10-07 and 2026-10-19 | Each fixed within about a day. #13699 is the cancellation fix in 2.1.6 |
| Django | #30490, #34610, and the 2023 forum thread (the audit's §5.2) | Declined | Migration locking. Not pursued |

## 5. Ranking A: severity and real-world impact

| Rank | ID | Failure class | Consequence | Who can hit it | Why this rank |
| --- | --- | --- | --- | --- | --- |
| 1 | PY-1 (a and b) | False transaction success | Every write in the transaction is lost. The API, `Transaction.status`, and downstream hooks report success | psycopg 3 code that catches a database error inside a transaction and continues. Through it: SQLAlchemy Core, SQLAlchemy ORM's `execute` path on psycopg, Django's manual commits, and Django's raw-cursor `on_commit` path | Silent, and the widest reach among Python stacks |
| 2 | PY-2 | False transaction success | The same | asyncpg code, Tortoise, and SQLAlchemy asyncio on asyncpg | The same severity. No report exists |
| 3 | PY-3 | Silent data loss | One object's write is lost, and `save()` returned normally | Tortoise code that reuses an instance after a rollback: retry wrappers, error handlers | Silent. Needs instance reuse |
| 4 | PY-6 | Cross-tenant or privilege carryover | The next borrower runs as the previous borrower's role. Row-level security keyed on the role is bypassed | Code on asyncpg's own `Pool`, and Tortoise, that uses session-level `SET ROLE` | The default configuration, whose docstring promises a reset |
| 5 | PY-5 | Cross-tenant state, behind a mitigation that does nothing | Role, GUC, `search_path`, timeout and temp tables carry over despite the documented reset | SQLAlchemy and psycopg 3 users who adopted the recipe | Silent. It hits the people who tried to protect themselves |
| 6 | PY-7 | Unsafe connection reuse | The next checkout commits the doomed writes | A commit that raises before `COMMIT`, on a healthy connection | Severe, but the trigger is rare |
| 7 | PY-4 | Incorrect rollback claim | Rollback hooks act on a committed transaction | Async code under level-triggered cancellation with a slow `COMMIT`. Possibly lost replies too (CHK-4) | Rare. The impact depends on how the hook is used |
| 8 | PY-8 | Wrong exception type | `except tortoise.exceptions.IntegrityError` misses COMMIT-time violations | Tortoise with deferred constraints | Loud, not silent |

## 6. Ranking B, and the execution order

### 6.1 Ranking B: best contributions for an independent developer

Receptiveness is what was observed on 2026-10-24. Acceptance is Judg.

| Rank | ID | Vehicle | Reproducibility | Ownership | Size | Regression tests | Receptiveness | Acceptance | Impact per effort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PY-1b | A comment on #1453 | 3 of 3, with a control | psycopg alone | A comment | Designed; a raising fix conflicts with `test_outer_transaction_error` (corrected 2026-10-24) | One maintainer writes most of the code. No reply on #1453 in three days | A comment needs no acceptance. A `status`-only fix to `transaction()` conflicts with no test found | High |
| 2 | PY-8 | A pull request | 3 of 3 | Tortoise alone | One decorator per backend | Easy | Very high: "just create a PR"; six merges on 2026-10-24 | High | Low impact |
| 3 | PY-5 | A docs change, written by its author | 3 of 3 on psycopg 3 | SQLAlchemy docs | Rewrite one example | A demonstration program | Very high; fixes land fast | High | Medium |
| 4 | PY-3 | An issue, then a PR | 3 of 3, with cross-framework controls | Tortoise alone | Moderate; needs a design choice | Must cover several backends | Very high | Moderate | High |
| 5 | PY-2 | An issue, then a PR | 3 of 3 with a control; a PPCS FAIL | asyncpg | Small | Easy; a raising fix conflicts with `test_timeout_06` (corrected 2026-10-24) | Low for issues. Outside PRs do get merged | Moderate | High |
| 6 | PY-7 | A discussion, written by its author | Ext, adversarially reviewed | SQLAlchemy Core | Small | Existing test classes | Very high | Moderate: reachability will be questioned | Medium |
| 7 | PY-6 | An issue | 3 of 3, plus psql | asyncpg | One statement and a capability flag | The pattern of #1392 | Low; #1392 is unreviewed | Moderate: compatibility | Medium |
| 8 | PY-4 | A discussion, written by its author, after CHK-4 | 3 of 3, two releases | Shared with the driver and runtime | Docs, or an event change | Hard to test | Very high | Low to moderate (#12728) | Medium |

### 6.2 Combining the two rankings

The brief puts data loss, false outcomes, unsafe reuse and tenant isolation first, so severity weighs more than feasibility.

- **Weights.** Severity (rank A) counts 60%, feasibility (rank B) 40%.
- **Score.** 0.6 × rank A + 0.4 × rank B. Lower comes first.
- **Precision.** The ranks are ordinal judgments, so differences under about 0.5 mean nothing.

| ID | Rank A | Rank B | Score |
| --- | --- | --- | --- |
| PY-1b | 1 | 1 | 1.0 |
| PY-2 | 2 | 5 | 3.2 |
| PY-3 | 3 | 4 | 3.4 |
| PY-5 | 5 | 3 | 4.2 |
| PY-6 | 4 | 7 | 5.2 |
| PY-8 | 8 | 2 | 5.6 |
| PY-7 | 6 | 6 | 6.0 |
| PY-4 | 7 | 8 | 7.4 |

### 6.3 Execution order

1. **PY-1b:** the follow-up comment on psycopg#1453.
2. **PY-2:** the asyncpg issue.
3. **PY-3:** the Tortoise issue. A PR follows once the maintainers choose a fix.
4. **PY-5:** the SQLAlchemy docs, written by the author, after CHK-3.
5. **PY-6:** the asyncpg role issue.
6. **PY-8:** the Tortoise translation PR. It is independent of PY-3 and can be done at any time.
7. **PY-7:** SQLAlchemy P5a, written by the author, after CHK-7. It is ready, and can move earlier if the author prefers. It goes to the same maintainers as PY-5, so leave time between the two.
8. **PY-4:** SQLAlchemy `after_rollback`, written by the author, after CHK-4 and P5a's reception.

This is a priority order, not a strict queue. Prerequisites set the calendar (§14).

### 6.4 Why PY-1b comes before PY-2

- **It is the smallest action, with the most complete evidence.**
  - It is a comment on an issue that is already filed: no new issue, no code.
  - Its evidence is a three-repetition run with a control, psycopg's own documentation, and a maintainer's statement.
- **Its timing matters.**
  - No fix for #1453 has been designed yet. The maintainer should see both commit paths before deciding, because they are separate code.
  - A fix in `Connection._commit_gen` alone would leave `Transaction.status` wrong.
  - On the `transaction()` path, a fix that only corrects `status` conflicts with no existing test, which may make the first step easier. A fix that raises conflicts with `test_outer_transaction_error` (corrected 2026-10-24).
- **It frames PY-2.**
  - The asyncpg report can point to #1453 for the same PostgreSQL behaviour.
  - If psycopg's maintainer answers first, for example on the exception class, PY-2 can use that answer.
  - PY-2 should not wait for that reply, though. It is drafted in the same week.

## 7. Proposed minimal fixes (not implemented)

Each entry gives the location, the incorrect assumption, the smallest correction, the layer, and whether to open an issue first or submit a PR directly.

**PY-1b and PY-1a: psycopg.** Driver.

- **Where:**
  - `psycopg/transaction.py`, `BaseTransaction._commit_gen` (133–140);
  - for `commit()`, `psycopg/_connection_base.py`, `BaseConnection._commit_gen` (577–595).
- **Incorrect assumption:** that a `COMMAND_OK` reply to `COMMIT` means the transaction committed. In `Transaction`, also that it will succeed, since `status` is set first.
- **Correction:**
  1. Keep the result of the outermost `COMMIT`. Set `COMMITTED` only after it returns.
  2. If `result.command_status == b"ROLLBACK"`, set a rolled-back (or failed) status and raise a `psycopg.Error` subclass.
  3. Prefer a `DatabaseError` subclass. Django's `atomic()` then takes its failure path (`except DatabaseError` around `commit()`; the audit's H1), and SQLAlchemy wraps the error as a DBAPI error.
  4. **For `commit()`:** the same check, once the maintainer decides about `test_auto_transaction_fail`.
  5. **Pipeline mode:** `_exec_command` returns `None` there. Either check the command status where the pipeline processes that result, or exclude pipeline mode explicitly.
- **First step:** the comment (§10). A PR only after the maintainer agrees on the exception class, the status value, and `commit()`.

**PY-2: asyncpg.** Driver.

- **Where:** `asyncpg/transaction.py`, `Transaction.__commit` (175–192).
- **Incorrect assumption:** an `execute('COMMIT;')` that does not raise has committed.
- **Correction:** in the non-nested case, keep the returned status. If it is `'ROLLBACK'`, set the state to `ROLLEDBACK` or `FAILED`, then raise an asyncpg exception. The class is the maintainers' choice.
- **First step:** an issue, with a conditional offer of a PR.

**PY-3: Tortoise.** ORM.

- **Where:**
  - `tortoise/models.py`, `Model.save()` (1131–1195);
  - for option (a), also `rollback` and `savepoint_rollback` in each `tortoise/backends/*/client.py`, and the transaction contexts in `tortoise/backends/base/client.py` (373–430).
- **Incorrect assumptions:**
  - that `_saved_in_db` means the row exists, though it is set inside a transaction that may roll back;
  - that an UPDATE matching no row succeeded.
- **Correction (a).** Record the instances that `save()` inserted in the current transaction or savepoint. When that scope rolls back, set their `_saved_in_db` back to False. A database-generated primary key is replaced at the next INSERT.
- **Correction (b).** When `execute_update()` sent an UPDATE that matched 0 rows, fall back to INSERT (Django's rule), or raise as `force_update` does. Apply this only on backends whose count means matched rows, and never when no statement was sent.
- **First step:** an issue asking which option the maintainers prefer, then a PR.

**PY-4: SQLAlchemy.** Documentation, with an optional behaviour change.

- **Where:**
  - the docstring of `SessionEvents.after_rollback` in `lib/sqlalchemy/orm/events.py` (1882–1898);
  - for behaviour, `SessionTransaction.rollback` in `orm/session.py` (1358–1414), with `_commit_impl` and `_handle_dbapi_exception` in `engine/base.py`.
- **Incorrect assumption:** that a failed `COMMIT` followed by a Session rollback means the database rolled back.
- **Correction (docs; the smallest).** State that the event also follows a failed or interrupted `COMMIT`, without a DBAPI rollback. State that the outcome is unknown when the connection was invalidated during `COMMIT`.
- **Correction (behaviour; optional).** Emit only `after_soft_rollback` when the root commit raised and the connection was invalidated.
- **First step:** a discussion, written by the author, after CHK-4.

**PY-5: SQLAlchemy docs.**

- **Where:** the section "Temporary Table / Resource Reset for Connection Pooling" in `lib/sqlalchemy/dialects/postgresql/base.py` (277–336).
- **Incorrect assumptions:**
  - that statements run in the hook persist, although the hook ends with `rollback()`;
  - that `RESET ALL` covers the role.
- **Correction.** The example below has not been run in this form; CHK-3 runs it.

  ```python
  @event.listens_for(postgresql_engine, "reset")
  def _reset_postgresql(dbapi_connection, connection_record, reset_state):
      # end the transaction first, so that the reset below is not undone by it
      dbapi_connection.rollback()
      if not reset_state.terminate_only:
          # DISCARD ALL cannot run inside a transaction block
          autocommit = dbapi_connection.autocommit
          dbapi_connection.autocommit = True
          try:
              cursor = dbapi_connection.cursor()
              cursor.execute("DISCARD ALL")
              cursor.close()
          finally:
              dbapi_connection.autocommit = autocommit
  ```

  Notes to go with it:
  - It is meant for psycopg2 and psycopg 3. CHK-3 checks both before anyone proposes it.
  - It also discards settings made with `SET SESSION` in a `connect` handler. Use startup `options`, or a `checkout` handler, for those instead.
  - It is not meant for the asyncpg dialect. `DISCARD ALL` would deallocate asyncpg's prepared statements, which is why asyncpg avoids it (#270).
- **First step:** a discussion or a docs PR, written by the author.

**PY-6: asyncpg.**

- **Where:**
  - `Connection.get_reset_query` in `asyncpg/connection.py` (1763–1790);
  - the `reset()` docstring (1567–1594);
  - the `create_pool` docs (`pool.py`, 1320–1340);
  - the server capabilities.
- **Incorrect assumption:** that `RESET ALL` resets all session configuration.
- **Correction.** Append `RESET ROLE;` behind a server capability, as #1392 does for `DISCARD TEMP`, and update the docstrings. If the maintainers prefer, correct the docstring instead and document a `reset=` callback that adds `RESET ROLE`.
- **First step:** an issue.

**PY-7: SQLAlchemy Core.**

- **Where:** `RootTransaction._do_commit` and `_close_impl` in `engine/base.py` (2697–2742), and the reset skip in `Connection.close()` (`_close_special`, `pool/base.py`).
- **Incorrect assumption:** that a transaction `_do_commit` deactivated has been resolved.
- **Correction:** after a failed commit, do not report `transaction_was_reset=True`, so the pool resets. Or send the DBAPI rollback while the connection is valid.
- **First step:** a Usage Questions discussion, written by the author (the venue decided on 2026-10-18).

**PY-8: Tortoise.**

- **Where:** `TransactionWrapper.commit`, and `rollback`, in `tortoise/backends/{asyncpg,psycopg,mysql,sqlite,odbc}/client.py`.
- **Incorrect assumption:** that `COMMIT` cannot raise an integrity error. With deferred constraints, it can.
- **Correction:** apply the backend's `translate_exceptions` to `commit()`, and to `rollback()`, as `begin()` already has.
- **First step:** a PR, asking whether the omission was deliberate.

## 8. Required regression tests (designed, not written or run)

"Before" is what the probes observed on the pinned versions. "After" is the intended behaviour.

**PY-1b: psycopg.** In `tests/test_transaction_async.py`; psycopg generates the sync tests from the async ones.

1. **A caught error, then a normal exit from the block.**
   - Before: no exception, and `COMMITTED` (Audit).
   - After: the exit raises; `tx.status` is not `COMMITTED`; `aconn.pgconn.transaction_status` is `IDLE`; a second connection sees no row.
   - An exit that raises also changes `test_outer_transaction_error` (`tests/test_pipeline.py:506`) and its async copy (corrected 2026-10-24).
2. **Control: an inner `transaction()` catches the error.** The outer block commits, `status` is `COMMITTED`, and the row is visible, before and after.
3. **`COMMIT` itself raises** (a deferred FK) inside `transaction()`.
   - Before: `COMMITTED`, predicted by Src (H-a; CHK-1).
   - After: `tx.status` is not `COMMITTED`.
4. **If `commit()` changes too:**
   - rewrite `test_auto_transaction_fail` (`tests/test_connection_async.py:401`) to expect the error, keeping its `IDLE` and row-absent assertions;
   - add a pipeline-mode case to `tests/test_pipeline_async.py`.

**PY-2: asyncpg.** In `tests/test_transaction.py`. A fix that raises also changes `tests/test_timeout.py::test_timeout_06` and `test_timeout_04`, which exit a transaction block normally after a caught timeout (corrected 2026-10-24).

1. **`async with con.transaction():`** insert, then catch the `UniqueViolationError` from a duplicate.
   - Before: the block exits normally (P1).
   - After: the exit raises; `con.is_in_transaction()` is False; the row is absent from a second connection.
2. **The explicit form**, `tr.start()` … `tr.commit()`. After: `commit()` raises. A second `commit()` or `rollback()` raises `InterfaceError`, as it already does for a finished transaction.
3. **Control: a nested `async with con.transaction():` catches the error.** The outer commit succeeds and the row is visible.
4. **Optional:** the same with `40001` (a REPEATABLE READ conflict), to show that the check does not depend on the SQLSTATE.

**PY-3: Tortoise.** In `tests/test_transactions.py`, run on every backend in CI.

1. **The lost write.** Create `obj = Model(...)`. Inside `in_transaction()`, call `await obj.save()`, then raise, so the transaction rolls back. Then call `await obj.save()` again.
   - Before: the call returns, and 0 rows exist (P4).
   - After: the row exists, or the call raises, depending on the chosen semantics.
2. **The savepoint variant.**
   - An outer `in_transaction()` contains a nested `in_transaction()` that saves, then raises; the exception is caught.
   - `obj.save()` runs again in the outer block, and the outer block commits.
   - After: the row exists.
3. **Controls:**
   - a `save()` with unchanged values on an existing row succeeds on every backend, MySQL included;
   - `force_update=True` on a missing row still raises;
   - an update with no effective fields still returns.

**PY-4: SQLAlchemy.** In `test/orm/test_events.py`, or under `test/ext/asyncio`.

- **Setup:** a DBAPI fixture whose `commit()` raises a disconnect error after sending.
- **Before:** `after_rollback` fires (P3; Src).
- **After, with a docs fix:** the event sequence is unchanged, and the test pins it.
- **After, with a behaviour fix:** no `after_rollback`, and one `after_soft_rollback`.

**PY-5: SQLAlchemy docs.** P7's three variants serve as the demonstration.

- The default and the documented recipe carry state.
- The corrected recipe resets the role, the GUC, `search_path`, `statement_timeout` and the temp table, on psycopg 3 and on psycopg2 (CHK-3).
- An engine at `isolation_level="AUTOCOMMIT"` stays in autocommit after a reset.

**PY-6: asyncpg.** In `tests/test_pool.py`, in the style of #1392's `test_pool_release_drops_temp_tables`.

1. **The leak.** Use a pool of one, and a role with a unique name. Acquire, run `SET ROLE r`, release, then reacquire the same connection (`con._con`).
   - Before: `current_user == r` (P2).
   - After: `current_user == session_user`.
2. **A connection-time role is kept.** For a pool with `server_settings={'role': r}`, `current_user == r` after a release and reacquisition.
3. **Teardown.** Drop the role: roles are cluster-wide.

**PY-7: SQLAlchemy Core.** As the review proposes, `ResetAgentTest` in `test/engine/test_transaction.py` gains a failed-commit case: a `commit` listener that raises, then `close()`.

- **Before:** no rollback is sent, and the next checkout inherits the transaction (Ext).
- **After:** the DBAPI `rollback()` is called, or `PoolResetState.transaction_was_reset` is False, and the next checkout starts a new transaction.

**PY-8: Tortoise.** A deferred-FK violation inside `in_transaction()`, on the PostgreSQL backends, and on SQLite with a deferred FK.

- **Before:** a raw `asyncpg.exceptions.ForeignKeyViolationError` (P5).
- **After:** `tortoise.exceptions.IntegrityError`.

## 9. Upstream maintainer and compatibility considerations

**psycopg.**

- **Process.** Nearly every PR merged in the last month is the maintainer's own (#1407 to #1440); one outside documentation PR was merged (#1410). Get agreement in a comment before opening a PR.
- **No policy on AI-written text was found** in the paths checked: the repository root and `.github/`.
- **Compatibility:**
  - `test_auto_transaction_fail`;
  - `test_outer_transaction_error` and its async copy, for a block that raises (corrected 2026-10-24);
  - code that follows psycopg 2 habits. Judg: psycopg2's `commit()` behaves the same way, but this was not checked here;
  - pipeline mode;
  - the exception class. A `DatabaseError` makes Django's `atomic()` roll back and drop `on_commit`, and the class decides how SQLAlchemy wraps the error.
- **Expect the question** of why the application caught the error, since psycopg's docs already say to roll back. Answer with the documented `transaction()` contract and the `status` docs.

**asyncpg.**

- **Process.** The issue template asks for versions, SaaS, pgbouncer, pip, Cython, and whether both asyncio and uvloop reproduce it.
- **Responsiveness:**
  - no maintainer reply on #1130 (2024), #1265 (2025, filed by zzzeek with a patch), #1293, #1386, or PR #1392;
  - outside PRs were merged in September 2026 (#1369, #1372, #1373).

  Expect silence on issues. A well-tested PR may move faster than an issue.
- **No security policy or AI policy was found.**
- **Compatibility:**
  - PY-2 changes `commit()` for code that swallows errors, including `test_timeout_06` and `test_timeout_04` (corrected 2026-10-24);
  - PY-6 changes roles set in `init`;
  - server capabilities (CockroachDB, Redshift, CrateDB) must gate any new reset statement;
  - `DISCARD ALL` is off the table (#270).

**Tortoise ORM.**

- **Process.** `docs/CONTRIBUTING.rst`: "If you want to contribute, check out the issues, or just create a PR." The default branch is `develop`. Six PRs were merged on 2026-10-24.
- **No AI policy was found.**
- **Compatibility:**
  - option (b) for PY-3 depends on each backend's row-count semantics (#1212);
  - option (a) touches the transaction wrapper of every backend;
  - PY-8 changes the exception types that users may catch today.

**SQLAlchemy.**

- **Policy.** `.github/CONTRIBUTING.md` (lines 48–62): "AI/LLM generated content is not spammed onto SQLAlchemy discussions, issues, or PRs, whether this is cut and pasted, fully automated, or even just lightly edited. Please use your own words". `CODE_OF_CONDUCT.md` asks participants to communicate "as a human, in a non-automated fashion", and allows LLM help with code that demonstrates an issue. So:
  - no agent posts anything;
  - the author writes every word of prose;
  - scripts and outputs can come from this research.
- **Venue.** The bug form routes reports to a Usage Questions discussion, which maintainers convert to issues (#13656 became #13657).
- **Responsiveness.** Very high: #13657 was fixed the day after it was filed, and #13699 the same day.
- **Compatibility:**
  - PY-5's corrected recipe discards connect-time `SET SESSION` state and server-side prepared statements;
  - a behaviour fix for PY-4 changes event delivery;
  - PY-7's fix adds a rollback round trip after a failed commit. psycopg's `rollback()` sends nothing when the connection is idle (Src, `_connection_base.py:597-619`).
- **Precedents:**
  - #12728: in-flight commits that cancellation did not stop were judged a driver matter;
  - #13381: fixed;
  - the `robots involved` label (the audit's §8.3).

**Django.** No contribution is recommended. If the optional note on the native pool is pursued, check Django's current contribution policy first; it was not checked here.

## 10. Immediate contribution sequence (Workstream 1)

Each entry gives the vehicle, an outline of the content (not the prose), the prerequisites, and when to stop.

- **Approval.** Every entry needs approval of its exact text.
- **Recording.** Record each post in `docs/upstream-submissions.md`. Check that file for another session's uncommitted edits first.

1. **PY-1b: comment on psycopg#1453.**
   - **Outline:**
     1. The second surface: `transaction()` exits normally and `tx.status` is `committed`, while PostgreSQL aborted. Three repetitions, with a savepoint control.
     2. One sentence each, quoting the documented block contract and the `status` docs ("final outcome", "retry logic").
     3. The two commit paths are separate (`Connection._commit_gen`, `BaseTransaction._commit_gen`), so a fix in one does not reach the other.
     4. An observation: `test_auto_transaction_fail` expects `commit()` to return after an error. `test_outer_transaction_error` does the same for the block. A `status`-only fix conflicts with neither (corrected 2026-10-24).
     5. A conditional offer of tests or a PR.
     6. Appendix A's program and output, in `<details>`.
   - **Prerequisites:**
     - re-check #1453 and `master`;
     - CHK-1 is optional, and its result goes in only if it was run;
     - aim for about 30–40 visible lines, the format of earlier comments.
   - **Stop if:**
     - #1453 is closed as intended behaviour. Record that; do not argue.
     - A fix covering `Transaction` lands. Verify it and record it.
     - A maintainer has already raised `transaction()`.
2. **PY-2: asyncpg issue.**
   - **Title,** along the lines of "Transaction.commit() returns normally when PostgreSQL answers COMMIT with ROLLBACK".
   - **Outline:**
     - the template's fields;
     - a standalone script derived from P1's asyncpg arms (managed, explicit, raw `execute`, savepoint control), with its full output;
     - what happened;
     - the expected behaviour: raise when the server completes `COMMIT` with `ROLLBACK`, without prescribing the implementation;
     - one line each:
       - where the status is dropped (`Transaction.__commit`);
       - that `40001`, `40P01` and `57014`, caught at statement level, end the same way (dropped from the draft on 2026-10-24, after the outside review);
       - that Tortoise's `in_transaction()` and SQLAlchemy's asyncpg dialect are callers;
     - a reference to #1453, the psycopg counterpart.
   - **Prerequisites:** CHK-2 (run the exact script to be posted, three times, including on uvloop); a fresh duplicate search.
   - **Stop if:**
     - a duplicate appears. Comment there instead.
     - asyncpg documents the behaviour. Switch to a documentation note for Tortoise or SQLAlchemy.
3. **PY-3: Tortoise issue.**
   - **Outline:**
     - the script (P4's Tortoise part, made standalone) and its output;
     - `_saved_in_db` and the ignored count, with two source references;
     - the contrast with `force_update`;
     - one sentence: Django and SQLAlchemy persisted the same retry;
     - the question of option (a) or (b), with the #1212 caution in one line;
     - a conditional offer of a PR.
   - **Prerequisites:** CHK-5 (a) and (b): recommended before posting, required before a PR.
   - **Stop if:** the maintainers say that reusing an instance after a rollback is unsupported. Propose a documentation note instead.
4. **PY-5: SQLAlchemy recipe, written by the author.**
   - **Evidence package:**
     - P7's program and outputs;
     - CHK-3's statement log, and its psycopg2 result;
     - the corrected example;
     - the page's own search-path note.
   - **The author writes the discussion, or a docs PR, in their own words.** The code can be adapted from here.
5. **PY-6: asyncpg role issue.**
   - **Outline:**
     - the script (a pool of one; `SET ROLE`; release; acquire; `current_user`) and its output;
     - the docstring sentence;
     - PostgreSQL's `RESET ALL` exclusion, and what `RESET ROLE` does;
     - the proposal: `RESET ROLE` behind a capability, as #1392 does, or a corrected docstring;
     - the `init` compatibility note;
     - references to #1293 and #1392.
   - **Prerequisites:** run the script to be posted three times, on a non-superuser login. CHK-6 is optional.
6. **PY-8: Tortoise PR.**
   - **Content:** `translate_exceptions` on `commit()`, and on `rollback()`, in each backend, with PY-8's test.
   - **Description:** asks whether the omission was deliberate.
   - **Prerequisite:** run Tortoise's test suite locally for the backends touched.
7. **PY-7: P5a, written by the author.** Run CHK-7 and a fresh duplicate search. Then the author posts the approved draft's content, in their own words, in Usage Questions.
8. **PY-4, written by the author.**
   - **When:** after CHK-4.
   - **Evidence package:** P3's program and outputs, CHK-4's result, and the source path PY-4 shares with P5a.
   - **Framing and venue:** decide after P5a's reception.

## 11. Targeted verification backlog (Workstream 2)

None of these was run for this roadmap.

- **Server.** Each check uses its own throwaway container, from PPCS's pinned image, on its own port. Never run `pnpm run pg:up`, and never use `ppcs-postgres`.
- **Method.** Three repetitions. Record outputs and hashes beside the program.

| ID | For | Question | Minimal design | Effort | Status |
| --- | --- | --- | --- | --- | --- |
| CHK-1 | PY-1b (optional) | Does `Transaction.status` stay `committed` when `COMMIT` raises (a deferred FK)? Does `AsyncConnection.transaction()` match the sync form on the caught-`23505` pattern? | Appendix A's program, plus two arms | 30 min | Not started |
| CHK-2 | PY-2 (required before posting) | The exact standalone script to post, on asyncio and on uvloop | P1's asyncpg arms, extracted | 1 h | Not started |
| CHK-3 | PY-5 (required) | Did the recipe's statements run and then roll back? What does the recipe do on psycopg2, the driver in its URL? Does the corrected example reset everything on both drivers, and keep an `isolation_level="AUTOCOMMIT"` engine in autocommit? | P7 with `log_statement=all` captured for the hook's session; a psycopg2-binary virtualenv | 1–2 h | Not started |
| CHK-4 | PY-4 (required) | Without cancellation, does `after_rollback` fire when the `COMMIT` reply is lost and PostgreSQL commits? Check a sync `Session` on psycopg, and `AsyncSession` | A small TCP proxy that forwards `COMMIT`, then closes the client socket (the shape of PPCS category E). Or P3's gate with a client-side socket close. SQLAlchemy 2.1.6. PP-3 is the gated alternative | 2–3 h | Not started |
| CHK-5 | PY-3 (recommended before the issue; required before a PR) | (a) Did the retry send an UPDATE that matched 0 rows? (b) Does the savepoint variant lose the write? (c) Does the psycopg backend behave the same? | P4's Tortoise part with a statement log, plus a nested `in_transaction()` arm | 1 h | Not started |
| CHK-6 | PY-6 (optional) | With `server_settings={'role': r}`, does `RESET ROLE` return to `r`? Does a custom `reset=` that adds `RESET ROLE` work as the documented workaround? | P2's asyncpg flavour, plus two arms | 30 min | Not started |
| CHK-7 | PY-7 (required) | Does `check/p5a_close_v2.py` still reproduce on SQLAlchemy 2.1.6? | Re-run it in a 2.1.6 virtualenv | 15 min | Not started |

The gap analysis's full cancellation investigation (its §9) is not on this list. For the upstream purpose, CHK-4 replaces it. The rest is a decision about PPCS's evidence model (PP-7).

## 12. PPCS development backlog (Workstream 3)

- **Approval needed.** New families, trigger categories, changes to the evidence model, and new adapter families all need maintainer approval (`AGENTS.md`, "Approval gates").
- **No reruns for their own sake.** Nothing here should be built only to show again what P1–P7 already showed.

| ID | Item | Why | Gate |
| --- | --- | --- | --- |
| PP-1 | Preserve the evidence. Commit the two reports, their evidence directories, this roadmap and the tracker, in commits separated by topic. Bring the unversioned adjacent evidence under version control: `../sqla-tx02-repro/` and `../tortoise-tx-investigation/` | Upstream texts and PPCS docs cite them | Approval to commit. Check for other sessions' uncommitted edits |
| PP-2 | Apply the audit's §4.4 corrections to PPCS text: the Core `commit` event; the scope of the Django `atomic()` claim; Django's FAIL count; the scope of `after_commit` in PR-01 | Accuracy of public PPCS text | A documentation task. The shared files carry other sessions' edits |
| PP-3 | Declare SQLAlchemy ORM's `after_rollback` as a rollback-claim channel in `adapters/sqlalchemy`, and re-record `TX-01B.commit-reply-unseen` | Exercises TX-01B.2, which PPCS defines but has never exercised for Python. A gated answer to CHK-4 | An adapter change and a re-recording. The maintainer approves the task |
| PP-4 | After upstream fixes land, re-run on the fixed releases: TX-01A for SQLAlchemy Core and Tortoise, and the Python rows of PR-01 | PPCS maintenance includes "tests of proposed fixes" (master plan) | Maintenance. The task's assignment is enough |
| PP-5 | Candidate family: ORM instance state after a rollback (the gap analysis, §7.3) | Fits the existing lost-write rule. It asks a new question of PPCS's other ORM adapters: MikroORM, TypeORM, EF Core, Active Record, Hibernate. It is not for showing the Tortoise result again | A new family: approval |
| PP-6 | Candidate family: session state across pool checkouts (§7.2) | Only for the cross-language question: Node, JVM, .NET and Go pools. Needs a role per run, a second schema, and a non-superuser login | A new family and fixture: approval |
| PP-7 | Candidate trigger category: application cancellation (§7.1), with async psycopg and SQLAlchemy asyncio adapters | Only after CHK-4 and SQLAlchemy's response. A new category changes the evidence model | A change to the evidence model: approval |

## 13. Findings that should not be pursued

| Item | Why not | Instead |
| --- | --- | --- |
| Reports to SQLAlchemy Core or Django about the commit tag | #1453 covers the driver. The tracker forbids them (P1) | — |
| SQLAlchemy ORM `after_commit` (Draft C, PY-9) | Downstream of PY-1 and PY-2 | Revisit if both drivers decline |
| Django's raw-cursor `on_commit` | Documented as unspecified | — |
| A Django MG-02 bug report | Declined twice (#30490, #34610) | An optional documentation note on the forum, at low priority |
| Django TX-02 not-sent | No production trigger | Keep it in PPCS |
| Session state in psycopg_pool, and Django's persistent connections | Documented behaviour | An optional documentation note on Django's pool |
| psycopg `AsyncConnectionPool` under level-triggered cancellation (PY-13) | No claim is made, and the outcome is documented | — |
| New SQLSTATE experiments; PR-01 re-runs | The same mechanism (P6) | Cite P6 in PY-1 and PY-2 |
| A comment on Tortoise #1094 | A different mechanism, never established | PY-3, as a new issue |
| Adding the role to asyncpg PR #1392 | Someone else's PR, with a different scope | PY-6, as its own issue |
| Recommending `DISCARD ALL` to asyncpg | Rejected in #270 | `RESET ROLE` |
| Tortoise's skipped rollback after a class-25 error | The consequence was never run. It needs an application that continues after an error inside a nested block | Mention it only if the PY-8 discussion invites it |
| SQLAlchemy Draft A (SA-03) and Draft B (SA-02) | A waits for P5a's reception. B has no realistic trigger | — |
| Starting the gap analysis's full cancellation investigation now | CHK-4 answers the upstream question. The rest is a decision about PPCS's evidence model | PP-7, later |
| Alembic race work | Stopped by an earlier decision | — |
| Agent-posted text on SQLAlchemy | Its rules forbid it | The author writes it |

## 14. 30-day execution plan

- **Start:** the plan assumes work begins on Monday 2026-10-26.
- **Follow-ups,** per `docs/upstream-submissions.md` §4:
  - allow about two weeks for a first reply;
  - then send one polite follow-up;
  - decide at about four weeks.

| Window | Work | Output |
| --- | --- | --- |
| Week 1 (10-26 to 11-01) | Re-check #1453. Optionally run CHK-1. Draft PY-1b, get approval, post. Run CHK-2. Draft PY-2, get approval, post. Decide on PP-1 (committing the evidence) | The #1453 comment; the asyncpg issue; tracker updates |
| Week 2 (11-02 to 11-08) | Run CHK-5. Draft PY-3, get approval, post. Draft PY-6, get approval, post. Prepare the PY-8 PR: local tests, approval, open. Run CHK-3, and hand the PY-5 evidence package to the author | The Tortoise issue and PR; the asyncpg role issue |
| Week 3 (11-09 to 11-15) | The author posts PY-5. Run CHK-7; the author posts PY-7. Check #1453; send a follow-up only if it has been silent since the comment | Two SQLAlchemy discussions |
| Week 4 (11-16 to 11-22) | Run CHK-4, or PP-3. Decide on PY-4. Answer maintainers. Prepare PRs only where a maintainer agreed: psycopg, asyncpg, and Tortoise PY-3. One follow-up each on PY-2 and PY-3, if silent | Decisions recorded |
| Day 30 (11-23) | Review what was accepted, declined, or ignored. Update this roadmap and the tracker. Decide on PP-5 to PP-7 | A revised plan |

**Success at day 30:**

- every Workstream 1 item is posted, or explicitly dropped;
- each one has a recorded maintainer response, or a recorded lack of one;
- at least one PR is under review where a maintainer agreed.

## Appendix A. Upstream and source checks, 2026-10-24

All were read-only: `gh`, and `curl` to PyPI and postgresql.org. Nothing was posted.

| Check | Result |
| --- | --- |
| psycopg#1453, with `gh issue view` | Open, no comments, no labels. The body covers `commit()` and asks that it raise |
| psycopg #967, #969, PR #1184, #1451, PR #1454 | As in §4 |
| psycopg duplicate searches: `commit ROLLBACK`, `transaction status committed`, `command_status commit`, `commit aborted transaction`, `INERROR commit`, `commit silently` | Only #1453 is relevant |
| psycopg `master` `99356800e`: `transaction.py`, `_connection_base.py`, `tests/test_connection*.py`, `tests/test_transaction_async.py`, `docs/basic/transactions.rst`, `docs/advanced/async.rst`, `docs/news.rst` | As quoted in §3.2 A, D and E |
| asyncpg duplicate searches: commit and tag (six phrasings), role and reset (seven phrasings) | No match. Related: #1130, #1293, PR #1392, #270, #1386, #1265 |
| asyncpg `master` `13b01910d`: `transaction.py`, `tests/test_transaction.py`, `docs/api/index.rst`, `.github/ISSUE_TEMPLATE.md`; no `SECURITY.md` in the repository or the organization | As quoted in §3.2 B and F |
| asyncpg merged PRs | Mostly the maintainer's own. Outside PRs #1369, #1372, #1373 (September 2026) |
| Tortoise duplicate searches: `saved_in_db`, `rollback save`, `rollback instance`, `retry save`, `IntegrityError commit`, `commit exception`, `force_update`, `not saved` | #1094 (symptom only), #1212 (`force_update` on MySQL). No match for PY-3 or PY-8 |
| Tortoise `develop` `536fc3abd`: `models.py`, `backends/asyncpg/client.py`, `docs/CONTRIBUTING.rst` | As quoted in §3.2 C and §9 |
| SQLAlchemy issue searches: `after_rollback` with invalidation, cancellation or commit; `CancelledError commit`; `anyio cancel commit`; reset recipe, `DISCARD ALL`, `RESET ALL`. Discussion searches through GraphQL | No match for PY-4 or PY-5. Related: #12728, #13381, #13657, #13699; discussions #13620, #12848 (cancellation; not these findings) |
| SQLAlchemy `main` `10f4d1e2d`: `orm/events.py`, `orm/session.py`, `engine/base.py`, `dialects/postgresql/base.py`; `.github/CONTRIBUTING.md` | As quoted in §3.2 D, E, G and §9 |
| PostgreSQL 18 docs: `sql-set-role.html`, `sql-discard.html` | `RESET ROLE`: "These forms can be executed by any user", and it returns to the connection-time setting. `DISCARD ALL` "cannot be executed inside a transaction block" |
| Issues, PRs and SQLAlchemy discussions opened from this research's posting account since 2026-10-20 | Among the Python items, only psycopg#1453 is filed. Nothing from this roadmap is posted |
