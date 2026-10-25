"""CHK-only: SQLite's translate_exceptions, as it stands, cannot wrap commit().

    python chk_sqlite_decorator_signature.py

The module's decorator has the signature (self, query, *args), and commit() takes no
argument. The program wraps SqliteTransactionWrapper.commit with it, on an in-memory
database, and runs an in_transaction() block that exits normally.
"""

import asyncio
import warnings

from tortoise import Tortoise
from tortoise.backends.sqlite.client import SqliteTransactionWrapper, translate_exceptions
from tortoise.transactions import in_transaction


async def main():
    warnings.filterwarnings("ignore", message='Module "__main__" has no models')
    SqliteTransactionWrapper.commit = translate_exceptions(SqliteTransactionWrapper.commit)
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["__main__"]})
    try:
        async with in_transaction() as conn:
            await conn.execute_query("SELECT 1")
        print("the block exited normally")
    except Exception as exc:  # noqa: BLE001
        print(f"the block raised {type(exc).__module__}.{type(exc).__qualname__}: {exc}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
