package org.ppcs.springjdbc;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Map;

import org.postgresql.jdbc.PgConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DataSourceUtils;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * One-off probes. Not the adapter protocol. Arguments: commit|release host port user password database.
 */
public final class Probes {
    public static void main(String[] args) throws Exception {
        if (Runtime.version().feature() < 21) {
            System.err.println("requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        if (args.length != 2) {
            System.err.println("usage: Probes commit|release path-to-ppcs-instance.json");
            System.exit(2);
        }
        Map<String, Object> instance = Json.object(Json.parse(Files.readString(Path.of(args[1]))));
        String url = "jdbc:postgresql://" + Json.text(instance, "host") + ":" + Json.integer(instance, "port")
                + "/postgres?ApplicationName=ppcs-probe";
        String user = Json.text(instance, "user");
        String password = Json.text(instance, "password");
        if (args[0].equals("commit")) commit(url, user, password);
        else if (args[0].equals("release")) release(url, user, password);
        else {
            System.err.println("unknown probe " + args[0]);
            System.exit(2);
        }
    }

    /** Does Connection.commit() return while the driver still reports a transaction in progress? */
    private static void commit(String url, String user, String password) throws SQLException {
        try (Connection raw = DriverManager.getConnection(url, user, password)) {
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.execute("select 1");
            }
            String before = String.valueOf(pg.getTransactionState());
            pg.commit();
            String after = String.valueOf(pg.getTransactionState());
            System.out.println("transaction_state_before=" + before);
            System.out.println("transaction_state_after=" + after);
            System.out.println("commit_returned_while_in_progress=" + !"IDLE".equals(after));
        }
    }

    /**
     * DriverManagerDataSource plus DataSourceUtils.releaseConnection, and the same
     * DataSource under TransactionTemplate. Prints whether a later unit sees the same backend.
     */
    private static void release(String url, String user, String password) throws SQLException {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.postgresql.Driver");
        dataSource.setUrl(url);
        dataSource.setUsername(user);
        dataSource.setPassword(password);
        try (Connection observer = DriverManager.getConnection(url, user, password)) {
            Connection open = dataSource.getConnection();
            open.setAutoCommit(false);
            int openPid = pid(open);
            DataSourceUtils.releaseConnection(open, dataSource);
            System.out.println("open_pid=" + openPid);
            System.out.println("open_connection_closed=" + open.isClosed());
            System.out.println("open_pid_present_after_release=" + present(observer, openPid));

            DataSourceTransactionManager manager = new DataSourceTransactionManager(dataSource);
            TransactionTemplate template = new TransactionTemplate(manager);
            JdbcTemplate jdbc = new JdbcTemplate(dataSource);
            int first = template.execute(status -> jdbc.queryForObject("select pg_backend_pid()", Integer.class));
            boolean firstPresent = present(observer, first);
            int second = template.execute(status -> jdbc.queryForObject("select pg_backend_pid()", Integer.class));
            System.out.println("template1_pid=" + first);
            System.out.println("template1_present_after_return=" + firstPresent);
            System.out.println("template2_pid=" + second);
            System.out.println("template_same_backend=" + (first == second));
        }
    }

    private static int pid(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery("select pg_backend_pid()")) {
            if (!rows.next()) throw new SQLException("pg_backend_pid returned no row");
            return rows.getInt(1);
        }
    }

    private static boolean present(Connection observer, int pid) throws SQLException {
        try (PreparedStatement statement = observer.prepareStatement(
                "select 1 from pg_stat_activity where pid = ? and datname = current_database()")) {
            statement.setInt(1, pid);
            try (ResultSet rows = statement.executeQuery()) {
                return rows.next();
            }
        }
    }
}
