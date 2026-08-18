#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd, run_cmd, wait_http

OBS_IMAGE = "rsl_rl_isrc:v3-C"


def main() -> int:
    runner = CaseRunner("T-OBS-04", Path(__file__).resolve().parent)
    docker_cmd(["rm", "-f", "obs-pub"])
    try:
        p = docker_cmd(
            ["run", "-d", "--name", "obs-pub", "--rm", "-p", "127.0.0.1:18080:8080", "-p", "127.0.0.1:15557:15557", OBS_IMAGE],
            timeout=30,
        )
        ready = wait_http("http://127.0.0.1:18080/health", timeout=25)
        runner.record_cmd(1, p, p.returncode == 0 and ready, note=f"health_ready={ready}")

        payload = "[[[0.1, 0.2, 0.9], [0.0, 0.0, 0.0, 1.0], [0.5, -0.3]]]"
        py = (
            "import json, subprocess, zmq; "
            f"payload={payload!r}; "
            "ctx=zmq.Context(); s=ctx.socket(zmq.SUB); s.setsockopt(zmq.SUBSCRIBE, b''); "
            "s.setsockopt(zmq.RCVTIMEO, 5000); s.connect('tcp://127.0.0.1:15557'); "
            "subprocess.run(['sg','docker','-c',"
            "'docker exec obs-pub python3 -c \"import json,urllib.request; "
            "req=urllib.request.Request(\\'http://127.0.0.1:15558/post\\', "
            "data=json.dumps(json.loads(\\'" + payload.replace("'", "\\'") + "\\')).encode(), "
            "headers={\\'Content-Type\\':\\'application/json\\'}, method=\\'POST\\'); "
            "print(urllib.request.urlopen(req, timeout=3).read().decode())\"'], check=True); "
            "msg=json.loads(s.recv().decode()); print(json.dumps(msg, ensure_ascii=False))"
        )
        p = run_cmd(["python3", "-c", py], timeout=20)
        ok = p.returncode == 0 and "ok" in p.stdout and payload.replace(" ", "") in p.stdout.replace(" ", "")
        runner.record_cmd(2, p, ok)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        p = docker_cmd(["stop", "obs-pub"], timeout=20)
        runner.record_cmd(3, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-pub"])
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
