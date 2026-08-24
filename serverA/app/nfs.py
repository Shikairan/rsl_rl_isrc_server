"""NFS mount helpers.

auto-mount (mount(8)) only runs when nfs.enabled is true. Starting a container
always requires the user's local_mount_path to already be an NFS mount.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from app.config import Settings, UserRecord

logger = logging.getLogger(__name__)

_NFS_FSTYPES = {"nfs", "nfs4"}


class NfsError(Exception):
    pass


def is_mount_point(path: str) -> bool:
    return os.path.ismount(path)


def _unescape_mountinfo_path(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 3 < len(raw) and raw[i + 1 : i + 4].isdigit():
            out.append(chr(int(raw[i + 1 : i + 4], 8)))
            i += 4
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


def _exact_fstype(path: str) -> str | None:
    target = os.path.realpath(path)
    try:
        with open("/proc/self/mountinfo", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for line in lines:
        if " - " not in line:
            continue
        left, right = line.rstrip("\n").split(" - ", 1)
        fields = left.split(" ")
        if len(fields) < 5:
            continue
        mountpoint = os.path.realpath(_unescape_mountinfo_path(fields[4]))
        if mountpoint != target:
            continue
        fstype = right.split(" ")[0]
        return fstype or None
    return None


def is_nfs_mount(path: str) -> bool:
    if not path or not os.path.ismount(path):
        return False
    fstype = _exact_fstype(path)
    return fstype in _NFS_FSTYPES


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


def ensure_user_nfs(user: UserRecord, *, auto_mount: bool) -> None:
    Path(user.local_mount_path).mkdir(parents=True, exist_ok=True)
    if auto_mount:
        remount_if_missing(user)
    if is_nfs_mount(user.local_mount_path):
        return
    expected = f"{user.nfs_host}:{user.nfs_export_path}"
    logger.warning(
        "NFS not mounted path=%s expected=%s; refusing container start",
        user.local_mount_path,
        expected,
    )
    raise NfsError(
        f"NFS not mounted at {user.local_mount_path}; "
        f"refusing to start container (expected {expected})"
    )


def mount_all_users(settings: Settings) -> None:
    if not settings.server.nfs.enabled:
        logger.info("nfs.enabled=false, skip auto-mount")
        return
    failures: list[str] = []
    for name, user in settings.users.items():
        try:
            mount_user(user)
        except NfsError as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        raise NfsError("NFS mount failed:\n" + "\n".join(failures))
