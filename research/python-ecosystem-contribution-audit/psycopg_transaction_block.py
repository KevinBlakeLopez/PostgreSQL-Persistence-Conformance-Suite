"""psycopg Connection.transaction() after a caught 23505. Diagnostic, not a PPCS case.

    DATABASE_URL=postgresql://postgres:...@127.0.0.1:55479/postgres python psycopg_transaction_block.py

Creates database audit_psycopg_tx, drops it at the end. Prints what the transaction
block reported (exception, Transaction.status, driver status) and what PostgreSQL did
(pg_xact_status of the xid captured inside the block, marker visibility, and the
backend's state and last statement), read from a separate connection.
"""

import os
import sys

import psycopg
from psycopg import errors
from psycopg.pq import TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "audit_psycopg_tx"
REPS = 3


def connect(dbname, autocommit=True):
    return psycopg.connect(URL, dbname=dbname, autocommit=autocommit)


def tstatus(conn):
    return TransactionStatus(conn.info.transaction_status).name


def observe(xid, pid, marker):
    with connect(NAME) as probe:
        fate = probe.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0]
        seen = probe.execute("select count(*) from item where name = %s", (marker,)).fetchone()[0]
        row = probe.execute(
            "select state, query from pg_stat_activity where pid = %s", (pid,)
        ).fetchone()
    return fate, seen, row


def subject(marker, recover_with_savepoint):
    conn = connect(NAME)
    pid = conn.info.backend_pid
    raised = None
    caught = None
    status_before_exit = None
    try:
        with conn.transaction() as tx:
            conn.execute("insert into item (name) values (%s)", (marker,))
            xid = conn.execute("select pg_current_xact_id()::text").fetchone()[0]
            if recover_with_savepoint:
                try:
                    with conn.transaction():
                        conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            else:
                try:
                    conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            status_before_exit = tstatus(conn)
    except Exception as exc:  # what the block raised on exit, if anything
        raised = f"{type(exc).__name__}: {exc}"
    status_after_exit = tstatus(conn)
    fate, seen, row = observe(xid, pid, marker)
    conn.close()
    return {
        "caught": caught,
        "driver status before block exit": status_before_exit,
        "block raised on exit": raised,
        "Transaction.status": tx.status.value,
        "driver status after block exit": status_after_exit,
        "pg_xact_status": fate,
        "marker visible": bool(seen),
        "backend state, last statement": row,
    }


def main():
    admin = connect("postgres")
    print(f"python {sys.version.split()[0]}")
    print(f"psycopg {psycopg.__version__}, impl {psycopg.pq.__impl__}, libpq {psycopg.pq.version()}")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    admin.close()
    with connect(NAME) as setup:
        setup.execute("create table item (id serial primary key, name text not null)")
        setup.execute("create table uniq (id serial primary key, code text not null unique)")
        setup.execute("insert into uniq (code) values ('taken')")

    # Control: a normal transaction block.
    conn = connect(NAME)
    with conn.transaction() as tx:
        conn.execute("insert into item (name) values ('control')")
    print("control: normal block")
    print(f"  Transaction.status {tx.status.value}")
    conn.close()
    with connect(NAME) as probe:
        n = probe.execute("select count(*) from item where name = 'control'").fetchone()[0]
    print(f"  marker visible {bool(n)}")

    for rep in range(1, REPS + 1):
        print(f"repetition {rep}: caught 23505 inside conn.transaction(), block exits normally")
        for key, value in subject(f"caught-{rep}", recover_with_savepoint=False).items():
            print(f"  {key}: {value}")
        print(f"repetition {rep}: savepoint recovery, inner conn.transaction() catches 23505")
        for key, value in subject(f"recovered-{rep}", recover_with_savepoint=True).items():
            print(f"  {key}: {value}")

    admin = connect("postgres")
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
