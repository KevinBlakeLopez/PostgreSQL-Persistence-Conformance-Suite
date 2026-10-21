# Tortoise adapter

Tortoise ORM 1.1.9 `in_transaction()` against the suite's disposable PostgreSQL, through `tortoise.backends.asyncpg` and asyncpg 0.32.0. `postgres://` selects that engine. The adapter is a separate Python program. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit.

A nested `in_transaction()` is a savepoint. `atomic()` is a decorator around the same function, so the context manager is the one form. Category C faults patch `asyncpg.Connection.execute` in this process, once, before Tortoise sees the error. A withheld statement raises `RuntimeError` with no SQLSTATE. A rewritten `ROLLBACK TO` is sent as `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint`, and `after-fault` is reported after PostgreSQL answers.

asyncpg's transaction rollback is the statement `ROLLBACK;`. On release, the pool's `Connection._reset` sends `ROLLBACK` with no semicolon when the protocol is still in a transaction. The withhold matches only `ROLLBACK;`, so that reset statement is left alone. `in_transaction()` does not return until the connection has been released, so the last statement visible at `after-end` is often the pool reset query. A TX-01A pass is then "mechanism not exercised" even when `COMMIT` ran. The classifier records that qualifier as an understatement.

Pool `maxsize` is 1, the catalog's `pool_max`. Tortoise's own default is 5. The pool stays open between TX-03's two units.

`TX-04.independent-inner` is unsupported, not applicable by design: there is no propagation mode that promises an independent transaction, and `Model.save` sends its `INSERT` when it is called. Both TX-05 cases are unsupported, capability absent: `in_transaction()` accepts only a connection name. `TX-01B.commit-reply-discarded` is not implemented. MG-02 and MG-03 are unsupported, capability absent: Tortoise ORM 1.1.9 has no migration runner. Aerich is a separate project and is not this adapter.

## Setup

`pnpm run setup` skips this directory because it has no `package.json`.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The manifest command is `./.venv/bin/python main.py`, run with this directory as the working directory.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=tortoise --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by the `TX-01B` prefix and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-19T12-45-38Z-c45624`](../../reports/examples/2026-10-19T12-45-38Z-c45624/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) is the per-case report.
