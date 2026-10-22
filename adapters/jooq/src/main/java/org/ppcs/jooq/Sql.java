package org.ppcs.jooq;

import static org.jooq.impl.DSL.field;
import static org.jooq.impl.DSL.name;
import static org.jooq.impl.DSL.table;

import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.Record;
import org.jooq.Table;

/**
 * Writes and reads against the runner's fixture tables. No generated catalog:
 * the tables are created per case, so this uses the DSL's plain-name API.
 */
final class Sql {
    static final Table<?> ITEM = table(name("item"));
    static final Table<?> UNIQ = table(name("uniq"));
    static final Field<String> ITEM_NAME = field(name("name"), String.class);
    static final Field<Integer> ITEM_QTY = field(name("qty"), Integer.class);
    static final Field<String> UNIQ_CODE = field(name("code"), String.class);

    private static final Field<Integer> PID = field("pg_backend_pid()", Integer.class);
    private static final Field<String> XID = field("pg_current_xact_id()::text", String.class);
    private static final Field<String> ISOLATION = field("current_setting('transaction_isolation')", String.class);

    private Sql() {}

    static void insertItem(DSLContext dsl, String marker) {
        int rows = dsl.insertInto(ITEM).columns(ITEM_NAME, ITEM_QTY).values(marker, 0).execute();
        if (rows != 1) throw new IllegalStateException("insert into item wrote " + rows + " rows");
    }

    static void insertTaken(DSLContext dsl) {
        dsl.insertInto(UNIQ).columns(UNIQ_CODE).values("taken").execute();
    }

    static void readItem(DSLContext dsl, String marker) {
        int rows = dsl.select(ITEM_NAME).from(ITEM).where(ITEM_NAME.eq(marker)).fetch().size();
        if (rows != 1) throw new IllegalStateException("reading " + marker + " returned " + rows + " rows");
    }

    /** One statement. {@code isolation} is null when the caller did not ask for it. */
    static Ident identify(DSLContext dsl, boolean isolation) {
        Record record = dsl.select(PID, XID, ISOLATION).fetchOne();
        if (record == null) throw new IllegalStateException("the identity query returned no row");
        Integer pid = record.get(PID);
        String xid = record.get(XID);
        if (pid == null || xid == null) throw new IllegalStateException("the identity query returned a null id");
        return new Ident(xid, pid, isolation ? record.get(ISOLATION) : null);
    }

    record Ident(String xid, int pid, String isolation) {}
}
