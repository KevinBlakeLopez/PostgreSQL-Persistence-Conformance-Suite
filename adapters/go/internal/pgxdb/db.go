package pgxdb

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/pgcfg"
	"ppcs.local/go/internal/protocol"
	"ppcs.local/go/internal/run"
)

// DB is one pgx connection, or a pgxpool.Pool when pooled is set.
// The native mode is not a pool: it dials a *pgx.Conn and, after pgx closes it,
// dials a replacement for the next transaction. The pooled mode is pgxpool with
// MaxConns equal to the case's pool_max.
type DB struct {
	build       pgcfg.Builder
	state       *fault.State
	conn        *pgx.Conn
	pool        *pgxpool.Pool
	pooled      bool
	reconnected bool
}

func Open(ctx context.Context, conn protocol.Connection, state *fault.State, pooled bool, poolMax int) (*DB, error) {
	if poolMax <= 0 {
		poolMax = 1
	}
	b := pgcfg.Builder{Connection: conn, State: state, Tracer: &fault.Tracer{State: state}}
	db := &DB{build: b, state: state, pooled: pooled}
	if !pooled {
		return db, nil
	}
	cfg, err := b.Config()
	if err != nil {
		return nil, err
	}
	poolCfg, err := pgxpool.ParseConfig("sslmode=disable")
	if err != nil {
		return nil, err
	}
	poolCfg.ConnConfig.Host = cfg.Host
	poolCfg.ConnConfig.Port = cfg.Port
	poolCfg.ConnConfig.User = cfg.User
	poolCfg.ConnConfig.Password = cfg.Password
	poolCfg.ConnConfig.Database = cfg.Database
	poolCfg.ConnConfig.RuntimeParams = cfg.RuntimeParams
	poolCfg.ConnConfig.Tracer = cfg.Tracer
	poolCfg.ConnConfig.DialFunc = cfg.DialFunc
	poolCfg.ConnConfig.TLSConfig = cfg.TLSConfig
	poolCfg.MaxConns = int32(poolMax)
	poolCfg.MinConns = 0
	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, err
	}
	db.pool = pool
	return db, nil
}

func (d *DB) Fault() *fault.State { return d.state }
func (d *DB) Surface() string     { return "pgx" }
func (d *DB) Reconnected() bool   { return d.reconnected }
func (d *DB) IsolationAPI() string {
	return "pgx.Conn.BeginTx or pgxpool.Pool.BeginTx with TxOptions.IsoLevel"
}

func (d *DB) Close() {
	ctx := context.Background()
	if d.conn != nil {
		_ = d.conn.Close(ctx)
	}
	if d.pool != nil {
		d.pool.Close()
	}
}

func (d *DB) Run(ctx context.Context, isolation string, fn func(run.Tx) error) run.Completion {
	tx, err := d.begin(ctx, isolation)
	if err != nil {
		return run.Completion{BeginErr: err}
	}
	return run.Finish(ctx, tx, fn)
}

func (d *DB) begin(ctx context.Context, isolation string) (run.Tx, error) {
	var opts pgx.TxOptions
	if isolation == "serializable" {
		opts.IsoLevel = pgx.Serializable
	} else if isolation != "" {
		return nil, fmt.Errorf("pgx adapter was asked for isolation %q", isolation)
	}
	if d.pooled {
		tx, err := d.pool.BeginTx(ctx, opts)
		if err != nil {
			return nil, err
		}
		return &pgxTx{tx: tx}, nil
	}
	if d.conn == nil || d.conn.IsClosed() {
		if d.conn != nil {
			d.reconnected = true
		}
		cfg, err := d.build.Config()
		if err != nil {
			return nil, err
		}
		c, err := pgx.ConnectConfig(ctx, cfg)
		if err != nil {
			return nil, err
		}
		d.conn = c
	}
	tx, err := d.conn.BeginTx(ctx, opts)
	if err != nil {
		return nil, err
	}
	return &pgxTx{tx: tx}, nil
}

type pgxTx struct {
	tx pgx.Tx
}

func (t *pgxTx) InsertItem(ctx context.Context, name string) error {
	_, err := t.tx.Exec(ctx, "INSERT INTO item (name, qty) VALUES ($1, 1)", name)
	return err
}

func (t *pgxTx) InsertTaken(ctx context.Context) error {
	_, err := t.tx.Exec(ctx, "INSERT INTO uniq (code) VALUES ('taken')")
	return err
}

func (t *pgxTx) ReadItem(ctx context.Context, name string) error {
	var qty int
	return t.tx.QueryRow(ctx, "SELECT qty FROM item WHERE name = $1", name).Scan(&qty)
}

func (t *pgxTx) Identify(ctx context.Context) (string, int, string, error) {
	var xid, iso string
	var pid int
	err := t.tx.QueryRow(ctx, "SELECT pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')").Scan(&xid, &pid, &iso)
	return xid, pid, iso, err
}

func (t *pgxTx) Commit(ctx context.Context) error   { return t.tx.Commit(ctx) }
func (t *pgxTx) Rollback(ctx context.Context) error { return t.tx.Rollback(ctx) }

func (t *pgxTx) Nested(ctx context.Context, fn func(run.Tx) error) (error, error) {
	sp, err := t.tx.Begin(ctx)
	if err != nil {
		return err, nil
	}
	fnErr := fn(&pgxTx{tx: sp})
	if fnErr != nil {
		return fnErr, sp.Rollback(ctx)
	}
	return sp.Commit(ctx), nil
}
