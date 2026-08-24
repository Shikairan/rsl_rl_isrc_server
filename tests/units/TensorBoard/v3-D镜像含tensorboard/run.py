#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd

TB_IMAGE = "rsl_rl_isrc:v3-D"


def main() -> int:
    runner = CaseRunner("T-TB-01", Path(__file__).resolve().parent)
    try:
        p = docker_cmd(["image", "inspect", TB_IMAGE, "--format", "{{.Id}}"], timeout=30)
        runner.record_cmd(1, p, p.returncode == 0 and p.stdout.strip().startswith("sha256:"))

        p = docker_cmd(
            ["run", "--rm", "--entrypoint", "tensorboard", TB_IMAGE, "--version"],
            timeout=45,
        )
        runner.record_cmd(2, p, p.returncode == 0)

        p = docker_cmd(
            ["image", "inspect", TB_IMAGE, "--format", "{{json .Config.ExposedPorts}}"],
            timeout=30,
        )
        ok = (
            p.returncode == 0
            and "8080/tcp" in p.combined
            and "15557/tcp" in p.combined
            and "6006/tcp" in p.combined
        )
        runner.record_cmd(3, p, ok)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
