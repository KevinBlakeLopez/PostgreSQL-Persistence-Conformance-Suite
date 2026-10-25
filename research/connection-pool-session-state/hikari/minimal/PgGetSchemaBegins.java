import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * pgjdbc only, no pool: in non-autocommit mode, Connection.getSchema() begins a transaction, unlike
 * getTransactionIsolation(). An observer connection reads the session's state from pg_stat_activity.
 *
 * Usage (single-file launch, Java 11+):
 *   PGURL=jdbc:postgresql://127.0.0.1:5432/postgres PGUSER=postgres PGPASSWORD=... \
 *   java -cp postgresql-42.7.14.jar PgGetSchemaBegins.java
 */
public class PgGetSchemaBegins {
   public static void main(String[] args) throws Exception {
      String url = System.getenv("PGURL"), user = System.getenv("PGUSER"), password = System.getenv("PGPASSWORD");
      String app = "pgjdbc-getschema-probe";
      try (Connection c = DriverManager.getConnection(url + (url.contains("?") ? "&" : "?") + "ApplicationName=" + app, user, password);
           Connection observer = DriverManager.getConnection(url, user, password)) {
         c.setAutoCommit(false);
         c.commit();
         String state = "select state from pg_stat_activity where application_name = '" + app + "'";

         c.getTransactionIsolation();
         System.out.println("after getTransactionIsolation(): " + scalar(observer, state));
         c.getSchema();
         System.out.println("after getSchema():               " + scalar(observer, state));
         try {
            c.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
            System.out.println("setTransactionIsolation(): returned");
         }
         catch (SQLException e) {
            System.out.println("setTransactionIsolation(): SQLSTATE " + e.getSQLState() + ": " + e.getMessage());
         }
         c.rollback();
         System.out.println("after rollback():                " + scalar(observer, state));
      }
   }

   static String scalar(Connection c, String sql) throws SQLException {
      try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery(sql)) {
         return rs.next() ? rs.getString(1) : null;
      }
   }
}
