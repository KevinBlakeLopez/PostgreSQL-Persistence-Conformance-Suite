package run

import (
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"ppcs.local/go/internal/fault"
)

// ErrApplication is the ordinary application failure CTL-01.rollback and TX-03 raise.
var ErrApplication = errors.New("application error: the request fails")

// ErrNested is the nested scope's application failure.
var ErrNested = errors.New("application error: the nested scope fails")

// ErrOuter is the outer scope's application failure after a nested scope completed.
var ErrOuter = errors.New("application error: the outer scope fails")

// ErrUnit is unit 1's application failure in TX-03.
var ErrUnit = errors.New("application error: unit 1 fails")

// Completion is what the transaction API did. It is not the database outcome.
type Completion struct {
	BeginErr       error
	BodyErr        error
	RollbackErr    error
	CommitErr      error
	CommitCalled   bool
	RollbackCalled bool
}

// APIError is the protocol's api_error object.
type APIError struct {
	Class   string  `json:"class"`
	Code    *string `json:"code"`
	Message string  `json:"message"`
}

func ErrorInfo(err error) *APIError {
	if err == nil {
		return nil
	}
	info := &APIError{Class: fmt.Sprintf("%T", err), Message: err.Error()}
	if errors.Is(err, pgx.ErrTxCommitRollback) {
		info.Class = "pgx.ErrTxCommitRollback"
	}
	if errors.Is(err, fault.LostCommit{}) {
		info.Class = "fault.LostCommit"
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code != "" {
		code := pgErr.Code
		info.Code = &code
		if info.Class != "pgx.ErrTxCommitRollback" {
			info.Class = "*pgconn.PgError"
		}
	}
	if len(info.Message) > 500 {
		info.Message = info.Message[:500]
	}
	return info
}

// Report maps a completion to the protocol's reported field.
// A nil Commit error is reported as committed. pgx.ErrTxCommitRollback is reported
// as rolled_back because that error asserts the transaction rolled back.
// Any other commit or rollback error is reported as failed: it does not assert an outcome.
// A body error whose rollback returned nil is reported as rolled_back.
func Report(surface string, c Completion) (reported, basis string, api *APIError) {
	switch surface {
	case "gorm-managed":
		return reportGormManaged(c)
	case "gorm-explicit":
		return reportExplicit("gorm.DB.Commit", "gorm.DB.Rollback", c)
	case "database/sql":
		return reportExplicit("sql.Tx.Commit", "sql.Tx.Rollback", c)
	default:
		return reportExplicit("pgx.Tx.Commit", "pgx.Tx.Rollback", c)
	}
}

func reportExplicit(commitName, rollbackName string, c Completion) (string, string, *APIError) {
	if c.BeginErr != nil {
		return "failed", "Begin returned an error", ErrorInfo(c.BeginErr)
	}
	if c.BodyErr != nil {
		if c.RollbackErr != nil {
			return "failed", rollbackName + " returned an error after the body failed. The error does not by itself assert that PostgreSQL rolled the transaction back.", ErrorInfo(c.RollbackErr)
		}
		return "rolled_back", "the body returned an error and " + rollbackName + " returned nil", ErrorInfo(c.BodyErr)
	}
	if !c.CommitCalled {
		return "failed", commitName + " was not called", nil
	}
	if c.CommitErr == nil {
		return "committed", commitName + " returned nil", nil
	}
	if errors.Is(c.CommitErr, pgx.ErrTxCommitRollback) {
		return "rolled_back", commitName + " returned pgx.ErrTxCommitRollback", ErrorInfo(c.CommitErr)
	}
	return "failed", commitName + " returned an error that does not assert a rollback", ErrorInfo(c.CommitErr)
}

func reportGormManaged(c Completion) (string, string, *APIError) {
	if c.BeginErr != nil {
		return "failed", "db.Transaction returned an error before the callback ran", ErrorInfo(c.BeginErr)
	}
	if c.BodyErr != nil {
		if c.RollbackErr != nil {
			return "failed", "the callback returned an error and db.Transaction returned a different error", ErrorInfo(c.RollbackErr)
		}
		return "rolled_back", "the callback returned an error. GORM v1.31.2 DB.Transaction rolls the transaction back and returns that error.", ErrorInfo(c.BodyErr)
	}
	if c.CommitErr == nil {
		return "committed", "db.Transaction returned nil", nil
	}
	if errors.Is(c.CommitErr, pgx.ErrTxCommitRollback) {
		return "rolled_back", "the callback returned nil and db.Transaction returned pgx.ErrTxCommitRollback", ErrorInfo(c.CommitErr)
	}
	return "failed", "the callback returned nil and db.Transaction returned an error that does not assert a rollback", ErrorInfo(c.CommitErr)
}
