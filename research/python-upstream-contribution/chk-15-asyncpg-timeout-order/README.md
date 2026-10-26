# CHK-15: which timeout fires first, and the race at the deadline, for asyncpg's false commit

Run 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

**Name.** It ran under the working name CHK-13, before a concurrent record took that ID. The program, its outputs and the server log say CHK-13 and `chk13-`, and are kept exactly as they ran.

**Question.** [CHK-11](../chk-11-asyncpg-client-timeout/README.md) showed that a caught client-side timeout gives asyncpg's false commit (PY-2 in [the tracker](../../python-upstream-contribution-tracker.md), [asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400)). It left three questions open:

1. What happens when a server-side `lock_timeout` or `statement_timeout` fires before the client's deadline?
2. What happens when the statement finishes just as the client's deadline passes?
3. Does `asyncio.timeout()` behave like `asyncio.wait_for()`?

**Answer (observed).**

1. **Whichever timeout fires first decides the outcome.** If the server's fires first, asyncpg raises `LockNotAvailableError` (55P03) or `QueryCanceledError` (57014). Neither is a subclass of `TimeoutError`, so `except TimeoutError` does not catch them. The error leaves the block, and asyncpg sends `ROLLBACK`. If the client's deadline fires first, the caught `TimeoutError` gives the false commit, also when a server timeout is set but longer. Each arm held 6 of 6: three runs on asyncio, three on uvloop.
2. **At the deadline, a caught `TimeoutError` does not say whether the transaction was lost.** In a sweep of 488 trials across both loops, the statement sometimes finished before the cancel reached the server. The server then ignored the cancel, and the transaction committed. Otherwise the cancel aborted the statement, and the transaction was lost although `COMMIT` returned normally. At durations from 0.1945 to 0.2040 s against a 0.2 s deadline, both outcomes followed the same exception. `COMMIT` never raised.
3. **`asyncio.timeout()` gives the false commit too,** 6 of 6.

**Scope: the trigger is not a recommended design.** In an all-or-nothing transaction, a statement that times out should end the transaction: roll back, or retry the whole transaction. These arms record what asyncpg reports when code catches the timeout and commits anyway, and which timeout decides that. They are a mechanism check, not an example of reasonable application code. The program's docstring calls the timed-out query "optional"; it is left as it ran.

## The transaction

Each arm and each race trial runs one transaction. It inserts an order, reads `pg_current_xact_id()`, then runs a query under a client deadline and catches `TimeoutError`:

```python
async with conn.transaction():
    await conn.execute("insert into orders (marker) values ($1)", marker)
    seen["xid"] = await conn.fetchval("select pg_current_xact_id()::text")
    try:
        await conn.fetch(query, *args, timeout=timeout)  # asyncio.timeout() in one arm
        seen["query"] = "returned"
    except TimeoutError:
        seen["query"] = "caught TimeoutError"
```

- **In the arms,** the query is `select sku from products order by popularity desc limit 3`, with a 0.5 s deadline. In every arm but the control, another session holds the `ACCESS EXCLUSIVE` lock on `products` that an `ALTER TABLE` takes, so the query waits. The server timeouts are set on the subject connection as startup parameters (asyncpg's `server_settings`).
- **In the race,** the query is `select pg_sleep($1)`, with a 0.2 s `fetch(timeout=)`. The 61 durations run from 0.185 to 0.215 s in steps of 0.5 ms, and each is tried four times on each loop.

Nothing is sent between the caught error and the end of the block.

## Each arm

| Arm | Server timeout | What asyncpg reported | PostgreSQL |
| --- | --- | --- | --- |
| `control_unlocked` | none; `products` not locked | the query returned; the block exited normally | `COMMIT`; `committed`; order visible |
| `client_first` | none | `TimeoutError` caught; the block exited normally | `57014` "canceling statement due to user request", then `COMMIT`; `aborted`; order absent |
| `server_lock_timeout_first` | `lock_timeout=200ms` | the block raised `LockNotAvailableError` (55P03) | `55P03` "canceling statement due to lock timeout", then `ROLLBACK`; `aborted`; order absent |
| `server_statement_timeout_first` | `statement_timeout=200ms` | the block raised `QueryCanceledError` (57014) | `57014` "canceling statement due to statement timeout", then `ROLLBACK`; `aborted`; order absent |
| `server_lock_timeout_later` | `lock_timeout=2s` | as `client_first` | as `client_first` |
| `server_statement_timeout_later` | `statement_timeout=2s` | as `client_first` | as `client_first` |
| `asyncio_timeout` | none; `asyncio.timeout(0.5)` instead of `fetch(timeout=)` | as `client_first` | as `client_first` |

## The race

| Class | What asyncpg reported | PostgreSQL | asyncio | uvloop | Durations |
| --- | --- | --- | --- | --- | --- |
| `R` | the query returned; the block exited normally | no error; `COMMIT`; `committed`; order visible | 103 | 94 | 0.1850–0.1985 s |
| `TC` | `TimeoutError` caught; the block exited normally | no error: the cancel arrived after the statement had finished; `COMMIT`; `committed`; order visible | 45 | 50 | 0.1945–0.2040 s |
| `TA` | `TimeoutError` caught; the block exited normally | `57014` "canceling statement due to user request", then `COMMIT`; `aborted`; order absent | 96 | 100 | 0.2015–0.2150 s |

- **The classes overlap.**
  - Every trial was `TC` at 0.1990–0.2010 s on asyncio (and at 0.2020 s), and at 0.1970–0.2010 s on uvloop.
  - Below that range, `R` and `TC` mixed; above it, `TC` and `TA` mixed.
  - `output/{asyncio,uvloop}.race.out` give each trial and a summary for each duration.
- **No trial fell outside the three classes.** In particular, the block never raised: a cancel that arrived after the statement had finished never cancelled the `COMMIT` that followed.

## Agreement

- **Three fates agree for all 530 transactions** (`output/log-check.txt`). They are the program's witness connection, `psql` inside the container (`output/psql-xact-status.txt`), and the server's statement log.
- **The server log's fate.** When PostgreSQL aborts a transaction, the local part of its virtual transaction ID becomes 0 (CHK-11's log check established this). So a final `COMMIT` or `ROLLBACK` with local part 0 arrived after the abort. Otherwise a final `COMMIT` means committed, and a final `ROLLBACK` means aborted.
- **The SQLSTATEs are logged,** with `%e` in the log prefix. The cancels' causes come from the logged messages.
- **The hypotheses.** They are in `log_check.v1.py`; `output/hashes-before.txt` lists that file's SHA-256 under its name at the time, `log_check.py`. The hypotheses are:
  - each arm's full outcome, in all six runs;
  - every race trial is `R`, `TC` or `TA`, with the server-log signature in the table above;
  - `R` occurs only below the deadline, and `TA` only above it, because a statement can be cancelled only while it runs.

  They were written after an exploratory run the same day, not part of this record, which had shown the same classes. All held, under the corrected check (next section).
- **The outputs.** With the transaction IDs masked, the six arm outputs are identical apart from their first line, which names the event loop.
- **The files.** The program, the runner, its helper and the first checker have the same SHA-256 before and after the runs (`output/hashes-before.txt`, `output/hashes-after.txt`).

## Apparatus incident

The first cross-check, `log_check.v1.py` (output `output/log-check.v1.txt`), compared the server's error messages verbatim, so it reported `server_lock_timeout_first` as not held. PostgreSQL logs that error as "canceling statement due to lock timeout at character 17". The suffix is the error's position: character 17 is where `products` starts in the query.

The corrected `log_check.py` drops the ` at character N` suffix before comparing; nothing else changed (`diff log_check.v1.py log_check.py`). Every other check passed in both versions. Both versions and both outputs are kept.

## Environment

| Item | Value |
| --- | --- |
| Packages | asyncpg 0.32.0 and uvloop 0.23.0, the latest releases on PyPI on 2026-10-26, in the virtualenv CHK-11 used (`versions-pip.txt`) |
| Python | 3.13.11 (Homebrew), macOS 26.6.2 arm64 |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` |
| Docker | colima 0.9.1, Docker server 28.4.0 (`output/env.txt`). The client reaches the server through colima's port forward |

**The container.**
- A throwaway container on `127.0.0.1:55493`, not `ppcs-postgres`.
- tmpfs storage, a random password and a random `cluster_name` token. The token was checked through the host port before the runs, and the container was removed after them.
- Settings: CHK-12's, with no server timeout by default (`output/server-settings.txt`).

## Commands

```sh
bash run.sh <venv>/bin/python      # container, token check, arms x3 per loop, race per loop, psql fates, server log, cross-check, removal
python -I log_check.py output      # the cross-check alone
```

`run.sh` refuses to start if its container name or port is already in use, and it removes the container on exit.

## Files

- `asyncpg_timeout_order.py`: the arms and the race. Run it as `python asyncpg_timeout_order.py asyncio|uvloop arms|race`, with `DATABASE_URL` set. It creates database `timeout_order` and drops it at the end.
- `run.sh` and `wait_for_server.py`: the runner, and its readiness and token check.
- `log_check.py` (and `log_check.v1.py`, superseded): the cross-check and the hypotheses.
- `output/{asyncio,uvloop}.arms.rep{1,2,3}.out` and `output/{asyncio,uvloop}.race.out`: the complete stdout and stderr of the eight runs. Every run exited 0 (`output/exit-codes.txt`).
- `output/server.log`: the server's complete log (`docker logs`), from initialisation to the `psql` check.
- `output/psql-xact-status.txt`, `output/server-settings.txt`, `output/env.txt`, `output/log-check.txt`, `output/log-check.v1.txt`, `output/hashes-before.txt`, `output/hashes-after.txt`.
- `versions-pip.txt`.
- `SHA256SUMS`: every file except this README and itself.

## Limits

- **The race's numbers are this machine's.** The width of the overlap depends on how long a cancel takes to reach the server, and asyncpg opens a new connection for every cancel. Here that path went through colima's port forward. Other networks were not measured, and nor was TLS, which would add a handshake to each cancel.
- **Not run:**
  - a pool (`create_pool`);
  - SQLAlchemy or Tortoise on top;
  - server timeouts set with `SET LOCAL`, or as role or database defaults;
  - older releases.
  - CHK-11 ran `command_timeout` and `asyncio.wait_for()`.
- **Two query shapes.** The arms wait for a lock, and the race sleeps.
- **Nothing runs after the catch.** A later statement in an aborted transaction would fail with `InFailedSQLTransactionError` (25P02).
