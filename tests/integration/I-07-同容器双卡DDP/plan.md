# I-07 同容器双卡 G1 DDP

## 测什么

Server A `gpu_count:2` 拉起 `runner-alice` 后，**同一只容器内**跑与单元 T-F-02 相同的 2 卡 G1 DDP smoke。

G1 脚本在镜像 `/opt/rsl_rl_isrc/...`，不在 NFS `/workspace`。Server B 路径守卫会拒绝对路径（见 I-05 步骤 3）。因此本项 DDP **不走** `POST /tasks/start`，而用 `docker exec` 在平台拉起的容器里跑 `torchrun`（与单元 T-E2E-02 一致）。

若要把 DDP 纳入客户端任务 API：须先把脚本拷到 `/mnt/nfs/alice/` 再用相对 `script_path`。那是后续增强，不作为本项通过条件。

## 依赖什么

- **依赖**：I-01；单元 T-F-02、T-E2E-02 已绿灯；宿主机至少 2 张 GPU。
- **不依赖**：ZMQ 观测服务（继续 `--no-zmq-obs`）。

## 前置条件

- A 常驻。
- 镜像 `rsl_rl_isrc:v3-B` 内有 `/opt/rsl_rl_isrc`。
- 当前 `docker run`（经 A）**未**加 `--shm-size` / `--ipc=host`。若 NCCL hang，记到真实结果，并与 T-F-02（带 shm）对照，不要先改镜像。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start 申请 2 GPU | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":2}'` | HTTP 200；`runner-alice` running | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 2 | 容器内可见 GPU 数 | `sg docker -c 'docker exec runner-alice python3 -c "import torch;print(torch.cuda.device_count())"'` | 输出 `2` | PASS；退出码 0；输出：2 |
| 3 | B 仍在（ENTRYPOINT 未被替换） | `curl -sS http://$EP/health` | HTTP 200 | PASS；HTTP 200 body={"status":"ok"} |
| 4 | exec 跑 DDP smoke | `sg docker -c 'docker exec -w /opt/rsl_rl_isrc runner-alice torchrun --standalone --nnodes=1 --nproc_per_node=2 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 16 --max-iterations 3 --no-zmq-obs'` | 退出码 0；日志含 world_size=2、3 个 iteration；无 NCCL 崩溃 | PASS；退出码 0；输出：[rank0] 未显式指定 --obs-server-host，自动推断为 172.17.0.9 ActorCriticRecurrent.__init__ got unexpected arguments, which will be ignored: dict_keys(['policy_class_name']) Actor MLP: Sequential( (0): Linear(in_features=128, out_features=512, bias=True) (1): ELU(alpha=1.0) (2): Linear(in_features=512, out_features=256, bias=True) (3): ELU(alpha=1.0) (4): Linear(in_feat… |
| 5 | 确认 B 仍可打 | `curl -sS http://$EP/health` | 仍 200（exec 训练不应打死 Server B） | PASS；HTTP 200 body={"status":"ok"} |
| 6 | 停容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；无 `runner-alice` | PASS；HTTP 200 body={"status":"stopped"} docker=无 |

## 通过标准

平台拉起的同一只 `v3-B` 容器内 2 卡 DDP 跑完，且 Server B 仍健康。不手工 `docker run` 起训练容器。
