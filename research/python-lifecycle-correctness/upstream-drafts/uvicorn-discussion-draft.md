# Draft: Uvicorn "Potential Issue" discussion

Status: draft for human review. Not posted. The exact text needs approval before anything is posted, and the upstream state (discussions, open PRs, `main`) must be re-checked first.

- Venue: https://github.com/Kludex/uvicorn/discussions, category "Potential Issue".
- Evidence behind each sentence: [../findings.md](../findings.md), F1.

---

**Title:** Lifespan shutdown starts while the requests cancelled by `--timeout-graceful-shutdown` are still running

When `--timeout-graceful-shutdown` expires, `Server.shutdown()` cancels the request tasks and then goes straight to the lifespan shutdown, without waiting for the cancelled tasks to finish:

```python
for t in self.server_state.tasks:
    t.cancel(msg="Task cancelled, timeout graceful shutdown exceeded")

# Send the lifespan shutdown event, and wait for application shutdown.
if not self.force_exit:
    await self.lifespan.shutdown()
```

So a cancelled request's `except CancelledError` / `finally` block runs at the same time as the app's lifespan shutdown, which usually closes the pools and clients that block needs. After `serve()` returns:

- on SIGTERM, the re-raised signal ends the process before that block finishes;
- on SIGINT, `asyncio.run`'s teardown cancels it a second time, and the 500 for the request is written after `Finished server process`.

The ASGI lifespan spec says `lifespan.shutdown` is sent once the server "has stopped accepting connections and closed all active connections", and the lifespan page in the docs shows pending requests completing before it.

With the app below, `uvicorn app:app --timeout-graceful-shutdown 1`, one request, then `kill -TERM <pid>`, Uvicorn 0.54.0 prints:

```
ERROR:    Cancel 1 running task(s), timeout graceful shutdown exceeded
INFO:     Waiting for application shutdown.
app: cleanup started
app: lifespan shutdown
INFO:     Application shutdown complete.
INFO:     Finished server process [...]
```

`app: cleanup finished` is never printed.

<details><summary>app.py</summary>

```python
import asyncio


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await receive()
        await send({"type": "lifespan.startup.complete"})
        await receive()
        print("app: lifespan shutdown", flush=True)
        await send({"type": "lifespan.shutdown.complete"})
        return
    try:
        print("app: request started", flush=True)
        await asyncio.Event().wait()  # outlives the graceful-shutdown timeout
    finally:
        print("app: cleanup started", flush=True)
        await asyncio.sleep(0.5)  # one more awaited step, e.g. a rollback
        print("app: cleanup finished", flush=True)
```

</details>

I saw the same order every time on 0.54.0 and on `main` (e4981ad), with CPython 3.13.11 and 3.14.2, with and without `uvicorn[standard]`, on macOS (arm64). I also checked it with a separate process standing in for a remote service: the cleanup's request reached it, but the server process ended before the answer came back. When the cleanup went through a pool that the lifespan shutdown closes, it failed with `ConnectionError`.

I tried two changes locally. Both pass the existing test suite:

1. `await asyncio.wait(self.server_state.tasks)` after the cancel loop restores the order. But a request that suppresses its cancellation then hangs SIGTERM shutdown, and a second Ctrl+C no longer forces quit while it waits.
2. Waiting for the cancelled tasks for at most another `timeout_graceful_shutdown`, and stopping on `force_exit` (polling like `_wait_tasks_to_complete`), restores the order for cleanup that fits in that window, and keeps shutdown bounded. Cleanup that takes longer is still cut off.

Is waiting for the cancelled tasks, within some bound, how you'd want the server to behave after the timeout, or is the current overlap intended? If the approach is useful, I'm happy to prepare a PR with a regression test.

Related: #2422 noted from the source that the cancelled tasks aren't awaited, and #2882 proposed aborting the connections after the timeout.
