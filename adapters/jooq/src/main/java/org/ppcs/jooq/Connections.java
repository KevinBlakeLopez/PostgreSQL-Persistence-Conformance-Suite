package org.ppcs.jooq;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.sql.SQLWarning;
import java.sql.Savepoint;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.logging.Logger;

import javax.sql.DataSource;

import org.postgresql.jdbc.PgConnection;
import org.postgresql.jdbc.PSQLSavepoint;

/**
 * The connection the framework sees, and the category C fault in front of pgjdbc.
 *
 * <p>{@code PgConnection.rollback()} and {@code PgConnection.commit()} do not become
 * statements. They call {@code executeTransactionCommand}. A top-level withhold is
 * therefore on {@code Connection.rollback()}, once, before that call.
 * {@code rollback(Savepoint)} is withheld or rewritten on that method, before
 * {@code execSQLUpdate}. The same proxy records commit, rollback, savepoint,
 * isolation, and autocommit calls without changing their results.
 */
final class Connections {
    private Connections() {}

    /** One physical connection per checkout. Not a pool. */
    static final class DriverDataSource implements DataSource {
        private final String url;
        private final String user;
        private final String password;

        DriverDataSource(String url, String user, String password) {
            this.url = url;
            this.user = user;
            this.password = password;
        }

        @Override
        public Connection getConnection() throws SQLException {
            Properties properties = new Properties();
            properties.setProperty("user", user);
            properties.setProperty("password", password);
            return DriverManager.getConnection(url, properties);
        }

        @Override
        public Connection getConnection(String username, String password) throws SQLException {
            Properties properties = new Properties();
            properties.setProperty("user", username);
            properties.setProperty("password", password);
            return DriverManager.getConnection(url, properties);
        }

        @Override
        public java.io.PrintWriter getLogWriter() {
            return null;
        }

        @Override
        public void setLogWriter(java.io.PrintWriter out) {}

        @Override
        public void setLoginTimeout(int seconds) {}

        @Override
        public int getLoginTimeout() {
            return 0;
        }

        @Override
        public Logger getParentLogger() throws SQLFeatureNotSupportedException {
            throw new SQLFeatureNotSupportedException();
        }

        @Override
        public <T> T unwrap(Class<T> iface) throws SQLException {
            if (iface.isInstance(this)) return iface.cast(this);
            throw new SQLException("not a " + iface.getName());
        }

        @Override
        public boolean isWrapperFor(Class<?> iface) {
            return iface.isInstance(this);
        }
    }

    /** JDBC calls this adapter observed, in order. Not used for classification. */
    static final class Trace {
        private final List<String> lines = new ArrayList<>();

        synchronized void note(String line) {
            if (lines.size() < 200) lines.add(line);
        }

        synchronized List<String> lines() {
            return List.copyOf(lines);
        }

        synchronized Map<String, Object> summary() {
            int commit = 0;
            int rollback = 0;
            int savepointRollback = 0;
            int setAutoCommit = 0;
            int setIsolation = 0;
            List<String> commitLines = new ArrayList<>();
            for (String line : lines) {
                if (line.startsWith("Connection.commit")) {
                    commit++;
                    commitLines.add(line);
                } else if (line.startsWith("Connection.rollback(Savepoint)")) {
                    savepointRollback++;
                } else if (line.startsWith("Connection.rollback")) {
                    rollback++;
                } else if (line.startsWith("Connection.setAutoCommit")) {
                    setAutoCommit++;
                } else if (line.startsWith("Connection.setTransactionIsolation")) {
                    setIsolation++;
                }
            }
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("commit_calls", commit);
            summary.put("rollback_calls", rollback);
            summary.put("savepoint_rollback_calls", savepointRollback);
            summary.put("set_autocommit_calls", setAutoCommit);
            summary.put("set_isolation_calls", setIsolation);
            summary.put("commit", commitLines);
            return summary;
        }
    }

    static final class FaultingDataSource implements DataSource {
        final DataSource delegate;
        private final Fault fault;
        private final Trace trace;
        private final Protocol protocol;

        FaultingDataSource(DataSource delegate, Fault fault, Trace trace, Protocol protocol) {
            this.delegate = delegate;
            this.fault = fault;
            this.trace = trace;
            this.protocol = protocol;
        }

        @Override
        public Connection getConnection() throws SQLException {
            return wrap(delegate.getConnection());
        }

        @Override
        public Connection getConnection(String username, String password) throws SQLException {
            return wrap(delegate.getConnection(username, password));
        }

        private Connection wrap(Connection raw) {
            return (Connection) java.lang.reflect.Proxy.newProxyInstance(
                    Connection.class.getClassLoader(),
                    new Class<?>[] {Connection.class},
                    (proxy, method, args) -> dispatch(raw, method, args == null ? new Object[0] : args));
        }

        private Object dispatch(Connection raw, Method method, Object[] args) throws Throwable {
            String name = method.getName();
            if (name.equals("equals") && args.length == 1) {
                return args[0] == raw || (args[0] != null && args[0].equals(raw));
            }
            if (name.equals("hashCode") && args.length == 0) return System.identityHashCode(raw);
            if (name.equals("toString") && args.length == 0) return "FaultConnection[" + raw + "]";
            if (name.equals("commit") && args.length == 0) {
                onCommit(raw);
                return null;
            }
            if (name.equals("rollback") && args.length == 0) {
                onRootRollback(raw);
                return null;
            }
            if (name.equals("rollback") && args.length == 1 && args[0] instanceof Savepoint savepoint) {
                onSavepointRollback(raw, savepoint);
                return null;
            }
            if (name.equals("setAutoCommit") && args.length == 1) {
                onSetAutoCommit(raw, (Boolean) args[0]);
                return null;
            }
            if (name.equals("setTransactionIsolation") && args.length == 1) {
                onSetIsolation(raw, (Integer) args[0]);
                return null;
            }
            if (name.equals("setSavepoint")) {
                Savepoint savepoint = args.length == 0 ? raw.setSavepoint() : raw.setSavepoint((String) args[0]);
                trace.note("Connection.setSavepoint state=" + state(raw));
                return savepoint;
            }
            if (name.equals("releaseSavepoint") && args.length == 1) {
                raw.releaseSavepoint((Savepoint) args[0]);
                trace.note("Connection.releaseSavepoint state=" + state(raw));
                return null;
            }
            if (name.equals("close") && args.length == 0) {
                trace.note("Connection.close state=" + state(raw));
                raw.close();
                return null;
            }
            try {
                return method.invoke(raw, args);
            } catch (InvocationTargetException ex) {
                Throwable cause = ex.getCause();
                if (cause instanceof RuntimeException runtime) throw runtime;
                if (cause instanceof Error error) throw error;
                if (cause instanceof SQLException sql) throw sql;
                throw ex;
            }
        }

        private void onCommit(Connection raw) throws SQLException {
            String before = state(raw);
            try {
                raw.commit();
            } catch (SQLException ex) {
                trace.note("Connection.commit " + before + " -> " + state(raw) + " threw " + code(ex));
                throw ex;
            }
            trace.note("Connection.commit " + before + " -> " + state(raw) + " returned warning=" + warning(raw));
        }

        /** Withhold {@code Connection.rollback()} once, before pgjdbc sends {@code ROLLBACK}. */
        private void onRootRollback(Connection raw) throws SQLException {
            if (fault.take(Fault.ROOT)) {
                fault.withheld.add("ROLLBACK");
                fault.trace.add("ROLLBACK -- WITHHELD on Connection.rollback before send");
                trace.note("Connection.rollback WITHHELD state=" + state(raw));
                protocol.checkpoint("after-fault", null, fault.pid);
                throw new SQLException("injected client-side failure: ROLLBACK was not sent");
            }
            String before = state(raw);
            try {
                raw.rollback();
            } catch (SQLException ex) {
                trace.note("Connection.rollback " + before + " -> " + state(raw) + " threw " + code(ex));
                throw ex;
            }
            trace.note("Connection.rollback " + before + " -> " + state(raw) + " returned");
        }

        /**
         * Withhold or rewrite {@code ROLLBACK TO SAVEPOINT} once, before pgjdbc sends it.
         * {@code after-fault} is reported from this layer, after the withhold or after
         * PostgreSQL's reply, before the exception reaches jOOQ.
         */
        private void onSavepointRollback(Connection raw, Savepoint savepoint) throws SQLException {
            if (!fault.take(Fault.SAVEPOINT)) {
                String before = state(raw);
                try {
                    raw.rollback(savepoint);
                } catch (SQLException ex) {
                    trace.note("Connection.rollback(Savepoint) " + before + " -> " + state(raw) + " threw " + code(ex));
                    throw ex;
                }
                trace.note("Connection.rollback(Savepoint) " + before + " -> " + state(raw) + " returned");
                return;
            }
            String original = savepointSql(savepoint);
            fault.withheld.add(original);
            if ("client-reject".equals(fault.mode)) {
                fault.trace.add(original + " -- WITHHELD before send");
                trace.note("Connection.rollback(Savepoint) WITHHELD state=" + state(raw));
                protocol.checkpoint("after-fault", null, fault.pid);
                throw new SQLException("injected client-side failure: ROLLBACK TO SAVEPOINT was not sent");
            }
            String rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint";
            fault.rewritten.add(rewritten);
            fault.trace.add(rewritten + " -- REWRITE of: " + original);
            SQLException error = null;
            Statement statement = raw.createStatement();
            try {
                statement.execute(rewritten);
            } catch (SQLException ex) {
                error = ex;
                String sqlState = Fault.sqlState(ex);
                fault.replyCodes.add(sqlState == null ? "error" : sqlState);
            } finally {
                try {
                    statement.close();
                } catch (SQLException ignored) {
                    // The server's reply is the error to report. Closing the statement is not a second fault.
                }
            }
            trace.note("Connection.rollback(Savepoint) REWRITE state=" + state(raw)
                    + " reply=" + (fault.replyCodes.isEmpty() ? "none" : fault.replyCodes.get(fault.replyCodes.size() - 1)));
            protocol.checkpoint("after-fault", null, fault.pid);
            if (error != null) throw error;
            throw new SQLException("rewritten ROLLBACK TO SAVEPOINT did not fail");
        }

        private void onSetAutoCommit(Connection raw, boolean autoCommit) throws SQLException {
            String before = state(raw);
            raw.setAutoCommit(autoCommit);
            trace.note("Connection.setAutoCommit(" + autoCommit + ") " + before + " -> " + state(raw));
        }

        private void onSetIsolation(Connection raw, int level) throws SQLException {
            String before = state(raw);
            raw.setTransactionIsolation(level);
            trace.note("Connection.setTransactionIsolation(" + level + ") " + before + " -> " + state(raw));
        }

        private static String savepointSql(Savepoint savepoint) throws SQLException {
            if (savepoint instanceof PSQLSavepoint pg) return "ROLLBACK TO SAVEPOINT " + pg.getPGName();
            return "ROLLBACK TO SAVEPOINT " + savepoint.getSavepointName();
        }

        private static String state(Connection raw) {
            try {
                if (raw.isClosed()) return "closed";
                PgConnection pg = raw.unwrap(PgConnection.class);
                return pg.getTransactionState().name() + " autoCommit=" + pg.getAutoCommit();
            } catch (Throwable ex) {
                return "unavailable";
            }
        }

        private static String warning(Connection raw) {
            try {
                SQLWarning warning = raw.getWarnings();
                if (warning == null) return "none";
                String state = warning.getSQLState() == null ? "" : warning.getSQLState() + " ";
                String message = warning.getMessage() == null ? "" : warning.getMessage();
                return (state + message).replaceAll("\\s+", " ").trim();
            } catch (SQLException ex) {
                return "unreadable";
            }
        }

        private static String code(SQLException ex) {
            String state = ex.getSQLState();
            return state == null || state.isEmpty() ? ex.getClass().getSimpleName() : state;
        }

        @Override
        public java.io.PrintWriter getLogWriter() throws SQLException {
            return delegate.getLogWriter();
        }

        @Override
        public void setLogWriter(java.io.PrintWriter out) throws SQLException {
            delegate.setLogWriter(out);
        }

        @Override
        public void setLoginTimeout(int seconds) throws SQLException {
            delegate.setLoginTimeout(seconds);
        }

        @Override
        public int getLoginTimeout() throws SQLException {
            return delegate.getLoginTimeout();
        }

        @Override
        public Logger getParentLogger() throws SQLFeatureNotSupportedException {
            return delegate.getParentLogger();
        }

        @Override
        public <T> T unwrap(Class<T> iface) throws SQLException {
            if (iface.isInstance(this)) return iface.cast(this);
            return delegate.unwrap(iface);
        }

        @Override
        public boolean isWrapperFor(Class<?> iface) throws SQLException {
            return iface.isInstance(this) || delegate.isWrapperFor(iface);
        }
    }

    /** One client-side injection, armed by the case and fired at most once. */
    static final class Fault {
        static final String ROOT = "root";
        static final String SAVEPOINT = "savepoint";

        String kind;
        /** {@code client-reject} withholds the statement. {@code rewrite} lets PostgreSQL answer the rewritten one. */
        String mode;
        boolean armed;
        int fired;
        Integer pid;
        final List<String> trace = new ArrayList<>();
        final List<String> withheld = new ArrayList<>();
        final List<String> rewritten = new ArrayList<>();
        final List<String> replyCodes = new ArrayList<>();

        synchronized boolean take(String expectedKind) {
            if (!armed || !expectedKind.equals(kind)) return false;
            armed = false;
            fired++;
            return true;
        }

        void arm(String kind, String mode) {
            this.kind = kind;
            this.mode = mode;
            this.armed = true;
        }

        void disarm() {
            this.armed = false;
            this.kind = null;
        }

        Map<String, Object> report() {
            Map<String, Object> report = new LinkedHashMap<>();
            report.put("mode", mode);
            report.put("fired", fired);
            report.put("injection", "client-side");
            report.put("withheld", List.copyOf(withheld));
            if (!rewritten.isEmpty()) report.put("rewritten", List.copyOf(rewritten));
            if (!replyCodes.isEmpty()) report.put("reply_codes", List.copyOf(replyCodes));
            return report;
        }

        static String sqlState(Throwable error) {
            return Errors.sqlState(error);
        }
    }

    static Map<String, Object> diagnostics(Trace trace, List<String> sql, List<String> listeners) {
        Map<String, Object> diagnostics = new LinkedHashMap<>();
        diagnostics.put("jdbc", trace.lines());
        diagnostics.put("sql", List.copyOf(sql));
        diagnostics.put("listeners", List.copyOf(listeners));
        return diagnostics;
    }

    static List<String> synchronizedList() {
        return Collections.synchronizedList(new ArrayList<>());
    }
}
