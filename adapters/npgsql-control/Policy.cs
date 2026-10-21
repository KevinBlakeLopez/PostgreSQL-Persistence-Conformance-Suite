using System.Data;
using Npgsql;
using Ppcs;

namespace Ppcs.NpgsqlControl;

/// <summary>
/// What <see cref="Policy"/> does after the I/O has already happened.
/// The strings are the reports the harness classifies. They are not a second transaction API.
/// </summary>
static class Decisions
{
    internal readonly record struct Input(
        bool Correct,
        bool BodyFailed,
        bool SavepointRollbackFailed,
        string Probe,
        bool RollbackAttempted,
        bool RollbackReturned,
        bool CommitAttempted,
        bool CommitReturned,
        bool RecoveryCommitAttempted,
        bool RecoveryCommitReturned);

    internal readonly record struct Result(string Reported, string Basis, bool DiscardConnection);

    internal static Result Map(Input input)
    {
        if (input.BodyFailed)
        {
            if (input.RollbackReturned)
            {
                return new Result(
                    "rolled_back",
                    "the body threw and NpgsqlTransaction.RollbackAsync returned",
                    false);
            }

            if (!input.Correct && input.RecoveryCommitAttempted)
            {
                var recovery = input.RecoveryCommitReturned
                    ? "CommitAsync then returned and the connection was kept."
                    : "CommitAsync then threw and the connection was kept.";
                return new Result(
                    "failed",
                    "the body threw and RollbackAsync threw. The unsafe policy called " + recovery,
                    false);
            }

            return new Result(
                "failed",
                "the body threw and RollbackAsync threw. The connection was disposed. CommitAsync was not called.",
                true);
        }

        if (input.SavepointRollbackFailed && input.Correct)
        {
            if (input.RollbackReturned)
            {
                return new Result(
                    "rolled_back",
                    "a savepoint rollback had failed, so the policy ended the transaction with RollbackAsync instead of CommitAsync",
                    false);
            }

            return new Result(
                "failed",
                "a savepoint rollback had failed, and RollbackAsync of the surrounding transaction also threw. The connection was disposed.",
                true);
        }

        if (!input.CommitAttempted)
        {
            return new Result("failed", "the policy did not call CommitAsync and did not report an outcome", true);
        }

        if (!input.CommitReturned)
        {
            if (input.Correct)
            {
                return new Result(
                    "failed",
                    "CommitAsync threw. The policy reports failed and disposes the connection. It does not report a confirmed rollback.",
                    true);
            }

            return new Result(
                "rolled_back",
                "CommitAsync threw, which the unsafe policy reports as a rollback",
                false);
        }

        if (!input.Correct)
        {
            var ignored = input.SavepointRollbackFailed ? " A savepoint rollback had failed and was ignored." : "";
            return new Result(
                "committed",
                "CommitAsync returned." + ignored + " The unsafe policy does not read a command tag and does not probe the session.",
                false);
        }

        return input.Probe switch
        {
            "failed" => new Result(
                "rolled_back",
                "SELECT 1 failed with 25P02 before CommitAsync, and CommitAsync then returned. "
                + "25P02 means the session is in a failed transaction block. "
                + "Npgsql 10.0.3 CommitAsync does not expose the command tag. "
                + "The policy reports rolled_back from the 25P02, not from a tag it did not read.",
                false),
            "queryable" => new Result(
                "committed",
                "SELECT 1 succeeded before CommitAsync, so the session was not in a failed transaction block, and CommitAsync returned. "
                + "The command tag is not exposed. The policy does not treat a bare return, with no prior probe, as a commit.",
                false),
            _ => new Result(
                "failed",
                "CommitAsync returned, but the policy could not tell whether the session was in a failed transaction block. It does not report a commit.",
                true),
        };
    }
}

sealed class Scope
{
    public bool RollbackOnly { get; set; }
    public Dictionary<string, object?>? RollbackError { get; set; }
}

sealed class Outcome
{
    public required string Reported { get; init; }
    public required string Basis { get; init; }
    public Dictionary<string, object?>? ApiError { get; init; }
    public string? Probe { get; init; }
    public bool Discarded { get; init; }
    public Dictionary<string, object?>? BodyError { get; init; }
    public Dictionary<string, object?>? CleanupError { get; init; }
}

/// <summary>
/// Two completion policies. They do not share a method.
/// The correct policy refuses to report a commit without a probe that the session was still queryable.
/// The unsafe policy reports a commit whenever <see cref="NpgsqlTransaction.CommitAsync"/> returns.
/// </summary>
static class Policy
{
    public const string CorrectContract =
        "The correct npgsql-control policy uses NpgsqlConnection.BeginTransactionAsync, NpgsqlTransaction.CommitAsync, RollbackAsync, SaveAsync, RollbackAsync(name), and ReleaseAsync. "
        + "Npgsql 10.0.3 CommitAsync sends COMMIT and waits for CommandComplete and ReadyForQuery. ExecuteInternalCommand does not read the command tag. "
        + "TransactionStatus on the connector is internal and is Idle after both a committed transaction and a COMMIT that PostgreSQL answered with ROLLBACK. "
        + "The public transaction API does not expose either fact. Before CommitAsync the policy runs SELECT 1 on the same connection. "
        + "SQLSTATE 25P02 means the session is in a failed transaction block. If that probe fails with 25P02 and CommitAsync returns, the policy reports rolled_back and says it did not read the tag. "
        + "If the probe succeeds and CommitAsync returns, the policy reports committed. A return from CommitAsync with no probe is not reported as a commit. "
        + "If CommitAsync throws, the policy reports failed and disposes the connection. If RollbackAsync throws, it disposes the connection and does not call CommitAsync. "
        + "A failed RollbackAsync(savepoint) is followed by RollbackAsync of the surrounding transaction. "
        + "IsolationLevel is passed to BeginTransactionAsync.";

    public const string UnsafeContract =
        "The unsafe npgsql-control policy reports committed whenever NpgsqlTransaction.CommitAsync returns. It does not probe the session and does not read a command tag. "
        + "It reports rolled_back when CommitAsync throws. It calls CommitAsync after RollbackAsync(savepoint) has thrown. "
        + "When RollbackAsync throws, it calls CommitAsync and keeps the connection. That is the mistake of clearing an open transaction by committing it. "
        + "It does not pass an IsolationLevel to BeginTransactionAsync. A write made before a nested savepoint is executed inside that savepoint.";

    public static string Contract(bool correct) => correct ? CorrectContract : UnsafeContract;

    public static async Task<Outcome> Run(
        bool correct,
        Sessions sessions,
        FaultingTransaction tx,
        Func<FaultingTransaction, Task> work,
        Scope scope,
        IsolationLevel? isolation)
    {
        if (correct && isolation is IsolationLevel level)
        {
            // Begin was already called by the caller when isolation is set on that begin.
            // The parameter is accepted so the call site shows the policy owns the decision.
            _ = level;
        }

        Exception? body = null;
        try
        {
            await work(tx);
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            body = ex;
        }

        if (body is not null)
        {
            return await AfterBodyFailure(correct, sessions, tx, body);
        }

        if (scope.RollbackOnly && correct)
        {
            var rollback = await TryRollback(tx);
            if (!rollback.Returned)
            {
                sessions.Discard();
                return Failed(
                    "a savepoint rollback had failed, and RollbackAsync of the surrounding transaction also threw. The connection was disposed.",
                    rollback.Error,
                    null,
                    true,
                    Errors.Info(bodyOr(rollback.Error)),
                    null);
            }

            return RolledBack(
                "a savepoint rollback had failed, so the policy ended the transaction with RollbackAsync instead of CommitAsync",
                Synthetic("a savepoint rollback failed, so the transaction was rolled back"),
                null,
                false);
        }

        string probe = "not-run";
        if (correct)
        {
            probe = await Probe(sessions, tx);
        }

        var commit = await TryCommit(tx);
        var mapped = Decisions.Map(new Decisions.Input(
            correct,
            BodyFailed: false,
            SavepointRollbackFailed: scope.RollbackOnly,
            Probe: probe,
            RollbackAttempted: false,
            RollbackReturned: false,
            CommitAttempted: true,
            CommitReturned: commit.Returned,
            RecoveryCommitAttempted: false,
            RecoveryCommitReturned: false));
        if (mapped.DiscardConnection)
        {
            sessions.Discard();
        }

        sessions.Note("probe=" + probe + " commitReturned=" + commit.Returned);
        return ToOutcome(mapped, commit.Error, probe, null, commit.Returned ? null : Errors.Info(bodyOr(commit.Error)));
    }

    private static async Task<Outcome> AfterBodyFailure(bool correct, Sessions sessions, FaultingTransaction tx, Exception body)
    {
        var rollback = await TryRollback(tx);
        if (rollback.Returned)
        {
            return RolledBack("the body threw and NpgsqlTransaction.RollbackAsync returned", Errors.Info(body), null, false, Errors.Info(body), null);
        }

        if (!correct)
        {
            sessions.Note("CommitAsync after a failed RollbackAsync");
            var recovery = await TryCommit(tx);
            sessions.Note("recovery commit returned=" + recovery.Returned);
            var basis = recovery.Returned
                ? "the body threw and RollbackAsync threw. CommitAsync then returned and the connection was kept."
                : "the body threw and RollbackAsync threw. CommitAsync then threw and the connection was kept.";
            return Failed(basis, recovery.Error ?? rollback.Error, null, false, Errors.Info(body), Errors.Info(bodyOr(recovery.Error ?? rollback.Error)));
        }

        sessions.Discard();
        return Failed(
            "the body threw and RollbackAsync threw. The connection was disposed. CommitAsync was not called.",
            rollback.Error,
            null,
            true,
            Errors.Info(body),
            Errors.Info(bodyOr(rollback.Error)));
    }

    private static async Task<string> Probe(Sessions sessions, FaultingTransaction tx)
    {
        try
        {
            await using var command = new NpgsqlCommand("select 1", tx.Connection, tx.Inner);
            await command.ExecuteScalarAsync();
            sessions.Note("probe queryable");
            return "queryable";
        }
        catch (PostgresException ex) when (ex.SqlState == "25P02")
        {
            sessions.Note("probe 25P02");
            return "failed";
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            sessions.Note("probe unreadable: " + ex.GetType().Name);
            return "unreadable";
        }
    }

    private static async Task<(bool Returned, Exception? Error)> TryCommit(FaultingTransaction tx)
    {
        try
        {
            await tx.CommitAsync();
            return (true, null);
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            return (false, ex);
        }
    }

    private static async Task<(bool Returned, Exception? Error)> TryRollback(FaultingTransaction tx)
    {
        try
        {
            await tx.RollbackAsync();
            return (true, null);
        }
        catch (Exception ex) when (ex is not ProtocolException)
        {
            return (false, ex);
        }
    }

    private static Exception bodyOr(Exception? error) => error ?? new InvalidOperationException("the driver call failed without an exception object");

    private static Outcome ToOutcome(Decisions.Result mapped, Exception? driverError, string probe, Dictionary<string, object?>? body, Dictionary<string, object?>? cleanup)
    {
        Dictionary<string, object?>? api = mapped.Reported switch
        {
            "committed" => null,
            "rolled_back" when driverError is null => Synthetic(mapped.Basis),
            _ => driverError is null ? Synthetic(mapped.Basis) : Errors.Info(driverError),
        };
        if (mapped.Reported == "rolled_back" && probe == "failed")
        {
            api = Synthetic("SELECT 1 failed with 25P02 before CommitAsync returned");
            api["code"] = "25P02";
        }

        return new Outcome
        {
            Reported = mapped.Reported,
            Basis = mapped.Basis,
            ApiError = api,
            Probe = probe,
            Discarded = mapped.DiscardConnection,
            BodyError = body,
            CleanupError = cleanup,
        };
    }

    private static Outcome RolledBack(string basis, Dictionary<string, object?> api, string? probe, bool discarded, Dictionary<string, object?>? body = null, Dictionary<string, object?>? cleanup = null)
        => new()
        {
            Reported = "rolled_back",
            Basis = basis,
            ApiError = api,
            Probe = probe,
            Discarded = discarded,
            BodyError = body,
            CleanupError = cleanup,
        };

    private static Outcome Failed(string basis, Exception? error, string? probe, bool discarded, Dictionary<string, object?>? body, Dictionary<string, object?>? cleanup)
        => new()
        {
            Reported = "failed",
            Basis = basis,
            ApiError = error is null ? Synthetic(basis) : Errors.Info(error),
            Probe = probe,
            Discarded = discarded,
            BodyError = body,
            CleanupError = cleanup,
        };

    private static Dictionary<string, object?> Synthetic(string message)
        => new()
        {
            ["class"] = "PolicyReport",
            ["code"] = null,
            ["message"] = message,
        };
}
