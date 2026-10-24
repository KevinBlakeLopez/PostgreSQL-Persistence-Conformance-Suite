# Findings

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

## Summary

| ID | Project | Failure | Severity | Evidence | Classification | Upstream status |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Uvicorn 0.54.0 and `main` `e4981ad` | When `--timeout-graceful-shutdown` expires, Uvicorn cancels the request tasks and sends `lifespan.shutdown` without waiting for them. Those tasks unwind concurrently with lifespan shutdown, and on SIGTERM the process ends before they finish | Medium | 131 unpatched repetitions with an outside observer, order violated in all 131; 60 patched repetitions in order; minimal reproduction; draft regression test; bounded-shutdown experiments on two candidate fixes | **CONFIRMED DEFECT** (lifecycle order). How to remedy it is a maintainer decision | Raised from source alone in discussion #2422 (2024; unanswered, closed as outdated). Related unmerged PR #2882. No issue, PR or test covers it |
| F2 | Uvicorn before 0.41.0 | A signal that arrives during lifespan startup makes the server exit without sending lifespan shutdown | Medium (historical) | 0.40.0: shutdown sent 0 of 10; 0.54.0: 10 of 10 | **ALREADY FIXED** | Fixed by PR #2812, released in 0.41.0 (2026-02-16) |
| F3 | Hypercorn 0.18.0 on Python 3.12+ | `graceful_timeout` is not enforced: shutdown waits for in-flight requests however long they take | Medium | 8 s of work with a 2 s timeout: exit after 8.6 s, request never cancelled, 10 of 10; stdlib probe of `Server.wait_closed()` | **DUPLICATE** | pgjones/hypercorn#308, open since 2025-06-23; fix PR #388 open |

The SIGTERM re-raise in `Server.capture_signals()` (candidate C3) is not reported separately. It is intentional (#1600), and here it mattered only by ending the process while F1 left cancelled tasks running.

## Environment

| Item | Value |
| --- | --- |
| Host | macOS 26.6.2, arm64 |
| Interpreters | CPython 3.13.11 and 3.14.2 (Homebrew) |
| Plain install (`pip install uvicorn`) | asyncio event loop, h11 0.16.0 |
| Standard install (`uvicorn[standard]`) | `uvloop.Loop` (uvloop 0.23.0) and `HttpToolsProtocol` (httptools 0.9.0), both confirmed from `Config` |
| Uvicorn builds | 0.54.0 (latest release); `main` at `e4981ad`; `main` plus each candidate fix (below); 0.40.0 for F2 |
| Other packages | Starlette 1.10.0, FastAPI 0.162.0, Hypercorn 0.18.0, AnyIO 4.15.1 |

`main` still reports version 0.54.0. Its `Server.shutdown()` differs from the release only in using `async with asyncio.timeout(...)` instead of `asyncio.wait_for(...)`.

Both candidate fixes are against `main`:

- **Unbounded fix,** [uvicorn-await-cancelled-tasks.diff](reproductions/uvicorn-await-cancelled-tasks.diff): after cancelling, `await asyncio.wait(self.server_state.tasks)`.
- **Bounded fix,** [uvicorn-await-cancelled-tasks-bounded.diff](reproductions/uvicorn-await-cancelled-tasks-bounded.diff): after cancelling, poll until the tasks are gone, for at most another `timeout_graceful_shutdown` seconds, and stop at a forced exit. The polling follows the style of `_wait_tasks_to_complete()`.

## How outcomes were decided

The harness ([reproductions/harness.py](reproductions/harness.py)) is also the application's backend. It is a TCP service in a separate process that logs every line the application sends, and answers each `CALL` with `OK <tag>` after a set delay that stands in for a remote service's latency. The application ([backend_link.py](reproductions/backend_link.py)) holds a connection for each unit of work:

1. `CALL work`: answered after 60 s. Controls: 0.3 s for in-time requests, 1 s for the background-task control, 8 s for Hypercorn.
2. In a `finally` block, `CALL release`: answered after 0.5 s, at once, or after 5 s depending on the case. This stands for a rollback, a lock release, or a job-status update.
3. `NOTE released`, sent only after the application received the release's answer.

The backend records three separate states of the cleanup:

1. **Reached the backend:** `CALL release` arrived.
2. **Answered by the backend:** `REPLY release`, logged from the harness version used for E3 onward.
3. **Finished:** `NOTE released` arrived, so the application received the answer and went on.

"Cleanup finished" in this document means state 3. Lifespan shutdown makes its own `CALL shutdown`, so the backend log orders the two.

The other records are:

- the application's witness file, written with unbuffered `os.write` so it survives the process being killed;
- the server's log and exit status;
- the HTTP client's view, including when its connection ended.

**Sequencing.** Barriers decide when the signal is sent: startup reached the backend, then the port accepted, then the unit of work reached the backend. The only fixed wait is F2's 0.2 s between the signal and releasing startup.

**Completeness.** A repetition counts only if every backend connection closed and the client finished; E3 records this per repetition. Checked retroactively, every earlier repetition was complete except the 10 run-1 Hypercorn ones, which are excluded (see `outputs/harness-development/README.md`).

**Reply attribution.** Before E3, replies were untagged. No reply could have been misattributed in those runs, because the 60 s work answer was never due within the observation window. A misattribution would also have made cleanup look finished, not lost. From E3 onward every reply names its call.

## F1. Uvicorn sends lifespan shutdown while the tasks its timeout cancelled are still running

### Hypothesis

When `timeout_graceful_shutdown` expires, `Server.shutdown()` cancels each request task and immediately awaits the lifespan shutdown. The cancelled tasks are still running their `except CancelledError` and `finally` blocks while the application's lifespan shutdown runs. After `serve()` returns:

- on SIGTERM, the re-raised signal ends the process before those blocks finish;
- on SIGINT, `asyncio.run` cancels them a second time.

### Contract

Two claims are kept apart:

- **Claim A (implementation):** Uvicorn does not await the tasks it cancels before lifespan shutdown and process exit.
- **Claim B (contract):** that violates a documented lifecycle order.

The sources for claim B:

- **ASGI lifespan specification** (`asgiref` `specs/lifespan.rst`, unchanged since `03571587bf`, 2023-03-12), on `lifespan.shutdown`:
  > Sent to the application when the server has stopped accepting connections and closed all active connections.

  This speaks of *connections*. A server could meet it by aborting connections without waiting for tasks.
- **Uvicorn's `docs/server-behavior.md`, "Graceful Process Shutdown":**
  > Uvicorn handles process shutdown gracefully, ensuring that connections are properly finalized, and all tasks have run to completion. During a shutdown period Uvicorn will ensure that responses and tasks must still complete within the configured timeout periods.
- **Uvicorn's `docs/concepts/lifespan.md`:** the sequence diagram places `AppTask->>AppTask: Complete pending requests` before `LifespanTask->>UserApp: {"type": "lifespan.shutdown"}`. This speaks of *tasks and requests*.
- **Uvicorn's `docs/settings.md`,** the option itself:
  > `--timeout-graceful-shutdown <int>` - Maximum number of seconds to wait for graceful shutdown. After this timeout, the server will start terminating requests.
- **CPython's `Task.cancel()` documentation (3.13):**
  > The coroutine then has a chance to clean up or even deny the request by suppressing the exception with a `try` ... ... `except CancelledError` ... `finally` block.

Terminating requests after the timeout is documented. Nothing says that `lifespan.shutdown` may be sent while terminated requests are still running, or that their connections may still be open. Nothing guarantees that arbitrary application cleanup completes either. This finding does not claim that it must.

### Setup and reproduction

- **Applications:** [asgi_app.py](reproductions/asgi_app.py) (plain ASGI, `GET /`) and [fastapi_app.py](reproductions/fastapi_app.py) (FastAPI `lifespan` plus `BackgroundTasks`, `POST /jobs` answered 202 before the job runs).
- **Server:** `python -m uvicorn <app> --host 127.0.0.1 --port <free> --lifespan on --timeout-graceful-shutdown 2`, as a child process in its own process group, with no shell.
- **Trigger:** a real `SIGTERM` or `SIGINT` sent to the server while the unit of work is in flight.
- **Commands:** [run-e1.sh](reproductions/run-e1.sh) (run twice) and [run-e3.sh](reproductions/run-e3.sh). The standard-install cases are listed in the README.
- **Single-file reproduction for maintainers:** [minimal_repro.py](reproductions/minimal_repro.py) (`python minimal_repro.py [--sigint]`). It prints a verdict and exits 1 when the cleanup did not finish before lifespan shutdown.

### Results

Totals by category, from [tally.py](reproductions/tally.py) over `outputs/e1-run1`, `e1-run2`, `e1-run3-standard` and `e3-run1`. Each category is defined by case name in that script.

| Category | Reps | Cleanup finished | Lifespan shutdown began before cleanup finished | Lifespan shutdown began after the cleanup began |
| --- | --- | --- | --- | --- |
| A. Unpatched, work outlives the timeout, 0.5 s cleanup | 100 | **0** | **100** | 0.06 to 0.79 ms (median 0.28) |
| B. Unpatched, release answered at once | 25 | 22 | **25** | 0.08 to 0.97 ms (median 0.40) |
| C. Unpatched, 5 s cleanup | 6 | **0** | **6** | 0.07 to 0.50 ms (median 0.27) |
| D. Unbounded fix, 0.5 s cleanup | 45 | 45 | 0 | 504.5 to 595.0 ms (median 507.6) |
| E. Bounded fix, 0.5 s cleanup | 15 | 15 | 0 | 504.3 to 608.1 ms (median 605.7) |
| F. Controls: work finishes in time, or no timeout | 30 | 30 | 0 | 505.4 to 606.6 ms (median 550.0) |

So in 131 unpatched repetitions where the work outlived the timeout:

- the order was violated in all 131;
- the cleanup was lost in 109: always when it needed 0.5 s or 5 s, and in 3 of 25 when the backend answered at once (a race with lifespan shutdown).

Category A spans every variant:

| Variant | Reps | Notes |
| --- | --- | --- |
| Plain ASGI, SIGTERM and SIGINT, 0.54.0 and `main` | 40 | |
| Python 3.14.2, SIGTERM | 10 | |
| Standard install (uvloop, httptools), SIGTERM and SIGINT | 10 | |
| Release wrapped in `asyncio.shield()`, SIGTERM and SIGINT | 10 | |
| Release through a lifespan-owned pool, SIGTERM and SIGINT | 10 | |
| Tagged-reply re-run, SIGTERM and SIGINT | 10 | |
| FastAPI background job, SIGTERM | 10 | The client received `202 Accepted` before the job ran |

Per-case tables are in [outputs/README.md](outputs/README.md) and in each run's `results.json`.

**What the external observer shows** (E3, tagged replies). For every unpatched repetition:

- the release reached the backend (state 1);
- the backend never answered it before the process ended (state 2 not reached);
- `NOTE released` never arrived (state 3 not reached).

**Shared resource.** When the release goes through a lifespan-owned pool that lifespan shutdown closes first, the unpatched cleanup failed with `ConnectionError` raised inside the cleanup, 0 of 10 finished. Witness order: `request.cleanup.begin`, `lifespan.shutdown.begin`, `lifespan.pool.closed`, `request.cleanup.interrupted ConnectionError`. Both fixes completed it, 10 of 10.

**A connection was still in use after lifespan shutdown.** Under SIGINT, the server log shows `Application shutdown complete.`, then `Finished server process`, then `Exception in ASGI application` for the request's second, message-less `CancelledError`, then the access-log line for the 500. A response was written on a request connection after the lifespan shutdown had completed. That is ASGI's "closed all active connections" observed false at the time `lifespan.shutdown` was sent. Under SIGTERM the connection stayed open until the process ended.

**Minimal reproduction.** Two passes, three runs per variant, in [outputs/minimal-repro/](outputs/minimal-repro/). The second pass is the hardened script:

| Build | Signal | Cleanup finished before lifespan shutdown | Exit status |
| --- | --- | --- | --- |
| 0.54.0 | TERM | 0 of 6 | −15 |
| 0.54.0 | INT | 0 of 6 | 0 |
| `main` `e4981ad` | TERM | 0 of 6 | −15 |
| `main` + unbounded fix | TERM | 6 of 6 | −15 |
| `main` + unbounded fix | INT | 3 of 3 (first pass only) | 0 |
| `main` + bounded fix | TERM | 3 of 3 | −15 |
| `main` + bounded fix | INT | 3 of 3 | 0 |

Unpatched output under SIGTERM runs in this order:

1. `Waiting for application shutdown.`, logged before the cancelled request prints `cleanup started`;
2. `app: lifespan shutdown`;
3. `Application shutdown complete.` and `Finished server process`;
4. no `cleanup finished`.

Exit status −15 means the server ended by the SIGTERM Uvicorn re-raises. That is the ordinary outcome of a SIGTERM, and a shell reports it as 143.

### Bounded shutdown: do the candidate fixes keep the deadline?

E3 ([run-e3.sh](reproductions/run-e3.sh), `outputs/e3-run1/`) uses a 2 s timeout, a 20 s hard limit, and 3 repetitions per cell. A "hung" cell means the harness killed the process group at the hard limit.

| Case | Unpatched 0.54.0 | Unbounded fix | Bounded fix |
| --- | --- | --- | --- |
| Request suppresses cancellation, SIGTERM | exit 2.2 s; work abandoned | **hung** | exit 4.2 s (2 s timeout + 2 s bound) |
| Request suppresses cancellation, SIGINT | **hung** | **hung** | **hung** |
| 5 s cleanup, SIGTERM | exit 2.2 s; cleanup lost | exit 7.2 s; cleanup finished | exit 4.2 s; cleanup lost |
| 5 s cleanup, second Ctrl+C once the cleanup reached the backend | exit 2.2 s; cleanup lost | exit 7.2 s; **second Ctrl+C ignored**; cleanup finished; lifespan shutdown skipped | exit 2.3 s; force exit honored; cleanup lost; lifespan shutdown skipped |

What the table establishes:

- **The unbounded fix is a regression.** A request that suppresses its cancellation hangs SIGTERM shutdown where the release exits at 2.2 s. Cleanup longer than the timeout extends shutdown past it. A second Ctrl+C, which Uvicorn advertises as "CTRL+C to force quit", no longer works while it waits. It should not be proposed as is.
- **The bounded fix keeps a deadline,** at most one more `timeout_graceful_shutdown`, and honors force exit. It restores the order for cleanup that fits within the bound (15 of 15). Cleanup longer than the bound is still lost, two seconds later than today. In E3 it is never worse than the release except for that extra bound.
- **Unpatched Uvicorn has no hard deadline under SIGINT either.** With a request that suppresses cancellation, the release hangs too: `asyncio.run` waits for every task in its teardown. Today's bound under SIGTERM exists because the re-raised signal kills the process, not because Uvicorn enforces one. A task that suppresses cancellation is application misbehavior (CPython: "actively discouraged"); this is recorded as context, not as a finding.

There is no change that both guarantees a deadline and guarantees completion of arbitrary cleanup. Which property to keep after the deadline is a maintainer decision. See [upstream-opportunities.md](upstream-opportunities.md).

### Controls

1. **Normal path.** Requests finishing inside the timeout, and background jobs with no timeout: cleanup finished before lifespan shutdown, 30 of 30. The harness records a completed cleanup when there is one.
2. **Suspect path.** Categories A to C above.
3. **Corrected variants.** Unbounded fix 45 of 45, bounded fix 15 of 15, both in order.
   - **Existing tests:** both builds pass every collected non-benchmark test in Uvicorn's suite, 1335 passed and 20 skipped ([with fix](outputs/uvicorn-test-suite-with-fix.txt), [with bounded fix](outputs/uvicorn-test-suite-with-bounded-fix.txt)). The 16 errors in each run are collection errors for two benchmark modules, `tests/benchmarks/test_http.py` and `test_ws.py`, counted once per pytest-xdist worker (8 workers). They occur because the optional `pytest-codspeed` plugin was not installed, so those benchmarks were not run.
4. **Application-level protection.** Wrapping the release in `asyncio.shield()` did not help, 0 of 10. Under SIGTERM the process ends regardless. Under SIGINT, `asyncio.run`'s teardown cancels every task, including the one `shield()` created.
5. **Regression test.** [uvicorn_regression_test.py](reproductions/uvicorn_regression_test.py), in Uvicorn's test style, records the order of `request cleanup started`, `request cleanup finished` and `lifespan.shutdown`.
   - **How it works:** the cleanup blocks on an event the test controls. The test gives the server 0.5 s to start lifespan shutdown while the cleanup is blocked, then releases it. A server that misbehaves within 0.5 s fails regardless of timing, and a correct server cannot fail. It asserts nothing about the HTTP response and runs under an outer 10 s timeout.
   - **Result:** it fails on `main`, with `lifespan.shutdown` at index 1. It passes with either fix, 3 of 3 each ([outputs/regression-test/hardened-repeated.txt](outputs/regression-test/hardened-repeated.txt)). An earlier version that used a fixed 0.1 s cleanup and asserted a 500 behaved the same, 4 of 4 each way.

### Source analysis

Phase 1, source reading, `uvicorn/server.py` at `e4981ad`:

```python
        try:
            async with asyncio.timeout(self.config.timeout_graceful_shutdown):
                await self._wait_tasks_to_complete()
        except TimeoutError:
            logger.error(
                "Cancel %s running task(s), timeout graceful shutdown exceeded",
                len(self.server_state.tasks),
            )
            for t in self.server_state.tasks:
                t.cancel(msg="Task cancelled, timeout graceful shutdown exceeded")

        # Send the lifespan shutdown event, and wait for application shutdown.
        if not self.force_exit:
            await self.lifespan.shutdown()
```

`t.cancel()` only schedules the `CancelledError`. Nothing awaits `self.server_state.tasks` afterwards, and the connections are not closed. The first suspension inside `self.lifespan.shutdown()` lets the cancelled tasks start unwinding, and from then on the two proceed concurrently. These lines are unchanged in substance since the option was added (#1950, 2023).

`server_state.tasks` includes Starlette and FastAPI background tasks. They run inside the request task after the response is sent: Starlette's `Response.__call__` awaits `self.background()`.

What happens after `serve()` returns depends on the signal:

- **SIGTERM.** `capture_signals()` restores the previous handler (normally `SIG_DFL`) and calls `signal.raise_signal()` (#1600, 0.29.0). The process ends inside the running event loop, so `asyncio.run` never finalizes the tasks still unwinding.
- **SIGINT.** The restored handler is the one `asyncio.Runner.run()` installed (CPython `asyncio/runners.py`, lines 105 to 107 in 3.13). It cancels the main task. The runner raises `KeyboardInterrupt`, and `_cancel_all_tasks()` calls `task.cancel()` on every remaining task and waits for them. `uvicorn.main.run()` swallows the `KeyboardInterrupt`, so the exit status is 0.

Phase 2, runtime: each step was observed.

- the order, in the witness and backend logs;
- the re-raised SIGTERM, in the −15 exit status;
- the second cancellation, in the SIGINT tracebacks (a `CancelledError` with no message);
- the teardown's wait, in the SIGINT hang with a cancellation-suppressing task.

**Existing tests.** `tests/supervisors/test_signal.py::test_sigint_abort_req` asserts only that the request is cut off and that "Cancel 1 running task(s)" is logged, using an in-process `handle_exit(SIGINT)`. Nothing checks the cancelled task's cleanup or its order against lifespan shutdown.

**Related upstream work.** The maintainer's PR #2882, "Add abort phase to graceful shutdown" (closed unmerged 2026-04-06), would have aborted the connections after the timeout and before lifespan shutdown. Its test asserted the order `shutdown`, `abort`, `lifespan`. It does not await the cancelled tasks, so it would satisfy the ASGI sentence about connections while the tasks still raced lifespan shutdown.

### Adversarial review

1. **Is the behavior documented?** Terminating requests after the timeout is. Sending `lifespan.shutdown` while those requests' tasks and connections are still active is not. Uvicorn's own documents describe pending requests completing first.
2. **Does the framework own the task?** Yes. These are Uvicorn's request tasks, tracked in `server_state.tasks`, and Uvicorn cancels them. FastAPI background tasks run inside them.
3. **Did the application misuse the API?** No. The cleanup is a plain `finally`, the pattern CPython documents for cancellation. The `asyncio.shield()` variant fails the same way. Only the E3 "suppresses cancellation" cases misbehave, on purpose.
4. **Does the timeout permit abandonment?** It permits terminating the requests. Whether "terminating" includes letting their cancellation handlers overlap lifespan shutdown, or be cut off by the process exit, is not stated. That is the one contract question for the maintainer. The ordering defect does not depend on the answer.
5. **Is it an unavoidable result of process termination?** No. The termination is Uvicorn's own re-raised SIGTERM, after its shutdown sequence has finished, not an outside SIGKILL. With either fix, the same path ends the process only after cleanup that fits the wait.
6. **Did the test introduce the failure?** The first backend version could not read a release queued behind a pending call. That was found and fixed before any recorded run (`outputs/harness-development/`). The minimal reproduction uses no harness and shows the same order. Both fixes pass in the same harness. Replies are tagged from E3 on.
7. **Is the outcome externally observable?** Yes: the backend process, the exit status, the client's response, and the order of the server's log lines.
8. **Does it depend on scheduling luck?** The order is deterministic: 131 of 131. Losing the cleanup is deterministic whenever the cleanup needs longer than lifespan shutdown, and a race otherwise (3 of 25 lost with an instant release). The hardened regression test makes the failing direction event-driven.
9. **Is it already reported?** Discussion #2422 (2024-08-12) noted from source that the cancelled tasks are not awaited. It gave no consequence or runtime evidence, received no replies, and was closed as "outdated" on 2025-03-16. No issue or PR was found when re-checked on 2026-10-24 at 21:21 UTC. PR #2882 is related but closed. Open PR #3217 changes the start of `shutdown()` for latency, not this block.
10. **Does the default branch fix it?** No. `main` at `e4981ad` reproduces it.
11. **Would the fix break legitimate behavior?** The unbounded fix would: E3 shows a SIGTERM hang and a broken force quit. The bounded fix passed every E3 case without a new hang. It adds up to one more timeout period to shutdown, and still loses cleanup that outlasts the bound.
12. **Who owns it?** Uvicorn (`Server.shutdown`). CPython's cancellation and `asyncio.run` behave as documented, and the application does what CPython recommends.

### What this does not show

- **No database was involved.** Whether a remote operation took effect when its request reached the server but the answer was never read depends on that system. Here the backend received `CALL release` in every unpatched repetition. What is shown is that the application's cleanup sequence did not complete, and that lifespan shutdown overlapped it.
- **No production incident or frequency data.** The trigger needs `--timeout-graceful-shutdown` set (it is off by default) and work that outlives it, which is the situation the option exists for.
- **The FastAPI `202 Accepted` case.** It shows the job's own cleanup was cut off after the client was told the job was accepted. FastAPI does not promise that background tasks are durable, and no durability claim is made.
- **Not tested:** Gunicorn with `uvicorn-worker`, Windows, HTTP/2 and WebSocket connections.

### Classification

**CONFIRMED DEFECT,** in the lifecycle order. On the graceful-timeout path Uvicorn sends `lifespan.shutdown` while the request tasks it cancelled are still running and their connections are still open. That contradicts the ASGI lifespan specification's statement about when `lifespan.shutdown` is sent, and Uvicorn's own documentation of the shutdown order.

- **Reproducibility:** 131 of 131 repetitions, on the latest release and `main`.
- **Owner:** the responsible code is identified (`Server.shutdown`).
- **Remedy:** a correction exists that keeps shutdown bounded. Wait, bound, or abort is the maintainer's choice.

Not claimed: that Uvicorn must guarantee completion of arbitrary application cleanup after the deadline.

**Severity: medium.**

- **Consequence:** cleanup for work the server terminated (rollbacks, lock releases, job-status updates, flushes) runs concurrently with lifespan shutdown, which typically closes the resources that cleanup uses (shown with a pool). On SIGTERM it is cut off by the process exit.
- **Visibility:** the cancellation is logged as an error; the interrupted cleanup is not reported.

## F2. Signal during lifespan startup skipped lifespan shutdown (before 0.41.0)

- **Hypothesis.** A SIGTERM or SIGINT received while lifespan startup is still running makes Uvicorn return from `_serve()` without sending `lifespan.shutdown`, although startup completed.
- **Contract.** The same ASGI lifespan text. Uvicorn's own bind-failure path shows the intended invariant: `startup()` calls `self.lifespan.shutdown()` before `sys.exit`, so once startup completed, shutdown is sent.
- **Setup.** [run-e2.sh](reproductions/run-e2.sh). The backend withholds its answer to the application's startup call. The harness sends the signal while startup waits, then releases it 0.2 s later.

| Build | Signal | Reps | Lifespan shutdown sent | Exit status |
| --- | --- | --- | --- | --- |
| 0.40.0 | TERM | 5 | **0** | −15 |
| 0.40.0 | INT | 5 | **0** | 0 |
| 0.54.0 | TERM | 5 | 5 | −15 |
| 0.54.0 | INT | 5 | 5 | 0 |

- **Limit of the runtime evidence.** The 0.2 s wait is not a barrier: the harness cannot see the server's signal handler run.
  - On 0.40.0 the outcome confirms the timing by itself. Lifespan shutdown can only be skipped if `should_exit` was set before startup returned; a signal handled later would have gone through the normal shutdown.
  - On 0.54.0 both orders lead to a lifespan shutdown, so those 10 runs do not show by themselves that the fix covers a signal during startup. That part rests on the source and on upstream's regression test `test_shutdown_on_early_exit_during_startup`.
- **Source.** 0.40.0's `_serve()` has `if self.should_exit: return` after `startup()`. Since PR #2812 (released in 0.41.0, 2026-02-16) it runs `shutdown()` whenever `self.started` is set.
- **Classification: ALREADY FIXED.** It is kept because it shows the harness detects a missing lifespan shutdown, and because deployments pinned below 0.41.0 still have it.

## F3. Hypercorn's graceful timeout is not enforced on Python 3.12+

- **Observation.** This came up while using Hypercorn as a differential for F1.
  - With `--graceful-timeout 2` and 8 s of work, Hypercorn 0.18.0 on Python 3.13 never cancelled the request. It exited with status 0 after 8.6 s, with the cleanup finished before lifespan shutdown (10 of 10, `outputs/e1-run2/`).
  - In run 1, with 60 s of work, it was still running at the 20 s hard limit. Run 1 is not usable as recorded: the harness killed only the supervisor, and the worker carried on as an orphan, completing the work at 60 s.
- **Mechanism.**
  - **Source reading:** `worker_serve()` (`src/hypercorn/asyncio/run.py`, lines 164 to 170 at `0e2311f`) awaits `server.wait_closed()` before the bounded `asyncio.wait_for(gathered_server_tasks, config.graceful_timeout)`.
  - **Runtime:** a stdlib probe ([outputs/stdlib-probe/](outputs/stdlib-probe/)) shows `Server.wait_closed()` still waiting after 1 s for an open connection on 3.13.11 and 3.14.2, and returning at once on 3.9.9.
- **Contract.** Hypercorn's configuration documentation describes `graceful_timeout` as "Time to wait after SIGTERM or Ctrl-C for any remaining requests (tasks) to complete", default 3 s.
- **Consequence for F1.** Hypercorn keeps the cleanup-before-lifespan order only because it never cancels anything. It is not evidence about how a server should order cancellation and lifespan shutdown.
- **Classification: DUPLICATE** of pgjones/hypercorn#308, open since 2025-06-23, which names the same `wait_closed()` call. Fix PR #388 is open; it was not reviewed or tested here.

## Candidates not tested

See [candidate-matrix.md](candidate-matrix.md) for each rejected candidate and why. ARQ, Dramatiq and Celery were not examined, so no claim is made about them.
