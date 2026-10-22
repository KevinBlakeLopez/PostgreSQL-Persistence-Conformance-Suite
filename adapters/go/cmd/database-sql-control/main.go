package main

import (
	"fmt"
	"os"

	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/protocol"
	"ppcs.local/go/internal/run"
	"ppcs.local/go/internal/sqldb"
	"ppcs.local/go/internal/version"
)

func main() {
	p := protocol.New()
	msg, err := p.Read()
	if err != nil {
		fail(p, err)
		return
	}
	if msg.Type != "case" {
		fail(p, fmt.Errorf("expected a case message"))
		return
	}
	pgxVersion := version.Module("github.com/jackc/pgx/v5")
	if err := p.Send(map[string]any{
		"type":      "hello",
		"adapter":   map[string]any{"name": "go-database-sql-control", "version": "0.1.0"},
		"framework": map[string]any{"name": "database/sql", "version": version.Go()},
		"driver":    map[string]any{"name": "github.com/jackc/pgx/v5/stdlib", "version": pgxVersion},
		"components": map[string]any{
			"github.com/jackc/pgx/v5": pgxVersion,
		},
		"runtime": map[string]any{"name": "go", "version": version.Go()},
		"mode":    msg.Mode,
		"configuration": map[string]any{
			"api":    "sql.DB.BeginTx, sql.Tx.Commit, and sql.Tx.Rollback",
			"pool":   "database/sql pool, MaxOpenConns = pool_max",
			"nested": "SAVEPOINT / ROLLBACK TO SAVEPOINT / RELEASE SAVEPOINT as SQL. database/sql has no savepoint type.",
			"driver": "pgx stdlib wrapTx.Commit calls pgx.Tx.Commit",
		},
	}); err != nil {
		return
	}
	state := &fault.State{}
	db, err := sqldb.Open(msg.Connection, state, msg.Case.Settings.PoolMax)
	if err != nil {
		fail(p, err)
		return
	}
	defer db.Close()
	res, err := run.Execute(p, db, msg)
	if err != nil {
		fail(p, err)
		return
	}
	if err := p.Checkpoint("after-end", "", 0, ""); err != nil {
		fail(p, err)
		return
	}
	_ = p.Send(res.Fields())
}

func fail(p *protocol.Protocol, err error) {
	_ = p.Send(map[string]any{
		"type":   "result",
		"status": "error",
		"error":  map[string]any{"class": fmt.Sprintf("%T", err), "message": err.Error()},
	})
	os.Exit(1)
}
