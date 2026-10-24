"""Plain ASGI application: no framework between the server and the code under test.

``GET /`` runs one unit of work (see backend_link.py) and answers when it is done.
"""

from backend_link import LifespanResource, unit_of_work


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        resource = LifespanResource()
        await receive()  # lifespan.startup
        await resource.start()
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
        await resource.stop()
        await send({"type": "lifespan.shutdown.complete"})
        return

    async def respond() -> None:
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"done"})

    await unit_of_work("request", on_done=respond)
