package org.ppcs.springtx;

import java.io.File;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicReference;
import java.util.jar.JarFile;

import javax.sql.DataSource;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * PPCS adapter for Spring's transaction manager, not for JdbcTemplate.
 *
 * <p>Programmatic mode calls {@link TransactionTemplate}. Declarative mode calls
 * a JDK proxy advised by Spring's transaction interceptor. Both use
 * {@link DataSourceTransactionManager} and {@code DataSourceUtils.getConnection}.
 * Writes are {@code PreparedStatement}s. There is no Spring Boot.
 */
public final class Main {
    private static final String FORM_TOP = "PROPAGATION_REQUIRED. Writes are PreparedStatement calls on the connection DataSourceUtils.getConnection returns.";
    private static final String FORM_NESTED = "Outer PROPAGATION_REQUIRED. Inner PROPAGATION_NESTED, which DataSourceTransactionManager maps to a JDBC savepoint. Not PROPAGATION_REQUIRES_NEW.";
    private static final String FORM_NEW = "Outer PROPAGATION_REQUIRED. Inner PROPAGATION_REQUIRES_NEW, which suspends the outer transaction and opens a second connection. Not a savepoint.";
    private static final String FORM_MANAGED = "Managed form: the callback runs inside the transaction and a normal return commits. Isolation is ISOLATION_SERIALIZABLE.";
    private static final String FORM_EXPLICIT = "Explicit form: PlatformTransactionManager.getTransaction returns a TransactionStatus, and the application calls commit on that handle. Isolation is ISOLATION_SERIALIZABLE. @Transactional does not return a handle, so declarative mode does not run this case.";

    public static void main(String[] args) {
        if (Runtime.version().feature() < 21) {
            System.err.println("spring-tx adapter requires Java 21 or newer; this JVM is " + Runtime.version());
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
            if (!"case".equals(message.get("type"))) {
                throw new Protocol.ProtocolException("expected a case message");
            }
            mode = Json.text(message, "mode");
            session = open(protocol, message, mode);
            protocol.send(hello(session, mode));
            helloSent = true;
            Map<String, Object> outcome = dispatch(session, message);
            protocol.checkpoint("after-end", null, null);
            result.put("status", "completed");
            result.putAll(outcome);
            result.put("diagnostics", session.diagnostics());
        } catch (Throwable ex) {
            if (!helloSent) protocol.send(fallbackHello(mode));
            result.put("status", "error");
            Map<String, Object> error = Boundaries.errInfo(ex);
            error.put("protocol", Protocol.isProtocol(ex));
            result.put("error", error);
            if (session != null) result.put("diagnostics", session.diagnostics());
        } finally {
            if (session != null) session.close();
        }
        protocol.send(result);
    }

    private Session open(Protocol protocol, Map<String, Object> message, String mode) {
        boolean declarative = mode.equals("declarative") || mode.equals("declarative-pooled");
        boolean pooled = mode.equals("pooled") || mode.equals("declarative-pooled");
        if (!mode.equals("native") && !mode.equals("declarative") && !mode.equals("pooled") && !mode.equals("declarative-pooled")) {
            throw new IllegalStateException("unknown mode \"" + mode + "\"");
        }
        Map<String, Object> connection = Json.object(message.get("connection"));
        String url = "jdbc:postgresql://" + Json.text(connection, "host") + ":" + Json.integer(connection, "port")
                + "/" + Json.text(connection, "database")
                + "?ApplicationName=" + URLEncoder.encode(Json.text(connection, "application_name"), StandardCharsets.UTF_8);
        String user = Json.text(connection, "user");
        String password = Json.text(connection, "password");
        DataSource raw;
        AutoCloseable closer;
        Map<String, Object> configuration = new LinkedHashMap<>();
        if (!pooled) {
            DriverManagerDataSource driver = new DriverManagerDataSource();
            driver.setDriverClassName("org.postgresql.Driver");
            driver.setUrl(url);
            driver.setUsername(user);
            driver.setPassword(password);
            raw = driver;
            closer = () -> { };
            configuration.put("dataSource", "org.springframework.jdbc.datasource.DriverManagerDataSource");
            configuration.put("pool", false);
        } else {
            HikariConfig hikari = new HikariConfig();
            hikari.setJdbcUrl(url);
            hikari.setUsername(user);
            hikari.setPassword(password);
            hikari.setMaximumPoolSize(1);
            HikariDataSource hikariDataSource = new HikariDataSource(hikari);
            raw = hikariDataSource;
            closer = hikariDataSource;
            configuration.put("dataSource", "com.zaxxer.hikari.HikariDataSource");
            configuration.put("pool", "HikariCP");
            configuration.put("maximumPoolSize", 1);
        }
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        DataSource exposed = new FaultingDataSource(raw, fault, pid -> protocol.checkpoint("after-fault", null, pid));
        DataSourceTransactionManager manager = new DataSourceTransactionManager(exposed);
        configuration.put("transactionManager", "DataSourceTransactionManager");
        configuration.put("nestedTransactionAllowed", manager.isNestedTransactionAllowed());
        configuration.put("rollbackOnCommitFailure", manager.isRollbackOnCommitFailure());
        configuration.put("globalRollbackOnParticipationFailure", manager.isGlobalRollbackOnParticipationFailure());
        configuration.put("failEarlyOnGlobalRollbackOnly", manager.isFailEarlyOnGlobalRollbackOnly());
        configuration.put("transactionSynchronization", synchronizationName(manager.getTransactionSynchronization()));
        configuration.put("invocation", declarative ? "TransactionInterceptor" : "TransactionTemplate");
        configuration.put("connectionAccess", "DataSourceUtils.getConnection");
        configuration.put("writes", "PreparedStatement");
        configuration.put("rollbackRule", declarative
                ? "default RuntimeException and Error; TX-03.statement-error-rollback-not-sent uses rollbackFor Exception.class"
                : "TransactionTemplate default: RuntimeException and Error. A checked SQLException is rethrown as SqlUnchecked where the case needs it to leave the callback.");
        Boundaries boundaries = new Boundaries(manager, declarative);
        return new Session(protocol, fault, exposed, new Sql(exposed, fault), boundaries, closer, mode, declarative, configuration);
    }

    private Map<String, Object> hello(Session session, String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "spring-tx", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "spring-framework", "version", versionOf(TransactionTemplate.class)));
        hello.put("driver", Map.of("name", "postgresql", "version", versionOf(org.postgresql.Driver.class)));
        Map<String, Object> components = new LinkedHashMap<>();
        components.put("spring-tx", versionOf(TransactionTemplate.class));
        components.put("spring-jdbc", versionOf(DataSourceTransactionManager.class));
        components.put("spring-aop", versionOf(org.springframework.aop.framework.ProxyFactory.class));
        components.put("spring-context", versionOf(org.springframework.context.ApplicationEventPublisherAware.class));
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
        hello.put("adapter", Map.of("name", "spring-tx", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "spring-framework", "version", "7.0.9"));
        hello.put("driver", Map.of("name", "postgresql", "version", "42.7.14"));
        hello.put("components", Map.of());
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode == null ? "unknown" : mode);
        hello.put("configuration", Map.of());
        return hello;
    }

    private Map<String, Object> dispatch(Session session, Map<String, Object> message) {
        String id = Json.text(Json.object(message.get("case")), "id");
        Map<String, Object> markers = Json.object(message.get("markers"));
        Map<String, Object> settings = messageSettings(message);
        return switch (id) {
            case "CTL-01.commit" -> top(session, markers, false);
            case "CTL-01.rollback" -> top(session, markers, true);
            case "TX-01A.caught-error-then-commit" -> caughtError(session, markers);
            case "TX-01B.conn-lost-before-commit" -> connLost(session, markers, settings);
            case "TX-02.savepoint-rollback-not-sent" -> savepoint(session, markers, settings, "not-sent");
            case "TX-02.savepoint-rollback-rejected" -> savepoint(session, markers, settings, "rejected");
            case "TX-02.conn-lost-before-savepoint-rollback" -> savepoint(session, markers, settings, "conn-lost");
            case "TX-03.rollback-not-sent" -> reuse(session, markers, settings, "rollback-not-sent");
            case "TX-03.statement-error-rollback-not-sent" -> reuse(session, markers, settings, "statement-error");
            case "TX-03.conn-lost-in-transaction" -> reuse(session, markers, settings, "conn-lost");
            case "TX-04.nested-failure-contained" -> nested(session, markers, "nested-fails");
            case "TX-04.nested-released-outer-rollback" -> nested(session, markers, "outer-fails");
            case "TX-04.independent-inner" -> independent(session, markers);
            case "TX-05.managed-serializable" -> managedIsolation(session, markers, settings);
            case "TX-05.explicit-serializable" -> explicitIsolation(session, markers, settings);
            default -> throw new IllegalStateException("this adapter does not implement " + id);
        };
    }

    private Map<String, Object> top(Session session, Map<String, Object> markers, boolean rollback) {
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "tx"));
            Sql.Ident ident = session.sql.identify(false);
            session.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            if (rollback) throw new AppException("application error: the request fails");
        });
        return formed(outcome, form(session, FORM_TOP));
    }

    private Map<String, Object> caughtError(Session session, Map<String, Object> markers) {
        Map<String, Object>[] violation = new Map[1];
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "tx"));
            Sql.Ident ident = session.sql.identify(false);
            session.protocol.checkpoint("after-write", ident.xid(), ident.pid());
            try {
                session.sql.insertTaken();
            } catch (java.sql.SQLException ex) {
                violation[0] = Boundaries.errInfo(ex);
            }
            if (violation[0] == null) throw new IllegalStateException("the duplicate insert did not raise");
            session.protocol.checkpoint("before-end", null, ident.pid());
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        if (violation[0] != null) steps.put("violation", violation[0]);
        outcome.put("steps", steps);
        return formed(outcome, form(session, FORM_TOP));
    }

    private Map<String, Object> connLost(Session session, Map<String, Object> markers, Map<String, Object> settings) {
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "tx"));
            Sql.Ident ident = session.sql.identify(false);
            session.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            sleep(settings);
        });
        return formed(outcome, form(session, FORM_TOP));
    }

    private Map<String, Object> savepoint(Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        AtomicReference<Map<String, Object>> nestedBox = new AtomicReference<>();
        Integer[] pid = new Integer[1];
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "outer"));
            Sql.Ident ident = session.sql.identify(false);
            pid[0] = ident.pid();
            session.protocol.checkpoint("outer-after-write", ident.xid(), ident.pid());
            nestedBox.set(session.boundaries.call(Boundaries.Kind.NESTED, () -> {
                session.sql.insertItem(Json.text(markers, "inner"));
                session.protocol.checkpoint("inner-after-write", null, pid[0]);
                if (kind.equals("conn-lost")) {
                    sleep(settings);
                } else if (kind.equals("not-sent")) {
                    session.fault.arm(FaultingDataSource.Fault.SAVEPOINT, "client-reject");
                } else {
                    session.fault.arm(FaultingDataSource.Fault.SAVEPOINT, "rewrite");
                }
                throw new AppException("application error: the nested scope fails");
            }));
        });
        session.protocol.checkpoint("after-outer", null, pid[0]);
        outcome.put("steps", nestedSteps(nestedBox.get(), kind.equals("conn-lost") ? null : session.fault.report()));
        return formed(outcome, form(session, FORM_NESTED));
    }

    private Map<String, Object> nested(Session session, Map<String, Object> markers, String kind) {
        AtomicReference<Map<String, Object>> nestedBox = new AtomicReference<>();
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "outer"));
            nestedBox.set(session.boundaries.call(Boundaries.Kind.NESTED, () -> {
                session.sql.insertItem(Json.text(markers, "inner"));
                Sql.Ident ident = session.sql.identify(false);
                session.protocol.checkpoint("inner-after-write", ident.xid(), ident.pid());
                if (kind.equals("nested-fails")) throw new AppException("application error: the nested scope fails");
            }));
            if (kind.equals("outer-fails")) throw new AppException("application error: the outer scope fails");
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nestedView(nestedBox.get()));
        outcome.put("steps", steps);
        return formed(outcome, form(session, FORM_NESTED));
    }

    private Map<String, Object> independent(Session session, Map<String, Object> markers) {
        AtomicReference<Map<String, Object>> nestedBox = new AtomicReference<>();
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
            session.sql.insertItem(Json.text(markers, "outer"));
            nestedBox.set(session.boundaries.call(Boundaries.Kind.REQUIRES_NEW, () -> {
                session.sql.insertItem(Json.text(markers, "inner"));
                Sql.Ident ident = session.sql.identify(false);
                session.protocol.checkpoint("inner-after-write", ident.xid(), ident.pid());
            }));
            throw new AppException("application error: the outer scope fails");
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nestedView(nestedBox.get()));
        outcome.put("steps", steps);
        return formed(outcome, form(session, FORM_NEW));
    }

    private Map<String, Object> managedIsolation(Session session, Map<String, Object> markers, Map<String, Object> settings) {
        requireSerializable(settings);
        boolean[] entered = {false};
        Map<String, Object> outcome = session.boundaries.call(Boundaries.Kind.SERIALIZABLE, () -> {
            entered[0] = true;
            isolationBody(session, markers, "after-read");
        });
        if (!entered[0]) outcome = withBaseline(session, outcome, false);
        return formed(outcome, form(session, FORM_MANAGED));
    }

    private Map<String, Object> explicitIsolation(Session session, Map<String, Object> markers, Map<String, Object> settings) {
        if (session.declarative) {
            throw new IllegalStateException("declarative mode has no explicit transaction handle");
        }
        requireSerializable(settings);
        Boundaries.Explicit first = session.boundaries.explicit(true, () -> isolationBody(session, markers, "after-read"));
        Map<String, Object> outcome = first.entered() ? first.outcome() : withBaseline(session, first.outcome(), true);
        return formed(outcome, form(session, FORM_EXPLICIT));
    }

    private void isolationBody(Session session, Map<String, Object> markers, String checkpoint) throws Throwable {
        String name = Json.text(markers, "tx");
        session.sql.insertItem(name);
        session.sql.readItem(name);
        Sql.Ident ident = session.sql.identify(true);
        session.protocol.checkpoint(checkpoint, ident.xid(), ident.pid(), ident.isolation());
    }

    private Map<String, Object> withBaseline(Session session, Map<String, Object> failed, boolean explicit) {
        Map<String, Object> steps = new LinkedHashMap<>();
        try {
            if (explicit) {
                Boundaries.Explicit baseline = session.boundaries.explicit(false, () -> {
                    Sql.Ident ident = session.sql.identify(false);
                    session.protocol.checkpoint("baseline", ident.xid(), ident.pid());
                });
                if (!"committed".equals(baseline.outcome().get("reported"))) {
                    steps.put("baseline", Map.of("error", baseline.outcome().get("api_error")));
                }
            } else {
                Map<String, Object> baseline = session.boundaries.call(Boundaries.Kind.PLAIN, () -> {
                    Sql.Ident ident = session.sql.identify(false);
                    session.protocol.checkpoint("baseline", ident.xid(), ident.pid());
                });
                if (!"committed".equals(baseline.get("reported"))) {
                    steps.put("baseline", Map.of("error", baseline.get("api_error")));
                }
            }
        } catch (Throwable ex) {
            Protocol.rethrowIfProtocol(ex);
            if (ex instanceof Boundaries.NotIntercepted notIntercepted) throw notIntercepted;
            steps.put("baseline", Map.of("error", Boundaries.errInfo(ex)));
        }
        if (!steps.isEmpty()) failed.put("steps", steps);
        return failed;
    }

    private Map<String, Object> reuse(Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        Map<String, Object>[] violation = new Map[1];
        Boundaries.Kind unitKind = session.declarative && kind.equals("statement-error")
                ? Boundaries.Kind.REQUIRED_ON_EXCEPTION
                : Boundaries.Kind.REQUIRED;
        Map<String, Object> unit1 = session.boundaries.call(unitKind, () -> {
            session.sql.insertItem(Json.text(markers, "doomed"));
            Sql.Ident ident = session.sql.identify(false);
            session.protocol.checkpoint("unit1-after-write", ident.xid(), ident.pid());
            if (kind.equals("conn-lost")) {
                sleep(settings);
            } else {
                session.fault.arm(FaultingDataSource.Fault.ROOT, "client-reject");
            }
            if (kind.equals("statement-error")) {
                try {
                    session.sql.insertTaken();
                } catch (java.sql.SQLException ex) {
                    violation[0] = Boundaries.errInfo(ex);
                    throw ex;
                }
            }
            throw new AppException("application error: unit 1 fails");
        });
        session.fault.disarm();
        boolean threadBound = TransactionSynchronizationManager.hasResource(session.exposed);
        Integer unit1Pid = session.fault.pid;
        session.protocol.checkpoint("after-unit1", null, unit1Pid);

        int bound = Json.integer(settings, "bound_ms", 5000);
        long started = System.nanoTime();
        AtomicReference<Integer> unit2Pid = new AtomicReference<>();
        ExecutorService executor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(task, "ppcs-unit2");
            thread.setDaemon(true);
            return thread;
        });
        Future<Map<String, Object>> future = executor.submit(() -> {
            try {
                return session.boundaries.call(Boundaries.Kind.REQUIRED, () -> {
                    if (session.protocol.haltCheckpoints) {
                        throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
                    }
                    session.sql.insertItem(Json.text(markers, "next"));
                    Sql.Ident ident = session.sql.identify(false);
                    unit2Pid.set(ident.pid());
                    session.protocol.checkpoint("unit2-after-write", ident.xid(), ident.pid());
                });
            } catch (Protocol.ProtocolException ex) {
                if (session.protocol.haltCheckpoints) return null;
                throw ex;
            }
        });
        Map<String, Object> unit2Result = null;
        boolean pending = false;
        try {
            unit2Result = future.get(bound, TimeUnit.MILLISECONDS);
        } catch (TimeoutException ex) {
            synchronized (session.protocol.lock) {
                session.protocol.haltCheckpoints = true;
            }
            if (future.isDone()) {
                try {
                    unit2Result = future.get();
                } catch (ExecutionException done) {
                    rethrowSetup(done.getCause());
                    unit2Result = failedCall(done.getCause(), session);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("interrupted while reading unit 2");
                }
            } else {
                pending = true;
            }
        } catch (ExecutionException ex) {
            rethrowSetup(ex.getCause());
            unit2Result = failedCall(ex.getCause(), session);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted while waiting for unit 2");
        }
        executor.shutdown();
        int elapsed = (int) ((System.nanoTime() - started) / 1_000_000L);
        Map<String, Object> unit2 = new LinkedHashMap<>();
        if (pending || unit2Result == null) {
            unit2.put("outcome", "pending");
            unit2.put("elapsed_ms", elapsed);
            unit2.put("reported", "pending");
        } else {
            unit2.put("outcome", "completed");
            unit2.put("elapsed_ms", elapsed);
            unit2.putAll(unit2Result);
        }
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("unit1_pid", unit1Pid);
        reuse.put("unit2_pid", unit2Pid.get());
        reuse.put("same_backend", unit1Pid != null && unit1Pid.equals(unit2Pid.get()));
        reuse.put("thread_bound_after_unit1", threadBound);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("unit2", unit2);
        steps.put("reuse", reuse);
        if (violation[0] != null) steps.put("violation", violation[0]);
        if (!kind.equals("conn-lost")) steps.put("fault", session.fault.report());
        if (kind.equals("statement-error")) {
            steps.put("rollback_rule", session.declarative
                    ? "rollbackFor Exception.class on the @Transactional method"
                    : "SQLException left the callback as SqlUnchecked so TransactionTemplate rolled back on RuntimeException");
        }
        unit1.put("steps", steps);
        return formed(unit1, form(session, FORM_TOP));
    }

    private static Map<String, Object> failedCall(Throwable escaped, Session session) {
        Map<String, Object> outcome = new LinkedHashMap<>();
        outcome.put("contract", session.boundaries.contract());
        outcome.put("reported", "failed");
        outcome.put("basis", "the unit threw before its transaction boundary returned an outcome");
        outcome.put("api_error", Boundaries.errInfo(escaped));
        return outcome;
    }

    private static Map<String, Object> nestedSteps(Map<String, Object> nestedOutcome, Map<String, Object> fault) {
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nestedView(nestedOutcome));
        if (fault != null) steps.put("fault", fault);
        return steps;
    }

    private static Map<String, Object> nestedView(Map<String, Object> nestedOutcome) {
        Map<String, Object> nested = new LinkedHashMap<>();
        boolean completed = nestedOutcome != null && "committed".equals(nestedOutcome.get("reported"));
        nested.put("completed", completed);
        nested.put("caught", nestedOutcome != null && !completed);
        if (nestedOutcome != null) {
            nested.put("reported", nestedOutcome.get("reported"));
            if (nestedOutcome.get("api_error") != null) nested.put("error", nestedOutcome.get("api_error"));
        }
        return nested;
    }

    private static String form(Session session, String body) {
        String invocation = session.declarative
                ? "Declarative: the call goes through a JDK proxy and TransactionInterceptor. "
                : "Programmatic: TransactionTemplate on DataSourceTransactionManager. ";
        return invocation + body;
    }

    private static Map<String, Object> formed(Map<String, Object> outcome, String form) {
        outcome.put("form", form);
        return outcome;
    }

    private static void requireSerializable(Map<String, Object> settings) {
        String level = Json.text(settings, "isolation_level");
        if (!"serializable".equals(level)) {
            throw new IllegalStateException("this adapter runs the requested level serializable, got \"" + level + "\"");
        }
    }

    private static Map<String, Object> messageSettings(Map<String, Object> message) {
        Object settings = Json.object(message.get("case")).get("settings");
        if (settings == null) return Map.of();
        return Json.object(settings);
    }

    private static void sleep(Map<String, Object> settings) {
        int millis = Json.integer(settings, "settle_ms", 100);
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted during settle_ms");
        }
    }

    private static void rethrowSetup(Throwable error) {
        Protocol.rethrowIfProtocol(error);
        Throwable current = error;
        while (current != null) {
            if (current instanceof Boundaries.NotIntercepted notIntercepted) throw notIntercepted;
            current = current.getCause();
        }
    }

    private static String synchronizationName(int value) {
        if (value == AbstractPlatformTransactionManager.SYNCHRONIZATION_ALWAYS) return "SYNCHRONIZATION_ALWAYS";
        if (value == AbstractPlatformTransactionManager.SYNCHRONIZATION_ON_ACTUAL_TRANSACTION) return "SYNCHRONIZATION_ON_ACTUAL_TRANSACTION";
        if (value == AbstractPlatformTransactionManager.SYNCHRONIZATION_NEVER) return "SYNCHRONIZATION_NEVER";
        return Integer.toString(value);
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
                }
            }
        } catch (Exception ignored) {
            // The pin in pom.xml is the fallback the caller sees as a startup failure.
        }
        throw new IllegalStateException(type.getName() + " has no Implementation-Version or Bundle-Version");
    }

    static final class AppException extends RuntimeException {
        AppException(String message) {
            super(message);
        }
    }

    static final class Session {
        final Protocol protocol;
        final FaultingDataSource.Fault fault;
        final DataSource exposed;
        final Sql sql;
        final Boundaries boundaries;
        final AutoCloseable closer;
        final String mode;
        final boolean declarative;
        final Map<String, Object> configuration;

        Session(Protocol protocol, FaultingDataSource.Fault fault, DataSource exposed, Sql sql, Boundaries boundaries,
                AutoCloseable closer, String mode, boolean declarative, Map<String, Object> configuration) {
            this.protocol = protocol;
            this.fault = fault;
            this.exposed = exposed;
            this.sql = sql;
            this.boundaries = boundaries;
            this.closer = closer;
            this.mode = mode;
            this.declarative = declarative;
            this.configuration = configuration;
        }

        Map<String, Object> diagnostics() {
            Map<String, Object> diagnostics = new LinkedHashMap<>();
            diagnostics.put("trace", List.copyOf(sql.trace));
            diagnostics.put("fault_trace", List.copyOf(fault.trace));
            diagnostics.put("withheld", List.copyOf(fault.withheld));
            diagnostics.put("rewritten", List.copyOf(fault.rewritten));
            diagnostics.put("reply_codes", List.copyOf(fault.replyCodes));
            diagnostics.put("injection", fault.fired == 0 ? null : "client-side");
            diagnostics.put("interceptor_invocations", boundaries.invocations());
            Map<String, Object> cleanup = new LinkedHashMap<>();
            cleanup.put("thread_bound", TransactionSynchronizationManager.hasResource(exposed));
            cleanup.put("synchronization_active", TransactionSynchronizationManager.isSynchronizationActive());
            cleanup.put("actual_transaction_active", TransactionSynchronizationManager.isActualTransactionActive());
            diagnostics.put("cleanup", cleanup);
            return diagnostics;
        }

        void close() {
            try {
                closer.close();
            } catch (Exception ex) {
                System.err.println("closing the DataSource failed: " + ex.getMessage());
            }
        }
    }
}
