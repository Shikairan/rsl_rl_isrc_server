#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from common import CaseRunner, docker_cmd, run_cmd

OBS_IMAGE = "rsl_rl_isrc:v3-C"


def main() -> int:
    runner = CaseRunner("T-OBS-06", Path(__file__).resolve().parent)
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
        runner.record_cmd(1, p, p.returncode == 0)

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
        runner.record_cmd(2, p, p.returncode == 0 and "===TRAIN===" in p.stdout and p.stdout.strip().startswith("["))
    except Exception as exc:  # noqa: BLE001
        runner.record(99, ok=False, cmd="(exception)", detail=f"未捕获异常：{exc}", rc=1)
    finally:
        p = docker_cmd(["stop", "obs-train"], timeout=20)
        runner.record_cmd(3, p, p.returncode == 0)
        docker_cmd(["rm", "-f", "obs-train"])
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
