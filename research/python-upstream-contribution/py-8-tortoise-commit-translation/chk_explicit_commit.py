"""CHK-only, review item 8: an explicit commit() inside in_transaction() that fails at COMMIT.

    PY8_TORTOISE_SRC=<checkout> PY8_SRC_LABEL=<label> \
    DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \
      python chk_explicit_commit.py [asyncpg|psycopg]

tests/test_manual_sql.py::test_in_transaction_commit calls conn.commit() inside the block,
so this is a supported pattern. PY8_TORTOISE_SRC, when set, is put first on sys.path. The
program drops any database named py8_explicit_commit, creates it, and drops it at the end.
Tortoise uses a pool of one connection; its sessions use application_name
py8-reuse-<label>-<backend>-explicit, followed by -r<PY8_REP> when PY8_REP is set.

(a) The row violates a deferred foreign key; conn.commit() is called inside the block and
    its error is not caught there.
(b) The same, but the block catches the error from conn.commit() and exits normally.

After each, a separate connection reads the backend's state and the row count, and an
independent block writes a row on the same pool. Python log records of WARNING and above
are printed.
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
from tortoise import Tortoise, fields  # noqa: E402
from tortoise.models import Model  # noqa: E402
from tortoise.transactions import in_transaction  # noqa: E402

import candidates  # noqa: E402
from tortoise_commit_translation import describe, qualname  # noqa: E402

NAME = "py8_explicit_commit"
DDL = [
    "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
    "INSERT INTO parent VALUES (1)",
    "CREATE TABLE explicit_item (id SERIAL PRIMARY KEY, label TEXT NOT NULL,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) DEFERRABLE INITIALLY DEFERRED)",
]


class ExplicitItem(Model):
    id = fields.IntField(primary_key=True)
    label = fields.CharField(max_length=20)
    parent_id = fields.IntField()

    class Meta:
        table = "explicit_item"


class Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(f"{record.levelname} {record.name}: {re.sub(r'0x[0-9a-f]+', '0x…', record.getMessage())}")


async def scalar(witness, sql, args=()):
    return (await (await witness.execute(sql, args)).fetchone())[0]


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
    app = f"py8-reuse-{label}-{backend}-explicit" + (f"-r{rep}" if rep else "")
    parts = urlsplit(url)
    db_url = urlunsplit(
        (backend, parts.netloc, f"/{NAME}", f"application_name={app}&minsize=1&maxsize=1", "")
    )
    await Tortoise.init(db_url=db_url, modules={"models": ["__main__"]})

    async def follow_up(arm, first_pid):
        async with in_transaction() as conn:
            pid = (await conn.execute_query_dict("SELECT pg_backend_pid() AS v"))[0]["v"]
            await ExplicitItem.create(label=f"{arm}-follow-up", parent_id=1, using_db=conn)
        state = await scalar(witness, "SELECT state FROM pg_stat_activity WHERE pid = %s", (pid,))
        count = await scalar(witness, "SELECT count(*) FROM explicit_item WHERE label = %s", (f"{arm}-follow-up",))
        print(f"  follow-up block: same backend as the arm: {pid == first_pid}; backend state after it {state!r}; its row committed: {count == 1}")

    try:
        for arm in ("a", "b"):
            if arm == "a":
                print("(a) conn.commit() inside the block fails; the block does not catch it")
            else:
                print("(b) conn.commit() inside the block fails; the block catches the error and exits normally")
            pid = None
            try:
                async with in_transaction() as conn:
                    pid = (await conn.execute_query_dict("SELECT pg_backend_pid() AS v"))[0]["v"]
                    await ExplicitItem.create(label=arm, parent_id=999, using_db=conn)
                    if arm == "a":
                        await conn.commit()
                    else:
                        try:
                            await conn.commit()
                        except Exception as exc:  # noqa: BLE001
                            print(f"  conn.commit() raised {qualname(exc)}; the block catches it")
                print("  the block exited normally")
            except Exception as exc:  # noqa: BLE001
                print("  the block raised:")
                describe(exc)
            state = await scalar(witness, "SELECT state FROM pg_stat_activity WHERE pid = %s", (pid,))
            print(f"  backend state after the block: {state!r}")
            print(f"  rows with label {arm!r}: {await scalar(witness, 'SELECT count(*) FROM explicit_item WHERE label = %s', (arm,))}")
            await follow_up(arm, pid)
        print(f"log records: {len(handler.lines)}")
        for line in handler.lines:
            print(f"  {line}")
    finally:
        await Tortoise.close_connections()
        await witness.close()
        await admin.execute(f"DROP DATABASE {NAME} WITH (FORCE)")
        await admin.close()


def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "asyncpg"
    if backend not in ("asyncpg", "psycopg"):
        sys.exit("usage: chk_explicit_commit.py [asyncpg|psycopg]")
    asyncio.run(run(backend))


if __name__ == "__main__":
    main()
