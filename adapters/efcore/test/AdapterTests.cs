using System.Text.Json;

namespace Ppcs.EfCore.Tests;

public class ManifestTests
{
    [Fact]
    public void Every_catalog_case_is_implemented_or_unsupported()
    {
        var root = RepoRoot();
        using var manifest = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "adapters/efcore/adapter.json")));
        var implemented = manifest.RootElement.GetProperty("implements").EnumerateArray().Select(item => item.GetString()).ToHashSet();
        var unsupported = manifest.RootElement.GetProperty("unsupported").EnumerateObject().Select(item => item.Name).ToHashSet();
        var intentional = new HashSet<string> { "TX-01B.commit-reply-discarded" };
        foreach (var id in CatalogIds(root))
        {
            Assert.True(implemented.Contains(id) || unsupported.Contains(id) || intentional.Contains(id), id);
        }
    }

    [Fact]
    public void The_migration_type_is_attributed_to_the_migration_context()
    {
        var attribute = typeof(M1Migration).GetCustomAttributes(inherit: false)
            .Single(item => item.GetType().Name == "MigrationAttribute");
        var id = attribute.GetType().GetProperty("Id")?.GetValue(attribute) as string;
        Assert.Equal("1_m1", id);
        Assert.True(typeof(MigrationDbContext).IsSubclassOf(typeof(Microsoft.EntityFrameworkCore.DbContext)));
    }

    private static string RepoRoot()
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

        throw new InvalidOperationException("repository root was not found");
    }

    private static HashSet<string> CatalogIds(string root)
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
}
