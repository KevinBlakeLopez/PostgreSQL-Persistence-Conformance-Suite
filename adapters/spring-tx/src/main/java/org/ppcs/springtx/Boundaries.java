package org.ppcs.springtx;

import java.util.LinkedHashMap;
import java.util.Map;

import org.aopalliance.intercept.MethodInvocation;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.TransactionSystemException;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.DefaultTransactionDefinition;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * The two ways this adapter starts a Spring transaction.
 *
 * <p>Programmatic: {@link TransactionTemplate#execute}. Declarative: a JDK proxy
 * whose advice is {@link TransactionInterceptor}. The proxy is the only object
 * the case code calls. {@link TxTarget} is not called directly.
 */
final class Boundaries {
    enum Kind {
        REQUIRED, NESTED, REQUIRES_NEW, REQUIRED_ON_EXCEPTION, SERIALIZABLE, PLAIN
    }

    /**
     * A callback return is committed. The throwable the callback threw, rethrown
     * by Spring, is rolled back. Any other throwable leaving the boundary is failed.
     * That third report is Spring's rollback or commit exception replacing the
     * application throwable. It is not a claim that PostgreSQL rolled back.
     */
    static final String CONTRACT_PROGRAMMATIC = "Spring Framework 7.0.9 TransactionTemplate.execute "
            + "(org.springframework.transaction.support.TransactionTemplate) obtains a transaction, runs the callback, "
            + "and calls PlatformTransactionManager.commit only when the callback returns. "
            + "On a RuntimeException or Error it rolls the transaction back and rethrows that same throwable. "
            + "On any other throwable it rolls back and throws java.lang.reflect.UndeclaredThrowableException. "
            + "If rollback throws TransactionSystemException, rollbackOnException stores the callback throwable with initApplicationException and throws the TransactionSystemException instead. "
            + "DataSourceTransactionManager.doCommit calls Connection.commit and translateException wraps a SQLException as TransactionSystemException(\"JDBC commit failed\", ex). "
            + "Connection.commit is void and does not return a command tag. "
            + "A normal return from execute is reported as committed. The callback's own throwable leaving execute is reported as rolled_back. "
            + "Any other throwable leaving execute is reported as failed. "
            + "Propagation.NESTED, Spring Framework 7.0.9: \"Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise.\" "
            + "Its note says actual nested transactions work on DataSourceTransactionManager. "
            + "DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. "
            + "Propagation.REQUIRES_NEW: \"Create a new transaction, and suspend the current transaction if one exists.\" "
            + "No custom rollback rule is installed on the template. "
            + "TransactionCallback cannot throw a checked SQLException. Where a case needs that error to leave the callback, the callback rethrows it as SqlUnchecked, a RuntimeException, so the template's RuntimeException rule sees it. "
            + "That wrap is application code. It is not JdbcTemplate's exception translation.";

    static final String CONTRACT_DECLARATIVE = "Spring Framework 7.0.9 @Transactional methods run through TransactionInterceptor "
            + "(org.springframework.transaction.interceptor.TransactionAspectSupport.completeTransactionAfterThrowing). "
            + "The call is on a JDK proxy. The target is not invoked directly. "
            + "If TransactionAttribute.rollbackOn returns true, the interceptor calls PlatformTransactionManager.rollback and rethrows the application throwable. "
            + "If rollback throws TransactionSystemException, that exception replaces the application throwable and initApplicationException stores the original. "
            + "If rollbackOn returns false, the interceptor calls commit. "
            + "With no rollbackFor rules, RuleBasedTransactionAttribute.rollbackOn delegates to DefaultTransactionAttribute.rollbackOn, which is true for RuntimeException and Error only. "
            + "The 7.0.9 reference, Rolling Back a Declarative Transaction, states: \"In its default configuration, the Spring Framework's transaction infrastructure code marks a transaction for rollback only in the case of runtime, unchecked exceptions. That is, when the thrown exception is an instance or subclass of RuntimeException. (Error instances also, by default, result in a rollback).\" "
            + "A normal return is reported as committed. The method's own throwable leaving the proxy is reported as rolled_back. "
            + "Any other throwable leaving the proxy is reported as failed. "
            + "Propagation.NESTED, Spring Framework 7.0.9: \"Execute within a nested transaction if a current transaction exists, behave like REQUIRED otherwise.\" "
            + "DataSourceTransactionManager's class javadoc says nestedTransactionAllowed defaults to true and nested transactions use JDBC savepoints. "
            + "Propagation.REQUIRES_NEW: \"Create a new transaction, and suspend the current transaction if one exists.\" "
            + "The statement-error case uses rollbackFor = Exception.class so a checked SQLException takes the rollback path that case describes. "
            + "The default rule would commit on that checked exception. That default is not substituted for the case.";

    private final boolean declarative;
    private final PlatformTransactionManager manager;
    private final TransactionTemplate required;
    private final TransactionTemplate nested;
    private final TransactionTemplate requiresNew;
    private final TransactionTemplate serializable;
    private final TxOps ops;
    private final CountingInterceptor interceptor;

    Boundaries(PlatformTransactionManager manager, boolean declarative) {
        this.declarative = declarative;
        this.manager = manager;
        this.required = template(manager, TransactionDefinition.PROPAGATION_REQUIRED, TransactionDefinition.ISOLATION_DEFAULT);
        this.nested = template(manager, TransactionDefinition.PROPAGATION_NESTED, TransactionDefinition.ISOLATION_DEFAULT);
        this.requiresNew = template(manager, TransactionDefinition.PROPAGATION_REQUIRES_NEW, TransactionDefinition.ISOLATION_DEFAULT);
        this.serializable = template(manager, TransactionDefinition.PROPAGATION_REQUIRED, TransactionDefinition.ISOLATION_SERIALIZABLE);
        if (declarative) {
            this.interceptor = new CountingInterceptor();
            interceptor.setTransactionManager(manager);
            interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
            interceptor.afterPropertiesSet();
            ProxyFactory factory = new ProxyFactory(new TxTarget());
            factory.setInterfaces(TxOps.class);
            factory.setProxyTargetClass(false);
            factory.addAdvice(interceptor);
            this.ops = (TxOps) factory.getProxy();
        } else {
            this.interceptor = null;
            this.ops = null;
        }
    }

    int invocations() {
        return interceptor == null ? 0 : interceptor.invocations;
    }

    String contract() {
        return declarative ? CONTRACT_DECLARATIVE : CONTRACT_PROGRAMMATIC;
    }

    Map<String, Object> call(Kind kind, Work work) {
        Throwable[] thrown = new Throwable[1];
        Work wrapped = () -> {
            if (declarative && !TransactionSynchronizationManager.isActualTransactionActive()) {
                throw new NotIntercepted("the callback ran without an active Spring transaction");
            }
            try {
                work.run();
            } catch (Throwable ex) {
                thrown[0] = ex;
                throw ex;
            }
        };
        int before = invocations();
        try {
            if (declarative) {
                invokeProxy(kind, wrapped);
            } else {
                invokeTemplate(kind, wrapped, thrown);
            }
        } catch (Throwable escaped) {
            rethrowSetup(escaped);
            if (declarative && invocations() == before) {
                throw new NotIntercepted("the call did not enter TransactionInterceptor");
            }
            return map(escaped, thrown[0]);
        }
        rethrowSetup(thrown[0]);
        if (declarative && invocations() == before) {
            throw new NotIntercepted("the call did not enter TransactionInterceptor");
        }
        return map(null, thrown[0]);
    }

    /**
     * Explicit transaction handle: {@code getTransaction} returns a {@link TransactionStatus},
     * and the application calls {@code commit}. Declarative mode does not use this.
     * The method returns the outcome and whether the body ran.
     */
    Explicit explicit(boolean serializable, Work work) {
        DefaultTransactionDefinition definition = new DefaultTransactionDefinition();
        definition.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        if (serializable) definition.setIsolationLevel(TransactionDefinition.ISOLATION_SERIALIZABLE);
        TransactionStatus status;
        try {
            status = manager.getTransaction(definition);
        } catch (RuntimeException ex) {
            rethrowSetup(ex);
            return new Explicit(map(ex, null), false);
        }
        if (!TransactionSynchronizationManager.isActualTransactionActive()) {
            throw new IllegalStateException("getTransaction returned without an active Spring transaction");
        }
        Throwable thrown = null;
        try {
            work.run();
        } catch (Throwable ex) {
            rethrowSetup(ex);
            thrown = ex;
        }
        if (thrown != null) {
            RuntimeException rollbackError = null;
            try {
                if (!status.isCompleted()) manager.rollback(status);
            } catch (RuntimeException ex) {
                rethrowSetup(ex);
                rollbackError = ex;
            }
            if (rollbackError != null) return new Explicit(map(rollbackError, thrown), true);
            return new Explicit(map(thrown, thrown), true);
        }
        try {
            manager.commit(status);
        } catch (RuntimeException ex) {
            rethrowSetup(ex);
            return new Explicit(map(ex, null), true);
        }
        return new Explicit(map(null, null), true);
    }

    private void invokeProxy(Kind kind, Work work) throws Throwable {
        switch (kind) {
            case REQUIRED -> ops.required(work);
            case NESTED -> ops.nested(work);
            case REQUIRES_NEW -> ops.requiresNew(work);
            case REQUIRED_ON_EXCEPTION -> ops.requiredOnException(work);
            case SERIALIZABLE -> ops.serializable(work);
            case PLAIN -> ops.plain(work);
        }
    }

    private void invokeTemplate(Kind kind, Work work, Throwable[] thrown) {
        TransactionTemplate template = switch (kind) {
            case REQUIRED, REQUIRED_ON_EXCEPTION, PLAIN -> required;
            case NESTED -> nested;
            case REQUIRES_NEW -> requiresNew;
            case SERIALIZABLE -> serializable;
        };
        template.execute(status -> {
            try {
                work.run();
            } catch (RuntimeException | Error ex) {
                throw ex;
            } catch (Throwable ex) {
                // TransactionCallback cannot throw a checked exception. The template itself
                // would wrap one that escaped doInTransaction. Record the wrapper as the
                // throwable the template sees, so a later rethrow still matches it.
                SqlUnchecked unchecked = new SqlUnchecked(ex);
                thrown[0] = unchecked;
                throw unchecked;
            }
            return null;
        });
    }

    private Map<String, Object> map(Throwable escaped, Throwable thrownInside) {
        Map<String, Object> outcome = new LinkedHashMap<>();
        outcome.put("contract", contract());
        if (escaped == null) {
            outcome.put("reported", "committed");
            outcome.put("basis", declarative
                    ? "the @Transactional proxy returned normally, so the interceptor committed"
                    : "TransactionTemplate.execute returned normally, so the template committed");
            return outcome;
        }
        if (thrownInside != null && escaped == thrownInside) {
            outcome.put("reported", "rolled_back");
            outcome.put("basis", declarative
                    ? "the @Transactional proxy rethrew the throwable raised inside the method, so the interceptor rolled back"
                    : "TransactionTemplate.execute rethrew the throwable raised inside the callback, so the template rolled back");
            outcome.put("api_error", errInfo(thrownInside));
            return outcome;
        }
        outcome.put("reported", "failed");
        outcome.put("basis", declarative
                ? "the @Transactional proxy threw a throwable the method did not throw"
                : "TransactionTemplate.execute threw a throwable the callback did not throw");
        outcome.put("api_error", errInfo(escaped));
        return outcome;
    }

    static Map<String, Object> errInfo(Throwable error) {
        StringBuilder message = new StringBuilder();
        java.util.Set<Throwable> seen = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
        Throwable current = error;
        while (current != null && seen.add(current)) {
            appendMessage(message, current.getMessage());
            if (current instanceof java.sql.SQLException sql) appendMessage(message, sql.getNextException() == null ? null : sql.getNextException().getMessage());
            if (current instanceof TransactionSystemException system) appendMessage(message, system.getApplicationException() == null ? null : system.getApplicationException().getMessage());
            current = current.getCause();
        }
        String text = message.toString().replaceAll("\\s+", " ").trim();
        if (text.length() > 500) text = text.substring(0, 500);
        Throwable application = applicationException(error);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", error.getClass().getSimpleName());
        info.put("code", FaultingDataSource.Fault.sqlState(error));
        info.put("message", text);
        if (application != null) info.put("application_class", application.getClass().getSimpleName());
        return info;
    }

    private static void appendMessage(StringBuilder message, String part) {
        if (part == null || part.isBlank() || message.indexOf(part) >= 0) return;
        if (message.length() > 0) message.append(": ");
        message.append(part);
    }

    private static Throwable applicationException(Throwable error) {
        if (error instanceof TransactionSystemException system) return system.getApplicationException();
        return null;
    }

    private static void rethrowSetup(Throwable error) {
        Protocol.rethrowIfProtocol(error);
        Throwable current = error;
        while (current != null) {
            if (current instanceof NotIntercepted notIntercepted) throw notIntercepted;
            if (current instanceof TransactionSystemException system) {
                Throwable application = system.getApplicationException();
                Protocol.rethrowIfProtocol(application);
                if (application instanceof NotIntercepted notIntercepted) throw notIntercepted;
            }
            current = current.getCause();
        }
    }

    private static TransactionTemplate template(PlatformTransactionManager manager, int propagation, int isolation) {
        TransactionTemplate template = new TransactionTemplate(manager);
        template.setPropagationBehavior(propagation);
        if (isolation != TransactionDefinition.ISOLATION_DEFAULT) template.setIsolationLevel(isolation);
        return template;
    }

    /** The body ran, or the transaction failed before the body. */
    record Explicit(Map<String, Object> outcome, boolean entered) {}

    /** TransactionCallback rethrows a checked exception as unchecked. Application code, not Spring JDBC. */
    static final class SqlUnchecked extends RuntimeException {
        SqlUnchecked(Throwable cause) {
            super(cause.getMessage(), cause);
        }
    }

    static final class NotIntercepted extends RuntimeException {
        NotIntercepted(String message) {
            super(message);
        }
    }

    static final class CountingInterceptor extends TransactionInterceptor {
        int invocations;

        @Override
        public Object invoke(MethodInvocation invocation) throws Throwable {
            invocations++;
            return super.invoke(invocation);
        }
    }
}
