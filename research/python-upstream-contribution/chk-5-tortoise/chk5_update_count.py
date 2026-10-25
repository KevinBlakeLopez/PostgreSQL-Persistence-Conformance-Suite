"""CHK-5 only, not for the upstream issue: the count that save() receives and ignores.

    DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55495/postgres \
      python -I chk5_update_count.py [asyncpg|psycopg]

Runs tortoise_save_after_rollback.py, from this file's directory and unchanged, with
BaseExecutor.execute_update wrapped so that each call prints the value it returns to
Model.save(). No other behaviour changes.
"""

import pathlib
import runpy

from tortoise.backends.base.executor import BaseExecutor

original = BaseExecutor.execute_update


async def execute_update(self, instance, update_fields):
    count = await original(self, instance, update_fields)
    print(f"  [wrapped] execute_update() returned {count!r} to save()")
    return count


BaseExecutor.execute_update = execute_update
runpy.run_path(
    str(pathlib.Path(__file__).with_name("tortoise_save_after_rollback.py")), run_name="__main__"
)
