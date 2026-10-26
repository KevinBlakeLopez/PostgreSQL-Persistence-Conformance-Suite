# CHK-13 facts for the author (PY-7)

These are facts for a SQLAlchemy Usage Questions discussion, which you write in your own words. Each fact says whether it was observed in CHK-13's runs or comes from source and documentation.

**Environment:** SQLAlchemy 2.1.6 and 2.0.55, Python 3.13.11, SQLite 3.54.1, macOS arm64. Each case ran 3 times, and the per-case records are byte-identical across the two versions.

## The trigger

1. **(Docs.)** In SQLite's default rollback-journal mode, `COMMIT` can fail with `SQLITE_BUSY` while another connection holds a read transaction. The transaction then stays active so that the commit can be retried.
2. **(Observed.)** A reader in a separate process holds `BEGIN` plus a `SELECT`. The writer's `commit()` then raises `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`, with a 0.2 s busy timeout and with `sqlite3`'s default 5 s. Afterwards `dbapi_connection.in_transaction` is still `True`.

## What SQLAlchemy does next, observed

3. **The close.** After the failed commit, a block that exits without `rollback()` closes the connection, and `close()` sends no DBAPI rollback. This holds for:
   - `with engine.connect() as conn: ...; conn.commit()`;
   - `with Session(engine) as session: ...; session.commit()`.

   The pool's `reset` event receives `transaction_was_reset=True` while `in_transaction` is `True`.
4. **The lock.** While the connection sits in the pool, an independent connection can neither read nor write (`database is locked`). This persists after the reader has finished.
5. **The next checkout.** It gets the same DBAPI connection, still inside the old transaction. Its insert and `commit()` succeed, and the failed unit's row is committed with its own row.
6. **Configurations.** Facts 3–5 hold with the default pysqlite setup and with `connect_args={"autocommit": False}`.
7. **The `BEGIN` recipe.** With the recipe from the SQLite dialect documentation, the next checkout fails with `cannot start a transaction within a transaction`. Its error handling then rolls the stranded transaction back.
8. **What's unaffected.**
   - `with engine.begin()` rolls back and leaves the connection clean.
   - An explicit `conn.rollback()` or `session.rollback()` before the block closes does too.
   - In Core, that `rollback()` itself sends no DBAPI rollback. It clears the transaction marker, so the pool's reset-on-return sends one.
9. **Controls.** With no reader, the commit succeeds. In WAL mode the reader does not block `COMMIT`.

## Source, the same path as P5a

10. **The leftover marker.** `RootTransaction._do_commit` leaves `Connection._transaction` set, with `is_active=False`, when `commit()` raises. `close()` then skips the DBAPI rollback and checks the connection in with `transaction_reset=True`. The review in `../python-orm-transactions` cites line numbers for 2.1.5; CHK-7's FACTS.md maps them to 2.1.6.

## Scope to state plainly

11. **What was run.** One-connection pool sequences only. Neither Linux nor a framework integration was run.
12. **PostgreSQL.** The same path there is reproduced only with an injected `commit()` failure (P5a, CHK-7).
