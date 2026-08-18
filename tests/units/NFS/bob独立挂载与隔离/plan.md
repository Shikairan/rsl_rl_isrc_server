# T-NFS-03 bob 独立挂载与隔离

## 测什么

bob 目录可独立挂载、可写；alice 挂载点看不到 bob 的文件。

## 依赖什么

- **依赖**：T-NFS-01；115 已导出 /mnt/dockerContainer/nfs/bob。
- **不依赖**：alice 里已有训练文件、Docker、Server A。

## 前置条件

本机尚未常挂 bob。需要 sudo 挂载。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 创建 bob 挂载点并挂载 | `sudo mkdir -p /mnt/nfs/bob && sudo mount -t nfs -o vers=4 10.250.30.115:/mnt/dockerContainer/nfs/bob /mnt/nfs/bob` | findmnt /mnt/nfs/bob 源为 10.250.30.115:/mnt/dockerContainer/nfs/bob | PASS；退出码 0；SOURCE=10.250.30.115:/mnt/dockerContainer/nfs/bob；输出：TARGET SOURCE FSTYPE OPTIONS /mnt/nfs/bob 10.250.30.115:/mnt/dockerContainer/nfs/bob nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=10.213.35.42,local_lock=none,addr=10.250.30.115 |
| 2 | 只在 bob 下写隔离文件 | `echo bob-only \| sudo tee /mnt/nfs/bob/bob_only.txt` | 本机 cat /mnt/nfs/bob/bob_only.txt 为 bob-only | PASS；退出码 0；cat='bob-only'；输出：bob-only |
| 3 | 确认 alice 挂载点看不到该文件 | `test ! -f /mnt/nfs/alice/bob_only.txt && echo isolated` | 输出 isolated；ls /mnt/nfs/alice 无 bob_only.txt | PASS；退出码 0；输出：isolated |
| 4 | 115 上确认文件只在 bob 导出目录 | `ssh kairan@10.250.30.115 'ls /mnt/dockerContainer/nfs/bob/bob_only.txt; test ! -f /mnt/dockerContainer/nfs/alice/bob_only.txt && echo ok'` | bob 路径存在；alice 下没有该文件；输出 ok | PASS；退出码 0；输出：/mnt/dockerContainer/nfs/bob/bob_only.txt ok |

## 通过标准

bob 可读写；alice 与 bob 文件互不可见。
