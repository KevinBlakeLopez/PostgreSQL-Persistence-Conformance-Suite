# Adversarial review: failed `commit()`, then `Connection.close()`

Review date: 2026-10-18. Written by: Claude Opus 5.5 (max).

Subject: [`sqlalchemy-p5a-close-issue-draft.md`](sqlalchemy-p5a-close-issue-draft.md) (approved, not submitted). The draft, the investigation records, and SQLAlchemy were not modified. Nothing was posted.

After this review, the draft was revised: it now cites the `PoolResetState` guarantee, with a reset listener added to its script, and includes the version comparison for the tested versions. The draft as reviewed is [`sqlalchemy-transaction-experiments/p5a-review/reviewed-draft.md`](sqlalchemy-transaction-experiments/p5a-review/reviewed-draft.md). The revised reproduction is `check/p5a_close_v2.py`, with its output in `check/p5a_close_v2.out`.

Labels: **[Obs]** run in this review. **[Src]** code reading. **[Doc]** documented text. **[Judg]** my assessment. Line numbers are SQLAlchemy 2.1.5 at tag `rel_2_1_5` (`4fbf72c`). Every cited module is byte-identical to the PyPI wheel (`E/e0/checks.txt`). `E/` is [`sqlalchemy-transaction-experiments/p5a-review/`](sqlalchemy-transaction-experiments/p5a-review/). The evidence index is at the end.

## Verdict: CONFIRMED DEFECT

The behavior contradicts two explicit documented guarantees. It is reachable without replacing any DBAPI method, and SQLAlchemy 1.3.24 does not have it. How often production commit failures meet the precondition is not established, so this review assigns no severity.

## Reproduction validity

- **[Obs]** After the single change `5432` → `55454`, the draft's script and `check/p5a_close.py` have identical ASTs. Their text differs only in comment lines (`E/e0/checks.txt`).
- **[Obs]** Fresh venv from PyPI: SQLAlchemy 2.1.5, psycopg 3.3.6 (binary, libpq 18.0.6), Python 3.13.11. Server: PostgreSQL 18.6 in `sa-tx-probe`. In the investigator's venv, all 270 SQLAlchemy files match the wheel's RECORD hashes.
- **[Obs]** Fresh process: exit 0. Stdout is byte-identical to the Observed block. Stderr has exactly two `Exception during reset or similar` entries (`E/e0/run.*`).
- **[Obs]** Server log for that run (`E/e0/server.log`): backend 3147 received `BEGIN` and the `doomed` insert, then nothing until the second checkout's `next` insert and `COMMIT`. It received no `ROLLBACK` and no second `BEGIN`.
- **[Obs]** Independent harness, case `explicit-runtime` (`E/harness/results/explicit-runtime.*`):
  - During `close()`, no DBAPI `rollback()` is called and psycopg sends nothing.
  - `PoolEvents.reset` fires with `transaction_was_reset=True` while psycopg is `INTRANS`.
  - The second checkout gets the same DBAPI object and pid. `in_transaction()` is false, but psycopg is `INTRANS` and `pg_stat_activity` shows `idle in transaction` with the same `backend_xid` and `xact_start`.
  - Before its own insert, `pg_current_xact_id_if_assigned()` returns the first transaction's xid. After its commit, both `doomed` and `next` are visible.
  - Control `explicit-none`: `transaction_was_reset=False`, the pool reset calls `rollback()`, and the next unit starts a new transaction (xid `NULL` before its insert).
- **Logical vs physical [Obs]:** to SQLAlchemy, the second checkout is "not in a transaction". To PostgreSQL, it is still the first checkout's transaction, with the same xid. The second checkout's `COMMIT` commits that transaction.

## Strongest argument against filing

**[Judg]** "No real driver failure produces this." Every real failure tried below either ended the transaction on the server or was classified as a disconnect. The state needs all of these at once:

- `commit()` raises before PostgreSQL processes `COMMIT`;
- the connection is still healthy;
- the exception is not an exit exception.

A maintainer has rejected a similar class before. In #13381 (zzzeek, 2026-06-17): "SQLAlchemy can't guard against this general idea … you would need to call `conn.invalidate()`".

What weakens it:

- SQLAlchemy sees this failure. The exception propagates through `RootTransaction._do_commit`, which keeps the marker "so that a rollback needs to occur" (`base.py` 2734–2736). DBAPI-level failures also pass through `_handle_dbapi_exception` (1169–1172). **[Src]**
- A documented hook reaches the state with no DBAPI method replaced: a raising `ConnectionEvents.commit` listener (`explicit-listener`, `connect_ctx-listener`, `orm_commit-listener`). **[Obs]**
- A genuine psycopg exception reaches it. Inside psycopg's own `Connection.transaction()`, `commit()` raises `ProgrammingError("Explicit commit() forbidden within a Transaction context")` before sending (psycopg `_connection_base.py` 577–584; case `explicit-psycopg_txn_block`). This mixes driver and SQLAlchemy transaction APIs. **[Obs]**
- SQLAlchemy's own suite models a commit failure that keeps the connection: `commit_no_disconnect` (`test/engine/test_reconnect.py` 112–121, 577–622). **[Src]**
- 1.3.24 rolls back in the same sequence (see Source assessment). **[Obs]**

## Contract assessment

The behavior contradicts these documented guarantees:

1. **[Doc]** `Connection.close()` (`base.py` 1252–1256): "Any transactional state present on the DBAPI connection is also unconditionally released via the DBAPI connection's `rollback()` method, regardless of any `Transaction` object that may be outstanding." **[Obs]** That `close()` makes no `rollback()` call.
2. **[Doc]** `PoolResetState.transaction_was_reset` (`pool/base.py` 59–68): it is True when the transaction "was closed inline within the `Connection.close()` method so is guaranteed to remain non-present when this event is reached". **[Obs]** It is True while psycopg is `INTRANS`. The draft does not cite this guarantee.
3. **[Doc]** `Engine.connect()` (`base.py` 3257–3262): leaving the `with` block "has the effect of rolling back any transaction that was explicitly begun or was begun via autobegin". **[Obs]** `connect_ctx-runtime` (commit-as-you-go) is not rolled back.

Nearest text a maintainer could cite in defense, **[Doc]** `pooling.rst` 139–144: "the `Connection` itself, if it releases its transaction upon close, considers `.rollback()` to have been called, and instructs the pool to skip this step." That describes the optimization. It does not permit returning an unresolved failed commit. When the skip was designed (#6004), the stated condition was "if the connection itself has actively emitted a ROLLBACK". That condition is not met here.

I found nothing permitting this. Checked: `Transaction.commit` (2602–2621), `Connection.commit`/`rollback` (998–1047), `errors.rst` 8s2b (235–247, invalidation only) and 8s2a (2009–2021, 1.4 only), and `pooling.rst` 128–175 and 490–505.

## Source assessment

The draft's mechanism and line ranges are correct **[Src]**, and the harness events confirm the path **[Obs]**:

1. `_do_commit` (2719–2737): its `finally` calls `_deactivate_from_connection()` (2676–2682), which sets `is_active=False`. It clears `_transaction` only after success (2737).
2. `close()` (1270–1286) sees the marker and calls `Transaction.close()`.
3. `_close_impl` rolls back only `if self.is_active` (2699–2700), then clears the marker (2707–2708).
4. `skip_reset` becomes true, so `close()` calls `_close_special(transaction_reset=True)` (`pool/base.py` 1575–1578).
5. `_reset` then skips `do_rollback` (1472–1478).

Two things the draft does not cover:

- **`rollback()` after a failed commit also emits nothing.** The same `is_active` gate applies to `Connection.rollback()` (2716–2717 → 2697–2711). **[Obs]**
  - In `rollback_close-runtime`, `rollback()` makes no DBAPI call and psycopg stays `INTRANS`. The actual `ROLLBACK` comes later, from the pool reset in `close()`: the marker is gone by then, so `skip_reset` stays false.
  - In `rollback_reuse-runtime`, the same Connection is reused after `rollback()`. It sees the first transaction's xid, and its `commit()` persists `doomed` with the new row.
  - So calling `rollback()` before `close()` is safe only because the pool reset runs afterwards. See the Follow-up section.
- **History.**
  - **[Src]** In 1.3.24, a failed commit left `is_active` true (`engine/base.py` 1757–1763). The pool reset rolled back through the reset agent, and called `do_rollback` directly even when the agent was inactive (`pool/base.py` 872–893).
  - **[Src]** 1.4.0 already has today's `_do_commit` (2415–2441), from the 1.4 transaction rework that #6004 refers to. It also has `close()` → `_close_no_reset()` (1073–1083), which #6004 added.
  - **[Obs]** Same psycopg2 sequence (`E/harness/p2_close.py`, `E/harness/results/p2-*.stdout`), by version:

    | SQLAlchemy | `rollback()` calls during `close()` | Visible after next commit |
    | --- | --- | --- |
    | 1.3.24 | 1 | `next` only |
    | 1.4.0 (legacy and future), 1.4.54, 2.0.55, 2.1.5 | 0 | `doomed`, `next` |

## Fault-injection assessment

The injection does not bypass SQLAlchemy's exception handling. The exception type matters only through SQLAlchemy's disconnect and exit classification.

- **[Src]** A `RuntimeError` from `do_commit` takes the same `_handle_dbapi_exception` path as a DBAPI error.
  - A disconnect needs a DBAPI error that `is_disconnect` accepts, or an exit exception (2224–2233).
  - psycopg's `is_disconnect` is `connection.closed or connection.broken` (`psycopg.py` 596–600). It never reads the message.
  - The auto-rollback at 2335–2336 is skipped because the transaction is still active at that point.
  - The only difference is wrapping (2256–2261): a `RuntimeError` reaches the caller unwrapped.
- **[Obs] Leaks:** `RuntimeError`; `psycopg.OperationalError` and `psycopg.ProgrammingError` on a healthy connection; `OperationalError("server closed the connection unexpectedly…")`, where the message is ignored and `connection_invalidated=False`; a raising commit listener; the genuine psycopg guard.
- **[Obs] Does not leak:** `KeyboardInterrupt`, `asyncio.CancelledError`, and builtin `TimeoutError`. The connection is invalidated, the next checkout gets a new backend, and `doomed` is absent. These are exit exceptions (`util/concurrency.py` 30–35); on Python 3.11+, `asyncio.TimeoutError` is the builtin.

## Real-world applicability

**Demonstrated [Obs]:**

- **Affected:**
  - explicit `Transaction.commit()` followed by `close()`;
  - `with engine.connect(): … conn.commit()`;
  - `with Session(engine): … session.commit()`. `SessionTransaction.close` skips the inactive transaction and then calls `connection.close()` (`orm/session.py` 1435–1438). **[Src]**
  - the asyncio engine with async psycopg (`E/harness/results/followup-asyncio.stdout`);
  - psycopg2;
  - SQLAlchemy 1.4.0, 1.4.54, 2.0.55, and 2.1.5. No other versions were run.
- **Not affected:** `engine.begin()` (which is `connect()` plus `conn.begin()`, 3234–3236), `Session.begin()`, `session.rollback()` then close, and `conn.rollback()` then `close()`. In each, `rollback()` runs first: explicitly, or from the context manager (`engine/util.py` 140–146). It clears the marker without a DBAPI call, so the pool reset sends `ROLLBACK`.
- **`pool_pre_ping=True` (psycopg 3):** the leak becomes loud, and one request fails (`E/harness/results/followup-preping.stdout`).
  - The next checkout raises `ProgrammingError: can't change 'autocommit' now: connection in transaction status INTRANS`, because `do_ping` toggles autocommit (`_psycopg_common.py` 183–196).
  - The pool invalidates the record (`pool/base.py` 1415–1422, 733–743), and the old backend disappears.
  - The following checkout is clean, and `doomed` is absent.
- **Real failures, no injection.** None of these reproduces the reported leak:
  - **Server rejects `COMMIT`:** deferred unique violation (23505), `SERIALIZABLE` failure "during commit attempt" (40001), `pg_cancel_backend` during `COMMIT` (57014). PostgreSQL ends the transaction: psycopg is `IDLE`, the server log shows the error on `COMMIT`, and the next unit sends a fresh `BEGIN`. Skipping the reset is harmless.
  - **Connection loss:** terminated while idle in transaction (57P01), terminated during `COMMIT`, or closed client-side. SQLAlchemy invalidates the connection.
  - **`KeyboardInterrupt` while waiting for `COMMIT`:** psycopg cancels the query (`connection.py` 485–515) and SQLAlchemy invalidates.
  - **Client-side non-exit exception after `COMMIT` was sent** (SIGALRM raising an `Exception` subclass; `E/harness/results/followup-alarm_outcome.stdout`): the same reset skip, with a different symptom.
    - The server completed that `COMMIT`, so `doomed` and `slow` were committed by their own transaction.
    - The pool took the connection back with `transaction_was_reset=True` while psycopg was `ACTIVE`.
    - The next checkout's first statement failed with "another command is already in progress", and the pool then discarded the connection.

**Hypothetical, not shown:**

- how often production commits fail before transmission without a disconnect;
- asyncpg, pg8000, other databases, and instrumentation wrappers that raise in `commit()`;
- whether SIGALRM-style client timeouts occur in practice.

## Duplicate assessment

No equivalent report found. On 2026-10-18 I searched GitHub issues and discussions (queries in the evidence index). `main` has nothing beyond `rel_2_1_5` except one version-placeholder commit. No open Gerrit change touches this path.

Nearby, but different:

- **#6004** (1.4.0): replaced the reset agent with `_close_no_reset`, and states the intended skip condition. This is the design origin, not a report of this bug.
- **#13657** (fixed in 2.1.5): a failed asyncpg `BEGIN` whose `close()` rollback raised. The fix keeps `skip_reset=False` only when that rollback raises (1267–1269). Here nothing raises.
- **#13381**: asyncpg cancellation inside `before_cursor_execute`. The 2.1 fix routes hook exceptions through error handling (`changelog_21.rst` 963). The `commit` hook is still dispatched outside the `try` (`base.py` 1158–1159).
- **#5824** (1.4): asyncpg must discard its transaction after a failed commit. That is a server-side failure with an adapter-level fix.
- **Discussions:** #12460 (asyncpg native transaction plus cancellation), #12745 (SSL disconnect), #10253 (ORM `PendingRollbackError` misuse).

Tests **[Src]**:

- `test_commit_fails_flat` / `_ctxmanager` (`test_transaction.py` 181–219) and `test_commit_fails_trans` (`test_reconnect.py` 577–622) assert only the logical state.
- `ResetAgentTest` (`test_transaction.py` 1669–1905) has no failed-commit case. Its class comment says reset-on-return exists so "the state is cleared".
- `test_failed_commit_recover` (`test_async_pg.py` 278–306) covers only the server-side failure.

No test or source comment states that the open transaction may be returned to the pool.

## Required corrections

None. Every factual claim in the draft held at runtime, and the line numbers are correct.

## Final recommendation

**File**, with text you approve. These additions are optional, not required. Each answers a question a maintainer is likely to ask:

1. A trigger with no DBAPI replacement: a raising `ConnectionEvents.commit` listener.
2. Affected versions: observed on 1.4.0, 1.4.54, 2.0.55, and 2.1.5. 1.3.24 rolls back.
3. The second guarantee: `PoolResetState.transaction_was_reset` (`pool/base.py` 59–68), observed True while `INTRANS`.
4. Scope:
   - affected: commit-as-you-go inside `with engine.connect()` or `with Session()`;
   - not affected: `engine.begin()` and `Session.begin()`;
   - with `pool_pre_ping=True`, it becomes one failed checkout instead of a silent commit.

**Venue.** SQLAlchemy's bug-report form asks reporters to open a Usage Questions discussion instead (`.github/ISSUE_TEMPLATE/bug_report.yaml` at `rel_2_1_5`; `config.yml` sets `blank_issues_enabled: false`). Maintainers converted #13656 into #13657, and #11816 into #11819. Decide the venue before posting.

**Related finding, outside this issue (no draft edited).** Draft A contrasts the two paths: "a failed commit keeps the marker so a rollback is still required". That is true at the logical level, but the required rollback sends no `ROLLBACK` (`rollback_reuse-runtime`). If a maintainer fixes Draft A by making the failed-rollback path mirror the commit path, reusing the same Connection would still commit the stranded writes.

## Follow-up: `rollback()` after a failed commit (not filed)

This is recorded as a follow-up. It is not part of P5a and has no upstream draft yet.

- **[Obs]** `rollback_reuse-runtime`, step by step:
  1. `commit()` raises before send.
  2. `Connection.rollback()` returns without a DBAPI call; psycopg stays `INTRANS`.
  3. The same Connection autobegins a new logical transaction. Its `pg_current_xact_id_if_assigned()` returns the first transaction's xid.
  4. Its `commit()` persists `doomed` together with `same-connection`. The server log shows one `BEGIN` for both.
- **[Src]** It goes through the same gate as P5a: `RootTransaction._do_rollback` → `_close_impl(try_deactivate=True)`, which calls the DBAPI rollback only `if self.is_active` (`base.py` 2697–2700, 2716–2717).
- **Relation to SA-03 (Draft A):** both reach the same checked-out reuse. Draft A gets there through a failed `rollback()`. This gets there through a failed `commit()` followed by a `rollback()` that appears to succeed.
- **Not yet tested:** a `Session` bound to an external `Connection` (the shape of Draft A's case 2), after a failed commit. A Session-owned connection is safe here: `session.rollback()` releases it, and the pool reset sends `ROLLBACK` (`orm_rollback_close-runtime`).

## Evidence index (`E/`)

- `README.md`: layout, how to rerun, and provenance notes.
- `e0/`: `draft_script.py` (extracted unchanged), `draft_script_55454.py`, `draft_observed.txt`, `run.stdout`, `run.stderr`, `run.exit`, `server.log`, plus the check scripts and `checks.txt`.
- `harness/p5a_review.py`: one case per process, using pass-through probes on psycopg `_exec_command`, `Connection.commit`/`rollback`, and pool and connection events. Each transaction runs one extra `select pg_current_xact_id_if_assigned()`. It writes only table `p5a_review`.
- `harness/run_cases.py`: runner. `harness/summary.txt`: per-case table. `harness/results/<case>.{json,stderr,serverlog}`.
- `harness/followups.py`: `results/followup-{preping,alarm_outcome,asyncio}.stdout`.
- `harness/p2_close.py`: `results/p2-{venv13,venv140,venv14,venv20,venv}-*.stdout` (SQLAlchemy 1.3.24, 1.4.0, 1.4.54, 2.0.55, 2.1.5).
- SQLAlchemy source, docs, and tests: tag `rel_2_1_5` (`4fbf72c07f5b`). The shallow clone was not kept.
- GitHub searches (issues): `commit "idle in transaction"`, `failed commit close pool rollback`, `transaction_was_reset`, `skip_reset`, `_close_no_reset`, `"Reset agent is not active"`, `commit exception connection returned to pool`, `commit fails rollback not called`, `inactive transaction close rollback`, `"rollback() fully" commit failed`, `commit error next checkout transaction`, `reset on return commit failed`. Discussions: five similar queries. Read in full: #6004, #13657, #13381, #11819, #5326, #5361, #5824, #7388, and discussions #12745, #10253, #12460.
