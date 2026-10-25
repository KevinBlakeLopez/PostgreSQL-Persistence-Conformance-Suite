"""Generate materials.md: the review package's verbatim source excerpts (items 1-4).

    python make_materials.py <tortoise checkout> <site-packages> > materials.md

Every excerpt is copied from the file as it is on disk, with its path, line range and the
file's SHA-256, so the package cannot drift from the code it describes. The checkout is
the branch fix/commit-integrity-error with its uncommitted patch; site-packages is the
virtualenv that ran the suite and the checks.
"""

import hashlib
import importlib.metadata as md
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKOUT, SITE = sys.argv[1], sys.argv[2]

# (section, title, base, path, first line, last line, note)
EXCERPTS = [
    ("2", "asyncpg backend: the exception translator", "t", "tortoise/backends/asyncpg/client.py", 89, 97, None),
    ("2", "asyncpg backend: TransactionWrapper (begin, savepoint, commit, release_savepoint, rollback, savepoint_rollback)", "t", "tortoise/backends/asyncpg/client.py", 157, 222, "The patched commit() is lines 197-208."),
    ("2", "psycopg backend: the pool class", "t", "tortoise/backends/psycopg/client.py", 28, 34, None),
    ("2", "psycopg backend: the exception translator", "t", "tortoise/backends/psycopg/client.py", 203, 218, None),
    ("2", "psycopg backend: TransactionWrapper", "t", "tortoise/backends/psycopg/client.py", 224, 284, "The patched commit() is lines 257-269."),
    ("2", "PostgreSQL decorator that routes to the backend's translator", "t", "tortoise/backends/base_postgres/client.py", 31, 36, None),
    ("2", "Base client: TransactionalDBClient and ConnectionWrapper", "t", "tortoise/backends/base/client.py", 283, 331, None),
    ("2", "Base client: the transaction contexts (exit and cleanup)", "t", "tortoise/backends/base/client.py", 332, 407, "Both PostgreSQL backends use TransactionContextPooled for the outermost block and NestedTransactionContext for nested blocks."),
    ("2", "Base client: PoolConnectionWrapper (plain queries)", "t", "tortoise/backends/base/client.py", 409, 434, None),
    ("2", "Tortoise exception classes involved", "t", "tortoise/exceptions.py", 33, 49, None),
    ("2", "asyncpg driver: Transaction start, state checks, commit and rollback", "s", "asyncpg/transaction.py", 96, 228, "asyncpg"),
    ("2", "asyncpg driver: Connection._reset and reset (run by the pool on release)", "s", "asyncpg/connection.py", 1527, 1571, "asyncpg"),
    ("2", "asyncpg driver: PoolConnectionHolder.release", "s", "asyncpg/pool.py", 195, 256, "asyncpg"),
    ("2", "asyncpg driver: Pool.release", "s", "asyncpg/pool.py", 901, 937, "asyncpg"),
    ("2", "psycopg driver: BaseTransaction enter, exit, commit and rollback generators", "s", "psycopg/transaction.py", 99, 241, "psycopg"),
    ("2", "psycopg driver: AsyncTransaction", "s", "psycopg/transaction.py", 277, 308, "psycopg"),
    ("2", "psycopg driver: AsyncConnection.transaction()", "s", "psycopg/connection_async.py", 374, 393, "psycopg"),
    ("2", "psycopg driver: Connection._rollback_gen (explicit rollback inside a Transaction context)", "s", "psycopg/_connection_base.py", 590, 615, "psycopg"),
    ("2", "psycopg_pool: _reset_connection (run when a connection is returned)", "s", "psycopg_pool/pool_async.py", 852, 892, "psycopg-pool"),
    ("3", "Model.get_or_create and Model._create_or_get", "t", "tortoise/models.py", 1271, 1316, None),
    ("3", "Model.update_or_create", "t", "tortoise/models.py", 1344, 1382, None),
    ("3", "in_transaction() and atomic()", "t", "tortoise/transactions.py", 18, 66, None),
    ("4", "Fixtures: db_module and db_isolated", "t", "conftest.py", 47, 157, "db (lines 67-109) and db_simple (111-127) are included for context."),
    ("4", "The IntFields model", "t", "tests/testmodels.py", 283, 286, None),
    ("4", "requireCapability", "t", "tortoise/contrib/test/__init__.py", 163, 216, "The class-decorating branch follows; the new tests are functions."),
    ("4", "tests/test_transactions.py: imports", "t", "tests/test_transactions.py", 1, 9, None),
    ("4", "tests/test_transactions.py: get_or_create inside a transaction", "t", "tests/test_transactions.py", 42, 52, None),
    ("4", "tests/test_transactions.py: caught exception in a nested transaction", "t", "tests/test_transactions.py", 75, 95, None),
    ("4", "tests/test_transactions.py: explicit commit and rollback misuse", "t", "tests/test_transactions.py", 265, 282, None),
    ("4", "tests/test_transactions.py: mocked commit and rollback, then the two new tests", "t", "tests/test_transactions.py", 405, 456, "The new tests start at line 430."),
]

SECTIONS = {
    "2": "2. Transaction code around the change (Tortoise on the branch, and the drivers it calls)",
    "3": "3. get_or_create() and update_or_create()",
    "4": "4. Fixtures, the model and the surrounding tests",
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def excerpt(base, rel, first, last):
    path = os.path.join(CHECKOUT if base == "t" else SITE, rel)
    lines = open(path, encoding="utf-8").read().splitlines()
    return path, "\n".join(lines[first - 1:last])


def main():
    out = []
    out.append("# PY-8 review package: materials (items 1-4)\n")
    out.append(
        "Generated by `make_materials.py` from the files on disk; every excerpt is verbatim. "
        "Tortoise paths are in the checkout of `fix/commit-integrity-error` (base `ad0d6ce2b878`, "
        "patch uncommitted). Driver paths are in the virtualenv's site-packages: "
        f"asyncpg {md.version('asyncpg')}, psycopg {md.version('psycopg')}, psycopg-pool {md.version('psycopg-pool')}.\n"
    )
    patch = os.path.join(HERE, "..", "branch", "fix-v2.patch")
    tested = os.path.join(HERE, "..", "branch", "fix.patch")
    out.append("## 1. The complete diff\n")
    out.append(
        f"`../branch/fix-v2.patch`, SHA-256 `{sha(patch)}`: `git diff` of the checkout, 4 files, 44 lines added and 4 removed. "
        f"The runs used `../branch/fix.patch` (SHA-256 `{sha(tested)}`). The two differ only in the changelog line, "
        "which now names `update_or_create()` too (assessment 8.9).\n"
    )
    out.append("```diff\n" + open(patch, encoding="utf-8").read().rstrip("\n") + "\n```\n")
    current = None
    for section, title, base, rel, first, last, note in EXCERPTS:
        if section != current:
            out.append(f"## {SECTIONS[section]}\n")
            current = section
        path, text = excerpt(base, rel, first, last)
        where = rel if base == "t" else f"{rel} ({note} {md.version(note)})"
        out.append(f"### {title}\n")
        out.append(f"`{where}`, lines {first}-{last}; file SHA-256 `{sha(path)[:16]}…`\n")
        if base == "t" and note:
            out.append(f"{note}\n")
        out.append("```python\n" + text + "\n```\n")
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main()
