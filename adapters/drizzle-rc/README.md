# Drizzle 1.0.0-rc.4 adapter

Drizzle ORM 1.0.0-rc.4 with `drizzle-orm/node-postgres` against the suite's disposable PostgreSQL, through `pg.Pool` and `db.transaction()`. The adapter speaks PPCS adapter protocol version 1. It uses `adapters/node-kit` for the protocol and for the node-postgres statement trace.

This release's `drizzle()` accepts `{ client: pool }` or a connection string. It does not accept a positional `Pool`. The adapter passes the case's pool as `drizzle({ client: pool })`. That is the documented constructor. It is not a transaction safeguard.

The cases, the pool size, the writes, the nested `tx.transaction()` calls, and the `{ isolationLevel: 'serializable' }` argument are the same as `adapters/drizzle` (0.45.4). pg is pinned to 8.23.1, the same driver as that adapter.

`TX-04.independent-inner` is UNSUPPORTED, not applicable by design. `TX-05.explicit-serializable` is UNSUPPORTED, capability absent. MG-02 and MG-03 are not implemented.

## Setup

`pnpm run setup` installs this directory from `pnpm-lock.yaml`.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=drizzle-rc --repeat=3
```

The run [`reports/examples/2026-10-19T14-34-08Z-26b178`](../../reports/examples/2026-10-19T14-34-08Z-26b178/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) compares it with 0.45.4.
