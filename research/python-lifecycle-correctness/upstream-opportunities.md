# Upstream opportunities

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

Nothing has been filed, posted or proposed upstream. Upstream state was last checked on 2026-10-24 at 21:21 UTC.

## Ranking

| Rank | Opportunity | Severity | Production reachability | Confidence | Fix feasibility | Upstream receptiveness | Impact per engineering hour | Remaining effort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Uvicorn: lifespan shutdown overlaps the requests the graceful timeout cancelled (F1) | Medium | Needs `--timeout-graceful-shutdown` (opt-in) and work that outlives it, which is the case the option exists for. Also covers FastAPI `BackgroundTasks` | High: 166 of 166 repetitions; release and `main`; macOS and Linux; asyncio and uvloop; Uvicorn's own registry at the boundary | A bounded fix exists and is tested; the remedy is a design choice | High: very active maintainer (commits on 2026-10-24); shutdown is an active area in 2026 | High | About 1 h to a reviewed discussion post; 3 to 5 h more for a PR if invited |
| 2 | Hypercorn: validate the open fix for `graceful_timeout` on Python 3.12+ (F3) | Medium | Every Hypercorn deployment on Python 3.12+ with long requests | High for the behavior; PR #388 not tested | The fix is already proposed upstream | Uncertain: last push to the repository was 2025-11-08 | Medium | 1 to 2 h |
| 3 | Uvicorn: document the post-timeout order, if maintainers decide the overlap is intended (fallback of 1) | Low | Same as 1 | Depends on the maintainers' answer | Documentation only | Depends on 1 | Low | 0.5 to 1 h |

## 1. Uvicorn: graceful-timeout lifecycle order (F1)

| Item | Detail |
| --- | --- |
| Repository | `Kludex/uvicorn` (formerly `encode/uvicorn`) |
| Source location | `uvicorn/server.py`, `Server.shutdown()`, lines 295 to 308 at `e4981ad` (the `except TimeoutError` block and the `lifespan.shutdown()` call after it) |
| Existing issue or PR | **Discussion #2422** (2024-08-12) pointed out from source that the cancelled tasks are not awaited. No replies; closed as "outdated" 2025-03-16. **PR #2882** (maintainer, closed unmerged 2026-04-06) aborted connections after the timeout, before lifespan shutdown, without awaiting tasks. **PR #3217** (open) changes the start of `shutdown()` for latency, a possible textual conflict. No issue |
| Maintainer activity | Commits on the day of this investigation; many shutdown-related changes in 2026 (#2812, #2829, #3053, #3084) |
| Contribution policy | `docs/contributing.md`: "Contributions should generally start out from a previous discussion", with possible bugs raised as a "Potential Issue" discussion. The issue template requires a linked discussion. The PR template: "I understand that this PR may be closed in case there was no previous discussion" |
| AI policy | `AI_POLICY.md` (2026-08-30): AI tools are allowed; the contributor is responsible for every contribution; search open and closed PRs, issues and discussions first; contributors who submit duplicate pull requests will be banned |
| Appropriate first step | A "Potential Issue" discussion with the minimal reproduction, asking which post-timeout behavior the maintainers want. Draft: [upstream-drafts/uvicorn-discussion-draft.md](upstream-drafts/uvicorn-discussion-draft.md) |

### Candidate corrections, as measured

| Option | Order restored | Shutdown stays bounded | Force quit (second Ctrl+C) | Existing suite | Notes |
| --- | --- | --- | --- | --- | --- |
| a. Unbounded `await asyncio.wait(tasks)` ([diff](reproductions/uvicorn-await-cancelled-tasks.diff), 3 lines) | Yes (45 of 45) | **No**: SIGTERM shutdown hangs on a request that suppresses its cancellation; 5 s cleanup extends shutdown to 7.2 s | **Broken** while it waits | Passes | Not recommended |
| b. Wait for at most another `timeout_graceful_shutdown`, stop on force exit ([diff](reproductions/uvicorn-await-cancelled-tasks-bounded.diff), 14 lines) | Yes, for cleanup that fits the bound (15 of 15) | Yes: at most one extra timeout period (4.2 s with a 2 s timeout) | Honored (2.3 s) | Passes | Recommended starting point. Cleanup longer than the bound is still lost, as today but later |
| c. Abort connections first (as in #2882), plus b | Meets ASGI's connection wording explicitly | As b | As b | Not tested | Worth raising, because #2882 shows the maintainer considered it |
| d. Documentation only | No | Unchanged | Unchanged | n/a | If the maintainers decide the overlap is intended |

Open design questions for the maintainers:

- the size of the bound: reuse `timeout_graceful_shutdown`, add a setting, or use a constant;
- whether to abort connections first;
- what to log for tasks that outlive the bound.

None of these options gives a hard deadline under SIGINT for a task that suppresses cancellation. `asyncio.run`'s teardown waits for every task, as it does today.

### Required regression tests

1. [uvicorn_regression_test.py](reproductions/uvicorn_regression_test.py): event-driven. It fails on `main` and passes with options a and b.
2. For option b, a second test: a cancelled request that suppresses cancellation must not delay shutdown past the bound. This would be written in the same in-process style; it is not drafted here.

### Compatibility risks (option b)

- Shutdown can take up to one more timeout period when cancelled tasks are slow to unwind.
- One new error log line when tasks outlive the bound.
- No change for the default configuration (no timeout set), where Uvicorn already waits for all tasks.
- Under SIGINT with a task that suppresses cancellation, the behavior is unchanged: it hangs, as today.

### Remaining effort

- **Discussion post:** human review and rewording of the draft, about 0.5 to 1 h. Re-check the upstream state just before posting.
- **If a PR is invited:**
  - patch in the chosen form, regression tests and a documentation touch (`docs/settings.md`, possibly `docs/server-behavior.md`): 2 to 3 h, including running the suite and lint locally;
  - review iterations: 1 to 2 h.
- **Linux validation:** done, in a Debian 13 container, with the same results (findings.md).

## 2. Hypercorn: validate PR #388 (F3)

- **Repository:** `pgjones/hypercorn`. The last push was 2025-11-08. Issue #308 is open. Later comments ask about progress (2025-12-27) and add a WebSocket case (2026-03-14). Fix PR #388, "Bound shutdown by graceful_timeout on Python 3.12+", is open.
- **Opportunity:** run this investigation's harness against PR #388's head, with Hypercorn and the same 8 s of work and a 2 s timeout. If the timeout then holds, post a short validation comment on the PR in the usual format (what was validated, before and after builds, limits).
- **Not done here:** PR #388 was neither reviewed nor tested.
- **Effort:** 1 to 2 h. The impact reaches every Hypercorn user on Python 3.12 or later, but whether a comment would speed up the merge is uncertain.

## 3. Uvicorn documentation (fallback of 1)

If the maintainers answer that, after the deadline, terminated requests may overlap lifespan shutdown and be cut off by the process exit, `docs/settings.md` and `docs/concepts/lifespan.md` should say so. Today the lifespan diagram shows pending requests completing before `lifespan.shutdown`. Effort: 0.5 to 1 h.

## Not opportunities

- **F2:** already fixed (#2812, 0.41.0).
- **The SIGINT hang with a request that suppresses cancellation:** caused by the application's misbehavior together with documented `asyncio.run` teardown semantics.
- **Lifespan shutdown having no deadline:** already reported (discussion #2716).
- **Force quit not cancelling ongoing tasks:** discussion #2525; the maintainer called it expected.
- **A connection in h11 `ERROR` state aborting shutdown:** discussion #3108; PR #3215 closed.
