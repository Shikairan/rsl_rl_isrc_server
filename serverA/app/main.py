from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_settings
from app.container_service import ContainerService
from app.docker_mgr import DockerMgr
from app.nfs import NfsError, mount_all_users
from app.ports import PortPool
from app.registry import Registry
from app.routers import auth, containers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("server_a")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    try:
        mount_all_users(settings)
    except NfsError:
        logger.exception("NFS mount failed; refusing to start")
        raise

    registry = Registry(settings.db_path)
    start, end = settings.server.port_range
    ports = PortPool(start, end, in_use=registry.allocated_ports())
    obs_start, obs_end = settings.server.obs_port_range
    obs_ports = PortPool(obs_start, obs_end, in_use=registry.allocated_obs_ports())
    docker = DockerMgr()
    app.state.registry = registry
    app.state.ports = ports
    app.state.obs_ports = obs_ports
    app.state.docker = docker
    app.state.containers = ContainerService(settings, registry, ports, obs_ports, docker)
    logger.info(
        "server A ready nfs.enabled=%s docker.enabled=%s users=%s db=%s",
        settings.server.nfs.enabled,
        settings.server.docker.enabled,
        list(settings.users),
        settings.db_path,
    )
    yield


app = FastAPI(title="Server A", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(containers.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
