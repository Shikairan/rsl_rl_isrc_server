#!/usr/bin/env bash
set -u
ROOT=/home/isrc5090/149server/tests/units
fail=0
echo "===== T-NFS-01 NFS/导出列表可见 ====="
python3 "$ROOT/NFS/导出列表可见/run.py" || fail=1
echo "===== T-NFS-02 NFS/alice读写回115 ====="
python3 "$ROOT/NFS/alice读写回115/run.py" || fail=1
echo "===== T-NFS-03 NFS/bob独立挂载与隔离 ====="
python3 "$ROOT/NFS/bob独立挂载与隔离/run.py" || fail=1
echo "===== T-NFS-04 NFS/卸载后重挂alice ====="
python3 "$ROOT/NFS/卸载后重挂alice/run.py" || fail=1
echo "===== T-NFS-05 NFS/nfs-server重启后导出仍在 ====="
python3 "$ROOT/NFS/nfs-server重启后导出仍在/run.py" || fail=1
echo "===== T-A-01 ServerA认证/健康检查 ====="
python3 "$ROOT/ServerA认证/健康检查/run.py" || fail=1
echo "===== T-A-02 ServerA认证/登录成功 ====="
python3 "$ROOT/ServerA认证/登录成功/run.py" || fail=1
echo "===== T-A-03 ServerA认证/登录失败 ====="
python3 "$ROOT/ServerA认证/登录失败/run.py" || fail=1
echo "===== T-A-04 ServerA认证/无Token拒绝容器接口 ====="
python3 "$ROOT/ServerA认证/无Token拒绝容器接口/run.py" || fail=1
echo "===== T-A-05 ServerA认证/docker关闭时容器接口503 ====="
python3 "$ROOT/ServerA认证/docker关闭时容器接口503/run.py" || fail=1
echo "===== T-A-06 容器API/start成功_mock ====="
python3 "$ROOT/容器API/start成功_mock/run.py" || fail=1
echo "===== T-A-07 容器API/start幂等_mock ====="
python3 "$ROOT/容器API/start幂等_mock/run.py" || fail=1
echo "===== T-A-08 容器API/健康检查失败回收_mock ====="
python3 "$ROOT/容器API/健康检查失败回收_mock/run.py" || fail=1
echo "===== T-A-09 容器API/current与stop_mock ====="
python3 "$ROOT/容器API/current与stop_mock/run.py" || fail=1
echo "===== T-A-10 容器API/真实Docker_start ====="
python3 "$ROOT/容器API/真实Docker_start/run.py" || fail=1
echo "===== T-D-01 Docker绑定NFS/容器看见NFS文件 ====="
python3 "$ROOT/Docker绑定NFS/容器看见NFS文件/run.py" || fail=1
echo "===== T-D-02 Docker绑定NFS/容器写回NFS ====="
python3 "$ROOT/Docker绑定NFS/容器写回NFS/run.py" || fail=1
echo "===== T-D-03 Docker绑定NFS/容器挂载用户隔离 ====="
python3 "$ROOT/Docker绑定NFS/容器挂载用户隔离/run.py" || fail=1
echo "===== T-E-01 torchrun与CUDA/旧镜像CPU_torchrun调度冒烟 ====="
python3 "$ROOT/torchrun与CUDA/旧镜像CPU_torchrun调度冒烟/run.py" || fail=1
echo "===== T-E-02 torchrun与CUDA/官方GPU_torchrun ====="
python3 "$ROOT/torchrun与CUDA/官方GPU_torchrun/run.py" || fail=1
echo "===== T-E-03 torchrun与CUDA/自定义镜像仍能GPU_torchrun ====="
python3 "$ROOT/torchrun与CUDA/自定义镜像仍能GPU_torchrun/run.py" || fail=1
echo "===== T-F-01 rsl_rl_isrc算法/镜像内包可import ====="
python3 "$ROOT/rsl_rl_isrc算法/镜像内包可import/run.py" || fail=1
echo "===== T-F-02 rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke ====="
python3 "$ROOT/rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke/run.py" || fail=1
echo "===== T-F-03 rsl_rl_isrc算法/DDP扩到4卡 ====="
python3 "$ROOT/rsl_rl_isrc算法/DDP扩到4卡/run.py" || fail=1
echo "===== T-F-04 rsl_rl_isrc算法/ZMQ观测通道 ====="
python3 "$ROOT/rsl_rl_isrc算法/ZMQ观测通道/run.py" || fail=1
echo "===== T-OBS-01 观测转发/pytest转发冒烟 ====="
python3 "$ROOT/观测转发/pytest转发冒烟/run.py" || fail=1
echo "===== T-OBS-02 观测转发/v3-C镜像含obsserver ====="
python3 "$ROOT/观测转发/v3-C镜像含obsserver/run.py" || fail=1
echo "===== T-OBS-03 观测转发/容器入口与B并存 ====="
python3 "$ROOT/观测转发/容器入口与B并存/run.py" || fail=1
echo "===== T-OBS-04 观测转发/POST中继到画面PUB ====="
python3 "$ROOT/观测转发/POST中继到画面PUB/run.py" || fail=1
echo "===== T-OBS-05 观测转发/中继环境变量 ====="
python3 "$ROOT/观测转发/中继环境变量/run.py" || fail=1
echo "===== T-OBS-06 观测转发/训练开ZMQ经中继出画面 ====="
python3 "$ROOT/观测转发/训练开ZMQ经中继出画面/run.py" || fail=1
echo "===== T-OBS-07 观测转发/ServerA返回画面地址 ====="
python3 "$ROOT/观测转发/ServerA返回画面地址/run.py" || fail=1
echo "===== T-TB-01 TensorBoard/v3-D镜像含tensorboard ====="
python3 "$ROOT/TensorBoard/v3-D镜像含tensorboard/run.py" || fail=1
echo "===== T-TB-02 TensorBoard/手工映射6006可打开 ====="
python3 "$ROOT/TensorBoard/手工映射6006可打开/run.py" || fail=1
echo "===== T-TB-03 TensorBoard/ServerA返回TB地址 ====="
python3 "$ROOT/TensorBoard/ServerA返回TB地址/run.py" || fail=1
echo "===== T-TB-04 TensorBoard/训练事件后TB可见 ====="
python3 "$ROOT/TensorBoard/训练事件后TB可见/run.py" || fail=1
echo "===== T-TB-05 TensorBoard/alice与bob隔离 ====="
python3 "$ROOT/TensorBoard/alice与bob隔离/run.py" || fail=1
echo "===== T-TB-06 TensorBoard/stop释放端口 ====="
python3 "$ROOT/TensorBoard/stop释放端口/run.py" || fail=1
echo "===== T-B-01 ServerB/健康检查 ====="
python3 "$ROOT/ServerB/健康检查/run.py" || fail=1
echo "===== T-B-02 ServerB/路径守卫 ====="
python3 "$ROOT/ServerB/路径守卫/run.py" || fail=1
echo "===== T-B-03 ServerB/单任务锁 ====="
python3 "$ROOT/ServerB/单任务锁/run.py" || fail=1
echo "===== T-B-04 ServerB/start_status_logs_stop ====="
python3 "$ROOT/ServerB/start_status_logs_stop/run.py" || fail=1
echo "===== T-B-05 ServerB/打入训练镜像后健康检查 ====="
python3 "$ROOT/ServerB/打入训练镜像后健康检查/run.py" || fail=1
echo "===== T-E2E-01 端到端/登录到任务全链路 ====="
python3 "$ROOT/端到端/登录到任务全链路/run.py" || fail=1
echo "===== T-E2E-02 端到端/同一容器跑G1_DDP ====="
python3 "$ROOT/端到端/同一容器跑G1_DDP/run.py" || fail=1
exit "$fail"
