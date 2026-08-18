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
    BOB,
    BOB_MNT,
    CaseRunner,
    ensure_live_a,
    force_rm,
    login,
    remount_alice,
    remount_bob,
    run_cmd,
    start_container,
    stop_container,
)

OBS_IMAGE = "rsl_rl_isrc:v3-C"
ALICE_REL = "jobs/obs_iobs04_alice.py"
BOB_REL = "jobs/obs_iobs04_bob.py"
ALICE_ABS = Path(ALICE_MNT) / ALICE_REL
BOB_ABS = Path(BOB_MNT) / BOB_REL
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


def _sub_and_maybe_start(ep: str, obs_ep: str, script_rel: str, *, timeout_ms: int = 8000) -> dict:
    py = f"""
import json, time, urllib.request, urllib.error, zmq
ep = {ep!r}
obs_ep = {obs_ep!r}
script_rel = {script_rel!r}
host, port = obs_ep.rsplit(":", 1)
ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"")
s.setsockopt(zmq.RCVTIMEO, {timeout_ms})
s.connect(f"tcp://{{host}}:{{port}}")
task_id = ""
if ep:
  payload = {{"script_path": script_rel, "torchrun_args": ["--nproc_per_node", "1", "--standalone"], "script_args": []}}
  req = urllib.request.Request(
    f"http://{{ep}}/tasks/start",
    data=json.dumps(payload).encode(),
    headers={{"content-type": "application/json"}},
    method="POST",
  )
  with urllib.request.urlopen(req, timeout=20) as resp:
    task_id = json.loads(resp.read().decode()).get("task_id", "")
try:
  frame = json.loads(s.recv().decode())
except Exception as exc:
  frame = []
  print(json.dumps({{"task_id": task_id, "frame": frame, "error": str(exc)}}, ensure_ascii=False))
  raise SystemExit(0)
deadline = time.time() + 120
last = {{}}
if task_id:
  while time.time() < deadline:
    with urllib.request.urlopen(f"http://{{ep}}/tasks/{{task_id}}/status", timeout=8) as resp:
      last = json.loads(resp.read().decode())
    if last.get("status") in {{"succeeded", "failed", "stopped"}}:
      break
    time.sleep(1)
print(json.dumps({{"task_id": task_id, "frame": frame, "final": last}}, ensure_ascii=False))
"""
    p = run_cmd(["python3", "-c", py], timeout=180)
    if not p.stdout.strip():
        return {"_rc": p.returncode, "_raw": p.combined}
    data = json.loads(p.stdout.strip())
    data["_rc"] = p.returncode
    return data


def main() -> int:
    runner = CaseRunner("I-OBS-04", Path(__file__).resolve().parent)
    alice_token = ""
    bob_token = ""
    try:
        ensure_live_a()
        remount_alice()
        remount_bob()
        force_rm("runner-alice", "runner-bob")
        ALICE_ABS.parent.mkdir(parents=True, exist_ok=True)
        BOB_ABS.parent.mkdir(parents=True, exist_ok=True)
        ALICE_ABS.write_text(OBS_SMOKE, encoding="utf-8")
        BOB_ABS.write_text(OBS_SMOKE, encoding="utf-8")

        _c1, _d1, alice_token = login(ALICE)
        code1, data1, alice_ep = start_container(alice_token, gpu_count=1, image=OBS_IMAGE)
        alice_obs = str(data1.get("obs_pub_endpoint") or "")
        runner.record(1, ok=code1 == 200 and bool(alice_obs), cmd="alice start", detail=f"HTTP {code1} body={json.dumps(data1, ensure_ascii=False)}", rc=code1)

        _c2, _d2, bob_token = login(BOB)
        code2, data2, bob_ep = start_container(bob_token, gpu_count=1, image=OBS_IMAGE)
        bob_obs = str(data2.get("obs_pub_endpoint") or "")
        runner.record(2, ok=code2 == 200 and bool(bob_obs), cmd="bob start", detail=f"HTTP {code2} body={json.dumps(data2, ensure_ascii=False)}", rc=code2)

        runner.record(3, ok=alice_obs != bob_obs and bool(alice_obs) and bool(bob_obs), cmd="compare obs_pub_endpoint", detail=f"alice={alice_obs} bob={bob_obs}", rc=0 if alice_obs != bob_obs else 1)

        alice_run = _sub_and_maybe_start(alice_ep, alice_obs, ALICE_REL)
        bob_idle = _sub_and_maybe_start("", bob_obs, "", timeout_ms=3000)
        runner.record(
            4,
            ok=isinstance(alice_run.get("frame"), list) and len(alice_run.get("frame") or []) > 0 and not (bob_idle.get("frame") or []),
            cmd="alice train 时对比 alice/bob SUB",
            detail=f"alice_frame={len(alice_run.get('frame') or [])>0} bob_frame={len(bob_idle.get('frame') or [])>0}",
            rc=0,
        )

        bob_run = _sub_and_maybe_start(bob_ep, bob_obs, BOB_REL)
        alice_idle = _sub_and_maybe_start("", alice_obs, "", timeout_ms=3000)
        runner.record(
            5,
            ok=isinstance(bob_run.get("frame"), list) and len(bob_run.get("frame") or []) > 0 and not (alice_idle.get("frame") or []),
            cmd="bob train 时对比 bob/alice SUB",
            detail=f"bob_frame={len(bob_run.get('frame') or [])>0} alice_frame={len(alice_idle.get('frame') or [])>0}",
            rc=0,
        )

        code6a, body6a = stop_container(alice_token)
        code6b, body6b = stop_container(bob_token)
        runner.record(
            6,
            ok=code6a == 200 and code6b == 200 and "stopped" in body6a and "stopped" in body6b,
            cmd="stop alice/bob containers",
            detail=f"alice={code6a}:{body6a} bob={code6b}:{body6b}",
            rc=0 if code6a == 200 and code6b == 200 else 1,
        )
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        if alice_token:
            stop_container(alice_token)
        if bob_token:
            stop_container(bob_token)
        force_rm("runner-alice", "runner-bob")
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
