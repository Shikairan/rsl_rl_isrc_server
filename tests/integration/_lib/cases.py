#!/usr/bin/env python3
"""Integration case implementations. Each folder's run.py calls execute()."""

from __future__ import annotations

import json
import time
from pathlib import Path

from common import (
    A_BASE,
    ALICE,
    ALICE_EXPORT,
    ALICE_MNT,
    BOB,
    BOB_MNT,
    NFS_HOST,
    SB_IMAGE,
    CaseRunner,
    b_url,
    current_container,
    docker_cmd,
    docker_ps_name,
    ensure_live_a,
    force_rm,
    http,
    login,
    loads,
    norm_uuid,
    one_line,
    parse_nvidia_uuid_map,
    parse_smi,
    poll_task,
    remount_alice,
    remount_bob,
    run_cmd,
    runner_absent_or_down,
    ssh_nfs,
    start_container,
    start_task,
    stop_container,
    sudo_cmd,
    wait_b_health,
)

G1_DDP4_PY = '''"""I-08: 经 Server B 启动；只使用宿主机 GPU 4,5,6,7；WORLD_SIZE=4。"""
from __future__ import annotations

import os
import runpy
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "4,5,6,7"

import torch  # noqa: E402

rank = os.environ.get("RANK", "?")
world = os.environ.get("WORLD_SIZE", "?")
print(
    f"I-08 rank={rank} WORLD_SIZE={world} "
    f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')} "
    f"device_count={torch.cuda.device_count()}",
    flush=True,
)
if torch.cuda.is_available():
    print(f"I-08 cuda:0 uuid={torch.cuda.get_device_properties(0).uuid}", flush=True)

os.chdir("/opt/rsl_rl_isrc")
ok = False
try:
    runpy.run_path(
        "/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
        run_name="__main__",
    )
    ok = True
except SystemExit as exc:
    ok = exc.code in (0, None)

if ok and rank in ("0", "?"):
    out = Path("/workspace/jobs/last_ddp4.txt")
    out.write_text(
        f"world_size={world}\\nvisible=4,5,6,7\\nexit=ok\\n",
        encoding="utf-8",
    )
    print(f"wrote {out}", flush=True)
'''


def execute(case_id: str, case_dir: Path) -> int:
    runner = CaseRunner(case_id, case_dir)
    fn = CASES[case_id]
    try:
        fn(runner)
    except Exception as exc:  # noqa: BLE001
        n = len(runner.steps) + 1
        runner.record(n, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}")
    return runner.finish()


def _setup_alice(*, gpu_count: int) -> tuple[str, str, dict]:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    code, data, token = login(ALICE)
    if code != 200 or not token:
        return token, "", data
    _c, body, ep = start_container(token, gpu_count=gpu_count)
    return token, ep, body


def i01(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    token = ""
    ep = ""
    tid = ""
    try:
        code, body = http("GET", f"{A_BASE}/health", timeout=5)
        r.record(
            1,
            ok=code == 200 and "ok" in body,
            cmd=f"GET {A_BASE}/health",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        code, data, token = login(ALICE)
        r.record(
            2,
            ok=code == 200 and data.get("nfs_host") == NFS_HOST and "alice" in str(data.get("nfs_export_path") or "") and bool(token),
            cmd="POST /login alice",
            detail=f"HTTP {code} nfs_host={data.get('nfs_host')} export={data.get('nfs_export_path')} token_len={len(token)}",
            rc=code,
        )
        p = run_cmd(["findmnt", ALICE_MNT])
        src_ok = ALICE_EXPORT in p.stdout.replace("\\040", " ")
        r.record_cmd(3, p, p.returncode == 0 and src_ok)
        code4, data4, ep = start_container(token, gpu_count=1)
        r.record(
            4,
            ok=code4 == 200
            and data4.get("container_name") == "runner-alice"
            and data4.get("container_status") == "running"
            and data4.get("nfs_mount_path") == "/workspace"
            and bool(ep)
            and ep.startswith(f"10.213.35.42:31"),
            cmd=f"POST /containers/start {SB_IMAGE} gpu_count=1",
            detail=f"HTTP {code4} endpoint={ep} body={json.dumps(data4, ensure_ascii=False)[:400]}",
            rc=code4,
        )
        hc, hb = wait_b_health(ep) if ep else (0, "无 endpoint")
        r.record(5, ok=hc == 200 and "ok" in hb, cmd=f"GET http://{ep}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        code6, data6 = (
            start_task(
                ep,
                {
                    "script_path": "jobs/train.py",
                    "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                    "script_args": ["--epochs", "3"],
                },
            )
            if ep
            else (0, {"error": "无 endpoint"})
        )
        tid = str(data6.get("task_id") or "")
        r.record(
            6,
            ok=code6 == 202 and data6.get("status") == "running" and bool(tid),
            cmd="POST $SERVER_B/tasks/start jobs/train.py",
            detail=f"HTTP {code6} body={data6}",
            rc=code6,
        )
        last, logs = poll_task(ep, tid, timeout=90) if ep and tid else ({}, "")
        r.record(
            7,
            ok=last.get("status") == "succeeded" and last.get("exit_code") == 0,
            cmd=f"GET $SERVER_B/tasks/{tid}/status",
            detail=str(last),
            rc=0 if last.get("status") == "succeeded" else 1,
        )
        r.record(
            8,
            ok=bool(logs.strip()),
            cmd=f"GET $SERVER_B/tasks/{tid}/logs（运行中采集，结束后 B 会释放日志）",
            detail=one_line(logs, 360) or "empty",
            rc=0 if logs.strip() else 1,
        )
        local = run_cmd(["ls", "-l", f"{ALICE_MNT}/jobs/last_run.txt"])
        remote = ssh_nfs("cat /mnt/dockerContainer/nfs/alice/jobs/last_run.txt")
        local_ok = local.returncode == 0
        remote_ok = remote.returncode != 0 or bool(remote.stdout.strip())
        r.record(
            9,
            ok=local_ok and remote_ok,
            cmd="ls last_run.txt；可选 115 cat",
            detail=f"本机 rc={local.returncode} {one_line(local.stdout, 120)}；115 rc={remote.returncode} {one_line(remote.stdout, 160)}",
            rc=local.returncode,
        )
        code10, body10 = stop_container(token) if token else (0, "无 token")
        r.record(
            10,
            ok=code10 == 200 and "stopped" in body10,
            cmd="POST /containers/stop",
            detail=f"HTTP {code10} body={body10}",
            rc=code10,
        )
        leftover = docker_ps_name("runner-alice")
        r.record(
            11,
            ok=runner_absent_or_down("runner-alice"),
            cmd="docker ps -a --filter name=runner-alice",
            detail=leftover or "无 runner-alice",
            rc=0,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i02(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    token = ""
    try:
        _c, _d, token = login(ALICE)
        code1, data1, ep1 = start_container(token, gpu_count=1)
        r.record(
            1,
            ok=code1 == 200 and bool(ep1) and data1.get("container_name") == "runner-alice",
            cmd="POST /containers/start #1",
            detail=f"HTTP {code1} endpoint={ep1} body={data1}",
            rc=code1,
        )
        code2, data2, ep2 = start_container(token, gpu_count=1)
        r.record(
            2,
            ok=code2 == 200 and ep2 == ep1 and data2.get("container_name") == "runner-alice",
            cmd="POST /containers/start #2 幂等",
            detail=f"HTTP {code2} ep1={ep1} ep2={ep2} body={data2}",
            rc=code2,
        )
        cc, cb = current_container(token)
        cur = loads(cb)
        r.record(
            3,
            ok=cc == 200 and cur.get("server_b_endpoint") == ep1 and cur.get("container_status") == "running",
            cmd="GET /containers/current",
            detail=f"HTTP {cc} body={cb}",
            rc=cc,
        )
        hc, hb = wait_b_health(ep1) if ep1 else (0, "无 endpoint")
        r.record(4, ok=hc == 200, cmd=f"GET http://{ep1}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        code5, body5 = stop_container(token)
        r.record(5, ok=code5 == 200 and "stopped" in body5, cmd="POST /containers/stop", detail=f"HTTP {code5} body={body5}", rc=code5)
        code6, data6, ep6 = start_container(token, gpu_count=1)
        hc6, hb6 = wait_b_health(ep6) if ep6 else (0, "无 endpoint")
        r.record(
            6,
            ok=code6 == 200 and bool(ep6) and hc6 == 200,
            cmd="stop 后再 start",
            detail=f"HTTP {code6} endpoint={ep6} health={hc6} {hb6}",
            rc=code6,
        )
        code7, body7 = stop_container(token)
        leftover = docker_ps_name("runner-alice")
        r.record(
            7,
            ok=code7 == 200 and runner_absent_or_down("runner-alice"),
            cmd="POST /containers/stop 收尾",
            detail=f"HTTP {code7} body={body7}；docker={leftover or '无'}",
            rc=code7,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i03(r: CaseRunner) -> None:
    token, ep, _start = _setup_alice(gpu_count=1)
    try:
        if not ep:
            for n in range(1, 6):
                r.record(n, ok=False, cmd="前置 start runner-alice", detail="未能 start，后续步骤跳过", rc=1)
            return
        code1, data1 = start_task(
            ep,
            {
                "script_path": "jobs/train.py",
                "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                "script_args": ["--epochs", "999"],
            },
        )
        tid = str(data1.get("task_id") or "")
        r.record(
            1,
            ok=code1 == 202 and data1.get("status") == "running" and bool(tid),
            cmd="POST /tasks/start epochs=999",
            detail=f"HTTP {code1} body={data1}",
            rc=code1,
        )
        code2, body2 = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={"script_path": "jobs/train.py", "torchrun_args": ["--standalone"], "script_args": []},
            timeout=15,
        )
        r.record(
            2,
            ok=code2 == 409 and "already running" in body2,
            cmd="POST /tasks/start 第二次",
            detail=f"HTTP {code2} body={body2}",
            rc=code2,
        )
        code3, body3 = http("POST", b_url(ep, f"/tasks/{tid}/stop"), timeout=30) if tid else (0, "无 task_id")
        r.record(3, ok=code3 == 200 and "stopped" in body3, cmd=f"POST /tasks/{tid}/stop", detail=f"HTTP {code3} body={body3}", rc=code3)
        time.sleep(0.5)
        code4, data4 = start_task(
            ep,
            {
                "script_path": "jobs/train.py",
                "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                "script_args": ["--epochs", "3"],
            },
        )
        tid2 = str(data4.get("task_id") or "")
        last, _logs = poll_task(ep, tid2, timeout=90) if tid2 else ({}, "")
        r.record(
            4,
            ok=code4 == 202 and last.get("status") == "succeeded",
            cmd="POST /tasks/start 短训",
            detail=f"HTTP {code4} start={data4} status={last}",
            rc=code4,
        )
        code5, body5 = stop_container(token)
        r.record(5, ok=code5 == 200 and "stopped" in body5, cmd="POST /containers/stop", detail=f"HTTP {code5} body={body5}", rc=code5)
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i04(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    remount_bob()
    force_rm("runner-alice", "runner-bob")
    ta = tb = ""
    try:
        p_a = sudo_cmd(["bash", "-lc", "echo alice-only | tee /mnt/nfs/alice/alice_only.txt"])
        p_b = sudo_cmd(["bash", "-lc", "echo bob-only | tee /mnt/nfs/bob/bob_only.txt"])
        ls_a = run_cmd(["ls", ALICE_MNT])
        ls_b = run_cmd(["ls", BOB_MNT])
        r.record(
            1,
            ok="alice-only" in p_a.stdout
            and "bob-only" in p_b.stdout
            and "bob_only.txt" not in ls_a.stdout
            and "alice_only.txt" not in ls_b.stdout,
            cmd="tee alice_only.txt / bob_only.txt",
            detail=f"alice ls={one_line(ls_a.stdout, 160)}；bob ls={one_line(ls_b.stdout, 160)}",
            rc=0,
        )
        _ca, _da, ta = login(ALICE)
        _cb, _db, tb = login(BOB)
        code_a, data_a, ep_a = start_container(ta, gpu_count=0)
        r.record(
            2,
            ok=code_a == 200 and data_a.get("container_name") == "runner-alice",
            cmd="POST /containers/start alice",
            detail=f"HTTP {code_a} endpoint={ep_a} body={data_a}",
            rc=code_a,
        )
        code_b, data_b, ep_b = start_container(tb, gpu_count=0)
        r.record(
            3,
            ok=code_b == 200 and data_b.get("container_name") == "runner-bob" and ep_b != ep_a and bool(ep_b),
            cmd="POST /containers/start bob",
            detail=f"HTTP {code_b} endpoint={ep_b} (alice={ep_a}) body={data_b}",
            rc=code_b,
        )
        ls_ca = docker_cmd(["exec", "runner-alice", "ls", "/workspace"])
        iso_a = docker_cmd(["exec", "runner-alice", "bash", "-lc", "test ! -f /workspace/bob_only.txt && echo isolated"])
        r.record(
            4,
            ok="alice_only.txt" in ls_ca.stdout and "bob_only.txt" not in ls_ca.stdout and "isolated" in iso_a.stdout,
            cmd="docker exec runner-alice ls / isolation",
            detail=f"ls={one_line(ls_ca.stdout, 200)} iso={iso_a.stdout.strip()}",
            rc=iso_a.returncode,
        )
        ls_cb = docker_cmd(["exec", "runner-bob", "ls", "/workspace"])
        iso_b = docker_cmd(["exec", "runner-bob", "bash", "-lc", "test ! -f /workspace/alice_only.txt && echo isolated"])
        r.record(
            5,
            ok="bob_only.txt" in ls_cb.stdout and "alice_only.txt" not in ls_cb.stdout and "isolated" in iso_b.stdout,
            cmd="docker exec runner-bob ls / isolation",
            detail=f"ls={one_line(ls_cb.stdout, 200)} iso={iso_b.stdout.strip()}",
            rc=iso_b.returncode,
        )
        code6, body6 = stop_container(ta)
        bob_ps = docker_ps_name("runner-bob")
        r.record(
            6,
            ok=code6 == 200 and "Up" in bob_ps,
            cmd="POST /containers/stop alice token",
            detail=f"HTTP {code6} body={body6}；runner-bob={bob_ps}",
            rc=code6,
        )
        code7, body7 = stop_container(tb)
        r.record(
            7,
            ok=code7 == 200 and runner_absent_or_down("runner-alice") and runner_absent_or_down("runner-bob"),
            cmd="POST /containers/stop bob",
            detail=f"HTTP {code7} body={body7} alice={docker_ps_name('runner-alice') or '无'} bob={docker_ps_name('runner-bob') or '无'}",
            rc=code7,
        )
    finally:
        if ta:
            stop_container(ta)
        if tb:
            stop_container(tb)
        force_rm("runner-alice", "runner-bob")


def i05(r: CaseRunner) -> None:
    token, ep, _start = _setup_alice(gpu_count=0)
    try:
        if not ep:
            for n in range(1, 6):
                r.record(n, ok=False, cmd="前置 start runner-alice", detail="未能 start，后续步骤跳过", rc=1)
            return
        wait_b_health(ep)
        code1, body1 = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={"script_path": "../etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
        )
        r.record(
            1,
            ok=code1 == 400 and "escapes workspace" in body1,
            cmd="POST /tasks/start ../etc/passwd",
            detail=f"HTTP {code1} body={body1}",
            rc=code1,
        )
        code2, body2 = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={"script_path": "/etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
        )
        r.record(
            2,
            ok=code2 == 400 and "must be relative" in body2,
            cmd="POST /tasks/start /etc/passwd",
            detail=f"HTTP {code2} body={body2}",
            rc=code2,
        )
        code3, body3 = http(
            "POST",
            b_url(ep, "/tasks/start"),
            json_body={
                "script_path": "/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
                "torchrun_args": ["--standalone"],
                "script_args": [],
            },
        )
        r.record(
            3,
            ok=code3 == 400 and "must be relative" in body3,
            cmd="POST /tasks/start /opt/rsl_rl_isrc/... ",
            detail=f"HTTP {code3} body={body3}",
            rc=code3,
        )
        code4, data4 = start_task(
            ep,
            {
                "script_path": "jobs/train.py",
                "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                "script_args": ["--epochs", "3"],
            },
        )
        r.record(4, ok=code4 == 202, cmd="POST /tasks/start jobs/train.py", detail=f"HTTP {code4} body={data4}", rc=code4)
        code5, body5 = stop_container(token)
        r.record(5, ok=code5 == 200, cmd="POST /containers/stop", detail=f"HTTP {code5} body={body5}", rc=code5)
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i06(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    token = ""
    try:
        _c, _d, token = login(ALICE)
        code1, data1, ep1 = start_container(token, gpu_count=0)
        r.record(
            1,
            ok=code1 == 200 and bool(ep1),
            cmd="POST /containers/start",
            detail=f"HTTP {code1} endpoint={ep1} body={data1}",
            rc=code1,
        )
        p2 = docker_cmd(["rm", "-f", "runner-alice"])
        leftover = docker_ps_name("runner-alice")
        r.record_cmd(2, p2, p2.returncode == 0 and not leftover, note=f"docker={leftover or '无'}")
        cc, cb = current_container(token)
        r.record(
            3,
            ok=cc != 200,
            cmd="GET /containers/current",
            detail=f"HTTP {cc} body={cb}",
            rc=cc,
        )
        code4, data4, ep4 = start_container(token, gpu_count=0)
        r.record(
            4,
            ok=code4 == 200 and data4.get("container_name") == "runner-alice" and data4.get("container_status") == "running" and bool(ep4),
            cmd="POST /containers/start 重建",
            detail=f"HTTP {code4} old={ep1} new={ep4} body={data4}",
            rc=code4,
        )
        hc, hb = wait_b_health(ep4) if ep4 else (0, "无 endpoint")
        r.record(5, ok=hc == 200, cmd=f"GET http://{ep4}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        code6, body6 = stop_container(token)
        r.record(
            6,
            ok=code6 == 200 and runner_absent_or_down("runner-alice"),
            cmd="POST /containers/stop",
            detail=f"HTTP {code6} body={body6} docker={docker_ps_name('runner-alice') or '无'}",
            rc=code6,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i07(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    token = ""
    ep = ""
    try:
        _c, _d, token = login(ALICE)
        code1, data1, ep = start_container(token, gpu_count=2)
        r.record(
            1,
            ok=code1 == 200 and data1.get("container_name") == "runner-alice",
            cmd="POST /containers/start gpu_count=2",
            detail=f"HTTP {code1} endpoint={ep} body={data1}",
            rc=code1,
        )
        p2 = docker_cmd(
            ["exec", "runner-alice", "python3", "-c", "import torch;print(torch.cuda.device_count())"]
        )
        r.record_cmd(2, p2, p2.returncode == 0 and p2.stdout.strip() == "2")
        hc, hb = wait_b_health(ep) if ep else (0, "无 endpoint")
        r.record(3, ok=hc == 200, cmd=f"GET http://{ep}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        p4 = docker_cmd(
            [
                "exec",
                "-w",
                "/opt/rsl_rl_isrc",
                "runner-alice",
                "torchrun",
                "--standalone",
                "--nnodes=1",
                "--nproc_per_node=2",
                "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
                "--num-envs",
                "16",
                "--max-iterations",
                "3",
                "--no-zmq-obs",
            ],
            timeout=600,
        )
        out = p4.combined
        r.record_cmd(4, p4, p4.returncode == 0 and ("world_size=2" in out or "0/3" in out or "2/3" in out))
        hc5, hb5 = wait_b_health(ep, timeout=8) if ep else (0, "无 endpoint")
        r.record(5, ok=hc5 == 200, cmd=f"GET http://{ep}/health 训练后", detail=f"HTTP {hc5} body={hb5}", rc=hc5)
        code6, body6 = stop_container(token)
        r.record(
            6,
            ok=code6 == 200 and runner_absent_or_down("runner-alice"),
            cmd="POST /containers/stop",
            detail=f"HTTP {code6} body={body6} docker={docker_ps_name('runner-alice') or '无'}",
            rc=code6,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


def i08(r: CaseRunner) -> None:
    ensure_live_a()
    remount_alice()
    force_rm("runner-alice")
    token = ""
    ep = ""
    host_uuids: dict[int, str] = {}
    try:
        code, body = http("GET", f"{A_BASE}/health", timeout=5)
        r.record(1, ok=code == 200 and "ok" in body, cmd=f"GET {A_BASE}/health", detail=f"HTTP {code} body={body}", rc=code)
        code2, data2, token = login(ALICE)
        r.record(
            2,
            ok=code2 == 200 and data2.get("nfs_host") == NFS_HOST and bool(token),
            cmd="POST /login alice",
            detail=f"HTTP {code2} nfs_host={data2.get('nfs_host')} token_len={len(token)}",
            rc=code2,
        )
        p3 = run_cmd(["findmnt", ALICE_MNT])
        r.record_cmd(3, p3, p3.returncode == 0 and ALICE_EXPORT in p3.stdout.replace("\\040", " "))
        host_uuids = parse_nvidia_uuid_map()
        p4 = run_cmd(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv"])
        r.record_cmd(4, p4, all(i in host_uuids for i in (4, 5, 6, 7)), note=f"GPU4={host_uuids.get(4)}")
        tmp = Path("/tmp/g1_ddp4.py")
        tmp.write_text(G1_DDP4_PY, encoding="utf-8")
        cp = sudo_cmd(["cp", str(tmp), f"{ALICE_MNT}/jobs/g1_ddp4.py"])
        sudo_cmd(["chmod", "a+r", f"{ALICE_MNT}/jobs/g1_ddp4.py"])
        exists = run_cmd(["ls", f"{ALICE_MNT}/jobs/g1_ddp4.py"])
        r.record_cmd(5, exists, exists.returncode == 0 and cp.returncode == 0)
        code6, data6, ep = start_container(token, gpu_count=8)
        r.record(
            6,
            ok=code6 == 200 and data6.get("container_name") == "runner-alice" and bool(ep),
            cmd="POST /containers/start gpu_count=8",
            detail=f"HTTP {code6} endpoint={ep} body={data6}",
            rc=code6,
        )
        hc, hb = wait_b_health(ep) if ep else (0, "无 endpoint")
        r.record(7, ok=hc == 200, cmd=f"GET http://{ep}/health", detail=f"HTTP {hc} body={hb}", rc=hc)
        p8 = docker_cmd(
            [
                "exec",
                "runner-alice",
                "python3",
                "-c",
                "import torch;print(torch.cuda.device_count());print(torch.cuda.get_device_properties(4).uuid)",
            ]
        )
        lines = [ln.strip() for ln in p8.stdout.splitlines() if ln.strip()]
        count_ok = bool(lines) and lines[0] == "8"
        uuid_ok = False
        if len(lines) >= 2 and 4 in host_uuids:
            uuid_ok = norm_uuid(lines[1]) == norm_uuid(host_uuids[4]) or norm_uuid(host_uuids[4]) in norm_uuid(lines[1])
        r.record_cmd(8, p8, p8.returncode == 0 and count_ok and uuid_ok, note=f"host4={host_uuids.get(4)}")
        code9, data9 = (
            start_task(
                ep,
                {
                    "script_path": "jobs/g1_ddp4.py",
                    "torchrun_args": ["--nproc_per_node", "4", "--standalone"],
                    "script_args": ["--num-envs", "8", "--max-iterations", "3", "--no-zmq-obs"],
                },
            )
            if ep
            else (0, {"error": "无 endpoint"})
        )
        tid = str(data9.get("task_id") or "")
        r.record(
            9,
            ok=code9 == 202 and data9.get("status") == "running" and bool(tid),
            cmd="POST /tasks/start jobs/g1_ddp4.py nproc=4",
            detail=f"HTTP {code9} body={data9}",
            rc=code9,
        )
        last: dict = {}
        log_chunks: list[str] = []
        offset = 0
        smi_text = ""
        busy_ok = False
        deadline = time.time() + 600
        while ep and tid and time.time() < deadline:
            util, _mem, smi_text = parse_smi()
            if any(util.get(i, 0) > 0 for i in (4, 5, 6, 7)):
                busy_ok = True
            _cs, bs = http("GET", b_url(ep, f"/tasks/{tid}/status"), timeout=8)
            last = loads(bs) or {"raw": bs}
            lc, lb = http("GET", b_url(ep, f"/tasks/{tid}/logs?since={offset}"), timeout=8)
            if lc == 200:
                log_data = loads(lb)
                chunk = log_data.get("lines") or []
                if isinstance(chunk, list):
                    log_chunks.extend(str(x) for x in chunk)
                offset = int(log_data.get("next_offset") or offset)
            if last.get("status") in {"succeeded", "failed", "stopped"}:
                break
            time.sleep(0.4)
        logs = "\n".join(log_chunks)
        r.record(
            10,
            ok=busy_ok,
            cmd="nvidia-smi 训练中采样",
            detail=one_line(smi_text, 360) or "empty",
            rc=0 if busy_ok else 1,
        )
        r.record(
            11,
            ok=last.get("status") == "succeeded" and last.get("exit_code") == 0,
            cmd=f"GET /tasks/{tid}/status",
            detail=str(last),
            rc=0 if last.get("status") == "succeeded" else 1,
        )
        host4 = host_uuids.get(4, "")
        logs_ok = (
            bool(logs.strip())
            and "CUDA_VISIBLE_DEVICES=4,5,6,7" in logs
            and ("WORLD_SIZE=4" in logs or "world_size=4" in logs)
            and "device_count=4" in logs
            and ("iteration" in logs.lower() or "Learning" in logs)
            and (not host4 or norm_uuid(host4) in norm_uuid(logs) or "uuid=" in logs)
        )
        r.record(
            12,
            ok=logs_ok,
            cmd=f"GET /tasks/{tid}/logs（运行中采集）",
            detail=one_line(logs, 420) or "empty",
            rc=0 if logs_ok else 1,
        )
        art = run_cmd(["cat", f"{ALICE_MNT}/jobs/last_ddp4.txt"])
        r.record_cmd(
            13,
            art,
            art.returncode == 0
            and "world_size=4" in art.stdout
            and "visible=4,5,6,7" in art.stdout
            and "exit=ok" in art.stdout,
        )
        code14, body14 = stop_container(token) if token else (0, "无 token")
        r.record(
            14,
            ok=code14 == 200 and "stopped" in body14,
            cmd="POST /containers/stop",
            detail=f"HTTP {code14} body={body14}",
            rc=code14,
        )
        leftover = docker_ps_name("runner-alice")
        r.record(
            15,
            ok=runner_absent_or_down("runner-alice"),
            cmd="docker ps -a --filter name=runner-alice",
            detail=leftover or "无 runner-alice",
            rc=0,
        )
    finally:
        if token:
            stop_container(token)
        force_rm("runner-alice")


CASES = {
    "I-01": i01,
    "I-02": i02,
    "I-03": i03,
    "I-04": i04,
    "I-05": i05,
    "I-06": i06,
    "I-07": i07,
    "I-08": i08,
}
