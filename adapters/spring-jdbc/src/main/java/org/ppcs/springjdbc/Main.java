package org.ppcs.springjdbc;

import java.io.File;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.jar.JarFile;
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

import javax.sql.DataSource;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.DefaultTransactionDefinition;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * PPCS adapter for Spring's {@link TransactionTemplate} on a {@link DataSourceTransactionManager}.
 * Writes go through {@link JdbcTemplate}. The runner creates {@code item} and {@code uniq}.
 */
public final class Main {
    /**
     * Spring Framework 7.0.9. No custom rollback rule is installed.
     *
     * <p>{@code TransactionTemplate.execute} (spring-tx 7.0.9) calls
     * {@code PlatformTransactionManager.commit} only when {@code doInTransaction} returns,
     * and on {@code RuntimeException} or {@code Error} it calls {@code rollbackOnException}
     * and rethrows that same throwable.
     *
     * <p>Reference, "Rolling Back a Declarative Transaction": "In its default configuration,
     * the Spring Framework's transaction infrastructure code marks a transaction for rollback
     * only in the case of runtime, unchecked exceptions. That is, when the thrown exception
     * is an instance or subclass of RuntimeException. (Error instances also, by default,
     * result in a rollback)." The default {@code <tx:advice/>} settings say: "Any
     * RuntimeException triggers rollback, and any checked Exception does not."
     *
     * <p>Reference, "Understanding PROPAGATION_NESTED": "PROPAGATION_NESTED uses a single
     * physical transaction with multiple savepoints that it can roll back to. Such partial
     * rollbacks let an inner transaction scope trigger a rollback for its scope, with the
     * outer transaction being able to continue the physical transaction despite some
     * operations having been rolled back. This setting is typically mapped onto JDBC
     * savepoints, so it works only with JDBC resource transactions."
     * {@code DataSourceTransactionManager}'s class javadoc: "This transaction manager
     * supports nested transactions via the JDBC Savepoint mechanism."
     */
    static final String CONTRACT = "Spring Framework 7.0.9 TransactionTemplate.execute (org.springframework.transaction.support.TransactionTemplate) "
            + "calls PlatformTransactionManager.commit only when the callback returns, and on a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. "
            + "The 7.0.9 reference, Rolling Back a Declarative Transaction, states the default rule: \"In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback).\" "
            + "The default tx:advice settings say: \"Any RuntimeException triggers rollback, and any checked Exception does not.\" "
            + "No custom rollback rule is installed. "
            + "The nested TransactionTemplate uses PROPAGATION_NESTED. The 7.0.9 reference, Understanding PROPAGATION_NESTED, states: \"PROPAGATION_NESTED uses a single physical transaction with multiple savepoints that it can roll back to. Such partial rollbacks let an inner transaction scope trigger a rollback for its scope, with the outer transaction being able to continue the physical transaction despite some operations having been rolled back. This setting is typically mapped onto JDBC savepoints, so it works only with JDBC resource transactions.\" "
            + "DataSourceTransactionManager's class javadoc states: \"This transaction manager supports nested transactions via the JDBC Savepoint mechanism.\"";

    private static final String FORM_TOP = "TransactionTemplate with the default PROPAGATION_REQUIRED on DataSourceTransactionManager. Writes go through JdbcTemplate.";
    private static final String FORM_NESTED = "Outer TransactionTemplate with the default PROPAGATION_REQUIRED, and a second TransactionTemplate with PROPAGATION_NESTED. Writes go through JdbcTemplate.";

    public static void main(String[] args) {
        if (Runtime.version().feature() < 21) {
            System.err.println("spring-jdbc adapter requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        new Main().run();
    }

    private void run() {
        Protocol protocol = new Protocol();
        Session session = null;
        boolean helloSent = false;
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("type", "result");
        try {
            Map<String, Object> message = protocol.read();
            if (!"case".equals(message.get("type"))) {
                throw new Protocol.ProtocolException("expected a case message");
            }
            session = open(protocol, message);
            protocol.send(hello(session, Json.text(message, "mode")));
            helloSent = true;
            Map<String, Object> outcome = dispatch(session, message);
            // after-end as soon as the case's TransactionTemplate calls have returned, before the DataSource is closed.
            protocol.checkpoint("after-end", null, null);
            result.put("status", "completed");
            result.putAll(outcome);
            result.put("diagnostics", session.diagnostics());
        } catch (NotImplemented ex) {
            if (!helloSent) protocol.send(fallbackHello(null));
            result.put("status", "not_implemented");
            result.put("reason", ex.getMessage());
            if (session != null) result.put("diagnostics", session.diagnostics());
        } catch (Throwable ex) {
            if (!helloSent) {
                protocol.send(fallbackHello(messageMode(ex)));
            }
            result.put("status", "error");
            Map<String, Object> error = errInfo(ex);
            error.put("protocol", isProtocol(ex));
            result.put("error", error);
            if (session != null) result.put("diagnostics", session.diagnostics());
        } finally {
            if (session != null) session.close();
        }
        protocol.send(result);
    }

    private static String messageMode(Throwable ignored) {
        return null;
    }

    private Session open(Protocol protocol, Map<String, Object> message) {
        String mode = Json.text(message, "mode");
        if (!mode.equals("native") && !mode.equals("pooled")) {
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
        configuration.put("outer", "PROPAGATION_REQUIRED");
        configuration.put("nested", "PROPAGATION_NESTED");
        configuration.put("rollbackRule", "default");
        if (mode.equals("native")) {
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
            // The only pool setting this mode changes. Defaults govern validation, lifetime, and eviction.
            hikari.setMaximumPoolSize(1);
            HikariDataSource pooled = new HikariDataSource(hikari);
            raw = pooled;
            closer = pooled;
            configuration.put("dataSource", "com.zaxxer.hikari.HikariDataSource");
            configuration.put("pool", "HikariCP");
            configuration.put("maximumPoolSize", 1);
        }
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        DataSource exposed = new FaultingDataSource(raw, fault, protocol);
        DataSourceTransactionManager manager = new DataSourceTransactionManager(exposed);
        TransactionTemplate outer = new TransactionTemplate(manager);
        TransactionTemplate nested = new TransactionTemplate(manager);
        nested.setPropagationBehavior(TransactionDefinition.PROPAGATION_NESTED);
        return new Session(protocol, fault, exposed, new JdbcTemplate(exposed), outer, nested, closer, mode, configuration);
    }

    private Map<String, Object> hello(Session session, String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "spring-jdbc", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "spring-framework", "version", versionOf(TransactionTemplate.class)));
        hello.put("driver", Map.of("name", "postgresql", "version", versionOf(org.postgresql.Driver.class)));
        Map<String, Object> components = new LinkedHashMap<>();
        components.put("spring-tx", versionOf(TransactionTemplate.class));
        components.put("spring-jdbc", versionOf(JdbcTemplate.class));
        components.put("postgresql", versionOf(org.postgresql.Driver.class));
        if ("pooled".equals(mode)) components.put("HikariCP", versionOf(HikariDataSource.class));
        hello.put("components", components);
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode);
        hello.put("configuration", session.configuration);
        return hello;
    }

    private Map<String, Object> fallbackHello(String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "spring-jdbc", "version", "0.1.0"));
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
            case "CTL-01.commit", "TX-01B.commit-reply-unseen" -> commit(session, markers);
            case "CTL-01.rollback" -> rollback(session, markers);
            case "TX-01A.caught-error-then-commit" -> caughtError(session, markers);
            case "PR-01.managed-catch-commit" -> pr(session, markers, "managed");
            case "PR-01.explicit-catch-commit" -> pr(session, markers, "explicit");
            case "PR-01.uncaught-control" -> pr(session, markers, "control");
            case "PR-01.savepoint-recovery" -> pr(session, markers, "savepoint");
            case "TX-01B.conn-lost-before-commit" -> connLostBeforeCommit(session, markers, settings);
            case "TX-02.savepoint-rollback-not-sent" -> savepoint(session, markers, settings, "not-sent");
            case "TX-02.savepoint-rollback-rejected" -> savepoint(session, markers, settings, "rejected");
            case "TX-02.conn-lost-before-savepoint-rollback" -> savepoint(session, markers, settings, "conn-lost");
            case "TX-03.rollback-not-sent" -> reuse(session, markers, settings, "rollback-not-sent");
            case "TX-03.statement-error-rollback-not-sent" -> reuse(session, markers, settings, "statement-error");
            case "TX-03.conn-lost-in-transaction" -> reuse(session, markers, settings, "conn-lost");
            default -> throw new IllegalStateException("this adapter does not implement " + id);
        };
    }

    private Map<String, Object> commit(Session session, Map<String, Object> markers) {
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            session.protocol.checkpoint("before-end", ident.xid, ident.pid);
        });
        outcome.put("form", FORM_TOP);
        return outcome;
    }

    private Map<String, Object> rollback(Session session, Map<String, Object> markers) {
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            session.protocol.checkpoint("before-end", ident.xid, ident.pid);
            throw new AppException("application error: the request fails");
        });
        outcome.put("form", FORM_TOP);
        return outcome;
    }

    private Map<String, Object> caughtError(Session session, Map<String, Object> markers) {
        DataAccessException[] violation = new DataAccessException[1];
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            session.protocol.checkpoint("after-write", ident.xid, ident.pid);
            try {
                session.jdbc.update("insert into uniq (code) values (?)", "taken");
            } catch (DataAccessException ex) {
                violation[0] = ex;
            }
            // The transaction is aborted. This checkpoint sends no query.
            session.protocol.checkpoint("before-end", null, ident.pid);
            if (violation[0] == null) {
                throw new IllegalStateException("the duplicate insert did not raise");
            }
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        if (violation[0] != null) steps.put("violation", errInfo(violation[0]));
        outcome.put("steps", steps);
        outcome.put("form", FORM_TOP);
        return outcome;
    }

    private Map<String, Object> connLostBeforeCommit(Session session, Map<String, Object> markers, Map<String, Object> settings) {
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            session.protocol.checkpoint("before-end", ident.xid, ident.pid);
            sleep(settings);
        });
        outcome.put("form", FORM_TOP);
        return outcome;
    }

    private Map<String, Object> savepoint(Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        AtomicReference<Map<String, Object>> nestedBox = new AtomicReference<>();
        Integer[] pid = new Integer[1];
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(Json.text(markers, "outer"));
            Ident ident = session.identify();
            pid[0] = ident.pid;
            session.protocol.checkpoint("outer-after-write", ident.xid, ident.pid);
            nestedBox.set(runTemplate(session, session.nested, () -> {
                session.write(Json.text(markers, "inner"));
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
            // The outer callback handles the nested result by continuing, then returns normally.
        });
        session.protocol.checkpoint("after-outer", null, pid[0]);
        Map<String, Object> nested = new LinkedHashMap<>();
        Map<String, Object> nestedOutcome = nestedBox.get();
        boolean caught = nestedOutcome != null && !"committed".equals(nestedOutcome.get("reported"));
        nested.put("caught", caught);
        if (nestedOutcome != null) {
            nested.put("reported", nestedOutcome.get("reported"));
            if (nestedOutcome.get("api_error") != null) nested.put("error", nestedOutcome.get("api_error"));
        }
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nested);
        if (!kind.equals("conn-lost")) steps.put("fault", session.fault.report());
        outcome.put("steps", steps);
        outcome.put("form", FORM_NESTED);
        return outcome;
    }

    private Map<String, Object> reuse(Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        TemplateResult unit1 = runTemplateResult(session, session.outer, () -> {
            session.write(Json.text(markers, "doomed"));
            Ident ident = session.identify();
            session.protocol.checkpoint("unit1-after-write", ident.xid, ident.pid);
            if (kind.equals("conn-lost")) {
                sleep(settings);
            } else {
                session.fault.arm(FaultingDataSource.Fault.ROOT, "client-reject");
            }
            if (kind.equals("statement-error")) {
                // Not caught. JdbcTemplate's DataAccessException leaves the callback.
                session.jdbc.update("insert into uniq (code) values (?)", "taken");
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
        Future<TemplateResult> future = executor.submit(() -> {
            try {
                return runTemplateResult(session, session.outer, () -> {
                    if (session.protocol.haltCheckpoints) {
                        throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
                    }
                    session.write(Json.text(markers, "next"));
                    Ident ident = session.identify();
                    unit2Pid.set(ident.pid);
                    session.protocol.checkpoint("unit2-after-write", ident.xid, ident.pid);
                });
            } catch (Protocol.ProtocolException ex) {
                if (session.protocol.haltCheckpoints) return null;
                throw ex;
            }
        });
        TemplateResult unit2Result = null;
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
                    rethrowIfProtocol(done.getCause());
                    unit2Result = failedTemplate(done.getCause());
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("interrupted while reading unit 2");
                }
            } else {
                pending = true;
            }
        } catch (ExecutionException ex) {
            rethrowIfProtocol(ex.getCause());
            unit2Result = failedTemplate(ex.getCause());
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
            unit2.putAll(unit2Result.outcome);
        }
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("unit1_pid", unit1Pid);
        reuse.put("unit2_pid", unit2Pid.get());
        reuse.put("same_backend", unit1Pid != null && unit1Pid.equals(unit2Pid.get()));
        reuse.put("thread_bound_after_unit1", threadBound);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("unit2", unit2);
        steps.put("reuse", reuse);
        if (kind.equals("statement-error") && unit1.thrownInside != null) {
            steps.put("violation", errInfo(unit1.thrownInside));
        }
        if (!kind.equals("conn-lost")) steps.put("fault", session.fault.report());
        Map<String, Object> outcome = new LinkedHashMap<>(unit1.outcome);
        outcome.put("steps", steps);
        outcome.put("form", FORM_TOP);
        return outcome;
    }

    /**
     * A normal return is committed. The exception thrown inside the callback, rethrown by the
     * template, is rolled back. Any other exception leaving {@code execute} is failed.
     */
    private Map<String, Object> runTemplate(Session session, TransactionTemplate template, Work work) {
        return runTemplateResult(session, template, work).outcome;
    }

    private TemplateResult runTemplateResult(Session session, TransactionTemplate template, Work work) {
        Throwable[] thrown = new Throwable[1];
        try {
            template.execute(status -> {
                try {
                    work.run();
                } catch (Throwable ex) {
                    thrown[0] = ex;
                    if (ex instanceof RuntimeException runtime) throw runtime;
                    if (ex instanceof Error error) throw error;
                    throw new IllegalStateException(ex);
                }
                return null;
            });
        } catch (Throwable escaped) {
            rethrowIfProtocol(escaped);
            rethrowIfProtocol(thrown[0]);
            return new TemplateResult(mapOutcome(escaped, thrown[0]), thrown[0]);
        }
        rethrowIfProtocol(thrown[0]);
        return new TemplateResult(mapOutcome(null, thrown[0]), thrown[0]);
    }

    private static TemplateResult failedTemplate(Throwable escaped) {
        return new TemplateResult(mapOutcome(escaped, null), null);
    }

    private static Map<String, Object> mapOutcome(Throwable escaped, Throwable thrownInside) {
        Map<String, Object> outcome = new LinkedHashMap<>();
        outcome.put("contract", CONTRACT);
        if (escaped == null) {
            outcome.put("reported", "committed");
            outcome.put("basis", "TransactionTemplate.execute returned normally, so the template committed");
            return outcome;
        }
        if (thrownInside != null && escaped == thrownInside) {
            outcome.put("reported", "rolled_back");
            outcome.put("basis", "TransactionTemplate.execute threw the exception raised inside the callback, so the template rolled back");
            outcome.put("api_error", errInfo(thrownInside));
            return outcome;
        }
        outcome.put("reported", "failed");
        outcome.put("basis", "TransactionTemplate.execute threw an exception the callback did not throw");
        outcome.put("api_error", errInfo(escaped));
        return outcome;
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

    private static boolean isProtocol(Throwable error) {
        Throwable current = error;
        while (current != null) {
            if (current instanceof Protocol.ProtocolException) return true;
            current = current.getCause();
        }
        return false;
    }

    private static void rethrowIfProtocol(Throwable error) {
        if (!isProtocol(error)) return;
        Throwable current = error;
        while (current != null) {
            if (current instanceof Protocol.ProtocolException protocol) throw protocol;
            current = current.getCause();
        }
    }

    static Map<String, Object> errInfo(Throwable error) {
        String message = error.getMessage() == null ? "" : error.getMessage();
        Throwable cause = error.getCause();
        if (cause != null && cause.getMessage() != null && !message.contains(cause.getMessage())) {
            message = message.isEmpty() ? cause.getMessage() : message + ": " + cause.getMessage();
        }
        message = message.replaceAll("\\s+", " ").trim();
        if (message.length() > 500) message = message.substring(0, 500);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", error.getClass().getSimpleName());
        info.put("code", FaultingDataSource.Fault.sqlState(error));
        info.put("message", message);
        return info;
    }

    /** Implementation-Version, or OSGi Bundle-Version for jars that only publish that. */
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
            // The pin in pom.xml is the fallback message below.
        }
        throw new IllegalStateException(type.getName() + " has no Implementation-Version or Bundle-Version");
    }

    @FunctionalInterface
    interface Work {
        void run() throws Throwable;
    }

    record Ident(String xid, int pid) {}

    record TemplateResult(Map<String, Object> outcome, Throwable thrownInside) {}

    static final class NotImplemented extends RuntimeException {
        NotImplemented(String message) { super(message); }
    }

    private Map<String, Object> pr(Session session, Map<String, Object> markers, String kind) {
        Map<String, Object>[] violation = new Map[1];
        Integer[] pid = new Integer[1];
        int[] afterCommit = {0};
        int[] completion = {-1};
        Map<String, Object>[] nested = new Map[1];
        Work work = () -> {
            registerHooks(afterCommit, completion);
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            pid[0] = ident.pid;
            session.protocol.checkpoint("after-write", ident.xid, ident.pid);
            if (kind.equals("savepoint")) {
                nested[0] = runTemplate(session, session.nested, () -> {
                    session.jdbc.update("insert into uniq (code) values (?)", "taken");
                });
                violation[0] = nested[0].get("api_error") instanceof Map<?, ?> error ? castError(error) : null;
                session.protocol.checkpoint("before-end", null, ident.pid);
                return;
            }
            try {
                session.jdbc.update("insert into uniq (code) values (?)", "taken");
            } catch (DataAccessException ex) {
                violation[0] = errInfo(ex);
                if (kind.equals("control")) throw ex;
                session.protocol.checkpoint("before-end", null, ident.pid);
                return;
            }
            throw new IllegalStateException("the duplicate insert did not raise");
        };
        Map<String, Object> outcome = kind.equals("explicit")
                ? explicitCaught(session, markers, afterCommit, completion, violation, pid)
                : runTemplate(session, session.outer, work);
        if (!kind.equals("explicit")) session.protocol.checkpoint("after-api", null, pid[0]);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("variant", kind);
        if (violation[0] != null) steps.put("violation", violation[0]);
        if (nested[0] != null) {
            Map<String, Object> savepoint = new LinkedHashMap<>();
            savepoint.put("recovered", "rolled_back".equals(nested[0].get("reported")) || "failed".equals(nested[0].get("reported")));
            savepoint.put("nested", nested[0]);
            steps.put("savepoint", savepoint);
        }
        steps.put("hooks", hookReport(afterCommit[0], completion[0]));
        steps.put("probe", probe(session));
        steps.put("reuse", reuseUnit(session, Json.text(markers, "reuse"), pid[0]));
        steps.put("command_tag", null);
        outcome.put("steps", steps);
        outcome.put("form", switch (kind) {
            case "explicit" -> "PlatformTransactionManager.getTransaction, catch DataAccessException, manager.commit. Writes use JdbcTemplate.";
            case "control" -> "TransactionTemplate.execute. DataAccessException leaves the callback.";
            case "savepoint" -> "TransactionTemplate.execute with a PROPAGATION_NESTED template around the duplicate. The nested error is contained and the outer callback returns.";
            default -> "TransactionTemplate.execute. The callback catches DataAccessException and returns. Writes use JdbcTemplate.";
        });
        return outcome;
    }

    private Map<String, Object> explicitCaught(Session session, Map<String, Object> markers, int[] afterCommit, int[] completion, Map<String, Object>[] violation, Integer[] pid) {
        PlatformTransactionManager manager = session.outer.getTransactionManager();
        if (manager == null) throw new IllegalStateException("TransactionTemplate has no transaction manager");
        TransactionStatus status = manager.getTransaction(new DefaultTransactionDefinition());
        try {
            registerHooks(afterCommit, completion);
            session.write(Json.text(markers, "tx"));
            Ident ident = session.identify();
            pid[0] = ident.pid;
            session.protocol.checkpoint("after-write", ident.xid, ident.pid);
            try {
                session.jdbc.update("insert into uniq (code) values (?)", "taken");
            } catch (DataAccessException ex) {
                violation[0] = errInfo(ex);
            }
            if (violation[0] == null) throw new IllegalStateException("the duplicate insert did not raise");
            session.protocol.checkpoint("before-end", null, ident.pid);
            manager.commit(status);
            session.protocol.checkpoint("after-api", null, pid[0]);
            Map<String, Object> outcome = new LinkedHashMap<>();
            outcome.put("reported", "committed");
            outcome.put("basis", "PlatformTransactionManager.commit returned");
            outcome.put("contract", CONTRACT + " Explicit form: getTransaction returns a TransactionStatus and the application calls commit.");
            return outcome;
        } catch (RuntimeException ex) {
            rethrowIfProtocol(ex);
            if (!status.isCompleted()) {
                try { manager.rollback(status); } catch (RuntimeException ignored) { }
            }
            session.protocol.checkpoint("after-api", null, pid[0]);
            Map<String, Object> outcome = new LinkedHashMap<>();
            outcome.put("reported", "failed");
            outcome.put("basis", "PlatformTransactionManager.commit raised, or the explicit transaction failed before it");
            outcome.put("contract", CONTRACT);
            outcome.put("api_error", errInfo(ex));
            return outcome;
        }
    }

    private static void registerHooks(int[] afterCommit, int[] completion) {
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override public void afterCommit() { afterCommit[0]++; }
            @Override public void afterCompletion(int status) { completion[0] = status; }
        });
    }

    private Map<String, Object> probe(Session session) {
        Map<String, Object> probe = new LinkedHashMap<>();
        probe.put("supported", true);
        try {
            session.jdbc.queryForObject("select 1", Integer.class);
            probe.put("ok", true);
            probe.put("error", null);
        } catch (RuntimeException ex) {
            rethrowIfProtocol(ex);
            probe.put("ok", false);
            probe.put("error", errInfo(ex));
        }
        return probe;
    }

    private Map<String, Object> reuseUnit(Session session, String name, Integer firstPid) {
        long started = System.nanoTime();
        Integer[] pid = new Integer[1];
        Map<String, Object> outcome = runTemplate(session, session.outer, () -> {
            session.write(name);
            Ident ident = session.identify();
            pid[0] = ident.pid;
            session.protocol.checkpoint("reuse-after-write", ident.xid, ident.pid);
        });
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("attempted", true);
        reuse.put("elapsed_ms", (System.nanoTime() - started) / 1_000_000L);
        reuse.put("reported", outcome.get("reported"));
        reuse.put("error", outcome.get("api_error"));
        reuse.put("pid", pid[0]);
        reuse.put("same_backend", firstPid != null && firstPid.equals(pid[0]));
        return reuse;
    }

    private static Map<String, Object> hookReport(int afterCommit, int completion) {
        String status = switch (completion) {
            case TransactionSynchronization.STATUS_COMMITTED -> "committed";
            case TransactionSynchronization.STATUS_ROLLED_BACK -> "rolled_back";
            case TransactionSynchronization.STATUS_UNKNOWN -> "unknown";
            default -> "not_invoked";
        };
        Map<String, Object> hooks = new LinkedHashMap<>();
        hooks.put("supported", true);
        hooks.put("after_commit", afterCommit);
        hooks.put("after_completion", status);
        return hooks;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castError(Map<?, ?> error) {
        return (Map<String, Object>) error;
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
        final JdbcTemplate jdbc;
        final TransactionTemplate outer;
        final TransactionTemplate nested;
        final AutoCloseable closer;
        final String mode;
        final Map<String, Object> configuration;

        Session(Protocol protocol, FaultingDataSource.Fault fault, DataSource exposed, JdbcTemplate jdbc,
                TransactionTemplate outer, TransactionTemplate nested, AutoCloseable closer, String mode,
                Map<String, Object> configuration) {
            this.protocol = protocol;
            this.fault = fault;
            this.exposed = exposed;
            this.jdbc = jdbc;
            this.outer = outer;
            this.nested = nested;
            this.closer = closer;
            this.mode = mode;
            this.configuration = configuration;
        }

        void write(String name) {
            jdbc.update("insert into item (name, qty) values (?, 0)", name);
        }

        Ident identify() {
            return jdbc.queryForObject("select pg_current_xact_id()::text, pg_backend_pid()", (rs, row) -> {
                Ident ident = new Ident(rs.getString(1), rs.getInt(2));
                fault.pid = ident.pid;
                return ident;
            });
        }

        Map<String, Object> diagnostics() {
            Map<String, Object> diagnostics = new LinkedHashMap<>();
            diagnostics.put("trace", List.copyOf(fault.trace));
            diagnostics.put("withheld", List.copyOf(fault.withheld));
            diagnostics.put("rewritten", List.copyOf(fault.rewritten));
            diagnostics.put("reply_codes", List.copyOf(fault.replyCodes));
            diagnostics.put("injection", fault.fired == 0 ? null : "client-side");
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
