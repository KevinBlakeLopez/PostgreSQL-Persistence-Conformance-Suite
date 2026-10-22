package org.ppcs.jdbccontrol;

import java.io.File;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Savepoint;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.jar.JarFile;

/**
 * PPCS adapter for a small application-owned JDBC transaction policy.
 * Writes use {@link java.sql.PreparedStatement} against the runner's {@code item} and {@code uniq} tables.
 * There is no pool, ORM, or transaction framework.
 */
public final class Main {
    private static final String FORM_TOP = "Connection.setAutoCommit(false), the work, then Connection.commit() or Connection.rollback(). Writes use PreparedStatement.";
    private static final String FORM_NESTED = "The outer transaction is Connection.setAutoCommit(false). The nested scope is Connection.setSavepoint, Connection.rollback(Savepoint), and Connection.releaseSavepoint.";
    private static final String FORM_REUSE = "One DriverManager connection is held and handed to the next unit. This is not a connection pool. correct closes it when Connection.rollback() throws. unsafe calls Connection.setAutoCommit(true) and keeps it.";
    private static final String FORM_MANAGED = "The policy runs the work and calls Connection.commit() when the work returns. JDBC has no managed-transaction type separate from Connection.";
    private static final String FORM_EXPLICIT = "The same Connection.setTransactionIsolation and Connection.commit calls as the managed case. JDBC's public API does not return a transaction handle distinct from the Connection.";

    public static void main(String[] args) {
        if (Runtime.version().feature() < 21) {
            System.err.println("jdbc-control adapter requires Java 21 or newer; this JVM is " + Runtime.version());
            System.exit(2);
        }
        new Main().run();
    }

    private void run() {
        Protocol protocol = new Protocol();
        Sessions sessions = null;
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
            sessions = open(protocol, message, mode);
            protocol.send(hello(mode, sessions));
            helloSent = true;
            Map<String, Object> outcome = dispatch(sessions, protocol, message, mode);
            protocol.checkpoint("after-end", null, null);
            result.put("status", "completed");
            result.putAll(outcome);
            result.put("diagnostics", sessions.diagnostics());
        } catch (Throwable ex) {
            if (!helloSent) protocol.send(fallbackHello(mode));
            result.put("status", "error");
            Map<String, Object> error = Policy.errInfo(ex);
            error.put("protocol", Protocol.isProtocol(ex));
            result.put("error", error);
            if (sessions != null) result.put("diagnostics", sessions.diagnostics());
        } finally {
            if (sessions != null) sessions.close();
        }
        protocol.send(result);
    }

    private Sessions open(Protocol protocol, Map<String, Object> message, String mode) {
        if (!mode.equals("correct") && !mode.equals("unsafe")) {
            throw new IllegalStateException("unknown mode \"" + mode + "\"");
        }
        Map<String, Object> connection = Json.object(message.get("connection"));
        String url = "jdbc:postgresql://" + Json.text(connection, "host") + ":" + Json.integer(connection, "port")
                + "/" + Json.text(connection, "database");
        return new Sessions(url, Json.text(connection, "user"), Json.text(connection, "password"),
                Json.text(connection, "application_name"), new Faults.Fault(), protocol);
    }

    private Map<String, Object> hello(String mode, Sessions sessions) {
        boolean correct = mode.equals("correct");
        String driver = versionOf(org.postgresql.Driver.class);
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "jdbc-control", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "jdbc-control", "version", "0.1.0"));
        hello.put("driver", Map.of("name", "postgresql", "version", driver));
        hello.put("components", Map.of("postgresql", driver));
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode);
        Map<String, Object> configuration = new LinkedHashMap<>();
        configuration.put("commit_outcome", correct
                ? "Connection.commit(); rolled_back when PgConnection.getTransactionState() was FAILED"
                : "committed whenever Connection.commit() returns");
        configuration.put("commit_error", correct ? "reported as failed; connection closed" : "reported as rolled_back");
        configuration.put("failed_savepoint_rollback", correct ? "outer Connection.rollback()" : "ignored; Connection.commit()");
        configuration.put("failed_rollback", correct ? "connection closed; setAutoCommit not called" : "setAutoCommit(true); connection kept");
        configuration.put("isolation_level", correct ? "Connection.setTransactionIsolation before setAutoCommit(false)" : "not called");
        configuration.put("write_before_savepoint", correct ? "sent before setSavepoint" : "sent inside the savepoint");
        configuration.put("connections", "DriverManager, one connection, no pool");
        hello.put("configuration", configuration);
        return hello;
    }

    private Map<String, Object> fallbackHello(String mode) {
        Map<String, Object> hello = new LinkedHashMap<>();
        hello.put("type", "hello");
        hello.put("adapter", Map.of("name", "jdbc-control", "version", "0.1.0"));
        hello.put("framework", Map.of("name", "jdbc-control", "version", "0.1.0"));
        hello.put("driver", Map.of("name", "postgresql", "version", "42.7.14"));
        hello.put("components", Map.of());
        hello.put("runtime", Map.of("name", "java", "version", Runtime.version().toString()));
        hello.put("mode", mode == null ? "unknown" : mode);
        hello.put("configuration", Map.of());
        return hello;
    }

    private Map<String, Object> dispatch(Sessions sessions, Protocol protocol, Map<String, Object> message, String mode) throws SQLException {
        String id = Json.text(Json.object(message.get("case")), "id");
        Map<String, Object> markers = Json.object(message.get("markers"));
        Map<String, Object> settings = messageSettings(message);
        boolean correct = mode.equals("correct");
        return switch (id) {
            case "CTL-01.commit", "TX-01B.commit-reply-unseen" -> commit(sessions, protocol, markers, correct);
            case "CTL-01.rollback" -> rollback(sessions, protocol, markers, correct);
            case "TX-01A.caught-error-then-commit" -> caughtError(sessions, protocol, markers, correct);
            case "TX-01B.conn-lost-before-commit" -> connLostBeforeCommit(sessions, protocol, markers, settings, correct);
            case "TX-02.savepoint-rollback-not-sent" -> savepoint(sessions, protocol, markers, settings, correct, "not-sent");
            case "TX-02.savepoint-rollback-rejected" -> savepoint(sessions, protocol, markers, settings, correct, "rejected");
            case "TX-02.conn-lost-before-savepoint-rollback" -> savepoint(sessions, protocol, markers, settings, correct, "conn-lost");
            case "TX-03.rollback-not-sent" -> reuse(sessions, protocol, markers, settings, correct, "rollback-not-sent");
            case "TX-03.statement-error-rollback-not-sent" -> reuse(sessions, protocol, markers, settings, correct, "statement-error");
            case "TX-03.conn-lost-in-transaction" -> reuse(sessions, protocol, markers, settings, correct, "conn-lost");
            case "TX-04.nested-failure-contained" -> nestedOnly(sessions, protocol, markers, correct, "nested-fails");
            case "TX-04.nested-released-outer-rollback" -> nestedOnly(sessions, protocol, markers, correct, "outer-fails");
            case "TX-05.managed-serializable" -> isolation(sessions, protocol, markers, settings, correct, FORM_MANAGED);
            case "TX-05.explicit-serializable" -> isolation(sessions, protocol, markers, settings, correct, FORM_EXPLICIT);
            default -> throw new IllegalStateException("this adapter does not implement " + id);
        };
    }

    private Map<String, Object> commit(Sessions sessions, Protocol protocol, Map<String, Object> markers, boolean correct) throws SQLException {
        Policy.Outcome outcome = run(sessions, protocol, correct, null, connection -> {
            sessions.insertItem(connection, Json.text(markers, "tx"));
            Sessions.Ident ident = sessions.identify(connection);
            protocol.checkpoint("before-end", ident.xid, ident.pid);
        });
        return result(correct, outcome, Map.of(), FORM_TOP);
    }

    private Map<String, Object> rollback(Sessions sessions, Protocol protocol, Map<String, Object> markers, boolean correct) throws SQLException {
        Policy.Outcome outcome = run(sessions, protocol, correct, null, connection -> {
            sessions.insertItem(connection, Json.text(markers, "tx"));
            Sessions.Ident ident = sessions.identify(connection);
            protocol.checkpoint("before-end", ident.xid, ident.pid);
            throw new AppException("application error: the request fails");
        });
        return result(correct, outcome, Map.of(), FORM_TOP);
    }

    private Map<String, Object> caughtError(Sessions sessions, Protocol protocol, Map<String, Object> markers, boolean correct) throws SQLException {
        Map<String, Object>[] violation = new Map[1];
        Policy.Outcome outcome = run(sessions, protocol, correct, null, connection -> {
            sessions.insertItem(connection, Json.text(markers, "tx"));
            Sessions.Ident ident = sessions.identify(connection);
            protocol.checkpoint("after-write", ident.xid, ident.pid);
            try {
                sessions.insertTaken(connection);
            } catch (SQLException ex) {
                violation[0] = Policy.errInfo(ex);
            }
            if (violation[0] == null) throw new IllegalStateException("the duplicate insert did not raise");
            protocol.checkpoint("before-end", null, ident.pid);
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        if (violation[0] != null) steps.put("violation", violation[0]);
        return result(correct, outcome, steps, FORM_TOP);
    }

    private Map<String, Object> connLostBeforeCommit(Sessions sessions, Protocol protocol, Map<String, Object> markers, Map<String, Object> settings, boolean correct) throws SQLException {
        Policy.Outcome outcome = run(sessions, protocol, correct, null, connection -> {
            sessions.insertItem(connection, Json.text(markers, "tx"));
            Sessions.Ident ident = sessions.identify(connection);
            protocol.checkpoint("before-end", ident.xid, ident.pid);
            sleep(settings);
        });
        return result(correct, outcome, Map.of(), FORM_TOP);
    }

    private Map<String, Object> savepoint(Sessions sessions, Protocol protocol, Map<String, Object> markers, Map<String, Object> settings, boolean correct, String kind) throws SQLException {
        Integer[] pid = new Integer[1];
        Map<String, Object> nested = new LinkedHashMap<>();
        nested.put("caught", false);
        Policy.Scope scope = new Policy.Scope();
        Policy.Outcome outcome = run(sessions, protocol, correct, scope, connection -> {
            sessions.insertItem(connection, Json.text(markers, "outer"));
            Sessions.Ident ident = sessions.identify(connection);
            pid[0] = ident.pid;
            protocol.checkpoint("outer-after-write", ident.xid, ident.pid);
            try {
                nestedScope(sessions, connection, scope, savepointConnection -> {
                    sessions.insertItem(savepointConnection, Json.text(markers, "inner"));
                    protocol.checkpoint("inner-after-write", null, pid[0]);
                    if (kind.equals("conn-lost")) sleep(settings);
                    else if (kind.equals("not-sent")) sessions.fault.arm(Faults.Fault.SAVEPOINT, "client-reject");
                    else sessions.fault.arm(Faults.Fault.SAVEPOINT, "rewrite");
                    throw new AppException("application error: the nested scope fails");
                });
            } catch (Throwable ex) {
                Protocol.rethrowIfProtocol(ex);
                nested.put("caught", true);
                nested.put("error", Policy.errInfo(ex));
            }
            if (scope.rollbackError != null) nested.put("rollback_error", scope.rollbackError);
        });
        protocol.checkpoint("after-outer", null, pid[0]);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nested);
        if (!kind.equals("conn-lost")) steps.put("fault", sessions.fault.report());
        return result(correct, outcome, steps, FORM_NESTED);
    }

    private Map<String, Object> reuse(Sessions sessions, Protocol protocol, Map<String, Object> markers, Map<String, Object> settings, boolean correct, String kind) throws SQLException {
        Map<String, Object>[] violation = new Map[1];
        Integer[] unit1Pid = new Integer[1];
        Policy.Outcome unit1 = run(sessions, protocol, correct, null, connection -> {
            sessions.insertItem(connection, Json.text(markers, "doomed"));
            Sessions.Ident ident = sessions.identify(connection);
            unit1Pid[0] = ident.pid;
            protocol.checkpoint("unit1-after-write", ident.xid, ident.pid);
            if (kind.equals("conn-lost")) sleep(settings);
            else sessions.fault.arm(Faults.Fault.ROOT, "client-reject");
            if (kind.equals("statement-error")) {
                try {
                    sessions.insertTaken(connection);
                } catch (SQLException ex) {
                    violation[0] = Policy.errInfo(ex);
                    throw ex;
                }
            }
            throw new AppException("application error: unit 1 fails");
        });
        sessions.fault.disarm();
        protocol.checkpoint("after-unit1", null, unit1Pid[0]);

        int bound = Json.integer(settings, "bound_ms", 5000);
        long started = System.nanoTime();
        Integer[] unit2Pid = new Integer[1];
        ExecutorService executor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(task, "ppcs-unit2");
            thread.setDaemon(true);
            return thread;
        });
        Future<Policy.Outcome> future = executor.submit(() -> {
            try {
                return run(sessions, protocol, correct, null, connection -> {
                    if (protocol.haltCheckpoints) {
                        throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
                    }
                    sessions.insertItem(connection, Json.text(markers, "next"));
                    Sessions.Ident ident = sessions.identify(connection);
                    unit2Pid[0] = ident.pid;
                    protocol.checkpoint("unit2-after-write", ident.xid, ident.pid);
                });
            } catch (Protocol.ProtocolException ex) {
                if (protocol.haltCheckpoints) return null;
                throw ex;
            }
        });
        Policy.Outcome unit2Result = null;
        boolean pending = false;
        try {
            unit2Result = future.get(bound, TimeUnit.MILLISECONDS);
        } catch (TimeoutException ex) {
            synchronized (protocol.lock) {
                protocol.haltCheckpoints = true;
            }
            if (future.isDone()) {
                try {
                    unit2Result = future.get();
                } catch (ExecutionException done) {
                    Protocol.rethrowIfProtocol(done.getCause());
                    unit2Result = failedStart(done.getCause());
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("interrupted while reading unit 2");
                }
            } else {
                pending = true;
            }
        } catch (ExecutionException ex) {
            Protocol.rethrowIfProtocol(ex.getCause());
            unit2Result = failedStart(ex.getCause());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted while waiting for unit 2");
        }
        executor.shutdown();
        sessions.last = unit1;
        int elapsed = (int) ((System.nanoTime() - started) / 1_000_000L);
        Map<String, Object> unit2 = new LinkedHashMap<>();
        if (pending || unit2Result == null) {
            unit2.put("outcome", "pending");
            unit2.put("elapsed_ms", elapsed);
            unit2.put("reported", "pending");
        } else {
            unit2.put("outcome", "completed");
            unit2.put("elapsed_ms", elapsed);
            unit2.putAll(outcomeFields(correct, unit2Result));
        }
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("unit1_pid", unit1Pid[0]);
        reuse.put("unit2_pid", unit2Pid[0]);
        reuse.put("same_backend", unit1Pid[0] != null && unit1Pid[0].equals(unit2Pid[0]));
        reuse.put("discarded", unit1.discarded);
        reuse.put("autocommit_restored", unit1.autocommitRestored);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("unit2", unit2);
        steps.put("reuse", reuse);
        if (violation[0] != null) steps.put("violation", violation[0]);
        if (unit1.bodyError != null) steps.put("body_error", unit1.bodyError);
        if (unit1.cleanupError != null) steps.put("cleanup_error", unit1.cleanupError);
        if (!kind.equals("conn-lost")) steps.put("fault", sessions.fault.report());
        return result(correct, unit1, steps, FORM_REUSE);
    }

    private Map<String, Object> nestedOnly(Sessions sessions, Protocol protocol, Map<String, Object> markers, boolean correct, String variant) throws SQLException {
        boolean[] caught = new boolean[1];
        boolean[] completed = new boolean[1];
        List<String> deferred = new ArrayList<>();
        Policy.Scope scope = new Policy.Scope();
        Policy.Outcome outcome = run(sessions, protocol, correct, scope, connection -> {
            if (correct) sessions.insertItem(connection, Json.text(markers, "outer"));
            else deferred.add(Json.text(markers, "outer"));
            try {
                nestedScope(sessions, connection, scope, nested -> {
                    for (String name : deferred) sessions.insertItem(connection, name);
                    deferred.clear();
                    sessions.insertItem(connection, Json.text(markers, "inner"));
                    Sessions.Ident ident = sessions.identify(connection);
                    protocol.checkpoint("inner-after-write", ident.xid, ident.pid);
                    if (variant.equals("nested-fails")) throw new AppException("application error: the nested scope fails");
                });
                completed[0] = true;
            } catch (Throwable ex) {
                Protocol.rethrowIfProtocol(ex);
                caught[0] = true;
            }
            if (variant.equals("outer-fails")) throw new AppException("application error: the outer scope fails");
        });
        Map<String, Object> nested = new LinkedHashMap<>();
        nested.put("caught", caught[0]);
        nested.put("completed", completed[0]);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", nested);
        return result(correct, outcome, steps, FORM_NESTED);
    }

    private Map<String, Object> isolation(Sessions sessions, Protocol protocol, Map<String, Object> markers, Map<String, Object> settings, boolean correct, String form) throws SQLException {
        String level = Json.text(settings, "isolation_level");
        int jdbcLevel = jdbcIsolation(level);
        Connection connection = sessions.acquire();
        try {
            Policy.Outcome outcome = run(sessions, protocol, correct, null, work -> {
                sessions.insertItem(work, Json.text(markers, "tx"));
                sessions.readItem(work, Json.text(markers, "tx"));
                Sessions.Ident ident = sessions.identify(work, true);
                protocol.checkpoint("after-read", ident.xid, ident.pid, ident.isolation);
            }, connection, correct ? Integer.valueOf(jdbcLevel) : null);
            Map<String, Object> steps = new LinkedHashMap<>();
            steps.put("isolation_request", correct ? "Connection.setTransactionIsolation" : "not called");
            steps.put("requested", level);
            return result(correct, outcome, steps, form);
        } catch (SQLException start) {
            Protocol.rethrowIfProtocol(start);
            sessions.discard();
            Map<String, Object> steps = new LinkedHashMap<>();
            steps.put("isolation_request", "Connection.setTransactionIsolation");
            steps.put("requested", level);
            try {
                Connection plain = sessions.acquire();
                Policy.Outcome baseline = run(sessions, protocol, true, null, work -> {
                    Sessions.Ident ident = sessions.identify(work);
                    protocol.checkpoint("baseline", ident.xid, ident.pid);
                }, plain, null);
                if (!"committed".equals(baseline.reported)) {
                    Map<String, Object> baselineError = new LinkedHashMap<>();
                    baselineError.put("error", baseline.apiError == null
                            ? Map.of("class", "Error", "code", null, "message", baseline.basis)
                            : baseline.apiError);
                    steps.put("baseline", baselineError);
                } else {
                    steps.put("baseline_reported", baseline.reported);
                }
            } catch (Throwable baselineError) {
                Protocol.rethrowIfProtocol(baselineError);
                steps.put("baseline", Map.of("error", Policy.errInfo(baselineError)));
            }
            Policy.Outcome failed = new Policy.Outcome("failed",
                    "Connection.setTransactionIsolation or setAutoCommit threw before the transaction body ran",
                    Policy.errInfo(start), null, true, false, null, null);
            sessions.last = failed;
            return result(correct, failed, steps, form);
        }
    }

    private Policy.Outcome run(Sessions sessions, Protocol protocol, boolean correct, Policy.Scope scope, Policy.Work work) throws SQLException {
        return run(sessions, protocol, correct, scope, work, sessions.acquire(), null);
    }

    private Policy.Outcome run(Sessions sessions, Protocol protocol, boolean correct, Policy.Scope scope, Policy.Work work, Connection connection, Integer isolation) throws SQLException {
        Policy.Outcome outcome = Policy.run(correct, sessions, connection, work, scope == null ? new Policy.Scope() : scope, isolation);
        sessions.last = outcome;
        return outcome;
    }

    private void nestedScope(Sessions sessions, Connection connection, Policy.Scope scope, Policy.Work work) throws Throwable {
        Savepoint savepoint = connection.setSavepoint("ppcs_nested");
        sessions.note("SAVEPOINT ppcs_nested");
        try {
            work.run(connection);
            connection.releaseSavepoint(savepoint);
            sessions.note("RELEASE SAVEPOINT ppcs_nested");
        } catch (Throwable error) {
            Protocol.rethrowIfProtocol(error);
            try {
                connection.rollback(savepoint);
            } catch (SQLException rollbackError) {
                Protocol.rethrowIfProtocol(rollbackError);
                scope.rollbackOnly = true;
                scope.rollbackError = Policy.errInfo(rollbackError);
            }
            throw error;
        }
    }

    private static Policy.Outcome failedStart(Throwable error) {
        return new Policy.Outcome("failed", "the unit could not start a transaction", Policy.errInfo(error), null, false, false, null, null);
    }

    private Map<String, Object> result(boolean correct, Policy.Outcome outcome, Map<String, Object> steps, String form) {
        Map<String, Object> result = outcomeFields(correct, outcome);
        Map<String, Object> withState = new LinkedHashMap<>(steps);
        if (outcome.commitStateBefore != null) withState.put("commit_state_before", outcome.commitStateBefore);
        if (outcome.bodyError != null && !withState.containsKey("body_error")) withState.put("body_error", outcome.bodyError);
        if (outcome.cleanupError != null && !withState.containsKey("cleanup_error")) withState.put("cleanup_error", outcome.cleanupError);
        result.put("steps", withState);
        result.put("form", form);
        return result;
    }

    private Map<String, Object> outcomeFields(boolean correct, Policy.Outcome outcome) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("reported", outcome.reported);
        fields.put("basis", outcome.basis);
        fields.put("contract", Policy.contract(correct));
        if (outcome.apiError != null) fields.put("api_error", outcome.apiError);
        return fields;
    }

    private static int jdbcIsolation(String level) {
        return switch (level) {
            case "read uncommitted" -> Connection.TRANSACTION_READ_UNCOMMITTED;
            case "read committed" -> Connection.TRANSACTION_READ_COMMITTED;
            case "repeatable read" -> Connection.TRANSACTION_REPEATABLE_READ;
            case "serializable" -> Connection.TRANSACTION_SERIALIZABLE;
            default -> throw new Protocol.ProtocolException("the case requests an unknown isolation level: " + level);
        };
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
            // The pin in pom.xml is the fallback.
        }
        return "42.7.14";
    }

    static final class AppException extends RuntimeException {
        AppException(String message) {
            super(message);
        }
    }
}
