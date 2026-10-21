package org.ppcs.hibernate;

import java.util.ArrayList;
import java.util.List;

import org.hibernate.resource.jdbc.spi.StatementInspector;

/** Records SQL Hibernate passes to the driver. The SQL is returned unchanged. */
final class SqlTrace implements StatementInspector {
    final List<String> sql = new ArrayList<>();

    @Override
    public String inspect(String sql) {
        synchronized (this.sql) {
            this.sql.add(sql);
        }
        return sql;
    }

    List<String> snapshot() {
        synchronized (sql) {
            return List.copyOf(sql);
        }
    }

    void clear() {
        synchronized (sql) {
            sql.clear();
        }
    }

    /** SQL this adapter sends through {@code Session.doReturningWork}, which does not pass the inspector. */
    void note(String statement) {
        synchronized (sql) {
            sql.add(statement);
        }
    }
}
