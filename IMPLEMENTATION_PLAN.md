# Server A / Server B 实现计划（验证版）

> 本文档基于 grilling 会话收敛的 64 项决策，作为后续开发的唯一依据。
> 范围：内网小范围验证。正式环境前需重新评审安全决策（标 ⚠️）。

---

## 1. 目标

构建一个控制面（Server A）+ 容器内执行面（Server B）系统：

- Server A 负责：用户登录认证、NFS 挂载管理、Docker 容器生命周期、端口分配、健康检查。
- 用户登录后获得 NFS 地址与容器内 Server B 地址，客户端自行挂载 NFS、向 Server B 发送 `torchrun` 启动命令。
- 验证环境：Linux 主机（已装 NVIDIA 驱动 + nvidia-container-toolkit + Docker `--gpus` 支持）。

---

## 2. 架构总览

```
客户端 (Client)
  │  ├─ 挂载 NFS（本机）          ← 登录响应中的 nfs_host + nfs_export_path
  │  └─ HTTP → Server B 任务命令   ← start 响应中的 server_b_endpoint
  │
  ▼  HTTP(登录/JWT)
Server A (FastAPI, Linux)
  ├─ 启动时挂载全部用户 NFS → /mnt/nfs/{user}
  ├─ docker run runner-{user}
  │     -v /mnt/nfs/{user}:/workspace
  │     -p 内网IP:31xxx:8080
  │     --gpus {N}
  │     --cpus / --memory（用户传值，原样透传）
  ├─ SQLite 注册表（端口分配/容器ID/状态）
  └─ 后台轮询 Docker 对账
        │
        ▼
NFS Server ── 用户目录（预置，Server A 只挂载）

Docker 容器 runner-{user}
  ├─ 镜像 ENTRYPOINT/CMD 自动启动 Server B
  ├─ Server B 监听 :8080
  │     ├─ /health
  │     ├─ /tasks/start  → 执行 torchrun（进程组，仅一个并发任务）
  │     ├─ /tasks/{id}/status | stop | logs
  │     └─ 日志内存保留，任务结束释放
  └─ 挂载 /workspace = 用户 NFS 目录（容器可写，靠约定不写 ⚠️）
```

---

## 3. 目录结构

```
server149/
├── 需求                          # 原始需求
├── plan/
│   └── IMPLEMENTATION_PLAN.md    # 本文档
└── server_a/                     # 控制面（宿主机运行）
    ├── app/
    │   ├── __init__.py
    │   ├── main.py               # FastAPI 入口、路由挂载
    │   ├── config.py             # 配置加载（YAML + 环境变量覆盖）
    │   ├── models.py             # SQLite 表结构（SQLAlchemy/raw sqlite3）
    │   ├── auth.py               # 登录、bcrypt 校验、JWT 签发/解析
    │   ├── nfs.py                # NFS 挂载/校验/重挂载
    │   ├── docker_mgr.py         # docker SDK：create/start/stop/rm/health
    │   ├── ports.py              # 端口池分配/释放（31000-31999）
    │   ├── registry.py           # 用户-容器注册表（SQLite）
    │   ├── reconciler.py         # 后台轮询 Docker 状态对账
    │   ├── routers/
    │   │   ├── __init__.py
    │   │   ├── auth.py           # POST /login
    │   │   └── containers.py     # /containers/start|current|stop
    │   └── schemas.py            # Pydantic 请求/响应模型
    ├── config/
    │   ├── users.yaml            # 管理员维护的用户+密码哈希+NFS
    │   └── server.yaml           # 端口池、JWT 密钥、挂载根目录等
    ├── requirements.txt
    └── tests/                    # pytest：auth/nfs/docker/ports/reconciler
└── server_b/                     # 执行面（打入/验证镜像内运行）
    ├── app/
    │   ├── __init__.py
    │   ├── main.py               # FastAPI 入口（监听 8080）
    │   ├── schemas.py            # 任务请求/响应模型
    │   ├── task_manager.py       # 任务状态机、进程组管理、并发锁
    │   ├── executor.py           # torchrun 子进程、SIGTERM/SIGKILL
    │   ├── log_store.py          # 内存日志环形缓冲 + 偏移量查询
    │   └── path_guard.py         # /workspace 路径防穿越校验
    ├── requirements.txt
    └── tests/
```

> 注：Server B 为独立包，通过多阶段构建或拷贝方式打入用户镜像；镜像验收时确认 `python3`、`torchrun` 可用且启动 Server B 于 8080。

---

## 4. Server A 设计

### 4.1 配置

**server.yaml**
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  internal_ip: "10.0.0.10"        # 端口绑定与返回给客户端的 IP
  jwt_secret: "CHANGE_ME"         # 由环境变量 SERVER_A_JWT_SECRET 覆盖
  jwt_ttl_hours: 24
  port_range: [31000, 31999]
  nfs_mount_root: "/mnt/nfs"
  container_workspace: "/workspace"
  health:
    interval_sec: 2
    timeout_sec: 60
  db_path: "./data/registry.db"
  reconcile_interval_sec: 30
```

**users.yaml**（管理员手工维护；密码为 bcrypt 哈希）
```yaml
users:
  alice:
    password_hash: "$2b$12$..."      # bcrypt
    nfs_host: "10.0.0.20"
    nfs_export_path: "/export/alice"
    local_mount_path: "/mnt/nfs/alice"   # 由 Server A 挂载
  bob:
    password_hash: "$2b$12$..."
    nfs_host: "10.0.0.20"
    nfs_export_path: "/export/bob"
    local_mount_path: "/mnt/nfs/bob"
```

### 4.2 SQLite 注册表（registry.db）

```sql
-- 端口分配与容器绑定（停止/删除容器时释放端口并清除记录）
CREATE TABLE containers (
    username     TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    container_name TEXT NOT NULL,        -- runner-{username}
    host_port    INTEGER NOT NULL,       -- 端口池内
    image        TEXT NOT NULL,
    gpu_count    INTEGER NOT NULL,
    cpu          TEXT,                   -- 原样透传 Docker 限制
    memory       TEXT,
    status       TEXT NOT NULL,          -- running / stopped / removing / failed
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
```

### 4.3 API

所有接口（除 `/login`）要求 `Authorization: Bearer <JWT>`，身份从 `sub=username` 解析。

#### POST /login
- 请求：`{"username": "alice", "password": "..."}`
- 成功 200：
```json
{
  "token": "<JWT>",
  "expires_at": "2026-08-18T12:00:00Z",
  "nfs_host": "10.0.0.20",
  "nfs_export_path": "/export/alice",
  "server_b_endpoint": "10.0.0.10:31001"
}
```
- 失败 401：`{"error": "invalid credentials"}`

#### POST /containers/start
- 请求：`{"image": "registry.example.com/runner:1.2.0", "gpu_count": 2, "cpu": "4", "memory": "16g"}`
- 逻辑（用户级锁 + 幂等）：
  1. 校验用户 NFS 挂载点存在，丢失则自动重挂；失败 500。
  2. 注册表中容器 running → 直接返回现有信息（幂等）。
  3. 注册表中存在 stopped/异常遗留容器 → `docker rm -f` 清理。
  4. 分配端口 → `docker run`（参数见 4.4）→ 健康检查 `/health`（2s 间隔 / 60s 超时）。
  5. 健康检查失败 → `docker rm -f` + 释放端口 + 返回 502 错误。
- 成功 200：
```json
{
  "server_b_endpoint": "10.0.0.10:31001",
  "container_status": "running",
  "container_name": "runner-alice",
  "nfs_mount_path": "/workspace"
}
```

#### GET /containers/current
- 实时向 Docker 校验状态后返回（同 start 响应结构），无容器则 404。

#### POST /containers/stop
- 逻辑：`docker stop`（默认 10s 宽限）→ `docker rm` → 释放端口 → 清除注册表记录。
- 容器内运行中的任务进程由容器销毁统一清理。
- 成功 200：`{"status": "stopped"}`；无容器 404。

### 4.4 docker run 参数（Server A 生成）

```
docker run -d --name runner-{user} \
  --restart no \
  -v {local_mount_path}:/workspace \
  -p {internal_ip}:{host_port}:8080 \
  --gpus {gpu_count} \
  --cpus {cpu} \
  --memory {memory} \
  {image}
```

- `--cpus/--memory` 为用户传值，**不设上限原样透传** ⚠️。
- 容器名、挂载路径、端口、网络全部由 Server A 生成，用户不可控。
- 用户镜像契约（验收清单）：ENTRYPOINT/CMD 自动启动 Server B 于 8080；含 `python3` 与 `torchrun`。

### 4.5 NFS 管理
- 启动时挂载全部用户：`mount -t nfs {nfs_host}:{nfs_export_path} {local_mount_path}`。
- 任一用户挂载失败 → **Server A 拒绝启动**（记录具体失败原因）。
- 启动前 `start` 流程中复查挂载点；丢失则自动重挂。
- 不主动卸载（挂载生命周期 = Server A 生命周期）。

### 4.6 后台对账（reconciler）
- 每 30s 轮询 Docker 容器状态，与注册表比对：
  - 注册表 running 但 Docker 中不存在/Exited → 标记为异常遗留（下次 start 时清理重建）。
  - Docker 中存在但注册表无记录（Server A 重启后残留）→ 若容器名匹配 `runner-*` 则补录，否则忽略。

---

## 5. Server B 设计

### 5.1 API（监听 0.0.0.0:8080）

#### GET /health
- 200 `{"status": "ok"}`（供 Server A 健康检查）。

#### POST /tasks/start
- 请求：
```json
{
  "script_path": "jobs/train.py",
  "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
  "script_args": ["--epochs", "10"]
}
```
- 校验：
  - `script_path` 相对路径 → `realpath` 解析 → 必须落在 `/workspace` 内，否则 400。
  - 同一容器已有 running 任务 → 409 冲突。
- 成功 202：
```json
{"task_id": "t-1", "status": "running", "started_at": "..."}
```

#### GET /tasks/{task_id}/status
- 200：
```json
{
  "task_id": "t-1",
  "status": "running | succeeded | failed | stopped",
  "exit_code": null,
  "started_at": "...",
  "finished_at": null
}
```

#### POST /tasks/{task_id}/stop
- 对进程组 SIGTERM → 5s 后 SIGKILL；状态置 `stopped`；幂等。

#### GET /tasks/{task_id}/logs?since=0
- 返回增量日志：`{"next_offset": 12345, "lines": ["...", "..."]}`。
- 任务结束后日志立即释放，后续查询 404 ⚠️（无历史日志，见 Q26/Q64）。

### 5.2 执行模型
```
torchrun <torchrun_args> /workspace/<script_path> <script_args>
```
- 参数数组原样透传，**不校验** ⚠️（Q35）。
- 使用 `subprocess.Popen` + `start_new_session=True` 创建独立进程组；停止时对 `os.killpg` 发 SIGTERM → 超时 SIGKILL。
- 任务状态机：`running → succeeded | failed | stopped`。
- 并发：容器级任务锁，同刻仅一个任务。
- 路径守卫：`Path("/workspace") / script_path` → `resolve()` 后 `is_relative_to("/workspace")`，拒绝 `..`/绝对路径/符号链接越界。
- 日志：内存保留（不设上限 ⚠️），按 task_id 存储追加行，供偏移量轮询。

### 5.3 镜像契约（人工验收）
- 镜像内含并自动启动 Server B（8080）。
- 存在 `python3`、`torchrun`。
- 客户端固定完整镜像引用与版本（写死在客户端）。

---

## 6. 实施步骤（Task 分解）

| # | 任务 | 产出 | 验收 |
|---|------|------|------|
| 1 | Server B 骨架 | server_b 包 + `/health` + 路径守卫 | pytest 通过；本机启动返回 ok |
| 2 | Server B 任务执行 | task_manager + executor（进程组信号）+ 单任务锁 | 启/停/状态/日志单测；SIGKILL 孤儿验证 |
| 3 | Server B 日志与状态 API | logs/status/stop 全接口 | 偏移量轮询测试通过 |
| 4 | Server A 配置与认证 | users.yaml/server.yaml 加载 + bcrypt + JWT + `/login` | 登录成功/失败用例 |
| 5 | Server A NFS 管理 | 启动挂载全部用户；失败拒绝启动；重挂 | 用假 NFS 或真实环境验证 |
| 6 | Server A 端口池与注册表 | SQLite + 分配/释放/持久化 | 并发分配测试 |
| 7 | Server A 容器管理 | docker_mgr + start/current/stop + 幂等 + 健康检查 | 真实 Docker 启停；健康失败回收 |
| 8 | 后台对账 | reconciler 轮询 | 手动 stop 容器后状态同步 |
| 9 | 端到端联调 | 客户端脚本：登录→挂 NFS→start→torchrun 任务→日志→stop | 全链路跑通一个 CPU+GPU 训练 |

---

## 7. 风险与已知取舍（验证版，正式前必须评审）

| ⚠️ 项 | 现状 | 风险 |
|-------|------|------|
| 容器可写 NFS | 靠约定不写 | 用户脚本可修改 NFS 文件 |
| torchrun 参数不校验 | 原样透传 | 接口可被滥用为任意命令执行 |
| Server B 无认证 | 内网开放 | 任意内网主机可发任务 |
| 资源不设上限 | 原样透传 | 单用户可占满宿主机 |
| 日志无历史 | 任务结束即丢 | 无法回溯失败现场 |
| GPU 无调度 | Docker 自动分配 | 多容器可能争用同一 GPU |
| 挂载全失败即拒启 | 单点故障放大 | 一个 NFS 故障导致平台不可用 |

---

## 8. 待确认/实现时需现场核实的事实

- 目标宿主机：Linux 发行版、Docker 版本、NVIDIA 驱动与 nvidia-container-toolkit 版本、Docker `--gpus` 可用性。
- 用户镜像清单：镜像地址、版本、内部 Server B 启动方式、`python3`/`torchrun` 路径。
- NFS 版本与挂载参数（nfsv3/v4、rsize/wsize、noatime 等）——配置预留扩展。
- 客户端操作系统（决定 NFS 挂载命令示例，不影响 Server 设计）。
