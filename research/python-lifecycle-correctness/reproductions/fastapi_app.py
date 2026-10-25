"""FastAPI application using the documented lifespan and BackgroundTasks APIs.

``POST /jobs`` answers 202 at once and runs one unit of work (see
backend_link.py) as a background task after the response is sent.
"""

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI

from backend_link import LifespanResource, unit_of_work


@asynccontextmanager
async def lifespan(app: FastAPI):
    resource = LifespanResource()
    await resource.start()
    yield
    await resource.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/jobs", status_code=202)
async def submit(background_tasks: BackgroundTasks) -> dict[str, bool]:
    background_tasks.add_task(unit_of_work, "job")
    return {"accepted": True}
