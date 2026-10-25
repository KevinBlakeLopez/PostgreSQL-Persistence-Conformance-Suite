# Draft: HikariCP issue — a connection whose state reset failed goes back to the pool

**Status: DRAFT. Not filed.** Filing needs the maintainer of this repository to approve the exact text below (`AGENTS.md` rule 9). Venue: a new issue on `brettwooldridge/HikariCP`. The repository has no CONTRIBUTING file, issue template or AI policy (checked 2026-10-24); its README asks for pull requests against `dev`.

**Before filing, re-check:** `dev` still has `ProxyConnection.close()` as quoted (it was identical to 7.1.0 at `a4d93f4f8`, 2026-06-14); no newer HikariCP or pgjdbc release changes the behaviour; the duplicate searches in [`../README.md`](../README.md#15-upstream-duplicate-searches) §15 still find nothing new.

**Evidence behind every sentence:** [`../README.md`](../README.md) §8 (F-H2) and the outputs it cites.

---

## Title

`close()` returns the connection to the pool when `resetConnectionState()` fails, so the next borrower gets the unreset state

## Body

**Versions:** HikariCP 7.1.0 (`dev` at `a4d93f4f8` has the same `ProxyConnection` and `PoolBase`); the reproduction below gives the same output on 4.0.3, 5.1.0, 6.3.3 and 7.0.2. pgjdbc 42.7.14, PostgreSQL 18.6, Java 21.

In `ProxyConnection.close()`, when `delegate.rollback()` or `resetConnectionState()` throws an `SQLException` whose SQLState `checkException()` does not treat as a disconnection, the exception is rethrown to the caller, but the `finally` block still calls `poolEntry.recycle()`. The partially reset connection goes back to the bag and is handed to the next borrower.

In #1009 you wrote that you would expect the calls in `resetConnectionState()` not to fail in a way that avoids eviction, and asked for a concrete example. Here is one with pgjdbc:

- pgjdbc's `setTransactionIsolation()` and `setReadOnly()` throw SQLSTATE `25001` ("Cannot change … in the middle of a transaction") whenever a transaction is open.
- A transaction can be open at `close()` while `isCommitStateDirty` is false: in non-autocommit mode, pgjdbc's `getSchema()`, `setSchema()` and `setSavepoint()` run SQL that begins a transaction, and `ProxyConnection` does not mark the commit state dirty for them (as it now does for `getMetaData()`, after #866).

So `close()` does not roll back, the isolation or read-only reset throws `25001`, and the connection is recycled with the transaction still open and the remaining resets skipped.

<details><summary>Reproduction: one file, pool of one, autoCommit=false, transactionIsolation=TRANSACTION_READ_COMMITTED</summary>

```java
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
```

Run with `PGURL=jdbc:postgresql://… PGUSER=… PGPASSWORD=… java -cp HikariCP-7.1.0.jar:postgresql-42.7.14.jar:slf4j-api-2.0.17.jar MinimalRepro.java`. Output, 3 of 3 runs:

```
A: close() threw SQLSTATE 25001: Cannot change transaction isolation level in the middle of a transaction.
pooled backend after A's close(): idle in transaction
B: transaction_isolation = serializable (pool configured READ COMMITTED)
B: hikari_reset_probe.v = 0 (committed value is 1)
```
</details>

B runs inside A's SERIALIZABLE transaction and reads A's snapshot. The PostgreSQL statement log shows B's statements in the same virtual transaction as A's `select current_schema()`, and no `SET SESSION CHARACTERISTICS … READ COMMITTED` is ever sent. A later borrower C still gets SERIALIZABLE, because the session default was never reset.

Two more consequences from the same mechanism, also 3 of 3:

- With `schema=public` configured and `setSchema("tenant_a")` as A's last call, B's committed unqualified insert lands in `tenant_a`.
- With the pool's defaults (autoCommit=true, readOnly=false), a read-only report (`setReadOnly(true)`, `setAutoCommit(false)`, query, `commit()`, then `getSchema()` for a log line) leaves the connection with autocommit off and read-only on. Each of the next three borrowers got it that way, and their inserts failed, first with `25006`, then with `25P02`. HikariCP's alive check ran before each borrow and passed: pgjdbc's `isValid()` treats `25P02` as alive. I did not test how long it lasts.

**Suggested fix:** when the rollback or the reset throws, mark the entry evicted, so `recycle()` closes it instead of returning it:

<details><summary>The change (one line in <code>close()</code>) and a regression test in <code>ConnectionStateTest</code></summary>

```diff
diff --git a/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java b/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
index dbf3f33..7e8b345 100644
--- a/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
+++ b/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
@@ -260,6 +260,9 @@ public abstract class ProxyConnection implements Connection
          catch (SQLException e) {
             // when connections are aborted, exceptions are often thrown that should not reach the application
             if (!poolEntry.isMarkedEvicted()) {
+               // The rollback or the state reset did not complete, so the connection's state is unknown: close it
+               // instead of returning it to the pool.
+               poolEntry.markEvicted();
                throw checkException(e);
             }
          }
diff --git a/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java b/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java
index b2da043..2853feb 100644
--- a/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java
+++ b/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java
@@ -22,6 +22,8 @@ import static org.junit.Assert.assertEquals;
 import static org.junit.Assert.assertSame;
 import static org.junit.Assert.assertTrue;
 import static org.junit.Assert.assertFalse;
+import static org.junit.Assert.assertNotSame;
+import static org.junit.Assert.fail;
 
 import java.sql.Connection;
 import java.sql.ResultSet;
@@ -32,6 +34,7 @@ import org.junit.Test;
 
 import com.zaxxer.hikari.HikariConfig;
 import com.zaxxer.hikari.HikariDataSource;
+import com.zaxxer.hikari.mocks.StubConnection;
 import com.zaxxer.hikari.util.UtilityElf;
 
 public class ConnectionStateTest
@@ -170,4 +173,39 @@ public class ConnectionStateTest
          }
       }
    }
+
+   @Test
+   public void testConnectionIsNotReusedWhenStateResetFails() throws SQLException
+   {
+      try (HikariDataSource ds = newHikariDataSource()) {
+         ds.setTransactionIsolation("TRANSACTION_READ_COMMITTED");
+         ds.setMinimumIdle(1);
+         ds.setMaximumPoolSize(1);
+         ds.setConnectionTestQuery("VALUES 1");
+         ds.setDataSourceClassName("com.zaxxer.hikari.mocks.StubDataSource");
+
+         StubConnection first;
+         try (Connection connection = ds.getConnection()) {
+            first = connection.unwrap(StubConnection.class);
+            connection.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
+
+            // The reset of the isolation level now fails without a disconnection SQLState, as pgjdbc's
+            // setTransactionIsolation() does (SQLSTATE 25001) when a transaction is open.
+            first.throwException = true;
+            try {
+               connection.close();
+               fail("close() should report the failed reset");
+            }
+            catch (SQLException e) {
+               // pass
+            }
+            first.throwException = false;
+         }
+
+         try (Connection connection = ds.getConnection()) {
+            assertNotSame("a connection whose state reset failed was handed out again", first, connection.unwrap(StubConnection.class));
+            assertEquals(Connection.TRANSACTION_READ_COMMITTED, connection.getTransactionIsolation());
+         }
+      }
+   }
 }
```

The new test fails on 7.1.0 ("a connection whose state reset failed was handed out again") and passes with the change. The rest of the suite (`mvn test '-Dtest=!PostgresTest'`, 192 tests) gives the same results with and without the change; the only other failure, `RampUpDown`, fails the same way without the change on my machine.
</details>

`close()` still throws, so the application is still told. On 7.1.0 as released, an `SQLExceptionOverride` that returns `MUST_EVICT` for SQLSTATE `25001` already makes `close()` evict the connection in the read-only case above (I checked; the next borrower gets a fresh connection). Separately, marking the commit state dirty in `getSchema()`, `setSchema()` and `setSavepoint()`, as #866 did for `getMetaData()`, would remove this particular trigger, but not the recycling of a connection whose reset failed. Related but different: #2144 and pgjdbc/pgjdbc#3005 (`setSchema()` begins a transaction, which the pool's own reset then leaves open).
