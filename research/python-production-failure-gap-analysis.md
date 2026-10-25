# Python production persistence failures PPCS does not yet cover

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This analysis asks which production-reachable correctness and reliability failures in Python PostgreSQL backends PPCS does not test, and which new investigations would prevent the most real failures. The subjects are Django, SQLAlchemy ORM and Core, psycopg 3, asyncpg, and Tortoise ORM.

**What this document is, and is not:**

- **It is a planning document.** It does not authorize the work it proposes (`AGENTS.md` rules 2 and 10).
- **It changes nothing recorded.** It changes no adapter, harness file, specification, catalog, or recorded result. Nothing was filed or posted.
- **Its runtime claims come from premise probes** run for this analysis in a throwaway container: [`python-production-failure-gap-analysis/`](python-production-failure-gap-analysis/README.md) holds the programs, outputs, versions and hashes.
  - **They are not PPCS results.** They ran outside the harness, with no CTL-01 or `pg-control` gate.
  - **They are repeated.** Each ran three times, and every repetition agreed.
  - **They are deliberately few.** The probes test the premises the ranking depends on, so most experiments here are designed, not run.
- **A concurrent audit covers the existing Python findings.** [`python-ecosystem-contribution-audit.md`](python-ecosystem-contribution-audit.md) decides which findings are ready for upstream. It cites this analysis's earlier results as "A2", and it owns upstream sequencing. The two documents were coordinated through the `AGENT-*-STATUS.md` notes, which are not for commit.

**Evidence labels**

| Label | Meaning |
| --- | --- |
| **PPCS** | A recorded run in this repository. Three repetitions; suite runs are gated by CTL-01 and `pg-control` |
| **Probe** | A premise probe for this analysis (P1–P7, or a psql check), with its output in `python-production-failure-gap-analysis/output/`. Three repetitions, all agreeing. Not gated |
| **Src** | Source reading of the installed version, with file and line. Not a runtime observation |
| **Doc** | Documentation, quoted. Fetched 2026-10-24 by this analysis's research subagents and taken from their notes; not fetched a second time |
| **Upstream** | Issue-tracker state on 2026-10-24, from the same subagents. The links can change |
| **Ext** | Recorded outside this repository. See the audit's §2.2 |
| **Judg** | This analysis's judgment or hypothesis. Not evidence |

**Versions.** Django 6.1.2, SQLAlchemy 2.1.5 (plus 2.1.6 for one re-check), psycopg 3.3.6 (binary, libpq 18.6; corrected 2026-10-24 from "18.0.6", a misreading of psycopg's `180006`), psycopg-pool 3.3.3, asyncpg 0.32.0, Tortoise ORM 1.1.9, anyio 4.15.1, and Python 3.13.11. The server is PostgreSQL 18.6, at PPCS's pinned digest `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. The Django, SQLAlchemy, psycopg, Tortoise, and asyncpg versions are PPCS's adapter pins.

## 1. Executive summary

PPCS's Python evidence is deep on one axis: what a transaction API reports after a failure that PostgreSQL or the runner produces. It covers a caught `23505` (TX-01A, PR-01), a withheld or rejected savepoint rollback (TX-02), a failed rollback on a pooled connection (TX-03), propagation (TX-04), isolation (TX-05), and connection loss around COMMIT (TX-01B). The four Python adapters are all synchronous except Tortoise, and every one of them declares no rollback-claim channel, so TX-01B.2 has never been exercised for Python.

**The three highest-value missing experiments:**

1. **Cancellation while COMMIT is in flight, in async stacks** (§7.1). An application cancelled its own task while COMMIT waited inside a deferred constraint check. With anyio's level-triggered cancellation:
   - **SQLAlchemy `AsyncSession.begin()`** fired `after_rollback` and `after_soft_rollback`, and **PostgreSQL then committed** the transaction. This happened on asyncpg and on psycopg, and on SQLAlchemy 2.1.5 and 2.1.6. SQLAlchemy documents `after_rollback` as "Execute after a real DBAPI rollback has occurred".
   - **psycopg's `AsyncConnectionPool`** discarded the connection with COMMIT still in flight, and PostgreSQL committed after the API had returned.
   - **asyncpg's pool and Tortoise** ended aborted.

   With asyncio's edge-triggered `task.cancel()`, every stack ended aborted, and SQLAlchemy's rollback events then matched PostgreSQL. PPCS has no cancellation trigger, and no async SQLAlchemy or psycopg adapter. The premise is Probe P3.

   **Scope note, added 2026-10-24.** The edge-triggered result holds for one `task.cancel()`, in an event loop that kept running until each driver had finished its own cancellation. It does not cover a process that exits first, or a second cancellation that arrives first.
   - Uvicorn's graceful-shutdown timeout produces both: under SIGTERM the process ends before the cancelled request's cleanup finishes, and under SIGINT `asyncio.run` cancels the request a second time ([Uvicorn discussion #3232](https://github.com/Kludex/uvicorn/discussions/3232)).
   - That discussion's evidence is a stand-in service, not PostgreSQL. This report does not measure PostgreSQL's outcome on that path.
   - §7.1 has the details.
2. **Session state that survives the connection pool** (§7.2). A unit of work set state and committed; the next unit of work on the same pool of one ran with it:
   - **`SET ROLE`** carried over in all six pools measured, including asyncpg's, whose reset is documented to reset "all session configuration variables".
   - **The rest** carried over in five pools: `search_path`, custom GUCs, `statement_timeout`, session advisory locks, and temp tables. Those five are psycopg_pool, SQLAlchemy's pool on psycopg and on asyncpg, Django's persistent connections, and Django's native pool. The next unit's unqualified insert landed in the previous unit's schema, as the previous unit's role.
   - **SQLAlchemy's documented reset recipe** resets nothing on psycopg 3.

   TX-03 checks transaction state only (Probes P2, P7, psql).
3. **ORM instance state reused after a rolled-back transaction** (§7.3). After a rolled-back `save()`, Tortoise keeps `pk` and `_saved_in_db = True`. A retried `save()` of the same instance in a new transaction issues an UPDATE that matches no row, returns normally, and persists nothing. Django and SQLAlchemy persisted the same retry. No PPCS family checks a write after a rollback (Probe P4).

**Answered here, so not proposed as new PPCS work:**

- **`57014`, `40P01` and `40001` are the PR-01 path.** Each was produced by PostgreSQL at statement level, caught, and the API then completed: 36 runs (Probe P6).
  - **The FAIL shape:** SQLAlchemy Core, asyncpg and Tortoise returned normally while PostgreSQL had aborted the transaction.
  - **The PASS shape:** Django `atomic()` rolled back, with ORM writes.

  The server's statement log shows how each transaction ended: every SQLAlchemy Core, asyncpg and Tortoise transaction with `COMMIT`, and every Django transaction with `ROLLBACK`.

  The PR-01 analogy holds for these stacks. Only a COMMIT that raises, or a timeout that interrupts the client, is a different path.
- **Tortoise's TX-01A FAIL is asyncpg's transaction API.** asyncpg's `Transaction.commit()` and `async with conn.transaction()` complete normally, with `state:committed`, when PostgreSQL answers COMMIT with `ROLLBACK`. asyncpg's raw `execute('COMMIT')` returns the string `'ROLLBACK'`. SQLAlchemy's `postgresql+asyncpg` dialect inherits the behaviour (Probe P1, Src). The audit's §8.2 owns the upstream question.
- **SQLAlchemy ORM's `after_commit` fires on an aborted transaction** when the error came from `Session.execute()` rather than from a flush. This holds on psycopg and on asyncpg (Probe P1). It narrows PR-01's "Answers", which counts the ORM events among the signals that distinguished the abort. The audit's §4.4, item 8, records the correction.
- **A COMMIT that PostgreSQL rejects (a deferred FK) is reported correctly by Django.** `atomic()` raises `IntegrityError 23503`, and `on_commit` does not run. Tortoise raises an untranslated `asyncpg.ForeignKeyViolationError` instead of `tortoise.exceptions.IntegrityError` (Probe P5). SQLAlchemy on psycopg was already measured outside this repository (§2.3).

**Not worth pursuing in PPCS** (§8): new SQLSTATEs on the caught-then-commit path; lost updates and write skew; PgBouncer; idle-in-transaction and transaction timeouts as new cases; outbox and queue-publication tests.

**Recommended next task** (§9): run §7.1 as a standalone research investigation under `research/`, with no harness change, after maintainer approval. §7.3 is the cheapest follow-on that fits the existing evidence model.

**No urgent PPCS correctness issue was found.** Two observations are serious for applications and are recorded, not acted on: the session-state carryover in §7.2, which can cross tenants, and Tortoise's silent lost write in §7.3.

## 2. Existing coverage inventory

### 2.1 The catalog, and the Python results

`specifications/transactions.v1.json` and `specifications/migrations.v1.json` contain 9 families and 24 cases. The Python results are from the root README matrix and the adapters' `FINDINGS.md`.

| Family | What it asserts | Python results (PPCS) | Trigger categories |
| --- | --- | --- | --- |
| CTL-01 | The observer sees a commit, and the absence of a rollback | PASS for all four adapters | none |
| TX-01A | A COMMIT answered `ROLLBACK` is not reported as success | Django PASS, mechanism not exercised. ORM INCONCLUSIVE: flush rolls back first. Core FAIL. Tortoise FAIL, with `mechanism_exercised` false because of the pool reset query | A (a caught `23505`) |
| TX-01B | No commit report without an acknowledgement; no confirmed rollback after an unknown outcome | `conn-lost-before-commit` PASS everywhere. `commit-reply-unseen` PASS, "TX-01B.2 not exercised", everywhere. `commit-reply-discarded` NOT_RUN | B, D, E |
| TX-02 | A failed savepoint rollback does not commit discarded writes | Not-sent: FAIL everywhere. Rejected: FAIL except Django | C, B |
| TX-03 | A connection whose rollback failed is not reused unsafely | PASS everywhere. Django only in `persistent` mode | C, B |
| TX-04 | Nested work lands where the propagation API promises | Savepoint cases PASS. `independent-inner` is not applicable by design | none |
| TX-05 | The requested isolation level is applied | Django and both SQLAlchemy adapters PASS. Tortoise UNSUPPORTED: no isolation parameter | none |
| MG-02, MG-03 | Migration runners coordinate and keep history consistent | Django `MigrationExecutor`: `held`, `session-loss` and `idle-session-timeout` FAIL; MG-03 PASS. The rest are capability-absent | none, B |

Every Python manifest declares `"rollback_claim_channels": []` (`adapters/{django,sqlalchemy,sqlalchemy-core,tortoise}/adapter.json`). TX-01B.2 is therefore "not exercised" for all of them (`docs/methodology.md`, "TX-01B.2 needs a channel").

### 2.2 Outside the catalog, in this repository

| Location | What it covers | Relevance here |
| --- | --- | --- |
| `research/production-reachability/` (PR-01; run `2026-10-19T18-15-49Z-b2c174`; Django follow-up `2026-10-19T20-58-26Z-508b7a`) | A caught `23505`, then the normal completion, with hooks, reuse, and savepoint recovery. SQLAlchemy Core and ORM and Django on psycopg | The caught-error-then-commit path is done. Its "Answers" argue `40P01`, `40001` and `57014` take the same path without running them. P6 runs them |
| `research/production-reachability/reproductions/psycopg_commit_tag.{py,txt}` | psycopg `Connection.commit()` on tag `ROLLBACK`. Filed as psycopg#1453 (`docs/upstream-submissions.md`, P1) | Not repeated |
| [`python-ecosystem-contribution-audit.md`](python-ecosystem-contribution-audit.md) and its directory | psycopg `conn.transaction()` with `Transaction.status` reported `committed` (Appendix A); upstream readiness | Not repeated |
| `research/sqlite-phase0/` | SQLite controls, and a SQLAlchemy Core comparison | Not PostgreSQL. Not used |
| `investigations/mysql-innodb-baseline/` | A MySQL companion runner | Not PostgreSQL. Not used |
| `docs/ownership-benchmark/` (Program B) | The Python cohort: psycopg, SQLAlchemy Core, SQLAlchemy ORM. Application concurrency checks (`test-contract.md` V2-6, V3-9). Pool reset differences "are library behavior, and part B of the transaction task records them as such" (`methodology-plan.md`) | Application-level concurrency belongs there. **"Async is a separate variable for a later study"** (`methodology-plan.md`, "Synchronous code"), so §7.1 does not overlap it |

### 2.3 Outside this repository

The audit's §2.2 lists these locations. Two answer questions this analysis would otherwise have asked:

- **SQLAlchemy 2.1.5, sync, on psycopg: a COMMIT that fails.** The P5a review harness summary (Ext) covers:
  - a deferred `23505` and a `40001` at COMMIT, both of which raise and leave the connection `IDLE` and safe to reuse;
  - `pg_cancel_backend` and `pg_terminate_backend` during a COMMIT slowed by a deferred trigger;
  - an alarm-raised exception during COMMIT, after which the connection went back to the pool `ACTIVE` and the outcome committed later;
  - injected `CancelledError`, `KeyboardInterrupt` and `TimeoutError`.

  Its confirmed defect, P5a, is a client-side exception raised by `commit()`, after which the pool skips the rollback. That is the audit's §8.3.
- **SQLAlchemy identity map, snapshots, and lost updates under READ COMMITTED and REPEATABLE READ** (Ext). It covers `version_id_col`, `with_for_update()` and `refresh(with_for_update=True)`. Every cell matched SQLAlchemy's or PostgreSQL's documented contract, and its report recommends keeping the matrix as application guidance, outside the catalog.

### 2.4 Coverage by failure category

| Category | What PPCS or adjacent work already covers | What is not covered |
| --- | --- | --- |
| A. Retry correctness | An aborting error that is caught, then committed (TX-01A, PR-01, P6). The failure leaves nothing to retry, because the API reports success | Retry with ORM objects from a failed attempt (§7.3). Retry after an ambiguous outcome (§7.1). Whether a framework preserves the SQLSTATE across its exceptions (§6, R7) |
| B. Timeouts | Server-side termination around COMMIT, category B. That is also how `idle_in_transaction_session_timeout` and `transaction_timeout` end a session (§8) | Client-side cancellation and application timeouts, during the body or during COMMIT (§7.1) |
| C. Concurrent writes | The requested isolation level is applied (TX-05) | By design, application-level concurrency is outside PPCS. It belongs to the identity-map work (Ext) and Program B (§8) |
| D. Identity maps and stale state | Pending writes across nested scopes (TX-04; MikroORM `clear-forks`) | Instance state after a rollback (§7.3). Instance state after a savepoint rollback: §7.3's savepoint variant, not probed |
| E. External effects | Commit hooks after a caught `23505` (PR-01); Django `on_commit`, SQLAlchemy events, and Spring `afterCommit`. `docs/specifications.md` lists "After-commit callbacks" under "Planned, not yet included" | Rollback hooks under an unknown outcome (§7.1). Post-commit callback errors reported as transaction failures (§6, R6) |
| F. Pooling and session state | Transaction state on reuse (TX-03). The methodology says poolers such as PgBouncer "are not covered" | Session state on reuse (§7.2) |

## 3. Confirmed coverage gaps

Each gap was checked against the catalog, the adapters' manifests and READMEs, and the research directories, by full-text search for the terms involved. A premise probe then established that the gap matters.

| Gap | Evidence that PPCS lacks it | Premise result |
| --- | --- | --- |
| **G1.** No ordinary-cancellation trigger, and TX-01B.2 is never exercised for Python | Every fault category is A–E (`docs/methodology.md`). The Python manifests declare no rollback-claim channel (§2.1). The README matrix shows "TX-01B.2 not exercised" for all four | Probe P3: under level-triggered cancellation, SQLAlchemy emits rollback events and PostgreSQL commits (§7.1) |
| **G2.** No session-state reuse check | TX-03's invariants concern the transaction only (`docs/specifications.md`). "Poolers such as PgBouncer … are not covered" (`docs/methodology.md`, "Single node, local container") | Probes P2 and P7: six pools carry over role, and five carry over everything (§7.2) |
| **G3.** No check of a write after a rollback | TX-04 checks pending writes inside one transaction tree. Nothing re-saves an object across transactions | Probe P4: Tortoise loses the retried write silently (§7.3) |
| **G4.** No COMMIT that raises | TX-01A's COMMIT is answered `ROLLBACK` without an error. TX-01B has no reply | Probe P5: Django is correct, and Tortoise leaves the error untranslated. The SQLAlchemy sync paths are measured outside PPCS (§2.3) |
| **G5.** No async adapter except Tortoise | The adapters table in the root README | Probes P1 and P3 cover asyncpg, psycopg async, and SQLAlchemy asyncio directly |
| **G6.** asyncpg's transaction API was never a subject | PR-01 has no asyncpg row. Tortoise's TX-01A evidence is the only asyncpg evidence | Probe P1: asyncpg reports `state:committed` on tag `ROLLBACK` |

## 4. Production failure taxonomy

**What the "Layer" column holds.** It names the layer that decides the outcome, among six: PostgreSQL, driver, pool, framework, application, deployment. A framework is not marked defective because PostgreSQL lets an application make a mistake.

| # | Failure class | Ordinary production trigger | Layer | What the application sees | PPCS coverage | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | False success after an aborting error | Catch `23505`, `57014`, `40P01`, `40001` or `55P03` inside the transaction, then let the API commit | The driver's commit, which discards the `ROLLBACK` tag: psycopg `commit()` and `transaction()`, asyncpg `Transaction`. The framework passes it through. Django `atomic()` and the SQLAlchemy flush avoid it | Success, with no row | Covered: TX-01A, PR-01 | PPCS; Probes P1 and P6. `55P03` not probed (Judg: the same abort) |
| T2 | A COMMIT that PostgreSQL rejects | Deferred FK checks, which are Django's default; a deferred unique constraint; `40001` at COMMIT under SERIALIZABLE | The framework's error path and exception translation | An exception, if the framework is correct | Not in PPCS. SQLAlchemy sync covered outside (§2.3) | Probe P5; Ext |
| T3 | An unknown outcome: COMMIT in flight when the client gives up | Connection loss (B, E); **cancellation and application timeouts**; process interruption | The driver's cancel strategy, plus the framework's hooks and reports | `CancelledError`, `TimeoutError`, or a cancelled scope that exits normally | Connection loss covered. Cancellation not covered | Probe P3 |
| T4 | A connection returned inside a transaction | A failed rollback (C, B). Cancellation during rollback or cleanup | Pool reset | The next unit joins, or the next unit fails | TX-03, with injection | Probe P3: not reproduced through cancellation. Every pool was safe |
| T5 | Session state carried over | `SET search_path` or `SET ROLE` per request; custom GUCs for RLS; `statement_timeout` per endpoint; session advisory locks; temp tables | The pool's reset contract, plus the application's use of `SET` versus `SET LOCAL` | Nothing: the next unit silently inherits | Not covered | Probes P2 and P7 |
| T6 | Stale ORM instance state after a rollback | Retry wrappers that reuse an instance; error handlers that save again | ORM state tracking | Success, with no row (Tortoise) | Not covered | Probe P4 |
| T7 | Retry correctness | Retrying `40001` or `40P01`, which PostgreSQL recommends; retrying timeouts | Application. No framework ships a PostgreSQL retry helper (Doc, §5) | Duplicates when the outcome was ambiguous (T3), lost writes with stale state (T6), no retry at all after a false success (T1) | T1 only | §5, and Probes P1, P3, P4 |
| T8 | External effects around COMMIT | `on_commit` or `after_commit` hooks; Celery `delay_on_commit`; rollback hooks used for compensation | Framework hooks | Hooks that disagree with PostgreSQL | PR-01, for a caught `23505` | Probes P1 (`after_commit`), P3 (`after_rollback`), P5 (`on_commit` dropped correctly) |
| T9 | Concurrency anomalies | Lost update and write skew under READ COMMITTED; read-modify-write | PostgreSQL semantics, plus application design | Last-writer-wins, or `40001` | Out of scope by design | Ext (identity-map report); Program B |
| T10 | Deployment interactions | PgBouncer transaction pooling; synchronous-replication waits during COMMIT | Deployment | Leaked session state across clients; slower COMMITs that widen T3 | Out of PPCS's profile | §8 |

## 5. Existing framework guarantees and mitigations

| Project | Documented guarantee or mitigation (Doc/Src) | What the probes observed |
| --- | --- | --- |
| **PostgreSQL** | **Retry guidance:** "It is important to retry the complete transaction … PostgreSQL does not offer an automatic retry facility" (mvcc-serialization-failure-handling). It names `40001`, `40P01`, `23505` and `23P01`.<br>**Advisory locks:** a session-level lock "acquired during a transaction that is later rolled back will still be held following the rollback" (explicit-locking).<br>**`DISCARD ALL`** "cannot be executed inside a transaction block". Its equivalent sequence runs `SET SESSION AUTHORIZATION DEFAULT` separately from `RESET ALL` (sql-discard).<br>**Serialization at COMMIT:** `40001` "Canceled on identification as a pivot, during commit attempt" (Src, `predicate.c`) | **psql:** `RESET ALL` leaves `SET ROLE` and `SET SESSION AUTHORIZATION` in place; `DISCARD ALL` resets them.<br>**A rolled-back advisory lock** is still held.<br>**An unlock attempted inside an aborted transaction** fails, and the lock stays held |
| **psycopg 3.3.6** | **Cancellation:** "cancelling the Python Task does not guarantee that the operation will not complete … consider calling `Connection.cancel()`" (docs, "Interrupting async operations").<br>**`AsyncConnection.wait`** sends a cancel and then waits up to 5 s on `CancelledError` (Src, `connection_async.py:535-552`).<br>**Retries:** no helper; `Transaction.status` "to implement retry logic" | **P3, level-triggered:** the connection was discarded with COMMIT in flight, and PostgreSQL committed. Judg: the cancel-and-wait was itself cancelled.<br>**P3, edge-triggered:** aborted.<br>**Audit:** `Transaction.status` reports `committed` on tag `ROLLBACK` |
| **psycopg_pool 3.3.3** | **Returned connections:** `INTRANS` or `INERROR` is rolled back, `ACTIVE` is closed (Src, `pool.py:790-827`).<br>**`reset`** callback documented.<br>**Maintainer, Discussion #893:** "the connection pool, by default, doesn't reset the connection … If you need a `DISCARD ALL`, you can execute it in a `reset` callback" | **P2:** everything carried over by default |
| **asyncpg 0.32.0** | **`Connection.reset()`:** "all session configuration variables are reset to their default values, and all advisory locks are released" (`connection.py:1567-1594`). The query is `pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;` (`1763-1790`).<br>**Hooks:** `create_pool(reset=…)` and an overridable `get_reset_query()` (0.30.0).<br>**`Pool.release()`** is shielded (`pool.py:1055`).<br>**`execute()`** returns the status string (`connection.py:348`).<br>**`Transaction.__commit`** discards it (`transaction.py:175-192`).<br>**Upstream:** temp tables, #1293 and PR #1392, both open; transaction state, #1130, open | **P2:** **role survived the documented reset**; the temp table survived; the rest was reset.<br>**P1:** `state:committed` on tag `ROLLBACK`.<br>**P3:** aborted in every style; the pool was safe |
| **SQLAlchemy 2.1.5** | **Reset on return:** the rollback "does not cover a wider range of session-level state, including temporary tables …". A recipe follows, using `PoolEvents.reset` with `CLOSE ALL`, `RESET ALL`, `DISCARD TEMP`, then `rollback()` (`dialects/postgresql/base.py`, about 275-335).<br>**`after_rollback`:** "Execute after a real DBAPI rollback has occurred" (`orm/events.py:1882-1898`).<br>**Cancellation is an exit exception** (`util/concurrency.py:30-35`), so the connection is invalidated. A cancelled reset calls `_checkin_failed` (`pool/base.py:1041-1052`).<br>**Changelog:** cancellation fixes in 2.0.55/2.1.2, 2.1.5, and 2.1.6 (#13699).<br>**Retries:** only the FAQ, for disconnects | **P7:** **the recipe, on psycopg 3, resets nothing.** Judg: its statements run inside psycopg's implicit transaction, which its own `rollback()` undoes. `RESET ALL` would not reset the role in any case (psql).<br>**P3, level-triggered:** `after_rollback` fired, and PostgreSQL committed (2.1.5 and 2.1.6).<br>**P1:** `after_commit` fires on an aborted transaction when `Session.execute()` raised |
| **Django 6.1.2** | **Persistent-connection caveat:** "If you modify parameters such as the connection's isolation level or time zone, you should either restore Django's defaults … or disable persistent connections".<br>**The native pool:** passes `configure=` only; `assume_role` runs at physical connect only (Src, `postgresql/base.py:194-236` and `381-392`).<br>**"The values of a model's fields won't be reverted when a transaction rollback happens."**<br>**`on_commit`:** callbacks are discarded on rollback; `robust` (4.2).<br>**Foreign keys** are created `DEFERRABLE INITIALLY DEFERRED` (Src, `postgresql/operations.py:150-151`). Trac #25955 is open: "FK constraints are not checked at the end of nested atomic blocks" | **P2:** everything carried over, in both connection modes.<br>**P5:** a rejected COMMIT is handled correctly.<br>**P4:** the retried `save()` re-INSERTs.<br>**P6:** rolls back for ORM writes |
| **Tortoise 1.1.9** | **Transactions:** "If error occurs transaction will rollback" (transactions docs). No isolation parameter (#952). No retry helper.<br>**`save()`** ignores the UPDATE rowcount unless `force_update` (Src, `models.py:1176-1194`).<br>**`commit()`** is not wrapped by `translate_exceptions` (Src, `backends/asyncpg/client.py:197`).<br>**Class-25 errors** become `TransactionManagementError`, and the exits skip rollback for that type (Src, `client.py:96-97`; `base/client.py:378-379`, `403-404`).<br>**Upstream:** #1094 is open, "it says `saved` but actually isn't", with the cause not established | **P4:** silent lost write.<br>**P5:** raw `asyncpg.ForeignKeyViolationError` at COMMIT.<br>**P3:** like asyncpg, aborted and safe |
| **anyio 4.15.1, Starlette, uvicorn** | **anyio:** tasks in a cancel scope "use level cancellation … any time it hits a yield point"; await in finalization only inside a shielded scope.<br>**Starlette 1.9.0 (Src):** normal endpoints are not cancelled on client disconnect, `BaseHTTPMiddleware` runs the app in a task group, and streaming responses can cancel.<br>**uvicorn:** `--timeout-graceful-shutdown` cancels request tasks | Reachability for §7.1 runs through application timeouts, task groups, middleware and shutdown. It does not run through plain client disconnects (Judg) |
| **Third party** | **django-rls-tenants PR #135** (merged 2026-10-14): Django's pool "keeps session GUCs between borrowers … an anonymous request saw tenant A's rows" (Upstream; not reproduced here).<br>**Celery 5.4** adds `delay_on_commit` through `transaction.on_commit` | Corroborates §7.2's reachability. Not a PPCS result |

**Missing features versus defects.** No library here ships a PostgreSQL retry helper, and PostgreSQL says it cannot offer one safely. That is a missing feature by design, so applications must manage retries. The retry hazards that frameworks do control are the ones the designs measure:

- reporting success when there is nothing to retry (T1);
- claiming an outcome they cannot know (T3);
- keeping stale state that makes a retry write nothing (T6);
- carrying session state into the next unit of work (T5).

## 6. Ranked investigation opportunities

**Scale.** Each criterion is an ordinal judgment from 1 (weak) to 5 (strong), with the reason in the row. The weighted total uses these weights:

- reachability 25%;
- impact 20%;
- gap 20%;
- reproducibility 15%;
- actionability 10%;
- Python relevance 10%.

The totals rank; they do not measure. Differences below about 0.3 are not meaningful.

| Rank | Opportunity | Reach | Impact | Gap | Repro | Action | Python | Total | Vehicle (§8 lists the rejects) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | Cancellation while COMMIT is in flight, async stacks (§7.1) | 4 | 5 | 5 | 5 | 4 | 5 | 4.7 | Standalone investigation, then an extension of TX-01B and TX-03 with a new trigger category |
| R2 | Session state survives the pool (§7.2) | 4 | 4 | 5 | 5 | 3 | 5 | 4.4 | Standalone investigation, then a new family |
| R3 | ORM instance state after a rollback, in a retry (§7.3) | 3 | 5 | 5 | 5 | 4 | 4 | 4.3 | A new family, using the existing evidence model; a regression test for Tortoise |
| R4 | asyncpg's transaction API, SQLAlchemy's asyncpg dialect, and the ORM `Session.execute()` error path on the PR-01 pattern | 5 | 4 | 2 | 5 | 3 | 5 | 4.0 | An extension of PR-01 and TX-01A: an asyncpg control and an ORM `execute` form. The upstream side is the audit's §8.2 |
| R5 | A COMMIT that PostgreSQL rejects: deferred FK, deferred unique, `40001` at COMMIT | 5 | 2 | 3 | 5 | 2 | 4 | 3.6 | A small TX-01 case; a Tortoise translation fix |
| R6 | A post-commit callback error reported as a transaction failure: Django `on_commit` with `robust=False`, SQLAlchemy `after_commit` raising | 3 | 4 | 4 | 5 | 1 | 4 | 3.6 | Documentation, or a static-analysis rule. Not probed |
| R7 | Retry classification: SQLSTATE preserved through framework exceptions | 4 | 3 | 3 | 4 | 2 | 5 | 3.5 | Framework regression tests and documentation |
| R8 | `idle_in_transaction_session_timeout` and `transaction_timeout` as real triggers for the category B endings | 4 | 2 | 2 | 5 | 1 | 3 | 3.0 | A note in the TX-01B and TX-03 documentation |

**Why each score:**

- **R1.**
  - **Reach 4, not 5.** It needs both a cancellation and a COMMIT that is still in flight. Ordinary COMMITs are short. Two things make them long: deferred FK checks that wait on a row lock, and synchronous replication. Django creates its FKs deferred (Src), and a deferred check can wait on a row lock (psql check).
  - **Impact 5.** A rollback hook fired for a committed transaction. Rollback hooks drive compensation, cache invalidation and retry decisions.
  - **Repro 5.** The server-side gate made the result deterministic: three repetitions agreed, on two SQLAlchemy releases.
  - **Action 4.** SQLAlchemy's event contract says "a real DBAPI rollback", and psycopg's documentation already warns about the outcome.
- **R2.**
  - **Impact 4.** The consequence is cross-tenant or wrong-role writes, and locks that block other workers. It is not 5 because applications control `SET LOCAL`.
  - **Action 3.** asyncpg's role gap contradicts its own docstring, and SQLAlchemy's recipe fails on psycopg 3. psycopg_pool and Django behave as documented, or are silent.
- **R3.**
  - **Reach 3.** It needs an instance reused across attempts.
  - **Impact 5.** The write is lost, and the API reports success.
  - **Python 4.** The defect is Tortoise's. Django and SQLAlchemy serve as controls.
- **R4.** **Gap 2.** The mechanism is PR-01's. The new parts are one driver API and one ORM hook.
- **R5.** **Impact 2.** Django was correct. Tortoise's defect is the exception type.
- **R6.** **Action 1.** Django documents both `robust` and the propagation. The hazard is for applications.
- **R7.** **Gap 3.** Tortoise's translation is inconsistent: COMMIT-time errors arrive raw (P5), and `25P02` becomes `TransactionManagementError` (Src).
- **R8.** **Gap 2.** The ending is category B. SQLAlchemy's psycopg dialect detects a disconnect from connection state, `closed` or `broken` (Src, `dialects/postgresql/psycopg.py:596-600`). Its asyncpg dialect uses `is_closed()` when it has a connection, and falls back to the message "connection is closed" when it does not (Src, `asyncpg.py:1211-1217`). Neither depends on which FATAL ended the session.

## 7. Detailed designs for the top three experiments

The designs reuse PPCS's evidence model wherever it applies:

- the transaction ID and PID, captured inside the transaction and bound in `pg_stat_activity`;
- `pg_xact_status()` at report time (`after-end`) and at the end;
- write evidence in `pg_locks`;
- marker visibility, with `xmin` attribution;
- three repetitions;
- native, configured, and hardened modes;
- positive and negative controls.

A new family or trigger category is a change to the evidence model, and it needs maintainer approval (`AGENTS.md`, "Approval gates"). Every design therefore starts as a standalone investigation under `research/`, like PR-01's own catalog and runner (`research/production-reachability/run.mjs`).

### 7.1 Cancellation while COMMIT is in flight (R1)

**Research question.** An application cancels its own task while the transaction's COMMIT is still being processed by PostgreSQL. Three things are asked:

1. Does any API, error, or hook claim an outcome the client could not know: a commit, or a confirmed rollback?
2. Can later work on the pool inherit the connection's state?
3. Who decided the outcome, the driver's cancel request or PostgreSQL after the client left, and was it decided before or after the API returned?

**PostgreSQL behavior being tested.**

- **Before the commit record.** COMMIT runs deferred constraint checks and deferred triggers before it writes the commit record. While one of those waits on a lock, the backend is `active`, with `wait_event_type = Lock`.
- **A CancelRequest** that arrives during the wait cancels it (`57014`), and the transaction aborts.
  - **What was observed.** P3's edge-triggered asyncpg and psycopg rows were already aborted when the API returned.
  - **The cancel itself is not observed.** Both drivers send one on `CancelledError` (Src).
- **A closed socket without a cancel** does not stop the wait. With `client_connection_check_interval = 0` (the default, and the probe's setting), the backend finishes COMMIT when the lock is released, and the transaction commits.
  - **What was observed.** P3's level-triggered psycopg and SQLAlchemy rows: still `in progress` when the API returned, and committed after the gate opened.
  - **What is inferred.** That no cancel reached the wait. This is Judg from the fates; the server log was not used to confirm it.
- **The protocol's limit.** The PostgreSQL protocol documentation says the client "has no direct way to tell whether a cancel request has succeeded" (Doc).
- **Not tested: synchronous replication.** There, the commit record is already written locally while COMMIT waits for the standby. Judg, from PostgreSQL's synchronous-replication design: a cancel then leaves the transaction committed. PPCS's single-node profile cannot reproduce that.

**The gate.** It is server-side; nothing is injected in the client.

- **G-FK, primary.** The fixture is `parent(id)` and `child(parent_id references parent DEFERRABLE INITIALLY DEFERRED)`, which is Django's FK form. The runner holds `SELECT … FOR UPDATE` on the parent row. The subject inserts a child, and its COMMIT waits on `Lock/transactionid` (psql check; README, "Two psql checks").
- **G-ADV, the one the probe used.** A deferred constraint trigger runs `pg_advisory_xact_lock(k)` while the runner holds `pg_advisory_lock(k)`.

**Framework APIs.**

- SQLAlchemy `AsyncSession.begin()` and `AsyncConnection.begin()`, on `postgresql+asyncpg` and on `postgresql+psycopg`;
- psycopg `AsyncConnection.transaction()` with `AsyncConnectionPool`;
- asyncpg `Pool` with `Connection.transaction()`;
- Tortoise `in_transaction()`.

**Cancellation styles.**

- **edge:** `asyncio.timeout()` or `Task.cancel()`;
- **level:** anyio `move_on_after()`, `fail_after()`, or a cancelled task group, on the asyncio backend.

**Minimal reproduction** (P3, `p3_cancellation.py`). Pool of one connection.

1. Unit 1 writes `tx` and captures its ID and PID.
2. The API's normal completion starts.
3. The runner waits until `pg_stat_activity` shows that backend `active`, with query `COMMIT` and a lock wait on the gate.
4. The application cancels.
5. Record what the API raised or returned, the hooks, and `pg_xact_status()`.
6. Release the gate. Record the final fate and the marker.
7. Unit 2 writes `next` on the same pool and commits. Record its backend, and whether its ID equals unit 1's.

**Protocol fit.** No new message type is needed:

- the adapter reports a `commit-started` checkpoint from a side task;
- the runner holds `resume` until it observes the gated COMMIT, with a bound;
- `resume` is the cue to cancel;
- `after-end` follows when the API returns.

The new parts are the gate fixture, the hold-until-gated rule, and the classification.

**Independent PostgreSQL observations.**

- at the gate: `pg_stat_activity` (`state`, `query`, `wait_event_type`, `wait_event`), and the lock waiter in `pg_locks`;
- `pg_xact_status()` at `after-end` and at the end. An `in progress` fate at `after-end` is an unknown outcome, decided after the API returned;
- marker visibility, with `xmin` attribution;
- unit 2's PID, `backend_start` and transaction ID, against unit 1's.

**Which hooks count as rollback claims.** The adapter declares the channels it observes:

- **SQLAlchemy ORM `after_rollback`,** documented as "Execute after a real DBAPI rollback has occurred". This is the claim channel.
- **SQLAlchemy `after_soft_rollback`:** record it, but do not count it. Its documentation says it fires even when no DBAPI rollback happened.
- **SQLAlchemy Core `rollback`:** do not count it. Like Core `commit`, it fires before the DBAPI call (Src, `engine/base.py:1133-1135`).
- **Django, Tortoise, psycopg, asyncpg:** none.

**Proposed invariants,** for review:

- **I1.** When the API returned while COMMIT was in flight, it does not report a successful commit. This is TX-01B.1 for this trigger.
- **I2.** In that state it also does not report a confirmed rollback, through its result, its errors, or its rollback hooks or events. This is TX-01B.2.
- **I3.** Unit 2 runs in its own transaction and commits within the bound. This is TX-03.1 and TX-03.2.

A rollback report made when the fate was already `aborted` at `after-end` is a known outcome, and it is allowed, as in `TX-01B.conn-lost-before-commit`.

**Positive controls:**

- the `none` style (no cancellation; open the gate): committed, and reported committed (P3: every subject);
- a driver-level mode that shields COMMIT (`anyio.CancelScope(shield=True)` or `asyncio.shield`) and reports the outcome it then receives;
- a psycopg mode that uses `Connection.cancel()`, psycopg's documented alternative, and reports the error it receives.

**Negative controls:**

- a mode that reports `rolled_back` on any cancellation and closes the socket without a cancel. It must FAIL I2; P3 shows this shape from SQLAlchemy under level-triggered cancellation;
- a mode that returns the connection to the pool without a rollback after a body-gated cancellation. It must FAIL I3.

**Fault injection.** None in the client. The trigger is the application cancelling its own task. It is neither a PostgreSQL error (A) nor a server termination (B) nor a client injection (C, D) nor a proxy (E), so it needs a category of its own, which requires approval.

**Production-reachability argument.** It needs two conditions together.

1. **Cancellation.** anyio documents level cancellation for cancel scopes and task groups. FastAPI and Starlette are anyio-based: `BaseHTTPMiddleware` runs the downstream app in a task group, application timeouts commonly use `fail_after` and `move_on_after`, and uvicorn's graceful-shutdown timeout cancels request tasks. Starlette does not cancel normal endpoints on client disconnect (Src), so a disconnect alone is not the trigger.
2. **A COMMIT that takes long enough.** Every Django FK check runs at COMMIT and can wait on a row lock (Src, psql check). Deferred triggers, synchronous replication and I/O stalls also lengthen COMMIT.

PPCS should not claim a frequency.

**Scope note, added 2026-10-24.** Item 1 above counts Uvicorn's graceful-shutdown timeout as a cancellation source. Its behaviour is narrower than "edge" or "level":

- the timeout cancels each remaining request task once (`t.cancel()`), then starts lifespan shutdown without waiting for those tasks;
- under SIGTERM, Uvicorn re-raises the signal after `serve()` returns, and the process ends before the cleanup finishes;
- under SIGINT, `asyncio.run`'s teardown cancels the remaining tasks again.

That is reported in [Uvicorn discussion #3232](https://github.com/Kludex/uvicorn/discussions/3232), and measured there with a stand-in service, not PostgreSQL.

P3's edge-triggered rows ended aborted, in a loop that kept running after the one cancel. Both drivers could therefore send their cancel and finish. They do not show what PostgreSQL does on this shutdown path, and this report does not measure it.

A design that adopts §7.1 should add the path as a third cancellation style: one cancel, then process exit (SIGTERM) or a second cancel (SIGINT).

**Classification.**

- **PASS:** the gate was observed before the cancel, the cancellation was delivered, I1–I3 held, the controls held, and the repetitions agreed.
- **FAIL:**
  - a declared rollback-claim channel fired (for SQLAlchemy, `after_rollback`), or `rolled_back` was reported, while the fate at `after-end` was `in progress`. Record the final fate: committed is the sharper counterexample, and P3's SQLAlchemy level-triggered rows are that shape;
  - `committed` reported in that state;
  - unit 2 inherited unit 1's transaction, or could not commit.
- **INCONCLUSIVE:**
  - the gate was not observed before the cancel;
  - the cancellation never reached the task;
  - the fate was unreadable;
  - unit 2 did not run;
  - the repetitions disagreed;
  - a control failed.

**Potential confounders.**

- **The cancel request races the socket close.** asyncpg sends its CancelRequest from a background task, and its connection cleanup cancels pending cancellation tasks (Src, `asyncpg/connection.py`, `_clean_tasks`). Record where each decision happened.
- **asyncpg's release is shielded** and continues after the scope exits (P3: decided after report time). The report-time and end fates handle this.
- **Gate type.** Under the gate, a cancel aborts the transaction; under synchronous replication it would not (Judg, above). Say which one a result covers.
- **Versions.** The anyio and asyncio versions, and SQLAlchemy's frequent cancellation fixes (2.1.6 is current). Record every version, and re-run on the latest release before any upstream use.
- **`client_connection_check_interval`** must stay 0, and be recorded in the server profile.

**Likely upstream owners.**

- **SQLAlchemy:** `after_rollback` emitted for an interrupted commit whose outcome is unknown. Its contributing rules require any text to be written by a person, in their own words (quoted in the audit's §8.3).
- **psycopg:** its cancel-and-wait is not protected from repeated cancellation. Its documentation already warns about the outcome, and the tracker records an open #1451 about a cancelled `AsyncConnection.transaction()` entry (`docs/upstream-submissions.md`; not re-read).
- **anyio, Starlette, application docs:** shield COMMIT and cleanup.
- **asyncpg and Tortoise:** no finding in P3.

**Estimated effort.**

- **Standalone investigation:** 2–3 days. That is five subjects, two gates, two styles, controls, and a report.
- **A PPCS extension:** 4–6 more days, plus approvals. That covers the gate fixture, the hold-until-gated rule, the classifier and its unit tests, async Python modes or adapters, control modes, and the methodology tests.

### 7.2 Session state that survives the pool (R2)

**Research question.** A unit of work changes session state and returns its connection. Does the next unit of work on the same pool run with that state? For each pool, which state does its reset clear, and does the pool's documented reset contract hold?

**PostgreSQL behavior being tested.**

- **`SET`** lasts for the session unless it is `LOCAL`, or the transaction that ran it rolls back.
- **`RESET ALL`** skips `role` and `session_authorization`. This was observed (psql). PostgreSQL's source flags both settings `GUC_NO_RESET_ALL` (Src, `guc_tables.c`, read by a research subagent).
- **`DISCARD ALL`** resets everything, but cannot run inside a transaction block.
- **Session advisory locks** survive `ROLLBACK`, and an unlock inside an aborted transaction fails (Doc, psql).
- **Temp tables** last for the session. `pg_temp` is searched first, so a temp table can shadow a permanent one.

**Framework APIs.**

- asyncpg `create_pool` (`reset=`, `Connection.get_reset_query`);
- psycopg_pool `ConnectionPool` and `AsyncConnectionPool` (`reset=`, `configure=`);
- SQLAlchemy `QueuePool` and `AsyncAdaptedQueuePool` (`pool_reset_on_return`, `PoolEvents.reset`);
- Django `CONN_MAX_AGE` and `OPTIONS["pool"]` (with `assume_role`);
- Tortoise, through asyncpg's pool.

**Minimal reproduction** (P2, `p2_session_state.py`). The login is a non-superuser member of `tenant_a`; the pool holds one connection.

1. Unit 1 runs `SET ROLE tenant_a`, `SET app.tenant_id`, `SET search_path = tenant_s, public` and `SET statement_timeout`. It also takes `pg_advisory_lock(k)` and creates a temp table. Then it commits.
2. Unit 2 inserts an unqualified row into `item`. `item` exists in `public` and in `tenant_s`, each with `inserted_by name DEFAULT current_user`.

**Fixture changes, if adopted into PPCS:**

- a second schema with its own `item`;
- an `inserted_by DEFAULT current_user` column;
- a NOLOGIN role granted to the case's login role;
- a login role that is not a superuser.

Roles are cluster-wide, so the harness would have to create and drop a uniquely named role per run. That is a harness change.

**Cases,** one per kind of state, so that a FAIL names what leaked:

- **role:** `inserted_by` is the evidence;
- **`search_path`:** the schema of the landed row;
- **custom GUC:** as for `search_path`, combined with an RLS policy or a `DEFAULT current_setting(…)` column;
- **`statement_timeout`:** unit 2 runs a statement slower than the leaked timeout, and `57014` is the evidence;
- **session advisory lock:** `pg_locks` for the backend between the two units;
- **temp table:** a temp `item` that shadows the permanent one. Unit 2's marker is then invisible: a lost write with write evidence. Attribute the write lock by relation OID, not by name.

**Independent observations.**

- the backend identity across the two units, from the PID and `backend_start`;
- `inserted_by`, and the schema of the landed row;
- `pg_locks` advisory entries between the units;
- unit 1's own marker, to confirm its state change took effect;
- the API error for the timeout case.

**Invariant,** proposed: a unit of work does not run with session state left by an earlier unit on the same pool. Its role, `search_path`, configuration parameters, session advisory locks and temporary objects are a fresh session's, or the pool's documented initial state.

**Positive control:** a `correct` raw-driver mode that, on return, rolls back and then runs `DISCARD ALL` in autocommit. P7's corrected variant reset everything.

**Negative control:** a mode with no reset. Five native pools behave this way in P2.

**Modes:**

- **native:** the defaults;
- **configured:** each pool's documented hook. SQLAlchemy's documented recipe is its own configured mode, because P7 shows it ineffective on psycopg 3;
- **hardened:** `SET LOCAL`, or `set_config(…, true)`.

**Fault injection.** None.

**Production-reachability argument.** These patterns are ordinary:

- schema-per-tenant `search_path`;
- RLS through `SET ROLE` or custom GUCs;
- a `statement_timeout` set per endpoint;
- session advisory locks for jobs, which can also leak through the aborted-unlock path;
- every code path that forgets to set the state again: background tasks, admin views, error handlers.

A third-party Django RLS library reports exactly this through Django's pool (Upstream, §5).

**Classification.**

- **PASS:** unit 2 ran on the same backend and showed none of unit 1's state.
- **FAIL:** a carryover, shown by independent evidence.
- **INCONCLUSIVE:** unit 2 did not reuse the backend (the invariant is not exercised); unit 1's change was not confirmed; or the repetitions disagreed.

**Potential confounders.**

- A `SET` inside a transaction that rolls back is undone, so unit 1 must commit or run in autocommit.
- The pool must be pinned to one connection.
- Frameworks may re-apply settings at checkout. Django re-applies `assume_role` only at physical connect (Src).
- Prepared-statement caches interact with `DISCARD ALL`. asyncpg keeps its statements on purpose (Upstream, #270), and psycopg handles `DISCARD` from 3.3.5.
- A `RESET` inside a transaction is undone by that transaction's rollback (P7).
- Superuser logins mask the role cases.

**Likely upstream owners.**

- **asyncpg:** role is not reset, contrary to its docstring. This is new, and no issue was found. Temp tables are #1293 and PR #1392, both open.
- **SQLAlchemy:** the documentation recipe. Any text must be written by the user.
- **Django:** a documentation note that the native pool does not reset session state.
- **psycopg_pool:** documented behaviour; possibly a documentation example.

**Estimated effort.**

- **Standalone investigation:** 1–2 days, starting from P2 and P7.
- **A PPCS family:** 3–5 days, plus approvals for the fixture, the role management, and the new family.

### 7.3 ORM write state after a rolled-back transaction (R3)

**Research question.** An ORM's save ran inside a transaction that rolled back. The application then saves the same in-memory object in a new transaction. Does the API report success only when the row is persisted?

**PostgreSQL behavior being tested.**

- `ROLLBACK` discards the INSERT; the sequence value stays consumed.
- An UPDATE that matches no row succeeds, with row count 0, and still takes `RowExclusiveLock` on the table (psql check). PPCS's write evidence therefore confirms the write was sent.

**Framework APIs.**

- Tortoise `Model.save()`;
- Django `Model.save()`;
- SQLAlchemy `Session.add()`, then commit, in a new `Session` per attempt, with a same-`Session` variant (see the confounders);
- later, and outside this Python scope: EF Core, MikroORM, TypeORM, and Active Record under the same case.

**Minimal reproduction** (P4, `p45_commit_error_and_retry.py`).

1. Construct the instance.
2. Inside the managed transaction API, save it, then raise an application error. The transaction rolls back.
3. In a new transaction, save the same instance, and end normally.

**What P4 observed after the rollback, and after the retry:**

| ORM | State after the rollback | The retry |
| --- | --- | --- |
| Tortoise | `pk = 1`, `_saved_in_db = True` | Returned; 0 rows |
| Django | `pk = 2`, `_state.adding = False` | Returned; 1 row |
| SQLAlchemy | transient, `pk = 1` | Returned; 1 row |

**PPCS case design.**

- **Unit 1** saves marker `tx` through the ORM. The write is confirmed by `RowExclusiveLock` at a checkpoint. The application then raises, and the runner confirms unit 1 aborted and the marker is absent.
- **Unit 2** saves the same instance. Its write is confirmed at a checkpoint, and it ends normally.

This fits `marker_writes` and the existing lost-write rule ("A committed transaction whose confirmed write is missing … is a lost write", `docs/methodology.md`).

**Invariant,** proposed: when the API reports that a transaction which saved an object committed, PostgreSQL committed a row for that object in that transaction.

**Positive controls:**

- Django (UPDATE, then an INSERT fallback) and SQLAlchemy (transient, then an INSERT) (P4);
- a raw-driver control that re-INSERTs.

**Negative control:** a `pg-control`-style mode that remembers "saved" and issues an UPDATE without checking the row count.

**Fault injection.** None. An application error, then a retry.

**Production-reachability argument.** PostgreSQL tells applications to retry the whole transaction, so retry wrappers are common. They are unsafe when the object was built outside the retried function. Error handlers that save the object again take the same path. Tortoise #1094 (Upstream, open) reports "it says `saved` but actually isn't", with the cause not established. It is not claimed as this case.

**Classification.**

- **PASS:**
  - unit 2 reported committed, and its marker is visible with `xmin` equal to unit 2's ID;
  - or the API raised: honest failure. Tortoise with `force_update=True` raises "Can't update object that doesn't exist" (Src).
- **FAIL:** reported committed, fate committed, write confirmed, marker absent.
- **INCONCLUSIVE:**
  - unit 1 did not abort, or its write was not confirmed;
  - unit 2 sent no statement. That is a different shape: record it;
  - the repetitions disagreed.

**Potential confounders.**

- **The PK source.** Use a serial PK and a client-side default, such as a UUID. Django forces an INSERT when `_state.adding` is true and the PK has a default. After a rollback `_state.adding` is false, so the two PK kinds can take different paths.
- **`update_fields` and `force_update`.**
- **Instances loaded from the database** rather than constructed.
- **SQLAlchemy reusing the same `Session` without re-adding the object.** The object was expunged, so the commit has nothing to flush. The documentation implies that; it is a hypothesis, not probed.
- **Django's `select_on_save`.**

**Savepoint variant, not probed.** The first save runs inside a nested scope that rolls back, while the outer transaction commits: a Django nested `atomic()`, a Tortoise nested `in_transaction()`, a SQLAlchemy `begin_nested()`. The same instance is then saved again in the outer scope. This is a hypothesis: Tortoise's `_saved_in_db` and Django's `_state.adding` have no savepoint-aware reset (Src), so the same shape is expected. Measure it as a separate case.

**Likely upstream owners.**

- **Tortoise:** the default `save()` path ignores the UPDATE row count, and `_saved_in_db` is not reverted on rollback.
- **Django and SQLAlchemy:** documented behaviour. Django does not document `_state.adding` after a rollback, so at most a documentation note.

**Estimated effort.**

- **Standalone investigation:** half a day to a day, since P4 is most of it.
- **A PPCS family:** 2–3 days, with cases for the ORM adapters only. The Core adapters are not applicable by design: they keep no write state.

## 8. Opportunities that should not be pursued

| Opportunity | Why not | Where it belongs, if anywhere |
| --- | --- | --- |
| `40P01`, `40001`, `57014` or `55P03` caught at statement level, then committed | The same mechanism as PR-01, now run for four stacks (P6). PR-01's report says another SQLSTATE "would repeat this mechanism unless a framework branches on it", and none of these four does. `docs/research-master-plan.md` asks for "its own question or a demonstrated gap" | A one-line note beside PR-01, citing P6. Only `40001` *at COMMIT* is different, and it is R5 |
| Re-running PR-01, or another psycopg, SQLAlchemy or Django commit-tag report | Done: PR-01, psycopg#1453, and the audit's Appendix A. The tracker says not to file SQLAlchemy or Django | — |
| SQLAlchemy 2.1.5 sync failed-COMMIT paths (deferred unique, `40001`, cancel or terminate during COMMIT, alarm) | Measured outside this repository (§2.3) | The audit's §8.3 (P5a) |
| Lost updates, write skew, optimistic and pessimistic locking, `select_for_update`, `get_or_create` races | These are PostgreSQL isolation semantics plus application design. SQLAlchemy's documented controls behaved as documented (Ext) | Program B's concurrency checks; application integration tests |
| PgBouncer transaction pooling | It adds a service and a deployment configuration outside PPCS's single-node profile (`docs/methodology.md`). Its main hazard is §7.2's, across clients | A later standalone study, only after §7.2 defines the observations |
| `idle_in_transaction_session_timeout` and `transaction_timeout` as new cases | The session ends by FATAL, which is the category B ending already recorded. The dialects detect it from connection state (R8) | A documentation note |
| Retry-helper libraries, outbox implementations, Celery publication timing | These are application architecture. No framework retry contract exists to test (§5) | Application integration tests; a static-analysis rule, for example flagging `.delay()` inside `atomic()` and suggesting `delay_on_commit` |
| Tortoise's skipped rollback after a class-25 error | Reachable only when an application keeps working after an error inside a nested block | A note for Tortoise maintainers, if R5 or R7 is pursued |
| Django TX-02 "not-sent" trigger search | Open-ended. The audit ranks it as research with an unknown trigger | — |

## 9. Recommended next implementation task

**Run §7.1 as a standalone research investigation, after maintainer approval:** `research/python-cancellation-during-commit/`.

- **Scope.**
  - **Subjects:** SQLAlchemy `AsyncSession` on asyncpg and on psycopg, psycopg `AsyncConnectionPool`, asyncpg `Pool`, and Tortoise.
  - **Gates:** G-FK first, then G-ADV.
  - **Styles:** edge and level.
  - **Controls:** the `none` control, the shielded-commit control, and the unsafe-reporting control.
  - **Repetitions:** three each.
  - Every version pinned and recorded, including SQLAlchemy 2.1.6, or the latest release on the day.
- **Method.**
  - PPCS's observation rules, in a Python runner modelled on `research/production-reachability/run.mjs`: transaction ID binding, report-time and end fates, write evidence, marker attribution, and the server-profile and safety gates.
  - Its own disposable container. Never `pnpm run pg:up`, which recreates the shared `ppcs-postgres`.
- **Deliverable.** A report with per-subject results and an explicit statement for each of I1–I3. The recorded runs, versions and hashes go beside it.
- **Decision at the end.** Should PPCS gain an "application cancellation" trigger category, and TX-01B and TX-03 cases for it? That needs approval under "changing the evidence model".
- **Do not:**
  - change `harness/` or `specifications/` during the investigation;
  - add a PPCS adapter;
  - file anything. Upstream text for SQLAlchemy must be written by the user.

**Why this one first.** It has the highest score. Its premise is already deterministic (P3, on two SQLAlchemy releases). It covers SQLAlchemy's asyncio extension and psycopg's async API, which no PPCS adapter runs, and Program B leaves async to a later study.

**Cheapest follow-on:** §7.3. It fits the existing lost-write rule unchanged, and P4 is most of the work.

## Appendix A. Premise probe results

The outputs and programs are in [`python-production-failure-gap-analysis/`](python-production-failure-gap-analysis/README.md). Every row below held in all three repetitions.

**P1. A caught `23505`, then the API's normal completion.** Independent asyncpg witness.

| Subject | API | Signals | PostgreSQL |
| --- | --- | --- | --- |
| asyncpg `async with conn.transaction()` | Exits normally | `state:committed` | Aborted; marker absent; last statement `COMMIT;` |
| asyncpg `Transaction.start()` / `commit()` | `commit()` returns `None` | `state:committed` | Aborted |
| asyncpg raw `execute('COMMIT')` | Returns `'ROLLBACK'` | — | Aborted |
| asyncpg nested `transaction()` (control) | Commits | — | **Committed**; marker visible |
| SQLAlchemy Core `postgresql+asyncpg`, `engine.begin()` | Exits normally | Core `commit` event (fires before every commit attempt; Src, `engine/base.py:1157-1172`) | Aborted |
| SQLAlchemy ORM `AsyncSession.begin()` (asyncpg), with the error from `Session.execute()` | Exits normally | **`after_commit`** | Aborted |
| SQLAlchemy ORM `Session.begin()` (psycopg), with the error from `Session.execute()` | Exits normally | **`after_commit`** | Aborted |
| SQLAlchemy ORM `Session.begin()` (psycopg), with the error from flush (PR-01's path) | Exits normally | `after_rollback`, `after_soft_rollback` | Aborted |

**P2. Session state seen by the next unit of work.** Pool of one; non-superuser login. Unit 1 set role, GUC, `search_path`, `statement_timeout`, a session advisory lock, and a temp table, then committed.

| Pool | Role | GUC, `search_path`, timeout | Advisory lock | Temp table | Unit 2's unqualified insert |
| --- | --- | --- | --- | --- | --- |
| asyncpg `Pool` | **Carried** | Reset | Released | **Carried** | `public.item`, by **`tenant_a`** |
| psycopg_pool `ConnectionPool` | Carried | Carried | **Held** | Carried | `tenant_s.item`, by `tenant_a` |
| SQLAlchemy `QueuePool` + psycopg | Carried | Carried | Held | Carried | `tenant_s.item`, by `tenant_a` |
| SQLAlchemy `AsyncAdaptedQueuePool` + asyncpg | Carried | Carried | Held | Carried | `tenant_s.item`, by `tenant_a` |
| Django, `CONN_MAX_AGE` None | Carried | Carried | Held | Carried | `tenant_s.item`, by `tenant_a` |
| Django, `OPTIONS["pool"]` | Carried | Carried | Held | Carried | `tenant_s.item`, by `tenant_a` |

**P3. Cancellation with COMMIT gated.** Pool of one. "Report" is `pg_xact_status` when the API returned. Every body-gated row ended aborted, and every pool was safe.

| Subject | Edge (`task.cancel()`) | Level (anyio `CancelScope.cancel()`) | Control (no cancellation) |
| --- | --- | --- | --- |
| asyncpg `Pool` | `CancelledError`; aborted at report time | The scope exits; `in progress` at report time; aborted, decided after the scope exited, while asyncpg's shielded release waited for its cancel | Committed |
| psycopg `AsyncConnectionPool` | `CancelledError`; aborted at report time | The scope exits; `in progress`, still waiting in COMMIT; **committed** after the gate opened; the connection was discarded | Committed |
| SQLAlchemy `AsyncSession` + asyncpg | `CancelledError`; invalidated; `after_rollback`; aborted at report time | The scope exits; invalidated; **`after_rollback`, `after_soft_rollback`**; `in progress`; **committed** after the gate opened | Committed; `after_commit` |
| SQLAlchemy `AsyncSession` + psycopg | As the asyncpg row | As the asyncpg row: **rollback events, then committed** | Committed; `after_commit` |
| Tortoise `in_transaction()` | `CancelledError`; aborted at report time | The scope exits; `in progress`; aborted, decided after the scope exited. asyncpg logged "Resetting connection with an active transaction" | Committed |
| SQLAlchemy 2.1.6, both drivers | Aborted, as above | **Rollback events, then committed**, as above | Not run |

**P4 and P5.** See §7.3 and §1. Django's FK DDL was `FOREIGN KEY (parent_id) REFERENCES dj_parent(id) DEFERRABLE INITIALLY DEFERRED`. After the rejected COMMIT:

- Django's next `atomic()` on the persistent connection succeeded;
- the Django instance kept `pk` and `_state.adding = False`, as documented.

**P6. Aborting SQLSTATEs at statement level, caught, then the normal completion.**

| Subject | `57014` | `40P01` | `40001` (REPEATABLE READ) |
| --- | --- | --- | --- |
| SQLAlchemy Core (psycopg) | Returned; aborted | Returned; aborted | Returned; aborted |
| asyncpg `transaction()` | Returned, `state:committed`; aborted | The same | The same |
| Tortoise `in_transaction()` | Returned; aborted | Returned; aborted | Returned; aborted |
| Django `atomic()`, with the failing statement from an ORM `update()` | Rolled back; `on_commit` not run | The same | The same |

**How each P6 transaction ended,** in the server's statement log (`log_statement=all`; `output/p6.server-log-endings.txt`):

- SQLAlchemy Core: `BEGIN … COMMIT`, after the dialect's first-connect `BEGIN ROLLBACK` probe;
- asyncpg and Tortoise: `COMMIT;`;
- Django: `BEGIN … ROLLBACK`.

So the FAIL-shape rows did send COMMIT, and Django never did.

**P7. SQLAlchemy's documented reset recipe** (`dialects/postgresql/base.py`, about 275–335), with the URL changed to `postgresql+psycopg`:

| Variant | Role, GUC, `search_path`, timeout, temp table seen by unit 2 |
| --- | --- |
| Default (`reset_on_return` rollback) | All carried |
| The documented recipe on psycopg 3 | **All carried** |
| `rollback()`, then `DISCARD ALL` in autocommit | All reset |
