"""CHK-only, review item 5: update_or_create() with PostgreSQL deferred constraints.

    PY8_TORTOISE_SRC=<checkout> PY8_SRC_LABEL=<label> \
    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python chk_update_or_create.py [asyncpg|psycopg]

PY8_TORTOISE_SRC, when set, is put first on sys.path, so Tortoise is imported from that
checkout; the program prints its label and the digest of the transaction wrapper's source.
The program drops any database named py8_update_or_create, creates it, and drops it at
the end. Tortoise's sessions use application_name py8-uoc-<label>-<backend>, followed by
-r<PY8_REP> when PY8_REP is set.

Table item: id serial primary key; code text, UNIQUE DEFERRABLE INITIALLY DEFERRED;
parent_id integer, REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED; value integer.
parent holds the row 1. A separate psycopg connection in autocommit reads the rows.

1. update path: item 'A' exists (parent 1, value 1); update_or_create(code='A',
   defaults={'parent_id': 999}). The save violates the deferred foreign key, so the
   COMMIT of update_or_create()'s first block fails.
2. create path: update_or_create(code='B', defaults={'parent_id': 999, 'value': 1}).
   The INSERT violates the deferred foreign key, so the COMMIT of _create_or_get()'s
   block fails.
3. race: a competitor inserts code 'C' (value 1) and leaves its transaction open.
   update_or_create(code='C', defaults={'value': 2, 'parent_id': 1}) misses it, inserts
   its own row, and its COMMIT waits for the competitor. Once pg_stat_activity shows the
   wait, the competitor commits.
4. control: update_or_create(code='D', ...) creates, then updates.
"""

import asyncio
import os
import sys
from urllib.parse import urlsplit, urlunsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.environ.get("PY8_TORTOISE_SRC"):
    sys.path.insert(0, os.environ["PY8_TORTOISE_SRC"])

import psycopg  # noqa: E402
from tortoise import Tortoise, fields  # noqa: E402
from tortoise.models import Model  # noqa: E402

import candidates  # noqa: E402
from tortoise_commit_translation import describe  # noqa: E402

NAME = "py8_update_or_create"
DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "INSERT INTO parent VALUES (1)",
    "CREATE TABLE item (id SERIAL PRIMARY KEY,"
    " code TEXT NOT NULL UNIQUE DEFERRABLE INITIALLY DEFERRED,"
    " parent_id INTEGER REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED,"
    " value INTEGER NOT NULL DEFAULT 0)",
]


class Item(Model):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=10)
    parent_id = fields.IntField(null=True)
    value = fields.IntField(default=0)

    class Meta:
        table = "item"


async def rows(witness, code):
    found = await (
        await witness.execute("SELECT id, parent_id, value FROM item WHERE code = %s ORDER BY id", (code,))
    ).fetchall()
    return f"rows with code {code!r} (id, parent_id, value): {found}"


async def call(label, coro):
    print(label)
    try:
        obj, created = await coro
        print(f"  returned created={created}, id={obj.id}, parent_id={obj.parent_id}, value={obj.value}")
    except Exception as exc:  # noqa: BLE001
        describe(exc)


async def run(backend):
    label = os.environ.get("PY8_SRC_LABEL", "installed")
    print(f"tortoise from: {label}; {candidates.source_digest(backend)} is the wrapper's source digest")
    url = os.environ["DATABASE_URL"]
    admin = await psycopg.AsyncConnection.connect(url, autocommit=True, application_name="py8-admin")
    await admin.execute(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {NAME}")
    witness = await psycopg.AsyncConnection.connect(
        url, dbname=NAME, autocommit=True, application_name="py8-witness"
    )
    for statement in DDL:
        await witness.execute(statement)
    await witness.execute("INSERT INTO item (code, parent_id, value) VALUES ('A', 1, 1)")

    rep = os.environ.get("PY8_REP")
    app = f"py8-uoc-{label}-{backend}" + (f"-r{rep}" if rep else "")
    parts = urlsplit(url)
    db_url = urlunsplit((backend, parts.netloc, f"/{NAME}", f"application_name={app}", ""))
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})
    try:
        await call(
            "1. update path: update_or_create(code='A', defaults={'parent_id': 999}); 'A' exists",
            Item.update_or_create(code="A", defaults={"parent_id": 999}),
        )
        print(f"  {await rows(witness, 'A')}")

        await call(
            "2. create path: update_or_create(code='B', defaults={'parent_id': 999, 'value': 1})",
            Item.update_or_create(code="B", defaults={"parent_id": 999, "value": 1}),
        )
        print(f"  {await rows(witness, 'B')}")

        print("3. race: a competitor's uncommitted row holds code 'C'")
        competitor = await psycopg.AsyncConnection.connect(
            url, dbname=NAME, application_name="py8-competitor"
        )
        cur = await competitor.execute(
            "INSERT INTO item (code, parent_id, value) VALUES ('C', 1, 1) RETURNING id"
        )
        print(f"  the competitor's row has id {(await cur.fetchone())[0]}")
        task = asyncio.create_task(
            Item.update_or_create(code="C", defaults={"value": 2, "parent_id": 1})
        )
        waited = None
        for _ in range(200):
            waited = await (
                await witness.execute(
                    "SELECT wait_event_type, wait_event, query FROM pg_stat_activity"
                    " WHERE application_name = %s AND state = 'active' AND wait_event_type = 'Lock'",
                    (app,),
                )
            ).fetchone()
            if waited or task.done():
                break
            await asyncio.sleep(0.05)
        if waited:
            print(f"  update_or_create() waits: {waited[0]}/{waited[1]} on {waited[2].strip()!r}")
        else:
            print("  update_or_create() was not seen waiting on a lock")
        await competitor.commit()
        print("  the competitor committed")
        await call("  update_or_create(code='C', defaults={'value': 2, 'parent_id': 1})", task)
        print(f"  {await rows(witness, 'C')}")
        await competitor.close()

        await call(
            "4. control: update_or_create(code='D', defaults={'value': 1, 'parent_id': 1})",
            Item.update_or_create(code="D", defaults={"value": 1, "parent_id": 1}),
        )
        await call(
            "   then update_or_create(code='D', defaults={'value': 2})",
            Item.update_or_create(code="D", defaults={"value": 2}),
        )
        print(f"  {await rows(witness, 'D')}")
    finally:
        await Tortoise.close_connections()
        await witness.close()
        await admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
        await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg"):
        sys.exit("usage: chk_update_or_create.py [asyncpg|psycopg]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
