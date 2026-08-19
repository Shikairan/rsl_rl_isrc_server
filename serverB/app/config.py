from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    launcher: str
    stop_grace_sec: float
    host: str
    port: int
    log_enabled: bool
    log_dir: Path
    log_level: str
    log_console: bool
    log_access: bool
    log_max_bytes: int
    log_backup_count: int


def load_settings() -> Settings:
    workspace_root = Path(os.environ.get("SERVER_B_WORKSPACE_ROOT", "/workspace"))
    log_dir_raw = os.environ.get("SERVER_B_LOG_DIR", "").strip()
    log_dir = Path(log_dir_raw) if log_dir_raw else workspace_root / "logs"
    return Settings(
        workspace_root=workspace_root,
        launcher=os.environ.get("SERVER_B_LAUNCHER", "torchrun"),
        stop_grace_sec=float(os.environ.get("SERVER_B_STOP_GRACE_SEC", "5")),
        host=os.environ.get("SERVER_B_HOST", "0.0.0.0"),
        port=int(os.environ.get("SERVER_B_PORT", "8080")),
        log_enabled=_env_flag("SERVER_B_LOG_ENABLED", True),
        log_dir=log_dir,
        log_level=os.environ.get("SERVER_B_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_console=_env_flag("SERVER_B_LOG_CONSOLE", True),
        log_access=_env_flag("SERVER_B_LOG_ACCESS", True),
        log_max_bytes=int(os.environ.get("SERVER_B_LOG_MAX_BYTES", str(10_485_760))),
        log_backup_count=int(os.environ.get("SERVER_B_LOG_BACKUP_COUNT", "5")),
    )
