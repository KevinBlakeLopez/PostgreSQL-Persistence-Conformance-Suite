# SQLite control

A `sqlite3` control for the Phase 1 cases. It is not registered with the PostgreSQL runner: there is no `adapter.json`, and it does not import the harness.

Each case opens `autocommit=True`, issues `BEGIN` / `COMMIT` / `ROLLBACK` itself, and checks a second connection. Expectations are the outcomes measured in the Phase 0 baseline.

```sh
/opt/homebrew/bin/python3.13 research/sqlite-phase0/control/run.py
```

The process exits 0 only when every case passes and the three repetitions agree. Evidence is written to `research/sqlite-phase0/control/evidence/<run-id>/`.

| Case | Expectation |
| --- | --- |
| `SQLITE-CTL.commit` | After SQL `COMMIT`, `in_transaction` is false and a second connection sees the marker. |
| `SQLITE-CTL.rollback` | After SQL `ROLLBACK`, the second connection does not see the marker. |
| `SQLITE-TX-01.caught-unique-then-commit` | `SQLITE_CONSTRAINT_UNIQUE` leaves the transaction open. `COMMIT` persists the earlier marker and not the duplicate. |
| `SQLITE-TX-02.missing-savepoint-then-commit` | `ROLLBACK TO` an unknown savepoint returns `SQLITE_ERROR`. The transaction stays usable, and `COMMIT` persists the earlier row and the follow-up. |
| `SQLITE-TX-04.release-then-outer-rollback` | `RELEASE` does not publish the table or the row. Outer `ROLLBACK` leaves neither. |
| `SQLITE-TX-03.reuse-while-open` | A second `BEGIN` fails. Insert and `COMMIT` on the same connection persist both units. |
| `SQLITE-TX-03.reuse-after-rollback` | After SQL `ROLLBACK`, the next unit commits only its own row. |
| `SQLITE-DDL.statement-error-rollback` | A unique violation inside a DDL transaction does not end it. `ROLLBACK` removes the tables and the rows. |
| `SQLITE-DDL.statement-error-commit` | The same sequence, then `COMMIT`, keeps both tables, the migration id, and the one account row. |
