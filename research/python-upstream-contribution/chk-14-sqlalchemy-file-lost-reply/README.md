# CHK-14: sqlalchemy-file deletes a committed row's file when the `COMMIT` reply is lost

Written by: Claude Opus 5.5 (max). Run 2026-10-26 (UTC), `out/2026-10-26T13-25-15Z/`. Nothing posted. For PY-4 and PY-24.

**ID.** It was run under the working name CHK-10. The tracker records it as CHK-14, because CHK-9 to CHK-12 were assigned to other checks in the meantime. The script names, the database objects (`chk10_*`) and the container (`ppcs-chk10-pg`) keep the working name.

**Changes since the run.** Two, both for publication:
- `scripts/chk10_proxy.mjs` imports the proxy by a relative path. When it ran, the import used an absolute local path.
- The server log's `url` values, which sqlalchemy-file records as local file paths, read `$CHECK_DIR`.
Nothing else was changed.

**Question.** PY-4 says SQLAlchemy fires `after_rollback` and `after_soft_rollback` after a root `COMMIT` that raised, also when PostgreSQL had committed (CHK-4). sqlalchemy-file 0.7.0, at about 90k downloads a month and integrated by starlette-admin, deletes the files uploaded in a unit of work from a `Session` `after_soft_rollback` listener. Does a lost `COMMIT` reply make it delete the file of a row that committed?

**Answer (observed, 3 of 3 per cell, byte-identical).** Yes, for two common commit shapes:
- `with session.begin()`;
- `session.commit()` followed by `session.rollback()` when the commit raises.

In both, PostgreSQL committed the row, which an independent connection read. Then sqlalchemy-file called `delete_files(1 file, ctx=after_soft_rollback)`. The committed row now references a file that no longer exists in storage.

## Setup

- **Versions:** SQLAlchemy 2.1.6, psycopg 3.3.6, sqlalchemy-file 0.7.0, apache-libcloud 3.9.1, Python 3.13.11, PostgreSQL 18.6.
- **Database:** a throwaway container (`postgres:18.6@sha256:74935e72…`) with `log_statement=all`, logging in as a non-superuser. The container was removed.
- **Storage:** as in sqlalchemy-file's README, a `LocalStorageDriver` container named `attachment`, fresh for each run.
- **Lost reply:** PPCS's category-E proxy, `harness/lib/pg-wire-proxy.mjs`, unchanged and on the first connection only. It forwards `COMMIT`, drops the server's reply, and closes both sockets. CHK-4 used the same proxy.
- **Arms:**
  - `lost-reply`;
  - `rejected`: a deferred foreign key fails at `COMMIT`, so PostgreSQL rolls back;
  - `no-fault`.
- **Ground truth:**
  - an independent psycopg connection reads whether the row committed;
  - sqlalchemy-file's own `StorageManager.get_file()`, plus the container listing, say whether the file exists.
- **Instrumentation:** it records SQLAlchemy events and wraps `FileFieldSessionTracker.delete_files`, calling through. It changes no behaviour.

## Results

| Form (unit 1) | `lost-reply` (PostgreSQL committed) | `rejected` (PostgreSQL rolled back) | `no-fault` |
| --- | --- | --- | --- |
| `begin`: `with Session(engine) as session, session.begin():` | **dangling**: row committed, file deleted | row absent, file deleted | consistent |
| `commit-rollback`: `session.commit()`, then `session.rollback()` and re-raise | **dangling** | row absent, file deleted | consistent |
| `docs`: the README's form, `session.add(...)` then `session.commit()`, with no rollback | consistent: no rollback event fires, so the file is kept | **orphan**: row absent, file kept | consistent |
| `admin`: starlette-admin's sync call sequence (`begin_nested()` plus `flush()` in `create()`, then the middleware's `commit()`, and `rollback()` if it raises). This is the call sequence, not starlette-admin itself | consistent | **orphan** | consistent |

**Event traces (repetition 1).**

```text
begin / commit-rollback, lost-reply:
  connect 1: through the proxy -> core.commit -> pool.invalidate -> pool.checkin -> orm.after_rollback
  -> sqlalchemy_file.delete_files: 1 file(s), ctx=after_soft_rollback -> orm.after_soft_rollback
docs, rejected:
  connect 1: direct -> core.commit -> pool.reset -> pool.checkin           (no rollback event; no cleanup)
admin, lost-reply:
  connect 1: through the proxy -> sqlalchemy_file.delete_files: 0 file(s), ctx=after_commit -> orm.after_commit
  -> core.commit -> pool.invalidate -> pool.checkin -> orm.after_rollback
  -> sqlalchemy_file.delete_files: 0 file(s), ctx=after_soft_rollback -> orm.after_soft_rollback
```

**Why the `admin` form escapes, observed.** `after_commit` fired when the `begin_nested()` block released its savepoint, before the root `COMMIT`. sqlalchemy-file's `_after_commit` then cleared the session's new-file set. The root rollback event that followed had nothing left to delete. That protects the lost-reply case by accident, and orphans the file on a real rejection.

## What it means

- **PY-4 (SQLAlchemy).** The consequence is no longer inferred. A widely used library treats `after_soft_rollback` as "nothing committed", and a lost `COMMIT` reply makes it destroy data belonging to a committed row.
- **sqlalchemy-file itself.** Three behaviours in its own scope:
  1. After an unknown-outcome commit it deletes files of committed rows. This is the dangling case.
  2. A failed `commit()` that is not rolled back leaves the uploaded files behind. This is the `docs` orphan.
  3. A savepoint release fires `after_commit`, which clears its tracking. This is the `admin` orphan.
- **Not run:** that the third behaviour also deletes a replaced file at `RELEASE SAVEPOINT`, before the outer transaction commits. That is source reading only: `_after_commit` deletes "old files".

## Limits

- The sync `Session` on psycopg only. No `AsyncSession`, no asyncpg, and no other storage driver was run.
- starlette-admin was not run. Only its SQLAlchemy call sequence was.
- The lost reply was produced by a proxy. This says nothing about how often replies are lost in production.

## Files

- `scripts/chk10.py`: the program.
- `scripts/run.py`: four forms × three arms × three repetitions.
- `scripts/chk10_proxy.mjs`: the proxy wrapper, with a port guard.
- `out/2026-10-26T13-25-15Z/`:
  - `<form>.<arm>.rep<N>.out` (stable stdout) and `.raw.json` (names, paths, events, storage listing);
  - `summary.json`, `versions.json`;
  - `server-log.full.txt`.
- `smoke/`: the first single run, of the `docs` form under `lost-reply`, made before the `commit-rollback` and `admin` forms were added. Same result as the matrix.
