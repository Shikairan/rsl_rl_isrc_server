#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd

OBS_IMAGE = "rsl_rl_isrc:v3-C"
SB_IMAGE = "rsl_rl_isrc:v3-B"


def main() -> int:
    runner = CaseRunner("T-OBS-05", Path(__file__).resolve().parent)
    try:
        p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "RSL_RL_ISRC_OBS_RELAY_URL"], timeout=30)
        runner.record_cmd(1, p, p.stdout.strip() == "http://127.0.0.1:15558/post")

        p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "RSL_RL_ISRC_OBS_RELAY_TIMEOUT"], timeout=30)
        runner.record_cmd(2, p, p.stdout.strip() == "0.05")

        p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "OBS_ENABLE"], timeout=30)
        runner.record_cmd(3, p, p.returncode == 0 and p.stdout.strip() in {"", "1"})

        p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", SB_IMAGE, "RSL_RL_ISRC_OBS_RELAY_URL"], timeout=30)
        runner.record_cmd(4, p, p.stdout.strip() == "")
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
