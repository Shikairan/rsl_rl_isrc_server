#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, ServerA, cleanup_runner_containers, docker_cmd, http

TB_IMAGE = "rsl_rl_isrc:v3-D"


def _login_start(base: str, user: str, password: str) -> tuple[str, int, dict]:
    _c, body = http("POST", f"{base}/login", json_body={"username": user, "password": password})
    token = json.loads(body).get("token") or "" if body else ""
    code, body2 = http(
        "POST",
        f"{base}/containers/start",
        json_body={"image": TB_IMAGE, "gpu_count": 0},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    data = json.loads(body2) if body2.startswith("{") else {}
    return token, code, data


def main() -> int:
    runner = CaseRunner("T-TB-05", Path(__file__).resolve().parent)
    cleanup_runner_containers()
    srv = ServerA(docker=True, port=18119)
    ta = tb = ""
    try:
        srv.start()
        ta, code1, data1 = _login_start(srv.base, "alice", "alice-dev")
        ep_a = str(data1.get("tensorboard_endpoint") or "")
        runner.record(1, ok=code1 == 200 and bool(ep_a), cmd="alice start", detail=f"HTTP {code1} tb={ep_a}", rc=code1)

        tb, code2, data2 = _login_start(srv.base, "bob", "bob-dev")
        ep_b = str(data2.get("tensorboard_endpoint") or "")
        runner.record(2, ok=code2 == 200 and bool(ep_b), cmd="bob start", detail=f"HTTP {code2} tb={ep_b}", rc=code2)

        isolated = bool(ep_a) and bool(ep_b) and ep_a != ep_b and ":33" in ep_a and ":33" in ep_b
        runner.record(3, ok=isolated, cmd="compare tensorboard_endpoint", detail=f"alice={ep_a} bob={ep_b}", rc=0 if isolated else 1)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        for token in (ta, tb):
            if token:
                http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        runner.record(4, ok=True, cmd="stop alice+bob", detail="issued stop", rc=200)
        srv.stop()
        cleanup_runner_containers()
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
