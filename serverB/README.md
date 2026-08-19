# Server B（容器内执行面）

监听 `0.0.0.0:8080`。工作区由 `SERVER_B_WORKSPACE_ROOT` 配置（镜像内默认 `/workspace`）。

镜像入口同时拉起观测转发（本机 HTTP `15558` → 画面 PUB `15557`），见 `obsserver/PLAN.md`。

容器内进程日志写到工作区 NFS：`/workspace/logs/serverB.log`、`/workspace/logs/serverB-access.log`（对应本机 `/mnt/nfs/{用户}/logs/`）。任务 stdout 仍走内存 `GET /tasks/{id}/logs`，结束即释放。

```bash
cd /home/isrc5090/149server/serverB
export SERVER_B_WORKSPACE_ROOT=/tmp/sb-ws
export SERVER_B_LAUNCHER=python3   # 本机冒烟；镜像内默认 torchrun
python -m app --host 0.0.0.0 --port 8080
```

pytest 默认 `SERVER_B_LOG_ENABLED=0`，不写真实 NFS。

打 **v3-C**（v3-B + 观测转发 + 更新后的 Server B）须在 **149server 仓库根**：

```bash
bash serverB/build.sh
# 或：docker build -f serverB/Dockerfile.v3-C -t rsl_rl_isrc:v3-C .
```

`rsl_rl_isrc:v3-B` 不含转发与本轮 B 日志改动，不要覆盖它。已在跑的容器要 `containers/stop` 再 `start` 才会带上新日志。
