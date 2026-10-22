package run

import (
	"context"

	"ppcs.local/go/internal/fault"
	"ppcs.local/go/internal/protocol"
)

// Tx is the transaction the case body uses. Each adapter implements it with that
// surface's ordinary API.
type Tx interface {
	InsertItem(ctx context.Context, name string) error
	InsertTaken(ctx context.Context) error
	ReadItem(ctx context.Context, name string) error
	Identify(ctx context.Context) (xid string, pid int, isolation string, err error)
	Nested(ctx context.Context, fn func(Tx) error) (fnErr error, rollbackErr error)
	Commit(ctx context.Context) error
	Rollback(ctx context.Context) error
}

// DB runs one outer transaction and exposes the fault and the tracer notes.
type DB interface {
	Run(ctx context.Context, isolation string, fn func(Tx) error) Completion
	Fault() *fault.State
	Close()
	Surface() string
	Reconnected() bool
	IsolationAPI() string
}

// Finish runs fn and then the explicit completion: rollback when fn returns an
// error, otherwise commit. A protocol error is still followed by a best-effort
// rollback so the connection is not left in the transaction.
func Finish(ctx context.Context, tx Tx, fn func(Tx) error) Completion {
	var c Completion
	err := fn(tx)
	if protocol.IsProtocol(err) {
		c.BodyErr = err
		c.RollbackCalled = true
		c.RollbackErr = tx.Rollback(ctx)
		return c
	}
	c.BodyErr = err
	if err != nil {
		c.RollbackCalled = true
		c.RollbackErr = tx.Rollback(ctx)
		return c
	}
	c.CommitCalled = true
	c.CommitErr = tx.Commit(ctx)
	return c
}
