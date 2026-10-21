# .NET adapter versions

Pinned on 2026-10-21. These are the packages the adapters build against. The process also records the assembly versions it actually loaded, in the `hello` message (`framework`, `driver`, `components`, `runtime`).

## Runtime and SDK

| Piece | Version | Why this one |
| --- | --- | --- |
| .NET SDK | 10.0.402 | Current SDK for the .NET 10 LTS line. Microsoft's download page lists it as the latest 10.0 SDK on 2026-10-13, including runtime 10.0.13. `global.json` sets `rollForward` to `disable` so a newer SDK is not substituted silently. |
| .NET runtime | 10.0.13 | The runtime inside SDK 10.0.402. .NET 10 is LTS, in active support until 2028-11-14 ([support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), updated 2026-10-13). .NET 8 and .NET 9 reach end of support on 2026-11-10. .NET 11 was a release candidate on that date, not the stable LTS line. |

The install used Microsoft's `dotnet-install.sh` at `--version 10.0.402`. A machine-wide SDK is not required. `adapters/*/run` uses `$DOTNET_ROOT` or `$HOME/.dotnet` when `dotnet` is not already on `PATH`.

## Libraries

| Package | Version | Why this one |
| --- | --- | --- |
| Npgsql | 10.0.3 | Latest stable ADO.NET driver on nuget.org on 2026-10-21. No 10.0.4 or later stable package was published. The 10.0 line is the driver EF Core 10's provider depends on. |
| Npgsql.EntityFrameworkCore.PostgreSQL | 10.0.3 | Latest stable provider. Its nuspec targets `net10.0` and depends on `Npgsql` 10.0.3 and on `Microsoft.EntityFrameworkCore` `[10.0.4, 11.0.0)`. Version 11.0.0-rc.2 exists and was not used. |
| Microsoft.EntityFrameworkCore | 10.0.13 | Latest 10.0 patch, the same patch level as the runtime. It is inside the provider's declared range. The provider was not assumed compatible merely because both packages are major version 10: the nuspec range was read. |
| Microsoft.EntityFrameworkCore.Relational | 10.0.13 | Same patch as `Microsoft.EntityFrameworkCore`. The provider depends on it in the same range. |

PostgreSQL stays 18.6, the image already pinned in `compose.yaml`. Npgsql EF Core 10.0 release notes document PostgreSQL 18 virtual generated columns and `uuidv7()` when `SetPostgresVersion(18, 0)` is set. These adapters do not need those features. They do not set a PostgreSQL compatibility version, so the provider uses its default SQL for the statements these cases send (`INSERT`, `SAVEPOINT`, `COMMIT`).

## What the public Npgsql API does not expose

Read from the Npgsql 10.0.3 sources (`NpgsqlTransaction.Commit` and `NpgsqlConnector.ExecuteInternalCommand`):

- `CommitAsync` sends the pregenerated simple-query message `COMMIT`.
- It then requires one `CommandComplete` message and one `ReadyForQuery` message.
- It does not read the command tag on `CommandComplete`.
- `ReadyForQuery` updates an internal connector field, `TransactionStatus`. That field is not a public property of `NpgsqlConnection` or `NpgsqlTransaction`.
- After either a committed transaction or a `COMMIT` that PostgreSQL answers with `ROLLBACK`, the driver is idle. `CommitAsync` returns in both cases when the server sends those two messages.

The correct control does not pretend otherwise. Before `CommitAsync` it runs `SELECT 1`. SQLSTATE `25P02` is public evidence that the session is in a failed transaction block. The policy's basis says when it did not see a command tag. The probe program prints what `CommitAsync` actually did on this server; the findings quote that run rather than this source note.

## Build

From the repository root, with SDK 10.0.402:

```sh
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
dotnet build -c Release adapters/npgsql-control/Ppcs.NpgsqlControl.csproj
dotnet build -c Release adapters/efcore/Ppcs.EfCore.csproj
dotnet test -c Release adapters/npgsql-control/test/Ppcs.NpgsqlControl.Tests.csproj
dotnet test -c Release adapters/efcore/test/Ppcs.EfCore.Tests.csproj
```

`packages.lock.json` is committed. The projects set `RestorePackagesWithLockFile` so a restore uses that lock file.
