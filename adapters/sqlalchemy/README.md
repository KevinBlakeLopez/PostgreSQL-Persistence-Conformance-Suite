# SQLAlchemy adapter

Speaks [the PPCS adapter protocol](../../docs/protocol.md). It does not use `adapters/node-kit/`.

Implemented cases: `CTL-01.commit`, `CTL-01.rollback`, and `TX-02.savepoint-rollback-not-sent`.

`TX-02.savepoint-rollback-not-sent` withholds the next `ROLLBACK TO SAVEPOINT` inside this process, before psycopg sends it, then reports `after-fault` and raises. That is the same client-side fault the Node adapters inject in `pg.Client.query`.

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
