# T-E-01 旧镜像 CPU torchrun（调度冒烟）

## 测什么

local/torchrun:0.01 能用 torchrun 执行 NFS 脚本。该镜像 PyTorch 2.4.1 无 sm_120，允许回退 CPU。

## 依赖什么

- **依赖**：T-D-01；镜像 local/torchrun:0.01；jobs/train.py 含 CUDA 架构不匹配则走 CPU。
- **不依赖**：rsl_rl_isrc、DDP、Server A。

## 前置条件

脚本 /mnt/nfs/alice/jobs/train.py 已存在。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 用旧镜像跑 torchrun | `docker run --rm --name runner-alice-old --gpus 1 --cpus 4 --memory 8g -v /mnt/nfs/alice:/workspace local/torchrun:0.01 torchrun --nproc_per_node=1 --standalone /workspace/jobs/train.py --epochs 3` | 退出码 0；日志可出现 sm_120 not in this wheel / using CPU；三轮 epoch 打印；wrote /workspace/jobs/last_run.txt | PASS；退出码 0；输出：========== == CUDA == ========== CUDA Version 12.2.0 Container image Copyright (c) 2016-2023, NVIDIA CORPORATION & AFFILIATES. All rights reserved. This container image and its contents are governed by the NVIDIA Deep Learning Container License. By pulling and using the container, you accept the terms and conditions of this license: https://developer.nvidia… |
| 2 | 读 NFS 结果 | `cat /mnt/nfs/alice/jobs/last_run.txt` | 含 torch=2.4.1+cu121；device=cpu（5090 上预期）；有 loss= | PASS；退出码 0；输出：finished_at=2026-08-18T02:32:21.959445+00:00 device=cpu torch=2.4.1+cu121 loss=1.2146183252334595 |

## 通过标准

证明 NFS+torchrun 调度通，不要求 GPU kernel。
