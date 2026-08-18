#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("INTEGRATION_A_PORT", "8017")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from common import (  # noqa: E402
    ALICE,
    ALICE_MNT,
    CaseRunner,
    b_url,
    ensure_live_a,
    force_rm,
    http,
    login,
    remount_alice,
    run_cmd,
    start_container,
    stop_container,
)

OBS_IMAGE = "rsl_rl_isrc:v3-C"
SCRIPT_REL = "jobs/obs_iobs02_smoke.py"
SCRIPT_ABS = Path(ALICE_MNT) / SCRIPT_REL
OBS_SMOKE = """from __future__ import annotations
import os
import runpy
import sys

os.chdir("/opt/rsl_rl_isrc")
sys.argv = [
    "test_ppo_g1_mujoco_ddp.py",
    "--num-envs", "8",
    "--max-iterations", "1",
]
runpy.run_path(
    "/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
    run_name="__main__",
)
"""


def main() -> int:
    runner = CaseRunner("I-OBS-02", Path(__file__).resolve().parent)
    token = ""
    try:
        ensure_live_a()
        remount_alice()
        force_rm("runner-alice")
        SCRIPT_ABS.parent.mkdir(parents=True, exist_ok=True)
        SCRIPT_ABS.write_text(OBS_SMOKE, encoding="utf-8")
        p0 = run_cmd(["ls", "-l", str(SCRIPT_ABS)], timeout=10)
        runner.record_cmd(1, p0, p0.returncode == 0 and SCRIPT_ABS.name in p0.stdout)

        code, _data, token = login(ALICE)
        code2, data2, ep = start_container(token, gpu_count=2, image=OBS_IMAGE)
        obs_ep = str(data2.get("obs_pub_endpoint") or "")
        runner.record(
            2,
            ok=code2 == 200 and bool(ep) and obs_ep.startswith("10.213.35.42:32"),
            cmd=f"POST /containers/start {OBS_IMAGE} gpu_count=2",
            detail=f"HTTP {code2} body={json.dumps(data2, ensure_ascii=False)}",
            rc=code2,
        )

        py = f"""
import json, time, urllib.request, zmq
ep = {ep!r}
obs_ep = {obs_ep!r}
payload = {{
  "script_path": {SCRIPT_REL!r},
  "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
  "script_args": []
}}
host, port = obs_ep.rsplit(":", 1)
ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"")
s.setsockopt(zmq.RCVTIMEO, 60000)
s.connect(f"tcp://{{host}}:{{port}}")
req = urllib.request.Request(
  f"http://{{ep}}/tasks/start",
  data=json.dumps(payload).encode(),
  headers={{"content-type": "application/json"}},
  method="POST",
)
with urllib.request.urlopen(req, timeout=20) as resp:
  body = json.loads(resp.read().decode())
task_id = body["task_id"]
frame = json.loads(s.recv().decode())
deadline = time.time() + 120
last = {{}}
while time.time() < deadline:
  with urllib.request.urlopen(f"http://{{ep}}/tasks/{{task_id}}/status", timeout=8) as resp:
    last = json.loads(resp.read().decode())
  if last.get("status") in {{"succeeded", "failed", "stopped"}}:
    break
  time.sleep(1)
print(json.dumps({{"task_id": task_id, "frame": frame, "final": last}}, ensure_ascii=False))
"""
        p = run_cmd(["python3", "-c", py], timeout=180)
        data3 = json.loads(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else {}
        runner.record_cmd(3, p, p.returncode == 0 and bool(data3.get("task_id")))
        frame = data3.get("frame") or []
        runner.record(
            4,
            ok=isinstance(frame, list) and len(frame) > 0,
            cmd="SUB obs_pub_endpoint 等首帧",
            detail=f"frame_head={json.dumps(frame[:1], ensure_ascii=False)[:300]}",
            rc=0 if frame else 1,
        )
        final = data3.get("final") or {}
        runner.record(
            5,
            ok=final.get("status") == "succeeded" and final.get("exit_code") == 0,
            cmd="GET /tasks/$TASK_ID/status",
            detail=str(final),
            rc=0 if final.get("status") == "succeeded" else 1,
        )

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
