#!/usr/bin/env python3
"""Per-case step implementations. Each independent folder's run.py calls execute()."""

from __future__ import annotations

import json
import time
from pathlib import Path

from common import (
    ALICE_EXPORT,
    ALICE_MNT,
    BOB_EXPORT,
    BOB_MNT,
    NFS_HOST,
    CaseRunner,
    REPO,
    ServerA,
    docker_cmd,
    ensure_nfs_route,
    http,
    pytest_cmd,
    remount_alice,
    remount_bob,
    run_cmd,
    ssh_nfs,
    sudo_cmd,
    wait_http,
)

SB_IMAGE = "rsl_rl_isrc:v3-C"
OBS_IMAGE = "rsl_rl_isrc:v3-C"
LEGACY_IMAGE = "rsl_rl_isrc:v3-B"


def execute(case_id: str, case_dir: Path) -> int:
    runner = CaseRunner(case_id, case_dir)
    fn = CASES[case_id]
    try:
        fn(runner)
    except Exception as exc:  # noqa: BLE001
        n = len(runner.steps) + 1
        runner.record(n, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}")
    return runner.finish()


def _has_exports(text: str) -> bool:
    return (
        "/mnt/dockerContainer/nfs" in text
        and "/mnt/dockerContainer/nfs/alice" in text
        and "/mnt/dockerContainer/nfs/bob" in text
    )


def t_nfs_01(r: CaseRunner) -> None:
    p = run_cmd(["showmount", "-e", NFS_HOST])
    r.record_cmd(1, p, p.returncode == 0 and _has_exports(p.stdout))
    p = ssh_nfs("systemctl is-active nfs-server")
    r.record_cmd(2, p, p.returncode == 0 and "active" in p.stdout)


def t_nfs_02(r: CaseRunner) -> None:
    p = run_cmd(["findmnt", ALICE_MNT])
    ok = p.returncode == 0 and ALICE_EXPORT in p.stdout.replace("\\040", " ") and "nfs" in p.stdout
    r.record_cmd(1, p, ok)
    if p.returncode != 0:
        sudo_cmd(["mkdir", "-p", ALICE_MNT])
        p2 = sudo_cmd(["mount", "-t", "nfs", "-o", "vers=4", ALICE_EXPORT, ALICE_MNT])
        r.record_cmd(2, p2, p2.returncode == 0)
    else:
        r.record(
            2,
            ok=True,
            cmd="(已挂载，跳过 mount)",
            detail="已挂载，未重复执行 mount",
            rc=0,
        )
    p = sudo_cmd(
        ["bash", "-lc", "mkdir -p /mnt/nfs/alice/jobs && echo nfs-rw-alice | tee /mnt/nfs/alice/jobs/nfs_rw.txt"]
    )
    local = run_cmd(["cat", f"{ALICE_MNT}/jobs/nfs_rw.txt"])
    r.record_cmd(
        3,
        p,
        p.returncode == 0 and "nfs-rw-alice" in (p.stdout + local.stdout),
        note=f"本机 cat={local.stdout.strip()!r}",
    )
    p = ssh_nfs("cat /mnt/dockerContainer/nfs/alice/jobs/nfs_rw.txt")
    r.record_cmd(4, p, p.returncode == 0 and p.stdout.strip() == "nfs-rw-alice")


def t_nfs_03(r: CaseRunner) -> None:
    ensure_nfs_route()
    sudo_cmd(["mkdir", "-p", BOB_MNT])
    mounted = run_cmd(["findmnt", BOB_MNT])
    if mounted.returncode != 0:
        p = sudo_cmd(["mount", "-t", "nfs", "-o", "vers=4", BOB_EXPORT, BOB_MNT])
    else:
        p = mounted
    chk = run_cmd(["findmnt", "-n", "-o", "SOURCE", BOB_MNT])
    r.record_cmd(1, p, BOB_EXPORT in chk.stdout, note=f"SOURCE={chk.stdout.strip()}")
    p = sudo_cmd(["bash", "-lc", "echo bob-only | tee /mnt/nfs/bob/bob_only.txt"])
    cat = run_cmd(["cat", f"{BOB_MNT}/bob_only.txt"])
    r.record_cmd(2, p, cat.stdout.strip() == "bob-only", note=f"cat={cat.stdout.strip()!r}")
    p = run_cmd(["bash", "-lc", "test ! -f /mnt/nfs/alice/bob_only.txt && echo isolated"])
    r.record_cmd(3, p, p.returncode == 0 and "isolated" in p.stdout)
    p = ssh_nfs(
        "ls /mnt/dockerContainer/nfs/bob/bob_only.txt; "
        "test ! -f /mnt/dockerContainer/nfs/alice/bob_only.txt && echo ok"
    )
    r.record_cmd(4, p, p.returncode == 0 and "ok" in p.stdout and "bob_only.txt" in p.stdout)


def t_nfs_04(r: CaseRunner) -> None:
    ensure_nfs_route()
    p = sudo_cmd(["umount", ALICE_MNT])
    gone = run_cmd(["findmnt", ALICE_MNT])
    r.record_cmd(1, p, p.returncode == 0 and gone.returncode != 0, note="findmnt 无挂载" if gone.returncode else gone.stdout)
    p = sudo_cmd(["mount", "-t", "nfs", "-o", "vers=4", ALICE_EXPORT, ALICE_MNT])
    r.record_cmd(2, p, p.returncode == 0)
    p = run_cmd(["findmnt", "-n", "-o", "SOURCE,FSTYPE", ALICE_MNT])
    r.record_cmd(3, p, ALICE_EXPORT in p.stdout and "nfs" in p.stdout)
    p = run_cmd(["ls", f"{ALICE_MNT}/jobs"])
    r.record_cmd(4, p, p.returncode == 0 and ("train.py" in p.stdout or "nfs_rw.txt" in p.stdout))


def t_nfs_05(r: CaseRunner) -> None:
    p = run_cmd(["showmount", "-e", NFS_HOST])
    r.record_cmd(1, p, p.returncode == 0 and _has_exports(p.stdout))
    p = ssh_nfs("sudo systemctl restart nfs-server && systemctl is-active nfs-server")
    r.record_cmd(2, p, p.returncode == 0 and "active" in p.stdout)
    time.sleep(2)
    p = run_cmd(["showmount", "-e", NFS_HOST])
    r.record_cmd(3, p, p.returncode == 0 and _has_exports(p.stdout))
    remount_alice()
    remount_bob()


def t_a_01(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_auth.py::test_health")
    r.record_cmd(1, p, p.returncode == 0)
    srv = ServerA(docker=False)
    try:
        srv.start()
        code, body = http("GET", f"{srv.base}/health")
        r.record(
            2,
            ok=code == 200 and '"ok"' in body,
            cmd=f"curl -sS {srv.base}/health",
            detail=f"HTTP {code} body={body}",
            rc=0 if code == 200 else code,
        )
    finally:
        srv.stop()


def t_a_02(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_auth.py::test_login_success")
    r.record_cmd(1, p, p.returncode == 0)
    srv = ServerA(docker=False)
    try:
        srv.start()
        code, body = http(
            "POST",
            f"{srv.base}/login",
            json_body={"username": "alice", "password": "alice-dev"},
        )
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}
        ok = (
            code == 200
            and data.get("nfs_host") == NFS_HOST
            and data.get("nfs_export_path") == "/mnt/dockerContainer/nfs/alice"
            and bool(data.get("token"))
        )
        r.record(
            2,
            ok=ok,
            cmd="POST /login alice",
            detail=(
                f"HTTP {code} nfs_host={data.get('nfs_host')} "
                f"nfs_export_path={data.get('nfs_export_path')} "
                f"token={'有' if data.get('token') else '无'} expires_at={data.get('expires_at')}"
            ),
            rc=code,
        )
    finally:
        srv.stop()


def t_a_03(r: CaseRunner) -> None:
    srv = ServerA(docker=False)
    try:
        srv.start()
        code, body = http(
            "POST",
            f"{srv.base}/login",
            json_body={"username": "alice", "password": "nope"},
        )
        r.record(
            1,
            ok=code == 401,
            cmd="POST /login wrong password",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        code, body = http(
            "POST",
            f"{srv.base}/login",
            json_body={"username": "carol", "password": "x"},
        )
        r.record(
            2,
            ok=code == 401,
            cmd="POST /login unknown user",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
    finally:
        srv.stop()
    p = pytest_cmd(
        "tests/test_auth.py::test_login_wrong_password",
        "tests/test_auth.py::test_login_unknown_user",
    )
    r.record_cmd(3, p, p.returncode == 0)


def t_a_04(r: CaseRunner) -> None:
    srv = ServerA(docker=False)
    try:
        srv.start()
        code, body = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": "example:latest", "gpu_count": 0},
        )
        r.record(
            1,
            ok=code == 401,
            cmd="POST /containers/start 无 token",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
    finally:
        srv.stop()
    p = pytest_cmd("tests/test_auth.py::test_containers_disabled_without_token")
    r.record_cmd(2, p, p.returncode == 0)


def t_a_05(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_auth.py::test_containers_disabled_with_token")
    r.record_cmd(1, p, p.returncode == 0)
    srv = ServerA(docker=False)
    try:
        srv.start()
        code, body = http(
            "POST",
            f"{srv.base}/login",
            json_body={"username": "alice", "password": "alice-dev"},
        )
        token = json.loads(body).get("token") if code == 200 else ""
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": "example:latest", "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.record(
            2,
            ok=code2 == 503,
            cmd="login + POST /containers/start docker=false",
            detail=f"login HTTP {code}；start HTTP {code2} body={body2}",
            rc=code2,
        )
    finally:
        srv.stop()


def t_a_06(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_containers.py::test_start_success")
    r.record_cmd(1, p, p.returncode == 0)


def t_a_07(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_containers.py::test_start_idempotent")
    r.record_cmd(1, p, p.returncode == 0)


def t_a_08(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_containers.py::test_start_health_fail_returns_502")
    r.record_cmd(1, p, p.returncode == 0)


def t_a_09(r: CaseRunner) -> None:
    p = pytest_cmd("tests/test_containers.py::test_current_404")
    r.record_cmd(1, p, p.returncode == 0)
    p = pytest_cmd("tests/test_containers.py::test_current_running")
    r.record_cmd(2, p, p.returncode == 0)
    p = pytest_cmd("tests/test_containers.py::test_stop_404")
    r.record_cmd(3, p, p.returncode == 0)
    p = pytest_cmd("tests/test_containers.py::test_stop_success")
    r.record_cmd(4, p, p.returncode == 0)


def t_a_10(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "runner-alice"])
    srv = ServerA(docker=True)
    try:
        srv.start()
        code, body = http(
            "POST",
            f"{srv.base}/login",
            json_body={"username": "alice", "password": "alice-dev"},
        )
        token = ""
        try:
            token = json.loads(body).get("token") or ""
        except json.JSONDecodeError:
            token = ""
        r.record(
            1,
            ok=bool(token),
            cmd="POST /login",
            detail=f"HTTP {code} token_len={len(token)}",
            rc=code,
        )
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": SB_IMAGE, "gpu_count": 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        ep = ""
        try:
            ep = json.loads(body2).get("server_b_endpoint") or ""
        except json.JSONDecodeError:
            pass
        r.record(
            2,
            ok=code2 == 200 and bool(ep),
            cmd=f"POST /containers/start image={SB_IMAGE} gpu_count=0",
            detail=f"HTTP {code2} endpoint={ep} body={body2[:400]}",
            rc=code2,
        )
        if code2 == 200 and ep:
            code3, body3 = http("GET", f"http://{ep}/health")
            r.record(
                3,
                ok=code3 == 200 and "ok" in body3,
                cmd=f"GET http://{ep}/health",
                detail=f"HTTP {code3} body={body3}",
                rc=code3,
            )
        else:
            r.record(
                3,
                ok=False,
                cmd="GET server_b /health",
                detail=f"无 endpoint；上一步 HTTP {code2}",
                rc=code2,
            )
        code_c, body_c = http(
            "GET",
            f"{srv.base}/containers/current",
            headers={"Authorization": f"Bearer {token}"},
        )
        code_s, body_s = http(
            "POST",
            f"{srv.base}/containers/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        ps = docker_cmd(["ps", "-a", "--filter", "name=runner-alice", "--format", "{{.Names}} {{.Status}}"])
        r.record(
            4,
            ok=code_c == 200 and code_s == 200 and "stopped" in body_s and "runner-alice" not in (ps.stdout or ""),
            cmd="GET /containers/current ; POST /containers/stop ; docker ps",
            detail=f"current HTTP {code_c} {body_c[:200]}；stop HTTP {code_s} {body_s[:200]}；docker={ps.stdout.strip() or '无 runner-alice'}",
            rc=code_s,
        )
    finally:
        srv.stop()
        docker_cmd(["rm", "-f", "runner-alice"])


def t_d_01(r: CaseRunner) -> None:
    remount_alice()
    p = run_cmd(["ls", "-l", f"{ALICE_MNT}/jobs/train.py"])
    r.record_cmd(1, p, p.returncode == 0)
    p = docker_cmd(
        [
            "run",
            "--rm",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime",
            "ls",
            "-l",
            "/workspace/jobs/train.py",
        ],
        timeout=180,
    )
    r.record_cmd(2, p, p.returncode == 0 and "train.py" in p.combined)


def t_d_02(r: CaseRunner) -> None:
    remount_alice()
    p = docker_cmd(
        [
            "run",
            "--rm",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime",
            "bash",
            "-lc",
            "echo from-container > /workspace/jobs/from_container.txt",
        ],
        timeout=180,
    )
    r.record_cmd(1, p, p.returncode == 0)
    p = run_cmd(["cat", f"{ALICE_MNT}/jobs/from_container.txt"])
    r.record_cmd(2, p, p.stdout.strip() == "from-container")
    p = ssh_nfs("cat /mnt/dockerContainer/nfs/alice/jobs/from_container.txt")
    r.record_cmd(3, p, p.stdout.strip() == "from-container")


def t_d_03(r: CaseRunner) -> None:
    remount_alice()
    p = docker_cmd(
        [
            "run",
            "--rm",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime",
            "bash",
            "-lc",
            "ls /workspace; test ! -f /workspace/bob_only.txt && echo isolated",
        ],
        timeout=180,
    )
    before, _, _after = p.combined.partition("isolated")
    r.record_cmd(1, p, p.returncode == 0 and "isolated" in p.combined and "bob_only.txt" not in before)


def t_e_01(r: CaseRunner) -> None:
    remount_alice()
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--name",
            "runner-alice-old",
            "--gpus",
            "1",
            "--cpus",
            "4",
            "--memory",
            "8g",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "local/torchrun:0.01",
            "torchrun",
            "--nproc_per_node=1",
            "--standalone",
            "/workspace/jobs/train.py",
            "--epochs",
            "3",
        ],
        timeout=300,
    )
    r.record_cmd(1, p, p.returncode == 0)
    p = run_cmd(["cat", f"{ALICE_MNT}/jobs/last_run.txt"])
    txt = p.stdout
    r.record_cmd(2, p, "2.4.1" in txt and "device=" in txt and "loss=" in txt)


def t_e_02(r: CaseRunner) -> None:
    remount_alice()
    p = docker_cmd(["images", "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime", "--format", "{{.Repository}}:{{.Tag}}"])
    r.record_cmd(1, p, "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime" in p.stdout)
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "1",
            "--cpus",
            "4",
            "--memory",
            "8g",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime",
            "torchrun",
            "--nproc_per_node=1",
            "--standalone",
            "/workspace/jobs/train.py",
            "--epochs",
            "3",
        ],
        timeout=300,
    )
    ok = p.returncode == 0 and "cuda:0" in p.combined and "2.11.0" in p.combined
    r.record_cmd(2, p, ok)
    p = run_cmd(["cat", f"{ALICE_MNT}/jobs/last_run.txt"])
    r.record_cmd(3, p, "device=cuda:0" in p.stdout and "2.11.0" in p.stdout)


def t_e_03(r: CaseRunner) -> None:
    remount_alice()
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "1",
            "--cpus",
            "4",
            "--memory",
            "8g",
            "-v",
            f"{ALICE_MNT}:/workspace",
            "rsl_rl_isrc:v3",
            "torchrun",
            "--nproc_per_node=1",
            "--standalone",
            "/workspace/jobs/train.py",
            "--epochs",
            "3",
        ],
        timeout=300,
    )
    r.record_cmd(1, p, p.returncode == 0 and "cuda:0" in p.combined)
    p = run_cmd(["cat", f"{ALICE_MNT}/jobs/last_run.txt"])
    r.record_cmd(2, p, "device=cuda:0" in p.stdout and "2.11.0" in p.stdout)


def t_f_01(r: CaseRunner) -> None:
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "1",
            "rsl_rl_isrc:v3",
            "python",
            "-c",
            "import rsl_rl_isrc, torch, mujoco; print(rsl_rl_isrc.__file__); print(torch.__version__, torch.cuda.is_available()); print(mujoco.__version__)",
        ],
        timeout=180,
    )
    out = p.combined
    ok = (
        p.returncode == 0
        and "rsl_rl_isrc" in out
        and "2.11.0" in out
        and "True" in out
        and "3.11" in out
    )
    r.record_cmd(1, p, ok)


def t_f_02(r: CaseRunner) -> None:
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "2",
            "--shm-size=16g",
            "--ipc=host",
            "-w",
            "/opt/rsl_rl_isrc",
            "rsl_rl_isrc:v3",
            "torchrun",
            "--standalone",
            "--nnodes=1",
            "--nproc_per_node=2",
            "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
            "--num-envs",
            "16",
            "--max-iterations",
            "2",
            "--no-zmq-obs",
        ],
        timeout=600,
    )
    out = p.combined
    ok = (
        p.returncode == 0
        and "world_size=2" in out
        and ("iteration 0" in out.lower() or "Learning iteration 0" in out or "0/2" in out)
    )
    r.record_cmd(1, p, ok)


def t_f_03(r: CaseRunner) -> None:
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "4",
            "--shm-size=16g",
            "--ipc=host",
            "-w",
            "/opt/rsl_rl_isrc",
            "rsl_rl_isrc:v3",
            "torchrun",
            "--standalone",
            "--nnodes=1",
            "--nproc_per_node=4",
            "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
            "--num-envs",
            "8",
            "--max-iterations",
            "1",
            "--no-zmq-obs",
        ],
        timeout=600,
    )
    out = p.combined
    ok = p.returncode == 0 and ("world_size=4" in out or "WORLD_SIZE=4" in out)
    r.record_cmd(1, p, ok)


def t_f_04(r: CaseRunner) -> None:
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--gpus",
            "2",
            "--shm-size=16g",
            "--ipc=host",
            "-p",
            "15555:15555",
            "-p",
            "15556:15556",
            "-w",
            "/opt/rsl_rl_isrc",
            "rsl_rl_isrc:v3",
            "torchrun",
            "--standalone",
            "--nproc_per_node=2",
            "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
            "--num-envs",
            "8",
            "--max-iterations",
            "1",
        ],
        timeout=600,
    )
    out = p.combined
    ok = p.returncode == 0 and ("15555" in out or "ObsInstr" in out or "zmq" in out.lower())
    r.record_cmd(1, p, ok)


def _sb_cleanup(name: str = "sb-health") -> None:
    docker_cmd(["rm", "-f", name])


def _sb_up(*, name: str = "sb-health", gpus: int | None = None, mount_alice: bool = False):
    _sb_cleanup(name)
    args = ["run", "-d", "--name", name, "--rm", "-p", "18080:8080"]
    if gpus:
        args += ["--gpus", str(gpus)]
    if mount_alice:
        remount_alice()
        args += ["-v", f"{ALICE_MNT}:/workspace"]
    args.append(SB_IMAGE)
    p = docker_cmd(args, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(p.combined)
    if not wait_http("http://127.0.0.1:18080/health", timeout=25):
        raise RuntimeError("Server B /health did not become ready")
    return p


def t_b_01(r: CaseRunner) -> None:
    try:
        p = _sb_up()
        inspect = docker_cmd(["inspect", "-f", "{{.State.Status}}", "sb-health"])
        r.record_cmd(
            1,
            p,
            p.returncode == 0 and "running" in inspect.stdout,
            note=f"inspect={inspect.stdout.strip()}",
        )
        code, body = http("GET", "http://127.0.0.1:18080/health", timeout=5)
        r.record(
            2,
            ok=code == 200 and "ok" in body,
            cmd="curl -sS http://127.0.0.1:18080/health",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        p = docker_cmd(["stop", "sb-health"])
        r.record_cmd(3, p, p.returncode == 0)
    finally:
        _sb_cleanup()


def t_b_02(r: CaseRunner) -> None:
    try:
        _sb_up()
        code, body = http(
            "POST",
            "http://127.0.0.1:18080/tasks/start",
            json_body={"script_path": "../etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
            timeout=5,
        )
        r.record(
            1,
            ok=code == 400,
            cmd="POST /tasks/start script_path=../etc/passwd",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
        code, body = http(
            "POST",
            "http://127.0.0.1:18080/tasks/start",
            json_body={"script_path": "/etc/passwd", "torchrun_args": ["--standalone"], "script_args": []},
            timeout=5,
        )
        r.record(
            2,
            ok=code == 400,
            cmd="POST /tasks/start script_path=/etc/passwd",
            detail=f"HTTP {code} body={body}",
            rc=code,
        )
    finally:
        _sb_cleanup()


def t_b_03(r: CaseRunner) -> None:
    try:
        _sb_up(gpus=1, mount_alice=True)
        payload = {
            "script_path": "jobs/train.py",
            "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
            "script_args": ["--epochs", "999"],
        }
        code, body = http("POST", "http://127.0.0.1:18080/tasks/start", json_body=payload, timeout=15)
        r.record(1, ok=code == 202, cmd="POST /tasks/start 长任务", detail=f"HTTP {code} body={body}", rc=code)
        task_id = ""
        try:
            task_id = json.loads(body).get("task_id") or ""
        except json.JSONDecodeError:
            pass
        code2, body2 = http(
            "POST",
            "http://127.0.0.1:18080/tasks/start",
            json_body={"script_path": "jobs/train.py", "torchrun_args": ["--standalone"], "script_args": []},
            timeout=5,
        )
        r.record(2, ok=code2 == 409, cmd="第二次 POST /tasks/start", detail=f"HTTP {code2} body={body2}", rc=code2)
        stop_url = f"http://127.0.0.1:18080/tasks/{task_id or 'unknown'}/stop"
        code3, body3 = http("POST", stop_url, timeout=15)
        r.record(3, ok=code3 == 200 and "stopped" in body3, cmd=f"POST {stop_url}", detail=f"HTTP {code3} body={body3}", rc=code3)
    finally:
        _sb_cleanup()


def t_b_04(r: CaseRunner) -> None:
    try:
        _sb_up(gpus=1, mount_alice=True)
        code, body = http(
            "POST",
            "http://127.0.0.1:18080/tasks/start",
            json_body={
                "script_path": "jobs/train.py",
                "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                "script_args": ["--epochs", "1"],
            },
            timeout=15,
        )
        r.record(1, ok=code == 202, cmd="POST /tasks/start", detail=f"HTTP {code} body={body}", rc=code)
        task_id = "unknown"
        try:
            task_id = json.loads(body).get("task_id") or "unknown"
        except json.JSONDecodeError:
            pass
        last_status = {}
        saw_logs = False
        log_body = ""
        deadline = time.time() + 90
        while time.time() < deadline:
            code2, body2 = http("GET", f"http://127.0.0.1:18080/tasks/{task_id}/status", timeout=5)
            try:
                last_status = json.loads(body2)
            except json.JSONDecodeError:
                last_status = {"raw": body2}
            if last_status.get("status") == "running":
                code3, body3 = http("GET", f"http://127.0.0.1:18080/tasks/{task_id}/logs?since=0", timeout=5)
                if code3 == 200:
                    saw_logs = True
                    log_body = body3[:300]
            if last_status.get("status") in {"succeeded", "failed", "stopped"}:
                break
            time.sleep(0.4)
        r.record(
            2,
            ok=last_status.get("status") in {"succeeded", "failed", "stopped"} and last_status.get("exit_code") is not None,
            cmd=f"GET /tasks/{task_id}/status",
            detail=f"HTTP 轮询结果 {last_status}",
            rc=0 if last_status.get("status") else 1,
        )
        r.record(
            3,
            ok=saw_logs,
            cmd=f"GET /tasks/{task_id}/logs?since=0",
            detail=f"运行中拿到日志={saw_logs} body={log_body}",
            rc=0 if saw_logs else 1,
        )
        code4, body4 = http("GET", f"http://127.0.0.1:18080/tasks/{task_id}/logs?since=0", timeout=5)
        # 结束后日志应释放为 404；若仍 running 则 stop
        if last_status.get("status") == "running":
            code_stop, body_stop = http("POST", f"http://127.0.0.1:18080/tasks/{task_id}/stop", timeout=15)
            r.record(
                4,
                ok=code_stop == 200,
                cmd=f"POST /tasks/{task_id}/stop",
                detail=f"仍 running，stop HTTP {code_stop} {body_stop}",
                rc=code_stop,
            )
        else:
            r.record(
                4,
                ok=code4 == 404,
                cmd=f"结束后 GET /tasks/{task_id}/logs",
                detail=f"HTTP {code4} body={body4}",
                rc=code4,
            )
    finally:
        _sb_cleanup()


def t_b_05(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "sb-v3"])
    try:
        p = docker_cmd(["run", "-d", "--name", "sb-v3", "--rm", "-p", "18080:8080", SB_IMAGE], timeout=30)
        ready = wait_http("http://127.0.0.1:18080/health", timeout=25)
        r.record_cmd(1, p, p.returncode == 0 and ready, note=f"health_ready={ready}")
        code, body = http("GET", "http://127.0.0.1:18080/health", timeout=5)
        r.record(2, ok=code == 200 and "ok" in body, cmd="curl /health", detail=f"HTTP {code} body={body}", rc=code)
        p = docker_cmd(
            ["exec", "sb-v3", "bash", "-lc", 'command -v torchrun && python -c "import torch;print(torch.__version__)"'],
            timeout=30,
        )
        r.record_cmd(3, p, p.returncode == 0 and "2.11.0" in p.combined)
        p = docker_cmd(["stop", "sb-v3"])
        r.record_cmd(4, p, p.returncode == 0)
    finally:
        docker_cmd(["rm", "-f", "sb-v3"])


def t_obs_01(r: CaseRunner) -> None:
    p = run_cmd(["python3", "-m", "pytest", "-q"], cwd=REPO / "obsserver", timeout=180)
    ok = p.returncode == 0 and ("passed" in p.combined or "4 passed" in p.combined)
    r.record_cmd(1, p, ok)


def t_obs_02(r: CaseRunner) -> None:
    p = docker_cmd(["image", "inspect", OBS_IMAGE, "--format", "{{.Id}}"], timeout=30)
    r.record_cmd(1, p, p.returncode == 0 and p.stdout.strip().startswith("sha256:"))
    p = docker_cmd(
        [
            "run",
            "--rm",
            "--entrypoint",
            "python3",
            OBS_IMAGE,
            "-c",
            'import obsserver; from obsserver.transform import transform; print(transform([[1]]))',
        ],
        timeout=45,
    )
    r.record_cmd(2, p, p.returncode == 0 and "[[1]]" in p.combined)
    p = docker_cmd(["image", "inspect", OBS_IMAGE, "--format", "{{json .Config.ExposedPorts}}"], timeout=30)
    ok = p.returncode == 0 and "8080/tcp" in p.combined and "15557/tcp" in p.combined
    r.record_cmd(3, p, ok)
    p = docker_cmd(["run", "--rm", "--entrypoint", "python3", LEGACY_IMAGE, "-c", "import obsserver"], timeout=45)
    r.record_cmd(4, p, p.returncode != 0 and "ModuleNotFoundError" in p.combined)


def t_obs_03(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "obs-entry"])
    try:
        p = docker_cmd(
            ["run", "-d", "--name", "obs-entry", "--rm", "-p", "127.0.0.1:18080:8080", "-p", "127.0.0.1:15557:15557", OBS_IMAGE],
            timeout=30,
        )
        ready = wait_http("http://127.0.0.1:18080/health", timeout=25)
        r.record_cmd(1, p, p.returncode == 0 and ready, note=f"health_ready={ready}")
        code, body = http("GET", "http://127.0.0.1:18080/health", timeout=5)
        r.record(2, ok=code == 200 and "ok" in body, cmd="curl /health", detail=f"HTTP {code} body={body}", rc=code)
        p = docker_cmd(["logs", "obs-entry"], timeout=20)
        ok = p.returncode == 0 and "15558/post" in p.combined and "15557" in p.combined
        r.record_cmd(3, p, ok)
        p = run_cmd(
            [
                "python3",
                "-c",
                "import socket;s=socket.create_connection(('127.0.0.1',15557),2);s.close();print('ok')",
            ],
            timeout=10,
        )
        r.record_cmd(4, p, p.returncode == 0 and "ok" in p.stdout)
    finally:
        p = docker_cmd(["stop", "obs-entry"], timeout=20)
        r.record_cmd(5, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-entry"])


def t_obs_04(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "obs-pub"])
    try:
        p = docker_cmd(
            ["run", "-d", "--name", "obs-pub", "--rm", "-p", "127.0.0.1:18080:8080", "-p", "127.0.0.1:15557:15557", OBS_IMAGE],
            timeout=30,
        )
        ready = wait_http("http://127.0.0.1:18080/health", timeout=25)
        r.record_cmd(1, p, p.returncode == 0 and ready, note=f"health_ready={ready}")
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
        r.record_cmd(2, p, ok)
    finally:
        p = docker_cmd(["stop", "obs-pub"], timeout=20)
        r.record_cmd(3, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-pub"])


def t_obs_05(r: CaseRunner) -> None:
    p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "RSL_RL_ISRC_OBS_RELAY_URL"], timeout=30)
    r.record_cmd(1, p, p.stdout.strip() == "http://127.0.0.1:15558/post")
    p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "RSL_RL_ISRC_OBS_RELAY_TIMEOUT"], timeout=30)
    r.record_cmd(2, p, p.stdout.strip() == "0.05")
    p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", OBS_IMAGE, "OBS_ENABLE"], timeout=30)
    r.record_cmd(3, p, p.returncode == 0 and p.stdout.strip() in {"", "1"})
    p = docker_cmd(["run", "--rm", "--entrypoint", "printenv", LEGACY_IMAGE, "RSL_RL_ISRC_OBS_RELAY_URL"], timeout=30)
    r.record_cmd(4, p, p.stdout.strip() == "")


def t_obs_06(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "obs-train"])
    try:
        p = docker_cmd(
            [
                "run",
                "-d",
                "--name",
                "obs-train",
                "--gpus",
                "2",
                "--shm-size=16g",
                "--ipc=host",
                "-p",
                "127.0.0.1:15557:15557",
                OBS_IMAGE,
            ],
            timeout=45,
        )
        r.record_cmd(1, p, p.returncode == 0)
        py = (
            "import json, subprocess, zmq; "
            "ctx=zmq.Context(); s=ctx.socket(zmq.SUB); s.setsockopt(zmq.SUBSCRIBE, b''); "
            "s.setsockopt(zmq.RCVTIMEO, 60000); s.connect('tcp://127.0.0.1:15557'); "
            "proc=subprocess.Popen(['sg','docker','-c',"
            "'docker exec -w /opt/rsl_rl_isrc obs-train torchrun --standalone --nproc_per_node=2 "
            "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 8 --max-iterations 1'],"
            "stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); "
            "msg=json.loads(s.recv().decode()); out,_=proc.communicate(timeout=600); "
            "print(json.dumps(msg, ensure_ascii=False)); print('\\n===TRAIN===\\n'+out)"
        )
        p = run_cmd(["python3", "-c", py], timeout=620)
        r.record_cmd(2, p, p.returncode == 0 and "===TRAIN===" in p.stdout and p.stdout.strip().startswith("["))
    finally:
        p = docker_cmd(["stop", "obs-train"], timeout=20)
        r.record_cmd(3, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-train"])


def t_obs_07(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "runner-alice"])
    srv = ServerA(docker=True)
    try:
        srv.start()
        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        data = {}
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pass
        token = data.get("token") or ""
        r.record(
            1,
            ok=code == 200 and bool(token),
            cmd="POST /login",
            detail=f"HTTP {code} token_len={len(token)} obs_pub_endpoint={data.get('obs_pub_endpoint')}",
            rc=code,
        )
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
        r.record(
            2,
            ok=code2 == 200 and bool(data2.get("obs_pub_endpoint")),
            cmd=f"POST /containers/start {OBS_IMAGE}",
            detail=f"HTTP {code2} server_b={data2.get('server_b_endpoint')} obs_pub={data2.get('obs_pub_endpoint')} body={body2[:400]}",
            rc=code2,
        )
        code3, body3 = http("GET", f"{srv.base}/containers/current", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        data3 = {}
        try:
            data3 = json.loads(body3)
        except json.JSONDecodeError:
            pass
        r.record(
            3,
            ok=code3 == 200 and bool(data3.get("obs_pub_endpoint")),
            cmd="GET /containers/current",
            detail=f"HTTP {code3} obs_pub={data3.get('obs_pub_endpoint')} body={body3[:400]}",
            rc=code3,
        )
        code4, body4 = http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        r.record(4, ok=code4 == 200 and "stopped" in body4, cmd="POST /containers/stop", detail=f"HTTP {code4} body={body4}", rc=code4)
    finally:
        srv.stop()
        docker_cmd(["rm", "-f", "runner-alice"])


def t_e2e_01(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "runner-alice"])
    remount_alice()
    srv = ServerA(docker=True)
    try:
        srv.start()
        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        data = {}
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pass
        token = data.get("token") or ""
        r.record(
            1,
            ok=code == 200 and data.get("nfs_host") == NFS_HOST and bool(token),
            cmd="POST /login",
            detail=f"HTTP {code} nfs_host={data.get('nfs_host')} token_len={len(token)}",
            rc=code,
        )
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": SB_IMAGE, "gpu_count": 1},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        ep = ""
        try:
            ep = json.loads(body2).get("server_b_endpoint") or ""
        except json.JSONDecodeError:
            pass
        r.record(
            2,
            ok=code2 == 200 and bool(ep),
            cmd=f"POST /containers/start {SB_IMAGE}",
            detail=f"HTTP {code2} endpoint={ep} body={body2[:400]}",
            rc=code2,
        )
        if ep:
            code3, body3 = http(
                "POST",
                f"http://{ep}/tasks/start",
                json_body={
                    "script_path": "jobs/train.py",
                    "torchrun_args": ["--nproc_per_node", "1", "--standalone"],
                    "script_args": ["--epochs", "1"],
                },
                timeout=15,
            )
        else:
            code3, body3 = 0, "无 server_b_endpoint"
        r.record(3, ok=code3 == 202, cmd="POST $SERVER_B/tasks/start", detail=f"HTTP {code3} body={body3}", rc=code3)
        task_id = ""
        try:
            task_id = json.loads(body3).get("task_id") or ""
        except json.JSONDecodeError:
            pass
        last = {}
        deadline = time.time() + 90
        while ep and task_id and time.time() < deadline:
            cs, bs = http("GET", f"http://{ep}/tasks/{task_id}/status", timeout=5)
            try:
                last = json.loads(bs)
            except json.JSONDecodeError:
                last = {"raw": bs, "http": cs}
            if last.get("status") in {"succeeded", "failed", "stopped"}:
                break
            time.sleep(0.4)
        r.record(
            4,
            ok=last.get("status") == "succeeded" and last.get("exit_code") == 0,
            cmd=f"GET $SERVER_B/tasks/{task_id}/status",
            detail=f"{last}",
            rc=0 if last.get("status") == "succeeded" else 1,
        )
        code5, body5 = http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        r.record(5, ok=code5 == 200 and "stopped" in body5, cmd="POST /containers/stop", detail=f"HTTP {code5} body={body5}", rc=code5)
    finally:
        srv.stop()
        docker_cmd(["rm", "-f", "runner-alice"])


def t_e2e_02(r: CaseRunner) -> None:
    docker_cmd(["rm", "-f", "runner-alice"])
    remount_alice()
    srv = ServerA(docker=True)
    try:
        srv.start()
        code, body = http("POST", f"{srv.base}/login", json_body={"username": "alice", "password": "alice-dev"})
        token = ""
        try:
            token = json.loads(body).get("token") or ""
        except json.JSONDecodeError:
            pass
        code2, body2 = http(
            "POST",
            f"{srv.base}/containers/start",
            json_body={"image": SB_IMAGE, "gpu_count": 2},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        r.record(
            1,
            ok=code2 == 200,
            cmd="POST /containers/start gpu_count=2",
            detail=f"login HTTP {code}；start HTTP {code2} body={body2[:400]}",
            rc=code2,
        )
        p = docker_cmd(
            [
                "exec",
                "-w",
                "/opt/rsl_rl_isrc",
                "runner-alice",
                "torchrun",
                "--standalone",
                "--nproc_per_node=2",
                "rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
                "--num-envs",
                "16",
                "--max-iterations",
                "2",
                "--no-zmq-obs",
            ],
            timeout=600,
        )
        r.record_cmd(2, p, p.returncode == 0 and ("world_size=2" in p.combined or "0/2" in p.combined))
        code3, body3 = http("POST", f"{srv.base}/containers/stop", headers={"Authorization": f"Bearer {token}"})
        r.record(3, ok=code3 == 200 and "stopped" in body3, cmd="POST /containers/stop", detail=f"HTTP {code3} body={body3}", rc=code3)
    finally:
        srv.stop()
        docker_cmd(["rm", "-f", "runner-alice"])


CASES = {
    "T-NFS-01": t_nfs_01,
    "T-NFS-02": t_nfs_02,
    "T-NFS-03": t_nfs_03,
    "T-NFS-04": t_nfs_04,
    "T-NFS-05": t_nfs_05,
    "T-A-01": t_a_01,
    "T-A-02": t_a_02,
    "T-A-03": t_a_03,
    "T-A-04": t_a_04,
    "T-A-05": t_a_05,
    "T-A-06": t_a_06,
    "T-A-07": t_a_07,
    "T-A-08": t_a_08,
    "T-A-09": t_a_09,
    "T-A-10": t_a_10,
    "T-D-01": t_d_01,
    "T-D-02": t_d_02,
    "T-D-03": t_d_03,
    "T-E-01": t_e_01,
    "T-E-02": t_e_02,
    "T-E-03": t_e_03,
    "T-F-01": t_f_01,
    "T-F-02": t_f_02,
    "T-F-03": t_f_03,
    "T-F-04": t_f_04,
    "T-OBS-01": t_obs_01,
    "T-OBS-02": t_obs_02,
    "T-OBS-03": t_obs_03,
    "T-OBS-04": t_obs_04,
    "T-OBS-05": t_obs_05,
    "T-OBS-06": t_obs_06,
    "T-OBS-07": t_obs_07,
    "T-B-01": t_b_01,
    "T-B-02": t_b_02,
    "T-B-03": t_b_03,
    "T-B-04": t_b_04,
    "T-B-05": t_b_05,
    "T-E2E-01": t_e2e_01,
    "T-E2E-02": t_e2e_02,
}
