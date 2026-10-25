# SQLite transaction-state divergence

Investigation date: 2026-10-25. Written by: Claude Opus 5.5 (max).

What happens when SQLite ends a transaction that SQLAlchemy or Django still believes it owns?

SQLite does this for `RAISE(ROLLBACK)`, `ON CONFLICT ROLLBACK`, and some `SQLITE_FULL`, `SQLITE_INTERRUPT` and `SQLITE_IOERR` errors, including a real disk full on an ordinary single-row insert. SQLAlchemy 2.1.6 and 2.0.55 keep their transaction active and, in the default and recipe configurations, report the later commit as successful. With the SAVEPOINT loop from SQLAlchemy's ORM guide and the `BEGIN` recipe from its SQLite documentation, a real disk-full during an import left `session.commit()` returning normally while 23 of the 29 records the application reported as committed were absent. Under `autocommit=False`, SQLAlchemy reports a masked error, can keep a pooled connection checked out, and can hand a connection to later work outside any transaction; the common driver cause is that CPython's `sqlite3` stops keeping a transaction open. Django 6.1.2 handles the same trigger correctly in its supported patterns.

The findings, their classifications and the root-cause analyses are in [`findings.md`](findings.md). The environment and method are in [`methodology.md`](methodology.md). Nothing has been filed upstream; [`upstream/`](upstream/) holds a facts package for SQLAlchemy and a draft for CPython.

This study does not change PPCS's harness, catalogs, specifications or adapters. It extends `research/sqlite-phase0/`.

## Layout

| Path | Contents |
| --- | --- |
| `findings.md` | Findings table with the required fields, details, root causes, production reachability, adversarial checks |
| `methodology.md` | Environment, transaction-control configurations, evidence layers, controls, caveats, limits |
| `repro/common.py` | Recording helpers shared by the experiments: errors with their chains, the trace, the independent observer, the callback sink, path scrubbing, the three-repetition runner |
| `repro/trace_check.py` | Checks what repeated trace lines mean |
| `repro/sqlite01_raw.py` | SQLITE-01: `sqlite3` alone, four transaction-control configurations |
| `repro/sqlite02_core.py` | SQLITE-02: SQLAlchemy Core |
| `repro/sqlite03_session.py` | SQLITE-03: SQLAlchemy ORM `Session` |
| `repro/sqlite04_savepoint.py` | SQLITE-04: savepoints, Core and ORM |
| `repro/sqlite05_realistic.py` | SQLITE-05: `SQLITE_FULL`, `SQLITE_INTERRUPT` and `EFBIG` with `sqlite3` |
| `repro/sqlite05b_batch.py` | SQLITE-05b: SQLAlchemy's documented SAVEPOINT loops |
| `repro/sqlite05c_enospc.py`, `repro/sqlite05c_enospc_container.py` | SQLITE-05c: a real `ENOSPC` in a disposable Linux container |
| `repro/sqlite06_django.py`, `repro/sdapp/` | SQLITE-06: Django `atomic()` |
| `repro/minimal/` | Five standalone reproductions, no harness |
| `repro/minimal_matrix.py` | Runs them in four environments, three times each |
| `repro/summarize.py` | Generates `output/RESULTS.md` |
| `repro/run_all.sh` | Records every experiment in order |
| `repro/requirements.txt` | `sqlalchemy==2.1.6`, `django==6.1.2` |
| `output/<experiment>/<run>/` | `environment.json`, `summary.json`, `cases/<variant>.rep<N>.json`; the database files are not kept (`.gitignore`) |
| `output/RESULTS.md` | One generated table per experiment |
| `output/run-all-2026-10-25T17-21-26Z.log` | Console output of the recorded `run_all.sh` invocation |
| `upstream/` | Prior-report search, the SQLAlchemy facts package, the CPython draft |

## Setup

From this directory (`research/sqlite-transaction-state-divergence/`), on macOS with Homebrew Python:

```sh
/opt/homebrew/bin/python3.13 -I -m venv .venv
.venv/bin/python -I -m pip install --only-binary=:all: -r repro/requirements.txt
/opt/homebrew/bin/python3.14 -I -m venv .venv-py314
.venv-py314/bin/python -I -m pip install --only-binary=:all: sqlalchemy==2.1.6
/opt/homebrew/bin/python3.13 -I -m venv .venv-sa20
.venv-sa20/bin/python -I -m pip install --only-binary=:all: sqlalchemy==2.0.55
```

The container experiments need Docker on the colima context, the image `python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962` already present, and the two Linux wheels in `.wheels-linux/` (checked by SHA-256 before every run):

```sh
.venv/bin/python -I -m pip download --only-binary=:all: \
  --platform manylinux_2_17_aarch64 --platform manylinux2014_aarch64 \
  --python-version 3.13 --implementation cp --abi cp313 \
  sqlalchemy==2.1.6 -d .wheels-linux
```

The containers run with `--rm --network none`, a tmpfs at `/data`, and this directory mounted read-only. They are named `ppcs-sqlite-sd-*` and do not touch other containers.

## Reproduce

Everything, in order, then `output/RESULTS.md` (a few minutes; the recorded invocation took 2 min 50 s before the matrix grew to five scripts):

```sh
./repro/run_all.sh
```

One experiment:

```sh
.venv/bin/python -I repro/sqlite02_core.py
```

Each run writes a new directory under `output/<experiment>/`. Set `STUDY_OUTPUT` to another directory for a scratch run.

The minimal reproductions run with any interpreter that has the stated packages:

```sh
.venv/bin/python -I repro/minimal/sa_savepoint_batch.py on-conflict
.venv/bin/python -I repro/minimal/sa_savepoint_batch.py page-limit
.venv/bin/python -I repro/minimal/sa_core_false_commit.py
.venv/bin/python -I repro/minimal/sa_session_close_leak.py
.venv/bin/python -I repro/minimal/sqlite3_autocommit_false.py
```

## Recorded runs

All recorded with the code in this directory; every variant agreed over three repetitions.

| Experiment | Run | Variants |
| --- | --- | --- |
| trace check | `output/trace-check/2026-10-25T17-21-27Z-d37fff/` | 4 |
| SQLITE-01 | `output/sqlite01-raw/2026-10-25T17-21-27Z-737440/` | 28 |
| SQLITE-02 | `output/sqlite02-core/2026-10-25T17-21-27Z-ca780e/` | 81 |
| SQLITE-03 | `output/sqlite03-session/2026-10-25T17-21-29Z-85d1f6/` | 90 |
| SQLITE-04 | `output/sqlite04-savepoint/2026-10-25T17-22-39Z-184fba/` | 54 |
| SQLITE-05 | `output/sqlite05-realistic/2026-10-25T17-22-41Z-001c2c/` | 20 |
| SQLITE-05b | `output/sqlite05b-batch/2026-10-25T17-22-43Z-4b67f2/` | 36 |
| SQLITE-05c | `output/sqlite05c-enospc/2026-10-25T17-22-54Z-9e213e/` | 4 |
| SQLITE-06 | `output/sqlite06-django/2026-10-25T17-22-45Z-b4103f/` | 24 |
| minimal reproductions | `output/minimal-matrix/2026-10-25T18-21-01Z-556213/` | 5 scripts × 4 environments × 3 |

The minimal matrix was recorded again after the `run_all.sh` invocation, once `sa_session_close_leak.py` and `sqlite3_autocommit_false.py` had been added; the log names the earlier matrix run.

## Paths in the record

Recorded strings pass through `common.scrub()`: this directory appears as `$STUDY`, the worktree as `$WORKTREE` and the home directory as `$HOME`. The container's paths are its own (`/repro`, `/data`, `/usr/local/lib/...`).

## Development runs not kept

These runs were made while the harness was still changing and are not in `output/`:

| Run | Why it was replaced | Compared with the recorded run |
| --- | --- | --- |
| `sqlite01-raw/2026-10-25T15-57-07Z-bc39bc` | before error chains and per-step warnings were recorded | `observed` identical for all 28 variants |
| `trace-check/2026-10-25T16-16-22Z-d85152` | same | identical for all 4 |
| `sqlite02-core/2026-10-25T16-02-42Z-db343a` | before pool-log routing, the end-of-scenario `gc.collect()` count and the 2 s `pool_timeout` | outcome fields identical for all 81 |
| `minimal-matrix/2026-10-25T16-43-07Z-1e0e4e` and `…T17-23-10Z-e6b0ad` | before two scripts were added | outputs of the three shared scripts byte-identical |

A first development run of SQLITE-03 had one variant whose repetitions disagreed: its log handler, attached to SQLAlchemy's module logger, credited one repetition with records from earlier repetitions' connections that the garbage collector finalized later. That is why pool records are now routed by `pool_logging_name` (`methodology.md`). A development version of SQLITE-06 recorded write errors without letting them propagate; it was fixed before the recorded run.

## What was not done

- No MySQL, and no async experiment: SQLITE-07 stopped at source reading because the remaining question belongs to the Python cancellation study (`findings.md`, X1).
- No fix was implemented in SQLAlchemy or CPython.
- Nothing was filed, posted or pushed.
