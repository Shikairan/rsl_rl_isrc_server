#!/usr/bin/env python3
"""Helpers for integration cases. Reuses units CaseRunner; talks to live Server A."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

UNITS_COMMON = Path("/home/isrc5090/149server/tests/units/_lib/common.py")
_spec = importlib.util.spec_from_file_location("units_test_common", UNITS_COMMON)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load {UNITS_COMMON}")
_uc = importlib.util.module_from_spec(_spec)
sys.modules["units_test_common"] = _uc
_spec.loader.exec_module(_uc)

ALICE_EXPORT = _uc.ALICE_EXPORT
ALICE_MNT = _uc.ALICE_MNT
BOB_MNT = _uc.BOB_MNT
CONDA_PY = _uc.CONDA_PY
CaseRunner = _uc.CaseRunner
NFS_HOST = _uc.NFS_HOST
SERVER_A = _uc.SERVER_A
docker_cmd = _uc.docker_cmd
http = _uc.http
one_line = _uc.one_line
remount_alice = _uc.remount_alice
remount_bob = _uc.remount_bob
run_cmd = _uc.run_cmd
ssh_nfs = _uc.ssh_nfs
sudo_cmd = _uc.sudo_cmd
wait_http = _uc.wait_http

A_HOST = "10.213.35.42"
A_PORT = int(os.environ.get("INTEGRATION_A_PORT", "8000"))
A_BASE = f"http://{A_HOST}:{A_PORT}"
SB_IMAGE = "rsl_rl_isrc:v3-B"
ALICE = {"username": "alice", "password": "alice-dev"}
BOB = {"username": "bob", "password": "bob-dev"}

_A_PROC: subprocess.Popen[str] | None = None
_A_LOG = Path(f"/tmp/servera-integration-{A_PORT}.log")


def loads(body: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def a_healthy() -> bool:
    return wait_http(f"{A_BASE}/health", timeout=3.0)


def ensure_live_a() -> str:
    """Reuse site Server A on 10.213.35.42:8000; start it if down. Do not use unit sqlite."""
    global _A_PROC
    if a_healthy():
        return "reused"
    if wait_http(f"http://127.0.0.1:{A_PORT}/health", timeout=2.0):
        run_cmd(["bash", "-lc", f"fuser -k {A_PORT}/tcp >/dev/null 2>&1 || true"], timeout=8)
        time.sleep(0.5)
        if a_healthy():
            return "reused"
    env = os.environ.copy()
    env["SERVER_A_DOCKER_ENABLED"] = "true"
    env["SERVER_A_NFS_ENABLED"] = "false"
    _A_LOG.write_text("", encoding="utf-8")
    logf = _A_LOG.open("w", encoding="utf-8")
    inner = [
        str(CONDA_PY),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(A_PORT),
    ]
    _A_PROC = subprocess.Popen(
        ["sg", "docker", "-c", " ".join(shlex.quote(x) for x in inner)],
        cwd=str(SERVER_A),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    if not wait_http(f"{A_BASE}/health", timeout=30):
        log = _A_LOG.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"Server A 未能在 {A_BASE} 探活；log={log}")
    return "started"


def login(user: dict[str, str] | None = None) -> tuple[int, dict[str, Any], str]:
    body_in = user or ALICE
    code, body = http("POST", f"{A_BASE}/login", json_body=body_in, timeout=15)
    data = loads(body)
    return code, data, str(data.get("token") or "")


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def start_container(
    token: str,
    *,
    gpu_count: int,
    image: str = SB_IMAGE,
    timeout: int = 120,
) -> tuple[int, dict[str, Any], str]:
    code, body = http(
        "POST",
        f"{A_BASE}/containers/start",
        json_body={"image": image, "gpu_count": gpu_count},
        headers=auth_header(token),
        timeout=timeout,
    )
    data = loads(body)
    return code, data, str(data.get("server_b_endpoint") or "")


def stop_container(token: str) -> tuple[int, str]:
    return http("POST", f"{A_BASE}/containers/stop", headers=auth_header(token), timeout=60)


def current_container(token: str) -> tuple[int, str]:
    return http("GET", f"{A_BASE}/containers/current", headers=auth_header(token), timeout=15)


def b_url(ep: str, path: str) -> str:
    return f"http://{ep}{path}"


def wait_b_health(ep: str, *, timeout: float = 20.0) -> tuple[int, str]:
    deadline = time.time() + timeout
    last = (0, "timeout")
    while time.time() < deadline:
        last = http("GET", b_url(ep, "/health"), timeout=3)
        if last[0] == 200 and "ok" in last[1]:
            return last
        time.sleep(0.4)
    return last


def start_task(ep: str, payload: dict[str, Any], *, timeout: int = 20) -> tuple[int, dict[str, Any]]:
    code, body = http("POST", b_url(ep, "/tasks/start"), json_body=payload, timeout=timeout)
    return code, loads(body) or {"raw": body, "http": code}


def poll_task(ep: str, task_id: str, *, timeout: float = 90.0) -> tuple[dict[str, Any], str]:
    """Poll status; collect logs while running (B drops logs after finish)."""
    last: dict[str, Any] = {}
    lines: list[str] = []
    offset = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        _cs, bs = http("GET", b_url(ep, f"/tasks/{task_id}/status"), timeout=8)
        last = loads(bs) or {"raw": bs}
        lc, lb = http("GET", b_url(ep, f"/tasks/{task_id}/logs?since={offset}"), timeout=8)
        if lc == 200:
            log_data = loads(lb)
            chunk = log_data.get("lines") or []
            if isinstance(chunk, list):
                lines.extend(str(x) for x in chunk)
            offset = int(log_data.get("next_offset") or offset)
        if last.get("status") in {"succeeded", "failed", "stopped"}:
            break
        time.sleep(1.0)
    return last, "\n".join(lines)


def docker_ps_name(name: str) -> str:
    p = docker_cmd(["ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}} {{.Status}}"])
    rows = []
    for line in p.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if parts and parts[0] == name:
            rows.append(line.strip())
    return "\n".join(rows)


def runner_absent_or_down(name: str) -> bool:
    text = docker_ps_name(name)
    return (not text) or ("Up" not in text)


def force_rm(*names: str) -> None:
    for name in names:
        docker_cmd(["rm", "-f", name], timeout=60)


def parse_nvidia_uuid_map() -> dict[int, str]:
    p = run_cmd(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"])
    out: dict[int, str] = {}
    for line in p.stdout.splitlines():
        if "," not in line:
            continue
        idx_s, uuid = line.split(",", 1)
        try:
            out[int(idx_s.strip())] = uuid.strip()
        except ValueError:
            continue
    return out


def norm_uuid(text: str) -> str:
    s = "".join(ch for ch in text.lower() if ch.isalnum())
    if s.startswith("gpu"):
        s = s[3:]
    return s


def parse_smi() -> tuple[dict[int, int], dict[int, int], str]:
    """Return (utilization%, memory_mib, raw_csv)."""
    p = run_cmd(
        ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used", "--format=csv,noheader,nounits"]
    )
    util: dict[int, int] = {}
    mem: dict[int, int] = {}
    for line in p.stdout.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
            util[idx] = int(float(parts[1]))
            mem[idx] = int(float(parts[2]))
        except ValueError:
            continue
    return util, mem, p.stdout


def stop_started_a() -> None:
    global _A_PROC
    if _A_PROC is None:
        return
    try:
        os.killpg(_A_PROC.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        _A_PROC.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(_A_PROC.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _A_PROC = None
