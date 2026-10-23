using System.Data;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Npgsql;
using Ppcs;

namespace Ppcs.EfCore;

static class EfCases
{
    public const string Contract =
        "EF Core 10 IDbContextTransaction.CommitAsync commits the transaction begun by Database.BeginTransactionAsync. "
        + "The EF Core transaction API does not return a PostgreSQL command tag. "
        + "A return from CommitAsync is reported as committed. A throw from CommitAsync is reported as failed. "
        + "A throw from the body followed by RollbackAsync returning is reported as rolled_back. "
        + "A throw from RollbackAsync is reported as failed. "
        + "Marker inserts use Database.ExecuteSqlAsync. SaveChangesAsync inside an explicit transaction inserts the row under a savepoint and releases it; the row xmin is then that subtransaction, while pg_current_xact_id() is the top-level id, and the harness does not attribute that xmin to a top-level write. "
        + "The native TX-01A violation is still SaveChangesAsync of a Uniq entity. The execute-sql mode uses ExecuteSqlAsync for that violation. "
        + "A nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. "
        + "EF Core creates its own savepoint around SaveChangesAsync when a user transaction is already active and the transaction reports SupportsSavepoints. "
        + "This adapter does not disable that savepoint and does not read Npgsql protocol messages.";

    private const string FormExplicit = "Database.BeginTransactionAsync returns the handle. The application calls CommitAsync or RollbackAsync. Marker inserts are Database.ExecuteSqlAsync so the row is written in the top-level transaction. SaveChangesAsync is the native TX-01A violation.";
    private const string FormSavepoint = "The outer transaction is BeginTransactionAsync. The nested scope is CreateSavepointAsync, RollbackToSavepointAsync, and ReleaseSavepointAsync. A second BeginTransactionAsync is not used.";
    private const string FormPool = "NpgsqlDataSource MaxPoolSize 1, passed to UseNpgsql. The context is disposed between units, which returns the connection. The pool is not cleared and no validation query is issued by this adapter.";
    private const string FormExecuteSql = "The marker is SaveChangesAsync. The unique violation is Database.ExecuteSqlAsync inside the same BeginTransactionAsync. CommitAsync is unchanged.";

    public static async Task<Dictionary<string, object?>> Dispatch(EfHost host, JsonElement message)
    {
        var id = CaseJson.Text(CaseJson.Object(message, "case"), "id");
        var markers = CaseJson.Object(message, "markers");
        var settings = CaseJson.OptionalObject(CaseJson.Object(message, "case"), "settings");
        if (id.StartsWith("MG-", StringComparison.Ordinal))
        {
            return await MigrationRun.Run(message);
        }

        return id switch
        {
            "CTL-01.commit" or "TX-01B.commit-reply-unseen" => await Commit(host, markers),
            "CTL-01.rollback" => await Rollback(host, markers),
            "TX-01A.caught-error-then-commit" => await CaughtError(host, markers),
            "TX-01B.conn-lost-before-commit" => await ConnLost(host, markers, settings),
            "TX-02.savepoint-rollback-not-sent" => await Savepoint(host, markers, settings, "not-sent"),
            "TX-02.savepoint-rollback-rejected" => await Savepoint(host, markers, settings, "rejected"),
            "TX-02.conn-lost-before-savepoint-rollback" => await Savepoint(host, markers, settings, "conn-lost"),
            "TX-03.rollback-not-sent" => await Reuse(host, markers, settings, "rollback-not-sent"),
            "TX-03.statement-error-rollback-not-sent" => await Reuse(host, markers, settings, "statement-error"),
            "TX-03.conn-lost-in-transaction" => await Reuse(host, markers, settings, "conn-lost"),
            "TX-04.nested-failure-contained" => await Nested(host, markers, "nested-fails"),
            "TX-04.nested-released-outer-rollback" => await Nested(host, markers, "outer-fails"),
            "TX-05.explicit-serializable" => await Isolation(host, markers, settings),
            _ => throw new InvalidOperationException("this adapter does not implement " + id),
        };
    }

    private static async Task<Dictionary<string, object?>> Commit(EfHost host, JsonElement markers)
    {
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "tx"));
            var ident = await Identify(ctx, tx, false);
            host.Protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
        });
        return Result(host, outcome, new Dictionary<string, object?>(), FormExplicit);
    }

    private static async Task<Dictionary<string, object?>> Rollback(EfHost host, JsonElement markers)
    {
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "tx"));
            var ident = await Identify(ctx, tx, false);
            host.Protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
            throw new AppException("application error: the request fails");
        });
        return Result(host, outcome, new Dictionary<string, object?>(), FormExplicit);
    }

    private static async Task<Dictionary<string, object?>> CaughtError(EfHost host, JsonElement markers)
    {
        Dictionary<string, object?>? violation = null;
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "tx"));
            var ident = await Identify(ctx, tx, false);
            host.Protocol.Checkpoint("after-write", ident.Xid, ident.Pid);
            try
            {
                if (host.ExecuteSqlViolation)
                {
                    await ctx.Database.ExecuteSqlAsync($"insert into uniq (code) values ({"taken"})");
                }
                else
                {
                    ctx.Uniqs.Add(new Uniq { Code = "taken" });
                    await ctx.SaveChangesAsync();
                }
            }
            catch (Exception ex) when (ex is not ProtocolException && Errors.IsUniqueViolation(ex))
            {
                violation = Errors.Info(ex);
            }

            if (violation is null)
            {
                throw new InvalidOperationException("the duplicate insert did not raise");
            }

            host.Protocol.Checkpoint("before-end", null, ident.Pid);
        });
        var steps = new Dictionary<string, object?>();
        if (violation is not null)
        {
            steps["violation"] = violation;
        }

        steps["violation_api"] = host.ExecuteSqlViolation ? "Database.ExecuteSqlAsync" : "SaveChangesAsync";
        return Result(host, outcome, steps, host.ExecuteSqlViolation ? FormExecuteSql : FormExplicit);
    }

    private static async Task<Dictionary<string, object?>> ConnLost(EfHost host, JsonElement markers, JsonElement settings)
    {
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "tx"));
            var ident = await Identify(ctx, tx, false);
            host.Protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
            await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
        });
        return Result(host, outcome, new Dictionary<string, object?>(), FormExplicit);
    }

    private static async Task<Dictionary<string, object?>> Savepoint(EfHost host, JsonElement markers, JsonElement settings, string kind)
    {
        int? pid = null;
        var nested = new Dictionary<string, object?> { ["caught"] = false };
        var scope = new SaveScope();
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "outer"));
            var ident = await Identify(ctx, tx, false);
            pid = ident.Pid;
            host.Fault.Pid = ident.Pid;
            host.Protocol.Checkpoint("outer-after-write", ident.Xid, ident.Pid);
            try
            {
                await NestedScope(host, ctx, tx, scope, async () =>
                {
                    await InsertItem(ctx, CaseJson.Text(markers, "inner"));
                    host.Protocol.Checkpoint("inner-after-write", null, pid);
                    if (kind == "conn-lost")
                    {
                        await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
                    }
                    else if (kind == "not-sent")
                    {
                        host.Fault.Arm(ClientFault.Savepoint, "client-reject");
                    }
                    else
                    {
                        host.Fault.Arm(ClientFault.Savepoint, "rewrite");
                    }

                    throw new AppException("application error: the nested scope fails");
                });
            }
            catch (Exception ex) when (ex is not ProtocolException)
            {
                nested["caught"] = true;
                nested["error"] = Errors.Info(ex);
            }

            if (scope.RollbackError is not null)
            {
                nested["rollback_error"] = scope.RollbackError;
            }
        });
        host.Protocol.Checkpoint("after-outer", null, pid);
        var steps = new Dictionary<string, object?> { ["nested"] = nested };
        if (kind != "conn-lost")
        {
            steps["fault"] = host.Fault.Report();
        }

        return Result(host, outcome, steps, FormSavepoint);
    }

    private static async Task<Dictionary<string, object?>> Reuse(EfHost host, JsonElement markers, JsonElement settings, string kind)
    {
        Dictionary<string, object?>? violation = null;
        int? unit1Pid = null;
        var unit1Context = host.Open();
        ApiOutcome unit1;
        await using (var tx = await unit1Context.Database.BeginTransactionAsync())
        {
            host.SupportsSavepoints = tx.SupportsSavepoints;
            unit1 = await Finish(host, tx, async () =>
            {
                await InsertItem(unit1Context, CaseJson.Text(markers, "doomed"));
                var ident = await Identify(unit1Context, tx, false);
                unit1Pid = ident.Pid;
                host.Fault.Pid = ident.Pid;
                host.Protocol.Checkpoint("unit1-after-write", ident.Xid, ident.Pid);
                if (kind == "conn-lost")
                {
                    await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
                }
                else
                {
                    host.Fault.Arm(ClientFault.Root, "client-reject");
                }

                if (kind == "statement-error")
                {
                    // SaveChanges would roll the violation back to its own savepoint and leave the
                    // top-level transaction open. This case needs the aborted transaction block.
                    try
                    {
                        await unit1Context.Database.ExecuteSqlAsync($"insert into uniq (code) values ({"taken"})");
                    }
                    catch (Exception ex) when (ex is not ProtocolException && Errors.IsUniqueViolation(ex))
                    {
                        violation = Errors.Info(ex);
                        throw;
                    }
                }

                throw new AppException("application error: unit 1 fails");
            });
        }

        host.Fault.Disarm();
        host.Release(unit1Context);
        host.Protocol.Checkpoint("after-unit1", null, unit1Pid);

        var bound = CaseJson.Int(settings, "bound_ms", 5000);
        var started = Environment.TickCount64;
        int? unit2Pid = null;
        ApiOutcome? unit2Result = null;
        var pending = false;
        var unit2Task = Task.Run(async () =>
        {
            var ctx = host.Open();
            await using var tx = await ctx.Database.BeginTransactionAsync();
            return await Finish(host, tx, async () =>
            {
                if (host.Protocol.HaltCheckpoints)
                {
                    throw new ProtocolException("unit 2 was given up before it wrote");
                }

                await InsertItem(ctx, CaseJson.Text(markers, "next"));
                var ident = await Identify(ctx, tx, false);
                unit2Pid = ident.Pid;
                host.Protocol.Checkpoint("unit2-after-write", ident.Xid, ident.Pid);
            });
        });
        var finished = await Task.WhenAny(unit2Task, Task.Delay(bound));
        if (finished != unit2Task)
        {
            lock (host.Protocol.Lock)
            {
                host.Protocol.HaltCheckpoints = true;
            }

            pending = true;
        }
        else
        {
            try
            {
                unit2Result = await unit2Task;
            }
            catch (Exception ex) when (ex is not ProtocolException)
            {
                unit2Result = ApiOutcome.Failed("the unit could not start a transaction", ex);
            }
        }

        var elapsed = (int)(Environment.TickCount64 - started);
        var unit2 = new Dictionary<string, object?>();
        if (pending || unit2Result is null)
        {
            unit2["outcome"] = "pending";
            unit2["elapsed_ms"] = elapsed;
            unit2["reported"] = "pending";
        }
        else
        {
            unit2["outcome"] = "completed";
            unit2["elapsed_ms"] = elapsed;
            foreach (var pair in unit2Result.Fields())
            {
                unit2[pair.Key] = pair.Value;
            }
        }

        var steps = new Dictionary<string, object?>
        {
            ["unit2"] = unit2,
            ["reuse"] = new Dictionary<string, object?>
            {
                ["unit1_pid"] = unit1Pid,
                ["unit2_pid"] = unit2Pid,
                ["same_backend"] = unit1Pid is not null && unit1Pid == unit2Pid,
            },
        };
        if (violation is not null)
        {
            steps["violation"] = violation;
        }

        if (kind != "conn-lost")
        {
            steps["fault"] = host.Fault.Report();
        }

        return Result(host, unit1, steps, FormPool);
    }

    private static async Task<Dictionary<string, object?>> Nested(EfHost host, JsonElement markers, string variant)
    {
        var caught = false;
        var completed = false;
        var scope = new SaveScope();
        var outcome = await Run(host, null, async (ctx, tx) =>
        {
            await InsertItem(ctx, CaseJson.Text(markers, "outer"));
            try
            {
                await NestedScope(host, ctx, tx, scope, async () =>
                {
                    await InsertItem(ctx, CaseJson.Text(markers, "inner"));
                    var ident = await Identify(ctx, tx, false);
                    host.Protocol.Checkpoint("inner-after-write", ident.Xid, ident.Pid);
                    if (variant == "nested-fails")
                    {
                        throw new AppException("application error: the nested scope fails");
                    }
                });
                completed = true;
            }
            catch (Exception ex) when (ex is not ProtocolException)
            {
                caught = true;
            }

            if (variant == "outer-fails")
            {
                throw new AppException("application error: the outer scope fails");
            }
        });
        var steps = new Dictionary<string, object?>
        {
            ["nested"] = new Dictionary<string, object?>
            {
                ["caught"] = caught,
                ["completed"] = completed,
            },
        };
        return Result(host, outcome, steps, FormSavepoint);
    }

    private static async Task<Dictionary<string, object?>> Isolation(EfHost host, JsonElement markers, JsonElement settings)
    {
        var level = CaseJson.Text(settings, "isolation_level");
        try
        {
            var outcome = await Run(host, MapIsolation(level), async (ctx, tx) =>
            {
                await InsertItem(ctx, CaseJson.Text(markers, "tx"));
                var found = await ctx.Items.AsNoTracking().Where(item => item.Name == CaseJson.Text(markers, "tx")).ToListAsync();
                if (found.Count != 1)
                {
                    throw new InvalidOperationException("the read did not return the marker from PostgreSQL");
                }

                var ident = await Identify(ctx, tx, true);
                host.Protocol.Checkpoint("after-read", ident.Xid, ident.Pid, ident.Isolation);
            });
            var steps = new Dictionary<string, object?>
            {
                ["isolation_request"] = "BeginTransactionAsync(IsolationLevel)",
                ["requested"] = level,
            };
            return Result(host, outcome, steps, FormExplicit);
        }
        catch (Exception start) when (start is not ProtocolException)
        {
            var steps = new Dictionary<string, object?>
            {
                ["isolation_request"] = "BeginTransactionAsync(IsolationLevel)",
                ["requested"] = level,
            };
            try
            {
                var baseline = await Run(host, null, async (ctx, tx) =>
                {
                    var ident = await Identify(ctx, tx, false);
                    host.Protocol.Checkpoint("baseline", ident.Xid, ident.Pid);
                });
                steps["baseline_reported"] = baseline.Reported;
            }
            catch (Exception baselineError) when (baselineError is not ProtocolException)
            {
                steps["baseline"] = new Dictionary<string, object?> { ["error"] = Errors.Info(baselineError) };
            }

            return Result(host, ApiOutcome.Failed("BeginTransactionAsync threw before the transaction body ran", start), steps, FormExplicit);
        }
    }

    private static async Task<ApiOutcome> Run(EfHost host, IsolationLevel? isolation, Func<AppDbContext, IDbContextTransaction, Task> work)
    {
        var context = host.Open();
        var tx = isolation is IsolationLevel level
            ? await context.Database.BeginTransactionAsync(level)
            : await context.Database.BeginTransactionAsync();
        // Disposed with the host, after after-end. EF still releases the connection when
        // CommitAsync or RollbackAsync completes, so the backend is often already gone then.
        host.Hold(tx);
        host.SupportsSavepoints ??= tx.SupportsSavepoints;
        return await Finish(host, tx, () => work(context, tx));
    }

    private static async Task<ApiOutcome> Finish(EfHost host, IDbContextTransaction tx, Func<Task> work)
    {
        Exception? body = null;
        try
        {
            await work();
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            body = ex;
        }

        if (body is not null)
        {
            try
            {
                await tx.RollbackAsync();
                return ApiOutcome.RolledBack("the body threw and IDbContextTransaction.RollbackAsync returned", body);
            }
            catch (Exception rollback) when (rollback is not ProtocolException)
            {
                return ApiOutcome.Failed("the body threw and RollbackAsync threw", rollback, body);
            }
        }

        try
        {
            await tx.CommitAsync();
            return ApiOutcome.Committed("IDbContextTransaction.CommitAsync returned");
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            return ApiOutcome.Failed("IDbContextTransaction.CommitAsync threw", ex);
        }
    }

    private static async Task NestedScope(EfHost host, AppDbContext context, IDbContextTransaction tx, SaveScope scope, Func<Task> work)
    {
        const string name = "ppcs_nested";
        await tx.CreateSavepointAsync(name);
        host.Notes.Add("CreateSavepointAsync " + name);
        try
        {
            await work();
            await tx.ReleaseSavepointAsync(name);
            host.Notes.Add("ReleaseSavepointAsync " + name);
        }
        catch (Exception error) when (error is not ProtocolException)
        {
            try
            {
                await tx.RollbackToSavepointAsync(name);
                host.Notes.Add("RollbackToSavepointAsync " + name);
            }
            catch (Exception rollbackError) when (rollbackError is not ProtocolException)
            {
                scope.RollbackOnly = true;
                scope.RollbackError = Errors.Info(rollbackError);
                host.Notes.Add("RollbackToSavepointAsync threw");
            }

            throw;
        }
    }

    private static async Task InsertItem(AppDbContext context, string name)
    {
        // ExecuteSql enlists in the current transaction and does not open the savepoint
        // SaveChanges uses around a batch. See the contract string.
        await context.Database.ExecuteSqlAsync($"insert into item (name) values ({name})");
    }

    private static async Task<Ident> Identify(AppDbContext context, IDbContextTransaction tx, bool isolation)
    {
        var connection = context.Database.GetDbConnection();
        if (connection.State != ConnectionState.Open)
        {
            await connection.OpenAsync();
        }

        await using var command = connection.CreateCommand();
        command.Transaction = tx.GetDbTransaction();
        command.CommandText = isolation
            ? "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
            : "select pg_current_xact_id()::text, pg_backend_pid()";
        await using var reader = await command.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
        {
            throw new InvalidOperationException("the identity query returned no row");
        }

        return new Ident(reader.GetString(0), reader.GetInt32(1), isolation ? reader.GetString(2) : null);
    }

    private static Dictionary<string, object?> Result(EfHost host, ApiOutcome outcome, Dictionary<string, object?> steps, string form)
    {
        steps["hooks"] = new Dictionary<string, object?>
        {
            ["transaction_committed"] = host.CommittedHooks,
            ["transaction_rolled_back"] = host.RolledBackHooks,
        };
        steps["supports_savepoints"] = host.SupportsSavepoints;
        var result = outcome.Fields();
        result["steps"] = steps;
        result["form"] = form;
        return result;
    }

    private static IsolationLevel MapIsolation(string level) => level switch
    {
        "read uncommitted" => IsolationLevel.ReadUncommitted,
        "read committed" => IsolationLevel.ReadCommitted,
        "repeatable read" => IsolationLevel.RepeatableRead,
        "serializable" => IsolationLevel.Serializable,
        _ => throw new ProtocolException("the case requests an unknown isolation level: " + level),
    };

    private sealed class SaveScope
    {
        public bool RollbackOnly { get; set; }
        public Dictionary<string, object?>? RollbackError { get; set; }
    }

    private readonly record struct Ident(string Xid, int Pid, string? Isolation);
}

sealed class ApiOutcome
{
    public required string Reported { get; init; }
    public required string Basis { get; init; }
    public Dictionary<string, object?>? ApiError { get; init; }
    public Dictionary<string, object?>? BodyError { get; init; }

    public static ApiOutcome Committed(string basis)
        => new() { Reported = "committed", Basis = basis };

    public static ApiOutcome RolledBack(string basis, Exception error)
        => new() { Reported = "rolled_back", Basis = basis, ApiError = Errors.Info(error) };

    public static ApiOutcome Failed(string basis, Exception error, Exception? body = null)
        => new()
        {
            Reported = "failed",
            Basis = basis,
            ApiError = Errors.Info(error),
            BodyError = body is null ? null : Errors.Info(body),
        };

    public Dictionary<string, object?> Fields()
    {
        var fields = new Dictionary<string, object?>
        {
            ["reported"] = Reported,
            ["basis"] = Basis,
            ["contract"] = EfCases.Contract,
        };
        if (ApiError is not null)
        {
            fields["api_error"] = ApiError;
        }

        return fields;
    }
}
