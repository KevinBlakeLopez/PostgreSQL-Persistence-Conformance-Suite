# Candidate matrix

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This matrix was written before any experiment ran. Its confidence column records what was known at that point: source reading, documentation, and upstream search. Experiments and their results are in [findings.md](findings.md).

## Versions examined

| Component | Latest release (PyPI, 2026-10-24) | Default branch read |
| --- | --- | --- |
| Uvicorn | 0.54.0 | `Kludex/uvicorn` `main` at `e4981ad` (2026-10-24) |
| Starlette | 1.10.0 | `Kludex/starlette` `main` at `8aa828c` (2026-10-24) |
| FastAPI | 0.162.0 | not cloned; not needed for the selected candidates |
| Hypercorn | 0.18.0 | `pgjones/hypercorn` `main` at `0e2311f` (2025-11-08) |
| AnyIO | 4.15.1 | not cloned |

Uvicorn 0.54.0's `server.py` differs from `main` only in replacing `asyncio.wait_for(...)` with `async with asyncio.timeout(...)` around `_wait_tasks_to_complete()`. Neither form awaits the tasks it cancels.

## Summary

| ID | Project | Candidate | Decision | Main reason |
| --- | --- | --- | --- | --- |
| C1 | Uvicorn | `--timeout-graceful-shutdown` cancels request tasks but does not await them before lifespan shutdown and process exit | **Selected (E1)** | Clear documented order, realistic trigger, single owner, only prior mention is an unanswered source-level discussion |
| C2 | Uvicorn | Signal during lifespan startup skips lifespan shutdown | **Selected as a historical control (E2)** | Fixed in 0.41.0 (#2812). Cheap to confirm on old vs current release, and it checks that the harness detects a skipped shutdown |
| C3 | Uvicorn | Exit by re-raising SIGTERM ends the process before `asyncio.run` finalizes remaining tasks | **Tested inside E1 as a variable** | Mechanism, not an independent defect: intentional since 0.29.0 (#1600). It matters only through what is still running when `serve()` returns |
| C4 | Uvicorn | Lifespan shutdown has no deadline and cannot be aborted | Rejected | Already reported (discussion #2716, open) |
| C5 | Uvicorn | Force quit (second Ctrl+C) does not cancel ongoing tasks | Rejected | Reported (discussion #2525); maintainer replied "it runs as expected" |
| C6 | Uvicorn | One connection in h11 `ERROR` state makes shutdown raise and skip lifespan shutdown | Rejected | Already reported (discussion #3108; PR #3215 closed 2026-10-19) |
| C7 | uvicorn-worker | Gunicorn's `graceful_timeout` is not passed to Uvicorn's `timeout_graceful_shutdown` | Rejected | Known (uvicorn PR #2094, maintainer: "PR welcome on uvicorn-worker"); the consequence is Gunicorn's documented SIGKILL |
| C8 | Hypercorn | `startup_timeout` expiry leaves resources acquired during startup | Rejected | Source reading: `asyncio.Runner` teardown cancels and awaits the lifespan task, so an application `finally` runs; startup never completed, so no shutdown is owed |
| C9 | Hypercorn | `graceful_timeout` path | **Used as a differential control in E1** | Source reading: `asyncio.wait_for(gather(...))` waits for cancelled tasks before lifespan shutdown. Not a defect candidate. In E1 it turned out that on Python 3.12+ the timeout is never reached at all (C17), so it is not a usable differential for cancellation order |
| C10 | Starlette / FastAPI | `BackgroundTasks` lost at shutdown | Merged into C1 | Background tasks run inside the request task after the response, so the server's task tracking owns them; tested as an E1 variant |
| C11 | Starlette / FastAPI | Client-disconnect cancellation interrupting cleanup (streaming generators, yield dependencies) | Rejected for this phase | Client-disconnect trigger, not shutdown; long public history in FastAPI and Starlette discussions; ownership split between app, framework and server |
| C12 | FastAPI | Exit order of yield dependencies relative to background tasks | Rejected | Documented behavior changes (0.106.0 and later releases) |
| C13 | CPython asyncio | `TaskGroup`, `timeout`, `wait_for` cancellation edge cases | Rejected | Heavily examined; several fixed upstream (for example `wait_for` reimplemented on `asyncio.timeout` in 3.12). High duplicate risk, no specific hypothesis |
| C14 | AnyIO | Cancel scopes, shielded cleanup | Rejected for this phase | No concrete hypothesis; semantics documented and well tested |
| C15 | Trio | Nursery cancellation | Rejected | Low production web reach; strict, documented semantics |
| C16 | ARQ, Dramatiq, Celery | Worker shutdown, acknowledgement, retry | Not examined | Tier 3; broker infrastructure; time box. Not evaluated, so no claim is made about them |
| C17 | Hypercorn | `graceful_timeout` not enforced on Python 3.12+ | Added after the matrix (found in E1); see findings.md F3 | Already reported as pgjones/hypercorn#308; fix PR #388 open |

## Selected candidates

### C1. Uvicorn graceful-shutdown timeout does not await cancelled tasks

| Field | Value |
| --- | --- |
| Framework | Uvicorn 0.54.0 and `main` `e4981ad` |
| API | `Server.shutdown()` with `timeout_graceful_shutdown` set (`--timeout-graceful-shutdown`) |
| Invariant | Lifespan shutdown happens after in-flight requests and their tasks have finished. Sources: the ASGI lifespan spec, Uvicorn's server-behavior and lifespan docs (quoted in findings.md) |
| Trigger | SIGTERM while a request or a Starlette/FastAPI background task outlives the configured timeout. Typical of rolling deploys on Kubernetes or systemd with a finite grace period |
| Suspected failure | After the timeout, `shutdown()` calls `t.cancel()` on each request task, then immediately awaits `self.lifespan.shutdown()`. The cancelled tasks unwind concurrently with the application's lifespan shutdown, which may close resources they still use. When the signal was SIGTERM, `capture_signals()` then re-raises SIGTERM with the default disposition, ending the process before tasks that are still unwinding finish their `finally` blocks |
| Severity | Hypothesis: cleanup of in-flight work interrupted or run against closed resources, with no error in the exit path. The process exits by SIGTERM, which orchestrators treat as a normal stop |
| Existing coverage | Discussion #2422 (2024-08-12) noted from source that the cancelled tasks are not awaited. No replies; closed as "outdated" 2025-03-16. No runtime evidence or consequence was given there. No issue or PR found. Uvicorn's tests (`tests/supervisors/test_signal.py::test_sigint_abort_req`) check only that the request is cut off and the "Cancel 1 running task(s)" message is logged, using an in-process `handle_exit(SIGINT)`. No test checks the cancelled task's cleanup, its order relative to lifespan shutdown, or SIGTERM. Found later, in the upstream comparison: the maintainer's own PR #2882 ("Add abort phase to graceful shutdown", closed unmerged 2026-04-06) aborted connections after the timeout and before lifespan shutdown, with a test asserting the order `shutdown`, `abort`, `lifespan`. No reason for closing it is recorded on the PR. It shows the post-timeout order was considered upstream, but aborting connections does not make the cancelled tasks finish |
| Reproduction cost | Low: one small app, one harness, real SIGTERM, an append-only witness file |
| Ownership | Uvicorn (`uvicorn/server.py`, `Server.shutdown`) |
| Confidence at selection | Source reading only. The control flow is clear; the consequences are not yet observed |

### C2. Signal during lifespan startup (historical control)

| Field | Value |
| --- | --- |
| Framework | Uvicorn before 0.41.0 (behavior); 0.54.0 (fixed) |
| API | `Server._serve()` |
| Invariant | Once lifespan startup completed, the server sends lifespan shutdown |
| Trigger | SIGTERM while lifespan startup is still running (slow startup, pod terminated during rollout) |
| Suspected failure | Before #2812, `_serve()` returned early when `should_exit` was set, so lifespan shutdown was never sent |
| Existing coverage | Fixed by PR #2812, released in 0.41.0 (2026-02-16) |
| Reproduction cost | Very low; reuses E1's harness |
| Ownership | Uvicorn |
| Confidence | Fix confirmed in source and release notes; runtime not yet observed |
| Why run it | It confirms the harness can detect a skipped lifespan shutdown (a positive control for the witness), and it classifies C2 as ALREADY FIXED from observation rather than from release notes alone |

### C3. SIGTERM re-raise (variable inside E1)

`Server.capture_signals()` restores the previous handlers and calls `signal.raise_signal()` for each captured signal after `_serve()` returns. For SIGTERM, the previous handler is normally `SIG_DFL`, so the process ends at that moment, inside the running event loop. For SIGINT, the previous handler is the one `asyncio.Runner` installed, so the main task is cancelled and `asyncio.run` cancels and awaits the remaining tasks. This was introduced in 0.29.0 (#1600) on purpose, and maintainers defended it in discussion #2547. E1 runs each case under both signals, because the consequence of C1 may depend on which signal ended the server.
