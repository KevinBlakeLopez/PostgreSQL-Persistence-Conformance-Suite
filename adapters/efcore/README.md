# Entity Framework Core adapter

EF Core 10.0.13 on the Npgsql EF Core provider 10.0.3 and Npgsql 10.0.3. The adapter speaks PPCS adapter protocol version 1. It uses `DbContext`, `Database.BeginTransactionAsync`, `CommitAsync`, `RollbackAsync`, and `CreateSavepointAsync`. It does not use Spring, a second ORM, or a hand-written transaction manager.

Versions and why they were chosen: [`../dotnet/VERSIONS.md`](../dotnet/VERSIONS.md).

## Setup

.NET SDK 10.0.402. From this directory:

```sh
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
dotnet build -c Release
dotnet test -c Release test/Ppcs.EfCore.Tests.csproj
chmod +x run
```

`pnpm run setup` does not build this adapter. From the repository root:

```sh
pnpm run pg:up
node harness/run.mjs --adapter=efcore --case=CTL-01,TX-01,TX-02,TX-03,TX-04,TX-05,MG-02,MG-03 --repeat=3
```

`pg-control` runs beside the scenario cases.

## Modes

| Mode | What it changes |
| --- | --- |
| `native` | `Pooling=false`. Marker inserts use `Database.ExecuteSqlAsync`. The TX-01A violation is `SaveChangesAsync` of a `Uniq` entity. |
| `execute-sql` | The same transaction calls. The TX-01A violation is `Database.ExecuteSqlAsync` instead of `SaveChangesAsync`. |
| `pooled` | `NpgsqlDataSource` with `MaxPoolSize` 1, TX-03 only. The context is disposed between units. |

`TX-05.managed-serializable` is unsupported: EF Core has no callback transaction API that accepts an isolation level. `TX-04.independent-inner` is unsupported: `BeginTransactionAsync` does not start an independent transaction while one is open. `TX-01B.commit-reply-discarded` is NOT_RUN. `CommitAsync` consumes the reply inside Npgsql before it returns, and this adapter does not discard that reply.

Marker inserts are `ExecuteSqlAsync` because `SaveChangesAsync` inside a user transaction writes the row under a savepoint. After that savepoint is released, the row's `xmin` is the subtransaction id, while `pg_current_xact_id()` is the top-level id. The harness does not attribute that `xmin` to a top-level write, so a `SaveChanges` marker makes the case INCONCLUSIVE before the commit is scored.

## Savepoint probe

Not a PPCS case. It checks `cluster_name`, creates `ppcs_efcore_probe`, and drops it:

```sh
dotnet exec bin/Release/net10.0/Ppcs.EfCore.dll probe ../../.ppcs-instance.json
```

Per-case results are in [`FINDINGS.md`](FINDINGS.md). The comparison with the other recorded adapters is in [`../dotnet/INVESTIGATION.md`](../dotnet/INVESTIGATION.md).
