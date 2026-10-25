# CHK-2: asyncpg's transaction API after PostgreSQL answers `COMMIT` with `ROLLBACK`

Run on 2026-10-24. Written by: Claude Opus 5.5 (max).

This is check CHK-2 from [`../../python-upstream-contribution-roadmap.md`](../../python-upstream-contribution-roadmap.md) §11. It runs the exact standalone program proposed for the PY-2 issue: three times on asyncio and three times on uvloop.

It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies. The independent checks are listed under "Independent verification".

## Question

The gap analysis's probe P1 (`../../python-production-failure-gap-analysis/p1_commit_tag.py`, `output/p1.out`) observed two things on asyncpg 0.32.0, three of three, on asyncio only:

- `async with conn.transaction()` and `Transaction.commit()` return normally after a caught `23505`, while PostgreSQL aborted the transaction;
- a raw `execute('COMMIT')` returns `'ROLLBACK'`.

P1's program also ran SQLAlchemy subjects, and it read asyncpg's state from `repr()`. CHK-2 asks three things:

- Does a standalone program, small enough to post, reproduce the result?
- Does it do so under uvloop as well?
- Can a public API, rather than `repr()`, show what asyncpg recorded?

## Files

| File | Contents | SHA-256 |
| --- | --- | --- |
| `asyncpg_commit_rollback.py` | The program proposed for the issue, byte-identical to the one that ran (same hash before and after the six runs) | `891ffa6a9efc9332f5d3991f904fec5379bd760dc0fc4fe36baca06cd0b0c104` |
| `output/asyncio.rep{1,2,3}.out` | Complete stdout and stderr of the three asyncio runs | `4cf47347…bac`, `b9e71900…4a8`, `ec3a9aac…43c` |
| `output/uvloop.rep{1,2,3}.out` | Complete stdout and stderr of the three uvloop runs | `3f213ff2…954b`, `98d1be2e…895`, `5026e96c…7c0` |
| `output/psql-xact-status.txt` | `pg_xact_status()` of all 24 transaction IDs, read with `psql` inside the container after the runs | `3cd7f7f5483459714703ecf30ae0528d30a55b4b5f767296db7d7b9909688129` |
| `output/server.log` | The server's complete log (`docker logs`), from initialisation to the `psql` check | `bd75bff5bfad248eae1ef21ee2e9d41501b104c90b157fb95f55d551d23e8e3f` |
| `server_log_sessions.py` | Cross-checks the server log, the six outputs and the `psql` fates. Not part of the issue | `5d72cbeaffc7c911f6e2038fd64d1cb8d0ca9320716383d935c33a6207bbacb9` |
| `output/server-log-sessions.txt` | Its output | `7965cf82e200e6680fb8cc9487f38daf7aa1779fab247ce53604fbdd002209db` |
| `output/pip-freeze.txt` | The virtualenv's packages, and how it was created | `f07bbe353a6897e63c649d737347a924210a2df1d8d7a1e751c546bda3199ed8` |

Full hashes of the six outputs:

```text
4cf47347fec1779ad6ea73b434f3343c7765d5e929e3f37cbde3f34bd54b1bac  output/asyncio.rep1.out
b9e71900f57ac112b7699172dbeed1fa7959e819328d0780c7af62c64f62e4a8  output/asyncio.rep2.out
ec3a9aac3fefd73db59b29aca6dbbd6313d622f3b4ebea0fa8f96a842454643c  output/asyncio.rep3.out
3f213ff2cc9d6d9dafb7b5ee2e79bdb77b670e10f2a0720eb5d1f02e4d9e954b  output/uvloop.rep1.out
98d1be2eead6ce646086f230f98d3e9a9c1102a500ebbcba5c5f0a9ba5758895  output/uvloop.rep2.out
5026e96c8fc932848776c75d35a143b0b12f27befd5fed2dd0bd9c59825667c0  output/uvloop.rep3.out
```

The six outputs differ only in the transaction IDs and the event-loop line. They are identical once both are masked.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest), arm64. A throwaway container, `ppcs-chk2-asyncpg-pg`, published on `127.0.0.1:55491`, with a tmpfs data directory, a random password and a random `cluster_name` token. Removed after the runs. Not `ppcs-postgres` |
| Server settings | PPCS's (`max_connections=100`, `log_lock_waits=on`, `deadlock_timeout=1s`), plus `log_statement=all` and `log_line_prefix='%m [%p] app=%a xid=%x '`. Read back before the runs: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout` and `idle_in_transaction_session_timeout` 0 |
| Host | macOS 26.6.2 arm64, colima 0.9.1, Docker server 28.4.0 |
| Python | 3.13.11 (Homebrew) |
| Packages | asyncpg 0.32.0 and uvloop 0.23.0, installed from PyPI wheels with `--only-binary=:all:` into a fresh virtualenv. Both were the latest releases on PyPI that day |
| asyncpg source | The installed `asyncpg/transaction.py` is byte-identical to `master` at `13b01910d` (SHA-256 `b8026893a4a1c7bf8a76de65e0d5fe189b4bc552523d74ce254af219d6c8546f`). `master` has not changed that file since 2023-05-30 |

## Commands

The password is replaced by `<password>`, and the token by `<token>`.

```sh
docker run -d --name ppcs-chk2-asyncpg-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55491:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_lock_waits=on \
  -c deadlock_timeout=1s -c log_statement=all -c 'log_line_prefix=%m [%p] app=%a xid=%x '

# Before the runs: `show cluster_name` through 127.0.0.1:55491 returned <token>.

# From this directory, three runs per event loop, each a separate process:
for loop in asyncio uvloop; do for rep in 1 2 3; do
  DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55491/postgres" \
    <venv>/bin/python -I asyncpg_commit_rollback.py $loop > output/$loop.rep$rep.out 2>&1
done; done

# After the runs: the psql check (its query is recorded in output/psql-xact-status.txt),
# the log, and the cross-check.
docker exec ppcs-chk2-asyncpg-pg psql -U postgres -d postgres -c "<query>"
docker logs ppcs-chk2-asyncpg-pg > output/server.log 2>&1
<venv>/bin/python -I server_log_sessions.py output > output/server-log-sessions.txt
docker rm -f ppcs-chk2-asyncpg-pg
```

All six runs exited 0. They ran one after another on 2026-10-24. By the server log, the first subject statement was at 16:27:54.553 UTC and the last run's `drop database` at 16:27:55.208 UTC. The program creates database `asyncpg_commit_rollback`, and drops it at the end of each run.

## The program

Each arm runs on its own connection. It inserts a marker row, and captures `pg_current_xact_id()`. It then inserts the duplicate `'taken'` into `uniq` and catches `UniqueViolationError`. Finally it finishes the transaction in the arm's own way:

| Arm | How the transaction ends |
| --- | --- |
| `managed` | `async with con.transaction():` exits normally, with the error caught inside the block |
| `explicit` | `tr.start()` … `await tr.commit()`. Then `await tr.rollback()`, to show through the public API what asyncpg recorded |
| `raw` | `execute('BEGIN')` … `execute('COMMIT')`, printing the status string that `execute()` returns |
| `control` | `async with con.transaction():`, with the duplicate insert inside a nested `con.transaction()` (a savepoint) and the error caught outside it |

After each arm, while the subject connection is still open, a separate connection (`repro-witness`) reads three things: `pg_xact_status()` of the captured ID, whether the marker is visible, and the subject session's `state` and `query` in `pg_stat_activity`.

## Result

All six runs agreed: three on asyncio (`asyncio.unix_events._UnixSelectorEventLoop`) and three on uvloop (`uvloop.Loop`).

| Arm | What asyncpg reported | `pg_xact_status` | Marker visible | Session after the call |
| --- | --- | --- | --- | --- |
| `managed` | The block exited normally | `aborted` | no | `idle`, last statement `COMMIT;` |
| `explicit` | `commit()` returned `None`. A following `rollback()` raised `InterfaceError: cannot rollback; the transaction is already committed` | `aborted` | no | `idle`, last statement `COMMIT;` |
| `raw` | `execute('COMMIT')` returned `'ROLLBACK'` | `aborted` | no | `idle`, last statement `COMMIT` |
| `control` (savepoint) | The block exited normally | `committed` | yes | `idle`, last statement `COMMIT;` |

## Independent verification

Three sources agree for all 24 subject transactions (`output/server-log-sessions.txt`: 0 mismatches).

1. **The program's witness connection,** described above. It uses asyncpg too.
2. **`psql` inside the container,** after all runs, with no asyncpg involved. It read `aborted` for the 18 `managed`, `explicit` and `raw` transactions, and `committed` for the 6 `control` transactions.
3. **The server's statement log.** Every subject session's error is the `23505` duplicate-key error. Its last line carries the transaction ID that the program printed. The statements each session sent were:
   - `managed` and `explicit`: `BEGIN;` … `COMMIT;`;
   - `raw`: `BEGIN` … `COMMIT`;
   - `control`: `BEGIN;`, `SAVEPOINT`, `ROLLBACK TO`, `COMMIT;`.

   The `explicit` arm's `rollback()` sent nothing. asyncpg raised `InterfaceError` without contacting the server.

## Compared with the earlier evidence

CHK-2 reproduces P1's asyncpg arms A–D. The managed and explicit forms return normally, and the raw `COMMIT` returns `'ROLLBACK'`. PostgreSQL aborted, and the savepoint control committed. There is no discrepancy. CHK-2 adds three things:

- uvloop;
- a standalone program;
- a public-API signal: `rollback()` reports "the transaction is already committed", where P1 read `state:committed` from `repr()`.

## What this establishes, and what it does not

- **Established.** On asyncpg 0.32.0 with PostgreSQL 18.6, under asyncio and under uvloop, `async with con.transaction()` and `Transaction.commit()` return normally for a transaction that PostgreSQL aborted. asyncpg then records the transaction as committed, as its own `rollback()` error message states. On the same server, a raw `execute('COMMIT')` returns the status string `'ROLLBACK'`.
- **Source reading** (installed 0.32.0, identical to `master`). `Transaction.__commit` (`asyncpg/transaction.py`, lines 175–192) awaits `self._connection.execute(query)` at line 187 without keeping its return value, then sets `TransactionState.COMMITTED` at line 192. `Connection.execute()` documents that return value as ":return str: Status of the last SQL command" (`asyncpg/connection.py`, line 348).
- **Not run here:**
  - other PostgreSQL versions;
  - a connection from `asyncpg.Pool`;
  - pgbouncer;
  - Linux;
  - a `COMMIT` that itself raises (deferred constraints already raise: asyncpg #508);
  - other SQLSTATEs. P6 in the gap analysis covers `57014`, `40P01` and `40001` with a different program.
