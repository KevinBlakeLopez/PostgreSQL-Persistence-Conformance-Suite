package gormdb

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/jackc/pgx/v5/stdlib"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/pgcfg"
	"ppcs.local/go/internal/protocol"
	"ppcs.local/go/internal/run"
)

// DB is GORM on a *sql.DB opened with pgx stdlib. managed uses DB.Transaction.
// explicit uses DB.Begin, DB.Commit, and DB.Rollback. Nested managed calls are
// DB.Transaction, which GORM implements as a savepoint. Nested explicit calls
// are SavePoint and RollbackTo.
type DB struct {
	gorm    *gorm.DB
	sql     *sql.DB
	state   *fault.State
	managed bool
}

func Open(conn protocol.Connection, state *fault.State, managed bool, poolMax int) (*DB, error) {
	if poolMax <= 0 {
		poolMax = 1
	}
	b := pgcfg.Builder{Connection: conn, State: state, Tracer: &fault.Tracer{State: state}}
	cfg, err := b.Config()
	if err != nil {
		return nil, err
	}
	connector := fault.NewConnector(stdlib.GetConnector(*cfg), state)
	sqlDB := sql.OpenDB(connector)
	sqlDB.SetMaxOpenConns(poolMax)
	sqlDB.SetMaxIdleConns(poolMax)
	gdb, err := gorm.Open(postgres.New(postgres.Config{Conn: sqlDB}), &gorm.Config{
		Logger: logger.Discard,
	})
	if err != nil {
		_ = sqlDB.Close()
		return nil, err
	}
	return &DB{gorm: gdb, sql: sqlDB, state: state, managed: managed}, nil
}

func (d *DB) Fault() *fault.State { return d.state }
func (d *DB) Reconnected() bool   { return false }
func (d *DB) Close()              { _ = d.sql.Close() }

func (d *DB) Surface() string {
	if d.managed {
		return "gorm-managed"
	}
	return "gorm-explicit"
}

func (d *DB) IsolationAPI() string {
	if d.managed {
		return "db.Transaction with sql.TxOptions.Isolation"
	}
	return "db.Begin with sql.TxOptions.Isolation"
}

func (d *DB) Run(ctx context.Context, isolation string, fn func(run.Tx) error) run.Completion {
	if isolation != "" && isolation != "serializable" {
		return run.Completion{BeginErr: fmt.Errorf("gorm adapter was asked for isolation %q", isolation)}
	}
	session := d.gorm.WithContext(ctx)
	if d.managed {
		return d.runManaged(session, isolation, fn)
	}
	return d.runExplicit(ctx, session, isolation, fn)
}

func (d *DB) runManaged(session *gorm.DB, isolation string, fn func(run.Tx) error) run.Completion {
	var comp run.Completion
	var err error
	call := func(tx *gorm.DB) error {
		comp.BodyErr = fn(&gtx{db: tx, managed: true})
		return comp.BodyErr
	}
	if isolation == "serializable" {
		err = session.Transaction(call, &sql.TxOptions{Isolation: sql.LevelSerializable})
	} else {
		err = session.Transaction(call)
	}
	if comp.BodyErr != nil {
		comp.RollbackCalled = true
		if err != nil && !sameErr(err, comp.BodyErr) {
			comp.RollbackErr = err
		}
		return comp
	}
	comp.CommitCalled = true
	comp.CommitErr = err
	return comp
}

func (d *DB) runExplicit(ctx context.Context, session *gorm.DB, isolation string, fn func(run.Tx) error) run.Completion {
	var tx *gorm.DB
	if isolation == "serializable" {
		tx = session.Begin(&sql.TxOptions{Isolation: sql.LevelSerializable})
	} else {
		tx = session.Begin()
	}
	if tx.Error != nil {
		return run.Completion{BeginErr: tx.Error}
	}
	return run.Finish(ctx, &gtx{db: tx, managed: false}, fn)
}

func sameErr(err, body error) bool {
	return err == body || (err != nil && body != nil && err.Error() == body.Error())
}

type gtx struct {
	db      *gorm.DB
	managed bool
}

func (t *gtx) InsertItem(_ context.Context, name string) error {
	return t.db.Exec("INSERT INTO item (name, qty) VALUES (?, 1)", name).Error
}

func (t *gtx) InsertTaken(context.Context) error {
	return t.db.Exec("INSERT INTO uniq (code) VALUES (?)", "taken").Error
}

func (t *gtx) ReadItem(_ context.Context, name string) error {
	var qty int
	return t.db.Raw("SELECT qty FROM item WHERE name = ?", name).Row().Scan(&qty)
}

func (t *gtx) Identify(context.Context) (string, int, string, error) {
	var xid, iso string
	var pid int
	err := t.db.Raw("SELECT pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')").Row().Scan(&xid, &pid, &iso)
	return xid, pid, iso, err
}

func (t *gtx) Commit(context.Context) error {
	return t.db.Commit().Error
}

func (t *gtx) Rollback(context.Context) error {
	return t.db.Rollback().Error
}

func (t *gtx) Nested(ctx context.Context, fn func(run.Tx) error) (error, error) {
	if t.managed {
		var fnErr error
		err := t.db.Transaction(func(inner *gorm.DB) error {
			fnErr = fn(&gtx{db: inner, managed: true})
			return fnErr
		})
		if fnErr != nil && err != nil && !sameErr(err, fnErr) {
			return fnErr, err
		}
		if fnErr == nil {
			return err, nil
		}
		return fnErr, nil
	}
	if err := t.db.SavePoint("ppcs_nested").Error; err != nil {
		return err, nil
	}
	fnErr := fn(t)
	if fnErr != nil {
		return fnErr, t.db.RollbackTo("ppcs_nested").Error
	}
	return nil, nil
}
