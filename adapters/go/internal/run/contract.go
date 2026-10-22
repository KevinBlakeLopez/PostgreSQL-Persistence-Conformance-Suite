package run

// Contracts are the texts a FAIL quotes. They describe the pinned sources.
const (
	contractPgx = "pgx v5.11.0 Tx.Commit (tx.go, dbTx.Commit) executes COMMIT and returns ErrTxCommitRollback when the command tag is ROLLBACK. " +
		"The Tx interface documents that a commit which fails with a rollback status returns an error where errors.Is(ErrTxCommitRollback) is true. " +
		"ErrTxCommitRollback's comment says PostgreSQL accepts COMMIT on an aborted transaction and treats it as ROLLBACK. " +
		"A nil error is pgx's report that the transaction committed. " +
		"dbTx.Rollback executes ROLLBACK and, on any error, calls Conn.die, which closes the connection. " +
		"A nested Tx.Begin is a savepoint. Nested Rollback executes ROLLBACK TO SAVEPOINT and does not close the connection."

	contractSQL = "Go database/sql Tx.Commit returns the error from driver.Tx.Commit and does not add a command tag (database/sql/sql.go). " +
		"pgx stdlib v5.11.0 wrapTx.Commit calls pgx.Tx.Commit and returns that error (stdlib/sql.go). " +
		"A nil error is database/sql's report that the transaction committed. " +
		"pgx.ErrTxCommitRollback therefore reaches the caller as a non-nil error. " +
		"stdlib Conn.ResetSession returns driver.ErrBadConn when pgx's transaction status is not idle, so the pool discards that connection before the next checkout. " +
		"database/sql has no savepoint type. This control sends SAVEPOINT, ROLLBACK TO SAVEPOINT, and RELEASE SAVEPOINT as SQL."

	contractGormManaged = "GORM v1.31.2 DB.Transaction (finisher_api.go) commits when the callback returns nil and returns tx.Commit().Error. " +
		"Its comment says: return error will rollback, otherwise to commit. A nil return is GORM's report that the transaction committed. " +
		"A non-nil return is not a successful commit. " +
		"gorm.io/driver/postgres v1.6.3 opens the pool with pgx stdlib (postgres.go Initialize) unless Config.Conn is set. " +
		"This adapter passes a *sql.DB opened on pgx stdlib, which is the supported Config.Conn path, so the pool limits and the tracer sit under GORM. " +
		"A nested DB.Transaction is a savepoint when DisableNestedTransaction is false, which is the default. " +
		"The postgres dialector's SavePoint and RollbackTo call Exec and return nil, ignoring the *gorm.DB that Exec returns."

	contractGormExplicit = "GORM v1.31.2 DB.Begin starts a transaction and DB.Commit calls the underlying Tx.Commit and stores its error (finisher_api.go). " +
		"A nil DB.Error after Commit is GORM's report that the transaction committed. " +
		"gorm.io/driver/postgres v1.6.3 uses pgx stdlib. This adapter passes *sql.DB through Config.Conn. " +
		"SavePoint and RollbackTo are the explicit savepoint API. The postgres dialector executes the SQL and returns nil from SavePoint and RollbackTo."
)

func contractFor(surface string) string {
	switch surface {
	case "database/sql":
		return contractSQL
	case "gorm-managed":
		return contractGormManaged
	case "gorm-explicit":
		return contractGormExplicit
	default:
		return contractPgx
	}
}
