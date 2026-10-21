package org.ppcs.hibernate;

import java.sql.SQLException;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/** Error object for a protocol result. {@code code} is a SQLSTATE when one is present. */
final class Errors {
    private Errors() {}

    static Map<String, Object> info(Throwable error) {
        StringBuilder message = new StringBuilder();
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        Throwable current = error;
        while (current != null && seen.add(current)) {
            append(message, current.getMessage());
            if (current instanceof SQLException sql && sql.getNextException() != null) {
                append(message, sql.getNextException().getMessage());
            }
            current = current.getCause();
        }
        String text = message.toString().replaceAll("\\s+", " ").trim();
        if (text.length() > 500) text = text.substring(0, 500);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("class", error.getClass().getSimpleName());
        info.put("code", FaultingDataSource.Fault.sqlState(error));
        info.put("message", text);
        return info;
    }

    private static void append(StringBuilder message, String part) {
        if (part == null || part.isBlank() || message.indexOf(part) >= 0) return;
        if (!message.isEmpty()) message.append(": ");
        message.append(part);
    }
}
