# CHK-7 facts: P5a on SQLAlchemy 2.1.6

Compiled 2026-10-24 (US Pacific); runs and checks at 2026-10-25 01:14–01:35 UTC. Revised the same night after an outside review. Facts 14–23, the supplement, were run at 2026-10-25 22:46 UTC: the outside review had noted that the two triggers that replace no DBAPI method were not re-run on 2.1.6. Written by: Claude Opus 5.5 (max).

This file lists facts for the author's own write-up. It is not text to post. Paths are relative to this directory. Labels:
- **Obs:** observed in a run recorded here;
- **Src:** source reading;
- **Doc:** quoted documentation;
- **Judg:** judgment.

## Versions and SHAs checked

| Item | Value | Checked |
| --- | --- | --- |
| SQLAlchemy run | 2.1.6, the latest release on PyPI (uploaded 2026-10-21) | 2026-10-25 01:14 UTC |
| Tag `rel_2_1_6` | `2f6968cc126d4da2d2eabc5a51285472bb9bfc9e` | 2026-10-25 |
| Tag `rel_2_1_5` | `4fbf72c07f5bebcabb02e35ee8b742a217ac649d` | 2026-10-25 |
| `main` | `10f4d1e2d706a7722ca78e79ce05b00333a7aa5b` (committed 2026-10-23) | 2026-10-25 01:16 UTC |
| psycopg | 3.3.6 with psycopg-binary 3.3.6, libpq 18.6 (`180006`). 3.3.6 is the latest release | 2026-10-25 |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg13+2), aarch64, image digest `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` | 2026-10-25 |
| Python, OS | 3.13.11; macOS arm64 (colima VM) | — |
| Script | `../../check/p5a_close_v2.py`, SHA-256 `52bab81dcc588b53e78a83f38e29549b74d8b445ed1c946365b05315c08984b3`, unchanged since `cca9b98` | before and after the runs |
| Installed SQLAlchemy | 270 of 270 files match the wheel RECORD. The cited modules are byte-identical to `rel_2_1_6` | `output/install-check.txt` |

## Observed facts

1. The script exited 0 in 3 of 3 runs (`output/rep{1,2,3}.exit`).
2. All three stdouts are byte-identical to `../../check/p5a_close_v2.out`, which was recorded on 2.1.5 on 2026-10-18. They are also byte-identical to the issue draft's Observed block. All of these files have SHA-256 `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` (`output/rep*.stdout`).
3. **Case 1, after the failed commit.** `commit()` raised before `COMMIT` was sent. The marker was still present, inactive, and `in_transaction()` was False. psycopg was `INTRANS`, and `pg_stat_activity` showed `idle in transaction` (`output/rep1.stdout`, line 2).
4. **Case 1, `close()`.** `close()` returned, and the backend stayed `idle in transaction` (line 3).
5. **Case 1, the reset event.** The pool's `reset` event received `transaction_was_reset=True` while psycopg was `INTRANS` (line 4).
6. **Case 1, the next checkout.** It got the same DBAPI connection and the same backend. `in_transaction()` was False, and psycopg was `INTRANS` (line 5).
7. **Case 1, the result.** After that checkout's `begin()`, insert and `commit()`, the witness connection saw both `doomed` and `next` (line 6).
8. **The server log confirms case 1 in all three runs** (`output/server-log-cases.txt`).
   - The `next` insert and its `COMMIT` ran on the same backend, under the same virtual transaction ID, as the `doomed` insert. In run 1 that is backend 115, vxid `6/3`.
   - The backend sent nothing while `close()` returned it, and no `ROLLBACK` or second `BEGIN` came before the `next` insert.
   - The `next` and `COMMIT` lines carry xid 766, and the `doomed` line carries none. log_statement logs a statement before it runs, and nothing earlier in that transaction assigned an xid. This is not a general rule: a statement such as `select pg_current_xact_id()` would assign one first. The decisive evidence is the shared backend and virtual transaction ID, with no transaction end or second `BEGIN` between the two inserts.
9. **`psql` confirms the commits** (`output/psql-xact-status.txt`). The transactions of case 1 are `committed`: xids 766, 773 and 780, one per run.
10. **Case 2.** A `rollback()` armed to raise was called 0 times during `close()`, and once at the next `close()` (lines 8, 9 and 11). The same connection was reused, and both rows persisted (line 10).
11. **Case 3, the control.**
    - `rollback()` raised, and the pool's reset `rollback()` raised too. The pool then discarded the connection.
    - The next checkout was a different DBAPI connection on a different backend, and only `next` was visible (lines 12–14).
    - In the log, case 3's first backend disconnected after `BEGIN` and `doomed`, with no `ROLLBACK` and no `COMMIT`.
    - `psql` reads xids 770, 777 and 784 as `aborted`. That these are case 3's transactions is inferred from gaps in the sequence, not observed: no log line carries them. The control's outcome rests on what was observed, the disconnection without `COMMIT` and the witness never seeing `doomed`.
12. **stderr** has two `Exception during reset or similar` entries per run, from case 2's later `close()` and from case 3. Both are raised by the armed `rollback()`, called from `_reset` → `pool._dialect.do_rollback`.
    - Compared with the 2026-10-18 run (`../e0/run.stderr`, the draft's script on 2.1.5), only two line numbers differ, each twice: `pool/base.py` 1485 → 1492, and the script's frame 31 → 38 (`output/stderr-vs-2026-10-18.diff`).
13. **The draft's embedded script** is the same program as `check/p5a_close_v2.py`. With its one URL changed from port 5432 to 55454, the ASTs are identical. It differs only in that port and in comment layout.

## Supplement: the two triggers that replace no DBAPI method

Run 2026-10-25 22:46:47–22:46:50 UTC; evidence in `supplement/`, whose README gives the environment and commands. The 2026-10-18 harness, `../harness/p5a_review.py`, ran unchanged (SHA-256 `f54a5d7c1306f7cec85d7700c0c773722f8a6c115b9a6beb4fc9107b0b08d48d`, as in `cca9b98`), with the packages and server image of facts 1–13, against its own throwaway container.

14. **Runs (Obs).** Five cases, 3 runs each, each run a separate process. All 15 exited 0, with empty stderr (`supplement/output/*.exit`, `*.stderr`).
    - `explicit-none`: the control; `commit()` succeeds.
    - A `ConnectionEvents.commit` listener that raises, through three API paths: `Transaction.commit()`, then `close()` (`explicit-listener`); `Connection.commit()` inside `with engine.connect()` (`connect_ctx-listener`); and `Session.commit()` inside `with Session(engine)` (`orm_commit-listener`).
    - SQLAlchemy's `Transaction.commit()` called inside psycopg's own `Connection.transaction()` block (`explicit-psycopg_txn_block`).
15. **Repeatability (Obs).** For each case, the three runs' summaries, which contain no pid, transaction ID or timestamp, are byte-identical (`supplement/output/summary.txt`).
16. **The listener, at the failed commit (Obs), 9 of 9 runs.** `commit()` raised `RuntimeError: commit listener failed`. SQLAlchemy called the DBAPI `commit()` 0 times, and psycopg sent nothing between the failed `commit()` and the connection's return to the pool. On the explicit path, after the failure, the marker was present and inactive, `in_transaction()` was False, psycopg was `INTRANS`, and the backend was `idle in transaction`.
17. **The listener, the return and the next checkout (Obs), 9 of 9 runs.**
    - The pool's `reset` event received `transaction_was_reset=True` while psycopg was `INTRANS`. No DBAPI `rollback()` was called, and the connection was not invalidated. After the return, the backend stayed `idle in transaction`, and the witness saw no row.
    - The next checkout got the same DBAPI connection and the same backend. `in_transaction()` was False, and psycopg was `INTRANS`. Before its own insert, `pg_current_xact_id_if_assigned()` on that connection returned the first unit's transaction ID.
    - After that checkout's `begin()`, insert and `commit()`, the witness saw both `doomed` and `next`.
18. **psycopg's own exception (Obs), 3 of 3 runs.**
    - The DBAPI `commit()` was called once. It raised `psycopg.ProgrammingError`: "Explicit commit() forbidden within a Transaction context. (Transaction will be automatically committed on successful exit from context.)" SQLAlchemy raised it as `sqlalchemy.exc.ProgrammingError`, with `connection_invalidated=False`.
    - psycopg sent only `SAVEPOINT "_pg3_1"`, `ROLLBACK TO "_pg3_1"` and `RELEASE "_pg3_1"`, entering and leaving its block. It sent no `COMMIT` and no `ROLLBACK`.
    - From the pool's `reset` event on, everything was as in fact 17.
19. **The server log, all 12 trigger runs (Obs)** (`supplement/output/server-log-extract.txt`).
    - The `doomed` insert, the next checkout's `next` insert and that checkout's `COMMIT` ran on one backend, under one virtual transaction ID.
    - Between the two inserts, the backend received only the harness's two `select pg_current_xact_id_if_assigned()` statements, plus psycopg's three savepoint statements in fact 18's case. No `COMMIT`, `ROLLBACK` or `BEGIN`.
    - The `next` insert and its `COMMIT` are logged with the transaction ID that the harness captured right after the `doomed` insert.
20. **`psql` (Obs)** (`supplement/output/psql-xact-status.txt`). In each trigger run, the transaction that holds `doomed` is `committed`: 12 transaction IDs, one per run. By fact 19, the next checkout's `COMMIT` is what ended it.
21. **The control (Obs), 3 of 3 runs.** `commit()` returned, and psycopg sent `COMMIT`. The pool's `reset` event received `transaction_was_reset=False` with psycopg `IDLE`, and `rollback()` was called once. The next checkout had no transaction ID before its insert. In the log, a `COMMIT` and a `BEGIN` separate the two inserts, which have different virtual transaction IDs. Both of each run's transactions are `committed` (6 IDs). The harness by itself does not produce facts 16–20.
22. **The same as on 2.1.5 (Obs, against the record).** The four trigger cases' outcomes match the single 2026-10-18 run of each, on 2.1.5 (`../harness/summary.txt`).
23. **Where the listener runs (Src, `rel_2_1_6`).** `Connection._commit_impl` (`lib/sqlalchemy/engine/base.py:1157`) dispatches the `commit` event at 1158–1159, before the `try` around `dialect.do_commit()` at 1169–1172. So an exception from a `commit` listener leaves `_commit_impl` without passing through `_handle_dbapi_exception`, which fits fact 16. #13381's change in 2.1 (`doc/build/changelog/changelog_21.rst:999-1015`) put the `before_cursor_execute` and `after_cursor_execute` hooks inside that error handling. It does not mention the `commit` hook.

## Source lines on 2.1.6 (Src)

Src, and Doc for the two quoted docstrings. `main` (`10f4d1e2d`) is byte-identical to 2.1.6 in both files.

| What | 2.1.6 location | 2.1.5 location, as cited in the draft and review |
| --- | --- | --- |
| `Connection.close()` docstring: released "unconditionally … via the DBAPI connection's `rollback()`" | `lib/sqlalchemy/engine/base.py:1252-1256` | same |
| `skip_reset` becomes True after `self._transaction.close()` | `engine/base.py:1270-1274` | same |
| `_close_special(transaction_reset=True)` call in `close()` | `engine/base.py:1282-1285` | 1281–1284 |
| `Connection.in_transaction()` | `engine/base.py:1058-1060` | same |
| `Connection._commit_impl`: `dispatch.commit` outside the `try` | `engine/base.py:1158-1159`, `do_commit` at 1170 | same |
| `RootTransaction._deactivate_from_connection` | `engine/base.py:2681-2687` | 2676–2682 |
| `RootTransaction._close_impl`: the DBAPI rollback only `if self.is_active` | `engine/base.py:2702-2716`, the gate at 2704–2705 | 2697–2711, gate 2699–2700 |
| `RootTransaction._do_close` / `_do_rollback` | `engine/base.py:2718-2719` / `2721-2722` | 2713–2714 / 2716–2717 |
| `RootTransaction._do_commit`: deactivates in `finally`, clears the marker only after success | `engine/base.py:2724-2750`; `finally` 2730–2737; clear at 2742 | 2719–2745 |
| `PoolResetState.transaction_was_reset` docstring ("guaranteed to remain non-present") | `lib/sqlalchemy/pool/base.py:59-68` | same |
| `_finalize_fairy` calls `fairy._reset(...)` | `pool/base.py:1020-1025` | same |
| "Exception during reset or similar", then `invalidate` for `Exception` | `pool/base.py:1041-1044`, `1059-1060` | 1041–1044, 1052–1053 |
| `_ConnectionFairy._reset`: skips `do_rollback` when `transaction_was_reset` | `pool/base.py:1458-1499`; skip 1479–1485; `do_rollback` 1492 | 1451–1492; 1472–1478; 1485 |
| `_ConnectionFairy._close_special` | `pool/base.py:1582-1585` | 1575–1578 |

**Changed in 2.1.6** (#13699, commit `9a70d8961`): `Connection.close()` (an extra `try`/`finally`) and `_finalize_fairy` (its non-`Exception` branch).
- Src: P5a does call `Connection.close()`, but the new code only acts when the pool connection's close or reset is interrupted. Nothing on the P5a path raises there, so the path behaves as on 2.1.5.
- Obs: the 2.1.6 runs reproduce.

## Upstream (read-only, 2026-10-25)

- **The recorded queries returned no matching item created or updated on or after 2026-10-18** (`output/github-search.txt`). They are the review's 12 issue queries, verbatim, and 5 discussion queries that replace the review's unrecorded ones. This is a search result, not proof that none exists.
- **Everything created since 2026-10-18** was read by title: 19 issues and pull requests, and 4 discussions. Only #13699 touches the same functions (`upstream-checks.md`). It is not a duplicate: its trigger is a cancellation during `close()`'s reset.
- **Gerrit** has no open change on `lib/sqlalchemy/pool/base.py`. The two open changes on `engine/base.py` are unrelated.

## Scripts and outputs the author can paste

- **The script.** The draft's embedded script, unchanged (port 5432). It is the same program as `../../check/p5a_close_v2.py`, which ran here unchanged (fact 13).
- **The output.** The draft's Observed block, unchanged. It is byte-identical to the 2.1.6 output (fact 2).
- **The environment block** would now read SQLAlchemy 2.1.6 (or "2.1.5 and 2.1.6"), psycopg 3.3.6, PostgreSQL 18.6, Python 3.13.
- **Line numbers.** The draft's "Line numbers are SQLAlchemy 2.1.5" stays true as written. If the write-up cites 2.1.6 instead, use the 2.1.6 column above.

## Open questions, and contradictions of earlier claims

- **No contradiction, within what was re-run.**
  - The draft's psycopg 3 run, its Observed block, reproduced byte for byte on 2.1.6.
  - Its other runtime claims, on psycopg2 and in the 1.3–2.0 comparison, were not re-run (below).
  - The verdict CONFIRMED DEFECT is the 2026-10-18 review's contract judgment (Judg). Nothing in CHK-7 contradicts it.
- **A narrowing of an earlier statement.** The PPCS tracker says that `RootTransaction` on `main` is unchanged, and that is still true. `Connection.close()` and `_finalize_fairy` did change in 2.1.6, but off the P5a path (above).
- **Not re-run on 2.1.6:**
  - psycopg2;
  - the asyncio engine;
  - `pool_pre_ping=True`;
  - the 1.3/1.4/2.0 comparison (`../harness/p2_close.py`);
  - the review's other harness cases, including its real driver and server failures. The supplement re-ran four of its cases, and its control (facts 14–23).

  The draft's psycopg2 and version-comparison sentences rest on the 2026-10-18 runs.
- **The review's five discussion queries** were not recorded verbatim. Five equivalent queries were used instead (`upstream-checks.md`).
- **Both supplement triggers can be read as misuse (Judg).** A `commit` listener that raises, and SQLAlchemy's `commit()` inside psycopg's own transaction block, may be called application errors. The supplement shows that each reaches P5a's state on 2.1.6, with a healthy connection. It does not show that SQLAlchemy supports either usage, or that an ordinary driver or network failure reaches this state.
