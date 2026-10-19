package org.ppcs.springtx;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** A small JSON codec for the protocol messages. Objects keep insertion order. */
final class Json {
    private Json() {}

    static Object parse(String text) {
        Parser parser = new Parser(text);
        Object value = parser.parseValue();
        parser.skip();
        if (parser.i != parser.s.length()) {
            throw new IllegalArgumentException("trailing data in JSON");
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> object(Object value) {
        if (!(value instanceof Map<?, ?> map)) {
            throw new IllegalArgumentException("expected a JSON object");
        }
        return (Map<String, Object>) map;
    }

    static String text(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (!(value instanceof String s)) {
            throw new IllegalArgumentException("expected a string at " + key);
        }
        return s;
    }

    static int integer(Map<String, Object> object, String key) {
        Object value = object.get(key);
        if (!(value instanceof Long n)) {
            throw new IllegalArgumentException("expected an integer at " + key);
        }
        return Math.toIntExact(n);
    }

    static int integer(Map<String, Object> object, String key, int fallback) {
        Object value = object.get(key);
        if (value == null) return fallback;
        if (!(value instanceof Long n)) {
            throw new IllegalArgumentException("expected an integer at " + key);
        }
        return Math.toIntExact(n);
    }

    static String stringify(Object value) {
        StringBuilder out = new StringBuilder();
        write(out, value);
        return out.toString();
    }

    private static void write(StringBuilder out, Object value) {
        switch (value) {
            case null -> out.append("null");
            case String s -> writeString(out, s);
            case Boolean b -> out.append(b ? "true" : "false");
            case Integer n -> out.append(n);
            case Long n -> out.append(n);
            case Number n -> out.append(n);
            case Map<?, ?> map -> {
                out.append('{');
                boolean first = true;
                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    if (!first) out.append(',');
                    first = false;
                    writeString(out, String.valueOf(entry.getKey()));
                    out.append(':');
                    write(out, entry.getValue());
                }
                out.append('}');
            }
            case List<?> list -> {
                out.append('[');
                boolean first = true;
                for (Object item : list) {
                    if (!first) out.append(',');
                    first = false;
                    write(out, item);
                }
                out.append(']');
            }
            default -> throw new IllegalArgumentException("cannot encode " + value.getClass().getName());
        }
    }

    private static void writeString(StringBuilder out, String value) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
                }
            }
        }
        out.append('"');
    }

    private static final class Parser {
        final String s;
        int i;

        Parser(String s) {
            this.s = s;
        }

        Object parseValue() {
            skip();
            if (i >= s.length()) throw new IllegalArgumentException("unexpected end of JSON");
            char c = s.charAt(i);
            if (c == '{') return parseObject();
            if (c == '[') return parseArray();
            if (c == '"') return parseString();
            if (c == 't') return literal("true", Boolean.TRUE);
            if (c == 'f') return literal("false", Boolean.FALSE);
            if (c == 'n') return literal("null", null);
            return parseNumber();
        }

        Map<String, Object> parseObject() {
            expect('{');
            Map<String, Object> object = new LinkedHashMap<>();
            skip();
            if (peek('}')) {
                i++;
                return object;
            }
            while (true) {
                skip();
                String key = parseString();
                skip();
                expect(':');
                object.put(key, parseValue());
                skip();
                if (peek('}')) {
                    i++;
                    return object;
                }
                expect(',');
            }
        }

        List<Object> parseArray() {
            expect('[');
            List<Object> list = new ArrayList<>();
            skip();
            if (peek(']')) {
                i++;
                return list;
            }
            while (true) {
                list.add(parseValue());
                skip();
                if (peek(']')) {
                    i++;
                    return list;
                }
                expect(',');
            }
        }

        String parseString() {
            expect('"');
            StringBuilder out = new StringBuilder();
            while (i < s.length()) {
                char c = s.charAt(i++);
                if (c == '"') return out.toString();
                if (c != '\\') {
                    out.append(c);
                    continue;
                }
                if (i >= s.length()) throw new IllegalArgumentException("truncated escape");
                char e = s.charAt(i++);
                switch (e) {
                    case '"', '\\', '/' -> out.append(e);
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> {
                        if (i + 4 > s.length()) throw new IllegalArgumentException("truncated unicode escape");
                        out.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                        i += 4;
                    }
                    default -> throw new IllegalArgumentException("bad escape \\" + e);
                }
            }
            throw new IllegalArgumentException("unterminated string");
        }

        Long parseNumber() {
            int start = i;
            if (peek('-')) i++;
            if (i >= s.length() || !Character.isDigit(s.charAt(i))) {
                throw new IllegalArgumentException("expected a number");
            }
            while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
            if (i < s.length() && (s.charAt(i) == '.' || s.charAt(i) == 'e' || s.charAt(i) == 'E')) {
                throw new IllegalArgumentException("only integers are used in protocol messages");
            }
            return Long.parseLong(s.substring(start, i));
        }

        Object literal(String word, Object value) {
            if (!s.startsWith(word, i)) throw new IllegalArgumentException("expected " + word);
            i += word.length();
            return value;
        }

        void skip() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
        }

        boolean peek(char c) {
            return i < s.length() && s.charAt(i) == c;
        }

        void expect(char c) {
            if (!peek(c)) throw new IllegalArgumentException("expected '" + c + "'");
            i++;
        }
    }
}
