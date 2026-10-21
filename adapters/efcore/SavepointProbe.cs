using System.Reflection;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

/// <summary>
/// Not a PPCS case. A failed SaveChangesAsync inside a transaction, then another SaveChangesAsync.
/// Refuses a server whose cluster_name is not the instance token.
/// </summary>
static class SavepointProbe
{
    public static async Task<int> Run(string instancePath)
    {
        using var document = JsonDocument.Parse(await File.ReadAllTextAsync(instancePath));
        var instance = document.RootElement;
        var host = CaseJson.Text(instance, "host");
        var port = CaseJson.Int(instance, "port");
        var user = CaseJson.Text(instance, "user");
        var password = CaseJson.Text(instance, "password");
        var token = CaseJson.Text(instance, "token");
        var adminCs = Cs(host, port, user, password, "postgres");
        await using (var admin = new NpgsqlConnection(adminCs))
        {
            await admin.OpenAsync();
            var cluster = await Scalar(admin, "select current_setting('cluster_name')");
            if (cluster != token)
            {
                Console.Error.WriteLine("cluster_name does not match the instance token; refusing to continue");
                return 2;
            }

            await Execute(admin, "drop database if exists ppcs_efcore_probe with (force)");
            await Execute(admin, "create database ppcs_efcore_probe");
        }

        var probeCs = Cs(host, port, user, password, "ppcs_efcore_probe");
        try
        {
            await using (var setup = new NpgsqlConnection(probeCs))
            {
                await setup.OpenAsync();
                await Execute(setup, "create table item (id serial primary key, name text not null, qty int not null default 0)");
                await Execute(setup, "create table uniq (id serial primary key, code text not null unique)");
                await Execute(setup, "insert into uniq (code) values ('taken')");
            }

            PrintApiSurface();
            await SaveChangesPath(probeCs);
            await ExecuteSqlPath(probeCs);
        }
        finally
        {
            await using var admin = new NpgsqlConnection(adminCs);
            await admin.OpenAsync();
            await Execute(admin, "drop database if exists ppcs_efcore_probe with (force)");
        }

        return 0;
    }

    private static void PrintApiSurface()
    {
        var names = typeof(Npgsql.EntityFrameworkCore.PostgreSQL.Infrastructure.NpgsqlDbContextOptionsBuilder)
            .GetMethods(BindingFlags.Instance | BindingFlags.Public)
            .Select(method => method.Name)
            .Where(name => name.Contains("Savepoint", StringComparison.OrdinalIgnoreCase) || name.Contains("Transaction", StringComparison.OrdinalIgnoreCase))
            .Distinct()
            .Order()
            .ToList();
        Console.WriteLine("efcore=" + EfHost.AssemblyVersion(typeof(DbContext)));
        Console.WriteLine("provider=" + EfHost.AssemblyVersion(typeof(Npgsql.EntityFrameworkCore.PostgreSQL.Infrastructure.NpgsqlDbContextOptionsBuilder)));
        Console.WriteLine("npgsql=" + EfHost.AssemblyVersion(typeof(NpgsqlConnection)));
        Console.WriteLine("runtime=" + Environment.Version);
        Console.WriteLine("provider_option_methods=" + (names.Count == 0 ? "none" : string.Join(",", names)));
    }

    private static async Task SaveChangesPath(string connectionString)
    {
        var sql = new List<string>();
        var counts = new SavepointCounts();
        await using var context = Context(connectionString, sql, counts);
        await using var tx = await context.Database.BeginTransactionAsync();
        Console.WriteLine("savechanges_supports_savepoints=" + tx.SupportsSavepoints);
        context.Items.Add(new Item { Name = "kept" });
        await context.SaveChangesAsync();
        string? violation = null;
        try
        {
            context.Uniqs.Add(new Uniq { Code = "taken" });
            await context.SaveChangesAsync();
        }
        catch (Exception ex)
        {
            violation = Errors.SqlState(ex) ?? ex.GetType().Name;
        }

        var failed = context.ChangeTracker.Entries<Uniq>().Select(entry => entry.State.ToString()).ToList();
        var kept = context.ChangeTracker.Entries<Item>().Single().State.ToString();
        string queryable;
        try
        {
            _ = await context.Items.AsNoTracking().CountAsync();
            queryable = "yes";
        }
        catch (Exception ex)
        {
            queryable = Errors.SqlState(ex) ?? ex.GetType().Name;
        }

        context.Items.Add(new Item { Name = "after" });
        string second;
        try
        {
            await context.SaveChangesAsync();
            second = "returned";
        }
        catch (Exception ex)
        {
            second = Errors.SqlState(ex) ?? ex.GetType().Name;
        }

        string commit;
        try
        {
            await tx.CommitAsync();
            commit = "returned";
        }
        catch (Exception ex)
        {
            commit = "threw " + (Errors.SqlState(ex) ?? ex.GetType().Name);
        }

        await using var observer = new NpgsqlConnection(connectionString);
        await observer.OpenAsync();
        Console.WriteLine("savechanges_violation=" + (violation ?? "none"));
        Console.WriteLine("savechanges_failed_entity_states=" + string.Join(",", failed));
        Console.WriteLine("savechanges_kept_entity_state=" + kept);
        Console.WriteLine("savechanges_queryable_after_failure=" + queryable);
        Console.WriteLine("savechanges_second=" + second);
        Console.WriteLine("savechanges_commit=" + commit);
        Console.WriteLine("savechanges_visible_kept=" + await Scalar(observer, "select count(*)::text from item where name = 'kept'"));
        Console.WriteLine("savechanges_visible_after=" + await Scalar(observer, "select count(*)::text from item where name = 'after'"));
        Console.WriteLine("savechanges_sql_has_savepoint=" + sql.Any(line => line.Contains("SAVEPOINT", StringComparison.OrdinalIgnoreCase)));
        Console.WriteLine("savechanges_created_savepoint_callbacks=" + counts.Created);
        Console.WriteLine("savechanges_rolled_back_to_savepoint_callbacks=" + counts.RolledBack);
        foreach (var line in sql.Where(line => line.Contains("SAVEPOINT", StringComparison.OrdinalIgnoreCase) || line.Contains("ROLLBACK TO", StringComparison.OrdinalIgnoreCase) || line.Contains("COMMIT", StringComparison.OrdinalIgnoreCase)))
        {
            Console.WriteLine("savechanges_sql=" + OneLine(line));
        }
    }

    private static async Task ExecuteSqlPath(string connectionString)
    {
        var sql = new List<string>();
        var counts = new SavepointCounts();
        await using var context = Context(connectionString, sql, counts);
        await using var tx = await context.Database.BeginTransactionAsync();
        context.Items.Add(new Item { Name = "sql-kept" });
        await context.SaveChangesAsync();
        string? violation = null;
        try
        {
            await context.Database.ExecuteSqlAsync($"insert into uniq (code) values ({"taken"})");
        }
        catch (Exception ex)
        {
            violation = Errors.SqlState(ex) ?? ex.GetType().Name;
        }

        string queryable;
        try
        {
            _ = await context.Items.AsNoTracking().CountAsync();
            queryable = "yes";
        }
        catch (Exception ex)
        {
            queryable = Errors.SqlState(ex) ?? ex.GetType().Name;
        }

        string commit;
        try
        {
            await tx.CommitAsync();
            commit = "returned";
        }
        catch (Exception ex)
        {
            commit = "threw " + (Errors.SqlState(ex) ?? ex.GetType().Name);
        }

        await using var observer = new NpgsqlConnection(connectionString);
        await observer.OpenAsync();
        Console.WriteLine("executesql_violation=" + (violation ?? "none"));
        Console.WriteLine("executesql_queryable_after_failure=" + queryable);
        Console.WriteLine("executesql_commit=" + commit);
        Console.WriteLine("executesql_visible_kept=" + await Scalar(observer, "select count(*)::text from item where name = 'sql-kept'"));
        Console.WriteLine("executesql_sql_has_savepoint=" + sql.Any(line => line.Contains("SAVEPOINT", StringComparison.OrdinalIgnoreCase)));
        Console.WriteLine("executesql_created_savepoint_callbacks=" + counts.Created);
        Console.WriteLine("executesql_rolled_back_to_savepoint_callbacks=" + counts.RolledBack);
    }

    private static AppDbContext Context(string connectionString, List<string> sql, SavepointCounts counts)
    {
        var options = new DbContextOptionsBuilder<AppDbContext>();
        options.UseNpgsql(connectionString);
        options.AddInterceptors(counts);
        options.LogTo(line => sql.Add(line), [DbLoggerCategory.Database.Command.Name], Microsoft.Extensions.Logging.LogLevel.Information);
        return new AppDbContext(options.Options);
    }

    private sealed class SavepointCounts : DbTransactionInterceptor
    {
        public int Created { get; private set; }
        public int RolledBack { get; private set; }

        public override void CreatedSavepoint(System.Data.Common.DbTransaction transaction, TransactionEventData eventData)
            => Created++;

        public override Task CreatedSavepointAsync(System.Data.Common.DbTransaction transaction, TransactionEventData eventData, CancellationToken cancellationToken = default)
        {
            Created++;
            return Task.CompletedTask;
        }

        public override void RolledBackToSavepoint(System.Data.Common.DbTransaction transaction, TransactionEventData eventData)
            => RolledBack++;

        public override Task RolledBackToSavepointAsync(System.Data.Common.DbTransaction transaction, TransactionEventData eventData, CancellationToken cancellationToken = default)
        {
            RolledBack++;
            return Task.CompletedTask;
        }
    }

    private static string Cs(string host, int port, string user, string password, string database)
        => new NpgsqlConnectionStringBuilder
        {
            Host = host,
            Port = port,
            Username = user,
            Password = password,
            Database = database,
            ApplicationName = "ppcs-efcore-probe",
            Pooling = false,
        }.ConnectionString;

    private static async Task Execute(NpgsqlConnection connection, string sql)
    {
        await using var command = new NpgsqlCommand(sql, connection);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<string> Scalar(NpgsqlConnection connection, string sql)
    {
        await using var command = new NpgsqlCommand(sql, connection);
        var value = await command.ExecuteScalarAsync();
        return value?.ToString() ?? "null";
    }

    private static string OneLine(string line) => line.Replace('\n', ' ').Replace('\r', ' ').Trim();
}
