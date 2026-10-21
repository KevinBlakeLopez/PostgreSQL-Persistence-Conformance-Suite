# Django adapter

Django 6.1 `transaction.atomic()` against the suite's disposable PostgreSQL, through the PostgreSQL backend and psycopg 3. The adapter is a separate Python program. It speaks PPCS adapter protocol version 1 on stdin and stdout. It does not use node-kit.

Native mode is Django's default for this pattern: `CONN_MAX_AGE` 0 and no connection pool. A nested `transaction.atomic()` is the savepoint. The two TX-04 savepoint cases use that nested block. `TX-04.independent-inner` is unsupported, not applicable by design: Django has no propagation mode that promises an independent transaction, and `Model.objects.create` sends the `INSERT` when it is called. Both TX-05 forms set `OPTIONS` `isolation_level` to `psycopg.IsolationLevel.SERIALIZABLE` before the connection opens, which is Django's documented connection isolation option. `atomic()` and `set_autocommit()` take no isolation argument. Category C faults are injected in this process, once, before psycopg sends the statement. A withheld statement raises `RuntimeError` with no SQLSTATE, the same shape as a failed send. A rewritten `ROLLBACK TO SAVEPOINT` is sent under the name `ppcs_no_such_savepoint`.

`TX-03` is not run in native mode. Django's default closes the connection at the end of each request, so the native default does not hand a transactionally active connection to later work (`not-applicable-by-design`). The persistent mode sets `CONN_MAX_AGE` to `None`, which is Django's documented unlimited persistent connection, and calls `django.db.close_old_connections()` between the two units. That is the function `request_finished` runs. See [Persistent connections](https://docs.djangoproject.com/en/6.1/ref/databases/#persistent-connections).

`TX-01B.commit-reply-discarded` is not implemented. psycopg 3.3.6 `Connection.commit` calls `_exec_command(b"COMMIT")` and does not return until that command finishes (`psycopg/_connection_base.py`, `_commit_gen`). A probe on PostgreSQL 18.6 observed `transaction_status` `INTRANS` before `commit()` and `IDLE` when `commit()` returned. The caller never sees a lost COMMIT reply while the driver still reports a transaction in progress. Closing the socket after `commit()` returns is not that loss. The node-postgres reply-lost simulation closes the socket after the driver has already parsed the reply, so it is not this probe. The case stays NOT_RUN.

## Setup

From this directory, with Python 3.13:

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

From the repository root, start the suite's disposable PostgreSQL if it is not already up:

```sh
pnpm run pg:up
```

## Run

From the repository root:

```sh
node harness/run.mjs --adapter=django --case=CTL-01,TX-01A,TX-01B,TX-02,TX-03,TX-04,TX-05 --repeat=3
```

`TX-01B.commit-reply-discarded` is selected by the `TX-01B` prefix and recorded as NOT_RUN. The controls that gate these cases, including `pg-control`, run in the same command.

The run [`reports/examples/2026-10-18T13-08-22Z-6d8443`](../../reports/examples/2026-10-18T13-08-22Z-6d8443/summary.md) is the recording. `adapters/django/FINDINGS.md` is the per-case report.
