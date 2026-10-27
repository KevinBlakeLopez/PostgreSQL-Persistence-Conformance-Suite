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
| psycopg 3 | Django, a raw-SQL error caught inside `atomic()`, or under `ATOMIC_REQUESTS` alone | the end of `atomic()` | returned normally; `on_commit` ran; the view returned 200 | [CHK-12](chk-12-django-raw-sql-false-commit/README.md); [its re-run](chk-12-django-raw-sql-false-commit/once-only-rerun/README.md) with a once-only bonus |
| psycopg 3 | Procrastinate 3.10.0, after an ignored `AlreadyEnqueued`: its Django integration, and its external-connection API | the end of `atomic()`; `conn.commit()` | returned normally; `on_commit` ran (Django) | [CHK-16](chk-16-procrastinate-queueing-lock/README.md) |
| psycopg2 | direct | `conn.commit()`, `with conn:` | returned normally | [CHK-9](chk-9-psycopg2-false-commit/README.md) |
| psycopg2 | SQLAlchemy Core | `Connection.commit()`, `engine.begin()` | returned normally | CHK-9 |
| psycopg2 | SQLAlchemy ORM | `Session.commit()`, `sessionmaker.begin()` | returned normally; `after_commit` ran | CHK-9 |
| asyncpg | direct | `async with conn.transaction()`, `Transaction.commit()` | returned normally | PY-2: [CHK-2](chk-2-asyncpg/README.md), on asyncio and uvloop; CHK-10 `ap-raw-*` |
| asyncpg | direct, after a caught client-side timeout | `async with conn.transaction()`, `Transaction.commit()` | returned normally; a raw `COMMIT` returned `ROLLBACK` | [CHK-11](chk-11-asyncpg-client-timeout/README.md): `fetch(timeout=)`, `command_timeout` and `asyncio.wait_for()`, on asyncio and uvloop; [CHK-15](chk-15-asyncpg-timeout-order/README.md): `asyncio.timeout()`, and a server timeout that fires after the client's |
| asyncpg | SQLAlchemy asyncio Core | `AsyncConnection.commit()`, `engine.begin()` | returned normally | [CHK-10](chk-10-sa-asyncpg-false-commit/README.md) |
| asyncpg | SQLAlchemy asyncio ORM | `AsyncSession.commit()`, `async_sessionmaker.begin()` | returned normally; `after_commit` ran | CHK-10 |
| asyncpg | Tortoise ORM | its transaction | PPCS FAIL, driver trace `COMMIT; -> ROLLBACK` | run [`c45624`](../../reports/examples/2026-10-19T12-45-38Z-c45624) |

CHK-9 and CHK-10 used the latest releases on 2026-10-26 (SQLAlchemy 2.1.6, psycopg2 2.9.13, psycopg 3.3.6, asyncpg 0.32.0) against PostgreSQL 18.6, three runs per arm. In each of their false-commit arms the server log shows the `COMMIT`, an independent connection finds the row absent, and `pg_xact_status` reads `aborted`. Sending `COMMIT` as plain SQL returned the status `ROLLBACK` on all three drivers. CHK-12 (Django 6.1.2 with psycopg 3.3.6) ran the same checks, three runs per arm, with the SQLSTATEs in the server log. The other rows record the versions in their own files.

## Observed not to report success

- **SQLAlchemy's ORM flush path.** When the failing statement is a flush, `Session.commit()` raises `PendingRollbackError` and SQLAlchemy sends `ROLLBACK` (CHK-9 and CHK-10, on psycopg2 and asyncpg).
- **Django's ORM inside `atomic()`.** PY-10, closed as not a defect. Django sends `ROLLBACK` itself and skips `on_commit`. The view still returns normally, though, and the write is gone (CHK-12).
- **Django's `atomic()` nested inside `ATOMIC_REQUESTS`, after a raw-SQL error.** Django's `RELEASE SAVEPOINT` fails with `25P02`, and the request returns 500 (CHK-12).
- **asyncpg, when a server timeout fires before the client's.** A `lock_timeout` or `statement_timeout` raises `LockNotAvailableError` or `QueryCanceledError`. Code that catches only `TimeoutError` lets it through, and the block rolls back (CHK-15).
- **asyncpg, when a timed-out statement had already finished.** At the deadline, the caught `TimeoutError` can follow a statement that completed before the cancel arrived. The server ignores the cancel, and the commit is real (CHK-15).

## Not run

- Django on psycopg2;
- Django under a WSGI or ASGI server (CHK-12 used Django's test client);
- SQLAlchemy's asyncio engine under uvloop;
- FastAPI or another web framework around the SQLAlchemy and asyncpg calls;
- older releases.

## Upstream

- **psycopg 3:** [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21, with the PY-1b comment of 2026-10-24. `dvarrazzo` closed it 2026-10-27 ([comment](https://github.com/psycopg/psycopg/issues/1453#issuecomment-6443758485)): `COMMIT` on `INERROR` is valid, and a caller who traps the error owns the connection state. No code change. The reply does not mention `transaction()` or `Transaction.status`. A thank-you is drafted and not posted.
- **asyncpg:** [asyncpg#1400](https://github.com/MagicStack/asyncpg/issues/1400), filed 2026-10-24. `Claire-ovo` reproduced it on 2026-10-27. Outside PR #1401 is open and not validated here.
- **psycopg2:** not filed. The #1453 follow-up that would have reported CHK-9 is dropped; the issue is closed ([draft](upstream-drafts/psycopg-1453-followup-psycopg2.md)).
- **SQLAlchemy:** PY-9, `after_commit` on an aborted transaction, stays deferred on asyncpg. psycopg will not raise from `commit()` on this path.
- **Procrastinate:** PY-25, an issue draft asking to add the savepoint caveat to its queueing-lock and Django pages; not posted.
- **Django:** no report. Django documents a caught raw-SQL error inside `atomic()` as unspecified (PY-10, CHK-12).
