package org.ppcs.hibernate;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicReference;

import org.hibernate.SessionFactory;

/**
 * Standalone observations. Not the adapter protocol.
 * Usage: java -cp ... org.ppcs.hibernate.Probe path-to-ppcs-instance.json
 *
 * <p>Refuses a server whose {@code cluster_name} is not that file's token, creates
 * {@code ppcs_hibernate_probe}, and drops it. Prints {@code key=value} lines.
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
        try (Connection admin = connect(adminUrl, user, password, "ppcs-hibernate-probe")) {
            String cluster = queryString(admin, "select current_setting('cluster_name')");
            if (!token.equals(cluster)) {
                System.err.println("cluster_name does not match the instance token; refusing to continue");
                System.exit(2);
            }
            try (Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_hibernate_probe with (force)");
                statement.execute("create database ppcs_hibernate_probe");
            }
        }
        String url = "jdbc:postgresql://" + host + ":" + port + "/ppcs_hibernate_probe";
        try {
            try (Connection observer = connect(url, user, password, "ppcs-hibernate-probe-observer")) {
                setup(observer);
                commitState(url, user, password);
                paths(url, user, password, observer);
                backends(url, user, password);
            }
        } finally {
            try (Connection admin = connect(adminUrl, user, password, "ppcs-hibernate-probe");
                 Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_hibernate_probe with (force)");
            }
        }
    }

    /** Does Connection.commit() return while pgjdbc still reports a transaction in progress? */
    private static void commitState(String url, String user, String password) {
        Run run = open(url, user, password);
        try {
            AtomicReference<Object> marker = new AtomicReference<>();
            Boundary.Outcome outcome = Boundary.run(run.factory, run.traced, false, marker, (session, tx) -> {
                marker.set(Observe.insertItem(session, "commit-state"));
            });
            String after = "missing";
            for (Map<String, Object> event : outcome.completionJdbc) {
                if ("Connection.commit".equals(event.get("call"))) after = String.valueOf(event.get("state_after"));
            }
            System.out.println("commit_state_after=" + after);
            System.out.println("commit_returned_while_in_progress=" + !"IDLE".equals(after));
            System.out.println("commit_reported=" + outcome.reported);
        } finally {
            run.close();
        }
    }

    private static void paths(String url, String user, String password, Connection observer) throws SQLException {
        path(url, user, password, observer, "entity", (session, tx) -> {
            Uniq uniq = new Uniq("taken");
            String phase = "persist";
            try {
                session.persist(uniq);
                phase = "flush";
                session.flush();
            } catch (RuntimeException ex) {
                throw new PathException(phase, ex);
            }
        });
        path(url, user, password, observer, "native-sql", (session, tx) -> {
            try {
                session.createNativeMutationQuery("insert into uniq (code) values ('taken')").executeUpdate();
            } catch (RuntimeException ex) {
                throw new PathException("executeUpdate", ex);
            }
        });
        path(url, user, password, observer, "dowork", (session, tx) -> {
            try {
                session.doWork(connection -> {
                    try (var statement = connection.prepareStatement("insert into uniq (code) values (?)")) {
                        statement.setString(1, "taken");
                        statement.executeUpdate();
                    }
                });
            } catch (RuntimeException ex) {
                throw new PathException("doWork", ex);
            }
        });
    }

    private static void path(String url, String user, String password, Connection observer, String name, Boundary.Work failing) throws SQLException {
        Run run = open(url, user, password);
        try {
            AtomicReference<Object> marker = new AtomicReference<>();
            AtomicReference<String> xid = new AtomicReference<>();
            AtomicReference<String> phase = new AtomicReference<>("none");
            AtomicReference<Map<String, Object>> beforeCommit = new AtomicReference<>();
            AtomicReference<Map<String, Object>> violation = new AtomicReference<>();
            Boundary.Outcome outcome = Boundary.run(run.factory, run.traced, false, marker, (session, tx) -> {
                marker.set(Observe.insertItem(session, name + "-marker"));
                xid.set(Observe.identify(session, run.sql, run.fault, false).xid());
                try {
                    failing.run(session, tx);
                    throw new IllegalStateException("the duplicate insert did not raise");
                } catch (PathException ex) {
                    phase.set(ex.phase);
                    violation.set(Errors.info(ex.getCause()));
                    beforeCommit.set(Observe.context(session, tx, marker.get()));
                }
            });
            boolean commitCalled = outcome.completionJdbc.stream().anyMatch(event -> "Connection.commit".equals(event.get("call")));
            boolean rollbackCalled = outcome.completionJdbc.stream().anyMatch(event -> "Connection.rollback".equals(event.get("call")));
            System.out.println(name + "_phase=" + phase.get());
            System.out.println(name + "_violation=" + violation.get());
            System.out.println(name + "_before_commit=" + beforeCommit.get());
            System.out.println(name + "_reported=" + outcome.reported);
            System.out.println(name + "_after_return=" + outcome.beforeClose);
            System.out.println(name + "_commit_called=" + commitCalled);
            System.out.println(name + "_rollback_called=" + rollbackCalled);
            System.out.println(name + "_completion=" + calls(outcome));
            System.out.println(name + "_fate=" + fate(observer, xid.get()));
            System.out.println(name + "_visible=" + count(observer, name + "-marker"));
        } finally {
            run.close();
        }
    }

    /** Two checkouts from the non-pooled DataSource. */
    private static void backends(String url, String user, String password) {
        Run run = open(url, user, password);
        try {
            int[] pids = new int[2];
            for (int i = 0; i < 2; i++) {
                int index = i;
                AtomicReference<Object> marker = new AtomicReference<>();
                Boundary.run(run.factory, run.traced, false, marker, (session, tx) -> {
                    marker.set(Observe.insertItem(session, "backend-" + index));
                    pids[index] = Observe.identify(session, run.sql, run.fault, false).pid();
                });
            }
            System.out.println("driver_pid_1=" + pids[0]);
            System.out.println("driver_pid_2=" + pids[1]);
            System.out.println("driver_same_backend=" + (pids[0] == pids[1]));
        } finally {
            run.close();
        }
    }

    private static String calls(Boundary.Outcome outcome) {
        StringBuilder text = new StringBuilder();
        for (Map<String, Object> event : outcome.completionJdbc) {
            if (!text.isEmpty()) text.append(',');
            text.append(event.get("call")).append(' ').append(event.get("state_before")).append("->").append(event.get("state_after"));
            if (event.get("error") != null) text.append(' ').append(event.get("error"));
        }
        return text.toString();
    }

    private static Run open(String url, String user, String password) {
        DriverDataSource driver = new DriverDataSource(url, user, password);
        TracingDataSource traced = new TracingDataSource(driver);
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        FaultingDataSource exposed = new FaultingDataSource(traced, fault, pid -> { });
        SqlTrace sql = new SqlTrace();
        Map<String, Object> configuration = new LinkedHashMap<>();
        SessionFactory factory = Boot.open(exposed, sql, configuration);
        traced.clear();
        sql.clear();
        return new Run(factory, traced, sql, fault);
    }

    private static void setup(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("drop table if exists item");
            statement.execute("drop table if exists uniq");
            statement.execute("create table item (id serial primary key, name text not null, qty int not null default 0)");
            statement.execute("create table uniq (id serial primary key, code text not null unique)");
            statement.execute("insert into uniq (code) values ('taken')");
        }
    }

    private static Connection connect(String url, String user, String password, String applicationName) throws SQLException {
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("ApplicationName", applicationName);
        return DriverManager.getConnection(url, properties);
    }

    private static String queryString(Connection connection, String sql) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery(sql)) {
            if (!rows.next()) throw new SQLException(sql + " returned no row");
            return rows.getString(1);
        }
    }

    private static String fate(Connection observer, String xid) throws SQLException {
        if (xid == null) return "none";
        try (PreparedStatement statement = observer.prepareStatement("select pg_xact_status(?::xid8)")) {
            statement.setString(1, xid);
            try (ResultSet rows = statement.executeQuery()) {
                rows.next();
                String status = rows.getString(1);
                return status == null ? "null" : status;
            }
        }
    }

    private static int count(Connection observer, String name) throws SQLException {
        try (PreparedStatement statement = observer.prepareStatement("select count(*) from item where name = ?")) {
            statement.setString(1, name);
            try (ResultSet rows = statement.executeQuery()) {
                rows.next();
                return rows.getInt(1);
            }
        }
    }

    private record Run(SessionFactory factory, TracingDataSource traced, SqlTrace sql, FaultingDataSource.Fault fault) {
        void close() {
            try {
                factory.close();
            } catch (RuntimeException ex) {
                System.err.println("closing the SessionFactory failed: " + ex.getMessage());
            }
        }
    }

    /** Carries the phase out of the work without becoming the boundary's reported error. */
    private static final class PathException extends RuntimeException {
        final String phase;

        PathException(String phase, RuntimeException cause) {
            super(cause);
            this.phase = phase;
        }
    }
}
