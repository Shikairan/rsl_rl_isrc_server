# T-D-01 容器看见 NFS 文件

## 测什么

docker -v /mnt/nfs/alice:/workspace 后，容器内能列出 NFS 上的 train.py。

## 依赖什么

- **依赖**：T-NFS-02；镜像 pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime；本机 docker。
- **不依赖**：Server A、训练是否成功、GPU。

## 前置条件

findmnt /mnt/nfs/alice 已挂上；/mnt/nfs/alice/jobs/train.py 存在。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 确认宿主机文件 | `ls -l /mnt/nfs/alice/jobs/train.py` | 文件存在 | PASS；退出码 0；输出：-rw-rw-r-- 1 isrc5090 isrc5090 2772 Aug 17 18:13 /mnt/nfs/alice/jobs/train.py |
| 2 | 容器内 ls 挂载路径（可不加 --gpus） | `docker run --rm -v /mnt/nfs/alice:/workspace pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime ls -l /workspace/jobs/train.py` | 退出码 0；列出 /workspace/jobs/train.py | PASS；退出码 0；输出：-rw-rw-r-- 1 ubuntu ubuntu 2772 Aug 17 10:13 /workspace/jobs/train.py |

## 通过标准

容器内路径与 NFS 文件对应，不依赖 torchrun。
