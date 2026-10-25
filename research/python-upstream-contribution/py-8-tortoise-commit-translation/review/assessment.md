# PY-8 review package: assessment (items 5-8)

Runs on 2026-10-25, 05:04–05:08 UTC; written after them, and amended at 06:04 UTC (8.9). Written by: Claude Opus 5.5 (max).

This file holds the runtime checks and the analysis. The code they refer to is quoted verbatim in [`materials.md`](materials.md). Read that first if you want to form your own view before reading this one.

**The patch under review** (`../branch/fix.patch`, SHA-256 `ac1bad08bc41016ca597885db9170cbe6065eb9d6dcbc66dfce24b60356a1540`, uncommitted on `fix/commit-integrity-error`, base `develop` `ad0d6ce2b878`). In the asyncpg and psycopg backends, `TransactionWrapper.commit()` catches the driver's integrity-error class (SQLSTATE class 23) around the driver's commit call, and raises `tortoise.exceptions.IntegrityError`. Every other error passes through unchanged. Two PostgreSQL-only tests and a changelog entry come with it.

**Labels.** Every claim is either observed in a recorded run (*observed*) or read from source (*Src*). "Develop" means a detached worktree of `origin/develop` `ad0d6ce2b878`. "Branch" means the checkout with the patch. Both ran in the same virtualenv: Python 3.13.11, asyncpg 0.31.0, psycopg 3.3.3, psycopg-pool 3.3.0, on PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72…`).

## Classification

| # | Concern | Classification | Evidence |
| --- | --- | --- | --- |
| 5 | `update_or_create()` with a deferred constraint: does the patch change its behaviour correctly? | Expected behavior (intended) | Observed, 3/3 per driver, develop and branch |
| 6 | Connection usability after a failed COMMIT | No issue found | Observed, 3/3 per driver; server log |
| 6 | Who cleans up after a failed COMMIT | Expected behavior: PostgreSQL ends the transaction; Tortoise sends nothing; the pools do only their routine step | Observed; server log; Src |
| 7 | Exception chaining differs between the asyncpg and psycopg changes | Expected behavior: each matches its module's translator; psycopg's form is historical | Git history; observed |
| 8.1 | Nested blocks: a failed `RELEASE SAVEPOINT` | No issue found | Observed (check 1 on the branch) |
| 8.2 | Nested blocks: a deferred violation inserted in a savepoint | No issue found | Observed (step 2, part 2) |
| 8.3 | `get_or_create()` inside an outer transaction with a deferred violation | Expected behavior (deferred constraints are checked at the outer COMMIT); unchanged | Src, and the mechanism of 8.2 |
| 8.4 | An explicit `conn.commit()` inside the block that fails | No issue introduced. Pre-existing: the block's exit replaces the error | Observed, identical on develop and branch |
| 8.5 | Callers that catch the driver's exception at block exit | Expected behavior (the intended compatibility change) | Observed |
| 8.6 | Fallback reads in `get_or_create()` and `update_or_create()` after a failed COMMIT | No issue found | Observed |
| 8.7 | Other errors at COMMIT (40001, 40P01, 25P03, a lost connection, custom SQLSTATEs from deferred triggers) | Expected behavior (unchanged) | Src; not run |
| 8.8 | Cancellation during COMMIT | No issue found | Src; not run |
| 8.9 | The changelog entry omits `update_or_create()`, whose behaviour changes too | Minor change recommended; applied afterwards (see 8.9) | Observed (item 5) |
| 8.10 | The changelog's `(#XXXX)` placeholder | Procedural: replace once the PR number exists | — |

No confirmed defect in the patch was found.

## 5. `update_or_create()` with a PostgreSQL deferred constraint

**How it reaches COMMIT** (Src, `tortoise/models.py` 1344–1382). Each of up to three attempts opens `in_transaction()`, locks with `SELECT … FOR UPDATE` and, if a row exists, updates it.
- **The update path.** `return instance, False` is evaluated inside that block, so a COMMIT failure in the block's `__aexit__` propagates instead of the return value. No handler catches it.
- **The create path.** Otherwise the attempt calls `_create_or_get()`. That catches `IntegrityError` from its own `in_transaction()` block, re-reads the row with `get()`, and either returns it with `created=False` or re-raises.
- **The retry.** When `created` is false, the loop retries the update path on a fresh, locked read.

**Program:** `../chk_update_or_create.py`. Outputs are in `output/update-or-create/{develop,branch}-{asyncpg,psycopg}.rep{1,2,3}.out`, with the server-log transcripts in `output/server-log-transcripts.txt`. Table `item` has a UNIQUE `code` and a foreign key `parent_id`, both `DEFERRABLE INITIALLY DEFERRED`. A separate psycopg connection reads the rows.

| Arm | Develop (asyncpg and psycopg) | Branch (asyncpg and psycopg) | Rows afterwards, both |
| --- | --- | --- | --- |
| 1. Update path: `'A'` exists; `defaults={'parent_id': 999}` violates the foreign key | the driver's `ForeignKeyViolation(Error)` from the COMMIT | `tortoise.exceptions.IntegrityError` | `'A'` unchanged: `(1, 1, 1)` |
| 2. Create path: `code='B'`, `defaults={'parent_id': 999, …}` | the driver's error; no SELECT after the failed COMMIT | `IntegrityError`, after one fallback SELECT (log) | no row `'B'` |
| 3. Race: a competitor's uncommitted row holds `code='C'` (id 3, value 1); `defaults={'value': 2, …}` | waits at `COMMIT`, then the driver's `UniqueViolation(Error)` (23505) | waits at `COMMIT`; fallback SELECT finds the competitor's row; the retry's `SELECT … FOR UPDATE` and `UPDATE` apply the defaults; returns `created=False, id=3, value=2` | develop: `(3, 1, 1)`; branch: `(3, 1, 2)` |
| 4. Control: create `'D'`, then update it | `created=True`, then `created=False, value=2` | the same | `(5, 1, 2)` |

All 12 runs exited 0. Each group's three repetitions are byte-identical, and so are the server-log transcripts of every group.

**Assessment.** The patch changes `update_or_create()` in exactly two ways.
- **Arms 1 and 2:** the exception class, with the database state unchanged.
- **Arm 3:** `update_or_create()` now completes the race recovery its loop was written for. It applies its defaults to the row the other caller inserted, instead of raising the driver's exception.

That is the documented intent. The docstring says "Each concurrent insert conflict is followed by a fresh locked read". PR #2276, which added the loop, says "The losing `update_or_create()` call now applies its own defaults to a freshly read row" (Src). Before the patch, that recovery was unreachable whenever the conflict surfaced at COMMIT, as it does for deferred unique constraints.

Classification: **expected behavior**. The changelog entry should name `update_or_create()` as well (8.9).

## 6. Connection usability after a failed COMMIT

**Program:** `../chk_connection_reuse.py`. Outputs: `output/connection-reuse/{develop,branch}-{asyncpg,psycopg}.rep{1,2,3}.out`.
- **Pool.** One connection (`minsize=1&maxsize=1`), so every block gets the same physical connection unless the pool replaces it.
- **Release instrument.** The pool's `release()` is wrapped. It records, at the moment Tortoise hands the connection back and before the pool's own reset:
  - the backend PID;
  - the driver connection object;
  - the driver's transaction state: asyncpg `is_in_transaction()` and whether a `Transaction` is still attached (`_top_xact`); psycopg `info.transaction_status` and its count of open `Transaction` contexts (`_num_transactions`).
- **Rollback counter.** `TransactionWrapper.rollback()` is wrapped to count Tortoise's calls.
- Neither instrument changes behaviour.

Observed, three of three per driver. Develop and branch are identical apart from the exception's class.

| Step | asyncpg | psycopg |
| --- | --- | --- |
| 1. Block that commits | baseline PID and object; released with `is_in_transaction()=False`, no `Transaction` attached | baseline; released `IDLE`, 0 open contexts |
| 2. Block whose COMMIT fails (deferred FK) | develop: `ForeignKeyViolationError`; branch: `IntegrityError` (cause and context the driver's error). Released: same PID, same object, `is_in_transaction()=False`, no `Transaction` attached. Tortoise `rollback()` calls: 0. `pg_xact_status`: aborted | develop: `ForeignKeyViolation`; branch: `IntegrityError` (context the driver's error). Released: same PID, same object, `IDLE`, 0 open contexts. `rollback()` calls: 0. aborted |
| 3. `pg_stat_activity` for that PID, from a separate connection | `idle`, no transaction start, no transaction ID | the same |
| 4. Independent block that writes and commits | same PID and object; committed; row visible to the separate connection | the same |
| 5. Plain query | same PID and object | the same |
| Python log records (WARNING and above) | none | none |

**The server log** (`output/server-log-transcripts.txt`, groups `py8-reuse-*`). One session serves the whole run. After `COMMIT` is answered with ERROR 23503, the next statement on the connection is the pool's routine step:
- asyncpg's reset query, `SELECT pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;`, which it sends after every release, including after the successful blocks;
- psycopg_pool's empty check query, which it sends before every checkout.

No `ROLLBACK` is sent by anyone.

**Who does what after a failed COMMIT:**
- **PostgreSQL** ends the transaction: a COMMIT that fails on a deferred constraint rolls it back. The backend is `idle` immediately afterwards (observed).
- **asyncpg** marks its `Transaction` failed. It detaches it from the connection before sending `COMMIT` (`if self._connection._top_xact is self: self._connection._top_xact = None`, Src, `asyncpg/transaction.py` `__commit`). So on release, `Connection.reset()` sees no open transaction, logs nothing, and sends no `ROLLBACK`; it only runs the reset query (observed; Src, `asyncpg/connection.py` 1527–1571).
- **psycopg** pops the transaction context before sending `COMMIT` (`_commit_gen` calls `_pop_savepoint`, Src). The connection is `IDLE` with no open context, so `psycopg_pool._reset_connection` has nothing to roll back (observed; Src, `psycopg_pool/pool_async.py` 852–892).
- **Tortoise** does nothing. `TransactionContextPooled.__aexit__` does not call `rollback()` when `commit()` raises, and only releases the connection in its `finally` (0 calls observed; Src, `backends/base/client.py` 373–386).

The patch replaces the exception object after the driver has finished, so none of this changes. Classification: connection reuse, **no issue found**; the cleanup, **expected behavior**.

## 7. Exception chaining

| Translator | Chains with `from exc`? | History (git) |
| --- | --- | --- |
| asyncpg `_translate_exceptions` | yes, all three branches | Added on 2026-09-12 by commit `a9f72df7a` "Fix lint issues", inside PR #2261 ("allow password to be a sync/async callable"). Before it, the translator raised without `from` |
| psycopg `_translate_exceptions` | no | Unchanged since it was written in #1072 (2022-03-04) |
| MySQL, ODBC, SQLite translators | no | — |

- **No stated rationale.** PR #2261's description, its single review (an approval with no text) and its comments say nothing about chaining; I searched for "from exc", "chain" and `__cause__`.
- **So psycopg's form is historical,** the repository's original convention, and asyncpg's chaining is an incidental later change. Neither is a recorded policy.
- **The functional difference is nil.** The driver's exception stays reachable either way: as `args[0]` and `__context__` on both drivers, and also as `__cause__` on asyncpg. Only the traceback's linking sentence differs. The runs above print exactly this.
- **The patch** follows its own module in each file. That is the conservative choice; making psycopg chain would be a separate convention change, and the evidence doesn't call for one.

Classification: **expected behavior**. No change recommended.

## 8. Remaining failure modes

**8.1 A failed `RELEASE SAVEPOINT` in a nested block.** `release_savepoint()` calls the patched `commit()` on both drivers.
- **Class 25.** On an aborted transaction, RELEASE fails with class 25, which the patch does not translate. On the branch the raw class-25 error still reaches the application, the outer block still sends its own `ROLLBACK`, the pool reuses the connection, and nothing is logged. Observed in check 1, 3/3 per driver, with the server log: `../branch/output/nested/`, `../branch/output/server-log-*`.
- **The rejected alternative.** Decorating `commit()` with the full translator (candidate C1) made the outer block skip its rollback. That is why the patch is narrow; step 1's evidence is in `../output/nested/`.
- **Class 23** cannot occur at RELEASE: see 8.2.

**No issue found.**

**8.2 A deferred violation inserted inside a savepoint.** The nested block exits normally, because RELEASE does not check deferred constraints. The outer COMMIT then fails, and on the branch raises `IntegrityError`. Observed, 3/3 per driver (`../branch/output/after-change/*`, part 2). **No issue found.**

**8.3 `get_or_create()` inside an outer transaction.** `_create_or_get()` then runs in a savepoint, so a deferred violation surfaces at the outer COMMIT, outside `get_or_create()`. Its fallback does not run, and it returns `created=True` for a row that will not commit. This follows from deferred constraints and is unchanged by the patch, which only changes the outer COMMIT's exception class. Src, plus the mechanism observed in 8.2; not run for `get_or_create()` itself. **Expected behavior.**

**8.4 An explicit `conn.commit()` inside the block that fails.** This is a supported pattern: `tests/test_manual_sql.py::test_in_transaction_commit`. Program `../chk_explicit_commit.py`; outputs `output/explicit-commit/`, 3/3 per driver, byte-identical.

| | asyncpg, develop and branch | psycopg, develop and branch |
| --- | --- | --- |
| (a) error not caught in the block | the block's exit calls `rollback()` on the failed transaction, and raises `InterfaceError: cannot rollback; the transaction is in error state` | the exit raises `RuntimeError: generator didn't stop after athrow()` |
| (b) error caught in the block | the exit calls `commit()` again: `InterfaceError: cannot commit; the transaction is in error state` | the exit's second `commit()` is a silent no-op, and the block exits normally |

- **Unchanged by the patch.** In (a) the original error is the replacement's `__context__`: the driver's error on develop, `IntegrityError` on the branch. That is the only difference, and the replacement exceptions are the same.
- **Database and connection.** In every case nothing was committed, the backend was `idle`, the same connection served a follow-up transaction, and the server received nothing after the failed `COMMIT` (transcripts in `output/server-log-transcripts-explicit.txt`).
- **Classification for the patch: no issue introduced.** The replaced error in (a) and (b) is pre-existing behaviour of the transaction contexts after an explicit commit fails. It could be a separate follow-up, outside this PR. Whether it is a defect is the maintainers' call.

**8.5 Callers that catch the driver's exception at block exit.** On asyncpg and psycopg, code that catches `asyncpg.IntegrityConstraintViolationError`, `psycopg.errors.IntegrityError`, their subclasses, or broad bases (`asyncpg.PostgresError`, `psycopg.Error`) around an `in_transaction()` exit no longer catches a COMMIT-time integrity error. The same goes for `atomic()`, which uses `in_transaction()` (Src). Code that catches `tortoise.exceptions.OperationalError` now does, since `IntegrityError` subclasses it, just as for the same error from a statement. Observed in every run above. **Expected behavior:** the intended compatibility change, which the PR text must state.

**8.6 Fallback reads after a failed COMMIT.** On PostgreSQL the failed COMMIT has already ended the transaction. `_create_or_get()`'s fallback `get()` runs through `using_db(db)`, the base client, so it uses a separate pool checkout and sees only committed data.
- With a deferred foreign key it found nothing and re-raised `IntegrityError`.
- In the race it found the competitor's committed row (items 5 and step 2).
- Observed. Contrast SQLite, which the patch leaves untouched: there the failed COMMIT leaves the transaction open on the shared connection, and the fallback read a phantom row (step 1).

**No issue found.**

**8.7 Other errors raised at COMMIT** stay untranslated, as before, because the patch's `except` names only the class-23 base (Src):
- serialization failure (40001) and deadlock (40P01), which the statement translators do not map either;
- an idle-in-transaction timeout (25P03), class 25 and deliberately left out;
- a lost connection (driver interface errors);
- custom SQLSTATEs raised by deferred constraint triggers.

Not run. **Expected behavior.**

**8.8 Cancellation.** The `except` clause names an `Exception` subclass, so `asyncio.CancelledError` (a `BaseException`) passes through as before. Src. **No issue found.**

**8.9 The changelog wording.** The entry says the change makes "`get_or_create()` handle it like an error from the `INSERT`". `update_or_create()` changes too (item 5: its race recovery now completes). **Minor change recommended:** name both.
- **Applied** on 2026-10-25, 06:03 UTC, at the user's request, after this assessment was written. The entry now ends "so ``get_or_create()`` and ``update_or_create()`` handle it like an error from the ``INSERT``. (#XXXX)".
- `../branch/fix-v2.patch` (SHA-256 `8f2244c160004a266908ebb260f8ee080c61cf895402636befb843f6b3bdcfd8`) is the current diff. It differs from `../branch/fix.patch`, which every run used, only in that line; the source part is byte-identical to `../branch/src.patch`.
- Docutils parses the changelog with the same two errors as on `develop`: the Sphinx roles `:meth:` and `:ref:`, far from this entry.

**8.10 The PR number.** The changelog ends with `(#XXXX)`. Replace it once the PR is opened, with a follow-up commit, since history is not rewritten.

**Not verified here:**
- Python 3.10–3.12 and 3.14 (upstream CI runs 3.10–3.14). The change uses no version-specific syntax (Src);
- the MySQL, MSSQL and Oracle CI jobs, where the new tests are skipped by `requireCapability(dialect="postgres")`. The skip was observed on SQLite;
- PostgreSQL versions other than 18.6. Upstream CI uses the untagged `postgres` image (Src);
- `atomic()` and `update_or_create()` beyond the runs above.

## Recommendation

**READY WITH MINOR CHANGES.**
- **The code and tests are ready as they stand.**
  - The patch does what it claims on both PostgreSQL drivers, three of three, cross-checked by a separate connection, `psql` and the server log.
  - The new tests fail on develop and pass on the branch.
  - The full suites gain exactly the two new tests and no failures, and `ruff`, `mypy`, `bandit`, the build and `twine` pass.
  - Nested-block behaviour and connection reuse are unchanged (items 6, 8.1, 8.2).
  - The behaviour change in `get_or_create()` and `update_or_create()` is the one their code and docstrings intend (item 5).
  - No new failure mode was found.
- **The minor change is to the changelog entry,** which should name `update_or_create()` alongside `get_or_create()` (8.9). Since applied: `../branch/fix-v2.patch`.
- **The `(#XXXX)` placeholder** is filled in after opening (8.10).
- **The pre-existing explicit-commit behaviour** (8.4) is outside this PR.
