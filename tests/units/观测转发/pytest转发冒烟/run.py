#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, REPO, run_cmd


def main() -> int:
    runner = CaseRunner("T-OBS-01", Path(__file__).resolve().parent)
    try:
        p = run_cmd(["python3", "-m", "pytest", "-q"], cwd=REPO / "obsserver", timeout=180)
        ok = p.returncode == 0 and ("passed" in p.combined or "4 passed" in p.combined)
        runner.record_cmd(1, p, ok)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
