# Final report: Python application shutdown and task lifecycle correctness

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

## Executive summary

The investigation asked whether widely used Python servers report a successful shutdown while breaking a lifecycle guarantee. It found one new, significant defect, in Uvicorn. Two other results matched problems already known upstream.

**Uvicorn's graceful-shutdown timeout (F1).** When the timeout expires, Uvicorn cancels the in-flight request tasks and immediately initiates lifespan shutdown. It neither waits for the cancelled tasks nor closes their connections. Two things follow:

- **Specification level.** Immediately before Uvicorn initiates lifespan shutdown, its own registry still holds the request's connection, open, with the task still running (10 of 10 instrumented runs). That contradicts the ASGI lifespan specification ("closed all active connections") and Uvicorn's lifespan documentation.
- **Application level.** The cancelled requests' cleanup runs concurrently with the application's lifespan shutdown, which typically closes the pools and clients that cleanup needs.
  - Under SIGTERM, Uvicorn re-raises the signal and the process ends before the cleanup finishes.
  - Under SIGINT, `asyncio.run` cancels the cleanup a second time.
  - Either way, the logs still read "Application shutdown complete." and "Finished server process".

An outside observer, a separate process standing in for a database or lock service, recorded:

- lifespan shutdown starting first in 166 of 166 unpatched repetitions (macOS and Linux) where the work outlived the timeout;
- the cleanup not finishing before the process exited in 144 of them. Its request reached the remote side each time, so the remote outcome is unknown;
- a `ConnectionError` inside the cleanup when it used a pool that lifespan shutdown closes;
- the same on Uvicorn 0.54.0 and `main`, Python 3.13 and 3.14, asyncio and uvloop, plain ASGI and FastAPI `BackgroundTasks`. In the FastAPI case the client had already received `202 Accepted`.

Two candidate fixes were tested against the same observer, Uvicorn's suite, and adversarial cases:

- **Unbounded wait:** it fixes the order, but hangs SIGTERM shutdown on a request that suppresses its cancellation, and disables force quit. That is a regression.
- **Bounded wait** (at most one more timeout period, honoring force exit): it fixes the order for cleanup that fits the bound and avoids that hang. Longer cleanup still does not finish, and `asyncio.run`'s SIGINT teardown can still hang on a task that suppresses cancellation.

The remedy is a policy choice for the maintainers. The only prior trace upstream is an unanswered 2024 discussion noting the missing `await` from source.

**Other results.**

- A signal during lifespan startup skipped lifespan shutdown in Uvicorn below 0.41.0 (F2, ALREADY FIXED; confirmed on 0.40.0 against 0.54.0).
- Hypercorn's `graceful_timeout` is not enforced on Python 3.12+ (F3, DUPLICATE of pgjones/hypercorn#308; fix PR open).
- Other candidates were already reported, documented, or not promising (see the candidate matrix).

**Recommendation.** After human review of the attached draft, open a Uvicorn "Potential Issue" discussion asking which post-timeout behavior the maintainers want, and offer a PR if they agree.

## Findings table

| ID | Project | Failure | Severity | Evidence | Classification | Upstream status |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Uvicorn 0.54.0, `main` `e4981ad` | Lifespan shutdown initiated while request connections are still open and the tasks the graceful timeout cancelled are still running. Their cleanup then does not finish before the process exits (SIGTERM) or is cancelled again (SIGINT) | Medium | Uvicorn's registry immediately before lifespan shutdown: connection open, 10 of 10; 166 of 166 unpatched repetitions with an external observer (macOS and Linux); 85 of 85 patched; minimal reproduction; regression test; bounded-shutdown experiments | CONFIRMED DEFECT | Not tracked: discussion #2422 (source-only, closed as outdated); related PR #2882 closed |
| F2 | Uvicorn below 0.41.0 | Signal during lifespan startup: lifespan shutdown never sent | Medium (historical) | 0.40.0: 0 of 10 sent; 0.54.0: 10 of 10 | ALREADY FIXED | PR #2812, 0.41.0 |
| F3 | Hypercorn 0.18.0, Python 3.12+ | `graceful_timeout` not enforced | Medium | 10 of 10 (8.6 s shutdown with a 2 s timeout); stdlib probe | DUPLICATE | #308 open; PR #388 open |

## Most significant finding: F1

- **What happens.**
  1. `Server.shutdown()` waits up to `timeout_graceful_shutdown` for the requests.
  2. It calls `t.cancel()` on each remaining task.
  3. It awaits `lifespan.shutdown()` straight away, without awaiting those tasks or closing their connections.

  Cancelling only schedules a `CancelledError`, so the tasks start unwinding during the lifespan shutdown, concurrently with it. Once `serve()` returns:
  - SIGTERM is re-raised with its default disposition and the process ends;
  - under SIGINT, the restored `asyncio.Runner` handler leads `asyncio.run` to cancel every remaining task again.
- **Why it matters.** Cancellation handlers are where applications roll back, release locks, update job status and flush buffers. Here they run against resources the lifespan shutdown is closing, and on SIGTERM they do not finish before the process exits. What happened to remote operations they had already sent is not established. Nothing reports the interrupted cleanup; only the cancellation itself is logged.
- **How realistic the trigger is.** It needs `--timeout-graceful-shutdown`, which is off by default, and work that outlives it. That is exactly the case the option exists for, typically in deployments with a finite termination grace period (Kubernetes, systemd). SIGTERM is the signal those orchestrators send.
- **Guarantee violated.**
  - The ASGI lifespan specification: `lifespan.shutdown` is "sent to the application when the server has stopped accepting connections and closed all active connections".
  - Uvicorn's `docs/concepts/lifespan.md`: pending requests complete before `lifespan.shutdown`.
  - Uvicorn's `docs/server-behavior.md`: "all tasks have run to completion".

  The registry evidence below meets the specification-level claim directly: a connection is still active when lifespan shutdown begins. The overlap of cleanup and teardown is the application-level consequence. The two reinforce each other but are not the same claim.

  The timeout documentation permits terminating requests, but says nothing about doing so concurrently with lifespan shutdown. Completion of arbitrary cleanup is not claimed as a guarantee.
- **Independent evidence.** A backend process recorded three states for every cleanup: request received, answer sent, application continued. Alongside it are the server's exit status and log order, the client's view, and an unbuffered witness file.
  - A diagnostic log line, reading Uvicorn's own `server_state` immediately before it initiates lifespan shutdown, showed the request's connection open and its task not done (10 of 10).
    - With the bounded fix or on the normal path, both were empty (15 of 15).
    - By source reading, nothing between that line and the shutdown message being queued gives control back to the event loop.
    - The regression test reads the same registry when the application receives the message: 1 connection on `main`, 0 with either fix.
  - The client saw its connection end after lifespan shutdown began in 121 of 121 unpatched repetitions, and before it with the fixes. Both timestamps come from one process.
  - With a shared pool, the cleanup failed with `ConnectionError` while lifespan shutdown was closing that pool (15 of 15, macOS and Linux).
  - Both candidate fixes restore the order in the same harness, on macOS and Linux.
- **Owner.** Uvicorn, `uvicorn/server.py`, `Server.shutdown()`. CPython's cancellation and `asyncio.run` behave as documented, and the application uses the documented pattern.

## Upstream opportunities

1. **Uvicorn F1.** A "Potential Issue" discussion (the project's required first step) with the minimal reproduction, then a PR if invited. The bounded fix is the starting point, and the measured trade-offs of both variants go with it. Draft: [upstream-drafts/uvicorn-discussion-draft.md](upstream-drafts/uvicorn-discussion-draft.md).
2. **Hypercorn F3.** Validate fix PR #388 with this harness and, if it holds, post a short validation comment.
3. **Uvicorn documentation.** Only if the maintainers decide the post-timeout overlap is intended: document it.

Details and remaining effort: [upstream-opportunities.md](upstream-opportunities.md).

## Engineering effort

| Item | Estimate |
| --- | --- |
| Time already spent | About 3 hours of active work, over about 5 hours of wall-clock time. The rest was the host asleep or the session idle. This includes the Linux validation and the registry diagnostic |
| Additional verification | Linux is done (Debian 13 container, 50 repetitions plus the minimal reproduction). Optional: Gunicorn with `uvicorn-worker`, 0.5 to 1 h |
| Minimal fix | Done locally as the bounded diff (14 lines). 0.5 to 1 h to adapt it to whatever shape the maintainers prefer |
| Regression tests | Two drafted and checked; both fail on `main` and pass with both fixes. One is remedy-neutral (no registered connection when the application receives `lifespan.shutdown`); the other applies only to a waiting remedy (the cancelled cleanup finishes first). About 1 h for a third if the bounded wait is chosen: a request that suppresses its cancellation must not delay Uvicorn's own wait past the bound |
| Upstream submission | 0.5 to 1 h to review and approve the discussion text; 2 to 3 h for a PR if invited, plus review iterations |

## Recommended next action

**File an issue after human review.** For Uvicorn that means opening a "Potential Issue" discussion, which its contribution process requires before an issue or PR. Use the draft in `upstream-drafts/` once its exact text has been reviewed and approved, and after re-checking the upstream state.
