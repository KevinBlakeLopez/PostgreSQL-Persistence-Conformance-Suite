# Transaction-outcome propagation

This directory records where a PostgreSQL transaction outcome is still visible, and where a later layer drops or rewrites it. It sits beside the PPCS suite. It does not change `ppcs-result/1`, the classifier, or recorded suite runs.

The first scenario is `TX-01A.caught-error-then-commit`: a unique violation is caught inside a transaction, then the transaction ends with COMMIT. PostgreSQL can answer that COMMIT with command tag `ROLLBACK`. The experiment checks three subjects against one disposable server:

| Subject | What it represents |
| --- | --- |
| `pg-read-tag` | Application code that reads `Result.command` |
| `pg-ignore-tag` | Application code that treats a resolved `COMMIT` as success |
| `typeorm-transaction` | TypeORM `DataSource.transaction(callback)` on the same `pg` |

A second connection reads `pg_xact_status()` and marker visibility. The information-loss boundary is computed from those observations. The experiment does not type the boundary in by hand.

`UNKNOWN` is an outcome that could not be established. It is not a failure. `NOT_OBSERVED` means this run did not see a value. `NOT_EXPOSED` means the examined API does not provide it.

## Run

```sh
pnpm run pg:up
node research/transaction-outcome-propagation/experiments/tx01a-pg-typeorm.mjs
```

The command writes `research/transaction-outcome-propagation/runs/<run-id>/`:

- `records/*.json` — one `ppcs-propagation/1` record per subject
- `capabilities/pg-8.23.1.json` — driver capabilities demonstrated by `pg-read-tag`
- `run.json` — versions, paths, and the command
- `summary.md` — the report

Regenerate the report from the JSON:

```sh
node research/transaction-outcome-propagation/report.mjs research/transaction-outcome-propagation/runs/<run-id>
```

Unit tests, with no database:

```sh
node --test research/transaction-outcome-propagation/test/boundary.test.mjs
```

`pnpm test` includes that file. The live experiment is not part of CI's `--expect` comparison.

Further scenarios, still outside the harness:

```sh
node research/transaction-outcome-propagation/experiments/followups.mjs
```

That run covers TX-01B connection loss, TX-01B with the existing commit-reply proxy, a client-triggered rejected savepoint rollback (TX-02), a withheld ROLLBACK (TX-03), and TX-01A through PHP `pdo_pgsql` and the Ruby `pg` gem when those runtimes are installed. pgjdbc, Npgsql, and psycopg are skipped when their runtimes are absent. The proxy module is used as-is.

## Add a driver observation

1. Add a subject function that calls the library the way an application does. Use the dependency already installed for an adapter. Do not add a package for instrumentation.
2. Record driver fields from a supported return value. A diagnostic wrapper is allowed when it only reads the object the driver already returned, and the record labels it `diagnostic_wrapper`.
3. Verify the database from another connection. Map `pg_xact_status()` and marker visibility with `verifiedOutcome`. Disagreement is `UNKNOWN`.
4. Pass the observations to `propagationRecord`. That function computes the boundary. Do not assign `information_loss_boundary` in the subject.
5. Leave untested capabilities as `UNKNOWN`. Use `NOT_APPLICABLE` when the capability does not apply to that driver.
6. Keep the new code under this directory. Do not import `harness/lib`.
7. Extend `schema/propagation.v1.schema.json` when a new field is required, and cover it with a database-free test.
8. Re-run the experiment and keep the new run next to the older one.

Pool and transaction-manager layers are recorded only when they are separate components. A transaction API inside the same library stays in the framework layer.

## Schemas

- `schema/propagation.v1.schema.json` — one subject
- `schema/capability.v1.schema.json` — one driver inventory
- `schema/run.v1.schema.json` — the run manifest

## Filing

`templates/upstream-issue.md` is a blank template. Do not post it. Fill a copy from a run and wait for approval of that exact text.
