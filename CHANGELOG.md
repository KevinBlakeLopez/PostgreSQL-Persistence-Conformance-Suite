# Changelog

Results from different versions are not comparable: each version can change what the evidence must show before a case passes or fails. Every run records the harness digest that identifies its rules, and `--expect` refuses to compare runs whose digests differ.

## Unreleased

- **MG-02 and MG-03 run on Lucid and `pg-control`.** Seven cases: a held migration, a first deployment, a lost session, an idle-session timeout, a valid reversal, a migration with no reversal, and a reversal that fails. Each role is its own process, named `ppcs-A`, `ppcs-B` or `ppcs-C`. The harness's own sessions stay excluded by backend PID together with `ppcs-observer`. On Lucid 22.4.2 the idle-session timeout is inconclusive, because the session inside the migration is not idle, and a migration with no reversal is reported reverted while its marker remains. The recorded run is `reports/examples/2026-10-18T00-11-46Z-95887b`.

## 0.3.0 (unreleased)

A requested isolation level.

- **New family: TX-05.** Two cases, one per API form (managed and explicit), request SERIALIZABLE.
  - **TX-05.1.** On PostgreSQL, a transaction the API started at a requested level runs at that level or a stricter one. A PASS needs two observations that agree: `current_setting('transaction_isolation')`, read in the same statement as the captured ID, and an `SIReadLock` the runner sees on `item` or one of its indexes, after a confirmed read of `item`.
  - **TX-05.2.** An API whose documentation accepts a level PostgreSQL supports does not reject a valid request. A rejection fails it only when its cause is established: the error carries no PostgreSQL SQLSTATE and no operating-system error code, and a plain transaction through the same form was bound at `baseline`.
- **INCONCLUSIVE reasons.** A TX-05 result records why it is INCONCLUSIVE, in `evaluation.inconclusive_reason`: `observation-conflict`, `evidence-missing`, `environment`, or `cause-not-established`. Other families keep none.
- **Evidence.** The observer records each `SIReadLock`'s target, whether the backend held an `AccessShareLock` on `item`, and `backend_xmin` as a diagnostic. A checkpoint that declares `captures_isolation` carries `transaction_isolation`.
- **Adapters.** Lucid, MikroORM and TypeORM implement both forms. `pg-control` `correct` starts the transaction with `BEGIN ISOLATION LEVEL SERIALIZABLE`; `unsafe` sends a plain `BEGIN`.

Results under 0.2.0 and 0.3.0 are not comparable: the harness digest changed.

## 0.2.0 (2026-10-17)

Hardening after an independent methodology review.

- **New case: `TX-03.statement-error-rollback-not-sent`.** A failed statement leaves unit 1 in an aborted transaction block when its `ROLLBACK` is withheld; the open-block case leaves an open transaction. A unit of work handed the connection then fails loudly with `25P02`, instead of silently joining a transaction. The case's fault declares the signature it must leave (`aborted-block`).
- **Runner sessions.** These are now identified by backend PID together with the runner's `application_name`. An adapter connection that uses the runner's name is counted against the pool.
- **Evidence.**
  - Fates are recorded at report time (`after-end`), when the framework's API returns, as well as after the framework has gone. A fate decided at teardown is reported as such.
  - A captured transaction ID must belong to the session that reported it.
  - Writes are confirmed in `pg_locks`. Visible markers are attributed by `xmin`. The runner checks for stray rows and fixture changes.
  - Client-side faults are confirmed on the server, at `after-fault`, before the framework sees their error.
  - TX-01A records whether COMMIT reached the server.
- **Classification.**
  - `TX-01B.conn-lost-before-commit` is a known outcome: a truthful report of rollback passes.
  - Without a declared rollback-claim channel, TX-01B.2 is "not exercised", never held.
  - The invariants evaluated must equal those the case declares.
  - A runtime `unsupported` and a repeated checkpoint are protocol errors. `pending` is an outcome of its own.
- **Run gates.**
  - Every case runs three times.
  - A result counts only if the run's own controls held.
  - Runs record the harness digest.
  - The server profile is asserted, and the runner's connections have timeouts.
- **Labels.**
  - Unsupported cases have a class: `capability-absent` or `not-applicable-by-design`.
  - `recommended` modes cite documentation.
  - Native forms are recorded.

## 0.1.0 (2026-10-16)

The initial suite:

- the observation controls (CTL-01), and TX-01A, TX-01B, TX-02, TX-03 and TX-04;
- adapters for Lucid, MikroORM and TypeORM;
- `pg-control`, with positive and negative control modes.
