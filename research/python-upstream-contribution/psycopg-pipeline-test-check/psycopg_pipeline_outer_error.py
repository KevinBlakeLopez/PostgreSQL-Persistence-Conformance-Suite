"""Replicates psycopg's tests/test_pipeline.py::test_outer_transaction_error (master 99356800e).

    DATABASE_URL=postgresql://postgres:...@127.0.0.1:<port>/postgres python -I psycopg_pipeline_outer_error.py

The test's body, with pytest.raises replaced by try/except on the same exception tuple:

    with conn.transaction():
        with pytest.raises((e.UndefinedColumn, e.OperationalError)):
            with conn.pipeline():
                conn.execute("select error")
                conn.execute("create table voila ()")

Question: when that outer block exits normally, is the transaction already aborted, so that
the block's COMMIT is answered with ROLLBACK? Arm "exact" runs the body as written (a
non-autocommit connection, like the test's `conn` fixture). Arm "witnessed" adds a marker
insert and pg_current_xact_id() before the pipeline, and reads the outcome from a separate
connection. Creates database chk_pipeline_outer, drops it at the end.
"""

import os
import sys

import psycopg
from psycopg import errors as e
from psycopg.pq import TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "chk_pipeline_outer"


def tstatus(conn):
    return TransactionStatus(conn.info.transaction_status).name


def arm(witnessed, rep):
    conn = psycopg.connect(URL, dbname=NAME, application_name=f"chk-pipe-{'w' if witnessed else 'x'}{rep}")
    pid = conn.info.backend_pid
    caught = raised = xid = before = None
    marker = f"m{rep}"
    try:
        with conn.transaction() as tx:
            if witnessed:
                conn.execute("insert into item (name) values (%s)", (marker,))
                xid = conn.execute("select pg_current_xact_id()::text").fetchone()[0]
            try:
                with conn.pipeline():
                    conn.execute("select error")
                    conn.execute("create table voila ()")
            except (e.UndefinedColumn, e.OperationalError) as exc:
                caught = type(exc).__name__
            before = tstatus(conn)
    except Exception as exc:
        raised = f"{type(exc).__name__}: {exc}"
    out = {
        "caught inside the block": caught,
        "driver status before block exit": before,
        "block raised on exit": raised,
        "Transaction.status": tx.status.value,
        "driver status after block exit": tstatus(conn),
    }
    with psycopg.connect(URL, dbname=NAME, autocommit=True) as w:
        if witnessed:
            out["pg_xact_status"] = w.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0]
            out["marker visible"] = bool(w.execute("select count(*) from item where name = %s", (marker,)).fetchone()[0])
        out["backend state, last statement"] = w.execute(
            "select state, query from pg_stat_activity where pid = %s", (pid,)).fetchone()
    conn.close()
    return out


def main():
    admin = psycopg.connect(URL, autocommit=True)
    print(f"python {sys.version.split()[0]}, psycopg {psycopg.__version__} ({psycopg.pq.__impl__}, libpq {psycopg.pq.version()})")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    with psycopg.connect(URL, dbname=NAME, autocommit=True) as setup:
        setup.execute("create table item (id serial primary key, name text not null)")
    for witnessed in (False, True):
        for rep in (1, 2, 3):
            print(f"{'witnessed' if witnessed else 'exact'} rep {rep}")
            for k, v in arm(witnessed, rep).items():
                print(f"  {k}: {v}")
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
