# T-A-03 登录失败

## 测什么

错误密码或未知用户返回 401，不签发 token。

## 依赖什么

- **依赖**：T-A-01。
- **不依赖**：Docker、NFS。

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
| 1 | 错密码 | `curl -sS -o /tmp/login_bad.json -w '%{http_code}' -X POST http://127.0.0.1:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"nope"}'` | HTTP 状态码 401；body 含 invalid credentials | PASS；HTTP 401 body={"detail":{"error":"invalid credentials"}} |
| 2 | 未知用户 | `curl -sS -o /tmp/login_unknown.json -w '%{http_code}' -X POST http://127.0.0.1:8000/login -H 'content-type: application/json' -d '{"username":"carol","password":"x"}'` | HTTP 401 | PASS；HTTP 401 body={"detail":{"error":"invalid credentials"}} |
| 3 | pytest | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_auth.py::test_login_wrong_password tests/test_auth.py::test_login_unknown_user -q` | 两例 PASSED | PASS；退出码 0；输出：.. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; instal… |

## 通过标准

两类失败均为 401，无 token。
