# T-E-02 官方 2.11+cu128 GPU torchrun

## 测什么

pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime 在 RTX 5090 上以 cuda:0 跑同一 NFS 脚本。

## 依赖什么

- **依赖**：T-D-01；已 docker pull 该镜像。
- **不依赖**：rsl_rl_isrc、DDP、Server A。

## 前置条件

nvidia-container-toolkit 可用。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 确认镜像存在 | `docker images pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime` | 有一行 REPOSITORY/TAG 匹配 | PASS；退出码 0；输出：pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime |
| 2 | GPU torchrun | `docker run --rm --gpus 1 --cpus 4 --memory 8g -v /mnt/nfs/alice:/workspace pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime torchrun --nproc_per_node=1 --standalone /workspace/jobs/train.py --epochs 3` | 日志含 device=cuda:0 torch=2.11.0+cu128 cuda=True；退出码 0；无 sm_120 不兼容报错 | PASS；退出码 0；输出：rank=0 local_rank=0 device=cuda:0 torch=2.11.0+cu128 cuda=True nproc=1 epoch=1/3 loss=0.986431 epoch=2/3 loss=0.895200 epoch=3/3 loss=1.055445 wrote /workspace/jobs/last_run.txt |
| 3 | 核对 last_run.txt | `cat /mnt/nfs/alice/jobs/last_run.txt` | device=cuda:0；torch=2.11.0+cu128 | PASS；退出码 0；输出：finished_at=2026-08-18T02:32:27.546778+00:00 device=cuda:0 torch=2.11.0+cu128 loss=1.055444598197937 |

## 通过标准

5090 上真正用 CUDA 跑完 3 epoch。
