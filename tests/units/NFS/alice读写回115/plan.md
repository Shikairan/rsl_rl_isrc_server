# T-NFS-02 alice 读写回 115

## 测什么

本机挂载 alice 后写入文件，115 磁盘上能读到同一内容（证明 NFSv4 读写通）。

## 依赖什么

- **依赖**：T-NFS-01 通过；本机已 mount 或可现场 mount alice。
- **不依赖**：Docker、Server A、GPU。

## 前置条件

alice 导出路径：10.250.30.115:/mnt/dockerContainer/nfs/alice。本机挂载点 /mnt/nfs/alice。写文件可能需要 sudo。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 查看本机是否已挂载 alice | `findmnt /mnt/nfs/alice` | SOURCE 为 10.250.30.115:/mnt/dockerContainer/nfs/alice，FSTYPE 为 nfs4 | PASS；退出码 0；输出：TARGET SOURCE FSTYPE OPTIONS /mnt/nfs/alice 10.250.30.115:/mnt/dockerContainer/nfs/alice nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=10.213.35.42,local_lock=none,addr=10.250.30.115 |
| 2 | 若未挂载则创建挂载点并挂载 | `sudo mkdir -p /mnt/nfs/alice && sudo mount -t nfs -o vers=4 10.250.30.115:/mnt/dockerContainer/nfs/alice /mnt/nfs/alice` | 命令成功；再次 findmnt 能看到挂载 | PASS；已挂载，未重复执行 mount |
| 3 | 确保 jobs 目录存在并写入测试文件 | `sudo mkdir -p /mnt/nfs/alice/jobs && echo nfs-rw-alice \| sudo tee /mnt/nfs/alice/jobs/nfs_rw.txt` | 本机 cat /mnt/nfs/alice/jobs/nfs_rw.txt 得到 nfs-rw-alice | PASS；退出码 0；本机 cat='nfs-rw-alice'；输出：nfs-rw-alice |
| 4 | 在 115 上核验同一文件 | `ssh kairan@10.250.30.115 'cat /mnt/dockerContainer/nfs/alice/jobs/nfs_rw.txt'` | 输出 nfs-rw-alice，与本机一致 | PASS；退出码 0；输出：nfs-rw-alice |

## 通过标准

本机与 115 读到的文件内容完全一致。
