#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, ServerA, cleanup_runner_containers, docker_cmd, http, run_cmd

TB_IMAGE = "rsl_rl_isrc:v3-D"


def tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    p = run_cmd(
        [
            "python3",
            "-c",
            f"import socket;s=socket.create_connection(({host!r},{port}),{timeout});s.close();print('ok')",
        ],
        timeout=10,
    )
    return p.returncode == 0 and "ok" in p.stdout


def main() -> int:
    runner = CaseRunner("T-TB-06", Path(__file__).resolve().parent)
    cleanup_runner_containers()
    srv = ServerA(docker=True, port=18120)
    token = ""
    host, port = "127.0.0.1", 0
    try:
        srv.start()
        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        token = json.loads(body).get("token") or "" if body else ""
        code1, body1 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": TB_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        data1 = json.loads(body1) if body1.startswith("{") else {}
        tb_ep = str(data1.get("tensorboard_endpoint") or "")
        if ":" in tb_ep:
            host, port_s = tb_ep.rsplit(":", 1)
            port = int(port_s)
        runner.record(1, ok=code1 == 200 and port > 0, cmd="POST /containers/start", detail=f"HTTP {code1} tb={tb_ep}", rc=code1)

        ok2 = port > 0 and tcp(host, port)
        runner.record(2, ok=ok2, cmd="TCP before stop", detail=f"{host}:{port} reachable={ok2}", rc=0 if ok2 else 1)

        code3, body3 = http(
            "POST",
            f"{srv.base}/containers/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        runner.record(3, ok=code3 == 200, cmd="POST /containers/stop", detail=f"HTTP {code3} {body3}", rc=code3)

        still = tcp(host, port) if port else True
        runner.record(4, ok=not still, cmd="TCP after stop", detail=f"{host}:{port} reachable={still}", rc=0 if not still else 1)

        p = docker_cmd(["ps", "--filter", "name=runner-alice", "--format", "{{.Names}}"], timeout=10)
        runner.record_cmd(5, p, p.returncode == 0 and "runner-alice" not in p.stdout)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
        if token:
            http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        srv.stop()
        cleanup_runner_containers()
        return runner.finish()
    srv.stop()
    cleanup_runner_containers()
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
