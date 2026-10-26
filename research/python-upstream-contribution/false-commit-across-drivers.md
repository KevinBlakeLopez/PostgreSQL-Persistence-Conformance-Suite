# The false commit across Python's PostgreSQL drivers and SQLAlchemy

Compiled 2026-10-26. Written by: Claude Opus 5.5 (max).

This page collects the observations behind PY-1, PY-2 and PY-9 in [the tracker](../python-upstream-contribution-tracker.md). The reasoning is in [the roadmap](../python-upstream-contribution-roadmap.md), §3.2 A and B.

**The behaviour.** When a statement fails inside a transaction, PostgreSQL aborts the transaction. If the application catches the error and then commits, PostgreSQL answers `COMMIT` with the command tag `ROLLBACK` and keeps nothing. Every driver below returns from its commit call as if the transaction had committed, and the libraries built on them report success. A statement sent after the caught error fails loudly instead (25P02, "current transaction is aborted"), so the silent case is a caught error followed by the commit.

## Observed

| Driver | Access path | Commit call | What it reported | Evidence |
| --- | --- | --- | --- | --- |
| psycopg 3 | direct | `Connection.commit()` | returned normally | PY-1a: [`psycopg_commit_tag.py`](../production-reachability/reproductions/psycopg_commit_tag.py); CHK-9 `p3-raw-commit` |
| psycopg 3 | direct | `with conn.transaction()` | exited normally; `Transaction.status` was `committed` | PY-1b: [the posted comment](https://github.com/psycopg/psycopg/issues/1453#issuecomment-6389997348) |
| psycopg 3 | SQLAlchemy Core | `Connection.commit()` | returned normally | runs [`64c5c5`](../../reports/examples/2026-10-19T12-35-51Z-64c5c5) and [`b2c174`](../production-reachability/runs/2026-10-19T18-15-49Z-b2c174); CHK-9 `p3-core-connect-commit` |
| psycopg 3 | SQLAlchemy ORM | `Session.commit()`, after an error from `session.execute()` | returned normally; `after_commit` ran | CHK-9 `p3-orm-execute-commit` |
| psycopg 3 | SQLAlchemy asyncio, Core and ORM | `AsyncConnection.commit()`, `AsyncSession.commit()` | returned normally; `after_commit` ran | CHK-10 `pa-core-connect-commit`, `pa-orm-execute-commit` |
| psycopg 3 | Django | a manual `commit()` | returned normally | run [`508b7a`](../production-reachability/runs/2026-10-19T20-58-26Z-508b7a) |
| psycopg2 | direct | `conn.commit()`, `with conn:` | returned normally | [CHK-9](chk-9-psycopg2-false-commit/README.md) |
| psycopg2 | SQLAlchemy Core | `Connection.commit()`, `engine.begin()` | returned normally | CHK-9 |
| psycopg2 | SQLAlchemy ORM | `Session.commit()`, `sessionmaker.begin()` | returned normally; `after_commit` ran | CHK-9 |
| asyncpg | direct | `async with conn.transaction()`, `Transaction.commit()` | returned normally | PY-2: [CHK-2](chk-2-asyncpg/README.md), on asyncio and uvloop; CHK-10 `ap-raw-*` |
| asyncpg | SQLAlchemy asyncio Core | `AsyncConnection.commit()`, `engine.begin()` | returned normally | [CHK-10](chk-10-sa-asyncpg-false-commit/README.md) |
| asyncpg | SQLAlchemy asyncio ORM | `AsyncSession.commit()`, `async_sessionmaker.begin()` | returned normally; `after_commit` ran | CHK-10 |
| asyncpg | Tortoise ORM | its transaction | PPCS FAIL, driver trace `COMMIT; -> ROLLBACK` | run [`c45624`](../../reports/examples/2026-10-19T12-45-38Z-c45624) |

CHK-9 and CHK-10 used the latest releases on 2026-10-26 (SQLAlchemy 2.1.6, psycopg2 2.9.13, psycopg 3.3.6, asyncpg 0.32.0) against PostgreSQL 18.6, three runs per arm. In each of their false-commit arms the server log shows the `COMMIT`, an independent connection finds the row absent, and `pg_xact_status` reads `aborted`. Sending `COMMIT` as plain SQL returned the status `ROLLBACK` on all three drivers. The other rows record the versions in their own files.

## Observed not to report success

- **SQLAlchemy's ORM flush path.** When the failing statement is a flush, `Session.commit()` raises `PendingRollbackError` and SQLAlchemy sends `ROLLBACK` (CHK-9 and CHK-10, on psycopg2 and asyncpg).
- **Django's ORM inside `atomic()`.** PY-10, closed as not a defect.

## Not run

Django on psycopg2; SQLAlchemy's asyncio engine under uvloop; FastAPI or another web framework around these calls; older releases.

## Upstream

- **psycopg 3:** [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21, with the PY-1b comment of 2026-10-24. No maintainer reply as of 2026-10-26.
- **asyncpg:** [asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400), filed 2026-10-24. No reply as of 2026-10-26.
- **psycopg2:** not filed. A follow-up for #1453 that reports it is drafted in [`upstream-drafts/psycopg-1453-followup-psycopg2.md`](upstream-drafts/psycopg-1453-followup-psycopg2.md), not posted.
- **SQLAlchemy:** PY-9, `after_commit` on an aborted transaction, stays deferred: it goes away if the drivers raise (roadmap §3.2 B).
