# Server A（本机 conda 环境 `serverA`）

当前：登录 + 容器 start/current/stop。`nfs.enabled=false`（不强制启动挂载），`docker.enabled=true`。

```bash
conda activate serverA
cd /home/isrc5090/149server/serverA
pip install -r requirements.txt
pytest
# 推荐入口（先装配落盘日志，再起 uvicorn，且 log_config=None）
python -m app --host 0.0.0.0 --port 8017
```

若直接 `uvicorn app.main:app ...`，uvicorn 可能覆盖 logging 配置，访问日志可能只在终端；生产/联调请用 `python -m app`。

验证用户（密码均为 `{user}-dev`）：`alice`、`bob`、`carol`、`dave`、`eve`、`frank`。
客户端接入见仓库 [`docs/CLIENT.md`](../docs/CLIENT.md)。

```bash
TOKEN=$(curl -s -X POST localhost:8017/login \
  -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' | python -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -X POST localhost:8017/containers/start \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"python:3.11-slim","gpu_count":0}'
```

镜像需在 8080 提供 `GET /health`（Server B 契约）。健康检查失败会 `docker rm -f` 并返回 502。
本机用户需在 `docker` 组才能访问 Docker socket。

## 落盘日志

配置见 `config/server.yaml` 的 `logging` 段。默认写到 `serverA/logs/`：

| 文件 | 内容 |
|------|------|
| `logs/serverA.log` | 应用日志（启动、NFS、容器 start/stop、登录成败等） |
| `logs/access.log` | HTTP 访问行（method path status duration user）；**不记** Authorization / body / 密码 |

```bash
tail -f logs/serverA.log logs/access.log
```

轮转：`max_bytes`（默认 10MB）× `backup_count`（默认 5）。写盘失败时进程继续跑，最多丢日志行。

环境变量：

- `SERVER_A_LOG_ENABLED` — `false` 关闭落盘（pytest 默认关）
- `SERVER_A_LOG_DIR` — 日志目录
- `SERVER_A_LOG_LEVEL` — 如 `INFO` / `DEBUG`
