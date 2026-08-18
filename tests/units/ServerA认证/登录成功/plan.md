# T-A-02 登录成功

## 测什么

alice 正确密码登录，签发 JWT，并返回 115 上的真实 NFS 路径。

## 依赖什么

- **依赖**：T-A-01 能起服务；config/users.yaml 中 alice 哈希对应 alice-dev。
- **不依赖**：容器、GPU、真实 mount。

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
| 1 | pytest 登录成功用例 | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_auth.py::test_login_success -q` | PASSED | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 2 | curl 登录 | `curl -sS -X POST http://127.0.0.1:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | HTTP 200；JSON 含 token、expires_at；nfs_host=10.250.30.115；nfs_export_path=/mnt/dockerContainer/nfs/alice | PASS；HTTP 200 nfs_host=10.250.30.115 nfs_export_path=/mnt/dockerContainer/nfs/alice token=有 expires_at=2026-08-19T02:31:55.883039Z |

## 通过标准

拿到 JWT 且 NFS 字段为现场真实路径，不是文档占位 IP。
