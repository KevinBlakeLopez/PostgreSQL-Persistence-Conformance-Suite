# Evidence for the P5a adversarial review

Run: 2026-10-18. The review is [`../../sqlalchemy-p5a-close-review.md`](../../sqlalchemy-p5a-close-review.md). The issue draft it reviews is [`../../sqlalchemy-p5a-close-issue-draft.md`](../../sqlalchemy-p5a-close-issue-draft.md). The original reproduction ([`../check/p5a_close.py`](../check/p5a_close.py)) and the files in [`../recorded/`](../recorded/) were not changed.

Server: PostgreSQL 18.6 in container `sa-tx-probe`, `127.0.0.1:55454`, database `scratch`, user `postgres`, `log_statement=all`. The scripts write only these tables: `p5a` (the draft's script), `p5a_review`, `p5a_review_f`, and `p5a_review_p2`. They were dropped after the run, except `p5a`.

## Layout

- `reviewed-draft.md`: the issue draft exactly as reviewed (approved 2026-10-18, 06:14, 11,071 bytes). The revised draft is [`../../sqlalchemy-p5a-close-issue-draft.md`](../../sqlalchemy-p5a-close-issue-draft.md). Its reproduction is [`../check/p5a_close_v2.py`](../check/p5a_close_v2.py), with output in `../check/p5a_close_v2.out`.
- `e0/`: the draft's reproduction, extracted and run in a fresh process.
  - `extract_and_compare.py` writes `draft_script.py`, `draft_observed.txt`, and `draft_script_55454.py`. The 55454 copy changes only the port. The script also compares that copy's AST with `check/p5a_close.py`.
  - `run.stdout`, `run.stderr`, `run.exit`, and `server.log` (the container log for the run window) are the run's outputs.
  - `check_record_hashes.py` checks the investigator's venv against the wheel's RECORD hashes. `compare_wheel_to_tag.sh` compares the fresh wheel with tag `rel_2_1_5`.
  - `checks.txt` holds the outputs of those checks and the interpreter and package versions.
- `harness/p5a_review.py`: the independent harness. It runs one case per process and prints JSON.
  - Its probes record and then call the original: psycopg's `_exec_command`, `psycopg.Connection.commit` and `rollback`, `ConnectionEvents.commit` and `rollback`, and `PoolEvents.reset`, `checkout`, `checkin`, and `invalidate`.
  - Each transaction runs one extra `select pg_current_xact_id_if_assigned()`.
  - A raw psycopg autocommit connection outside SQLAlchemy serves as the witness.
- `harness/run_cases.py`: runs each case in a fresh process. It writes `results/<case>.json` and `.stderr`, plus `<case>.serverlog`: the container log lines for that case's backend pids.
- `harness/summarize.py`: writes `harness/summary.txt`, one block per case.
- `harness/followups.py`: three follow-ups (`preping`, `alarm_outcome`, `asyncio`). Outputs are in `results/followup-<name>.stdout` and `.stderr`.
- `harness/p2_close.py`: the draft's case 1 sequence with psycopg2, for the version comparison. Outputs are in `results/p2-<venv>-<legacy|future>.stdout` and `.stderr`.

## Rerunning

```sh
cd docs/sqlalchemy-transaction-experiments/p5a-review
python3.13 -m venv venv   # venv/ is gitignored; run_cases.py expects it here
venv/bin/pip install 'SQLAlchemy==2.1.5' 'psycopg==3.3.6' 'psycopg-binary==3.3.6' 'psycopg2-binary==2.9.13' greenlet
cd harness
../venv/bin/python run_cases.py            # all cases; or name cases
../venv/bin/python summarize.py > summary.txt
../venv/bin/python followups.py preping    # also: alarm_outcome, asyncio
../venv/bin/python p2_close.py             # add "future" for 1.4 future mode
```

`run_cases.py` reads the container log with `DOCKER_CONTEXT=colima docker logs --since <case start> sa-tx-probe`.

For the version comparison, run `p2_close.py` with each interpreter listed in `e0/checks.txt`. 1.3.24 and 1.4.0 used Python 3.9.9 with psycopg2-binary 2.9.12. 1.4.54, 2.0.55, and 2.1.5 used Python 3.13.11 with psycopg2-binary 2.9.13.

The e0 run was:

```sh
cd e0
T0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
../venv/bin/python draft_script_55454.py > run.stdout 2> run.stderr; echo "exit=$?" | tee run.exit
DOCKER_CONTEXT=colima docker logs --since "$T0" sa-tx-probe > server.log 2>&1
diff -u draft_observed.txt run.stdout
```

## Provenance notes

- **Where it ran.** The review ran in a scratch directory and was copied here afterwards. Absolute paths in JSON and stderr (`<scratch>/…`) are that directory.
- **Inline checks.** `extract_and_compare.py` is the inline script that ran, saved unchanged. `check_record_hashes.py` and `compare_wheel_to_tag.sh` are also the inline commands. They were saved after the run, and only comment lines were added. `util/concurrency.py` was compared later than the other nine modules.
- **One case added later.** `explicit-builtin_timeout_error` was added to `p5a_review.py` after the main run, as two dictionary entries. Its results come from the edited file. Every other `results/<case>.*` came from the file before that addition; no other case's code changed. `summary.txt` was regenerated after the addition.
- **Draft snapshot.** `extract_and_compare.py` read the draft as it was on 2026-10-18 06:14 (11,071 bytes). `e0/draft_script.py` and `e0/draft_observed.txt` are that snapshot, and `reviewed-draft.md` is the whole file. The path the script reads now holds the revised draft, so to extract the reviewed version, point it at `reviewed-draft.md`.
