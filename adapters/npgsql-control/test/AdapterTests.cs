using System.Text;
using System.Text.Json;
using Ppcs;
using Ppcs.NpgsqlControl;

namespace Ppcs.NpgsqlControl.Tests;

public class DecisionTests
{
    [Fact]
    public void Correct_reports_rolled_back_when_the_probe_failed_and_commit_returned()
    {
        var result = Decisions.Map(Commit(correct: true, probe: "failed", commitReturned: true));
        Assert.Equal("rolled_back", result.Reported);
        Assert.False(result.DiscardConnection);
        Assert.Contains("25P02", result.Basis);
        Assert.Contains("command tag", result.Basis);
    }

    [Fact]
    public void Correct_reports_committed_only_when_the_probe_was_queryable()
    {
        var result = Decisions.Map(Commit(correct: true, probe: "queryable", commitReturned: true));
        Assert.Equal("committed", result.Reported);
        Assert.False(result.DiscardConnection);
    }

    [Fact]
    public void Correct_does_not_report_a_commit_when_the_probe_was_unreadable()
    {
        var result = Decisions.Map(Commit(correct: true, probe: "unreadable", commitReturned: true));
        Assert.Equal("failed", result.Reported);
        Assert.True(result.DiscardConnection);
    }

    [Fact]
    public void Correct_reports_failed_when_commit_throws()
    {
        var result = Decisions.Map(Commit(correct: true, probe: "queryable", commitReturned: false));
        Assert.Equal("failed", result.Reported);
        Assert.True(result.DiscardConnection);
    }

    [Fact]
    public void Unsafe_reports_committed_when_commit_returns_without_a_probe()
    {
        var result = Decisions.Map(Commit(correct: false, probe: "not-run", commitReturned: true, savepointFailed: true));
        Assert.Equal("committed", result.Reported);
        Assert.Contains("savepoint", result.Basis);
    }

    [Fact]
    public void Unsafe_reports_rolled_back_when_commit_throws()
    {
        var result = Decisions.Map(Commit(correct: false, probe: "not-run", commitReturned: false));
        Assert.Equal("rolled_back", result.Reported);
        Assert.False(result.DiscardConnection);
    }

    [Fact]
    public void A_body_failure_with_a_successful_rollback_is_rolled_back()
    {
        var result = Decisions.Map(new Decisions.Input(
            Correct: true,
            BodyFailed: true,
            SavepointRollbackFailed: false,
            Probe: "not-run",
            RollbackAttempted: true,
            RollbackReturned: true,
            CommitAttempted: false,
            CommitReturned: false,
            RecoveryCommitAttempted: false,
            RecoveryCommitReturned: false));
        Assert.Equal("rolled_back", result.Reported);
        Assert.False(result.DiscardConnection);
    }

    [Fact]
    public void Correct_discards_the_connection_when_rollback_throws()
    {
        var result = Decisions.Map(new Decisions.Input(
            Correct: true,
            BodyFailed: true,
            SavepointRollbackFailed: false,
            Probe: "not-run",
            RollbackAttempted: true,
            RollbackReturned: false,
            CommitAttempted: false,
            CommitReturned: false,
            RecoveryCommitAttempted: false,
            RecoveryCommitReturned: false));
        Assert.Equal("failed", result.Reported);
        Assert.True(result.DiscardConnection);
    }

    private static Decisions.Input Commit(bool correct, string probe, bool commitReturned, bool savepointFailed = false)
        => new(
            Correct: correct,
            BodyFailed: false,
            SavepointRollbackFailed: savepointFailed,
            Probe: probe,
            RollbackAttempted: false,
            RollbackReturned: false,
            CommitAttempted: true,
            CommitReturned: commitReturned,
            RecoveryCommitAttempted: false,
            RecoveryCommitReturned: false);
}

public class FaultTests
{
    [Fact]
    public void A_fault_fires_once()
    {
        var fault = new Fault();
        fault.Arm(Fault.Root, "client-reject");
        Assert.True(fault.Take(Fault.Root));
        Assert.False(fault.Take(Fault.Root));
        Assert.Equal(1, fault.Report()["fired"]);
    }

    [Fact]
    public void A_savepoint_fault_does_not_take_a_root_rollback()
    {
        var fault = new Fault();
        fault.Arm(Fault.Savepoint, "rewrite");
        Assert.False(fault.Take(Fault.Root));
        Assert.True(fault.Take(Fault.Savepoint));
    }
}

public class ProtocolTests
{
    [Fact]
    public void Checkpoint_writes_a_protocol_line_and_reads_the_resume()
    {
        var resume = "{\"ppcs\":1,\"type\":\"resume\",\"name\":\"before-end\",\"actions\":[]}\n";
        using var input = new MemoryStream(Encoding.UTF8.GetBytes(resume));
        using var output = new MemoryStream();
        var protocol = new Protocol(input, output);
        var message = protocol.Checkpoint("before-end", "1165", 7, "serializable");
        Assert.Equal("resume", message.GetProperty("type").GetString());
        output.Position = 0;
        using var sent = JsonDocument.Parse(new StreamReader(output).ReadLine()!);
        Assert.Equal(1, sent.RootElement.GetProperty("ppcs").GetInt32());
        Assert.Equal("checkpoint", sent.RootElement.GetProperty("type").GetString());
        Assert.Equal("1165", sent.RootElement.GetProperty("xid").GetString());
        Assert.Equal(7, sent.RootElement.GetProperty("pid").GetInt32());
        Assert.Equal("serializable", sent.RootElement.GetProperty("transaction_isolation").GetString());
    }
}

public class ManifestTests
{
    [Fact]
    public void Every_catalog_case_is_implemented_unsupported_or_an_intentional_not_run()
    {
        var root = RepoRoot();
        var manifest = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "adapters/npgsql-control/adapter.json")));
        var implemented = Ids(manifest.RootElement, "implements");
        var unsupported = manifest.RootElement.GetProperty("unsupported").EnumerateObject().Select(item => item.Name).ToHashSet();
        var intentional = new HashSet<string> { "TX-01B.commit-reply-discarded" };
        foreach (var id in CatalogIds(root))
        {
            Assert.True(implemented.Contains(id) || unsupported.Contains(id) || intentional.Contains(id), id);
        }
    }

    internal static string RepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "specifications", "transactions.v1.json")))
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        throw new InvalidOperationException("repository root was not found from " + AppContext.BaseDirectory);
    }

    internal static HashSet<string> CatalogIds(string root)
    {
        var ids = new HashSet<string>();
        foreach (var file in new[] { "transactions.v1.json", "migrations.v1.json" })
        {
            using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "specifications", file)));
            foreach (var kase in document.RootElement.GetProperty("cases").EnumerateArray())
            {
                ids.Add(kase.GetProperty("id").GetString()!);
            }
        }

        return ids;
    }

    internal static HashSet<string> Ids(JsonElement manifest, string property)
        => manifest.GetProperty(property).EnumerateArray().Select(item => item.GetString()!).ToHashSet();
}
