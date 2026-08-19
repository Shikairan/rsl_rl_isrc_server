# T-NFS-01 导出列表可见

## 测什么

验证 115 上 nfs-server 正在运行，且本机可以看到 alice/bob 以及导出根目录。

## 依赖什么

- **依赖**：115 已安装 nfs-kernel-server；本机已装 nfs-common（提供 showmount）。
- **不依赖**：Server A、Docker、GPU、conda。

## 前置条件

本机可访问 10.250.30.115:2049/111。不启动 FastAPI。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 在本机查询 NFS 导出列表 | `showmount -e 10.250.30.115` | 命令退出码 0；输出含三路：<br>/mnt/dockerContainer/nfs<br>/mnt/dockerContainer/nfs/alice<br>/mnt/dockerContainer/nfs/bob<br>均对 10.0.0.0/8 导出 | PASS；退出码 0；输出：Export list for 10.250.30.115: /mnt/dockerContainer/nfs/frank 10.0.0.0/8 /mnt/dockerContainer/nfs/eve 10.0.0.0/8 /mnt/dockerContainer/nfs/dave 10.0.0.0/8 /mnt/dockerContainer/nfs/carol 10.0.0.0/8 /mnt/dockerContainer/nfs/bob 10.0.0.0/8 /mnt/dockerContainer/nfs/alice 10.0.0.0/8 /mnt/dockerContainer/nfs 10.0.0.0/8 |
| 2 | 确认 nfs-server 在 115 为 active（可选，SSH 到 115） | `ssh kairan@10.250.30.115 'systemctl is-active nfs-server'` | 输出 active | PASS；退出码 0；输出：active |

## 通过标准

showmount 列出上述三条导出路径。
