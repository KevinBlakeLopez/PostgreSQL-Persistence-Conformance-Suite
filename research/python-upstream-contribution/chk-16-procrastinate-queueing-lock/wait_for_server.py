"""Waits until the throwaway server accepts connections, then checks that it is the
container run.sh started: its cluster_name must equal the random TOKEN."""

import os
import sys
import time

import psycopg

deadline = time.monotonic() + 90
while True:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as c:
            name = c.execute("show cluster_name").fetchone()[0]
        break
    except psycopg.OperationalError:
        if time.monotonic() > deadline:
            sys.exit("the server did not start within 90 s")
        time.sleep(1)
if name != os.environ["TOKEN"]:
    sys.exit(f"wrong server: cluster_name is {name!r}")
print("server ready; cluster_name token matches")
