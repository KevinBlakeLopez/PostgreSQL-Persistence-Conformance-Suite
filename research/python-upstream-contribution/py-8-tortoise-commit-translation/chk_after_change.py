"""CHK-only: what a candidate change does to the reproduction and to three more cases.

    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python chk_after_change.py [asyncpg|psycopg|sqlite] [develop|C1|C2|C3|R]

Part 1 runs tortoise_commit_translation.py's four arms, unchanged, with the candidate
applied. Every Tortoise session of the program uses application_name
py8-after-<backend>-<candidate>, followed by -r<PY8_REP> when PY8_REP is set.

Part 2 (all backends): a nested in_transaction() inserts a row that violates the deferred
foreign key and exits normally; the outer block then exits normally. This shows which
statement fails: RELEASE SAVEPOINT or the outer COMMIT.

Parts 3 and 4 (asyncpg and psycopg only) use their own database, py8_after_change,
created and dropped by the program:

- Part 3, get_or_create() racing a competitor, with a UNIQUE constraint declared
  DEFERRABLE INITIALLY DEFERRED. A separate connection inserts code 'X' and leaves its
  transaction open. get_or_create(code='X') then misses it, inserts its own row, and its
  COMMIT waits for the competitor. Once pg_stat_activity shows that wait, the competitor
  commits, and the program prints what get_or_create() returned or raised.
- Part 4, rollback() on a connection whose backend was terminated: the block raises
  AppError after pg_terminate_backend(), so in_transaction() calls rollback().
"""

import asyncio
import os
import shutil
import sqlite3
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tortoise import Tortoise, fields  # noqa: E402
from tortoise.models import Model  # noqa: E402
from tortoise.transactions import in_transaction  # noqa: E402

import candidates  # noqa: E402
import tortoise_commit_translation as repro  # noqa: E402

NAME = "py8_after_change"
DDL = [
    "CREATE TABLE deferred_unique (id INTEGER PRIMARY KEY,"
    " code TEXT NOT NULL UNIQUE DEFERRABLE INITIALLY DEFERRED)",
]


class DeferredUnique(Model):
    id = fields.IntField(primary_key=True, generated=False)
    code = fields.CharField(max_length=10)

    class Meta:
        table = "deferred_unique"


class AppError(Exception):
    pass


async def scalar(conn, sql, args=()):
    return (await (await conn.execute(sql, args)).fetchone())[0]


async def part2_nested(backend, app):
    print("part 2: a nested block inserts a row that violates the deferred foreign key; both blocks exit normally")
    tmp = None
    if backend == "sqlite":
        tmp = tempfile.mkdtemp(prefix="py8-")
        path = os.path.join(tmp, "py8_part2.sqlite3")
        setup = sqlite3.connect(path)
        for statement in repro.DDL:
            setup.execute(statement)
        setup.commit()
        setup.close()
        db_url = f"sqlite://{path}"
    else:
        import psycopg

        url = os.environ["DATABASE_URL"]
        admin = await psycopg.AsyncConnection.connect(url, autocommit=True, application_name="py8-admin")
        await admin.execute("DROP DATABASE IF EXISTS py8_part2 WITH (FORCE)")
        await admin.execute("CREATE DATABASE py8_part2")
        setup = await psycopg.AsyncConnection.connect(url, dbname="py8_part2", autocommit=True)
        for statement in repro.DDL:
            await setup.execute(statement)
        await setup.close()
        parts = urlsplit(url)
        db_url = urlunsplit((backend, parts.netloc, "/py8_part2", f"application_name={app}", ""))
    await Tortoise.init(db_url=db_url, modules={"models": ["tortoise_commit_translation"]})
    try:
        async with in_transaction() as outer:
            async with in_transaction() as inner:
                await repro.DeferredChild.create(id=3, parent_id=999, using_db=inner)
            print("  the nested block exited normally")
        print("  the outer block exited normally")
    except Exception as exc:  # noqa: BLE001
        repro.describe(exc)
    finally:
        await Tortoise.close_connections()
    if tmp:
        witness = sqlite3.connect(path)
        print(f"  rows in deferred_child with id=3: {witness.execute('SELECT count(*) FROM deferred_child WHERE id = 3').fetchone()[0]}")
        witness.close()
        shutil.rmtree(tmp)
    else:
        witness = await psycopg.AsyncConnection.connect(url, dbname="py8_part2", autocommit=True)
        print(f"  rows in deferred_child with id=3: {await scalar(witness, 'SELECT count(*) FROM deferred_child WHERE id = 3')}")
        await witness.close()
        await admin.execute("DROP DATABASE py8_part2 WITH (FORCE)")
        await admin.close()


async def part3_race(url, witness, app):
    import psycopg

    print("part 3: get_or_create(code='X', defaults={'id': 101}) while a competitor's uncommitted row holds code 'X'")
    competitor = await psycopg.AsyncConnection.connect(url, dbname=NAME, application_name="py8-competitor")
    await competitor.execute("INSERT INTO deferred_unique (id, code) VALUES (100, 'X')")
    task = asyncio.create_task(DeferredUnique.get_or_create(code="X", defaults={"id": 101}))
    waited = None
    for _ in range(200):
        row = await (
            await witness.execute(
                "SELECT wait_event_type, wait_event, query FROM pg_stat_activity"
                " WHERE application_name = %s AND state = 'active' AND wait_event_type = 'Lock'",
                (app,),
            )
        ).fetchone()
        if row:
            waited = row
            break
        if task.done():
            break
        await asyncio.sleep(0.05)
    if waited:
        print(f"  get_or_create() waits: {waited[0]}/{waited[1]} on {waited[2].strip()!r}")
    else:
        print("  get_or_create() was not seen waiting on a lock")
    await competitor.commit()
    print("  the competitor committed")
    try:
        obj, created = await task
        print(f"  get_or_create() returned id={obj.id}, created={created}")
    except Exception as exc:  # noqa: BLE001
        repro.describe(exc)
    rows = await (await witness.execute("SELECT id FROM deferred_unique WHERE code = 'X' ORDER BY id")).fetchall()
    print(f"  ids with code 'X': {[r[0] for r in rows]}")
    await competitor.close()


async def part4_rollback(witness):
    print("part 4: the block raises AppError after its backend was terminated, so in_transaction() calls rollback()")
    try:
        async with in_transaction() as conn:
            pid = (await conn.execute_query_dict("SELECT pg_backend_pid() AS v"))[0]["v"]
            await witness.execute("SELECT pg_terminate_backend(%s)", (pid,))
            for _ in range(200):
                if not await scalar(witness, "SELECT count(*) FROM pg_stat_activity WHERE pid = %s", (pid,)):
                    break
                await asyncio.sleep(0.02)
            print("  the backend is gone; the block raises AppError")
            raise AppError("the application fails after its backend was terminated")
    except Exception as exc:  # noqa: BLE001
        repro.describe(exc)


async def run(backend, candidate):
    print(candidates.apply(candidate, backend))
    app = f"py8-after-{backend}-{candidate}" + (f"-r{os.environ['PY8_REP']}" if os.environ.get("PY8_REP") else "")
    print("part 1: tortoise_commit_translation.py's arms")
    repro.APP = app
    await repro.run(backend)
    await part2_nested(backend, app)
    if backend == "sqlite":
        return
    import psycopg

    url = os.environ["DATABASE_URL"]
    admin = await psycopg.AsyncConnection.connect(url, autocommit=True, application_name="py8-admin")
    await admin.execute(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {NAME}")
    witness = await psycopg.AsyncConnection.connect(
        url, dbname=NAME, autocommit=True, application_name="py8-witness"
    )
    for statement in DDL:
        await witness.execute(statement)
    parts = urlsplit(url)
    db_url = urlunsplit((backend, parts.netloc, f"/{NAME}", f"application_name={app}", ""))
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})
    try:
        await part3_race(url, witness, app)
        await part4_rollback(witness)
    finally:
        await Tortoise.close_connections()
        await witness.close()
        await admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
        await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    candidate = sys.argv[2] if len(sys.argv) > 2 else "develop"
    if backend not in ("asyncpg", "psycopg", "sqlite") or candidate not in candidates.CANDIDATES:
        sys.exit("usage: chk_after_change.py [asyncpg|psycopg|sqlite] [develop|C1|C2|C3|R]")
    asyncio.run(run(backend, candidate))


if __name__ == "__main__":
    main()
