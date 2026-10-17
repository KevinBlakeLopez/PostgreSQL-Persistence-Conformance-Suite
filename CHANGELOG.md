# Changelog

Results from different versions are not comparable: each version can change what the evidence must show before a case passes or fails. Every run records the harness digest that identifies its rules, and `--expect` refuses to compare runs whose digests differ.

## 0.2.0 (unreleased)

Hardening after an independent methodology review.

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
