package org.ppcs.springtx;

import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * The transactional target. Each method only runs the {@link Work} it was given.
 * Nested work is another call on the proxy, made by that {@link Work}, not a
 * call to {@code this}. A call to {@code this} would bypass the proxy.
 */
public class TxTarget implements TxOps {
    @Override
    @Transactional(propagation = Propagation.REQUIRED)
    public void required(Work work) throws Throwable {
        work.run();
    }

    @Override
    @Transactional(propagation = Propagation.NESTED)
    public void nested(Work work) throws Throwable {
        work.run();
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void requiresNew(Work work) throws Throwable {
        work.run();
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRED, rollbackFor = Exception.class)
    public void requiredOnException(Work work) throws Throwable {
        work.run();
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRED, isolation = Isolation.SERIALIZABLE)
    public void serializable(Work work) throws Throwable {
        work.run();
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRED)
    public void plain(Work work) throws Throwable {
        work.run();
    }
}
