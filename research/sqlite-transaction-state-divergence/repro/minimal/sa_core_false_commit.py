"""engine.begin() returns normally after SQLite rolled the transaction back.

Default engine (no recipe). The application debits an account, then tries a
second insert that violates a UNIQUE ... ON CONFLICT ROLLBACK constraint
(declared through SQLAlchemy's sqlite_on_conflict_unique), and skips the
duplicate, as SQLite's default ABORT behaviour allows. SQLite has already
rolled the whole transaction back. A later write starts a new transaction.

    python sa_core_false_commit.py
"""

import os
import sqlite3
import tempfile

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, update
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
account = Table("account", metadata, Column("id", Integer, primary_key=True), Column("balance", Integer))
transfer = Table("transfer", metadata, Column("id", Integer, primary_key=True),
                 Column("ref", String, unique=True, sqlite_on_conflict_unique="ROLLBACK"))
audit = Table("audit", metadata, Column("id", Integer, primary_key=True), Column("note", String))

path = os.path.join(tempfile.mkdtemp(), "demo.db")
engine = create_engine(f"sqlite:///{path}")
metadata.create_all(engine)
with engine.begin() as conn:
    conn.execute(insert(account).values(id=1, balance=100))
    conn.execute(insert(transfer).values(ref="t-1"))

with engine.begin() as conn:
    conn.execute(update(account).where(account.c.id == 1).values(balance=account.c.balance - 30))
    try:
        conn.execute(insert(transfer).values(ref="t-1"))  # a duplicate reference
    except IntegrityError:
        print("duplicate transfer reference skipped")
    print("SQLAlchemy in_transaction():", conn.in_transaction(),
          "| sqlite3 in_transaction:", conn.connection.driver_connection.in_transaction)
    conn.execute(insert(audit).values(note="debited 30"))
print("engine.begin() block committed without error")
engine.dispose()

check = sqlite3.connect(path)
print("balance:", check.execute("SELECT balance FROM account WHERE id = 1").fetchone()[0])
print("audit:", [row[0] for row in check.execute("SELECT note FROM audit")])
check.close()
