using System.Data;
using System.Data.Common;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

/// <summary>
/// Category C injection before Npgsql sends.
/// EF Core calls <see cref="DbTransaction.Rollback"/> and <see cref="DbTransaction.Rollback(string)"/>
/// from <c>RelationalTransaction</c>. Those calls do not go through <see cref="DbCommand"/>.
/// This interceptor runs immediately before that call. It is not EF Core's own transaction policy.
/// </summary>
sealed class FaultInterceptor : DbTransactionInterceptor
{
    private readonly EfHost _host;

    public FaultInterceptor(EfHost host) => _host = host;

    public override InterceptionResult TransactionRollingBack(DbTransaction transaction, TransactionEventData eventData, InterceptionResult result)
    {
        WithholdRoot();
        return result;
    }

    public override ValueTask<InterceptionResult> TransactionRollingBackAsync(
        DbTransaction transaction,
        TransactionEventData eventData,
        InterceptionResult result,
        CancellationToken cancellationToken = default)
    {
        WithholdRoot();
        return new ValueTask<InterceptionResult>(result);
    }

    public override InterceptionResult RollingBackToSavepoint(DbTransaction transaction, TransactionEventData eventData, InterceptionResult result)
    {
        OnSavepoint(transaction);
        return result;
    }

    public override ValueTask<InterceptionResult> RollingBackToSavepointAsync(
        DbTransaction transaction,
        TransactionEventData eventData,
        InterceptionResult result,
        CancellationToken cancellationToken = default)
    {
        OnSavepoint(transaction);
        return new ValueTask<InterceptionResult>(result);
    }

    public override Task TransactionCommittedAsync(DbTransaction transaction, TransactionEndEventData eventData, CancellationToken cancellationToken = default)
    {
        _host.CommittedHooks++;
        return Task.CompletedTask;
    }

    public override void TransactionCommitted(DbTransaction transaction, TransactionEndEventData eventData)
        => _host.CommittedHooks++;

    public override Task TransactionRolledBackAsync(DbTransaction transaction, TransactionEndEventData eventData, CancellationToken cancellationToken = default)
    {
        _host.RolledBackHooks++;
        return Task.CompletedTask;
    }

    public override void TransactionRolledBack(DbTransaction transaction, TransactionEndEventData eventData)
        => _host.RolledBackHooks++;

    private void WithholdRoot()
    {
        if (!_host.Fault.Take(ClientFault.Root))
        {
            return;
        }

        _host.Fault.Withheld.Add("ROLLBACK");
        _host.Fault.Trace.Add("ROLLBACK -- WITHHELD in TransactionRollingBack before Npgsql send");
        _host.Protocol.Checkpoint("after-fault", null, _host.Fault.Pid);
        throw new NpgsqlException("injected client-side failure: ROLLBACK was not sent");
    }

    private void OnSavepoint(DbTransaction transaction)
    {
        if (!_host.Fault.Take(ClientFault.Savepoint))
        {
            return;
        }

        const string original = "ROLLBACK TO SAVEPOINT";
        _host.Fault.Withheld.Add(original);
        if (_host.Fault.Mode == "client-reject")
        {
            _host.Fault.Trace.Add(original + " -- WITHHELD in RollingBackToSavepoint before Npgsql send");
            _host.Protocol.Checkpoint("after-fault", null, _host.Fault.Pid);
            throw new NpgsqlException("injected client-side failure: ROLLBACK TO SAVEPOINT was not sent");
        }

        const string rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint";
        _host.Fault.Rewritten.Add(rewritten);
        _host.Fault.Trace.Add(rewritten + " -- REWRITE before Npgsql's own ROLLBACK TO SAVEPOINT");
        Exception? error = null;
        var connection = transaction.Connection ?? throw new InvalidOperationException("the transaction has no connection");
        using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = rewritten;
        try
        {
            command.ExecuteNonQuery();
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            error = ex;
            _host.Fault.ReplyCodes.Add(Errors.SqlState(ex) ?? "error");
        }

        _host.Protocol.Checkpoint("after-fault", null, _host.Fault.Pid);
        if (error is not null)
        {
            throw error;
        }

        throw new NpgsqlException("rewritten ROLLBACK TO SAVEPOINT did not fail");
    }
}

sealed class ClientFault
{
    public const string Root = "root";
    public const string Savepoint = "savepoint";

    public string? Mode { get; private set; }
    public int Fired { get; private set; }
    public int? Pid { get; set; }
    public List<string> Trace { get; } = [];
    public List<string> Withheld { get; } = [];
    public List<string> Rewritten { get; } = [];
    public List<string> ReplyCodes { get; } = [];

    private string? _kind;
    private bool _armed;

    public void Arm(string kind, string mode)
    {
        _kind = kind;
        Mode = mode;
        _armed = true;
    }

    public void Disarm()
    {
        _armed = false;
        _kind = null;
    }

    public bool Take(string expectedKind)
    {
        if (!_armed || _kind != expectedKind)
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
