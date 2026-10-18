# SQLAlchemy adapter

Speaks [the PPCS adapter protocol](../../docs/protocol.md). It does not use `adapters/node-kit/`.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, and `TX-02.savepoint-rollback-not-sent`.

`TX-02.savepoint-rollback-not-sent` withholds the next `ROLLBACK TO SAVEPOINT` inside this process, before psycopg sends it, then reports `after-fault` and raises. That is the same client-side fault the Node adapters inject in `pg.Client.query`. At `after-fault` the session is `idle in transaction` and still holds both transaction ids.

The SQLAlchemy FAIL is the same ending as Lucid, MikroORM, and `pg-control` unsafe. The outer API reports a commit, PostgreSQL commits, and both the outer and inner rows are visible. The session is idle afterward, so TX-02.2 holds. Recorded in `results/2026-10-17T23-08-15Z-6704a7`: three repetitions agreed, xid 5788 committed, markers `outer` and `inner` both visible.

TypeORM's FAIL on this case is not that ending. After the same withheld rollback it sends `RELEASE SAVEPOINT`, reports a commit, and leaves the session `idle in transaction`. Teardown then aborts the transaction, so neither row remains. TX-02.1 and TX-02.2 both fail. In the PPCS 0.3.0 recording that transaction is xid 2279. Do not describe TypeORM as having committed the inner write.

`pg-control` correct sends `ROLLBACK` after the same withheld statement and passes.

## Setup

`pnpm run setup` skips this directory because it has no `package.json`.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The manifest command is `./.venv/bin/python main.py`, run with this directory as the working directory.

## Run

From the suite root, with the disposable server up:

```sh
node harness/run.mjs --adapter=sqlalchemy --case=TX-02
```

`CTL-01` runs as well. The runner schedules it for every adapter mode, and a scenario result is inconclusive unless both controls pass.
