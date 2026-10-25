"""CHK-only, PY-8 check 2: Tortoise's SQLite backend after a COMMIT that failed.

    python chk_sqlite_failed_commit.py [develop|C1]

The program uses a file in a new temporary directory, and removes the directory at the
end. A deferred foreign key makes the COMMIT that in_transaction() sends at exit fail.
The program then probes, in this order, what the backend's single shared connection does
next:

1. whether that connection is still inside a transaction (sqlite3's in_transaction);
2. a plain Note.create() outside any transaction block;
3. the next in_transaction(), which writes a note;
4. a second in_transaction(), with a 5-second limit;
5. a plain Note.create() again;
6. Tortoise.close_connections();
7. closing the shared aiosqlite connection directly.

After each step, a separate sqlite3 connection, opened on the same file, counts the rows
that are committed. The program also prints the class of connections.get("default"),
which in_transaction() replaces with its transaction wrapper while a block is open, and
the class of the context that in_transaction() would return next.
"""

import asyncio
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tortoise import Tortoise, connections, fields  # noqa: E402
from tortoise.models import Model  # noqa: E402
from tortoise.transactions import in_transaction  # noqa: E402

import candidates  # noqa: E402
from tortoise_commit_translation import describe  # noqa: E402

DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "CREATE TABLE deferred_child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED)",
    "CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)",
]


class DeferredChild(Model):
    id = fields.IntField(primary_key=True, generated=False)
    parent_id = fields.IntField()

    class Meta:
        table = "deferred_child"


class Note(Model):
    id = fields.IntField(primary_key=True, generated=False)
    body = fields.TextField()

    class Meta:
        table = "note"


def committed(path):
    """Row counts read through a separate sqlite3 connection."""
    witness = sqlite3.connect(path, timeout=0.1)
    try:
        child = witness.execute("SELECT count(*) FROM deferred_child").fetchone()[0]
        notes = [r[0] for r in witness.execute("SELECT id FROM note ORDER BY id")]
        return f"deferred_child rows {child}, note ids {notes}"
    except sqlite3.Error as exc:
        return f"the witness read raised {type(exc).__module__}.{type(exc).__qualname__}: {exc}"
    finally:
        witness.close()


async def probe(path, raw):
    current = connections.get("default")
    print(f"    connections.get('default') is {type(current).__name__}")
    print(f"    in_transaction() would return {type(in_transaction()).__name__}")
    print(f"    shared connection in_transaction: {raw.in_transaction}")
    print(f"    committed, read by a separate connection: {committed(path)}")


async def step(title, coro, path, raw, limit=None):
    print(title)
    try:
        if limit is None:
            await coro
        else:
            await asyncio.wait_for(coro, limit)
        print("  returned normally")
    except asyncio.TimeoutError:
        print(f"  did not finish within {limit} seconds; cancelled")
    except Exception as exc:  # noqa: BLE001
        describe(exc)
    await probe(path, raw)


async def failed_commit():
    async with in_transaction() as conn:
        await DeferredChild.create(id=1, parent_id=999, using_db=conn)


async def write_in_transaction(pk):
    async with in_transaction() as conn:
        await Note.create(id=pk, body=f"in_transaction() note {pk}", using_db=conn)


async def run(candidate):
    print(candidates.apply(candidate, "sqlite"))
    tmp = tempfile.mkdtemp(prefix="py8-")
    path = os.path.join(tmp, "py8_sqlite_failed_commit.sqlite3")
    setup = sqlite3.connect(path)
    for statement in DDL:
        setup.execute(statement)
    setup.commit()
    setup.close()
    try:
        await Tortoise.init(db_url=f"sqlite://{path}", modules={"models": ["__main__"]})
        client = connections.get("default")
        await client.execute_query("SELECT 1")
        raw = client._connection  # the aiosqlite connection that every block shares
        print("before anything:")
        await probe(path, raw)
        await step(
            "1. in_transaction() with an INSERT that violates the deferred foreign key",
            failed_commit(), path, raw,
        )
        await step(
            "2. plain Note.create(id=1) outside a transaction block",
            Note.create(id=1, body="plain note 1"), path, raw,
        )
        await step("3. in_transaction() writes note 2", write_in_transaction(2), path, raw, limit=5)
        await step("4. in_transaction() writes note 3", write_in_transaction(3), path, raw, limit=5)
        await step(
            "5. plain Note.create(id=4) outside a transaction block",
            Note.create(id=4, body="plain note 4"), path, raw,
        )
        print("6. Tortoise.close_connections()")
        try:
            await Tortoise.close_connections()
            print("  returned normally")
        except Exception as exc:  # noqa: BLE001
            describe(exc)
        state = raw.in_transaction if raw._connection is not None else "(closed)"
        print(f"    shared connection in_transaction: {state}")
        print(f"    committed, read by a separate connection: {committed(path)}")
        print("7. the shared aiosqlite connection is closed directly")
        if raw._connection is not None:
            await raw.close()
            print("  closed")
        else:
            print("  already closed")
        print(f"    committed, read by a separate connection: {committed(path)}")
    finally:
        shutil.rmtree(tmp)


def main():
    candidate = sys.argv[1] if len(sys.argv) > 1 else "develop"
    if candidate not in ("develop", "C1"):
        sys.exit("usage: chk_sqlite_failed_commit.py [develop|C1]")
    asyncio.run(run(candidate))


if __name__ == "__main__":
    main()
