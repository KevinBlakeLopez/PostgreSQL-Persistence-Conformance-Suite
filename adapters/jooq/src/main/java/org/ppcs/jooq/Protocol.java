package org.ppcs.jooq;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * PPCS adapter protocol version 1 on stdin and stdout.
 * A checkpoint exchange failure is a protocol error, never a transaction outcome.
 */
final class Protocol {
    static final int VERSION = 1;

    private final BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
    /** Held across a checkpoint so a timed-out unit cannot write a line in the middle of another exchange. */
    final Object lock = new Object();
    /** Set when unit 2 has been given up. A checkpoint that has not started yet must not start. */
    volatile boolean haltCheckpoints;

    Map<String, Object> read() {
        try {
            while (true) {
                String line = in.readLine();
                if (line == null) throw new ProtocolException("the runner closed the protocol stream");
                line = line.trim();
                if (line.isEmpty()) continue;
                Object parsed;
                try {
                    parsed = Json.parse(line);
                } catch (RuntimeException ex) {
                    continue;
                }
                if (!(parsed instanceof Map<?, ?>)) continue;
                Map<String, Object> message = Json.object(parsed);
                Object version = message.get("ppcs");
                if (version instanceof Long n && n == VERSION) return message;
            }
        } catch (ProtocolException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ProtocolException("reading the protocol stream failed: " + ex.getMessage(), ex);
        }
    }

    void send(Map<String, Object> message) {
        Map<String, Object> line = new LinkedHashMap<>();
        line.put("ppcs", VERSION);
        line.putAll(message);
        System.out.println(Json.stringify(line));
        System.out.flush();
    }

    Map<String, Object> checkpoint(String name, String xid, Integer pid) {
        return checkpoint(name, xid, pid, null);
    }

    Map<String, Object> checkpoint(String name, String xid, Integer pid, String transactionIsolation) {
        synchronized (lock) {
            if (haltCheckpoints) {
                throw new ProtocolException("checkpoint \"" + name + "\" was not sent: the wait for this unit was given up");
            }
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("type", "checkpoint");
            body.put("name", name);
            if (pid != null) body.put("pid", pid);
            if (xid != null) body.put("xid", xid);
            if (transactionIsolation != null) body.put("transaction_isolation", transactionIsolation);
            send(body);
            Map<String, Object> resume = read();
            Object type = resume.get("type");
            Object resumeName = resume.get("name");
            if (!"resume".equals(type) || !name.equals(resumeName)) {
                throw new ProtocolException("expected resume for checkpoint \"" + name + "\"");
            }
            return resume;
        }
    }

    static boolean isProtocol(Throwable error) {
        Throwable current = error;
        while (current != null) {
            if (current instanceof ProtocolException) return true;
            current = current.getCause();
        }
        return false;
    }

    static void rethrowIfProtocol(Throwable error) {
        if (!isProtocol(error)) return;
        Throwable current = error;
        while (current != null) {
            if (current instanceof ProtocolException protocol) throw protocol;
            current = current.getCause();
        }
    }

    static final class ProtocolException extends RuntimeException {
        ProtocolException(String message) {
            super(message);
        }

        ProtocolException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
