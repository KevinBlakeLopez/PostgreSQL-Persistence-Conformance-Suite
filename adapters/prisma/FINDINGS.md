# Prisma transaction recovery, PPCS run 2026-10-21T14-10-47Z-148b69

Prisma Client 7.10.1, `@prisma/adapter-pg` 7.10.1, pg 8.23.1, pg-pool 3.14.0, Node.js v24.14.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Suite revision `4df66a5` plus this adapter. The recording's adapter digest is the adapter as it ran; this file and `README.md` were written after that run. Three repetitions agreed. CTL-01 and pg-control held their gates. No Prisma result was gated.

Native mode passes a `pg.Pool` to `new PrismaPg(pool)` and calls `prisma.$transaction(async (tx) => ...)`. Nested work is `tx.$transaction()`. Writes are `$executeRaw`. The pool max is the case's `pool_max` (1 on every case this adapter ran). Prisma's interactive-transaction defaults stay in place: `timeout` 5000 ms, `maxWait` 2000 ms. None of these cases hit them. The adapter does not read the command tag, discard a connection, or add a rollback. Category C is a client-side injection in `pg.Client.prototype.query`, fired once. Category B is the runner's `pg_terminate_backend`. A resolved `$transaction()` is reported committed. A rejection with the callback's own error is reported rolled back. Any other rejection is reported failed.

`trace_sees_framework_pg` is true. `external_pool` is true. The adapter and `@prisma/adapter-pg` resolve one `pg` module, and `PrismaPg` kept the pool this adapter constructed.

The query compiler is the client engine (`compilerBuild = "fast"`). `$executeRaw` and the transaction manager's `COMMIT` / `ROLLBACK` go to the driver adapter as SQL. They do not pass through the query compiler. The compiler was not the layer that saw, or failed to see, the command tag on `COMMIT`.

## Where the calls go

Installed `@prisma/client@7.10.1`, `runtime/client.mjs`:

`_transactionWithCallback` starts a transaction, runs the callback, and on return calls `transaction("commit")`. If the callback throws, it calls `transaction("rollback")` and rethrows that error. A nested call sets `newTxId` from the transaction client. It does not write that id back onto the options object.

The transaction manager's close path, for an adapter with `usePhantomQuery: false` (what `@prisma/adapter-pg` sets), sends `{ sql: "COMMIT" }` through `executeRaw` and, if that promise resolves, calls `transaction.commit()`. If `executeRaw` rejects, it calls `transaction.rollback()` and rethrows. A top-level rollback sends `{ sql: "ROLLBACK" }` and then always calls `transaction.rollback()`. A nested rollback calls `rollbackToSavepoint` and then `releaseSavepoint`. A nested commit calls `releaseSavepoint` only.

Installed `@prisma/adapter-pg@7.10.1`, `dist/index.mjs` (the ESM build this adapter's `import` loads; the CommonJS `dist/index.js` has the same classes):

`PgQueryable.executeRaw` returns `result.rowCount`. It does not read `result.command`. `PgTransaction.commit` and `PgTransaction.rollback` call `client.release()` with no argument. `startTransaction` checks a client out, listens for `'error'` on it, sends `BEGIN`, and if an isolation level was passed sends `SET TRANSACTION ISOLATION LEVEL …`. Savepoints are `SAVEPOINT prisma_sp_N`, `ROLLBACK TO SAVEPOINT prisma_sp_N`, and `RELEASE SAVEPOINT prisma_sp_N`.

pg-pool 3.14.0 `_release` removes the client when `release` is called with an error, or when the client is not queryable. A release with no error returns the client to the idle list. It does not look at the transaction state.

`PrismaPg.connect` listens for idle-client `'error'` events. The checked-out listener is separate and is removed before `release()`. That listener is why the category B cases returned an API result instead of killing the process.

## Cases

| Case | Fault | Prisma reported | PostgreSQL | Invariant |
| --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed | xid 13307 committed; marker visible. Command tag `COMMIT` | CTL-01.1 held |
| `CTL-01.rollback` | none | rolled back (callback error) | xid 13319 aborted; marker absent. Last statement `ROLLBACK` | CTL-01.2 held |
| `TX-01A.caught-error-then-commit` | A, caught `23505` (`P2010`) | committed | xid 13331 aborted before the end and after exit; marker absent. After the API returned the session was idle and its last statement was `COMMIT`. The reply was command tag `ROLLBACK` | TX-01A.1 failed. Mechanism exercised. 3 of 3 |
| `TX-01B.conn-lost-before-commit` | B | failed | xid 13343 aborted; marker absent. Trace: `COMMIT`, then `Client has encountered a connection error and is not queryable` | TX-01B.1 held |
| `TX-01B.commit-reply-discarded` | D, reply-lost, fired once | failed | xid 13355 committed; marker visible. The reply was discarded in the driver | TX-01B.1 held. TX-01B.2 not exercised |
| `TX-02.savepoint-rollback-not-sent` | C, client-reject, fired once | committed. The outer callback caught the nested error and returned | xid 13367 committed; both markers visible. Command tag `COMMIT`. The withheld statement was `ROLLBACK TO SAVEPOINT prisma_sp_0` | TX-02.1 failed. TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` | C, rewrite, reply `3B001`, fired once | committed | xid 13382 aborted; neither marker visible. Session idle. Last statement `COMMIT`. Command tag `ROLLBACK` | TX-02.1 failed. TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` | B | failed | xid 13397 aborted; neither marker visible. Session closed | TX-02.1 held. TX-02.2 held |
| `TX-03.rollback-not-sent` | C, client-reject, fired once | rolled back (the callback's error). Unit 2 reported committed after 39 ms | unit 1 was in progress at `after-unit1` and was committed by unit 2. Both markers visible, both xmin 13412. Same backend pid 1183488 | TX-03.1 failed. TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` | C, client-reject after `23505` | rolled back. Unit 2 reported failed after 1 ms (`P2039`, SQLSTATE `25P02`) | xid 13424 aborted; doomed absent. At `after-unit1` the session was idle in transaction (aborted). The next statement was `BEGIN` on the same backend (pid 1183619) | TX-03.1 held. TX-03.2 failed |
| `TX-03.conn-lost-in-transaction` | B | rolled back (the callback's error). Unit 2 committed after 44 ms | unit 1 xid 13436 aborted; unit 2 xid 13437 committed on a new backend (pid 1183720, then pid 1183741) | TX-03.1 held. TX-03.2 held |
| `TX-04.nested-failure-contained` | none | committed | xid 13451 committed; outer visible; inner absent. Trace: `ROLLBACK TO SAVEPOINT prisma_sp_0`, `RELEASE SAVEPOINT prisma_sp_0`, `COMMIT` tag `COMMIT` | TX-04.1 held |
| `TX-04.nested-released-outer-rollback` | none | rolled back | xid 13466 aborted; neither marker visible. Trace: `RELEASE SAVEPOINT prisma_sp_0`, then `ROLLBACK` | TX-04.2 held |
| `TX-04.independent-inner` | none | not run | | UNSUPPORTED, not applicable by design |
| `TX-05.managed-serializable` | none | committed | xid 13481 committed at `serializable`. `current_setting('transaction_isolation')` was `serializable`. The runner's SIReadLock check agreed | TX-05.1 held. TX-05.2 held |
| `TX-05.explicit-serializable` | none | not run | | UNSUPPORTED, capability absent |
| MG-02 | | recorded in `reports/examples/2026-10-21T20-00-04Z-178fa4` | | `prisma migrate deploy` holds `pg_advisory_lock(72707369)`. `MG-02.held`, `MG-02.first-deployment`, and `MG-02.session-loss` pass. `MG-02.idle-session-timeout` is INCONCLUSIVE because the session inside the migration did not end |
| MG-03 | | unsupported | | capability absent. A migration directory has no down file |

Xids, pids, traces, and command tags above are from the first repetition, the only one whose full record a case file keeps (`combineRepetitions` in `harness/lib/suite.mjs`). It agreed with the other two on classification. The per-repetition summaries keep the reported outcome, the transaction fates, and marker visibility, not the trace.

## Command tags, aborted state, pool, timeout

**Command tags.** On the first repetition, pg recorded `command tag ROLLBACK` for the `COMMIT` in TX-01A and in `TX-02.savepoint-rollback-rejected`. `@prisma/adapter-pg` `executeRaw` returned only `rowCount`. The transaction manager treated that resolved promise as a successful commit and released the connection. The query compiler was not on the path.

**Aborted state.** A caught `23505` did not make Prisma skip `COMMIT`. The callback returned, and the next statement Prisma sent was `COMMIT`. Prisma does not keep a client-side aborted flag that refuses further use of that connection. In `TX-03.statement-error-rollback-not-sent` the next unit's `BEGIN` was sent and PostgreSQL answered `25P02`. Prisma reported that as `P2039`.

**Pool ownership.** The application owns the `pg.Pool`. `PrismaPg` checks a client out and returns it with `client.release()` and no error, including when `ROLLBACK` was not sent or failed. pg-pool then puts that client back on the idle list if it is still queryable. The same-xid commit in `TX-03.rollback-not-sent` and the `25P02` on the next `BEGIN` are that release. On a lost connection, the next `prisma.$transaction()` checked out a new backend.

**Timeout.** The 5000 ms interactive timeout and 2000 ms `maxWait` are Prisma's defaults. Every executed case finished inside them. This run does not show what Prisma does when the timeout fires.

## Upstream candidates

These are observations. A PPCS FAIL is a counterexample to a PPCS invariant. It is not, by itself, a filed defect.

1. **Confirmed framework defect: a resolved `COMMIT` is reported as success when PostgreSQL's command tag was `ROLLBACK`.** Seen in `TX-01A.caught-error-then-commit` and `TX-02.savepoint-rollback-rejected`. Both cases failed 3 of 3. pg returned the tag on the first repetition, the only one whose trace is kept. `@prisma/adapter-pg` `executeRaw` dropped it. The transaction manager in `@prisma/client` treated the resolved call as a commit. The query compiler did not see the statement. Reproduction: `node harness/run.mjs --adapter=prisma --mode=native --case=TX-01A.caught-error-then-commit`.

2. **Confirmed framework behavior, with pg-pool doing what `release()` asks: a failed `ROLLBACK` returns the connection to the pool.** `PgTransaction.rollback` and the commit-failure path call `client.release()` with no error. pg-pool 3.14.0 keeps a queryable client released that way. `TX-03.rollback-not-sent`: the next `$transaction` ran `BEGIN` on that connection, PostgreSQL stayed in xid 13412, and `COMMIT` made both markers visible. `TX-03.statement-error-rollback-not-sent`: the same connection was still idle in transaction (aborted), and the next `BEGIN` failed with `25P02`. The driver did not decide to discard. Prisma did not ask it to.

3. **Confirmed PPCS failure, same shape as other callback transactions: a withheld savepoint rollback is caught, and the outer callback's return commits both markers.** `TX-02.savepoint-rollback-not-sent`. The nested `$transaction` did reject. The outer callback caught that error. Prisma then sent `COMMIT` and PostgreSQL committed. This is the transaction manager following a normal outer return, not a lost command tag. Prisma's nested-transaction notes describe savepoint rollback when the nested callback throws. They do not say a failed savepoint rollback makes the outer transaction unusable if the caller catches the error.

4. **Documented API limitation.** `TX-05.explicit-serializable` cannot be expressed. There is no handle that the application commits with a separate call. `TX-04.independent-inner` cannot arise: a nested `$transaction` is a savepoint, and `$executeRaw` sends the write when it is awaited.

5. **Not a Prisma result.** MG-02 and MG-03 were not run. Prisma Migrate was not driven. The interactive-transaction timeout was not reached.

No issues were filed.
