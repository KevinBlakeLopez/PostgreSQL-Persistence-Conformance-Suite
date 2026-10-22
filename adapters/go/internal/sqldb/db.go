package sqldb

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/jackc/pgx/v5/stdlib"
	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/pgcfg"
	"ppcs.local/go/internal/protocol"
	"ppcs.local/go/internal/run"
)

// DB is a database/sql pool on pgx's stdlib driver. MaxOpenConns is the case's
// pool_max. The driver wrapper sits under sql.Tx.Commit so a category D fault
// can discard a reply pgx has already parsed.
type DB struct {
	db    *sql.DB
	state *fault.State
}

func Open(conn protocol.Connection, state *fault.State, poolMax int) (*DB, error) {
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
	return &DB{db: sqlDB, state: state}, nil
}

func (d *DB) Fault() *fault.State { return d.state }
func (d *DB) Surface() string     { return "database/sql" }
func (d *DB) Reconnected() bool   { return false }
func (d *DB) IsolationAPI() string {
	return "sql.DB.BeginTx with sql.TxOptions.Isolation"
}
func (d *DB) Close() { _ = d.db.Close() }

func (d *DB) Run(ctx context.Context, isolation string, fn func(run.Tx) error) run.Completion {
	var opts *sql.TxOptions
	if isolation == "serializable" {
		opts = &sql.TxOptions{Isolation: sql.LevelSerializable}
	} else if isolation != "" {
		return run.Completion{BeginErr: fmt.Errorf("database/sql adapter was asked for isolation %q", isolation)}
	}
	tx, err := d.db.BeginTx(ctx, opts)
	if err != nil {
		return run.Completion{BeginErr: err}
	}
	return run.Finish(ctx, &sqlTx{tx: tx}, fn)
}

type sqlTx struct{ tx *sql.Tx }

func (t *sqlTx) InsertItem(ctx context.Context, name string) error {
	_, err := t.tx.ExecContext(ctx, "INSERT INTO item (name, qty) VALUES ($1, 1)", name)
	return err
}

func (t *sqlTx) InsertTaken(ctx context.Context) error {
	_, err := t.tx.ExecContext(ctx, "INSERT INTO uniq (code) VALUES ('taken')")
	return err
}

func (t *sqlTx) ReadItem(ctx context.Context, name string) error {
	var qty int
	return t.tx.QueryRowContext(ctx, "SELECT qty FROM item WHERE name = $1", name).Scan(&qty)
}

func (t *sqlTx) Identify(ctx context.Context) (string, int, string, error) {
	var xid, iso string
	var pid int
	err := t.tx.QueryRowContext(ctx, "SELECT pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')").Scan(&xid, &pid, &iso)
	return xid, pid, iso, err
}

func (t *sqlTx) Commit(ctx context.Context) error   { return t.tx.Commit() }
func (t *sqlTx) Rollback(ctx context.Context) error { return t.tx.Rollback() }

func (t *sqlTx) Nested(ctx context.Context, fn func(run.Tx) error) (error, error) {
	if _, err := t.tx.ExecContext(ctx, "SAVEPOINT ppcs_nested"); err != nil {
		return err, nil
	}
	fnErr := fn(t)
	if fnErr != nil {
		_, rbErr := t.tx.ExecContext(ctx, "ROLLBACK TO SAVEPOINT ppcs_nested")
		return fnErr, rbErr
	}
	_, err := t.tx.ExecContext(ctx, "RELEASE SAVEPOINT ppcs_nested")
	return err, nil
}
