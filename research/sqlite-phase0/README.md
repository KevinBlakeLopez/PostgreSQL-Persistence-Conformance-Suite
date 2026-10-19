# SQLite Phase 0

Research baseline for SQLite transaction semantics, using Python's standard-library `sqlite3`. It does not change the PostgreSQL suite, the catalogs, the harness, or any existing adapter.

The recorded run is `evidence/2026-10-19T13-20-36Z-py313/`. Fifty-seven variants ran three times each, on fresh database files. Every repetition agreed.

## Run

From this worktree (`spike/sqlite-phase0`):

```sh
/opt/homebrew/bin/python3.13 research/sqlite-phase0/controls/run_all.py
```

Python 3.12 or newer is required. The `python3` on `PATH` in this environment is 3.9.9, which has neither `Connection.autocommit` nor `sqlite_errorcode`. The script exits if the interpreter is older than 3.12.

Each invocation writes a new directory under `research/sqlite-phase0/evidence/<run-id>/`. It does not delete earlier runs and it does not open PostgreSQL.

## Layout

| Path | Contents |
| --- | --- |
| `controls/` | The experiments. `run_all.py` is the entry point. |
| `evidence/<run-id>/environment.json` | Interpreter, SQLite library, compile options, and a fresh file's PRAGMAs. |
| `evidence/<run-id>/summary.json` | Whether the three repetitions agreed. |
| `evidence/<run-id>/cases/` | One JSON file per variant per repetition: SQL trace, exceptions, error codes, `in_transaction`, and the second connection's reads. |
| `evidence/<run-id>/db/` | The database files those runs left behind. |
| `report/baseline-report.md` | Environment, method, and SQLITE-01 through SQLITE-06. |
| `report/compatibility-matrix.md` | Existing PPCS cases classified for SQLite. |
| `report/adapter-proposal.md` | Smallest way to add SQLite adapters later. |
| `report/decision-memo.md` | Whether SQLite is a useful PCS target, and what Phase 1 should be. |

## Phase 1 control

`control/run.py` is the sqlite3 control for the Phase 1 cases. It is not part of the PostgreSQL runner. See `control/README.md`.

```sh
/opt/homebrew/bin/python3.13 research/sqlite-phase0/control/run.py
```

## Transaction control in the baseline

The baseline issues `BEGIN`, `COMMIT`, and `ROLLBACK` itself, on connections opened with `autocommit=True`. Legacy transaction control and `autocommit=False` appear only in the variants that compare driver-managed transactions.
