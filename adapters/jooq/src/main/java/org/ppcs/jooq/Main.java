package org.ppcs.jooq;

import java.io.File;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.jar.JarFile;

import javax.sql.DataSource;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import org.jooq.DSLContext;
import org.jooq.ExecuteContext;
import org.jooq.ExecuteListener;
import org.jooq.ExecuteListenerProvider;
import org.jooq.SQLDialect;
import org.jooq.TransactionContext;
import org.jooq.TransactionListener;
import org.jooq.TransactionListenerProvider;
import org.jooq.impl.DSL;
import org.jooq.impl.DefaultConfiguration;
import org.jooq.impl.DefaultExecuteListenerProvider;
import org.jooq.impl.DefaultTransactionListenerProvider;
import org.jooq.impl.DefaultTransactionProvider;

/**
 * PPCS adapter for jOOQ's SQL DSL.
 *
 * <p>{@code native} and {@code pooled} call {@code DSLContext.transaction}.
 * {@code jdbc} and {@code jdbc-pooled} execute SQL through jOOQ and commit
 * through JDBC. Neither mode patches jOOQ.
 */
public final class Main {
    public static void main(String[] args) {
        if (Runtime.version().feature() < 21) {
            System.err.println("jooq adapter requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        new Main().run();
    }

    private void run() {
        Protocol protocol = new Protocol();
        Session session = null;
        boolean helloSent = false;
        String mode = null;
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("type", "result");
        try {
            Map<String, Object> message = protocol.read();
            if (!"case".equals(message.get("type"))) throw new Protocol.ProtocolException("expected a case message");
            mode = Json.text(message, "mode");
            session = open(protocol, message, mode);
            protocol.send(hello(session, mode));
            helloSent = true;
            Map<String, Object> outcome = Cases.dispatch(session, Json.text(Json.object(message.get("case")), "id"),
                    Json.object(message.get("markers")), messageSettings(message));
            protocol.checkpoint("after-end", null, null);
            result.put("status", "completed");
            result.putAll(outcome);
            result.put("diagnostics", session.diagnostics());
        } catch (Throwable ex) {
            if (!helloSent) protocol.send(fallbackHello(mode));
            result.put("status", "error");
            Map<String, Object> error = Errors.info(ex);
            error.put("protocol", Protocol.isProtocol(ex));
            result.put("error", error);
            if (session != null) result.put("diagnostics", session.diagnostics());
        } finally {
            if (session != null) session.close();
        }
        protocol.send(result);
    }

    private Session open(Protocol protocol, Map<String, Object> message, String mode) {
        boolean jdbc = switch (mode) {
            case "native", "pooled" -> false;
            case "jdbc", "jdbc-pooled" -> true;
            default -> throw new IllegalStateException("unknown mode \"" + mode + "\"");
        };
        boolean pooled = mode.equals("pooled") || mode.equals("jdbc-pooled");
        Map<String, Object> connection = Json.object(message.get("connection"));
        String url = "jdbc:postgresql://" + Json.text(connection, "host") + ":" + Json.integer(connection, "port")
                + "/" + Json.text(connection, "database")
                + "?ApplicationName=" + URLEncoder.encode(Json.text(connection, "application_name"), StandardCharsets.UTF_8);
        Connections.DriverDataSource driver = new Connections.DriverDataSource(url, Json.text(connection, "user"), Json.text(connection, "password"));
        Connections.Fault fault = new Connections.Fault();
        Connections.Trace trace = new Connections.Trace();
        DataSource exposedPool;
        AutoCloseable closer;
        Map<String, Object> configuration = new LinkedHashMap<>();
        if (!pooled) {
            exposedPool = driver;
            closer = () -> { };
            configuration.put("dataSource", "org.ppcs.jooq.Connections.DriverDataSource");
            configuration.put("pool", false);
        } else {
            HikariConfig hikari = new HikariConfig();
            hikari.setDataSource(driver);
            hikari.setMaximumPoolSize(1);
            HikariDataSource hikariDataSource = new HikariDataSource(hikari);
            exposedPool = hikariDataSource;
            closer = hikariDataSource;
            configuration.put("dataSource", "com.zaxxer.HikariDataSource");
            configuration.put("pool", "HikariCP");
            configuration.put("maximumPoolSize", 1);
        }
        DataSource exposed = new Connections.FaultingDataSource(exposedPool, fault, trace, protocol);
        List<String> sql = Connections.synchronizedList();
        List<String> listeners = Connections.synchronizedList();
        ExecuteListenerProvider executeListener = new DefaultExecuteListenerProvider(new ExecuteListener() {
            @Override
            public void executeStart(ExecuteContext ctx) {
                if (ctx.sql() != null && sql.size() < 200) sql.add(ctx.sql());
            }
        });
        TransactionListenerProvider transactionListener = new DefaultTransactionListenerProvider(new TransactionListener() {
            @Override
            public void beginStart(TransactionContext ctx) { listeners.add("beginStart"); }
            @Override
            public void commitStart(TransactionContext ctx) { listeners.add("commitStart"); }
            @Override
            public void commitEnd(TransactionContext ctx) { listeners.add("commitEnd"); }
            @Override
            public void rollbackStart(TransactionContext ctx) { listeners.add("rollbackStart"); }
            @Override
            public void rollbackEnd(TransactionContext ctx) { listeners.add("rollbackEnd"); }
        });
        DSLContext dsl = null;
        if (!jdbc) {
            DefaultConfiguration jooq = new DefaultConfiguration();
            jooq.set(exposed);
            jooq.set(SQLDialect.POSTGRES);
            jooq.set(executeListener);
            jooq.set(transactionListener);
            dsl = DSL.using(jooq);
            var provider = dsl.configuration().transactionProvider();
            configuration.put("transaction", "DSLContext.transaction");
            configuration.put("transactionProvider", provider.getClass().getName());
            configuration.put("transactionProviderInstalled", false);
            if (provider instanceof DefaultTransactionProvider defaults) configuration.put("nestedSavepoints", defaults.nested());
            configuration.put("dialect", "POSTGRES");
        } else {
            configuration.put("transaction", "Connection.setAutoCommit(false), Connection.commit, Connection.rollback");
            configuration.put("jooq", "SQL execution only; DSLContext.transaction is not called");
            configuration.put("dialect", "POSTGRES");
        }
        configuration.put("sql", "DSL table and field names, no generated catalog");
        configuration.put("edition", "org.jooq:jooq Open Source Edition");
        return new Session(protocol, fault, trace, exposed, closer, dsl, jdbc, executeListener, sql, listeners, configuration);
    }

    private Map<String, Object> hello(Session session, String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "jooq", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "jooq", "version", versionOf(DSLContext.class)));
        hello.put("driver", Map.of("name", "postgresql", "version", versionOf(org.postgresql.Driver.class)));
        Map<String, Object> components = new LinkedHashMap<>();
        components.put("jooq", versionOf(DSLContext.class));
        components.put("postgresql", versionOf(org.postgresql.Driver.class));
        if (session.configuration.get("pool") instanceof String) components.put("HikariCP", versionOf(HikariDataSource.class));
        hello.put("components", components);
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode);
        hello.put("configuration", session.configuration);
        return hello;
    }

    private Map<String, Object> fallbackHello(String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "jooq", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "jooq", "version", "3.21.9"));
        hello.put("driver", Map.of("name", "postgresql", "version", "42.7.14"));
        hello.put("components", Map.of());
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode == null ? "unknown" : mode);
        hello.put("configuration", Map.of());
        return hello;
    }

    private static Map<String, Object> messageSettings(Map<String, Object> message) {
        Object settings = Json.object(message.get("case")).get("settings");
        if (settings == null) return Map.of();
        return Json.object(settings);
    }

    private static String versionOf(Class<?> type) {
        Package pkg = type.getPackage();
        String version = pkg == null ? null : pkg.getImplementationVersion();
        if (version != null && !version.isBlank()) return version;
        try {
            var source = type.getProtectionDomain().getCodeSource();
            if (source != null && source.getLocation() != null) {
                try (JarFile jar = new JarFile(new File(source.getLocation().toURI()))) {
                    var attributes = jar.getManifest().getMainAttributes();
                    String bundle = attributes.getValue("Bundle-Version");
                    if (bundle != null && !bundle.isBlank()) return bundle;
                    String implementation = attributes.getValue("Implementation-Version");
                    if (implementation != null && !implementation.isBlank()) return implementation;
                }
            }
        } catch (Exception ignored) {
            // The pin in pom.xml is the version the startup failure names.
        }
        throw new IllegalStateException(type.getName() + " has no Implementation-Version or Bundle-Version");
    }

    static final class Session {
        final Protocol protocol;
        final Connections.Fault fault;
        final Connections.Trace trace;
        final DataSource dataSource;
        final AutoCloseable closer;
        final DSLContext dsl;
        final boolean jdbc;
        final ExecuteListenerProvider executeListener;
        final List<String> sql;
        final List<String> listeners;
        final Map<String, Object> configuration;
        Connection leased;

        Session(Protocol protocol, Connections.Fault fault, Connections.Trace trace, DataSource dataSource,
                AutoCloseable closer, DSLContext dsl, boolean jdbc, ExecuteListenerProvider executeListener,
                List<String> sql, List<String> listeners, Map<String, Object> configuration) {
            this.protocol = protocol;
            this.fault = fault;
            this.trace = trace;
            this.dataSource = dataSource;
            this.closer = closer;
            this.dsl = dsl;
            this.jdbc = jdbc;
            this.executeListener = executeListener;
            this.sql = sql;
            this.listeners = listeners;
            this.configuration = configuration;
        }

        String contract() {
            return jdbc ? Tx.JDBC_CONTRACT : Tx.NATIVE_CONTRACT;
        }

        ExecuteListenerProvider executeListener() {
            return executeListener;
        }

        Tx.Outcome jdbc(Integer isolation, boolean release, Tx.Body body) {
            try {
                Connection connection = dataSource.getConnection();
                DSLContext statements = Cases.dsl(connection, this);
                Tx.Outcome outcome = Tx.jdbcTop(connection, statements, release, isolation, body);
                if (!release && outcome.started) leased = connection;
                else if (!release) closeQuietly(connection);
                return outcome;
            } catch (SQLException ex) {
                Tx.Outcome outcome = new Tx.Outcome();
                outcome.started = false;
                outcome.reported = "failed";
                outcome.basis = "DataSource.getConnection threw before the transaction body ran";
                outcome.apiError = Errors.info(ex);
                return outcome;
            }
        }

        Map<String, Object> diagnostics() {
            return Connections.diagnostics(trace, sql, listeners);
        }

        void close() {
            closeQuietly(leased);
            leased = null;
            try {
                closer.close();
            } catch (Exception ignored) {
                // The result has already been decided. Shutdown is not a second outcome.
            }
        }

        private static void closeQuietly(Connection connection) {
            if (connection == null) return;
            try {
                connection.close();
            } catch (SQLException ignored) {
                // Process exit also closes it. A second close is not an outcome.
            }
        }
    }
}
