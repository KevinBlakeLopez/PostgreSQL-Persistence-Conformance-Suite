"""CHK-only. Candidate changes for PY-8, applied at run time to unchanged Tortoise code.

Each candidate wraps methods of the backend's transaction wrapper class, exactly as a
decorator in the source would. Nothing in the Tortoise checkout is edited.

- develop: no change.
- C1: the backend's translate_exceptions on commit(). On asyncpg and psycopg,
  release_savepoint() calls self.commit(), so a nested block's RELEASE SAVEPOINT is
  translated too.
- C2: as C1, but release_savepoint() calls the undecorated commit(), so a nested block
  behaves as on develop.
- C3: commit() maps only the driver's integrity error to tortoise's IntegrityError, as the
  backend's translator does (asyncpg chains it with `from exc`; psycopg and sqlite do not).
  Every other error, class 25 included, passes through as on develop.
- R: C1, plus the backend's translate_exceptions on rollback(). savepoint_rollback()
  calls self.rollback() on asyncpg and psycopg, so it is translated too.

On sqlite, the module's translate_exceptions requires a query argument, so it cannot wrap
commit(). The sqlite candidates use a copy of its mapping with the signature (self, *args),
which is MySQL's and ODBC's signature. SQLite's release_savepoint() does not call commit(),
so C1 and C2 are the same change there.
"""

import functools
import hashlib
import inspect
import sqlite3

from tortoise.exceptions import IntegrityError, OperationalError

CANDIDATES = ("develop", "C1", "C2", "C3", "R")


def sqlite_translate_exceptions(func):
    @functools.wraps(func)
    async def translate_exceptions_(self, *args):
        try:
            return await func(self, *args)
        except sqlite3.OperationalError as exc:
            raise OperationalError(exc)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(exc)

    return translate_exceptions_


def integrity_only(backend):
    """C3's wrapper: only the driver's integrity error is translated."""
    if backend == "asyncpg":
        import asyncpg

        def translate(exc):
            if isinstance(exc, asyncpg.IntegrityConstraintViolationError):
                raise IntegrityError(exc) from exc

    elif backend == "psycopg":
        import psycopg

        def translate(exc):
            if isinstance(exc, psycopg.errors.IntegrityError):
                raise IntegrityError(exc)

    else:

        def translate(exc):
            if isinstance(exc, sqlite3.IntegrityError):
                raise IntegrityError(exc)

    def decorate(func):
        @functools.wraps(func)
        async def commit(self, *args):
            try:
                return await func(self, *args)
            except Exception as exc:
                translate(exc)
                raise

        return commit

    return decorate


def _wrapper_class(backend):
    if backend == "asyncpg":
        from tortoise.backends.asyncpg.client import TransactionWrapper
        from tortoise.backends.base_postgres.client import translate_exceptions
    elif backend == "psycopg":
        from tortoise.backends.base_postgres.client import translate_exceptions
        from tortoise.backends.psycopg.client import TransactionWrapper
    else:
        from tortoise.backends.sqlite.client import SqliteTransactionWrapper as TransactionWrapper

        translate_exceptions = sqlite_translate_exceptions
    return TransactionWrapper, translate_exceptions


def source_digest(backend):
    """SHA-256 of the unchanged wrapper class's source, so an output names the code it ran on."""
    cls, _ = _wrapper_class(backend)
    return hashlib.sha256(inspect.getsource(cls).encode()).hexdigest()[:16]


def apply(candidate, backend):
    if candidate not in CANDIDATES:
        raise SystemExit(f"unknown candidate {candidate!r}; expected one of {CANDIDATES}")
    cls, translate = _wrapper_class(backend)
    digest = source_digest(backend)
    if candidate == "develop":
        return f"candidate develop (no change); {cls.__module__}.{cls.__name__} source {digest}"
    commit = cls.commit
    if candidate == "C3":
        cls.commit = integrity_only(backend)(commit)
        return f"candidate C3; {cls.__module__}.{cls.__name__} source {digest}"
    cls.commit = translate(commit)
    if candidate == "C2" and backend != "sqlite":

        async def release_savepoint(self):
            return await commit(self)

        cls.release_savepoint = release_savepoint
    if candidate == "R":
        cls.rollback = translate(cls.rollback)
    return f"candidate {candidate}; {cls.__module__}.{cls.__name__} source {digest}"
