#!/usr/bin/env python3
"""Shared helpers for independent case scripts under 149server/tests."""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO = Path("/home/isrc5090/149server")
TESTS = REPO / "tests"
SERVER_A = REPO / "serverA"
CONDA_BIN = Path.home() / "miniconda3" / "envs" / "serverA" / "bin"
CONDA_PY = CONDA_BIN / "python"
CONDA_PYTEST = CONDA_BIN / "pytest"
SSHPASS = Path.home() / "miniconda3" / "bin" / "sshpass"
NFS_HOST = "10.250.30.115"
ALICE_EXPORT = f"{NFS_HOST}:/mnt/dockerContainer/nfs/alice"
BOB_EXPORT = f"{NFS_HOST}:/mnt/dockerContainer/nfs/bob"
ALICE_MNT = "/mnt/nfs/alice"
BOB_MNT = "/mnt/nfs/bob"
GROUP_ALPHA_EXPORT = f"{NFS_HOST}:/mnt/dockerContainer/nfs/groups/team-alpha"
GROUP_BETA_EXPORT = f"{NFS_HOST}:/mnt/dockerContainer/nfs/groups/team-beta"
GROUP_ALPHA_MNT = "/mnt/nfs/groups/team-alpha"
GROUP_BETA_MNT = "/mnt/nfs/groups/team-beta"
TZ = timezone(timedelta(hours=8))


def _parse_kv_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data


def local_sudo_password() -> str:
    return _parse_kv_file(REPO / "localpasswd")["passwd"]


def nfs_ssh_creds() -> tuple[str, str, str]:
    data = _parse_kv_file(REPO / "115ssh")
    return data["user"], data["ip"], data["passwd"]


def now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z")


def clip(text: str, limit: int = 1200) -> str:
    text = (text or "").replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n...\n" + text[-limit // 2 :]


def one_line(text: str, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", (text or "").replace("\r", " ").replace("\n", " ")).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text.replace("|", "\\|")


@dataclass
class CmdResult:
    cmd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def combined(self) -> str:
        parts = [p for p in (self.stdout, self.stderr) if p]
        return "\n".join(parts)


def run_cmd(
    args: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = 120,
    input_text: str | None = None,
) -> CmdResult:
    if isinstance(args, str):
        cmd_s = args
        popen_args: Any = args
        shell = True
    else:
        cmd_s = " ".join(shlex.quote(a) for a in args)
        popen_args = args
        shell = False
    try:
        proc = subprocess.run(
            popen_args,
            cwd=str(cwd) if cwd else None,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=shell,
        )
        return CmdResult(cmd_s, proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return CmdResult(cmd_s, 124, out, err + "\n[timeout]", timed_out=True)


def sudo_cmd(args: list[str], *, timeout: int = 60) -> CmdResult:
    return run_cmd(
        ["sudo", "-S", "-p", "", *args],
        input_text=local_sudo_password() + "\n",
        timeout=timeout,
    )


def ssh_nfs(remote: str, *, timeout: int = 60) -> CmdResult:
    user, host, password = nfs_ssh_creds()
    env = os.environ.copy()
    env["SSHPASS"] = password
    return run_cmd(
        [
            str(SSHPASS),
            "-e",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            f"{user}@{host}",
            remote,
        ],
        env=env,
        timeout=timeout,
    )


def docker_cmd(args: list[str], *, timeout: int = 120) -> CmdResult:
    inner = "docker " + " ".join(shlex.quote(a) for a in args)
    return run_cmd(["sg", "docker", "-c", inner], timeout=timeout)


def cleanup_runner_containers(*names: str) -> None:
    """Remove test runner containers so 31xxx/32xxx/33xxx ports are free."""
    if names:
        docker_cmd(["rm", "-f", *names])
        return
    listed = docker_cmd(["ps", "-aq", "--filter", "name=^runner-"])
    ids = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if ids:
        docker_cmd(["rm", "-f", *ids])


def pytest_cmd(*nodeids: str, timeout: int = 120) -> CmdResult:
    return run_cmd([str(CONDA_PYTEST), "-q", *nodeids], cwd=SERVER_A, timeout=timeout)


def wait_http(url: str, *, timeout: float = 20.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


class ServerA:
    def __init__(self, *, docker: bool, nfs: bool = False, port: int = 18017) -> None:
        self.docker = docker
        self.nfs = nfs
        self.port = port
        self.proc: subprocess.Popen[str] | None = None
        self.log_path = Path(f"/tmp/servera-uvicorn-{port}.log")
        self.db_path = Path(f"/tmp/servera-test-{port}-{os.getpid()}-{int(time.time())}.db")

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self.proc is not None:
            return
        self._kill_port()
        env = os.environ.copy()
        env["SERVER_A_DOCKER_ENABLED"] = "true" if self.docker else "false"
        env["SERVER_A_NFS_ENABLED"] = "true" if self.nfs else "false"
        env["SERVER_A_JWT_SECRET"] = "test-secret-must-be-32-bytes-ok!"
        env["SERVER_A_DB_PATH"] = str(self.db_path)
        self.log_path.write_text("", encoding="utf-8")
        logf = self.log_path.open("w", encoding="utf-8")
        inner = [
            str(CONDA_PY),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]
        self.proc = subprocess.Popen(
            ["sg", "docker", "-c", " ".join(shlex.quote(x) for x in inner)],
            cwd=str(SERVER_A),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        if not wait_http(f"{self.base}/health", timeout=25):
            self.stop()
            raise RuntimeError(
                f"uvicorn failed to become healthy; log={self.log_path.read_text(encoding='utf-8', errors='replace')[-2000:]}"
            )

    def _kill_port(self) -> None:
        run_cmd(
            ["bash", "-lc", f"fuser -k {self.port}/tcp >/dev/null 2>&1 || true"],
            timeout=8,
        )
        time.sleep(0.4)

    def stop(self) -> None:
        if self.proc is None:
            self._kill_port()
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.proc.wait(timeout=5)
        self.proc = None
        self._kill_port()


def http(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    data = None
    hdrs = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return int(resp.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return int(exc.code), body
    except Exception as exc:
        return 0, str(exc)


@dataclass
class StepOutcome:
    step: int
    ok: bool
    text: str
    cmd: str
    returncode: int | None = None


@dataclass
class CaseRunner:
    case_id: str
    case_dir: Path
    steps: list[StepOutcome] = field(default_factory=list)

    def record(
        self,
        step: int,
        *,
        ok: bool,
        cmd: str,
        detail: str,
        rc: int | None = None,
    ) -> None:
        verdict = "PASS" if ok else "FAIL"
        text = f"{verdict}；{detail}"
        self.steps.append(StepOutcome(step, ok, text, cmd, rc))
        line = f"[{self.case_id} step {step}] {verdict} rc={rc} cmd={cmd}\n{detail}\n"
        print(line, flush=True)

    def record_cmd(
        self,
        step: int,
        result: CmdResult,
        ok: bool,
        note: str = "",
    ) -> None:
        bits = [f"退出码 {result.returncode}"]
        if result.timed_out:
            bits.append("命令超时")
        if note:
            bits.append(note)
        out = one_line(result.combined, 360)
        if out:
            bits.append(f"输出：{out}")
        self.record(step, ok=ok, cmd=result.cmd, detail="；".join(bits), rc=result.returncode)

    def finish(self) -> int:
        payload = {
            "id": self.case_id,
            "dir": str(self.case_dir),
            "time": now_iso(),
            "passed": all(s.ok for s in self.steps) if self.steps else False,
            "steps": [
                {
                    "step": s.step,
                    "ok": s.ok,
                    "cmd": s.cmd,
                    "returncode": s.returncode,
                    "result": s.text,
                }
                for s in self.steps
            ],
        }
        (self.case_dir / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log = [f"# {self.case_id} {now_iso()}", f"passed={payload['passed']}", ""]
        for s in self.steps:
            log.append(f"## step {s.step} {'PASS' if s.ok else 'FAIL'}")
            log.append(f"cmd: {s.cmd}")
            log.append(s.text)
            log.append("")
        (self.case_dir / "result.log").write_text("\n".join(log), encoding="utf-8")
        fill_plan_results(self.case_dir / "plan.md", [s.text for s in self.steps])
        return 0 if payload["passed"] else 1


def fill_plan_results(plan_path: Path, results: list[str]) -> None:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    idx = 0
    in_table = False
    for line in lines:
        if line.startswith("| 步骤"):
            in_table = True
            out.append(line)
            continue
        if in_table and line.startswith("|------"):
            out.append(line)
            continue
        if in_table and line.startswith("|"):
            cells = line.split("|")
            # '', step, op, cmd, expected, actual, ''
            actual = results[idx] if idx < len(results) else ""
            if len(cells) >= 3:
                cells[-2] = f" {actual} "
            out.append("|".join(cells))
            idx += 1
            continue
        in_table = False
        out.append(line)
    plan_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def ensure_nfs_route() -> None:
    """Clash Meta 会把 10.250.30.115 走 198.18.0.1，NFSv4 会 EPERM。强制走网卡网关。"""
    chk = run_cmd(["ip", "route", "get", NFS_HOST])
    if "ens15f0" in chk.stdout and "198.18" not in chk.stdout:
        return
    sudo_cmd(["ip", "rule", "add", "to", NFS_HOST, "lookup", "main", "pref", "8000"])


def remount_alice() -> CmdResult:
    ensure_nfs_route()
    sudo_cmd(["mkdir", "-p", ALICE_MNT])
    probe = run_cmd(["ls", f"{ALICE_MNT}/jobs"])
    if probe.returncode == 0:
        return probe
    sudo_cmd(["umount", "-l", ALICE_MNT])
    return sudo_cmd(
        [
            "mount",
            "-t",
            "nfs",
            "-o",
            "vers=4,clientaddr=10.213.35.42",
            ALICE_EXPORT,
            ALICE_MNT,
        ],
        timeout=30,
    )


def remount_bob() -> CmdResult:
    ensure_nfs_route()
    sudo_cmd(["mkdir", "-p", BOB_MNT])
    probe = run_cmd(["ls", BOB_MNT])
    if probe.returncode == 0 and "bob_only.txt" in (probe.stdout + "x"):
        # directory readable is enough
        pass
    if run_cmd(["bash", "-lc", f"test -d {BOB_MNT} && ls {BOB_MNT} >/dev/null"]).returncode == 0:
        # if already a live nfs mount
        src = run_cmd(["findmnt", "-n", "-o", "SOURCE", BOB_MNT])
        if NFS_HOST in src.stdout:
            ls = run_cmd(["ls", BOB_MNT])
            if ls.returncode == 0:
                return ls
    sudo_cmd(["umount", "-l", BOB_MNT])
    return sudo_cmd(
        [
            "mount",
            "-t",
            "nfs",
            "-o",
            "vers=4,clientaddr=10.213.35.42",
            BOB_EXPORT,
            BOB_MNT,
        ],
        timeout=30,
    )


def remount_group_alpha() -> CmdResult:
    ensure_nfs_route()
    sudo_cmd(["mkdir", "-p", GROUP_ALPHA_MNT])
    src = run_cmd(["findmnt", "-n", "-o", "SOURCE", GROUP_ALPHA_MNT])
    if src.returncode == 0 and NFS_HOST in src.stdout:
        return run_cmd(["ls", GROUP_ALPHA_MNT])
    sudo_cmd(["umount", "-l", GROUP_ALPHA_MNT])
    return sudo_cmd(
        [
            "mount",
            "-t",
            "nfs",
            "-o",
            "vers=4,clientaddr=10.213.35.42",
            GROUP_ALPHA_EXPORT,
            GROUP_ALPHA_MNT,
        ],
        timeout=30,
    )


def remount_group_beta() -> CmdResult:
    ensure_nfs_route()
    sudo_cmd(["mkdir", "-p", GROUP_BETA_MNT])
    src = run_cmd(["findmnt", "-n", "-o", "SOURCE", GROUP_BETA_MNT])
    if src.returncode == 0 and NFS_HOST in src.stdout:
        return run_cmd(["ls", GROUP_BETA_MNT])
    sudo_cmd(["umount", "-l", GROUP_BETA_MNT])
    return sudo_cmd(
        [
            "mount",
            "-t",
            "nfs",
            "-o",
            "vers=4,clientaddr=10.213.35.42",
            GROUP_BETA_EXPORT,
            GROUP_BETA_MNT,
        ],
        timeout=30,
    )
