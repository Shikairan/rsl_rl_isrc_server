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
    current_container,
    ensure_live_a,
    force_rm,
    login,
    remount_alice,
    run_cmd,
    start_container,
    stop_container,
)

OBS_IMAGE = "rsl_rl_isrc:v3-C"
SCRIPT_REL = "jobs/obs_iobs03_smoke.py"
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


def _run_once(ep: str, obs_ep: str) -> dict:
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
    if p.returncode != 0 or not p.stdout.strip():
        return {"_cmd": p.cmd, "_rc": p.returncode, "_raw": p.combined}
    data = json.loads(p.stdout.strip())
    data["_cmd"] = p.cmd
    data["_rc"] = p.returncode
    return data


def main() -> int:
    runner = CaseRunner("I-OBS-03", Path(__file__).resolve().parent)
    token = ""
    try:
        ensure_live_a()
        remount_alice()
        force_rm("runner-alice")
        SCRIPT_ABS.parent.mkdir(parents=True, exist_ok=True)
        SCRIPT_ABS.write_text(OBS_SMOKE, encoding="utf-8")

        _c, _d, token = login(ALICE)
        code1, data1, ep = start_container(token, gpu_count=2, image=OBS_IMAGE)
        obs_ep = str(data1.get("obs_pub_endpoint") or "")
        runner.record(
            1,
            ok=code1 == 200 and bool(ep) and obs_ep.startswith("10.213.35.42:32"),
            cmd=f"POST /containers/start {OBS_IMAGE}",
            detail=f"HTTP {code1} body={json.dumps(data1, ensure_ascii=False)}",
            rc=code1,
        )

        first = _run_once(ep, obs_ep)
        runner.record(
            2,
            ok=bool(first.get("task_id")) and (first.get("final") or {}).get("status") == "succeeded",
            cmd="第一次 /tasks/start + SUB 收帧",
            detail=str(first.get("final") or first),
            rc=int(first.get("_rc", 1)),
        )
        runner.record(
            3,
            ok=isinstance(first.get("frame"), list) and len(first.get("frame") or []) > 0,
            cmd="第一次训练帧",
            detail=json.dumps((first.get("frame") or [])[:1], ensure_ascii=False)[:300],
            rc=0 if first.get("frame") else 1,
        )

        code4, body4 = current_container(token)
        data4 = json.loads(body4) if code4 == 200 else {}
        code5, data5, _ep5 = start_container(token, gpu_count=2, image=OBS_IMAGE)
        same_obs = data4.get("obs_pub_endpoint") == data5.get("obs_pub_endpoint") == obs_ep
        runner.record(
            4,
            ok=code4 == 200 and code5 == 200 and same_obs,
            cmd="GET /containers/current + 幂等 start",
            detail=f"current={data4.get('obs_pub_endpoint')} start2={data5.get('obs_pub_endpoint')}",
            rc=0 if same_obs else 1,
        )

        second = _run_once(ep, obs_ep)
        runner.record(
            5,
            ok=bool(second.get("task_id")) and (second.get("final") or {}).get("status") == "succeeded",
            cmd="第二次 /tasks/start + SUB 收帧",
            detail=str(second.get("final") or second),
            rc=int(second.get("_rc", 1)),
        )
        runner.record(
            6,
            ok=isinstance(second.get("frame"), list) and len(second.get("frame") or []) > 0,
            cmd="第二次训练帧",
            detail=json.dumps((second.get("frame") or [])[:1], ensure_ascii=False)[:300],
            rc=0 if second.get("frame") else 1,
        )

        code7, body7 = stop_container(token)
        runner.record(7, ok=code7 == 200 and "stopped" in body7, cmd="POST /containers/stop", detail=f"HTTP {code7} body={body7}", rc=code7)
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
