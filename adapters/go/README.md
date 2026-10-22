# Go adapters

One Go module, `adapters/go`, implements three PPCS adapters. They speak the protocol in `docs/protocol.md`. They do not have a separate harness.

| Adapter | Command | API |
| --- | --- | --- |
| `go-pgx-control` | `adapters/go-pgx-control/run` | pgx v5.11.0 `Conn.BeginTx` / `Tx.Commit`. `pooled` is `pgxpool.Pool` |
| `go-database-sql-control` | `adapters/go-database-sql-control/run` | `database/sql` with `github.com/jackc/pgx/v5/stdlib` |
| `gorm` | `adapters/gorm/run` | GORM v1.31.2. `managed` is `DB.Transaction`. `explicit` is `Begin` / `Commit` / `Rollback` |

Pinned versions are in `adapters/go/go.mod`: Go 1.27.3, pgx v5.11.0, `gorm.io/gorm` v1.31.2, `gorm.io/driver/postgres` v1.6.3. The GORM driver's own module requires pgx v5.10.0. This module selects v5.11.0 for all three binaries.

GORM's PostgreSQL dialector opens connections with pgx's `database/sql` driver (`stdlib.OpenDB`). This adapter passes that `*sql.DB` through `postgres.Config.Conn`. Native pgx does not go through `database/sql`.

From the repository root, with Go 1.27.3 on `PATH` and the disposable server up:

```sh
(cd adapters/go && go test ./...)
node harness/run.mjs --adapter=go-pgx-control,go-database-sql-control,gorm --repeat=3
```

The comparison is [`docs/go-persistence.md`](../../docs/go-persistence.md). The recording is [`reports/examples/2026-10-22T13-24-28Z-606909`](../../reports/examples/2026-10-22T13-24-28Z-606909/summary.md).
