package org.ppcs.springtx;

import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * The methods the JDK proxy exposes. The adapter calls this interface.
 * It does not call {@link TxTarget} directly, so the call enters
 * {@code TransactionInterceptor}.
 *
 * <p>Annotations are repeated on {@link TxTarget}. Spring resolves the
 * attribute from the most specific method. The copy on this interface is
 * the method a JDK proxy invokes.
 */
public interface TxOps {
    @Transactional(propagation = Propagation.REQUIRED)
    void required(Work work) throws Throwable;

    @Transactional(propagation = Propagation.NESTED)
    void nested(Work work) throws Throwable;

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    void requiresNew(Work work) throws Throwable;

    /** Explicit rollback rule. The default rule does not roll back a checked exception. */
    @Transactional(propagation = Propagation.REQUIRED, rollbackFor = Exception.class)
    void requiredOnException(Work work) throws Throwable;

    @Transactional(propagation = Propagation.REQUIRED, isolation = Isolation.SERIALIZABLE)
    void serializable(Work work) throws Throwable;

    @Transactional(propagation = Propagation.REQUIRED)
    void plain(Work work) throws Throwable;
}
