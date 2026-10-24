# Python application shutdown and task lifecycle correctness

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

## Objective

This study asked whether widely used Python servers and frameworks report a successful shutdown while breaking a lifecycle guarantee. Examples of such a break: work they own is abandoned, cleanup is cut off, or lifespan shutdown runs before the work it should follow. It applies the PPCS method:

- an explicit invariant;
- a minimal trigger;
- an outside observer;
- controls;
- repetition;
- source reading;
- an upstream check.

It is a research package for human review. Nothing was filed or posted upstream. The brief is [../python-lifecycle-investigation-prompt.md](../python-lifecycle-investigation-prompt.md).

## Scope

- **Examined:** Uvicorn (the main subject), Starlette and FastAPI (lifespan, `BackgroundTasks`), Hypercorn (as a comparison), and CPython asyncio as far as the servers depend on it (`Task.cancel`, `asyncio.run` teardown, `Server.wait_closed`).
- **Considered and set aside:** AnyIO, Trio, and the CPython `TaskGroup` and `timeout` internals. [candidate-matrix.md](candidate-matrix.md) gives the reasons.
- **Not examined:** ARQ, Dramatiq, Celery; Gunicorn with `uvicorn-worker`; Windows; HTTP/2 and WebSocket connections.
- **Independence from PPCS:** this study is separate from PPCS's PostgreSQL experiments. It uses no database, no PPCS adapter, and no PPCS infrastructure.

## Tested versions

| Component | Versions |
| --- | --- |
| Uvicorn | 0.54.0 (latest release, plain and `[standard]`); `main` at `e4981ad`; `main` plus each candidate fix; 0.40.0 for F2 |
| Starlette, FastAPI | 1.10.0, 0.162.0 |
| Hypercorn | 0.18.0 (`main` at `0e2311f` read) |
| AnyIO, h11, uvloop, httptools | 4.15.1, 0.16.0, 0.23.0, 0.9.0 |
| Python | CPython 3.13.11 and 3.14.2; 3.9.9 for one stdlib probe |
| Event loops | asyncio (plain install), `uvloop.Loop` (standard install) |
| OS | macOS 26.6.2, arm64 |

## Main conclusions

- **F1, CONFIRMED DEFECT (Uvicorn).** When `--timeout-graceful-shutdown` expires, Uvicorn cancels the request tasks and sends `lifespan.shutdown` without waiting for them.
  - **Order:** in 131 of 131 unpatched repetitions where the work outlived the timeout, lifespan shutdown began 0.06 to 0.97 ms after the cancelled task's cleanup began, while that task and its connection were still active.
  - **Lost cleanup:** that cleanup was lost in 109 of them. Under SIGTERM, the signal Uvicorn re-raises ends the process mid-cleanup; under SIGINT, `asyncio.run` cancels the cleanup again. When the cleanup used a pool that lifespan shutdown closes, it failed with `ConnectionError`.
  - **Reach:** it holds on the latest release and `main`, Python 3.13 and 3.14, asyncio and uvloop, plain ASGI and FastAPI `BackgroundTasks`.
  - **Candidate fixes:** an unbounded wait fixes the order but makes shutdown hang on a request that suppresses its cancellation, and breaks force quit. A bounded wait (at most one more timeout period, honoring force exit) fixes the order for cleanup that fits within the bound and keeps shutdown bounded. Both pass Uvicorn's existing tests.
- **F2, ALREADY FIXED (Uvicorn below 0.41.0).** A signal during lifespan startup skipped lifespan shutdown.
- **F3, DUPLICATE (Hypercorn on Python 3.12+).** `graceful_timeout` is not enforced. This is pgjones/hypercorn#308, with fix PR #388 open.

Details: [findings.md](findings.md). Ranked contribution options: [upstream-opportunities.md](upstream-opportunities.md). Draft discussion post (not posted): [upstream-drafts/uvicorn-discussion-draft.md](upstream-drafts/uvicorn-discussion-draft.md). Report: [FINAL-REPORT.md](FINAL-REPORT.md).

## Evidence and classification

**How an outcome is decided.** By an observer outside the server, not by the server's own messages. The harness is the application's backend, a TCP service in another process. It records three states of each cleanup:

1. its request reached the backend;
2. the backend answered;
3. the application received the answer and went on.

It also records the server's exit status, the HTTP client's view, and an unbuffered witness file written by the application.

**Controls:** a normal lifecycle; the suspect lifecycle; two corrected builds of Uvicorn; and an application-level protection (`asyncio.shield`) that turned out not to help.

**Classifications** use the brief's labels: CONFIRMED DEFECT, CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN, PRODUCTION RISK, APPLICATION RESPONSIBILITY, EXPECTED BEHAVIOR, INCONCLUSIVE, ALREADY FIXED and DUPLICATE. Runtime claims are backed by a recorded run. Statements from source reading are labelled as such in findings.md.

## Layout

| Path | Contents |
| --- | --- |
| `candidate-matrix.md` | Every candidate considered, with the reason it was selected or rejected |
| `findings.md` | Hypothesis, contract, setup, results, controls, source analysis, adversarial review and classification per finding |
| `upstream-opportunities.md` | Ranked upstream opportunities and the measured trade-offs of the candidate fixes |
| `upstream-drafts/` | A draft discussion post for Uvicorn, for human review |
| `FINAL-REPORT.md` | The report in the brief's section 14 format |
| `reproductions/` | Applications, harness, run scripts, minimal reproduction, draft regression test, candidate fixes as diffs, probe, summarizers |
| `outputs/` | Raw recorded evidence; see [outputs/README.md](outputs/README.md) |

## Running the experiments

The investigation used isolated virtual environments outside this repository. Nothing is installed into PPCS's own environment. Recreate them in a directory of your choice and export it as `LC_VENVS`:

```bash
export LC_VENVS=/path/to/venvs            # any directory outside the repository
PY313=python3.13 PY314=python3.14
$PY313 -m venv $LC_VENVS/venv-313 && $LC_VENVS/venv-313/bin/pip install uvicorn==0.54.0 starlette==1.10.0 fastapi==0.162.0 hypercorn==0.18.0
$PY313 -m venv $LC_VENVS/venv-313-std && $LC_VENVS/venv-313-std/bin/pip install "uvicorn[standard]==0.54.0"
$PY313 -m venv $LC_VENVS/venv-313-old && $LC_VENVS/venv-313-old/bin/pip install uvicorn==0.40.0
$PY314 -m venv $LC_VENVS/venv-314 && $LC_VENVS/venv-314/bin/pip install uvicorn==0.54.0

# Uvicorn's default branch and the two candidate fixes, built from a clone kept outside the repository.
# Run from this research directory, so that $PWD/reproductions resolves.
SRC=$LC_VENVS/src && mkdir -p $SRC
git clone https://github.com/Kludex/uvicorn.git $SRC/uvicorn && git -C $SRC/uvicorn checkout e4981ad
git -C $SRC/uvicorn worktree add $SRC/uvicorn-fix e4981ad && git -C $SRC/uvicorn-fix apply "$PWD/reproductions/uvicorn-await-cancelled-tasks.diff"
git -C $SRC/uvicorn worktree add $SRC/uvicorn-fixb e4981ad && git -C $SRC/uvicorn-fixb apply "$PWD/reproductions/uvicorn-await-cancelled-tasks-bounded.diff"
$PY313 -m venv $LC_VENVS/venv-313-main && $LC_VENVS/venv-313-main/bin/pip install $SRC/uvicorn
$PY313 -m venv $LC_VENVS/venv-313-fix && $LC_VENVS/venv-313-fix/bin/pip install $SRC/uvicorn-fix fastapi==0.162.0 starlette==1.10.0
$PY313 -m venv $LC_VENVS/venv-313-fixb && $LC_VENVS/venv-313-fixb/bin/pip install $SRC/uvicorn-fixb fastapi==0.162.0 starlette==1.10.0
```

Run them from `reproductions/`. Each run writes a new timestamped directory under `outputs/` and never overwrites earlier evidence. On macOS the scripts wrap each case in `caffeinate -i`.

```bash
cd reproductions
LC_VENVS=$LC_VENVS ./run-e1.sh     # F1 core cases, controls, FastAPI, Hypercorn, main, fix, Python 3.14
LC_VENVS=$LC_VENVS ./run-e2.sh     # F2: signal during lifespan startup, 0.40.0 vs 0.54.0
LC_VENVS=$LC_VENVS ./run-e3.sh     # bounded shutdown: suppressed cancellation, long cleanup, second Ctrl+C, shared pool

# the uvicorn[standard] cases (outputs/e1-run3-standard)
$LC_VENVS/venv-313/bin/python harness.py --reps 5 --case e1-18-standard-exceeds-term --python $LC_VENVS/venv-313-std/bin/python --timeout 2 --signal TERM
$LC_VENVS/venv-313/bin/python harness.py --reps 5 --case e1-19-standard-exceeds-int  --python $LC_VENVS/venv-313-std/bin/python --timeout 2 --signal INT

# single-file reproduction (exits 1 when the cleanup did not finish before lifespan shutdown)
$LC_VENVS/venv-313/bin/python minimal_repro.py [--sigint]

# stdlib probe: does Server.wait_closed() wait for an open connection?
python3.13 -I wait_closed_probe.py

# summaries and the category totals quoted in findings.md
python3 summarize.py ../outputs/e3-run1
python3 tally.py ../outputs
```

To run the draft regression test, copy `reproductions/uvicorn_regression_test.py` into a Uvicorn checkout's `tests/` directory. Install that checkout with its development dependencies and run `pytest -n 0 tests/<file>`. It fails on `main` and passes with either candidate fix.
