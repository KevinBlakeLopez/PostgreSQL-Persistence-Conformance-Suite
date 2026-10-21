# Django transaction recovery, PPCS run 2026-10-18T13-08-22Z-6d8443

Django 6.1.2, psycopg 3.3.6, Python 3.13.11, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Three repetitions agreed. CTL-01 and pg-control held their gates in this run for every Django scenario result below.

Native mode is `transaction.atomic()` with `CONN_MAX_AGE` 0 and no pool. `TX-03` runs only in the persistent mode (`CONN_MAX_AGE` null), which calls `django.db.close_old_connections()` between units. Category C is a client-side injection in this process, fired once, before psycopg sends. Category B is the runner's `pg_terminate_backend`. Django flags are not the verdict.

`TX-01B.commit-reply-discarded` is NOT_RUN. On this server, `Connection.commit()` returned with `transaction_status` `IDLE` after it had been `INTRANS`. psycopg does not return from `commit()` until `_exec_command(b"COMMIT")` finishes, so the caller never observes a lost COMMIT reply while the driver still reports a transaction. The node-postgres reply-lost simulation is not that probe.

TX-04 and TX-05 are a later run, [`reports/examples/2026-10-21T19-26-59Z-4ccef5`](../../reports/examples/2026-10-21T19-26-59Z-4ccef5/summary.md). Both savepoint cases passed. `TX-04.independent-inner` is unsupported, not applicable by design. Both TX-05 forms passed with `transaction_isolation` `serializable`. Three repetitions agreed.

MG-02 and MG-03 are [`reports/examples/2026-10-21T20-00-04Z-178fa4`](../../reports/examples/2026-10-21T20-00-04Z-178fa4/summary.md). `MigrationExecutor` takes no advisory lock. `MG-02.held` fails: marker count 2, history count 2, and A and B were inside the migration at once. `MG-03.no-reversal` passes: unapply raises `IrreversibleError`, and the marker and the `django_migrations` row remain. Three repetitions agreed.

## Cases

| Case | Fault | Django reported | PostgreSQL at report time, and after exit | Same backend reused | Invariant |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` (native and persistent) | none | committed (`commit()`) | xid 766 / 778 committed at `after-end`; still committed after exit; marker visible | not a reuse case | CTL-01.1 held |
| `CTL-01.rollback` (native and persistent) | none | rolled back (`AppError`, then `rollback()`) | xid 790 / 802 aborted at `after-end`; still aborted after exit; marker absent | not a reuse case | CTL-01.2 held |
| `TX-02.savepoint-rollback-not-sent` | C, client-reject. Withheld `ROLLBACK TO SAVEPOINT "s8398037376_x1"` once. At `after-fault` the session was idle in transaction, holding xids 838 and 839 | committed (`commit()`) | xid 838 committed at `after-outer`; still committed after exit; both markers visible; session idle | not a reuse case | TX-02.1 failed. TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` | C, rewrite to `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint`. Reply `3B001`. At `after-fault` the session was idle in transaction (aborted) and the top-level transaction was in progress | rolled back (`rollback()`; the block did not raise) | xid 853 aborted at `after-outer`; still aborted after exit; neither marker visible; session idle, last statement `ROLLBACK` | not a reuse case | TX-02.1 and TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` | B, backend terminated at `inner-after-write` | failed (`OperationalError`: the connection is lost). The block did not raise; `rollback()` raised and Django dropped the connection | xid 868 aborted at `after-outer`; still aborted after exit; neither marker visible; session closed | the terminated backend was not reused | TX-02.1 and TX-02.2 held |
| `TX-03.rollback-not-sent` (persistent) | C, client-reject. Withheld `ROLLBACK` once. At `after-fault` the session was idle in transaction on xid 884 | failed (`ProgrammingError`: cannot change autocommit while `INTRANS`). Unit 2 reported committed | unit 1 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 885 committed; next visible | no. Autocommit was false, so `close_old_connections()` closed pid 4248. Unit 2 used pid 4264 | TX-03.1 and TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` (persistent) | C, client-reject after `23505`. At `after-fault` the session was idle in transaction (aborted), no backend xid, unit 1 already aborted | failed (`ProgrammingError`: cannot change autocommit while `INERROR`). Unit 2 reported committed | unit 1 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 900 committed; next visible | no. The same close dropped pid 4382. Unit 2 used pid 4398 | TX-03.1 and TX-03.2 held |
| `TX-03.conn-lost-in-transaction` (persistent) | B, backend terminated at `unit1-after-write` | rolled back (`AppError` left `atomic()`). `rollback()` had raised `57P01` | unit 1 xid 914 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 915 committed; next visible | no. The terminated pid 4516 was gone. Unit 2 used pid 4533 | TX-03.1 and TX-03.2 held |
| `TX-01A.caught-error-then-commit` | A, caught `23505` | rolled back (`rollback()`; the block did not raise) | xid 814 aborted at `before-end` (idle in transaction (aborted)) and after exit; marker absent. After the API returned the session was idle and its last statement was `ROLLBACK` | not a reuse case | TX-01A.1 held. The COMMIT-answered-ROLLBACK mechanism was not exercised |
| `TX-01B.conn-lost-before-commit` | B, backend terminated at `before-end` | failed (`OperationalError` `57P01`) | xid 826 aborted at `after-end` and after exit; marker absent | the terminated backend was not reused | TX-01B.1 held |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run | not run |

Native `TX-03` was not executed. Django's default `CONN_MAX_AGE` is 0, which closes the connection at the end of each request ([Persistent connections](https://docs.djangoproject.com/en/6.1/ref/databases/#persistent-connections)). That is `not-applicable-by-design` for handing a transactionally active connection to later work. The persistent rows are the documented mechanism that can keep a connection, `CONN_MAX_AGE` null. After these faults it did not hand the same backend on: `close_if_unusable_or_obsolete` drops a connection whose autocommit was not restored ("If the application didn't restore the original autocommit setting, don't take chances, drop the connection").

## Contract beside the failure

`TX-02.savepoint-rollback-not-sent` is the one counterexample. The withheld statement raised `RuntimeError`, which is not `django.db.Error`. `Atomic.__exit__` sets `needs_rollback` only in `except Error` around `savepoint_rollback`. The flag stayed false, the outer block exited with no exception, and Django called `commit()`. PostgreSQL committed both the outer and the inner marker. The session was idle afterward. TX-02.2 held.

Django's opening sentence is: "If the block of code is successfully completed, the changes are committed to the database. If there is an exception, the changes are rolled back." The DatabaseError admonition, which says a caught database error makes Django roll back at the end of the block, does not cover this `RuntimeError`. The source comment on the `except Error` branch says a failed savepoint rollback marks the connection for rollback at a higher level; the `except` itself applies only to `django.db.Error`.

The same ending is already recorded for SQLAlchemy (`results/2026-10-17T23-08-15Z-6704a7`: outer API reported commit, PostgreSQL committed, both markers visible, session idle), and for Lucid, MikroORM, and pg-control unsafe in `reports/examples/2026-10-18T00-11-46Z-95887b`. pg-control correct sends `ROLLBACK` after the withheld statement and passes. TypeORM's FAIL on that case is a different ending: it reports commit, the session stays idle in transaction, and neither marker remains, so TX-02.1 and TX-02.2 both fail.

The rewrite case is the contrast. PostgreSQL's `3B001` is a database error. Django rolled the outer transaction back and did not report a commit. Both TX-02 invariants held.

## Recommendation

Keep the case in PPCS only.

The run shows one reproducible mismatch, and it is Django's reaction to a plain exception injected before send. A server rejection of the same statement (`3B001`) follows Django's `except Error` path and matches PostgreSQL. An upstream report would be a question about whether every failure of `savepoint_rollback`, including an exception that is not `django.db.Error`, should set `needs_rollback`. The run does not show that Django mishandles a database error on that statement. Category C does not say how often the fault occurs, and it is not a network partition. Category B, where the runner terminated the backend, aborted the transaction and Django did not report a commit.
