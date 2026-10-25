# Draft: comment on pgjdbc/pgjdbc#3005 — `getSchema()` begins a transaction too

**Status: DRAFT. Not posted.** Posting needs the maintainer of this repository to approve the exact text below (`AGENTS.md` rule 9). Venue: a regular comment on https://github.com/pgjdbc/pgjdbc/issues/3005 (open; "Connection.setSchema starts a new transaction when autoCommit=false"). In that thread a maintainer proposed on 2023-11-22 to "skip creating transactions for `setSchema` calls"; another called it a breaking change they were OK with. 42.7.14 and `master` at `874745258` (2026-10-08) still run both methods as ordinary statements.

**Before posting, re-check:** #3005 is still open and has no newer comment covering `getSchema()`; `master` still implements `getSchema()` with `createStatement().executeQuery("select current_schema()")`.

**Evidence:** [`../README.md`](../README.md) §8, and `output/hikari-minimal/pgjdbc-getschema.rep{1,2,3}.out` (byte-identical).

---

`getSchema()` has the same effect: in non-autocommit mode it runs `select current_schema()` through an ordinary statement, so it begins a transaction (42.7.14, and `master` at 874745258). `getTransactionIsolation()` avoids this ("nb: no BEGIN triggered"). If the `setSchema()` change goes ahead, could `getSchema()` get the same treatment?

It matters for pools: HikariCP does not count either call as starting a transaction, so a connection can reach `close()` with one open, and HikariCP's later `setTransactionIsolation()`/`setReadOnly()` reset then fails with `25001`. Details: [HikariCP issue link, to be added when filed].

<details><summary>pgjdbc-only reproduction</summary>

```java
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
```

Output, 3 of 3 runs (PostgreSQL 18.6, Java 21):

```
after getTransactionIsolation(): idle
after getSchema():               idle in transaction
setTransactionIsolation(): SQLSTATE 25001: Cannot change transaction isolation level in the middle of a transaction.
after rollback():                idle
```
</details>
