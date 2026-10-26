# Production relevance: failed transaction-control statements and reused connections

Compiled 2026-10-26. Written by: Claude Opus 5.5 (max).

This page rates seven filed findings under [`docs/production-relevance.md`](../../../docs/production-relevance.md): K2, K3, Y1, M4, M2, T1 and T2. Each one is about a `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` or `ROLLBACK TO SAVEPOINT` that fails, and about what the library then does with the connection. It is a desk assessment: read-only GitHub searches, reading code at commits, and reading our own records. Nothing was run, posted or contacted.

Our records are in PPCS [`docs/upstream-submissions.md`](../../../docs/upstream-submissions.md) and in the research repository `nest-adonis-spike`, cited by repository-relative path and branch. Some of its files are uncommitted working copies; they are marked.

## Summary

**Tiers** (judgment, 2026-10-26). They weigh likelihood, the strength and source of the evidence, and whether the failure is silent. They rate no severity and no contract status.

- **Higher:** none. No report shows a silent outcome from any of these findings on a real deployment.
- **Middle:** T2, Y1 and K3.
  - T2: silent. A 7,761-star project reproduced the same reuse through TypeORM's own `save()` and fixed it in its database client (OneUptime#4650).
  - Y1: silent. Kysely's maintainers describe the same sequence (#2148) and fixed it on `master` (#2155). No release contains the fix.
  - K3: the best-sourced evidence in the group (production logs in knex#4630, a downstream workaround in supabase/storage#459). Its failure is loud.
- **Lower:** K2, T1, M4 and M2.
  - K2: silent, and the same mechanism as Y1 and T2. Nothing knex-specific was found, and knex configurations with `query_timeout` were rare in the sample.
  - T1: its triggers are subscriber errors, misuse or injection. Its natural trigger, a missing savepoint name, comes from concurrent nested transactions, which a TypeORM maintainer calls invalid.
  - M4: nothing found for a `ROLLBACK` that fails on a live connection. The one MikroORM audit that looked at it scoped it out.
  - M2: injected and subscriber triggers only. The `query_timeout` path is inferred, not run. Fixed on `master`, not released.
- **No production trigger:** none. M2 would move here without its inferred `query_timeout` path.
- **Not defects, or folded into other items:** none. M4's case is folded into Y1 in MikroORM builds that pin Kysely 0.29.7 (see M4).

| ID | Filed as | Trigger, and how our runs produced it | Strongest real-world evidence | Real code run | Consequence | Likelihood (judgment) |
| --- | --- | --- | --- | --- | --- | --- |
| T2 | typeorm#12978, issue, 2026-10-17. Outside fix PR #12980 | A `ROLLBACK` that fails on a live connection, after which TypeORM releases it: injected (TR1d, TR1d3). A direct `release()` without rollback: the ordinary API, no fault | Audit: OneUptime#4650 (7,761 stars) reproduced TypeORM dropping `save()`'s `ROLLBACK` behind PgBouncer with `query_timeout` 35 s, in its own suite. Exposed code: Twenty (59,802 stars) sets `query_timeout` 10 s on its core pool, and no `statement_timeout` in that file | No. OneUptime's suite ran its own code | The next checkout's `COMMIT` commits the earlier unit's rows. Silent | Low to moderate |
| Y1 | Comment on kysely#1990, 2026-10-18 | pg's `query_timeout` drops a queued `ROLLBACK`: real timeouts, no injection (controlled 3 of 3; callback API 2 of 2 on 0.29.6 and on 0.29.7) | Acknowledged: kysely#2148 by a maintainer, fixed on `master` by #2155. Not released | No | The next transaction's `COMMIT` commits the failed transaction's writes. Silent | Low |
| K3 | Comment on knex#4709, 2026-10-17 | A failed `BEGIN` or `SAVEPOINT`: a server-rejected `BEGIN` (invalid isolation level) and a `SAVEPOINT` in an aborted transaction, both real errors | Production: knex#4630 quotes production logs. `BEGIN` never reached the server, and the application got "Transaction query already complete". Audit: supabase/storage#459 works around #4709 | No | `await knex.transaction()` returns a dead transaction and the real error is masked; the handler form runs the handler first. Loud | Moderate |
| K2 | knex#6546, issue, 2026-10-17; PR #6548, 2026-10-18, head `32d6d0d` | pg's `query_timeout` drops a queued `ROLLBACK` or `COMMIT`: real timeouts (K2-4, K2-L1, A.1). knex's 5 s rollback timer with `query_timeout` above 5 s: the PR's regression test | The same mechanism in other libraries (OneUptime#4650, kysely#2148, drizzle#6114). None on knex. 1 of 10 inspected knex hits has the exposed configuration | No | The next transaction's `COMMIT` commits the failed transaction's writes (its `ROLLBACK` discards them). Silent | Low |
| T1 | typeorm#12976 and #12977, issues, 2026-10-17; PR #12979. Outside PRs #12983 and #12997 | #12976: a caught error, then a nested `transaction()` (real error); a throwing subscriber. #12977: an injected `ROLLBACK TO SAVEPOINT` failure, an injected missing savepoint (3B001), a throwing subscriber | The trigger occurs: typeorm#11543 logs 3B001 at `ROLLBACK TO SAVEPOINT`; #12308 hits it with concurrent nested transactions, closed as not planned. No report of the consequence | No | The caller is rolled back and its later writes autocommit (loud); or the connection is released inside its transaction and the next unit commits it (silent) | Low |
| M4 | Comment on mikro-orm PR #8448, 2026-10-18 | A `ROLLBACK` that fails on a live connection: injected (T7d) | None for this case. open-mercato#7333 scoped it out: "hard to reach because the platform sets no `query_timeout`" | No | On 7.2.5 the connection stays checked out inside its transaction until the session ends. On `master`, Y1's reuse (source reading) | Low |
| M2 | Comment on mikro-orm PR #8462, 2026-10-17, the fix for #8458 | A client-side failure of `ROLLBACK TO SAVEPOINT`: injected, and a throwing `beforeTransactionRollback` subscriber | None. #8458's reporter injected the failure and calls it "not a frequent production event" | No | The inner writes commit with the outer transaction. Silent | Low |

## The findings

### T2: typeorm#12978

- **Filed:** issue [typeorm#12978](https://github.com/typeorm/typeorm/issues/12978), 2026-10-17. A non-maintainer opened fix PR [#12980](https://github.com/typeorm/typeorm/pull/12980) on 2026-10-18. No maintainer has replied. TypeORM 1.1.2 is the latest release.
- **Production relevance (2026-10-26):**
  - **Consequence:** `release()` returns a pooled connection that is still inside a transaction, and the next checkout's `COMMIT` commits the earlier unit's rows (PostgreSQL, MySQL, MariaDB). TypeORM reaches the same release on its own when a `ROLLBACK` fails: `EntityManager.transaction()` and `save()` swallow the rollback error and release in `finally`. Silent.
  - **Trigger, a `ROLLBACK` that fails on a live connection:** in production, the event yes (a client timeout over a slow statement); whether it has committed a failed unit's rows, unknown. OneUptime#4650 found that its deployed configuration reaches this path, and reproduced it. In our runs, injected (TR1d, TR1d3). Code shape: TypeORM's managed transaction, `save()`, or the documented manual pattern, all reasonable. The configuration it needs, pg's `query_timeout` with no shorter server-side `statement_timeout`, is a minority choice; behind PgBouncer a startup `statement_timeout` is dropped. Evidence: audit, OneUptime#4650 (7,761 stars; reproduced in the project's own suite; no incident stated). Exposed code: Twenty's core pool.
  - **Trigger, `release()` without a rollback after an application error:** in production, unknown. In our runs, the ordinary API with no fault. Code shape: contrary to TypeORM's documented pattern, which rolls back in `catch`. Evidence: 0 of 10 inspected manual-transaction hits do this.
  - **Reproduced on real code:** no. OneUptime's suite ran OneUptime's code; we did not.
  - **Searches:** 4 of 10 inspected TypeORM `query_timeout` hits (3 of 6 projects) have no server bound at or below the client timeout. 8 of 10 inspected manual-transaction hits use the documented pattern, which releases an open transaction when the `ROLLBACK` fails.
  - **Likelihood (judgment):** low to moderate. Every TypeORM transaction path reaches it once a `ROLLBACK` fails; the trigger needs `query_timeout` without a server bound, and a statement or stall about twice that long.
  - **Not established:** a production incident; Twenty's deployed `statement_timeout`; how often long statements meet `query_timeout`.

### Y1: comment on kysely#1990

- **Filed:** [comment](https://github.com/kysely-org/kysely/issues/1990#issuecomment-6249837924) on kysely#1990, 2026-10-18. The issue was closed on 2026-10-17 with 0.29.7.
- **Production relevance (2026-10-26):**
  - **Consequence:** a `ROLLBACK` that never reached PostgreSQL returns the client to the pool inside its transaction; the next transaction's `COMMIT` commits the failed transaction's writes. Affected: `startTransaction()` on 0.29.7 and 0.28.18, and the callback API on every version checked (0.29.6 and 0.29.7 at runtime; 0.27.6 and 0.28.18 by source). The callback API also replaces the caller's error with the rollback's. Silent: the server logs only a warning.
  - **Trigger, `query_timeout` while a statement keeps running:** in production, the event yes; the outcome, unknown. In our runs, real timeouts through pg's documented option, no injection (case 4, 3 of 3; x1qt, 2 of 2 per version; the posted script, 3 of 3 and 3 of 3 from a fresh install). Code shape: ordinary rollback after an error. Evidence: acknowledged: [kysely#2148](https://github.com/kysely-org/kysely/issues/2148) (igalklebanov, MEMBER, 2026-10-19) describes the same five steps and their result, and [#2155](https://github.com/kysely-org/kysely/pull/2155) (merged 2026-10-22, `b506b6390a`) discards the client after a failed rollback.
  - **Trigger, a network stall:** in production, possible. In our runs, a `ROLLBACK` that was sent and answered late (backend stopped with `SIGSTOP`) was data-safe, 6 of 6. A stall on the statement before the `ROLLBACK` was not run on Kysely (aihub-be#1285 ran one on Prisma, through a proxy).
  - **Trigger, an injected `ROLLBACK` failure:** injection only (case 2, x1).
  - **Reproduced on real code:** no.
  - **Searches:** 5 of 10 inspected Kysely `query_timeout` hits (3 of 7 projects) have no server bound. 1 of 10 inspected Kysely `statement_timeout` hits also sets `query_timeout`, at the same value.
  - **Likelihood (judgment):** low. The callback API is exposed in every version checked, but the trigger needs `query_timeout` without a server bound, and a statement or stall about twice that long. The fix is on `master`.
  - **Not established:** any report of the reuse (the production reports on #1990 are about the pool leak); how many Kysely users set `query_timeout`; #2155 was read, not run.

### K3: comment on knex#4709

- **Filed:** [comment](https://github.com/knex/knex/issues/4709#issuecomment-6236885052) on knex#4709, 2026-10-17. The issue, by miszczu-drako, has been open since 2021-10-07. It is tracked under knex's meta-issue #6241.
- **Production relevance (2026-10-26):**
  - **Consequence:** when `BEGIN` or a nested `SAVEPOINT` fails, `await knex.transaction()` resolves with a transaction that is already complete. Its first query fails with "Transaction query already complete", which hides the real error. The handler form rejects with the real error, but only after the handler has run outside any transaction. No data is lost by this alone. Loud but misleading.
  - **Trigger, `BEGIN` on a connection that does not deliver:** in production, yes. knex#4630 (2021-08-20) quotes production client logs: `BEGIN` was logged on the client and never on the server, failed after about 16 minutes, and the application then got "Transaction query already complete". In our runs, not used. Code shape: the documented manual form. Evidence: production, from the reporter's logs, which we did not check.
  - **Trigger, a pooler or server that refuses the `BEGIN`:** in production, yes: supabase/storage (1,339 stars) worked around #4709 in its external-pool mode, next to a retry on the 08P01 error "no more connections allowed" (#459, merged 2024-04-24). In our runs, a server-rejected `BEGIN` with the isolation level `snapshot`, a real error but a misuse: knex documents `snapshot` as mssql-only. Evidence: audit, a downstream project's workaround read at its merge commit.
  - **Trigger, a nested transaction in an aborted PostgreSQL transaction:** in our runs, a real error through the ordinary API (K3-10, `SAVEPOINT` fails with 25P02). Code shape: continuing after a caught error inside a PostgreSQL transaction without a savepoint; not reasonable on PostgreSQL, ordinary on MySQL.
  - **Reproduced on real code:** no.
  - **Searches:** the workaround appears in supabase/storage and two copies of it; no other workaround in the inspected hits.
  - **Likelihood (judgment):** moderate. The manual form is common, and `BEGIN` fails with poolers and broken connections. The result is a misleading error, not silent data loss.
  - **Not established:** how often `BEGIN` fails in practice; whether any handler side effect caused harm.

### K2: knex#6546 and PR #6548

- **Filed:** issue [knex#6546](https://github.com/knex/knex/issues/6546), 2026-10-17, and PR [#6548](https://github.com/knex/knex/pull/6548), 2026-10-18, head `32d6d0d`. No comments or reviews. The PR's CI runs are `action_required`, waiting for a maintainer to approve workflows. knex 3.3.0 is the latest release, and `master` is still its release commit `e25d54bcb7` (2026-06-26).
- **Production relevance (2026-10-26):**
  - **Consequence:** after a top-level `ROLLBACK` or `COMMIT` that never reached the server, knex releases the connection with the transaction open. The failed transaction rejects. The next transaction on that connection gets only a server warning (25001), and its `COMMIT` commits the earlier writes (its `ROLLBACK` discards them). Silent. A plain query on that connection joins the leftover transaction. One failing statement then poisons the connection, and every later use fails with 25P02, which is loud.
  - **Trigger, `query_timeout` while a statement keeps running:** in production, the events (slow statements, lock waits) yes; the combination, unknown. In our runs, real timeouts through pg's documented option, no injection (K2-4, K2-L1, A.1). Code shape: a handler that throws is ordinary. The `COMMIT` variant needs a handler that catches a timed-out statement and returns, which is not reasonable inside an all-or-nothing transaction. Evidence: none on knex; the same mechanism in other libraries.
  - **Trigger, knex's 5 s rollback timer with `query_timeout` above 5 s:** the same production class. knex releases the connection while the `ROLLBACK` is still queued. In our runs, the PR's regression test (`query_timeout` 6000 and a 14 s statement). It falsified the first patch, `e5b339a`: the next transaction committed `doomed`.
  - **Trigger, an injected client-side failure:** injection only (K2-2, K2-6, K2-7).
  - **Reproduced on real code:** no.
  - **Searches:** 1 of 10 inspected knex `query_timeout` hits has the exposed configuration; 2 use knex's own `.timeout(ms, { cancel: true })`, which cancels the statement on the server. 0 of 5 knex configurations with `statement_timeout` also set `query_timeout`.
  - **Likelihood (judgment):** low. It needs `query_timeout` without a shorter server timeout, rare in the knex sample, and a statement or lock wait about twice that long inside a transaction. knex offers a cancelling timeout of its own.
  - **Not established:** any knex report; how many deployments set `query_timeout` outside code.

### T1: typeorm#12976, #12977 and PR #12979

- **Filed:** issues [#12976](https://github.com/typeorm/typeorm/issues/12976) and [#12977](https://github.com/typeorm/typeorm/issues/12977), 2026-10-17, and PR [#12979](https://github.com/typeorm/typeorm/pull/12979) for #12976. Outside PRs: [#12983](https://github.com/typeorm/typeorm/pull/12983) (for #12976) and [#12997](https://github.com/typeorm/typeorm/pull/12997) (for #12977). No maintainer has reviewed any of them.
- **Production relevance (2026-10-26):**
  - **Consequence:**
    - #12976: a failed nested start rolls back the caller's transaction. The caller's later writes autocommit one by one, and the outer call rejects with `TransactionNotStartedError`: loud, with writes committed. If a `beforeTransactionStart` subscriber throws, no `ROLLBACK` is sent and the next unit commits the caller's rows: silent.
    - #12977: after a failed `ROLLBACK TO SAVEPOINT` the depth stays one level too high, and the outer "commit" sends `RELEASE SAVEPOINT`. The outer call resolves although nothing committed; the connection is released inside its transaction, and the next unit commits the outer and inner writes. Silent.
  - **Trigger, a caught error and then a nested `transaction()` (#12976):** in production, unknown. In our runs, a real error (FS3). Code shape: continuing after a caught error inside a PostgreSQL transaction without a savepoint; not reasonable on PostgreSQL, plausible in code written for MySQL. Evidence: none.
  - **Trigger, a missing or colliding savepoint name (#12977):** in production, the trigger occurs: typeorm#11543 and #12308. In our runs, injected by renaming the savepoint. Code shape: concurrent nested transactions on one connection, which a TypeORM maintainer calls invalid. Evidence: the trigger occurs; no report of the consequence.
  - **Trigger, a throwing subscriber:** application errors; our runs used no injection (S1 for #12976; G for #12977).
  - **Trigger, a client-side `ROLLBACK TO SAVEPOINT` failure:** injected. A `query_timeout` path is inferred from pg's source, not run.
  - **Reproduced on real code:** no.
  - **Searches:** `Propagation.NESTED` with typeorm-transactional appears in 16 files. Usage only; the failing path was not searched.
  - **Likelihood (judgment):** low. Each trigger is a misuse, a subscriber error or an injection.
  - **Not established:** whether #11543's or #12308's code left a connection inside a transaction.

### M4: comment on mikro-orm PR #8448

- **Filed:** [comment](https://github.com/mikro-orm/mikro-orm/pull/8448#issuecomment-6249891879) on PR #8448, 2026-10-18. B4nan (MEMBER) opened #8448 on 2026-10-13 and merged it on 2026-10-15 (`ada68f83`). It closed #8447.
- **Production relevance (2026-10-26):**
  - **Consequence:** our claim is that when a `ROLLBACK` fails on a live connection, no `error` event fires, so #8448's listener does nothing.
    - On 7.2.5, which pins Kysely 0.29.6, the connection stays checked out inside its transaction, holding its locks, until the session ends. After `pool.max` such events the pool is starved and `orm.close()` hangs. Silent at first, loud later.
    - On `master`, which pins Kysely 0.29.7 since `d12e730d12` (2026-10-19; dev builds from 7.2.6-dev.17), Kysely releases the client after a failed rollback, so the case becomes Y1's silent reuse. This is source reading and npm metadata, not run.
  - **Trigger, `query_timeout` set through `driverOptions`:** in production, unknown. In our runs, not used through MikroORM. Code shape: an ordinary `em.transactional()`. Evidence: none. Only 5 files matched `query_timeout` with MikroORM, and 2 of them have no server bound.
  - **Trigger, an injected client-side failure:** injection only (T7d).
  - **Reproduced on real code:** no.
  - **Searches:** [open-mercato#7333](https://github.com/open-mercato/open-mercato/issues/7333) (1,883 stars) lists "dropping a still-queryable client whose ROLLBACK failed" as a non-goal, because "the case is hard to reach because the platform sets no `query_timeout`". That is evidence against.
  - **Likelihood (judgment):** low. MikroORM configurations with `query_timeout` are rare, and the dead-connection case that production reports describe is fixed on `master`.
  - **Not established:** any report of this case.

### M2: comment on mikro-orm PR #8462 (fix for #8458)

- **Filed:** [comment](https://github.com/mikro-orm/mikro-orm/pull/8462#issuecomment-6236026353) on PR #8462, 2026-10-17. The PR was merged on 2026-10-22 (`1610b6005b`). The fix first appears in `@mikro-orm/sql` 7.2.6-dev.20. No stable release contains it: npm `latest` is 7.2.5, from 2026-10-09.
- **Production relevance (2026-10-26):**
  - **Consequence:** before the fix, when `ROLLBACK TO SAVEPOINT` fails and the caller catches the inner error, the outer `COMMIT` commits the inner writes. The rollback failure is logged only with `debug` on. Silent.
  - **Trigger, a client-side `ROLLBACK TO SAVEPOINT` failure:** in production, unknown. In our runs and the reporter's, injected. Evidence: none.
  - **Trigger, a throwing `beforeTransactionRollback` subscriber:** an application error; our runs needed no driver fault (scenarios b, g).
  - **Trigger, `query_timeout` inside the nested block:** inferred from pg's source and the verified top-level case. Not run for `ROLLBACK TO SAVEPOINT`.
  - **Code shape:** a nested transaction whose caller catches its failure and continues. MikroORM documents nested savepoints. Judgment: reasonable when the inner unit is self-contained, such as an insert-if-absent. The loss needs an inner unit with more than one write.
  - **Server-side failures are safe on PostgreSQL:** the transaction aborts and the outer `COMMIT` fails. A killed connection was also safe (scenario f).
  - **Reproduced on real code:** no.
  - **Searches:** `TransactionPropagation.NESTED` appears in 91 files, mostly MikroORM's own documentation. Usage only.
  - **Likelihood (judgment):** low. The demonstrated triggers are injection and a throwing subscriber, and the fix is on `master`.
  - **Not established:** a natural client-side failure through MikroORM; MySQL, where a server-side failure does not abort the transaction (not assessed here).

## Details

### Natural triggers, and what our runs used

The table answers which events make a transaction-control statement fail or time out on the client, what state the connection is left in, and which of them our runs used. It draws on pg 8.23.1's `client.js` at `0980cefebe` and on the evidence below.

| Event | What fails on the client | Connection afterwards | Trigger class | Our runs |
| --- | --- | --- | --- | --- |
| pg's `query_timeout` while an earlier statement is still running. The queued statement's own timer removes it from the queue unsent (`client.js` lines 702–722) | Any queued `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` or `ROLLBACK TO SAVEPOINT` | Usable to pg; the transaction is still open | A real production event: a client deadline over a slow statement or a lock wait | K2 and Y1: real timeouts, no injection |
| A network stall without a socket error, longer than about twice `query_timeout` | The same | Usable to pg; open if the server finished the statement | A real production event | Not run by us. aihub-be#1285 ran one through a proxy, on Prisma. knex#4630 saw `BEGIN` fail this way |
| `query_timeout` on a `ROLLBACK` that was sent and is answered late | `ROLLBACK` | Usable; the next borrower waits behind it | A real production event | K2-5 and Y1 5a/5b, backend stopped with `SIGSTOP`: data-safe |
| A server `statement_timeout` or `lock_timeout` | The long statement, not the control statement | Aborted; the `ROLLBACK` then succeeds | A real production event | Not run in this group |
| `idle_in_transaction_session_timeout` | The next statement: the server has closed the session (25P03) | Dead; pg-pool discards it on release | A real production event | MikroORM T7e (as a mitigation) |
| A restart, failover, administrator termination, or network loss with an error | Any | Dead; discarded by pg-pool and knex; leaked by Kysely 0.29.6 controlled transactions | A real production event | Y1 case 3, knex L3-1, the M4 listener test: data-safe |
| A pooler or server at its connection limits: a connection-limit error (08P01 "no more connections allowed"), or a client queued past the pooler's wait limit | `BEGIN`, the first statement of a checkout | Depends on the pooler | A real production event | Not run. supabase/storage#459 retries 08P01 and works around #4709. OneUptime#4650 sets PgBouncer's `query_wait_timeout` below its client timeout |
| A missing or colliding savepoint name (3B001) | `ROLLBACK TO` or `RELEASE SAVEPOINT` | Aborted on PostgreSQL | Application misuse (concurrent nested transactions) | T1: injected by renaming |
| An aborted transaction (25P02) | A nested `SAVEPOINT` | Aborted | A real error after a caught error | K3-10 and T1 FS3: real errors |
| A throwing subscriber or hook | TypeORM's start and rollback hooks; MikroORM's `beforeTransactionRollback` | The server is not involved | An application error | M2 (b), T1 S1 and G: no injection |
| An invalid isolation level | `BEGIN` | Idle | Application misuse | K3 (`snapshot`); T1 S0 |

**Timing.** For the first row, the earlier statement must still be running when the queued statement's own timer fires. When the rollback follows the timeout at once, that is about twice the timeout after the statement started. This is source reading of pg 8.23.1, and it agrees with our runs: a 3 s statement with a 1 s timeout (K2), 2.5 s with 1 s (Y1), and 14 s with 6 s (the #6548 test).

**A server timeout at or below `query_timeout`.** Judgment from source reading, not run: then the server ends a long statement first, and the queued `ROLLBACK` is sent before its own timer fires. A network stall still reaches the first row: aihub-be#1285 had `statement_timeout` 4 s below `query_timeout` 5 s.

**PgBouncer** does not pass a `statement_timeout` given at connect on to the server, so projects behind it fall back on `query_timeout`. OneUptime#4650 records this ("PgBouncer drops the `statement_timeout` the app asks for at connect"), and ever-gauzy's shared settings note that "a transaction-mode PgBouncer refuses them as startup parameters". PgBouncer's own documentation was not read.

### Configurations: how common is the trigger's setup?

Code search counts files where the terms co-occur, not configurations. Each sample below was read at its commit. The failing shape is pg's `query_timeout` with no server-side `statement_timeout` at or below it in the same file.

**`query_timeout` samples:** 12 of 35 inspected hits, in 9 projects, have the failing shape.

- **knex** (`query_timeout knex client pg`, 214 files): 1 of 10.
  - Failing shape: snapshot-labs/checkpoint `src/knex.ts` @ `0fa975c635`, lines 64–79: `query_timeout: 60_000`, no `statement_timeout`.
  - Handled with knex's cancelling timeout: teableio/teable `apps/nestjs-backend/src/global/data-db-client-manager.service.ts` @ `feae0c71ca`, lines 189–215 and 715; supertokens/supertokens-core `migration_scripts/to_version_7_0_12/index.js` @ `8703a12c21`, lines 28 and 52–63.
  - Error classification only: ever-co/ever-gauzy `packages/core/src/lib/core/errors/database-unavailable.ts` @ `1142f47a3d`, lines 64–66. Its shared settings, `packages/config/src/lib/database.ts` lines 105–143, set only opt-in server-side timeouts.
  - Not configurations: type declarations (parkdigy/express-template, feasibleone/blong); knex's changelogs (2); pgkit's documentation; River's README, which suggests `query_timeout` against dead sockets.
- **Kysely** (`query_timeout PostgresDialect kysely`, 86 files): 5 of 10 hits, 3 of 7 projects.
  - Failing shape:
    - TimIsOverpowered/archive `src/db/meta-client.ts` line 43 and `src/db/streamer-client.ts` lines 62–63 @ `3d5788f9b9`;
    - proompteng/lab `services/agents/src/server/db.ts` lines 261–279 and `services/jangar/src/server/db.ts` lines 654–678 @ `50320283ea` (20 s default);
    - stephancill/farcaster-shuttle `src/shuttle/db.ts` @ `1bcbf74c61`, lines 152–153 (1,000,000 ms).
  - Equal values: fmenis/fastify-core-starter `src/lib/kysely.ts` @ `cb73c93958`, lines 13–15; wenerme/wode `packages/wener-ai/src/mcp/sql/utils.ts` @ `6fc4704513`, lines 44–46; jedmund/siero-bot `src/services/connection.ts` @ `354e934ef2`, lines 23–25; HamedMP/matrix-os `packages/gateway/src/jev/owned-maintenance.ts` @ `f875f29ea3`, lines 6–26.
  - Handled: HamedMP/matrix-os `packages/gateway/src/sites/bootstrap.ts` @ `f875f29ea3`, lines 8–18. Lock 2 s, statement 5 s, query 7.5 s, and it discards the socket on a timeout: "pg's query_timeout rejects the read without cancelling PostgreSQL".
- **TypeORM** (`query_timeout typeorm extra postgres`, 486 files): 4 of 10 hits, 3 of 6 projects.
  - Failing shape:
    - twentyhq/twenty `packages/twenty-server/src/database/typeorm/core/core.datasource.ts` @ `35d68da9b0`, lines 80–84: `query_timeout` defaults to 10000, and the file sets no `statement_timeout`. The hit was `.../2-46/utils/create-core-index-concurrently.util.ts`, lines 3–31;
    - RuSS-B/nestjs-common-tools `src/typeorm/config/postgres-typeorm-options.factory.ts` line 89 and its spec, lines 26–28 @ `a2c74728cc`;
    - Nicolas-Olmos-Wompi/checkout-technical-challenge `server/src/adapter/out/postgres/typeorm.config.ts` @ `2ed8d8b27c`, lines 39–44: query 5 s below statement 10 s.
  - Handled: OneUptime/oneuptime `packages/Common/Server/Infrastructure/Postgres/DataSourceOptions.ts` and `CancelOnTimeoutClient.ts` @ `4c3d8397b9`, and a migration that notes "When the client gives up first the server keeps executing".
  - Advises against `query_timeout`: bettaku/engawa's documentation (2 hits): "This only gives up on the client side; the query keeps running on the server. Prefer `statement_timeout`".
  - Not judged: Davison27/ledgerly `apps/back/src/database/typeorm.config.ts` @ `45d74dcea0`, lines 23–25; both values come from runtime configuration.
- **MikroORM** (`query_timeout driverOptions mikro-orm`, 5 files): 2 of 5.
  - Failing shape: davidloiret/agentic-design `backend/src/mikro-orm.config.ts` @ `a74b58b994`, lines 26–28; fega-kt/backend-mikroorm `libs/core-shared/config/mikro-orm.config.ts` @ `74d0360661`, lines 22–23 (120 s, against dead sockets).
  - Equal values: jbl428/study-note (3 s); almerav/merged-spaceport (30 s defaults); mdavila-2001/mantra-core-health-api (a test).

**`statement_timeout` samples.** Server-side timeouts are the common choice, and few of these configurations also set `query_timeout`:

- knex (878 files): 0 of 5 knex configurations: NangoHQ/nango `packages/scheduler/lib/db/client.ts` @ `8eb7fa72b0`, and four Nearblocks indexers @ `42f8ded092`, 60 s. The other 5 hits are type declarations, a lint fixture and supabase/storage's raw pg code.
- Kysely (220 files): 1 of 10, fastify-core-starter, at equal values.
- TypeORM (122 files): 2 of 8 projects, OneUptime (handled) and the Wompi challenge.
- MikroORM (268 files): 1 of 6 configurations, jbl428 (equal). The other hits are documentation, and one Python file.
- TypeORM with `idle_in_transaction_session_timeout` (589 files): 0 of 10 hits also set `query_timeout`.

**Other evidence against exposure:**

- Directus (38,638 stars, knex) could not pass `query_timeout` or `statement_timeout` through its environment configuration. [directus#23241](https://github.com/directus/directus/issues/23241) has been open since 2024-08-07.
- A Drizzle user wrote, "We run server-side `statement_timeout`/`lock_timeout` rather than `query_timeout`" ([drizzle#6120](https://github.com/drizzle-team/drizzle-orm/pull/6120), 2026-10-12).

**Judgment.** Of the 35 inspected `query_timeout` hits:

- 12, in 9 projects, have the failing shape;
- 7 set an equal server timeout;
- 8 handle the timeout or advise against it (OneUptime ×3, matrix-os, teable, supertokens, engawa's documentation ×2);
- 8 are not configurations, or were not judged.

In the knex and Kysely searches, whose terms are parallel, `query_timeout` co-occurs in fewer files than `statement_timeout`: 214 against 878, and 86 against 220. The TypeORM and MikroORM totals use different terms and are not comparable. The exposed setups are a minority, but they include a large project (Twenty), and PgBouncer pushes projects toward them.

### Symptom reports, and whether their mechanism matches

| Symptom | Report | Situation | Mechanism |
| --- | --- | --- | --- |
| A failed request's writes committed by the next borrower | [OneUptime#4650](https://github.com/OneUptime/oneuptime/pull/4650), simlarsen (CONTRIBUTOR), merged 2026-10-10; 7,761 stars | Audit. The project's real-Postgres suite failed 5 of 9 tests on the old client. No incident stated | **Ours** (T2, and K2's and Y1's class): `save()`'s `ROLLBACK` "ran out of time too and node-postgres dropped it unsent", and "the next request ... committed the first request's write". `query_timeout` 35 s; PgBouncer dropped the startup `statement_timeout` |
| The same | [kysely#2148](https://github.com/kysely-org/kysely/issues/2148), igalklebanov (MEMBER), 2026-10-19 | A maintainer's analysis, reproducing the busy client 3 of 3 | **Ours** (Y1). Fixed by #2155 |
| The same | [aihub-be#1285](https://github.com/AiHub-Ecosystem/aihub-be/issues/1285), COLLABORATOR, 2026-10-26; 0 stars | Audit through a proxy hang: "not a production incident" | **Ours**, on Prisma with `@prisma/adapter-pg` 7.10.1, with `statement_timeout` below `query_timeout`; triggered by a stall |
| The same | [metasheet2#6217](https://github.com/zensgit/metasheet2/issues/6217), COLLABORATOR, 2026-10-01; 0 stars | Audit on a disposable PostgreSQL 16 | **Ours**, in the project's own pg pool wrapper (`query_timeout` 30 s by default) |
| Pool leak, plus reuse after a failed `ROLLBACK` | [drizzle#6114](https://github.com/drizzle-team/drizzle-orm/issues/6114) and [#6120](https://github.com/drizzle-team/drizzle-orm/pull/6120); 36,145 stars | Audit. One user runs the fix "in production as a pnpm patch"; another found it "in review". Fixed in 1.0.0-rc.5 (COLLABORATOR, 2026-10-21) | **Ours**, in Drizzle's own code: "run inside the leftover transaction" |
| Pool starvation after failed control statements | kysely#1990: YohoCX (2026-08-19), nuzayets (2026-10-08), rolandvar (2026-10-12), all NONE | Production claims without logs | Kysely 0.29.6's leak, mostly through dropped connections; not reuse. Fixed in 0.29.7 |
| The same | [mikro-orm#8447](https://github.com/mikro-orm/mikro-orm/issues/8447), rolandvar (NONE), 2026-10-12 | A production claim ("the platform (Cloud Run) occasionally resets all outbound connections"), with a reproduction | The same leak; prompted #8448 |
| The same | [open-mercato#7333](https://github.com/open-mercato/open-mercato/issues/7333), CONTRIBUTOR, 2026-10-13; 1,883 stars | Audit: "No production report of pool starvation from this cause is known" | The same leak, triggered by its own 120 s `idle_in_transaction_session_timeout` |
| `BEGIN` fails, and the application sees "Transaction query already complete" | [knex#4630](https://github.com/knex/knex/issues/4630), miszczu-drako (NONE), 2021-08-20 | Production client logs quoted (not checked by us) | **K3's symptom.** A broken connection never delivered `BEGIN` |
| A savepoint missing at `ROLLBACK TO SAVEPOINT` (3B001) | [typeorm#11543](https://github.com/typeorm/typeorm/issues/11543), 2025-06-22; [#12308](https://github.com/typeorm/typeorm/issues/12308), 2026-04-04 | Structured logs from a bundled application; "In my production codebase I have removed the use of the SAVEPOINT logic" | T1's trigger. The consequence is not reported. A TypeORM maintainer (alumni, COLLABORATOR) closed #12308 as not planned: "You can run transactions in parallel … **But not nested ones**" |
| Connections "idle in transaction" holding a pool slot | kodus-ai (1,527 stars), `libs/core/infrastructure/database/typeorm/typeORM.factory.ts` @ `c37c055686`, lines 108–112 | A code comment: "A transaction left open by a crashed handler used to hold row locks + a pool slot until the RDS `idle_in_transaction_session_timeout` (10min) kicked in" | Symptom only; the mechanism is not stated |
| The same | [vendure#5649](https://github.com/vendurehq/vendure/issues/5649), 2026-10-23; [mikro-orm#7456](https://github.com/mikro-orm/mikro-orm/issues/7456), 2026-04-01 | A pool deadlock through a shared cache refresh; a migration hang after an upgrade | Different mechanisms |
| "there is already a transaction in progress" | None in knex, Kysely or MikroORM. typeorm#6067 is about Expo with SQLite | — | No match. The warning appears only in server logs, so its absence from issue trackers is weak evidence |
| "current transaction is aborted" in unrelated requests | None matching. TypeORM's hits are schema-sync errors | — | No match |
| "Transaction already started for the given connection" (TypeORM) | #1884, #8527, #646 | — | Different: SQLite's single connection, clearing a database inside a transaction, migrations |

The audits that describe the reuse mechanism are dated 2026-08 to 2026-10. None reports a production incident.

### K2 details

- **How it was reproduced without injection.**
  - pg's documented `query_timeout: 1000` was set, and the transaction ran `select pg_sleep(3)`. The statement failed on the client at 1 s and kept running on the server.
  - The `ROLLBACK` (or, in the catch-and-return variant, the `COMMIT`) queued behind it in pg's client queue. At 2 s its own timer removed it unsent.
  - The server log has no `ROLLBACK` or `COMMIT`, and the next `BEGIN` logs `WARNING: there is already a transaction in progress`.
  - Records: nest-adonis-spike `docs/knex-root-cause-review.md` §3 (K2-4, K2-L1) and addendum A.1. The recorded output is in `docs/knex-root-cause-review/recorded/upstream-knex-open-transaction-reuse.txt`, with its `.server-log.txt` (branches `docs/kysely-y1-review` and `docs/lucid-isolation-level-fix`).
- **The release path:** knex `lib/execution/transaction.js` @ `e25d54bcb7`.
  - `Transaction.query()` swallows the failure into `executionPromise` (lines 165–195).
  - `acquireConnection()` releases in `finally`, unconditionally (lines 263–280).
  - `rollback()` gives up after 5 s (lines 142–151).
- **The patch `e5b339a`, falsified.** knex's 5 s timer releases the connection while the `ROLLBACK` is still queued. With `query_timeout` above 5 s, the status check at the failure point (`e5b339a`) is too late: the next borrower already holds the connection.
  - The regression test `test/integration2/transaction/failed-transaction-end-rollback-timer.spec.js` @ `32d6d0d1f4` (lines 24–39 and 67–87) uses `query_timeout` 6000 and `pg_sleep(14)`.
  - It fails 2 of 2 with the behaviour of 3.3.0 or of `e5b339a` restored, and passes 2 of 2 with `6982698`. Record: nest-adonis-spike `docs/knex-root-cause-review/fixes/6546-fix-report.md`, line 70 (branch `docs/lucid-isolation-level-fix`). The PR body says the same.
- **Related occurrence.** knex#4630 (2021-10-04 comment): in a performance test with `query_timeout: 5000`, "184 transactions in a row failing on BEGIN" on one broken pooled connection, which knex kept handing out. That is reuse after client-side failures, but on a dead connection, so no data was affected.
- **Evidence against:** knex disposes connections that report an error (review L3-1). Two inspected projects use knex's cancelling `.timeout()`. Directus could not set `query_timeout` through its environment.

### K3 details: the host reporter and the collaborator

- **The reporter**, miszczu-drako (NONE), 2021-10-07: knex 0.95.10, pg 8.7.1, PostgreSQL 10. "I have been playing around with `query_timeout` recently."
  - The issue's reproduction forced a 1 ms timeout on `BEGIN` by editing `node_modules/pg/lib/client.js`. That is injection.
  - The same reporter's knex#4630 (2021-08-20) is a production report: "It happens once per thousands of requests", "We see it only on our production environment".
  - Its 2021-10-04 comment reports the 184 consecutive `BEGIN; - Query read timeout` failures.
  - Its 2025-10-20 comment gives the workaround: `statement_timeout: 4000`, `query_timeout: 4500`, `idle_in_transaction_session_timeout: 2000`, `keepAlive`, and pool `min` equal to `max`.
- **The collaborator**, mercmobily (COLLABORATOR), 2025-10-18, posted two comments.
  - The first links the issue to meta-issue #6241. The same 152-character text was posted on #4630, #5434 and #4423 within 4 seconds.
  - The second agrees that "The first version is clearly buggy", and says both forms should throw and the connection should be released. Similar long replies went to the same four issues within 23 seconds.
  - Judgment: acknowledgment during a triage pass, not an investigation. No fix was proposed.
- **supabase/storage#459** (fenos, CONTRIBUTOR, merged 2024-04-24; 1,339 stars): "When there is an error during the creation of a transaction, there is a bug in knex https://github.com/knex/knex/issues/4709 where the error is not consistent and propagated."
  - The code is `src/database/connection.ts` @ `2ee8828d4d`, lines 160–213: a retry on 08P01 "no more connections allowed" (lines 167–176), and the workaround at lines 192–201.
  - The workaround is copied in two other repositories, vvaldik/storage-api and arraypad/supabase-storage.
  - supabase/storage no longer depends on knex at `79f6853a0c`.

### Y1 details: the 13 comments on kysely#1990

Kysely has 14,304 stars. Kysely itself had about 13.3 million npm downloads in the week of 2026-10-16 to 2026-10-22. None of the production claims below quotes logs, and none describes reuse.

| # | Commenter (association), date | Situation | Mechanism |
| --- | --- | --- | --- |
| Body | YohoCX (NONE), 2026-08-19 | Production claim: "I got this issue on production, having pool starvation". Analysis and a patch; the reproduction uses a mock driver, with no database | The leak after a failed `BEGIN`, `COMMIT` or `ROLLBACK` (0.29.5) |
| 1 | YohoCX (NONE), 2026-08-19 | Production claim: "I am running MikroORM with kysely query builder, and issue is critical running on prod" | The same leak |
| 2 | dylanpulver (NONE), 2026-08-19 | Asks to be assigned; restates the fix. Later unassigned by a maintainer: "Activity suggests low/no human involvement contribution farming" | — |
| 3 | koskimas (MEMBER), 2026-08-23 | Maintainer: assigns | — |
| 4 | hacker-cb (NONE), 2026-09-08 | Test: a reproduction with `pg_terminate_backend` and pg-pool's counters on 0.29.5. It notes the leak needs no timeout, and that MikroORM pins Kysely exactly | The leak, through dead connections |
| 5 | koskimas (MEMBER), 2026-09-13 | Maintainer: asks about progress | — |
| 6 | igalklebanov (MEMBER), 2026-09-13 | Maintainer: unassigns comment 2's author | — |
| 7 | koskimas (MEMBER), 2026-09-16 | Maintainer: a remark about bots | — |
| 8 | igalklebanov (MEMBER), 2026-09-16 | Maintainer: a remark | — |
| 9 | nuzayets (NONE), 2026-10-08 | Production claim: "We hit this in prod too", with no details | Unspecified; the issue's leak |
| 10 | vkartaviy (NONE), 2026-10-11 | Review and test: reads `master` `fcc56f52` and #2081, and reproduces with `pg_terminate_backend` on 0.29.6. Suggests `release(true)` | The leak after a failed `ROLLBACK` on a dead connection |
| 11 | rolandvar (NONE), 2026-10-12 | Production claim (Kysely 0.29.6 through MikroORM 7, "behind a pooler"; "The platform occasionally resets every outbound connection of an instance at once"), and a test of a `finally` patch. Notes that `release(true)` is untested for a still-queryable connection | The leak, through dead connections. Also filed mikro-orm#8447 |
| 12 | igalklebanov (MEMBER), 2026-10-17 | Maintainer: closes with 0.29.7 | — |
| 13 | KevinBlakeLopez (NONE), 2026-10-18 | Ours: `query_timeout` runs | Reuse after a `ROLLBACK` that was never sent |

- **Our claim and its basis:** nest-adonis-spike `docs/kysely-y1-review.md` §1–§5 (branch `docs/kysely-y1-review`), and `docs/kysely-connection-recovery-comment-draft.md`, comment 1.
  - The doomed state came from `query_timeout`, with no injection: case 4 on 0.29.7 (3 runs) and on 0.28.18 (1 run); x1qt (callback API) on 0.29.6 and 0.29.7 (2 runs each).
  - The source agrees: `src/kysely.ts` @ `ac876c212c` releases in `finally` after a failed rollback (lines 1089–1101). The callback form calls `rollbackTransaction` inside the connection provider (lines 911–929), and the provider's `finally` then releases the client (the review cites the published 0.29.7's `driver/default-connection-provider.js`, lines 12–13). The PostgreSQL driver releases with no argument (`postgres-driver.ts` lines 284–286).
- **Maintainers' position.** On #2136 (2026-10-13), igalklebanov wrote that "There are different scenarios where a rollback might fail, but the transaction and session are healthy", and "For now, we'll leave the stuff above to dialects' drivers". #2155 then discards the client in the PostgreSQL driver. It is in `PostgresDriver.rollbackTransaction`, which both forms call; that is source reading, not run.
- **Fix status:** npm `latest` is 0.29.7 and `release-0.28` is 0.28.18, read on 2026-10-26. No release contains #2155.

### M4 details: what prompted #8448

- **mikro-orm#8447**, rolandvar (NONE), 2026-10-12: "Connection dropped during a transaction leaves the pool slot checked out (kysely#1990); orm.close() never resolves". "We hit this in production: the platform (Cloud Run) occasionally resets all outbound connections of an instance at once". It includes a reproduction with `pg_terminate_backend` and a measurement with Kysely patched locally.
- **YuraD (NONE), comment on #8447, 2026-10-14:** an independent confirmation on 7.2.5, and a third trigger: "ROLLBACK rejected after a failing callback: the caller correctly gets the callback's original error, but the client still leaks". Their workaround wraps `client.query` and calls `client.release(err)` when a transaction-control statement is rejected. These are tests, not production.
- **#8448's listener:** `packages/postgresql/src/PostgreSqlConnection.ts` @ `9688b6ae30`, lines 64–92. It acts only on a client's `error` event.
- **Fix status, checked by reading the published tarballs, not running them:** the listener is present in `@mikro-orm/postgresql` 7.2.6-dev.13, published 20 minutes after the merge, and absent from 7.2.5. `@mikro-orm/sql` 7.2.5 pins Kysely 0.29.6; 7.2.6-dev.17 and later pin 0.29.7 (`d12e730d12`, 2026-10-19).
- **Our evidence:** nest-adonis-spike `docs/mikroorm-postgres-verification.md` T7d (fault-injected) and T7e, and `docs/kysely-connection-recovery-comment-draft.md`, comment 2.

### M2 details: the reporter and the release

- **#8458**, YuraD (NONE), 2026-10-14: MikroORM 7.2.5, Kysely 0.29.6, pg 8.23.1, PostgreSQL 17.7. "To make `ROLLBACK TO SAVEPOINT` fail deterministically, we injected an error for that statement at the pg client". "We have not yet seen a natural server-side failure that leaves the transaction usable … So this is a correctness gap in the error handling, not a frequent production event."
- **#8462**, lazerg (CONTRIBUTOR), merged by B4nan on 2026-10-22.
  - The merged head is `d3d3b5da`. It adds B4nan's test commit `895e134ebd` and a merge of `master` to the head we validated, `272a1081`; the two fix commits are unchanged.
  - The guard is in `@mikro-orm/sql` 7.2.6-dev.20's tarball, and not in dev.19 or 7.2.5.
  - Affected: stable releases up to 7.2.5. 6.x was not checked.
- **Our evidence:** nest-adonis-spike `docs/mikroorm-pr-8462-validation.md` (an uncommitted working copy) and `docs/mikroorm-8458-comment-draft.md`.

### T1 details

- **Source:** TypeORM `packages/typeorm/src/entity-manager/EntityManager.ts` @ `fe92394287`, lines 157–172, rolls back whenever `startTransaction()` throws. `PostgresQueryRunner.ts`, lines 231–246, moves the depth only after the rollback succeeds.
- **Activity:** neither file changed on `master` in a way that affects these paths: `EntityManager.ts` has no commits since 2026-10-01, and `PostgresQueryRunner.ts` has one, `dca49fd1d7`, about query timing.
- **Our evidence:** nest-adonis-spike `docs/typeorm-savepoint-depth-fix/HANDOFF.md` and `design-review.md` (uncommitted working copies), and `runs/r2-tx6-master.txt`.
- **The outside PRs:** both are by Asadshah7950 (NONE). #12983 was labelled a possible duplicate of #12979 by a bot. Neither has a maintainer review.

### T2 details

- **Source:** TypeORM @ `fe92394287`.
  - `PostgresQueryRunner.release()` (lines 165–166) returns the client with no error argument.
  - `EntityPersistExecutor.ts` (`save()`, lines 199–212) and `EntityManager.ts` (lines 157–172) swallow a rollback error, then release.
  - The documented manual pattern, `docs/docs/transactions.mdx` lines 276–289, rolls back in `catch` and releases in `finally`. That puts the duty to roll back on the caller.
- **Inspected manual-transaction hits** (`createQueryRunner startTransaction commitTransaction release finally`, 16,064 files, 10 projects):
  - **The documented pattern,** 8: t10d/kingdom-node-sdk-orm, Victor-Palha/oban-ts, sirhCC/CICD-Pipeline-Analyzer, Dontress/legtito-middlewave, harryWonder/softalliance_movies, Henry25t/API-SEECODE, ztmbuilds/event-management-system and ory/polis (`npm/src/db/sql/sql.ts` @ `e13ed6541e`, lines 367–392).
  - **No rollback when `COMMIT` fails,** 1: paraskumar2003/nest-js-everything `src/db/db.service.ts` @ `2587a7fb3b`, lines 33–51.
  - **Refuses to release an active transaction** (it leaks the connection instead), 1: mohamed7-dev/myportfolio `orm/transaction-manager.ts` @ `4470e269ff`, lines 99–102.
- **OneUptime's code:** `CancelOnTimeoutClient.ts` @ `4c3d8397b9`, lines 1–45. Its path's history starts at `b7ff38f4ad` (2026-10-10).
  - Its header states the mechanism.
  - The fix cancels a timed-out statement on the server, and closes the connection instead of returning it.
  - The PR also sets PgBouncer's `query_wait_timeout` below the application's timeout.
- **Our evidence:** nest-adonis-spike `docs/typeorm-objection-sequelize-assessment.md` §4.3 and §5.2: TR1d, TR1d3 (fault-injected), and TR1d2 (a real termination, safe).

### Discrepancies with our records

- **M4's posted sentence is now version-dependent.** "Without that timeout, the slot is held for the life of the process" holds for MikroORM 7.2.5. It does not hold for `master` and the dev builds since 2026-10-19, which pin Kysely 0.29.7: there the slot is released with its transaction open (source reading).
- **Our K3 draft's note on the trigger is imprecise.** nest-adonis-spike `docs/knex-4709-comment-draft.md` says "The reporter used `pg`'s `query_timeout`". The reproduction in #4709 patched pg's client to force the timeout on `BEGIN`. The natural occurrences are in #4630.
- **The T2 filing date.** PPCS `docs/upstream-submissions.md` said T2 was submitted on 2026-10-18. GitHub shows #12978 created at 2026-10-17 18:32 UTC. Corrected in the same change as this page.
- **Three links that cannot resolve.** PPCS `docs/upstream-submissions.md` links three nest-adonis-spike files on branch `docs/lucid-isolation-level-fix`: `docs/mikroorm-pr-8462-validation.md`, `docs/typeorm-savepoint-depth-fix/HANDOFF.md` and `docs/typeorm-savepoint-depth-fix/design-review.md`. They are not on any branch; they exist only as uncommitted working copies.
- **A superseded statement.** nest-adonis-spike `docs/mikroorm-postgres-verification.md` (2026-10-14) calls a failure that "loses the statement yet leaves the connection usable … rare in practice". The knex and Kysely runs of 2026-10-17 then showed `query_timeout` doing exactly that with no injection.

## Method

Read-only GitHub searches, run on 2026-10-26 between 15:47 and 16:00 UTC through a shared paced wrapper around `gh api search/issues` and `search/code`. The queries are in `searches/q-batch1.json` to `q-batch3.json`: 36 issue searches and 21 code searches. `searches/searches.txt` lists each query with its total and the hits it showed, and `searches/raw/` holds the raw results.

95 code-search hits were read at their commits through the contents API, and they are the basis of every "k of n". Other code results were judged only from the returned fragments, and no count uses them.

Issues, pull requests, timelines, releases and source files were read through `gh api` at the commits cited. Package versions, dependency pins and publish times come from the npm registry. Published MikroORM tarballs were downloaded and searched for the fix markers, and not run: `@mikro-orm/sql` 7.2.5, 7.2.6-dev.19 and dev.20, and `@mikro-orm/postgresql` 7.2.5 and 7.2.6-dev.13 (dev.12 did not download).

A search that finds nothing is a result with a scope, not proof of absence. "None found" above means none in these 57 queries.
