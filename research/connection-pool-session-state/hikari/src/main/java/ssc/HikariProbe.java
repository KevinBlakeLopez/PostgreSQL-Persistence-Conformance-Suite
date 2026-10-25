package ssc;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.postgresql.PGConnection;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * HikariCP session-state probes. Each scenario uses a pool of one physical connection and consecutive borrowers.
 *
 * <p>Evidence comes from three places, never from HikariCP's bookkeeping alone:
 * <ul>
 *   <li>the borrower's own reads through the borrowed connection;</li>
 *   <li>an independent observer connection (a superuser, outside the pool) reading pg_stat_activity and the tables;</li>
 *   <li>the server's statement log (docker logs), read separately.</li>
 * </ul>
 * Physical-session identity is the backend PID reported by the driver (no SQL) together with that backend's
 * backend_start as seen by the observer. The output has no PIDs, timestamps or transaction IDs.
 *
 * <p>Usage: java -cp ... ssc.HikariProbe &lt;instance-file&gt; &lt;scenario&gt;
 */
public final class HikariProbe {
   private static Map<String, String> inst;
   private static Connection observer;
   private static String appName;

   public static void main(String[] args) throws Exception {
      inst = parseInstance(Files.readString(Path.of(args[0])));
      String scenario = args[1];
      appName = "ssc-hikari-" + scenario;
      observer = DriverManager.getConnection(url("ssc-hikari-observer"), props(true));
      String token = scalar(observer, "select current_setting('cluster_name')");
      if (!token.equals(inst.get("token"))) {
         throw new IllegalStateException("refusing: cluster_name is not this investigation's server");
      }
      exec(observer, "delete from public.item; delete from tenant_a.item; delete from tenant_b.item; "
            + "update public.probe_row set v = 0");
      System.out.println("scenario: " + scenario);
      switch (scenario) {
         case "iso-reset" -> isoReset();
         case "schema-unconfigured" -> schemaReset(null);
         case "schema-configured" -> schemaReset("public");
         case "setup-schema-noautocommit" -> setupSchemaNoAutocommit();
         case "reset-undone" -> resetUndone();
         case "reset-fails" -> resetFails(true);
         case "reset-fails-control" -> resetFails(false);
         case "reset-fails-readonly" -> resetFailsReadOnly();
         case "reset-fails-configured-getschema" -> resetFailsConfigured("getSchema", false);
         case "reset-fails-configured-setschema" -> resetFailsConfigured("setSchema", false);
         case "reset-fails-configured-savepoint" -> resetFailsConfigured("setSavepoint", false);
         case "reset-fails-configured-none" -> resetFailsConfigured("none", false);
         case "reset-fails-configured-evicted" -> resetFailsConfigured("setSchema", true);
         case "readonly-report-poison" -> readOnlyReportPoison();
         case "raw-sql-state" -> rawSqlState();
         case "readonly-report-override" -> readOnlyReportOverride();
         case "autocommit-reset-commits" -> autocommitResetCommits();
         case "reset-fails-isolate-internal" -> resetFailsIsolateInternal();
         default -> throw new IllegalArgumentException("unknown scenario " + scenario);
      }
      observer.close();
   }

   // ---------------------------------------------------------------------------------------------------------------
   // Scenarios

   /** Control: an isolation level set through JDBC is restored to the captured driver default on close. */
   private static void isoReset() throws Exception {
      try (var ds = pool(true, null)) {
         Session a = borrow(ds, "A");
         a.conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         print("A", "setTransactionIsolation(SERIALIZABLE), then close()", closeOutcome(a));
         Thread.sleep(1000);
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "show transaction_isolation (autocommit statement)", scalar(b.conn, "show transaction_isolation"));
         print("B", "close()", closeOutcome(b));
      }
   }

   /** Schema set through Connection.setSchema(), with the pool's schema property unset or set. */
   private static void schemaReset(String configuredSchema) throws Exception {
      try (var ds = pool(true, configuredSchema)) {
         Session a = borrow(ds, "A");
         print("A", "current_schema() at checkout", scalar(a.conn, "select current_schema()"));
         a.conn.setSchema("tenant_a");
         print("A", "current_schema() after setSchema(\"tenant_a\")", scalar(a.conn, "select current_schema()"));
         print("A", "close()", closeOutcome(a));
         Thread.sleep(1000);
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "current_schema() at checkout", scalar(b.conn, "select current_schema()"));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         print("observer", "where B's unqualified insert landed", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));
      }
   }

   /** The pool's schema property with autoCommit=false: is the setup's SET committed? */
   private static void setupSchemaNoAutocommit() throws Exception {
      try (var ds = pool(false, "tenant_b")) {
         print("observer", "pool backend after pool start", backendState());
         Session a = borrow(ds, "A");
         print("A", "current_schema() at checkout", scalar(a.conn, "select current_schema()"));
         exec(a.conn, "insert into item(label) values ('A-unqualified')");
         a.conn.rollback();
         print("A", "current_schema() after A's rollback()", scalar(a.conn, "select current_schema()"));
         a.conn.commit();
         print("A", "close()", closeOutcome(a));
         Thread.sleep(1000);
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         b.conn.commit();
         print("observer", "where B's committed unqualified insert landed", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));
      }
   }

   /** autoCommit=false, schema property set: HikariCP's own reset SET runs in a transaction it does not commit. */
   private static void resetUndone() throws Exception {
      try (var ds = pool(false, "public")) {
         Session z = borrow(ds, "Z");
         z.conn.commit();   // ends whatever the connection setup left open, so the scenario starts clean
         print("Z", "commit(), then close()", closeOutcome(z));
         print("observer", "pool backend before A", backendState());

         Session a = borrow(ds, "A");
         a.conn.setSchema("tenant_a");
         exec(a.conn, "insert into item(label) values ('A-unqualified')");
         a.conn.commit();
         print("observer", "where A's committed unqualified insert landed", landed("A-unqualified"));
         print("A", "setSchema(\"tenant_a\"), insert, commit(), then close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());

         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "current_schema() at checkout", scalar(b.conn, "select current_schema()"));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         b.conn.rollback();
         print("B", "current_schema() after B's rollback()", scalar(b.conn, "select current_schema()"));
         b.conn.commit();
         print("B", "close()", closeOutcome(b));
         print("observer", "pool backend after B's close()", backendState());

         Session c = borrow(ds, "C");
         print("C", "same physical session as A", c.sameAs(a));
         exec(c.conn, "insert into item(label) values ('C-unqualified')");
         c.conn.commit();
         print("observer", "where C's committed unqualified insert landed", landed("C-unqualified"));
         print("C", "close()", closeOutcome(c));
      }
   }

   /**
    * autoCommit=false. A changes the session's isolation through JDBC (tracked), and a later getSchema() opens a
    * transaction that HikariCP's commit-state flag does not see. With openTransaction=false the getSchema() call is
    * skipped: that is the control.
    */
   private static void resetFails(boolean openTransaction) throws Exception {
      try (var ds = pool(false, null)) {
         Session z = borrow(ds, "Z");
         z.conn.commit();
         print("Z", "commit(), then close()", closeOutcome(z));

         Session a = borrow(ds, "A");
         a.conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         if (openTransaction) {
            print("A", "getSchema() (pgjdbc runs select current_schema())", a.conn.getSchema());
         }
         print("observer", "pool backend before A's close()", backendState());
         exec(observer, "update public.probe_row set v = 1");
         print("observer", "committed probe_row.v = 1 after A's last statement", "done");
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         Thread.sleep(1000);

         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "getTransactionIsolation() through the pool", isolationName(b.conn.getTransactionIsolation()));
         print("B", "show transaction_isolation", scalar(b.conn, "show transaction_isolation"));
         print("B", "B's first statement is not its transaction's first (now() < statement_timestamp() - 500 ms)",
               scalar(b.conn, "select (now() < statement_timestamp() - interval '500 milliseconds')::text"));
         print("B", "probe_row.v as B reads it (observer committed 1)", scalar(b.conn, "select v::text from public.probe_row"));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         b.conn.commit();
         print("observer", "where B's committed insert landed", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));

         Session c = borrow(ds, "C");
         print("C", "same physical session as A", c.sameAs(a));
         print("C", "show transaction_isolation", scalar(c.conn, "show transaction_isolation"));
         c.conn.commit();
         print("C", "close()", closeOutcome(c));
      }
   }

   /**
    * autoCommit=false with both defaults configured explicitly: transactionIsolation=TRANSACTION_READ_COMMITTED and
    * schema=public. A sets SERIALIZABLE through JDBC, then one driver call that pgjdbc implements with SQL and that
    * HikariCP's commit-state flag does not count: getSchema(), setSchema("tenant_a") or setSavepoint(). "none" is
    * the control. With evictBeforeB, the pool soft-evicts its connections after A's close(): the recovery control.
    */
   private static void resetFailsConfigured(String trigger, boolean evictBeforeB) throws Exception {
      try (var ds = pool(false, "public", "TRANSACTION_READ_COMMITTED")) {
         Session z = borrow(ds, "Z");
         z.conn.commit();   // ends the transaction the setup's setSchema("public") left open (HikariCP #1369)
         print("Z", "commit(), then close()", closeOutcome(z));

         Session a = borrow(ds, "A");
         a.conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         switch (trigger) {
            case "getSchema" -> print("A", "getSchema()", a.conn.getSchema());
            case "setSchema" -> {
               a.conn.setSchema("tenant_a");
               print("A", "setSchema(\"tenant_a\")", "done");
            }
            case "setSavepoint" -> {
               a.conn.setSavepoint();
               print("A", "setSavepoint()", "done");
            }
            default -> print("A", "no further call (control)", "done");
         }
         print("observer", "pool backend before A's close()", backendState());
         exec(observer, "update public.probe_row set v = 1");
         print("observer", "committed probe_row.v = 1 after A's last statement", "done");
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         if (evictBeforeB) {
            ds.getHikariPoolMXBean().softEvictConnections();
            print("pool", "softEvictConnections() after A's close()", "done");
         }
         Thread.sleep(1000);

         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "show transaction_isolation", scalar(b.conn, "show transaction_isolation"));
         print("B", "current_schema()", scalar(b.conn, "select current_schema()"));
         print("B", "B's first statement is not its transaction's first (now() < statement_timestamp() - 500 ms)",
               scalar(b.conn, "select (now() < statement_timestamp() - interval '500 milliseconds')::text"));
         print("B", "probe_row.v as B reads it (observer committed 1)", scalar(b.conn, "select v::text from public.probe_row"));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         b.conn.commit();
         print("observer", "where B's committed unqualified insert landed", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));

         Session c = borrow(ds, "C");
         print("C", "same physical session as B", c.sameAs(b));
         print("C", "show transaction_isolation", scalar(c.conn, "show transaction_isolation"));
         print("C", "current_schema()", scalar(c.conn, "select current_schema()"));
         c.conn.commit();
         print("C", "close()", closeOutcome(c));
      }
   }

   /**
    * The pool's defaults (autoCommit=true, readOnly=false). A is a read-only report: setReadOnly(true),
    * setAutoCommit(false), a query, commit(), then getSchema() for a log line, then close(). Later borrowers expect
    * the pool's defaults and insert in autocommit mode.
    */
   private static void readOnlyReportPoison() throws Exception {
      try (var ds = pool(true, null)) {
         Session a = borrow(ds, "A");
         a.conn.setReadOnly(true);
         a.conn.setAutoCommit(false);
         print("A", "setReadOnly(true), setAutoCommit(false), report query", scalar(a.conn, "select count(*)::text from public.item"));
         a.conn.commit();
         print("A", "commit(), then getSchema() for a log line", a.conn.getSchema());
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         for (String name : new String[] {"B", "C", "D"}) {
            Thread.sleep(600);   // past the 500 ms alive-check bypass window, so HikariCP validates on each borrow
            Session s = borrow(ds, name);
            print(name, "same physical session as A", s.sameAs(a));
            print(name, "getAutoCommit() | isReadOnly() through the pool",
                  s.conn.getAutoCommit() + " | " + s.conn.isReadOnly());
            print(name, "insert (expects the pool default, autocommit)",
                  tryExec(s.conn, "insert into item(label) values ('" + name + "-unqualified')"));
            print("observer", "where " + name + "'s insert is visible", landed(name + "-unqualified"));
            print(name, "close()", closeOutcome(s));
            print("observer", "pool backend after " + name + "'s close()", backendState());
         }
      }
   }

   /**
    * Pool default autoCommit=true. A turns autocommit off and sets SERIALIZABLE (both tracked), and getSchema() opens a
    * transaction the commit-state flag does not see. Read-only is not dirty, so the autocommit reset runs first.
    */
   private static void autocommitResetCommits() throws Exception {
      try (var ds = pool(true, null)) {
         Session a = borrow(ds, "A");
         a.conn.setAutoCommit(false);
         a.conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         print("A", "setAutoCommit(false), setTransactionIsolation(SERIALIZABLE), getSchema()", a.conn.getSchema());
         print("observer", "pool backend before A's close()", backendState());
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "getAutoCommit() through the pool", String.valueOf(b.conn.getAutoCommit()));
         print("B", "show transaction_isolation", scalar(b.conn, "show transaction_isolation"));
         print("B", "close()", closeOutcome(b));
      }
   }

   /**
    * readonly-report-poison on unmodified HikariCP, with exceptionOverrideClassName set to EvictOnStateResetRejected:
    * the configuration-only mitigation.
    */
   private static void readOnlyReportOverride() throws Exception {
      var config = new HikariConfig();
      config.setPoolName("ssc");
      config.setJdbcUrl(url(appName));
      config.setUsername(inst.get("user"));
      config.setPassword(inst.get("password"));
      config.setMaximumPoolSize(1);
      config.setMinimumIdle(1);
      config.setExceptionOverrideClassName(EvictOnStateResetRejected.class.getName());
      try (var ds = new HikariDataSource(config)) {
         Session a = borrow(ds, "A");
         a.conn.setReadOnly(true);
         a.conn.setAutoCommit(false);
         print("A", "setReadOnly(true), setAutoCommit(false), report query", scalar(a.conn, "select count(*)::text from public.item"));
         a.conn.commit();
         print("A", "commit(), then getSchema() for a log line", a.conn.getSchema());
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         Thread.sleep(600);
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "getAutoCommit() | isReadOnly() through the pool", b.conn.getAutoCommit() + " | " + b.conn.isReadOnly());
         print("B", "insert (expects the pool default, autocommit)", tryExec(b.conn, "insert into item(label) values ('B-unqualified')"));
         print("observer", "where B's insert is visible", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));
      }
   }

   /**
    * Session state changed with SQL rather than through the JDBC API, on a pool with schema=public configured.
    * HikariCP tracks only JDBC API calls, so none of this sets a dirty bit.
    */
   private static void rawSqlState() throws Exception {
      try (var ds = pool(true, "public")) {
         Session a = borrow(ds, "A");
         exec(a.conn, "SET search_path TO tenant_a, public");
         exec(a.conn, "SET ROLE ssc_tenant_a");
         exec(a.conn, "select pg_advisory_lock(4713)");
         exec(a.conn, "CREATE TEMP TABLE ssc_temp_probe (id int)");
         print("A", "SQL: SET search_path, SET ROLE, pg_advisory_lock, CREATE TEMP TABLE", "done");
         print("A", "close()", closeOutcome(a));
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "current_user | search_path", scalar(b.conn, "select current_user || ' | ' || current_setting('search_path')"));
         print("B", "ssc_temp_probe visible", scalar(b.conn, "select (to_regclass('pg_temp.ssc_temp_probe') is not null)::text"));
         print("observer", "advisory lock 4713 held by the pool's backend",
               scalar(observer, "select (count(*) > 0)::text from pg_locks l join pg_stat_activity s using (pid) "
                     + "where l.locktype = 'advisory' and l.objid = 4713 and s.application_name = '" + appName + "'"));
         exec(b.conn, "insert into item(label) values ('B-unqualified')");
         print("observer", "where B's unqualified insert landed, and as whom",
               scalar(observer, "select string_agg(s || '/' || u, ', ') from (select 'public' s, inserted_by::text u "
                     + "from public.item where label = 'B-unqualified' union all select 'tenant_a', inserted_by::text "
                     + "from tenant_a.item where label = 'B-unqualified') x"));
         exec(b.conn, "RESET ROLE; select pg_advisory_unlock_all()");
         print("B", "close()", closeOutcome(b));
      }
   }

   /** reset-fails with isolateInternalQueries=true: HikariCP rolls back after its alive check on borrow. */
   private static void resetFailsIsolateInternal() throws Exception {
      var config = new HikariConfig();
      config.setPoolName("ssc");
      config.setJdbcUrl(url(appName));
      config.setUsername(inst.get("user"));
      config.setPassword(inst.get("password"));
      config.setMaximumPoolSize(1);
      config.setMinimumIdle(1);
      config.setAutoCommit(false);
      config.setTransactionIsolation("TRANSACTION_READ_COMMITTED");
      config.setIsolateInternalQueries(true);
      try (var ds = new HikariDataSource(config)) {
         Session a = borrow(ds, "A");
         a.conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         print("A", "getSchema()", a.conn.getSchema());
         exec(observer, "update public.probe_row set v = 1");
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         Thread.sleep(1000);   // so the borrow runs the alive check, which isolateInternalQueries follows with rollback()
         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("observer", "B's backend at checkout, before B's first statement", backendState());
         print("B", "show transaction_isolation", scalar(b.conn, "show transaction_isolation"));
         print("B", "probe_row.v as B reads it (observer committed 1)", scalar(b.conn, "select v::text from public.probe_row"));
         b.conn.commit();
         print("B", "close()", closeOutcome(b));
      }
   }

   /**
    * Pool default autoCommit=true. A turns autocommit off and read-only on (both tracked), and getSchema() opens a
    * transaction the commit-state flag does not see. HikariCP resets read-only first.
    */
   private static void resetFailsReadOnly() throws Exception {
      try (var ds = pool(true, null)) {
         Session a = borrow(ds, "A");
         a.conn.setAutoCommit(false);
         a.conn.setReadOnly(true);
         print("A", "getSchema() (pgjdbc runs select current_schema())", a.conn.getSchema());
         print("A", "close()", closeOutcome(a));
         print("observer", "pool backend after A's close()", backendState());
         Thread.sleep(1000);

         Session b = borrow(ds, "B");
         print("B", "same physical session as A", b.sameAs(a));
         print("B", "getAutoCommit() through the pool", String.valueOf(b.conn.getAutoCommit()));
         print("B", "isReadOnly() through the pool", String.valueOf(b.conn.isReadOnly()));
         print("B", "insert (B expects autocommit)", tryExec(b.conn, "insert into item(label) values ('B-unqualified')"));
         print("observer", "where B's insert is visible", landed("B-unqualified"));
         print("B", "close()", closeOutcome(b));
         print("observer", "pool backend after B's close()", backendState());
      }
   }

   // ---------------------------------------------------------------------------------------------------------------
   // Helpers

   private record Session(String name, Connection conn, int pid, String backendStart) {
      String sameAs(Session other) {
         return String.valueOf(pid == other.pid && backendStart.equals(other.backendStart));
      }
   }

   private static Session borrow(HikariDataSource ds, String name) throws SQLException {
      Connection conn = ds.getConnection();
      int pid = conn.unwrap(PGConnection.class).getBackendPID();   // from BackendKeyData: no SQL is sent
      String start = scalar(observer, "select backend_start::text from pg_stat_activity where pid = " + pid);
      return new Session(name, conn, pid, start);
   }

   private static String closeOutcome(Session s) {
      try {
         s.conn.close();
         return "returned normally";
      }
      catch (SQLException e) {
         return "threw SQLException SQLSTATE " + e.getSQLState() + ": " + e.getMessage();
      }
   }

   private static String backendState() throws SQLException {
      List<String> rows = new ArrayList<>();
      try (var st = observer.createStatement();
           ResultSet rs = st.executeQuery("select state, xact_start is not null, backend_xid is not null, "
                 + "backend_xmin is not null from pg_stat_activity where application_name = '" + appName + "' "
                 + "and datname = current_database() order by pid")) {
         while (rs.next()) {
            rows.add("state=" + rs.getString(1) + " xact_open=" + rs.getBoolean(2) + " xid=" + rs.getBoolean(3)
                  + " xmin=" + rs.getBoolean(4));
         }
      }
      return rows.isEmpty() ? "no backend" : String.join("; ", rows);
   }

   private static String landed(String label) throws SQLException {
      List<String> rows = new ArrayList<>();
      try (var ps = observer.prepareStatement("select 'public', inserted_by from public.item where label = ? "
            + "union all select 'tenant_a', inserted_by from tenant_a.item where label = ? "
            + "union all select 'tenant_b', inserted_by from tenant_b.item where label = ? order by 1")) {
         ps.setString(1, label);
         ps.setString(2, label);
         ps.setString(3, label);
         try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
               rows.add(rs.getString(1) + "/" + rs.getString(2));
            }
         }
      }
      return rows.isEmpty() ? "not visible (uncommitted or absent)" : String.join(", ", rows);
   }

   private static String tryExec(Connection conn, String sql) {
      try {
         exec(conn, sql);
         return "ok";
      }
      catch (SQLException e) {
         return "SQLSTATE " + e.getSQLState() + ": " + e.getMessage().lines().findFirst().orElse("");
      }
   }

   private static String isolationName(int level) {
      return switch (level) {
         case Connection.TRANSACTION_READ_COMMITTED -> "READ_COMMITTED";
         case Connection.TRANSACTION_REPEATABLE_READ -> "REPEATABLE_READ";
         case Connection.TRANSACTION_SERIALIZABLE -> "SERIALIZABLE";
         default -> String.valueOf(level);
      };
   }

   private static void print(String who, String step, String observed) {
      System.out.printf("%-9s %-92s %s%n", who, step, observed);
   }

   private static HikariDataSource pool(boolean autoCommit, String schema) {
      return pool(autoCommit, schema, null);
   }

   private static HikariDataSource pool(boolean autoCommit, String schema, String isolation) {
      var config = new HikariConfig();
      if (isolation != null) {
         config.setTransactionIsolation(isolation);
      }
      config.setPoolName("ssc");
      config.setJdbcUrl(url(appName));
      config.setUsername(inst.get("user"));
      config.setPassword(inst.get("password"));
      config.setMaximumPoolSize(1);
      config.setMinimumIdle(1);
      config.setAutoCommit(autoCommit);
      if (schema != null) {
         config.setSchema(schema);
      }
      return new HikariDataSource(config);
   }

   private static String url(String applicationName) {
      return "jdbc:postgresql://" + inst.get("host") + ":" + inst.get("port") + "/" + inst.get("database")
            + "?ApplicationName=" + applicationName;
   }

   private static Properties props(boolean superuser) {
      var p = new Properties();
      p.setProperty("user", inst.get(superuser ? "superuser" : "user"));
      p.setProperty("password", inst.get(superuser ? "superuser_password" : "password"));
      return p;
   }

   private static String scalar(Connection conn, String sql) throws SQLException {
      try (Statement st = conn.createStatement(); ResultSet rs = st.executeQuery(sql)) {
         return rs.next() ? rs.getString(1) : null;
      }
   }

   private static void exec(Connection conn, String sql) throws SQLException {
      try (Statement st = conn.createStatement()) {
         st.execute(sql);
      }
   }

   private static Map<String, String> parseInstance(String json) {
      Map<String, String> m = new HashMap<>();
      Matcher matcher = Pattern.compile("\"(\\w+)\":(?:\"([^\"]*)\"|(\\d+))").matcher(json);
      while (matcher.find()) {
         m.put(matcher.group(1), matcher.group(2) != null ? matcher.group(2) : matcher.group(3));
      }
      return m;
   }
}
