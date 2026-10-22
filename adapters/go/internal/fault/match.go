package fault

import (
	"regexp"
	"strings"
)

// Statement classes the tracer and the wire rewriter recognize.
// Root rollback must not match ROLLBACK TO SAVEPOINT.
var (
	rollbackTo   = regexp.MustCompile(`(?i)^rollback\s+to\b`)
	rootRollback = regexp.MustCompile(`(?i)^rollback\b`)
	commitStmt   = regexp.MustCompile(`(?i)^(commit|end)\b`)
	txControl    = regexp.MustCompile(`(?i)^(begin|start\s+transaction|commit|end|rollback|savepoint|release)\b`)
)

func normalize(sql string) string {
	return strings.TrimSpace(sql)
}

// IsRollbackTo reports a ROLLBACK TO [SAVEPOINT] statement.
func IsRollbackTo(sql string) bool {
	return rollbackTo.MatchString(normalize(sql))
}

// IsRootRollback reports a top-level ROLLBACK, not ROLLBACK TO.
func IsRootRollback(sql string) bool {
	s := normalize(sql)
	if IsRollbackTo(s) {
		return false
	}
	return rootRollback.MatchString(s)
}

// IsCommit reports COMMIT or END.
func IsCommit(sql string) bool {
	return commitStmt.MatchString(normalize(sql))
}

// IsTxControl reports a transaction-control statement worth tracing.
func IsTxControl(sql string) bool {
	return txControl.MatchString(normalize(sql))
}
