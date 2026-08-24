from __future__ import annotations

from pathlib import Path

import pytest

from app.config import UserRecord
from app.nfs import NfsError, ensure_user_nfs, is_nfs_mount


def _user(tmp_path: Path) -> UserRecord:
    return UserRecord(
        password_hash="x",
        nfs_host="10.250.30.115",
        nfs_export_path="/mnt/dockerContainer/nfs/alice",
        local_mount_path=str(tmp_path / "alice"),
    )


def test_is_nfs_mount_false_for_plain_directory(tmp_path: Path) -> None:
    (tmp_path / "alice").mkdir()
    assert is_nfs_mount(str(tmp_path / "alice")) is False


def test_ensure_user_nfs_raises_when_unmounted(tmp_path: Path) -> None:
    user = _user(tmp_path)
    with pytest.raises(NfsError, match="NFS not mounted"):
        ensure_user_nfs(user, auto_mount=False)
