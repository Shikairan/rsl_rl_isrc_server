#!/usr/bin/env python3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, ServerA, cleanup_runner_containers, docker_cmd, http, run_cmd

TB_IMAGE = "rsl_rl_isrc:v3-D"


def main() -> int:
    runner = CaseRunner("T-TB-03", Path(__file__).resolve().parent)
    cleanup_runner_containers()
    srv = ServerA(docker=True, port=18117)
    token = ""
    try:
        srv.start()
        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        token = json.loads(body).get("token") or "" if body else ""
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": TB_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        data2 = json.loads(body2) if body2.startswith("{") else {}
        tb_ep = data2.get("tensorboard_endpoint")
        runner.record(
            1,
            ok=code2 == 200 and bool(tb_ep) and ":33" in str(tb_ep),
            cmd=f"POST /containers/start {TB_IMAGE}",
            detail=f"HTTP {code2} tb={tb_ep} body={body2[:400]}",
            rc=code2,
        )

        code3, body3 = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        data3 = json.loads(body3) if body3.startswith("{") else {}
        runner.record(
            2,
            ok=code3 == 200 and data3.get("tensorboard_endpoint") == tb_ep,
            cmd="POST /login",
            detail=f"HTTP {code3} tb={data3.get('tensorboard_endpoint')}",
            rc=code3,
        )

        tcp_ok = False
        if tb_ep and ":" in str(tb_ep):
            host, port_s = str(tb_ep).rsplit(":", 1)
            p = run_cmd(
                [
                    "python3",
                    "-c",
                    f"import socket;s=socket.create_connection(({host!r},{int(port_s)}),3);s.close();print('ok')",
                ],
                timeout=10,
            )
            tcp_ok = p.returncode == 0 and "ok" in p.stdout
        else:
            p = run_cmd(["python3", "-c", "print('no-tb-endpoint')"], timeout=5)
        runner.record(
            3,
            ok=bool(tb_ep) and tcp_ok,
            cmd="TCP connect tensorboard_endpoint",
            detail=f"tb={tb_ep} tcp={tcp_ok} probe={p.stdout.strip() or p.stderr.strip()}",
            rc=p.returncode,
        )

        p = docker_cmd(["ps", "--filter", "name=runner-alice", "--format", "{{.Ports}}"], timeout=10)
        runner.record_cmd(4, p, p.returncode == 0 and "6006/tcp" in p.stdout and "33" in p.stdout)

        code4, body4 = http(
            "GET",
            f"{srv.base}/containers/current",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        data4 = json.loads(body4) if body4.startswith("{") else {}
        code5, body5 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": TB_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        data5 = json.loads(body5) if body5.startswith("{") else {}
        same = data4.get("tensorboard_endpoint") == data5.get("tensorboard_endpoint") == tb_ep
        runner.record(
            5,
            ok=code4 == 200 and code5 == 200 and same,
            cmd="GET /containers/current + POST /containers/start again",
            detail=f"current={data4.get('tensorboard_endpoint')} start2={data5.get('tensorboard_endpoint')}",
            rc=0 if code4 == 200 and code5 == 200 else 1,
        )
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        code6, body6 = http(
            "POST",
            f"{srv.base}/containers/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        runner.record(6, ok=code6 == 200 and "stopped" in body6, cmd="POST /containers/stop", detail=f"HTTP {code6} body={body6}", rc=code6)
        srv.stop()
        cleanup_runner_containers()
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
