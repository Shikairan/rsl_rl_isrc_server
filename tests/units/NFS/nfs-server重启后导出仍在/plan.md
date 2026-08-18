# T-NFS-05 nfs-server 重启后导出仍在

## 测什么

115 重启 nfs-server 后，本机 showmount 仍能列出三路导出。

## 依赖什么

- **依赖**：T-NFS-01；SSH 可登录 115 且有 sudo。
- **不依赖**：Server A、Docker。

## 前置条件

操作会短暂中断 NFS。若本机已挂载，重启后可能需重挂（属 T-NFS-04）。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 重启前记录导出 | `showmount -e 10.250.30.115` | 三条导出路径存在 | PASS；退出码 0；输出：Export list for 10.250.30.115: /mnt/dockerContainer/nfs/bob 10.0.0.0/8 /mnt/dockerContainer/nfs/alice 10.0.0.0/8 /mnt/dockerContainer/nfs 10.0.0.0/8 |
| 2 | 在 115 上重启 NFS 服务 | `ssh kairan@10.250.30.115 'sudo systemctl restart nfs-server && systemctl is-active nfs-server'` | 输出 active | PASS；退出码 0；输出：active |
| 3 | 本机再次查询导出 | `showmount -e 10.250.30.115` | 仍列出 /mnt/dockerContainer/nfs 及其 alice、bob 子路径 | PASS；退出码 0；输出：Export list for 10.250.30.115: /mnt/dockerContainer/nfs/bob 10.0.0.0/8 /mnt/dockerContainer/nfs/alice 10.0.0.0/8 /mnt/dockerContainer/nfs 10.0.0.0/8 |

## 通过标准

重启后导出列表与重启前一致。
