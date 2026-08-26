from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.docker_mgr import ContainerInfo

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("SERVER_A_CONFIG_DIR", str(ROOT / "config"))
    monkeypatch.setenv("SERVER_A_JWT_SECRET", "test-secret-must-be-32-bytes-ok!")
    monkeypatch.setenv("SERVER_A_DOCKER_ENABLED", "false")
    monkeypatch.setenv("SERVER_A_NFS_ENABLED", "false")
    monkeypatch.setenv("SERVER_A_LOG_ENABLED", "false")
    monkeypatch.setenv("SERVER_A_DB_PATH", str(tmp_path / "registry.db"))
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def docker_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("SERVER_A_CONFIG_DIR", str(ROOT / "config"))
    monkeypatch.setenv("SERVER_A_JWT_SECRET", "test-secret-must-be-32-bytes-ok!")
    monkeypatch.setenv("SERVER_A_DOCKER_ENABLED", "true")
    monkeypatch.setenv("SERVER_A_NFS_ENABLED", "false")
    monkeypatch.setenv("SERVER_A_LOG_ENABLED", "false")
    monkeypatch.setenv("SERVER_A_DB_PATH", str(tmp_path / "registry.db"))
    from app.main import app

    with TestClient(app) as test_client:
        ws = tmp_path / "alice-ws"
        ws.mkdir()
        test_client.app.state.settings.users["alice"].local_mount_path = str(ws)
        for group_id, group in test_client.app.state.settings.groups.items():
            gdir = tmp_path / "groups" / group_id
            gdir.mkdir(parents=True, exist_ok=True)
            group.local_mount_path = str(gdir)
        docker = test_client.app.state.docker
        docker._client = MagicMock()
        docker.inspect = MagicMock(return_value=None)
        docker.remove_force = MagicMock()
        docker.stop_and_remove = MagicMock()
        docker.run = MagicMock(return_value="cid-1")
        svc = test_client.app.state.containers
        svc.health_fn = MagicMock(return_value=True)
        monkeypatch.setattr("app.nfs.is_nfs_mount", lambda path: True)
        yield test_client


def _token(client: TestClient) -> str:
    return client.post("/login", json={"username": "alice", "password": "alice-dev"}).json()["token"]


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client)}"}
