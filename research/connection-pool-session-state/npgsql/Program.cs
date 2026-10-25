// Npgsql pool session-state probes.
//
// Npgsql documents that closing a pooled connection arranges for its state to be reset "the next time it's used":
// DISCARD ALL (or an equivalent sequence that keeps Npgsql's prepared statements) is written into the connector's
// buffer and sent with the first statement after the connection is reopened. These probes measure what that means
// on the server while the connector is idle in the pool, and what happens when the connection fails around close.
//
// Pool of one connector (Maximum Pool Size=1). Borrower A changes session state and closes. Borrower B opens next.
// Evidence: B's reads; an independent observer connection (superuser, Pooling=false) reading pg_locks, the catalogs
// and the tables; a competing connection for the advisory lock; physical identity from the driver-reported PID
// (BackendKeyData, no SQL) plus that backend's backend_start. The output has no PIDs or timestamps.
//
// Usage: dotnet run -c Release -- <instance-file> <scenario>

using System.Text.Json;
using Npgsql;

var inst = JsonDocument.Parse(File.ReadAllText(args[0])).RootElement;
var scenario = args[1];
var app = $"ssc-npgsql-{scenario}";
const long LockKey = 4712;

string Cs(bool super, string appName, bool pooling, string extra = "") =>
    $"Host={inst.GetProperty("host").GetString()};Port={inst.GetProperty("port").GetInt32()};" +
    $"Database={inst.GetProperty("database").GetString()};" +
    $"Username={inst.GetProperty(super ? "superuser" : "user").GetString()};" +
    $"Password={inst.GetProperty(super ? "superuser_password" : "password").GetString()};" +
    $"Application Name={appName};Pooling={pooling};{extra}";

void Out(string who, string step, object? observed) => Console.WriteLine($"{who,-9} {step,-84} {observed}");

async Task<object?> Scalar(NpgsqlConnection c, string sql)
{
    await using var cmd = new NpgsqlCommand(sql, c);
    return await cmd.ExecuteScalarAsync();
}

async Task Exec(NpgsqlConnection c, string sql)
{
    await using var cmd = new NpgsqlCommand(sql, c);
    await cmd.ExecuteNonQueryAsync();
}

await using var obs = new NpgsqlConnection(Cs(true, "ssc-npgsql-observer", false));
await obs.OpenAsync();
if ((string?)await Scalar(obs, "select current_setting('cluster_name')") != inst.GetProperty("token").GetString())
    throw new InvalidOperationException("refusing: cluster_name is not this investigation's server");
await Exec(obs, "delete from public.item; delete from tenant_a.item; delete from tenant_b.item");

await using var competitor = new NpgsqlConnection(Cs(false, "ssc-npgsql-competitor", false));
await competitor.OpenAsync();

async Task<string> BackendStart(int pid) =>
    (string)(await Scalar(obs, $"select backend_start::text from pg_stat_activity where pid = {pid}"))!;

async Task<string> PoolLockHolders() =>
    $"{await Scalar(obs, $"select count(*) from pg_locks l join pg_stat_activity a using (pid) where l.locktype = 'advisory' and l.objid = {LockKey} and l.granted and a.application_name = '{app}'")} backend(s) of the pool";

async Task<string> TempTables(int pid) =>
    (string)(await Scalar(obs, $@"select coalesce(string_agg(c.relname, ',' order by c.relname), 'none')
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'pg_temp_' || (select b from pg_stat_get_backend_idset() b where pg_stat_get_backend_pid(b) = {pid})
          and c.relkind = 'r'"))!;

async Task<string> CompetitorTry()
{
    var got = (bool)(await Scalar(competitor, $"select pg_try_advisory_lock({LockKey})"))!;
    if (got) await Exec(competitor, "select pg_advisory_unlock_all()");
    return got.ToString();
}

async Task<string> Landed(string label) =>
    (string)(await Scalar(obs, $@"select coalesce(string_agg(s, ', ' order by s), 'not visible') from (
        select 'public' s from public.item where label = '{label}' union all
        select 'tenant_a' from tenant_a.item where label = '{label}') x"))!;

async Task Dirty(NpgsqlConnection c)
{
    await Exec(c, "SET ROLE ssc_tenant_a");
    await Exec(c, "SET search_path TO tenant_a, public");
    await Exec(c, $"select pg_advisory_lock({LockKey})");
    await Exec(c, "CREATE TEMP TABLE ssc_temp_probe (id int)");
    await Exec(c, "LISTEN ppcs_probe_channel");
    await Exec(c, "PREPARE ssc_user_stmt AS SELECT 42");
    Out("A", "current_user | search_path after the session changes",
        await Scalar(c, "select current_user || ' | ' || current_setting('search_path')"));
}

async Task InspectB(NpgsqlDataSource ds, (int Pid, string Start) a)
{
    await using var b = await ds.OpenConnectionAsync();
    Out("B", "same physical session as A", b.ProcessID == a.Pid && await BackendStart(b.ProcessID) == a.Start);
    Out("B", "first statement: current_user | search_path | channels",
        await Scalar(b, "select current_user || ' | ' || current_setting('search_path') || ' | ' || " +
                        "coalesce((select string_agg(c, ',') from pg_listening_channels() c), 'no channels')"));
    Out("B", "SQL-level prepared statement ssc_user_stmt still defined",
        await Scalar(b, "select count(*) > 0 from pg_prepared_statements where name = 'ssc_user_stmt'"));
    Out("observer", $"advisory lock {LockKey} holders after B's first statement", await PoolLockHolders());
    Out("observer", "temp tables of B's backend after B's first statement", await TempTables(b.ProcessID));
    await Exec(b, "insert into item(label) values ('B-unqualified')");
    Out("observer", "where B's unqualified insert landed", await Landed("B-unqualified"));
}

Console.WriteLine($"scenario: {scenario}");
var extraSettings = scenario switch
{
    "no-reset" => "No Reset On Close=true;",
    "pruned" => "Connection Idle Lifetime=1;Connection Pruning Interval=1;",
    _ => "",
};
await using var ds = NpgsqlDataSource.Create(Cs(false, app, true, "Maximum Pool Size=1;" + extraSettings));

switch (scenario)
{
    case "pruned":
    {
        int pid;
        await using (var conn = await ds.OpenConnectionAsync())
        {
            pid = conn.ProcessID;
            await Dirty(conn);
        }
        Out("A", "Close()", "returned");
        Out("observer", $"advisory lock {LockKey} holders right after Close()", await PoolLockHolders());
        Out("competitor", $"pg_try_advisory_lock({LockKey}) right after Close()", await CompetitorTry());
        await Task.Delay(4000);
        Out("observer", "A's backend still exists 4 s later (idle lifetime 1 s, pruning every 1 s)",
            (long)(await Scalar(obs, $"select count(*) from pg_stat_activity where pid = {pid}"))! > 0);
        Out("competitor", $"pg_try_advisory_lock({LockKey}) 4 s after Close()", await CompetitorTry());
        break;
    }
    case "normal":
    case "no-reset":
    case "prepared":
    {
        (int Pid, string Start) a;
        await using (var conn = await ds.OpenConnectionAsync())
        {
            a = (conn.ProcessID, await BackendStart(conn.ProcessID));
            await Dirty(conn);
            if (scenario == "prepared")
            {
                await using var cmd = new NpgsqlCommand("select 1", conn);
                await cmd.PrepareAsync();   // Npgsql now has a prepared statement, so it resets without DISCARD ALL
                await cmd.ExecuteScalarAsync();
                Out("A", "Npgsql prepared statement created with NpgsqlCommand.Prepare()", "done");
            }
        }
        Out("A", "Close()", "returned");
        await Task.Delay(300);
        Out("observer", $"advisory lock {LockKey} holders while the connector is idle in the pool", await PoolLockHolders());
        Out("observer", "temp tables of the idle connector's backend", await TempTables(a.Pid));
        Out("competitor", $"pg_try_advisory_lock({LockKey}) while the connector is idle", await CompetitorTry());
        await InspectB(ds, a);
        Out("competitor", $"pg_try_advisory_lock({LockKey}) after B's first statement", await CompetitorTry());
        break;
    }
    case "rollback-fails":
    {
        (int Pid, string Start) a;
        var conn = await ds.OpenConnectionAsync();
        a = (conn.ProcessID, await BackendStart(conn.ProcessID));
        await using (var tx = await conn.BeginTransactionAsync())
        {
            await Exec(conn, "insert into item(label) values ('A-uncommitted')");
            await Dirty(conn);
            await Exec(obs, $"select pg_terminate_backend({a.Pid})");
            while ((long)(await Scalar(obs, $"select count(*) from pg_stat_activity where pid = {a.Pid}"))! > 0)
                await Task.Delay(50);
            Out("observer", "terminated A's backend inside A's transaction", "done");
            try { await tx.DisposeAsync(); Out("A", "transaction Dispose()", "returned"); }
            catch (Exception e) { Out("A", "transaction Dispose()", $"threw {e.GetType().Name}"); }
        }
        try { await conn.CloseAsync(); Out("A", "Close()", $"returned, state {conn.State}"); }
        catch (Exception e) { Out("A", "Close()", $"threw {e.GetType().Name}"); }
        Out("observer", "A's uncommitted insert", await Landed("A-uncommitted"));
        await InspectB(ds, a);
        break;
    }
    case "idle-killed":
    {
        (int Pid, string Start) a;
        await using (var conn = await ds.OpenConnectionAsync())
        {
            a = (conn.ProcessID, await BackendStart(conn.ProcessID));
            await Dirty(conn);
        }
        await Exec(obs, $"select pg_terminate_backend({a.Pid})");
        while ((long)(await Scalar(obs, $"select count(*) from pg_stat_activity where pid = {a.Pid}"))! > 0)
            await Task.Delay(50);
        Out("observer", "terminated the idle connector's backend", "done");
        try
        {
            await using var b0 = await ds.OpenConnectionAsync();
            Out("B0", "first statement on the reused connector", await Scalar(b0, "select 1"));
        }
        catch (Exception e) { Out("B0", "first statement on the reused connector", $"threw {e.GetType().Name}"); }
        await InspectB(ds, a);
        break;
    }
    default:
        throw new ArgumentException($"unknown scenario {scenario}");
}
