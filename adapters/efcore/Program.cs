using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args is ["probe", var instancePath])
        {
            return await SavepointProbe.Run(instancePath);
        }

        var protocol = new Protocol();
        EfHost? host = null;
        var helloSent = false;
        string? mode = null;
        var result = new Dictionary<string, object?> { ["type"] = "result" };
        try
        {
            var message = protocol.Read();
            if (!message.TryGetProperty("type", out var type) || type.GetString() != "case")
            {
                throw new ProtocolException("expected a case message");
            }

            mode = CaseJson.Text(message, "mode");
            if (mode is not ("native" or "execute-sql" or "pooled"))
            {
                throw new InvalidOperationException("unknown mode \"" + mode + "\"");
            }

            host = Open(protocol, message, mode);
            protocol.Send(Hello(mode));
            helloSent = true;
            var outcome = await EfCases.Dispatch(host, message);
            protocol.Checkpoint("after-end", null, null);
            result["status"] = "completed";
            foreach (var pair in outcome)
            {
                result[pair.Key] = pair.Value;
            }

            result["diagnostics"] = host.Diagnostics();
        }
        catch (Exception ex)
        {
            if (!helloSent)
            {
                protocol.Send(FallbackHello(mode));
            }

            result["status"] = "error";
            var error = Errors.Info(ex);
            error["protocol"] = ex is ProtocolException;
            result["error"] = error;
            if (host is not null)
            {
                result["diagnostics"] = host.Diagnostics();
            }
        }
        finally
        {
            host?.Dispose();
        }

        protocol.Send(result);
        return 0;
    }

    private static EfHost Open(Protocol protocol, JsonElement message, string mode)
    {
        var connection = CaseJson.Object(message, "connection");
        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = CaseJson.Text(connection, "host"),
            Port = CaseJson.Int(connection, "port"),
            Username = CaseJson.Text(connection, "user"),
            Password = CaseJson.Text(connection, "password"),
            Database = CaseJson.Text(connection, "database"),
            ApplicationName = CaseJson.Text(connection, "application_name"),
            Pooling = false,
        };
        return new EfHost(builder.ConnectionString, pooled: mode == "pooled", protocol, executeSqlViolation: mode == "execute-sql");
    }

    private static Dictionary<string, object?> Hello(string mode)
    {
        var ef = EfHost.AssemblyVersion(typeof(DbContext));
        var provider = EfHost.AssemblyVersion(typeof(Npgsql.EntityFrameworkCore.PostgreSQL.Infrastructure.NpgsqlDbContextOptionsBuilder));
        var driver = EfHost.AssemblyVersion(typeof(NpgsqlConnection));
        return new Dictionary<string, object?>
        {
            ["type"] = "hello",
            ["adapter"] = new Dictionary<string, object?> { ["name"] = "efcore", ["version"] = "0.1.0" },
            ["framework"] = new Dictionary<string, object?> { ["name"] = "Microsoft.EntityFrameworkCore", ["version"] = ef },
            ["driver"] = new Dictionary<string, object?> { ["name"] = "Npgsql", ["version"] = driver },
            ["components"] = new Dictionary<string, object?>
            {
                ["Microsoft.EntityFrameworkCore"] = ef,
                ["Npgsql.EntityFrameworkCore.PostgreSQL"] = provider,
                ["Npgsql"] = driver,
                ["runtime"] = Environment.Version.ToString(),
            },
            ["runtime"] = new Dictionary<string, object?> { ["name"] = "dotnet", ["version"] = Environment.Version.ToString() },
            ["mode"] = mode,
            ["configuration"] = new Dictionary<string, object?>
            {
                ["transactions"] = "Database.BeginTransactionAsync, IDbContextTransaction.CommitAsync and RollbackAsync",
                ["writes"] = mode == "execute-sql"
                    ? "Database.ExecuteSqlAsync for the marker and for the unique violation"
                    : "Database.ExecuteSqlAsync for markers; SaveChangesAsync for the native TX-01A unique violation",
                ["savepoints"] = "CreateSavepointAsync, RollbackToSavepointAsync, ReleaseSavepointAsync; SaveChangesAsync may create its own savepoint",
                ["execution_strategy"] = "the provider default; EnableRetryOnFailure is not called",
                ["connections"] = mode == "pooled"
                    ? "NpgsqlDataSource MaxPoolSize 1"
                    : "Pooling=false",
                ["migrations"] = "Database.MigrateAsync, history table ef_migrations_history",
            },
        };
    }

    private static Dictionary<string, object?> FallbackHello(string? mode)
        => new()
        {
            ["type"] = "hello",
            ["adapter"] = new Dictionary<string, object?> { ["name"] = "efcore", ["version"] = "0.1.0" },
            ["framework"] = new Dictionary<string, object?> { ["name"] = "Microsoft.EntityFrameworkCore", ["version"] = "10.0.13" },
            ["driver"] = new Dictionary<string, object?> { ["name"] = "Npgsql", ["version"] = "10.0.3" },
            ["components"] = new Dictionary<string, object?>(),
            ["runtime"] = new Dictionary<string, object?> { ["name"] = "dotnet", ["version"] = Environment.Version.ToString() },
            ["mode"] = mode ?? "unknown",
            ["configuration"] = new Dictionary<string, object?>(),
        };
}
