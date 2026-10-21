package org.ppcs.hibernate;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import org.hibernate.Session;
import org.hibernate.SessionFactory;
import org.hibernate.Transaction;

/**
 * Explicit {@code Session.beginTransaction} / {@code Transaction.commit}.
 *
 * <p>When {@code rollbackOnException} is set, an exception from the work is followed
 * by {@code Transaction.rollback} if the transaction is still active. That is the
 * call {@code TransactionManagement} makes for {@code Session.inTransaction}. TX-01A
 * leaves the flag unset: the work catches the statement error and this method calls
 * {@code commit}. A rollback that throws is the exception the outcome reports.
 * The caught work exception is suppressed on it.
 */
final class Boundary {
    static final String CONTRACT = "Hibernate ORM 7.4.13.Final Transaction (org.hibernate.Transaction) is a resource-local transaction begun with Session.beginTransaction and ended with Transaction.commit or Transaction.rollback. "
            + "The interface javadoc says there is at most one uncommitted transaction for a Session, and that after a rollback the persistence context must be discarded because Hibernate does not restore entity state. "
            + "PostgreSQLDialect.causesRollback returns true, so JdbcCoordinatorImpl.afterFailedStatementExecution marks the JDBC transaction rollback-only when a statement throws SQLException. That call does not send ROLLBACK. "
            + "JdbcResourceLocalTransactionCoordinatorImpl.commitRollbackOnly, when the transaction is MARKED_ROLLBACK, calls rollback and returns. It throws jakarta.persistence.RollbackException only when jpaCompliance.isJpaTransactionComplianceEnabled is true. "
            + "hibernate.jpa.compliance.transaction defaults to hibernate.jpa.compliance, which defaults to false. This adapter sets both false and reads the flag back from the SessionFactory. "
            + "AbstractLogicalConnectionImplementor.begin calls Connection.setAutoCommit(false) unless the provider already disabled autocommit. rollback calls Connection.rollback and then afterCompletion. If Connection.rollback throws, status becomes FAILED_ROLLBACK and afterCompletion is not called. "
            + "afterCompletion calls Connection.setAutoCommit(true) only when autocommit was on at begin, then releases the connection when the handling mode is not ON_CLOSE. "
            + "Session.inTransaction delegates to TransactionManagement.manageTransaction, which calls Transaction.rollback when the action throws and the transaction is still active. "
            + "A returning Transaction.commit is reported as committed. A returning Transaction.rollback, followed by the application error leaving the boundary, is reported as rolled_back. "
            + "An exception leaving the boundary is reported as failed. It is not a claim that PostgreSQL rolled back. "
            + "TX-01A catches the statement error inside the work and then calls Transaction.commit. It does not call Transaction.rollback first.";

    @FunctionalInterface
    interface Work {
        void run(Session session, Transaction transaction) throws Exception;
    }

    static final class Outcome {
        String reported;
        String basis;
        Map<String, Object> apiError;
        Map<String, Object> trigger;
        Map<String, Object> beforeClose;
        Map<String, Object> afterClose;
        List<Map<String, Object>> completionJdbc = List.of();
        boolean rollbackOnException;
        String closeError;

        Map<String, Object> toMap() {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("reported", reported);
            map.put("basis", basis);
            map.put("contract", CONTRACT);
            if (apiError != null) map.put("api_error", apiError);
            return map;
        }
    }

    private Boundary() {}

    static Outcome run(SessionFactory factory, TracingDataSource tracer, boolean rollbackOnException,
                       AtomicReference<Object> marker, Work work) {
        Session session = factory.openSession();
        Transaction transaction = session.beginTransaction();
        Outcome outcome = new Outcome();
        outcome.rollbackOnException = rollbackOnException;
        Exception escaped = null;
        int completionMark = -1;
        try {
            work.run(session, transaction);
            completionMark = tracer.size();
            transaction.commit();
        } catch (Exception ex) {
            Protocol.rethrowIfProtocol(ex);
            outcome.trigger = Errors.info(ex);
            if (rollbackOnException && transaction.isActive()) {
                completionMark = tracer.size();
                try {
                    transaction.rollback();
                    escaped = ex;
                } catch (RuntimeException rollbackFailure) {
                    Protocol.rethrowIfProtocol(rollbackFailure);
                    rollbackFailure.addSuppressed(ex);
                    escaped = rollbackFailure;
                }
            } else {
                escaped = ex;
            }
        } finally {
            if (completionMark >= 0) outcome.completionJdbc = tracer.since(completionMark);
            outcome.beforeClose = Observe.context(session, transaction, marker.get());
            try {
                session.close();
            } catch (RuntimeException closeFailure) {
                outcome.closeError = closeFailure.getClass().getSimpleName() + ": " + closeFailure.getMessage();
            }
            outcome.afterClose = Observe.context(session, transaction, marker.get());
        }
        if (escaped == null) {
            outcome.reported = "committed";
            outcome.basis = "Transaction.commit() returned";
        } else if (escaped instanceof AppException) {
            outcome.reported = "rolled_back";
            outcome.basis = "Transaction.rollback() returned and the application error left the boundary";
            outcome.apiError = Errors.info(escaped);
        } else {
            outcome.reported = "failed";
            outcome.basis = "an exception left the boundary: " + escaped.getClass().getName();
            outcome.apiError = Errors.info(escaped);
        }
        return outcome;
    }

    static final class AppException extends RuntimeException {
        AppException(String message) {
            super(message);
        }
    }
}
