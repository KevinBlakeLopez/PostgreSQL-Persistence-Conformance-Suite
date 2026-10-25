# CHK-4: facts for the author (PY-4)

Written by: Claude Opus 5.5 (max). These are facts and pointers for the author's own SQLAlchemy discussion. They are not text to post: SQLAlchemy's rules require the author's own words (see the tracker's PY-4 entry). The evidence and the method are in [`README.md`](README.md).

**Versions.** SQLAlchemy 2.1.6 (the latest release, 2026-10-21) and 2.1.5; psycopg 3.3.6 (binary, libpq 18.6); asyncpg 0.32.0; greenlet 3.5.6; Python 3.13.11; PostgreSQL 18.6. Every cell ran 3 times. The three outputs of each cell are byte-identical, and 2.1.5's equal 2.1.6's apart from the version field.

## Observed

1. **A lost `COMMIT` reply, with no cancellation.** PostgreSQL received `COMMIT` and committed. A proxy then dropped the reply and closed the connection: PPCS's category-E proxy, run unchanged. This was run with `Session.begin()` on psycopg, and with `AsyncSession.begin()` on asyncpg and on psycopg.
   - **What the block raised:** psycopg: `sqlalchemy.exc.OperationalError`, "consuming input failed: server closed the connection unexpectedly". asyncpg: `sqlalchemy.exc.DBAPIError`, "connection was closed in the middle of operation". `connection_invalidated` was true in both.
   - **The events:** the ORM then fired `after_rollback`, followed by `after_soft_rollback`.
   - **The database:** by the time the block had raised, `pg_xact_status()` already read `committed`, and the row was visible with `xmin` equal to the transaction's xid. `psql` inside the container agreed.
2. **No DBAPI rollback took place.**
   - After the failed commit, SQLAlchemy did not call the dialect's `do_rollback`. A wrapper recorded every call.
   - The server log shows nothing more on that backend after `COMMIT` except its disconnection.
3. **The order of events:** `core.commit`; the DBAPI commit raising; `pool.invalidate`; `pool.close`; `pool.checkin`; `after_rollback`; `after_soft_rollback`. This is the order P3 recorded for its anyio-cancelled rows.
4. **A rejected `COMMIT`** (added beyond the brief). A deferred foreign key failed at `COMMIT` (`23503`), and PostgreSQL rolled the transaction back.
   - The block raised `sqlalchemy.exc.IntegrityError`, and the connection was not invalidated.
   - `after_rollback` and `after_soft_rollback` fired.
   - `after_rollback` fired before the pool's reset-on-return called `do_rollback`.
   - No `ROLLBACK` reached the server: the next statement that backend logged was the next unit's `BEGIN`.
5. **No fault:** `after_commit` only, and the transaction committed.
6. **The next unit of work** on the same engine committed normally every time. After a lost reply it used a new connection. After a rejected `COMMIT` it reused the backend, in a new transaction.

## Source reading (2.1.6)

7. **The commit side,** `engine/base.py:2724-2750`, `RootTransaction._do_commit`: it deactivates the transaction in a `finally`, whether or not the commit succeeded. `_close_impl` (`2702-2716`) calls the DBAPI rollback only `if self.is_active`.
8. **The event,** `orm/session.py:1376-1380`, `SessionTransaction.rollback`: it calls each connection transaction's `rollback()`, then dispatches `after_rollback`. `after_soft_rollback` follows at line 1414.
9. **The docstring,** `orm/events.py:1882-1898`, `after_rollback` begins:

   ```text
   Execute after a real DBAPI rollback has occurred.

   Note that this event only fires when the *actual* rollback against
   the database occurs - it does *not* fire each time the
   :meth:`.Session.rollback` method is called, if the underlying
   DBAPI transaction has already been rolled back.
   ```

10. **`main`** (`10f4d1e2d7`, 2026-10-23) is three commits past `rel_2_1_6`. None of its `orm/session.py` changes touches rollback, commit or event dispatch, and `engine/base.py` is unchanged. This is from GitHub's compare view, read 2026-10-25; it was not run.

## What it answers

- **Roadmap hypothesis H-b holds.** The rollback event follows a lost `COMMIT` reply with no cancellation involved, and PostgreSQL had committed.
- **So PY-4 is not specific to cancellation or to anyio.** In every run so far, the event fired after a root `COMMIT` that raised, whatever PostgreSQL decided:
  - **PostgreSQL committed:** the lost reply here, level-triggered cancellation in P3, and SIGINT under Uvicorn in P8;
  - **PostgreSQL rolled back:** the rejected `COMMIT` here.
- **The contract question is the maintainers'.** Whether this matches the event's contract is their judgment.

## Limits

- **How the reply was lost.** A proxy on the wire dropped it: PostgreSQL wrote its reply, and the client never read it. This says nothing about how often replies are lost in production.
- **The setup.** One server, PostgreSQL 18.6, with `synchronous_commit` on. A pool of one with default settings (`pool_pre_ping` off).
- **The connection.** In the recorded runs, unit 1 always ran on the pool's first connection.
- **The forms.** Only the context-manager forms ran: `with session.begin()` and `async with session.begin()`. An explicit `session.commit()` followed by the application's own `rollback()` was not run.
- **Not run:** psycopg2, pg8000, and other databases.
