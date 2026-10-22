package fault

import "testing"

func TestMatchers(t *testing.T) {
	cases := []struct {
		sql    string
		to     bool
		root   bool
		commit bool
	}{
		{"rollback", false, true, false},
		{"ROLLBACK", false, true, false},
		{"rollback;", false, true, false},
		{"rollback to savepoint sp_1", true, false, false},
		{"ROLLBACK TO SAVEPOINT sp123", true, false, false},
		{"commit", false, false, true},
		{"COMMIT", false, false, true},
		{"end", false, false, true},
		{"release savepoint sp_1", false, false, false},
		{"savepoint ppcs_nested", false, false, false},
		{"INSERT INTO item (name, qty) VALUES ($1, 1)", false, false, false},
	}
	for _, tc := range cases {
		if got := IsRollbackTo(tc.sql); got != tc.to {
			t.Errorf("IsRollbackTo(%q) = %v, want %v", tc.sql, got, tc.to)
		}
		if got := IsRootRollback(tc.sql); got != tc.root {
			t.Errorf("IsRootRollback(%q) = %v, want %v", tc.sql, got, tc.root)
		}
		if got := IsCommit(tc.sql); got != tc.commit {
			t.Errorf("IsCommit(%q) = %v, want %v", tc.sql, got, tc.commit)
		}
	}
}
