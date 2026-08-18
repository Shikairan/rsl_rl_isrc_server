from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    launcher: str
    stop_grace_sec: float
    host: str
    port: int


def load_settings() -> Settings:
    return Settings(
        workspace_root=Path(os.environ.get("SERVER_B_WORKSPACE_ROOT", "/workspace")),
        launcher=os.environ.get("SERVER_B_LAUNCHER", "torchrun"),
        stop_grace_sec=float(os.environ.get("SERVER_B_STOP_GRACE_SEC", "5")),
        host=os.environ.get("SERVER_B_HOST", "0.0.0.0"),
        port=int(os.environ.get("SERVER_B_PORT", "8080")),
    )
