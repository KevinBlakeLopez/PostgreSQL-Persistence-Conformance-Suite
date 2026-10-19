package org.ppcs.springtx;

/** Application work inside a Spring transaction boundary. Checked exceptions stay checked. */
@FunctionalInterface
public interface Work {
    void run() throws Throwable;
}
