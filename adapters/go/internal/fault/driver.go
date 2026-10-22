package fault

import (
	"context"
	"database/sql/driver"
	"errors"

	"github.com/jackc/pgx/v5/stdlib"
)

// LostCommit is the error category D returns in place of a parsed COMMIT.
// It does not wrap the parsed result: errors.Is(pgx.ErrTxCommitRollback) must be false.
type LostCommit struct{}

func (LostCommit) Error() string { return "connection lost after sending COMMIT" }

// Connector wraps pgx's database/sql connector. BeginTx returns a driver.Tx whose
// Commit can discard a reply pgx has already parsed. ResetSession and the other
// pgx stdlib methods stay promoted, so database/sql still discards a connection
// whose transaction status is not idle.
type Connector struct {
	driver.Connector
	state *State
}

func NewConnector(inner driver.Connector, state *State) driver.Connector {
	return &Connector{Connector: inner, state: state}
}

func (c *Connector) Connect(ctx context.Context) (driver.Conn, error) {
	raw, err := c.Connector.Connect(ctx)
	if err != nil {
		return nil, err
	}
	sc, ok := raw.(*stdlib.Conn)
	if !ok {
		return raw, nil
	}
	return &conn{Conn: sc, state: c.state}, nil
}

type conn struct {
	*stdlib.Conn
	state *State
}

func (c *conn) BeginTx(ctx context.Context, opts driver.TxOptions) (driver.Tx, error) {
	tx, err := c.Conn.BeginTx(ctx, opts)
	if err != nil {
		return nil, err
	}
	return &txWrap{Tx: tx, state: c.state, raw: c.Conn}, nil
}

type txWrap struct {
	driver.Tx
	state *State
	raw   *stdlib.Conn
}

// Commit runs pgx.Tx.Commit through the stdlib wrapper, which parses the command
// tag. When the category D fault is armed, that parsed result is discarded and
// the caller receives LostCommit. pgx.Tx.Commit has already returned; database/sql
// and GORM have not seen it yet.
func (t *txWrap) Commit() error {
	if t.state != nil && t.state.Take(KindCommit, ModeReplyLost) {
		err := t.Tx.Commit()
		if err == nil {
			t.state.NoteDiscarded("nil")
		} else {
			t.state.NoteDiscarded(err.Error())
		}
		if t.raw != nil {
			_ = t.raw.Close()
		}
		return LostCommit{}
	}
	return t.Tx.Commit()
}

// ErrBadConn reports whether database/sql should discard the connection.
func IsLost(err error) bool {
	return errors.Is(err, LostCommit{})
}
