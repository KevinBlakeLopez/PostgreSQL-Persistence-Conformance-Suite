package fault

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

type sqlKey struct{}

// Tracer is a pgx.QueryTracer. It records transaction-control statements and,
// when a category C fault is armed, injects it inside Conn.Exec:
//
//   - client-reject returns an already-cancelled context from TraceQueryStart.
//     pgx calls TraceQueryStart before it sends. For a statement with no
//     parameters, pgconn.Exec checks that context and returns before SendQuery.
//     The server does not see the statement. The connection stays open.
//   - rewrite lets the statement through. The wire connection replaces the SQL.
//     TraceQueryEnd runs after pgx has parsed the reply and before Conn.Exec
//     returns that reply to Tx.Rollback or to database/sql.
//
// Category D is not done here. Conn.Exec has already chosen its return value
// before TraceQueryEnd returns, so a tracer cannot hide a parsed COMMIT from
// pgx.Tx.Commit. database/sql hides it in the driver.Tx wrapper instead.
type Tracer struct {
	State *State
}

func (t *Tracer) TraceQueryStart(ctx context.Context, _ *pgx.Conn, data pgx.TraceQueryStartData) context.Context {
	sql := normalize(data.SQL)
	ctx = context.WithValue(ctx, sqlKey{}, sql)
	if t.State == nil {
		return ctx
	}
	if t.State.Peek(KindSavepoint, ModeClientReject) && IsRollbackTo(sql) {
		t.State.Withhold(sql)
		return cancelled(sql)
	}
	if t.State.Peek(KindRoot, ModeClientReject) && IsRootRollback(sql) {
		t.State.Withhold(sql)
		return cancelled(sql)
	}
	return ctx
}

func (t *Tracer) TraceQueryEnd(ctx context.Context, _ *pgx.Conn, data pgx.TraceQueryEndData) {
	if t.State == nil {
		return
	}
	sql, _ := ctx.Value(sqlKey{}).(string)
	if sql == "" {
		return
	}
	note := Note{SQL: sql}
	if tag := data.CommandTag.String(); tag != "" {
		note.CommandTag = tag
	}
	if data.Err != nil {
		note.Error = data.Err.Error()
	}
	if IsTxControl(sql) || data.Err != nil && (IsRollbackTo(sql) || IsRootRollback(sql) || IsCommit(sql)) {
		t.State.AddNote(note)
	}
	if t.State.Peek(KindSavepoint, ModeRewrite) && IsRollbackTo(sql) {
		code := "ok"
		var pgErr *pgconn.PgError
		if errors.As(data.Err, &pgErr) && pgErr.Code != "" {
			code = pgErr.Code
		} else if data.Err != nil {
			code = "error"
		}
		t.State.NoteReply(code)
	}
}

func cancelled(sql string) context.Context {
	dead, cancel := context.WithCancel(context.Background())
	cancel()
	return context.WithValue(dead, sqlKey{}, sql)
}
