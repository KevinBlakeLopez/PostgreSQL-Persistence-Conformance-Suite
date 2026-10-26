# CHK-7 supplement: the P5a triggers that replace no DBAPI method, on SQLAlchemy 2.1.6

Run 2026-10-25 22:46:47–22:46:50 UTC (15:46 US Pacific). Written by: Claude Opus 5.5 (max).

CHK-7 re-ran `../../../check/p5a_close_v2.py` on 2.1.6. That script reaches P5a by replacing the DBAPI connection's `commit()`. An outside review of CHK-7 noted that the 2026-10-18 review's two other triggers, which replace no DBAPI method, were not re-run on 2.1.6. This supplement re-runs them, with the 2026-10-18 harness, unchanged:

1. **A raising `ConnectionEvents.commit` listener,** through three API paths:
   - `Transaction.commit()`, then `close()` (`explicit-listener`);
   - `Connection.commit()` inside `with engine.connect()` (`connect_ctx-listener`);
   - `Session.commit()` inside `with Session(engine)` (`orm_commit-listener`).
2. **psycopg's own `ProgrammingError`:** SQLAlchemy's `Transaction.commit()` called inside psycopg's `Connection.transaction()` block (`explicit-psycopg_txn_block`).

The control is `explicit-none`, where `commit()` succeeds. Each case ran 3 times, each run a separate process, 15 runs in all. The facts are in `../FACTS.md`, facts 14–23.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest). A throwaway container, `chk7s-p5a-pg`, on `127.0.0.1:55454`, with a tmpfs data directory, a random password and a random `cluster_name`. Removed after the runs. Not `ppcs-postgres`, and not `sa-tx-probe` (stopped throughout) |
| Why port 55454 | The harness's URL is `postgresql+psycopg://postgres@127.0.0.1:55454/scratch`. Running it unchanged needs that port and database. libpq read the password from a passfile outside the repository (`PGPASSFILE`) |
| Server identity | Before the runs, `show cluster_name` through `127.0.0.1:55454` returned this container's random token (`output/server-settings.txt`) |
| Server settings | `log_statement=all`, `log_connections=on`, `log_disconnections=on`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '`; read back: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout` and `idle_in_transaction_session_timeout` 0 (`output/server-settings.txt`) |
| Packages | SQLAlchemy 2.1.6, psycopg 3.3.6 with psycopg-binary 3.3.6 (libpq `180006`), typing_extensions 4.16.0, in CHK-7's virtualenv (installed with `pip install --only-binary=:all:`). Both were the latest releases on PyPI, checked just before the runs |
| Python, host | 3.13.11 (Homebrew); macOS arm64, colima VM, `DOCKER_CONTEXT=colima` |
| Harness | `../../harness/p5a_review.py`, SHA-256 `f54a5d7c1306f7cec85d7700c0c773722f8a6c115b9a6beb4fc9107b0b08d48d`, the same bytes as in `cca9b98`; `run_triggers.py` refuses to run otherwise |

## How the outcome was checked

Three sources, independent of the API's return values:

1. **The harness's witness:** a raw psycopg connection in autocommit, outside SQLAlchemy, reading table `p5a_review` after each unit.
2. **The server's statement log:** for each run, the statements of the SQLAlchemy backend, grouped by virtual transaction ID (`%v`). `output/server-log-extract.txt` holds those backends' lines. The whole log stayed outside the repository. Each backend pid had exactly one `connection received` line in the container's lifetime, which the runner checks.
3. **`psql` inside the container:** `pg_xact_status` for each run's transaction IDs, as the harness captured them (`output/psql-xact-status.txt`).

## Commands

`<venv>`, `<password>`, `<token>` and `<scratch>` stand for local values. None of them is in any saved file.

```sh
docker run -d --name chk7s-p5a-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55454:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_statement=all \
  -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x ' -c log_connections=on -c log_disconnections=on
docker exec chk7s-p5a-pg psql -U postgres -qc "create database scratch"
# from the host, with PGPASSFILE: `show cluster_name` returned <token>; settings in output/server-settings.txt

PGPASSFILE=<scratch>/pgpass python3 -I run_triggers.py <venv>/bin/python chk7s-p5a-pg <scratch>/server.log
python3 -I analyze_triggers.py        # prints the xids to look up
docker exec chk7s-p5a-pg psql -U postgres -d scratch -At -F '|' -c "select x, pg_xact_status(x::xid8) \
  from unnest('{757,758,763,764,769,770,775,780,785,790,795,800,805,810,815,820,825,830}'::text[]) as x \
  order by x::bigint" > output/psql-xact-status.txt
python3 -I analyze_triggers.py output/psql-xact-status.txt > output/summary.txt
docker rm -f chk7s-p5a-pg
```

`run_triggers.py` replaced the virtualenv prefix with `<venv>` and this repository's path with `<repo>` in what it saved. Nothing else was edited.

## Files

| File | What it is | SHA-256 |
| --- | --- | --- |
| `run_triggers.py` | Runs the harness, unchanged, 3 times per case; saves outputs and the log extract | `89e285e67b18910ed89f26f4a922b0c378272874736d5575912253a6c70ffbfd` |
| `analyze_triggers.py` | One block per run from the JSON, the log extract and psql, with no pid, xid or timestamp; compares the 3 runs of each case | `d8c3aee80b0891695d2bb3d459885161a0950de6d5c5c5b47855cc71ed11cc89` |
| `output/<case>.rep<N>.json` | The harness's JSON document for each run, including its full event timeline | — |
| `output/<case>.rep<N>.stderr`, `.exit` | stderr (empty in all 15 runs) and the exit code (0 in all 15) | — |
| `output/runs.json` | Each run's start and end times (UTC), exit code and backend pids | `2132087aafc2bf992f78c4545570f831c4715940e9240c3651083754b05cb7dd` |
| `output/server-log-extract.txt` | The server log's lines for the 15 SQLAlchemy backends (315 lines) | `e42c94402bc5feb643ea60d78b75891c1ea5436d007db90e66623846d4be6bb2` |
| `output/psql-xact-status.txt` | `pg_xact_status` for the 18 transaction IDs | `90f52a38770bc5a6ea4f11fde5707b1e51969f70f2394d8fe1f230e66f51e7b4` |
| `output/server-settings.txt` | The server-identity check and the settings read back | `d67fc4d33b30d820fd367e3ffca87bf7bc501ba4387e25a6bacc50424910d296` |
| `output/summary.txt` | `analyze_triggers.py`'s output | `b8779c50b7f3579b6bd82492a2d1e100504bceefb6fabf44b72b9bc721a23c9f` |

## Result

| Case | `commit()` | DBAPI calls from `commit()` to the return to the pool | Pool reset | Next checkout | Server log | `pg_xact_status` |
| --- | --- | --- | --- | --- | --- | --- |
| `explicit-none` (control) | returned | `commit()` once; `rollback()` once, by the reset | `transaction_was_reset=False`, psycopg `IDLE` | Same connection, `IDLE`, no transaction ID before its insert | `COMMIT` and `BEGIN` between the two inserts; different vxids | Both transactions `committed` |
| `explicit-listener` | `RuntimeError: commit listener failed` | none; psycopg sent nothing | `transaction_was_reset=True`, psycopg `INTRANS` | Same connection and backend, `in_transaction()` False, psycopg `INTRANS`, already in the first unit's transaction | The `doomed` insert, the `next` insert and its `COMMIT` in one vxid; no `COMMIT`, `ROLLBACK` or `BEGIN` between the inserts | The first unit's transaction `committed`, by that `COMMIT` |
| `connect_ctx-listener` | the same | the same | the same | the same | the same | the same |
| `orm_commit-listener` | the same | the same | the same | the same | the same | the same |
| `explicit-psycopg_txn_block` | `sqlalchemy.exc.ProgrammingError` wrapping psycopg's "Explicit commit() forbidden within a Transaction context", `connection_invalidated=False` | `commit()` once, raised; psycopg sent `SAVEPOINT`, `ROLLBACK TO` and `RELEASE` of `"_pg3_1"` only | the same as the listener | the same as the listener | the same as the listener, with the three savepoint statements between the inserts | the same as the listener |

In every case, the three runs' blocks in `output/summary.txt` are byte-identical. The witness saw no row after the failed first unit, and both `doomed` and `next` after the next checkout's commit.

One run of each trigger, from `output/server-log-extract.txt`, from the unit's `BEGIN` or its `doomed` insert to the next checkout's `COMMIT`:

```text
22:46:48.190 UTC [110] vxid=11/3 xid=0    statement: BEGIN
22:46:48.191 UTC [110] vxid=11/3 xid=0    statement: insert into p5a_review (code) values ('doomed')
22:46:48.191 UTC [110] vxid=11/3 xid=775  statement: select pg_current_xact_id_if_assigned()::text
22:46:48.196 UTC [110] vxid=11/3 xid=775  statement: select pg_current_xact_id_if_assigned()::text
22:46:48.197 UTC [110] vxid=11/3 xid=775  statement: insert into p5a_review (code) values ('next')
22:46:48.197 UTC [110] vxid=11/3 xid=775  statement: COMMIT

22:46:50.100 UTC [128] vxid=29/3 xid=0    statement: insert into p5a_review (code) values ('doomed')
22:46:50.101 UTC [128] vxid=29/3 xid=820  statement: select pg_current_xact_id_if_assigned()::text
22:46:50.102 UTC [128] vxid=29/3 xid=820  statement: SAVEPOINT "_pg3_1"
22:46:50.103 UTC [128] vxid=29/3 xid=820  statement: ROLLBACK TO "_pg3_1"
22:46:50.103 UTC [128] vxid=29/3 xid=820  statement: RELEASE "_pg3_1"
22:46:50.106 UTC [128] vxid=29/3 xid=820  statement: select pg_current_xact_id_if_assigned()::text
22:46:50.107 UTC [128] vxid=29/3 xid=820  statement: insert into p5a_review (code) values ('next')
22:46:50.107 UTC [128] vxid=29/3 xid=820  statement: COMMIT
```

The `app=[unknown]` field and the date are dropped from these lines; the extract has them in full.

## What this establishes, and what it does not

- **Establishes (observed):** on SQLAlchemy 2.1.6 with psycopg 3.3.6, both triggers reach P5a's state in 3 of 3 runs each, through all three API paths for the listener. The next checkout's `COMMIT` commits the failed unit's write. The outcomes match the single 2026-10-18 run of each of the same four cases, on 2.1.5 (`../../harness/summary.txt`).
- **Does not establish:**
  - whether SQLAlchemy supports a raising `commit` listener, or calling its `commit()` inside psycopg's own transaction block. Both can be read as application misuse;
  - that any ordinary driver or network failure reaches this state. The 2026-10-18 review's real-failure cases ended the transaction on the server or were classified as disconnects; they were not re-run here;
  - production frequency.
- **Not run:** psycopg2, the asyncio engine, `pool_pre_ping=True`, the harness's other cases, and Linux clients.
