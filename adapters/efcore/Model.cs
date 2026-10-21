using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Microsoft.EntityFrameworkCore.Migrations;

namespace Ppcs.EfCore;

public sealed class Item
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public int Qty { get; set; }
}

public sealed class Uniq
{
    public int Id { get; set; }
    public string Code { get; set; } = "";
}

public sealed class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options)
        : base(options)
    {
    }

    public DbSet<Item> Items => Set<Item>();
    public DbSet<Uniq> Uniqs => Set<Uniq>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Item>(MapItem);
        modelBuilder.Entity<Uniq>(MapUniq);
    }

    private static void MapItem(EntityTypeBuilder<Item> entity)
    {
        entity.ToTable("item");
        entity.Property(item => item.Id).HasColumnName("id").ValueGeneratedOnAdd();
        entity.Property(item => item.Name).HasColumnName("name").IsRequired();
        entity.Property(item => item.Qty).HasColumnName("qty");
    }

    private static void MapUniq(EntityTypeBuilder<Uniq> entity)
    {
        entity.ToTable("uniq");
        entity.Property(uniq => uniq.Id).HasColumnName("id").ValueGeneratedOnAdd();
        entity.Property(uniq => uniq.Code).HasColumnName("code").IsRequired();
        entity.HasIndex(uniq => uniq.Code).IsUnique();
    }
}

/// <summary>
/// Empty model. The runner already created <c>item</c> and <c>uniq</c>.
/// This context only executes the case migration through <c>Database.Migrate</c>.
/// </summary>
public sealed class MigrationDbContext : DbContext
{
    public MigrationDbContext(DbContextOptions<MigrationDbContext> options)
        : base(options)
    {
    }
}

[DbContextAttribute(typeof(MigrationDbContext))]
[Migration("1_m1")]
public sealed class M1Migration : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql("insert into item (name) values (current_setting('ppcs.marker'));");
        migrationBuilder.Sql(
            """
            do $ppcs$
            begin
              if current_setting('ppcs.hold', true) = 'true' then
                perform pg_advisory_xact_lock(current_setting('ppcs.gate')::bigint);
              end if;
            end
            $ppcs$;
            """);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql(
            """
            do $ppcs$
            begin
              if current_setting('ppcs.reversal', true) = 'none' then
                raise exception 'the migration has no reversal';
              end if;
              delete from item where name = current_setting('ppcs.marker');
              insert into ppcs_undo (name) values (current_setting('ppcs.marker'));
              if current_setting('ppcs.reversal', true) = 'partial-then-error' then
                raise exception 'the reversal failed on purpose after deleting the marker';
              end if;
            end
            $ppcs$;
            """);
    }
}

[DbContextAttribute(typeof(MigrationDbContext))]
public sealed class MigrationDbContextModelSnapshot : ModelSnapshot
{
    protected override void BuildModel(ModelBuilder modelBuilder)
    {
        modelBuilder.HasAnnotation("ProductVersion", "10.0.13");
    }
}
