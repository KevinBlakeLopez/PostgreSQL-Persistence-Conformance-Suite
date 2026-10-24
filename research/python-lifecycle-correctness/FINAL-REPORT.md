# Final report: Python application shutdown and task lifecycle correctness

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

## Executive summary

The investigation asked whether widely used Python servers report a successful shutdown while breaking a lifecycle guarantee. It found one new, significant defect, in Uvicorn. Two further results confirmed problems that are already known.

**Uvicorn's graceful-shutdown timeout (F1).** When the timeout expires, Uvicorn cancels the in-flight request tasks and immediately sends `lifespan.shutdown`. It does not wait for those tasks to finish handling the cancellation. Their `finally` blocks therefore run at the same time as the application's lifespan shutdown, which typically closes the pools and clients they need. Then:

- under SIGTERM, Uvicorn re-raises the signal after its shutdown sequence, and the process ends before those blocks finish;
- under SIGINT, `asyncio.run` cancels them a second time.

The logs read "Application shutdown complete." and "Finished server process", and the exit status is the ordinary one for that signal. This contradicts the ASGI lifespan specification ("closed all active connections") and Uvicorn's own lifespan documentation, which shows pending requests completing before `lifespan.shutdown`.

The evidence comes from an outside observer: a separate process the application talks to, standing in for a database or lock service. It shows the following:

- In 131 of 131 unpatched repetitions where the work outlived the timeout, lifespan shutdown began within 1 ms of the cancelled task starting its cleanup.
- The cleanup was lost in 109 of them, and in every case where it needed more time than the lifespan shutdown took.
- When the cleanup used a pool that lifespan shutdown closes, it failed with `ConnectionError`.
- The same holds on Uvicorn 0.54.0 and `main`, Python 3.13 and 3.14, asyncio and uvloop, plain ASGI and FastAPI `BackgroundTasks`. In the FastAPI case the client had already received `202 Accepted`.

Two candidate fixes were tested against the same observer, Uvicorn's own suite, and adversarial cases:

- **Unbounded wait:** it fixes the order but hangs SIGTERM shutdown on a request that suppresses its cancellation, and disables force quit. It would be a regression.
- **Bounded wait:** at most one more timeout period, honoring force exit. It fixes the order for cleanup that fits within the bound and keeps shutdown bounded. Cleanup longer than the bound is still lost.

Which trade-off to accept is the maintainers' decision. The only prior trace upstream is an unanswered 2024 discussion that noted the missing `await` from source.

**Other results.**

- A signal during lifespan startup skipped lifespan shutdown in Uvicorn below 0.41.0 (F2, ALREADY FIXED, confirmed on 0.40.0 against 0.54.0).
- Hypercorn's `graceful_timeout` is not enforced on Python 3.12+ (F3). That is a DUPLICATE of pgjones/hypercorn#308, with a fix PR open.
- Several other candidates were already reported, documented, or not promising (see the candidate matrix).

**Recommendation.** After human review of the attached draft, open a Uvicorn "Potential Issue" discussion asking which post-timeout behavior the maintainers want. Offer a PR based on the bounded fix if they agree.

## Findings table

| ID | Project | Failure | Severity | Evidence | Classification | Upstream status |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Uvicorn 0.54.0, `main` `e4981ad` | Lifespan shutdown sent while the request tasks the graceful timeout cancelled are still running; their cleanup is then cut off (SIGTERM) or cancelled again (SIGINT) | Medium | 131 of 131 unpatched repetitions with an external observer; 60 of 60 patched; minimal reproduction; regression test; bounded-shutdown experiments | CONFIRMED DEFECT | Not tracked: discussion #2422 (source-only, closed as outdated); related PR #2882 closed |
| F2 | Uvicorn below 0.41.0 | Signal during lifespan startup: lifespan shutdown never sent | Medium (historical) | 0.40.0: 0 of 10 sent; 0.54.0: 10 of 10 | ALREADY FIXED | PR #2812, 0.41.0 |
| F3 | Hypercorn 0.18.0, Python 3.12+ | `graceful_timeout` not enforced | Medium | 10 of 10 (8.6 s shutdown with a 2 s timeout); stdlib probe | DUPLICATE | #308 open; PR #388 open |

## Most significant finding: F1

- **What happens.**
  1. `Server.shutdown()` waits up to `timeout_graceful_shutdown` for the requests.
  2. It calls `t.cancel()` on each remaining task.
  3. It awaits `lifespan.shutdown()` straight away.

  Cancelling only schedules a `CancelledError`, so the tasks start unwinding during the lifespan shutdown, concurrently with it. Once `serve()` returns:
  - SIGTERM is re-raised with its default disposition and the process ends;
  - under SIGINT, the restored `asyncio.Runner` handler leads `asyncio.run` to cancel every remaining task again.
- **Why it matters.** Cancellation handlers are where applications roll back, release locks, update job status and flush buffers. Here they run against resources the lifespan shutdown is closing, and on SIGTERM they do not finish at all. Nothing reports the interrupted cleanup; only the cancellation itself is logged.
- **How realistic the trigger is.** It needs `--timeout-graceful-shutdown`, which is off by default, and work that outlives it. That is exactly the case the option exists for, typically in deployments with a finite termination grace period (Kubernetes, systemd). SIGTERM is the signal those orchestrators send.
- **Guarantee violated.**
  - The ASGI lifespan specification: `lifespan.shutdown` is "sent to the application when the server has stopped accepting connections and closed all active connections".
  - Uvicorn's `docs/concepts/lifespan.md`: pending requests complete before `lifespan.shutdown`.
  - Uvicorn's `docs/server-behavior.md`: "all tasks have run to completion".

  The timeout documentation permits terminating requests, but says nothing about doing so concurrently with lifespan shutdown. Completion of arbitrary cleanup is not claimed as a guarantee.
- **Independent evidence.** A backend process recorded three states for every cleanup: request received, answer sent, application continued. Alongside it are the server's exit status and log order, the client's view, and an unbuffered witness file.
  - Under SIGINT, the 500 for the cancelled request was written after "Finished server process".
  - With a shared pool, the cleanup failed with `ConnectionError` while lifespan shutdown was closing that pool.
  - Both candidate fixes restore the order in the same harness.
- **Owner.** Uvicorn, `uvicorn/server.py`, `Server.shutdown()`. CPython's cancellation and `asyncio.run` behave as documented, and the application uses the documented pattern.

## Upstream opportunities

1. **Uvicorn F1.** A "Potential Issue" discussion (the project's required first step) with the minimal reproduction, then a PR if invited. The bounded fix is the starting point, and the measured trade-offs of both variants go with it. Draft: [upstream-drafts/uvicorn-discussion-draft.md](upstream-drafts/uvicorn-discussion-draft.md).
2. **Hypercorn F3.** Validate fix PR #388 with this harness and, if it holds, post a short validation comment.
3. **Uvicorn documentation.** Only if the maintainers decide the post-timeout overlap is intended: document it.

Details and remaining effort: [upstream-opportunities.md](upstream-opportunities.md).

## Engineering effort

| Item | Estimate |
| --- | --- |
| Time already spent | About 2.5 hours of active work, over about 4 hours of wall-clock time. The rest was the host asleep or the session idle |
| Additional verification | 1 to 1.5 h: run the minimal reproduction and the core harness cases on Linux (all evidence so far is from macOS); optionally Gunicorn with `uvicorn-worker` |
| Minimal fix | Done locally as the bounded diff (14 lines). 0.5 to 1 h to adapt it to whatever shape the maintainers prefer |
| Regression tests | One drafted and checked (fails on `main`, passes with both fixes). About 1 h for the second test the bounded variant needs: a request that suppresses its cancellation must not delay shutdown past the bound |
| Upstream submission | 0.5 to 1 h to review and approve the discussion text; 2 to 3 h for a PR if invited, plus review iterations |

## Recommended next action

**File an issue after human review.** For Uvicorn that means opening a "Potential Issue" discussion, which its contribution process requires before an issue or PR. Use the draft in `upstream-drafts/` once its exact text has been reviewed and approved, and after re-checking the upstream state.
