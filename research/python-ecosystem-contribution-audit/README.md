# psycopg `Connection.transaction()` after a caught unique violation

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This directory preserves the one diagnostic run made for [`../python-ecosystem-contribution-audit.md`](../python-ecosystem-contribution-audit.md). It is not a PPCS case. The harness did not run it. No CTL-01 or `pg-control` gate applies.

| File | Contents | SHA-256 |
| --- | --- | --- |
| `psycopg_transaction_block.py` | The program, byte-identical to the one that ran | `951bcb4917cd777486591391f7be3f075d913f0070946d83c1e11de5cb39148b` |
| `psycopg_transaction_block.txt` | Its complete stdout and stderr from that run | `079ce18aacc8e1a07a6b26c708b66dbeb21532a80a88895442c270299579c296` |

## Question

psycopg#1453 reports that `Connection.commit()` returns `None` after PostgreSQL answers `COMMIT` with command tag `ROLLBACK`. psycopg also has a transaction context manager, `Connection.transaction()`. Its `Transaction` object exposes a public `status` attribute, added by psycopg PR #1184 for psycopg issue #969 to record whether the block committed or rolled back. No earlier run in this repository exercised that API.

## Run

- **Started:** 2026-10-24T14:10:49Z. Three repetitions, inside one process. Each repetition used a fresh connection.
- **Server:** a throwaway container `ppcs-audit-psycopg-pg`, `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned image), published on `127.0.0.1:55479`, random password. It was removed after the run. The suite's `ppcs-postgres` was not used.
- **Interpreter:** `adapters/sqlalchemy-core/.venv/bin/python -I`, Python 3.13.11. That virtualenv holds psycopg 3.3.6, binary implementation; `psycopg.pq.version()` printed `180006`.
- **Command,** with the password replaced:

  ```sh
  DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55479/postgres" \
    adapters/sqlalchemy-core/.venv/bin/python -I psycopg_transaction_block.py
  ```

The program creates database `audit_psycopg_tx`, and drops it at the end.

Each repetition has two arms, each on its own connection in autocommit mode:

- **Caught.** `with conn.transaction() as tx:` inserts a marker and reads `pg_current_xact_id()`. It then inserts the duplicate `'taken'` into `uniq`, catches `UniqueViolation` inside the block, and lets the block end normally.
- **Recovered.** The same, except the duplicate insert runs inside a nested `conn.transaction()`. That is a savepoint, so the outer transaction stays usable.

After each block, a separate connection reads `pg_xact_status()` of the captured transaction ID, whether the marker is visible, and the backend's `state` and `query` in `pg_stat_activity`.

## Result

All three repetitions agreed.

| Arm | Block raised | `tx.status` | Driver status before → after exit | `pg_xact_status` | Marker visible | Backend after exit |
| --- | --- | --- | --- | --- | --- | --- |
| Control: normal block | — | `committed` | — | — | yes | — |
| Caught `23505` inside the block | no | `committed` | `INERROR` → `IDLE` | `aborted` | no | `idle`, last statement `COMMIT` |
| Savepoint recovery (inner block caught `23505`) | no | `committed` | `INTRANS` → `IDLE` | `committed` | yes | `idle`, last statement `COMMIT` |

## What this establishes, and what it does not

- **Established.** psycopg 3.3.6's transaction context manager returns normally, and reports `Transaction.status` `committed`, for a transaction PostgreSQL aborted. The last statement the server ran for that session was `COMMIT`. The savepoint-recovery arm shows the API committing correctly when the application recovers with a savepoint.
- **Not read here: the command tag of that `COMMIT`.** This program does not wrap psycopg internals. On this server and driver, the tag for `COMMIT` after a caught `23505` is `ROLLBACK`, with status `COMMAND_OK`. That is recorded in [`../production-reachability/reproductions/psycopg_commit_tag.txt`](../production-reachability/reproductions/psycopg_commit_tag.txt), through `cursor.execute("COMMIT")`.
- **Source reading, psycopg 3.3.6 `psycopg/transaction.py`.** `BaseTransaction._commit_gen` (lines 133–140) sets `status` to `COMMITTED` before it sends `COMMIT` through `_exec_command`, and discards the result. `FAILED` is set only when the connection is not `OK` on entry to `__exit__` (lines 272–274). That is consistent with the run. It is not a measured statement about a `COMMIT` that raises.
- **Scope.** Not run: `AsyncConnection.transaction()`, pipeline mode, or another psycopg version.
