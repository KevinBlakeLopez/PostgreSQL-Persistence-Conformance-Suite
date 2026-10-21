using System.Text.Json;
using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args is ["probe", var instancePath])
        {
            return await Probe.Run(instancePath);
        }

        var protocol = new Protocol();
        Sessions? sessions = null;
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
            var correct = mode is "correct" or "pooled" or "pooled-no-reset";
            if (!correct && mode != "unsafe")
            {
                throw new InvalidOperationException("unknown mode \"" + mode + "\"");
            }

            sessions = Open(message, mode);
            protocol.Send(Hello(mode));
            helloSent = true;
            var outcome = await Cases.Dispatch(sessions, protocol, message, mode != "unsafe");
            protocol.Checkpoint("after-end", null, null);
            result["status"] = "completed";
            foreach (var pair in outcome)
            {
                result[pair.Key] = pair.Value;
            }

            result["diagnostics"] = sessions.Diagnostics();
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
            if (sessions is not null)
            {
                result["diagnostics"] = sessions.Diagnostics();
            }
        }
        finally
        {
            sessions?.Dispose();
        }

        protocol.Send(result);
        return 0;
    }

    private static Sessions Open(JsonElement message, string mode)
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
        var options = CaseJson.OptionalText(connection, "options");
        if (!string.IsNullOrEmpty(options))
        {
            builder.Options = options;
        }

        var pooled = mode is "pooled" or "pooled-no-reset";
        return new Sessions(builder.ConnectionString, pooled, noResetOnClose: mode == "pooled-no-reset");
    }

    private static Dictionary<string, object?> Hello(string mode)
    {
        var driver = Cases.AssemblyVersion(typeof(NpgsqlConnection));
        var correct = mode != "unsafe";
        return new Dictionary<string, object?>
        {
            ["type"] = "hello",
            ["adapter"] = new Dictionary<string, object?> { ["name"] = "npgsql-control", ["version"] = "0.1.0" },
            ["framework"] = new Dictionary<string, object?> { ["name"] = "npgsql-control", ["version"] = "0.1.0" },
            ["driver"] = new Dictionary<string, object?> { ["name"] = "Npgsql", ["version"] = driver },
            ["components"] = new Dictionary<string, object?>
            {
                ["Npgsql"] = driver,
                ["runtime"] = Environment.Version.ToString(),
            },
            ["runtime"] = new Dictionary<string, object?> { ["name"] = "dotnet", ["version"] = Environment.Version.ToString() },
            ["mode"] = mode,
            ["configuration"] = Configuration(mode, correct),
        };
    }

    private static Dictionary<string, object?> Configuration(string mode, bool correct)
    {
        var configuration = new Dictionary<string, object?>
        {
            ["commit_outcome"] = correct
                ? "CommitAsync after SELECT 1; rolled_back when the probe failed with 25P02; the command tag is not read"
                : "committed whenever CommitAsync returns",
            ["commit_error"] = correct ? "reported as failed; connection disposed" : "reported as rolled_back",
            ["failed_savepoint_rollback"] = correct ? "outer RollbackAsync" : "ignored; CommitAsync",
            ["failed_rollback"] = correct ? "connection disposed; CommitAsync not called" : "CommitAsync; connection kept",
            ["isolation_level"] = correct ? "BeginTransactionAsync(IsolationLevel)" : "not passed",
            ["write_before_savepoint"] = correct ? "sent before SaveAsync" : "sent inside the savepoint",
            ["command_tag"] = "not exposed by NpgsqlTransaction.CommitAsync",
        };
        configuration["connections"] = mode switch
        {
            "pooled" => "NpgsqlDataSource MaxPoolSize 1, reset on close",
            "pooled-no-reset" => "NpgsqlDataSource MaxPoolSize 1, NoResetOnClose",
            _ => "one NpgsqlConnection, pooling off",
        };
        return configuration;
    }

    private static Dictionary<string, object?> FallbackHello(string? mode)
        => new()
        {
            ["type"] = "hello",
            ["adapter"] = new Dictionary<string, object?> { ["name"] = "npgsql-control", ["version"] = "0.1.0" },
            ["framework"] = new Dictionary<string, object?> { ["name"] = "npgsql-control", ["version"] = "0.1.0" },
            ["driver"] = new Dictionary<string, object?> { ["name"] = "Npgsql", ["version"] = "10.0.3" },
            ["components"] = new Dictionary<string, object?>(),
            ["runtime"] = new Dictionary<string, object?> { ["name"] = "dotnet", ["version"] = Environment.Version.ToString() },
            ["mode"] = mode ?? "unknown",
            ["configuration"] = new Dictionary<string, object?>(),
        };
}
