# Prisma adapter

Prisma Client 7.10.1 with the client query compiler and `@prisma/adapter-pg` 7.10.1 against the suite's disposable PostgreSQL, through a `pg.Pool` and `prisma.$transaction()`. The adapter speaks PPCS adapter protocol version 1. It uses `adapters/node-kit` for the protocol and for the node-postgres statement trace.

The stable release is 7.10.1. On 21 October 2026 the `prisma` CLI `latest` tag was `8.0.0-rc.24`. `@prisma/client` and `@prisma/adapter-pg` `latest` were `7.10.1`, and the CLI `prev` tag was `7.10.1`. This adapter pins the CLI to 7.10.1 so generate matches the client. It does not use the Rust query engine. `schema.prisma` sets `compilerBuild = "fast"`. `prisma --version` reports `Query Compiler: enabled`. The CLI's schema engine is the binary shipped in `@prisma/engines` 7.10.1 (`schema-engine`, engines hash `d1b3f377ca835d73fd50954a5e22128b9ebdd6b8`). The client does not use that binary to run queries.

`PrismaPg` is constructed with a `pg.Pool`. That overload is in `@prisma/adapter-pg` `dist/index.d.ts` (`pg.Pool | pg.PoolConfig | string`). The pool `max` is the case's `pool_max`. Passing a config object instead would use the adapter's default `max` of 10. `disposeExternalPool` is left false. After the case, the adapter calls `prisma.$disconnect()` and then `pool.end()`. Interactive transactions keep Prisma's defaults: `timeout` 5000 ms and `maxWait` 2000 ms. This run did not hit either.

Writes are `tx.$executeRaw`. Identity and the TX-05 read are `tx.$queryRaw`. Nested work is `tx.$transaction()`. `TX-05` passes `{ isolationLevel: Prisma.TransactionIsolationLevel.Serializable }`. The driver adapter then sends `BEGIN` and `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE`.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, `TX-01A.caught-error-then-commit`, `TX-01B.conn-lost-before-commit`, `TX-01B.commit-reply-discarded`, `TX-02.savepoint-rollback-not-sent`, `TX-02.savepoint-rollback-rejected`, `TX-02.conn-lost-before-savepoint-rollback`, `TX-03.rollback-not-sent`, `TX-03.statement-error-rollback-not-sent`, `TX-03.conn-lost-in-transaction`, `TX-04.nested-failure-contained`, `TX-04.nested-released-outer-rollback`, and `TX-05.managed-serializable`.

`TX-04.independent-inner` is UNSUPPORTED, not applicable by design. A nested `tx.$transaction()` is a savepoint on the same transaction. Prisma has no propagation mode that promises an independent transaction, and `$executeRaw` does not defer writes. `TX-05.explicit-serializable` is UNSUPPORTED, capability absent. Neither `$transaction(callback)` nor `$transaction([queries])` returns a handle with a separate commit call. MG-02 and MG-03 are not implemented. Prisma Migrate exists. This adapter does not drive it.

Category C and D faults are injected in `pg.Client.prototype.query`, once, through `adapters/node-kit/pg-instrument.mjs`. `@prisma/adapter-pg` 7.10.1 and this adapter resolve the same `pg@8.23.1`. The native mode does not read `Result.command`, does not pass an error to `client.release()`, and does not add a rollback.

`@prisma/adapter-pg` listens for `'error'` on a checked-out client for the life of the transaction, and on the pool for idle clients. The category B cases returned. They did not exit on an unhandled `'error'` event.

pnpm 12 reads `allowBuilds` from `pnpm-workspace.yaml`. `@prisma/engines` and `prisma` are set to `false`, so their install scripts do not run. `scripts/setup.sh` installs this directory without `--ignore-workspace`, because that flag drops `pnpm-workspace.yaml`. It then runs `prisma generate`. The generated client is `generated/prisma` and is not committed. Node.js 24 imports it with type stripping (`process.features.typescript === "strip"`).

## Setup

`pnpm run setup` installs this directory from `pnpm-lock.yaml` and generates the client.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=prisma --repeat=3
```

The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-21T14-10-47Z-148b69`](../../reports/examples/2026-10-21T14-10-47Z-148b69/summary.md) is the recording. [`FINDINGS.md`](FINDINGS.md) is the per-case report.

`prisma.config.ts` holds a placeholder URL used only by `prisma generate`. The adapter connects with the connection in the case message.
