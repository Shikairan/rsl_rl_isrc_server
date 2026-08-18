#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, ServerA, docker_cmd, http, run_cmd

OBS_IMAGE = "rsl_rl_isrc:v3-C"


def main() -> int:
    runner = CaseRunner("T-OBS-07", Path(__file__).resolve().parent)
    docker_cmd(["rm", "-f", "runner-alice"])
    srv = ServerA(docker=True, port=8017)
    token = ""
    try:
        srv.start()

        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        data = {}
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pass
        token = data.get("token") or ""
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": OBS_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        data2 = {}
        try:
            data2 = json.loads(body2)
        except json.JSONDecodeError:
            pass
        obs_ep = data2.get("obs_pub_endpoint")
        runner.record(
            1,
            ok=code2 == 200 and bool(data2.get("obs_pub_endpoint")),
            cmd=f"POST /containers/start {OBS_IMAGE}",
            detail=f"HTTP {code2} server_b={data2.get('server_b_endpoint')} obs_pub={data2.get('obs_pub_endpoint')} body={body2[:400]}",
            rc=code2,
        )

        code3, body3 = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        data3 = {}
        try:
            data3 = json.loads(body3)
        except json.JSONDecodeError:
            pass
        runner.record(
            2,
            ok=code3 == 200 and data3.get("obs_pub_endpoint") == obs_ep,
            cmd="POST /login",
            detail=f"HTTP {code3} server_b={data3.get('server_b_endpoint')} obs_pub={data3.get('obs_pub_endpoint')} body={body3[:400]}",
            rc=code3,
        )

        if obs_ep and ":" in obs_ep:
            host, port_s = obs_ep.rsplit(":", 1)
            p = run_cmd(
                ["python3", "-c", f"import socket;s=socket.create_connection(({host!r},{int(port_s)}),2);s.close();print('ok')"],
                timeout=10,
            )
            tcp_ok = p.returncode == 0 and "ok" in p.stdout
        else:
            p = run_cmd(["python3", "-c", "print('no-obs-endpoint')"], timeout=5)
            tcp_ok = False
        runner.record(
            3,
            ok=bool(obs_ep) and tcp_ok,
            cmd="TCP connect obs_pub_endpoint",
            detail=f"obs_pub={obs_ep} tcp_ready={tcp_ok} probe={p.stdout.strip() or p.stderr.strip()}",
            rc=p.returncode,
        )

        p = docker_cmd(["ps", "--filter", "name=runner-alice", "--format", "{{.Ports}}"], timeout=10)
        runner.record_cmd(4, p, p.returncode == 0 and "15557/tcp" in p.stdout and "32" in p.stdout)

        code4, body4 = http("GET", f"{srv.base}/containers/current", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        data4 = {}
        try:
            data4 = json.loads(body4)
        except json.JSONDecodeError:
            pass
        code5, body5 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": OBS_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        data5 = {}
        try:
            data5 = json.loads(body5)
        except json.JSONDecodeError:
            pass
        same_obs = data4.get("obs_pub_endpoint") == data5.get("obs_pub_endpoint") == obs_ep
        same_name = data4.get("container_name") == data5.get("container_name") == "runner-alice"
        runner.record(
            5,
            ok=code4 == 200 and code5 == 200 and same_obs and same_name,
            cmd="GET /containers/current + POST /containers/start again",
            detail=(
                f"current HTTP {code4} obs_pub={data4.get('obs_pub_endpoint')} "
                f"start2 HTTP {code5} obs_pub={data5.get('obs_pub_endpoint')} "
                f"same_name={same_name}"
            ),
            rc=0 if code4 == 200 and code5 == 200 else 1,
        )
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        code6, body6 = http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        runner.record(
            6,
            ok=code6 == 200 and "stopped" in body6,
            cmd="POST /containers/stop",
            detail=f"HTTP {code6} body={body6}",
            rc=code6,
        )
        srv.stop()
        docker_cmd(["rm", "-f", "runner-alice"])
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
