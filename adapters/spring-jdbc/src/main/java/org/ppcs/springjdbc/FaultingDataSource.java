package org.ppcs.springjdbc;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.sql.Savepoint;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Set;
import java.util.logging.Logger;

import javax.sql.DataSource;

import org.postgresql.jdbc.PSQLSavepoint;

/**
 * Category C faults, injected in this process before pgjdbc 42.7.14 sends.
 *
 * <p>{@code PgConnection.rollback()} does not become a {@link Statement}. It calls
 * {@code executeTransactionCommand(rollbackQuery)}, which calls
 * {@code QueryExecutor.execute} directly. The top-level withhold is therefore on
 * {@code Connection.rollback()}, once, before that call. {@code rollback(Savepoint)}
 * is a different method: {@code execSQLUpdate} creates a statement and sends
 * {@code ROLLBACK TO SAVEPOINT}. That withhold or rewrite is on
 * {@code rollback(Savepoint)}, before {@code execSQLUpdate}. One rollback fires one hook.
 */
final class FaultingDataSource implements DataSource {
    final DataSource delegate;
    private final Fault fault;
    private final Protocol protocol;

    FaultingDataSource(DataSource delegate, Fault fault, Protocol protocol) {
        this.delegate = delegate;
        this.fault = fault;
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
        if (name.equals("rollback") && args.length == 0) {
            onRootRollback(raw);
            return null;
        }
        if (name.equals("rollback") && args.length == 1 && args[0] instanceof Savepoint savepoint) {
            onSavepointRollback(raw, savepoint);
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

    /** Withhold {@code Connection.rollback()} once, before pgjdbc sends {@code ROLLBACK}. */
    private void onRootRollback(Connection raw) throws SQLException {
        if (fault.take(Fault.ROOT)) {
            fault.withheld.add("ROLLBACK");
            fault.trace.add("ROLLBACK -- WITHHELD on Connection.rollback before send");
            protocol.checkpoint("after-fault", null, fault.pid);
            throw new SQLException("injected client-side failure: ROLLBACK was not sent");
        }
        raw.rollback();
    }

    /**
     * Withhold or rewrite {@code ROLLBACK TO SAVEPOINT} once, before pgjdbc's
     * {@code execSQLUpdate} sends it. The rewrite is sent through the driver's
     * statement path so PostgreSQL answers. {@code after-fault} is reported from
     * this layer, after the withhold or after that reply, before the exception
     * reaches Spring.
     */
    private void onSavepointRollback(Connection raw, Savepoint savepoint) throws SQLException {
        if (!fault.take(Fault.SAVEPOINT)) {
            raw.rollback(savepoint);
            return;
        }
        String original = savepointSql(savepoint);
        fault.withheld.add(original);
        if ("client-reject".equals(fault.mode)) {
            fault.trace.add(original + " -- WITHHELD before send");
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
            String code = Fault.sqlState(ex);
            fault.replyCodes.add(code == null ? "error" : code);
        } finally {
            try {
                statement.close();
            } catch (SQLException ignored) {
                // The server's reply is the error to report. Closing the statement is not a second fault.
            }
        }
        protocol.checkpoint("after-fault", null, fault.pid);
        if (error != null) throw error;
        throw new SQLException("rewritten ROLLBACK TO SAVEPOINT did not fail");
    }

    /** The SQL {@code PgConnection.rollback(Savepoint)} would pass to {@code execSQLUpdate}. */
    private static String savepointSql(Savepoint savepoint) throws SQLException {
        if (savepoint instanceof PSQLSavepoint pg) {
            return "ROLLBACK TO SAVEPOINT " + pg.getPGName();
        }
        return "ROLLBACK TO SAVEPOINT " + savepoint.getSavepointName();
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

        java.util.Map<String, Object> report() {
            java.util.Map<String, Object> report = new java.util.LinkedHashMap<>();
            report.put("mode", mode);
            report.put("fired", fired);
            report.put("injection", "client-side");
            report.put("withheld", java.util.List.copyOf(withheld));
            if (!rewritten.isEmpty()) report.put("rewritten", java.util.List.copyOf(rewritten));
            if (!replyCodes.isEmpty()) report.put("reply_codes", java.util.List.copyOf(replyCodes));
            return report;
        }

        static String sqlState(Throwable error) {
            Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
            Throwable current = error;
            while (current != null && seen.add(current)) {
                if (current instanceof SQLException sql) {
                    if (sql.getSQLState() != null && !sql.getSQLState().isEmpty()) return sql.getSQLState();
                    SQLException next = sql.getNextException();
                    if (next != null && !seen.contains(next)) {
                        current = next;
                        continue;
                    }
                }
                current = current.getCause();
            }
            return null;
        }
    }
}
