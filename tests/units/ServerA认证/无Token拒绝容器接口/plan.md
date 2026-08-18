# T-A-04 无 Token 拒绝容器接口

## 测什么

未带 Authorization 的 /containers/start 被 JWT 守卫拒绝。

## 依赖什么

- **依赖**：T-A-01。
- **不依赖**：真实 Docker。

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
| 1 | 不带头调用 start | `curl -sS -o /tmp/no_token.json -w '%{http_code}' -X POST http://127.0.0.1:8000/containers/start -H 'content-type: application/json' -d '{"image":"example:latest","gpu_count":0}'` | HTTP 401 | PASS；HTTP 401 body={"detail":{"error":"missing token"}} |
| 2 | pytest | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_auth.py::test_containers_disabled_without_token -q` | PASSED | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |

## 通过标准

无 Bearer token 时容器接口 401。
