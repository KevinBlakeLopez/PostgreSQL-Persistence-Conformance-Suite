# PPCS integration recommendation

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This is a recommendation, not a change. Adding a family, changing the evidence model or adding fixture roles needs maintainer approval (`AGENTS.md`, "Approval gates"). The evidence is in [`README.md`](README.md).

## Recommendation

**Add no PPCS case now.** Keep this study as a companion investigation under `research/`. If a session-state family is approved later (the gap analysis's R2, §7.2), give it the two invariants below and nothing more.

## Why not now

1. **PPCS's subjects are frameworks' transaction APIs.** Pools appear only as the pooled modes of adapters (Spring JDBC, Spring TX, Hibernate and jOOQ use HikariCP 7.1.0).
   - F-H2 needs a driver-begun transaction after the last commit, plus a dirty isolation or read-only setting at `close()`.
   - Frameworks that restore isolation and read-only themselves avoid that order. Spring's `DataSourceUtils.resetConnectionAfterTransaction` is one; that is source reading, not a run.
   - So a framework-level case would mostly PASS without exercising the mechanism.
2. **TX-03 cannot see F-H2.** Its unit 1 executes statements through the framework, which sets HikariCP's commit-state flag, so HikariCP rolls back on close. The existing TX-03 results need no reclassification.
3. **Session state needs fixture changes.** A second schema, an `inserted_by DEFAULT current_user` column, a NOLOGIN role granted to a non-superuser login, and per-run role management are harness changes. The gap analysis §7.2 already lists them.
4. **The pools found safe here would add rows that only confirm documented behaviour:** asyncpg, SQLAlchemy, psycopg_pool and Npgsql under cleanup failure. That is matrix growth without a question (`AGENTS.md` rule 5).

## If a session-state family is approved: two invariants

**SS-1. Initial state.** A unit of work does not run with session state left by an earlier unit on the same pool. Its role, `search_path`, configuration parameters, session advisory locks and temporary objects are those of a fresh session, or the pool's documented initial state. This is R2's invariant, unchanged.

- *Evidence:* the row's schema and `inserted_by`; `pg_locks` for the backend between the units; the temp schema's relations in the catalogs.
- *Modes:* native (defaults), and configured (the pool's documented reset hook).

**SS-2. No reuse after a failed cleanup.** A connection whose release-time cleanup did not complete is not handed to another unit of work.

- *Evidence:* backend identity at the next checkout (PID plus `backend_start`); at that checkout, before the unit's first statement, the backend's `xact_start` and `backend_xmin` from `pg_stat_activity`; the unit's `current_setting('transaction_isolation')` and `current_user`.
- *FAIL:* the same backend is reused while still carrying the earlier unit's transaction or a setting the cleanup should have reset.
- *PASS:* a different backend, or the same backend in the pool's documented initial state.
- *INCONCLUSIVE:* the cleanup did not fail (the fault's signature is missing), or the repetitions disagree.
- *Faults:*
  - **natural, category A-like:** a driver call that begins a transaction the pool does not track, as with HikariCP and pgjdbc's `getSchema()` after the last commit;
  - **category C:** the driver fails the pool's reset statement without sending it. This is the reset-step analogue of `TX-03.rollback-not-sent`, and only pools that send reset statements (asyncpg, Npgsql, HikariCP, psycopg_pool with `reset=`) can exercise it.
- *Controls:* a `correct` pool policy that rolls back, runs `DISCARD ALL` in autocommit, and closes the connection if either fails; an `unsafe` policy that returns the connection after a failure.

## What not to do

- Do not turn TX-03 into a connection-pool benchmark, or add pools as adapters of their own.
- Do not add PgBouncer or another pooling layer for this question: no result here depends on one.
- Do not move the probes in `research/connection-pool-session-state/` into `harness/` or `adapters/` without an approved case specification.
