# 客户端接入说明

内网验证平台。Client 只做三件事：登录并挂自己的 NFS、向 Server A 要容器、向容器里的 Server B 开停训练，同时按需订阅画面口。

谁的数据看连的是哪个地址，报文里没有用户名、没有任务号。每用户同一时间一只容器。

---

## 1. 现场地址与账号

| 项 | 值 |
|----|----|
| Server A | `http://10.213.35.42:8017`（含画面字段；`8000` 上可能仍是旧进程，不要混用） |
| NFS | `10.250.30.115`，网段 `10.0.0.0/8` |
| 训练镜像 | `rsl_rl_isrc:v3-C`（含 Server B + 画面转发；不要用 `v3-B`） |

账号（密码均为 `{用户名}-dev`）：

| 用户 | NFS 导出 | 容器工作区（宿主机） | 容器内路径 |
|------|----------|----------------------|------------|
| `alice` | `/mnt/dockerContainer/nfs/alice` | `/mnt/nfs/alice` | `/workspace` |
| `bob` | `/mnt/dockerContainer/nfs/bob` | `/mnt/nfs/bob` | `/workspace` |
| `carol` | `/mnt/dockerContainer/nfs/carol` | `/mnt/nfs/carol` | `/workspace` |
| `dave` | `/mnt/dockerContainer/nfs/dave` | `/mnt/nfs/dave` | `/workspace` |
| `eve` | `/mnt/dockerContainer/nfs/eve` | `/mnt/nfs/eve` | `/workspace` |
| `frank` | `/mnt/dockerContainer/nfs/frank` | `/mnt/nfs/frank` | `/workspace` |

用登录返回的 `nfs_host` + `nfs_export_path`，不要写死别的导出。

---

## 2. 推荐调用顺序

```
1. POST /login                         → token、NFS 地址；若容器已在跑，还会带任务地址和画面地址
2. 本机挂载 NFS                         → 把训练脚本放到导出目录（容器里是 /workspace）
3. POST /containers/start              → server_b_endpoint、obs_pub_endpoint
4. （可选）先 SUB 画面地址               → 此时还没有帧，TCP/ZMQ 可先连上
5. POST http://{server_b_endpoint}/tasks/start
6. 轮询 /tasks/{id}/status；运行中拉 /logs；SUB 收帧
7. 任务结束：容器还在，画面停在最后一帧；可再 start
8. POST /containers/stop               → 删容器，两个地址作废
```

要点：

- 任务打到 **Server B**，不经 A。
- 开训不要加 `--no-zmq-obs`，否则没有画面（平台不拦）。
- 任务结束 **不会** 删容器；只有 `POST /containers/stop` 才删。
- 同一用户再 `start` 容器是幂等的：还在跑就返回正在用的那只，**不会偷偷重建**。老容器没有画面口时 `obs_pub_endpoint` 可为 `null`，要换新口请自己 `stop` 再 `start`。

---

## 3. Server A

Base URL 记为 `$A`。除 `/login`、`/health` 外，容器接口都要：

```http
Authorization: Bearer <token>
```

JWT 默认 24 小时。过期后重新登录即可；已有容器不受影响。

### 3.1 `POST /login`

```bash
curl -sS -X POST "$A/login" \
  -H 'content-type: application/json' \
  -d '{"username":"carol","password":"carol-dev"}'
```

成功 `200`：

```json
{
  "token": "...",
  "expires_at": "2026-08-19T08:00:00.000000Z",
  "nfs_host": "10.250.30.115",
  "nfs_export_path": "/mnt/dockerContainer/nfs/carol",
  "server_b_endpoint": null,
  "obs_pub_endpoint": null
}
```

容器已在跑时，后两个字段为 `host:port`（例如 `10.213.35.42:31002` / `10.213.35.42:32002`）。失败 `401`：`{"detail":{"error":"invalid credentials"}}`。

### 3.2 挂载 NFS

在 **client 本机**（能访问 115 的机器）挂登录返回的导出：

```bash
export NFS_HOST=10.250.30.115
export NFS_EXPORT=/mnt/dockerContainer/nfs/carol   # 用 login 返回值
export MNT=/mnt/nfs/carol                          # 本机自选挂载点

sudo mkdir -p "$MNT"
sudo mount -t nfs -o vers=4,clientaddr=$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1) \
  "$NFS_HOST:$NFS_EXPORT" "$MNT"
```

若本机 Clash TUN 把 115 拐到 `198.18.0.0/16`，先加：

```bash
sudo ip rule add to 10.250.30.115 lookup main pref 8000
```

训练脚本放到 `$MNT/jobs/`。容器内对应 `/workspace/jobs/`。`script_path` 必须是相对工作区的路径，例如 `jobs/train.py`，禁止绝对路径。

### 3.3 `POST /containers/start`

```bash
curl -sS -X POST "$A/containers/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}'
```

请求字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `image` | string | 必填。验证用 `rsl_rl_isrc:v3-C` |
| `gpu_count` | int | 默认 `0`。按数量向 Docker 申请 GPU，本轮不指定卡号 |
| `cpu` | string / null | 可选，透传为 CPU 核数上限，例如 `"4"` |
| `memory` | string / null | 可选，透传 Docker 内存上限，例如 `"32g"` |

成功 `200`：

```json
{
  "server_b_endpoint": "10.213.35.42:31002",
  "obs_pub_endpoint": "10.213.35.42:32002",
  "container_status": "running",
  "container_name": "runner-carol",
  "nfs_mount_path": "/workspace"
}
```

| 字段 | 含义 |
|------|------|
| `server_b_endpoint` | `内网IP:31xxx`，映射容器 `8080`，给任务 HTTP |
| `obs_pub_endpoint` | `内网IP:32xxx`，映射容器 `15557`，给画面 ZMQ SUB；老容器可能为 `null` |
| `container_name` | `runner-{用户名}` |
| `nfs_mount_path` | 容器内工作区，固定 `/workspace` |

失败：`401` 缺/坏 token；`502` 健康检查失败（容器会被删掉）；`503` Docker 未开或端口池耗尽。

就绪只看 Server B `GET /health`。画面口 TCP 不通时，只要 B 健康仍会返回；连不上画面再自己处理。

### 3.4 `GET /containers/current`

同一套返回体。没有容器时 `404`：`{"detail":{"error":"no container"}}`。

### 3.5 `POST /containers/stop`

```bash
curl -sS -X POST "$A/containers/stop" \
  -H "Authorization: Bearer $TOKEN"
```

成功 `{"status":"stopped"}`。容器删除，`31xxx` / `32xxx` 释放。没有容器时 `404`。

---

## 4. Server B（任务）

Base：`http://{server_b_endpoint}`。**不需要** A 的 JWT。同一容器同一时间只能有一个任务。

### 4.1 `GET /health`

`{"status":"ok"}`。A 起容器时已探过；client 可再探。

### 4.2 `POST /tasks/start` → `202`

```bash
curl -sS -X POST "http://$EP/tasks/start" \
  -H 'content-type: application/json' \
  -d '{
    "script_path": "jobs/train.py",
    "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
    "script_args": []
  }'
```

| 字段 | 说明 |
|------|------|
| `script_path` | 相对 `/workspace`，必须已存在于该用户 NFS |
| `torchrun_args` | 插在启动器与脚本之间。镜像内启动器默认 `torchrun` |
| `script_args` | 跟在脚本路径后面 |

实际命令：`torchrun {torchrun_args} /workspace/{script_path} {script_args}`，工作目录 `/workspace`。

成功：

```json
{"task_id":"t-1","status":"running","started_at":"2026-08-18T08:00:00+00:00"}
```

| HTTP | 原因 |
|------|------|
| `400` | 路径非法、逃出工作区、或文件不存在 |
| `409` | 已有任务在跑 |

`gpu_count` 与 `--nproc_per_node` 由 client 自己对齐（2 卡就写 `2`）。

### 4.3 `GET /tasks/{task_id}/status`

```json
{
  "task_id": "t-1",
  "status": "running",
  "exit_code": null,
  "started_at": "...",
  "finished_at": null
}
```

`status`：`running` / `succeeded` / `failed` / `stopped`。不存在 `404`。

### 4.4 `GET /tasks/{task_id}/logs?since=0`

在 **running 期间**拉。任务结束后内存日志会释放，再拉是 `404` `logs released`。

`since` 是日志拼接文本的 **字符偏移**（不是行号）。下次用返回的 `next_offset`：

```json
{"next_offset": 1204, "lines": ["..."]}
```

### 4.5 `POST /tasks/{task_id}/stop`

`{"status":"stopped"}`。只停训练，不删容器，画面停在最后一帧。

---

## 5. 画面口（ZMQ SUB）

`obs_pub_endpoint` 形如 `10.213.35.42:32002`。Client 用 **SUB** 连 `tcp://{host}:{port}`，订阅空前缀。

- 无 topic、无用户名、无任务号。连错地址才会串到别人的画面。
- 一帧一条 UTF-8 JSON，不是 multipart，也不是算法包那套 `label + " " + json` 文本。
- 默认原样转发训练中继，每帧最多 **64** 个机器人：

```json
[
  [[x, y, z], [qx, qy, qz, qw], [dof, ...]],
  ...
]
```

每行三个数组：**位置**、**姿态（四元数）**、**关节**。

训完没有新帧，已连接的订阅停在最后一帧。同一容器接着跑下一份训练，画面口不变；要不要重连由 client 自己决定。

Python 示例：

```python
import json
import zmq

host, port = obs_pub_endpoint.rsplit(":", 1)
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.setsockopt(zmq.SUBSCRIBE, b"")
sock.connect(f"tcp://{host}:{port}")
raw = sock.recv()
frame = json.loads(raw.decode("utf-8"))
# frame[i] == [position, quaternion, joints]
```

---

## 6. 最小端到端（carol）

```bash
A=http://10.213.35.42:8017

LOGIN=$(curl -sS -X POST "$A/login" -H 'content-type: application/json' \
  -d '{"username":"carol","password":"carol-dev"}')
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$LOGIN")
NFS_HOST=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["nfs_host"])' <<<"$LOGIN")
NFS_EXPORT=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["nfs_export_path"])' <<<"$LOGIN")

sudo mkdir -p /mnt/nfs/carol
sudo mount -t nfs -o vers=4 "$NFS_HOST:$NFS_EXPORT" /mnt/nfs/carol
# 把训练脚本写到 /mnt/nfs/carol/jobs/your_train.py

START=$(curl -sS -X POST "$A/containers/start" \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}')
EP=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["server_b_endpoint"])' <<<"$START")
OBS=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["obs_pub_endpoint"])' <<<"$START")

# 可视化：SUB tcp://$OBS
curl -sS -X POST "http://$EP/tasks/start" -H 'content-type: application/json' \
  -d '{"script_path":"jobs/your_train.py","torchrun_args":["--nproc_per_node","2","--standalone"],"script_args":[]}'
```

---

## 7. 隔离与约束

- 每用户一只容器、一套 `31xxx` + `32xxx`。alice 的画面地址和 carol 的不同，连自己的就不会串。
- 容器 bind 的是 **该用户** 的 NFS。不要把脚本写到别人的导出。
- 本轮单机多卡：`gpu_count` 申请数量，不指定具体 GPU 编号。
- 不要自己 `docker run`；必须经 A 的 `containers/start`。
- 不要连容器内 `15555` / `15556`（不映射）。画面只走 `obs_pub_endpoint`。

---

## 8. 常见问题

| 现象 | 先看 |
|------|------|
| login 401 | 用户名/密码；改过 `users.yaml` 后 A 要重启才生效 |
| start 502 | 镜像不是 `v3-C`、B 没起来；失败时容器已被删 |
| 有任务地址无画面字段 | 老容器没映射 `15557`：`stop` 再 `start` |
| 有口一直没画面 | 没开训、加了 `--no-zmq-obs`、或 SUB 连错地址 |
| tasks/start 400 | `script_path` 不是相对路径，或 NFS 上没有该文件 |
| tasks/start 409 | 上一份训练还在跑，先 `tasks/{id}/stop` |
| logs 404 | 任务已经结束，日志已释放 |
| NFS 挂不上 / 读到空目录 | 用 login 返回的导出；Clash TUN 见 §3.2 |
| 看到别人的机器人 | 连错了 `obs_pub_endpoint` |
