"""pytest plugin (CHK-only): record every exception that a transaction wrapper's commit() raises,
with the running test's node id, and re-raise it unchanged. No behaviour change."""
import functools
import os

import pytest

_scheme = os.environ.get("TORTOISE_TEST_DB", "sqlite://").split(":", 1)[0]
if _scheme == "asyncpg":
    from tortoise.backends.asyncpg.client import TransactionWrapper as _W
elif _scheme == "psycopg":
    from tortoise.backends.psycopg.client import TransactionWrapper as _W
else:
    from tortoise.backends.sqlite.client import SqliteTransactionWrapper as _W

_current = {"test": None}
_log = os.path.join(os.environ["PY8_MARKERS"], f"commit-trace-{os.getpid()}")
_orig = _W.commit


@functools.wraps(_orig)
async def commit(self, *args):
    try:
        return await _orig(self, *args)
    except BaseException as exc:
        with open(_log, "a") as fh:
            fh.write(f"{_current['test']}\t{type(exc).__module__}.{type(exc).__qualname__}\t{str(exc)[:120]}\n")
        raise


_W.commit = commit


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    _current["test"] = item.nodeid
    yield
    _current["test"] = None
