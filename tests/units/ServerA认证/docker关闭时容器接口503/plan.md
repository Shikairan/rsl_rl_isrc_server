# T-A-05 docker 关闭时容器接口 503

## 测什么

docker.enabled=false 时，即使有合法 JWT，start 也返回 503，不碰 Docker。

## 依赖什么

- **依赖**：T-A-02（能登录）。
- **不依赖**：Docker daemon、镜像。

## 前置条件

环境变量 SERVER_A_DOCKER_ENABLED=false（pytest conftest 已设）。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 登录取 token 再 start（docker 关） | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_auth.py::test_containers_disabled_with_token -q` | PASSED，对应该场景 HTTP 503 | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 2 | 手工：先 login 再带 token start | `TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}' \| python -c 'import sys,json;print(json.load(sys.stdin)["token"])')<br>curl -sS -o /tmp/docker_off.json -w '%{http_code}' -X POST http://127.0.0.1:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"example:latest","gpu_count":0}'` | 在 SERVER_A_DOCKER_ENABLED=false 的 uvicorn 下，HTTP 503 | PASS；login HTTP 200；start HTTP 503 body={"detail":{"error":"docker disabled; set server.docker.enabled=true"}} |

## 通过标准

docker 开关关闭时容器 API 为 503 而非 500/真起容器。
