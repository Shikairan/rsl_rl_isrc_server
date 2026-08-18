# 联调测试方案

> 单元测试（`tests/units/`）已全部绿灯。联调不再拆层，按**真实客户端路径**一次拉齐：NFS 115 + Server A + Docker + Server B（`rsl_rl_isrc:v3-B` / `v3-C`）+ GPU。
>
> 现场：NFS `10.250.30.115`，Server A `10.213.35.42:8000`。账号 `alice` / `alice-dev`，`bob` / `bob-dev`。

## 和单元测试的差别

| | 单元 `tests/units/` | 联调 `tests/integration/` |
|--|---------------------|---------------------------|
| 目的 | 一层只测一个能力，失败只归这一层 | 跨层一次走通，失败按链路排查 |
| Server A | pytest / 测试夹具起进程、独立 sqlite | 按现场方式常驻 `0.0.0.0:8000` |
| Docker / B | 可直接 `docker run` 绕过 A | **禁止**手工 `docker run` 当主路径；必须经 `POST /containers/start` |
| 客户端 | 测试脚本内部 curl | 只使用登录返回的 NFS 地址和 `server_b_endpoint` |
| 结果 | 各用例目录已填真实结果 | 本目录步骤表「真实结果」列先空着，执行后再填 |

依赖的单元绿灯（已完成）：T-NFS-02、T-A-02、T-A-10、T-B-01～05、T-E-03、T-F-02。

## 环境与前置

| 项 | 要求 |
|----|------|
| NFS | 本机 `/mnt/nfs/alice`（及联调 bob 时 `/mnt/nfs/bob`）已挂 115 导出 |
| 镜像 | 本地存在 `rsl_rl_isrc:v3-B`（Server B）与 `rsl_rl_isrc:v3-C`（Server B + obs 转发） |
| Server A | `conda env serverA`；`docker.enabled=true`；进程能访问 Docker socket |
| GPU | I-01 / I-03 至少 1 张；I-07 双卡；I-08 需要物理卡 **4、5、6、7**（现场 8×5090，`WORLD_SIZE=4`） |
| 端口 | `8000` 给 A；容器映射 `31000–31999 → 8080`；obs 画面口 `32000–32999 → 15557` |

启动 Server A（联调全程共用这一份进程，不要用单元测试那套临时库）：

```bash
conda activate serverA
cd /home/isrc5090/149server/serverA
export SERVER_A_DOCKER_ENABLED=true
# 本机已手工挂 NFS 时保持 false；若要测 A 启动时自动 mount 再改为 true
export SERVER_A_NFS_ENABLED=false
# 需要 docker 组：newgrp docker 或 sg docker
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

探活：`curl -sS http://10.213.35.42:8000/health` → `{"status":"ok"}`。

## 怎么跑

脚本在各用例目录：`run.sh` / `run.py`，会把真实结果写回 `plan.md`。

```bash
# 全部（顺序与下表建议顺序一致）
bash /home/isrc5090/149server/tests/integration/run_all.sh

# 单条
bash /home/isrc5090/149server/tests/integration/I-01-alice主链路/run.sh
```

A 已在 `10.213.35.42:8000` 探活则复用；否则脚本按上面的现场方式拉起。不要用单元测试那套临时 sqlite。

## 客户端主路径（所有正向用例共用）

```
客户端
  1. POST /login          → token、nfs_host、nfs_export_path
  2. 本机挂载 NFS         → 用登录返回的 115 路径，不写死别的导出
  3. POST /containers/start → runner-{user}，server_b_endpoint / obs_pub_endpoint
  4. GET  {endpoint}/health → Server B 就绪（A 在 start 时已查过）
  5. POST {endpoint}/tasks/start → torchrun
  6. GET  status / logs
  7. POST /containers/stop
```

## 用例清单

| 编号 | 标题 | 文件 | 跨哪些层 |
|------|------|------|----------|
| [I-01](I-01-alice主链路/plan.md) | alice 登录到 GPU 训练再停干净 | `I-01-alice主链路/` | NFS + A + Docker + B + GPU |
| [I-02](I-02-start幂等与current/plan.md) | 重复 start 与 current | `I-02-start幂等与current/` | A + Docker + B |
| [I-03](I-03-单任务锁/plan.md) | 平台拉起的 B 上第二任务 409 | `I-03-单任务锁/` | A + B + GPU |
| [I-04](I-04-bob隔离/plan.md) | bob 容器看不到 alice 文件 | `I-04-bob隔离/` | NFS + A + Docker + B |
| [I-05](I-05-路径守卫/plan.md) | 经 A 拉起的容器上越界 400 | `I-05-路径守卫/` | A + B |
| [I-06](I-06-容器被杀后重建/plan.md) | 外部删容器后再 start 能重建 | `I-06-容器被杀后重建/` | A + Docker + B |
| [I-07](I-07-同容器双卡DDP/plan.md) | 同一 runner 内 2 卡 G1 DDP | `I-07-同容器双卡DDP/` | A + Docker + B + 2 GPU |
| [I-08](I-08-指定GPU4到7的4卡DDP全链路/plan.md) | 指定 GPU 4–7、WORLD_SIZE=4 的全链路 | `I-08-指定GPU4到7的4卡DDP全链路/` | NFS + A + Docker + B + GPU 4–7 |
| [I-OBS-01](I-OBS-01-画面地址返回与映射/plan.md) | 画面地址返回与映射 | `I-OBS-01-画面地址返回与映射/` | A + Docker + obs |
| [I-OBS-02](I-OBS-02-先连画面后开训出首帧/plan.md) | 先连画面后开训出首帧 | `I-OBS-02-先连画面后开训出首帧/` | A + Docker + B + obs + GPU |
| [I-OBS-03](I-OBS-03-同容器重复开训地址不变/plan.md) | 同容器重复开训地址不变 | `I-OBS-03-同容器重复开训地址不变/` | A + Docker + B + obs + GPU |
| [I-OBS-04](I-OBS-04-alice与bob画面隔离/plan.md) | alice 与 bob 画面隔离 | `I-OBS-04-alice与bob画面隔离/` | NFS + A + Docker + B + obs + GPU |

建议顺序：I-01 → I-02 → I-03 → I-OBS-01 → I-OBS-02 → I-OBS-03 → I-05 → I-06 → I-04 → I-OBS-04 → I-07 → I-08。

## 失败归属（联调）

| 现象 | 先查 |
|------|------|
| `/login` 不是 200 | users.yaml / A 未起，不查 Docker |
| start 502 | 镜像不是 `v3-B` 或 8080 `/health` 没起来 |
| start 200 但客户端打不通 endpoint | 绑的是 `10.213.35.42:31xxx`，不要打容器内 8080 |
| start 200 但没有 `obs_pub_endpoint` | 镜像不是 `v3-C`、A 还没发新字段，或命中了旧容器兼容路径 |
| 有 `obs_pub_endpoint` 但 TCP 连不上 | A 没映射 `32xxx->15557`，或容器入口没起 obs 转发 |
| TCP 能连但没有画面 | 训练脚本带了 `--no-zmq-obs`，或 `/workspace/jobs/` 的 smoke 脚本没真正发 obs |
| 任务 400 | `script_path` 必须相对 `/workspace`（NFS 上的路径） |
| 任务 409 | 已有 running，先 stop 任务 |
| 训练成功但本机看不到 `last_run.txt` | bind `/mnt/nfs/{user}:/workspace`，不是训练代码 |
| DDP hang / NCCL | Server A 当前 `docker run` 未加 `--shm-size/--ipc=host`，I-07 / I-08 同样受此限制 |
| I-08 打到了 GPU 0–3 | A 只支持 `gpu_count`；必须 `gpu_count:8` + 包装脚本 `CUDA_VISIBLE_DEVICES=4,5,6,7`，不要只用 `gpu_count:4` |
| bob 看到 alice 文件 | 挂错卷或 start 用了 alice 的 token |

## 明确不测

- 115 上跑 Server A / B / 训练容器
- 改 `rsl_rl_isrc:v3`（无 Server B）当联调主镜像
- Server B 无认证（内网验证版既定取舍，不在本轮补 JWT）
- 手工 `docker run` 假装 obs 联调通过（obs 联调主路径必须经 A 返回 `obs_pub_endpoint`）
