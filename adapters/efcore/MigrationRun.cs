using System.Data;
using System.Data.Common;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Logging;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

/// <summary>
/// Applies the case settings on every connection EF opens. Migrate may open its own connection.
/// Custom <c>ppcs.*</c> settings are not startup parameters, so they are set after open.
/// </summary>
sealed class MigrationSettings : DbConnectionInterceptor
{
    private readonly string _marker;
    private readonly string _gate;
    private readonly string _hold;
    private readonly string _reversal;

    public MigrationSettings(string marker, string gate, string hold, string reversal)
    {
        _marker = marker;
        _gate = gate;
        _hold = hold;
        _reversal = reversal;
    }

    public override void ConnectionOpened(DbConnection connection, ConnectionEndEventData eventData)
        => Apply(connection);

    public override Task ConnectionOpenedAsync(DbConnection connection, ConnectionEndEventData eventData, CancellationToken cancellationToken = default)
    {
        Apply(connection);
        return Task.CompletedTask;
    }

    private void Apply(DbConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "select set_config('ppcs.marker', @marker, false), set_config('ppcs.gate', @gate, false), set_config('ppcs.hold', @hold, false), set_config('ppcs.reversal', @reversal, false)";
        Add(command, "marker", _marker);
        Add(command, "gate", _gate);
        Add(command, "hold", _hold);
        Add(command, "reversal", _reversal);
        command.ExecuteNonQuery();
    }

    private static void Add(DbCommand command, string name, string value)
    {
        var parameter = command.CreateParameter();
        parameter.ParameterName = name;
        parameter.Value = value;
        command.Parameters.Add(parameter);
    }
}

static class MigrationRun
{
    private const string Contract =
        "EF Core 10 Database.MigrateAsync applies pending migrations compiled in this assembly, or moves to a target migration. "
        + "On PostgreSQL the relational provider runs each migration in a transaction when the provider reports transactional migrations. "
        + "This adapter does not take an advisory lock of its own before reading history. "
        + "The migration SQL inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock inside that migration. "
        + "History is the table ef_migrations_history. The adapter reports applied when EF logs Applying migration, and nothing_to_do when MigrateAsync returns without that log. "
        + "MigrateAsync(\"0\") runs the Down method. An exception whose message says the migration has no reversal is reported as refused. Any other exception is reported as failed.";

    public static async Task<Dictionary<string, object?>> Run(JsonElement message)
    {
        var connection = CaseJson.Object(message, "connection");
        var migration = CaseJson.Object(message, "migration");
        var markers = CaseJson.Object(message, "markers");
        var marker = markers.EnumerateObject().First().Value.GetString()
            ?? throw new ProtocolException("the migration case has no marker");
        var operation = CaseJson.Text(migration, "operation");
        var reversal = CaseJson.OptionalText(migration, "reversal") ?? "valid";
        var hold = CaseJson.Bool(migration, "hold");
        var gate = CaseJson.Int(migration, "gate");
        var options = CaseJson.OptionalText(connection, "options");
        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = CaseJson.Text(connection, "host"),
            Port = CaseJson.Int(connection, "port"),
            Username = CaseJson.Text(connection, "user"),
            Password = CaseJson.Text(connection, "password"),
            Database = CaseJson.Text(connection, "database"),
            ApplicationName = CaseJson.Text(connection, "application_name"),
            Pooling = false,
            Timeout = 15,
            CommandTimeout = 30,
        };
        if (!string.IsNullOrEmpty(options))
        {
            builder.Options = options;
        }

        NpgsqlConnection? spare = null;
        if (options?.Contains("idle_session_timeout", StringComparison.Ordinal) == true)
        {
            spare = new NpgsqlConnection(builder.ConnectionString);
            await spare.OpenAsync();
            await using var ping = new NpgsqlCommand("select 1", spare);
            await ping.ExecuteScalarAsync();
        }

        try
        {
            var appliedByThisProcess = false;
            var optionsBuilder = new DbContextOptionsBuilder<MigrationDbContext>();
            optionsBuilder.UseNpgsql(builder.ConnectionString, npgsql => npgsql.MigrationsHistoryTable("ef_migrations_history"));
            optionsBuilder.AddInterceptors(new MigrationSettings(marker, gate.ToString(), hold ? "true" : "false", reversal));
            optionsBuilder.LogTo(
                line =>
                {
                    if (line.Contains("Applying migration", StringComparison.Ordinal))
                    {
                        appliedByThisProcess = true;
                    }
                },
                [DbLoggerCategory.Migrations.Name],
                LogLevel.Information);
            await using var context = new MigrationDbContext(optionsBuilder.Options);
            var known = context.Database.GetMigrations().ToList();
            if (!known.Contains("1_m1"))
            {
                return Outcome("failed", 1, "Database.GetMigrationsAsync did not contain 1_m1", new InvalidOperationException("migration 1_m1 was not discovered"));
            }

            await context.Database.OpenConnectionAsync();
            await SetConfig(context, marker, gate.ToString(), hold ? "true" : "false", reversal);
            if (operation == "revert")
            {
                try
                {
                    await context.Database.MigrateAsync("0");
                    return Outcome("reverted", 0, "Database.MigrateAsync(\"0\") returned", null);
                }
                catch (Exception ex) when (ex is not ProtocolException)
                {
                    var refused = ex.ToString().Contains("no reversal", StringComparison.Ordinal);
                    return Outcome(
                        refused ? "refused" : "failed",
                        1,
                        refused
                            ? "Database.MigrateAsync(\"0\") threw because the migration SQL refused a reversal"
                            : "Database.MigrateAsync(\"0\") threw",
                        ex);
                }
            }

            await context.Database.MigrateAsync();
            if (appliedByThisProcess)
            {
                return Outcome("applied", 0, "Database.MigrateAsync returned and EF logged that it was applying the migration", null);
            }

            return Outcome("nothing_to_do", 0, "Database.MigrateAsync returned without logging that it applied a migration", null);
        }
        finally
        {
            if (spare is not null)
            {
                await spare.DisposeAsync();
            }
        }
    }

    private static async Task SetConfig(MigrationDbContext context, string marker, string gate, string hold, string reversal)
    {
        var connection = context.Database.GetDbConnection();
        await using var command = connection.CreateCommand();
        command.CommandText = "select set_config('ppcs.marker', @marker, false), set_config('ppcs.gate', @gate, false), set_config('ppcs.hold', @hold, false), set_config('ppcs.reversal', @reversal, false)";
        var markerParameter = command.CreateParameter();
        markerParameter.ParameterName = "marker";
        markerParameter.Value = marker;
        command.Parameters.Add(markerParameter);
        var gateParameter = command.CreateParameter();
        gateParameter.ParameterName = "gate";
        gateParameter.Value = gate;
        command.Parameters.Add(gateParameter);
        var holdParameter = command.CreateParameter();
        holdParameter.ParameterName = "hold";
        holdParameter.Value = hold;
        command.Parameters.Add(holdParameter);
        var reversalParameter = command.CreateParameter();
        reversalParameter.ParameterName = "reversal";
        reversalParameter.Value = reversal;
        command.Parameters.Add(reversalParameter);
        await command.ExecuteNonQueryAsync();
    }

    private static Dictionary<string, object?> Outcome(string reported, int exitCode, string basis, Exception? error)
    {
        var result = new Dictionary<string, object?>
        {
            ["reported"] = reported,
            ["exit_code"] = exitCode,
            ["basis"] = basis,
            ["contract"] = Contract,
            ["form"] = "Database.MigrateAsync on a Migration whose Up inserts the marker and optionally waits on the case gate. Down deletes the marker, refuses when ppcs.reversal is none, or raises after the delete when the reversal is partial-then-error.",
            ["steps"] = new Dictionary<string, object?>(),
        };
        if (error is not null)
        {
            result["api_error"] = Errors.Info(error);
        }

        return result;
    }
}
