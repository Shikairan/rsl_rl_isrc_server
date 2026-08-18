# Server B（容器内执行面）

监听 `0.0.0.0:8080`。工作区由 `SERVER_B_WORKSPACE_ROOT` 配置（镜像内默认 `/workspace`）。

镜像入口同时拉起观测转发（本机 HTTP `15558` → 画面 PUB `15557`），见 `obsserver/PLAN.md`。

```bash
cd /home/isrc5090/149server/serverB
export SERVER_B_WORKSPACE_ROOT=/tmp/sb-ws
export SERVER_B_LAUNCHER=python3   # 本机冒烟；镜像内默认 torchrun
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

打 **v3-C**（v3-B + 观测转发）须在 **149server 仓库根**：

```bash
bash serverB/build.sh
# 或：docker build -f serverB/Dockerfile.v3-C -t rsl_rl_isrc:v3-C .
```

`rsl_rl_isrc:v3-B` 不含转发，不要覆盖它。
