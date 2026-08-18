# Server A（本机 conda 环境 `serverA`）

当前：登录 + 容器 start/current/stop。`nfs.enabled=false`（不强制启动挂载），`docker.enabled=true`。

```bash
conda activate serverA
cd /home/isrc5090/149server/serverA
pip install -r requirements.txt
pytest
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

验证用户（密码均为 `{user}-dev`）：`alice`、`bob`、`carol`、`dave`、`eve`、`frank`。
客户端接入见仓库 [`docs/CLIENT.md`](../docs/CLIENT.md)。

```bash
TOKEN=$(curl -s -X POST localhost:8000/login \
  -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' | python -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -X POST localhost:8000/containers/start \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"python:3.11-slim","gpu_count":0}'
```

镜像需在 8080 提供 `GET /health`（Server B 契约）。健康检查失败会 `docker rm -f` 并返回 502。
本机用户需在 `docker` 组才能访问 Docker socket。
