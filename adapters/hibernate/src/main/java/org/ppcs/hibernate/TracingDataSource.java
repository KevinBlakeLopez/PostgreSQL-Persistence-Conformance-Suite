package org.ppcs.hibernate;

import java.lang.StackWalker.StackFrame;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

import javax.sql.DataSource;

import org.postgresql.jdbc.PgConnection;

/**
 * Records JDBC transaction calls that reach this wrapper, with the caller and
 * pgjdbc's transaction state before and after the call. It does not change the call.
 */
final class TracingDataSource implements DataSource {
    final DataSource delegate;
    final List<Map<String, Object>> events = new ArrayList<>();

    TracingDataSource(DataSource delegate) {
        this.delegate = delegate;
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
        ClassLoader loader = Connection.class.getClassLoader();
        if (loader == null) loader = TracingDataSource.class.getClassLoader();
        return (Connection) java.lang.reflect.Proxy.newProxyInstance(
                loader,
                new Class<?>[] {Connection.class},
                (proxy, method, args) -> dispatch(raw, method, args == null ? new Object[0] : args));
    }

    private Object dispatch(Connection raw, Method method, Object[] args) throws Throwable {
        String name = method.getName();
        if (name.equals("equals") && args.length == 1) {
            return args[0] == raw || (args[0] != null && args[0].equals(raw));
        }
        if (name.equals("hashCode") && args.length == 0) return System.identityHashCode(raw);
        if (name.equals("toString") && args.length == 0) return "TracingConnection[" + raw + "]";
        boolean traced = switch (name) {
            case "commit", "rollback", "setAutoCommit", "setTransactionIsolation", "setSavepoint", "releaseSavepoint", "close", "abort" -> true;
            default -> false;
        };
        if (!traced) return invoke(raw, method, args);
        String before = transactionState(raw);
        Object value = null;
        Throwable thrown = null;
        try {
            value = invoke(raw, method, args);
            return value;
        } catch (Throwable ex) {
            thrown = ex;
            throw ex;
        } finally {
            Map<String, Object> event = new LinkedHashMap<>();
            event.put("call", callText(name, args));
            event.put("state_before", before);
            event.put("state_after", transactionState(raw));
            event.put("caller", caller());
            if (thrown != null) event.put("error", thrown.getClass().getSimpleName());
            synchronized (events) {
                events.add(event);
            }
        }
    }

    static String callText(String name, Object[] args) {
        if (name.equals("setAutoCommit") && args.length == 1) return "Connection.setAutoCommit(" + args[0] + ")";
        if (name.equals("setTransactionIsolation") && args.length == 1) return "Connection.setTransactionIsolation(" + args[0] + ")";
        if (name.equals("rollback") && args.length == 1) return "Connection.rollback(Savepoint)";
        if (name.equals("close")) return "Connection.close";
        return "Connection." + name;
    }

    static String transactionState(Connection connection) {
        try {
            PgConnection pg = connection instanceof PgConnection direct ? direct : connection.unwrap(PgConnection.class);
            return String.valueOf(pg.getTransactionState());
        } catch (RuntimeException | SQLException ex) {
            return "unreadable";
        }
    }

    static String caller() {
        return StackWalker.getInstance().walk(frames -> frames
                .map(StackFrame::getClassName)
                .filter(name -> !name.startsWith("org.ppcs.hibernate"))
                .filter(name -> !name.startsWith("java.lang.reflect"))
                .filter(name -> !name.startsWith("jdk.proxy"))
                .filter(name -> !name.startsWith("jdk.internal.reflect"))
                .filter(name -> !name.contains("$$Lambda"))
                .filter(name -> !name.startsWith("java.lang.invoke"))
                .limit(6)
                .reduce((left, right) -> left + " < " + right)
                .orElse("unknown"));
    }

    private static Object invoke(Connection raw, Method method, Object[] args) throws Throwable {
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

    List<Map<String, Object>> snapshot() {
        synchronized (events) {
            return List.copyOf(events);
        }
    }

    int size() {
        synchronized (events) {
            return events.size();
        }
    }

    List<Map<String, Object>> since(int mark) {
        synchronized (events) {
            if (mark >= events.size()) return List.of();
            return List.copyOf(events.subList(mark, events.size()));
        }
    }

    void clear() {
        synchronized (events) {
            events.clear();
        }
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
