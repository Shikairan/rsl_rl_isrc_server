# 独立功能测试方案

> 一项功能一项测：每条用例只验证一个能力，失败只归这一层。
> 现场：NFS=`10.250.30.115`，Server A 宿主机=`10.213.35.42`。
> 账号：`alice` / `alice-dev`，`bob` / `bob-dev`。
>
> **执行用独立目录**：每条用例一个中文目录、一份 `plan.md`（步骤表含真实结果），脚本为 `run.sh`。索引见 [README.md](README.md)。

原则：

1. **不跨层联调**，直到本层绿灯。
2. 每条用例写清「不依赖什么」。
3. 失败先看本层验收，不要同时改 NFS、Docker、代码。
4. 已跑通过的标 **PASS**；未做标 **TODO**。

---

## 0. 环境对照

| 组件 | 位置 | 当前状态 |
|------|------|----------|
| NFS 导出 | 115 `/mnt/dockerContainer/nfs/{alice,bob}` | 已导出 |
| 本机挂载 | `/mnt/nfs/alice` | 已挂 NFSv4.2 |
| Server A | conda env `serverA`，`149server/serverA` | 登录+容器 API 已实现 |
| 训练镜像 | `rsl_rl_isrc:v3` / `v3-B`（+ Server B）/ **`v3-C`（+ 观测转发）** | v3、v3-B 已构建；**v3-C 已构建** |
| 观测转发 | 容器内 `obsserver`：HTTP `:15558/post` → PUB `:15557` | **已实现**（见 `obsserver/PLAN.md`） |
| Server B | 8080 任务 API | v3-B 已打入；T-B* 部分 PASS |

---

## A. NFS（115 + 本机 mount，不启动 Server A）

### [T-NFS-01](NFS/导出列表可见/plan.md) 导出列表可见
- **测**：115 `nfs-server` 在播
- **不依赖**：FastAPI、Docker、GPU
- **步骤**：`showmount -e 10.250.30.115`
- **通过**：出现 `/mnt/dockerContainer/nfs`、`.../alice`、`.../bob`
- **状态**：PASS

### [T-NFS-02](NFS/alice读写回115/plan.md) alice 读写
- **测**：本机挂载 alice 后可写回 115
- **不依赖**：Docker、Server A
- **步骤**：
  ```bash
  findmnt /mnt/nfs/alice
  echo ping | sudo tee /mnt/nfs/alice/jobs/nfs_rw.txt
  # 115 上 cat /mnt/dockerContainer/nfs/alice/jobs/nfs_rw.txt
  ```
- **通过**：两边内容一致
- **状态**：PASS（此前 `jobs/train.py`、`last_run.txt` 已写回）

### [T-NFS-03](NFS/bob独立挂载与隔离/plan.md) bob 独立挂载
- **测**：第二用户目录互不影响
- **不依赖**：alice 上的文件、Docker
- **步骤**：挂 `/mnt/nfs/bob`，写 `bob_only.txt`，确认 alice 目录看不到
- **状态**：TODO（bob 已导出，本机尚未常挂）

### [T-NFS-04](NFS/卸载后重挂alice/plan.md) 卸载后重挂
- **测**：丢失挂载可恢复
- **步骤**：`umount /mnt/nfs/alice` → 再 `mount -t nfs -o vers=4 10.250.30.115:/mnt/dockerContainer/nfs/alice /mnt/nfs/alice`
- **通过**：`findmnt` 源仍是 115
- **状态**：TODO（可随时补）

### [T-NFS-05](NFS/nfs-server重启后导出仍在/plan.md) nfs-server 重启
- **测**：115 服务重启后导出仍在
- **步骤**：115 上 `sudo systemctl restart nfs-server`，本机 `showmount -e` 仍列出三路
- **状态**：TODO

---

## B. Server A 认证（本机 pytest / curl，Docker 可关）

环境：`conda activate serverA`，`cd 149server/serverA`。  
单测已强制 `SERVER_A_DOCKER_ENABLED=false`。

### [T-A-01](ServerA认证/健康检查/plan.md) 健康检查
- **测**：进程能起
- **步骤**：`curl localhost:8000/health`
- **通过**：`{"status":"ok"}`
- **状态**：PASS（pytest `test_health`）

### [T-A-02](ServerA认证/登录成功/plan.md) 登录成功
- **测**：bcrypt + JWT + 返回真实 NFS 地址
- **不依赖**：容器、GPU
- **步骤**：`POST /login` `{"username":"alice","password":"alice-dev"}`
- **通过**：200，含 `token`、`nfs_host=10.250.30.115`、`nfs_export_path=/mnt/dockerContainer/nfs/alice`
- **状态**：PASS

### [T-A-03](ServerA认证/登录失败/plan.md) 登录失败
- **测**：错密码 / 未知用户
- **通过**：401
- **状态**：PASS

### [T-A-04](ServerA认证/无Token拒绝容器接口/plan.md) 无 Token 拒绝容器接口
- **测**：JWT 守卫
- **步骤**：不带 Authorization 调 `/containers/start`
- **通过**：401
- **状态**：PASS

### [T-A-05](ServerA认证/docker关闭时容器接口503/plan.md) docker 关闭时容器接口 503
- **测**：`docker.enabled=false` 隔离
- **步骤**：`SERVER_A_DOCKER_ENABLED=false` 启动，带 token 调 start
- **通过**：503
- **状态**：PASS

---

## C. Server A 容器生命周期（可 mock Docker；真机另测）

单测：`pytest tests/test_containers.py`（Docker 为 MagicMock）。

### [T-A-06](容器API/start成功_mock/plan.md) start 成功
- **测**：分配端口、注册表、返回 `runner-{user}` 与 `server_b_endpoint`
- **不依赖**：真实镜像、NFS、GPU
- **通过**：200，`container_name=runner-alice`，endpoint 形如 `10.213.35.42:31xxx`
- **状态**：PASS（mock）

### [T-A-07](容器API/start幂等_mock/plan.md) start 幂等
- **测**：已 running 不再 `docker run`
- **通过**：第二次 start 不调用 run，endpoint 不变
- **状态**：PASS（mock）

### [T-A-08](容器API/健康检查失败回收_mock/plan.md) 健康检查失败回收
- **测**：502 + `docker rm -f` + 释放端口 + 清注册表
- **通过**：502，registry 无 alice
- **状态**：PASS（mock）

### [T-A-09](容器API/current与stop_mock/plan.md) current / stop
- **测**：无容器 404；stop 后记录清除
- **状态**：PASS（mock）

### [T-A-10](容器API/真实Docker_start/plan.md) 真实 Docker start（无 NFS 要求）
- **测**：Docker socket + 端口绑定，**不测训练**
- **不依赖**：GPU、rsl 库、torchrun
- **前置**：镜像必须在 **8080** 提供 `GET /health`（当前 `rsl_rl_isrc:v3` **没有** Server B，此条会 502，属预期，直到 T-B-01 完成）
- **步骤**：`nfs.enabled=false`，`POST /containers/start` `{"image":"...","gpu_count":0}`
- **通过**：200 且 `curl 10.213.35.42:{port}/health` 为 ok
- **状态**：TODO（被 Server B 契约挡住）

---

## D. Docker + NFS 绑定（docker CLI，不经 Server A）

### [T-D-01](Docker绑定NFS/容器看见NFS文件/plan.md) 容器看见 NFS 文件
- **测**：`-v /mnt/nfs/alice:/workspace` 能读到脚本
- **不依赖**：Server A、训练成功
- **步骤**：
  ```bash
  docker run --rm -v /mnt/nfs/alice:/workspace pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime \
    ls /workspace/jobs/train.py
  ```
- **通过**：文件存在
- **状态**：PASS（torchrun 已读到该路径）

### [T-D-02](Docker绑定NFS/容器写回NFS/plan.md) 容器写回 NFS
- **测**：容器内写 `/workspace/jobs/last_run.txt`，本机 NFS 可见
- **通过**：`cat /mnt/nfs/alice/jobs/last_run.txt`
- **状态**：PASS

### [T-D-03](Docker绑定NFS/容器挂载用户隔离/plan.md) 用户隔离
- **测**：挂 alice 看不到 bob 的文件
- **状态**：TODO（配合 T-NFS-03）

---

## E. torchrun / CUDA（docker CLI）

每条只加一个变量。

### [T-E-01](torchrun与CUDA/旧镜像CPU_torchrun调度冒烟/plan.md) CPU torchrun（旧镜像，证明调度）
- **镜像**：`local/torchrun:0.01`（2.4.1，无 sm_120）
- **测**：torchrun 能跑 NFS 脚本（允许 CPU 回退）
- **状态**：PASS

### [T-E-02](torchrun与CUDA/官方GPU_torchrun/plan.md) GPU torchrun（新镜像）
- **镜像**：`pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime`
- **测**：RTX 5090 上 `device=cuda:0`，`torch=2.11.0+cu128`
- **不依赖**：rsl_rl_isrc、DDP、Server A
- **步骤**：
  ```bash
  docker run --rm --gpus 1 -v /mnt/nfs/alice:/workspace \
    pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime \
    torchrun --nproc_per_node=1 --standalone /workspace/jobs/train.py --epochs 3
  ```
- **通过**：`last_run.txt` 中 `device=cuda:0`
- **状态**：PASS

### [T-E-03](torchrun与CUDA/自定义镜像仍能GPU_torchrun/plan.md) 自定义镜像仍能 GPU torchrun
- **镜像**：`rsl_rl_isrc:v3`
- **测**：commit 后没把 CUDA 跑坏
- **不依赖**：PPO / MuJoCo
- **状态**：PASS

---

## F. rsl_rl_isrc 镜像与算法

### [T-F-01](rsl_rl_isrc算法/镜像内包可import/plan.md) 包可 import
- **测**：镜像内 `import rsl_rl_isrc, torch, mujoco`
- **不依赖**：NFS、多卡
- **通过**：`torch 2.11.0+cu128`，`mujoco 3.11.0`，`cuda True`
- **状态**：PASS

### [T-F-02](rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke/plan.md) G1 MuJoCo PPO DDP（2 卡 smoke）
- **测**：`torchrun` 双进程 + CPU 仿真 + GPU 策略
- **不依赖**：Server A、NFS、ZMQ 观测服务
- **步骤**：
  ```bash
  docker run --rm --gpus 2 --shm-size=16g --ipc=host \
    -w /opt/rsl_rl_isrc rsl_rl_isrc:v3 \
    torchrun --standalone --nnodes=1 --nproc_per_node=2 \
      rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py \
      --num-envs 16 --max-iterations 2 --no-zmq-obs
  ```
- **通过**：`world_size=2`，2 个 iteration 结束，退出码 0
- **状态**：PASS

### [T-F-03](rsl_rl_isrc算法/DDP扩到4卡/plan.md) DDP 扩卡（可选）
- **测**：`--gpus 4 --nproc_per_node=4` 仍收敛一步
- **不依赖**：ZMQ
- **状态**：TODO

### [T-F-04](rsl_rl_isrc算法/ZMQ观测通道/plan.md) ZMQ 观测通道（训练内 ObsInstrServer）
- **测**：去掉 `--no-zmq-obs` 后 rank0 拉起 PULL/REP（**不是** HTTP 中继 / 画面 PUB）
- **不依赖**：更长训练、v3-C、obsserver 转发
- **状态**：PASS
- **与 T-OBS 关系**：全链路「训练 → 中继 → 画面口」见 **T-OBS-06**

---

## I. 观测转发（obsserver + `rsl_rl_isrc:v3-C`）

方案：[obsserver/PLAN.md](../obsserver/PLAN.md)。链路：`StepObsPublisher` → rank0 `ObsInstrServer` → HTTP `127.0.0.1:15558/post` → 常驻 `obsserver` → PUB `:15557`；Server A 映射 `32xxx→15557` 并返回 `obs_pub_endpoint`（T-OBS-07，A 侧待做）。

原则：转发**随容器 ENTRYPOINT 起**，不跟某次 torchrun；15555/15556 **不映射**宿主机；报文不写用户名。

### [T-OBS-01](units/观测转发/pytest转发冒烟/plan.md) obsserver pytest 转发冒烟
- **测**：宿主机 `pytest`（transform 原样、POST→PUB、坏 JSON、404）
- **不依赖**：Docker、GPU、Server A、训练
- **状态**：TODO（`obsserver/tests` 本地已 4 passed，待纳入用例脚本）

### [T-OBS-02](units/观测转发/v3-C镜像含obsserver/plan.md) v3-C 镜像含 obsserver
- **测**：`import obsserver`；EXPOSE `15557`；对比 v3-B 无模块
- **不依赖**：Server A、NFS、GPU
- **状态**：TODO

### [T-OBS-03](units/观测转发/容器入口与B并存/plan.md) 容器入口：转发与 Server B 并存
- **测**：`/health` ok + 日志 bind `15558→15557` + 15557 TCP 可连
- **不依赖**：训练、Server A
- **状态**：TODO

### [T-OBS-04](units/观测转发/POST中继到画面PUB/plan.md) POST 中继 → 画面 PUB
- **测**：容器内 POST 示例 JSON，宿主机 SUB `15557` 收到原样数组
- **不依赖**：ObsInstrServer 真跑、Server A
- **状态**：TODO

### [T-OBS-05](units/观测转发/中继环境变量/plan.md) 中继环境变量
- **测**：`RSL_RL_ISRC_OBS_RELAY_URL`、`RSL_RL_ISRC_OBS_RELAY_TIMEOUT`；v3-B 无 RELAY
- **不依赖**：训练
- **状态**：TODO

### [T-OBS-06](units/观测转发/训练开ZMQ经中继出画面/plan.md) 训练开 ZMQ，经中继出画面（可选）
- **测**：v3-C 内极短 DDP（无 `--no-zmq-obs`），宿主机 SUB 至少一帧
- **依赖**：T-OBS-04、T-F-02；GPU ≥2
- **状态**：TODO

### [T-OBS-07](units/观测转发/ServerA返回画面地址/plan.md) Server A 返回 obs_pub_endpoint（预留）
- **测**：start/login/current 含 `obs_pub_endpoint`；`32xxx→15557` 映射；幂等不偷偷重建
- **依赖**：Server A 实现 PLAN §5、T-A-10、v3-C
- **状态**：TODO（等 A 改完）

---

## G. Server B（预留，尚未实现）

镜像契约：ENTRYPOINT 在 **8080** 起 Server B；含 `python3` / `torchrun`。

### [T-B-01](ServerB/健康检查/plan.md) /health
- 容器起来后 `GET :8080/health` → `{"status":"ok"}`

### [T-B-02](ServerB/路径守卫/plan.md) 路径守卫
- `script_path` 含 `..` 或绝对路径 → 400

### [T-B-03](ServerB/单任务锁/plan.md) 单任务锁
- 已有 running 再 start → 409

### [T-B-04](ServerB/start_status_logs_stop/plan.md) start / status / logs / stop
- 用 NFS 上 `jobs/train.py`；stop 后进程组退出

### [T-B-05](ServerB/打入训练镜像后健康检查/plan.md) 打入 `rsl_rl_isrc:v3` 后健康检查
- 通过后 **T-A-10** 才能对真实 `POST /containers/start` 绿灯

---

## H. 端到端（全部绿灯后才做）

### [T-E2E-01](端到端/登录到任务全链路/plan.md) 登录 → 客户端知 NFS → A 启容器 → B 跑 torchrun
- **依赖**：T-NFS-02、T-A-02、T-B-01、T-E-03
- **步骤**：login → start 指定 `rsl_rl_isrc:v3`（或带 Server B 的后续 tag）→ `POST /tasks/start` → logs → stop
- **状态**：TODO

### [T-E2E-02](端到端/同一容器跑G1_DDP/plan.md) 同一容器跑 G1 DDP
- start 时 `gpu_count: 2`，任务命令为 T-F-02 那条 torchrun
- **状态**：TODO

---

## 推荐执行顺序（未完成项）

```
T-OBS-01 pytest 转发冒烟
T-OBS-02～05 v3-C 镜像与 POST→PUB
T-OBS-06（可选）训练经中继出画面
T-OBS-07 Server A obs_pub_endpoint（A 实现后）
T-NFS-03 bob 隔离
T-NFS-04 重挂
T-A-10 真实 Docker + 健康检查（建议镜像切 v3-C）
T-E2E-01（建议镜像切 v3-C）
```

已完成主路径：**NFS 读写 → GPU torchrun → rsl_rl_isrc:v3 → 2 卡 PPO DDP**。

---

## 失败归属

| 现象 | 先查 |
|------|------|
| `showmount` 失败 | 115 nfs-server / 防火墙 |
| 本机能挂、容器内看不到文件 | bind 路径，不是训练代码 |
| torch 报 sm_120 | 镜像 CUDA 太旧，不是 NFS |
| `/containers/start` 502 | 镜像没有 :8080 `/health` |
| DDP hang / NCCL | `--shm-size` / `--ipc=host` / GPU 数 |
| login 401 | users.yaml 哈希，不是 Docker |
| SUB 画面口无数据 | 转发未起、`--no-zmq-obs`、15557 未映射、RELAY_URL 空 |
| POST 15558 无响应 | `OBS_ENABLE=0`、entrypoint watchdog、查 `docker logs` |
| 老容器无 obs_pub_endpoint | A **不**自动重建；用户 stop 再 start |
