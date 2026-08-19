# I-01 alice 登录到 GPU 训练再停干净

## 测什么

客户端只走 HTTP：login → 核对 NFS → `POST /containers/start` → 打 `server_b_endpoint` 跑短训 → logs/status → NFS 上看到产物 → `POST /containers/stop`。全程不手工 `docker run`。

## 依赖什么

- **依赖**：单元 T-NFS-02、T-A-02、T-A-10、T-B-04、T-E2E-01 已绿灯；镜像 `rsl_rl_isrc:v3-B`；`/mnt/nfs/alice/jobs/train.py` 存在。
- **不依赖**：bob、双卡、G1 DDP。

## 前置条件

- Server A 按 [PLAN.md](../PLAN.md) 常驻 `http://10.213.35.42:8000`，`SERVER_A_DOCKER_ENABLED=true`。
- 本机已挂 `/mnt/nfs/alice`（源为 115）。
- 当前 `docker ps` 无 `runner-alice`。
- 至少 1 张 GPU。

共用变量（后续步骤沿用）：

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | A 探活 | `curl -sS http://10.213.35.42:8000/health` | HTTP 200；`{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 2 | 登录 | `curl -sS -X POST http://10.213.35.42:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | HTTP 200；`nfs_host=10.250.30.115`；`nfs_export_path` 含 alice；token 非空 | PASS；HTTP 200 nfs_host=10.250.30.115 export=/mnt/dockerContainer/nfs/alice token_len=147 |
| 3 | 核对本机 NFS | `findmnt /mnt/nfs/alice` | 源为 `10.250.30.115:/mnt/dockerContainer/nfs/alice` | PASS；退出码 0；输出：TARGET SOURCE FSTYPE OPTIONS /mnt/nfs/alice 10.250.30.115:/mnt/dockerContainer/nfs/alice nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=10.213.35.42,local_lock=none,addr=10.250.30.115 |
| 4 | start 容器 | `curl -sS -X POST http://10.213.35.42:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":1}'` | HTTP 200；`container_name=runner-alice`；`container_status=running`；`nfs_mount_path=/workspace`；`server_b_endpoint` 形如 `10.213.35.42:31xxx` | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={"server_b_endpoint": "10.213.35.42:31000", "obs_pub_endpoint": "10.213.35.42:32000", "container_status": "running", "container_name": "runner-alice", "nfs_mount_path": "/workspace"} |
| 5 | 客户端打 B 健康 | `curl -sS http://$SERVER_B/health`（`$SERVER_B` 取上一步 endpoint） | HTTP 200；`{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 6 | start 短训 | `curl -sS -X POST http://$SERVER_B/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","3"]}'` | HTTP 202；`status=running`；返回 `task_id` | PASS；HTTP 202 body={'task_id': 't-1', 'status': 'running', 'started_at': '2026-08-18T11:00:55.383624+00:00'} |
| 7 | 轮询 status | `curl -sS http://$SERVER_B/tasks/$TID/status`（可间隔 1s 直到终态） | 最终 `status=succeeded`；`exit_code=0` | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T11:00:55.383624+00:00', 'finished_at': '2026-08-18T11:00:59.628716+00:00'} |
| 8 | 拉 logs | `curl -sS http://$SERVER_B/tasks/$TID/logs` | HTTP 200；正文非空 | PASS；rank=0 local_rank=0 device=cuda:0 torch=2.11.0+cu128 cuda=True nproc=1 epoch=1/3 loss=1.208100 epoch=2/3 loss=0.775710 epoch=3/3 loss=1.206483 wrote /workspace/jobs/last_run.txt |
| 9 | NFS 产物 | `ls -l /mnt/nfs/alice/jobs/last_run.txt`；可选在 115 上 `cat /mnt/dockerContainer/nfs/alice/jobs/last_run.txt` | 本机文件存在；若查 115 则内容一致 | PASS；本机 rc=0 -rw-r--r-- 1 root root 102 Aug 18 19:00 /mnt/nfs/alice/jobs/last_run.txt；115 rc=0 finished_at=2026-08-18T11:00:58.790002+00:00 device=cuda:0 torch=2.11.0+cu128 loss=1.2064834833145142 |
| 10 | 停容器 | `curl -sS -X POST http://10.213.35.42:8000/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`{"status":"stopped"}` | PASS；HTTP 200 body={"status":"stopped"} |
| 11 | 无残留 | `sg docker -c 'docker ps -a --filter name=runner-alice --format "{{.Names}} {{.Status}}"'` | 无 `runner-alice`，或至少不在 Up | PASS；无 runner-alice |

## 通过标准

登录到停容器一次走通；产物写回 NFS；无需手工 `docker run`。
