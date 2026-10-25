"""What the test applications use to talk to the harness.

The harness plays a backend service (think database or lock service) in a
separate process. The applications open TCP connections to it, the way real
code holds connections to such a service, and the backend logs every line it
receives. That log is the independent record of what the application
actually completed.

``witness()`` is the application's own view: unbuffered appends to a file, so
the record survives the process being killed by a signal.

Environment: ``BACKEND`` (host:port), ``WITNESS`` (path), and optional modes:

* ``SHIELD=1``: wrap the release in ``asyncio.shield()``, the protection an application can add itself;
* ``SHARED=1``: release through a lifespan-owned connection (a "pool") that lifespan shutdown closes first;
* ``STUBBORN=1``: suppress the cancellation and keep working, the misbehaving pattern a bounded
  shutdown has to survive.
"""

import asyncio
import os
import time

BACKEND_HOST, BACKEND_PORT = os.environ["BACKEND"].rsplit(":", 1)
WITNESS = os.environ["WITNESS"]
SHIELD = os.environ.get("SHIELD") == "1"
SHARED = os.environ.get("SHARED") == "1"
STUBBORN = os.environ.get("STUBBORN") == "1"

CURRENT_RESOURCE: "LifespanResource | None" = None


def witness(event: str) -> None:
    fd = os.open(WITNESS, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, f"{time.time():.6f} {os.getpid()} {event}\n".encode())
    finally:
        os.close(fd)


class Link:
    """One TCP connection to the backend. ``call`` waits for the backend's OK."""

    def __init__(self, name: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.name = name
        self.reader = reader
        self.writer = writer

    @classmethod
    async def open(cls, name: str) -> "Link":
        reader, writer = await asyncio.open_connection(BACKEND_HOST, int(BACKEND_PORT))
        return cls(name, reader, writer)

    async def call(self, tag: str, who: str | None = None) -> None:
        self.writer.write(f"CALL {tag} {who or self.name}\n".encode())
        await self.writer.drain()
        # Replies carry their call's tag. A reply to an earlier, abandoned call is skipped.
        while True:
            line = await self.reader.readline()
            if not line:
                raise ConnectionError("backend closed the connection")
            if line.decode().strip() == f"OK {tag}":
                return
            witness(f"{who or self.name}.skipped-reply {line.decode().strip()}")

    def note(self, tag: str, who: str | None = None) -> None:
        self.writer.write(f"NOTE {tag} {who or self.name}\n".encode())

    def close(self) -> None:
        self.writer.close()


async def unit_of_work(name: str, on_done=None) -> None:
    """Hold a backend connection, do work, and release it in ``finally``.

    The release is one awaited round trip, as returning a connection, rolling
    back, or dropping a lock would be. ``NOTE released`` is sent only after the
    backend acknowledged the release, so its arrival at the backend proves the
    cleanup finished.
    """
    link = await Link.open(name)
    witness(f"{name}.begin")
    try:
        while True:
            try:
                await link.call("work")
                break
            except asyncio.CancelledError:
                if not STUBBORN:
                    raise
                witness(f"{name}.cancellation.suppressed")
        witness(f"{name}.worked")
        if on_done is not None:
            await on_done()
    except asyncio.CancelledError:
        witness(f"{name}.cancelled")
        raise
    finally:
        witness(f"{name}.cleanup.begin")
        release_link = CURRENT_RESOURCE.pool if SHARED and CURRENT_RESOURCE is not None else link
        try:
            if SHIELD:
                await asyncio.shield(release_link.call("release", who=name))
            else:
                await release_link.call("release", who=name)
            release_link.note("released", who=name)
            witness(f"{name}.cleanup.done")
        except BaseException as exc:
            witness(f"{name}.cleanup.interrupted {type(exc).__name__}")
            raise
        finally:
            link.close()


class LifespanResource:
    """Lifespan-owned connections: opened at startup, closed at shutdown.

    ``pool`` stands for a shared resource such as a connection pool or an HTTP
    client. Lifespan shutdown closes it first, as applications usually do.
    """

    async def start(self) -> None:
        global CURRENT_RESOURCE
        witness("lifespan.startup.begin")
        self.link = await Link.open("lifespan")
        self.pool = await Link.open("pool")
        CURRENT_RESOURCE = self
        await self.link.call("startup")
        witness("lifespan.startup.done")

    async def stop(self) -> None:
        witness("lifespan.shutdown.begin")
        self.pool.close()
        witness("lifespan.pool.closed")
        await self.link.call("shutdown")
        self.link.close()
        witness("lifespan.shutdown.done")
