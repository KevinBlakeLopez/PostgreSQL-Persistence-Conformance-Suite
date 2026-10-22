package org.ppcs.jooq;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Savepoint;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.jooq.Configuration;
import org.jooq.DSLContext;
import org.jooq.TransactionProperty;
/**
 * Two transaction owners.
 *
 * <p>Native mode calls {@code DSLContext.transaction}. jOOQ 3.21.9
 * {@code DefaultDSLContext.transactionResult0} commits when the callback returns
 * and rolls back when it throws. {@code DefaultTransactionProvider.commit} calls
 * {@code Connection.commit()} for the outermost scope and
 * {@code Connection.releaseSavepoint} for a nested one. The callback's runtime
 * exception is rethrown after rollback. A checked exception is wrapped in
 * {@code DataAccessException}. A failure of {@code rollback} is added as a
 * suppressed exception and the original exception is rethrown.
 *
 * <p>JDBC mode does not call {@code transaction}. The application calls
 * {@code Connection.setAutoCommit(false)}, uses jOOQ to execute SQL, and calls
 * {@code Connection.commit} or {@code Connection.rollback}. A nested scope is
 * {@code Connection.setSavepoint}. The same completion rule is applied, so a
 * difference in the result is a difference in who issued commit, not in how this
 * adapter scores the call.
 */
final class Tx {
    static final String NATIVE_CONTRACT = "jOOQ 3.21 manual, Transaction management: a callback that returns is an implicit commit, "
            + "and an uncaught exception rolls the transactional scope back. DSLContext.transaction javadoc: a runtime exception thrown by the "
            + "transactional logic indicates that a rollback has occurred, and a checked exception is wrapped in DataAccessException with the same meaning. "
            + "DefaultTransactionProvider.commit calls Connection.commit when the savepoint stack is empty. Connection.commit() is void and does not return a command tag. "
            + "DefaultTransactionProvider models a nested transaction() as a JDBC Savepoint. It does not open a second connection.";

    static final String JDBC_CONTRACT = "jOOQ 3.21 manual, Transaction management: jOOQ can run on a JDBC connection whose transaction the application already owns, "
            + "by calling Connection.commit and Connection.rollback rather than DSLContext.transaction. "
            + "This mode does not call DSLContext.transaction. A returning Connection.commit() is reported committed. "
            + "The application's exception is reported rolled back only when Connection.rollback() returns. "
            + "A thrown Connection.rollback() or Connection.commit() is reported failed: it asserts neither outcome. "
            + "Connection.commit() is void and does not return a command tag. A nested scope is Connection.setSavepoint on the same connection.";

    private Tx() {}

    static final class AppException extends RuntimeException {
        AppException(String message) {
            super(message);
        }
    }

    static final class Outcome {
        boolean started = true;
        String reported;
        String basis;
        Map<String, Object> apiError;
        List<Map<String, Object>> suppressed = List.of();

        Map<String, Object> toMap(String contract) {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("reported", reported);
            map.put("basis", basis);
            map.put("contract", contract);
            if (apiError != null) map.put("api_error", apiError);
            return map;
        }
    }

    @FunctionalInterface
    interface Body {
        void run(Scope scope) throws Throwable;
    }

    static final class Scope {
        final DSLContext dsl;
        private final Configuration configuration;
        private final Connection connection;
        private final boolean jdbc;

        private Scope(DSLContext dsl, Configuration configuration, Connection connection, boolean jdbc) {
            this.dsl = dsl;
            this.configuration = configuration;
            this.connection = connection;
            this.jdbc = jdbc;
        }

        /**
         * A nested scope. A normal return releases the savepoint and is reported committed.
         * An exception rolls back to the savepoint and is reported rolled back when that
         * call returns, or failed when the savepoint rollback throws a different exception.
         * The exception does not leave this method, except a protocol failure.
         */
        Outcome savepoint(Body body) {
            if (jdbc) return jdbcSavepoint(body);
            return nativeSavepoint(body);
        }

        private Outcome nativeSavepoint(Body body) {
            Throwable[] thrown = new Throwable[1];
            try {
                configuration.dsl().transaction(inner -> {
                    try {
                        body.run(new Scope(inner.dsl(), inner, null, false));
                    } catch (Throwable ex) {
                        thrown[0] = ex;
                        rethrow(ex);
                    }
                });
            } catch (Throwable escaped) {
                Protocol.rethrowIfProtocol(escaped);
                Protocol.rethrowIfProtocol(thrown[0]);
                return map(NATIVE_CONTRACT, escaped, thrown[0], true,
                        "DSLContext.transaction returned normally, so jOOQ released the nested savepoint",
                        "DSLContext.transaction rethrew the exception raised inside the nested callback, so jOOQ rolled back to the savepoint",
                        "DSLContext.transaction threw an exception the nested callback did not throw");
            }
            Protocol.rethrowIfProtocol(thrown[0]);
            return committed(NATIVE_CONTRACT, "DSLContext.transaction returned normally, so jOOQ released the nested savepoint");
        }

        private Outcome jdbcSavepoint(Body body) {
            Savepoint savepoint;
            try {
                savepoint = connection.setSavepoint();
            } catch (SQLException ex) {
                return failed(JDBC_CONTRACT, "Connection.setSavepoint threw before the nested body ran", ex);
            }
            try {
                body.run(new Scope(dsl, null, connection, true));
                connection.releaseSavepoint(savepoint);
                return committed(JDBC_CONTRACT, "Connection.releaseSavepoint returned, so the nested scope stayed in the outer transaction");
            } catch (Throwable ex) {
                Protocol.rethrowIfProtocol(ex);
                Throwable cleanup = null;
                try {
                    connection.rollback(savepoint);
                } catch (Throwable rollbackError) {
                    Protocol.rethrowIfProtocol(rollbackError);
                    cleanup = rollbackError;
                    ex.addSuppressed(rollbackError);
                }
                if (cleanup != null && cleanup != ex) {
                    return map(JDBC_CONTRACT, cleanup, ex, true,
                            "Connection.releaseSavepoint returned",
                            "the nested body threw and Connection.rollback(Savepoint) threw a different exception",
                            "Connection.rollback(Savepoint) threw");
                }
                Outcome outcome = rolledBack(JDBC_CONTRACT,
                        "the nested body threw and Connection.rollback(Savepoint) returned", ex);
                return outcome;
            }
        }
    }

    static Outcome nativeTop(DSLContext dsl, TransactionProperty[] properties, Body body) {
        Throwable[] thrown = new Throwable[1];
        boolean[] entered = {false};
        try {
            if (properties.length == 0) {
                dsl.transaction(outer -> enter(outer, thrown, entered, body));
            } else {
                dsl.transaction(outer -> enter(outer, thrown, entered, body), properties);
            }
        } catch (Throwable escaped) {
            Protocol.rethrowIfProtocol(escaped);
            Protocol.rethrowIfProtocol(thrown[0]);
            if (!entered[0]) return notStarted(NATIVE_CONTRACT, escaped);
            return map(NATIVE_CONTRACT, escaped, thrown[0], true,
                    "DSLContext.transaction returned normally, so jOOQ committed",
                    "DSLContext.transaction rethrew the exception raised inside the callback, so jOOQ rolled back",
                    "DSLContext.transaction threw an exception the callback did not throw");
        }
        Protocol.rethrowIfProtocol(thrown[0]);
        return committed(NATIVE_CONTRACT, "DSLContext.transaction returned normally, so jOOQ committed");
    }

    private static void enter(Configuration outer, Throwable[] thrown, boolean[] entered, Body body) throws Exception {
        entered[0] = true;
        try {
            body.run(new Scope(outer.dsl(), outer, null, false));
        } catch (Throwable ex) {
            thrown[0] = ex;
            rethrow(ex);
        }
    }

    /**
     * @param release when true, close the connection before returning. TX-03 does this
     *                so the pool can hand the connection out again. Other cases keep it
     *                until the process closes, which is after {@code after-end}.
     */
    static Outcome jdbcTop(Connection connection, DSLContext dsl, boolean release, Integer isolation, Body body) {
        boolean entered = false;
        boolean bodyFinished = false;
        try {
            if (isolation != null) connection.setTransactionIsolation(isolation);
            connection.setAutoCommit(false);
            entered = true;
            body.run(new Scope(dsl, null, connection, true));
            bodyFinished = true;
            connection.commit();
            return committed(JDBC_CONTRACT, "Connection.commit() returned, so the application reported a commit");
        } catch (Throwable ex) {
            Protocol.rethrowIfProtocol(ex);
            if (!entered) return notStarted(JDBC_CONTRACT, ex);
            if (!bodyFinished) {
                Throwable cleanup = rollback(connection);
                if (cleanup != null) ex.addSuppressed(cleanup);
                if (cleanup != null) {
                    Outcome failed = failed(JDBC_CONTRACT,
                            "the body threw and Connection.rollback() threw. The outcome is failed: rollback did not return.",
                            cleanup);
                    failed.suppressed = List.of(Errors.info(ex));
                    return failed;
                }
                return rolledBack(JDBC_CONTRACT, "the body threw and Connection.rollback() returned", ex);
            }
            Throwable cleanup = rollback(connection);
            if (cleanup != null) ex.addSuppressed(cleanup);
            return failed(JDBC_CONTRACT,
                    "Connection.commit() threw. The application reports failed and does not report a confirmed rollback.",
                    ex);
        } finally {
            if (release) {
                try {
                    connection.close();
                } catch (SQLException ignored) {
                    // The unit's outcome is already decided. Closing returns the connection to the pool.
                }
            }
        }
    }

    private static Throwable rollback(Connection connection) {
        try {
            connection.rollback();
            return null;
        } catch (Throwable ex) {
            Protocol.rethrowIfProtocol(ex);
            return ex;
        }
    }

    private static void rethrow(Throwable ex) throws Exception {
        if (ex instanceof Exception exception) throw exception;
        throw (Error) ex;
    }

    private static Outcome notStarted(String contract, Throwable ex) {
        Outcome outcome = new Outcome();
        outcome.started = false;
        outcome.reported = "failed";
        outcome.basis = "the transaction API threw before the body ran";
        outcome.apiError = Errors.info(ex);
        outcome.suppressed = suppressed(ex);
        return outcome;
    }

    private static Outcome committed(String contract, String basis) {
        Outcome outcome = new Outcome();
        outcome.reported = "committed";
        outcome.basis = basis;
        return outcome;
    }

    private static Outcome rolledBack(String contract, String basis, Throwable error) {
        Outcome outcome = new Outcome();
        outcome.reported = "rolled_back";
        outcome.basis = basis;
        outcome.apiError = Errors.info(error);
        outcome.suppressed = suppressed(error);
        return outcome;
    }

    private static Outcome failed(String contract, String basis, Throwable error) {
        Outcome outcome = new Outcome();
        outcome.reported = "failed";
        outcome.basis = basis;
        outcome.apiError = Errors.info(error);
        outcome.suppressed = suppressed(error);
        return outcome;
    }

    /**
     * {@code escaped == thrown} is the callback's own exception leaving the transaction API.
     * jOOQ rethrows that object after rollback. Anything else, including an exception from
     * commit, is failed.
     */
    private static Outcome map(String contract, Throwable escaped, Throwable thrown, boolean started,
                               String committedBasis, String rolledBackBasis, String failedBasis) {
        if (thrown != null && escaped == thrown) return rolledBack(contract, rolledBackBasis, thrown);
        Outcome outcome = failed(contract, failedBasis, escaped);
        outcome.started = started;
        if (thrown != null) {
            List<Map<String, Object>> extra = new ArrayList<>(outcome.suppressed);
            extra.add(Errors.info(thrown));
            outcome.suppressed = extra;
        }
        return outcome;
    }

    private static List<Map<String, Object>> suppressed(Throwable error) {
        Throwable[] all = error.getSuppressed();
        if (all.length == 0) return List.of();
        List<Map<String, Object>> list = new ArrayList<>();
        for (Throwable suppressed : all) list.add(Errors.info(suppressed));
        return list;
    }

    static Map<String, Object> nestedSteps(Outcome nested) {
        Map<String, Object> map = new LinkedHashMap<>();
        boolean caught = nested != null && !"committed".equals(nested.reported);
        boolean completed = nested != null && "committed".equals(nested.reported);
        map.put("caught", caught);
        map.put("completed", completed);
        if (nested != null) {
            map.put("reported", nested.reported);
            if (nested.apiError != null) map.put("error", nested.apiError);
            if (!nested.suppressed.isEmpty()) map.put("suppressed", nested.suppressed);
        }
        return map;
    }
}
