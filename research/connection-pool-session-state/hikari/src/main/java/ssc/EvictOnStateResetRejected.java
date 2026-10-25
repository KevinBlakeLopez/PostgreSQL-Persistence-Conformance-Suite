package ssc;

import com.zaxxer.hikari.SQLExceptionOverride;

import java.sql.SQLException;

/**
 * A configuration-only mitigation for F-H2 on unmodified HikariCP: evict the connection when pgjdbc rejects a state
 * change because a transaction is open (SQLSTATE 25001, "Cannot change ... in the middle of a transaction").
 * HikariCP consults the override in checkException(), which close() calls when the reset throws.
 *
 * It also applies to the same SQLSTATE raised by any other JDBC call on the connection, which then evicts too.
 */
public final class EvictOnStateResetRejected implements SQLExceptionOverride {
   @java.lang.Override   // the nested SQLExceptionOverride.Override enum shadows the annotation's simple name
   public Override adjudicate(final SQLException e) {
      return "25001".equals(e.getSQLState()) ? Override.MUST_EVICT : Override.CONTINUE_EVICT;
   }
}
