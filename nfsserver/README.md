# nfsserver — 115 NFS 控制面（不跑 FastAPI）

本机开发，通过 SSH 应用到 `10.250.30.115`。

```bash
conda activate serverA   # 仅需 PyYAML；apply 还用本机 sshpass
cd /home/isrc5090/149server/nfsserver
python nfsctl.py render
python nfsctl.py showmount
python nfsctl.py status
python nfsctl.py apply
python nfsctl.py add-user gina    # 改本地 config 后需再 apply；已有 alice/bob/carol/dave/eve/frank
```

用户目录定义在 `config/users.yaml`。SSH 账号读上级目录 `115ssh`，不要写进本仓库脚本。
客户端挂载与调用见仓库 [`docs/CLIENT.md`](../docs/CLIENT.md)。
