from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "workspace"
    jobs = ws / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "hello.py").write_text(
        "import sys, time\n"
        "print('hello-from-sb', flush=True)\n"
        "print('args', sys.argv[1:], flush=True)\n"
        "time.sleep(0.3)\n",
        encoding="utf-8",
    )
    (jobs / "sleep.py").write_text(
        "import sys, time\n"
        "print('sleep-start', flush=True)\n"
        "time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 30)\n"
        "print('sleep-end', flush=True)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SERVER_B_WORKSPACE_ROOT", str(ws))
    monkeypatch.setenv("SERVER_B_LAUNCHER", sys.executable)
    monkeypatch.setenv("SERVER_B_STOP_GRACE_SEC", "1")
    monkeypatch.setenv("SERVER_B_LOG_ENABLED", "0")
    return ws


@pytest.fixture()
def client(workspace: Path) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
