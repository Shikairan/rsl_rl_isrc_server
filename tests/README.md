# 测试索引

现场：NFS `10.250.30.115`，Server A `10.213.35.42`。

- **单元**（一项一能力）：目录在 [`units/`](units/)，总方案 [TEST_PLAN.md](TEST_PLAN.md)。下表链接相对 `units/`。
- **联调**（拆项全链路）：方案在 [`integration/PLAN.md`](integration/PLAN.md)，索引 [`integration/README.md`](integration/README.md)。全部执行：`bash /home/isrc5090/149server/tests/integration/run_all.sh`
- **完整全链路**（登录→挂载→检查→起容器→开训→SUB 画面→看 obs 结果）：[`complete/PLAN.md`](complete/PLAN.md)

# 独立测试用例索引

一项一目录（中文名），目录内：

- `plan.md`：测什么 / 依赖 / 步骤表（含真实结果列）
- `run.sh` / `run.py`：按步骤执行并把真实结果写回 `plan.md`
- `result.log` / `result.json`：最近一次执行的完整记录

总方案：[TEST_PLAN.md](TEST_PLAN.md)

| 编号 | 标题 | 目录 | 脚本 |
|------|------|------|------|
| [T-NFS-01](NFS/导出列表可见/plan.md) | 导出列表可见 | `NFS/导出列表可见/` | [`run.sh`](NFS/导出列表可见/run.sh) |
| [T-NFS-02](NFS/alice读写回115/plan.md) | alice 读写回 115 | `NFS/alice读写回115/` | [`run.sh`](NFS/alice读写回115/run.sh) |
| [T-NFS-03](NFS/bob独立挂载与隔离/plan.md) | bob 独立挂载与隔离 | `NFS/bob独立挂载与隔离/` | [`run.sh`](NFS/bob独立挂载与隔离/run.sh) |
| [T-NFS-04](NFS/卸载后重挂alice/plan.md) | 卸载后重挂 alice | `NFS/卸载后重挂alice/` | [`run.sh`](NFS/卸载后重挂alice/run.sh) |
| [T-NFS-05](NFS/nfs-server重启后导出仍在/plan.md) | nfs-server 重启后导出仍在 | `NFS/nfs-server重启后导出仍在/` | [`run.sh`](NFS/nfs-server重启后导出仍在/run.sh) |
| [T-A-01](ServerA认证/健康检查/plan.md) | 健康检查 | `ServerA认证/健康检查/` | [`run.sh`](ServerA认证/健康检查/run.sh) |
| [T-A-02](ServerA认证/登录成功/plan.md) | 登录成功 | `ServerA认证/登录成功/` | [`run.sh`](ServerA认证/登录成功/run.sh) |
| [T-A-03](ServerA认证/登录失败/plan.md) | 登录失败 | `ServerA认证/登录失败/` | [`run.sh`](ServerA认证/登录失败/run.sh) |
| [T-A-04](ServerA认证/无Token拒绝容器接口/plan.md) | 无 Token 拒绝容器接口 | `ServerA认证/无Token拒绝容器接口/` | [`run.sh`](ServerA认证/无Token拒绝容器接口/run.sh) |
| [T-A-05](ServerA认证/docker关闭时容器接口503/plan.md) | docker 关闭时容器接口 503 | `ServerA认证/docker关闭时容器接口503/` | [`run.sh`](ServerA认证/docker关闭时容器接口503/run.sh) |
| [T-A-06](容器API/start成功_mock/plan.md) | start 成功（mock Docker） | `容器API/start成功_mock/` | [`run.sh`](容器API/start成功_mock/run.sh) |
| [T-A-07](容器API/start幂等_mock/plan.md) | start 幂等（mock） | `容器API/start幂等_mock/` | [`run.sh`](容器API/start幂等_mock/run.sh) |
| [T-A-08](容器API/健康检查失败回收_mock/plan.md) | 健康检查失败回收（mock） | `容器API/健康检查失败回收_mock/` | [`run.sh`](容器API/健康检查失败回收_mock/run.sh) |
| [T-A-09](容器API/current与stop_mock/plan.md) | current 与 stop（mock） | `容器API/current与stop_mock/` | [`run.sh`](容器API/current与stop_mock/run.sh) |
| [T-A-10](容器API/真实Docker_start/plan.md) | 真实 Docker start | `容器API/真实Docker_start/` | [`run.sh`](容器API/真实Docker_start/run.sh) |
| [T-D-01](Docker绑定NFS/容器看见NFS文件/plan.md) | 容器看见 NFS 文件 | `Docker绑定NFS/容器看见NFS文件/` | [`run.sh`](Docker绑定NFS/容器看见NFS文件/run.sh) |
| [T-D-02](Docker绑定NFS/容器写回NFS/plan.md) | 容器写回 NFS | `Docker绑定NFS/容器写回NFS/` | [`run.sh`](Docker绑定NFS/容器写回NFS/run.sh) |
| [T-D-03](Docker绑定NFS/容器挂载用户隔离/plan.md) | 容器挂载用户隔离 | `Docker绑定NFS/容器挂载用户隔离/` | [`run.sh`](Docker绑定NFS/容器挂载用户隔离/run.sh) |
| [T-E-01](torchrun与CUDA/旧镜像CPU_torchrun调度冒烟/plan.md) | 旧镜像 CPU torchrun 调度冒烟 | `torchrun与CUDA/旧镜像CPU_torchrun调度冒烟/` | [`run.sh`](torchrun与CUDA/旧镜像CPU_torchrun调度冒烟/run.sh) |
| [T-E-02](torchrun与CUDA/官方GPU_torchrun/plan.md) | 官方 GPU torchrun | `torchrun与CUDA/官方GPU_torchrun/` | [`run.sh`](torchrun与CUDA/官方GPU_torchrun/run.sh) |
| [T-E-03](torchrun与CUDA/自定义镜像仍能GPU_torchrun/plan.md) | 自定义镜像仍能 GPU torchrun | `torchrun与CUDA/自定义镜像仍能GPU_torchrun/` | [`run.sh`](torchrun与CUDA/自定义镜像仍能GPU_torchrun/run.sh) |
| [T-F-01](rsl_rl_isrc算法/镜像内包可import/plan.md) | 镜像内包可 import | `rsl_rl_isrc算法/镜像内包可import/` | [`run.sh`](rsl_rl_isrc算法/镜像内包可import/run.sh) |
| [T-F-02](rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke/plan.md) | G1 MuJoCo PPO DDP 双卡 smoke | `rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke/` | [`run.sh`](rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke/run.sh) |
| [T-F-03](rsl_rl_isrc算法/DDP扩到4卡/plan.md) | DDP 扩到 4 卡 | `rsl_rl_isrc算法/DDP扩到4卡/` | [`run.sh`](rsl_rl_isrc算法/DDP扩到4卡/run.sh) |
| [T-F-04](rsl_rl_isrc算法/ZMQ观测通道/plan.md) | ZMQ 观测通道（训练内 ObsInstrServer） | `rsl_rl_isrc算法/ZMQ观测通道/` | [`run.sh`](rsl_rl_isrc算法/ZMQ观测通道/run.sh) |
| [T-OBS-01](观测转发/pytest转发冒烟/plan.md) | obsserver pytest 转发冒烟 | `观测转发/pytest转发冒烟/` | [`run.py`](观测转发/pytest转发冒烟/run.py) |
| [T-OBS-02](观测转发/v3-C镜像含obsserver/plan.md) | v3-C 镜像含 obsserver | `观测转发/v3-C镜像含obsserver/` | [`run.py`](观测转发/v3-C镜像含obsserver/run.py) |
| [T-OBS-03](观测转发/容器入口与B并存/plan.md) | 容器入口：转发与 B 并存 | `观测转发/容器入口与B并存/` | [`run.py`](观测转发/容器入口与B并存/run.py) |
| [T-OBS-04](观测转发/POST中继到画面PUB/plan.md) | POST 中继 → 画面 PUB | `观测转发/POST中继到画面PUB/` | [`run.py`](观测转发/POST中继到画面PUB/run.py) |
| [T-OBS-05](观测转发/中继环境变量/plan.md) | 中继环境变量 | `观测转发/中继环境变量/` | [`run.py`](观测转发/中继环境变量/run.py) |
| [T-OBS-06](观测转发/训练开ZMQ经中继出画面/plan.md) | 训练开 ZMQ 经中继出画面（可选） | `观测转发/训练开ZMQ经中继出画面/` | [`run.py`](观测转发/训练开ZMQ经中继出画面/run.py) |
| [T-OBS-07](观测转发/ServerA返回画面地址/plan.md) | Server A 返回 obs_pub_endpoint | `观测转发/ServerA返回画面地址/` | [`run.py`](观测转发/ServerA返回画面地址/run.py) |
| [T-B-01](ServerB/健康检查/plan.md) | Server B 健康检查 | `ServerB/健康检查/` | [`run.sh`](ServerB/健康检查/run.sh) |
| [T-B-02](ServerB/路径守卫/plan.md) | 路径守卫 | `ServerB/路径守卫/` | [`run.sh`](ServerB/路径守卫/run.sh) |
| [T-B-03](ServerB/单任务锁/plan.md) | 单任务锁 | `ServerB/单任务锁/` | [`run.sh`](ServerB/单任务锁/run.sh) |
| [T-B-04](ServerB/start_status_logs_stop/plan.md) | start / status / logs / stop | `ServerB/start_status_logs_stop/` | [`run.sh`](ServerB/start_status_logs_stop/run.sh) |
| [T-B-05](ServerB/打入训练镜像后健康检查/plan.md) | 打入训练镜像后健康检查 | `ServerB/打入训练镜像后健康检查/` | [`run.sh`](ServerB/打入训练镜像后健康检查/run.sh) |
| [T-E2E-01](端到端/登录到任务全链路/plan.md) | 登录到任务全链路 | `端到端/登录到任务全链路/` | [`run.sh`](端到端/登录到任务全链路/run.sh) |
| [T-E2E-02](端到端/同一容器跑G1_DDP/plan.md) | 同一容器跑 G1 DDP | `端到端/同一容器跑G1_DDP/` | [`run.sh`](端到端/同一容器跑G1_DDP/run.sh) |

## 目录分组

- `NFS/`
- `ServerA认证/`
- `容器API/`
- `Docker绑定NFS/`
- `torchrun与CUDA/`
- `rsl_rl_isrc算法/`
- `观测转发/`（T-OBS-01～07，方案见 [obsserver/PLAN.md](../obsserver/PLAN.md)）
- `ServerB/`
- `端到端/`

全部执行：`bash /home/isrc5090/149server/tests/run_all.sh`

## 最近一次批量执行（2026-08-18 16:16）

**39 / 39 通过。** 其中 `T-OBS-01 ~ T-OBS-07` 已纳入 `run_all.sh`；`T-OBS-07` 已验证 `server_b_endpoint + obs_pub_endpoint`、`32xxx->15557/tcp` 映射、TCP 可连与幂等 start。

