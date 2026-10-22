package org.ppcs.hibernate;

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

import org.hibernate.Session;
import org.hibernate.SessionFactory;
import org.hibernate.Transaction;

/**
 * PPCS adapter for native Hibernate ORM.
 *
 * <p>The transaction shape is {@code Session.openSession}, {@code beginTransaction},
 * {@code commit}, and {@code session.close}. A case whose application error is the
 * rollback signal calls {@code Transaction.rollback} from that catch. TX-01A catches
 * the statement error and calls {@code commit}.
 */
public final class Main {
    private static final String FORM = "Explicit Session.openSession, Session.beginTransaction, Session.persist, Session.flush, and Transaction.commit. "
            + "Flush mode is the SessionFactory default. Schema generation is off. "
            + "CTL-01.rollback and TX-03 call Transaction.rollback when the work throws and the transaction is still active. "
            + "TX-01A catches the unique violation inside the transaction and then calls Transaction.commit. "
            + "TX-01B calls Transaction.commit after the runner has terminated the backend. "
            + "Identity is Session.doReturningWork on the transactional connection.";

    public static void main(String[] args) {
        if (Runtime.version().feature() < 21) {
            System.err.println("hibernate adapter requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        new Main().run();
    }

    private void run() {
        Protocol protocol = new Protocol();
        Holder holder = null;
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
            holder = open(protocol, message, mode);
            protocol.send(hello(holder, mode));
            helloSent = true;
            Map<String, Object> outcome = dispatch(holder, message);
            protocol.checkpoint("after-end", null, null);
            result.put("status", "completed");
            result.putAll(outcome);
            result.put("diagnostics", holder.diagnostics());
        } catch (Throwable ex) {
            if (!helloSent) protocol.send(fallbackHello(mode));
            result.put("status", "error");
            Map<String, Object> error = Errors.info(ex);
            error.put("protocol", Protocol.isProtocol(ex));
            result.put("error", error);
            if (holder != null) result.put("diagnostics", holder.diagnostics());
        } finally {
            if (holder != null) holder.close();
        }
        protocol.send(result);
    }

    private Holder open(Protocol protocol, Map<String, Object> message, String mode) {
        boolean pooled = switch (mode) {
            case "native" -> false;
            case "pooled" -> true;
            default -> throw new IllegalStateException("unknown mode \"" + mode + "\"");
        };
        Map<String, Object> connection = Json.object(message.get("connection"));
        String url = "jdbc:postgresql://" + Json.text(connection, "host") + ":" + Json.integer(connection, "port")
                + "/" + Json.text(connection, "database")
                + "?ApplicationName=" + URLEncoder.encode(Json.text(connection, "application_name"), StandardCharsets.UTF_8);
        String user = Json.text(connection, "user");
        String password = Json.text(connection, "password");
        DriverDataSource driver = new DriverDataSource(url, user, password);
        TracingDataSource traced = new TracingDataSource(driver);
        DataSource pooledSource = null;
        AutoCloseable closer;
        Map<String, Object> configuration = new LinkedHashMap<>();
        if (!pooled) {
            pooledSource = traced;
            closer = () -> { };
            configuration.put("dataSource", "org.ppcs.hibernate.DriverDataSource");
            configuration.put("pool", false);
        } else {
            HikariConfig hikari = new HikariConfig();
            hikari.setDataSource(traced);
            hikari.setMaximumPoolSize(1);
            HikariDataSource hikariDataSource = new HikariDataSource(hikari);
            pooledSource = hikariDataSource;
            closer = hikariDataSource;
            configuration.put("dataSource", "com.zaxxer.HikariDataSource");
            configuration.put("pool", "HikariCP");
            configuration.put("maximumPoolSize", 1);
            configuration.put("hikariUnderlying", "TracingDataSource over DriverDataSource");
        }
        FaultingDataSource.Fault fault = new FaultingDataSource.Fault();
        DataSource exposed = new FaultingDataSource(pooledSource, fault, pid -> protocol.checkpoint("after-fault", null, pid));
        SqlTrace sql = new SqlTrace();
        SessionFactory factory = Boot.open(exposed, sql, configuration);
        int bootstrapJdbc = traced.size();
        traced.clear();
        sql.clear();
        configuration.put("bootstrapJdbcEventsCleared", bootstrapJdbc);
        return new Holder(protocol, fault, traced, sql, factory, closer, mode, configuration);
    }

    private Map<String, Object> hello(Holder holder, String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "hibernate", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "hibernate-orm", "version", versionOf(Session.class)));
        hello.put("driver", Map.of("name", "postgresql", "version", versionOf(org.postgresql.Driver.class)));
        Map<String, Object> components = new LinkedHashMap<>();
        components.put("hibernate-core", versionOf(Session.class));
        components.put("jakarta.persistence-api", versionOf(jakarta.persistence.Entity.class));
        components.put("postgresql", versionOf(org.postgresql.Driver.class));
        if (holder.configuration.get("pool") instanceof String) components.put("HikariCP", versionOf(HikariDataSource.class));
        hello.put("components", components);
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode);
        hello.put("configuration", holder.configuration);
        return hello;
    }

    private Map<String, Object> fallbackHello(String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "hibernate", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "hibernate-orm", "version", "7.4.13.Final"));
        hello.put("driver", Map.of("name", "postgresql", "version", "42.7.14"));
        hello.put("components", Map.of());
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode == null ? "unknown" : mode);
        hello.put("configuration", Map.of());
        return hello;
    }

    private Map<String, Object> dispatch(Holder holder, Map<String, Object> message) {
        String id = Json.text(Json.object(message.get("case")), "id");
        Map<String, Object> markers = Json.object(message.get("markers"));
        Map<String, Object> settings = messageSettings(message);
        return switch (id) {
            case "CTL-01.commit", "TX-01B.commit-reply-unseen" -> top(holder, markers, false);
            case "CTL-01.rollback" -> top(holder, markers, true);
            case "TX-01A.caught-error-then-commit" -> caughtError(holder, markers);
            case "TX-01B.conn-lost-before-commit" -> connLost(holder, markers, settings);
            case "TX-03.rollback-not-sent" -> reuse(holder, markers, settings, "rollback-not-sent");
            case "TX-03.statement-error-rollback-not-sent" -> reuse(holder, markers, settings, "statement-error");
            case "TX-03.conn-lost-in-transaction" -> reuse(holder, markers, settings, "conn-lost");
            default -> throw new IllegalStateException("this adapter does not implement " + id);
        };
    }

    private Map<String, Object> top(Holder holder, Map<String, Object> markers, boolean rollback) {
        AtomicReference<Object> marker = new AtomicReference<>();
        Boundary.Outcome outcome = Boundary.run(holder.factory, holder.traced, rollback, marker, (session, tx) -> {
            marker.set(Observe.insertItem(session, Json.text(markers, "tx")));
            Observe.Ident ident = Observe.identify(session, holder.sql, holder.fault, false);
            holder.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            if (rollback) throw new Boundary.AppException("application error: the request fails");
        });
        return formed(outcome, Map.of());
    }

    private Map<String, Object> caughtError(Holder holder, Map<String, Object> markers) {
        AtomicReference<Object> marker = new AtomicReference<>();
        Map<String, Object> extra = new LinkedHashMap<>();
        Boundary.Outcome outcome = Boundary.run(holder.factory, holder.traced, false, marker, (session, tx) -> {
            Item item = Observe.insertItem(session, Json.text(markers, "tx"));
            marker.set(item);
            Observe.Ident ident = Observe.identify(session, holder.sql, holder.fault, false);
            holder.protocol.checkpoint("after-write", ident.xid(), ident.pid());
            Uniq uniq = new Uniq("taken");
            String phase = "persist";
            Map<String, Object> violation = null;
            try {
                session.persist(uniq);
                phase = "flush";
                session.flush();
                throw new IllegalStateException("the duplicate insert did not raise");
            } catch (RuntimeException ex) {
                if (ex instanceof IllegalStateException && "the duplicate insert did not raise".equals(ex.getMessage())) throw ex;
                violation = Errors.info(ex);
                violation.put("phase", phase);
                Map<String, Object> beforeCommit = Observe.context(session, tx, item);
                try {
                    beforeCommit.put("contains_uniq", session.contains(uniq));
                } catch (RuntimeException contains) {
                    beforeCommit.put("contains_uniq_error", contains.getClass().getSimpleName());
                }
                extra.put("before_commit", beforeCommit);
            }
            if (violation == null) throw new IllegalStateException("the duplicate insert did not raise");
            extra.put("violation", violation);
            holder.protocol.checkpoint("before-end", null, ident.pid());
        });
        return formed(outcome, extra);
    }

    private Map<String, Object> connLost(Holder holder, Map<String, Object> markers, Map<String, Object> settings) {
        AtomicReference<Object> marker = new AtomicReference<>();
        Boundary.Outcome outcome = Boundary.run(holder.factory, holder.traced, false, marker, (session, tx) -> {
            marker.set(Observe.insertItem(session, Json.text(markers, "tx")));
            Observe.Ident ident = Observe.identify(session, holder.sql, holder.fault, false);
            holder.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            sleep(settings);
        });
        return formed(outcome, Map.of());
    }

    private Map<String, Object> reuse(Holder holder, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        AtomicReference<Object> marker = new AtomicReference<>();
        Boundary.Outcome unit1 = Boundary.run(holder.factory, holder.traced, true, marker, (session, tx) -> {
            marker.set(Observe.insertItem(session, Json.text(markers, "doomed")));
            Observe.Ident ident = Observe.identify(session, holder.sql, holder.fault, false);
            holder.protocol.checkpoint("unit1-after-write", ident.xid(), ident.pid());
            if (kind.equals("conn-lost")) {
                sleep(settings);
            } else {
                holder.fault.arm(FaultingDataSource.Fault.ROOT, "client-reject");
            }
            if (kind.equals("statement-error")) Observe.insertTaken(session);
            throw new Boundary.AppException("application error: unit 1 fails");
        });
        holder.fault.disarm();
        Integer unit1Pid = holder.fault.pid;
        holder.protocol.checkpoint("after-unit1", null, unit1Pid);

        int bound = Json.integer(settings, "bound_ms", 5000);
        long started = System.nanoTime();
        AtomicReference<Integer> unit2Pid = new AtomicReference<>();
        ExecutorService executor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(task, "ppcs-unit2");
            thread.setDaemon(true);
            return thread;
        });
        Future<Boundary.Outcome> future = executor.submit(() -> {
            if (holder.protocol.haltCheckpoints) {
                throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
            }
            AtomicReference<Object> next = new AtomicReference<>();
            return Boundary.run(holder.factory, holder.traced, true, next, (session, tx) -> {
                if (holder.protocol.haltCheckpoints) {
                    throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
                }
                next.set(Observe.insertItem(session, Json.text(markers, "next")));
                Observe.Ident ident = Observe.identify(session, holder.sql, holder.fault, false);
                unit2Pid.set(ident.pid());
                holder.protocol.checkpoint("unit2-after-write", ident.xid(), ident.pid());
            });
        });
        Boundary.Outcome unit2Result = null;
        boolean pending = false;
        try {
            unit2Result = future.get(bound, TimeUnit.MILLISECONDS);
        } catch (TimeoutException ex) {
            synchronized (holder.protocol.lock) {
                holder.protocol.haltCheckpoints = true;
            }
            if (future.isDone()) {
                try {
                    unit2Result = future.get();
                } catch (ExecutionException done) {
                    Protocol.rethrowIfProtocol(done.getCause());
                    unit2Result = failed(done.getCause());
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("interrupted while reading unit 2");
                }
            } else {
                pending = true;
            }
        } catch (ExecutionException ex) {
            Protocol.rethrowIfProtocol(ex.getCause());
            unit2Result = failed(ex.getCause());
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
            unit2.putAll(unit2Result.toMap());
        }
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("unit1_pid", unit1Pid);
        reuse.put("unit2_pid", unit2Pid.get());
        reuse.put("same_backend", unit1Pid != null && unit1Pid.equals(unit2Pid.get()));
        reuse.put("session_closed_before_unit2", true);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("unit2", unit2);
        steps.put("reuse", reuse);
        if (unit1.trigger != null && "23505".equals(unit1.trigger.get("code"))) steps.put("violation", unit1.trigger);
        if (!kind.equals("conn-lost")) steps.put("fault", holder.fault.report());
        return formed(unit1, steps);
    }

    private static Boundary.Outcome failed(Throwable escaped) {
        Boundary.Outcome outcome = new Boundary.Outcome();
        outcome.reported = "failed";
        outcome.basis = "the unit threw before its transaction boundary returned an outcome";
        outcome.apiError = Errors.info(escaped);
        return outcome;
    }

    private static Map<String, Object> formed(Boundary.Outcome outcome, Map<String, Object> extra) {
        Map<String, Object> map = outcome.toMap();
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("rollback_on_exception", outcome.rollbackOnException);
        steps.put("completion_jdbc", outcome.completionJdbc);
        steps.put("persistence_context", outcome.beforeClose);
        steps.put("persistence_context_after_close", outcome.afterClose);
        if (outcome.trigger != null) steps.put("trigger", outcome.trigger);
        if (outcome.closeError != null) steps.put("close_error", outcome.closeError);
        steps.putAll(extra);
        map.put("steps", steps);
        map.put("form", FORM);
        return map;
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
            // The pin in pom.xml is the fallback the caller sees as a startup failure.
        }
        throw new IllegalStateException(type.getName() + " has no Implementation-Version or Bundle-Version");
    }

    static final class Holder {
        final Protocol protocol;
        final FaultingDataSource.Fault fault;
        final TracingDataSource traced;
        final SqlTrace sql;
        final SessionFactory factory;
        final AutoCloseable closer;
        final String mode;
        final Map<String, Object> configuration;

        Holder(Protocol protocol, FaultingDataSource.Fault fault, TracingDataSource traced, SqlTrace sql,
               SessionFactory factory, AutoCloseable closer, String mode, Map<String, Object> configuration) {
            this.protocol = protocol;
            this.fault = fault;
            this.traced = traced;
            this.sql = sql;
            this.factory = factory;
            this.closer = closer;
            this.mode = mode;
            this.configuration = configuration;
        }

        Map<String, Object> diagnostics() {
            Map<String, Object> diagnostics = new LinkedHashMap<>();
            diagnostics.put("sql", sql.snapshot());
            diagnostics.put("jdbc", traced.snapshot());
            diagnostics.put("fault_trace", List.copyOf(fault.trace));
            diagnostics.put("withheld", List.copyOf(fault.withheld));
            diagnostics.put("rewritten", List.copyOf(fault.rewritten));
            diagnostics.put("reply_codes", List.copyOf(fault.replyCodes));
            diagnostics.put("injection", fault.fired == 0 ? null : "client-side");
            return diagnostics;
        }

        void close() {
            try {
                factory.close();
            } catch (Exception ex) {
                System.err.println("closing the SessionFactory failed: " + ex.getMessage());
            }
            try {
                closer.close();
            } catch (Exception ex) {
                System.err.println("closing the DataSource failed: " + ex.getMessage());
            }
        }
    }
}
