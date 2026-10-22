package org.ppcs.jooq;

import java.sql.Connection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicReference;

import org.jooq.DSLContext;
import org.jooq.Isolation;
import org.jooq.impl.DSL;

/**
 * The catalog cases. The steps are the same in both modes. {@link Tx} is the
 * only place that chooses {@code DSLContext.transaction} or JDBC.
 */
final class Cases {
    static final String FORM_TOP = "Top-level transaction, then an insert into item through the DSL. "
            + "Native mode is DSLContext.transaction. JDBC mode is Connection.setAutoCommit(false) and Connection.commit, with the same DSL insert.";
    static final String FORM_NESTED = "Outer transaction and a nested DSLContext.transaction, which DefaultTransactionProvider implements as a JDBC savepoint. "
            + "JDBC mode uses Connection.setSavepoint on the same connection. The outer callback catches the nested failure and returns.";
    static final String FORM_MANAGED = "DSLContext.transaction(callback, Isolation.SERIALIZABLE). "
            + "DefaultTransactionProvider.brace calls Connection.setTransactionIsolation before Connection.setAutoCommit(false).";
    static final String FORM_EXPLICIT = "Connection.setTransactionIsolation(TRANSACTION_SERIALIZABLE) before Connection.setAutoCommit(false), then Connection.commit. "
            + "jOOQ executes the insert and the read. DSLContext.transaction is not called. JDBC has no transaction handle distinct from the Connection.";

    private Cases() {}

    static Map<String, Object> dispatch(Main.Session session, String id, Map<String, Object> markers, Map<String, Object> settings) {
        return switch (id) {
            case "CTL-01.commit", "TX-01B.commit-reply-unseen" -> top(session, markers, false);
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
            case "TX-05.managed-serializable" -> isolation(session, markers, settings, true);
            case "TX-05.explicit-serializable" -> isolation(session, markers, settings, false);
            default -> throw new IllegalStateException("this adapter does not implement " + id);
        };
    }

    private static Map<String, Object> top(Main.Session session, Map<String, Object> markers, boolean rollback) {
        Tx.Outcome outcome = run(session, null, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "tx"));
            Sql.Ident ident = identify(session, scope, false);
            session.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            if (rollback) throw new Tx.AppException("application error: the request fails");
        });
        return formed(session, outcome, Map.of(), FORM_TOP);
    }

    private static Map<String, Object> caughtError(Main.Session session, Map<String, Object> markers) {
        Map<String, Object>[] violation = new Map[1];
        Tx.Outcome outcome = run(session, null, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "tx"));
            Sql.Ident ident = identify(session, scope, false);
            session.protocol.checkpoint("after-write", ident.xid(), ident.pid());
            try {
                Sql.insertTaken(scope.dsl);
                throw new IllegalStateException("the duplicate insert did not raise");
            } catch (RuntimeException ex) {
                if (ex instanceof IllegalStateException && "the duplicate insert did not raise".equals(ex.getMessage())) throw ex;
                violation[0] = Errors.info(ex);
            }
            if (violation[0] == null) throw new IllegalStateException("the duplicate insert did not raise");
            session.protocol.checkpoint("before-end", null, ident.pid());
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("callback", "caught");
        if (violation[0] != null) steps.put("violation", violation[0]);
        return formed(session, outcome, steps, FORM_TOP);
    }

    private static Map<String, Object> connLost(Main.Session session, Map<String, Object> markers, Map<String, Object> settings) {
        Tx.Outcome outcome = run(session, null, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "tx"));
            Sql.Ident ident = identify(session, scope, false);
            session.protocol.checkpoint("before-end", ident.xid(), ident.pid());
            sleep(settings);
        });
        return formed(session, outcome, Map.of(), FORM_TOP);
    }

    private static Map<String, Object> savepoint(Main.Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        Integer[] pid = new Integer[1];
        Tx.Outcome[] nested = new Tx.Outcome[1];
        Tx.Outcome outcome = run(session, null, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "outer"));
            Sql.Ident ident = identify(session, scope, false);
            pid[0] = ident.pid();
            session.protocol.checkpoint("outer-after-write", ident.xid(), ident.pid());
            nested[0] = scope.savepoint(inner -> {
                Sql.insertItem(inner.dsl, Json.text(markers, "inner"));
                session.protocol.checkpoint("inner-after-write", null, pid[0]);
                if (kind.equals("conn-lost")) sleep(settings);
                else if (kind.equals("not-sent")) session.fault.arm(Connections.Fault.SAVEPOINT, "client-reject");
                else session.fault.arm(Connections.Fault.SAVEPOINT, "rewrite");
                throw new Tx.AppException("application error: the nested scope fails");
            });
        });
        session.protocol.checkpoint("after-outer", null, pid[0]);
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", Tx.nestedSteps(nested[0]));
        if (!kind.equals("conn-lost")) steps.put("fault", session.fault.report());
        return formed(session, outcome, steps, FORM_NESTED);
    }

    private static Map<String, Object> nested(Main.Session session, Map<String, Object> markers, String variant) {
        Tx.Outcome[] nested = new Tx.Outcome[1];
        Tx.Outcome outcome = run(session, null, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "outer"));
            nested[0] = scope.savepoint(inner -> {
                Sql.insertItem(inner.dsl, Json.text(markers, "inner"));
                Sql.Ident ident = identify(session, inner, false);
                session.protocol.checkpoint("inner-after-write", ident.xid(), ident.pid());
                if (variant.equals("nested-fails")) throw new Tx.AppException("application error: the nested scope fails");
            });
            if (variant.equals("outer-fails")) throw new Tx.AppException("application error: the outer scope fails");
        });
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("nested", Tx.nestedSteps(nested[0]));
        return formed(session, outcome, steps, FORM_NESTED);
    }

    private static Map<String, Object> isolation(Main.Session session, Map<String, Object> markers, Map<String, Object> settings, boolean managed) {
        if (!session.jdbc && !managed) {
            throw new IllegalStateException("native mode has no explicit transaction handle");
        }
        String level = Json.text(settings, "isolation_level");
        if (!"serializable".equals(level)) throw new IllegalStateException("this case requested " + level);
        Integer jdbcLevel = session.jdbc ? Connection.TRANSACTION_SERIALIZABLE : null;
        org.jooq.TransactionProperty[] properties = session.jdbc || !managed
                ? new org.jooq.TransactionProperty[0]
                : new org.jooq.TransactionProperty[] {Isolation.SERIALIZABLE};
        Tx.Outcome outcome = run(session, jdbcLevel, properties, scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "tx"));
            Sql.readItem(scope.dsl, Json.text(markers, "tx"));
            Sql.Ident ident = identify(session, scope, true);
            session.protocol.checkpoint("after-read", ident.xid(), ident.pid(), ident.isolation());
        });
        String form = session.jdbc
                ? "JDBC mode, " + (managed ? "managed case" : "explicit case") + ". " + FORM_EXPLICIT
                : FORM_MANAGED;
        if (outcome.started) {
            Map<String, Object> steps = new LinkedHashMap<>();
            steps.put("requested", level);
            steps.put("isolation_order", session.trace.summary());
            return formed(session, outcome, steps, form);
        }
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("requested", level);
        steps.put("isolation_order", session.trace.summary());
        try {
            Tx.Outcome baseline = run(session, null, scope -> {
                Sql.Ident ident = identify(session, scope, false);
                session.protocol.checkpoint("baseline", ident.xid(), ident.pid());
            });
            if (!"committed".equals(baseline.reported)) {
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("error", baseline.apiError == null
                        ? Map.of("class", "Error", "code", null, "message", baseline.basis)
                        : baseline.apiError);
                steps.put("baseline", error);
            } else {
                steps.put("baseline_reported", baseline.reported);
            }
        } catch (Throwable baselineError) {
            Protocol.rethrowIfProtocol(baselineError);
            steps.put("baseline", Map.of("error", Errors.info(baselineError)));
        }
        return formed(session, outcome, steps, form);
    }

    private static Map<String, Object> reuse(Main.Session session, Map<String, Object> markers, Map<String, Object> settings, String kind) {
        Tx.Outcome unit1 = run(session, null, true, new org.jooq.TransactionProperty[0], scope -> {
            Sql.insertItem(scope.dsl, Json.text(markers, "doomed"));
            Sql.Ident ident = identify(session, scope, false);
            session.protocol.checkpoint("unit1-after-write", ident.xid(), ident.pid());
            if (kind.equals("conn-lost")) sleep(settings);
            else session.fault.arm(Connections.Fault.ROOT, "client-reject");
            if (kind.equals("statement-error")) Sql.insertTaken(scope.dsl);
            throw new Tx.AppException("application error: unit 1 fails");
        });
        session.fault.disarm();
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
        Future<Tx.Outcome> future = executor.submit(() -> {
            try {
                return run(session, null, true, new org.jooq.TransactionProperty[0], scope -> {
                    if (session.protocol.haltCheckpoints) {
                        throw new Protocol.ProtocolException("unit 2 was given up before it wrote");
                    }
                    Sql.insertItem(scope.dsl, Json.text(markers, "next"));
                    Sql.Ident ident = identify(session, scope, false);
                    unit2Pid.set(ident.pid());
                    session.protocol.checkpoint("unit2-after-write", ident.xid(), ident.pid());
                });
            } catch (Protocol.ProtocolException ex) {
                if (session.protocol.haltCheckpoints) return null;
                throw ex;
            }
        });
        Tx.Outcome unit2Result = null;
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
            unit2.putAll(unit2Result.toMap(session.contract()));
        }
        Map<String, Object> reuse = new LinkedHashMap<>();
        reuse.put("unit1_pid", unit1Pid);
        reuse.put("unit2_pid", unit2Pid.get());
        reuse.put("same_backend", unit1Pid != null && unit1Pid.equals(unit2Pid.get()));
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("unit2", unit2);
        steps.put("reuse", reuse);
        if (kind.equals("statement-error") && unit1.apiError != null && "23505".equals(unit1.apiError.get("code"))) {
            steps.put("violation", unit1.apiError);
        } else if (kind.equals("statement-error")) {
            for (Map<String, Object> suppressed : unit1.suppressed) {
                if ("23505".equals(suppressed.get("code"))) steps.put("violation", suppressed);
            }
        }
        if (!kind.equals("conn-lost")) steps.put("fault", session.fault.report());
        return formed(session, unit1, steps, FORM_TOP);
    }

    private static Tx.Outcome run(Main.Session session, Integer isolation, Tx.Body body) {
        return run(session, isolation, false, new org.jooq.TransactionProperty[0], body);
    }

    private static Tx.Outcome run(Main.Session session, Integer isolation, org.jooq.TransactionProperty[] properties, Tx.Body body) {
        return run(session, isolation, false, properties, body);
    }

    private static Tx.Outcome run(Main.Session session, Integer isolation, boolean release, org.jooq.TransactionProperty[] properties, Tx.Body body) {
        if (session.jdbc) return session.jdbc(isolation, release, body);
        return Tx.nativeTop(session.dsl, properties, body);
    }

    private static Sql.Ident identify(Main.Session session, Tx.Scope scope, boolean isolation) {
        Sql.Ident ident = Sql.identify(scope.dsl, isolation);
        session.fault.pid = ident.pid();
        return ident;
    }

    private static Tx.Outcome failed(Throwable escaped) {
        Tx.Outcome outcome = new Tx.Outcome();
        outcome.reported = "failed";
        outcome.basis = "the unit threw before its transaction boundary returned an outcome";
        outcome.apiError = Errors.info(escaped);
        return outcome;
    }

    private static Map<String, Object> formed(Main.Session session, Tx.Outcome outcome, Map<String, Object> extra, String form) {
        Map<String, Object> map = outcome.toMap(session.contract());
        Map<String, Object> steps = new LinkedHashMap<>();
        steps.put("transaction_owner", session.jdbc ? "jdbc" : "jooq");
        steps.put("completion", session.trace.summary());
        if (!outcome.suppressed.isEmpty()) steps.put("suppressed", outcome.suppressed);
        if (!session.listeners.isEmpty()) steps.put("listeners", java.util.List.copyOf(session.listeners));
        steps.putAll(extra);
        map.put("steps", steps);
        map.put("form", form);
        return map;
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

    static DSLContext dsl(Connection connection, Main.Session session) {
        org.jooq.impl.DefaultConfiguration configuration = new org.jooq.impl.DefaultConfiguration();
        configuration.set(connection);
        configuration.set(org.jooq.SQLDialect.POSTGRES);
        configuration.set(session.executeListener());
        return DSL.using(configuration);
    }
}
