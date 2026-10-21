// pgjdbc only. No Spring.
//
//   JAVA_HOME=/opt/homebrew/opt/openjdk@21
//   javac -cp adapters/spring-jdbc/target/dependency/postgresql-42.7.14.jar \
//     research/production-reachability/reproductions/PgjdbcCommit.java
//   java -cp research/production-reachability/reproductions:adapters/spring-jdbc/target/dependency/postgresql-42.7.14.jar \
//     PgjdbcCommit
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import org.postgresql.jdbc.PgConnection;

public final class PgjdbcCommit {
    public static void main(String[] args) throws Exception {
        String json = java.nio.file.Files.readString(java.nio.file.Path.of(".ppcs-instance.json"));
        String host = field(json, "host", "127.0.0.1");
        String port = field(json, "port", "55435");
        String user = field(json, "user", "postgres");
        String password = field(json, "password", null);
        String adminUrl = "jdbc:postgresql://" + host + ":" + port + "/postgres";
        String name = "ppcs_repro_pgjdbc";
        try (Connection admin = DriverManager.getConnection(adminUrl, user, password)) {
            admin.setAutoCommit(true);
            try (Statement s = admin.createStatement()) {
                s.execute("drop database if exists " + name + " with (force)");
                s.execute("create database " + name);
            }
        }
        String url = "jdbc:postgresql://" + host + ":" + port + "/" + name;
        try (Connection subject = DriverManager.getConnection(url, user, password);
             Connection observer = DriverManager.getConnection(url, user, password)) {
            observer.setAutoCommit(true);
            try (Statement s = subject.createStatement()) {
                s.execute("create table item (id serial primary key, name text not null)");
                s.execute("create table uniq (id serial primary key, code text not null unique)");
                s.execute("insert into uniq (code) values ('taken')");
            }
            PgConnection pg = subject.unwrap(PgConnection.class);
            subject.setAutoCommit(false);
            try (PreparedStatement insert = subject.prepareStatement("insert into item (name) values (?)")) {
                insert.setString(1, "kept");
                insert.executeUpdate();
            }
            String xid;
            int pid;
            try (Statement s = subject.createStatement();
                 ResultSet rs = s.executeQuery("select pg_current_xact_id()::text, pg_backend_pid()")) {
                rs.next();
                xid = rs.getString(1);
                pid = rs.getInt(2);
            }
            String violation = null;
            try (PreparedStatement dup = subject.prepareStatement("insert into uniq (code) values (?)")) {
                dup.setString(1, "taken");
                dup.executeUpdate();
            } catch (SQLException ex) {
                violation = ex.getSQLState();
            }
            String before = pg.getTransactionState().name();
            String commitResult = "returned";
            String commitState = null;
            try {
                subject.commit();
            } catch (SQLException ex) {
                commitResult = "threw " + ex.getClass().getSimpleName() + " " + ex.getSQLState() + " " + ex.getMessage();
            }
            String after = pg.getTransactionState().name();
            String status;
            int visible;
            try (PreparedStatement q = observer.prepareStatement(
                    "select pg_xact_status(?::xid8), (select count(*) from item where name = 'kept')")) {
                q.setString(1, xid);
                try (ResultSet rs = q.executeQuery()) {
                    rs.next();
                    status = rs.getString(1);
                    visible = rs.getInt(2);
                }
            }
            String reuse = "ok";
            try {
                subject.setAutoCommit(false);
                try (PreparedStatement next = subject.prepareStatement("insert into item (name) values (?)")) {
                    next.setString(1, "next");
                    next.executeUpdate();
                }
                subject.commit();
            } catch (SQLException ex) {
                reuse = "failed " + ex.getSQLState() + " " + ex.getMessage();
            }
            int nextVisible;
            try (Statement s = observer.createStatement();
                 ResultSet rs = s.executeQuery("select count(*) from item where name = 'next'")) {
                rs.next();
                nextVisible = rs.getInt(1);
            }
            System.out.println("driver=" + PgConnection.class.getPackage().getImplementationVersion());
            System.out.println("violation_sqlstate=" + violation);
            System.out.println("xid=" + xid + " backend_pid=" + pid);
            System.out.println("transaction_state_before_commit=" + before);
            System.out.println("commit=" + commitResult);
            System.out.println("transaction_state_after_commit=" + after);
            System.out.println("command_tag=not exposed by Connection.commit()");
            System.out.println("pg_xact_status=" + status);
            System.out.println("kept_visible=" + visible);
            System.out.println("reuse=" + reuse + " next_visible=" + nextVisible);
        } finally {
            try (Connection admin = DriverManager.getConnection(adminUrl, user, password);
                 Statement s = admin.createStatement()) {
                admin.setAutoCommit(true);
                s.execute("drop database if exists " + name + " with (force)");
            }
        }
    }

    private static String field(String json, String key, String fallback) {
        String needle = "\"" + key + "\"";
        int i = json.indexOf(needle);
        if (i < 0) {
            return fallback;
        }
        int colon = json.indexOf(':', i + needle.length());
        int start = colon + 1;
        while (start < json.length() && Character.isWhitespace(json.charAt(start))) {
            start++;
        }
        if (json.charAt(start) == '"') {
            int end = json.indexOf('"', start + 1);
            return json.substring(start + 1, end);
        }
        int end = start;
        while (end < json.length() && "0123456789".indexOf(json.charAt(end)) >= 0) {
            end++;
        }
        return json.substring(start, end);
    }
}
