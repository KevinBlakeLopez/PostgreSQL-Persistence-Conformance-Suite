"""sqlite3 with autocommit=False after SQLite rolls a transaction back by itself.

The docs: autocommit=False means "sqlite3 ensures a transaction is always
open", and commit()/rollback() do nothing "if there is no open transaction".
A UNIQUE ... ON CONFLICT ROLLBACK violation makes SQLite end the transaction.

    python sqlite3_autocommit_false.py
"""

import os
import sqlite3
import tempfile

path = os.path.join(tempfile.mkdtemp(), "demo.db")
con = sqlite3.connect(path, autocommit=False)
con.execute("CREATE TABLE t (x INTEGER UNIQUE ON CONFLICT ROLLBACK)")
con.commit()

con.execute("INSERT INTO t VALUES (1)")
try:
    con.execute("INSERT INTO t VALUES (1)")
except sqlite3.IntegrityError as exc:
    print("IntegrityError:", exc)
print("in_transaction:", con.in_transaction)

for name in ("commit", "rollback"):
    try:
        getattr(con, name)()
        print(f"{name}(): returned")
    except sqlite3.OperationalError as exc:
        print(f"{name}(): OperationalError:", exc)
    print("in_transaction:", con.in_transaction)

con.execute("INSERT INTO t VALUES (2)")  # the next unit of work
try:
    con.rollback()
    print("rollback(): returned")
except sqlite3.OperationalError as exc:
    print("rollback(): OperationalError:", exc)

other = sqlite3.connect(path)
print("committed rows:", [row[0] for row in other.execute("SELECT x FROM t ORDER BY x")])
other.close()
con.close()
