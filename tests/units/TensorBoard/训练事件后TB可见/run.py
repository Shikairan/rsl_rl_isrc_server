#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, ServerA, cleanup_runner_containers, docker_cmd, http, wait_http

TB_IMAGE = "rsl_rl_isrc:v3-D"
WRITE_EVT = (
    "from torch.utils.tensorboard import SummaryWriter;"
    "w=SummaryWriter('/workspace/logs/tensorboard/t_tb_04');"
    "w.add_scalar('loss', 1.23, 0); w.flush(); w.close(); print('ok')"
)


def main() -> int:
    runner = CaseRunner("T-TB-04", Path(__file__).resolve().parent)
    cleanup_runner_containers()
    srv = ServerA(docker=True, port=18118)
    token = ""
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
        runner.record(
            1,
            ok=code1 == 200 and bool(tb_ep),
            cmd="POST /containers/start",
            detail=f"HTTP {code1} tb={tb_ep}",
            rc=code1,
        )

        p = docker_cmd(["exec", "runner-alice", "python3", "-c", WRITE_EVT], timeout=60)
        runner.record_cmd(2, p, p.returncode == 0 and "ok" in p.combined)

        url = f"http://{tb_ep}/" if tb_ep else "http://127.0.0.1:9/"
        ready = wait_http(url, timeout=20) if tb_ep else False
        code3, body3 = http("GET", url, timeout=10) if tb_ep else (0, "no-tb")
        runner.record(
            3,
            ok=bool(tb_ep) and ready and code3 == 200,
            cmd=f"GET {url}",
            detail=f"ready={ready} HTTP {code3} body={body3[:160]}",
            rc=code3,
        )
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        code4, body4 = http(
            "POST",
            f"{srv.base}/containers/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        runner.record(4, ok=code4 == 200, cmd="POST /containers/stop", detail=f"HTTP {code4} {body4}", rc=code4)
        srv.stop()
        cleanup_runner_containers()
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
