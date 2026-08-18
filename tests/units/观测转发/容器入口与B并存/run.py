#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd, http, run_cmd, wait_http

OBS_IMAGE = "rsl_rl_isrc:v3-C"


def main() -> int:
    runner = CaseRunner("T-OBS-03", Path(__file__).resolve().parent)
    docker_cmd(["rm", "-f", "obs-entry"])
    try:
        p = docker_cmd(
            ["run", "-d", "--name", "obs-entry", "--rm", "-p", "127.0.0.1:18080:8080", "-p", "127.0.0.1:15557:15557", OBS_IMAGE],
            timeout=30,
        )
        ready = wait_http("http://127.0.0.1:18080/health", timeout=25)
        runner.record_cmd(1, p, p.returncode == 0 and ready, note=f"health_ready={ready}")

        code, body = http("GET", "http://127.0.0.1:18080/health", timeout=5)
        runner.record(2, ok=code == 200 and "ok" in body, cmd="curl /health", detail=f"HTTP {code} body={body}", rc=code)

        p = docker_cmd(["logs", "obs-entry"], timeout=20)
        ok = p.returncode == 0 and "15558/post" in p.combined and "15557" in p.combined
        runner.record_cmd(3, p, ok)

        p = run_cmd(
            ["python3", "-c", "import socket;s=socket.create_connection(('127.0.0.1',15557),2);s.close();print('ok')"],
            timeout=10,
        )
        runner.record_cmd(4, p, p.returncode == 0 and "ok" in p.stdout)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        p = docker_cmd(["stop", "obs-entry"], timeout=20)
        runner.record_cmd(5, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-entry"])
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
