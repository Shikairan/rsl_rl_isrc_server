# 完整全链路测试

> 本目录是**一条客户端主路径从头走到尾**：登录 → 挂载 NFS → 内部检查 → 经 Server A 起容器 → 经 Server B 执行任务 → 等待结束 → 查看结果（含 obs 画面帧）并停干净。
>
> 与 `tests/units/`（一层一项）和 `tests/integration/`（拆成 I-01～I-08 / I-OBS-01～04）不同：这里不拆用例，按真实使用顺序一次验收整条链。
>
> 现场：NFS `10.250.30.115`，Server A 默认 `10.213.35.42:8017`（`INTEGRATION_A_PORT`，避免现场旧 8000 进程无 obs 字段）。账号 `alice` / `alice-dev`。镜像 `rsl_rl_isrc:v3-C`。训练：NFS 上 `jobs/complete_obs_smoke.py`（G1 1 iter，**不开** `--no-zmq-obs`）。
>
> 步骤表「真实结果」列先空着，执行后再填。禁止把手工 `docker run` 当主路径。

## 链路总览

```
客户端
  ① 登录        POST /login
                ← token、nfs_host、nfs_export_path
  ② 挂载        用登录返回的 115 路径挂到本机
  ③ 内部检查    A /health、导出、挂载源、镜像 v3-C、GPU、工作区脚本
  ④ 运行容器    POST /containers/start（v3-C，gpu_count:2）
                ← runner-alice、server_b_endpoint、obs_pub_endpoint
                再查 B /health、画面口 TCP、容器内 /workspace
  ⑤ 执行        POST {endpoint}/tasks/start  jobs/complete_obs_smoke.py
  ⑥ 等待        轮询 /tasks/{id}/status，运行中拉 logs；SUB obs_pub_endpoint 收帧
  ⑦ 查看结果    succeeded + NFS last_run.txt + complete_obs_frames.json
                POST /containers/stop，确认无残留
```

```
客户端 ──HTTP──► Server A :8000          NFS 115
                 │  login / start / stop     │
                 │  docker run runner-alice  │
                 │  -v /mnt/nfs/alice:/workspace
                 ▼
              容器 :8080（映射 31xxx）+ 画面口 :15557（映射 32xxx）
                 Server B  → torchrun jobs/complete_obs_smoke.py
                 obsserver PUB → 宿主机 SUB obs_pub_endpoint
                 产物写回 /workspace = NFS
```

## 环境与前置

| 项 | 要求 |
|----|------|
| Server A | 脚本默认拉起/复用 `http://10.213.35.42:8017`（`INTEGRATION_A_PORT`）；`docker.enabled=true` |
| NFS | 115 导出 `/mnt/dockerContainer/nfs/alice`；本机目标 `/mnt/nfs/alice` |
| 镜像 | 本地 `rsl_rl_isrc:v3-C`（ENTRYPOINT 自启 Server B `:8080` + obsserver `:15557`） |
| 脚本 | `/mnt/nfs/alice/jobs/train.py` 仍须存在（检查用）；真正开训用脚本写入 `jobs/complete_obs_smoke.py` |
| GPU | 至少 2 张（本链路 `gpu_count:2`，torchrun `--nproc_per_node=2`） |
| 残留 | `docker ps` 无 `runner-alice` |

启动 Server A（若尚未探活）：

```bash
conda activate serverA
cd /home/isrc5090/149server/serverA
export SERVER_A_DOCKER_ENABLED=true
export SERVER_A_NFS_ENABLED=false
# 需要 docker 组：newgrp docker 或 sg docker
uvicorn app.main:app --host 0.0.0.0 --port 8017
```

全程共用变量（① 登录成功后补齐 `TOKEN`，④ 成功后补齐 `EP` / `OBS_EP` / `TID`）：

```bash
A=http://10.213.35.42:8017
NFS_HOST=10.250.30.115
NFS_EXPORT=/mnt/dockerContainer/nfs/alice
MNT=/mnt/nfs/alice
```

---

## ① 登录

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1.1 | A 探活 | `curl -sS $A/health` | HTTP 200；`{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 1.2 | 错密码应失败（对照） | `curl -sS -o /tmp/c-login-bad.json -w '%{http_code}' -X POST $A/login -H 'content-type: application/json' -d '{"username":"alice","password":"wrong"}'` | HTTP 401 | PASS；HTTP 401 body={"detail":{"error":"invalid credentials"}} |
| 1.3 | 正确登录 | `curl -sS -X POST $A/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | HTTP 200；`token` 非空；`nfs_host=10.250.30.115`；`nfs_export_path` 为 `/mnt/dockerContainer/nfs/alice` | PASS；HTTP 200 nfs_host=10.250.30.115 export=/mnt/dockerContainer/nfs/alice token_len=147 |

取出 token：

```bash
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
echo "token_len=${#TOKEN}"
```

无 token 不能起容器（对照）：

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1.4 | 无 Authorization | `curl -sS -o /tmp/c-notoken.json -w '%{http_code}' -X POST $A/containers/start -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}'` | HTTP 401 | PASS；HTTP 401 body={"detail":{"error":"missing token"}} |

---

## ② 挂载

用**登录返回**的 `nfs_host` + `nfs_export_path`，不要写死别的导出。若 Clash TUN 把 115 拐到 `198.18.0.1`，先加 `ip rule add to 10.250.30.115 lookup main pref 8000`，mount 加 `clientaddr=10.213.35.42`。

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 2.1 | 115 导出列表 | `showmount -e 10.250.30.115` | 出现 `/mnt/dockerContainer/nfs`、`.../alice` | PASS；退出码 0；输出：Export list for 10.250.30.115: /mnt/dockerContainer/nfs/bob 10.0.0.0/8 /mnt/dockerContainer/nfs/alice 10.0.0.0/8 /mnt/dockerContainer/nfs 10.0.0.0/8 |
| 2.2 | 本机是否已挂 | `findmnt /mnt/nfs/alice` | 若已挂：SOURCE 为 `10.250.30.115:/mnt/dockerContainer/nfs/alice`，fstype nfs | PASS；退出码 0；输出：TARGET SOURCE FSTYPE OPTIONS /mnt/nfs/alice 10.250.30.115:/mnt/dockerContainer/nfs/alice nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=10.213.35.42,local_lock=none,addr=10.250.30.115 |
| 2.3 | 未挂则挂上 | `sudo mkdir -p /mnt/nfs/alice`；`sudo mount -t nfs -o vers=4,clientaddr=10.213.35.42 10.250.30.115:/mnt/dockerContainer/nfs/alice /mnt/nfs/alice` | `findmnt` 源仍是 115 | PASS；已挂载，未重复执行 mount |
| 2.4 | 本机可读工作区 | `ls /mnt/nfs/alice/jobs/train.py` | 文件存在 | PASS；退出码 0；输出：/mnt/nfs/alice/jobs/train.py |

---

## ③ 内部检查

在起容器之前确认控制面、存储、镜像、GPU 都就绪。失败停在这一层，不要继续 start。

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 3.1 | 本机 NFS 可写回 | `echo ping \| sudo tee /mnt/nfs/alice/jobs/complete_probe.txt`；本机 `cat /mnt/nfs/alice/jobs/complete_probe.txt` | 内容为 `ping` | PASS；退出码 0；本机 cat='ping'；输出：ping |
| 3.2 | 115 侧可见同一文件 | 115 上 `cat /mnt/dockerContainer/nfs/alice/jobs/complete_probe.txt` | 内容为 `ping` | PASS；退出码 0；输出：ping |
| 3.3 | 训练镜像在本地 | `sg docker -c 'docker image inspect rsl_rl_isrc:v3-C --format "{{.Id}} {{.Config.Entrypoint}}"'` | 镜像存在；Entrypoint 会起 Server B；ExposedPorts 含 `15557`（不要用无 obs 的 `v3-B`） | PASS；退出码 0；须为 v3-C（含 Server B + obsserver）；输出：sha256:7e3e1f8913ef8ab409ba3a4069a07b686d83394b4d1567c722074031bce7fcae ["/opt/serverB/entrypoint.sh"] {"15557/tcp":{},"8080/tcp":{}} |
| 3.4 | GPU 可见 | `nvidia-smi -L` | 至少 1 张卡 | PASS；退出码 0；输出：GPU 0: NVIDIA GeForce RTX 5090 (UUID: GPU-8f3532a7-6994-9d8d-7ab2-962e3e4fd2cd) GPU 1: NVIDIA GeForce RTX 5090 (UUID: GPU-54dacabd-569b-f97a-b07c-52917620e8fd) GPU 2: NVIDIA GeForce RTX 5090 (UUID: GPU-6f1ae41a-8a1b-cb4d-78e6-ee6cca10242b) GPU 3: NVIDIA GeForce RTX 5090 (UUID: GPU-4469f8e3-945d-5f0c-6e16-b18fd0e6c257) GPU 4: NVIDIA GeForce RTX 5090 (UUID: G… |
| 3.5 | 无残留容器 | `sg docker -c 'docker ps -a --filter name=runner-alice --format "{{.Names}} {{.Status}}"'` | 无 `runner-alice`，或先 `POST /containers/stop` | PASS；无 runner-alice |
| 3.6 | 工作区脚本 | `head -n 5 /mnt/nfs/alice/jobs/train.py` | 可读取；后续 `script_path` 用相对路径 `jobs/train.py` | PASS；退出码 0；输出：#!/usr/bin/env python3 """Tiny PyTorch job for NFS + torchrun smoke test. Uses CUDA when the installed wheel supports this GPU; otherwise CPU. local/torchrun:0.01 ships torch 2.4.1 (max sm_90) which cannot run RTX 5090 (sm_120). |

---

## ④ 运行容器

必须经 `POST /containers/start`。A 会 bind `/mnt/nfs/alice` → 容器 `/workspace`，映射 `10.213.35.42:31xxx → 8080` 与 `32xxx → 15557`，并对 B `/health` 探活，失败则 502 且 `docker rm -f`。

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 4.1 | start | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}'` | HTTP 200；`container_name=runner-alice`；`server_b_endpoint` 形如 `10.213.35.42:31xxx`；`obs_pub_endpoint` 形如 `10.213.35.42:32xxx` | PASS；HTTP 200 endpoint=10.213.35.42:31000 obs_pub=10.213.35.42:32000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 4.2 | current 与 start 一致 | `curl -sS -H "Authorization: Bearer $TOKEN" $A/containers/current` | HTTP 200；`server_b_endpoint` / `obs_pub_endpoint` / name 与 4.1 相同 | PASS；HTTP 200 body={"server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 4.3 | 幂等再 start | 命令同 4.1 | HTTP 200；**同一** `server_b_endpoint` 与 `obs_pub_endpoint` | PASS；HTTP 200 ep1=10.213.35.42:31000 ep2=10.213.35.42:31000 obs=10.213.35.42:32000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 4.4 | 宿主机看见容器 | `sg docker -c 'docker ps --filter name=runner-alice --format "{{.Names}} {{.Status}} {{.Ports}}"'` | `runner-alice` Up；`31xxx->8080/tcp` 且 `32xxx->15557/tcp` | PASS；退出码 0；输出：runner-alice Up 2 seconds 10.213.35.42:31000->8080/tcp, 10.213.35.42:32000->15557/tcp |
| 4.5 | 容器内看见 NFS | `sg docker -c 'docker exec runner-alice ls /workspace/jobs/train.py'` | 文件存在（与本机 `jobs/train.py` 同一份） | PASS；退出码 0；输出：/workspace/jobs/train.py |
| 4.6 | Server B 健康 | `curl -sS http://$EP/health`（`$EP` 取 4.1 的 endpoint） | HTTP 200；`{"status":"ok"}`。打宿主机映射端口，不要打容器内 `8080` | PASS；HTTP 200 body={"status":"ok"} |
| 4.7 | 画面口 TCP | `python3 -c "import socket;s=socket.create_connection(('10.213.35.42',32xxx),2);s.close();print('ok')"` | 打印 `ok` | PASS；退出码 0；输出：ok |

取出 endpoint：

```bash
EP=$(curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["server_b_endpoint"]);print(d["obs_pub_endpoint"], file=sys.stderr)')
echo "EP=$EP"
```

---

## ⑤ 执行

客户端把任务打到 **Server B**，不经 A。`script_path` 必须相对 `/workspace`。本链路跑 G1 1 iter **开 ZMQ obs**（不要 `--no-zmq-obs`）。

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 5.1 | 越界路径应拒绝 | `curl -sS -o /tmp/c-esc.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"../etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400；`script_path escapes workspace` | PASS；HTTP 400 body={"detail":{"error":"script_path escapes workspace"}} |
| 5.2 | 绝对路径应拒绝 | `curl -sS -o /tmp/c-abs.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"/etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400；`script_path must be relative to workspace` | PASS；HTTP 400 body={"detail":{"error":"script_path must be relative to workspace"}} |
| 5.3 | start 训练（开 obs） | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/complete_obs_smoke.py","torchrun_args":["--nproc_per_node","2","--standalone"],"script_args":[]}'` | HTTP 202；`status=running`；返回 `task_id` | PASS；HTTP 202 body={'task_id': 't-1', 'status': 'running', 'started_at': '2026-08-18T08:42:59.647863+00:00'} obs_pub=10.213.35.42:32000 |

```bash
TID=$(curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' \
  -d '{"script_path":"jobs/complete_obs_smoke.py","torchrun_args":["--nproc_per_node","2","--standalone"],"script_args":[]}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["task_id"])')
echo "TID=$TID"
```

---

## ⑥ 等待

任务结束后 Server B **会释放内存日志**。要在 **running 期间**拉 logs，不要等 succeeded 再第一次 GET logs。同时 SUB `obs_pub_endpoint` 收画面帧。

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 6.1 | 运行中拉 logs | `curl -sS "http://$EP/tasks/$TID/logs?since=0"` | HTTP 200；`lines` 非空（含 rank / iteration / cuda）。已结束后再查可能 404 `logs released` | PASS；W0818 08:43:00.767000 72 torch/distributed/run.py:851] W0818 08:43:00.767000 72 torch/distributed/run.py:851] ***************************************** W0818 08:43:00.767000 72 torch/distributed/run.py:851] Setting OMP_NUM_THREADS environment variable for each process to be 1 in default, to avoid your system being overloaded, please further tune the variabl… |
| 6.2 | 第二任务应 409 | （仍 running 时）再 POST 一次 `/tasks/start` | HTTP 409；`a task is already running` | PASS；HTTP 409 body={"detail":{"error":"a task is already running"}} |
| 6.3 | 轮询 status | `curl -sS http://$EP/tasks/$TID/status`（间隔约 1s 直到终态） | 最终 `status=succeeded`；`exit_code=0` | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T08:42:59.647863+00:00', 'finished_at': '2026-08-18T08:43:06.669554+00:00'} |
| 6.4 | SUB 画面口出帧 | 宿主机 SUB `tcp://$OBS_EP` | 至少 1 帧 JSON 数组；元素为 `[位置,姿态,关节]`；终端打印 `======== OBS 画面帧 ========` | PASS；n_frames=24 head=[[[[0.8647451400756836, 0.3887401521205902, 0.7984024286270142], [-0.015115750022232533, 0.006550956051796675, 0.00015763593546580523, 0.9998642802238464], [-0.04433643817901611, 0.09725047647953033, 0.09105551242828369, 0.31314772367477417, -0.20392243564128876, -0.021056275814771652, -0.026255184784531593, 0.08008196949958801, 0.07164422422647476, 0.04263… |

轮询示例：

```bash
while true; do
  curl -sS "http://$EP/tasks/$TID/status"
  echo
  st=$(curl -sS "http://$EP/tasks/$TID/status" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  case "$st" in succeeded|failed|stopped) break ;; esac
  sleep 1
done
```

---

## ⑦ 查看结果

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 7.1 | 终态 | `curl -sS http://$EP/tasks/$TID/status` | `succeeded`；`exit_code=0`；有 `finished_at` | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T08:42:59.647863+00:00', 'finished_at': '2026-08-18T08:43:06.669554+00:00'} |
| 7.2 | 本机 NFS 产物 | `cat /mnt/nfs/alice/jobs/last_run.txt` | 含 `device=cuda:0`、`torch=2.11.0+cu128`、`loss=` | PASS；退出码 0；输出：finished_at=complete-obs-smoke device=cuda:0 torch=2.11.0+cu128 loss=obs |
| 7.3 | 115 同一份文件 | 115 上 `cat /mnt/dockerContainer/nfs/alice/jobs/last_run.txt` | 与本机内容一致 | PASS；退出码 0；本机=finished_at=complete-obs-smoke device=cuda:0 torch=2.11.0+cu128 loss=obs；输出：finished_at=complete-obs-smoke device=cuda:0 torch=2.11.0+cu128 loss=obs |
| 7.4 | 本机 obs 帧文件 | `cat /mnt/nfs/alice/jobs/complete_obs_frames.json` | `n_frames>0`；含 `obs_pub_endpoint` 与 `frames` | PASS；退出码 0；n_frames=24 obs_pub=10.213.35.42:32000；输出：{ "obs_pub_endpoint": "10.213.35.42:32000", "n_frames": 24, "frames": [ [ [ [ 0.8647451400756836, 0.3887401521205902, 0.7984024286270142 ], [ -0.015115750022232533, 0.006550956051796675, 0.00015763593546580523, 0.9998642802238464 ], [ -0.04433643817901611, 0.09725047647953033, 0.09105551242828369, 0.31314772367477417, -0.20392243564128876, -0.02105627581477… |
| 7.5 | 停容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`{"status":"stopped"}` | PASS；HTTP 200 body={"status":"stopped"} |
| 7.6 | current 应空 | `curl -sS -o /tmp/c-cur.json -w '%{http_code}' -H "Authorization: Bearer $TOKEN" $A/containers/current` | HTTP 404；`no container` | PASS；HTTP 404 body={"detail":{"error":"no container"}} |
| 7.7 | Docker 无残留 | `sg docker -c 'docker ps -a --filter name=runner-alice --format "{{.Names}} {{.Status}}"'` | 无 `runner-alice`，或至少不在 Up | PASS；无 runner-alice |

---

## 通过标准

1. 登录拿到 115 的 NFS 地址和 JWT；错密码 / 无 token 被拒。
2. 本机挂载源就是登录返回的导出；本机写入能在 115 读到。
3. 容器只经 A start `v3-C`；B `/health` 走映射端口；`obs_pub_endpoint` 可 TCP；容器内 `/workspace` 能看见 NFS。
4. 非法 `script_path` 400；合法 obs 开训 202 → `succeeded` / `exit_code=0`。
5. 运行中能拉到 logs；并发第二任务 409。
6. SUB `obs_pub_endpoint` 至少收到 1 帧；`complete_obs_frames.json` 本机可读。
7. `last_run.txt` 本机与 115 一致；stop 后无 `runner-alice`。

## 失败归属

| 现象 | 先查 |
|------|------|
| `/login` 非 200 | A 未起 / users.yaml，不查 Docker |
| 挂载 EPERM / stale | Clash 路由、`umount -l` 再挂、`clientaddr=10.213.35.42` |
| start 502 | 镜像不是 `v3-C`，或 8080 `/health` 没起来 |
| 打不通 endpoint | 用 `10.213.35.42:31xxx`，不要打容器内 8080 |
| 有 endpoint 但无画面 | 脚本带了 `--no-zmq-obs`，或没 SUB `obs_pub_endpoint` |
| 任务 400 | `script_path` 必须相对 `/workspace` |
| 任务 409 | 已有 running |
| succeeded 但本机无 `last_run.txt` | bind 不是 `/mnt/nfs/alice:/workspace` |
| 结束后 logs 404 | 正常（B 释放日志）；应在 running 时采集 |

## 本链路不覆盖

拆项验收见 `tests/integration/`：bob 隔离（I-04）、外部删容器重建（I-06）、同容器 2 卡 G1（I-07）、指定 GPU 4–7 且 `WORLD_SIZE=4`（I-08）。
