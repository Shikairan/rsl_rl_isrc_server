from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.access_middleware import AccessLogMiddleware
from app.config import load_settings
from app.logging_setup import setup_logging
from app.routers.tasks import router as tasks_router
from app.task_manager import TaskManager

logger = logging.getLogger("server_b")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    setup_logging(settings)
    app.state.settings = settings
    app.state.tasks = TaskManager(settings)
    logger.info(
        "server B ready workspace=%s launcher=%s log_dir=%s",
        settings.workspace_root,
        settings.launcher,
        settings.log_dir if settings.log_enabled else "(disabled)",
    )
    yield
    app.state.tasks.shutdown()


app = FastAPI(title="Server B", version="0.1.0", lifespan=lifespan)
app.add_middleware(AccessLogMiddleware)
app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
