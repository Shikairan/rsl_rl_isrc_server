# T-A-06 start 成功（mock Docker）

## 测什么

start 分配端口、写入注册表、返回 runner-alice 与 server_b_endpoint。不调用真实 docker。

## 依赖什么

- **依赖**：pytest、tests/test_containers.py、MagicMock Docker。
- **不依赖**：真实镜像、NFS、GPU。

## 前置条件

conda activate serverA；cd /home/isrc5090/149server/serverA

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 跑 start 成功单测 | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_containers.py::test_start_success -q` | PASSED；断言 container_name=runner-alice，container_status=running，nfs_mount_path=/workspace，server_b_endpoint 以 10.213.35.42: 开头，且 mock 的 docker.run 被调用一次 | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |

## 通过标准

200 响应结构符合 IMPLEMENTATION_PLAN 的 start 成功体。
