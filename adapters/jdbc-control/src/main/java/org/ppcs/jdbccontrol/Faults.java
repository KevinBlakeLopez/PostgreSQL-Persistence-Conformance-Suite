package org.ppcs.jdbccontrol;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Savepoint;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.postgresql.jdbc.PSQLSavepoint;

/**
 * Category C faults, injected in this process before pgjdbc 42.7.14 sends.
 *
 * <p>{@code PgConnection.rollback()} does not become a {@link Statement}. It calls
 * {@code executeTransactionCommand}, which calls {@code QueryExecutor.execute} directly.
 * The top-level withhold is therefore on {@code Connection.rollback()}, once, before that
 * call. {@code ROLLBACK TO SAVEPOINT} is withheld or rewritten on
 * {@code Connection.rollback(Savepoint)}, before {@code execSQLUpdate} sends it.
 * {@code after-fault} is reported from this layer, before the policy sees the error.
 *
 * <p>The proxy does not intercept {@code commit()} or {@code setAutoCommit}. Those stay
 * ordinary public JDBC calls. No private pgjdbc field is read or written.
 */
final class Faults {
    private Faults() {}

    static Connection wrap(Connection raw, Fault fault, Protocol protocol) {
        return (Connection) java.lang.reflect.Proxy.newProxyInstance(
                Connection.class.getClassLoader(),
                new Class<?>[] {Connection.class},
                (proxy, method, args) -> dispatch(raw, proxy, method, args == null ? new Object[0] : args, fault, protocol));
    }

    private static Object dispatch(Connection raw, Object proxy, Method method, Object[] args, Fault fault, Protocol protocol) throws Throwable {
        String name = method.getName();
        if (name.equals("equals") && args.length == 1) {
            return args[0] == proxy || args[0] == raw;
        }
        if (name.equals("hashCode") && args.length == 0) return System.identityHashCode(raw);
        if (name.equals("toString") && args.length == 0) return "FaultConnection[" + raw + "]";
        if (name.equals("unwrap") && args.length == 1 && args[0] instanceof Class<?> iface) {
            if (iface.isInstance(proxy)) return iface.cast(proxy);
            return raw.unwrap(iface);
        }
        if (name.equals("isWrapperFor") && args.length == 1 && args[0] instanceof Class<?> iface) {
            return iface.isInstance(proxy) || raw.isWrapperFor(iface);
        }
        if (name.equals("rollback") && args.length == 0) {
            onRootRollback(raw, fault, protocol);
            return null;
        }
        if (name.equals("rollback") && args.length == 1 && args[0] instanceof Savepoint savepoint) {
            onSavepointRollback(raw, savepoint, fault, protocol);
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
    private static void onRootRollback(Connection raw, Fault fault, Protocol protocol) throws SQLException {
        if (fault.take(Fault.ROOT)) {
            fault.withheld.add("ROLLBACK");
            fault.trace.add("ROLLBACK -- WITHHELD on Connection.rollback before send");
            protocol.checkpoint("after-fault", null, fault.pid);
            throw new SQLException("injected client-side failure: ROLLBACK was not sent");
        }
        fault.trace.add("ROLLBACK");
        raw.rollback();
    }

    /**
     * Withhold or rewrite {@code ROLLBACK TO SAVEPOINT} once, before pgjdbc sends it.
     * The rewrite is executed on the raw connection so PostgreSQL answers. {@code after-fault}
     * is reported after the withhold, or after that reply, before the exception reaches the policy.
     */
    private static void onSavepointRollback(Connection raw, Savepoint savepoint, Fault fault, Protocol protocol) throws SQLException {
        if (!fault.take(Fault.SAVEPOINT)) {
            fault.trace.add(savepointSql(savepoint));
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
            String code = sqlState(ex);
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

    /** The SQL {@code PgConnection.rollback(Savepoint)} passes to {@code execSQLUpdate}. */
    private static String savepointSql(Savepoint savepoint) throws SQLException {
        if (savepoint instanceof PSQLSavepoint pg) {
            return "ROLLBACK TO SAVEPOINT " + pg.getPGName();
        }
        return "ROLLBACK TO SAVEPOINT " + savepoint.getSavepointName();
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
    }
}
