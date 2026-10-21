package org.ppcs.hibernate;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;

import org.hibernate.Session;
import org.hibernate.Transaction;

/** Writes and identity reads on the Session's own connection. */
final class Observe {
    private Observe() {}

    record Ident(String xid, int pid, String isolation) {}

    static Item insertItem(Session session, String name) {
        Item item = new Item(name);
        session.persist(item);
        session.flush();
        return item;
    }

    static void insertTaken(Session session) {
        session.persist(new Uniq("taken"));
        session.flush();
    }

    static Ident identify(Session session, SqlTrace sql, FaultingDataSource.Fault fault, boolean isolation) {
        String statement = isolation
                ? "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')"
                : "select pg_current_xact_id()::text, pg_backend_pid()";
        sql.note(statement);
        Ident ident = session.doReturningWork(connection -> {
            try (PreparedStatement prepared = connection.prepareStatement(statement);
                 ResultSet rows = prepared.executeQuery()) {
                if (!rows.next()) throw new SQLException("identify returned no row");
                return new Ident(rows.getString(1), rows.getInt(2), isolation ? rows.getString(3) : null);
            }
        });
        fault.pid = ident.pid();
        return ident;
    }

    static Map<String, Object> context(Session session, Transaction transaction, Object marker) {
        Map<String, Object> map = new LinkedHashMap<>();
        put(map, "session_open", () -> session.isOpen());
        put(map, "status", () -> transaction.getStatus().name());
        put(map, "rollback_only", transaction::getRollbackOnly);
        put(map, "active", transaction::isActive);
        put(map, "contains_marker", () -> marker != null && session.contains(marker));
        if (marker instanceof Item item) put(map, "marker_id", item::getId);
        return map;
    }

    private static void put(Map<String, Object> map, String key, Read read) {
        try {
            map.put(key, read.get());
        } catch (RuntimeException ex) {
            map.put(key + "_error", ex.getClass().getSimpleName());
        }
    }

    @FunctionalInterface
    private interface Read {
        Object get();
    }
}
