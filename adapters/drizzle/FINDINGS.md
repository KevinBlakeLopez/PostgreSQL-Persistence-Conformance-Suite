# Drizzle transaction recovery, PPCS run 2026-10-19T13-38-47Z-39ea07

Drizzle ORM 0.45.4, `drizzle-orm/node-postgres`, pg 8.23.1, pg-pool 3.14.0, Node.js v24.14.1, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Suite revision `1715609` plus this uncommitted adapter. The recording's adapter digest is the adapter as it ran; this file and `README.md` were written after that run. Three repetitions agreed. CTL-01 and pg-control held their gates. No Drizzle result was gated.

Native mode is `drizzle(pool)` with `pool.max` equal to the case's `pool_max` (1). `db.transaction(callback)` is the transaction. `tx.transaction(callback)` is the savepoint. The adapter does not read the command tag, discard a connection, or add a rollback. Category C is a client-side injection in `pg.Client.prototype.query`, fired once. Category B is the runner's `pg_terminate_backend`. A resolved `db.transaction()` is reported committed. A rejection with the callback's own error is reported rolled back. Any other rejection is reported failed.

`trace_sees_framework_pg` is true. Drizzle and the adapter resolve one `pg` module.

## Where the calls go

Installed `drizzle-orm@0.45.4`, `node-postgres/session.js`:

`NodePgSession.transaction` (lines 180–194) checks `client instanceof Pool` or a constructor name containing `Pool`. For a pool it does `client.connect()`, then `BEGIN`, then the callback, then `COMMIT`, and returns the callback's value. On any throw it runs `ROLLBACK` and rethrows. `finally` calls `session.client.release()` with no argument. `BEGIN` is before the `try`. The `pg` `Result` of `COMMIT`, including `command`, is discarded.

`NodePgTransaction.transaction` (lines 205–221) uses `SAVEPOINT spN`, `RELEASE SAVEPOINT spN`, and `ROLLBACK TO SAVEPOINT spN`. A throw from the rollback replaces the callback's error, because the rollback is awaited before `throw err`.

`PgTransaction.getTransactionConfigSQL` (`pg-core/session.js`, lines 148–159) appends `isolation level …`, the access mode, and `deferrable` or `not deferrable` to `BEGIN`. The type allows `read uncommitted`, `read committed`, `repeatable read`, and `serializable` (`pg-core/session.d.ts`).

pg 8.23.1 `Client.query` (`lib/client.js`, lines 702–730) starts `query_timeout` when the query is submitted. On expiry it rejects with `Query read timeout`, ignores the later reply, and on the non-pipeline path does not destroy the socket. A query still in `_queryQueue` is removed and not sent.

pg-pool 3.14.0 `_acquireClient` (line 344) removes the pool's client `'error'` listener while the client is checked out. `_release` (line 392) destroys the client when called with an error, or when the client is not queryable. A release with no error returns it to the idle list.

The adapter's `pool.on('error')` covers idle clients only. pg-pool forwards an idle client's `'error'` to the pool through a listener of its own on that client, and `_acquireClient` removes that client listener on checkout. The tables in this section are native mode, without a client listener. The configured mode below adds one.

## Cases

| Case | Fault | Drizzle reported | PostgreSQL at report time, and after exit | Same backend reused | Invariant |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed (`db.transaction` resolved) | xid 4967 committed; marker visible. Command tag `COMMIT` | not a reuse case | CTL-01.1 held |
| `CTL-01.rollback` | none | rolled back (callback `Error`) | xid 4979 aborted; marker absent. Command tag `ROLLBACK` on `rollback` | not a reuse case | CTL-01.2 held |
| `TX-01A.caught-error-then-commit` | A, caught `23505` | committed, because `db.transaction` resolved | xid 4991 aborted at `before-end` and after exit; marker absent. At `before-end` the session was idle in transaction (aborted) and its last statement was the duplicate `INSERT`. After the API returned the session was idle and its last statement was `commit`. The reply to `commit` was command tag `ROLLBACK` | not a reuse case | TX-01A.1 failed. Mechanism exercised |
| `TX-01B.conn-lost-before-commit` | B, backend terminated at `before-end` | no result. Process exit 1 | xid aborted; marker absent. stderr is an unhandled `'error'` event, SQLSTATE `57P01`, emitted on the checked-out `Client` with no listener | the process died during the transaction | not classified. Three repetitions agreed |
| `TX-01B.commit-reply-discarded` | D, reply-lost, fired once | failed (`DrizzleQueryError`: `Failed query: rollback`) | xid 5015 committed at the end; marker visible. Trace: `commit` injected, then `rollback` failed with `Client was closed and is not queryable` | the closed backend was not reused | TX-01B.1 held. TX-01B.2 not exercised |
| `TX-02.savepoint-rollback-not-sent` | C, client-reject. Withheld `rollback to savepoint sp1` once | committed. The outer callback caught `DrizzleQueryError` `Failed query: rollback to savepoint sp1` and returned | xid 5027 committed; both markers visible (outer xmin 5027, inner xmin 5028); session idle; last statement `commit`. Command tag `COMMIT` | not a reuse case | TX-02.1 failed. TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` | C, rewrite. Reply `3B001` | committed. The outer callback caught `DatabaseError` `3B001` and returned | xid 5042 aborted; neither marker visible; session idle; last statement `commit`. The reply to `commit` was command tag `ROLLBACK` | not a reuse case | TX-02.1 failed. TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` | B, backend terminated at `inner-after-write` | no result. Process exit 1 | transaction aborted; neither marker visible. Same unhandled `57P01` on the checked-out `Client` | the process died inside the nested scope | not classified. Three repetitions agreed |
| `TX-03.rollback-not-sent` | C, client-reject. Withheld `rollback` once | failed (`Failed query: rollback`). Unit 2 reported committed after 46 ms | unit 1 xid 5072 was in progress at `after-unit1` and committed by unit 2. Both markers visible, both xmin 5072. Session idle in transaction until that `commit` | yes. Unit 1 and unit 2 both used pid 189814, and unit 2's transaction id is unit 1's | TX-03.1 failed. TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` | C, client-reject after `23505` | failed (`Failed query: rollback`). The caught violation was `23505`. Unit 2 reported failed after 0 ms (`Failed query: begin`) | unit 1 xid 5084 aborted; doomed absent. At `after-fault` and `after-unit1` the session was idle in transaction (aborted). The next statement was `begin` and PostgreSQL answered `25P02`. `pool.end()` did not return within 5 s | the next checkout used the same connection and did not leave the aborted block | TX-03.1 held. TX-03.2 failed |
| `TX-03.conn-lost-in-transaction` | B, backend terminated at `unit1-after-write` | no result. Process exit 1 | unit 1 aborted; doomed absent. Same unhandled `57P01` | the process died before unit 2 | not classified. Three repetitions agreed |
| `TX-04.nested-failure-contained` | none | committed. Nested error caught. Trace: `rollback to savepoint sp1` command tag `ROLLBACK`, then `commit` command tag `COMMIT` | xid 5109 committed; outer visible; inner absent | not a reuse case | TX-04.1 held |
| `TX-04.nested-released-outer-rollback` | none | rolled back. Trace: `release savepoint sp1` command tag `RELEASE`, then `rollback` command tag `ROLLBACK` | xid 5124 aborted; neither marker visible | not a reuse case | TX-04.2 held |
| `TX-05.managed-serializable` | none | committed (`db.transaction(callback, { isolationLevel: 'serializable' })`) | xid 5139 committed; PostgreSQL reported `serializable`; the backend held an `SIReadLock` on `item`. Trace begins `begin isolation level serializable` | not a reuse case | TX-05.1 and TX-05.2 held |

The xids and pids above are the repetition stored in each case file. The other two repetitions agreed on the classification and its qualifiers.

`TX-04.independent-inner` is UNSUPPORTED, not applicable by design. `TX-05.explicit-serializable` is UNSUPPORTED, capability absent. MG-02 is [`reports/examples/2026-10-21T20-00-04Z-178fa4`](../../reports/examples/2026-10-21T20-00-04Z-178fa4/summary.md). `migrate()` takes no advisory lock. `MG-02.held`, `MG-02.session-loss`, and `MG-02.idle-session-timeout` fail. `MG-02.first-deployment` is INCONCLUSIVE because the repetitions disagree. MG-03 is UNSUPPORTED, capability absent: there is no down migration.

## Findings

| Case | Result | PostgreSQL outcome | API outcome | Reachability | Severity | Drizzle |
| --- | --- | --- | --- | --- | --- | --- |
| `TX-01A.caught-error-then-commit` | FAIL, mechanism exercised | aborted; marker absent; `COMMIT` answered `ROLLBACK` | `db.transaction` resolved | R1. Caught unique violation, then a normal return, is ordinary use of the documented callback | S1 | Yes. `NodePgSession.transaction` awaits `commit` and returns the callback value. It does not read `Result.command`. pg delivered the tag. The adapter did not |
| `TX-01B.conn-lost-before-commit` | INCONCLUSIVE | aborted; marker absent | process exit 1 before the call returned. stderr: unhandled `'error'`, `57P01` | R2. `pg_terminate_backend` is a server-side disconnect while the checked-out client is idle between statements | S3. The exception is not delivered to `db.transaction`. The process dies. It does not report a commit | The missing listener is Drizzle's. pg-pool removes its listener on checkout (`_acquireClient`). The application does not hold the client. A probe that adds a listener, which this adapter does not, sees `db.transaction` reject with `Failed query: rollback` / `Client has encountered a connection error and is not queryable`, and the row stays absent |
| `TX-01B.commit-reply-discarded` | PASS, TX-01B.2 not exercised | committed; marker visible | failed. The error that left the call was `Failed query: rollback`, after the injected loss on `commit` | R4. Category D simulation. The driver has already parsed the reply | S3 for the lost commit error, inside a PASS. The call did not report a commit or a confirmed rollback | Yes, the replacement. The `catch` awaits `rollback` before rethrowing the original error, so a failed rollback replaces the commit error. pg closed the socket because the simulation did |
| `TX-02.savepoint-rollback-not-sent` | FAIL | committed; both markers visible; session idle | committed, after the outer callback caught the savepoint-rollback error | R4. The rollback is withheld in the client. The suite does not establish how often that send fails | S1. The original application error is also replaced (S3) | Yes. `NodePgTransaction.transaction` lets the rollback error escape. The outer callback caught it, returned, and the outer `COMMIT` ran. PostgreSQL committed the open transaction, including the savepoint's write |
| `TX-02.savepoint-rollback-rejected` | FAIL | aborted; neither marker visible; session idle; last statement `commit`; command tag `ROLLBACK` | committed | R4 for the rewritten savepoint name. The commit-tag path is the same one TX-01A reaches with no injection | S1 | Yes. Same `COMMIT` path as TX-01A, after PostgreSQL's `3B001` had aborted the transaction |
| `TX-02.conn-lost-before-savepoint-rollback` | INCONCLUSIVE | aborted; neither marker visible | process exit 1, unhandled `57P01` | R2, same disconnect as TX-01B, inside the nested callback | S3, same lost exception | Same missing listener |
| `TX-03.rollback-not-sent` | FAIL | the failed transaction committed; doomed and next both visible under xid 5072 | unit 1 failed (`Failed query: rollback`); unit 2 committed | R4 for the withheld `ROLLBACK`. The same ending is reachable with `query_timeout` (below), which is R2 | S1 | Yes. `finally` calls `release()` with no error, and this run reused that client. pg-pool's `_release` removes a client when the argument is an error; this run did not execute that call. The next `BEGIN` does not start a new transaction. Drizzle's later `COMMIT` commits the open one |
| `TX-03.statement-error-rollback-not-sent` | FAIL | unit 1 aborted; doomed absent; session stayed idle in transaction (aborted); `begin` got `25P02` | unit 1 failed (`Failed query: rollback`); unit 2 failed immediately (`Failed query: begin`) | R4 for the withheld `ROLLBACK`. The `25P02` is what PostgreSQL does in an aborted block | S2. The next unit fails loudly and does not commit the doomed row. `pool.end()` did not return within 5 s because `BEGIN` threw before the `try`, so the client was never released | Yes, the leak. The `25P02` is PostgreSQL. The checkout that never returns is `BEGIN` sitting outside the `try` in `NodePgSession.transaction` |
| `TX-03.conn-lost-in-transaction` | INCONCLUSIVE | unit 1 aborted; doomed absent | process exit 1, unhandled `57P01`, before unit 2 | R2 | S3 | Same missing listener. Unit 2 was not reached, so this run does not show whether the pool would have reused a dead connection |
| `TX-04.nested-failure-contained` | PASS | committed; outer visible; inner absent | committed | ordinary nested callback | not a failure | `tx.transaction` issued `SAVEPOINT sp1` and `ROLLBACK TO SAVEPOINT sp1` |
| `TX-04.nested-released-outer-rollback` | PASS | aborted; neither marker visible | rolled back | ordinary nested callback, then an outer throw | not a failure | `RELEASE SAVEPOINT sp1`, then `rollback` |
| `TX-05.managed-serializable` | PASS | `serializable`, with an `SIReadLock` on `item` | committed | ordinary config argument | not a failure | The server setting matches the argument. The API call alone was not the evidence |

An ordinary rollback is not in this table as a failure. `CTL-01.rollback` passed: the callback threw, Drizzle sent `rollback`, and the command tag was `ROLLBACK`.

## Command tag

On TX-01A, pg's reply to `commit` was command tag `ROLLBACK`. The trace records it. `NodePgPreparedQuery.execute` returns that `Result` for a statement with no field mapper (`session.js`, the branch `return await client.query(...)`). `NodePgSession.transaction` awaits it and ignores the return value. Drizzle retains the tag only inside the driver result that it discards. It does not reject the transaction. The callback's resolved promise is what the application sees.

`pg-control` `correct` reads `reply.command` and reports a rollback. `unsafe` reports committed when `COMMIT` does not throw. Drizzle matches `unsafe` on this point.

## `query_timeout`, `statement_timeout`, and a lost backend

`investigations/drizzle-followups/probe.mjs`, same package versions, same disposable server, three repetitions each. The probe adds a `Client` `'error'` listener so its own cleanup does not kill the process. That listener is not in the adapter. `query_timeout` rejects a promise; it does not need the listener for the result below.

| Condition | What was configured | API | PostgreSQL | Rows afterwards | Class |
| --- | --- | --- | --- | --- | --- |
| `query_timeout` 300 ms on a `pg.Pool` of 1. Insert `abandoned`, then `select pg_sleep(2)`. Wait until the session is idle in transaction. Then `db.transaction` inserts `later` | documented `pg.Pool` option `query_timeout` | first call rejects `Failed query: rollback` / `Query read timeout`. Later call resolves | before the later call the session is idle in transaction and its last statement is `select pg_sleep(2)`. After the later call the session is idle and its last statement is `commit` | `abandoned` and `later` both visible. 3 of 3 | R2, S1. A slow statement plus the documented client timeout. Not a withheld statement |
| Same `query_timeout` on a direct `pg.Client` passed to `drizzle(client)` | documented client, not the adapter's pool | same pair of outcomes. The later call resolves | same idle-in-transaction state, then `commit` | `abandoned` and `later`. 3 of 3 | R2, S1. Direct client and pool agree once the connection is idle again |
| Same pool, but a second `db.transaction` is started while `pg_sleep` is still active | same option | the second `BEGIN` also times out. A third call then waits on `pool.connect` and hits the probe's 8 s bound | session ends idle in transaction. No commit in that window | no visible rows. 3 of 3 | R2, S2. `BEGIN` is outside the `try`, so that timed-out checkout is not released. This is not the commit above |
| `statement_timeout` 300 ms on the pool. Same insert and `pg_sleep(2)`, then a later insert of `next` | PostgreSQL startup parameter, not `query_timeout` | first call rejects `57014` `canceling statement due to statement timeout`. Later call resolves | session idle; last statement `commit` | only `next` | R2, S4. The server cancelled the statement. Drizzle's rollback completed. Not the same outcome as `query_timeout` |
| `pg_terminate_backend` during `db.transaction`, with the probe's error listener | the listener is the probe's | rejects `Failed query: rollback` / `Client has encountered a connection error and is not queryable` | row absent | none | The 2026-10-19 suite, without this listener, is the INCONCLUSIVE exit. With it, the call does not report a commit |

The `ROLLBACK` text appears in the `query_timeout` trace because the probe logs `query()` calls. The session's last statement stayed `select pg_sleep(2)` until the later `commit`, so that rollback did not end the transaction. pg's timer can drop a query that is still queued behind the sleep, or stop waiting after it has been sent. This probe does not separate those two timings. It does separate them from a server-side `statement_timeout`, and from the category C withhold in TX-03.

A rollback that is sent and acknowledged is `CTL-01.rollback`. A commit whose acknowledgement is discarded is `TX-01B.commit-reply-discarded`: PostgreSQL committed, and Drizzle reported failure rather than success. A broken connection with no listener is the category B exit in the 2026-10-19 recording.

## Comparison

Demonstrated transaction outcomes, not API surface.

| Case | Kysely / MikroORM | Knex / Lucid | TypeORM | pg-control correct | Drizzle |
| --- | --- | --- | --- | --- | --- |
| `TX-01A` | MikroORM FAIL. Kysely is the SQL layer under MikroORM 7.2.5, not a separate PPCS adapter | FAIL | FAIL | PASS. It reads the command tag | FAIL, mechanism exercised. Same report as the three Node frameworks: the call resolves, PostgreSQL aborted |
| `TX-01B` connection loss | MikroORM PASS | FAIL | PASS | PASS | INCONCLUSIVE. The process dies on the checked-out client's `'error'` event. The other Node adapters returned an API result |
| `TX-01B` reply discarded | MikroORM PASS, TX-01B.2 not exercised | FAIL, TX-01B.2 not exercised | PASS, TX-01B.2 not exercised | PASS in `correct`; `unsafe` reports a rollback | PASS, TX-01B.2 not exercised. The surfaced error is the failed `rollback`, not the lost `commit` |
| `TX-02` rollback not sent | FAIL. Both markers committed | FAIL. Both markers committed | FAIL. The session was still in a transaction at report time | PASS. It sends `ROLLBACK` instead of `COMMIT` | FAIL. Both markers committed, session idle. The Lucid / MikroORM ending, not TypeORM's open session |
| `TX-02` rollback rejected | FAIL | FAIL | FAIL, session still open at report time | PASS | FAIL. Command tag `ROLLBACK` on `commit`, session idle. Same shape as SQLAlchemy Core's rejected-savepoint FAIL |
| `TX-03` rollback not sent | FAIL | FAIL | FAIL | PASS. It discards the connection | FAIL. Unit 2 committed xid 5072, which was unit 1's transaction, on pid 189814 |
| `TX-04` savepoints | MikroORM's contained-failure case FAILs in native mode because of its unit of work. Not this shape | PASS | PASS | PASS | PASS. The trace is `SAVEPOINT sp1` / `ROLLBACK TO` / `RELEASE` |
| `TX-05` | both forms PASS | managed PASS; explicit FAIL | both PASS | `correct` PASS; `unsafe` drops the level | managed PASS. No explicit form |

The Kysely 0.29.7 `query_timeout` outcome described for that investigation — a later unit of work commits rows the failed transaction abandoned — is what this Drizzle pool did, 3 of 3, in `investigations/drizzle-followups/probe.mjs`. This run did not re-execute Kysely.

## Isolation outside the catalog

The suite's TX-05 case requests `serializable` only. The probe also read `current_setting` inside `db.transaction` for the other documented options. The server reported:

| Config | `transaction_isolation` | `transaction_read_only` | `transaction_deferrable` |
| --- | --- | --- | --- |
| none | `read committed` | off | off |
| `read committed` | `read committed` | off | off |
| `repeatable read` | `repeatable read` | off | off |
| `serializable` | `serializable` | off | off |
| `serializable`, `read only` | `serializable` | on | off |
| `serializable`, `read only`, `deferrable: true` | `serializable` | on | on |
| `serializable`, `read write`, `deferrable: false` | `serializable` | off | off |

These are one observation each, not three suite repetitions. They match the SQL `getTransactionConfigSQL` builds. They are not a concurrency test.

## Migration tooling

`drizzle-orm` 0.45.4 `PgDialect.migrate` (`pg-core/dialect.js`, lines 44–71) creates the history table, reads the latest `created_at` outside a transaction, then runs every pending migration's statements and the history insert inside one `session.transaction`. There is no advisory lock and no down migration. The recorded run sets `migrationsSchema` to `public` and `migrationsTable` to `drizzle_migrations` so the runner can count that identifier. The library default schema is `drizzle`. `drizzle-kit` was not installed and was not run.

MG-02 is [`reports/examples/2026-10-21T20-00-04Z-178fa4`](../../reports/examples/2026-10-21T20-00-04Z-178fa4/summary.md). Two migrators can both observe the same last row and both enter the transaction. `MG-02.held`, `MG-02.session-loss`, and `MG-02.idle-session-timeout` fail. `MG-02.first-deployment` is INCONCLUSIVE because the repetitions disagree. MG-03 is declared unsupported: this runtime has no reversal API.

## Architectural assessment

1. Drizzle does not preserve PostgreSQL transaction outcomes more accurately than Lucid, MikroORM, or TypeORM. On TX-01A it reports success when the reply to `COMMIT` is `ROLLBACK`. pg already returned that tag. The correct control reads it. Drizzle throws it away.
2. It does not safely handle a failed rollback. `release()` without an error puts the connection back. A later `db.transaction` can commit the abandoned rows. That happened under the synthetic withhold and under documented `query_timeout`. A failed `BEGIN` is outside the `try`, so that checkout is not released, and `pool.end()` waited out the adapter's 5 s close bound.
3. The thin path is easier to inspect. The transaction implementation is one function, and the trace shows the SQL and the command tag. The repair, if one were authorized, would be local: read `Result.command`, and pass a rollback or connection failure to `release(err)`. Ease of inspection is not the same as a correct report.
4. Against direct pg, the value that showed up here is the schema-aware statement builder and the small amount of code a reader has to audit. The transaction wrapper does not keep the fact pg already reported. Under a discipline that reviews the library instead of trusting it, that audit is short, and it fails the commit-tag check.
5. The outcomes that block treating this as a reliable PostgreSQL transaction layer are the R1 false commit on an aborted transaction, the R2 commit of abandoned rows after `query_timeout`, and the R2 process crash when the backend is disconnected during a checked-out transaction. The 2026-10-23 native re-run reproduced that crash. Nested savepoints and the isolation argument did what PostgreSQL was asked, in the runs where cleanup succeeded. In the configured mode below, where the application adds a client listener, the disconnect is reported as a failure. That does not change the false commit or the abandoned-row commit.

## 1.0.0-rc.4

The same cases on Drizzle ORM 1.0.0-rc.4, with the same pg 8.23.1 and the same server, are in `reports/examples/2026-10-19T14-34-08Z-26b178` and `adapters/drizzle-rc/FINDINGS.md`. No classification changed. The transaction control flow in that package is the same sequence as the 0.45.4 function cited above. That package has no `client-error-listener` mode and was not re-run.

## Category B in native mode and with a client listener

`reports/examples/2026-10-23T13-55-28Z-620447`. Drizzle ORM 0.45.4, pg 8.23.1, pg-pool 3.14.0, Node.js v24.14.1, PostgreSQL 18.6. Both modes ran the three category B cases. Three repetitions agreed in each. CTL-01 passed in both modes, and `pg-control` held its gates.

In native mode all three cases are INCONCLUSIVE, as on 2026-10-19. The adapter exited with code 1 before `db.transaction()` returned. stderr is an unhandled `'error'` event, `terminating connection due to administrator command`.

The configured mode `client-error-listener` adds `pool.on('connect', (client) => client.on('error', () => {}))`. The listener does not roll back or discard the connection. pg-pool's `_release` destroys a client that is not queryable.

| Case | Drizzle reported | PostgreSQL | Invariant |
| --- | --- | --- | --- |
| `TX-01B.conn-lost-before-commit` | failed (`DrizzleQueryError`: `Failed query: rollback`). Trace: `commit`, then `Client has encountered a connection error and is not queryable`, then the same error on `rollback`. Process exit 0 | xid 40416 aborted; marker absent | TX-01B.1 held. PASS |
| `TX-02.conn-lost-before-savepoint-rollback` | failed (`Failed query: rollback`). The nested scope raised `Failed query: rollback to savepoint sp1`. The callback caught it, and `commit` and `rollback` then failed with the same driver text | xid 40443 aborted; neither marker visible | TX-02.1 and TX-02.2 held. PASS |
| `TX-03.conn-lost-in-transaction` | unit 1 failed (`Failed query: rollback`). Unit 2 reported committed after 45 ms | unit 1 xid 40471 aborted on pid 2212459; doomed absent. Unit 2 xid 40472 committed on pid 2212480; next visible | TX-03.1 and TX-03.2 held. PASS. The dead backend was not reused |

The xids, pids, and timings are the repetition stored in each case file. The other two repetitions agreed on the classification.

`reports/examples/2026-10-23T13-11-06Z-d7cd89` ran the same three cases with this listener installed in native mode. Its case files say `native`, and its mode description does not mention the listener. It is kept as recorded. The 2026-10-23T13-55-28Z run supersedes it.

## Next actions

1. Do not file an upstream issue unless that is authorized. The candidate is `NodePgSession.transaction`: it ignores the `COMMIT` result, and it calls `release()` with no error after a failed `ROLLBACK`. `BEGIN` before the `try` is the checkout leak.
2. Native mode stays without a client `'error'` listener, so the matrix keeps the process exit as INCONCLUSIVE. The configured mode measures the same cases with the listener an application would add. A classification for "the driver error killed the process before the call returned" would make the native rows comparable with adapters that return a failure. That is a harness change, not an adapter workaround.
3. Leave `investigations/drizzle-followups/probe.mjs` as the `query_timeout` reproduction. Do not fold it into a catalog case in this pass, and do not start a Drizzle application port. Migration cases can wait on a separate adapter that drives `migrate()` and states that there is no reversal.
