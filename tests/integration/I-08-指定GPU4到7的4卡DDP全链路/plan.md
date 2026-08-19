# I-08 指定 GPU 4–7 的 4 卡 DDP 全链路

## 测什么

alice 走与 I-01 相同的客户端路径（login → NFS → A start → B `/health` → `POST /tasks/start` → status/logs → NFS 产物 → A stop），但训练是 **4 进程 DDP**，只用宿主机物理卡 **4、5、6、7**。

`ddp-world-rank=4` 在本项里按 **`WORLD_SIZE=4`** 理解：`torchrun --nproc_per_node=4 --standalone`，进程 `RANK`/`LOCAL_RANK` 为 0–3，**不是** `RANK=4`。

G1 脚本在镜像 `/opt/rsl_rl_isrc/...`，不在 NFS。路径守卫拒绝对路径，因此把包装脚本放到 `/mnt/nfs/alice/jobs/g1_ddp4.py`，再经 B 用相对路径启动（这才是完整链路，不用 `docker exec` 当主路径）。

## 依赖什么

- **依赖**：I-01；单元 T-F-03（4 卡 G1 smoke 已过）；宿主机 8 张卡，其中 4–7 空闲。
- **不依赖**：bob；ZMQ（继续 `--no-zmq-obs`）。

## 前置条件

- Server A 按 [PLAN.md](../PLAN.md) 常驻 `http://10.213.35.42:8000`。
- 本机已挂 `/mnt/nfs/alice`。
- `docker ps` 无 `runner-alice`。
- `nvidia-smi -L` 能看到 GPU 4–7（现场 8× RTX 5090）。
- **卡选择缺口**：`POST /containers/start` 目前只有 `gpu_count`，没有 `gpu_ids`。`gpu_count:4` 会绑到前 4 张（通常是 0–3），**绑不到 4–7**。本项不改 A，采用：
  - start 时 `gpu_count: 8`（容器内 index 与宿主机 0–7 对齐）；
  - 包装脚本设置 `CUDA_VISIBLE_DEVICES=4,5,6,7`，进程内 `cuda:0` = 物理卡 4。
- 若执行前已给 A 加上 `gpu_ids`：步骤 6 改为 `"gpu_ids":["4","5","6","7"]`（不要同时传 count 和 device_ids），包装脚本**不要**再设 `CUDA_VISIBLE_DEVICES`。
- A 的 `docker run` **未**加 `--shm-size` / `--ipc=host`。4 卡 NCCL 若 hang，记到真实结果，对照 T-F-03（带 shm），不要先改镜像。

共用变量：

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
HOST_UUID4=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F', ' '$1==4{print $2}')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | A 探活 | `curl -sS http://10.213.35.42:8000/health` | HTTP 200；`{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 2 | 登录 | `curl -sS -X POST http://10.213.35.42:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | HTTP 200；`nfs_host=10.250.30.115`；token 非空 | PASS；HTTP 200 nfs_host=10.250.30.115 token_len=147 |
| 3 | 核对本机 NFS | `findmnt /mnt/nfs/alice` | 源为 `10.250.30.115:/mnt/dockerContainer/nfs/alice` | PASS；退出码 0；输出：TARGET SOURCE FSTYPE OPTIONS /mnt/nfs/alice 10.250.30.115:/mnt/dockerContainer/nfs/alice nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=10.213.35.42,local_lock=none,addr=10.250.30.115 |
| 4 | 记录物理卡 UUID | `nvidia-smi --query-gpu=index,uuid --format=csv` | GPU 4–7 各有 UUID；记下 GPU 4 的 UUID，后面与容器内 `cuda:0` 对照 | PASS；退出码 0；GPU4=GPU-92438bf1-5d53-fa0a-2801-81a6ea00fccd；输出：index, uuid 0, GPU-8f3532a7-6994-9d8d-7ab2-962e3e4fd2cd 1, GPU-54dacabd-569b-f97a-b07c-52917620e8fd 2, GPU-6f1ae41a-8a1b-cb4d-78e6-ee6cca10242b 3, GPU-4469f8e3-945d-5f0c-6e16-b18fd0e6c257 4, GPU-92438bf1-5d53-fa0a-2801-81a6ea00fccd 5, GPU-6e1d68b0-2ea5-1e96-6f16-d638d5341e40 6, GPU-96d0ab7b-ceec-1dec-1c0f-7adc7d1dac2b 7, GPU-a6ec4063-b604-1895-afd2-e2a9e15c… |
| 5 | 写入 NFS 包装脚本 | 见下方 `jobs/g1_ddp4.py`（`sudo tee /mnt/nfs/alice/jobs/g1_ddp4.py`） | 本机 `ls /mnt/nfs/alice/jobs/g1_ddp4.py` 存在 | PASS；退出码 0；输出：/mnt/nfs/alice/jobs/g1_ddp4.py |
| 6 | start 容器（8 卡可见） | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":8}'` | HTTP 200；`container_name=runner-alice`；`server_b_endpoint` 形如 `10.213.35.42:31xxx` | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 7 | 客户端打 B 健康 | `curl -sS http://$EP/health` | HTTP 200；`{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 8 | 容器内卡数与 UUID | `sg docker -c 'docker exec runner-alice python3 -c "import torch;print(torch.cuda.device_count());print(torch.cuda.get_device_properties(4).uuid)"'` | `device_count=8`；index 4 的 UUID 与步骤 4 的宿主机 GPU 4 一致 | PASS；退出码 0；host4=GPU-92438bf1-5d53-fa0a-2801-81a6ea00fccd；输出：8 92438bf1-5d53-fa0a-2801-81a6ea00fccd |
| 9 | start 4 卡 DDP 任务 | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/g1_ddp4.py","torchrun_args":["--nproc_per_node","4","--standalone"],"script_args":["--num-envs","8","--max-iterations","3","--no-zmq-obs"]}'` | HTTP 202；`status=running`；记下 `task_id` | PASS；HTTP 202 body={'task_id': 't-1', 'status': 'running', 'started_at': '2026-08-18T11:02:48.965295+00:00'} |
| 10 | 训练中看哪几张卡在忙 | `nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv`（任务 running 期间采一次） | GPU **4–7** 有利用率或显存占用；0–3 不应是本任务主负载 | PASS；0, 0, 25795 1, 0, 25795 2, 0, 25795 3, 0, 25795 4, 0, 15 5, 0, 15 6, 0, 15 7, 0, 15 |
| 11 | 轮询 status | `curl -sS http://$EP/tasks/$TID/status`（间隔数秒直到终态；4 卡 1 iteration 通常一两分钟内） | 最终 `status=succeeded`；`exit_code=0` | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T11:02:48.965295+00:00', 'finished_at': '2026-08-18T11:03:00.828400+00:00'} |
| 12 | 拉 logs | `curl -sS http://$EP/tasks/$TID/logs` | HTTP 200；含 `CUDA_VISIBLE_DEVICES=4,5,6,7`；`WORLD_SIZE=4` 或 `world_size=4`；`device_count=4`；`cuda:0` UUID 对上 GPU 4；有 Learning iteration；无 NCCL 崩溃 | PASS；W0818 11:02:50.064000 176 torch/distributed/run.py:851] W0818 11:02:50.064000 176 torch/distributed/run.py:851] ***************************************** W0818 11:02:50.064000 176 torch/distributed/run.py:851] Setting OMP_NUM_THREADS environment variable for each process to be 1 in default, to avoid your system being overloaded, please further tune the variable for optimal performance in your application as needed. … |
| 13 | NFS 产物 | `cat /mnt/nfs/alice/jobs/last_ddp4.txt` | 含 `world_size=4`、`visible=4,5,6,7`、`exit=ok` | PASS；退出码 0；输出：world_size=4 visible=4,5,6,7 exit=ok |
| 14 | 停容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`{"status":"stopped"}` | PASS；HTTP 200 body={"status":"stopped"} |
| 15 | 无残留 | `sg docker -c 'docker ps -a --filter name=runner-alice --format "{{.Names}} {{.Status}}"'` | 无 `runner-alice`，或至少不在 Up | PASS；无 runner-alice |

### 步骤 5 包装脚本内容

```bash
sudo tee /mnt/nfs/alice/jobs/g1_ddp4.py >/dev/null <<'PY'
"""I-08: 经 Server B 启动；只使用宿主机 GPU 4,5,6,7；WORLD_SIZE=4。"""
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
runpy.run_path(
    "/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py",
    run_name="__main__",
)

if rank in ("0", "?",):
    out = Path("/workspace/jobs/last_ddp4.txt")
    out.write_text(
        f"world_size={world}\nvisible=4,5,6,7\nexit=ok\n",
        encoding="utf-8",
    )
    print(f"wrote {out}", flush=True)
PY
```

## 通过标准

- 全程只走 HTTP（login / start / tasks / stop），不手工 `docker run` 起训练容器。
- `WORLD_SIZE=4`，4 个 DDP 进程跑完 3 个 G1 iteration，`exit_code=0`。
- 实际计算卡是物理 **4、5、6、7**（UUID + `nvidia-smi` 占用），不是 0–3。
- NFS 上能看到 `jobs/last_ddp4.txt`；A stop 后无 `runner-alice`。
