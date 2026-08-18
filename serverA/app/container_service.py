"""Container start/current/stop orchestration (plan 4.3)."""

from __future__ import annotations

import logging
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings, UserRecord
from app.docker_mgr import DockerError, DockerMgr
from app.models import ContainerRecord
from app.nfs import NfsError, remount_if_missing
from app.ports import PortPoolExhausted
from app.registry import Registry
from app.schemas import ContainerResponse, ContainerStartRequest

logger = logging.getLogger(__name__)


class ContainerConflict(Exception):
    pass


class HealthCheckFailed(Exception):
    pass


class ContainerNotFound(Exception):
    pass


def container_name_for(username: str) -> str:
    return f"runner-{username}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wait_healthy(url: str, interval_sec: float, timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=min(interval_sec, 2.0))
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(interval_sec)
    return False


def tcp_connectable(host: str, port: int, timeout_sec: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


class ContainerService:
    def __init__(
        self,
        settings: Settings,
        registry: Registry,
        ports: PortPool,
        obs_ports: PortPool,
        docker: DockerMgr,
        health_fn=wait_healthy,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.ports = ports
        self.obs_ports = obs_ports
        self.docker = docker
        self.health_fn = health_fn
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _user_lock(self, username: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(username)
            if lock is None:
                lock = threading.Lock()
                self._locks[username] = lock
            return lock

    def _ensure_workspace(self, user: UserRecord) -> None:
        Path(user.local_mount_path).mkdir(parents=True, exist_ok=True)
        if self.settings.server.nfs.enabled:
            remount_if_missing(user)

    def _endpoint(self, host_port: int) -> str:
        return f"{self.settings.server.internal_ip}:{host_port}"

    def _obs_endpoint(self, obs_host_port: int | None) -> str | None:
        if obs_host_port is None:
            return None
        return self._endpoint(obs_host_port)

    def _to_response(self, rec: ContainerRecord) -> ContainerResponse:
        return ContainerResponse(
            server_b_endpoint=self._endpoint(rec.host_port),
            obs_pub_endpoint=self._obs_endpoint(rec.obs_host_port),
            container_status=rec.status,
            container_name=rec.container_name,
            nfs_mount_path=self.settings.server.container_workspace,
        )

    def start(self, username: str, req: ContainerStartRequest) -> ContainerResponse:
        user = self.settings.users[username]
        with self._user_lock(username):
            try:
                self._ensure_workspace(user)
            except NfsError as exc:
                raise
            existing = self.registry.get(username)
            name = container_name_for(username)
            if existing:
                info = self.docker.inspect(existing.container_id) or self.docker.inspect(name)
                if info and info.running:
                    existing.status = "running"
                    self.registry.upsert(existing)
                    return self._to_response(existing)
                # leftover / stopped / missing → rm -f and recreate
                self.docker.remove_force(existing.container_id)
                self.docker.remove_force(name)
                self.ports.release(existing.host_port)
                if existing.obs_host_port is not None:
                    self.obs_ports.release(existing.obs_host_port)
                self.registry.delete(username)

            try:
                host_port = self.ports.allocate()
                obs_host_port = self.obs_ports.allocate()
            except PortPoolExhausted:
                if "host_port" in locals():
                    self.ports.release(host_port)
                raise

            rec = ContainerRecord(
                username=username,
                container_id="",
                container_name=name,
                host_port=host_port,
                obs_host_port=obs_host_port,
                image=req.image,
                gpu_count=req.gpu_count,
                cpu=req.cpu,
                memory=req.memory,
                status="running",
                created_at=_now(),
                updated_at=_now(),
            )
            try:
                container_id = self.docker.run(
                    image=req.image,
                    name=name,
                    workspace_host=user.local_mount_path,
                    workspace_container=self.settings.server.container_workspace,
                    bind_ip=self.settings.server.internal_ip,
                    host_port=host_port,
                    obs_host_port=obs_host_port,
                    obs_container_port=self.settings.server.obs_container_port,
                    gpu_count=req.gpu_count,
                    cpu=req.cpu,
                    memory=req.memory,
                    obs_relay_http_url=self.settings.server.obs_relay_http_url,
                    obs_relay_timeout_sec=self.settings.server.obs_relay_timeout_sec,
                )
                rec.container_id = container_id
                self.registry.upsert(rec)
            except DockerError:
                self.docker.remove_force(name)
                self.ports.release(host_port)
                self.obs_ports.release(obs_host_port)
                raise

            health = self.settings.server.health
            url = f"http://{self._endpoint(host_port)}/health"
            if not self.health_fn(url, health.interval_sec, health.timeout_sec):
                self.docker.remove_force(container_id)
                self.docker.remove_force(name)
                self.ports.release(host_port)
                self.obs_ports.release(obs_host_port)
                self.registry.delete(username)
                raise HealthCheckFailed(f"health check failed: {url}")

            rec.status = "running"
            self.registry.upsert(rec)
            return self._to_response(rec)

    def current(self, username: str) -> ContainerResponse:
        rec = self.registry.get(username)
        if rec is None:
            raise ContainerNotFound()
        info = self.docker.inspect(rec.container_id) or self.docker.inspect(rec.container_name)
        if info is None or not info.running:
            rec.status = "failed" if info is None else "stopped"
            self.registry.upsert(rec)
            raise ContainerNotFound()
        rec.status = "running"
        self.registry.upsert(rec)
        return self._to_response(rec)

    def stop(self, username: str) -> None:
        rec = self.registry.get(username)
        name = container_name_for(username)
        if rec is None and self.docker.inspect(name) is None:
            raise ContainerNotFound()
        target = rec.container_id if rec else name
        self.docker.stop_and_remove(target)
        self.docker.remove_force(name)
        if rec:
            self.ports.release(rec.host_port)
            if rec.obs_host_port is not None:
                self.obs_ports.release(rec.obs_host_port)
            self.registry.delete(username)

    def running_endpoints(self, username: str) -> tuple[str | None, str | None]:
        rec = self.registry.get(username)
        if rec is None or rec.status != "running":
            return None, None
        info = self.docker.inspect(rec.container_id) or self.docker.inspect(rec.container_name)
        if info and info.running:
            return self._endpoint(rec.host_port), self._obs_endpoint(rec.obs_host_port)
        return None, None
