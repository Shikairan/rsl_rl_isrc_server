from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("SERVER_A_CONFIG_DIR", ROOT / "config"))


class HealthSettings(BaseModel):
    interval_sec: int = 2
    timeout_sec: int = 60


class FeatureFlag(BaseModel):
    enabled: bool = False


class LoggingSettings(BaseModel):
    enabled: bool = True
    dir: str = "./logs"
    level: str = "INFO"
    console: bool = True
    access_log: bool = True
    max_bytes: int = 10_485_760
    backup_count: int = 5


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    internal_ip: str = "10.213.35.42"
    jwt_secret: str = "CHANGE_ME"
    jwt_ttl_hours: int = 24
    port_range: list[int] = Field(default_factory=lambda: [31000, 31999])
    obs_port_range: list[int] = Field(default_factory=lambda: [32000, 32999])
    tensorboard_port_range: list[int] = Field(default_factory=lambda: [33000, 33999])
    nfs_mount_root: str = "/mnt/nfs"
    container_workspace: str = "/workspace"
    health: HealthSettings = Field(default_factory=HealthSettings)
    db_path: str = "./data/registry.db"
    reconcile_interval_sec: int = 30
    nfs: FeatureFlag = Field(default_factory=FeatureFlag)
    docker: FeatureFlag = Field(default_factory=FeatureFlag)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # obs 转发端口与训练侧中继 URL（注入到容器环境变量）
    obs_container_port: int = 15557
    obs_relay_http_url: str = "http://127.0.0.1:15558/post"
    obs_relay_timeout_sec: float = 0.05
    tensorboard_container_port: int = 6006


class UserRecord(BaseModel):
    password_hash: str
    nfs_host: str
    nfs_export_path: str
    local_mount_path: str


class Settings:
    def __init__(self, server: ServerSettings, users: dict[str, UserRecord]) -> None:
        self.server = server
        self.users = users

    @property
    def jwt_secret(self) -> str:
        return os.environ.get("SERVER_A_JWT_SECRET", self.server.jwt_secret)

    @property
    def db_path(self) -> Path:
        raw = os.environ.get("SERVER_A_DB_PATH", self.server.db_path)
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        return path

    @property
    def log_dir(self) -> Path:
        raw = os.environ.get("SERVER_A_LOG_DIR", self.server.logging.dir)
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        return path


def _env_flag(name: str, current: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return current
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid yaml (expected mapping): {path}")
    return data


def load_settings(
    server_path: Path | None = None,
    users_path: Path | None = None,
) -> Settings:
    server_path = server_path or CONFIG_DIR / "server.yaml"
    users_path = users_path or CONFIG_DIR / "users.yaml"
    server_raw = _load_yaml(server_path).get("server") or {}
    users_raw = _load_yaml(users_path).get("users") or {}
    server = ServerSettings.model_validate(server_raw)
    server.nfs.enabled = _env_flag("SERVER_A_NFS_ENABLED", server.nfs.enabled)
    server.docker.enabled = _env_flag("SERVER_A_DOCKER_ENABLED", server.docker.enabled)
    server.logging.enabled = _env_flag("SERVER_A_LOG_ENABLED", server.logging.enabled)
    level_override = os.environ.get("SERVER_A_LOG_LEVEL")
    if level_override and level_override.strip():
        server.logging.level = level_override.strip().upper()
    users = {
        name: UserRecord.model_validate(body)
        for name, body in users_raw.items()
    }
    return Settings(server=server, users=users)
