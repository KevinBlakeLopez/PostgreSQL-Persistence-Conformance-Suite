# PY-7: SQLAlchemy P5a evidence (a failed `commit()`, then `close()`)

Published 2026-10-26 (UTC). Written by: Claude Opus 5.5 (max).

This is the evidence behind PY-7 in [the tracker](../../python-upstream-contribution-tracker.md) (section "PY-7"). It is copied from the author's private repository, `python-orm-transactions`, at commit `90cfaf3`, so that it can be checked and re-run. Nothing has been posted to SQLAlchemy.

**The finding.** Suppose `commit()` raises before `COMMIT` reaches PostgreSQL, and the code then calls `Connection.close()`. The connection goes back to the pool with its transaction still open: the pool's reset gets `transaction_was_reset=True` and sends no `ROLLBACK`. The next checkout then runs inside that transaction, and its `COMMIT` commits the failed unit's writes. This was reproduced on SQLAlchemy 2.1.6 with psycopg 3.3.6 and PostgreSQL 18.6. It also happens through a `commit` event listener that raises, and through psycopg's own `transaction()` block; neither replaces a DBAPI method.

## Contents

| Path | What it is |
| --- | --- |
| `sqlalchemy-p5a-close-review.md` | The adversarial review of 2026-10-18: verdict, reproduction validity, contract and source assessment, real-world applicability |
| `sqlalchemy-transaction-experiments/check/` | The reproduction: `p5a_close.py`; `p5a_close_v2.py`, which adds a pool `reset` listener; and `p5a_close_v2.out`, its recorded output |
| `sqlalchemy-transaction-experiments/p5a-review/` | The review's evidence: `e0/`, the draft's script run in a fresh process; `harness/`, the independent harness with every case's results; and a README |
| `sqlalchemy-transaction-experiments/p5a-review/chk-7/` | CHK-7, the rerun on SQLAlchemy 2.1.6, with `FACTS.md` |
| `sqlalchemy-transaction-experiments/p5a-review/chk-7/supplement/` | The two triggers that replace no DBAPI method, re-run on 2.1.6 |
| `SOURCE-HASHES.txt` | Each file's SHA-256 in the source repository and here |

## Reproducing it

The scripts connect to `postgresql://postgres@127.0.0.1:55454/scratch`. Use a throwaway server: they drop and recreate their tables.

```sh
docker run -d --name p5a-pg -e POSTGRES_PASSWORD=<password> -p 127.0.0.1:55454:5432 \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336
docker exec p5a-pg psql -U postgres -c "create database scratch"   # once the server is up
python3 -m venv venv
venv/bin/pip install --only-binary=:all: SQLAlchemy==2.1.6 psycopg==3.3.6 psycopg-binary==3.3.6

# The reproduction: no output from diff means the run matched the recorded one.
PGPASSWORD=<password> venv/bin/python sqlalchemy-transaction-experiments/check/p5a_close_v2.py \
  | diff sqlalchemy-transaction-experiments/check/p5a_close_v2.out -

# A trigger that replaces no DBAPI method: one JSON document per run.
PGPASSWORD=<password> venv/bin/python sqlalchemy-transaction-experiments/p5a-review/harness/p5a_review.py explicit-listener
```

`p5a_close_v2.py` also writes two `Exception during reset or similar` entries to stderr, from its cases 2 and 3; that is expected. In the harness's JSON, the leak shows as `second_checkout.same_xid_as_first: true` and `second_checkout.visible_after_next: ["doomed", "next"]`. The other cases are listed in `harness/p5a_review.py`, under `CASES`. The READMEs in `p5a-review/`, `chk-7/` and `chk-7/supplement/` give the full commands, including the server-log checks.

## How this copy differs from the source

- **Local paths are replaced by placeholders,** in 38 files: `<venv>` for a run's virtualenv, `<investigator-venv>` for the virtualenv behind the investigation's recorded runs, `<scratch>` for the directory a run started in, and `<repo>` for the source repository's checkout. `SOURCE-HASHES.txt` marks those files. Nothing else was edited. Where a document lists a file's SHA-256, it is the source's: compare it with the first column of `SOURCE-HASHES.txt`.
- **The SQLAlchemy issue draft is not included:** `sqlalchemy-p5a-close-issue-draft.md`, and `p5a-review/reviewed-draft.md`, the snapshot of it that the review used. The author writes any SQLAlchemy text in their own words, as SQLAlchemy's `.github/CONTRIBUTING.md` (lines 48–65) asks. The draft's code and output are here: `p5a-review/e0/` holds the reviewed version's script and Observed block, and `check/p5a_close_v2.py` is the same program as the revised version's script.
- **Links that point outside this copy** lead into the source repository, which is private:
  - `docs/sqlalchemy-p5a-close-issue-draft.md`, linked from `sqlalchemy-p5a-close-review.md`, `sqlalchemy-transaction-experiments/p5a-review/README.md`, `sqlalchemy-transaction-experiments/p5a-review/chk-7/README.md`
  - `docs/sqlalchemy-transaction-experiments/p5a-review/reviewed-draft.md`, linked from `sqlalchemy-p5a-close-review.md`
  - `docs/sqlalchemy-transaction-experiments/recorded`, linked from `sqlalchemy-transaction-experiments/p5a-review/README.md`
- **Paths written as `../python-orm-transactions/…`** in the documents refer to the source repository's checkout.
