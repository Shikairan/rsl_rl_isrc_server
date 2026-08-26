from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import load_settings
from app.docker_mgr import ContainerInfo


def test_login_alice_has_team_alpha(client) -> None:
    """T-G-01: alice login groups contains team-alpha."""
    resp = client.post("/login", json={"username": "alice", "password": "alice-dev"})
    assert resp.status_code == 200
    groups = resp.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["group_id"] == "team-alpha"
    assert groups[0]["nfs_export_path"] == "/mnt/dockerContainer/nfs/groups/team-alpha"
    assert groups[0]["local_mount_hint"] == "/mnt/nfs/groups/team-alpha"


def test_login_carol_team_beta_eve_empty(client) -> None:
    """T-G-02: carol has team-beta; eve has no groups."""
    carol = client.post("/login", json={"username": "carol", "password": "carol-dev"})
    assert carol.status_code == 200
    assert len(carol.json()["groups"]) == 1
    assert carol.json()["groups"][0]["group_id"] == "team-beta"

    eve = client.post("/login", json={"username": "eve", "password": "eve-dev"})
    assert eve.status_code == 200
    assert eve.json()["groups"] == []


def test_start_alice_two_volume_binds(docker_client, tmp_path: Path) -> None:
    """T-G-03: alice start binds private workspace + group team-alpha."""
    ws = docker_client.app.state.settings.users["alice"].local_mount_path
    group_ws = docker_client.app.state.settings.groups["team-alpha"].local_mount_path

    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers=_auth(docker_client),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["group_mounts"] == [
        {"group_id": "team-alpha", "container_path": "/workspace/groups/team-alpha"}
    ]
    run_kw = docker_client.app.state.docker.run.call_args.kwargs
    volumes = run_kw.get("group_volumes") or []
    assert run_kw["workspace_host"] == ws
    assert (group_ws, "/workspace/groups/team-alpha") in volumes


def test_start_carol_single_group_bind(docker_client, tmp_path: Path) -> None:
    """T-G-04 variant: carol has team-beta only."""
    ws = tmp_path / "carol-ws"
    ws.mkdir()
    docker_client.app.state.settings.users["carol"].local_mount_path = str(ws)
    group_ws = docker_client.app.state.settings.groups["team-beta"].local_mount_path
    token = docker_client.post(
        "/login", json={"username": "carol", "password": "carol-dev"}
    ).json()["token"]
    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    run_kw = docker_client.app.state.docker.run.call_args.kwargs
    assert (group_ws, "/workspace/groups/team-beta") in (run_kw.get("group_volumes") or [])


def test_start_eve_no_group_mounts(docker_client, tmp_path: Path) -> None:
    """T-G-04: user without groups has empty group_mounts and no extra volumes."""
    ws = tmp_path / "eve-ws"
    ws.mkdir()
    docker_client.app.state.settings.users["eve"].local_mount_path = str(ws)
    token = docker_client.post("/login", json={"username": "eve", "password": "eve-dev"}).json()["token"]
    resp = docker_client.post(
        "/containers/start",
        json={"image": "runner:test", "gpu_count": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["group_mounts"] == []
    run_kw = docker_client.app.state.docker.run.call_args.kwargs
    assert run_kw.get("group_volumes") in (None, [])


def test_groups_for_user_multi_group(tmp_path: Path) -> None:
    """T-G-04: user in two groups yields two volume binds."""
    groups_path = tmp_path / "groups.yaml"
    groups_path.write_text(
        """
groups:
  team-alpha:
    nfs_host: "10.250.30.115"
    nfs_export_path: "/mnt/dockerContainer/nfs/groups/team-alpha"
    local_mount_path: "/mnt/nfs/groups/team-alpha"
    members: [alice]
  team-beta:
    nfs_host: "10.250.30.115"
    nfs_export_path: "/mnt/dockerContainer/nfs/groups/team-beta"
    local_mount_path: "/mnt/nfs/groups/team-beta"
    members: [alice, carol]
""",
        encoding="utf-8",
    )
    settings = load_settings(groups_path=groups_path)
    ids = [gid for gid, _ in settings.groups_for_user("alice")]
    assert ids == ["team-alpha", "team-beta"]


def test_validate_group_unknown_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    groups_path = tmp_path / "groups.yaml"
    groups_path.write_text(
        """
groups:
  bad:
    nfs_host: "10.250.30.115"
    nfs_export_path: "/mnt/dockerContainer/nfs/groups/bad"
    local_mount_path: "/mnt/nfs/groups/bad"
    members: [nobody]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown member"):
        load_settings(groups_path=groups_path)


def _auth(client) -> dict[str, str]:
    token = client.post("/login", json={"username": "alice", "password": "alice-dev"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
