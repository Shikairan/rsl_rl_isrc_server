from __future__ import annotations


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_success(client) -> None:
    resp = client.post("/login", json={"username": "alice", "password": "alice-dev"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["nfs_host"] == "10.250.30.115"
    assert body["nfs_export_path"] == "/mnt/dockerContainer/nfs/alice"
    assert body["token"]
    assert body["obs_pub_endpoint"] is None


def test_login_wrong_password(client) -> None:
    resp = client.post("/login", json={"username": "alice", "password": "nope"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "invalid credentials"


def test_login_unknown_user(client) -> None:
    resp = client.post("/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_containers_disabled_without_token(client) -> None:
    resp = client.post(
        "/containers/start",
        json={"image": "example:latest", "gpu_count": 0},
    )
    assert resp.status_code == 401


def test_containers_disabled_with_token(client) -> None:
    token = client.post("/login", json={"username": "alice", "password": "alice-dev"}).json()["token"]
    resp = client.post(
        "/containers/start",
        json={"image": "example:latest", "gpu_count": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
