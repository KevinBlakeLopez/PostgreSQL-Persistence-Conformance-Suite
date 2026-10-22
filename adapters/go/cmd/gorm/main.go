package main

import (
	"fmt"
	"os"

	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/gormdb"
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
	managed := msg.Mode == "managed"
	pgxVersion := version.Module("github.com/jackc/pgx/v5")
	gormVersion := version.Module("gorm.io/gorm")
	driverVersion := version.Module("gorm.io/driver/postgres")
	api := "db.Begin, db.Commit, and db.Rollback. Nested scopes use SavePoint and RollbackTo."
	if managed {
		api = "db.Transaction. A nested db.Transaction is a savepoint. DisableNestedTransaction is left at its default, false."
	}
	if err := p.Send(map[string]any{
		"type":      "hello",
		"adapter":   map[string]any{"name": "gorm", "version": "0.1.0"},
		"framework": map[string]any{"name": "gorm.io/gorm", "version": gormVersion},
		"driver":    map[string]any{"name": "gorm.io/driver/postgres", "version": driverVersion},
		"components": map[string]any{
			"database/sql":            version.Go(),
			"github.com/jackc/pgx/v5": pgxVersion,
		},
		"runtime": map[string]any{"name": "go", "version": version.Go()},
		"mode":    msg.Mode,
		"configuration": map[string]any{
			"api":       api,
			"pool":      "database/sql pool under GORM, MaxOpenConns = pool_max. Not pgxpool.",
			"connector": "postgres.Config.Conn is a *sql.DB opened with pgx stdlib. GORM's DSN path uses the same driver.",
			"logger":    "logger.Discard, so GORM does not write on the protocol stdout",
		},
	}); err != nil {
		return
	}
	state := &fault.State{}
	db, err := gormdb.Open(msg.Connection, state, managed, msg.Case.Settings.PoolMax)
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
