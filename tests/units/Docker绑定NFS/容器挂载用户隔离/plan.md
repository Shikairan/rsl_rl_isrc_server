# T-D-03 容器挂载用户隔离

## 测什么

只 bind alice 时，容器内看不到 bob 的文件。

## 依赖什么

- **依赖**：T-NFS-03（bob_only.txt 已存在）；T-D-01。
- **不依赖**：训练。

## 前置条件

先完成 T-NFS-03 写入 /mnt/nfs/bob/bob_only.txt。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 仅挂 alice 进容器并查找 bob 文件 | `docker run --rm -v /mnt/nfs/alice:/workspace pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime bash -lc 'ls /workspace; test ! -f /workspace/bob_only.txt && echo isolated'` | 输出 isolated；ls 无 bob_only.txt | PASS；退出码 0；输出：jobs mount_test.txt rsl_rl_isrc wheels isolated |

## 通过标准

alice 容器工作区不含 bob 文件。
