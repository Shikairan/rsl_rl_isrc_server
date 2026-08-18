# 分阶段开发方案（本机 Server A / 115 NFS / 分开测试）

> 依据 `IMPLEMENTATION_PLAN.md`。不改 64 项产品决策，只调整**开发顺序、机器分工、验收边界**。
> 目标：115 与本机可独立开发、独立失败、独立验收；最后再汇合。

---

## 0. 现场分工（已确认）

| 角色 | 机器 | IP | 做什么 | 不做什么 |
|------|------|-----|--------|----------|
| NFS Server | 115 | `10.250.30.115` | 导出用户目录；保证 NFS 服务稳定 | 不跑 Server A / Server B / 用户容器 |
| Server A 宿主机 | 本机 | `10.213.35.42` | 开发/运行控制面；挂载 115 的 NFS；后续 `docker run` | 不在 115 上部署 A |
| Server B | 本机 Docker 容器（后期） | 映射 `10.213.35.42:31xxx → :8080` | 容器内执行 `torchrun` | 不在 115 上跑 |

**真实路径（替换计划文档中的占位 IP）：**

```yaml
# Server A server.yaml
internal_ip: "10.213.35.42"
nfs_mount_root: "/mnt/nfs"

# users.yaml
alice:
  nfs_host: "10.250.30.115"
  nfs_export_path: "/mnt/dockerContainer/nfs/alice"
  local_mount_path: "/mnt/nfs/alice"
bob:
  nfs_host: "10.250.30.115"
  nfs_export_path: "/mnt/dockerContainer/nfs/bob"
  local_mount_path: "/mnt/nfs/bob"
```

**已完成基线：** 115 已装 `nfs-kernel-server`，导出 `alice`/`bob`；本机已装 `nfs-common`，`alice` 已成功挂到 `/mnt/nfs/alice`。

---

## 1. 分开测试原则

1. **115 轨道只验 NFS。** 验收命令是 `showmount` / `mount` / 读写文件，**不启动 FastAPI**。
2. **本机轨道默认可关外部依赖。** Server A 增加两个开关（实现时写入 `server.yaml`）：
   ```yaml
   nfs:
     enabled: true    # P2 单测设 false；P3 起对 115 设 true
   docker:
     enabled: true    # P2–P4 设 false；P6 起设 true
   ```
   - `nfs.enabled: false`：不执行 `mount`，启动不因 NFS 失败而退出。
   - `docker.enabled: false`：`/containers/*` 返回 503，登录仍可用。
3. **Server B 在本机先当普通进程测**，不进镜像、不经 Server A、不挂 NFS。
4. **Docker 与 NFS 分两次接入：** 先 `-v 本地目录:/workspace`，再换成 `-v /mnt/nfs/{user}:/workspace`。
5. 每阶段有**本阶段独立验收清单**；未通过不进入下一阶段对该依赖的联调。

---

## 2. 两条轨道（可并行）

```
115 轨道                         本机轨道
────────                         ────────
P1 NFS 独立验收                  P2 Server A 认证（nfs/docker 关）
  │                              P4 端口池 + SQLite
  │                              P5 Server B 进程级（假 torchrun）
  ▼                              ▼
                         P3 A 对接真实 NFS（docker 仍关）
                         P6 A 管 Docker（本地目录，不挂 NFS）
                         P7 Docker bind 真实 NFS
                         P8 reconciler
                         P9 端到端（先 CPU，再 GPU）
```

P1 ∥ P2 ∥ P4 ∥ P5 可同时进行。P3 依赖 P1+P2。P6 依赖 P4+P5。P7 依赖 P3+P6。

---

## 3. 阶段明细

### P0 — 环境冻结（进行中，不写业务代码）

**本机**

- Conda 环境：`conda create -n server149 python=3.11`（建议，避免 base 3.14）
- 确认：Docker、`nvidia-container-toolkit`、`docker run --gpus`（P6/P9 才硬性需要）
- 本机用户需能 `sudo mount`（Server A 启动挂载）以及访问 Docker socket

**115**

- 只维护 NFS；不要在上面装 Server A 依赖

**验收：** 两台机器角色书面确认；本文档路径/IP 与现场一致。

---

### P1 — 115 NFS 独立验收（不经 Server A）

**115 产出**

- 导出保持：
  - `/mnt/dockerContainer/nfs`
  - `/mnt/dockerContainer/nfs/alice`
  - `/mnt/dockerContainer/nfs/bob`
- 加用户流程：只在 115 建目录 + 改 `/etc/exports` + `exportfs -ra`（与 Server A 的 `users.yaml` 分两次改，先改 115）
- `nfs-server` enable；重启 NFS 服务后导出仍在

**本机验收（手动，禁止启动 Server A）**

```bash
showmount -e 10.250.30.115
sudo mkdir -p /mnt/nfs/bob
sudo mount -t nfs -o vers=4 10.250.30.115:/mnt/dockerContainer/nfs/bob /mnt/nfs/bob
echo test | sudo tee /mnt/nfs/bob/p1_rw.txt
# 在 115 上 cat 该文件应可见
sudo umount /mnt/nfs/bob
```

alice 已通过，本阶段补 **bob**、**卸载/重挂**、**nfs-server restart 后仍可挂**。

**失败归 115，不改 Server A。**

---

### P2 — 本机 Server A 认证面（NFS/Docker 关闭）

对应原计划 Task 4。本机 `~/149server/serverA/`（conda 环境名 `serverA`）。

**产出**

- 包结构、`requirements.txt`、conda 环境
- `config.py` 加载 YAML + 环境变量覆盖
- `users.yaml` / `server.yaml`（真实 NFS 字段先写上，但 `nfs.enabled: false`）
- bcrypt + JWT + `POST /login`
- pytest：登录成功/失败、过期 token

**验收（本机，不碰 115）**

```bash
pytest server_a/tests/test_auth.py
curl -X POST localhost:8000/login -d '{"username":"alice","password":"..."}'
# 200 含 token / nfs_host / nfs_export_path；密码错 401
# /containers/start 在 docker.enabled=false 时 503
```

**失败归本机代码，与 NFS 无关。**

---

### P3 — 本机 Server A 对接 115 NFS（Docker 仍关闭）

对应原计划 Task 5。`nfs.enabled: true`。

**产出**

- `nfs.py`：启动挂载全部用户；丢失则重挂；失败拒绝启动并打日志
- 启动前 `start` 路径中的挂载复查（即使 Docker 关，也可提供内部函数/管理接口，或仅在进程启动时挂载）

**验收（本机 ↔ 115，不跑容器）**

1. 先 `umount` 本机 `/mnt/nfs/alice`（若已手工挂上）。
2. 启动 Server A → 两个用户目录均为 NFS 挂载点。
3. `findmnt /mnt/nfs/alice` 源为 `10.250.30.115:/mnt/dockerContainer/nfs/alice`。
4. 人为 `umount` 后调用重挂逻辑，目录恢复。
5. 临时改 `users.yaml` 指向不存在的 export → **进程拒绝启动**。

登录接口返回的 `nfs_host` / `nfs_export_path` 必须是 115 真实值（给客户端自己挂，不是本机 `/mnt/nfs/...`）。

**失败：挂不上归 115/网络；挂载逻辑错归 Server A。**

---

### P4 — 本机端口池 + SQLite 注册表

对应原计划 Task 6。不需要 115，不需要 Docker。

**产出**

- `ports.py`：31000–31999 分配/释放
- `registry.py` + `registry.db`
- 并发分配 pytest

**验收：** 纯单测。与 NFS 并行无耦合。

---

### P5 — 本机 Server B 独立（不经 A、不经 NFS）

对应原计划 Task 1–3。本机后续 `~/149server/serverB/`（尚未建）。NFS 管理代码在 `~/149server/nfsserver/`。

**产出**

- `/health`、路径守卫、`task_manager` / `executor` / 日志 API
- 测试用 `WORKSPACE_ROOT=/tmp/sb-ws`（不要写死必须 `/workspace`，用配置；镜像里再设 `/workspace`）
- 用 `python3 -c 'print("ok")'` 或假脚本代替 `torchrun`（`executor` 可配置 `launcher`，默认 `torchrun`）

**验收（本机进程）**

```bash
pytest server_b/tests
uvicorn server_b.app.main:app --port 8080
curl localhost:8080/health          # {"status":"ok"}
# start/status/stop/logs；越界路径 400；第二任务 409
```

**失败归 Server B，与 115、Server A 无关。**

---

### P6 — 本机 Docker 生命周期（先不挂 NFS）

对应原计划 Task 7 的 Docker 部分。`docker.enabled: true`，卷用**本地目录**。

**产出**

- `docker_mgr.py` + `/containers/start|current|stop`
- 最小验证镜像：只跑 Server B `:8080`，可无 GPU、无 torch
- `docker run` 先：
  ```
  -v /tmp/runner-alice:/workspace
  -p 10.213.35.42:{port}:8080
  ```
  不要 `--gpus`（本阶段）

**验收（本机 Docker，115 不参与）**

- start 幂等；stop 删容器并释放端口
- 健康检查失败 → `docker rm -f` + 502
- `curl 10.213.35.42:{port}/health` 为 ok

**失败归 Docker/镜像/Server A，不查 NFS。**

---

### P7 — 容器挂真实 NFS（仍可不跑训练）

把 P6 的 bind 换成 P3 的挂载点：

```
-v /mnt/nfs/alice:/workspace
```

**验收**

- 本机往 `/mnt/nfs/alice/jobs/hello.py` 写文件（或 115 上写）
- 容器内 `ls /workspace/jobs/hello.py` 看得到
- 不调用 `/tasks/start` 也可过本阶段

**失败：容器内看不到文件 → 查 bind 与 NFS；容器起不来 → 退回 P6。**

---

### P8 — 后台对账 reconciler

对应原计划 Task 8。本机 Docker。

**验收：** 手动 `docker stop runner-alice` 后 30s 内注册表变为异常遗留；再次 start 能清理重建。不需要 115 新操作。

---

### P9 — 端到端（先 CPU，再 GPU）

对应原计划 Task 9。这是**唯一**要求 A + NFS + B 同时在线的阶段。

**P9a CPU（强制先做）**

1. 客户端（本机即可）：`POST /login` → 拿到 NFS 地址（115）与 token  
2. 客户端自行挂 NFS（或复用已挂的 `/mnt/nfs/alice` 只读检查）  
3. `POST /containers/start`（`gpu_count: 0` 或镜像无 GPU）  
4. `POST http://10.213.35.42:31xxx/tasks/start` 跑短脚本  
5. 拉 logs / stop 容器  

**P9b GPU**

- `--gpus N` + 真实 `torchrun`；镜像契约人工验收（`python3`、`torchrun`、ENTRYPOINT 起 Server B）

---

## 4. 建议开发顺序（本机人力单线程时）

| 顺序 | 阶段 | 预估 | 依赖 |
|------|------|------|------|
| 1 | P0 收尾 + P1 bob 补测 | 短 | 无 |
| 2 | P2 认证 | 中 | P0 |
| 3 | P5 Server B 骨架+任务 | 中 | P0 |
| 4 | P4 端口/SQLite | 短 | P2 |
| 5 | P3 对接 115 NFS | 短 | P1, P2 |
| 6 | P6 Docker（本地卷） | 中 | P4, P5 |
| 7 | P7 NFS bind 进容器 | 短 | P3, P6 |
| 8 | P8 reconciler | 短 | P6 |
| 9 | P9a CPU 联调 → P9b GPU | 中 | P7, P8 |

P2 与 P5 谁先做都可以；**不要**在 P2 未关 Docker 时就写 `docker run`。

---

## 5. 阶段隔离检查表

| 测什么 | 需要 115 NFS | 需要本机 Docker | 需要 GPU | 需要 Server A | 需要 Server B |
|--------|-------------|----------------|----------|---------------|---------------|
| P1 NFS | 是 | 否 | 否 | 否 | 否 |
| P2 登录 | 否 | 否 | 否 | 是 | 否 |
| P3 A 挂 NFS | 是 | 否 | 否 | 是 | 否 |
| P4 端口库 | 否 | 否 | 否 | 单测即可 | 否 |
| P5 B API | 否 | 否 | 否 | 否 | 进程 |
| P6 容器启停 | 否 | 是 | 否 | 是 | 最小镜像 |
| P7 容器见 NFS | 是 | 是 | 否 | 是 | 最小镜像 |
| P8 对账 | 否 | 是 | 否 | 是 | 最小镜像 |
| P9a 任务 | 是 | 是 | 否 | 是 | 是 |
| P9b 训练 | 是 | 是 | 是 | 是 | 含 torch |

---

## 6. 与原计划 Task 的映射

| 原 Task | 本方案 |
|---------|--------|
| 1–3 Server B | P5（独立进程），镜像化推迟到 P6 |
| 4 认证 | P2 |
| 5 NFS | P1（115 侧）+ P3（A 侧）拆开 |
| 6 端口/注册表 | P4 |
| 7 容器管理 | P6（无 NFS）+ P7（有 NFS）拆开 |
| 8 reconciler | P8 |
| 9 端到端 | P9a / P9b |

原计划把 NFS 和 Docker 都放在 Server A 一条链里，现场改成 **115 先独立可用，A 用开关分轨接入**。
