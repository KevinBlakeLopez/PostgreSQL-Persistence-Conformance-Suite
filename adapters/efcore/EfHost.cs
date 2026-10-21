using System.Data;
using System.Reflection;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Logging;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

sealed class EfHost : IDisposable
{
    private readonly string _connectionString;
    private readonly NpgsqlDataSource? _dataSource;
    private readonly List<AppDbContext> _held = [];
    private readonly List<Microsoft.EntityFrameworkCore.Storage.IDbContextTransaction> _transactions = [];

    public EfHost(string connectionString, bool pooled, Protocol protocol, bool executeSqlViolation)
    {
        Protocol = protocol;
        ExecuteSqlViolation = executeSqlViolation;
        Pooled = pooled;
        var builder = new NpgsqlConnectionStringBuilder(connectionString)
        {
            Pooling = pooled,
            MaxPoolSize = 1,
            MinPoolSize = 0,
            Timeout = 15,
            CommandTimeout = 30,
        };
        _connectionString = builder.ConnectionString;
        if (pooled)
        {
            _dataSource = NpgsqlDataSource.Create(_connectionString);
        }
    }

    public Protocol Protocol { get; }
    public ClientFault Fault { get; } = new();
    public bool ExecuteSqlViolation { get; }
    public bool Pooled { get; }
    public int CommittedHooks { get; set; }
    public int RolledBackHooks { get; set; }
    public string? Strategy { get; private set; }
    public bool? SupportsSavepoints { get; set; }
    public List<string> Sql { get; } = [];
    public List<string> Notes { get; } = [];

    public AppDbContext Open()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>();
        if (_dataSource is not null)
        {
            options.UseNpgsql(_dataSource);
        }
        else
        {
            options.UseNpgsql(_connectionString);
        }

        options.AddInterceptors(new FaultInterceptor(this));
        options.LogTo(
            line =>
            {
                if (Sql.Count < 100)
                {
                    Sql.Add(line);
                }
            },
            [DbLoggerCategory.Database.Command.Name],
            LogLevel.Information);
        var context = new AppDbContext(options.Options);
        Strategy ??= context.Database.CreateExecutionStrategy().GetType().Name;
        _held.Add(context);
        return context;
    }

    public void Hold(Microsoft.EntityFrameworkCore.Storage.IDbContextTransaction transaction)
        => _transactions.Add(transaction);

    public void Release(AppDbContext context)
    {
        _held.Remove(context);
        context.Dispose();
    }

    public Dictionary<string, object?> Diagnostics()
        => new()
        {
            ["notes"] = Notes.ToList(),
            ["sql"] = Sql.ToList(),
            ["trace"] = Fault.Trace.ToList(),
            ["execution_strategy"] = Strategy,
            ["supports_savepoints"] = SupportsSavepoints,
            ["hooks"] = new Dictionary<string, object?>
            {
                ["transaction_committed"] = CommittedHooks,
                ["transaction_rolled_back"] = RolledBackHooks,
            },
            ["pooled"] = Pooled,
        };

    public void Dispose()
    {
        foreach (var transaction in _transactions)
        {
            transaction.Dispose();
        }

        _transactions.Clear();
        foreach (var context in _held.ToList())
        {
            context.Dispose();
        }

        _held.Clear();
        _dataSource?.Dispose();
    }

    public static string AssemblyVersion(Type type)
    {
        var assembly = type.Assembly;
        var info = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
        if (!string.IsNullOrEmpty(info))
        {
            var plus = info.IndexOf('+', StringComparison.Ordinal);
            return plus > 0 ? info[..plus] : info;
        }

        return assembly.GetName().Version?.ToString() ?? "unknown";
    }
}
