package org.ppcs.springtx;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Map;
import java.util.Properties;

import javax.sql.DataSource;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import org.postgresql.jdbc.PgConnection;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DataSourceUtils;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.TransactionSystemException;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Standalone observations against the disposable PostgreSQL. Not the adapter protocol.
 * Usage: java -cp ... org.ppcs.springtx.Probe path-to-ppcs-instance.json
 *
 * <p>Refuses a server whose {@code cluster_name} is not that file's token, creates
 * {@code ppcs_springtx_probe}, and drops it. Prints {@code key=value} lines.
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
        try (Connection admin = connect(adminUrl, user, password, "ppcs-springtx-probe")) {
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
                statement.execute("drop database if exists ppcs_springtx_probe with (force)");
                statement.execute("create database ppcs_springtx_probe");
            }
        }
        String url = "jdbc:postgresql://" + host + ":" + port + "/ppcs_springtx_probe";
        try {
            commitState(url, user, password);
            release(url, user, password);
            templateAbortedCommit(url, user, password);
            rollbackOnly(url, user, password, false);
            rollbackOnly(url, user, password, true);
            checkedSqlDefault(url, user, password);
            savepointFault(url, user, password, "client-reject");
            savepointFault(url, user, password, "rewrite");
            rollbackWithhold(url, user, password);
        } finally {
            try (Connection admin = connect(adminUrl, user, password, "ppcs-springtx-probe");
                 Statement statement = admin.createStatement()) {
                statement.execute("drop database if exists ppcs_springtx_probe with (force)");
            }
        }
    }

    /** Does Connection.commit() return while the driver still reports a transaction in progress? */
    private static void commitState(String url, String user, String password) throws SQLException {
        try (Connection raw = connect(url, user, password, "ppcs-springtx-probe")) {
            PgConnection pg = raw.unwrap(PgConnection.class);
            pg.setAutoCommit(false);
            try (Statement statement = pg.createStatement()) {
                statement.execute("select 1");
            }
            String before = String.valueOf(pg.getTransactionState());
            pg.commit();
            String after = String.valueOf(pg.getTransactionState());
            System.out.println("commit_state_before=" + before);
            System.out.println("commit_state_after=" + after);
            System.out.println("commit_returned_while_in_progress=" + !"IDLE".equals(after));
        }
    }

    /** DriverManagerDataSource.releaseConnection, then two TransactionTemplate calls. */
    private static void release(String url, String user, String password) throws SQLException {
        DriverManagerDataSource dataSource = dataSource(url, user, password);
        try (Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            Connection open = dataSource.getConnection();
            open.setAutoCommit(false);
            int openPid = pid(open);
            DataSourceUtils.releaseConnection(open, dataSource);
            System.out.println("release_open_pid=" + openPid);
            System.out.println("release_open_closed=" + open.isClosed());
            System.out.println("release_open_present=" + present(observer, openPid));
            DataSourceTransactionManager manager = new DataSourceTransactionManager(dataSource);
            TransactionTemplate template = new TransactionTemplate(manager);
            int first = template.execute(status -> queryPid(dataSource));
            boolean firstPresent = present(observer, first);
            int second = template.execute(status -> queryPid(dataSource));
            System.out.println("release_template1_pid=" + first);
            System.out.println("release_template1_present_after_return=" + firstPresent);
            System.out.println("release_template2_pid=" + second);
            System.out.println("release_template_same_backend=" + (first == second));
        }
    }

    /** Caught unique violation, then a normal TransactionTemplate return. Observer reads the fate. */
    private static void templateAbortedCommit(String url, String user, String password) throws SQLException {
        DriverManagerDataSource dataSource = dataSource(url, user, password);
        try (Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            DataSourceTransactionManager manager = new DataSourceTransactionManager(dataSource);
            TransactionTemplate template = new TransactionTemplate(manager);
            String[] xid = new String[1];
            String[] state = new String[1];
            String[] sqlState = new String[1];
            Throwable escaped = null;
            try {
                template.execute(status -> {
                    try {
                        update(dataSource, "insert into item (name, qty) values (?, 0)", "aborted-marker");
                        xid[0] = queryString(dataSource, "select pg_current_xact_id()::text");
                        try {
                            update(dataSource, "insert into uniq (code) values (?)", "taken");
                        } catch (SQLException ex) {
                            sqlState[0] = ex.getSQLState();
                        }
                        state[0] = transactionState(dataSource);
                    } catch (SQLException ex) {
                        throw new IllegalStateException(ex);
                    }
                    return null;
                });
            } catch (Throwable ex) {
                escaped = ex;
            }
            System.out.println("aborted_commit_sqlstate=" + sqlState[0]);
            System.out.println("aborted_commit_state_before_return=" + state[0]);
            System.out.println("aborted_commit_escaped=" + name(escaped));
            System.out.println("aborted_commit_fate=" + fate(observer, xid[0]));
            System.out.println("aborted_commit_visible=" + count(observer, "aborted-marker"));
            System.out.println("aborted_commit_thread_bound=" + TransactionSynchronizationManager.hasResource(dataSource));
        }
    }

    /** Inner PROPAGATION_REQUIRED marks the shared transaction rollback-only. The outer catches and returns. */
    private static void rollbackOnly(String url, String user, String password, boolean declarative) throws Exception {
        DriverManagerDataSource dataSource = dataSource(url, user, password);
        String prefix = declarative ? "rollback_only_declarative" : "rollback_only_programmatic";
        try (Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            DataSourceTransactionManager manager = new DataSourceTransactionManager(dataSource);
            String[] xid = new String[1];
            Throwable escaped = null;
            try {
                if (declarative) {
                    TxOps ops = proxy(manager);
                    ops.required(() -> {
                        update(dataSource, "insert into item (name, qty) values (?, 0)", prefix + "-outer");
                        xid[0] = queryString(dataSource, "select pg_current_xact_id()::text");
                        try {
                            ops.required(() -> {
                                update(dataSource, "insert into item (name, qty) values (?, 0)", prefix + "-inner");
                                throw new RuntimeException("inner");
                            });
                        } catch (RuntimeException ex) {
                            if (!"inner".equals(ex.getMessage())) throw ex;
                        }
                    });
                } else {
                    TransactionTemplate outer = new TransactionTemplate(manager);
                    TransactionTemplate inner = new TransactionTemplate(manager);
                    outer.execute(status -> {
                        try {
                            update(dataSource, "insert into item (name, qty) values (?, 0)", prefix + "-outer");
                            xid[0] = queryString(dataSource, "select pg_current_xact_id()::text");
                            try {
                                inner.execute(ignored -> {
                                    try {
                                        update(dataSource, "insert into item (name, qty) values (?, 0)", prefix + "-inner");
                                    } catch (SQLException ex) {
                                        throw new IllegalStateException(ex);
                                    }
                                    throw new RuntimeException("inner");
                                });
                            } catch (RuntimeException ex) {
                                if (!"inner".equals(ex.getMessage())) throw ex;
                            }
                        } catch (SQLException ex) {
                            throw new IllegalStateException(ex);
                        }
                        return null;
                    });
                }
            } catch (Throwable ex) {
                escaped = ex;
            }
            System.out.println(prefix + "_escaped=" + name(escaped));
            System.out.println(prefix + "_application=" + applicationName(escaped));
            System.out.println(prefix + "_fate=" + fate(observer, xid[0]));
            System.out.println(prefix + "_outer_visible=" + count(observer, prefix + "-outer"));
            System.out.println(prefix + "_inner_visible=" + count(observer, prefix + "-inner"));
            System.out.println(prefix + "_thread_bound=" + TransactionSynchronizationManager.hasResource(dataSource));
            System.out.println(prefix + "_synchronization_active=" + TransactionSynchronizationManager.isSynchronizationActive());
        }
    }

    /** Default @Transactional does not roll back a checked SQLException. The duplicate insert is a real 23505. */
    private static void checkedSqlDefault(String url, String user, String password) throws Exception {
        DriverManagerDataSource raw = dataSource(url, user, password);
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        DataSource dataSource = new FaultingDataSource(raw, fault, pid -> { });
        try (Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            TxOps ops = proxy(new DataSourceTransactionManager(dataSource));
            String[] xid = new String[1];
            Throwable escaped = null;
            try {
                ops.required(() -> {
                    update(dataSource, "insert into item (name, qty) values (?, 0)", "checked-marker");
                    xid[0] = queryString(dataSource, "select pg_current_xact_id()::text");
                    update(dataSource, "insert into uniq (code) values (?)", "taken");
                });
            } catch (Throwable ex) {
                escaped = ex;
            }
            System.out.println("checked_sql_escaped=" + name(escaped));
            System.out.println("checked_sql_application=" + applicationName(escaped));
            System.out.println("checked_sql_code=" + (escaped == null ? null : FaultingDataSource.Fault.sqlState(escaped)));
            System.out.println("checked_sql_fate=" + fate(observer, xid[0]));
            System.out.println("checked_sql_visible=" + count(observer, "checked-marker"));
            System.out.println("checked_sql_trace=" + fault.trace);
        }
    }

    /**
     * Nested savepoint rollback, withheld before send or rewritten so PostgreSQL answers.
     * The outer callback catches the nested failure and returns normally.
     */
    private static void savepointFault(String url, String user, String password, String mode) throws SQLException {
        DriverManagerDataSource raw = dataSource(url, user, password);
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        DataSource exposed = new FaultingDataSource(raw, fault, pid -> { });
        String prefix = "savepoint-" + mode;
        try (Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            DataSourceTransactionManager manager = new DataSourceTransactionManager(exposed);
            TransactionTemplate outer = new TransactionTemplate(manager);
            TransactionTemplate nested = new TransactionTemplate(manager);
            nested.setPropagationBehavior(TransactionTemplate.PROPAGATION_NESTED);
            String[] xid = new String[1];
            Throwable[] nestedEscaped = new Throwable[1];
            Throwable outerEscaped = null;
            try {
                outer.execute(status -> {
                    try {
                        update(exposed, "insert into item (name, qty) values (?, 0)", prefix + "-outer");
                        xid[0] = queryString(exposed, "select pg_current_xact_id()::text");
                        try {
                            nested.execute(ignored -> {
                                try {
                                    update(exposed, "insert into item (name, qty) values (?, 0)", prefix + "-inner");
                                } catch (SQLException ex) {
                                    throw new IllegalStateException(ex);
                                }
                                fault.arm(FaultingDataSource.Fault.SAVEPOINT, mode);
                                throw new RuntimeException("nested");
                            });
                        } catch (RuntimeException ex) {
                            nestedEscaped[0] = ex;
                        }
                    } catch (SQLException ex) {
                        throw new IllegalStateException(ex);
                    }
                    return null;
                });
            } catch (Throwable ex) {
                outerEscaped = ex;
            }
            System.out.println(prefix + "_fired=" + fault.fired);
            System.out.println(prefix + "_reply=" + (fault.replyCodes.isEmpty() ? "none" : fault.replyCodes.get(0)));
            System.out.println(prefix + "_nested=" + name(nestedEscaped[0]));
            System.out.println(prefix + "_nested_application=" + applicationName(nestedEscaped[0]));
            System.out.println(prefix + "_outer=" + name(outerEscaped));
            System.out.println(prefix + "_fate=" + fate(observer, xid[0]));
            System.out.println(prefix + "_outer_visible=" + count(observer, prefix + "-outer"));
            System.out.println(prefix + "_inner_visible=" + count(observer, prefix + "-inner"));
        }
    }

    /** Withheld top-level ROLLBACK. Spring then restores autocommit. A second template uses HikariCP of size 1. */
    private static void rollbackWithhold(String url, String user, String password) throws SQLException {
        HikariConfig hikari = new HikariConfig();
        hikari.setJdbcUrl(url);
        hikari.setUsername(user);
        hikari.setPassword(password);
        hikari.setMaximumPoolSize(1);
        try (HikariDataSource pooled = new HikariDataSource(hikari);
             Connection observer = connect(url, user, password, "ppcs-springtx-probe-observer")) {
            setup(observer);
            FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
            DataSource exposed = new FaultingDataSource(pooled, fault, pid -> { });
            DataSourceTransactionManager manager = new DataSourceTransactionManager(exposed);
            TransactionTemplate template = new TransactionTemplate(manager);
            String[] xid = new String[1];
            Integer[] pid = new Integer[1];
            Throwable escaped = null;
            try {
                template.execute(status -> {
                    try {
                        update(exposed, "insert into item (name, qty) values (?, 0)", "withhold-doomed");
                        xid[0] = queryString(exposed, "select pg_current_xact_id()::text");
                        pid[0] = queryInt(exposed, "select pg_backend_pid()");
                    } catch (SQLException ex) {
                        throw new IllegalStateException(ex);
                    }
                    fault.arm(FaultingDataSource.Fault.ROOT, "client-reject");
                    throw new RuntimeException("unit");
                });
            } catch (Throwable ex) {
                escaped = ex;
            }
            fault.disarm();
            String fateAtReport = fate(observer, xid[0]);
            int visibleAtReport = count(observer, "withhold-doomed");
            Integer second = null;
            Throwable secondEscaped = null;
            try {
                second = template.execute(status -> {
                    try {
                        update(exposed, "insert into item (name, qty) values (?, 0)", "withhold-next");
                        return queryInt(exposed, "select pg_backend_pid()");
                    } catch (SQLException ex) {
                        throw new IllegalStateException(ex);
                    }
                });
            } catch (Throwable ex) {
                secondEscaped = ex;
            }
            System.out.println("rollback_withhold_fired=" + fault.fired);
            System.out.println("rollback_withhold_escaped=" + name(escaped));
            System.out.println("rollback_withhold_application=" + applicationName(escaped));
            System.out.println("rollback_withhold_fate=" + fateAtReport);
            System.out.println("rollback_withhold_visible=" + visibleAtReport);
            System.out.println("rollback_withhold_pid=" + pid[0]);
            System.out.println("rollback_withhold_second_pid=" + second);
            System.out.println("rollback_withhold_same_backend=" + (pid[0] != null && pid[0].equals(second)));
            System.out.println("rollback_withhold_second=" + name(secondEscaped));
            System.out.println("rollback_withhold_next_visible=" + count(observer, "withhold-next"));
            System.out.println("rollback_withhold_thread_bound=" + TransactionSynchronizationManager.hasResource(exposed));
        }
    }

    private static TxOps proxy(DataSourceTransactionManager manager) {
        TransactionInterceptor interceptor = new TransactionInterceptor();
        interceptor.setTransactionManager(manager);
        interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        interceptor.afterPropertiesSet();
        ProxyFactory factory = new ProxyFactory(new TxTarget());
        factory.setInterfaces(TxOps.class);
        factory.addAdvice(interceptor);
        return (TxOps) factory.getProxy();
    }

    private static DriverManagerDataSource dataSource(String url, String user, String password) {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.postgresql.Driver");
        dataSource.setUrl(url);
        dataSource.setUsername(user);
        dataSource.setPassword(password);
        return dataSource;
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

    private static void update(DataSource dataSource, String sql, String value) throws SQLException {
        Connection connection = DataSourceUtils.getConnection(dataSource);
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, value);
            statement.executeUpdate();
        } finally {
            DataSourceUtils.releaseConnection(connection, dataSource);
        }
    }

    private static String queryString(DataSource dataSource, String sql) throws SQLException {
        Connection connection = DataSourceUtils.getConnection(dataSource);
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery(sql)) {
            if (!rows.next()) throw new SQLException(sql + " returned no row");
            return rows.getString(1);
        } finally {
            DataSourceUtils.releaseConnection(connection, dataSource);
        }
    }

    private static int queryInt(DataSource dataSource, String sql) throws SQLException {
        return Integer.parseInt(queryString(dataSource, sql));
    }

    private static int queryPid(DataSource dataSource) {
        try {
            return queryInt(dataSource, "select pg_backend_pid()");
        } catch (SQLException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static String transactionState(DataSource dataSource) throws SQLException {
        Connection connection = DataSourceUtils.getConnection(dataSource);
        try {
            return String.valueOf(connection.unwrap(PgConnection.class).getTransactionState());
        } finally {
            DataSourceUtils.releaseConnection(connection, dataSource);
        }
    }

    private static Connection connect(String url, String user, String password, String applicationName) throws SQLException {
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("password", password);
        properties.setProperty("ApplicationName", applicationName);
        return DriverManager.getConnection(url, properties);
    }

    private static int pid(Connection connection) throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery("select pg_backend_pid()")) {
            rows.next();
            return rows.getInt(1);
        }
    }

    private static boolean present(Connection observer, int pid) throws SQLException {
        try (PreparedStatement statement = observer.prepareStatement("select 1 from pg_stat_activity where pid = ?")) {
            statement.setInt(1, pid);
            try (ResultSet rows = statement.executeQuery()) {
                return rows.next();
            }
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

    private static String name(Throwable error) {
        return error == null ? "none" : error.getClass().getSimpleName();
    }

    private static String applicationName(Throwable error) {
        if (error instanceof TransactionSystemException system && system.getApplicationException() != null) {
            return system.getApplicationException().getClass().getSimpleName();
        }
        return "none";
    }
}
