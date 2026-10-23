# Npgsql control

A small application-owned transaction policy on Npgsql 10.0.3. No EF Core and no framework. The adapter speaks PPCS adapter protocol version 1 on stdin and stdout. Writes use parameterized commands against the runner's `item` and `uniq` tables.

`correct` is the positive control. `unsafe` is the negative control. `pooled` and `pooled-no-reset` are the correct policy on an `NpgsqlDataSource` with `MaxPoolSize` 1. The manifest kinds are `native` and `configured`, not `control`, so this adapter is not a second case-control gate and does not replace `pg-control`.

Versions and why they were chosen: [`../dotnet/VERSIONS.md`](../dotnet/VERSIONS.md).

## Setup

.NET SDK 10.0.402. `global.json` does not roll forward. From this directory:

```sh
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
dotnet build -c Release
dotnet test -c Release test/Ppcs.NpgsqlControl.Tests.csproj
chmod +x run
```

`pnpm run setup` does not build this adapter.

From the repository root, start the suite's disposable PostgreSQL if it is not already up:

```sh
pnpm run pg:up
```

## Run

From the repository root:

```sh
node harness/run.mjs --adapter=npgsql-control --case=CTL-01,TX-01,TX-02,TX-03,TX-04,TX-05,MG-02,MG-03 --repeat=3
```

`pg-control` runs beside the scenario cases. `TX-01B.commit-reply-discarded` is selected by the `TX-01` prefix and recorded as NOT_RUN. `TX-01B.commit-reply-unseen` is the runner's protocol proxy. `correct` reports `failed` when `CommitAsync` throws. `unsafe` reports `rolled_back`. The recording is `reports/examples/2026-10-23T12-49-21Z-094ceb`.

A probe, not a PPCS case, prints what `CommitAsync` does after a unique violation. It checks `cluster_name` against `.ppcs-instance.json`, creates `ppcs_npgsql_probe`, and drops that database:

```sh
dotnet exec bin/Release/net10.0/Ppcs.NpgsqlControl.dll probe ../../.ppcs-instance.json
```

## What the public API does not show

`CommitAsync` returns after Npgsql has read `CommandComplete` and `ReadyForQuery`. It does not expose the command tag. There is no public transaction-status property on `NpgsqlConnection` or `NpgsqlTransaction`. The correct policy runs `SELECT 1` before `CommitAsync`. SQLSTATE `25P02` means the session is in a failed transaction block. A return from `CommitAsync` after that probe is reported as `rolled_back`. The basis says the tag was not read. A return after a queryable probe is reported as `committed`. A throw is reported as `failed`, and the connection is disposed.

The unsafe policy reports `committed` whenever `CommitAsync` returns.

Per-case results are in [`FINDINGS.md`](FINDINGS.md).
