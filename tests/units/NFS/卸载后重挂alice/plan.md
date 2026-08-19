# T-NFS-04 卸载后重挂 alice

## 测什么

本机 umount 后再 mount，挂载源仍指向 115 的 alice 导出。

## 依赖什么

- **依赖**：T-NFS-02（alice 曾经挂成功）。
- **不依赖**：Docker、Server A。

## 前置条件

执行 umount 前确认没有容器占用 /mnt/nfs/alice。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 卸载 alice | `sudo umount /mnt/nfs/alice` | 退出码 0；findmnt /mnt/nfs/alice 无输出 | PASS；退出码 0；findmnt 无挂载 |
| 2 | 按 NFSv4 重新挂载 | `sudo mount -t nfs -o vers=4 10.250.30.115:/mnt/dockerContainer/nfs/alice /mnt/nfs/alice` | 退出码 0 | PASS；退出码 0 |
| 3 | 核对挂载源 | `findmnt -n -o SOURCE,FSTYPE /mnt/nfs/alice` | SOURCE=10.250.30.115:/mnt/dockerContainer/nfs/alice，FSTYPE=nfs4 | PASS；退出码 0；输出：10.250.30.115:/mnt/dockerContainer/nfs/alice nfs4 |
| 4 | 抽查旧文件仍在 | `ls /mnt/nfs/alice/jobs` | 仍能看到此前 jobs 下文件（如 train.py） | PASS；退出码 0；输出：complete_obs_frames.json complete_obs_smoke.py complete_probe.txt from_container.txt g1_ddp4.py last_ddp4.txt last_run.txt nfs_rw.txt obs_iobs02_smoke.py obs_iobs03_smoke.py obs_iobs04_alice.py train.py |

## 通过标准

重挂成功且源地址未变。
