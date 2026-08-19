# 观测出口（Obs Server）

容器常驻转发：训练里的 `ObsInstrServer` 把位姿 HTTP POST 到本机，本进程再 PUB 到画面口。

方案全文见 [PLAN.md](PLAN.md)。

## 本进程做什么

- 听 `127.0.0.1:15558/post`（只本机，给中继用）
- 经 `obsserver.transform.transform`（默认原样）后，从 `0.0.0.0:15557` PUB
- 不占训练的 `15555`

以后要改发出格式，只改 `src/obsserver/transform.py` 里的 `transform`。

## 本地测

```bash
cd obsserver
PYTHONPATH=src python3 -m pytest -q
```

冒烟（另开终端 SUB）：

```bash
PYTHONPATH=src python3 -m obsserver
# 然后
curl -sS -X POST http://127.0.0.1:15558/post \
  -H 'content-type: application/json' \
  -d '[[[0,0,0.8],[0,0,0,1],[0]]]'
```

## 打进镜像（以 `v3-B` 为底，新标签 `v3-C`，不覆盖 v3-B）：

```bash
bash serverB/build.sh
# 或在 149server 根目录：
docker build -f serverB/Dockerfile.v3-C -t rsl_rl_isrc:v3-C .
```

入口脚本会后台拉起转发（挂了再拉），再起 Server B。`OBS_ENABLE=0` 可关掉转发。

进程日志写到与 Server B 同一目录：`/workspace/logs/obsserver.log`（用户 NFS）。**不记录画面帧 JSON。** 环境变量 `OBS_LOG_DIR`（默认 `/workspace/logs`）、`OBS_LOG_ENABLED`。已在跑的容器需 stop 再 start。
