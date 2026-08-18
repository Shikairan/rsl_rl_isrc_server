#!/usr/bin/env python3
"""Complete client-path test: login → mount → inspect → start → run → wait → results + obs."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("INTEGRATION_A_PORT", "8017")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "integration" / "_lib"))

from common import (  # noqa: E402
    A_BASE,
    ALICE,
    ALICE_EXPORT,
    ALICE_MNT,
    NFS_HOST,
    CaseRunner,
    b_url,
    current_container,
    docker_cmd,
    docker_ps_name,
    ensure_live_a,
    force_rm,
    http,
    loads,
    login,
    one_line,
    remount_alice,
    run_cmd,
    runner_absent_or_down,
    ssh_nfs,
    start_container,
    start_task,
    stop_container,
    sudo_cmd,
    wait_b_health,
)

import units_test_common as _uc  # noqa: E402

fill_plan_results = _uc.fill_plan_results

OBS_IMAGE = "rsl_rl_isrc:v3-C"
OBS_SCRIPT_REL = "jobs/complete_obs_smoke.py"
OBS_SCRIPT_ABS = Path(ALICE_MNT) / OBS_SCRIPT_REL
OBS_FRAMES_ABS = Path(ALICE_MNT) / "jobs/complete_obs_frames.json"
OBS_SMOKE = """from __future__ import annotations
import os
import runpy
import sys
from pathlib import Path

os.chdir("/opt/rsl_rl_isrc")
sys.argv = [
    "test_ppo_g1_mujoco_ddp.py",
    "--num-envs", "8",
    "--max-iterations", "1",
]
ok = False
try:
    runpy.run_path(
        "/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
        run_name="__main__",
    )
    ok = True
except SystemExit as exc:
    ok = exc.code in (0, None)
if ok:
    Path("/workspace/jobs/last_run.txt").write_text(
        "finished_at=complete-obs-smoke\\ndevice=cuda:0\\ntorch=2.11.0+cu128\\nloss=obs\\n",
        encoding="utf-8",
    )
    print("wrote /workspace/jobs/last_run.txt", flush=True)
"""


def _sub_obs(obs_ep: str, frames: list, stop: threading.Event) -> None:
    try:
        import zmq
    except ImportError:
        return
    if not obs_ep or ":" not in obs_ep:
        return
    host, port_s = obs_ep.rsplit(":", 1)
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, b"")
    sock.setsockopt(zmq.RCVTIMEO, 500)
    sock.connect(f"tcp://{host}:{port_s}")
    try:
        while not stop.is_set():
            try:
                frames.append(json.loads(sock.recv().decode()))
            except zmq.Again:
                continue
            except Exception:
                break
    finally:
        sock.close()
        ctx.term()


class CompleteRunner(CaseRunner):
    def finish(self) -> int:
        payload = {
            "id": self.case_id,
            "dir": str(self.case_dir),
            "time": _uc.now_iso(),
            "passed": all(s.ok for s in self.steps) if self.steps else False,
            "steps": [
                {
                    "step": s.step,
                    "ok": s.ok,
                    "cmd": s.cmd,
                    "returncode": s.returncode,
                    "result": s.text,
                }
                for s in self.steps
            ],
        }
        (self.case_dir / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log = [f"# {self.case_id} {_uc.now_iso()}", f"passed={payload['passed']}", ""]
        for s in self.steps:
            log.append(f"## step {s.step} {'PASS' if s.ok else 'FAIL'}")
            log.append(f"cmd: {s.cmd}")
            log.append(s.text)
            log.append("")
        (self.case_dir / "result.log").write_text("\n".join(log), encoding="utf-8")
        fill_plan_results(self.case_dir / "PLAN.md", [s.text for s in self.steps])
        return 0 if payload["passed"] else 1


def run_complete(r: CompleteRunner) -> None:
    ensure_live_a()
    token = ""
    ep = ""
    obs_ep = ""
    tid = ""
    try:
        # ① 登录
        code, body = http("GET", f"{A_BASE}/health", timeout=5)
        r.record(
            1,
            ok=code == 200 and "ok" in body,
            cmd="GET $A/health",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        code, body = http(
            "POST",
            f"{A_BASE}/login",
            json_body={"username": "alice", "password": "wrong"},
            timeout=15,
        )
        r.record(2, ok=code == 401, cmd="POST /login 错密码", detail=f"HTTP {code} body={body}", rc=code)
        code, data, token = login(ALICE)
        r.record(
            3,
            ok=code == 200
            and bool(token)
            and data.get("nfs_host") == NFS_HOST
            and data.get("nfs_export_path") == ALICE_EXPORT.split(":", 1)[-1],
            cmd="POST /login alice",
            detail=f"HTTP {code} nfs_host={data.get('nfs_host')} export={data.get('nfs_export_path')} token_len={len(token)}",
            rc=code,
        )
        code, body = http(
            "POST",
            f"{A_BASE}/containers/start",
            json_body={"image": OBS_IMAGE, "gpu_count": 2},
            timeout=15,
        )
        r.record(4, ok=code == 401, cmd="POST /containers/start 无 token", detail=f"HTTP {code} body={body}", rc=code)

        # ② 挂载
        p = run_cmd(["showmount", "-e", NFS_HOST])
        r.record_cmd(
            5,
            p,
            p.returncode == 0
            and "/mnt/dockerContainer/nfs" in p.stdout
            and "/mnt/dockerContainer/nfs/alice" in p.stdout,
        )
        p = run_cmd(["findmnt", ALICE_MNT])
        mounted = p.returncode == 0 and ALICE_EXPORT in p.stdout.replace("\\040", " ") and "nfs" in p.stdout
        r.record_cmd(6, p, mounted)
        if mounted:
            r.record(7, ok=True, cmd="(已挂载，跳过 mount)", detail="已挂载，未重复执行 mount", rc=0)
        else:
            remount_alice()
            chk = run_cmd(["findmnt", "-n", "-o", "SOURCE", ALICE_MNT])
            r.record_cmd(7, chk, NFS_HOST in chk.stdout and "alice" in chk.stdout)
        p = run_cmd(["ls", f"{ALICE_MNT}/jobs/train.py"])
        r.record_cmd(8, p, p.returncode == 0)

        # ③ 内部检查
        p = sudo_cmd(
            ["bash", "-lc", "echo ping | tee /mnt/nfs/alice/jobs/complete_probe.txt"]
        )
        local = run_cmd(["cat", f"{ALICE_MNT}/jobs/complete_probe.txt"])
        r.record_cmd(
            9,
            p,
            p.returncode == 0 and local.stdout.strip() == "ping",
            note=f"本机 cat={local.stdout.strip()!r}",
        )
        p = ssh_nfs("cat /mnt/dockerContainer/nfs/alice/jobs/complete_probe.txt")
        r.record_cmd(10, p, p.returncode == 0 and p.stdout.strip() == "ping")
        p = docker_cmd(
            ["image", "inspect", OBS_IMAGE, "--format", "{{.Id}} {{json .Config.Entrypoint}} {{json .Config.ExposedPorts}}"]
        )
        r.record_cmd(
            11,
            p,
            p.returncode == 0 and "entrypoint.sh" in p.stdout and "15557" in p.stdout,
            note="须为 v3-C（含 Server B + obsserver）",
        )
        p = run_cmd(["nvidia-smi", "-L"])
        r.record_cmd(12, p, p.returncode == 0 and "GPU 0:" in p.stdout)
        leftover = docker_ps_name("runner-alice")
        if leftover and token:
            stop_container(token)
            force_rm("runner-alice")
            leftover = docker_ps_name("runner-alice")
        r.record(
            13,
            ok=runner_absent_or_down("runner-alice"),
            cmd="docker ps -a --filter name=runner-alice",
            detail=leftover or "无 runner-alice",
            rc=0,
        )
        p = run_cmd(["head", "-n", "5", f"{ALICE_MNT}/jobs/train.py"])
        r.record_cmd(14, p, p.returncode == 0 and "python" in p.stdout.lower())
        OBS_SCRIPT_ABS.parent.mkdir(parents=True, exist_ok=True)
        OBS_SCRIPT_ABS.write_text(OBS_SMOKE, encoding="utf-8")

        # ④ 运行容器
        code4, data4, ep = start_container(token, gpu_count=2, image=OBS_IMAGE)
        obs_ep = str(data4.get("obs_pub_endpoint") or "")
        r.record(
            15,
            ok=code4 == 200
            and data4.get("container_name") == "runner-alice"
            and data4.get("container_status") == "running"
            and data4.get("nfs_mount_path") == "/workspace"
            and bool(ep)
            and ep.startswith("10.213.35.42:31")
            and obs_ep.startswith("10.213.35.42:32"),
            cmd=f"POST /containers/start {OBS_IMAGE} gpu_count=2",
            detail=f"HTTP {code4} endpoint={ep} obs_pub={obs_ep} body={data4}",
            rc=code4,
        )
        cc, cb = current_container(token)
        cur = loads(cb)
        r.record(
            16,
            ok=cc == 200
            and cur.get("server_b_endpoint") == ep
            and cur.get("obs_pub_endpoint") == obs_ep
            and cur.get("container_name") == "runner-alice",
            cmd="GET /containers/current",
            detail=f"HTTP {cc} body={cb}",
            rc=cc,
        )
        code_id, data_id, ep2 = start_container(token, gpu_count=2, image=OBS_IMAGE)
        r.record(
            17,
            ok=code_id == 200 and ep2 == ep and data_id.get("obs_pub_endpoint") == obs_ep,
            cmd="POST /containers/start 幂等",
            detail=f"HTTP {code_id} ep1={ep} ep2={ep2} obs={data_id.get('obs_pub_endpoint')} body={data_id}",
            rc=code_id,
        )
        p = docker_cmd(
            ["ps", "--filter", "name=runner-alice", "--format", "{{.Names}} {{.Status}} {{.Ports}}"]
        )
        r.record_cmd(
            18,
            p,
            "runner-alice" in p.stdout
            and "Up" in p.stdout
            and "8080" in p.stdout
            and "15557" in p.stdout,
        )
        p = docker_cmd(["exec", "runner-alice", "ls", "/workspace/jobs/train.py"])
        r.record_cmd(19, p, p.returncode == 0 and "train.py" in p.stdout)
        hc, hb = wait_b_health(ep) if ep else (0, "无 endpoint")
        r.record(20, ok=hc == 200 and "ok" in hb, cmd=f"GET http://{ep}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        if obs_ep and ":" in obs_ep:
            host, port_s = obs_ep.rsplit(":", 1)
            p = run_cmd(
                [
                    "python3",
                    "-c",
                    f"import socket;s=socket.create_connection(({host!r},{int(port_s)}),2);s.close();print('ok')",
                ],
                timeout=10,
            )
        else:
            p = run_cmd(["python3", "-c", "print('missing obs_pub_endpoint')"], timeout=5)
        r.record_cmd(21, p, p.returncode == 0 and "ok" in p.stdout)

        # ⑤ 执行
        code, body = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={"script_path": "../etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
        )
        r.record(
            22,
            ok=code == 400 and "escapes workspace" in body,
            cmd="POST /tasks/start ../etc/passwd",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        code, body = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={"script_path": "/etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
        )
        r.record(
            23,
            ok=code == 400 and "must be relative" in body,
            cmd="POST /tasks/start /etc/passwd",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        frames: list = []
        stop_sub = threading.Event()
        sub_thr = threading.Thread(target=_sub_obs, args=(obs_ep, frames, stop_sub), daemon=True)
        sub_thr.start()
        time.sleep(0.3)
        code5, data5 = start_task(
            ep,
            {
                "script_path": OBS_SCRIPT_REL,
                "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
                "script_args": [],
            },
        )
        tid = str(data5.get("task_id") or "")
        r.record(
            24,
            ok=code5 == 202 and data5.get("status") == "running" and bool(tid),
            cmd=f"POST /tasks/start {OBS_SCRIPT_REL}（开 ZMQ obs，无 --no-zmq-obs）",
            detail=f"HTTP {code5} body={data5} obs_pub={obs_ep}",
            rc=code5,
        )

        # ⑥ 等待：先拉 logs、再打 409，再轮询终态（B 结束后释放日志）
        logs_text = ""
        last: dict = {}
        if ep and tid:
            code409, body409 = http(
                "POST",
                b_url(ep, "/tasks/start"),
                json_body={
                    "script_path": "jobs/train.py",
                    "torchrun_args": ["--standalone"],
                    "script_args": [],
                },
            )
            offset = 0
            deadline = time.time() + 90
            while time.time() < deadline:
                lc, lb = http("GET", b_url(ep, f"/tasks/{tid}/logs?since={offset}"), timeout=8)
                if lc == 200:
                    extra = loads(lb).get("lines") or []
                    if extra:
                        logs_text = (logs_text + "\n" + "\n".join(str(x) for x in extra)).strip()
                    offset = int(loads(lb).get("next_offset") or offset)
                _cs, bs = http("GET", b_url(ep, f"/tasks/{tid}/status"), timeout=8)
                last = loads(bs) or {"raw": bs}
                if last.get("status") in {"succeeded", "failed", "stopped"}:
                    break
                time.sleep(0.4)
            stop_sub.set()
            sub_thr.join(timeout=2)
            OBS_FRAMES_ABS.write_text(
                json.dumps({"obs_pub_endpoint": obs_ep, "n_frames": len(frames), "frames": frames[:8]}, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            r.record(
                25,
                ok=bool(logs_text.strip())
                and ("cuda" in logs_text.lower() or "rank=" in logs_text or "iteration" in logs_text.lower() or "world_size" in logs_text),
                cmd=f"GET /tasks/{tid}/logs?since=0（running 期间采集）",
                detail=one_line(logs_text, 360) or "empty",
                rc=0 if logs_text.strip() else 1,
            )
            r.record(
                26,
                ok=code409 == 409 and "already running" in body409,
                cmd="POST /tasks/start 第二次",
                detail=f"HTTP {code409} body={body409}",
                rc=code409,
            )
            r.record(
                27,
                ok=last.get("status") == "succeeded" and last.get("exit_code") == 0,
                cmd=f"GET /tasks/{tid}/status 轮询",
                detail=str(last),
                rc=0 if last.get("status") == "succeeded" else 1,
            )
            head = json.dumps(frames[:1], ensure_ascii=False)[:420] if frames else ""
            print("======== OBS 画面帧 ========", flush=True)
            print(f"obs_pub_endpoint={obs_ep} n_frames={len(frames)}", flush=True)
            print(head or "(empty)", flush=True)
            print("===========================", flush=True)
            r.record(
                28,
                ok=len(frames) > 0 and isinstance(frames[0], list),
                cmd=f"SUB {obs_ep} 收画面帧",
                detail=f"n_frames={len(frames)} head={one_line(head, 360) or 'empty'}",
                rc=0 if frames else 1,
            )
        else:
            stop_sub.set()
            r.record(25, ok=False, cmd="GET logs", detail="无 endpoint/task_id", rc=1)
            r.record(26, ok=False, cmd="POST 第二次", detail="跳过", rc=1)
            r.record(27, ok=False, cmd="轮询 status", detail="跳过", rc=1)
            r.record(28, ok=False, cmd="SUB obs", detail="跳过", rc=1)
            last = {}

        # ⑦ 查看结果
        r.record(
            29,
            ok=last.get("status") == "succeeded" and last.get("exit_code") == 0 and bool(last.get("finished_at")),
            cmd=f"GET /tasks/{tid}/status 终态",
            detail=str(last),
            rc=0 if last.get("status") == "succeeded" else 1,
        )
        local = run_cmd(["cat", f"{ALICE_MNT}/jobs/last_run.txt"])
        r.record_cmd(
            30,
            local,
            local.returncode == 0
            and "device=cuda:0" in local.stdout
            and "2.11.0" in local.stdout
            and "loss=" in local.stdout,
        )
        remote = ssh_nfs("cat /mnt/dockerContainer/nfs/alice/jobs/last_run.txt")
        r.record_cmd(
            31,
            remote,
            remote.returncode == 0 and remote.stdout.strip() == local.stdout.strip(),
            note=f"本机={one_line(local.stdout, 120)}",
        )
        obs_file = run_cmd(["cat", str(OBS_FRAMES_ABS)])
        obs_ok = False
        try:
            obs_data = json.loads(obs_file.stdout) if obs_file.returncode == 0 else {}
            obs_ok = int(obs_data.get("n_frames") or 0) > 0
        except json.JSONDecodeError:
            obs_data = {}
        r.record_cmd(
            32,
            obs_file,
            obs_file.returncode == 0 and obs_ok,
            note=f"n_frames={obs_data.get('n_frames')} obs_pub={obs_data.get('obs_pub_endpoint')}",
        )
        code_stop, body_stop = stop_container(token) if token else (0, "无 token")
        r.record(
            33,
            ok=code_stop == 200 and "stopped" in body_stop,
            cmd="POST /containers/stop",
            detail=f"HTTP {code_stop} body={body_stop}",
            rc=code_stop,
        )
        cc, cb = current_container(token) if token else (0, "无 token")
        r.record(
            34,
            ok=cc == 404 and "no container" in cb,
            cmd="GET /containers/current",
            detail=f"HTTP {cc} body={cb}",
            rc=cc,
        )
        leftover = docker_ps_name("runner-alice")
        r.record(
            35,
            ok=runner_absent_or_down("runner-alice"),
            cmd="docker ps -a --filter name=runner-alice",
            detail=leftover or "无 runner-alice",
            rc=0,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def main() -> int:
    runner = CompleteRunner("C-FULL", HERE)
    try:
        run_complete(runner)
    except Exception as exc:  # noqa: BLE001
        n = len(runner.steps) + 1
        runner.record(n, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}")
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
