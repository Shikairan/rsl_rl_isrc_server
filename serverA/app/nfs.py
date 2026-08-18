"""NFS mount helpers. No-op when nfs.enabled is false (P2)."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from app.config import Settings, UserRecord

logger = logging.getLogger(__name__)


class NfsError(Exception):
    pass


def is_mount_point(path: str) -> bool:
    return os.path.ismount(path)


def mount_user(user: UserRecord) -> None:
    local = Path(user.local_mount_path)
    local.mkdir(parents=True, exist_ok=True)
    if is_mount_point(user.local_mount_path):
        logger.info("nfs already mounted: %s", user.local_mount_path)
        return
    source = f"{user.nfs_host}:{user.nfs_export_path}"
    cmd = ["mount", "-t", "nfs", "-o", "vers=4", source, user.local_mount_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise NfsError(
            f"mount failed {source} -> {user.local_mount_path}: {result.stderr.strip()}"
        )
    logger.info("nfs mounted %s -> %s", source, user.local_mount_path)


def remount_if_missing(user: UserRecord) -> None:
    if not is_mount_point(user.local_mount_path):
        mount_user(user)


def mount_all_users(settings: Settings) -> None:
    if not settings.server.nfs.enabled:
        logger.info("nfs.enabled=false, skip mounting")
        return
    failures: list[str] = []
    for name, user in settings.users.items():
        try:
            mount_user(user)
        except NfsError as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        raise NfsError("NFS mount failed:\n" + "\n".join(failures))
