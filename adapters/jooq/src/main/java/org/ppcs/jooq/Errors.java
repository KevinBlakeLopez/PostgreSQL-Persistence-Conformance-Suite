package org.ppcs.jooq;

import java.sql.SQLException;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

import org.jooq.exception.DataAccessException;

/** The protocol's error object: class, SQLSTATE when one exists, and a short message. */
final class Errors {
    private Errors() {}

    static Map<String, Object> info(Throwable error) {
        String message = error.getMessage() == null ? "" : error.getMessage();
        Throwable cause = error.getCause();
        if (cause != null && cause.getMessage() != null && !message.contains(cause.getMessage())) {
            message = message.isEmpty() ? cause.getMessage() : message + ": " + cause.getMessage();
        }
        message = message.replaceAll("\\s+", " ").trim();
        if (message.length() > 500) message = message.substring(0, 500);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", error.getClass().getSimpleName());
        info.put("code", sqlState(error));
        info.put("message", message);
        return info;
    }

    static String sqlState(Throwable error) {
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        Throwable current = error;
        while (current != null && seen.add(current)) {
            if (current instanceof DataAccessException data) {
                String state = data.sqlState();
                if (state != null && !state.isEmpty()) return state;
            }
            if (current instanceof SQLException sql) {
                if (sql.getSQLState() != null && !sql.getSQLState().isEmpty()) return sql.getSQLState();
                SQLException next = sql.getNextException();
                if (next != null && !seen.contains(next)) {
                    current = next;
                    continue;
                }
            }
            current = current.getCause();
        }
        return null;
    }
}
