package run

import (
	"errors"
	"testing"

	"github.com/jackc/pgx/v5"
	"ppcs.local/go/internal/fault"
)

func TestReportCommitTag(t *testing.T) {
	reported, _, api := Report("pgx", Completion{CommitCalled: true, CommitErr: pgx.ErrTxCommitRollback})
	if reported != "rolled_back" {
		t.Fatalf("reported %s", reported)
	}
	if api == nil || api.Class != "pgx.ErrTxCommitRollback" {
		t.Fatalf("api %#v", api)
	}
	reported, _, _ = Report("database/sql", Completion{CommitCalled: true})
	if reported != "committed" {
		t.Fatalf("nil commit reported %s", reported)
	}
	reported, _, api = Report("gorm-managed", Completion{CommitCalled: true, CommitErr: fault.LostCommit{}})
	if reported != "failed" {
		t.Fatalf("lost commit reported %s", reported)
	}
	if api == nil || api.Class != "fault.LostCommit" {
		t.Fatalf("lost class %#v", api)
	}
	if errors.Is(fault.LostCommit{}, pgx.ErrTxCommitRollback) {
		t.Fatal("lost commit must not assert a rollback")
	}
}

func TestReportBodyRollback(t *testing.T) {
	reported, _, api := Report("pgx", Completion{BodyErr: ErrApplication, RollbackCalled: true})
	if reported != "rolled_back" || api == nil || api.Message != ErrApplication.Error() {
		t.Fatalf("reported %s api %#v", reported, api)
	}
	reported, _, _ = Report("gorm-managed", Completion{BodyErr: ErrApplication, RollbackCalled: true})
	if reported != "rolled_back" {
		t.Fatalf("gorm body %s", reported)
	}
}
