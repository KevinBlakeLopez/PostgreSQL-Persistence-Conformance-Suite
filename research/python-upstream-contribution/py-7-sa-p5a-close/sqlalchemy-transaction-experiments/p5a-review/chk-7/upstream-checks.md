# CHK-7 upstream checks

Checked 2026-10-25 between 01:14 and 01:35 UTC (2026-10-24, US Pacific). Written by: Claude Opus 5.5 (max).

All checks were read-only: PyPI's JSON API, a blobless clone of `github.com/sqlalchemy/sqlalchemy`, `gh` (REST and GraphQL), and Gerrit's REST API. Nothing was posted.

## Releases and branches

| Item | Value |
| --- | --- |
| Latest SQLAlchemy on PyPI | **2.1.6**, first file uploaded 2026-10-21 16:25 UTC. The 2.1.x uploads before it: 2.1.5 (2026-10-16), 2.1.4 (2026-10-07). 2.0.55 was uploaded 2026-10-16 |
| Tag `rel_2_1_5` | `4fbf72c07f5bebcabb02e35ee8b742a217ac649d` |
| Tag `rel_2_1_6` | `2f6968cc126d4da2d2eabc5a51285472bb9bfc9e`, committed 2026-10-21 ("- 2.1.6") |
| `main` head | `10f4d1e2d706a7722ca78e79ce05b00333a7aa5b`, committed 2026-10-23 ("disable autoflush within Session.merge_all()"). It is three commits past `rel_2_1_6`: `a4ceb755a` (version 2.1.7 placeholder), `69e49c9c0` (loader criteria), `10f4d1e2d` |
| Latest psycopg on PyPI | 3.3.6 (2026-09-18), the version run |

## Did the cited code change after `rel_2_1_5`?

**Method.** Each function was located with `ast` in the file at each revision. Its dedented source text was then hashed, so a body that only moved compares equal.

**Results,** for `lib/sqlalchemy/engine/base.py`:

| Function | 2.1.5 lines | 2.1.6 lines | Body |
| --- | --- | --- | --- |
| `RootTransaction._do_commit` | 2719–2745 | 2724–2750 | identical |
| `RootTransaction._close_impl` | 2697–2711 | 2702–2716 | identical |
| `RootTransaction._do_close` | 2713–2714 | 2718–2719 | identical |
| `RootTransaction._do_rollback` | 2716–2717 | 2721–2722 | identical |
| `RootTransaction._deactivate_from_connection` | 2676–2682 | 2681–2687 | identical |
| `Connection.in_transaction` | 1058–1060 | 1058–1060 | identical |
| `Connection._commit_impl` | 1157–1172 | 1157–1172 | identical |
| `Connection._rollback_impl` | 1133–1155 | 1133–1155 | identical |
| `Connection._handle_dbapi_exception` | 2211–2355 | 2216–2360 | identical |
| `Connection.close` | 1244–1293 | 1244–1298 | **changed** |

For `lib/sqlalchemy/pool/base.py`:

| Function | 2.1.5 lines | 2.1.6 lines | Body |
| --- | --- | --- | --- |
| `_ConnectionFairy._reset` | 1451–1492 | 1458–1499 | identical |
| `_ConnectionFairy._close_special` | 1575–1578 | 1582–1585 | identical |
| `_ConnectionFairy._checkin` | 1438–1446 | 1445–1453 | identical |
| `PoolResetState` (including the `transaction_was_reset` docstring, 59–68) | 48–90 | 48–90 | identical |
| `_ConnectionRecord._checkin_failed` | 733–743 | 733–743 | identical |
| `_finalize_fairy` | 955–1087 | 955–1094 | **changed** |

`main` is byte-identical to `rel_2_1_6` in `engine/base.py`, `pool/base.py`, `pool/impl.py`, `engine/default.py`, `engine/util.py`, `util/concurrency.py`, and the PostgreSQL dialect files.

### The two changes

Both come from commit `9a70d8961` (2026-10-19, "detach fairy and Connection when close is interrupted"), the fix for issue #13699.

- **`Connection.close()`** (2.1.6 lines 1270–1298). The `finally` that returns the pool connection is now wrapped in a second `try`/`finally`, which sets `_dbapi_connection = None` and `__can_reconnect = False` even if `_close_special()` or `conn.close()` is interrupted.
  - Unchanged: `skip_reset` starts False (1270). It becomes True after `self._transaction.close()` returns (1272–1274). Then `_close_special(transaction_reset=True)` is called (1282–1285).
- **`_finalize_fairy`** (2.1.6 lines 1045–1058). In the branch for an exception that is not an `Exception` subclass, the fairy is now detached from the record before `_checkin_failed()` and the re-raise.
  - Unchanged: the `Exception` branch, which logs "Exception during reset or similar" (1042–1044) and calls `connection_record.invalidate(e=e)` (1059–1060).

**Source reading.** Neither change touches the P5a path. That path is a failed `commit()`, the marker kept, `_close_impl` skipping the DBAPI rollback, `skip_reset=True`, and `_reset` skipping `do_rollback`. No exception is raised during `close()` on it. The 2.1.6 runs agree (see [`README.md`](README.md)).

**Line numbers for 2.1.6.** The issue draft's lines are 2.1.5's. On 2.1.6:
- `RootTransaction` sits 5 lines lower: for example, `_do_commit` is at 2724 and `_close_impl` at 2702;
- `_reset`, `_close_special` and `_checkin` in `pool/base.py` sit 7 lines lower;
- `Connection.close()` keeps its start line (1244) and docstring (1252–1256), but its `_close_special` call moved from 1282–1284 to 1283–1285.

## Duplicate search, 2026-10-18 onward

**Method.** These are GitHub GraphQL searches through `gh api graphql`, run 2026-10-25 01:24:21–01:24:56 UTC. Every query was scoped to `repo:sqlalchemy/sqlalchemy`. The results are in `output/github-search.txt`, and the script is `sa_search.py`.

- **The review's twelve issue queries** (its evidence index) ran over issues and pull requests, all time. Every hit was then filtered to those created or updated on or after 2026-10-18. **Result: none**, for all twelve.
- **Discussions.** The review lists "five similar queries" but not their text. Five equivalent ones ran:
  - `transaction_was_reset`;
  - `failed commit close pool`;
  - `commit exception connection returned to pool`;
  - `commit "idle in transaction"`;
  - `reset on return commit failed`.

  **Result: no hit created or updated on or after 2026-10-18.**
- **Everything new since 2026-10-18.** The search found 19 issues and pull requests, and 4 discussions, created on or after 2026-10-18. It found 36 issues and pull requests, and 5 discussions, updated in that period. Every title was read; they are listed in `output/github-search.txt`.
  - Only #13699 concerns the same code (see below).
  - The four new discussions are #13702 (a docstring typo), #13708 (bind parameters on MySQL 8.4), #13712 (HSTORE `IS NULL`) and #13713 (the greenlet dependency).
- **#13699** (opened 2026-10-19 by the maintainer, closed 2026-10-19 as completed, labels `bug`, `connection pool`, `asyncio`).
  - A cancelled `AsyncConnection.close()`, during the rollback-on-return, left the `AsyncConnection` and its fairy attached to a record that had been checked in. A later `invalidate()` on the stale handle then closed the next checkout's DBAPI connection.
  - Its trigger is a `BaseException` raised during `close()`'s pool reset.
  - P5a's trigger is an exception from `commit()` before `close()`, after which `close()` raises nothing and the reset is skipped.
  - It is not a duplicate. Its fix is the 2.1.6 change above.
- **#13694** appears in the updated-since list. It was opened 2026-10-17 19:29 UTC, carries the label `robots involved :robot:`, and was closed as not planned 12 minutes later; its last update is dated 2026-10-18. Its title is "Cancelled reset on close leaves Connection pointing at a pooled record": a cancellation during `close()`, the same family as #13699, not P5a.

## Gerrit

`https://gerrit.sqlalchemy.org/changes/?q=status:open+file:"<path>"`, queried 2026-10-25:

| Path | Open changes |
| --- | --- |
| `lib/sqlalchemy/pool/base.py` | none |
| `lib/sqlalchemy/engine/base.py` | 6591 "interop typed_col and orm" (updated 2026-05-20); 6548 "WIP: refactor Inspector/TableReflector to a common base" (2026-01-08) |

Neither open change concerns transactions or the pool.
