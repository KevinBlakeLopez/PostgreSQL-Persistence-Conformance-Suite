using System.Data;
using System.Reflection;
using System.Text.Json;
using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

static class Cases
{
    private const string FormTop = "NpgsqlConnection.BeginTransactionAsync, parameterized commands, then CommitAsync or RollbackAsync. One connection is held until the case's after-end checkpoint, unless the policy disposed it.";
    private const string FormNested = "The outer transaction is BeginTransactionAsync. The nested scope is SaveAsync, RollbackAsync(name), and ReleaseAsync on that NpgsqlTransaction. There is no second connection.";
    private const string FormReuse = "The next unit receives the same connection when the policy kept it, or a new checkout when the policy disposed it. pooled uses NpgsqlDataSource with MaxPoolSize 1. It is not a framework pool.";
    private const string FormManaged = "The policy runs the work and calls CommitAsync when the work returns. Npgsql has no managed-transaction type separate from NpgsqlTransaction.";
    private const string FormExplicit = "The same BeginTransactionAsync(IsolationLevel) and CommitAsync calls as the managed case. The handle is the NpgsqlTransaction the begin call returns.";

    public static async Task<Dictionary<string, object?>> Dispatch(Sessions sessions, Protocol protocol, JsonElement message, bool correct)
    {
        var id = CaseJson.Text(CaseJson.Object(message, "case"), "id");
        var markers = CaseJson.Object(message, "markers");
        var settings = CaseJson.OptionalObject(CaseJson.Object(message, "case"), "settings");
        return id switch
        {
            "CTL-01.commit" or "TX-01B.commit-reply-unseen" => await Commit(sessions, protocol, markers, correct),
            "CTL-01.rollback" => await Rollback(sessions, protocol, markers, correct),
            "TX-01A.caught-error-then-commit" => await CaughtError(sessions, protocol, markers, correct),
            "TX-01B.conn-lost-before-commit" => await ConnLost(sessions, protocol, markers, settings, correct),
            "TX-02.savepoint-rollback-not-sent" => await Savepoint(sessions, protocol, markers, settings, correct, "not-sent"),
            "TX-02.savepoint-rollback-rejected" => await Savepoint(sessions, protocol, markers, settings, correct, "rejected"),
            "TX-02.conn-lost-before-savepoint-rollback" => await Savepoint(sessions, protocol, markers, settings, correct, "conn-lost"),
            "TX-03.rollback-not-sent" => await Reuse(sessions, protocol, markers, settings, correct, "rollback-not-sent"),
            "TX-03.statement-error-rollback-not-sent" => await Reuse(sessions, protocol, markers, settings, correct, "statement-error"),
            "TX-03.conn-lost-in-transaction" => await Reuse(sessions, protocol, markers, settings, correct, "conn-lost"),
            "TX-04.nested-failure-contained" => await Nested(sessions, protocol, markers, correct, "nested-fails"),
            "TX-04.nested-released-outer-rollback" => await Nested(sessions, protocol, markers, correct, "outer-fails"),
            "TX-05.managed-serializable" => await Isolation(sessions, protocol, markers, settings, correct, FormManaged),
            "TX-05.explicit-serializable" => await Isolation(sessions, protocol, markers, settings, correct, FormExplicit),
            _ => throw new InvalidOperationException("this adapter does not implement " + id),
        };
    }

    private static async Task<Dictionary<string, object?>> Commit(Sessions sessions, Protocol protocol, JsonElement markers, bool correct)
    {
        var outcome = await Run(sessions, protocol, correct, null, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "tx"));
            var ident = await sessions.Identify(tx, false);
            protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
        });
        return Result(correct, outcome, new Dictionary<string, object?>(), FormTop);
    }

    private static async Task<Dictionary<string, object?>> Rollback(Sessions sessions, Protocol protocol, JsonElement markers, bool correct)
    {
        var outcome = await Run(sessions, protocol, correct, null, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "tx"));
            var ident = await sessions.Identify(tx, false);
            protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
            throw new AppException("application error: the request fails");
        });
        return Result(correct, outcome, new Dictionary<string, object?>(), FormTop);
    }

    private static async Task<Dictionary<string, object?>> CaughtError(Sessions sessions, Protocol protocol, JsonElement markers, bool correct)
    {
        Dictionary<string, object?>? violation = null;
        var outcome = await Run(sessions, protocol, correct, null, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "tx"));
            var ident = await sessions.Identify(tx, false);
            protocol.Checkpoint("after-write", ident.Xid, ident.Pid);
            try
            {
                await sessions.InsertTaken(tx);
            }
            catch (PostgresException ex)
            {
                violation = Errors.Info(ex);
            }

            if (violation is null)
            {
                throw new InvalidOperationException("the duplicate insert did not raise");
            }

            protocol.Checkpoint("before-end", null, ident.Pid);
        });
        var steps = new Dictionary<string, object?>();
        if (violation is not null)
        {
            steps["violation"] = violation;
        }

        return Result(correct, outcome, steps, FormTop);
    }

    private static async Task<Dictionary<string, object?>> ConnLost(Sessions sessions, Protocol protocol, JsonElement markers, JsonElement settings, bool correct)
    {
        var outcome = await Run(sessions, protocol, correct, null, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "tx"));
            var ident = await sessions.Identify(tx, false);
            protocol.Checkpoint("before-end", ident.Xid, ident.Pid);
            await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
        });
        return Result(correct, outcome, new Dictionary<string, object?>(), FormTop);
    }

    private static async Task<Dictionary<string, object?>> Savepoint(Sessions sessions, Protocol protocol, JsonElement markers, JsonElement settings, bool correct, string kind)
    {
        int? pid = null;
        var nested = new Dictionary<string, object?> { ["caught"] = false };
        var scope = new Scope();
        var outcome = await Run(sessions, protocol, correct, scope, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "outer"));
            var ident = await sessions.Identify(tx, false);
            pid = ident.Pid;
            sessions.Fault.Pid = ident.Pid;
            protocol.Checkpoint("outer-after-write", ident.Xid, ident.Pid);
            try
            {
                await NestedScope(sessions, tx, scope, async savepointTx =>
                {
                    await sessions.InsertItem(savepointTx, CaseJson.Text(markers, "inner"));
                    protocol.Checkpoint("inner-after-write", null, pid);
                    if (kind == "conn-lost")
                    {
                        await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
                    }
                    else if (kind == "not-sent")
                    {
                        sessions.Fault.Arm(Fault.Savepoint, "client-reject");
                    }
                    else
                    {
                        sessions.Fault.Arm(Fault.Savepoint, "rewrite");
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
        protocol.Checkpoint("after-outer", null, pid);
        var steps = new Dictionary<string, object?> { ["nested"] = nested };
        if (kind != "conn-lost")
        {
            steps["fault"] = sessions.Fault.Report();
        }

        return Result(correct, outcome, steps, FormNested);
    }

    private static async Task<Dictionary<string, object?>> Reuse(Sessions sessions, Protocol protocol, JsonElement markers, JsonElement settings, bool correct, string kind)
    {
        Dictionary<string, object?>? violation = null;
        int? unit1Pid = null;
        var unit1 = await Run(sessions, protocol, correct, null, null, async tx =>
        {
            await sessions.InsertItem(tx, CaseJson.Text(markers, "doomed"));
            var ident = await sessions.Identify(tx, false);
            unit1Pid = ident.Pid;
            sessions.Fault.Pid = ident.Pid;
            protocol.Checkpoint("unit1-after-write", ident.Xid, ident.Pid);
            if (kind == "conn-lost")
            {
                await Task.Delay(CaseJson.Int(settings, "settle_ms", 100));
            }
            else
            {
                sessions.Fault.Arm(Fault.Root, "client-reject");
            }

            if (kind == "statement-error")
            {
                try
                {
                    await sessions.InsertTaken(tx);
                }
                catch (PostgresException ex)
                {
                    violation = Errors.Info(ex);
                    throw;
                }
            }

            throw new AppException("application error: unit 1 fails");
        });
        sessions.Fault.Disarm();
        sessions.ReleaseIfPooled();
        protocol.Checkpoint("after-unit1", null, unit1Pid);

        var bound = CaseJson.Int(settings, "bound_ms", 5000);
        var started = Environment.TickCount64;
        int? unit2Pid = null;
        Outcome? unit2Result = null;
        var pending = false;
        var unit2Task = Task.Run(async () =>
        {
            return await Run(sessions, protocol, correct, null, null, async tx =>
            {
                if (protocol.HaltCheckpoints)
                {
                    throw new ProtocolException("unit 2 was given up before it wrote");
                }

                await sessions.InsertItem(tx, CaseJson.Text(markers, "next"));
                var ident = await sessions.Identify(tx, false);
                unit2Pid = ident.Pid;
                protocol.Checkpoint("unit2-after-write", ident.Xid, ident.Pid);
            });
        });
        var finished = await Task.WhenAny(unit2Task, Task.Delay(bound));
        if (finished != unit2Task)
        {
            lock (protocol.Lock)
            {
                protocol.HaltCheckpoints = true;
            }

            sessions.Discard();
            var late = await Task.WhenAny(unit2Task, Task.Delay(200));
            if (late == unit2Task && unit2Task.Status == TaskStatus.RanToCompletion)
            {
                unit2Result = await unit2Task;
            }
            else
            {
                pending = true;
            }
        }
        else
        {
            try
            {
                unit2Result = await unit2Task;
            }
            catch (Exception ex) when (ex is not ProtocolException)
            {
                unit2Result = FailedStart(ex);
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
            foreach (var pair in OutcomeFields(correct, unit2Result))
            {
                unit2[pair.Key] = pair.Value;
            }
        }

        var reuse = new Dictionary<string, object?>
        {
            ["unit1_pid"] = unit1Pid,
            ["unit2_pid"] = unit2Pid,
            ["same_backend"] = unit1Pid is not null && unit1Pid == unit2Pid,
            ["discarded"] = unit1.Discarded,
        };
        var steps = new Dictionary<string, object?>
        {
            ["unit2"] = unit2,
            ["reuse"] = reuse,
        };
        if (violation is not null)
        {
            steps["violation"] = violation;
        }

        if (unit1.BodyError is not null)
        {
            steps["body_error"] = unit1.BodyError;
        }

        if (unit1.CleanupError is not null)
        {
            steps["cleanup_error"] = unit1.CleanupError;
        }

        if (kind != "conn-lost")
        {
            steps["fault"] = sessions.Fault.Report();
        }

        return Result(correct, unit1, steps, FormReuse);
    }

    private static async Task<Dictionary<string, object?>> Nested(Sessions sessions, Protocol protocol, JsonElement markers, bool correct, string variant)
    {
        var caught = false;
        var completed = false;
        var deferred = new List<string>();
        var scope = new Scope();
        var outcome = await Run(sessions, protocol, correct, scope, null, async tx =>
        {
            if (correct)
            {
                await sessions.InsertItem(tx, CaseJson.Text(markers, "outer"));
            }
            else
            {
                deferred.Add(CaseJson.Text(markers, "outer"));
            }

            try
            {
                await NestedScope(sessions, tx, scope, async nested =>
                {
                    foreach (var name in deferred)
                    {
                        await sessions.InsertItem(nested, name);
                    }

                    deferred.Clear();
                    await sessions.InsertItem(nested, CaseJson.Text(markers, "inner"));
                    var ident = await sessions.Identify(nested, false);
                    protocol.Checkpoint("inner-after-write", ident.Xid, ident.Pid);
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
        return Result(correct, outcome, steps, FormNested);
    }

    private static async Task<Dictionary<string, object?>> Isolation(Sessions sessions, Protocol protocol, JsonElement markers, JsonElement settings, bool correct, string form)
    {
        var level = CaseJson.Text(settings, "isolation_level");
        var mapped = MapIsolation(level);
        try
        {
            var outcome = await Run(sessions, protocol, correct, null, correct ? mapped : null, async tx =>
            {
                await sessions.InsertItem(tx, CaseJson.Text(markers, "tx"));
                await sessions.ReadItem(tx, CaseJson.Text(markers, "tx"));
                var ident = await sessions.Identify(tx, true);
                protocol.Checkpoint("after-read", ident.Xid, ident.Pid, ident.Isolation);
            });
            var steps = new Dictionary<string, object?>
            {
                ["isolation_request"] = correct ? "BeginTransactionAsync(IsolationLevel)" : "not called",
                ["requested"] = level,
            };
            return Result(correct, outcome, steps, form);
        }
        catch (Exception start) when (start is not ProtocolException)
        {
            sessions.Discard();
            var steps = new Dictionary<string, object?>
            {
                ["isolation_request"] = "BeginTransactionAsync(IsolationLevel)",
                ["requested"] = level,
            };
            try
            {
                var baseline = await Run(sessions, protocol, true, null, null, async tx =>
                {
                    var ident = await sessions.Identify(tx, false);
                    protocol.Checkpoint("baseline", ident.Xid, ident.Pid);
                });
                steps["baseline_reported"] = baseline.Reported;
                if (baseline.Reported != "committed")
                {
                    steps["baseline"] = new Dictionary<string, object?> { ["error"] = baseline.ApiError };
                }
            }
            catch (Exception baselineError) when (baselineError is not ProtocolException)
            {
                steps["baseline"] = new Dictionary<string, object?> { ["error"] = Errors.Info(baselineError) };
            }

            var failed = new Outcome
            {
                Reported = "failed",
                Basis = "BeginTransactionAsync threw before the transaction body ran",
                ApiError = Errors.Info(start),
                Discarded = true,
            };
            return Result(correct, failed, steps, form);
        }
    }

    private static async Task<Outcome> Run(Sessions sessions, Protocol protocol, bool correct, Scope? scope, IsolationLevel? isolation, Func<FaultingTransaction, Task> work)
    {
        var tx = await sessions.Begin(protocol, correct ? isolation : null);
        try
        {
            return await Policy.Run(correct, sessions, tx, work, scope ?? new Scope(), isolation);
        }
        finally
        {
            try
            {
                await tx.Inner.DisposeAsync();
            }
            catch (Exception ex) when (ex is not ProtocolException)
            {
                sessions.Note("transaction dispose: " + ex.GetType().Name);
            }
        }
    }

    private static async Task NestedScope(Sessions sessions, FaultingTransaction tx, Scope scope, Func<FaultingTransaction, Task> work)
    {
        const string name = "ppcs_nested";
        await tx.SaveAsync(name);
        try
        {
            await work(tx);
            await tx.ReleaseAsync(name);
        }
        catch (Exception error) when (error is not ProtocolException)
        {
            try
            {
                await tx.RollbackToSavepointAsync(name);
            }
            catch (Exception rollbackError) when (rollbackError is not ProtocolException)
            {
                scope.RollbackOnly = true;
                scope.RollbackError = Errors.Info(rollbackError);
            }

            throw;
        }
    }

    private static Outcome FailedStart(Exception error)
        => new()
        {
            Reported = "failed",
            Basis = "the unit could not start a transaction",
            ApiError = Errors.Info(error),
            Discarded = false,
        };

    private static Dictionary<string, object?> Result(bool correct, Outcome outcome, Dictionary<string, object?> steps, string form)
    {
        var result = OutcomeFields(correct, outcome);
        if (outcome.Probe is not null)
        {
            steps["probe"] = outcome.Probe;
        }

        if (outcome.BodyError is not null && !steps.ContainsKey("body_error"))
        {
            steps["body_error"] = outcome.BodyError;
        }

        if (outcome.CleanupError is not null && !steps.ContainsKey("cleanup_error"))
        {
            steps["cleanup_error"] = outcome.CleanupError;
        }

        result["steps"] = steps;
        result["form"] = form;
        return result;
    }

    private static Dictionary<string, object?> OutcomeFields(bool correct, Outcome outcome)
    {
        var fields = new Dictionary<string, object?>
        {
            ["reported"] = outcome.Reported,
            ["basis"] = outcome.Basis,
            ["contract"] = Policy.Contract(correct),
        };
        if (outcome.ApiError is not null)
        {
            fields["api_error"] = outcome.ApiError;
        }

        return fields;
    }

    private static IsolationLevel MapIsolation(string level) => level switch
    {
        "read uncommitted" => IsolationLevel.ReadUncommitted,
        "read committed" => IsolationLevel.ReadCommitted,
        "repeatable read" => IsolationLevel.RepeatableRead,
        "serializable" => IsolationLevel.Serializable,
        _ => throw new ProtocolException("the case requests an unknown isolation level: " + level),
    };

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
