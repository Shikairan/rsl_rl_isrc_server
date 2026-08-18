# T-A-01 健康检查

## 测什么

Server A 进程启动后 /health 返回 ok。

## 依赖什么

- **依赖**：conda 环境 serverA；149server/serverA 代码。
- **不依赖**：NFS、Docker、GPU。

## 前置条件

```bash
conda activate serverA
cd /home/isrc5090/149server/serverA
export SERVER_A_DOCKER_ENABLED=false
export SERVER_A_NFS_ENABLED=false
# 走 curl 时启动服务；走 pytest 则不必启 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 用 pytest 跑健康检查（推荐，不占 8000 端口） | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_auth.py::test_health -q` | 该用例 PASSED | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 2 | 或启动服务后 curl | `curl -sS http://127.0.0.1:8000/health` | HTTP 200，正文 {"status":"ok"} | PASS；HTTP 200 body={"status":"ok"} |

## 通过标准

health 接口返回 ok。
