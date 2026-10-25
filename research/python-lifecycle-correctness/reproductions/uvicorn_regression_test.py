"""Draft regression tests, written in the style of Uvicorn's tests/test_server.py.

Copy into Uvicorn's tests/ directory and run with pytest. Both fail on main at e4981ad
and pass with either uvicorn-await-cancelled-tasks.diff or
uvicorn-await-cancelled-tasks-bounded.diff applied.

They assert two different things, so that a maintainer can keep the one that matches
the chosen remedy:

* test_no_active_connections_when_lifespan_shutdown_starts: the ASGI lifespan invariant
  ("closed all active connections"). It does not care how the server gets there, so a
  remedy that aborts the connections instead of waiting would also pass it.
* test_cancelled_request_cleanup_finishes_before_lifespan_shutdown: the stronger policy
  in which the server waits for the cancelled tasks. Keep it only if that is the remedy.

The request's cleanup blocks on an event the test controls, so whether lifespan shutdown
starts while it is blocked does not depend on how long the cleanup takes. The server gets
0.5 s to (wrongly) start lifespan shutdown before the test lets the cleanup finish. That
window can only miss a server that misbehaves later than that; it cannot make a correct
server fail.
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


async def shut_down_during_blocked_cleanup(unused_tcp_port: int) -> tuple[list[str], list[int]]:
    """Run one request past the graceful-shutdown timeout and record the shutdown order.

    Returns the events in order, and the number of connections Uvicorn still had
    registered when the application received lifespan.shutdown.
    """
    events: list[str] = []
    connections_at_lifespan_shutdown: list[int] = []
    request_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleanup_may_finish = asyncio.Event()
    lifespan_shutdown_started = asyncio.Event()

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope["type"] == "lifespan":
            await receive()
            await send({"type": "lifespan.startup.complete"})
            await receive()
            connections_at_lifespan_shutdown.append(len(server.server_state.connections))
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
    return events, connections_at_lifespan_shutdown


async def test_no_active_connections_when_lifespan_shutdown_starts(unused_tcp_port: int):
    """ASGI: lifespan.shutdown is sent once the server has closed all active connections."""
    _, connections = await shut_down_during_blocked_cleanup(unused_tcp_port)
    assert connections == [0]


async def test_cancelled_request_cleanup_finishes_before_lifespan_shutdown(unused_tcp_port: int):
    """Policy: the server waits for the tasks its graceful-shutdown timeout cancelled."""
    events, _ = await shut_down_during_blocked_cleanup(unused_tcp_port)
    assert events == ["request cleanup started", "request cleanup finished", "lifespan.shutdown"]
