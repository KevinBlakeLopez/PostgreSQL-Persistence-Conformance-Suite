"""CHK-only, review item 6: the same pooled connection after a failed COMMIT.

    PY8_TORTOISE_SRC=<checkout> PY8_SRC_LABEL=<label> \
    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python chk_connection_reuse.py [asyncpg|psycopg]

PY8_TORTOISE_SRC, when set, is put first on sys.path, so Tortoise is imported from that
checkout. The program drops any database named py8_connection_reuse, creates it, and drops
it at the end. Tortoise uses a pool of one connection (minsize=1, maxsize=1), so every block
gets the same physical connection unless the pool replaces it. Its sessions use
application_name py8-reuse-<label>-<backend>, followed by -r<PY8_REP> when PY8_REP is set.

Instruments, which observe and change nothing:
- the pool's release() is wrapped to record, at the moment Tortoise hands a connection back
  and before the pool's own reset: the backend PID, the driver connection object, and the
  driver's transaction state. For asyncpg: is_in_transaction(), and whether a Transaction
  is still attached (_top_xact). For psycopg: info.transaction_status, and the number of
  open Transaction contexts (_num_transactions);
- the transaction wrapper's rollback() is wrapped to count Tortoise's calls to it;
- Python log records of WARNING and above are printed.

Steps:
1. a block that writes and commits: the baseline identity;
2. a block whose COMMIT fails on a deferred foreign key;
3. pg_stat_activity for that backend, read by a separate connection;
4. an independent block that writes and commits;
5. a plain query outside any block.
"""

import asyncio
import logging
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("PY8_TORTOISE_SRC"):
    sys.path.insert(0, os.environ["PY8_TORTOISE_SRC"])

import psycopg  # noqa: E402
from tortoise import Tortoise, connections, fields  # noqa: E402
from tortoise.models import Model  # noqa: E402
from tortoise.transactions import in_transaction  # noqa: E402

import candidates  # noqa: E402
from tortoise_commit_translation import describe  # noqa: E402

NAME = "py8_connection_reuse"
DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "INSERT INTO parent VALUES (1)",
    "CREATE TABLE reuse_item (id SERIAL PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED)",
]


class ReuseItem(Model):
    id = fields.IntField(primary_key=True)
    parent_id = fields.IntField()

    class Meta:
        table = "reuse_item"


class Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(f"{record.levelname} {record.name}: {re.sub(r'0x[0-9a-f]+', '0x…', record.getMessage())}")


class Observer:
    def __init__(self, backend):
        self.backend = backend
        self.releases = []
        self.rollbacks = 0
        self.first = None  # (pid, id(driver connection)) of step 1

    def driver_state(self, connection):
        if self.backend == "asyncpg":
            con = getattr(connection, "_con", connection)  # asyncpg's pool hands out a proxy
            return con.get_server_pid(), id(con), (
                f"is_in_transaction()={con.is_in_transaction()}, Transaction attached={con._top_xact is not None}"
            )
        return connection.info.backend_pid, id(connection), (
            f"transaction_status={connection.info.transaction_status.name}, "
            f"open Transaction contexts={connection._num_transactions}"
        )

    def identity(self, pid, obj):
        if self.first is None:
            return "the baseline"
        return f"same backend PID as step 1: {pid == self.first[0]}; same driver connection object: {obj == self.first[1]}"

    def install(self, client, wrapper_cls):
        pool = client._pool
        observer = self
        if self.backend == "asyncpg":
            # asyncpg's Pool defines __slots__, so release() is wrapped on the class
            pool_cls = type(pool)
            original_cls_release = pool_cls.release

            async def cls_release(pool_self, connection, *args, **kwargs):
                observer.releases.append(observer.driver_state(connection))
                return await original_cls_release(pool_self, connection, *args, **kwargs)

            pool_cls.release = cls_release
        else:
            original = pool.release

            async def release(connection, *args, **kwargs):
                observer.releases.append(observer.driver_state(connection))
                return await original(connection, *args, **kwargs)

            pool.release = release
        original_rollback = wrapper_cls.rollback

        async def rollback(self, *args):
            observer.rollbacks += 1
            return await original_rollback(self, *args)

        wrapper_cls.rollback = rollback

    def report(self):
        for pid, obj, state in self.releases:
            print(f"  released to the pool: {self.identity(pid, obj)}; {state}")
        self.releases.clear()


async def inside(conn, sql, key):
    return (await conn.execute_query_dict(sql))[0][key]


async def run(backend):
    label = os.environ.get("PY8_SRC_LABEL", "installed")
    print(f"tortoise from: {label}; {candidates.source_digest(backend)} is the wrapper's source digest")
    handler = Records()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.WARNING)

    url = os.environ["DATABASE_URL"]
    admin = await psycopg.AsyncConnection.connect(url, autocommit=True, application_name="py8-admin")
    await admin.execute(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {NAME}")
    witness = await psycopg.AsyncConnection.connect(
        url, dbname=NAME, autocommit=True, application_name="py8-witness"
    )
    for statement in DDL:
        await witness.execute(statement)

    rep = os.environ.get("PY8_REP")
    app = f"py8-reuse-{label}-{backend}" + (f"-r{rep}" if rep else "")
    parts = urlsplit(url)
    db_url = urlunsplit(
        (backend, parts.netloc, f"/{NAME}", f"application_name={app}&minsize=1&maxsize=1", "")
    )
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})
    client = connections.get("default")
    await client.execute_query("SELECT 1")  # creates the pool
    wrapper_cls, _ = candidates._wrapper_class(backend)
    observer = Observer(backend)
    observer.install(client, wrapper_cls)

    async def fate(xid):
        return (await (await witness.execute("SELECT pg_xact_status(%s::xid8)", (xid,))).fetchone())[0]

    try:
        print("1. a block that writes and commits")
        async with in_transaction() as conn:
            pid1 = await inside(conn, "SELECT pg_backend_pid() AS v", "v")
            xid1 = await inside(conn, "SELECT pg_current_xact_id()::text AS v", "v")
            await ReuseItem.create(parent_id=1, using_db=conn)
        observer.first = observer.releases[0][:2]
        observer.report()
        print(f"  pg_xact_status: {await fate(xid1)}")

        print("2. a block whose COMMIT fails on the deferred foreign key")
        try:
            async with in_transaction() as conn:
                pid2 = await inside(conn, "SELECT pg_backend_pid() AS v", "v")
                xid2 = await inside(conn, "SELECT pg_current_xact_id()::text AS v", "v")
                await ReuseItem.create(parent_id=999, using_db=conn)
            print("  the block exited normally")
        except Exception as exc:  # noqa: BLE001
            describe(exc)
        observer.report()
        print(f"  Tortoise's rollback() calls during the block: {observer.rollbacks}")
        print(f"  pg_xact_status: {await fate(xid2)}")
        print(f"  same backend PID as step 1, read inside the block: {pid2 == pid1}")

        print("3. pg_stat_activity for that backend, read by a separate connection")
        row = await (
            await witness.execute(
                "SELECT state, xact_start IS NULL, backend_xid IS NULL FROM pg_stat_activity WHERE pid = %s",
                (pid2,),
            )
        ).fetchone()
        print(f"  state={row[0]!r}, no transaction start={row[1]}, no transaction ID={row[2]}")

        print("4. an independent block that writes and commits")
        async with in_transaction() as conn:
            pid4 = await inside(conn, "SELECT pg_backend_pid() AS v", "v")
            xid4 = await inside(conn, "SELECT pg_current_xact_id()::text AS v", "v")
            item = await ReuseItem.create(parent_id=1, using_db=conn)
        observer.report()
        print(f"  same backend PID as step 1, read inside the block: {pid4 == pid1}")
        print(f"  pg_xact_status: {await fate(xid4)}")
        visible = await (await witness.execute("SELECT count(*) FROM reuse_item WHERE id = %s", (item.id,))).fetchone()
        print(f"  its row is visible to the separate connection: {visible[0] == 1}")

        print("5. a plain query outside any block")
        pid5 = (await client.execute_query_dict("SELECT pg_backend_pid() AS v"))[0]["v"]
        observer.report()
        print(f"  same backend PID as step 1: {pid5 == pid1}")
        print(f"  Tortoise's rollback() calls in all: {observer.rollbacks}")
        print(f"  log records: {len(handler.lines)}")
        for line in handler.lines:
            print(f"    {line}")
    finally:
        await Tortoise.close_connections()
        await witness.close()
        await admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
        await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg"):
        sys.exit("usage: chk_connection_reuse.py [asyncpg|psycopg]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
