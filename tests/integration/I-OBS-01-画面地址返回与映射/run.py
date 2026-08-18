#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("INTEGRATION_A_PORT", "8017")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from common import (  # noqa: E402
    ALICE,
    CaseRunner,
    current_container,
    docker_cmd,
    ensure_live_a,
    force_rm,
    login,
    remount_alice,
    run_cmd,
    start_container,
    stop_container,
)

OBS_IMAGE = "rsl_rl_isrc:v3-C"


def main() -> int:
    runner = CaseRunner("I-OBS-01", Path(__file__).resolve().parent)
    token = ""
    try:
        ensure_live_a()
        remount_alice()
        force_rm("runner-alice")

        code, _data, token = login(ALICE)
        code1, data1, _ep1 = start_container(token, gpu_count=0, image=OBS_IMAGE)
        obs_ep = str(data1.get("obs_pub_endpoint") or "")
        runner.record(
            1,
            ok=code1 == 200 and obs_ep.startswith("10.213.35.42:32"),
            cmd=f"POST /containers/start {OBS_IMAGE}",
            detail=f"HTTP {code1} body={json.dumps(data1, ensure_ascii=False)}",
            rc=code1,
        )

        code2, body2 = current_container(token)
        data2 = json.loads(body2) if code2 == 200 else {}
        runner.record(
            2,
            ok=code2 == 200 and data2.get("obs_pub_endpoint") == obs_ep,
            cmd="GET /containers/current",
            detail=f"HTTP {code2} body={body2}",
            rc=code2,
        )

        code3, data3, _token2 = login(ALICE)
        runner.record(
            3,
            ok=code3 == 200 and data3.get("obs_pub_endpoint") == obs_ep,
            cmd="POST /login alice",
            detail=f"HTTP {code3} body={json.dumps(data3, ensure_ascii=False)}",
            rc=code3,
        )

        p = docker_cmd(["ps", "--filter", "name=runner-alice", "--format", "{{.Ports}}"], timeout=10)
        ok = p.returncode == 0 and "->8080/tcp" in p.stdout and "->15557/tcp" in p.stdout
        runner.record_cmd(4, p, ok)

        if ":" in obs_ep:
            host, port_s = obs_ep.rsplit(":", 1)
            p = run_cmd(
                ["python3", "-c", f"import socket;s=socket.create_connection(({host!r},{int(port_s)}),2);s.close();print('ok')"],
                timeout=10,
            )
        else:
            p = run_cmd(["python3", "-c", "print('missing obs endpoint')"], timeout=5)
        runner.record_cmd(5, p, p.returncode == 0 and "ok" in p.stdout)

        code6, body6 = stop_container(token)
        runner.record(6, ok=code6 == 200 and "stopped" in body6, cmd="POST /containers/stop", detail=f"HTTP {code6} body={body6}", rc=code6)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
