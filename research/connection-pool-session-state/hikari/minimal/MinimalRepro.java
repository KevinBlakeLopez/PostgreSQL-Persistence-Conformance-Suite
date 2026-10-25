import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * HikariCP returns a connection to the pool after its state reset failed.
 *
 * A pool of one connection with autoCommit=false and transactionIsolation=TRANSACTION_READ_COMMITTED. Borrower A sets
 * SERIALIZABLE, then calls getSchema(); pgjdbc runs "select current_schema()" and so begins a transaction that
 * HikariCP's commit-state tracking does not count. On close(), HikariCP does not roll back, its reset of the
 * isolation level fails with SQLSTATE 25001, and the connection is returned to the pool anyway. Borrower B then runs
 * inside A's SERIALIZABLE transaction and reads A's snapshot.
 *
 * Usage (single-file launch, Java 11+):
 *   PGURL=jdbc:postgresql://127.0.0.1:5432/postgres PGUSER=postgres PGPASSWORD=... \
 *   java -cp HikariCP-7.1.0.jar:postgresql-42.7.14.jar:slf4j-api-2.0.17.jar MinimalRepro.java
 * It creates and drops a table named hikari_reset_probe. Point it at a disposable database.
 */
public class MinimalRepro {
   public static void main(String[] args) throws Exception {
      String url = System.getenv("PGURL"), user = System.getenv("PGUSER"), password = System.getenv("PGPASSWORD");
      try (Connection setup = DriverManager.getConnection(url, user, password)) {
         run(setup, "drop table if exists hikari_reset_probe; create table hikari_reset_probe (v int); insert into hikari_reset_probe values (0)");
      }

      HikariConfig config = new HikariConfig();
      config.setJdbcUrl(url + (url.contains("?") ? "&" : "?") + "ApplicationName=hikari-reset-probe");
      config.setUsername(user);
      config.setPassword(password);
      config.setMaximumPoolSize(1);
      config.setAutoCommit(false);
      config.setTransactionIsolation("TRANSACTION_READ_COMMITTED");

      try (HikariDataSource ds = new HikariDataSource(config);
           Connection observer = DriverManager.getConnection(url, user, password)) {
         Connection a = ds.getConnection();
         a.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
         a.getSchema();   // pgjdbc: BEGIN; select current_schema()
         run(observer, "update hikari_reset_probe set v = 1");   // committed after A's snapshot was taken
         try {
            a.close();
            System.out.println("A: close() returned normally");
         }
         catch (SQLException e) {
            System.out.println("A: close() threw SQLSTATE " + e.getSQLState() + ": " + e.getMessage());
         }
         System.out.println("pooled backend after A's close(): "
               + scalar(observer, "select state from pg_stat_activity where application_name = 'hikari-reset-probe'"));

         try (Connection b = ds.getConnection()) {
            System.out.println("B: transaction_isolation = " + scalar(b, "show transaction_isolation")
                  + " (pool configured READ COMMITTED)");
            System.out.println("B: hikari_reset_probe.v = " + scalar(b, "select v from hikari_reset_probe")
                  + " (committed value is 1)");
            b.commit();
         }
      }
      try (Connection cleanup = DriverManager.getConnection(url, user, password)) {
         run(cleanup, "drop table hikari_reset_probe");
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
