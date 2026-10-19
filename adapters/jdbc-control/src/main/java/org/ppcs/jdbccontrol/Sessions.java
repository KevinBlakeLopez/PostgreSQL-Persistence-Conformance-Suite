package org.ppcs.jdbccontrol;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

/**
 * One {@link DriverManager} connection at a time. This is not a pool.
 * {@code discard} closes it so the next {@code acquire} opens another.
 */
final class Sessions {
    final String url;
    final String user;
    final String password;
    final String applicationName;
    final Faults.Fault fault;
    final List<String> trace = new ArrayList<>();
    private final Protocol protocol;
    private Connection current;
    Policy.Outcome last;

    Sessions(String url, String user, String password, String applicationName, Faults.Fault fault, Protocol protocol) {
        this.url = url;
        this.user = user;
        this.password = password;
        this.applicationName = applicationName;
        this.fault = fault;
        this.protocol = protocol;
    }

    Connection acquire() throws SQLException {
        if (current != null) return current;
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("ApplicationName", applicationName);
        Connection raw = DriverManager.getConnection(url, properties);
        current = Faults.wrap(raw, fault, protocol);
        note("DriverManager.getConnection");
        return current;
    }

    /** Close the connection and do not hand it out again. */
    void discard() {
        Connection connection = current;
        current = null;
        if (connection == null) return;
        try {
            connection.close();
            note("Connection.close");
        } catch (SQLException ex) {
            note("Connection.close failed: " + ex.getMessage());
        }
    }

    void close() {
        discard();
    }

    void note(String line) {
        trace.add(line);
    }

    void insertItem(Connection connection, String name) throws SQLException {
        note("insert into item (name, qty) values (?, 0)");
        try (PreparedStatement statement = connection.prepareStatement("insert into item (name, qty) values (?, 0)")) {
            statement.setString(1, name);
            statement.executeUpdate();
        }
    }

    void insertTaken(Connection connection) throws SQLException {
        note("insert into uniq (code) values ('taken')");
        try (PreparedStatement statement = connection.prepareStatement("insert into uniq (code) values (?)")) {
            statement.setString(1, "taken");
            statement.executeUpdate();
        }
    }

    void readItem(Connection connection, String name) throws SQLException {
        note("select name from item where name = ?");
        try (PreparedStatement statement = connection.prepareStatement("select name from item where name = ?")) {
            statement.setString(1, name);
            try (ResultSet rows = statement.executeQuery()) {
                while (rows.next()) rows.getString(1);
            }
        }
    }

    Ident identify(Connection connection) throws SQLException {
        return identify(connection, false);
    }

    Ident identify(Connection connection, boolean isolation) throws SQLException {
        String sql = isolation
                ? "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
                : "select pg_current_xact_id()::text, pg_backend_pid()";
        note(sql);
        try (PreparedStatement statement = connection.prepareStatement(sql);
             ResultSet rows = statement.executeQuery()) {
            if (!rows.next()) throw new SQLException("identify returned no row");
            Ident ident = new Ident(rows.getString(1), rows.getInt(2), isolation ? rows.getString(3) : null);
            fault.pid = ident.pid;
            return ident;
        }
    }

    Map<String, Object> diagnostics() {
        Map<String, Object> diagnostics = new LinkedHashMap<>();
        diagnostics.put("trace", List.copyOf(trace));
        diagnostics.put("fault_trace", List.copyOf(fault.trace));
        diagnostics.put("withheld", List.copyOf(fault.withheld));
        diagnostics.put("rewritten", List.copyOf(fault.rewritten));
        diagnostics.put("reply_codes", List.copyOf(fault.replyCodes));
        diagnostics.put("injection", fault.fired == 0 ? null : "client-side");
        if (last != null) {
            diagnostics.put("commit_state_before", last.commitStateBefore);
            diagnostics.put("discarded", last.discarded);
            diagnostics.put("autocommit_restored", last.autocommitRestored);
        }
        return diagnostics;
    }

    static final class Ident {
        final String xid;
        final int pid;
        final String isolation;

        Ident(String xid, int pid, String isolation) {
            this.xid = xid;
            this.pid = pid;
            this.isolation = isolation;
        }
    }
}
