package org.ppcs.jdbccontrol;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;

import org.postgresql.core.TransactionState;
import org.postgresql.jdbc.PgConnection;

/**
 * Two transaction policies. They share no completion method.
 *
 * <pre>
 *                                  correct                                      unsafe
 *   driver state FAILED at commit  Connection.commit(), then rolled_back       Connection.commit() returning is committed
 *   commit() throws               failed, connection closed                    rolled_back
 *   rollback(Savepoint) fails     outer Connection.rollback(), not commit      commit anyway
 *   rollback() throws             connection closed, autocommit left alone     setAutoCommit(true), connection kept
 *   isolation requested           Connection.setTransactionIsolation           not called
 *   write before a savepoint      sent before setSavepoint                     sent inside the savepoint
 * </pre>
 *
 * <p>Neither policy calls {@code setAutoCommit(true)} after a successful commit. pgjdbc 42.7.14
 * {@code PgConnection.setAutoCommit(true)} calls {@code commit()} when auto-commit is off
 * ({@code PgConnection.java} lines 985-987). Java 21 {@code Connection.setAutoCommit} says that
 * changing auto-commit during a transaction commits that transaction.
 */
final class Policy {
    private Policy() {}

    /** What the case does inside one transaction. */
    @FunctionalInterface
    interface Work {
        void run(Connection connection) throws Throwable;
    }

    /** Set by a failed {@code Connection.rollback(Savepoint)}. The outer completion reads it. */
    static final class Scope {
        boolean rollbackOnly;
        Map<String, Object> rollbackError;
    }

    static final class Outcome {
        final String reported;
        final String basis;
        final Map<String, Object> apiError;
        final String commitStateBefore;
        final boolean discarded;
        final boolean autocommitRestored;
        final Map<String, Object> bodyError;
        final Map<String, Object> cleanupError;

        Outcome(String reported, String basis, Map<String, Object> apiError, String commitStateBefore,
                boolean discarded, boolean autocommitRestored, Map<String, Object> bodyError, Map<String, Object> cleanupError) {
            this.reported = reported;
            this.basis = basis;
            this.apiError = apiError;
            this.commitStateBefore = commitStateBefore;
            this.discarded = discarded;
            this.autocommitRestored = autocommitRestored;
            this.bodyError = bodyError;
            this.cleanupError = cleanupError;
        }
    }

    /**
     * Positive control. Reads {@link PgConnection#getTransactionState()} before
     * {@link Connection#commit()}. That method is public on the driver class. {@code Connection.commit()}
     * is void and does not return a command tag: pgjdbc 42.7.14 {@code TransactionCommandHandler}
     * does not implement {@code handleCommandStatus}.
     */
    static final class Correct {
        static final String CONTRACT = "The correct jdbc-control policy uses Connection.setAutoCommit(false), Connection.commit, Connection.rollback, "
                + "Connection.setSavepoint, Connection.rollback(Savepoint), and Connection.setTransactionIsolation. "
                + "Java 21 Connection.commit() is void: \"Makes all changes made since the previous commit/rollback permanent and releases any database locks currently held by this Connection object.\" "
                + "It does not return a command tag. pgjdbc 42.7.14 PgConnection.commit sends COMMIT through executeTransactionCommand when getTransactionState() is not IDLE, and TransactionCommandHandler does not implement handleCommandStatus, so a COMMIT that PostgreSQL answers with the command tag ROLLBACK does not throw. "
                + "Before commit(), the policy reads PgConnection.getTransactionState(), a public method. FAILED means the server has already sent ReadyForQuery status E (QueryExecutorImpl.receiveRFQ). "
                + "If that state was FAILED and commit() returns, the policy reports rolled_back. It does not claim to have read the command tag. If commit() throws, the policy reports failed and closes the connection. "
                + "If Connection.rollback() throws, the policy closes the connection and does not call setAutoCommit(true). "
                + "Java 21 Connection.setAutoCommit says: \"If this method is called during a transaction and the auto-commit mode is changed, the transaction is committed.\" "
                + "pgjdbc 42.7.14 implements the change to true by calling commit() (PgConnection.setAutoCommit). "
                + "A failed Connection.rollback(Savepoint) is followed by Connection.rollback() of the surrounding transaction, not by Connection.commit(). "
                + "A requested isolation level is sent with Connection.setTransactionIsolation before setAutoCommit(false), while the driver state is IDLE.";

        private Correct() {}

        static boolean requestsIsolation() {
            return true;
        }

        static boolean defersOuterWrite() {
            return false;
        }

        static Outcome finish(Sessions sessions, Connection connection, Throwable bodyError, Scope scope) {
            if (bodyError != null) {
                return afterBodyFailure(sessions, connection, bodyError);
            }
            if (scope.rollbackOnly) {
                SqlFailure rollback = rollback(connection);
                if (rollback.failed()) {
                    sessions.discard();
                    return failed("a savepoint rollback had failed, and Connection.rollback() of the surrounding transaction also threw; the connection was closed",
                            rollback.error, null, true, false, null, errInfo(rollback.error));
                }
                return rolledBack("a savepoint rollback had failed, so the policy ended the transaction with Connection.rollback() instead of Connection.commit()",
                        rolledBackError("a savepoint rollback failed, so the transaction was rolled back"), null, false, false);
            }
            String before = transactionState(connection);
            sessions.note("commit state before=" + before);
            try {
                connection.commit();
            } catch (SQLException ex) {
                sessions.discard();
                sessions.note("Connection.commit() threw; connection closed");
                return failed("Connection.commit() threw. The policy reports failed and closes the connection. It does not report a confirmed rollback.",
                        ex, before, true, false, null, errInfo(ex));
            }
            if ("FAILED".equals(before)) {
                return rolledBack("PgConnection.getTransactionState() was FAILED before Connection.commit(), and commit() returned. "
                                + "FAILED is ReadyForQuery status E. commit() does not expose the command tag. The policy reports rolled_back.",
                        rolledBackError("the driver transaction state was FAILED before Connection.commit() returned"), before, false, false);
            }
            if (!"OPEN".equals(before)) {
                sessions.discard();
                return failed("Connection.commit() returned, but the driver state before the call was " + before + ", not OPEN. The policy does not report a commit.",
                        new SQLException("driver transaction state before commit was " + before), before, true, false, null, null);
            }
            return committed("Connection.commit() returned and PgConnection.getTransactionState() was OPEN before the call. The command tag is not exposed.", before);
        }

        private static Outcome afterBodyFailure(Sessions sessions, Connection connection, Throwable bodyError) {
            SqlFailure rollback = rollback(connection);
            if (rollback.failed()) {
                sessions.discard();
                return failed("the body threw and Connection.rollback() threw. The connection was closed. setAutoCommit(true) was not called.",
                        rollback.error, null, true, false, errInfo(bodyError), errInfo(rollback.error));
            }
            return rolledBack("the body threw and Connection.rollback() returned", errInfo(bodyError), null, false, false);
        }
    }

    /**
     * Negative control. The defects are the ones the cases already name: an unchecked commit return,
     * a commit after a failed savepoint rollback, {@code setAutoCommit(true)} after a failed rollback,
     * a dropped isolation level, and a write moved into a savepoint.
     */
    static final class Unsafe {
        static final String CONTRACT = "The unsafe jdbc-control policy reports committed whenever Connection.commit() returns, whatever PgConnection.getTransactionState() was before the call. "
                + "It reports rolled_back when Connection.commit() throws. "
                + "It calls Connection.commit() after Connection.rollback(Savepoint) has thrown. "
                + "When Connection.rollback() throws, it calls Connection.setAutoCommit(true) and keeps the connection. "
                + "Java 21 Connection.setAutoCommit says: \"If this method is called during a transaction and the auto-commit mode is changed, the transaction is committed.\" "
                + "pgjdbc 42.7.14 PgConnection.setAutoCommit(true) calls commit() when auto-commit is off. "
                + "It does not call Connection.setTransactionIsolation. A write made before a nested savepoint is executed inside that savepoint.";

        private Unsafe() {}

        static boolean requestsIsolation() {
            return false;
        }

        static boolean defersOuterWrite() {
            return true;
        }

        static Outcome finish(Sessions sessions, Connection connection, Throwable bodyError, Scope scope) {
            if (bodyError != null) {
                return afterBodyFailure(sessions, connection, bodyError);
            }
            // A failed savepoint rollback is ignored. The surrounding transaction is committed.
            String before = transactionState(connection);
            sessions.note("commit state before=" + before);
            try {
                connection.commit();
            } catch (SQLException ex) {
                sessions.note("Connection.commit() threw; reported as a rollback");
                return rolledBack("Connection.commit() threw, which the unsafe policy reports as a rollback",
                        errInfo(ex), before, false, false);
            }
            String ignored = scope.rollbackOnly ? " A savepoint rollback had failed and was ignored." : "";
            return committed("Connection.commit() returned." + ignored + " The driver state before the call was " + before + ".", before);
        }

        private static Outcome afterBodyFailure(Sessions sessions, Connection connection, Throwable bodyError) {
            SqlFailure rollback = rollback(connection);
            if (!rollback.failed()) {
                return rolledBack("the body threw and Connection.rollback() returned", errInfo(bodyError), null, false, false);
            }
            boolean restored = false;
            SQLException restoreError = null;
            try {
                sessions.note("setAutoCommit(true) after a failed Connection.rollback()");
                connection.setAutoCommit(true);
                restored = true;
                sessions.note("setAutoCommit(true) returned; driver state " + transactionState(connection));
            } catch (SQLException ex) {
                restoreError = ex;
                sessions.note("setAutoCommit(true) threw: " + ex.getSQLState() + " " + ex.getMessage());
            }
            String basis = restored
                    ? "the body threw and Connection.rollback() threw. Connection.setAutoCommit(true) returned and the connection was kept."
                    : "the body threw and Connection.rollback() threw. Connection.setAutoCommit(true) also threw. The connection was kept.";
            Map<String, Object> cleanup = errInfo(restoreError != null ? restoreError : rollback.error);
            return failed(basis, restoreError != null ? restoreError : rollback.error, null, false, restored, errInfo(bodyError), cleanup);
        }
    }

    static Outcome run(boolean correct, Sessions sessions, Connection connection, Work work, Scope scope, Integer isolation) throws SQLException {
        if (correct && isolation != null) {
            connection.setTransactionIsolation(isolation);
        }
        connection.setAutoCommit(false);
        Throwable body = null;
        try {
            work.run(connection);
        } catch (Throwable ex) {
            Protocol.rethrowIfProtocol(ex);
            body = ex;
        }
        return correct ? Correct.finish(sessions, connection, body, scope) : Unsafe.finish(sessions, connection, body, scope);
    }

    static String contract(boolean correct) {
        return correct ? Correct.CONTRACT : Unsafe.CONTRACT;
    }

    private static SqlFailure rollback(Connection connection) {
        try {
            connection.rollback();
            return new SqlFailure(null);
        } catch (SQLException ex) {
            Protocol.rethrowIfProtocol(ex);
            return new SqlFailure(ex);
        }
    }

    /** {@code IDLE}, {@code OPEN}, {@code FAILED}, or {@code unread} if the driver connection cannot be unwrapped. */
    static String transactionState(Connection connection) {
        try {
            PgConnection pg = connection.unwrap(PgConnection.class);
            TransactionState state = pg.getTransactionState();
            return state == null ? "null" : state.name();
        } catch (SQLException ex) {
            return "unread";
        }
    }

    private static Outcome committed(String basis, String commitStateBefore) {
        return new Outcome("committed", basis, null, commitStateBefore, false, false, null, null);
    }

    private static Outcome rolledBack(String basis, Map<String, Object> apiError, String commitStateBefore, boolean discarded, boolean autocommitRestored) {
        return new Outcome("rolled_back", basis, apiError, commitStateBefore, discarded, autocommitRestored, null, null);
    }

    private static Outcome failed(String basis, Throwable apiError, String commitStateBefore, boolean discarded, boolean autocommitRestored,
                                  Map<String, Object> bodyError, Map<String, Object> cleanupError) {
        return new Outcome("failed", basis, apiError == null ? null : errInfo(apiError), commitStateBefore, discarded, autocommitRestored, bodyError, cleanupError);
    }

    private static Map<String, Object> rolledBackError(String message) {
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", "TransactionRolledBack");
        info.put("code", null);
        info.put("message", message);
        return info;
    }

    static Map<String, Object> errInfo(Throwable error) {
        String message = error.getMessage() == null ? "" : error.getMessage();
        Throwable cause = error.getCause();
        if (cause != null && cause.getMessage() != null && !message.contains(cause.getMessage())) {
            message = message.isEmpty() ? cause.getMessage() : message + ": " + cause.getMessage();
        }
        message = message.replaceAll("\\s+", " ").trim();
        if (message.length() > 500) message = message.substring(0, 500);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", error.getClass().getSimpleName());
        info.put("code", Faults.sqlState(error));
        info.put("message", message);
        return info;
    }

    private record SqlFailure(SQLException error) {
        boolean failed() {
            return error != null;
        }
    }
}
