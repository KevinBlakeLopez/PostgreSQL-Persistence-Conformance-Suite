# Drizzle adapter

Drizzle ORM 0.45.4 with `drizzle-orm/node-postgres` against the suite's disposable PostgreSQL, through `pg.Pool` and `db.transaction()`. The adapter speaks PPCS adapter protocol version 1 on stdin and stdout. It uses `adapters/node-kit` for the protocol and for the node-postgres statement trace.

The pool is the primary configuration. `drizzle(connectionString)` constructs a `pg.Pool`, and the `drizzle()` default client type is `Pool`. A direct `pg.Client` is a documented alternative. It is not this adapter. The follow-up script compares the two for `query_timeout`.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, `TX-01A.caught-error-then-commit`, `TX-01B.conn-lost-before-commit`, `TX-01B.commit-reply-discarded`, `TX-02.savepoint-rollback-not-sent`, `TX-02.savepoint-rollback-rejected`, `TX-02.conn-lost-before-savepoint-rollback`, `TX-03.rollback-not-sent`, `TX-03.statement-error-rollback-not-sent`, `TX-03.conn-lost-in-transaction`, `TX-04.nested-failure-contained`, `TX-04.nested-released-outer-rollback`, and `TX-05.managed-serializable`. All of them run in the native mode. The configured mode `client-error-listener` runs the three category B cases, `TX-01B.conn-lost-before-commit`, `TX-02.conn-lost-before-savepoint-rollback`, and `TX-03.conn-lost-in-transaction`, and the four MG-02 cases with an `'error'` listener on every pooled client. Writes are `insert()` and are sent when the call is awaited. Nested work is `tx.transaction()`. `TX-05` passes `{ isolationLevel: 'serializable' }` to `db.transaction()`.

`TX-04.independent-inner` is UNSUPPORTED, not applicable by design. `tx.transaction()` is a savepoint on the same transaction. Drizzle has no propagation mode that promises an independent transaction, and `insert()` does not defer writes. `TX-05.explicit-serializable` is UNSUPPORTED, capability absent. The documented transaction API is the callback. There is no handle with a separate commit call. MG-02 runs `migrate()` from `drizzle-orm/node-postgres/migrator`. There is no advisory lock. MG-03 is unsupported, capability absent: `migrate()` has no reversal.

Category C and D faults are injected in `pg.Client.prototype.query`, once, through `adapters/node-kit/pg-instrument.mjs`. Drizzle 0.45.4 and this adapter resolve the same `pg@8.23.1`. The native mode does not read `Result.command`, does not pass an error to `client.release()`, and does not add a rollback.

The pool has an `'error'` listener so an idle client's error does not kill the process. pg-pool forwards an idle client's error to the pool through a client listener of its own, and removes that client listener while the client is checked out. Drizzle adds none. In native mode the category B cases exit on the checked-out client's `'error'` event. `client-error-listener` adds `pool.on('connect', (client) => client.on('error', () => {}))`, so a terminated backend does not kill the process before `db.transaction()` can reject. That listener does not roll back or discard the connection. `migration.mjs` installs the same listener on the pool `migrate()` uses, in that mode only.

## Setup

`pnpm run setup` installs this directory from `pnpm-lock.yaml`.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=drizzle --repeat=3
```

The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-19T13-38-47Z-39ea07`](../../reports/examples/2026-10-19T13-38-47Z-39ea07/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) is the per-case report.

`investigations/drizzle-followups/probe.mjs` is not part of the suite. It checks `query_timeout`, `statement_timeout`, isolation options, and a backend termination. The category B cases in both modes are [`reports/examples/2026-10-23T13-55-28Z-620447`](../../reports/examples/2026-10-23T13-55-28Z-620447/summary.md). [`reports/examples/2026-10-23T13-11-06Z-d7cd89`](../../reports/examples/2026-10-23T13-11-06Z-d7cd89/summary.md) ran them with the listener installed in native mode, and is superseded. The 2026-10-19 transaction recording is unchanged. The MG-02 cases in both modes are [`reports/examples/2026-10-23T14-12-26Z-e1679c`](../../reports/examples/2026-10-23T14-12-26Z-e1679c/summary.md). [`reports/examples/2026-10-21T20-00-04Z-178fa4`](../../reports/examples/2026-10-21T20-00-04Z-178fa4/summary.md) ran them with the listener installed in native mode.
