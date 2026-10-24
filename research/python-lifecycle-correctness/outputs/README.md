# Recorded outputs

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

Raw evidence, kept as recorded. Nothing here was edited after recording except one thing: machine-specific paths in logs and `results.json` files were replaced with placeholders before commit. The placeholders are `<research>` (this research directory), `<venvs>` (the directory holding the virtual environments), `<python-3.13>` and `<python-3.14>` (the interpreters' installation prefixes), and `<home>`, `<user>` and `<tmp>`.

## Layout

| Directory | What it holds |
| --- | --- |
| `e1-run1/` | First full E1 pass (second harness version), 5 repetitions per case. Its two Hypercorn cases are not usable; see `harness-development/README.md` |
| `e1-run2/` | Second full E1 pass (third harness version: own process group, group kill at the hard limit, client snapshot), under `caffeinate -i` |
| `e1-run3-standard/` | The two core F1 cases on `uvicorn[standard]` (uvloop, httptools) |
| `e2-run1/` | E2, signal during lifespan startup, on 0.40.0 and 0.54.0 |
| `e3-run1/` | E3 (fourth harness version: tagged and logged replies, observation completeness): core F1 re-check, shared pool, cancellation-suppressing request, long cleanup, second Ctrl+C; unpatched, unbounded fix, bounded fix |
| `minimal-repro/` | `reproductions/minimal_repro.py`: a first pass, a hardened pass, and one manual run with `uvicorn`, `curl` and `kill` |
| `regression-test/` | `reproductions/uvicorn_regression_test.py` inside Uvicorn's suite: the first version (`with-fix.txt`, `without-fix.txt`, `repeated.txt`) and the hardened one (`hardened-repeated.txt`) |
| `stdlib-probe/` | `reproductions/wait_closed_probe.py` on Python 3.13.11, 3.14.2 and 3.9.9 |
| `uvicorn-test-suite-with-fix.txt`, `uvicorn-test-suite-with-bounded-fix.txt` | Uvicorn's own suite on `main` plus each candidate fix |
| `harness-development/` | Runs made while building the harness; not evidence for any finding |

Each case directory holds:

- `results.json`: the harness settings, interpreter and package versions, and for each repetition the command, exit status, timings, client view, every backend event (seconds relative to the signal), and the witness lines;
- `rep-N.server.log`: the server's combined output;
- `rep-N.witness.log`: the application's own unbuffered record.

`console.jsonl` in each run directory is what the harness printed.

## Per-case tables

Generated with `python reproductions/summarize.py outputs/<run>`.

- **n/r:** not recorded by the harness version that made the run.
- **Release reached backend / answered / cleanup finished:** the three cleanup states in findings.md.
- **Signal to exit:** wall-clock seconds from the first signal to the process exit. Run 1's `e1-15` includes host sleep in two repetitions; see `harness-development/README.md`.

### e1-run1

| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e1-01-in-time-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 OK ×5 | 0.87, 0.90 |
| e1-02-in-time-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 OK ×5 | 0.88, 0.94 |
| e1-03-exceeds-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.16, 2.23 |
| e1-04-exceeds-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.21, 2.26 |
| e1-05-exceeds-term-fast-release | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 4/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×4, (no response) ×1 | 2.17, 2.22 |
| e1-06-fastapi-bg-exceeds-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 202 Accepted ×5 | 2.20, 2.23 |
| e1-07-fastapi-bg-no-timeout-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 202 Accepted ×5 | 1.57, 1.62 |
| e1-08-hypercorn-exceeds-term | hypercorn 0.18.0, Python 3.13.11 | TERM | 5 | n/r | -9 ×5 | 5/5 | 0/5 | 0/5 | n/r | 0/5 | 0/5 | HTTP/1.1 200 ×4 | 20.01, 20.01 |
| e1-09-hypercorn-exceeds-int | hypercorn 0.18.0, Python 3.13.11 | INT | 5 | n/r | -9 ×5 | 5/5 | 0/5 | 0/5 | n/r | 0/5 | 0/5 | HTTP/1.1 200 ×4 | 20.01, 20.01 |
| e1-10-main-exceeds-term | uvicorn main e4981ad, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.16, 2.21 |
| e1-11-main-exceeds-int | uvicorn main e4981ad, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.22, 2.25 |
| e1-12-fix-exceeds-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.69, 2.73 |
| e1-13-fix-exceeds-int | uvicorn main e4981ad + fix, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.70, 2.76 |
| e1-14-fix-fastapi-bg-exceeds-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 202 Accepted ×5 | 2.70, 2.79 |
| e1-15-py314-exceeds-term | uvicorn 0.54.0, Python 3.14.2 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.23, 990.79 |

### e1-run2

| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e1-01-in-time-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 OK ×5 | 0.88, 0.94 |
| e1-02-in-time-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 OK ×5 | 0.93, 0.98 |
| e1-03-exceeds-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.16, 2.22 |
| e1-04-exceeds-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.22, 2.22 |
| e1-05-exceeds-term-fast-release | uvicorn 0.54.0, Python 3.13.11 | TERM | 20 | n/r | -15 ×20 | 0/20 | 20/20 | 20/20 | n/r | 18/20 | 20/20 | HTTP/1.1 500 Internal Server Error ×18, (no response) ×2 | 2.18, 2.21 |
| e1-16-exceeds-term-shielded | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.17, 2.22 |
| e1-17-exceeds-int-shielded | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.21, 2.26 |
| e1-06-fastapi-bg-exceeds-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 202 Accepted ×5 | 2.17, 2.26 |
| e1-07-fastapi-bg-no-timeout-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 202 Accepted ×5 | 1.58, 1.58 |
| e1-08-hypercorn-8s-work-term | hypercorn 0.18.0, Python 3.13.11 | TERM | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 ×5 | 8.58, 8.60 |
| e1-09-hypercorn-8s-work-int | hypercorn 0.18.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 200 ×5 | 8.59, 8.60 |
| e1-10-main-exceeds-term | uvicorn main e4981ad, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.17, 2.23 |
| e1-11-main-exceeds-int | uvicorn main e4981ad, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.22, 2.26 |
| e1-12-fix-exceeds-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.71, 2.76 |
| e1-13-fix-exceeds-int | uvicorn main e4981ad + fix, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.71, 2.75 |
| e1-14-fix-fastapi-bg-exceeds-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 5/5 | 0/5 | HTTP/1.1 202 Accepted ×5 | 2.71, 2.74 |
| e1-15-py314-exceeds-term | uvicorn 0.54.0, Python 3.14.2 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.18, 2.21 |

### e1-run3-standard

| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e1-18-standard-exceeds-term | uvicorn 0.54.0 [standard], Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | (no response) ×5 | 2.19, 2.21 |
| e1-19-standard-exceeds-int | uvicorn 0.54.0 [standard], Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 5/5 | n/r | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.21, 2.22 |

### e2-run1

| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e2-01-startup-signal-0.40.0-term | uvicorn 0.40.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 0/5 | 0/5 | n/r | 0/5 | 0/5 | n/a ×5 | 0.21, 0.22 |
| e2-02-startup-signal-0.40.0-int | uvicorn 0.40.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 0/5 | 0/5 | n/r | 0/5 | 0/5 | n/a ×5 | 0.23, 0.23 |
| e2-03-startup-signal-0.54.0-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | n/r | -15 ×5 | 0/5 | 5/5 | 0/5 | n/r | 0/5 | 5/5 | n/a ×5 | 0.34, 0.36 |
| e2-04-startup-signal-0.54.0-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | n/r | 0 ×5 | 0/5 | 5/5 | 0/5 | n/r | 0/5 | 5/5 | n/a ×5 | 0.34, 0.35 |

### e3-run1

| Case | Server | Signal | Reps | Observation complete | Exit status | Hung | Lifespan shutdown sent | Release reached backend | Release answered by backend | Cleanup finished | Lifespan shutdown before cleanup finished | Client saw | Signal to exit (median s, max s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e3-01-release-exceeds-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 | 5/5 | (no response) ×5 | 2.18, 2.21 |
| e3-02-release-exceeds-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | 5/5 | 0 ×5 | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.21, 2.27 |
| e3-03-fix-exceeds-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.70, 2.75 |
| e3-04-fix-exceeds-int | uvicorn main e4981ad + fix, Python 3.13.11 | INT | 5 | 5/5 | 0 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.70, 2.76 |
| e3-05-fixb-exceeds-term | uvicorn main e4981ad + bounded fix, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.79, 2.81 |
| e3-06-fixb-exceeds-int | uvicorn main e4981ad + bounded fix, Python 3.13.11 | INT | 5 | 5/5 | 0 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.80, 2.80 |
| e3-07-release-shared-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.20, 2.23 |
| e3-08-release-shared-int | uvicorn 0.54.0, Python 3.13.11 | INT | 5 | 5/5 | 0 ×5 | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 | 5/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.19, 2.27 |
| e3-09-fix-shared-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.69, 2.76 |
| e3-10-fixb-shared-term | uvicorn main e4981ad + bounded fix, Python 3.13.11 | TERM | 5 | 5/5 | -15 ×5 | 0/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 | HTTP/1.1 500 Internal Server Error ×5 | 2.79, 2.84 |
| e3-11-release-stubborn-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 3 | 3/3 | -15 ×3 | 0/3 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 2.20, 2.22 |
| e3-12-release-stubborn-int | uvicorn 0.54.0, Python 3.13.11 | INT | 3 | 3/3 | -9 ×3 | 3/3 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 20.01, 20.01 |
| e3-13-fix-stubborn-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 3 | 3/3 | -9 ×3 | 3/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | (no response) ×3 | 20.01, 20.01 |
| e3-14-fix-stubborn-int | uvicorn main e4981ad + fix, Python 3.13.11 | INT | 3 | 3/3 | -9 ×3 | 3/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | (no response) ×3 | 20.02, 20.03 |
| e3-15-fixb-stubborn-term | uvicorn main e4981ad + bounded fix, Python 3.13.11 | TERM | 3 | 3/3 | -15 ×3 | 0/3 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 4.20, 4.25 |
| e3-16-fixb-stubborn-int | uvicorn main e4981ad + bounded fix, Python 3.13.11 | INT | 3 | 3/3 | -9 ×3 | 3/3 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 20.01, 20.01 |
| e3-17-release-long-cleanup-term | uvicorn 0.54.0, Python 3.13.11 | TERM | 3 | 3/3 | -15 ×3 | 0/3 | 3/3 | 3/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 2.17, 2.23 |
| e3-18-fix-long-cleanup-term | uvicorn main e4981ad + fix, Python 3.13.11 | TERM | 3 | 3/3 | -15 ×3 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | HTTP/1.1 500 Internal Server Error ×3 | 7.17, 7.26 |
| e3-19-fixb-long-cleanup-term | uvicorn main e4981ad + bounded fix, Python 3.13.11 | TERM | 3 | 3/3 | -15 ×3 | 0/3 | 3/3 | 3/3 | 0/3 | 0/3 | 3/3 | (no response) ×3 | 4.19, 4.26 |
| e3-20-release-long-cleanup-int-int | uvicorn 0.54.0, Python 3.13.11 | INT then INT | 3 | 3/3 | 0 ×3 | 0/3 | 3/3 | 3/3 | 0/3 | 0/3 | 3/3 | HTTP/1.1 500 Internal Server Error ×3 | 2.19, 2.22 |
| e3-21-fix-long-cleanup-int-int | uvicorn main e4981ad + fix, Python 3.13.11 | INT then INT | 3 | 3/3 | 0 ×3 | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 | 0/3 | HTTP/1.1 500 Internal Server Error ×3 | 7.21, 7.27 |
| e3-22-fixb-long-cleanup-int-int | uvicorn main e4981ad + bounded fix, Python 3.13.11 | INT then INT | 3 | 3/3 | 0 ×3 | 0/3 | 0/3 | 3/3 | 0/3 | 0/3 | 0/3 | HTTP/1.1 500 Internal Server Error ×3 | 2.28, 2.33 |

