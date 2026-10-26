"""Wait until DATABASE_URL accepts connections, then refuse unless cluster_name equals TOKEN."""

import asyncio
import os
import sys
import time

import asyncpg


async def main():
    deadline = time.monotonic() + 90
    while True:
        try:
            con = await asyncpg.connect(os.environ["DATABASE_URL"], timeout=5)
            break
        except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
            if time.monotonic() > deadline:
                sys.exit(f"server not reachable: {exc!r}")
            await asyncio.sleep(0.5)
    token = await con.fetchval("show cluster_name")
    await con.close()
    if token != os.environ["TOKEN"]:
        sys.exit("cluster_name does not match: refusing to run")
    print("server reachable; cluster_name matches")


asyncio.run(main())
