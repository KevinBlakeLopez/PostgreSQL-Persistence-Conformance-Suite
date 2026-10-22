package main

import (
	"context"
	"fmt"
	"os"

	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/pgxdb"
	"ppcs.local/go/internal/protocol"
	"ppcs.local/go/internal/run"
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
	pooled := msg.Mode == "pooled"
	pgxVersion := version.Module("github.com/jackc/pgx/v5")
	config := map[string]any{
		"api":    "pgx.Tx.Begin, Commit, and Rollback",
		"pool":   "single *pgx.Conn, replaced only after pgx closes it",
		"nested": "pgx.Tx.Begin is a savepoint",
		"pgx":    pgxVersion,
	}
	if pooled {
		config["pool"] = "pgxpool.Pool MaxConns = pool_max, MinConns = 0"
		config["api"] = "pgxpool.Pool.BeginTx, then pgxpool.Tx.Commit or Rollback, which Release the connection"
	}
	if err := p.Send(map[string]any{
		"type":          "hello",
		"adapter":       map[string]any{"name": "go-pgx-control", "version": "0.1.0"},
		"framework":     map[string]any{"name": "github.com/jackc/pgx/v5", "version": pgxVersion},
		"driver":        map[string]any{"name": "github.com/jackc/pgx/v5", "version": pgxVersion},
		"components":    map[string]any{},
		"runtime":       map[string]any{"name": "go", "version": version.Go()},
		"mode":          msg.Mode,
		"configuration": config,
	}); err != nil {
		return
	}
	state := &fault.State{}
	db, err := pgxdb.Open(context.Background(), msg.Connection, state, pooled, msg.Case.Settings.PoolMax)
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
