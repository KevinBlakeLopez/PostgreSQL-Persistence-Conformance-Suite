"""Direct psycopg check. Uses DATABASE_URL and a throwaway database.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python psycopg_commit_tag.py

Does not print the password. Does not trace libpq. The command tag is read from
cursor.execute("COMMIT") on a second connection, not from Connection.commit().
"""

import os

import psycopg
from psycopg.pq import ExecStatus, TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "ppcs_repro_psycopg_tag"


def connect(dbname, autocommit):
    return psycopg.connect(URL, dbname=dbname, autocommit=autocommit)


def status_name(conn):
    return TransactionStatus(conn.info.transaction_status).name


def names(rows):
    return [row[0] for row in rows]


def setup(conn):
    conn.execute("create table item (id serial primary key, name text not null)")
    conn.execute("create table uniq (id serial primary key, code text not null unique)")
    conn.execute("insert into uniq (code) values ('taken')")


def abort_with_unique(conn):
    conn.execute("insert into item (name) values ('kept')")
    try:
        conn.execute("insert into uniq (code) values ('taken')")
    except psycopg.errors.UniqueViolation as exc:
        return exc.sqlstate
    return None


def main():
    admin = connect("postgres", True)
    print(f"psycopg {psycopg.__version__}")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    admin.close()

    with connect(NAME, True) as setup_conn:
        setup(setup_conn)

    control = connect(NAME, False)
    control.execute("insert into item (name) values ('seen')")
    print("normal commit() control")
    print(f"  commit() returned {control.commit()!r}")
    control.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")
        probe.execute("delete from item")

    subject = connect(NAME, False)
    caught = abort_with_unique(subject)
    print("commit() after caught 23505")
    print(f"  caught {caught}")
    print(f"  transaction_status before commit() {status_name(subject)}")
    print(f"  commit() returned {subject.commit()!r}")
    print(f"  transaction_status after commit() {status_name(subject)}")
    subject.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")
        probe.execute("delete from item")

    other = connect(NAME, False)
    caught = abort_with_unique(other)
    print("cursor.execute('COMMIT') on a second connection, not commit()")
    print(f"  caught {caught}")
    print(f"  transaction_status before execute {status_name(other)}")
    cur = other.cursor()
    cur.execute("COMMIT")
    result = cur.pgresult
    print(f"  statusmessage {cur.statusmessage!r}")
    print(f"  pgresult.status {ExecStatus(result.status).name}")
    print(f"  pgresult.command_status {result.command_status.decode()!r}")
    other.close()
    with connect(NAME, True) as probe:
        visible = names(probe.execute("select name from item order by name").fetchall())
        print(f"  visible from another connection {visible}")

    admin = connect("postgres", True)
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
