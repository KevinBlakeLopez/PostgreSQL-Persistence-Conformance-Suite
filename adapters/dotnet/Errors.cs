using Npgsql;

namespace Ppcs;

public static class Errors
{
    public static Dictionary<string, object?> Info(Exception error)
    {
        return new Dictionary<string, object?>
        {
            ["class"] = error.GetType().Name,
            ["code"] = SqlState(error),
            ["message"] = error.Message,
        };
    }

    /// <summary>The first PostgreSQL SQLSTATE on this exception, walking inner exceptions.</summary>
    public static string? SqlState(Exception? error)
    {
        var seen = new HashSet<Exception>(ReferenceEqualityComparer.Instance);
        for (var current = error; current is not null && seen.Add(current); current = current.InnerException)
        {
            if (current is PostgresException postgres && !string.IsNullOrEmpty(postgres.SqlState))
            {
                return postgres.SqlState;
            }
        }

        return null;
    }

    public static bool IsUniqueViolation(Exception error) => SqlState(error) == "23505";
}

public sealed class AppException : Exception
{
    public AppException(string message)
        : base(message)
    {
    }
}
