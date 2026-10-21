using System.Data;
using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

sealed class Ident
{
    public required string Xid { get; init; }
    public required int Pid { get; init; }
    public string? Isolation { get; init; }
}

/// <summary>
/// One connection, or a pool of one. The correct policy disposes a connection whose rollback or commit threw.
/// The pooled modes return that connection to an <see cref="NpgsqlDataSource"/> with <c>MaxPoolSize</c> 1.
/// </summary>
sealed class Sessions : IDisposable
{
    private readonly string _connectionString;
    private readonly bool _pooled;
    private readonly NpgsqlDataSource? _dataSource;
    private NpgsqlConnection? _held;
    private readonly List<string> _notes = [];

    public Fault Fault { get; } = new();

    public Sessions(string connectionString, bool pooled, bool noResetOnClose)
    {
        _pooled = pooled;
        var builder = new NpgsqlConnectionStringBuilder(connectionString)
        {
            Pooling = pooled,
            MaxPoolSize = 1,
            MinPoolSize = 0,
            NoResetOnClose = noResetOnClose,
            Timeout = 15,
            CommandTimeout = 30,
        };
        _connectionString = builder.ConnectionString;
        if (pooled)
        {
            _dataSource = NpgsqlDataSource.Create(_connectionString);
        }
    }

    public void Note(string text) => _notes.Add(text);

    public async Task<FaultingTransaction> Begin(Protocol protocol, IsolationLevel? isolation)
    {
        var connection = await Open();
        NpgsqlTransaction transaction = isolation is IsolationLevel level
            ? await connection.BeginTransactionAsync(level)
            : await connection.BeginTransactionAsync();
        Note(isolation is null ? "BEGIN" : "BEGIN isolation " + isolation);
        return new FaultingTransaction(connection, transaction, Fault, protocol);
    }

    public void Discard()
    {
        Note("connection disposed");
        _held?.Dispose();
        _held = null;
    }

    /// <summary>Pooled checkouts are returned when the unit finishes, so the next unit can take the only slot.</summary>
    public void ReleaseIfPooled()
    {
        if (!_pooled)
        {
            return;
        }

        _held?.Dispose();
        _held = null;
    }

    public async Task InsertItem(FaultingTransaction tx, string name)
    {
        await using var command = new NpgsqlCommand("insert into item (name) values ($1)", tx.Connection, tx.Inner);
        command.Parameters.AddWithValue(name);
        await command.ExecuteNonQueryAsync();
    }

    public async Task InsertTaken(FaultingTransaction tx)
    {
        await using var command = new NpgsqlCommand("insert into uniq (code) values ('taken')", tx.Connection, tx.Inner);
        await command.ExecuteNonQueryAsync();
    }

    public async Task ReadItem(FaultingTransaction tx, string name)
    {
        await using var command = new NpgsqlCommand("select name from item where name = $1", tx.Connection, tx.Inner);
        command.Parameters.AddWithValue(name);
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            _ = reader.GetString(0);
        }
    }

    public async Task<Ident> Identify(FaultingTransaction tx, bool isolation)
    {
        var sql = isolation
            ? "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
            : "select pg_current_xact_id()::text, pg_backend_pid()";
        await using var command = new NpgsqlCommand(sql, tx.Connection, tx.Inner);
        await using var reader = await command.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
        {
            throw new InvalidOperationException("the identity query returned no row");
        }

        return new Ident
        {
            Xid = reader.GetString(0),
            Pid = reader.GetInt32(1),
            Isolation = isolation ? reader.GetString(2) : null,
        };
    }

    public Dictionary<string, object?> Diagnostics()
        => new()
        {
            ["notes"] = _notes.ToList(),
            ["trace"] = Fault.Trace.ToList(),
            ["pooled"] = _pooled,
        };

    public void Dispose()
    {
        _held?.Dispose();
        _held = null;
        _dataSource?.Dispose();
    }

    private async Task<NpgsqlConnection> Open()
    {
        if (_held is { State: ConnectionState.Open })
        {
            return _held;
        }

        _held?.Dispose();
        _held = _dataSource is null ? new NpgsqlConnection(_connectionString) : await _dataSource.OpenConnectionAsync();
        if (_dataSource is null)
        {
            await _held.OpenAsync();
        }

        Note("opened backend");
        return _held;
    }
}
