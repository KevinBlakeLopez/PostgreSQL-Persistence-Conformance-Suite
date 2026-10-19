package org.ppcs.springtx;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

import javax.sql.DataSource;

import org.springframework.jdbc.datasource.DataSourceUtils;

/**
 * Writes and reads through the connection Spring bound to this thread.
 * {@link DataSource#getConnection()} would open a different physical connection
 * and leave the Spring transaction.
 */
final class Sql {
    final DataSource dataSource;
    final FaultingDataSource.Fault fault;
    final List<String> trace = new ArrayList<>();

    Sql(DataSource dataSource, FaultingDataSource.Fault fault) {
        this.dataSource = dataSource;
        this.fault = fault;
    }

    void insertItem(String name) throws SQLException {
        update("insert into item (name, qty) values (?, 0)", name);
    }

    void insertTaken() throws SQLException {
        update("insert into uniq (code) values (?)", "taken");
    }

    void readItem(String name) throws SQLException {
        note("select name from item where name = ?");
        withConnection(connection -> {
            try (PreparedStatement statement = connection.prepareStatement("select name from item where name = ?")) {
                statement.setString(1, name);
                try (ResultSet rows = statement.executeQuery()) {
                    while (rows.next()) rows.getString(1);
                }
            }
            return null;
        });
    }

    Ident identify(boolean isolation) throws SQLException {
        String sql = isolation
                ? "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
                : "select pg_current_xact_id()::text, pg_backend_pid()";
        note(sql);
        return withConnection(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(sql);
                 ResultSet rows = statement.executeQuery()) {
                if (!rows.next()) throw new SQLException("identify returned no row");
                Ident ident = new Ident(rows.getString(1), rows.getInt(2), isolation ? rows.getString(3) : null);
                fault.pid = ident.pid;
                return ident;
            }
        });
    }

    private void update(String sql, String value) throws SQLException {
        note(sql);
        withConnection(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(sql)) {
                statement.setString(1, value);
                statement.executeUpdate();
            }
            return null;
        });
    }

    private <T> T withConnection(SqlWork<T> work) throws SQLException {
        Connection connection = DataSourceUtils.getConnection(dataSource);
        try {
            return work.run(connection);
        } finally {
            DataSourceUtils.releaseConnection(connection, dataSource);
        }
    }

    private void note(String sql) {
        trace.add(sql);
    }

    @FunctionalInterface
    interface SqlWork<T> {
        T run(Connection connection) throws SQLException;
    }

    record Ident(String xid, int pid, String isolation) {}
}
