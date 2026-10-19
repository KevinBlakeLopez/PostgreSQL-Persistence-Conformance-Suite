package org.ppcs.jdbccontrol;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.SQLWarning;
import java.sql.Statement;
import java.util.Map;
import java.util.Properties;

import org.postgresql.jdbc.PgConnection;

/**
 * One-off observations against the disposable PostgreSQL. Not the adapter protocol.
 * Usage: java -cp ... org.ppcs.jdbccontrol.Probe path-to-ppcs-instance.json
 *
 * <p>Refuses a server whose {@code cluster_name} is not that file's token, creates
 * {@code ppcs_jdbc_probe}, and drops it. Prints {@code key=value} lines.
 */
public final class Probe {
    public static void main(String[] args) throws Exception {
        if (Runtime.version().feature() < 21) {
            System.err.println("requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        if (args.length != 1) {
            System.err.println("usage: Probe path-to-ppcs-instance.json");
            System.exit(2);
        }
        Map<String, Object> instance = Json.object(Json.parse(Files.readString(Path.of(args[0]))));
        String host = Json.text(instance, "host");
        int port = Json.integer(instance, "port");
        String user = Json.text(instance, "user");
        String password = Json.text(instance, "password");
        String token = Json.text(instance, "token");
        String adminUrl = "jdbc:postgresql://" + host + ":" + port + "/postgres";
        try (Connection admin = connect(adminUrl, user, password, "ppcs-jdbc-probe")) {
            String cluster;
            try (Statement statement = admin.createStatement();
                 ResultSet rows = statement.executeQuery("select current_setting('cluster_name')")) {
                rows.next();
                cluster = rows.getString(1);
            }
            if (!token.equals(cluster)) {
                System.err.println("cluster_name does not match the instance token; refusing to continue");
                System.exit(2);
            }
            try (Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_jdbc_probe with (force)");
                statement.execute("create database ppcs_jdbc_probe");
            }
        }
        String url = "jdbc:postgresql://" + host + ":" + port + "/ppcs_jdbc_probe";
        try {
            abortedCommit(url, user, password);
            autocommitOpen(url, user, password);
            autocommitFailed(url, user, password);
            statementCommitTag(url, user, password);
            isolation(url, user, password);
        } finally {
            try (Connection admin = connect(adminUrl, user, password, "ppcs-jdbc-probe");
                 Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_jdbc_probe with (force)");
            }
        }
    }

    /** Connection.commit() after a unique violation. Does the call throw, and what is the driver state? */
    private static void abortedCommit(String url, String user, String password) throws SQLException {
        try (Connection observer = connect(url, user, password, "ppcs-jdbc-probe-observer");
             Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            setup(raw);
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.executeUpdate("insert into item (name) values ('marker')");
                try {
                    statement.executeUpdate("insert into uniq (code) values ('taken')");
                } catch (SQLException ex) {
                    System.out.println("aborted_violation_sqlstate=" + ex.getSQLState());
                }
            }
            String before = String.valueOf(pg.getTransactionState());
            boolean threw = false;
            try {
                pg.commit();
            } catch (SQLException ex) {
                threw = true;
                System.out.println("aborted_commit_sqlstate=" + ex.getSQLState());
            }
            String after = String.valueOf(pg.getTransactionState());
            SQLWarning warning = pg.getWarnings();
            System.out.println("aborted_commit_state_before=" + before);
            System.out.println("aborted_commit_threw=" + threw);
            System.out.println("aborted_commit_state_after=" + after);
            System.out.println("aborted_commit_warning=" + (warning == null ? "none" : warning.getMessage()));
            System.out.println("aborted_marker_visible=" + visible(observer, "marker"));
        }
    }

    /** setAutoCommit(true) while a transaction is open and not aborted. */
    private static void autocommitOpen(String url, String user, String password) throws SQLException {
        try (Connection observer = connect(url, user, password, "ppcs-jdbc-probe-observer");
             Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.executeUpdate("insert into item (name) values ('open-marker')");
            }
            String before = String.valueOf(pg.getTransactionState());
            boolean threw = false;
            try {
                pg.setAutoCommit(true);
            } catch (SQLException ex) {
                threw = true;
                System.out.println("autocommit_open_sqlstate=" + ex.getSQLState());
            }
            System.out.println("autocommit_open_state_before=" + before);
            System.out.println("autocommit_open_threw=" + threw);
            System.out.println("autocommit_open_state_after=" + pg.getTransactionState());
            System.out.println("autocommit_open_autocommit=" + pg.getAutoCommit());
            System.out.println("autocommit_open_visible=" + visible(observer, "open-marker"));
        }
    }

    /** setAutoCommit(true) after a statement has aborted the transaction. */
    private static void autocommitFailed(String url, String user, String password) throws SQLException {
        try (Connection observer = connect(url, user, password, "ppcs-jdbc-probe-observer");
             Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.executeUpdate("insert into item (name) values ('failed-marker')");
                try {
                    statement.executeUpdate("insert into uniq (code) values ('taken')");
                } catch (SQLException ignored) {
                    // The unique violation aborts the transaction. The probe continues to setAutoCommit.
                }
            }
            String before = String.valueOf(pg.getTransactionState());
            boolean threw = false;
            try {
                pg.setAutoCommit(true);
            } catch (SQLException ex) {
                threw = true;
                System.out.println("autocommit_failed_sqlstate=" + ex.getSQLState());
            }
            System.out.println("autocommit_failed_state_before=" + before);
            System.out.println("autocommit_failed_threw=" + threw);
            System.out.println("autocommit_failed_state_after=" + pg.getTransactionState());
            System.out.println("autocommit_failed_visible=" + visible(observer, "failed-marker"));
        }
    }

    /**
     * Statement.execute("COMMIT") stores an update count, not the command tag.
     * This is an observation of the statement API. The control policy does not use it.
     */
    private static void statementCommitTag(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.executeUpdate("insert into item (name) values ('tag-marker')");
                try {
                    statement.executeUpdate("insert into uniq (code) values ('taken')");
                } catch (SQLException ignored) {
                    // Aborted transaction. The next execute is COMMIT as a statement.
                }
                boolean resultSet = statement.execute("COMMIT");
                System.out.println("statement_commit_result_set=" + resultSet);
                System.out.println("statement_commit_update_count=" + statement.getUpdateCount());
                SQLWarning warning = statement.getWarnings();
                System.out.println("statement_commit_warning=" + (warning == null ? "none" : warning.getMessage()));
            }
            System.out.println("statement_commit_state_after=" + pg.getTransactionState());
        }
    }

    private static void isolation(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            raw.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
            raw.setAutoCommit(false);
            try (Statement statement = raw.createStatement();
                 ResultSet rows = statement.executeQuery("select current_setting('transaction_isolation')")) {
                rows.next();
                System.out.println("isolation_after_set=" + rows.getString(1));
            }
            raw.rollback();
        }
        try (Connection raw = connect(url, user, password, "ppcs-jdbc-probe")) {
            raw.setAutoCommit(false);
            try (Statement statement = raw.createStatement();
                 ResultSet rows = statement.executeQuery("select current_setting('transaction_isolation')")) {
                rows.next();
                System.out.println("isolation_default=" + rows.getString(1));
            }
            raw.rollback();
        }
    }

    private static void setup(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("create table item (id serial primary key, name text, qty int)");
            statement.execute("create table uniq (id serial primary key, code text unique)");
            statement.execute("insert into uniq (code) values ('taken')");
        }
    }

    private static boolean visible(Connection observer, String name) throws SQLException {
        try (PreparedStatement statement = observer.prepareStatement("select 1 from item where name = ?")) {
            statement.setString(1, name);
            try (ResultSet rows = statement.executeQuery()) {
                return rows.next();
            }
        }
    }

    private static Connection connect(String url, String user, String password, String applicationName) throws SQLException {
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("ApplicationName", applicationName);
        return DriverManager.getConnection(url, properties);
    }
}
