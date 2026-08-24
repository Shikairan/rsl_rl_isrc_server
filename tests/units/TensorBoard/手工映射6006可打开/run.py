#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd, http, wait_http

TB_IMAGE = "rsl_rl_isrc:v3-D"
NAME = "tb-manual"


def main() -> int:
    runner = CaseRunner("T-TB-02", Path(__file__).resolve().parent)
    docker_cmd(["rm", "-f", NAME])
    try:
        p = docker_cmd(
            [
                "run",
                "-d",
                "--name",
                NAME,
                "--rm",
                "-p",
                "127.0.0.1:18080:8080",
                "-p",
                "127.0.0.1:13306:6006",
                TB_IMAGE,
            ],
            timeout=30,
        )
        ready_b = wait_http("http://127.0.0.1:18080/health", timeout=25)
        ready_tb = wait_http("http://127.0.0.1:13306/", timeout=40)
        runner.record_cmd(1, p, p.returncode == 0 and ready_b and ready_tb, note=f"health={ready_b} tb={ready_tb}")

        code, body = http("GET", "http://127.0.0.1:13306/", timeout=10)
        runner.record(
            2,
            ok=code == 200,
            cmd="GET http://127.0.0.1:13306/",
            detail=f"HTTP {code} body={body[:200]}",
            rc=code,
        )
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        p = docker_cmd(["rm", "-f", NAME], timeout=20)
        runner.record_cmd(3, p, True)
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
