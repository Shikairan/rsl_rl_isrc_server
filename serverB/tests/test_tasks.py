from __future__ import annotations

import time


def _wait_status(client, task_id: str, terminal: set[str], timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/tasks/{task_id}/status")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in terminal:
            return last
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} not terminal: {last}")


def test_path_escape_http(client) -> None:
    resp = client.post(
        "/tasks/start",
        json={"script_path": "../etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/tasks/start",
        json={"script_path": "/etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
    )
    assert resp.status_code == 400


def test_start_status_logs_then_released(client) -> None:
    resp = client.post(
        "/tasks/start",
        json={"script_path": "jobs/hello.py", "torchrun_args": [], "script_args": ["--epochs", "1"]},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    task_id = body["task_id"]

    seen: list[str] = []
    deadline = time.time() + 5
    offset = 0
    while time.time() < deadline:
        logs = client.get(f"/tasks/{task_id}/logs", params={"since": offset})
        if logs.status_code == 200:
            payload = logs.json()
            seen.extend(payload["lines"])
            offset = payload["next_offset"]
        st = client.get(f"/tasks/{task_id}/status")
        if st.json()["status"] != "running":
            break
        time.sleep(0.05)

    final = _wait_status(client, task_id, {"succeeded", "failed"})
    assert final["status"] == "succeeded"
    assert final["exit_code"] == 0
    gone = client.get(f"/tasks/{task_id}/logs", params={"since": 0})
    assert gone.status_code == 404
    joined = "\n".join(seen)
    assert "hello-from-sb" in joined


def test_single_task_lock_and_stop(client) -> None:
    first = client.post(
        "/tasks/start",
        json={"script_path": "jobs/sleep.py", "torchrun_args": [], "script_args": ["8"]},
    )
    assert first.status_code == 202
    task_id = first.json()["task_id"]

    second = client.post(
        "/tasks/start",
        json={"script_path": "jobs/hello.py", "torchrun_args": [], "script_args": []},
    )
    assert second.status_code == 409

    stopped = client.post(f"/tasks/{task_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    again = client.post(f"/tasks/{task_id}/stop")
    assert again.status_code == 200

    final = _wait_status(client, task_id, {"stopped", "succeeded", "failed"})
    assert final["status"] == "stopped"

    third = client.post(
        "/tasks/start",
        json={"script_path": "jobs/hello.py", "torchrun_args": [], "script_args": []},
    )
    assert third.status_code == 202
    _wait_status(client, third.json()["task_id"], {"succeeded", "failed"})
