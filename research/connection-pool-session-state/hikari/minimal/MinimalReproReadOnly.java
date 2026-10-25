import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * HikariCP returns a connection to the pool after its state reset failed: the default-configuration case.
 *
 * A pool of one connection with HikariCP's defaults (autoCommit=true, readOnly=false). Borrower A runs a read-only
 * report: setReadOnly(true), setAutoCommit(false), a query, commit(), then getSchema() for a log line. pgjdbc runs
 * "select current_schema()" and so begins a transaction that HikariCP's commit-state tracking does not count. On
 * close(), HikariCP does not roll back, its reset of read-only fails with SQLSTATE 25001, and the connection is
 * returned to the pool anyway, with autocommit off and read-only on. Three later borrowers each wait past HikariCP's
 * 500 ms alive-check bypass, so the pool validates the connection before handing it out.
 *
 * Usage (single-file launch, Java 11+):
 *   PGURL=jdbc:postgresql://127.0.0.1:5432/postgres PGUSER=postgres PGPASSWORD=... \
 *   java -cp HikariCP-7.1.0.jar:postgresql-42.7.14.jar:slf4j-api-2.0.17.jar MinimalReproReadOnly.java
 * It creates and drops a table named hikari_ro_probe. Point it at a disposable database.
 */
public class MinimalReproReadOnly {
   public static void main(String[] args) throws Exception {
      String url = System.getenv("PGURL"), user = System.getenv("PGUSER"), password = System.getenv("PGPASSWORD");
      try (Connection setup = DriverManager.getConnection(url, user, password)) {
         run(setup, "drop table if exists hikari_ro_probe; create table hikari_ro_probe (v int)");
      }

      HikariConfig config = new HikariConfig();
      config.setJdbcUrl(url + (url.contains("?") ? "&" : "?") + "ApplicationName=hikari-ro-probe");
      config.setUsername(user);
      config.setPassword(password);
      config.setMaximumPoolSize(1);

      try (HikariDataSource ds = new HikariDataSource(config);
           Connection observer = DriverManager.getConnection(url, user, password)) {
         Connection a = ds.getConnection();
         a.setReadOnly(true);
         a.setAutoCommit(false);
         scalar(a, "select count(*) from hikari_ro_probe");   // the report
         a.commit();
         a.getSchema();   // e.g. for a log line; pgjdbc: BEGIN READ ONLY; select current_schema()
         try {
            a.close();
            System.out.println("A: close() returned normally");
         }
         catch (SQLException e) {
            System.out.println("A: close() threw SQLSTATE " + e.getSQLState() + ": " + e.getMessage());
         }
         String state = scalar(observer, "select state from pg_stat_activity where application_name = 'hikari-ro-probe'");
         System.out.println("pooled backend after A's close(): " + (state == null ? "none (closed)" : state));

         for (String name : new String[] {"B", "C", "D"}) {
            Thread.sleep(600);   // past the 500 ms alive-check bypass window
            try (Connection c = ds.getConnection()) {
               String result;
               try (Statement st = c.createStatement()) {
                  st.execute("insert into hikari_ro_probe values (1)");
                  result = "ok";
               }
               catch (SQLException e) {
                  result = "SQLSTATE " + e.getSQLState();
               }
               System.out.println(name + ": autoCommit=" + c.getAutoCommit() + " readOnly=" + c.isReadOnly()
                     + " (pool defaults: true, false); insert: " + result);
            }
         }
         System.out.println("rows in hikari_ro_probe (three inserts attempted): "
               + scalar(observer, "select count(*) from hikari_ro_probe"));
      }
      try (Connection cleanup = DriverManager.getConnection(url, user, password)) {
         run(cleanup, "drop table hikari_ro_probe");
      }
   }

   static void run(Connection c, String sql) throws SQLException {
      try (Statement st = c.createStatement()) {
         st.execute(sql);
      }
   }

   static String scalar(Connection c, String sql) throws SQLException {
      try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery(sql)) {
         return rs.next() ? rs.getString(1) : null;
      }
   }
}
