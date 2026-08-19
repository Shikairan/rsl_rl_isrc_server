# T-OBS-06 训练开 ZMQ，经中继出画面（可选）

## 测什么

在 `v3-C` 容器内跑 **极短** G1 DDP smoke（**不要** `--no-zmq-obs`），rank0 起 `ObsInstrServer` 且中继 URL 已设；宿主机 SUB 画面口能在训练 step 期间收到至少一帧（JSON 数组，最多 64 机器人行）。

## 依赖什么

- **依赖**：T-OBS-04、T-F-02；镜像 `rsl_rl_isrc:v3-C`；GPU ≥2；`--shm-size=16g --ipc=host`。
- **不依赖**：Server A、NFS。

## 前置条件

15555/15556/15557/15558 映射策略：

- **15557** 映射到宿主机供 SUB。
- **15555/15556 不要**映射到宿主机（仍只在容器内给训练用）。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 起容器（GPU） | `sg docker -c 'docker run -d --name obs-train --gpus 2 --shm-size=16g --ipc=host -p 127.0.0.1:15557:15557 rsl_rl_isrc:v3-C'` | running | PASS；退出码 0；输出：0877546d7dcf38359d74ec475a302f9b1d90ca387b6ea51b8b0ff21c1c55ea0a |
| 2 | 宿主机 SUB 后台 | 同 T-OBS-04 SUB 脚本，超时 ≥60s | — | PASS；退出码 0；输出：[[[0.8647451400756836, 0.3887401521205902, 0.7984024286270142], [-0.015115750022232533, 0.006550956051796675, 0.00015763593546580523, 0.9998642802238464], [-0.04433643817901611, 0.09725047647953033, 0.09105551242828369, 0.31314772367477417, -0.20392243564128876, -0.021056275814771652, -0.026255184784531593, 0.08008196949958801, 0.07164422422647476, 0.042632… |
| 3 | 极短 DDP + zmq obs | `sg docker -c 'docker exec -w /opt/rsl_rl_isrc obs-train torchrun --standalone --nproc_per_node=2 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 8 --max-iterations 1'` | 退出码 0；日志含 ObsInstrServer PULL/REP | PASS；退出码 0；输出：obs-train |
| 4 | SUB 收到帧 | 查看 SUB 输出 | 非空 JSON 数组；元素为 `[pos,quat,dof]` 行 |  |
| 5 | 清理 | `sg docker -c 'docker stop obs-train'` | 退出 |  |

## 通过标准

训练不卡死、SUB 至少一帧。若 SUB 无帧：查是否误加 `--no-zmq-obs`、RELAY_URL 是否为空、转发是否起来。

## 说明

- 比 T-OBS-04 多一层：**ObsInstrServer → HTTP 中继 → 转发 PUB**。
- 仍属单元（手工 docker），不是 `POST /containers/start` 主路径；全链路见 integration/complete 后续用 `v3-C` 增补。
