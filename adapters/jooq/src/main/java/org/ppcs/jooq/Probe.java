package org.ppcs.jooq;

import java.lang.reflect.InvocationTargetException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.SQLWarning;
import java.sql.Statement;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicInteger;

import org.jooq.DSLContext;
import org.jooq.SQLDialect;
import org.jooq.exception.DataAccessException;
import org.jooq.impl.DSL;
import org.postgresql.jdbc.PgConnection;

/**
 * Observations that are not catalog cases. Refuses a server whose
 * {@code cluster_name} is not the instance file's token.
 *
 * <p>Usage: {@code java -cp ... org.ppcs.jooq.Probe path-to-ppcs-instance.json}
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
        try (Connection admin = connect(adminUrl, user, password, "ppcs-jooq-probe")) {
            String cluster = query(admin, "select current_setting('cluster_name')");
            if (!token.equals(cluster)) {
                System.err.println("cluster_name does not match the instance token; refusing to continue");
                System.exit(2);
            }
            try (Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_jooq_probe with (force)");
                statement.execute("create database ppcs_jooq_probe");
            }
        }
        String url = "jdbc:postgresql://" + host + ":" + port + "/ppcs_jooq_probe";
        try {
            System.out.println("jooq=" + bundleVersion(DSLContext.class));
            System.out.println("pgjdbc=" + bundleVersion(org.postgresql.Driver.class));
            System.out.println("java=" + Runtime.version());
            escape(url, user, password);
            catchThenCommit(url, user, password);
            statementCommitTag(url, user, password);
            isolationBeforeStart(url, user, password);
            isolationAfterStart(url, user, password);
        } finally {
            try (Connection admin = connect(adminUrl, user, password, "ppcs-jooq-probe");
                 Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_jooq_probe with (force)");
            }
        }
    }

    /** The callback lets the unique violation escape. jOOQ should roll back, not commit. */
    private static void escape(String url, String user, String password) throws SQLException {
        Counts counts = new Counts();
        try (Connection observer = connect(url, user, password, "ppcs-jooq-probe-observer");
             Connection raw = counted(connect(url, user, password, "ppcs-jooq-probe"), counts)) {
            setup(raw);
            DSLContext dsl = DSL.using(raw, SQLDialect.POSTGRES);
            String[] xid = new String[1];
            boolean returned = false;
            String thrown = "none";
            try {
                dsl.transaction(tx -> {
                    tx.dsl().execute("insert into item (name) values (?)", "escape-marker");
                    xid[0] = tx.dsl().fetchOne("select pg_current_xact_id()::text").get(0, String.class);
                    tx.dsl().execute("insert into uniq (code) values (?)", "taken");
                });
                returned = true;
            } catch (RuntimeException ex) {
                thrown = ex.getClass().getSimpleName() + " " + (ex instanceof DataAccessException data ? data.sqlState() : "");
            }
            System.out.println("escape_returned=" + returned);
            System.out.println("escape_thrown=" + thrown.trim());
            System.out.println("escape_commit_calls=" + counts.commit.get());
            System.out.println("escape_rollback_calls=" + counts.rollback.get());
            System.out.println("escape_fate=" + fate(observer, xid[0]));
            System.out.println("escape_visible=" + visible(observer, "escape-marker"));
        }
    }

    /** The callback catches 23505 and returns. This is the catalog shape, printed with the driver state. */
    private static void catchThenCommit(String url, String user, String password) throws SQLException {
        Counts counts = new Counts();
        try (Connection observer = connect(url, user, password, "ppcs-jooq-probe-observer");
             Connection raw = counted(connect(url, user, password, "ppcs-jooq-probe"), counts)) {
            setup(raw);
            DSLContext dsl = DSL.using(raw, SQLDialect.POSTGRES);
            String[] xid = new String[1];
            String[] stateBeforeCommit = new String[1];
            boolean returned = false;
            try {
                dsl.transaction(tx -> {
                    tx.dsl().execute("insert into item (name) values (?)", "catch-marker");
                    xid[0] = tx.dsl().fetchOne("select pg_current_xact_id()::text").get(0, String.class);
                    try {
                        tx.dsl().execute("insert into uniq (code) values (?)", "taken");
                    } catch (DataAccessException ex) {
                        System.out.println("catch_violation=" + ex.sqlState());
                        stateBeforeCommit[0] = raw.unwrap(PgConnection.class).getTransactionState().name();
                    }
                });
                returned = true;
            } catch (RuntimeException ex) {
                System.out.println("catch_escaped=" + ex.getClass().getSimpleName());
            }
            System.out.println("catch_returned=" + returned);
            System.out.println("catch_state_before_commit=" + stateBeforeCommit[0]);
            System.out.println("catch_commit_calls=" + counts.commit.get());
            System.out.println("catch_rollback_calls=" + counts.rollback.get());
            System.out.println("catch_fate=" + fate(observer, xid[0]));
            System.out.println("catch_visible=" + visible(observer, "catch-marker"));
        }
    }

    private static void statementCommitTag(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-jooq-probe")) {
            setup(raw);
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.executeUpdate("insert into item (name) values ('tag-marker')");
                try {
                    statement.executeUpdate("insert into uniq (code) values ('taken')");
                } catch (SQLException ignored) {
                    // The transaction is aborted. The next execute is COMMIT as a statement.
                }
                boolean resultSet = statement.execute("COMMIT");
                SQLWarning warning = statement.getWarnings();
                System.out.println("statement_commit_result_set=" + resultSet);
                System.out.println("statement_commit_update_count=" + statement.getUpdateCount());
                System.out.println("statement_commit_warning=" + (warning == null ? "none" : warning.getSQLState()));
                System.out.println("statement_commit_state_after=" + pg.getTransactionState());
            }
        }
    }

    private static void isolationBeforeStart(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-jooq-probe")) {
            raw.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
            raw.setAutoCommit(false);
            System.out.println("isolation_before_start=" + query(raw, "select current_setting('transaction_isolation')"));
            raw.rollback();
        }
    }

    /** setTransactionIsolation after the first statement has opened the transaction. */
    private static void isolationAfterStart(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-jooq-probe")) {
            raw.setAutoCommit(false);
            query(raw, "select 1");
            try {
                raw.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
                System.out.println("isolation_after_start=" + query(raw, "select current_setting('transaction_isolation')"));
            } catch (SQLException ex) {
                System.out.println("isolation_after_start_sqlstate=" + ex.getSQLState());
                System.out.println("isolation_after_start_error=" + ex.getMessage().replaceAll("\\s+", " ").trim());
                System.out.println("isolation_after_start_level=" + query(raw, "select current_setting('transaction_isolation')"));
            }
            raw.rollback();
        }
    }

    private static String bundleVersion(Class<?> type) throws Exception {
        var source = type.getProtectionDomain().getCodeSource();
        try (java.util.jar.JarFile jar = new java.util.jar.JarFile(new java.io.File(source.getLocation().toURI()))) {
            String bundle = jar.getManifest().getMainAttributes().getValue("Bundle-Version");
            if (bundle != null && !bundle.isBlank()) return bundle;
            String implementation = jar.getManifest().getMainAttributes().getValue("Implementation-Version");
            return implementation == null ? "unknown" : implementation;
        }
    }

    private static void setup(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("drop table if exists item");
            statement.execute("drop table if exists uniq");
            statement.execute("create table item (id serial primary key, name text, qty int)");
            statement.execute("create table uniq (id serial primary key, code text unique)");
            statement.execute("insert into uniq (code) values ('taken')");
        }
    }

    private static String fate(Connection observer, String xid) throws SQLException {
        if (xid == null) return "none";
        try (var statement = observer.prepareStatement("select pg_xact_status(?::xid8)")) {
            statement.setString(1, xid);
            try (ResultSet rows = statement.executeQuery()) {
                rows.next();
                return rows.getString(1);
            }
        }
    }

    private static boolean visible(Connection observer, String name) throws SQLException {
        try (var statement = observer.prepareStatement("select 1 from item where name = ?")) {
            statement.setString(1, name);
            try (ResultSet rows = statement.executeQuery()) {
                return rows.next();
            }
        }
    }

    private static String query(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery(sql)) {
            rows.next();
            return rows.getString(1);
        }
    }

    private static Connection connect(String url, String user, String password, String applicationName) throws SQLException {
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("ApplicationName", applicationName);
        return DriverManager.getConnection(url, properties);
    }

    private static Connection counted(Connection raw, Counts counts) {
        return (Connection) java.lang.reflect.Proxy.newProxyInstance(
                Connection.class.getClassLoader(),
                new Class<?>[] {Connection.class},
                (proxy, method, args) -> {
                    String name = method.getName();
                    if ("commit".equals(name) && (args == null || args.length == 0)) counts.commit.incrementAndGet();
                    if ("rollback".equals(name) && (args == null || args.length == 0)) counts.rollback.incrementAndGet();
                    try {
                        return method.invoke(raw, args == null ? new Object[0] : args);
                    } catch (InvocationTargetException ex) {
                        Throwable cause = ex.getCause();
                        if (cause instanceof RuntimeException runtime) throw runtime;
                        if (cause instanceof Error error) throw error;
                        if (cause instanceof SQLException sql) throw sql;
                        throw ex;
                    }
                });
    }

    private static final class Counts {
        final AtomicInteger commit = new AtomicInteger();
        final AtomicInteger rollback = new AtomicInteger();
    }
}
