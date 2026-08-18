"""Docker SDK: create/start/stop/rm and inspect."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class DockerError(Exception):
    pass


@dataclass
class ContainerInfo:
    id: str
    name: str
    status: str
    running: bool


def _not_found(exc: BaseException) -> bool:
    try:
        import docker.errors

        return isinstance(exc, docker.errors.NotFound)
    except Exception:
        return type(exc).__name__ == "NotFound"


class DockerMgr:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import docker

            self._client = docker.from_env()
        return self._client

    def inspect(self, name_or_id: str) -> ContainerInfo | None:
        try:
            c = self.client.containers.get(name_or_id)
        except Exception as exc:
            if _not_found(exc):
                return None
            raise DockerError(f"inspect failed: {exc}") from exc
        state = (c.attrs.get("State") or {}).get("Status") or c.status
        running = bool((c.attrs.get("State") or {}).get("Running")) or c.status == "running"
        return ContainerInfo(id=c.id, name=c.name, status=str(state), running=running)

    def remove_force(self, name_or_id: str) -> None:
        try:
            c = self.client.containers.get(name_or_id)
        except Exception as exc:
            if _not_found(exc):
                return
            logger.warning("docker get %s: %s", name_or_id, exc)
            return
        try:
            c.remove(force=True)
        except Exception as exc:
            logger.warning("docker rm -f %s: %s", name_or_id, exc)

    def stop_and_remove(self, name_or_id: str, timeout: int = 10) -> None:
        try:
            c = self.client.containers.get(name_or_id)
        except Exception as exc:
            if _not_found(exc):
                return
            raise DockerError(f"inspect failed: {exc}") from exc
        try:
            c.stop(timeout=timeout)
        except Exception as exc:
            logger.warning("docker stop %s: %s", name_or_id, exc)
        try:
            c.remove(force=True)
        except Exception as exc:
            raise DockerError(f"docker rm failed: {exc}") from exc

    def run(
        self,
        *,
        image: str,
        name: str,
        workspace_host: str,
        workspace_container: str,
        bind_ip: str,
        host_port: int,
        obs_host_port: int,
        obs_container_port: int,
        gpu_count: int,
        cpu: str | None,
        memory: str | None,
        obs_relay_http_url: str,
        obs_relay_timeout_sec: float,
    ) -> str:
        kwargs: dict[str, Any] = {
            "image": image,
            "name": name,
            "detach": True,
            "restart_policy": {"Name": "no"},
            "volumes": {workspace_host: {"bind": workspace_container, "mode": "rw"}},
            "ports": {
                "8080/tcp": (bind_ip, host_port),
                f"{obs_container_port}/tcp": (bind_ip, obs_host_port),
            },
            "environment": {
                "OBS_ENABLE": "1",
                "OBS_PUB_PORT": str(obs_container_port),
                "OBS_RELAY_HTTP": obs_relay_http_url,
                "RSL_RL_ISRC_OBS_RELAY_URL": obs_relay_http_url,
                "RSL_RL_ISRC_OBS_RELAY_TIMEOUT": str(obs_relay_timeout_sec),
            },
        }
        if cpu:
            kwargs["nano_cpus"] = int(float(cpu) * 1_000_000_000)
        if memory:
            kwargs["mem_limit"] = memory
        if gpu_count > 0:
            import docker.types

            kwargs["device_requests"] = [
                docker.types.DeviceRequest(count=gpu_count, capabilities=[["gpu"]])
            ]
        try:
            container = self.client.containers.run(**kwargs)
        except Exception as exc:
            raise DockerError(f"docker run failed: {exc}") from exc
        return str(container.id)
