# Prior-report search

Searched 2026-10-25, about 16:50–17:15 UTC, with the GitHub API through `gh`. Issue searches used `gh api search/issues` with unquoted words (so they match all words, not a phrase); discussion searches used the GraphQL `search(type: DISCUSSION)`. Counts are GitHub's totals at that time. "Relevant" means the item was opened and read.

## SQLAlchemy (`sqlalchemy/sqlalchemy`)

| Query | Kind | Total | Relevant results |
| --- | --- | --- | --- |
| `no such savepoint` | issues | 24 | #7716 (2022, a savepoint-only dialect for tests; different question). #13640 (2026, MSSQL savepoint cursors not closed; different) |
| `sqlite RAISE ROLLBACK` | issues | 89 | none |
| `sqlite on conflict rollback` | issues | 19 | #5968 (2021, `sqlite_on_conflict="IGNORE"` made an INSERT fail silently and the ORM warned about a replaced identity; closed as a question; the maintainer: the ORM "expects INSERT operations to either succeed or fail with an exception") |
| `database or disk is full` | issues | 4 | none |
| `cannot rollback no transaction is active` | issues | 12 | none about SQLite |
| `cannot commit no transaction is active` | issues | 20 | none |
| `no such savepoint` | discussions | 21 | none |
| `sqlite savepoint rollback trigger` | discussions | 2 | none |
| `sqlite on conflict rollback` | discussions | 9 | #5982 is the discussion form of #5968 |
| `sqlite disk full` | discussions | 1 | none |
| `sqlite autocommit False no transaction is active` | discussions | 2 | #7723 is the discussion form of #7716 |
| `session close rollback raises connection checked out` | discussions | 2 | none |

Read directly:

- **#2696** (2013, closed, `bug, high priority, orm`): on MySQL, "mysql has already automatically rolled back by itself, and so destroyed savepoints", and the `SAVEPOINT does not exist` error hid the original one. The maintainer: "the transaction knows that its a savepoint so it's probably reasonable to be ready for the SAVEPOINT to be missing." Resolved through exception chaining and a warning for Python 2. It does not cover a transaction that stays active and later reports a commit.
- **#13657** (2026-10-06, closed, `bug, regression`), from discussion #13656: a failed `BEGIN` on asyncpg left `_transaction` set, so the rollback in `Connection.close()` masked the original error and leaked the pooled connection. Fixed by `d29277af2b80` ("fix leak and masked error after failed asyncpg BEGIN"), which changed `lib/sqlalchemy/engine/base.py`, `lib/sqlalchemy/dialects/postgresql/asyncpg.py` and tests in `test/dialect/postgresql/test_async_pg.py` and `test/engine/test_reconnect.py`. `orm/session.py` was not changed. This is the Core form of F3.
- `SessionTransaction.close()` on `main` at `10f4d1e2d706` (2026-10-23) is unchanged from 2.1.6. No commit to `lib/sqlalchemy/engine/base.py` or `lib/sqlalchemy/dialects/sqlite/` since 2026-10-21.
- Documentation at `rel_2_1_6` (`doc/` and `lib/sqlalchemy/dialects/sqlite/`), searched locally for `RAISE(ROLLBACK`, `ON CONFLICT ROLLBACK`, `SQLITE_FULL`, `disk is full`, `rolled back automatically`, `automatically rolled back`, `automatic rollback`, `no such savepoint`, `sqlite3_get_autocommit`, `in_transaction`: the only related hit is the changelog entry for #2696.

Not searched: the SQLAlchemy mailing list, Gerrit changes, Stack Overflow.

## CPython (`python/cpython`)

| Query | Kind | Total | Relevant results |
| --- | --- | --- | --- |
| `sqlite3 autocommit no transaction is active` | issues | 6 | none about an automatic rollback |
| `sqlite3 autocommit False commit raises` | issues | 2 | none |
| `sqlite3 in_transaction rollback conflict` | issues | 1 | none |
| `sqlite3 ON CONFLICT ROLLBACK` | issues | 10 | none about `autocommit=False` |
| `sqlite3 autocommit transaction always open` | issues | 13 | gh-112441 (below) |
| `sqlite3 cannot rollback no transaction` | issues | 8 | none |

Read directly:

- **gh-112441** (2023, closed as not planned): `autocommit=False` breaks `executescript("BEGIN; COMMIT")`. A maintainer: "`autocommit=False` implies PEP-249 compliant behaviour, meaning a transaction **is always open**." That issue concerned transaction control issued by the user; F4 is SQLite's own rollback.
- **gh-83638**, the issue that introduced `Connection.autocommit`: its comments (about 51 KB) were searched for `automatically roll`, `rolled back automatically`, `automatic rollback`, `ON CONFLICT`, `RAISE(`, `SQLITE_FULL`, `sqlite3_get_autocommit`, `in_transaction`. The last two appear only where the discussion explains what `in_transaction` reports; the others do not appear. The review comments of the implementing PR, gh-93823, were not read.
- `Modules/_sqlite/connection.c`: `pysqlite_connection_commit_impl` and `pysqlite_connection_rollback_impl` are identical at `v3.13.11` and at `main` `efbd165392e2` (2026-10-25).

## Django

Not searched: no Django finding in this study needs a report.
