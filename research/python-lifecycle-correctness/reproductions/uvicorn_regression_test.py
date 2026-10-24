"""Draft regression test, written in the style of Uvicorn's tests/test_server.py.

Copy into Uvicorn's tests/ directory and run with pytest. It fails on main at
e4981ad and passes with either uvicorn-await-cancelled-tasks.diff or
uvicorn-await-cancelled-tasks-bounded.diff applied.

The request's cleanup blocks on an event the test controls, so whether lifespan
shutdown starts while that cleanup is still in progress does not depend on how
long the cleanup takes. The test gives the server 0.5 s to (wrongly) start the
lifespan shutdown, then lets the cleanup finish. That window can only miss a
server that starts lifespan shutdown later than 0.5 s after the cancellation;
it cannot make a correct server fail.
"""

from __future__ import annotations

import asyncio
import contextlib

import httpx2
import pytest

from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.config import Config
from uvicorn.server import Server

pytestmark = pytest.mark.anyio


async def test_lifespan_shutdown_waits_for_tasks_cancelled_by_graceful_timeout(unused_tcp_port: int):
    """A request cancelled by the graceful-shutdown timeout finishes unwinding before lifespan.shutdown."""
    events: list[str] = []
    request_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleanup_may_finish = asyncio.Event()
    lifespan_shutdown_started = asyncio.Event()

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope["type"] == "lifespan":
            await receive()
            await send({"type": "lifespan.startup.complete"})
            await receive()
            events.append("lifespan.shutdown")
            lifespan_shutdown_started.set()
            await send({"type": "lifespan.shutdown.complete"})
            return
        try:
            request_started.set()
            await asyncio.Event().wait()  # outlives the graceful-shutdown timeout
        finally:
            events.append("request cleanup started")
            cleanup_started.set()
            await cleanup_may_finish.wait()
            events.append("request cleanup finished")

    config = Config(app=app, lifespan="on", port=unused_tcp_port, timeout_graceful_shutdown=1)
    server = Server(config=config)
    serve = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(10), httpx2.AsyncClient() as client:
            while not server.started:
                await asyncio.sleep(0.05)
            request = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))
            await request_started.wait()
            server.should_exit = True

            await cleanup_started.wait()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(lifespan_shutdown_started.wait(), 0.5)
            cleanup_may_finish.set()

            await serve
            with contextlib.suppress(httpx2.HTTPError):
                await request
    finally:
        cleanup_may_finish.set()
        serve.cancel()

    assert events == ["request cleanup started", "request cleanup finished", "lifespan.shutdown"]
