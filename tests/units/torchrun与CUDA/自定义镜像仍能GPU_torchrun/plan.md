# T-E-03 rsl_rl_isrc:v3 仍能 GPU torchrun

## 测什么

commit 自定义镜像后，同一 NFS 脚本仍走 cuda:0，CUDA 未被装包破坏。

## 依赖什么

- **依赖**：T-E-02；镜像 rsl_rl_isrc:v3 已构建。
- **不依赖**：PPO、MuJoCo、DDP。

## 前置条件

docker images 能看到 rsl_rl_isrc:v3。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | v3 跑与 T-E-02 相同的 torchrun | `docker run --rm --gpus 1 --cpus 4 --memory 8g -v /mnt/nfs/alice:/workspace rsl_rl_isrc:v3 torchrun --nproc_per_node=1 --standalone /workspace/jobs/train.py --epochs 3` | device=cuda:0；torch=2.11.0+cu128；退出码 0 | PASS；退出码 0；输出：rank=0 local_rank=0 device=cuda:0 torch=2.11.0+cu128 cuda=True nproc=1 epoch=1/3 loss=0.902094 epoch=2/3 loss=0.868031 epoch=3/3 loss=0.963183 wrote /workspace/jobs/last_run.txt |
| 2 | 读 last_run.txt | `cat /mnt/nfs/alice/jobs/last_run.txt` | device=cuda:0；torch=2.11.0+cu128 | PASS；退出码 0；输出：finished_at=2026-08-18T10:59:29.358372+00:00 device=cuda:0 torch=2.11.0+cu128 loss=0.9631833434104919 |

## 通过标准

v3 未破坏 GPU torchrun。
