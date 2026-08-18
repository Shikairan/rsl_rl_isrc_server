# T-D-02 容器写回 NFS

## 测什么

容器内写入 /workspace/jobs 的文件，本机 NFS 挂载点立刻可见。

## 依赖什么

- **依赖**：T-D-01。
- **不依赖**：Server A、GPU。

## 前置条件

alice 已挂载且目录可写（0777 或当前用户可写）。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 容器内写标记文件 | `docker run --rm -v /mnt/nfs/alice:/workspace pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime bash -lc 'echo from-container > /workspace/jobs/from_container.txt'` | 退出码 0 | PASS；退出码 0 |
| 2 | 本机读取 | `cat /mnt/nfs/alice/jobs/from_container.txt` | 内容为 from-container | PASS；退出码 0；输出：from-container |
| 3 | 可选：115 上读取 | `ssh kairan@10.250.30.115 'cat /mnt/dockerContainer/nfs/alice/jobs/from_container.txt'` | 同样为 from-container | PASS；退出码 0；输出：from-container |

## 通过标准

三处（容器写、本机、115）内容一致。此前 last_run.txt 也可作为旁证。
