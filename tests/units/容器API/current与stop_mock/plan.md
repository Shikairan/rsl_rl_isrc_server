# T-A-09 current 与 stop（mock）

## 测什么

无容器时 current/stop 为 404；start 后 current 200；stop 清除记录。

## 依赖什么

- **依赖**：T-A-06 mock 链路。
- **不依赖**：真实 Docker。

## 前置条件

conda activate serverA。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | current 无容器 | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_containers.py::test_current_404 -q` | PASSED，对应 404 | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 2 | current 在 running 时 | `pytest tests/test_containers.py::test_current_running -q` | PASSED，container_name=runner-alice | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 3 | stop 无容器 | `pytest tests/test_containers.py::test_stop_404 -q` | PASSED，404 | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |
| 4 | stop 成功 | `pytest tests/test_containers.py::test_stop_success -q` | PASSED；{"status":"stopped"}；registry 无 alice | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |

## 通过标准

404/200/stopped 行为与方案 4.3 一致。
