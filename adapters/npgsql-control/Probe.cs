using System.Reflection;
using System.Text.Json;
using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

/// <summary>
/// One-off observations against the disposable PostgreSQL. Not an adapter case.
/// Refuses a server whose cluster_name is not the instance file's token.
/// </summary>
static class Probe
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
        var admin = Admin(host, port, user, password, "postgres");
        await using (admin)
        {
            await admin.OpenAsync();
            var cluster = await Scalar(admin, "select current_setting('cluster_name')");
            if (cluster != token)
            {
                Console.Error.WriteLine("cluster_name does not match the instance token; refusing to continue");
                return 2;
            }

            await Execute(admin, "drop database if exists ppcs_npgsql_probe with (force)");
            await Execute(admin, "create database ppcs_npgsql_probe");
        }

        var probe = Admin(host, port, user, password, "ppcs_npgsql_probe");
        try
        {
            await using (probe)
            {
                await probe.OpenAsync();
                await Execute(probe, "create table item (id serial primary key, name text not null, qty int not null default 0)");
                await Execute(probe, "create table uniq (id serial primary key, code text not null unique)");
                await Execute(probe, "insert into uniq (code) values ('taken')");
            }

            PrintPublicApi();
            await AbortedCommit(host, port, user, password);
            await CleanCommit(host, port, user, password);
            await DirectCommitStatement(host, port, user, password);
        }
        finally
        {
            var cleanup = Admin(host, port, user, password, "postgres");
            await using (cleanup)
            {
                await cleanup.OpenAsync();
                await Execute(cleanup, "drop database if exists ppcs_npgsql_probe with (force)");
            }
        }

        return 0;
    }

    private static void PrintPublicApi()
    {
        var connectionProperty = typeof(NpgsqlConnection).GetProperty("TransactionStatus", BindingFlags.Instance | BindingFlags.Public);
        var transactionProperty = typeof(NpgsqlTransaction).GetProperty("TransactionStatus", BindingFlags.Instance | BindingFlags.Public);
        Console.WriteLine("npgsql=" + Cases.AssemblyVersion(typeof(NpgsqlConnection)));
        Console.WriteLine("runtime=" + Environment.Version);
        Console.WriteLine("public_connection_transaction_status=" + (connectionProperty is null ? "absent" : "present"));
        Console.WriteLine("public_transaction_transaction_status=" + (transactionProperty is null ? "absent" : "present"));
    }

    private static async Task AbortedCommit(string host, int port, string user, string password)
    {
        var worker = Admin(host, port, user, password, "ppcs_npgsql_probe");
        var observer = Admin(host, port, user, password, "ppcs_npgsql_probe");
        await using (worker)
        await using (observer)
        {
            await worker.OpenAsync();
            await observer.OpenAsync();
            await using var tx = await worker.BeginTransactionAsync();
            await Execute(worker, "insert into item (name) values ('marker')", tx);
            var xid = await Scalar(worker, "select pg_current_xact_id()::text", tx);
            string? violation = null;
            try
            {
                await Execute(worker, "insert into uniq (code) values ('taken')", tx);
            }
            catch (PostgresException ex)
            {
                violation = ex.SqlState;
            }

            string probe;
            try
            {
                await Scalar(worker, "select 1", tx);
                probe = "queryable";
            }
            catch (PostgresException ex)
            {
                probe = ex.SqlState ?? "error";
            }

            string commit;
            try
            {
                await tx.CommitAsync();
                commit = "returned";
            }
            catch (Exception ex)
            {
                commit = "threw " + ex.GetType().Name + " " + (Errors.SqlState(ex) ?? "");
            }

            var fate = await Scalar(observer, "select pg_xact_status($1::xid8)", null, xid);
            var visible = await Scalar(observer, "select count(*)::text from item where name = 'marker'");
            Console.WriteLine("aborted_violation=" + (violation ?? "none"));
            Console.WriteLine("aborted_probe=" + probe);
            Console.WriteLine("aborted_commit=" + commit);
            Console.WriteLine("aborted_fate=" + fate);
            Console.WriteLine("aborted_marker_visible=" + visible);
        }
    }

    private static async Task CleanCommit(string host, int port, string user, string password)
    {
        var worker = Admin(host, port, user, password, "ppcs_npgsql_probe");
        var observer = Admin(host, port, user, password, "ppcs_npgsql_probe");
        await using (worker)
        await using (observer)
        {
            await worker.OpenAsync();
            await observer.OpenAsync();
            await using var tx = await worker.BeginTransactionAsync();
            await Execute(worker, "insert into item (name) values ('clean')", tx);
            var xid = await Scalar(worker, "select pg_current_xact_id()::text", tx);
            await Scalar(worker, "select 1", tx);
            string commit;
            try
            {
                await tx.CommitAsync();
                commit = "returned";
            }
            catch (Exception ex)
            {
                commit = "threw " + ex.GetType().Name;
            }

            var fate = await Scalar(observer, "select pg_xact_status($1::xid8)", null, xid);
            Console.WriteLine("clean_commit=" + commit);
            Console.WriteLine("clean_fate=" + fate);
        }
    }

    private static async Task DirectCommitStatement(string host, int port, string user, string password)
    {
        var worker = Admin(host, port, user, password, "ppcs_npgsql_probe");
        await using (worker)
        {
            await worker.OpenAsync();
            await using var tx = await worker.BeginTransactionAsync();
            await Execute(worker, "insert into item (name) values ('statement')", tx);
            try
            {
                await Execute(worker, "insert into uniq (code) values ('taken')", tx);
            }
            catch (PostgresException)
            {
                // The transaction is aborted. The next statement is COMMIT as a command, not CommitAsync.
            }

            await using var commit = new NpgsqlCommand("COMMIT", worker, tx);
            try
            {
                var count = await commit.ExecuteNonQueryAsync();
                Console.WriteLine("statement_commit=returned");
                Console.WriteLine("statement_commit_records=" + count);
            }
            catch (Exception ex)
            {
                Console.WriteLine("statement_commit=threw " + ex.GetType().Name + " " + (Errors.SqlState(ex) ?? ""));
            }
        }
    }

    private static NpgsqlConnection Admin(string host, int port, string user, string password, string database)
        => new(new NpgsqlConnectionStringBuilder
        {
            Host = host,
            Port = port,
            Username = user,
            Password = password,
            Database = database,
            ApplicationName = "ppcs-npgsql-probe",
            Pooling = false,
        }.ConnectionString);

    private static async Task Execute(NpgsqlConnection connection, string sql, NpgsqlTransaction? tx = null)
    {
        await using var command = new NpgsqlCommand(sql, connection, tx);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<string> Scalar(NpgsqlConnection connection, string sql, NpgsqlTransaction? tx = null, string? arg = null)
    {
        await using var command = new NpgsqlCommand(sql, connection, tx);
        if (arg is not null)
        {
            command.Parameters.AddWithValue(arg);
        }

        var value = await command.ExecuteScalarAsync();
        return value?.ToString() ?? "null";
    }
}
