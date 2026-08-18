from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_settings
from app.routers.tasks import router as tasks_router
from app.task_manager import TaskManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.tasks = TaskManager(settings)
    yield
    app.state.tasks.shutdown()


app = FastAPI(title="Server B", version="0.1.0", lifespan=lifespan)
app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
