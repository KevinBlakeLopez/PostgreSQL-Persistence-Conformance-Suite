"""Hold a SQLite read transaction in its own process until told to release it.

Usage: python -I reader.py <database path>
Prints READY <row count> once the read transaction holds its SHARED lock,
waits for one line on stdin, rolls back, and prints RELEASED.
"""

import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1], isolation_level=None, timeout=5)
conn.execute("BEGIN")
count = conn.execute("SELECT count(*) FROM item").fetchone()[0]
print(f"READY {count}", flush=True)
sys.stdin.readline()
conn.execute("ROLLBACK")
conn.close()
print("RELEASED", flush=True)
