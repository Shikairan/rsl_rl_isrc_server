from __future__ import annotations

from unittest.mock import MagicMock

from app.docker_mgr import ContainerInfo


def test_start_rejects_unmounted_nfs(docker_client, monkeypatch) -> None:
    monkeypatch.setattr("app.nfs.is_nfs_mount", lambda path: False)
    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert resp.status_code == 503, resp.text
    err = resp.json()["detail"]["error"].lower()
    assert "nfs not mounted" in err
    assert "refusing to start container" in err
    docker_client.app.state.docker.run.assert_not_called()


def test_start_success(docker_client) -> None:
    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0, "cpu": "2", "memory": "4g"},
        headers=_auth(docker_client),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["container_name"] == "runner-alice"
    assert body["container_status"] == "running"
    assert body["nfs_mount_path"] == "/workspace"
    assert body["group_mounts"] == [
        {"group_id": "team-alpha", "container_path": "/workspace/groups/team-alpha"}
    ]
    assert body["server_b_endpoint"].startswith("10.213.35.42:")
    assert body["obs_pub_endpoint"].startswith("10.213.35.42:32")
    assert body["tensorboard_endpoint"].startswith("10.213.35.42:33")
    docker_client.app.state.docker.run.assert_called_once()
    run_kw = docker_client.app.state.docker.run.call_args.kwargs
    assert run_kw["tb_container_port"] == 6006
    assert run_kw["tb_host_port"] == 33000


def test_start_idempotent(docker_client) -> None:
    docker_client.app.state.docker.inspect.return_value = ContainerInfo(
        id="cid-1", name="runner-alice", status="running", running=True
    )
    first = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert first.status_code == 200
    docker_client.app.state.docker.run.reset_mock()
    second = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert second.status_code == 200
    docker_client.app.state.docker.run.assert_not_called()
    assert second.json()["server_b_endpoint"] == first.json()["server_b_endpoint"]
    assert second.json()["obs_pub_endpoint"] == first.json()["obs_pub_endpoint"]
    assert second.json()["tensorboard_endpoint"] == first.json()["tensorboard_endpoint"]


def test_start_health_fail_returns_502(docker_client) -> None:
    docker_client.app.state.containers.health_fn = MagicMock(return_value=False)
    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert resp.status_code == 502
    docker_client.app.state.docker.remove_force.assert_called()
    assert docker_client.app.state.registry.get("alice") is None


def test_current_404(docker_client) -> None:
    resp = docker_client.get("/containers/current", headers=_auth(docker_client))
    assert resp.status_code == 404


def test_current_running(docker_client) -> None:
    start = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert start.status_code == 200
    docker_client.app.state.docker.inspect.return_value = ContainerInfo(
        id="cid-1", name="runner-alice", status="running", running=True
    )
    resp = docker_client.get("/containers/current", headers=_auth(docker_client))
    assert resp.status_code == 200
    assert resp.json()["container_name"] == "runner-alice"
    assert resp.json()["obs_pub_endpoint"].startswith("10.213.35.42:32")
    assert resp.json()["tensorboard_endpoint"].startswith("10.213.35.42:33")


def test_stop_404(docker_client) -> None:
    resp = docker_client.post("/containers/stop", headers=_auth(docker_client))
    assert resp.status_code == 404


def test_stop_success(docker_client) -> None:
    start = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert start.status_code == 200
    resp = docker_client.post("/containers/stop", headers=_auth(docker_client))
    assert resp.status_code == 200
    assert resp.json() == {"status": "stopped"}
    assert docker_client.app.state.registry.get("alice") is None


def test_login_returns_obs_endpoint_for_running_container(docker_client) -> None:
    start = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert start.status_code == 200
    docker_client.app.state.docker.inspect.return_value = ContainerInfo(
        id="cid-1", name="runner-alice", status="running", running=True
    )
    resp = docker_client.post("/login", json={"username": "alice", "password": "alice-dev"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_b_endpoint"] == start.json()["server_b_endpoint"]
    assert body["obs_pub_endpoint"] == start.json()["obs_pub_endpoint"]
    assert body["tensorboard_endpoint"] == start.json()["tensorboard_endpoint"]


def _auth(client) -> dict[str, str]:
    token = client.post("/login", json={"username": "alice", "password": "alice-dev"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
