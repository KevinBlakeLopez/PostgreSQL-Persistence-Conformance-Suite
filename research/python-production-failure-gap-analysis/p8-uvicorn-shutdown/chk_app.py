"""ASGI app for the Uvicorn shutdown check: one SQLAlchemy AsyncSession transaction per request.

Uvicorn serves this module. The request inserts a row whose deferred constraint trigger
waits at COMMIT on an advisory lock that the runner holds (the P3 commit gate). The lifespan
shutdown disposes the engine, as an ordinary application does. Every SQLAlchemy ORM, Core
and pool event, and every step of the request and lifespan, is written with os.write to an
append-only file descriptor, so a line exists only if the process reached it before exiting.
"""
import json
import os
import time

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session

DSN = os.environ["CHK_DSN"]
DRIVER = os.environ["CHK_DRIVER"]
MARKER = os.environ["CHK_MARKER"]
APPNAME = os.environ["CHK_APPNAME"]
_fd = os.open(os.environ["CHK_EVENT_LOG"], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)


def ev(name, **kw):
    os.write(_fd, (json.dumps({"t": time.time(), "ev": name, **kw}) + "\n").encode())


engine = None


def _install_listeners(eng):
    for n in ("after_begin", "after_commit", "after_rollback", "after_soft_rollback"):
        event.listen(Session, n, (lambda n: lambda *a, **k: ev(f"orm.{n}"))(n))
    for n in ("commit", "rollback"):
        event.listen(eng.sync_engine, n, (lambda n: lambda *a, **k: ev(f"core.{n}"))(n))
    for n in ("checkout", "checkin", "reset", "invalidate", "soft_invalidate", "close", "detach", "close_detached"):
        event.listen(eng.sync_engine.pool, n, (lambda n: lambda *a, **k: ev(f"pool.{n}"))(n))


def _connect_args():
    if DRIVER == "asyncpg":
        return {"server_settings": {"application_name": APPNAME}}
    return {"application_name": APPNAME}


async def _lifespan(receive, send):
    global engine
    while True:
        msg = await receive()
        if msg["type"] == "lifespan.startup":
            engine = create_async_engine(DSN, pool_size=1, max_overflow=0, connect_args=_connect_args())
            _install_listeners(engine)
            ev("lifespan.startup")
            await send({"type": "lifespan.startup.complete"})
        elif msg["type"] == "lifespan.shutdown":
            ev("lifespan.shutdown.start")
            try:
                await engine.dispose()
                ev("lifespan.dispose.returned")
            except BaseException as e:  # noqa: record, then let it propagate
                ev("lifespan.dispose.raised", err=f"{type(e).__name__}: {e}"[:200])
                raise
            await send({"type": "lifespan.shutdown.complete"})
            ev("lifespan.shutdown.complete")
            return


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await _lifespan(receive, send)
        return
    ev("request.start", path=scope["path"])
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                await s.execute(text("insert into item(name) values (:n)"), {"n": MARKER})
                pid, xid = (await s.execute(text("select pg_backend_pid(), pg_current_xact_id()::text"))).one()
                ev("request.in_transaction", pid=pid, xid=xid)
                ev("request.commit_starting")
            ev("request.commit_returned")
    except BaseException as e:  # noqa: record what the application saw, then let it propagate
        ev("request.raised", err=f"{type(e).__module__}.{type(e).__name__}: {e}"[:200])
        raise
    finally:
        ev("request.finally")
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-length", b"2")]})
    await send({"type": "http.response.body", "body": b"ok"})
    ev("request.responded")
