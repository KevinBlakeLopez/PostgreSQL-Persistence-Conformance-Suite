# Draft: HikariCP issue — a connection whose cleanup failed goes back to the pool

**Status: DRAFT, revision 2 (2026-10-25). Not filed.** Production relevance (2026-10-26): [`unfiled findings`, HikariCP F-H2](../../unfiled-findings-production-relevance/README.md). Likelihood: low. Frequency is not established. Filing needs the maintainer of this repository to approve the exact text below (`AGENTS.md` rule 9). Venue: a new issue on `brettwooldridge/HikariCP`. The repository has no CONTRIBUTING file, issue template or AI policy (checked 2026-10-24); its README asks for pull requests against `dev`.

**Revision 2, after a review on 2026-10-25:**

- The body leads with the default-configuration read-only reproduction, run on five versions.
- It states the pool defect separately from its pgjdbc trigger.
- It proposes a completion-flag fix. Revision 1's change in the `catch` missed unchecked exceptions, which a second test shows.
- It states the suite result for HikariCP's default test selection.

Revision 1 is in git history.

**Before filing, re-check:** `dev` still has `ProxyConnection.close()` as quoted (it was identical to 7.1.0 at `a4d93f4f8`, 2026-06-14); no newer HikariCP or pgjdbc release changes the behaviour; the duplicate searches in [`../README.md`](../README.md#15-upstream-duplicate-searches) §15 still find nothing new.

**Evidence behind every sentence:** [`../README.md`](../README.md) §8 and §18, and the outputs they cite.

---

## Title

`close()` returns a connection to the pool when its rollback or state reset failed

## Body

**Versions:** HikariCP 7.1.0 (`dev` at `a4d93f4f8` has the same `ProxyConnection`). The reproduction below gives the same output on 4.0.3, 5.1.0, 6.3.3 and 7.0.2. pgjdbc 42.7.14, PostgreSQL 18.6, Java 21.

In `ProxyConnection.close()`, when `delegate.rollback()`, `resetConnectionState()` or `clearWarnings()` throws, the exception reaches the caller, but the `finally` block still calls `poolEntry.recycle()`. Unless `checkException()` evicted the entry, which it does only for disconnection-type `SQLException`s, the connection goes back to the bag with its cleanup incomplete, and the next borrower gets it. This does not depend on PostgreSQL or pgjdbc: the first regression test below shows it with HikariCP's own `StubConnection`.

In #1009 you said you would expect the reset calls not to fail in a way that avoids eviction, and asked for a concrete example. pgjdbc gives one, with standard JDBC calls only:

- In non-autocommit mode, pgjdbc's `getSchema()` runs `select current_schema()`, which begins a transaction. So do `setSchema()` and `setSavepoint()`. `ProxyConnection` does not count these as dirty commit state, so `close()` skips its rollback.
- `resetConnectionState()` then calls pgjdbc's `setReadOnly()` or `setTransactionIsolation()`. Both throw SQLSTATE `25001`, because a transaction is open.

**With the pool's default settings,** a read-only report (`setReadOnly(true)`, `setAutoCommit(false)`, a query, `commit()`, then `getSchema()` for a log line) leaves the pool's only connection with autocommit off and read-only on. Each of the next three borrowers' inserts failed, and HikariCP's alive check passed before each borrow:

<details><summary>Reproduction (one file, pool of one, HikariCP defaults) and output</summary>

```java
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
```

Run with `PGURL=jdbc:postgresql://… PGUSER=… PGPASSWORD=… java -cp HikariCP-7.1.0.jar:postgresql-42.7.14.jar:slf4j-api-2.0.17.jar MinimalReproReadOnly.java`. Output, 3 of 3 runs, identical on HikariCP 4.0.3, 5.1.0, 6.3.3, 7.0.2 and 7.1.0:

```
A: close() threw SQLSTATE 25001: Cannot change transaction read-only property in the middle of a transaction.
pooled backend after A's close(): idle in transaction
B: autoCommit=false readOnly=true (pool defaults: true, false); insert: SQLSTATE 25006
C: autoCommit=false readOnly=true (pool defaults: true, false); insert: SQLSTATE 25P02
D: autoCommit=false readOnly=true (pool defaults: true, false); insert: SQLSTATE 25P02
rows in hikari_ro_probe (three inserts attempted): 0
```
</details>

The PostgreSQL statement log shows each borrower's validation query running inside the transaction that A's `getSchema()` began, followed by its failed insert.

Two more consequences of the same path:

- **The next borrower runs inside A's SERIALIZABLE transaction and reads A's snapshot.** This is with `autoCommit=false` and `transactionIsolation=TRANSACTION_READ_COMMITTED` configured, after A sets SERIALIZABLE and calls `getSchema()`. A second single-file reproduction, which I can post, gives the same output on all five versions.
- **The next borrower's committed unqualified insert lands in `tenant_a`.** This is with `schema=public` configured, when A has also set SERIALIZABLE and its last call is `setSchema("tenant_a")`: the isolation reset fails, so the schema reset never runs (7.1.0).

**Suggested fix:** mark the entry evicted unless the cleanup completed. `recycle()` then closes it instead of returning it.

<details><summary>The change and two regression tests in <code>ConnectionStateTest</code></summary>

```diff
diff --git a/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java b/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
index dbf3f33..59ece89 100644
--- a/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
+++ b/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java
@@ -245,6 +245,7 @@ public abstract class ProxyConnection implements Connection
       if (delegate != ClosedConnection.CLOSED_CONNECTION) {
          leakTask.cancel();
 
+         var isStateReset = false;
          try {
             if (isCommitStateDirty && !isAutoCommit) {
                delegate.rollback();
@@ -256,6 +257,7 @@ public abstract class ProxyConnection implements Connection
             }
 
             delegate.clearWarnings();
+            isStateReset = true;
          }
          catch (SQLException e) {
             // when connections are aborted, exceptions are often thrown that should not reach the application
@@ -264,6 +266,11 @@ public abstract class ProxyConnection implements Connection
             }
          }
          finally {
+            if (!isStateReset) {
+               // The rollback or the state reset did not complete, so the connection's state is unknown: close it
+               // instead of returning it to the pool.
+               poolEntry.markEvicted();
+            }
             delegate = ClosedConnection.CLOSED_CONNECTION;
             poolEntry.recycle();
          }
diff --git a/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java b/src/test/java/com/zaxxer/hikari/pool/ConnectionStateTest.java
index b2da043..7cf2f3f 100644
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
@@ -32,6 +34,8 @@ import org.junit.Test;
 
 import com.zaxxer.hikari.HikariConfig;
 import com.zaxxer.hikari.HikariDataSource;
+import com.zaxxer.hikari.mocks.StubConnection;
+import com.zaxxer.hikari.mocks.StubDataSource;
 import com.zaxxer.hikari.util.UtilityElf;
 
 public class ConnectionStateTest
@@ -170,4 +174,92 @@ public class ConnectionStateTest
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
+
+   @Test
+   public void testConnectionIsNotReusedWhenStateResetThrowsUncheckedException() throws SQLException
+   {
+      final class ResetFailingConnection extends StubConnection
+      {
+         volatile boolean failIsolationReset;
+
+         @Override
+         public void setTransactionIsolation(int level) throws SQLException
+         {
+            if (failIsolationReset) {
+               throw new IllegalStateException("isolation reset failed");
+            }
+            super.setTransactionIsolation(level);
+         }
+      }
+
+      HikariConfig config = newHikariConfig();
+      config.setTransactionIsolation("TRANSACTION_READ_COMMITTED");
+      config.setMinimumIdle(1);
+      config.setMaximumPoolSize(1);
+      config.setConnectionTestQuery("VALUES 1");
+      config.setDataSource(new StubDataSource() {
+         @Override
+         public Connection getConnection()
+         {
+            return new ResetFailingConnection();
+         }
+      });
+
+      try (HikariDataSource ds = new HikariDataSource(config)) {
+         ResetFailingConnection first;
+         try (Connection connection = ds.getConnection()) {
+            first = connection.unwrap(ResetFailingConnection.class);
+            connection.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
+            first.failIsolationReset = true;
+            try {
+               connection.close();
+               fail("close() should report the failed reset");
+            }
+            catch (IllegalStateException e) {
+               // pass
+            }
+            first.failIsolationReset = false;
+         }
+
+         try (Connection connection = ds.getConnection()) {
+            assertNotSame("a connection whose state reset failed was handed out again", first, connection.unwrap(ResetFailingConnection.class));
+            assertEquals(Connection.TRANSACTION_READ_COMMITTED, connection.getTransactionIsolation());
+         }
+      }
+   }
 }
```

On 7.1.0 both tests fail. With the change both pass. With `markEvicted()` added only inside the existing `catch (SQLException e)`, the second test still fails: an unchecked exception from the driver skips that `catch` and reaches `recycle()`. With HikariCP's default test selection, excluding only `PostgresTest` (it needs Docker), 192 tests ran. On 7.1.0 the two new tests failed; with the change none did. Two tests in `TomcatConcurrentBagLeakTest` were skipped in both runs.
</details>

`close()` still throws, so the application is still told. On 7.1.0 as released, an `SQLExceptionOverride` that returns `MUST_EVICT` for SQLSTATE `25001` already makes `close()` evict the connection in the read-only case above: the next borrower got a fresh connection.

Separate from this fix: counting `getSchema()`, `setSchema()` and `setSavepoint()` as dirty commit state, as #866 did for `getMetaData()`, would remove this trigger, but not the recycling. Related but different: #2144 and pgjdbc/pgjdbc#3005. I can send the change as a pull request against `dev`.
