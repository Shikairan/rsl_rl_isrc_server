# T-A-07 start 幂等（mock）

## 测什么

注册表已有 running 容器时，再次 start 不执行 docker run，endpoint 不变。

## 依赖什么

- **依赖**：T-A-06 同类 mock 夹具。
- **不依赖**：真实 Docker。

## 前置条件

同上 conda + serverA 目录。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 跑幂等单测 | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_containers.py::test_start_idempotent -q` | PASSED；第二次 start 不调用 docker.run；两次 server_b_endpoint 相同 | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |

## 通过标准

重复 start 幂等，不重复创建容器。
