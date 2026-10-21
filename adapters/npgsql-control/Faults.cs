using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

/// <summary>
/// One category C injection. Armed by the case, fired at most once, before Npgsql sends.
/// </summary>
sealed class Fault
{
    public const string Root = "root";
    public const string Savepoint = "savepoint";

    public string? Kind { get; private set; }
    public string? Mode { get; private set; }
    public int Fired { get; private set; }
    public int? Pid { get; set; }
    public List<string> Trace { get; } = [];
    public List<string> Withheld { get; } = [];
    public List<string> Rewritten { get; } = [];
    public List<string> ReplyCodes { get; } = [];

    private bool _armed;

    public void Arm(string kind, string mode)
    {
        Kind = kind;
        Mode = mode;
        _armed = true;
    }

    public void Disarm()
    {
        _armed = false;
        Kind = null;
    }

    public bool Take(string expectedKind)
    {
        if (!_armed || Kind != expectedKind)
        {
            return false;
        }

        _armed = false;
        Fired++;
        return true;
    }

    public Dictionary<string, object?> Report()
    {
        var report = new Dictionary<string, object?>
        {
            ["mode"] = Mode,
            ["fired"] = Fired,
            ["injection"] = "client-side",
            ["withheld"] = Withheld.ToList(),
        };
        if (Rewritten.Count > 0)
        {
            report["rewritten"] = Rewritten.ToList();
        }

        if (ReplyCodes.Count > 0)
        {
            report["reply_codes"] = ReplyCodes.ToList();
        }

        return report;
    }
}

/// <summary>
/// The policy's transaction handle. Rollback calls are the injection point.
/// Commit is not intercepted: it is the public <see cref="NpgsqlTransaction.CommitAsync"/>.
/// </summary>
sealed class FaultingTransaction
{
    private readonly Fault _fault;
    private readonly Protocol _protocol;

    public FaultingTransaction(NpgsqlConnection connection, NpgsqlTransaction transaction, Fault fault, Protocol protocol)
    {
        Connection = connection;
        Inner = transaction;
        _fault = fault;
        _protocol = protocol;
    }

    public NpgsqlConnection Connection { get; }
    public NpgsqlTransaction Inner { get; }

    public Task CommitAsync() => Inner.CommitAsync();

    public async Task RollbackAsync()
    {
        if (_fault.Take(Fault.Root))
        {
            _fault.Withheld.Add("ROLLBACK");
            _fault.Trace.Add("ROLLBACK -- WITHHELD on NpgsqlTransaction.RollbackAsync before send");
            _protocol.Checkpoint("after-fault", null, _fault.Pid);
            throw new NpgsqlException("injected client-side failure: ROLLBACK was not sent");
        }

        _fault.Trace.Add("ROLLBACK");
        await Inner.RollbackAsync();
    }

    public async Task SaveAsync(string name)
    {
        _fault.Trace.Add("SAVEPOINT " + name);
        await Inner.SaveAsync(name);
    }

    public async Task ReleaseAsync(string name)
    {
        _fault.Trace.Add("RELEASE SAVEPOINT " + name);
        await Inner.ReleaseAsync(name);
    }

    public async Task RollbackToSavepointAsync(string name)
    {
        var original = "ROLLBACK TO SAVEPOINT " + name;
        if (!_fault.Take(Fault.Savepoint))
        {
            _fault.Trace.Add(original);
            await Inner.RollbackAsync(name);
            return;
        }

        _fault.Withheld.Add(original);
        if (_fault.Mode == "client-reject")
        {
            _fault.Trace.Add(original + " -- WITHHELD before send");
            _protocol.Checkpoint("after-fault", null, _fault.Pid);
            throw new NpgsqlException("injected client-side failure: ROLLBACK TO SAVEPOINT was not sent");
        }

        const string rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint";
        _fault.Rewritten.Add(rewritten);
        _fault.Trace.Add(rewritten + " -- REWRITE of: " + original);
        Exception? error = null;
        try
        {
            await using var command = new NpgsqlCommand(rewritten, Connection, Inner);
            await command.ExecuteNonQueryAsync();
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            error = ex;
            _fault.ReplyCodes.Add(Errors.SqlState(ex) ?? "error");
        }

        _protocol.Checkpoint("after-fault", null, _fault.Pid);
        if (error is not null)
        {
            throw error;
        }

        throw new NpgsqlException("rewritten ROLLBACK TO SAVEPOINT did not fail");
    }
}
