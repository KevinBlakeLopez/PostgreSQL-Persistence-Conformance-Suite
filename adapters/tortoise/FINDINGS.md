# Tortoise transaction recovery, PPCS run 2026-10-19T12-45-38Z-c45624

Tortoise ORM 1.1.9, asyncpg 0.32.0, Python 3.13.11, PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`). Three repetitions agreed. CTL-01 and `pg-control` held their gates in this run for every Tortoise scenario result below.

Native mode is `in_transaction()` on `tortoise.backends.asyncpg`, the engine `postgres://` selects. A nested `in_transaction()` is a savepoint. Pool `minsize` is 1 and `maxsize` is 1. Tortoise's own default `maxsize` is 5. The pool stays open between TX-03's two units. Category C patches `asyncpg.Connection.execute` once, before Tortoise sees the error. A top-level withhold matches `ROLLBACK;` and leaves the pool reset's `ROLLBACK` (no semicolon) alone. Category B is the runner's `pg_terminate_backend`. A clean exit is reported committed. An exit with the exception raised inside the block is reported rolled back. An exit with an error the block did not raise is reported failed.

`TX-01B.commit-reply-discarded` is NOT_RUN. `asyncpg.Transaction.commit` awaits `Connection.execute` until the command finishes. `TX-04.independent-inner` is unsupported, not applicable by design. Both TX-05 cases are unsupported, capability absent. MG-02 and MG-03 are NOT_RUN.

## Cases

| Case | Fault | Tortoise reported | PostgreSQL at report time, and after exit | Same backend reused | Invariant |
| --- | --- | --- | --- | --- | --- |
| `CTL-01.commit` | none | committed (clean exit) | xid 3636 committed at `after-end`; still committed after exit; marker visible | not a reuse case | CTL-01.1 held |
| `CTL-01.rollback` | none | rolled back (`AppError`) | xid 3648 aborted at `after-end`; still aborted after exit; marker absent | not a reuse case | CTL-01.2 held |
| `TX-01A.caught-error-then-commit` | A, caught `23505` | committed (clean exit) | xid 3660 aborted at `after-end`; still aborted after exit; marker absent. At `before-end` the session was idle in transaction (aborted) | not a reuse case | TX-01A.1 failed. `mechanism_exercised` is false: after the API returned the last statement was the pool reset query |
| `TX-01B.conn-lost-before-commit` | B, backend terminated at `before-end` | failed (an error the block did not raise) | xid 3672 aborted at `after-end`; still aborted after exit; marker absent | the terminated backend was not reused | TX-01B.1 held |
| `TX-01B.commit-reply-discarded` | D | NOT_RUN | not run | not run | not run |
| `TX-02.savepoint-rollback-not-sent` | C, client-reject. Withheld `ROLLBACK TO __asyncpg_savepoint_3__;` once | committed (clean exit). Driver trace: `COMMIT; -> COMMIT` | xid 3684 committed at `after-outer`; still committed after exit; both markers visible; session idle | not a reuse case | TX-02.1 failed. TX-02.2 held |
| `TX-02.savepoint-rollback-rejected` | C, rewrite to `ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint`. Reply `3B001` | committed (clean exit). Driver trace: `COMMIT; -> ROLLBACK` | xid 3700 aborted at `after-outer`; still aborted after exit; neither marker visible; session idle | not a reuse case | TX-02.1 failed. TX-02.2 held |
| `TX-02.conn-lost-before-savepoint-rollback` | B, backend terminated at `inner-after-write` | failed (an error the block did not raise) | xid 3724 aborted at `after-outer`; still aborted after exit; neither marker visible | the terminated backend was not reused | TX-02.1 and TX-02.2 held |
| `TX-03.rollback-not-sent` | C, client-reject. Withheld `ROLLBACK;` once. The pool reset then sent `ROLLBACK` | failed (`RuntimeError`: ROLLBACK was not sent). Unit 2 reported committed after 43 ms | unit 1 xid 3739 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 3740 committed; next visible | yes. Both units used pid 158036 | TX-03.1 and TX-03.2 held |
| `TX-03.statement-error-rollback-not-sent` | C, client-reject after `23505`. The withheld `ROLLBACK;` replaced the `IntegrityError` as the exception that left the block | failed (the injected `RuntimeError`). Unit 2 reported committed after 38 ms | unit 1 xid 3754 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 3755 committed; next visible | yes. Both units used pid 158167 | TX-03.1 and TX-03.2 held |
| `TX-03.conn-lost-in-transaction` | B, backend terminated at `unit1-after-write` | failed (an error the block did not raise). Unit 2 reported committed after 41 ms | unit 1 xid 3769 aborted at `after-unit1` and after exit; doomed absent. Unit 2 xid 3770 committed; next visible | no. Unit 1 pid 158306 was gone. Unit 2 used pid 158314 | TX-03.1 and TX-03.2 held |
| `TX-04.nested-failure-contained` | none | committed (clean exit) | xid 3784 committed at `after-end`; still committed after exit; outer visible; inner absent | not a reuse case | TX-04.1 held |
| `TX-04.nested-released-outer-rollback` | none | rolled back (`AppError`) | xid 3799 aborted at `after-end`; still aborted after exit; neither marker visible | not a reuse case | TX-04.2 held |
| `TX-04.independent-inner` | none | UNSUPPORTED (not applicable by design) | not run | not run | outside coverage |
| `TX-05.managed-serializable` | none | UNSUPPORTED (capability absent) | not run | not run | outside coverage |
| `TX-05.explicit-serializable` | none | UNSUPPORTED (capability absent) | not run | not run | outside coverage |

The driver trace is a diagnostic. The runner does not classify from it. On TX-01A the trace records `COMMIT; -> ROLLBACK`, and `pg_stat_activity` at `after-end` shows the pool reset query (`pg_advisory_unlock_all`, `CLOSE ALL`, `UNLISTEN *`, `RESET ALL`), because `in_transaction()` releases the connection before it returns.

## Endings

`TX-02.savepoint-rollback-not-sent` is the same ending as Django, SQLAlchemy `Session`, and `pg-control` unsafe: the outer API reports a commit, PostgreSQL commits, and both markers are visible. The session is idle, so TX-02.2 holds. In this run that transaction is xid 3684.

`TX-02.savepoint-rollback-rejected` is the same ending as SQLAlchemy's rejected-savepoint FAIL. The API reports a commit, the session is idle at `after-outer`, and PostgreSQL aborted the transaction, so neither marker remains. Django's run passed this case. In this run the transaction is xid 3700. The reply code recorded by the adapter is `3B001`.

`TX-01A.caught-error-then-commit` reports a commit of xid 3660, which PostgreSQL aborted. The marker is absent. Spring JDBC's recorded run fails this case the same way. Django rolls the transaction back inside the block, so its PASS does not send `COMMIT`. SQLAlchemy's `Session` run is INCONCLUSIVE because the flush rolled back before `before-end`.

`TX-03.rollback-not-sent` and `TX-03.statement-error-rollback-not-sent` pass on the same backend with a new transaction id. The withheld `ROLLBACK;` is followed, in the driver trace, by the pool reset's `ROLLBACK`. SQLAlchemy's native pool also passes these two. Spring JDBC's pooled mode fails the open-block case because restoring autocommit sends `COMMIT`. Django's persistent mode passes all three TX-03 cases.
